import gc
import tempfile
import tkinter as tk
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chat_assistant.app import AssistantApp
from chat_assistant.core import Message
from chat_assistant.storage import SettingsStore
from chat_assistant.ui_themes import theme_color
from chat_assistant.history_analysis import time_bounds


class DateLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=tk.Tk()
        self.app=AssistantApp(self.root,SettingsStore(Path(self.temp.name)),show_guide=False)
        self.root.geometry('1100x760')
        self.root.update()
        self.center=self.app.import_center
        self.history=self.center.history

    def tearDown(self):
        self.app.close();self.app=None;self.root=None;self.center=None;self.history=None
        gc.collect();self.temp.cleanup()

    def add_profile(self,name='合成好友'):
        p=self.app.archives.create(name,'微信',name,'self')
        self.app.archives.import_messages(p.id,[Message('对方',f'第{d}天',timestamp=f'2026-09-{d:02d}T12:00:00+08:00',message_id=str(d)) for d in range(20,31)]+[Message('我','十月',timestamp='2026-10-01T12:00:00+08:00',message_id='oct')])
        self.center.refresh(p.id)
        return p

    def test_date_popup_leap_day_cancel_and_range_validation(self):
        self.assertTrue(hasattr(self.history,'start_picker'),'Time fields must open a date picker')
        self.add_profile()
        self.history.start_var.set('2024-02-28');self.history.end_var.set('2024-03-01')
        picker=self.history.start_picker.open()
        self.root.update()
        self.assertLessEqual(picker.window.winfo_rooty()+picker.window.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height()-6)
        picker.set_month(2024,2);picker.choose_day(29);picker.confirm()
        self.assertEqual(self.history.start_var.get(),'2024-02-29')
        picker=self.history.start_picker.open()
        picker.set_month(2024,3);picker.choose_day(5);picker.confirm()
        self.assertTrue(picker.window.winfo_exists())
        self.assertIn('开始',picker.error.get())
        self.assertEqual(self.history.start_var.get(),'2024-02-29')
        picker.close()
        picker=self.history.start_picker.open()
        picker.set_month(2024,12);picker.move_month(1)
        self.root.update()
        self.assertEqual(len(picker.day_buttons),31)
        self.assertLessEqual(picker.window.winfo_rooty()+picker.window.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height()-6)
        self.assertEqual((picker.year,picker.month),(2025,1))
        picker.choose_day(10);picker.close()
        self.assertEqual(self.history.start_var.get(),'2024-02-29')

    def test_quick_ranges_beijing_inclusive_week_and_reset(self):
        self.assertTrue(hasattr(self.history,'quick_range'),'Quick date ranges are missing')
        p=self.add_profile()
        with patch('chat_assistant.date_picker.beijing_today',return_value=date(2026,10,1)):
            self.history.quick_range('today')
            self.assertEqual((self.history.start_var.get(),self.history.end_var.get()),('2026-10-01','2026-10-01'))
            self.assertEqual(len(self.history.entries),1)
            self.history.quick_range('week')
            self.assertEqual((self.history.start_var.get(),self.history.end_var.get()),('2026-09-25','2026-10-01'))
            self.assertEqual(len(self.history.entries),7)
            self.history.quick_range('all')
            self.assertEqual(len(self.history.entries),12)
            self.app.archives.import_messages(p.id,[Message('对方','今日零点',timestamp='2026-10-01T00:00:00+08:00',message_id='midnight'),
                Message('我','今日最后一秒',timestamp='2026-10-01T23:59:59+08:00',message_id='end'),
                Message('对方','次日零点',timestamp='2026-10-02T00:00:00+08:00',message_id='outside')])
            self.history.quick_range('today')
            self.assertEqual({e.message.text for e in self.history.entries},{'十月','今日零点','今日最后一秒'})
            self.history.quick_range('today');self.history.reset_range()
            self.assertEqual((self.history.start_var.get(),self.history.end_var.get()),('',''))
            self.assertEqual(len(self.history.entries),15)

    def test_precise_time_can_be_restored_and_selected_in_popup(self):
        self.assertTrue(hasattr(self.history,'start_picker'))
        self.add_profile()
        self.history.start_var.set('2026-09-30 12:34:56')
        picker=self.history.start_picker.open()
        self.assertTrue(picker.time_enabled.get())
        self.assertEqual((picker.hour.get(),picker.minute.get(),picker.second.get()),('12','34','56'))
        picker.choose_day(29);picker.confirm()
        self.assertEqual(self.history.start_var.get(),'2026-09-29 12:34:56')
        self.history.start_var.set('2026-09-30 12:00')
        self.history.end_var.set('2026-09-30 12:34')
        bounds=time_bounds(self.history.start_var.get(),self.history.end_var.get())
        for field in (self.history.start_picker,self.history.end_picker):
            picker=field.open();picker.confirm()
        self.assertEqual(self.history.end_var.get(),'2026-09-30 12:34')
        self.assertEqual(time_bounds(self.history.start_var.get(),self.history.end_var.get()),bounds)
        self.history.start_var.set('2024/02/29')
        picker=self.history.start_picker.open();picker.confirm()
        self.assertEqual(self.history.start_var.get(),'2024-02-29')

    def test_three_cards_and_controls_fit_small_window(self):
        self.assertTrue(hasattr(self.center,'contact_card'),'Contacts need a separate rounded card')
        self.add_profile();self.root.update()
        cards=[self.center.contact_card,self.center.message_card,self.center.character_card]
        for card in cards:
            self.assertEqual(card.radius,6)
            self.assertTrue(card.winfo_ismapped())
            self.assertLessEqual(card.winfo_rootx()+card.winfo_width(),self.root.winfo_rootx()+self.root.winfo_width())
        self.assertLessEqual(cards[0].winfo_rootx()+cards[0].winfo_width(),cards[1].winfo_rootx())
        self.assertLessEqual(cards[1].winfo_rootx()+cards[1].winfo_width(),cards[2].winfo_rootx())
        self.assertEqual(self.history.character.master,self.center.character_body)
        self.assertTrue(self.center.import_button.primary)
        self.assertTrue(self.history.start_button.primary)
        self.assertFalse(self.history.filter_button.primary)
        self.assertFalse(self.history.more_button.primary)
        for control in (self.history.start_picker,self.history.end_picker,self.history.filter_button,self.history.reset_button):
            self.assertGreaterEqual(control.winfo_rootx(),cards[1].winfo_rootx())
            self.assertLessEqual(control.winfo_rootx()+control.winfo_width(),cards[1].winfo_rootx()+cards[1].winfo_width())

    def test_contacts_hover_search_and_friendly_empty_state(self):
        self.assertTrue(hasattr(self.center.list,'hover_at'),'Contact hover is missing')
        p=self.add_profile('小林');self.add_profile('小王');self.center.refresh(p.id);self.root.update()
        first=self.center.list.bbox(0)
        self.center.list.hover_at(SimpleNamespace(y=first[1]+2))
        self.assertEqual(self.center.list.hover_index,0)
        self.assertEqual(self.center.list.itemcget(0,'background'),theme_color(self.root,'#EEF1FA'))
        self.center.list.clear_hover()
        self.assertEqual(self.center.list.hover_index,-1)
        self.center.search_var.set('不存在的联系人');self.root.update()
        self.assertEqual(self.center.list.size(),0)
        self.assertIsNone(self.history.profile)
        texts=[self.history.chat.canvas.itemcget(i,'text') for i in self.history.chat.canvas.find_all() if self.history.chat.canvas.type(i)=='text']
        self.assertTrue(any('选择联系人' in text for text in texts))
        self.assertEqual(self.history.start_button.cget('state'),'disabled')

    def test_background_preview_save_and_reopen_without_saving_other_drafts(self):
        self.assertTrue(hasattr(self.app,'surface_var'),'Section background selector is missing')
        original=self.app.saved_settings()
        self.app.surface_var.set('雾蓝');self.app.preview_theme();self.root.update()
        preview=self.root.cget('bg')
        self.assertEqual(self.app.saved_settings().surface_scheme,original.surface_scheme)
        self.app.save_settings()
        self.app.close();self.root=tk.Tk()
        self.app=AssistantApp(self.root,SettingsStore(Path(self.temp.name)),show_guide=False)
        self.root.update();self.center=self.app.import_center;self.history=self.center.history
        self.assertEqual(self.app.saved_settings().surface_scheme,'mist')
        self.assertEqual(self.root.cget('bg'),preview)

    def test_tooltip_delayed_show_hide_does_not_change_focus_or_settings(self):
        self.assertTrue(hasattr(self.history,'range_tooltip'),'Date help must be in a tooltip')
        tooltip=self.history.range_tooltip
        self.assertIsNone(tooltip.window)
        tooltip.show()
        self.root.update()
        self.assertTrue(tooltip.window.winfo_exists())
        self.assertIsNone(self.root.grab_current())
        tooltip.hide();self.root.update()
        self.assertIsNone(tooltip.window)
        self.assertFalse(self.app.store.path.exists())
        # A visible child tooltip must not corrupt Tcl's default root on close.
        tooltip.show();self.root.update()
        self.app.close();self.root=tk.Tk()
        self.app=AssistantApp(self.root,SettingsStore(Path(self.temp.name)),show_guide=False)
        self.center=self.app.import_center;self.history=self.center.history
        self.root.update()
        self.assertFalse(self.app.store.path.exists())
