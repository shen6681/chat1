import json
import gc
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_assistant.app import AssistantApp, button
from chat_assistant.core import Settings, Message
from chat_assistant.storage import SettingsStore
from chat_assistant.onboarding import GuideState
from chat_assistant.ui_fonts import bundled_fonts
from chat_assistant.ui_themes import PALETTES, THEMES


class AppearanceGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp.name))
        self.root = tk.Tk()
        self.app = AssistantApp(self.root, self.store, show_guide=False)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.app=None
        self.root=None
        gc.collect()  # Dispose obsolete Tk variables on their owning thread before later worker tests.
        self.temp.cleanup()

    def test_bundled_fonts_are_real_available_and_saved(self):
        fonts = bundled_fonts()
        self.assertEqual(len(fonts), 4)
        for entry in fonts:
            self.assertIn(entry['label'], self.app.fonts.choices)
        choice = fonts[0]['label']
        self.app.font_var.set(choice)
        self.app.preview_font()
        actual = self.app.fonts.font().actual('family')
        self.assertIn(actual, (fonts[0]['family'], '霞鹜文楷 轻便版'))
        self.app.save_settings()
        self.assertEqual(self.store.load().font_family, self.app.fonts.choices[choice])
        selected_family=self.app.fonts.family
        self.app.close()
        self.root=tk.Tk()
        self.app=AssistantApp(self.root,self.store,show_guide=False)
        self.root.update()
        self.assertEqual(self.app.fonts.family,selected_family)

    def test_theme_preview_save_reopen_and_new_dialog_and_canvas(self):
        self.app.theme_var.set('樱花粉')
        self.app.preview_theme()
        expected = PALETTES['sakura']['#F4F6FB']
        self.assertEqual(self.root.cget('bg'), expected)
        self.assertEqual(self.app.saved_settings().theme, 'blue')
        dialog = tk.Toplevel(self.root)
        new_button = button(dialog, '新按钮', lambda:None, True)
        new_button.pack()
        self.root.update()
        fills = [new_button.itemcget(i,'fill') for i in new_button.find_all()]
        self.assertIn(PALETTES['sakura']['#6658D9'], fills)
        profile = self.app.archives.create('合成', '微信', 'p', 'self')
        self.app.archives.import_messages(profile.id,[Message('我','你好'),Message('对方','晚上好')])
        self.app.import_center.refresh(profile.id)
        self.root.update()
        self.app.import_center.history.chat.draw()
        canvas = self.app.import_center.history.chat.canvas
        self.assertEqual(canvas.cget('bg'), PALETTES['sakura']['#EEF2F5'])
        self.assertIn(PALETTES['sakura']['#95EC69'], [canvas.itemcget(i,'fill') for i in canvas.find_all() if canvas.type(i)=='polygon'])
        self.app.save_settings()
        self.assertEqual(self.store.load().theme, 'sakura')
        dialog.destroy()
        self.app.close()
        self.root = tk.Tk()
        self.app = AssistantApp(self.root,self.store,show_guide=False)
        self.root.update()
        self.assertEqual(self.root.cget('bg'), expected)
        for label, name in THEMES.items():
            self.app.theme_var.set(label); self.app.preview_theme()
            self.assertEqual(self.root.cget('bg'), PALETTES[name]['#F4F6FB'])
            self.root.update()
            primary=self.app.import_center.import_button
            self.assertIn(PALETTES[name]['#6658D9'],[primary.itemcget(i,'fill') for i in primary.find_all()])
            primary.set_hover(True);primary.set_hover(False)
            self.assertIn(PALETTES[name]['#6658D9'],[primary.itemcget(i,'fill') for i in primary.find_all()])

    def test_skipping_guide_is_once_and_does_not_save_credentials_draft(self):
        self.store.save(Settings(chat_key='synthetic-saved-key'))
        original = self.store.path.read_bytes()
        self.app.fields['chat_key'].set('synthetic-unsaved-draft')
        self.app.start_guide()
        self.root.update()
        self.assertIsNotNone(self.app.guide)
        self.app.guide.skip()
        self.assertTrue(GuideState(self.store.directory).done)
        self.assertEqual(original,self.store.path.read_bytes())
        self.assertEqual(self.app.fields['chat_key'].get(),'synthetic-unsaved-draft')
        self.app.maybe_start_guide()
        self.assertIsNone(self.app.guide)
        self.app.start_guide()
        self.assertIsNotNone(self.app.guide)  # Help can replay it voluntarily.
        self.app.guide.skip()

    def test_complete_guide_uses_no_api_and_stays_inside_small_window(self):
        self.root.geometry('1100x760')
        with patch('urllib.request.urlopen',side_effect=AssertionError('No tutorial API requests')):
            self.app.start_guide()
            guide = self.app.guide
            for i in range(len(guide.steps)):
                self.root.update()
                guide.position()
                box = guide.card
                self.assertGreaterEqual(box.winfo_x(), 0)
                self.assertGreaterEqual(box.winfo_y(), 0)
                self.assertLessEqual(box.winfo_x()+box.winfo_width(), self.root.winfo_width())
                self.assertLessEqual(box.winfo_y()+box.winfo_height(), self.root.winfo_height())
                guide.next()
        self.assertIsNone(self.app.guide)
        state = json.loads((self.store.directory/'ui_state.json').read_text())
        self.assertEqual(state['onboarding'], 'completed')
        self.app.maybe_start_guide()
        self.assertIsNone(self.app.guide)

    def test_first_launch_is_automatic_and_close_cleans_callbacks(self):
        self.app.close()
        self.root = tk.Tk()
        self.app = AssistantApp(self.root,self.store)
        self.root.after(950, self.root.quit)
        self.root.mainloop()
        self.assertIsNotNone(self.app.guide)
        self.assertFalse(GuideState(self.store.directory).done)
        self.app.guide.skip()
        self.app.close()
        self.root = tk.Tk()
        self.app = AssistantApp(self.root,self.store)
        self.root.after(950,self.root.quit)
        self.root.mainloop()
        self.assertIsNone(self.app.guide)

    def test_legacy_settings_default_theme_and_invalid_theme_rejected(self):
        self.store.directory.mkdir(exist_ok=True)
        self.store.path.write_text('{"mode":"TypeSafe Jev"}')
        self.assertEqual(self.store.load().theme,'blue')
        with self.assertRaises(ValueError):
            Settings(theme='nonexistent').validate(require_keys=False)
