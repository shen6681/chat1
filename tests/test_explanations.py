import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_assistant.archives import ArchiveStore
from chat_assistant.core import Message, Settings
from tests.test_history import rating
import chat_assistant.batch_analysis as batch


class ExplanationTests(unittest.TestCase):
    def test_selected_explanation_is_text_only_and_preserves_jev_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ArchiveStore(Path(folder)); p=store.create('合成','微信','p','self')
            store.import_messages(p.id,[Message('我' if i%2==0 else '对方',f'合成{i}') for i in range(6)])
            entries=store.entries(p.id)
            for entry in entries:
                store.save_rating(p.id,entry.id,rating(entry.message.speaker),'h','s')
            before=[e.rating for e in store.entries(p.id)]
            sent=[]
            def post(url,key,payload,timeout):
                sent.append((url,payload))
                state=json.loads(payload['messages'][1]['content'])
                return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'explanations':[{'index':t['index'],'text':'结合前文，表达自然，先回应问题。'} for t in state['targets']]})}}]}
            self.assertTrue(hasattr(batch,'explain_messages'),'缺少按需解释入口')
            with patch('chat_assistant.batch_analysis.post_json',side_effect=post):
                results=batch.explain_messages(Settings(chat_key='fake',mode='TypeSafe Jev'),entries,[1,3])
            self.assertEqual([r['entry_id'] for r in results],[entries[1].id,entries[3].id])
            self.assertEqual(len(sent),1)
            self.assertTrue(sent[0][0].endswith('/chat/completions'))
            self.assertNotIn('image_url',json.dumps(sent))
            state=json.loads(sent[0][1]['messages'][1]['content'])
            self.assertEqual([t['index'] for t in state['targets']],[2,3])
            store.save_explanations(p.id,results)
            after=ArchiveStore(Path(folder)).entries(p.id)
            self.assertEqual([e.rating for e in after],before)
            self.assertEqual(after[1].explanation['text'],'结合前文，表达自然，先回应问题。')
            self.assertIsNone(after[0].explanation)

