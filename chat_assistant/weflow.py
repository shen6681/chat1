"""Public WeFlow localhost HTTP API adapter; no copied WeFlow implementation."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .importers import from_json


class WeFlowClient:
    def __init__(self, base: str = "http://127.0.0.1:5031", token: str = ""):
        parsed = urllib.parse.urlparse(base.strip())
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("WeFlow 地址应为本机 HTTP 地址，例如 http://127.0.0.1:5031。")
        self.base = base.rstrip("/")
        self.token = token.strip()

    def get(self, route, parameters=None):
        url = self.base + route + ("?" + urllib.parse.urlencode(parameters) if parameters else "")
        request = urllib.request.Request(url, headers={"Accept": "application/json", **({"Authorization": "Bearer " + self.token} if self.token else {})})
        # Refuse redirects so a local service cannot forward chat requests off-device.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(request, timeout=30) as response:
                raw = response.read(50 * 1024 * 1024 + 1)
                if len(raw) > 50 * 1024 * 1024:
                    raise ValueError("WeFlow 返回过大，请缩小导出范围。")
                data = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise ValueError("WeFlow 访问令牌不正确，请检查其 API 设置。") from None
            raise ValueError(f"WeFlow API 返回 HTTP {error.code}。") from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError("无法连接 WeFlow。请先启动 WeFlow，并启用本地 API 服务。") from None
        if not isinstance(data, dict) or data.get("success") is False:
            raise ValueError("WeFlow 未能返回会话数据，请检查解密配置及 API 服务。")
        return data

    def sessions(self):
        data = self.get("/api/v1/sessions", {"limit": 10000})
        rows = data.get("sessions", [])
        if not isinstance(rows, list):
            raise ValueError("WeFlow 返回的会话格式不正确。")
        return [row for row in rows if isinstance(row, dict) and not str(row.get("username", "")).endswith("@chatroom")]

    def history(self, talker: str, name: str = "微信会话"):
        messages = []
        for offset in range(0, 300000, 1000):
            page = self.get("/api/v1/messages", {"talker": talker, "limit": 1000, "offset": offset})
            rows = page.get("messages", [])
            if not isinstance(rows, list):
                raise ValueError("WeFlow 消息格式不正确。")
            messages.extend(rows)
            if not rows or not page.get("hasMore", len(rows) == 1000):
                return from_json({"weflow": {}, "session": {"username": talker, "displayName": name}, "messages": messages}, "WeFlow 本地 API")
        raise ValueError("该会话超过 30 万条，请先按时间导出文件再导入。")
