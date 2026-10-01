"""Independent readers for public export formats and read-only plaintext SQLite."""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from html.parser import HTMLParser
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_FILE = 150 * 1024 * 1024
MAX_MESSAGES = 300_000
MEDIA_TYPES = {"image", "picture", "emoji", "sticker", "face", "video", "voice", "audio", "file", "图片", "表情包", "动画表情", "表情", "视频", "语音", "文件"}
MEDIA_PLACEHOLDER = re.compile(r"^(?:\[(?:图片|表情包|动画表情|表情|视频|语音|文件)\]\s*)+$")


@dataclass
class ImportedMessage:
    sender: str
    text: str
    timestamp: str = ""
    message_id: str = ""
    self_flag: bool | None = None
    display_name: str = ""


@dataclass
class Conversation:
    key: str
    name: str
    platform: str = "导入"
    messages: list[ImportedMessage] = field(default_factory=list)
    owner: str = ""
    is_group: bool = False

    def identities(self) -> list[str]:
        return list(dict.fromkeys(m.sender for m in self.messages if m.sender))

    def choose_self(self, identity: str):
        from .core import Message
        if self.is_group:
            raise ValueError("当前助手分析双方对话，请选择私聊会话。")
        if not identity or identity not in self.identities():
            raise ValueError("请先确认哪位发言人是你。")
        if "未确认" in self.identities():
            raise ValueError("部分消息缺少发言人，无法可靠映射双方。请补齐发言人字段后重新导入。")
        others = {m.sender for m in self.messages if m.sender != identity}
        if len(others) > 1:
            raise ValueError("这个会话有多位其他发言人，请导出单独的私聊再导入。")
        return [Message("我" if m.sender == identity else "对方", m.text, 1.0, m.timestamp, m.sender, m.message_id, self.platform) for m in self.messages]


@dataclass
class ImportBundle:
    conversations: list[Conversation]
    source: str
    warnings: list[str] = field(default_factory=list)


def stamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("/", "-").replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return raw


def flag(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if str(value).strip().lower() in {"1", "true", "yes", "我", "自己", "self"}:
        return True
    if str(value).strip().lower() in {"0", "false", "no", "对方", "other"}:
        return False
    return None


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str((part.get("data") or {}).get("text", part.get("text", ""))) for part in value if isinstance(part, dict) and part.get("type") == "text").strip()
    if isinstance(value, dict):
        if str(value.get("type", "")).lower() in MEDIA_TYPES:
            return ""
        value = value.get("text", value.get("content", ""))
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("消息内容是压缩或二进制数据，请使用对应工具导出文本 / JSON 后导入。") from None
    text = str(value or "").strip()
    return "" if MEDIA_PLACEHOLDER.fullmatch(text) else text


def _finish(conversations, source, warnings=None, allow_empty=False):
    result = [c for c in conversations if c.messages]
    if not result and not allow_empty:
        raise ValueError("没有找到可导入的文本消息。请选择文本聊天导出文件。")
    total = sum(len(c.messages) for c in result)
    if total > MAX_MESSAGES:
        raise ValueError("单次导入最多 30 万条文本消息，请按联系人或时间拆分。")
    for c in result:
        # Stable sorting keeps equal-time messages in their export order.
        if all(m.timestamp for m in c.messages):
            c.messages.sort(key=lambda m: m.timestamp)
        if not c.owner:
            owners = {m.sender for m in c.messages if m.self_flag is True}
            if len(owners) == 1:
                c.owner = owners.pop()
    return ImportBundle(result, source, warnings or [])


