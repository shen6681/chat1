import tempfile
import tkinter as tk
import unittest
import time
import json
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from chat_assistant.app import AssistantApp, RoundedButton
from chat_assistant.capture import enable_dpi_awareness
from chat_assistant.storage import SettingsStore
from chat_assistant.core import Message, Settings
from tests.test_api import native_result


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        enable_dpi_awareness()
        self.temp = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp.name))
        self.root = tk.Tk()
        self.app = AssistantApp(self.root,self.store,show_guide=False)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_unsaved_draft_does_not_change_runtime_saved_preferences(self):
        self.app.mode_var.set('TypeSafe Jev')
        self.app.fields['style'].set('轻松温柔')
        self.assertEqual(self.app.saved_settings().mode,'DeepSeek')
        self.assertEqual(self.app.saved_settings().style,'自然简短')
        self.app.chat_size_var.set(13)
        family = list(self.app.fonts.choices)[-1]
        self.app.font_var.set(family)
        self.app.preview_font()
        self.assertEqual(self.app.saved_settings().chat_font_size,11)
        self.app.save_settings()
        reopened = self.store.load()
        self.assertEqual((reopened.mode,reopened.style,reopened.chat_font_size),('TypeSafe Jev','轻松温柔',13))
        self.assertEqual(reopened.font_family,self.app.fonts.choices[family])
        self.assertEqual(self.app.saved_settings().mode,'TypeSafe Jev')

    def test_model_selector_only_in_settings_and_contacts_have_no_analysis_buttons(self):
        self.app.show_page('设置')
        self.root.update()
        modes = [w for w in descendants(self.root) if isinstance(w,ttk.Combobox) and str(w.cget('textvariable'))==str(self.app.mode_var)]
        self.assertEqual(len(modes),1)
        self.assertTrue(modes[0].winfo_ismapped())
        captions = [w.cget('text') for w in descendants(self.app.import_center.page) if isinstance(w,RoundedButton)]
        self.assertNotIn('分析所选时间范围',captions)
        self.assertNotIn('带历史进入实时分析',captions)
        self.assertNotIn('导出为 JSON',captions)
        self.assertIn('打开存档目录',captions)

    def test_batch_view_warns_page_without_pausing_and_selected_explanations_survive_reload(self):
        profile=self.app.archives.create('合成好友','微信','p','self')
        self.app.archives.import_messages(profile.id,[Message('我' if i%2==0 else '对方',f'合成消息{i}',message_id=str(i)) for i in range(23)])
        self.app.settings=Settings(mode='Jev + DeepSeek',jev_key='fake',chat_key='fake')
        self.app.import_center.refresh(profile.id)
        history=self.app.import_center.history;history.PAGE_SIZE=10
        requests=[]
        def post(url,key,body,timeout):
            requests.append(url)
            if url.endswith('/systemone'):
                response=native_result(body['questions'])
                if len(requests)==2:
                    response['answers'].pop('m22_delta',None)
                    # Targets are locally numbered after twenty preceding messages.
                    target=body['state']['targets'][1]
                    response['answers'].pop(f"m{target['index']}_delta",None)
                return response
            state=json.loads(body['messages'][1]['content'])
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'explanations':[{'index':t['index'],'text':'这是用户主动请求的解释。'} for t in state['targets']]})}}]}
        def finish():
            end=time.monotonic()+5
            while history.busy and time.monotonic()<end:
                self.root.update();time.sleep(.01)
            self.assertFalse(history.busy)
        with patch('chat_assistant.batch_analysis.post_json',side_effect=post),patch.object(self.app,'show_error') as error:
            history.start();finish()
            self.assertEqual(self.app.archives.last_run(profile.id)['completed'],23)
            self.assertIn('第 2 页',history.issue_note.get())
            self.assertFalse(error.called)
            self.assertEqual(len(requests),3)
            history.jump_issue()
            self.assertEqual(history.page_index,1)
            history.toggle_selection(history.entries[1].id)
            history.toggle_selection(history.entries[13].id)
            self.assertEqual(len(history.selected_ids),2)
            self.app.import_center.analyzed_profile=profile.id
            history.explain_selected();finish()
            self.assertIsNone(self.app.import_center.analyzed_profile)
            self.assertEqual(len(requests),4)
            self.assertTrue(requests[-1].endswith('/chat/completions'))
            history.apply_range()
            self.assertEqual(sum(bool(e.explanation) for e in history.entries),2)
            self.assertEqual(sum(bool(e.issue) for e in history.entries),1)
            self.assertFalse(history.pause_button.winfo_ismapped())
