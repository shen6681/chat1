import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chat_assistant.qq_export import QQHistoryClient, export_plain_database
from chat_assistant.archives import ArchiveStore
from chat_assistant.importers import from_json


class QQExportTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.requests.append((self.path,body,self.headers.get('Authorization')))
                if self.headers.get('Authorization')!='Bearer local-test':self.send_response(401);self.end_headers();return
                if self.path=='/get_login_info':data={'user_id':10001,'nickname':'合成账号'}
                elif self.path=='/get_friend_list':data=[{'user_id':10002,'nickname':'合成联系人'}]
                elif self.path=='/get_friend_msg_history':
                    def msg(i,text,sender):return {'message_id':i,'message_seq':i,'time':1790000000+i,'sender':{'user_id':sender},'message_type':'private','message':[{'type':'text','data':{'text':text}}]}
                    cursor=str(body['message_seq'])
                    if cursor=='0':rows=[msg(4,'最新消息',10002),msg(3,'我的回复',10001),{'message_id':5,'time':1790000005,'sender':{'user_id':10002},'message':[{'type':'image','data':{'file':'fake.png'}}]}]
                    elif cursor=='3':rows=[msg(3,'我的回复',10001),msg(2,'早一点的消息',10002),msg(1,'第一条',10001)]
                    else:rows=[msg(1,'第一条',10001)]
                    data={'messages':rows}
                else:self.send_response(404);self.end_headers();return
                raw=json.dumps({'status':'ok','retcode':0,'data':data},ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.client=QQHistoryClient(f'http://127.0.0.1:{self.server.server_port}','local-test')

    def tearDown(self):self.server.shutdown();self.server.server_close()

    def test_connect_paginate_export_reimport_archive_dedupe(self):
        account,friends=self.client.connect()
        bundle,data=self.client.history(account['user_id'],friends[0]['user_id'],'合成联系人',100)
        c=bundle.conversations[0]
        self.assertEqual([m.message_id for m in c.messages],['1','2','3','4'])
        self.assertEqual(c.owner,'10001')
        self.assertTrue(any('非文本' in w for w in bundle.warnings))
        exported=from_json(json.loads(json.dumps(data)))
        with tempfile.TemporaryDirectory() as folder:
            store=ArchiveStore(Path(folder));p=store.create(c.name,c.platform,c.key,c.owner)
            self.assertEqual(store.import_messages(p.id,c.choose_self(c.owner)),4)
            self.assertEqual(store.import_messages(p.id,exported.conversations[0].choose_self(c.owner)),0)
        self.assertTrue(all(r[0] in ['/get_login_info','/get_friend_list','/get_friend_msg_history'] for r in self.requests))

    def test_token_error_does_not_echo_service_body_or_key(self):
        client=QQHistoryClient(self.client.base,'private-invalid-key')
        with self.assertRaises(ValueError) as result:client.connect()
        self.assertIn('Token',str(result.exception));self.assertNotIn('private-invalid-key',str(result.exception))

    def test_limit_and_cancel(self):
        bundle,_=self.client.history('10001','10002','合成联系人',2)
        self.assertEqual(len(bundle.conversations[0].messages),2)
        self.assertTrue(any('读取上限' in w for w in bundle.warnings))
        event=threading.Event();event.set()
        with self.assertRaisesRegex(ValueError,'取消'):self.client.history('10001','10002','合成联系人',100,cancel=event)

    def test_local_only_read_actions_and_encrypted_database_rejection(self):
        for address in ['https://example.com','http://example.com','http://127.0.0.1:3000?key=x','http://x:y@127.0.0.1']:
            with self.assertRaises(ValueError):QQHistoryClient(address)
        with self.assertRaises(ValueError):self.client.call('send_private_msg',{})
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'nt_msg.db').write_bytes(b'encrypted-original')
            with self.assertRaisesRegex(ValueError,'仍然加密'):export_plain_database(root,root/'out')
            self.assertFalse((root/'out').exists())

    def test_later_error_retains_partial_history_with_explicit_warning(self):
        original=self.client.call
        def operation(action,params=None):
            if action=='get_friend_msg_history' and params['message_seq']!='0':raise ValueError('server error')
            return original(action,params)
        self.client.call=operation
        bundle,_=self.client.history('10001','10002','合成联系人',100)
        self.assertEqual(len(bundle.conversations[0].messages),2)
        self.assertTrue(any('部分历史' in w for w in bundle.warnings))

if __name__=='__main__':unittest.main()
