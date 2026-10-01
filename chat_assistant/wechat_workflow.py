"""User-selected directories and backup → text export → identity preview."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .history_analysis import time_bounds
from .importers import MAX_FILE
from .wechat_client import WechatClient, ensure_wechat


def choose_directory(purpose):
    # Browser fallback: one native folder picker, not the legacy app window.
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
    try:
        return filedialog.askdirectory(parent=root,title='选择微信'+('备份目录' if purpose=='backup' else '文字导出目录'),mustexist=True) or None
    finally: root.destroy()


class DirectoryChoices:
    def __init__(self, picker=None):
        self.picker=picker or choose_directory;self.tokens={};self.lock=threading.Lock()

    def choose(self,purpose):
        if purpose not in ('backup','export'): raise ValueError('请选择备份目录或导出目录。')
        if not self.lock.acquire(blocking=False): raise ValueError('目录选择窗口已打开。')
        try:
            chosen=self.picker(purpose)
            if not chosen: return {'cancelled':True}
            path=Path(chosen).resolve()
            if not path.is_dir(): raise ValueError('请选择已有的可用目录。')
            token=uuid.uuid4().hex
            self.tokens={k:v for k,v in self.tokens.items() if time.monotonic()-v[2]<3600}
            self.tokens[token]=(purpose,path,time.monotonic())
            return {'token':token,'path':str(path)}
        finally: self.lock.release()

    def resolve(self,token,purpose):
        with self.lock:
            row=self.tokens.get(token)
            if not row or row[0]!=purpose or time.monotonic()-row[2]>=3600:
                raise ValueError('请主动选择'+('备份目录' if purpose=='backup' else '导出目录')+'，不使用默认地址。')
            if not row[1].is_dir(): raise ValueError('所选目录已不可用，请重新选择。')
            return row[1]


class WechatWorkflow:
    def __init__(self,service,client=None,choices=None,ensure=None,reader_factory=None):
        self.service=service;self.client=client or WechatClient();self.choices=choices or DirectoryChoices()
        self.ensure=ensure or (lambda:ensure_wechat(self.client));self.lock=threading.RLock()
        self.jobs={};self.closed=False
        if reader_factory is None:
            from .wechat_reader import ScopedWechatReader
            reader_factory=lambda backup,account,identity:ScopedWechatReader(service.directory,backup,account,identity)
        self.reader_factory=reader_factory

    def active(self):
        with self.lock:
            job=next((j for j in reversed(list(self.jobs.values())) if j['state'] not in ('dismissed','imported')),None)
            return self.view(job['id']) if job else None

    def imported(self,preview_id):
        with self.lock:
            for job in self.jobs.values():
                if job.get('preview',{}).get('id')==preview_id:job['state']='imported'

    def _close_reader(self,job):
        reader=job.pop('reader',None)
        if reader and hasattr(reader,'close'):reader.close()
        self.service.store.release_analysis('wechat-import','wechat:'+job['id'])

    def view(self,identity):
        with self.lock:
            if identity not in self.jobs: raise ValueError('微信导入任务不存在，请重新开始。')
            return {k:v for k,v in self.jobs[identity].items() if k not in ('thread','backupPath','exportPath','account','selection','reader')}

    def wait(self,identity,timeout=180): self.jobs[identity]['thread'].join(timeout)

    def _work(self,job,callback):
        def work():
            try: callback()
            except Exception as error:
                self._close_reader(job)
                with self.lock: job.update(state='error',error=self.service.safe_error(error))
            finally:
                if self.closed:self._close_reader(job)
        job['thread']=threading.Thread(target=work,daemon=True,name='wechat-import');job['thread'].start()

    def _progress(self,job,event):
        with self.lock:
            job.update(detail=str(event.get('detail',''))[:400],progress=event.get('progress',0))

    def scan(self):
        with self.lock:
            if self.closed: raise ValueError('程序正在关闭。')
            if any(j['state'] in ('scanning','choose_account','backing_up','choose_contact','exporting') for j in self.jobs.values()):
                raise ValueError('已有微信流程运行，请完成或关闭当前向导。')
            identity=uuid.uuid4().hex
            job={'id':identity,'state':'scanning','detail':'正在连接微信工具…','progress':0,'error':'','accounts':[],'contacts':[]}
            self.jobs[identity]=job
            def work():
                self.ensure();result=self.client.stream('/api/backup/scan',{},lambda e:self._progress(job,e))
                accounts=result.get('accounts')
                if not isinstance(accounts,list) or not accounts: raise ValueError('未找到微信账号，请登录自己的微信后打开仪表盘检查数据目录。')
                with self.lock: job.update(state='choose_account',accounts=accounts,detail='选择要备份的微信账号。')
            self._work(job,work)
            return self.view(identity)

    def backup(self,body):
        with self.lock:
            job=self.jobs.get(body.get('id'))
            if not job or job['state']!='choose_account': raise ValueError('请先检测并选择微信账号。')
            backup=self.choices.resolve(body.get('backupToken'),'backup')
            export=self.choices.resolve(body.get('exportToken'),'export')
            account=next((a for a in job['accounts'] if a.get('db_path')==body.get('account')),None)
            if not account or not account.get('wxid'): raise ValueError('请主动选择检测到的微信账号。')
            start,end=str(body.get('start','')),str(body.get('end',''));time_bounds(start,end)
            if not self.service.store.acquire_analysis('wechat-import','wechat:'+job['id'],86400):
                raise ValueError('另一个窗口正在进行微信备份或导入，请先完成或关闭它的向导。')
            job.update(state='backing_up',account=account,backupPath=backup,exportPath=export,
                       selectedBackupDirectory=str(backup),selectedExportDirectory=str(export),
                       start=start,end=end,detail='正在备份，完成后选择联系人…',progress=0)
            def work():
                payload={'db_dir':account['db_path'],'output_dir':str(backup),'start_date':start,'end_date':end}
                result=self.client.stream('/api/backup/run',payload,lambda e:self._progress(job,e))
                if result.get('success') is not True: raise ValueError('微信备份未成功，请在仪表盘查看原因。')
                if result.get('wxid')!=account['wxid']:
                    raise ValueError('备份返回的账号与所选账号不同，已停止；请在仪表盘核对，不会混入其他账号。')
                job['reader']=self.reader_factory(backup,account,job['id'])
                contacts=job['reader'].contacts()
                if not contacts: raise ValueError('备份完成但没有可读联系人，请检查仪表盘账号。')
                with self.lock: job.update(state='choose_contact',contacts=contacts,detail='备份完成，选择一个私聊导入文字。',progress=1)
            self._work(job,work)
            return self.view(job['id'])

    def export(self,body):
        with self.lock:
            job=self.jobs.get(body.get('id'))
            if not job or job['state']!='choose_contact': raise ValueError('请先完成微信备份，再选择联系人。')
            contact=next((c for c in job['contacts'] if c.get('id')==body.get('contact')),None)
            if not contact or not contact.get('id'): raise ValueError('请选择备份中的联系人。')
            if contact.get('type')=='group' or contact['id'].endswith('@chatroom'): raise ValueError('好感分析仅支持双人私聊，请选择个人。')
            job.update(state='exporting',detail='仅提取文字，图片和表情包不会读取…',progress=0)
            def work():
                rows,seen,size=[],set(),0
                for messages in job['reader'].messages(contact['id'],job['start'],job['end']):
                    for row in messages:
                        if not isinstance(row,dict): raise ValueError('微信消息格式无效。')
                        if row.get('msg_type')!=1: continue
                        text=row.get('content');side=row.get('sender_side')
                        if not isinstance(text,str) or not text.strip(): continue
                        if side not in ('me','other') or type(row.get('is_sender')) is not bool or row['is_sender']!=(side=='me'):
                            raise ValueError('存在发言人未确认的文字，请在仪表盘检查；不会自动猜测“我”和“对方”。')
                        timestamp=row.get('create_time')
                        if type(timestamp) not in (int,float): raise ValueError('微信消息缺少有效时间。')
                        fingerprint=hashlib.sha256(json.dumps([job['account']['wxid'],contact['id'],row.get('id'),timestamp,side,text],ensure_ascii=False).encode()).hexdigest()
                        if fingerprint in seen: continue
                        seen.add(fingerprint);size+=len(text.encode('utf-8'))+500
                        if size>MAX_FILE: raise ValueError('文字超过150MB，请按日期分段导入。')
                        rows.append({'sender':'self' if side=='me' else 'peer','type':0,'content':text,
                                     'timestamp':timestamp,'platformMessageId':fingerprint,'messageId':fingerprint})
                    with self.lock: job.update(detail=f'已提取 {len(rows)} 条文字…')
                if not rows: raise ValueError('所选联系人/日期范围没有可导入文字。')
                rows.sort(key=lambda m:m['timestamp'])
                key=hashlib.sha256((job['account']['wxid']+'\0'+contact['id']).encode()).hexdigest()
                document={'chatlab':{'version':'0.0.2'},'meta':{'platform':'微信','type':'private',
                    'name':contact.get('name') or contact['id'],'username':'wechat:'+key,'ownerId':'self'},
                    'members':[{'platformId':'self','accountName':'我'},{'platformId':'peer','accountName':contact.get('name') or contact['id']}], 'messages':rows}
                data=json.dumps(document,ensure_ascii=False).encode('utf-8')
                if len(data)>MAX_FILE: raise ValueError('文字文件超过150MB，请按日期分段导入。')
                folder=job['exportPath']
                filename='微信文字-'+key[:12]+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.json'
                temporary=folder/('.'+filename+'.tmp');destination=folder/filename
                try:
                    with temporary.open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())
                    temporary.replace(destination)
                finally:
                    if temporary.exists(): temporary.unlink()
                preview=self.service.preview_import({'name':filename,'data':base64.b64encode(data).decode('ascii')})
                # Stable account/contact identity only for this verified workflow;
                # arbitrary uploaded files continue to require explicit destinations.
                with self.service.lock:
                    bundle=self.service.previews[preview['id']][1]
                    bundle.conversations[0].key='wechat-api:'+key
                with self.lock: job.update(state='preview',detail='文字已导出，确认身份后保存档案。',
                                          progress=1,preview=preview,exportFile=str(destination))
                self._close_reader(job)
            self._work(job,work)
            return self.view(job['id'])

    def dismiss(self,identity):
        with self.lock:
            job=self.jobs.get(identity)
            if not job: return {'closed':True}
            if job['state'] in ('scanning','backing_up','exporting'):
                raise ValueError('微信工具操作仍在进行，请等待完成；关闭页面不会取消工具备份。')
            job['state']='dismissed'
            self._close_reader(job)
            return {'closed':True}

    def close(self):
        self.closed=True
        with self.lock: threads=[j.get('thread') for j in self.jobs.values()]
        for thread in threads:
            if thread and thread.is_alive(): thread.join(5)
        with self.lock:
            for job in self.jobs.values():self._close_reader(job)
