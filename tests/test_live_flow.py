"""End-to-end live loop against synthetic chat pixels and a local mock API."""
import threading
import json
import time
import tkinter as tk
import unittest
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import ImageDraw, ImageFont, ImageTk

from chat_assistant.app import AssistantApp
from chat_assistant.capture import CaptureTarget, enable_dpi_awareness
from chat_assistant.core import Region, Message
from chat_assistant.storage import SettingsStore
from test_api import Handler
from test_ocr_integration import synthetic_chat


class LiveFlowTest(unittest.TestCase):
    def test_screen_to_ocr_to_reply_and_dedupe(self):
        enable_dpi_awareness()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        Handler.requests.clear()
        Handler.fault = None
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk()
            app = AssistantApp(root, SettingsStore(Path(directory)),show_guide=False)
            profile = app.archives.create("合成联系人", "ChatLab", "test", "self")
            app.archives.import_messages(profile.id, [Message("对方", "之前说过喜欢喜剧电影"), Message("我", "记住了")])
            app.activate_profile(profile.id)
            root.withdraw()
            window = tk.Toplevel(root)
            window.title("Synthetic chat test · not a real QQ / WeChat session")
            window.geometry("760x350+30+50")
            window.resizable(False, False)
            window.attributes("-topmost", True)
            image = synthetic_chat()
            photo = ImageTk.PhotoImage(image)
            canvas = tk.Canvas(window, width=760, height=350, highlightthickness=0)
            canvas.pack()
            item = canvas.create_image(0, 0, image=photo, anchor="nw")
            root.update()
            app.target = CaptureTarget.bind(Region(canvas.winfo_rootx(), canvas.winfo_rooty(), 760, 350))
            base = f"http://127.0.0.1:{server.server_port}"
            for name, value in (("chat_url", base), ("chat_key", "fake-live-test-key"), ("interval", "1"), ("cooldown", "3")):
                app.fields[name].set(value)
            app.float_var.set(False)
            app.save_settings()

            def until(predicate, timeout=12):
                end = time.monotonic() + timeout
                while time.monotonic() < end:
                    root.update()
                    if predicate():
                        return
                    time.sleep(.04)
                self.fail("Live loop did not reach its expected state")

            try:
                app.toggle_monitor()
                root.withdraw()
                until(lambda: app.result is not None)
                self.assertIn("电影", app.transcript.text)
                self.assertEqual(len(Handler.requests), 1)
                request_state = json.loads(Handler.requests[0][1]["messages"][1]["content"])
                self.assertEqual(request_state["archive"]["name"], "合成联系人")
                self.assertIn("之前说过喜欢喜剧电影", [m["text"] for m in request_state["history_context"]])
                self.assertGreater(app.archives.profile(profile.id).count, 2)
                end = time.monotonic() + 2.2
                while time.monotonic() < end:
                    root.update()
                    time.sleep(.04)
                self.assertEqual(len(Handler.requests), 1)
                draw = ImageDraw.Draw(image)
                draw.rectangle((42, 245, 420, 309), fill="white")
                draw.text((60, 259), "周末想看电影，什么时候？", font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 25), fill="#222222")
                photo = ImageTk.PhotoImage(image)
                canvas.itemconfigure(item, image=photo)
                until(lambda: len(Handler.requests) == 2 and app.result is not None)
                self.assertIn("周末", app.transcript.text)
                self.assertEqual(app.archives.profile(profile.id).count, 6)
                app.stop_monitor()
                self.assertFalse(app.monitoring)
            finally:
                app.close()
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
