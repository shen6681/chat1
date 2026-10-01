import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from chat_assistant.archives import ArchiveStore
from chat_assistant.core import Message, Transcript
from chat_assistant.importers import from_json, from_text, guess_columns, load_file, load_sqlite, sqlite_tables
from chat_assistant.weflow import WeFlowClient


class ImportTests(unittest.TestCase):
    def test_chatlab_and_explicit_identity(self):
        bundle = from_json({"chatlab": {"version": "0.0.2"}, "meta": {"name": "小林", "type": "private", "ownerId": "10"}, "members": [{"platformId": "10", "accountName": "自己"}], "messages": [{"sender": "20", "timestamp": 100, "type": 0, "content": "最近怎么样", "platformMessageId": "a"}, {"sender": "10", "timestamp": 101, "type": 0, "content": "挺好的"}, {"sender": "20", "timestamp": 102, "type": 1, "content": "照片"}]})
        c = bundle.conversations[0]
        self.assertEqual(c.owner, "10")
        self.assertEqual([m.speaker for m in c.choose_self("10")], ["对方", "我"])
        self.assertEqual(len(c.messages), 2)
        with self.assertRaises(ValueError):
            c.choose_self("")

    def test_weflow_detailed_compact_and_attachment_filter(self):
        for key in ("senderUsername", "senderID"):
            c = from_json({"weflow": {}, "session": {"username": "wxid_lin", "displayName": "小林"}, "senders": [{"displayName": "小林"}], "messages": [{"localId": 1, "createTime": 100, "isSend": 0, key: 0, "localType": 1, "content": "你好"}, {"localId": 2, "createTime": 101, "isSend": 1, "localType": 1, "content": "好久不见"}, {"localId": 3, "createTime": 102, "isSend": 0, "localType": 3, "content": "[图片]"}]}).conversations[0]
            self.assertEqual([m.speaker for m in c.choose_self("我")], ["对方", "我"])
            self.assertEqual(c.key, "wxid_lin")

    def test_qq_exporter_native_clean_message(self):
        c = from_json({"metadata": {"name": "QQChatExporter"}, "chatInfo": {"name": "小林", "type": "private", "selfUin": "10"}, "messages": [{"id": "q1", "timestamp": 1700000000000, "sender": {"uin": "20", "uid": "u_20", "name": "小林"}, "content": {"text": "你来了"}}, {"id": "q2", "timestamp": 1700000001000, "sender": {"uin": "10", "name": "自己"}, "content": {"text": "是呀"}}, {"id": "q3", "recalled": True, "sender": {"uin": "20"}, "content": {"text": "撤回内容"}}]}).conversations[0]
        self.assertEqual([m.speaker for m in c.choose_self(c.owner)], ["对方", "我"])
        self.assertTrue(c.messages[0].timestamp.startswith("2023-"))
        self.assertEqual(c.messages[0].message_id, "q1")

    def test_group_and_unknown_sender_are_rejected(self):
        for c in (from_json({"chatlab": {}, "meta": {"type": "group"}, "messages": [{"sender": "a", "content": "hi", "type": 0}]}).conversations[0], from_json([{"content": "hi"}]).conversations[0], from_text("甲：a\n乙：b\n丙：c").conversations[0]):
            with self.assertRaises(ValueError):
                c.choose_self(c.identities()[0])

    def test_text_qq_and_wechat_multiline(self):
        qq = from_text("2026-09-20 12:00:00 小林(20)\n你好\n第二行\n2026-09-20 12:00:01 自己(10)\n来了").conversations[0]
        self.assertEqual(qq.messages[0].text, "你好\n第二行")
        self.assertEqual([m.speaker for m in qq.choose_self("10")], ["对方", "我"])
        wx = from_text("小林\n2026-09-20 12:00:00\n你好\n自己\n2026-09-20 12:00:01\n来了").conversations[0]
        self.assertEqual(wx.identities(), ["小林", "自己"])

    def test_csv_bom_legacy_encoding_and_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "对话.csv"
            path.write_bytes("时间,发送者,内容\n2026-09-20 12:00:00,小林,你好\n2026-09-20 12:00:01,自己,来了\n".encode("gb18030"))
            self.assertEqual(len(load_file(path).conversations[0].messages), 2)
            path = Path(directory) / "对话.txt"
            path.write_bytes("我：你好\n对方：来了".encode("utf-16"))
            self.assertEqual(len(load_file(path).conversations[0].messages), 2)
            path = Path(directory) / "对话.jsonl"
            path.write_text(json.dumps({"sender": "10", "text": "你好"}, ensure_ascii=False), encoding="utf-8-sig")
            self.assertEqual(load_file(path).conversations[0].messages[0].sender, "10")

    def test_sqlite_session_separation_readonly_and_encrypted_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MSG.db"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE MSG(StrTalker TEXT, StrContent TEXT, IsSender INTEGER, CreateTime INTEGER, Type INTEGER, MsgSvrID INTEGER)")
            db.executemany("INSERT INTO MSG VALUES(?,?,?,?,?,?)", [("wxid_a", "你好", 0, 100, 1, 11), ("wxid_a", "我来了", 1, 101, 1, 12), ("wxid_b", "别的会话", 0, 102, 1, 13), ("wxid_a", "图片", 0, 103, 3, 14)])
            db.commit()
            db.close()
            before = path.read_bytes()
            schema = sqlite_tables(path)
            bundle = load_sqlite(path, "MSG", guess_columns(schema["MSG"]), "1")
            self.assertEqual(len(bundle.conversations), 2)
            self.assertEqual(len(bundle.conversations[0].choose_self("我")), 2)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ValueError):
                load_sqlite(path, 'MSG";DROP TABLE MSG;', {}, "")
            path.write_bytes(b"synthetic-encrypted-header")
            with self.assertRaisesRegex(ValueError, "加密数据库"):
                sqlite_tables(path)

    def test_large_sqlite_attachment_history_does_not_hide_later_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MSG.db"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE MSG(StrTalker TEXT, StrContent TEXT, IsSender INTEGER, CreateTime INTEGER, Type INTEGER)")
            db.executemany("INSERT INTO MSG VALUES('lin','image',0,?,3)", ((i,) for i in range(300002)))
            db.execute("INSERT INTO MSG VALUES('lin','后面的文本',0,300003,1)")
            db.commit()
            db.close()
            schema = sqlite_tables(path)
            bundle = load_sqlite(path, "MSG", guess_columns(schema["MSG"]), "1")
            self.assertEqual([m.text for m in bundle.conversations[0].messages], ["后面的文本"])


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = ArchiveStore(Path(self.folder.name))
        self.profile = self.store.create("小林", "ChatLab", "lin", "10")

    def tearDown(self):
        self.folder.cleanup()

    def test_persistence_reimport_and_distinct_repeated_text(self):
        messages = [Message("对方", "哈哈"), Message("对方", "哈哈"), Message("我", "收到", message_id="100")]
        self.assertEqual(self.store.import_messages(self.profile.id, messages), 3)
        self.assertEqual(self.store.import_messages(self.profile.id, messages), 0)
        reopened = ArchiveStore(Path(self.folder.name))
        self.assertEqual(reopened.profile(self.profile.id).count, 3)
        self.assertEqual([m.text for m in reopened.messages(self.profile.id)], ["哈哈", "哈哈", "收到"])

    def test_live_overlap_scrollback_and_profile_isolation(self):
        self.store.import_messages(self.profile.id, [Message("对方", "A"), Message("我", "B")])
        current = Transcript([Message("对方", "A"), Message("我", "B"), Message("对方", "C")])
        self.assertEqual(self.store.append_live(self.profile.id, current), 1)
        self.assertEqual(self.store.append_live(self.profile.id, current), 0)
        self.assertEqual(self.store.append_live(self.profile.id, Transcript([Message("对方", "A")])), 0)
        other = self.store.create("小王", "ChatLab", "wang", "10")
        self.store.import_messages(other.id, [Message("对方", "另一人的隐私")])
        context = self.store.context(self.profile.id, Transcript([Message("对方", "C")]))
        self.assertEqual([m.text for m in context.history], ["A", "B"])
        self.assertNotIn("另一人的隐私", json.dumps(context.state(), ensure_ascii=False))

    def test_context_budget_current_numbering_and_export_roundtrip(self):
        self.store.import_messages(self.profile.id, [Message("我" if i % 2 else "对方", "电影" + str(i) + "长" * 300, timestamp=f"2026-09-20T12:{i // 60:02}:{i % 60:02}+00:00", message_id=str(i + 1)) for i in range(150)])
        transcript = self.store.transcript(self.profile.id)
        self.assertEqual(len(transcript.messages), 40)
        self.assertLessEqual(sum(len(m.text) + 100 for m in transcript.history), 12000)
        self.assertEqual(transcript.archive_count, 150)
        self.assertNotIn(transcript.messages[-1].text, [m.text for m in transcript.history])
        path = Path(self.folder.name) / "export.json"
        self.store.export_chatlab(self.profile.id, path)
        exported = load_file(path).conversations[0]
        self.assertEqual(len(exported.messages), 150)
        self.assertEqual(exported.choose_self("self")[-1].text, transcript.messages[-1].text)

    def test_overlapping_import_ranges_sort_chronologically(self):
        self.store.import_messages(self.profile.id, [Message("我", "later", timestamp="2026-09-22T00:00:00+00:00", message_id="2")])
        self.store.import_messages(self.profile.id, [Message("我", "earlier", timestamp="2026-09-20T00:00:00+00:00", message_id="1")])
        self.assertEqual([m.text for m in self.store.messages(self.profile.id)], ["earlier", "later"])


class WeFlowTests(unittest.TestCase):
    def test_local_api_auth_pagination_and_private_sessions(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                calls.append((self.path, self.headers.get("Authorization")))
                if self.path.startswith("/api/v1/sessions"):
                    data = {"success": True, "sessions": [{"username": "lin", "displayName": "小林"}, {"username": "test@chatroom"}]}
                else:
                    offset = parse_qs(urlparse(self.path).query)["offset"][0]
                    data = {"success": True, "hasMore": offset == "0", "messages": [{"localId": offset, "createTime": int(offset) + 100, "isSend": int(offset) > 0, "localType": 1, "content": "来了"}]}
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = WeFlowClient(f"http://127.0.0.1:{server.server_port}", "test-local-token")
            self.assertEqual(len(client.sessions()), 1)
            self.assertEqual(len(client.history("lin").conversations[0].messages), 2)
            self.assertTrue(all(auth == "Bearer test-local-token" for path, auth in calls))
            self.assertIn("offset=1000", calls[-1][0])
        finally:
            server.shutdown()
            server.server_close()
        with self.assertRaises(ValueError):
            WeFlowClient("https://remote.example")


if __name__ == "__main__":
    unittest.main()
