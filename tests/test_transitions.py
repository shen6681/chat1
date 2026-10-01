import gc
import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from chat_assistant.app import AssistantApp,button
from chat_assistant.storage import SettingsStore
from chat_assistant.ui_themes import theme_color


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        from chat_assistant.capture import enable_dpi_awareness
        enable_dpi_awareness()
        self.root=tk.Tk()
        self.app=AssistantApp(self.root,SettingsStore(Path(self.temp.name)),show_guide=False)
        self.root.geometry('1100x760+30+30');self.root.attributes('-topmost',True)
        self.root.update()

    def tearDown(self):
        self.app.close();self.app=None;self.root=None
        gc.collect();self.temp.cleanup()

    def settle(self):
        deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            self.root.update()
            if not self.app.page_transition.running:return
            time.sleep(.01)
        self.fail('Page animation did not finish')

    def test_switch_keeps_old_and_new_mapped_and_avoids_style_walks(self):
        old=self.app.pages['导入记录']
        with patch.object(self.app.fonts,'apply',wraps=self.app.fonts.apply) as fonts,patch.object(self.app.themes,'apply',wraps=self.app.themes.apply) as themes:
            self.app.show_page('设置');self.root.update()
            self.assertTrue(old.winfo_ismapped(),'Do not unmap the rendered page during a switch')
            self.assertTrue(self.app.pages['设置'].winfo_ismapped())
            self.assertEqual(fonts.call_count,0,'Warm navigation must not reapply fonts')
            self.assertEqual(themes.call_count,0,'Warm navigation must not recolor the widget tree')
            self.settle()
        self.assertEqual(self.app.pages['设置'].winfo_x(),0)

    def test_rapid_navigation_same_page_and_close_cancel_animation(self):
        self.assertTrue(hasattr(self.app,'page_transition'),'Navigation needs a cancellable transition')
        self.app.show_page('设置')
        self.assertTrue(self.app.page_transition.running)
        token=self.app.page_transition.timer
        self.app.show_page('设置')
        self.assertEqual(self.app.page_transition.timer,token,'Repeated clicks must not restart a transition')
        for name in ('实时分析','使用说明','导入记录','设置'):
            self.app.show_page(name)
        self.settle()
        self.assertEqual(self.app.current_page,'设置')
        self.assertTrue(self.app.nav_buttons['设置'].selected)
        self.assertTrue(all(p.winfo_x()==0 for p in self.app.pages.values()))
        self.app.fields['goal'].set('合成：保留未保存草稿')
        self.app.settings_panel.canvas.yview_moveto(.5)
        position=self.app.settings_panel.canvas.yview()
        self.app.show_page('实时分析');self.settle()
        self.app.show_page('设置');self.settle()
        self.assertEqual(self.app.fields['goal'].get(),'合成：保留未保存草稿')
        self.assertEqual(self.app.settings_panel.canvas.yview(),position)
        self.app.show_page('导入记录')
        self.app.page_transition.close()
        self.assertFalse(self.app.page_transition.running)
        self.assertIsNone(self.app.page_transition.timer)

    def test_navigation_never_moves_content(self):
        self.assertTrue(hasattr(self.app,'page_transition'))
        self.app.show_page('设置');self.root.update()
        for _ in range(12):
            self.root.update()
            self.assertTrue(all((p.winfo_x(),p.winfo_y())==(0,0) for p in self.app.pages.values()),'Content must not slide or shake')
            time.sleep(.016)
        self.settle()

    @unittest.skipUnless(os.name=='nt','Windows native paint regression')
    def test_windows_switch_repaints_cached_page_without_old_content(self):
        from chat_assistant.capture import grab
        from chat_assistant.core import Region
        import numpy as np
        panel=self.app.settings_panel
        region=Region(panel.winfo_rootx(),panel.winfo_rooty(),panel.winfo_width(),panel.winfo_height())
        grab(Region(self.root.winfo_rootx(),self.root.winfo_rooty(),self.root.winfo_width(),self.root.winfo_height()))
        self.app.show_page('设置')
        # One ordinary event-loop turn, not an extra resize / theme update that
        # could hide missing native invalidation. Exclude the animated heading.
        frames=[]
        self.root.after(40,lambda:frames.append(np.asarray(grab(region)).astype(int)))
        self.root.after(80,self.root.quit);self.root.mainloop()
        actual=frames[0]
        # Compare against a fully invalidated native surface, not another
        # screenshot that might contain the very same stale pixels.
        import ctypes
        ctypes.windll.user32.RedrawWindow(ctypes.c_void_p(self.app.pages['设置'].winfo_id()),None,None,0x185)
        self.root.update();time.sleep(.04)
        expected=np.asarray(grab(region)).astype(int)
        changed=float(np.mean(np.max(np.abs(expected-actual),axis=2)>12))
        self.assertLess(changed,.01,'Previous page pixels must not survive under newly raised controls')

    def test_keyboard_focus_and_dynamic_controls_are_isolated(self):
        self.assertTrue(hasattr(self.app,'page_transition'))
        self.app.show_page('设置',animate=False)
        entry=self.app.font_combo
        entry.focus_force();self.root.update()
        self.app.show_page('导入记录');self.root.update()
        self.assertEqual(self.root.focus_get(),self.app.nav_buttons['导入记录'],'Move focus off hidden settings fields')
        first=self.app.nav_buttons['使用说明'];widget=first
        visited=set()
        for _ in range(100):
            widget=self.root.tk.call('tk_focusNext',str(widget))
            if str(widget) in visited:break
            visited.add(str(widget))
        forbidden=[str(self.app.pages[k]) for k in self.app.pages if k!='导入记录']
        self.assertFalse(any(any(w.startswith(page+'.') or w==page for page in forbidden) for w in visited),'Tab must not activate hidden controls')
        self.assertIn(str(self.app.import_center.search_entry),visited)
        widget=first
        for _ in range(80):
            widget=self.root.tk.call('tk_focusPrev',str(widget))
            self.assertFalse(any(str(widget).startswith(page+'.') or str(widget)==page for page in forbidden),'Shift-Tab must stay in the active page')
        self.settle()
        hidden=button(self.app.pages['实时分析'],'合成后台按钮',lambda:None)
        hidden.place(x=0,y=0);self.root.update()
        self.assertEqual(str(hidden.cget('takefocus')),'0')
        self.app.show_page('实时分析');self.settle()
        self.assertEqual(str(hidden.cget('takefocus')),'1')
        hidden.destroy()

    def test_resize_during_switch_settles_inside_page_and_new_dialogs_still_style(self):
        self.assertTrue(hasattr(self.app,'page_transition'))
        self.app.show_page('设置')
        self.root.geometry('1260x830');self.root.update();self.settle()
        page=self.app.pages['设置'];container=self.app.page_container
        self.assertEqual((page.winfo_x(),page.winfo_y()),(0,0))
        self.assertEqual((page.winfo_width(),page.winfo_height()),(container.winfo_width(),container.winfo_height()))
        self.app.theme_var.set('樱花粉');self.app.preview_theme()
        window=tk.Toplevel(self.root)
        new_button=button(window,'新对话框',lambda:None,True);new_button.pack()
        label=tk.Label(window,text='新窗口文字',font=('Arial',9),bg='#F4F6FB');label.pack()
        self.root.update()
        self.assertEqual(label.cget('bg'),theme_color(self.root,'#F4F6FB'))
        from tkinter import font
        self.assertEqual(font.Font(root=self.root,font=label.cget('font')).actual('family'),self.app.fonts.family)
        self.assertIn(theme_color(self.root,'#6658D9'),[new_button.itemcget(i,'fill') for i in new_button.find_all()])
        window.destroy()

    def test_newbie_guide_skips_animation_when_positioning_real_controls(self):
        self.assertTrue(hasattr(self.app,'page_transition'))
        self.app.show_page('设置')
        self.app.start_guide();self.root.update()
        self.app.guide.next();self.root.update()
        self.assertFalse(self.app.page_transition.running,'Guide anchors must already be at their final position')
        self.assertEqual(self.app.pages['设置'].winfo_x(),0)
        self.app.guide.skip()

    def test_theme_change_during_transition_preserves_final_title_colors(self):
        self.app.show_page('设置')
        self.assertTrue(self.app.page_transition.running)
        self.app.theme_var.set('樱花粉');self.app.preview_theme()
        self.assertFalse(self.app.page_transition.running)
        for label in self.app.page_transition.headings[self.app.pages['设置']]:
            self.assertEqual(label.cget('fg'),theme_color(self.root,'#24304A'))
        self.app.show_page('导入记录');self.settle()
        self.app.theme_var.set('清透蓝');self.app.preview_theme()
        for page in self.app.pages.values():
            for label in self.app.page_transition.headings[page]:
                self.assertEqual(label.cget('fg'),theme_color(self.root,'#24304A'))
