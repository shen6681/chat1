import tempfile
import threading
import unittest
from pathlib import Path

from chat_assistant.core import Message
from chat_assistant.web_backend import LocalService


class ProfileDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = LocalService(Path(self.temp.name))
        self.first = self.service.store.create('小林', '微信', 'lin', 'self')
        self.other = self.service.store.create('小王', 'QQ', 'wang', 'self')
        self.service.store.import_messages(self.first.id, [Message('我', '第一条', message_id='one')])
        self.service.store.import_messages(self.other.id, [Message('对方', '保留这条', message_id='two')])

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_delete_removes_profile_and_related_data_but_preserves_others(self):
        entry = self.service.store.entries(self.first.id)[0]
        self.service.store.save_rating(self.first.id, entry.id, {'speaker': '我'}, 'context', 'signature')
        self.service.store.save_stages([{'entry_id': entry.id, 'speaker': '我'}], 'signature', 'context')
        self.service.store.save_explanations(self.first.id, [{'entry_id': entry.id, 'text': '解释', 'source': 'test'}])
        run = self.service.store.begin_run(self.first.id, '', '', [entry], 'signature', 'model')
        self.service.affinity.save_stage(self.first.id, 'affinity-test', {'score': 51})
        self.service.self_affinity.save_stage(self.first.id, 'self-test', {'score': 52})
        with self.service.store.connection() as db:
            db.execute("INSERT INTO affinity_batches VALUES(?,?,?,?,?,?,?,?)", ('batch', self.first.id, 50, 1, 51, '{}', 'model', 'now'))
            db.execute("INSERT INTO affinity_targets VALUES(?,?)", (entry.id, 'batch'))
        self.assertEqual({'deleted': self.first.id}, self.service.post('/api/profiles/delete', {'id': self.first.id}))
        self.assertEqual([self.other.id], [p.id for p in self.service.store.profiles()])
        self.assertEqual(['保留这条'], [m.text for m in self.service.store.messages(self.other.id)])
        with self.service.store.connection() as db:
            for table in ('messages', 'analysis_runs', 'analysis_leases', 'affinity_batches', 'affinity_stages', 'self_affinity_stages'):
                self.assertEqual(0, db.execute(f'SELECT COUNT(*) FROM {table} WHERE profile_id=?', (self.first.id,)).fetchone()[0], table)
            for table, column, value in (('message_ratings', 'message_seq', entry.id), ('message_explanations', 'message_seq', entry.id), ('analysis_stages', 'message_seq', entry.id), ('analysis_targets', 'run_id', run), ('affinity_targets', 'message_seq', entry.id)):
                self.assertEqual(0, db.execute(f'SELECT COUNT(*) FROM {table} WHERE {column}=?', (value,)).fetchone()[0], table)
            self.assertEqual([], db.execute('PRAGMA foreign_key_check').fetchall())
        with self.assertRaisesRegex(ValueError, '不存在'):
            self.service.post('/api/profiles/delete', {'id': self.first.id})

    def test_running_task_blocks_deletion(self):
        self.service.tasks['running'] = {'profile': self.first.id, 'state': 'running'}
        try:
            with self.assertRaisesRegex(ValueError, '正在分析'):
                self.service.post('/api/profiles/delete', {'id': self.first.id})
            self.assertEqual(self.first.id, self.service.store.profile(self.first.id).id)
        finally:
            self.service.tasks.pop('running')

    def test_active_analysis_lease_blocks_deletion(self):
        self.assertTrue(self.service.store.acquire_analysis(self.first.id, 'other-process'))
        with self.assertRaisesRegex(ValueError, '正在分析'):
            self.service.post('/api/profiles/delete', {'id': self.first.id})
        self.service.store.release_analysis(self.first.id, 'other-process')
        self.assertEqual({'deleted': self.first.id}, self.service.post('/api/profiles/delete', {'id': self.first.id}))


if __name__ == '__main__':
    unittest.main()
