import tempfile
import tkinter as tk
import unittest
import time
from pathlib import Path
from functools import partial
from chat_assistant.history_runner import run_history
from unittest.mock import patch

from chat_assistant.app import AssistantApp, set_text
from chat_assistant.capture import CaptureTarget, CaptureUnavailable, enable_dpi_awareness, window_at
from chat_assistant.core import Region
from chat_assistant.storage import SettingsStore


class UITests(unittest.TestCase):
    def setUp(self):
        enable_dpi_awareness()
        self.folder = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.app = AssistantApp(self.root, SettingsStore(Path(self.folder.name)),show_guide=False)
        self.root.geometry("1180x820+100+100")
        self.root.attributes("-topmost", True)
        self.settle()

    def settle(self):
        # Wait for the native window manager to finish map / move messages.
        end = time.monotonic() + .2
        while time.monotonic() < end:
            self.root.update()
            time.sleep(.01)

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def test_demo_clear_and_editor_invalidate_results(self):
        self.app.load_demo()
        self.root.update()
        self.assertIsNotNone(self.app.result)
        self.app.editor.insert("end", "\n对方：我先睡了")
        self.root.update()
        self.assertIsNone(self.app.result)
        self.app.clear()
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "")
        self.assertIsNone(self.app.result_transcript)

    def test_unreadable_crop_clears_data_and_invalidates_inflight_result(self):
        self.app.load_demo()
        self.app.monitoring = True
        generation = self.app.generation
        self.app.events.put((1, generation, "unavailable", "聊天被遮挡"))
        self.app.poll()
        self.assertIsNone(self.app.result)
        self.assertIsNone(self.app.image)
        self.assertIsNone(self.app.transcript)
        self.assertGreater(self.app.generation, generation)

    def test_actual_window_binding_and_movement(self):
        # Only this application's test window is inspected, never QQ / WeChat.
        self.root.lift()
        self.root.update()
        region = Region(self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20, 160, 100)
        target = CaptureTarget.bind(region)
        self.assertEqual(target.resolve(), region)
        self.root.geometry("1180x820+100+70")
        self.settle()
        moved = target.resolve()
        self.assertEqual((moved.width, moved.height), (160, 100))
        self.assertEqual((moved.left, moved.top), (self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20))
        self.root.geometry("1200x820+100+70")
        self.settle()
        with self.assertRaises(CaptureUnavailable):
            target.resolve()

    def test_occlusion_guard_does_not_accept_other_window(self):
        region = Region(self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20, 160, 100)
        target = CaptureTarget.bind(region)
        with patch("chat_assistant.capture.window_at", return_value=target.hwnd + 1):
            with self.assertRaises(CaptureUnavailable):
                target.resolve()

    def test_archive_selection_clear_and_contact_switch_isolation(self):
        from chat_assistant.core import Message
        first = self.app.archives.create("小林", "微信", "lin", "我")
        self.app.archives.import_messages(first.id, [Message("对方", "周末想看电影")])
        second = self.app.archives.create("小王", "QQ", "wang", "我")
        self.app.archives.import_messages(second.id, [Message("对方", "其他人的记录")])
        self.app.import_center.refresh(first.id)
        self.app.import_center.realtime()
        self.assertEqual(self.app.active_profile, first.id)
        self.app.clear()
        self.assertEqual(self.app.active_profile, first.id)
        self.assertEqual(self.app.archives.profile(first.id).count, 1)
        self.app.activate_profile(second.id)
        self.assertIsNone(self.app.target)
        self.assertIsNone(self.app.result)
        self.assertEqual(self.app.active_profile, second.id)
        self.app.activate_profile(None)
        self.assertIsNone(self.app.active_profile)

    def test_embedded_preview_confirm_import_without_api(self):
        from chat_assistant.importers import from_json
        bundle = from_json({"chatlab": {}, "meta": {"name": "小林", "type": "private", "ownerId": "self"}, "messages": [{"sender": "self", "type": 0, "content": "你好"}, {"sender": "other", "type": 0, "content": "最近怎么样"}]})
        self.app.import_center.preview(bundle)
        self.root.update()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        from chat_assistant.app import RoundedButton
        commit = next(w for w in descendants(self.root) if isinstance(w, (tk.Button, RoundedButton)) and w.cget("text") == "确认身份并保存档案")
        commit.invoke()
        self.root.update()
        self.assertEqual(len(self.app.archives.profiles()), 1)
        self.assertEqual(self.app.archives.profile(self.app.active_profile).count, 2)
        self.assertIsNone(self.app.analysis_job)

    def test_qq_export_center_can_read_preview_and_archive_at_minimum_size(self):
        from chat_assistant.qq_ui import QQExportDialog
        from chat_assistant.importers import from_json
        from chat_assistant.app import RoundedButton
        data={"chatlab":{},"meta":{"name":"合成好友","type":"private","platform":"qq","ownerId":"10001"},"messages":[{"sender":"10001","type":0,"content":"最近怎么样"},{"sender":"10002","type":0,"content":"今天忙完了"}]}
        bundle=from_json(data)
        self.app.import_center.search_var.set("找不到的新联系人")
        with patch("chat_assistant.qq_ui.QQHistoryClient") as factory:
            factory.return_value.connect.return_value=({"user_id":10001,"nickname":"合成账号"},[{"user_id":10002,"nickname":"合成好友"}])
            factory.return_value.history.return_value=(bundle,data)
            dialog=QQExportDialog(self.app.import_center)
            dialog.window.geometry("850x700")
            self.settle()
            for action in [dialog.import_button,dialog.save_button,dialog.read_button]:
                self.assertTrue(action.winfo_ismapped())
                self.assertLessEqual(action.winfo_rooty()+action.winfo_height(),dialog.window.winfo_rooty()+dialog.window.winfo_height())
            def finished():
                deadline=time.monotonic()+4
                while dialog.busy and time.monotonic()<deadline:
                    self.root.update();time.sleep(.02)
                self.assertFalse(dialog.busy)
            dialog.connect();finished()
            self.assertEqual(dialog.friend_combo.current(),0)
            dialog.read_button.invoke();finished()
            self.assertEqual(dialog.import_button.cget("state"),"normal")
            dialog.import_button.invoke();self.root.update()
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child;yield from descendants(child)
            commit=next(w for w in descendants(self.root) if isinstance(w,RoundedButton) and w.cget("text")=="确认身份并保存档案")
            commit.invoke();self.root.update()
            self.assertEqual(self.app.import_center.search_var.get(),"")
            self.assertEqual(self.app.archives.profile(self.app.active_profile).count,2)
            self.assertEqual(self.app.import_center.current_profile().id,self.app.active_profile)
            self.assertIsNone(self.app.analysis_job)

    def test_range_bubbles_checkpoint_resume_and_draggable_orb(self):
        from chat_assistant.core import Message, Settings
        from tests.test_history import rating
        profile=self.app.archives.create("合成好友","微信","range","self")
        self.app.archives.import_messages(profile.id,[Message("我" if i%2==0 else "对方",f"合成聊天 {i}",
              timestamp=f"2026-09-30T12:0{i}:00+00:00") for i in range(4)]+[Message("对方","范围外",timestamp="2026-10-01T01:00:00+00:00")])
        center=self.app.import_center
        center.refresh(profile.id)
        self.app.show_page("导入记录")
        history=center.history
        history.start_var.set("2026-09-30");history.end_var.set("2026-09-30")
        history.apply_range()
        self.assertEqual(len(history.entries),4)
        calls=[]
        def score(s,t,*a,**k):
            calls.append(t.messages[-1].text)
            self.assertNotIn("范围外",t.text)
            if len(calls)==2:
                history.cancel.set()
            return rating(t.messages[-1].speaker,score=75)
        def finish():
            deadline=time.monotonic()+5
            while history.busy and time.monotonic()<deadline:
                self.root.update();time.sleep(.02)
            self.assertFalse(history.busy)
        with patch.object(self.app,"saved_settings",return_value=Settings(chat_key="synthetic")),patch("chat_assistant.history_ui.run_history",side_effect=partial(run_history,batch_size=1)),patch("chat_assistant.history_runner.analyze_message",side_effect=score):
            history.start();finish()
        self.assertEqual(calls,["合成聊天 0","合成聊天 1"])
        self.assertEqual(history.resume_button.cget("state"),"normal")
        self.assertEqual(history.ball.score,70)
        texts=[history.chat.canvas.itemcget(i,"text") for i in history.chat.canvas.find_all() if history.chat.canvas.type(i)=="text"]
        self.assertTrue(any("已分析" in t and "A" in t for t in texts))
        self.assertTrue(any("好感度 +1" in t for t in texts))
        # Loading the view again reads saved ratings without an API request.
        history.select_profile(profile)
        self.assertEqual(sum(e.rating is not None for e in history.entries),2)
        resumed=[]
        with patch.object(self.app,"saved_settings",return_value=Settings(chat_key="synthetic")),patch("chat_assistant.history_ui.run_history",side_effect=partial(run_history,batch_size=1)),patch("chat_assistant.history_runner.analyze_message",side_effect=lambda s,t,*a,**k:resumed.append(t.messages[-1].text) or rating(t.messages[-1].speaker)):
            history.resume();finish()
        self.assertEqual(resumed,["合成聊天 2","合成聊天 3"])
        self.settle()
        ball=history.ball
        from types import SimpleNamespace
        ball.start_drag(SimpleNamespace(x_root=0,y_root=0))
        ball.drag(SimpleNamespace(x_root=-50,y_root=-40))
        self.assertTrue(ball.dragged)
        self.assertGreaterEqual(ball.winfo_x(),0)
        self.assertGreaterEqual(ball.winfo_y(),0)
        self.assertFalse(history.pause_button.winfo_ismapped())
        self.assertFalse(history.resume_button.winfo_ismapped())
        for action in [history.start_button]:
            self.assertTrue(action.winfo_ismapped())
            self.assertLessEqual(action.winfo_rooty()+action.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height())

    def test_wechat_exp_launcher_uses_bundled_tool_and_preserves_import_flow(self):
        from chat_assistant.app import RoundedButton
        from chat_assistant.qq_export import tool_root
        self.app.import_center.wechat_dialog()
        self.settle()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child;yield from descendants(child)
        launch=next(w for w in descendants(self.root) if isinstance(w,RoundedButton) and w.cget("text")=="启动导出器")
        with patch("chat_assistant.wechat_ui.subprocess.Popen") as process:
            launch.invoke()
            process.assert_called_once()
        args,kwargs=process.call_args
        self.assertEqual(Path(args[0][0]).name,"wechat_exp_2.10.20260928.exe")
        self.assertEqual(Path(kwargs["cwd"]),tool_root()/"WeChatEXP")
        imported=next(w for w in descendants(self.root) if isinstance(w,RoundedButton) and w.cget("text")=="导入导出文件")
        with patch.object(self.app.import_center,"pick_file") as pick:
            imported.invoke()
            pick.assert_called_once()


if __name__ == "__main__":
    unittest.main()
