"""Read-only OneBot QQ history client and an offline QQNT_Export adapter."""
from __future__ import annotations

import html
from contextlib import closing
import json
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .importers import from_json, load_file


class QQHistoryClient:
    def __init__(self, base="http://127.0.0.1:3000", token=""):
        parsed = urllib.parse.urlparse(base.strip())
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("请填写本机 OneBot HTTP 地址，例如 http://127.0.0.1:3000；不要填 WebUI 登录地址。")
        self.base, self.token = base.strip().rstrip("/"), token.strip()

    def call(self, action, parameters=None):
        if action not in {"get_login_info", "get_friend_list", "get_friend_msg_history"}:
            raise ValueError("QQ 导出中心只允许读取记录。")
        request = urllib.request.Request(self.base + "/" + action, data=json.dumps(parameters or {}).encode(), headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + self.token} if self.token else {})})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args): return None
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(request, timeout=45) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024: raise ValueError("单次 QQ API 返回过大，请缩小读取数量。")
                data = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (401, 403): raise ValueError("OneBot HTTP 的 Token 不正确。它与 QQ WebUI 的登录密码不同。") from None
            raise ValueError(f"QQ HTTP API 返回 {error.code}；请确认启用了 OneBot HTTP 服务，而非仅打开登录页面。") from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError("没有连上 QQ 记录服务。请在 NapCat / LLOneBot 中启用 OneBot HTTP 服务（本机 3000 端口），再连接。登录 QQ 本身不会开启这个接口。") from None
        except (ValueError, UnicodeDecodeError):
            raise ValueError("该地址没有返回 OneBot JSON。请填写 HTTP API 地址，不是 WebUI 页面地址。") from None
        if not isinstance(data, dict) or data.get("status") != "ok" or data.get("retcode", 0) != 0:
            raise ValueError("QQ 记录接口未能完成读取；请确认 QQ 已登录、好友会话可见且连接器支持历史接口。")
        return data.get("data")

    def connect(self):
        account = self.call("get_login_info")
        friends = self.call("get_friend_list")
        if not isinstance(account, dict) or not account.get("user_id") or not isinstance(friends, list):
            raise ValueError("QQ 登录或好友列表的返回格式不正确。")
        return account, [f for f in friends if isinstance(f, dict) and f.get("user_id")]

    def history(self, owner, friend, name, limit=1000, progress=None, cancel=None):
        limit = int(limit)
        if not 1 <= limit <= 30000: raise ValueError("单次读取数量应在 1 到 30000 之间。")
        owner, friend = str(owner), str(friend)
        cursor="0"; anchors=set(); seen=set(); messages=[]; skipped=0; partial=False;page_failed=False
        for _ in range(400):
            if cancel and cancel.is_set(): raise ValueError("已取消读取；尚未写入档案。")
            try:
                page=self.call("get_friend_msg_history", {"user_id":friend,"message_seq":cursor,"count":min(100,limit-len(messages)+1),"reverse_order":True,"reverseOrder":True})
            except ValueError:
                if not messages:raise
                page_failed=True;break
            rows=page.get("messages") if isinstance(page,dict) else None
            if not isinstance(rows,list): raise ValueError("QQ 历史接口没有返回 messages 数组。")
            if not rows: break
            valid=[r for r in rows if isinstance(r,dict)]
            fresh=0
            for row in valid:
                identity=str(row.get("message_id", ""))
                sender=row.get("sender") or {}
                sender=str(sender.get("user_id",row.get("user_id",""))) if isinstance(sender,dict) else ""
                if not identity or identity in seen: continue
                seen.add(identity);fresh+=1
                if sender not in {owner,friend} or row.get("message_type") == "group": skipped+=1;continue
                content=row.get("message", row.get("raw_message", ""))
                if isinstance(content,list): text="".join(str((s.get("data") or {}).get("text", "")) for s in content if isinstance(s,dict) and s.get("type")=="text")
                elif isinstance(content,str): text=html.unescape(re.sub(r"\[CQ:[^\]]*\]", "",content))
                else:text=""
                if not text.strip():skipped+=1;continue
                messages.append({"sender":sender,"content":text.strip(),"timestamp":row.get("time",0),"type":0,"platformMessageId":identity})
                if len(messages)>=limit:partial=True;break
            if progress:progress(len(messages))
            if len(messages)>=limit or not fresh:break
            # NapCat's message_seq parameter resolves a OneBot message_id; do not substitute a raw QQ sequence.
            oldest=min(valid,key=lambda r:(int(r.get("time") or 0),int(r.get("message_seq") or 0))) if valid else {}
            next_cursor=str(oldest.get("message_id", ""))
            if not next_cursor or next_cursor in anchors or next_cursor==cursor:break
            anchors.add(next_cursor);cursor=next_cursor
        else:partial=True
        data={"chatlab":{"version":"0.0.2"},"meta":{"name":name,"platform":"qq","type":"private","ownerId":owner,"id":"qq:"+friend},"members":[{"platformId":owner,"accountName":"我"},{"platformId":friend,"accountName":name}],"messages":messages}
        bundle=from_json(data,"QQ 导出中心 · 本机 OneBot")
        bundle.warnings.append("读取的是当前 QQ / 连接器能够返回的历史，不保证涵盖云端或其他设备的全部记录。")
        if skipped:bundle.warnings.append(f"跳过 {skipped} 条非文本或非双方消息。")
        if page_failed:bundle.warnings.append("继续翻页时接口返回错误，保留了已读取的记录；这是部分历史，请核对后存档。")
        if partial:bundle.warnings.append(f"达到读取上限 {limit} 条；可增加数量后再导入，已有记录会去重。")
        return bundle,data


