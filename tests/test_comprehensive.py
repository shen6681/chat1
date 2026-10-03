import tempfile
import threading
import unittest
from pathlib import Path

from chat_assistant.archives import ArchiveStore
from chat_assistant.affinity import AffinityStore
from chat_assistant.core import Message, Settings
from chat_assistant.comprehensive import run_comprehensive


class ComprehensiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive = ArchiveStore(Path(self.temp.name))
        self.profile = self.archive.create('合成', '微信', 'synthesis', 'me').id
        self.store = AffinityStore(self.archive)
        self.settings = Settings(chat_key='synthetic')

    def tearDown(self): self.temp.cleanup()

    def seed(self, count=201):
        self.archive.import_messages(self.profile, [Message('我' if i % 2 == 0 else '对方', f'合成原文{i}', message_id=str(i)) for i in range(count)])
        return self.archive.entries(self.profile)

    def commit(self, entries):
        self.store.commit(self.profile, entries, {'rawDelta':1,'confidence':1,'summary':'批次总结',
            'evidence':[{'entryId':e.id,'quote':e.message.text,'signal':'依据'} for e in entries[:4]]}, 'synthetic')

    def model(self, rows, settings):
        evidence = next((r['evidence'] for r in rows if any(e['speaker']=='对方' for e in r['evidence'])), rows[0]['evidence'])
        peer = next((e for e in evidence if e['speaker']=='对方'), None)
        return {'rawDelta':0, 'confidence':.5, 'summary':'综合所有批次后的沟通观察', 'evidence':evidence,
                'personality': [] if peer is None else [{'text':'关系与沟通的综合观察', 'evidenceIds':[peer['entryId']]}],
                'pursuitAdvice':[], 'uncertainties':[]}

    def run_report(self, model=None, cancel=None):
        return run_comprehensive(self.archive,self.settings,self.profile,cancel or threading.Event(),analyze=model or self.model)

    def test_empty_and_partial_and_filtered_profiles_remain_locked(self):
        self.assertFalse(self.store.view(self.profile)['comprehensiveReady'])
        with self.assertRaises(ValueError): self.run_report()
        entries = self.seed()
        self.commit(entries[:100])
        filtered = self.store.view(self.profile, entries[:100])
        self.assertEqual(0, filtered['pending'])
        self.assertEqual(101, filtered['globalPending'])
        self.assertFalse(filtered['comprehensiveReady'])
        with self.assertRaises(ValueError): self.run_report()

    def test_all_batches_including_tail_are_used_and_new_messages_relock(self):
        entries = self.seed()
        for offset in range(0,len(entries),100): self.commit(entries[offset:offset+100])
        self.assertTrue(self.store.view(self.profile)['comprehensiveReady'])
        calls = []
        def model(rows, settings):
            calls.extend(rows)
            return self.model(rows, settings)
        report = self.run_report(model)
        self.assertEqual(3, sum(r['coveredBatches'] for r in calls))
        self.assertEqual(201, report['messageCount'])
        self.assertEqual(3, report['batchCount'])
        self.assertEqual(report, self.run_report(lambda *_: self.fail('cached report called model')))
        self.assertFalse(AffinityStore(self.archive,'self').view(self.profile)['comprehensiveReady'])
        self.archive.import_messages(self.profile,[Message('对方','新增原文',message_id='new')])
        view = self.store.view(self.profile)
        self.assertFalse(view['comprehensiveReady'])
        self.assertIsNone(view['comprehensive'])
        with self.assertRaises(ValueError): self.run_report()

    def test_new_messages_during_request_prevent_publishing(self):
        entries = self.seed(10); self.commit(entries)
        def model(rows, settings):
            self.archive.import_messages(self.profile,[Message('对方','新增原文',message_id='new')])
            return self.model(rows, settings)
        with self.assertRaises(ValueError): self.run_report(model)
        self.assertIsNone(self.store.view(self.profile)['comprehensive'])

    def test_cancelled_request_resumes_saved_stage(self):
        entries = self.seed(10); self.commit(entries)
        cancel = threading.Event()
        def model(rows, settings):
            cancel.set()
            return self.model(rows, settings)
        self.assertIsNone(self.run_report(model, cancel))
        self.assertIsNone(self.store.view(self.profile)['comprehensive'])
        report = self.run_report(lambda *_: self.fail('paid stage repeated'))
        self.assertEqual(10, report['messageCount'])

    def test_fabricated_quotes_are_rejected(self):
        entries = self.seed(10); self.commit(entries)
        def model(rows, settings):
            result = self.model(rows,settings)
            result['evidence'][0]['quote'] = '虚构引用'
            return result
        with self.assertRaises(ValueError): self.run_report(model)

    def test_long_history_reduces_all_groups_without_losing_batches(self):
        entries = self.seed(600)
        for offset in range(0,600,100): self.commit(entries[offset:offset+100])
        # Make each stored batch large enough to require multiple synthesis calls.
        import json
        with self.archive.connection() as db:
            for row in db.execute('SELECT id,result_json FROM affinity_batches').fetchall():
                result = json.loads(row['result_json'])
                result['summary'] = '总结' * 1500
                result['uncertainties'] = ['疑点' * 150] * 4
                for evidence in result['evidence']: evidence['signal'] = '依据' * 150
                db.execute('UPDATE affinity_batches SET result_json=? WHERE id=?',(json.dumps(result),row['id']))
        calls = []
        def model(rows, settings):
            calls.append(sum(r['coveredBatches'] for r in rows))
            return self.model(rows,settings)
        report = self.run_report(model)
        self.assertGreater(len(calls), 1)
        self.assertEqual(6, calls[-1])
        self.assertEqual(6, report['batchCount'])


if __name__ == '__main__': unittest.main()