def from_json(data: Any, source: str = "JSON", *, _allow_empty: bool = False) -> ImportBundle:
    if isinstance(data, list) and any(isinstance(row, dict) and row.get("_type") == "header" for row in data):
        blocks, current = [], None
        for row in data:
            if not isinstance(row, dict):
                continue
            kind = row.get("_type")
            if kind == "header":
                current = {**row, "members": [], "messages": []}; blocks.append(current)
            elif current is not None and kind in {"member", "message"}:
                current["members" if kind == "member" else "messages"].append(row)
        bundles = [from_json(block, source, _allow_empty=True) for block in blocks]
        return _finish([c for b in bundles for c in b.conversations], source, [w for b in bundles for w in b.warnings], _allow_empty)
    if isinstance(data, list) and data and all(isinstance(x, dict) and "messages" in x for x in data):
        bundles = [from_json(x, source, _allow_empty=True) for x in data]
        return _finish([c for b in bundles for c in b.conversations], source, [w for b in bundles for w in b.warnings], _allow_empty)
    if isinstance(data, dict) and isinstance(data.get("sessions"), list):
        if any(not isinstance(x, dict) or "messages" not in x for x in data["sessions"]):
            raise ValueError("会话结构无效，每个会话需要 messages 数组；请重新导出 JSON。")
        bundles = [from_json(x, source, _allow_empty=True) for x in data["sessions"]]
        return _finish([c for b in bundles for c in b.conversations], source, [w for b in bundles for w in b.warnings], _allow_empty)
    root = data if isinstance(data, dict) else {}
    messages = root.get("messages", data if isinstance(data, list) else None)
    if not isinstance(messages, list):
        raise ValueError("JSON 中未找到 messages 数组；支持 ChatLab、WeFlow、QQChatExporter。")
    if _allow_empty and any(not isinstance(row, dict) or not any(key in row for key in
            ("content", "text", "message", "parsedContent", "type", "localType", "recalled", "system")) for row in messages):
        raise ValueError("会话中存在结构无效的消息；请重新导出，不会将其当作图片或空记录跳过。")
    meta = root.get("meta") or root.get("chatInfo") or root.get("session") or {}
    if not isinstance(meta, dict):
        meta = {"name": str(meta)}
    chatlab = "chatlab" in root
    weflow = "weflow" in root or "session" in root or "talker" in root
    qce = "chatInfo" in root
    platform = "ChatLab / " + str(meta.get("platform", "导入")) if chatlab else "微信 / WeFlow" if weflow else "QQ / QQChatExporter" if qce else "JSON"
    name = str(meta.get("displayName") or meta.get("name") or meta.get("nickname") or meta.get("username") or root.get("talker") or "导入会话")
    key = str(meta.get("username") or meta.get("platformId") or meta.get("id") or root.get("talker") or name)
    group = str(meta.get("type", "")).lower() in {"group", "groupchat", "群聊"} or key.endswith("@chatroom")
    owner = str(meta.get("ownerId") or meta.get("selfUin") or meta.get("selfUid") or "")
    names = {}
    for member in root.get("members", []):
        if isinstance(member, dict):
            names[str(member.get("platformId", ""))] = str(member.get("accountName") or member.get("groupNickname") or "")
            if chatlab and not owner and member.get("accountName") == "我":
                owner = str(member.get("platformId", ""))
    senders = root.get("senders", [])
    if isinstance(senders, list):
        for i, sender in enumerate(senders):
            if isinstance(sender, dict):
                names[str(i)] = str(sender.get("displayName") or sender.get("name") or sender.get("username") or i)
            else:
                names[str(i)] = str(sender)
    elif isinstance(senders, dict):
        names.update({str(k): str(v.get("displayName") or v.get("name") or k) if isinstance(v, dict) else str(v) for k, v in senders.items()})
    conversations = OrderedDict()
    skipped = 0
    for row in messages:
        if not isinstance(row, dict):
            continue
        if row.get("recalled") or row.get("system"):
            skipped += 1
            continue
        kind = row.get("localType", row.get("type"))
        if isinstance(kind, str) and kind.lower() in MEDIA_TYPES:
            skipped += 1
            continue
        if chatlab and kind not in (None, 0, "0", "TEXT", "text"):
            skipped += 1
            continue
        if weflow and kind not in (None, 1, "1", "text", "文本消息", 244813135921, "244813135921"):
            skipped += 1
            continue
        text = _text(row.get("content", row.get("text", row.get("message", row.get("parsedContent", "")))))
        if not text:
            skipped += 1
            continue
        self_flag = flag(row.get("isSend", row.get("isSender", row.get("is_self"))))
        sender = row.get("sender", row.get("senderUsername", row.get("senderID", row.get("sender_id", row.get("name", "")))))
        display = str(row.get("senderDisplayName") or row.get("accountName") or "")
        if isinstance(sender, dict):
            display = str(sender.get("name") or sender.get("nickname") or "")
            sender = sender.get("uin") or sender.get("uid") or display
        sender = str(sender or ("我" if self_flag is True else "对方" if self_flag is False else "未确认"))
        # WeFlow's send flag is authoritative even when sender IDs are absent.
        if weflow and self_flag is not None:
            sender = "我" if self_flag else "对方"
        display = display or names.get(sender, sender)
        row_key = str(row.get("talker") or row.get("conversation_id") or key)
        if row_key not in conversations:
            conversations[row_key] = Conversation(row_key, name if row_key == key else row_key, platform, owner=owner if not weflow else "我", is_group=group or row_key.endswith("@chatroom"))
        identifier = str(row.get("platformMessageId") or row.get("serverId") or row.get("id") or row.get("localId") or row.get("message_id") or "")
        if identifier == "0":
            identifier = ""
        conversations[row_key].messages.append(ImportedMessage(sender, text, stamp(row.get("timestamp", row.get("createTime", row.get("formattedTime", "")))), identifier, self_flag, display))
    return _finish(conversations.values(), source, [f"已跳过 {skipped} 条非文本或空消息。"] if skipped else [], _allow_empty)


