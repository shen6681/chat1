import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from chat_assistant.analysis import APIError, DIMENSIONS
from chat_assistant.archives import ArchiveEntry, ArchiveStore
from chat_assistant.core import Message, Settings, Transcript
from chat_assistant.history_analysis import (ProgressStats, analyze_message, context_for, parse_message_rating,
                                           progress_summary, rating_label, time_bounds)
from chat_assistant.history_runner import run_history
from chat_assistant.importers import from_json, from_rows, from_text, load_file, stamp
from tests.test_api import native_result


def rating(speaker="对方", score=80, boundary=0):
    r = parse_message_rating({"score":score,"affinity_delta":1,"confidence":.9,"reason":"接住了对方的问题。",
                              "boundary":boundary,"dimensions":{k:{"score":70,"confidence":.8,"evidence":"具体追问"} for k in DIMENSIONS}}, speaker)
    r["source"] = "本机合成测试"
    return r


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.store = ArchiveStore(self.directory)
        self.profile = self.store.create("合成小林", "微信", "lin", "self")
        self.settings = Settings(chat_key="synthetic-key")
        self.store.import_messages(self.profile.id, [Message("我" if i%2==0 else "对方", f"合成消息 {i}",
                  timestamp=f"2026-09-30T12:0{i}:00+00:00", message_id=str(i)) for i in range(5)])

    def tearDown(self):
        self.temp.cleanup()

    def test_date_and_second_boundaries_and_unknown_time(self):
        self.store.import_messages(self.profile.id, [Message("对方", "次日午夜", timestamp=stamp("2026-10-01 00:00:00")),
                                                     Message("我", "无时间")])
        entries = self.store.entries(self.profile.id, *time_bounds("2026-09-30", "2026-09-30"))
        self.assertEqual(len(entries),5)
        self.assertEqual(len(self.store.entries(self.profile.id, *time_bounds("2026-09-30 20:02:00", "2026-09-30 20:02:00"))),1)
        self.assertEqual(len(self.store.entries(self.profile.id, *time_bounds())),7)
        for start,end in [("2026-10-01","2026-09-30"),("2026-09-31",""),("2026-09-30 25:00", ""),("昨天","")]:
            with self.assertRaises(ValueError):
                time_bounds(start,end)

    def test_context_only_uses_selected_past_and_has_budget(self):
        entries=self.store.entries(self.profile.id)[1:4]
        transcript=context_for(entries,1)
        self.assertEqual([m.text for m in transcript.messages],["合成消息 1","合成消息 2"])
        self.assertEqual(transcript.history,[])
        long=[ArchiveEntry(i,Message("我","字"*4000)) for i in range(30)]
        self.assertLessEqual(len(context_for(long,29).text),10000)
        with self.assertRaises(ValueError):
            context_for([ArchiveEntry(0,Message("我","字"*10001))],0)

    def test_commit_visible_before_callback_and_resume_after_failure(self):
        calls=[]
        def score(settings, transcript, *args, **kwargs):
            calls.append(transcript.messages[-1].text)
            if len(calls)==3:
                raise APIError("模拟网络中断")
            return rating(transcript.messages[-1].speaker)
        def observe(kind, data):
            if kind=="rated":
                reopened=ArchiveStore(self.directory)
                self.assertEqual(reopened.run_info(data["run_id"])["completed"],data["completed"])
                self.assertIsNotNone(next(e for e in reopened.entries(self.profile.id) if e.id==data["entry_id"]).rating)
        with patch("chat_assistant.history_runner.analyze_message",side_effect=score):
            with self.assertRaises(APIError):
                run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id),batch_size=1,on_progress=observe)
        previous=self.store.last_run(self.profile.id)
        self.assertEqual((previous["state"],previous["completed"]),("error",2))
        self.store.import_messages(self.profile.id,[Message("对方","后来导入，不应加入旧任务",message_id="new")])
        resumed=[]
        with patch("chat_assistant.history_runner.analyze_message",side_effect=lambda s,t,*a,**k:resumed.append(t.messages[-1].text) or rating(t.messages[-1].speaker)):
            result=run_history(self.store,self.settings,self.profile.id,batch_size=1,run_id=previous["id"])
        self.assertEqual(resumed,["合成消息 2","合成消息 3","合成消息 4"])
        self.assertEqual((result["state"],result["completed"]),("completed",5))
        self.assertEqual(len(self.store.run_entries(previous["id"])),5)

    def test_default_cached_messages_make_no_requests(self):
        for entry in self.store.entries(self.profile.id):
            self.store.save_rating(self.profile.id,entry.id,rating(entry.message.speaker),"hash","signature")
        with patch("chat_assistant.history_runner.analyze_message") as call:
            result=run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id),batch_size=1)
            call.assert_not_called()
        self.assertEqual(result["completed"],5)

    def test_pause_after_inflight_result_saves_then_force_resume_skips_done(self):
        cancel=threading.Event()
        for entry in self.store.entries(self.profile.id):
            self.store.save_rating(self.profile.id,entry.id,rating(entry.message.speaker),"old","old")
        def score(settings,transcript,*args,**kwargs):
            cancel.set()
            return rating(transcript.messages[-1].speaker,score=90)
        with patch("chat_assistant.history_runner.analyze_message",side_effect=score) as call:
            result=run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id),batch_size=1,force=True,cancel=cancel)
            self.assertEqual(call.call_count,1)
        self.assertEqual((result["state"],result["completed"]),("paused",1))
        entries=self.store.run_entries(result["run_id"])
        self.assertEqual(sum(e.done for e in entries),1)
        with patch("chat_assistant.history_runner.analyze_message",side_effect=lambda s,t,*a,**k:rating(t.messages[-1].speaker)) as call:
            run_history(self.store,self.settings,self.profile.id,batch_size=1,run_id=result["run_id"])
            self.assertEqual(call.call_count,4)

    def test_concurrent_job_lease_and_cross_profile_result_rejected(self):
        self.assertTrue(self.store.acquire_analysis(self.profile.id,"other-job"))
        with patch("chat_assistant.history_runner.analyze_message") as call:
            with self.assertRaisesRegex(ValueError,"阻止重复请求"):
                run_history(self.store,self.settings,self.profile.id,self.store.entries(self.profile.id),batch_size=1)
            call.assert_not_called()
        self.store.release_analysis(self.profile.id,"other-job")
        second=self.store.create("另一个联系人","QQ","wang","self")
        entry=self.store.entries(self.profile.id)[0]
        with self.assertRaises(ValueError):
            self.store.save_rating(second.id,entry.id,rating("我"),"hash","signature")

    def test_real_process_exit_preserves_checkpoint_and_reclaims_dead_lease(self):
        code='''import os, sys
from pathlib import Path
from chat_assistant.archives import ArchiveStore
from tests.test_history import rating
s=ArchiveStore(Path(sys.argv[1])); p=sys.argv[2]; e=s.entries(p)
s.acquire_analysis(p,"crashing-worker")
r=s.begin_run(p,"","",e,"s","mock")
s.save_rating(p,e[0].id,rating(e[0].message.speaker),"h","s",r)
os._exit(23)
'''
        child=subprocess.run([sys.executable,"-c",code,str(self.directory),self.profile.id],capture_output=True,cwd=Path(__file__).parents[1],timeout=20)
        self.assertEqual(child.returncode,23,child.stderr.decode(errors="replace"))
        reopened=ArchiveStore(self.directory)
        previous=reopened.last_run(self.profile.id)
        self.assertEqual(previous["completed"],1)
        with patch("chat_assistant.history_runner.analyze_message",side_effect=lambda s,t,*a,**k:rating(t.messages[-1].speaker)) as call:
            run_history(reopened,self.settings,self.profile.id,batch_size=1,run_id=previous["id"])
        self.assertEqual(call.call_count,4)

    def test_schema_upgrade_keeps_messages(self):
        path=self.directory/"legacy"; path.mkdir()
        db=sqlite3.connect(path/"archives.sqlite3")
        db.executescript("""CREATE TABLE profiles(id TEXT PRIMARY KEY,name TEXT,platform TEXT,conversation_key TEXT,self_identity TEXT,live_snapshot TEXT DEFAULT '');
          CREATE TABLE messages(seq INTEGER PRIMARY KEY,profile_id TEXT,dedupe TEXT,speaker TEXT,text TEXT,confidence REAL,timestamp TEXT,sender_id TEXT,message_id TEXT,origin TEXT,UNIQUE(profile_id,dedupe));
          INSERT INTO profiles(id,name,platform,conversation_key,self_identity) VALUES('p','保留','微信','k','self');
          INSERT INTO messages VALUES(1,'p','d','我','已有消息',1,'2026-09-30T12:00:00+00:00','','','微信');""")
        db.commit();db.close()
        upgraded=ArchiveStore(path)
        self.assertEqual(upgraded.entries("p",*time_bounds("2026-09-30","2026-09-30"))[0].message.text,"已有消息")
        self.assertEqual(upgraded.profile("p").count,1)

    def test_ratings_labels_boundary_and_incremental_progress_match(self):
        self.assertIn("A",rating_label(rating("我",score=75)))
        self.assertEqual(rating_label(rating()),"好感度 +1")
        self.assertEqual(rating("对方",boundary=.9)["affinity_delta"],0)
        entries=self.store.entries(self.profile.id)
        stats=ProgressStats(entries)
        self.assertIsNone(stats.summary()["score"])
        for entry in entries:
            entry.rating=rating(entry.message.speaker)
            stats.update(entry)
            self.assertEqual(stats.summary(),progress_summary(entries))
        entries[-1].rating=rating("我",boundary=.9)
        stats.update(entries[-1])
        self.assertEqual(stats.summary()["score"],25)
        self.assertEqual(stats.summary(),progress_summary(entries))
        bad=rating();bad["affinity_delta"]=True
        with self.assertRaises(APIError):
            parse_message_rating(bad,"对方")


