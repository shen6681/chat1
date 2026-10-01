"""WeChatEXP v2.10.20260928 loopback API, without media fetches or redirects."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from .analysis import _NoRedirect


class WechatClient:
    def __init__(self, port=5000):
        if type(port) is not int or not 1<=port<=65535: raise ValueError('微信工具只能使用本机端口。')
        self.base = f'http://127.0.0.1:{port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())

    def request(self, path, body=None, timeout=65):
        if path.split('?',1)[0] not in {'/','/api/backup/scan','/api/backup/run','/api/contacts','/api/messages'}:
            raise ValueError('不支持的微信接口。')
        data = None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8')
        return self.opener.open(urllib.request.Request(self.base+path,data=data,
            headers={'Content-Type':'application/json','User-Agent':'ChatReplyAssistant/2.8'}),timeout=timeout)

    def ready(self):
        try:
            with self.request('/',timeout=2) as response:
                html=response.read(100000).decode('utf-8','replace').lower()
                return 'wechat exp' in html or 'wechat_exp' in html
        except (OSError,ValueError): return False

    def stream(self, path, body, progress=None):
        try:
            with self.request(path,body) as response:
                if response.headers.get_content_type()!='text/event-stream': raise ValueError('微信工具未返回预期SSE进度。')
                parts=[]; terminal=None
                for raw in response:
                    if len(raw)>200000: raise ValueError('微信工具进度内容过大。')
                    line=raw.decode('utf-8').rstrip('\r\n')
                    if line.startswith('data:'): parts.append(line[5:].lstrip())
                    if sum(map(len,parts))>1000000: raise ValueError('微信工具进度内容过大。')
                    if line or not parts: continue
                    event=json.loads('\n'.join(parts));parts=[]
                    if not isinstance(event,dict): raise ValueError('微信工具SSE数据格式无效。')
                    if progress: progress(event)
                    stage=event.get('stage')
                    if stage=='error': raise ValueError('微信工具未完成：'+str(event.get('message','请查看仪表盘。'))[:400])
                    if stage=='select': raise ValueError('微信工具需要重新确认账号，请查看仪表盘。')
                    if stage=='done': terminal=event.get('result');break
                if not isinstance(terminal,dict): raise ValueError('微信工具连接中断，未收到完成确认；请在仪表盘确认备份是否仍在运行。')
                return terminal
        except (urllib.error.URLError,TimeoutError,OSError):
            raise ValueError('微信工具连接失败；备份可能仍在工具中运行，请打开仪表盘确认，不会自动重复备份。') from None

    def json(self,path):
        try:
            with self.request(path) as response:
                raw=response.read(10_000_001)
                if len(raw)>10_000_000: raise ValueError('微信文字分页过大，请在仪表盘缩小日期范围。')
                result=json.loads(raw)
                if not isinstance(result,dict): raise ValueError('微信接口没有返回对象。')
                return result
        except (urllib.error.URLError,TimeoutError,OSError):
            raise ValueError('无法读取微信工具，请打开仪表盘检查备份和账号。') from None

    def contacts(self):
        result=self.json('/api/contacts');rows=result.get('contacts')
        if not isinstance(rows,list): raise ValueError('微信联系人格式无效。')
        return rows

    def messages(self, contact, start='',end=''):
        page=1; pages=None
        while True:
            query=urllib.parse.urlencode({'chat_id':contact,'page':page,'per_page':200,'type':'1',
                                         'start_date':start,'end_date':end})
            result=self.json('/api/messages?'+query);rows=result.get('messages');pagination=result.get('pagination',{})
            total_pages=pagination.get('total_pages')
            if not isinstance(rows,list) or type(total_pages) is not int or not 0<=total_pages<=100000:
                raise ValueError('微信消息分页格式无效。')
            if pages is None: pages=total_pages
            if pages!=total_pages: raise ValueError('微信备份在导出期间发生变化，请停止其他备份后重新导出。')
            yield rows
            if page>=pages: break
            page+=1


def ensure_wechat(client):
    if client.ready(): return
    from .qq_export import tool_root
    directory=tool_root()/'WeChatEXP';exe=directory/'wechat_exp_2.10.20260928.exe'
    if not exe.is_file(): raise ValueError('缺少 WeChatEXP，请使用完整便携文件夹。')
    subprocess.Popen([str(exe)],cwd=str(directory),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    for _ in range(60):
        if client.ready(): return
        time.sleep(.25)
    raise ValueError('微信工具暂未启动完成，请确认系统程序提示后打开仪表盘；不会打开旧聊天窗口。')


def open_dashboard():
    client=WechatClient();ensure_wechat(client);webbrowser.open(client.base+'/')
    return {'opened':True,'url':client.base+'/'}
