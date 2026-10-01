"""Synthetic, offline checks for the packaged app. Never reads a chat window."""
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .capture import LocalOCR
from .storage import _crypt


def run_self_test(path: Path) -> bool:
    result = {"version": "2.7.0", "synthetic_only": True, "network_requests": 0}
    try:
        from .ui_fonts import register_bundled_fonts, FontBook
        from .onboarding import GuideState
        import tkinter as tk
        fonts=register_bundled_fonts()
        font_root=tk.Tk();font_root.withdraw()
        try:
            book=FontBook(font_root)
            result['bundled_fonts']=len(fonts)==4 and all(f['label'] in book.choices for f in fonts)
        finally:
            font_root.destroy()
        image = Image.new("RGB", (760, 240), "#eeeeee")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
        draw.rounded_rectangle((35, 25, 415, 90), radius=10, fill="white")
        draw.text((50, 42), "今天想看电影，你有推荐吗？", fill="#222222", font=font)
        draw.rounded_rectangle((385, 130, 720, 200), radius=10, fill="#95ec69")
        draw.text((400, 150), "你喜欢什么类型的电影？", fill="#222222", font=font)
        transcript = LocalOCR().recognize(image)
        result["ocr"] = "电影" in transcript.text and [m.speaker for m in transcript.messages] == ["对方", "我"]
        secret = b"synthetic-local-self-test"
        result["dpapi"] = _crypt(_crypt(secret), decrypt=True) == secret
        from .archives import ArchiveStore
        from .importers import from_json
        from .core import Message, Transcript
        bundle = from_json({"chatlab": {}, "meta": {"name": "合成会话", "type": "private", "ownerId": "self"}, "messages": [{"sender": "other", "type": 0, "content": "之前说过喜欢电影", "platformMessageId": "1"}, {"sender": "self", "type": 0, "content": "明白了", "platformMessageId": "2"}]})
        messages = bundle.conversations[0].choose_self("self")
        with tempfile.TemporaryDirectory() as folder:
            guide=GuideState(Path(folder))
            guide.finish('skipped')
            result['guide_persistence']=GuideState(Path(folder)).done and not (Path(folder)/'settings.json').exists()
            archive = ArchiveStore(Path(folder))
            profile = archive.create("合成会话", "ChatLab", "test", "self")
            imported = archive.import_messages(profile.id, messages)
            repeated = archive.import_messages(profile.id, messages)
            live = Transcript([*messages, Message("对方", "今天想看什么？")])
            appended = archive.append_live(profile.id, live)
            reopened = ArchiveStore(Path(folder))
            context = reopened.context(profile.id, Transcript([live.messages[-1]]))
            result["archive_import_live"] = imported == 2 and repeated == 0 and appended == 1 and len(context.history) == 2 and context.archive_count == 3
            from .analysis import DIMENSIONS
            from .history_analysis import parse_message_rating, progress_summary
            entries = reopened.entries(profile.id)
            identity = reopened.begin_run(profile.id,"","",entries,"self-test","synthetic")
            for entry in entries:
                rating = parse_message_rating({"score":75,"affinity_delta":1,"confidence":.9,"reason":"合成测试",
                    "boundary":0,"dimensions":{k:{"score":70,"confidence":.8,"evidence":"合成文字"} for k in DIMENSIONS}},entry.message.speaker)
                rating["source"]="合成测试"
                reopened.save_rating(profile.id,entry.id,rating,"self-test","self-test",identity)
            reopened.finish_run(identity,"paused")
            after = ArchiveStore(Path(folder))
            summary = progress_summary(after.entries(profile.id))
            result["history_checkpoint"] = after.run_info(identity)["completed"] == 3 and all(e.done for e in after.run_entries(identity)) and summary["score"] == 70
            after.import_messages(profile.id,[Message("对方",f"合成批次{i}",message_id=f"batch{i}") for i in range(7)])
            entries=after.entries(profile.id)
            identity=after.begin_run(profile.id,"","",entries,"batch-test","synthetic",force=True)
            rows=[{"entry_id":e.id,"rating":rating if e.message.speaker==rating["speaker"] else None,"issue":{"kind":"unjudgeable","reason":"合成：无法判断"}} for e in entries]
            after.save_batch(profile.id,rows,"batch-test","batch-test",identity)
            final=ArchiveStore(Path(folder))
            result["batch_checkpoint"]=final.run_info(identity)["completed"]==10 and all(e.issue and e.done for e in final.entries(profile.id))
            final.save_explanations(profile.id,[{"entry_id":entries[0].id,"text":"合成按需解释","source":"synthetic"}])
            result["explanation_persistence"]=ArchiveStore(Path(folder)).entries(profile.id)[0].explanation["text"]=="合成按需解释"
        result["ok"] = all(result[k] for k in ("bundled_fonts","guide_persistence","ocr","dpapi","archive_import_live","history_checkpoint","batch_checkpoint","explanation_persistence"))
    except Exception:
        result["ok"] = False
        result["error"] = "Bundled OCR, DPAPI or archive self-test failed."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return bool(result["ok"])
