"""Built collaborator UI with a loopback-only, session-authenticated local API."""
from __future__ import annotations

import json
import secrets
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .web_backend import LocalService, VERSION

MAX_BODY = 202 * 1024 * 1024


class SPAHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def valid_host(self): return self.headers.get('Host','') in self.server.hosts
    def authenticated(self):
        origin = self.headers.get('Origin')
        return self.valid_host() and (not origin or origin in self.server.origins) and secrets.compare_digest(
            self.headers.get('X-Chat1-Token',''),self.server.token)
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',f"default-src 'self'; script-src 'self' 'nonce-{self.server.token}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        super().end_headers()
    def respond(self,data,code=200):
        raw = json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        route = urlsplit(self.path).path
        if route.startswith('/api/'):
            if not self.authenticated(): return self.respond({'error':'本机接口验证失败，请从程序打开页面。'},403)
            try:
                query = {k:v[-1] for k,v in parse_qs(urlsplit(self.path).query).items()}
                return self.respond(self.server.service.get(route,query))
            except Exception as error: return self.respond({'error':self.server.service.safe_error(error)},400)
        if not self.valid_host(): return self.send_error(403)
        base = Path(self.directory).resolve(); target = Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(base): return self.send_error(403)
        if route.startswith('/fonts/'):
            from .ui_fonts import font_directory
            folder = font_directory().resolve(); target = (folder/route.rsplit('/',1)[-1]).resolve()
            if not target.is_relative_to(folder) or target.suffix!='.ttf' or not target.is_file(): return self.send_error(404)
            raw = target.read_bytes(); self.send_response(200); self.send_header('Content-Type','font/ttf')
            self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if target.is_file() and target.name!='index.html': return super().do_GET()
        if Path(route).suffix and not route.endswith('index.html'): return self.send_error(404)
        index = base/'index.html'
        if not index.is_file(): return self.send_error(503)
        document = index.read_text(encoding='utf-8')
        bootstrap = f'<script nonce="{self.server.token}">window.__CHAT1_TOKEN__={json.dumps(self.server.token)};</script>'
        raw = document.replace('</head>',bootstrap+'</head>').encode('utf-8')
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        if not self.authenticated(): return self.respond({'error':'本机接口验证失败。'},403)
        try:
            size = int(self.headers.get('Content-Length','0'))
            if size<=0 or size>MAX_BODY: return self.respond({'error':'文件过大或请求内容为空。'},413)
            if self.headers.get_content_type()!='application/json': return self.respond({'error':'请求格式无效。'},415)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body,dict): raise ValueError('请求内容必须为对象。')
            if urlsplit(self.path).path=='/api/quit':
                self.respond({'stopping':True})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            return self.respond(self.server.service.post(urlsplit(self.path).path,body))
        except Exception as error: return self.respond({'error':self.server.service.safe_error(error)},400)
    def do_HEAD(self):
        if not self.valid_host(): return self.send_error(403)
        self.send_error(405)


def make_server(dist_dir,service=None,port=0):
    server = ThreadingHTTPServer(('127.0.0.1',port),partial(SPAHandler,directory=str(dist_dir)))
    server.service = service or LocalService(); server.token = secrets.token_urlsafe(32)
    server.hosts = {f'127.0.0.1:{server.server_port}',f'localhost:{server.server_port}'}
    server.origins = {'http://'+host for host in server.hosts}; server.daemon_threads = True
    return server


def launch_web(dist_dir=None,open_browser=True,ready_file=None):
    root = Path(__file__).resolve().parent.parent
    dist_dir = Path(dist_dir) if dist_dir else root/'web'/'dist'
    if not (dist_dir/'index.html').is_file(): raise SystemExit('未找到新界面资源，请使用完整便携包或先运行 npm run build。')
    server = make_server(dist_dir); url = f'http://127.0.0.1:{server.server_port}/'
    if ready_file:
        Path(ready_file).write_text(json.dumps({'url':url,'version':VERSION,'pid':__import__('os').getpid()}),encoding='utf-8')
    if sys.stdout: print('聊有据 '+VERSION+' '+url,flush=True)
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.service.close(); server.server_close()
