import json
import tempfile
import threading
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from chat_assistant.analysis import APIError
from chat_assistant.archives import ArchiveStore
from chat_assistant.core import Message, Settings
from chat_assistant.history_runner import run_history
from tests.test_api import native_result
from tests.test_history import rating
from chat_assistant.history_analysis import ProgressStats, progress_summary


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.store = ArchiveStore(self.path)
        self.profile = self.store.create('合成联系人', '微信', 'p', 'self')
        self.store.import_messages(self.profile.id, [Message('我' if i%2==0 else '对方', f'消息{i:02}', message_id=str(i)) for i in range(23)])
        self.settings = Settings(mode='Jev + DeepSeek', jev_key='fake', chat_key='fake')
        self.calls = []
        self.fault = None
        self.cancel = None

    def tearDown(self):
        self.temp.cleanup()

    def post(self, url, key, body, timeout):
        self.calls.append((url, body))
        if self.fault == 'network' and len(self.calls)==2:
            raise APIError('模拟网络故障')
        if self.cancel:
            self.cancel.set()
        if url.endswith('/systemone'):
            response = native_result(body['questions'])
            if self.fault == 'row' and len(self.calls)==2:
                response['answers'] = {}
            return response
        state = json.loads(body['messages'][1]['content'])
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'ratings':[{'index':t['index'], **rating(t['speaker'])} for t in state['targets']]})}}]}

    def run_job(self, **kwargs):
        with patch('chat_assistant.batch_analysis.post_json', side_effect=self.post), patch('chat_assistant.history_analysis.post_json',side_effect=AssertionError('禁止旧路径访问网络')):
            return run_history(self.store, self.settings, self.profile.id, self.store.entries(self.profile.id), **kwargs)

    def test_ten_at_once_jev_scoring_never_calls_deepseek_for_explanations(self):
        observed = []
        def event(kind, data):
            if kind == 'batch':
                reopened = ArchiveStore(self.path)
                observed.append(reopened.run_info(data['run_id'])['completed'])
        result = self.run_job(on_progress=event)
        self.assertEqual(result['completed'], 23)
        self.assertEqual(observed, [10,20,23])
        self.assertEqual([len(body['state']['targets']) for url,body in self.calls], [10,10,3])
        self.assertTrue(all(url.endswith('/v1/systemone') for url,_ in self.calls))
        self.assertEqual(sum(bool(e.rating) for e in self.store.entries(self.profile.id)),23)

    def test_invalid_rows_persist_issues_continue_next_batch_and_skip_on_restart(self):
        self.fault = 'row'
        result = self.run_job()
        self.assertEqual(result['state'],'completed')
        entries = ArchiveStore(self.path).entries(self.profile.id)
        self.assertEqual(sum(bool(e.issue) for e in entries),10)
        self.assertTrue(all(e.done for e in entries))
        self.assertEqual(sum(bool(e.rating) for e in entries),13)
        self.calls.clear()
        self.run_job()
        self.assertEqual(self.calls, [])

    def test_network_failure_preserves_first_ten_and_resume_never_repeats_them(self):
        self.fault = 'network'
        with self.assertRaisesRegex(APIError,'网络故障'):
            self.run_job()
        previous = self.store.last_run(self.profile.id)
        self.assertEqual(previous['completed'],10)
        self.fault = None; self.calls.clear()
        self.run_job(run_id=previous['id'])
        self.assertEqual([len(body['state']['targets']) for _,body in self.calls], [10,3])
        self.assertEqual(self.store.run_info(previous['id'])['completed'],23)

    def test_pause_during_request_saves_whole_batch_before_stopping(self):
        self.cancel = threading.Event()
        result = self.run_job(cancel=self.cancel)
        self.assertEqual((result['state'],result['completed']),('paused',10))
        self.assertEqual(sum(e.done for e in self.store.run_entries(result['run_id'])),10)

    def test_tenth_invalid_result_rolls_back_entire_transaction(self):
        entries = self.store.entries(self.profile.id)
        run = self.store.begin_run(self.profile.id,'','',entries,'s','mock')
        rows = [{'entry_id':e.id,'rating':rating(e.message.speaker)} for e in entries[:10]]
        rows[-1]['rating'] = rating('我' if entries[9].message.speaker=='对方' else '对方')
        with self.assertRaises(ValueError):
            self.store.save_batch(self.profile.id,rows,'h','s',run)
        self.assertEqual(sum(bool(e.rating) for e in self.store.entries(self.profile.id)),0)
        self.assertEqual(self.store.run_info(run)['completed'],0)

    def test_unjudgeable_reanalysis_preserves_old_rating_but_does_not_count_it_as_current(self):
        entry=self.store.entries(self.profile.id)[1]
        self.store.save_rating(self.profile.id,entry.id,rating('对方'),'h','s')
        self.store.save_batch(self.profile.id,[{'entry_id':entry.id,'rating':None,'issue':{'kind':'unjudgeable','reason':'证据不足'}}],'h','s')
        reopened=self.store.entries(self.profile.id)
        stats=ProgressStats(reopened).summary()
        self.assertEqual(stats['analyzed'],0)
        self.assertIsNone(stats['score'])
        self.assertEqual(stats,progress_summary(reopened))
        self.assertIsNotNone(reopened[1].rating)

    def test_deepseek_malformed_group_is_handled_once_then_next_group_runs(self):
        self.settings=replace(self.settings,mode='DeepSeek')
        calls=[]
        def post(url,key,body,timeout):
            calls.append(body)
            state=json.loads(body['messages'][1]['content'])
            content='模型无法判断此组' if len(calls)==2 else json.dumps({'ratings':[{'index':t['index'],**rating(t['speaker'])} for t in state['targets']]})
            return {'choices':[{'finish_reason':'stop','message':{'content':content}}]}
        with patch('chat_assistant.batch_analysis.post_json',side_effect=post):
            result=run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id))
        self.assertEqual(result['completed'],23)
        self.assertEqual(len(calls),3)
        self.assertEqual(sum(bool(e.issue) for e in self.store.entries(self.profile.id)),10)

    def test_jev_scoring_in_combo_does_not_require_a_deepseek_key(self):
        self.settings=replace(self.settings,chat_key='')
        self.run_job()
        self.assertEqual(sum(bool(e.rating) for e in self.store.entries(self.profile.id)),23)

    def test_pause_after_long_request_saves_received_subgroup_and_leaves_rest_pending(self):
        self.profile=self.store.create('合成长文本','微信','long','self')
        self.store.import_messages(self.profile.id,[Message('对方',f'{i}'+('字'*9000),message_id=str(i)) for i in range(10)])
        self.cancel=threading.Event()
        result=self.run_job(cancel=self.cancel)
        self.assertEqual((result['state'],result['completed']),('paused',3))
        self.assertEqual(sum(e.done for e in self.store.run_entries(result['run_id'])),3)

    def test_later_long_subrequest_failure_preserves_received_scores_for_resume(self):
        self.profile=self.store.create('合成长文本断网','微信','long-failure','self')
        self.store.import_messages(self.profile.id,[Message('对方',str(i)+('字'*9000),message_id=str(i)) for i in range(10)])
        self.fault='network'
        observed=[]
        def progress(kind,data):
            if kind=='batch':
                observed.append(ArchiveStore(self.path).run_info(data['run_id'])['completed'])
        with self.assertRaisesRegex(APIError,'网络故障'):
            self.run_job(on_progress=progress)
        reopened=ArchiveStore(self.path)
        previous=reopened.last_run(self.profile.id)
        self.assertEqual(previous['state'],'error')
        self.assertEqual(previous['completed'],3)
        self.assertEqual(sum(e.done for e in reopened.run_entries(previous['id'])),3)
        self.assertEqual(observed,[3])
        self.fault=None;self.calls.clear()
        result=self.run_job(run_id=previous['id'])
        targets=[t['entry_id'] for _,body in self.calls for t in body['state']['targets']]
        self.assertEqual(targets,[e.id for e in reopened.entries(self.profile.id)[3:]])
        self.assertEqual((result['state'],result['completed']),('completed',10))

    def test_cancel_with_subrequest_error_preserves_received_scores(self):
        self.profile=self.store.create('合成长文本暂停','微信','long-cancel','self')
        self.store.import_messages(self.profile.id,[Message('对方',str(i)+('字'*9000),message_id=str(i)) for i in range(10)])
        cancel=threading.Event()
        original=self.post
        def post(url,key,body,timeout):
            if len(self.calls)==1:
                cancel.set()
                raise APIError('模拟暂停时网络故障')
            return original(url,key,body,timeout)
        with patch('chat_assistant.batch_analysis.post_json',side_effect=post):
            result=run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id),cancel=cancel)
        self.assertEqual((result['state'],result['completed']),('paused',3))
        self.assertEqual(self.store.run_info(result['run_id'])['completed'],3)

    def test_real_process_crash_after_committed_ten_resumes_at_eleventh(self):
        code='''import os,sys
from pathlib import Path
from unittest.mock import patch
from chat_assistant.archives import ArchiveStore
from chat_assistant.core import Settings
from chat_assistant.history_runner import run_history
from tests.test_api import native_result
store=ArchiveStore(Path(sys.argv[1]));p=sys.argv[2]
def event(kind,data):
    if kind=='batch':os._exit(31)
with patch('chat_assistant.batch_analysis.post_json',side_effect=lambda u,k,b,t:native_result(b['questions'])):
    run_history(store,Settings(mode='TypeSafe Jev',jev_key='fake'),p,store.entries(p),on_progress=event)
'''
        child=subprocess.run([sys.executable,'-c',code,str(self.path),self.profile.id],cwd=Path(__file__).parents[1],capture_output=True,timeout=20)
        self.assertEqual(child.returncode,31,child.stderr.decode(errors='replace'))
        previous=ArchiveStore(self.path).last_run(self.profile.id)
        self.assertEqual(previous['completed'],10)
        self.run_job(run_id=previous['id'])
        self.assertEqual([len(b['state']['targets']) for _,b in self.calls],[10,3])
        self.assertEqual(self.calls[0][1]['state']['targets'][0]['entry_id'],self.store.entries(self.profile.id)[10].id)


if __name__ == '__main__':
    unittest.main()
