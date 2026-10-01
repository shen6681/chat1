from __future__ import annotations

import os
import sys
import socket
import webbrowser
import threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class SPAHandler(SimpleHTTPRequestHandler):
    """Serve static assets with Single Page Application (SPA) fallback to index.html."""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            index_path = os.path.join(self.directory, "index.html")
            if os.path.exists(index_path):
                self.path = "/index.html"
        return super().do_GET()

    def end_headers(self):
        # Enable CORS and disable aggressive caching for local development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress routine request spam
        pass


def find_free_port(start_port: int = 5173) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def launch_web(dist_dir: Path | None = None, open_browser: bool = True):
    root = Path(__file__).resolve().parent.parent
    if dist_dir is None:
        dist_dir = root / "web" / "dist"

    if not dist_dir.exists() or not (dist_dir / "index.html").exists():
        # Fallback to dev mode if node is installed
        print("未检测到编译后的 web/dist，正在尝试以开发模式启动前端...")
        web_dir = root / "web"
        if (web_dir / "package.json").exists():
            os.system(f'npm --prefix "{web_dir}" run dev')
            return
        raise SystemExit(f"错误：未找到前端编译目录: {dist_dir}")

    port = find_free_port(5173)
    url = f"http://localhost:{port}/"

    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        lambda *args, **kwargs: SPAHandler(*args, directory=str(dist_dir), **kwargs)
    )

    print("=" * 60)
    print("  聊有据 · 现代化高精科学沟通与回复辅助系统 (v2.6)")
    print(f"  本地服务地址: {url}")
    print("=" * 60)
    print("  按 Ctrl + C 可停止服务\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已平稳停止。")
        server.server_close()
