import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_assistant.archives import ArchiveStore
from chat_assistant.core import Message, Settings
from chat_assistant.affinity import AffinityStore, validate_result
from chat_assistant.affinity_runner import run_affinity


class AffinityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive = ArchiveStore(Path(self.temp.name))
        self.profile = self.archive.create('合成人物', '微信', 'test', 'self').id
        self.affinity = AffinityStore(self.archive)
        self.settings = Settings(chat_key='synthetic', chat_model='synthetic-model')

    def tearDown(self):
        self.temp.cleanup()

    def entries(self, count):
        self.archive.import_messages(self.profile, [Message('我' if i % 2 == 0 else '对方',
            f'合成原文{i}', timestamp=f'2026-10-01T12:{i // 60:02d}:{i % 60:02d}+00:00',
            message_id=str(i)) for i in range(count)])
        return self.archive.entries(self.profile)

    def model(self, rows, settings):
        peer = next(r for r in rows if r['speaker'] == '对方')
        return {'rawDelta': 10, 'confidence': .5, 'summary': '双方有具体积极回应。',
                'evidence': [{'entryId': peer['id'], 'quote': peer['text'], 'signal': '接纳'}],
                'uncertainties': ['仅依据文字。']}

    def run_analysis(self, entries, model=None):
        return run_affinity(self.archive, self.settings, self.profile, entries,
                            threading.Event(), analyze=model or self.model)

    def test_99_messages_do_not_call_model_or_change_initial_50(self):
        calls = []
        result = self.run_analysis(self.entries(99), lambda rows, settings: calls.append(rows))
        self.assertEqual([], calls)
        self.assertEqual(50, result['score'])
        self.assertEqual(99, result['pending'])

    def test_perspectives_have_independent_scores_checkpoints_and_original_speakers(self):
        entries = self.entries(100)
        self.run_analysis(entries)
        own_store = AffinityStore(self.archive, 'self')
        self.assertEqual(100, own_store.view(self.profile)['pending'])
        def own_model(rows, settings):
            own = next(r for r in rows if r['speaker'] == '我')
            return {**self.model(rows, settings), 'rawDelta': -4,
                    'evidence': [{'entryId': own['id'], 'quote': own['text'], 'signal': '我表达退让。'}]}
        result = run_affinity(self.archive, self.settings, self.profile, entries,
                              threading.Event(), analyze=own_model, perspective='self')
        self.assertEqual(48, result['score'])
        self.assertEqual('self', result['perspective'])
        self.assertEqual('我', result['batches'][0]['evidence'][0]['speaker'])
        self.assertEqual(55, self.affinity.view(self.profile)['score'])
        reopened = AffinityStore(ArchiveStore(Path(self.temp.name)), 'self')
        self.assertEqual(100, reopened.view(self.profile)['processed'])
        self.assertEqual(0, reopened.view(self.profile)['pending'])

    def test_self_direction_requires_self_evidence(self):
        result = run_affinity(self.archive, self.settings, self.profile, self.entries(100),
                              threading.Event(), analyze=self.model, perspective='self')
        self.assertEqual(50, result['score'])

    def test_insights_persist_and_must_reference_checked_evidence(self):
        entries = self.entries(100)
        raw = self.model([{'id':e.id, 'speaker':e.message.speaker, 'text':e.message.text} for e in entries], self.settings)
        insight = {'text': '可能更习惯直接表达，仅限本段聊天。', 'evidenceIds': [raw['evidence'][0]['entryId']]}
        raw.update(personality=[insight], pursuitAdvice=[insight])
        result = self.run_analysis(entries, lambda rows, settings: raw)
        self.assertEqual([insight], result['batches'][0]['personality'])
        self.assertEqual([insight], result['batches'][0]['pursuitAdvice'])
        for ids in ([], [999999], [entries[0].id], [True]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate_result({**raw, 'personality': [{**insight, 'evidenceIds': ids}]}, entries)

    def test_invalid_perspective_is_rejected(self):
        with self.assertRaises(ValueError): AffinityStore(self.archive, 'invalid')

    def test_provider_receives_explicit_direction_and_keeps_emoji(self):
        from chat_assistant.affinity_runner import analyze_affinity
        with patch('chat_assistant.affinity_runner.post_json', return_value={'choices':[{'message':{'content':'{}'}}]}) as request:
            analyze_affinity([{'id':1, 'speaker':'我', 'text':'😭😠'}], self.settings, 'self')
        payload = request.call_args.args[2]
        self.assertIn('评分主体是“我”', payload['messages'][0]['content'])
        self.assertIn('😭😠', payload['messages'][1]['content'])

    def test_100_messages_apply_confidence_and_persist_without_rerunning(self):
        calls = []
        def analyze(rows, settings):
            calls.append(rows); return self.model(rows, settings)
        entries = self.entries(100)
        result = self.run_analysis(entries, analyze)
        self.assertEqual(55, result['score'])
        self.assertEqual(100, result['processed'])
        self.assertEqual(1, len(calls))
        self.affinity = AffinityStore(ArchiveStore(Path(self.temp.name)))
        result = self.run_analysis(entries[20:], analyze)
        self.assertEqual(55, result['score'])
        self.assertEqual(1, len(calls))
        self.assertEqual(100, self.affinity.view(self.profile)['processed'])

    def test_second_batch_failure_keeps_first_checkpoint_for_resume(self):
        entries = self.entries(200); calls = []
        def fail_second(rows, settings):
            calls.append(rows)
            if len(calls) == 2: raise ValueError('合成断网')
            return self.model(rows, settings)
        self.run_analysis(entries, fail_second)
        with self.assertRaises(ValueError): self.run_analysis(entries, fail_second)
        self.assertEqual(55, self.affinity.view(self.profile)['score'])
        self.assertEqual(100, self.affinity.view(self.profile)['processed'])
        resumed = self.run_analysis(entries)
        self.assertEqual(59.5, resumed['score'])
        self.assertEqual(200, resumed['processed'])

    def test_fabricated_or_self_only_evidence_does_not_raise_affinity(self):
        entries = self.entries(100)
        fake = self.model([{'id':e.id, 'speaker':e.message.speaker, 'text':e.message.text} for e in entries], self.settings)
        fake['evidence'][0]['quote'] = '原文里不存在的表白'
        with self.assertRaises(ValueError): validate_result(fake, entries)
        fake['evidence'] = [{'entryId': entries[0].id, 'quote': entries[0].message.text, 'signal':'我单方面说话'}]
        result = self.run_analysis(entries, lambda rows, settings: fake)
        self.assertEqual(50, result['score'])
        self.assertEqual(0, result['batches'][0]['delta'])

    def test_bad_number_and_foreign_id_are_rejected(self):
        entries = self.entries(100)
        raw = self.model([{'id':e.id, 'speaker':e.message.speaker, 'text':e.message.text} for e in entries], self.settings)
        for value in (True, float('nan'), 11):
            with self.subTest(value=value), self.assertRaises(ValueError): validate_result({**raw,'rawDelta':value},entries)
        raw['evidence'][0]['entryId'] = 999999
        with self.assertRaises(ValueError): validate_result(raw, entries)

    def test_score_never_leaves_bounds_and_negative_change_uses_headroom(self):
        entries = self.entries(300)
        def negative(rows, settings): return {**self.model(rows,settings),'rawDelta':-10,'confidence':1}
        for _ in range(3): result = self.run_analysis(entries, negative)
        self.assertEqual(25.6, result['score'])
        self.assertTrue(all(0 <= batch['after'] <= 100 for batch in result['batches']))

    def test_each_manual_click_analyzes_only_the_next_100_messages(self):
        entries = self.entries(250); calls = []; progress = []
        def analyze(rows, settings):
            calls.append([r['id'] for r in rows]); return self.model(rows, settings)
        def click():
            return run_affinity(self.archive, self.settings, self.profile, entries,
                                threading.Event(), progress.append, analyze)
        first = click()
        self.assertEqual(100, first['processed'])
        self.assertEqual(150, first['pending'])
        self.assertEqual(1, len(calls))
        self.assertEqual(100, progress[-1]['total'])
        second = click()
        self.assertEqual(200, second['processed'])
        self.assertEqual(50, second['pending'])
        self.assertEqual(2, len(calls))
        self.assertTrue(set(calls[0]).isdisjoint(calls[1]))
        click()
        self.assertEqual(2, len(calls))

    def test_atomic_commit_rolls_back_message_marks_when_insert_fails(self):
        entries = self.entries(100)
        with self.archive.connection() as db:
            db.execute("CREATE TRIGGER reject_affinity BEFORE INSERT ON affinity_targets BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END")
        with self.assertRaises(Exception): self.run_analysis(entries)
        self.assertEqual(0, self.affinity.view(self.profile)['processed'])
        self.assertEqual(50, self.affinity.view(self.profile)['score'])

    def test_long_input_stages_resume_without_repeating_paid_success(self):
        entries = self.entries(100)
        for e in entries: e.message.text += '文字' * 300
        calls = []
        def fail_second(rows, settings):
            calls.append(rows)
            if len(calls) == 2: raise ValueError('合成断网')
            return self.model(rows,settings)
        with self.assertRaises(ValueError): self.run_analysis(entries, fail_second)
        first_ids = [r['id'] for r in calls[0]]
        resumed_calls = []
        def resumed(rows,settings): resumed_calls.append(rows); return self.model(rows,settings)
        result = self.run_analysis(entries,resumed)
        self.assertEqual(100,result['processed'])
        self.assertNotEqual(first_ids, [r['id'] for r in resumed_calls[0]])

    def test_maximum_valid_evidence_aggregation_strictly_reduces_paid_calls(self):
        entries=self.entries(100)
        for e in entries: e.message.text='字'*1000+e.message.text+'字'*1000
        calls=[]
        def maximum(rows,settings):
            calls.append(rows)
            if len(calls)>30:raise ValueError('aggregation did not terminate')
            peer=next(r for r in rows if r['speaker']=='对方')
            return {'rawDelta':1,'confidence':1,'summary':'细'*3000,
                    'evidence':[{'entryId':peer['id'],'quote':peer['text'][:1000],'signal':'依'*1000} for _ in range(12)],
                    'uncertainties':['疑'*1000]*12}
        result=self.run_analysis(entries,maximum)
        self.assertEqual(100,result['processed'])
        self.assertLess(len(calls),30)


if __name__ == '__main__': unittest.main()