def from_text(text: str, source: str = "粘贴文本") -> ImportBundle:
    pc_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(?:\[([^\]]+)\]\s*)?([^：:]+)[：:]\s*(.*)$")
    if any(pc_pattern.match(line.strip()) for line in text.splitlines()):
        messages, current, skipped = [], None, 0
        for line in text.splitlines():
            match = pc_pattern.match(line.strip())
            if match:
                timestamp, kind, sender, content = match.groups()
                if kind and kind not in {"文本", "文本消息"}:
                    skipped += 1; current = None; continue
                current = ImportedMessage(sender.strip(), _text(content), stamp(timestamp), display_name=sender.strip())
                messages.append(current)
            elif current and line.strip():
                current.text += "\n" + line.strip()
        return _finish([Conversation(Path(source).stem, Path(source).stem, "微信 / WeChat EXP", [m for m in messages if m.text], "我" if any(m.sender == "我" for m in messages) else "")], source, [f"已跳过 {skipped} 条非文本消息；推荐导出 ChatLab JSONL 保留身份和消息 ID。"])
    messages = []
    current = None
    pending_name = None
    time_re = r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?"
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        raw = raw.strip()
        if not raw:
            continue
        match = re.match(rf"^({time_re})\s+(.+?)(?:\((\d+)\))?$", raw)
        named = re.match(r"^([^：:\n]{1,100})[：:]\s*(.*)$", raw)
        timed = re.fullmatch(time_re, raw)
        # Common WeChat export: nickname, timestamp, body on separate lines.
        next_timed = i + 1 < len(lines) and re.fullmatch(time_re, lines[i + 1].strip())
        if next_timed:
            pending_name = raw
        elif timed and pending_name:
            current = ImportedMessage(pending_name, "", stamp(raw), display_name=pending_name)
            messages.append(current)
            pending_name = None
        elif match:
            sender = match.group(3) or match.group(2).strip()
            current = ImportedMessage(sender, "", stamp(match.group(1)), display_name=match.group(2).strip())
            messages.append(current)
        elif named and not timed:
            sender, content = named.groups()
            current = ImportedMessage(sender, content.strip(), display_name=sender)
            messages.append(current)
        elif current:
            current.text += ("\n" if current.text else "") + raw
    messages = [m for m in messages if _text(m.text)]
    if not messages:
        raise ValueError("无法分辨发言人。请使用“昵称：内容”、QQ 时间+昵称格式，或导出 JSON / CSV。")
    return _finish([Conversation(Path(source).stem, Path(source).stem or "粘贴会话", "TXT", messages, "我" if any(m.sender == "我" for m in messages) else "")], source, ["TXT 缺少消息 ID 时，用时间、文字和重复次数去重；导入前请检查发言人。"])


ALIASES = {
    "text": ("content", "text", "message", "strcontent", "消息内容", "内容"),
    "sender": ("senderusername", "sender_id", "sender", "nickname", "name", "发送者", "发言人", "昵称"),
    "self": ("issender", "issend", "is_self", "是否发送", "是否自己"),
    "time": ("createtime", "timestamp", "time", "datetime", "formattedtime", "时间", "发送时间"),
    "conversation": ("strtalker", "talker", "conversation_id", "chat_id", "会话", "联系人"),
    "id": ("msgsvrid", "serverid", "message_id", "id", "localid", "消息id"),
    "type": ("localtype", "type", "消息类型"),
}


def guess_columns(columns: list[str]) -> dict[str, str]:
    lower = {c.strip().lower(): c for c in columns}
    return {key: next((lower[a] for a in aliases if a in lower), "") for key, aliases in ALIASES.items()}


