import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from chat_assistant.web_backend import LocalService
from chat_assistant.web_server import make_server
from chat_assistant.core import Settings
from chat_assistant.history_analysis import DIMENSIONS


class WebBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dist = self.root / 'web'; self.dist.mkdir()
        (self.dist / 'index.html').write_text('<html><head></head><body>UI</body></html>')
        self.service = LocalService(self.root / 'user')
        self.server = make_server(self.dist, self.service, port=0)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.service.close(); self.server.shutdown(); self.server.server_close()
        self.thread.join(); self.temp.cleanup()

    def request(self, route, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(self.url + route, data=data, headers={
            'Content-Type': 'application/json', 'X-Chat1-Token': self.server.token,
            **(headers or {})})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def preview(self):
        rows = [{'sender':'self','text':'真实测试文字一','timestamp':'2026-09-29 12:00:00'},
                {'sender':'peer','text':'真实测试文字二','timestamp':'2026-10-01 12:00:00'},
                {'sender':'peer','type':'image','text':'[图片]'}]
        return self.request('/api/import/preview', {'name':'sample.json',
            'data':base64.b64encode(json.dumps(rows).encode()).decode()})

    def imported(self):
        preview = self.preview()
        return self.request('/api/import/commit', {'importId':preview['id'],
            'conversation':0,'self':'self','name':'合成联系人'})['profileId']

    def test_real_import_identity_dedupe_and_time_filter(self):
        identity = self.imported()
        result = self.request('/api/messages?profile=' + identity)
        self.assertEqual(['真实测试文字一','真实测试文字二'], [m['text'] for m in result['messages']])
        self.assertEqual(['我','对方'], [m['speaker'] for m in result['messages']])
        filtered = self.request('/api/messages?profile=' + identity + '&start=2026-10-01&end=2026-10-01')
        self.assertEqual(1, filtered['total'])
        self.assertEqual(1, len(self.service.store.profiles()))
        preview = self.preview()
        self.request('/api/import/commit', {'importId':preview['id'],
            'conversation':0,'self':'self','name':'合成联系人'})
        self.assertEqual(1, len(self.service.store.profiles()))
        self.assertEqual(2, self.service.store.profile(identity).count)

    def test_affinity_job_routes_and_persists_selected_perspective(self):
        from chat_assistant.core import Message
        identity = self.imported()
        self.service.store.import_messages(identity, [Message('我' if i % 2 == 0 else '对方', f'合成消息{i}', message_id=f'extra-{i}') for i in range(100)])
        self.service.settings = Settings(chat_key='synthetic')
        def model(rows, settings, perspective='other'):
            subject = '我' if perspective == 'self' else '对方'
            quote = next(row for row in rows if row['speaker'] == subject)
            return {'rawDelta': 4, 'confidence': 1, 'summary': '合成结果',
                    'evidence': [{'entryId': quote['id'], 'quote': quote['text'], 'signal': '可核对的表达'}]}
        with patch('chat_assistant.affinity_runner.analyze_affinity', side_effect=model):
            job = self.request('/api/jobs/affinity', {'profile': identity, 'calculate': True, 'perspective': 'self'})
            self.service.wait_task(job['id'])
        final = self.request('/api/jobs/' + job['id'])
        self.assertEqual('completed', final['state'])
        self.assertEqual('self', final['perspective'])
        page = self.request('/api/messages?profile=' + identity)
        self.assertEqual(54, page['selfAffinity']['score'])
        self.assertEqual(100, page['selfAffinity']['processed'])
        self.assertEqual(50, page['affinity']['score'])
        self.assertEqual(0, page['affinity']['processed'])
        with self.assertRaises(HTTPError):
            self.request('/api/jobs/affinity', {'profile': identity, 'calculate': True, 'perspective': 'invalid'})

    def test_identity_preview_uses_member_names_without_changing_identity_keys(self):
        data = {'chatlab': {'version': '0.0.2'}, 'meta': {'platform': 'weixin', 'ownerId': 'self'},
                'members': [{'platformId': 'self', 'accountName': '我'}, {'platformId': 'peer', 'accountName': '小星'}],
                'messages': [
                    {'sender': 'self', 'type': 0, 'content': '合成文字一', 'timestamp': 1790841600},
                    {'sender': 'peer', 'type': 0, 'content': '合成文字二', 'timestamp': 1790841601}]}
        preview = self.request('/api/import/preview', {'name': 'names.json',
            'data': base64.b64encode(json.dumps(data).encode()).decode()})
        conversation = preview['conversations'][0]
        self.assertEqual(['self', 'peer'], conversation['speakers'])
        self.assertEqual({'self': '我', 'peer': '小星'}, conversation['speakerNames'])
        self.assertEqual(['我', '小星'], [m['sender'] for m in conversation['sample']])

    def test_affinity_requires_explicit_choice_and_keeps_jev_dimensions_separate(self):
        identity = self.imported()
        with self.assertRaises(HTTPError) as refused:
            self.request('/api/jobs/affinity',{'profile':identity})
        self.assertEqual(400,refused.exception.code)
        page=self.request('/api/messages?profile='+identity)
        self.assertEqual(50,page['affinity']['score'])
        self.assertIsNone(page['analysis']['overallScore'])
        self.service.settings = Settings(chat_key='synthetic-only')
        with patch('chat_assistant.affinity_runner.analyze_affinity', return_value={'rawDelta':0,'confidence':0,'summary':'证据不足','evidence':[]}):
            job=self.request('/api/jobs/affinity',{'profile':identity,'calculate':True})
            self.service.wait_task(job['id'])
        result=self.request('/api/jobs/'+job['id'])
        self.assertEqual('completed',result['state'])
        self.assertEqual(50,result['affinity']['score'])

    def test_comprehensive_endpoint_cannot_bypass_whole_profile_gate(self):
        identity = self.imported()
        with patch('chat_assistant.web_backend.run_comprehensive') as run:
            with self.assertRaises(HTTPError):
                self.request('/api/jobs/comprehensive', {'profile':identity, 'calculate':True, 'start':'2026-10-01'})
            run.assert_not_called()
        page = self.request('/api/messages?profile=' + identity + '&start=2026-10-01')
        self.assertFalse(page['affinity']['comprehensiveReady'])
        self.assertEqual(2, page['affinity']['globalPending'])

    def test_guide_only_save_does_not_reencrypt_api_configuration(self):
        self.service.settings=Settings(chat_key='synthetic-only')
        self.service.config.save(self.service.settings)
        before=self.service.config.path.read_bytes()
        self.request('/api/settings',{'guideDone':True})
        self.assertEqual(before,self.service.config.path.read_bytes())

    def test_keys_never_returned_or_cleared_by_untouched_fields(self):
        self.service.settings = Settings(chat_key='synthetic-only-key', jev_key='synthetic-jev')
        settings = self.request('/api/settings')
        self.assertEqual('', settings['chatKey'])
        self.assertTrue(settings['hasChatKey'])
        updated = self.request('/api/settings', {'chatKey':'','chatModel':'custom-model'})
        self.assertEqual('synthetic-only-key', self.service.settings.chat_key)
        self.assertNotIn('synthetic-only-key', json.dumps(updated))
        loaded = LocalService(self.service.directory)
        self.assertEqual('synthetic-only-key', loaded.settings.chat_key)
        loaded.close()

    def test_requires_token_and_rejects_cross_origin_even_with_token(self):
        for headers in ({'X-Chat1-Token':''}, {'Origin':'https://unrelated.example'},
                        {'Host':'unrelated.example'}):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/settings', headers=headers)
            self.assertEqual(403, ctx.exception.code)

    def test_spa_document_bootstraps_session_and_missing_assets_are_404(self):
        with urlopen(self.url) as response:
            document = response.read().decode()
            self.assertIn(self.server.token, document)
            self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url + '/assets/missing.js')
        self.assertEqual(404, ctx.exception.code)

    def test_invalid_import_does_not_make_a_fake_profile(self):
        with self.assertRaises(HTTPError):
            self.request('/api/import/preview', {'name':'bad.json','data':'bm90IGpzb24='})
        self.assertEqual([], self.service.store.profiles())

    def test_scoring_uses_real_saved_ratings_and_only_reports_completed_after_commit(self):
        identity = self.imported()
        self.service.settings = Settings(mode='Jev + DeepSeek', jev_key='synthetic', chat_key='')
        def mock_score(settings, messages, targets, cancel):
            return [{'entry_id':t['entry_id'], 'rating':{
                'speaker':t['speaker'],'score':80 if t['speaker']=='我' else None,
                'affinity_delta':1 if t['speaker']=='对方' else None,
                'confidence':.9,'boundary':0,'reason':'结构化评分',
                'dimensions':{k:{'score':75,'confidence':.9,'evidence':'合成证据'} for k in DIMENSIONS}}, 'issue':None} for t in targets]
        with patch('chat_assistant.history_runner.analyze_batch', side_effect=mock_score):
            task = self.request('/api/jobs/score', {'profile':identity})
            self.service.wait_task(task['id'], timeout=4)
        result = self.request('/api/jobs/' + task['id'])
        self.assertEqual('completed', result['state'])
        self.assertEqual(2, result['completed'])
        saved = self.request('/api/messages?profile=' + identity)
        self.assertTrue(all(m['rating'] for m in saved['messages']))

    def test_connection_error_is_not_success_and_api_error_redacts_keys(self):
        self.service.settings = Settings(chat_key='synthetic-secret')
        with patch('chat_assistant.web_backend.check_connection', side_effect=RuntimeError('synthetic-secret')):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/connection', {'provider':'DeepSeek'})
            payload = ctx.exception.read().decode()
            self.assertNotIn('synthetic-secret', payload)
            self.assertIn('error', payload)

    def test_distinct_generic_export_files_do_not_mix_contacts(self):
        first = self.imported()
        data = base64.b64encode(json.dumps([{'sender':'self','text':'另一个联系人的文字'},
            {'sender':'peer','text':'不要混入原联系人'}]).encode()).decode()
        preview = self.request('/api/import/preview', {'name':'other.json','data':data})
        other = self.request('/api/import/commit', {'importId':preview['id'],
            'conversation':0,'self':'self','name':'另一个人'})['profileId']
        self.assertNotEqual(first, other)
        self.assertEqual(2, self.service.store.profile(first).count)

    def test_jev_connection_uses_jev_route_and_draft_never_overwrites_saved_settings(self):
        self.service.settings = Settings(chat_key='synthetic-chat',jev_key='synthetic-jev')
        with patch('chat_assistant.web_backend.check_connection', return_value='synthetic-ok') as check:
            result = self.request('/api/connection', {'provider':'TypeSafe Jev',
                'settings':{'jevModel':'draft-jev','jevKey':''}})
        self.assertEqual('synthetic-ok', result['message'])
        candidate, provider = check.call_args.args
        self.assertEqual('jev', provider)
        self.assertEqual('draft-jev', candidate.jev_model)
        self.assertEqual('synthetic-jev', candidate.jev_key)
        self.assertEqual('jev-latest', self.service.settings.jev_model)

    def test_unknown_batch_auto_continues_and_is_persisted_without_fake_scores(self):
        from chat_assistant.batch_analysis import UnjudgeableResponse
        identity = self.imported()
        self.service.settings = Settings(mode='TypeSafe Jev',jev_key='synthetic')
        with patch('chat_assistant.history_runner.analyze_batch', side_effect=UnjudgeableResponse('无法判断')):
            task = self.request('/api/jobs/score', {'profile':identity})
            self.service.wait_task(task['id'],timeout=4)
        result = self.request('/api/jobs/'+task['id'])
        self.assertEqual('completed',result['state'])
        self.assertEqual(1,result['notices'][0]['page'])
        saved = self.request('/api/messages?profile='+identity)['messages']
        self.assertTrue(all(m['done'] and m['issue'] and not m['rating'] for m in saved))
        restarted = LocalService(self.service.directory)
        self.assertTrue(all(e.done for e in restarted.store.entries(identity)))
        restarted.close()

    def test_explicit_explanation_is_saved_and_reused_without_changing_ratings(self):
        identity = self.imported()
        self.service.settings = Settings(chat_key='synthetic')
        ids = [e.id for e in self.service.store.entries(identity)]
        rows = [{'entry_id':i,'text':'合成解释','source':'synthetic'} for i in ids]
        with patch('chat_assistant.web_backend.explain_messages',return_value=rows) as explain:
            task = self.request('/api/jobs/explain',{'profile':identity,'ids':ids})
            self.service.wait_task(task['id'],timeout=4)
            second = self.request('/api/jobs/explain',{'profile':identity,'ids':ids})
            self.service.wait_task(second['id'],timeout=4)
        self.assertEqual(1,explain.call_count)
        entries = self.service.store.entries(identity)
        self.assertTrue(all(e.explanation and not e.rating for e in entries))

    def test_failed_model_request_stays_error_and_never_marks_unsaved_messages_done(self):
        from chat_assistant.analysis import APIError
        identity = self.imported()
        self.service.settings = Settings(mode='TypeSafe Jev',jev_key='synthetic')
        with patch('chat_assistant.history_runner.analyze_batch',side_effect=APIError('接口失败')):
            task = self.request('/api/jobs/score',{'profile':identity})
            self.service.wait_task(task['id'],timeout=4)
        result = self.request('/api/jobs/'+task['id'])
        self.assertEqual('error',result['state'])
        self.assertTrue(all(not e.done for e in self.service.store.entries(identity)))

    def test_same_filename_different_people_never_automatically_share_a_profile(self):
        first = self.imported()
        rows = [{'sender':'self','text':'另一段我方文字'}, {'sender':'different-peer','text':'另一位联系人的回复'}]
        preview = self.request('/api/import/preview',{'name':'sample.json',
            'data':base64.b64encode(json.dumps(rows).encode()).decode()})
        other = self.request('/api/import/commit',{'importId':preview['id'],'conversation':0,'self':'self','name':'不同联系人'})['profileId']
        self.assertNotEqual(first,other)
        self.assertEqual(2,self.service.store.profile(first).count)
        explicit = self.request('/api/import/commit',{'importId':preview['id'],'conversation':0,
            'self':'self','name':'显式追加','profileId':first})
        self.assertEqual(first,explicit['profileId'])
        self.assertEqual(4,self.service.store.profile(first).count)

    def test_long_selected_explanations_are_split_under_the_context_budget(self):
        from chat_assistant.batch_analysis import batch_context
        from chat_assistant.core import Message
        identity = self.service.store.create('long','JSON','long','self').id
        self.service.store.import_messages(identity,[Message('我' if i%2 else '对方','长'*9000,message_id=str(i)) for i in range(4)])
        self.service.settings = Settings(chat_key='synthetic')
        entries = self.service.store.entries(identity)
        def explain(settings,entries,positions):
            batch_context(entries,positions)
            return [{'entry_id':entries[i].id,'text':'长文字合成解释','source':'synthetic'} for i in positions]
        with patch('chat_assistant.web_backend.explain_messages',side_effect=explain) as model:
            task = self.request('/api/jobs/explain',{'profile':identity,'ids':[e.id for e in entries]})
            self.service.wait_task(task['id'],timeout=4)
        self.assertEqual('completed',self.request('/api/jobs/'+task['id'])['state'])
        self.assertEqual(2,model.call_count)
        self.assertTrue(all(e.explanation for e in self.service.store.entries(identity)))

    def test_unjudgeable_rescore_does_not_display_old_score_or_old_boundary(self):
        identity = self.imported(); entry = self.service.store.entries(identity)[0]
        rating = {'speaker':'我','score':80,'confidence':.9,'boundary':.9,
            'dimensions':{k:{'score':80,'confidence':.9,'evidence':'synthetic'} for k in DIMENSIONS}}
        self.service.store.save_rating(identity,entry.id,rating,'context','signature')
        self.service.store.save_batch(identity,[{'entry_id':entry.id,'rating':None,
            'issue':{'kind':'unjudgeable','reason':'无法判断'}}],'context','signature')
        result = self.request('/api/messages?profile='+identity)
        self.assertIsNone(result['messages'][0]['rating'])
        self.assertFalse(result['analysis']['boundaryAlert'])

    def test_native_updated_keys_are_retained_when_web_saves_only_font(self):
        from chat_assistant.storage import SettingsStore
        SettingsStore(self.service.directory).save(Settings(chat_key='synthetic-new-native-key'))
        self.request('/api/settings',{'fontFamily':'LXGW WenKai Lite','chatKey':''})
        self.assertEqual('synthetic-new-native-key',self.service.settings.chat_key)
        self.assertEqual('LXGW WenKai Lite',SettingsStore(self.service.directory).load().font_family)


if __name__ == '__main__':
    unittest.main()