class ExportFormatTests(unittest.TestCase):
    def test_pc_wechat_exp_typed_jsonl_and_media_skipped(self):
        rows=[{"_type":"header","chatlab":{"version":"0.0.2"},"meta":{"name":"合成好友","platform":"wechat","type":"private"}},
              {"_type":"member","platformId":"self","accountName":"我"},
              {"_type":"member","platformId":"peer","accountName":"合成好友"},
              {"_type":"message","platformMessageId":"message_1.db:12","sender":"self","type":0,"content":"你好"},
              {"_type":"message","sender":"peer","type":1,"content":"private-image.jpg"},
              {"_type":"message","sender":"peer","type":5,"content":"private-sticker.gif"},
              {"_type":"message","sender":"peer","type":0,"content":"文字🙂"}]
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"history.jsonl"
            file.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows),encoding="utf-8")
            bundle=load_file(file)
        conversation=bundle.conversations[0]
        self.assertEqual(conversation.owner,"self")
        self.assertEqual([m.text for m in conversation.choose_self("self")],["你好","文字🙂"])
        self.assertEqual(conversation.messages[0].message_id,"message_1.db:12")

    def test_pc_txt_and_html_skip_nontext_multiline_and_never_open_media(self):
        raw="会话：合成好友\n[2026-09-30 20:00:00] 我: 你好\n第二行\n[2026-09-30 20:01:00] [图片]好友: [图片]\nprivate-image.jpg\n[2026-09-30 20:02:00] [表情包]好友: [表情包]\n[2026-09-30 20:03:00] 好友: 来了 & <文本>"
        self.assertEqual([m.text for m in from_text(raw).conversations[0].messages],["你好\n第二行","来了 & <文本>"])
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"history.html"
            file.write_text("<html><script>ignore</script>"+"".join('<div class="msg-line">'+escape(line)+"</div>" for line in raw.splitlines())+"</html>",encoding="utf-8")
            self.assertEqual([m.text for m in load_file(file).conversations[0].messages],["你好\n第二行","来了 & <文本>"])

    def test_csv_segment_text_and_plain_placeholders(self):
        rows=[{"sender":"我","text":"正常文字","type":"1"},{"sender":"对方","text":"img.jpg","type":"3"},
              {"sender":"对方","text":"emoji.gif","type":"sticker"}]
        bundle=from_rows(rows,{"sender":"sender","text":"text","type":"type"})
        self.assertEqual(len(bundle.conversations[0].messages),1)
        bundle=from_json([{"sender":"我","message":[{"type":"text","data":{"text":"只有文字"}},{"type":"image","data":{"file":"img.jpg"}}]},
                          {"sender":"对方","content":"[表情包]"}])
        self.assertEqual([m.text for m in bundle.conversations[0].messages],["只有文字"])