def from_rows(rows, mapping, source="CSV", platform="导入", text_type=""):
    conversations = OrderedDict()
    skipped = 0
    count = 0
    for row in rows:
        def get(key):
            return row.get(mapping.get(key, ""), "")
        if text_type and str(get("type")) != text_type:
            skipped += 1
            continue
        if not text_type and mapping.get("type"):
            kind = str(get("type")).strip().lower()
            if kind and kind not in {"0", "1", "text", "文本", "文本消息", "244813135921"}:
                skipped += 1
                continue
        text = _text(get("text"))
        if not text:
            skipped += 1
            continue
        self_flag = flag(get("self"))
        sender = str(get("sender") or "未确认")
        if self_flag is not None:
            sender = "我" if self_flag else "对方"
        key = str(get("conversation") or "default")
        if key not in conversations:
            conversations[key] = Conversation(key, key if key != "default" else Path(source).stem, platform, owner="我" if mapping.get("self") else "", is_group=key.endswith("@chatroom"))
        identifier = str(get("id") or "")
        conversations[key].messages.append(ImportedMessage(sender, text, stamp(get("time")), "" if identifier == "0" else identifier, self_flag, sender))
        count += 1
        if count > MAX_MESSAGES:
            raise ValueError("单次导入最多 30 万条文本消息，请按联系人拆分。")
    return _finish(conversations.values(), source, [f"已跳过 {skipped} 条非文本或空消息。"] if skipped else [])


def decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("文件编码无法识别。请重新导出为 UTF-8。")


def load_file(path: Path) -> ImportBundle:
    if path.stat().st_size > MAX_FILE:
        raise ValueError("文件超过 150 MB，请按联系人或日期拆分导出。")
    suffix = path.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("请使用导入中心的 SQLite 数据库入口选择消息表与字段。")
    raw = decode(path.read_bytes())
    if suffix in {".json", ".jsonl", ".ndjson"}:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()] if suffix != ".json" else json.loads(raw)
        return from_json(data, str(path))
    if suffix in {".html", ".htm"}:
        class TextLines(HTMLParser):
            def __init__(self):
                super().__init__(); self.depth = 0; self.parts = []; self.lines = []
            def handle_starttag(self, tag, attrs):
                if tag in {"img", "br", "hr", "input", "meta", "link", "source", "wbr"}:
                    if self.depth and tag == "br":
                        self.parts.append("\n")
                    return
                if self.depth:
                    self.depth += 1
                elif tag == "div" and "msg-line" in dict(attrs).get("class", "").split():
                    self.depth = 1; self.parts = []
            def handle_endtag(self, tag):
                if self.depth:
                    self.depth -= 1
                    if not self.depth:
                        self.lines.append("".join(self.parts))
            def handle_data(self, data):
                if self.depth:
                    self.parts.append(data)
        parser = TextLines(); parser.feed(raw)
        if not parser.lines:
            raise ValueError("只支持 WeChat EXP 的聊天 HTML；请选择该工具导出的 ChatLab JSONL / JSON / TXT。")
        return from_text("\n".join(parser.lines), str(path))
    if suffix in {".csv", ".tsv"}:
        try:
            dialect = csv.Sniffer().sniff(raw[:16000], delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel_tab if suffix == ".tsv" else csv.excel
        reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
        mapping = guess_columns(reader.fieldnames or [])
        if not mapping.get("text") or not (mapping.get("sender") or mapping.get("self")):
            raise ValueError("CSV 需要内容与发言人（或 isSend）列。可转换成 ChatLab JSON 后导入。")
        return from_rows(reader, mapping, str(path), "CSV")
    return from_text(raw, str(path))


def readonly_db(path: Path):
    with path.open("rb") as file:
        header = file.read(16)
    if header != b"SQLite format 3\x00":
        raise ValueError("这不是明文 SQLite，可能是微信 / QQ 加密数据库。微信请用微信导出入口中的 WeChat EXP 导出文字；QQ 可通过 QQ 导出中心在线读取或先准备解密副本。本程序不会解密或修改原数据库。")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sqlite_tables(path: Path) -> dict[str, list[str]]:
    connection = readonly_db(path)
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {table: [row[1] for row in connection.execute("PRAGMA table_info(" + quote(table) + ")")] for table in tables}
    finally:
        connection.close()


def load_sqlite(path: Path, table: str, mapping: dict[str, str], text_type: str = "") -> ImportBundle:
    schema = sqlite_tables(path)
    if table not in schema or any(c and c not in schema[table] for c in mapping.values()):
        raise ValueError("选定的消息表或字段不存在。")
    if not mapping.get("text") or not (mapping.get("sender") or mapping.get("self")):
        raise ValueError("请选择消息内容，以及发言人或是否自己字段。")
    connection = readonly_db(path)
    try:
        order = " ORDER BY " + quote(mapping["time"]) if mapping.get("time") else ""
        condition = " WHERE CAST(" + quote(mapping["type"]) + " AS TEXT)=?" if text_type and mapping.get("type") else ""
        rows = connection.execute("SELECT * FROM " + quote(table) + condition + order, (text_type,) if condition else ())
        return from_rows((dict(row) for row in rows), mapping, str(path), "SQLite", text_type)
    finally:
        connection.close()