def tool_root():
    return Path(sys.executable).parent / "tools" if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[1] / "tools"


def export_plain_database(database_directory: Path, output: Path, qq_numbers=""):
    """Invoke unmodified upstream exporter with an explicit config; never open an encrypted original as SQLite."""
    database_directory=database_directory.resolve()
    message_db=database_directory / "nt_msg.db"
    if not message_db.is_file():raise ValueError("请选择包含已解密 nt_msg.db 的文件夹，不是 QQ 程序安装目录。")
    with message_db.open("rb") as file:
        if file.read(16)!=b"SQLite format 3\0":raise ValueError("nt_msg.db 仍然加密。QQNT_Export 只读取已解密数据库；请先按 QQDecrypt 官方文档准备数据库副本，或使用在线读取页。")
    uri=message_db.as_uri()+"?mode=ro"
    with closing(sqlite3.connect(uri,uri=True)) as conn:
        if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():raise ValueError("数据库没有消息表。")
    ids=[v for v in re.split(r"[\s,，]+",qq_numbers.strip()) if v]
    if any(not v.isdigit() for v in ids):raise ValueError("QQ 号筛选只接受数字，多个 QQ 号用逗号分隔。")
    exe=tool_root()/"QQNT_Export"/"QQNT_Export_3.3.0.exe"
    if not exe.is_file():raise ValueError("缺少 QQNT_Export 程序，请重新解压完整 chat1 文件夹。")
    output.mkdir(parents=True,exist_ok=True)
    config=output/"export-config.toml"
    config.write_text("\n".join(["db_path = "+json.dumps(str(database_directory)),"pic_path = \"\"","output_path = "+json.dumps(str(output)),"c2c_filters = "+json.dumps([int(v) for v in ids]),"group_filters = []","conversation_types = [\"c2c\"]","output_format = [\"chatlab_json\"]","copy_resources = false"]),encoding="utf-8")
    try:
        completed=subprocess.run([str(exe),str(config)],cwd=str(exe.parent),capture_output=True,timeout=600,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    except subprocess.TimeoutExpired:
        raise ValueError("数据库导出超过 10 分钟，已停止。可先指定单个 QQ 号缩小导出范围，再重试。尚未导入任何记录。") from None
    exports=sorted((output/"c2c").glob("*.json"))
    if completed.returncode or not exports:raise ValueError("QQNT_Export 未生成私聊 JSON。请检查数据库版本、所选目录及 QQ 号筛选。未导入任何记录。")
    # Do not rely on exit code: the upstream tool can report a per-conversation error and still exit with 0.
    for file in exports:load_file(file)
    return exports
