import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from chat_assistant.wechat_client import WechatClient
from chat_assistant.wechat_workflow import DirectoryChoices, WechatWorkflow
from chat_assistant.web_backend import LocalService


class WechatAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.backup = self.root/'user-backup'; self.backup.mkdir()
        self.export = self.root/'user-export'; self.export.mkdir()
        self.service = LocalService(self.root/'settings')
        self.requests = []; self.mode = 'normal'
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def respond(self,data,ctype='application/json',code=200):
                raw = data.encode() if isinstance(data,str) else json.dumps(data).encode()
                self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path,body))
                if self.path.endswith('/scan'):
                    result = {'accounts':[{'db_path':'C:/synthetic-db','wxid':'wxid_self_suffix','size_mb':1,'db_count':2,'mtime':1}]}
                else:
                    if owner.mode=='wrong-account': return self.respond('event: done\ndata: '+json.dumps({'stage':'done','result':{'success':True,'wxid':'different-account'}})+'\n\n','text/event-stream')
                    if owner.mode=='fail': return self.respond('event: error\ndata: {"stage":"error","message":"synthetic failure"}\n\n','text/event-stream')
                    if owner.mode=='incomplete': return self.respond('event: progress\ndata: {"stage":"backup","progress":0.5}\n\n','text/event-stream')
                    result = {'success':True,'wxid':'wxid_self_suffix'}
                self.respond(': heartbeat\n\nevent: progress\ndata: {"stage":"scan","detail":"working","progress":0.3}\n\nevent: done\ndata: '+json.dumps({'stage':'done','result':result})+'\n\n','text/event-stream')
            def do_GET(self):
                parts = urlsplit(self.path); q = parse_qs(parts.query)
                owner.requests.append((parts.path,q))
                if parts.path=='/api/contacts': return self.respond({'contacts':[{'id':'peer','name':'合成朋友','type':'user','msg_count':3},{'id':'g@chatroom','name':'合成群聊','type':'group','msg_count':2}],'total':2})
                if parts.path=='/api/messages':
                    page = int(q['page'][0])
                    rows = [{'id':1,'msg_type':1,'is_sender':True,'sender_side':'me','sender_name':'我','sender_wxid':'wxid_self','content':'我的合成文字','create_time':1790848800},
                            {'id':1,'msg_type':1,'is_sender':False,'sender_side':'other','sender_name':'合成朋友','sender_wxid':'peer','content':'朋友的合成文字','create_time':1790848801},
                            {'id':2,'msg_type':3,'is_sender':False,'sender_side':'other','content':'不读取图片','create_time':1790848802}]
                    if owner.mode=='unknown': rows[1]['sender_side']='unknown'
                    return self.respond({'messages':rows if page==1 else [rows[1]],'pagination':{'page':page,'per_page':200,'total':4,'total_pages':2}})
                self.respond({'error':'missing'},code=404)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=WechatClient(port=self.server.server_port)
        self.paths=DirectoryChoices(lambda purpose: str(self.backup if purpose=='backup' else self.export))
        self.bound=[]
        def reader(backup,account,identity):
            self.bound.append((str(backup),account['wxid'],identity))
            return self.client
        self.flow=WechatWorkflow(self.service,self.client,self.paths,ensure=lambda:None,reader_factory=reader)

    def tearDown(self):
        self.flow.close();self.service.close();self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def prepare(self):
        scan=self.flow.scan();self.flow.wait(scan['id'])
        return scan['id']

    def selected(self):
        return self.paths.choose('backup')['token'],self.paths.choose('export')['token']

    def test_directory_selection_mandatory_and_purpose_bound(self):
        scan=self.prepare()
        for backup,export in [('', ''),('/pretend/path','/pretend/path')]:
            with self.assertRaises(ValueError):self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export})
        backup,export=self.selected()
        with self.assertRaises(ValueError):self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':export,'exportToken':backup})
        self.assertEqual(1,len(self.requests))

    def test_backup_export_only_text_selected_path_and_identity_preview(self):
        scan=self.prepare(); backup,export=self.selected()
        self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
        result=self.flow.view(scan);self.assertEqual('choose_contact',result['state'])
        self.flow.export({'id':scan,'contact':'peer'});self.flow.wait(scan)
        result=self.flow.view(scan);self.assertEqual('preview',result['state'])
        files=list(self.export.glob('*.json'));self.assertEqual(1,len(files))
        data=json.loads(files[0].read_text(encoding='utf-8'))
        self.assertEqual(['我的合成文字','朋友的合成文字'],[m['content'] for m in data['messages']])
        self.assertEqual(2,len({m['messageId'] for m in data['messages']}))
        self.assertEqual(str(self.backup),next(body for route,body in self.requests if route=='/api/backup/run')['output_dir'])
        self.assertTrue(all(q.get('type')==['1'] for route,q in self.requests if route=='/api/messages'))
        self.assertFalse(any(route=='/api/export/chat' for route,body in self.requests))
        preview=result['preview'];saved=self.service.commit_import({'importId':preview['id'],'conversation':0,'self':'self','name':'合成朋友'})
        self.assertEqual(2,saved['added']);self.assertEqual(['我','对方'],[e.message.speaker for e in self.service.store.entries(saved['profileId'])])

    def test_backup_error_and_missing_done_do_not_allow_export(self):
        for mode in ('fail','incomplete'):
            self.mode=mode;scan=self.prepare();backup,export=self.selected()
            self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
            self.assertEqual('error',self.flow.view(scan)['state'])
            with self.assertRaises(ValueError):self.flow.export({'id':scan,'contact':'peer'})
        self.assertEqual([],list(self.export.glob('*.json')))

    def test_group_unknown_sender_and_forged_contact_do_not_import(self):
        scan=self.prepare();backup,export=self.selected()
        self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
        for contact in ('g@chatroom','forged'):
            with self.assertRaises(ValueError):self.flow.export({'id':scan,'contact':contact})
        self.mode='unknown';self.flow.export({'id':scan,'contact':'peer'});self.flow.wait(scan)
        self.assertEqual('error',self.flow.view(scan)['state'])
        self.assertEqual([],list(self.export.glob('*.json')))
        self.assertEqual([],self.service.store.profiles())

    def test_cancelled_directory_picker_has_no_token(self):
        result=DirectoryChoices(lambda purpose: None).choose('backup')
        self.assertEqual({'cancelled':True},result)

    def test_external_port_or_url_cannot_be_substituted(self):
        with self.assertRaises(ValueError):WechatClient(port='https://example.com')

    def test_wrong_account_backup_cannot_be_exported_under_selected_account(self):
        self.mode='wrong-account';scan=self.prepare();backup,export=self.selected()
        self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
        self.assertEqual('error',self.flow.view(scan)['state'])
        self.assertEqual([],self.bound)
        with self.assertRaises(ValueError):self.flow.export({'id':scan,'contact':'peer'})

    def test_second_scan_cannot_orphan_an_account_selection_or_run_parallel_backup(self):
        scan=self.prepare()
        with self.assertRaises(ValueError):self.flow.scan()
        self.assertEqual(scan,self.flow.active()['id'])
        backup,export=self.selected()
        self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
        with self.assertRaises(ValueError):self.flow.scan()
        self.assertEqual([(str(self.backup),'wxid_self_suffix',scan)],self.bound)

    def test_active_job_restores_after_reload_without_directory_defaults(self):
        scan=self.prepare();backup,export=self.selected()
        self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export});self.flow.wait(scan)
        restored=self.flow.active()
        self.assertEqual('choose_contact',restored['state'])
        self.assertEqual(scan,restored['id'])
        self.assertNotIn('backupToken',restored)
        self.assertEqual(str(self.backup),restored['selectedBackupDirectory'])
        self.flow.dismiss(scan)
        self.assertIsNone(self.flow.active())

    def test_cross_process_directory_store_lease_blocks_second_backup(self):
        scan=self.prepare();backup,export=self.selected()
        owner='synthetic-other-instance'
        self.assertTrue(self.service.store.acquire_analysis('wechat-import',owner,86400))
        try:
            with self.assertRaises(ValueError):self.flow.backup({'id':scan,'account':'C:/synthetic-db','backupToken':backup,'exportToken':export})
            self.assertFalse(any(route=='/api/backup/run' for route,body in self.requests))
        finally:self.service.store.release_analysis('wechat-import',owner)


if __name__=='__main__':unittest.main()
