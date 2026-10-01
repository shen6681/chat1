"""WebView2 shell adapted from Yangfan Hu's UI f699a7c (2026-10-01).

Uses the existing authenticated LocalService rather than a second archive/RPC
implementation. Native folder pickers have no preselected application path.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

from .web_server import make_server
from .web_backend import LocalService, VERSION


def get_asset_path():
    root = Path(sys._MEIPASS) if hasattr(sys,'_MEIPASS') else Path(__file__).resolve().parent.parent
    return root/'web'/'dist'


def require_runtime():
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full') as key:
        release,_=winreg.QueryValueEx(key,'Release')
    if release<394802: raise RuntimeError('需要 Windows .NET Framework 4.6.2 或更新版本。')
    client=r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for prefix in ('SOFTWARE\\','SOFTWARE\\WOW6432Node\\'):
            try:
                with winreg.OpenKey(hive,prefix+client) as key: version,_=winreg.QueryValueEx(key,'pv')
                if int(version.split('.')[0])>=86: return
            except (OSError,ValueError): pass
    raise RuntimeError('未安装 Edge WebView2 Runtime。可使用 --browser 打开同一工作台，或安装微软 Evergreen Runtime。')


def start_desktop(directory=None,ready_file=None,on_loaded=None):
    if os.name!='nt': raise RuntimeError('原生桌面窗口需要 Windows 10/11。')
    require_runtime()
    import webview
    from .capture import enable_dpi_awareness
    enable_dpi_awareness()
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ChatReplyAssistant.Desktop')
    dist=get_asset_path()
    if not (dist/'index.html').is_file(): raise RuntimeError('缺少界面资源，请使用完整便携包。')
    service=LocalService(directory);server=make_server(dist,service);url=f'http://127.0.0.1:{server.server_port}/'
    if ready_file: Path(ready_file).write_text(json.dumps({'url':url,'version':VERSION,'pid':os.getpid(),'shell':'WebView2'}),encoding='utf-8')
    background='#09090b' if service.settings_view()['theme']=='dark' else '#f8f9fa'
    # No privileged JavaScript RPC is exposed. Only the loopback session API is used.
    window=webview.create_window('聊有据 · 科学沟通辅助系统',url=url,width=1320,height=860,
                                 min_size=(960,640),background_color=background,text_select=True)
    def folder(purpose):
        result=window.create_file_dialog(webview.FOLDER_DIALOG,allow_multiple=False)
        return result[0] if result else None
    service.wechat.choices.picker=folder
    thread=threading.Thread(target=server.serve_forever,daemon=True,name='desktop-local-api')
    window.events.closed += server.shutdown
    def secure_window():
        from System import Action
        from webview.platforms.winforms import BrowserView
        form=BrowserView.instances[window.uid]
        def attach():
            from System.Drawing import Icon
            icon=dist.parent.parent/'assets'/'icon.ico'
            if icon.is_file(): form.Icon=Icon(str(icon))
            origin=urlsplit(url)
            def guard(sender,args):
                target=urlsplit(str(args.Uri))
                if (target.scheme,target.netloc)!=(origin.scheme,origin.netloc): args.Cancel=True
            form.browser.web_view.NavigationStarting += guard
            window._desktop_navigation_guard=guard
        form.Invoke(Action(attach))
        if on_loaded: on_loaded(window,service)
    window.events.loaded += secure_window
    def monitor():
        thread.join()
        # /api/quit also closes the native window, preserving the same quit command.
        if window in webview.windows: window.destroy()
    thread.start();threading.Thread(target=monitor,daemon=True).start()
    try:
        webview.start(gui='edgechromium',debug=False,private_mode=True,
                      user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 ChatReplyAssistantDesktop/'+VERSION)
    finally:
        server.shutdown();thread.join(5);service.close();server.server_close()
    return 0
