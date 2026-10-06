"""Local adapter for the collaborator UI. The existing core owns persistence."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .analysis import APIError, DIMENSIONS, call_chat, check_connection, grade
from .archives import ArchiveStore, latest_window
from .batch_analysis import explain_messages
from .core import Message, Transcript
from .history_analysis import effective_rating, progress_summary, time_bounds
from .history_runner import run_history
from .importers import MAX_FILE, load_file, load_sqlite, sqlite_tables
from .storage import SettingsStore
from .affinity import AffinityStore
from .affinity_runner import run_affinity
from .comprehensive import run_comprehensive
from .wechat_workflow import WechatWorkflow

VERSION = '2.8.1'
SETTING_FIELDS = {'mode':'mode', 'chatUrl':'chat_url', 'chatModel':'chat_model',
    'jevUrl':'jev_url', 'jevModel':'jev_model', 'rememberKeys':'remember_keys',
    'autoAnalyze':'auto_analyze', 'interval':'interval', 'cooldown':'cooldown',
    'fontFamily':'font_family', 'chatFontSize':'chat_font_size', 'accent':'theme',
    'surface':'surface_scheme', 'goal':'goal', 'style':'style', 'selfOnRight':'self_on_right'}
WEB_DEFAULTS = {'theme':'light', 'fontSize':'default', 'reducedMotion':False,
                'hapticSound':False, 'guideDone':False}


class LocalService:
    def __init__(self, directory=None):
        self.config = SettingsStore(directory)
        self.directory = self.config.directory
        self.settings = self.config.load()
        self.config_stamp = self._settings_stamp()
        self.store = ArchiveStore(self.directory)
        self.affinity = AffinityStore(self.store)
        self.self_affinity = AffinityStore(self.store, 'self')
        self.lock = threading.RLock()
        self.previews, self.tasks, self.native = {}, {}, None
        self.wechat = WechatWorkflow(self)
        self.preferences = dict(WEB_DEFAULTS)
        try:
            saved = json.loads((self.directory/'web-preferences.json').read_text(encoding='utf-8'))
            self.preferences.update({k:saved[k] for k in WEB_DEFAULTS if k in saved})
        except (OSError, ValueError, TypeError): pass

    def safe_error(self, error):
        text = str(error) if isinstance(error,(ValueError,APIError)) else '操作失败，请检查接口地址、密钥、网络或文件格式后重试。'
        for key in (self.settings.chat_key, self.settings.jev_key):
            if key: text = text.replace(key, '[密钥已隐藏]')
        return text[:600]

    def _settings_stamp(self):
        try:
            info = self.config.path.stat()
            return info.st_mtime_ns, info.st_size
        except FileNotFoundError: return None

    def _refresh_settings(self):
        stamp = self._settings_stamp()
        if stamp!=self.config_stamp:
            self.settings = self.config.load()
            self.config_stamp = stamp

    def settings_view(self):
        with self.lock:
            self._refresh_settings()
            return {**{key:getattr(self.settings, field) for key,field in SETTING_FIELDS.items()},
                **self.preferences, 'chatKey':'', 'jevKey':'',
                'hasChatKey':bool(self.settings.chat_key), 'hasJevKey':bool(self.settings.jev_key),
                'useDpapi':True, 'version':VERSION}

    def save_settings(self, body):
        with self.lock:
            self._refresh_settings()
            candidate = replace(self.settings, **{field:body[key] for key,field in SETTING_FIELDS.items() if key in body})
            for web, field in (('chatKey','chat_key'), ('jevKey','jev_key')):
                if body.get(web): setattr(candidate, field, str(body[web]).strip())
                if body.get('clear'+web[0].upper()+web[1:]): setattr(candidate, field, '')
            candidate.validate(require_keys=False)
            preferences = {**self.preferences, **{k:body[k] for k in WEB_DEFAULTS if k in body}}
            if preferences['theme'] not in ('light','dark','system') or preferences['fontSize'] not in ('dense','default','relaxed'):
                raise ValueError('外观选项无效。')
            if candidate != self.settings:
                self.config.save(candidate)
            self.config_stamp = self._settings_stamp()
            temporary = self.directory/'web-preferences.tmp'
            temporary.write_text(json.dumps(preferences, ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.directory/'web-preferences.json')
            self.settings, self.preferences = candidate, preferences
            return self.settings_view()

    @staticmethod
    def message_view(entry):
        m, r = entry.message, effective_rating(entry)
        return {'id':entry.id, 'speaker':m.speaker, 'text':m.text, 'timestamp':m.timestamp,
            'senderName':m.sender_id, 'messageId':m.message_id, 'confidence':m.confidence,
            'done':entry.done, 'rating':None if not r else {**r,'affinityDelta':r.get('affinity_delta'), 'grade':grade(r.get('score'))},
            'issue':entry.issue, 'explanation':None if not entry.explanation else {
                **entry.explanation,'createdAt':entry.explanation.get('created_at','')}}

    @staticmethod
    def profile_view(p):
        return {'id':p.id, 'name':p.name, 'platform':p.platform, 'avatarText':p.name[:1],
            'avatarBg':'from-indigo-500/20 to-purple-500/20 text-indigo-400 border-indigo-500/30',
            'conversationKey':p.conversation_key, 'selfIdentity':p.self_identity,
            'messageCount':p.count, 'lastActive':'本机存档', 'healthSignal':None,
            'signalLabel':'真实档案 · 选择后查看评分'}

    def summary(self, entries):
        stats = progress_summary(entries)
        boundary = max((effective_rating(e).get('boundary',0) for e in entries[-10:] if effective_rating(e)), default=0)
        return {'summary':f"当前范围共 {stats['total']} 条文字，已评分 {stats['analyzed']} 条。",
            'selfLogic':'点击消息后可按需解释；批量评分不会自动调用 DeepSeek。',
            'otherLogic':'六维互动积极度与好感度分开；好感度只在你主动选择后由 DeepSeek 计算。',
            'overallScore':stats['score'], 'boundaryAlert':boundary>=.8, 'boundaryProbability':boundary,
            'shouldWait':boundary>=.8, 'cautions':['互动分数不表示对方真实喜欢的概率。'], 'replies':[],
            'dimensions':[{'key':k,'name':v[0],'weight':v[1], 'description':v[2],
                'score':stats['dimensions'][k], 'confidence':1 if stats['dimensions'][k] is not None else 0,
                'evidence':'来自本机已保存评分的加权汇总。'} for k,v in DIMENSIONS.items()],
            'evaluatedAt':'本机存档', 'model':self.settings.mode}

    def messages(self, query):
        profile = query.get('profile',''); self.store.profile(profile)
        start, end = time_bounds(query.get('start',''), query.get('end',''))
        entries = self.store.entries(profile, start, end)
        offset = max(0,int(query.get('offset',0))); limit = min(200,max(1,int(query.get('limit',100))))
        return {'profileId':profile, 'messages':[self.message_view(e) for e in entries[offset:offset+limit]],
            'total':len(entries), 'offset':offset, 'limit':limit, 'analysis':self.summary(entries),
            'lastRun':self.store.last_run(profile), 'affinity':self.affinity.view(profile,entries),
            'selfAffinity':self.self_affinity.view(profile,entries)}

    def preview_import(self, body):
        name = str(body.get('name','')).replace('\\','/').rsplit('/',1)[-1]
        suffix = Path(name).suffix.lower()
        if ':' in name or name.split('.',1)[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise ValueError('文件名无效，请重命名后导入。')
        if suffix not in ('.json','.jsonl','.txt','.csv','.html','.htm','.sqlite','.sqlite3','.db'):
            raise ValueError('请选择 JSON、JSONL、TXT、CSV、HTML 或明文 SQLite 文件。')
        try: data = base64.b64decode(body.get('data',''),validate=True)
        except (ValueError,TypeError): raise ValueError('文件传输内容无效。') from None
        if not data or len(data)>MAX_FILE: raise ValueError('文件为空或超过150MB，请拆分后导入。')
        with tempfile.TemporaryDirectory(prefix='chat1-import-') as directory:
            path = Path(directory)/name; path.write_bytes(data)
            if suffix in ('.sqlite','.sqlite3','.db'):
                if not body.get('table'): return {'schema':sqlite_tables(path),'name':name}
                bundle = load_sqlite(path,body['table'],body.get('mapping',{}),body.get('textType',''))
            else: bundle = load_file(path)
        for index, conversation in enumerate(bundle.conversations):
            # Only an identical export automatically dedupes. Partial/new exports
            # require an explicit destination, never a filename-based identity guess.
            conversation.key = 'import:' + hashlib.sha256(data).hexdigest()[:24] + ':' + str(index) + ':' + conversation.key[:120]
            if conversation.name == '导入会话': conversation.name = Path(name).stem
        identity = uuid.uuid4().hex
        with self.lock:
            self.previews = {k:v for k,v in self.previews.items() if time.monotonic()-v[0]<1800}
            if len(self.previews)>=3: self.previews.pop(next(iter(self.previews)))
            self.previews[identity] = (time.monotonic(),bundle)
        return {'id':identity,'warnings':bundle.warnings,'conversations':[
            {'index':i,'key':c.key,'name':c.name,'platform':c.platform,'owner':c.owner,
             'speakers':c.identities(),'count':len(c.messages),'isGroup':c.is_group,
             'speakerNames':{m.sender:m.display_name or m.sender for m in c.messages},
             'sample':[{'sender':m.display_name or m.sender,'text':m.text} for m in c.messages[:5]]}
             for i,c in enumerate(bundle.conversations)]}

    def commit_import(self, body):
        with self.lock:
            preview = self.previews.get(body.get('importId'))
            if not preview: raise ValueError('导入预览已过期，请重新选择文件。')
            conversations = preview[1].conversations; index = int(body.get('conversation',0))
            if not 0<=index<len(conversations): raise ValueError('请选择有效的会话。')
            c = conversations[index]; identity = str(body.get('self','')); messages = c.choose_self(identity)
            name = str(body.get('name') or c.name).strip()[:120]
            p = self.store.profile(body['profileId']) if body.get('profileId') else next((p for p in self.store.profiles() if p.conversation_key==c.key and p.self_identity==identity),None)
            if p and p.self_identity!=identity: raise ValueError('已有档案的我方身份与当前选择不同，请确认或新建档案。')
            if not p: p = self.store.create(name,c.platform,c.key,identity)
            added = self.store.import_messages(p.id,messages)
            self.wechat.imported(body.get('importId'))
            return {'profileId':p.id,'added':added,'total':self.store.profile(p.id).count}

    def task_view(self, identity):
        with self.lock:
            if identity not in self.tasks: raise ValueError('任务不存在。')
            return {k:v for k,v in self.tasks[identity].items() if k not in ('thread','cancel')}

    def wait_task(self, identity, timeout=180): self.tasks[identity]['thread'].join(timeout)

    def start_task(self, kind, body):
        perspective = body.get('perspective', 'other')
        if kind in ('affinity', 'comprehensive') and perspective not in ('other', 'self'):
            raise ValueError('分析视角无效。')
        if kind in ('affinity', 'comprehensive') and body.get('calculate') is not True:
            raise ValueError('好感度不会自动计算，请主动选择计算后再开始。')
        profile = str(body.get('profile',''))
        if kind == 'comprehensive':
            affinity_store = self.self_affinity if perspective == 'self' else self.affinity
            if not affinity_store.view(profile)['comprehensiveReady']:
                raise ValueError('全部聊天记录分析完成后才能开放综合分析。')
        with self.lock:
            self.store.profile(profile)
            self._refresh_settings()
            if any(t['state']=='running' and t['profile']==profile for t in self.tasks.values()):
                raise ValueError('当前联系人已有任务运行，请等待或暂停后再操作。')
            settings = replace(self.settings)
            (replace(settings,mode='TypeSafe Jev') if kind=='score' and settings.mode!='DeepSeek'
             else replace(settings,mode='DeepSeek') if kind!='score' else settings).validate()
            start,end = time_bounds(body.get('start',''),body.get('end',''))
            entries = self.store.run_entries(body['runId']) if kind=='score' and body.get('runId') else self.store.entries(profile,start,end)
            if kind == 'comprehensive': entries = self.store.entries(profile)
            if body.get('runId') and self.store.run_info(body['runId'])['profile_id']!=profile:
                raise ValueError('续做任务不属于当前联系人。')
            if not entries: raise ValueError('当前范围没有文字消息。')
            identity = uuid.uuid4().hex
            task = {'id':identity,'profile':profile,'kind':kind,'state':'running','completed':0,
                'total':len(entries),'error':'','notices':[],'cancel':threading.Event()}
            if kind=='affinity':
                affinity_store = self.self_affinity if perspective == 'self' else self.affinity
                task.update(total=min(100,len(affinity_store.pending(profile,entries))), perspective=perspective)
            if kind == 'comprehensive': task['perspective'] = perspective
            task.update(start=body.get('start',''),end=body.get('end',''))
            if len(self.tasks)>=30:
                finished = next((k for k,t in self.tasks.items() if t['state']!='running'), None)
                if finished: self.tasks.pop(finished)
            self.tasks[identity] = task
            def update(event,data):
                with self.lock:
                    task.update({k:data[k] for k in ('run_id','completed','total') if k in data})
                    for row in data.get('results',[]):
                        if row.get('issue'):
                            at = next(i for i,e in enumerate(entries) if e.id==row['entry_id'])
                            task['notices'].append({'page':at//100+1,'entryId':row['entry_id'],'reason':row['issue']['reason']})
            def work():
                try:
                    if kind=='score':
                        result = run_history(self.store,settings,profile,entries,
                            body.get('start',''),body.get('end',''),force=False,
                            run_id=body.get('runId') or None,cancel=task['cancel'],on_progress=update)
                        with self.lock: task.update(result)
                    elif kind=='explain':
                        chosen = set(body.get('ids',[]))
                        positions = [i for i,e in enumerate(entries) if e.id in chosen and not e.explanation]
                        if not chosen or len(chosen)>100: raise ValueError('请选择1到100条消息解释。')
                        if not chosen.issubset({e.id for e in entries}): raise ValueError('所选消息不属于当前范围。')
                        groups, group, length = [], [], 0
                        for index in positions:
                            size = len(entries[index].message.text)+50
                            if size>32000: raise ValueError('所选单条文字超过解释预算，请缩短后解释。')
                            if group and (len(group)>=10 or length+size>32000):
                                groups.append(group); group=[]; length=0
                            group.append(index); length+=size
                        if group: groups.append(group)
                        with self.lock: task['total']=len(positions)
                        for group in groups:
                            if task['cancel'].is_set(): break
                            rows = explain_messages(settings,entries,group)
                            self.store.save_explanations(profile,rows)
                            with self.lock: task['completed']+=len(rows)
                        with self.lock: task['state']='paused' if task['cancel'].is_set() else 'completed'
                    elif kind=='reply':
                        transcript = Transcript(latest_window([e.message for e in entries]),'所选档案范围')
                        result = call_chat(replace(settings,mode='DeepSeek',vision=False),transcript)
                        summary = self.summary(entries)
                        summary.update(summary=result.summary,selfLogic=result.self_logic,otherLogic=result.other_logic,
                            replies=result.replies,cautions=result.cautions,shouldWait=result.should_wait,model=result.source)
                        with self.lock: task.update(state='completed',analysis=summary)
                    elif kind=='comprehensive':
                        def comprehensive_progress(data):
                            with self.lock: task.update(data)
                        result = run_comprehensive(self.store,settings,profile,task['cancel'],comprehensive_progress,perspective=perspective)
                        with self.lock: task.update(state='paused' if result is None else 'completed', comprehensive=result)
                    elif kind=='affinity':
                        def affinity_progress(data):
                            with self.lock: task.update(data)
                        result = run_affinity(self.store,settings,profile,entries,task['cancel'],affinity_progress,perspective=perspective)
                        with self.lock: task.update(state='paused' if task['cancel'].is_set() else 'completed',affinity=result)
                    else: raise ValueError('任务类型无效。')
                except Exception as error:
                    with self.lock: task.update(state='error',error=self.safe_error(error))
            thread = threading.Thread(target=work,daemon=True)
            task['thread']=thread; thread.start()
            return self.task_view(identity)

    def delete_profile(self, body):
        identity = body.get('id')
        if not isinstance(identity, str) or not identity:
            raise ValueError('请选择要删除的联系人档案。')
        with self.lock:
            if any(t['profile'] == identity and t['state'] == 'running' for t in self.tasks.values()):
                raise ValueError('该联系人正在分析，请先等待或暂停任务。')
            self.store.delete(identity)
            self.tasks = {key: task for key, task in self.tasks.items() if task['profile'] != identity}
        return {'deleted': identity}

    def native_workspace(self):
        with self.lock:
            if self.native is None or self.native.poll() is not None:
                command = [sys.executable,'--desktop'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve().parent.parent/'main.py'),'--desktop']
                self.native = subprocess.Popen(command,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'opened':True}

    def get(self,route,query):
        if route=='/api/settings': return self.settings_view()
        if route=='/api/profiles': return {'profiles':[self.profile_view(p) for p in self.store.profiles()]}
        if route=='/api/messages': return self.messages(query)
        if route=='/api/wechat/active': return self.wechat.active()
        if route.startswith('/api/wechat/jobs/'):
            return self.wechat.view(route.rsplit('/',1)[-1])
        if route.startswith('/api/jobs/'): return self.task_view(route.rsplit('/',1)[-1])
        if route=='/api/health': return {'version':VERSION,'storage':'SQLite','realBackend':True}
        raise ValueError('接口不存在。')

    def post(self,route,body):
        if route=='/api/settings': return self.save_settings(body)
        if route=='/api/profiles/delete': return self.delete_profile(body)
        if route=='/api/import/preview': return self.preview_import(body)
        if route=='/api/import/commit': return self.commit_import(body)
        if route.startswith('/api/jobs/') and route.rsplit('/',1)[-1] in ('score','explain','reply','affinity','comprehensive'):
            return self.start_task(route.rsplit('/',1)[-1],body)
        if route=='/api/jobs/pause':
            with self.lock:
                task = self.tasks.get(body.get('id'))
                if not task: raise ValueError('任务不存在。')
                task['cancel'].set()
            return self.task_view(task['id'])
        if route=='/api/messages':
            profile = str(body.get('profile','')); self.store.profile(profile)
            text = str(body.get('text','')).strip(); speaker = body.get('speaker')
            if not text or len(text)>10000 or speaker not in ('我','对方'): raise ValueError('请输入有效文字并确认发言人。')
            m = Message(speaker,text,timestamp=datetime.now(timezone.utc).isoformat(),message_id=uuid.uuid4().hex,origin='手动补充')
            return {'added':self.store.import_messages(profile,[m])}
        if route=='/api/connection':
            provider = body.get('provider')
            if provider not in ('DeepSeek','TypeSafe Jev'): raise ValueError('请选择有效的接口。')
            draft = body.get('settings') or {}
            candidate = replace(self.settings, **{field:draft[key] for key,field in SETTING_FIELDS.items() if key in draft})
            for web,field in (('chatKey','chat_key'),('jevKey','jev_key')):
                if draft.get(web): setattr(candidate,field,str(draft[web]).strip())
            candidate = replace(candidate,mode='DeepSeek' if provider=='DeepSeek' else 'TypeSafe Jev')
            candidate.validate()
            return {'message':check_connection(candidate,'chat' if provider=='DeepSeek' else 'jev')}
        if route=='/api/native': return self.native_workspace()
        if route=='/api/wechat/dashboard':
            from .wechat_client import open_dashboard
            return open_dashboard()
        if route=='/api/wechat/directory': return self.wechat.choices.choose(body.get('purpose'))
        if route=='/api/wechat/scan': return self.wechat.scan()
        if route=='/api/wechat/backup': return self.wechat.backup(body)
        if route=='/api/wechat/export': return self.wechat.export(body)
        if route=='/api/wechat/dismiss': return self.wechat.dismiss(body.get('id'))
        if route=='/api/open-archive':
            if os.name=='nt': os.startfile(str(self.directory))
            return {'opened':True}
        raise ValueError('接口不存在。')

    def close(self):
        self.wechat.close()
        with self.lock:
            for task in self.tasks.values(): task['cancel'].set()
            threads = [task['thread'] for task in self.tasks.values()]
        deadline = time.monotonic()+self.settings.timeout+15
        for thread in threads:
            if thread is not threading.current_thread(): thread.join(max(0,deadline-time.monotonic()))