class RatingHandler(BaseHTTPRequestHandler):
    calls=[]
    fail_chat=False
    def log_message(self,*args):
        pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append((self.path,body))
        if self.path.endswith("/systemone"):
            response=native_result(body["questions"])
        elif self.fail_chat:
            self.send_response(503);self.end_headers();return
        else:
            state=json.loads(body["messages"][1]["content"])
            response={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(rating(state["messages"][-1]["speaker"]),ensure_ascii=False)}}]}
        self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers()
        self.wfile.write(json.dumps(response,ensure_ascii=False).encode())


class RatingAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),RatingHandler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        RatingHandler.calls.clear();RatingHandler.fail_chat=False
        self.settings=Settings(chat_url=self.base,jev_url=self.base,chat_key="fake",jev_key="fake",vision=True)
    def test_rating_text_only_contract_even_with_vision_enabled(self):
        result=analyze_message(self.settings,Transcript([Message("对方","合成问题")]))
        self.assertEqual(result["affinity_delta"],1)
        body=RatingHandler.calls[0][1]
        self.assertIsInstance(body["messages"][1]["content"],str)
        state=json.loads(body["messages"][1]["content"])
        self.assertEqual(state["target_index"],1)
        self.assertNotIn("image_url",json.dumps(body))
    def test_combination_checkpoint_reuses_jev_after_second_provider_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ArchiveStore(Path(folder));p=store.create("合成好友","微信","p","self")
            store.import_messages(p.id,[Message("对方","合成问题")])
            settings=replace(self.settings,mode="Jev + DeepSeek")
            RatingHandler.fail_chat=True
            with self.assertRaises(APIError):
                run_history(store,settings,p.id,store.entries(p.id),batch_size=1)
            self.assertEqual(store.last_run(p.id)["completed"],0)
            self.assertEqual([path for path,_ in RatingHandler.calls],["/v1/systemone","/chat/completions"])
            RatingHandler.fail_chat=False
            run_history(store,settings,p.id,batch_size=1,run_id=store.last_run(p.id)["id"])
            self.assertEqual([path for path,_ in RatingHandler.calls],["/v1/systemone","/chat/completions","/chat/completions"])
            self.assertEqual(store.entries(p.id)[0].rating["source"],"Jev 评分 + DeepSeek 解释")


if __name__ == "__main__":
    unittest.main()
