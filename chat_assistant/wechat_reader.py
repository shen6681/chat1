"""A fresh official serve process, bound to one verified backup/account.

The upstream backup API updates DECRYPTED_DIR but leaves WXID stale. Reusing
that process for message reads could swap speakers. This private instance uses
an isolated, minimal config and never copies or edits the user's login keys.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from .wechat_client import WechatClient


def no_browser_command():
    if getattr(sys,'frozen',False):
        args=[sys.executable,'--wechat-no-browser','%s']
    else:
        pythonw=Path(sys.executable).with_name('pythonw.exe')
        args=[str(pythonw if pythonw.exists() else Path(sys.executable)),str(Path(__file__).resolve().parent.parent/'main.py'),'--wechat-no-browser','%s']
    return ' '.join('"'+a.replace('\\','/')+'"' if a!='%s' else '%s' for a in args)


class ScopedWechatReader:
    def __init__(self,directory,backup,account,identity):
        from .qq_export import tool_root
        if not re.fullmatch('[a-f0-9]{32}',identity): raise ValueError('微信任务编号无效。')
        self.backup=Path(backup).resolve();self.process=None
        if not self.backup.is_dir() or not account.get('wxid') or not account.get('db_path'):
            raise ValueError('请先完成所选账号的备份。')
        source=tool_root()/'WeChatEXP'/'wechat_exp_2.10.20260928.exe'
        if not source.is_file(): raise ValueError('缺少 WeChatEXP，请将上游 v2.10.20260928 的 EXE 放到 tools/WeChatEXP。源码安装说明见 third_party/README.md。')
        runtime=Path(directory)/'wechat-api-runtime'/'2.10.20260928';runtime.mkdir(parents=True,exist_ok=True)
        cached=runtime/source.name
        def digest(path):
            with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
        source_hash=digest(source)
        if not cached.exists() or digest(cached)!=source_hash:
            tmp=runtime/(source.name+'.tmp');shutil.copy2(source,tmp);tmp.replace(cached)
        folder=Path(directory)/'wechat-api-sessions'/identity;folder.mkdir(parents=True,exist_ok=True)
        exe=folder/source.name
        if not exe.exists():
            try:os.link(cached,exe)
            except OSError:shutil.copy2(cached,exe)
        self.config=folder/'.wechat_exp_config.json'
        raw=json.dumps({'last_backup_data_dir':str(self.backup),'last_backup_wxid':account['wxid']},ensure_ascii=False).encode('utf-8')
        self.config.write_bytes(raw);self.config_hash=hashlib.sha256(raw).hexdigest()
        self.snapshot=self._snapshot()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        self.client=WechatClient(port)
        env=dict(os.environ,BROWSER=no_browser_command())
        self.process=subprocess.Popen([str(exe),'serve','--decrypted-dir',str(self.backup),
            '--db-dir',str(account['db_path']),'--host','127.0.0.1','--port',str(port)],cwd=str(folder),env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(120):
                if self.process.poll() is not None: raise ValueError('微信读取服务未启动，请检查完整程序和目录权限。')
                if self.client.ready():return
                time.sleep(.25)
            raise ValueError('微信读取服务启动超时；备份已保存在你选的目录，可打开仪表盘查看。')
        except Exception:self.close();raise

    def _snapshot(self):
        return sorted((str(p.relative_to(self.backup)),p.stat().st_size,p.stat().st_mtime_ns)
                      for p in self.backup.rglob('*.db') if p.is_file())

    def verify(self):
        if self.process.poll() is not None or hashlib.sha256(self.config.read_bytes()).hexdigest()!=self.config_hash or self._snapshot()!=self.snapshot:
            raise ValueError('所选账号/备份在导出期间发生变化，已停止导入；请结束其他备份后重新开始。')

    def contacts(self):
        self.verify();result=self.client.contacts();self.verify();return result

    def messages(self,contact,start,end):
        self.verify()
        for rows in self.client.messages(contact,start,end):
            self.verify();yield rows
        self.verify()

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(5)
