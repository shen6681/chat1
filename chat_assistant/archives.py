from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .core import Message, Transcript


def normalized(message: Message) -> tuple[str, str]:
    return message.speaker, re.sub(r"\s+", "", message.text)


def latest_window(messages: list[Message]) -> list[Message]:
    result, size = [], 0
    for message in reversed(messages[-40:]):
        if size + len(message.text) + 8 > 18000:
            break
        result.append(message)
        size += len(message.text) + 8
    if not result and messages:
        raise ValueError("单条消息超过分析长度上限，请校对或缩短后分析。")
    return list(reversed(result))


@dataclass
class Profile:
    id: str
    name: str
    platform: str
    conversation_key: str
    self_identity: str
    count: int = 0


@dataclass
class ArchiveEntry:
    id: int
    message: Message
    rating: dict | None = None
    done: bool = False
    issue: dict | None = None
    explanation: dict | None = None


class ArchiveStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "archives.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, platform TEXT NOT NULL,
                    conversation_key TEXT NOT NULL, self_identity TEXT NOT NULL,
                    live_snapshot TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS messages(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL,
                    dedupe TEXT NOT NULL, speaker TEXT NOT NULL, text TEXT NOT NULL,
                    confidence REAL NOT NULL, timestamp TEXT NOT NULL, sender_id TEXT NOT NULL,
                    message_id TEXT NOT NULL, origin TEXT NOT NULL,
                    sort_time TEXT NOT NULL DEFAULT '',
                    UNIQUE(profile_id, dedupe), FOREIGN KEY(profile_id) REFERENCES profiles(id));
                CREATE INDEX IF NOT EXISTS profile_sequence ON messages(profile_id, seq);
                CREATE TABLE IF NOT EXISTS message_ratings(
                    message_seq INTEGER PRIMARY KEY, context_hash TEXT NOT NULL,
                    signature TEXT NOT NULL, result_json TEXT NOT NULL, analyzed_at TEXT NOT NULL,
                    FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS analysis_runs(
                    id TEXT PRIMARY KEY, profile_id TEXT NOT NULL,
                    start_text TEXT NOT NULL, end_text TEXT NOT NULL,
                    state TEXT NOT NULL, signature TEXT NOT NULL, model_label TEXT NOT NULL,
                    updated_at TEXT NOT NULL, error_text TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(profile_id) REFERENCES profiles(id));
                CREATE TABLE IF NOT EXISTS analysis_targets(
                    run_id TEXT NOT NULL, message_seq INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,message_seq),
                    FOREIGN KEY(run_id) REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS analysis_leases(
                    profile_id TEXT PRIMARY KEY, owner TEXT NOT NULL, pid INTEGER NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS analysis_stages(
                    message_seq INTEGER PRIMARY KEY, signature TEXT NOT NULL,
                    context_hash TEXT NOT NULL, native_json TEXT NOT NULL,
                    FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS analysis_issues(
                    message_seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, reason TEXT NOT NULL,
                    created_at TEXT NOT NULL, signature TEXT NOT NULL,
                    FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS message_explanations(
                    message_seq INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(message_seq) REFERENCES messages(seq) ON DELETE CASCADE);
            """)
            if "sort_time" not in {r[1] for r in db.execute("PRAGMA table_info(messages)")}:
                db.execute("ALTER TABLE messages ADD COLUMN sort_time TEXT NOT NULL DEFAULT ''")
            db.execute("UPDATE messages SET sort_time=CASE WHEN timestamp<>'' THEN timestamp ELSE ? END WHERE sort_time=''", (datetime.now(timezone.utc).isoformat(),))
            if "timestamp_epoch" not in {r[1] for r in db.execute("PRAGMA table_info(messages)")}:
                db.execute("ALTER TABLE messages ADD COLUMN timestamp_epoch REAL")
                db.execute("UPDATE messages SET timestamp_epoch=(julianday(timestamp)-2440587.5)*86400 WHERE timestamp<>''")
            db.execute("CREATE INDEX IF NOT EXISTS profile_time ON messages(profile_id,timestamp_epoch,seq)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def profiles(self) -> list[Profile]:
        with self.connection() as db:
            rows = db.execute("SELECT p.id,p.name,p.platform,p.conversation_key,p.self_identity,COUNT(m.seq) AS count FROM profiles p LEFT JOIN messages m ON m.profile_id=p.id GROUP BY p.id ORDER BY p.rowid DESC")
            return [Profile(**dict(row)) for row in rows]

    def profile(self, identity: str) -> Profile:
        for profile in self.profiles():
            if profile.id == identity:
                return profile
        raise ValueError("联系人档案不存在，请重新选择。")

    def create(self, name, platform, conversation_key, self_identity) -> Profile:
        profile = Profile(uuid.uuid4().hex, name.strip() or "未命名会话", platform, conversation_key, self_identity)
        with self.connection() as db:
            db.execute("INSERT INTO profiles(id,name,platform,conversation_key,self_identity) VALUES(?,?,?,?,?)", (profile.id, profile.name, platform, conversation_key, self_identity))
        return profile

    def _insert(self, db, profile_id, dedupe, message):
        cursor = db.execute("INSERT OR IGNORE INTO messages(profile_id,dedupe,speaker,text,confidence,timestamp,sender_id,message_id,origin,sort_time,timestamp_epoch) VALUES(?,?,?,?,?,?,?,?,?,?,(julianday(?)-2440587.5)*86400)", (profile_id, dedupe, message.speaker, message.text, message.confidence, message.timestamp, message.sender_id, message.message_id, message.origin, message.timestamp or datetime.now(timezone.utc).isoformat(), message.timestamp or None))
        return cursor.rowcount

    def import_messages(self, profile_id: str, messages: list[Message]) -> int:
        self.profile(profile_id)
        occurrences = Counter()
        added = 0
        with self.connection() as db:
            for message in messages:
                # ID preferred; repeated identical text without IDs is retained by occurrence.
                identity = json.dumps([message.timestamp, message.speaker, message.text], ensure_ascii=False)
                occurrences[identity] += 1
                key = "id:" + message.message_id if message.message_id else "text:" + hashlib.sha256((identity + ":" + str(occurrences[identity])).encode()).hexdigest()
                added += self._insert(db, profile_id, key, message)
        return added

    @staticmethod
    def _message(row):
        return Message(**{key: row[key] for key in ("speaker", "text", "confidence", "timestamp", "sender_id", "message_id", "origin")})

    def messages(self, profile_id: str, limit: int | None = None) -> list[Message]:
        with self.connection() as db:
            # Preserve chronological timestamps for imported batches from overlapping ranges.
            sql = "SELECT * FROM messages WHERE profile_id=? ORDER BY sort_time DESC, seq DESC"
            rows = db.execute(sql + (" LIMIT ?" if limit else ""), (profile_id, limit) if limit else (profile_id,)).fetchall()
            return [self._message(row) for row in reversed(rows)]

    def entries(self, profile_id: str, start=None, end=None) -> list[ArchiveEntry]:
        self.profile(profile_id)
        condition, params = "m.profile_id=?", [profile_id]
        if start is not None:
            condition += " AND m.timestamp_epoch>=?"; params.append(start - .0001)
        if end is not None:
            condition += " AND m.timestamp_epoch<?"; params.append(end - .0001)
        with self.connection() as db:
            rows = db.execute("SELECT m.*,r.result_json,r.context_hash,r.signature,r.analyzed_at,i.kind AS issue_kind,i.reason AS issue_reason,i.created_at AS issue_time,e.text AS explanation,e.source AS explanation_source,e.created_at AS explanation_time FROM messages m LEFT JOIN message_ratings r ON r.message_seq=m.seq LEFT JOIN analysis_issues i ON i.message_seq=m.seq LEFT JOIN message_explanations e ON e.message_seq=m.seq WHERE " + condition + " ORDER BY m.sort_time,m.seq", params)
            entries = []
            for row in rows:
                rating = json.loads(row["result_json"]) if row["result_json"] else None
                if rating:
                    rating.update(context_hash=row["context_hash"], signature=row["signature"], analyzed_at=row["analyzed_at"])
                issue = {"kind":row["issue_kind"],"reason":row["issue_reason"],"created_at":row["issue_time"]} if row["issue_kind"] else None
                explanation={"text":row["explanation"],"source":row["explanation_source"],"created_at":row["explanation_time"]} if row["explanation"] else None
                entries.append(ArchiveEntry(row["seq"], self._message(row), rating, bool(rating or issue),issue,explanation))
            return entries

    def save_explanations(self, profile_id, results):
        with self.connection() as db:
            for row in results:
                if not db.execute("SELECT 1 FROM messages WHERE seq=? AND profile_id=?",(row["entry_id"],profile_id)).fetchone():
                    raise ValueError("解释不属于当前联系人。")
                db.execute("INSERT INTO message_explanations(message_seq,text,source,created_at) VALUES(?,?,?,?) ON CONFLICT(message_seq) DO UPDATE SET text=excluded.text,source=excluded.source,created_at=excluded.created_at",(row["entry_id"],row["text"],row["source"],datetime.now(timezone.utc).isoformat()))

    def save_rating(self, profile_id: str, entry_id: int, rating: dict, context_hash: str, signature: str, run_id=None):
        self.save_batch(profile_id,[{"entry_id":entry_id,"rating":rating}],context_hash,signature,run_id)

    def save_batch(self, profile_id, results, context_hash, signature, run_id=None):
        """One durable transaction for at most ten ratings, review notes and target checkpoints."""
        if not 1 <= len(results) <= 10 or len({r["entry_id"] for r in results}) != len(results):
            raise ValueError("每组必须包含1到10条不同的消息。")
        with self.connection() as db:
            now = datetime.now(timezone.utc).isoformat()
            for result in results:
                entry_id, rating, issue = result["entry_id"], result.get("rating"), result.get("issue")
                row = db.execute("SELECT speaker FROM messages WHERE seq=? AND profile_id=?", (entry_id,profile_id)).fetchone()
                if not row or (rating and row["speaker"]!=rating["speaker"]) or (not rating and not issue):
                    raise ValueError("评分与当前联系人或发言人不匹配，未保存。")
                if run_id and not db.execute("SELECT 1 FROM analysis_runs r JOIN analysis_targets t ON t.run_id=r.id WHERE r.id=? AND r.profile_id=? AND t.message_seq=?",(run_id,profile_id,entry_id)).fetchone():
                    raise ValueError("该条消息不属于本次分析任务，未保存。")
                if rating:
                    db.execute("INSERT INTO message_ratings(message_seq,context_hash,signature,result_json,analyzed_at) VALUES(?,?,?,?,?) ON CONFLICT(message_seq) DO UPDATE SET context_hash=excluded.context_hash,signature=excluded.signature,result_json=excluded.result_json,analyzed_at=excluded.analyzed_at",(entry_id,context_hash,signature,json.dumps(rating,ensure_ascii=False,allow_nan=False),now))
                db.execute("DELETE FROM message_explanations WHERE message_seq=?",(entry_id,))
                db.execute("DELETE FROM analysis_issues WHERE message_seq=?",(entry_id,))
                if issue:
                    db.execute("INSERT INTO analysis_issues(message_seq,kind,reason,created_at,signature) VALUES(?,?,?,?,?)",(entry_id,issue["kind"],issue["reason"][:800],now,signature))
                if run_id:
                    db.execute("UPDATE analysis_targets SET done=1 WHERE run_id=? AND message_seq=?",(run_id,entry_id))
                db.execute("DELETE FROM analysis_stages WHERE message_seq=?",(entry_id,))
            if run_id:
                db.execute("UPDATE analysis_runs SET updated_at=? WHERE id=?",(now,run_id))

    def save_stages(self, results, signature, context_hash):
        with self.connection() as db:
            db.executemany("INSERT INTO analysis_stages(message_seq,signature,context_hash,native_json) VALUES(?,?,?,?) ON CONFLICT(message_seq) DO UPDATE SET signature=excluded.signature,context_hash=excluded.context_hash,native_json=excluded.native_json",((r["entry_id"],signature,context_hash,json.dumps(r,ensure_ascii=False,allow_nan=False)) for r in results))

    def stage(self, entry_id, signature, context_hash):
        with self.connection() as db:
            row = db.execute("SELECT native_json FROM analysis_stages WHERE message_seq=? AND signature=? AND context_hash=?", (entry_id, signature, context_hash)).fetchone()
        return json.loads(row[0]) if row else None

    def save_stage(self, entry_id, signature, context_hash, native):
        with self.connection() as db:
            db.execute("INSERT INTO analysis_stages(message_seq,signature,context_hash,native_json) VALUES(?,?,?,?) ON CONFLICT(message_seq) DO UPDATE SET signature=excluded.signature,context_hash=excluded.context_hash,native_json=excluded.native_json", (entry_id, signature, context_hash, json.dumps(native, ensure_ascii=False, allow_nan=False)))

    @staticmethod
    def _process_running(pid):
        if pid == os.getpid():
            return True
        if os.name != "nt":
            try:
                os.kill(pid, 0); return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)

    def acquire_analysis(self, profile_id, owner, ttl=480):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM analysis_leases WHERE profile_id=?", (profile_id,)).fetchone()
            if row and row["owner"] != owner and row["expires"] > time.time() and self._process_running(row["pid"]):
                return False
            db.execute("INSERT INTO analysis_leases(profile_id,owner,pid,expires) VALUES(?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET owner=excluded.owner,pid=excluded.pid,expires=excluded.expires", (profile_id, owner, os.getpid(), time.time()+ttl))
        return True

    def release_analysis(self, profile_id, owner):
        with self.connection() as db:
            db.execute("DELETE FROM analysis_leases WHERE profile_id=? AND owner=?", (profile_id, owner))

    def begin_run(self, profile_id, start_text, end_text, entries, signature, model_label, force=False):
        identity = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("INSERT INTO analysis_runs(id,profile_id,start_text,end_text,state,signature,model_label,updated_at) VALUES(?,?,?,?,?,?,?,?)", (identity, profile_id, start_text, end_text, "running", signature, model_label, datetime.now(timezone.utc).isoformat()))
            db.executemany("INSERT INTO analysis_targets(run_id,message_seq,done) VALUES(?,?,?)", ((identity, e.id, int(bool(e.rating or e.issue) and not force)) for e in entries))
        return identity

    def run_info(self, identity):
        with self.connection() as db:
            row = db.execute("SELECT r.*,COUNT(t.message_seq) AS total,COALESCE(SUM(t.done),0) AS completed FROM analysis_runs r LEFT JOIN analysis_targets t ON t.run_id=r.id WHERE r.id=? GROUP BY r.id", (identity,)).fetchone()
            if not row:
                raise ValueError("分析任务不存在。")
            return dict(row)

    def last_run(self, profile_id):
        with self.connection() as db:
            row = db.execute("SELECT id FROM analysis_runs WHERE profile_id=? ORDER BY rowid DESC LIMIT 1", (profile_id,)).fetchone()
        return self.run_info(row["id"]) if row else None

    def run_entries(self, identity):
        info = self.run_info(identity)
        with self.connection() as db:
            states = {r["message_seq"]: bool(r["done"]) for r in db.execute("SELECT message_seq,done FROM analysis_targets WHERE run_id=?", (identity,))}
        entries = [e for e in self.entries(info["profile_id"]) if e.id in states]
        for entry in entries:
            entry.done = states[entry.id]
        return entries

    def finish_run(self, identity, state, error=""):
        if state not in {"running", "paused", "completed", "error"}:
            raise ValueError("任务状态无效。")
        with self.connection() as db:
            db.execute("UPDATE analysis_runs SET state=?,error_text=?,updated_at=? WHERE id=?", (state, error[:500], datetime.now(timezone.utc).isoformat(), identity))

    def append_live(self, profile_id: str, transcript: Transcript) -> int:
        if not transcript.messages or any(m.speaker not in {"我", "对方"} for m in transcript.messages):
            return 0
        snapshot = [normalized(m) for m in transcript.messages]
        encoded = json.dumps(snapshot, ensure_ascii=False)
        with self.connection() as db:
            row = db.execute("SELECT live_snapshot FROM profiles WHERE id=?", (profile_id,)).fetchone()
            if not row:
                raise ValueError("联系人档案不存在。")
            if row[0] == encoded:
                return 0
        tail = [normalized(m) for m in self.messages(profile_id, 200)]
        # Scrolling back to any already archived contiguous segment does not append.
        if any(tail[i:i + len(snapshot)] == snapshot for i in range(max(0, len(tail) - len(snapshot) + 1))):
            new_messages = []
        else:
            overlap = next((n for n in range(min(len(tail), len(snapshot)), 0, -1) if tail[-n:] == snapshot[:n]), 0)
            if not overlap:
                # A missed / changed bubble can break tail matching; don't re-save
                # the already known prefix when a later suffix appears.
                overlap = next((n for n in range(min(len(tail), len(snapshot)), 0, -1) if any(tail[i:i + n] == snapshot[:n] for i in range(len(tail) - n + 1))), 0)
            new_messages = transcript.messages[overlap:]
        added = 0
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            for message in new_messages:
                saved = Message(message.speaker, message.text, message.confidence, message.timestamp or now, message.sender_id, message.message_id, "实时 OCR")
                added += self._insert(db, profile_id, "live:" + uuid.uuid4().hex, saved)
            db.execute("UPDATE profiles SET live_snapshot=? WHERE id=?", (encoded, profile_id))
        return added

    def context(self, profile_id: str, current: Transcript) -> Transcript:
        profile = self.profile(profile_id)
        pool = self.messages(profile_id, 800)
        visible = [normalized(m) for m in current.messages]
        # Exclude the current contiguous sequence from history, including scrollback.
        at = next((i for i in range(len(pool) - len(visible), -1, -1) if [normalized(m) for m in pool[i:i + len(visible)]] == visible), len(pool)) if visible else len(pool)
        pool = pool[:at]
        recent = pool[-60:]
        keywords = set(re.findall(r"[a-zA-Z0-9]{3,}|[\u4e00-\u9fff]{2,}", current.text.lower()))
        grams = {word[i:i + 2] for word in keywords for i in range(len(word) - 1)}
        candidates = sorted(enumerate(pool[:-60]), key=lambda item: sum(g in item[1].text.lower() for g in grams), reverse=True)[:20] if grams else []
        relevant = [m for i, m in sorted(candidates) if any(g in m.text.lower() for g in grams)]
        # Budget prioritizes recent history, then relevant older excerpts.
        chosen, size = [], 0
        for message in reversed(recent):
            if size + len(message.text) + 100 <= 12000:
                chosen.insert(0, message)
                size += len(message.text) + 100
        older = []
        for message in relevant:
            if size + len(message.text) + 100 <= 12000:
                older.append(message)
                size += len(message.text) + 100
        return Transcript(current.messages, current.source, list(current.warnings), older + chosen, profile.name, profile.count)

    def transcript(self, profile_id: str) -> Transcript:
        messages = self.messages(profile_id, 840)
        current = Transcript(latest_window(messages), "导入档案")
        return self.context(profile_id, current)

    def export_chatlab(self, profile_id: str, path: Path):
        profile = self.profile(profile_id)
        data = {"chatlab": {"version": "0.0.2", "exportedAt": int(datetime.now().timestamp())}, "meta": {"name": profile.name, "platform": profile.platform, "type": "private", "ownerId": "self"}, "members": [{"platformId": "self", "accountName": "我"}, {"platformId": "other", "accountName": "对方"}], "messages": []}
        for message in self.messages(profile_id):
            item = {"sender": "self" if message.speaker == "我" else "other", "type": 0, "content": message.text}
            if message.timestamp:
                try:
                    item["timestamp"] = datetime.fromisoformat(message.timestamp).timestamp()
                except ValueError:
                    item["formattedTime"] = message.timestamp
            if message.message_id:
                item["platformMessageId"] = message.message_id
            data["messages"].append(item)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
