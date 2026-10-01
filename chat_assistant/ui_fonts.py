"""Named Tk fonts shared by one window, with installed-family choices and live preview."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
import ctypes
import hashlib
import json
import os
import sys
from pathlib import Path

_registered = set()


def font_directory():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / 'fonts'
    return Path(__file__).resolve().parent.parent / 'assets' / 'fonts'


def bundled_fonts():
    directory = font_directory()
    manifest = directory / 'provenance.json'
    if not manifest.exists():
        return []
    entries = json.loads(manifest.read_text(encoding='utf-8'))
    for entry in entries:
        path = (directory / entry['file']).resolve()
        if not path.is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('附带字体文件校验失败。')
    return entries


def register_bundled_fonts():
    entries = bundled_fonts()
    if os.name == 'nt':
        gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        gdi.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_void_p]
        gdi.AddFontResourceExW.restype = ctypes.c_int
        for entry in entries:
            path = str((font_directory()/entry['file']).resolve())
            if path not in _registered and gdi.AddFontResourceExW(path, 0x10, None):
                _registered.add(path)  # FR_PRIVATE: this process only, no system installation.
    return entries

PREFERRED = (("微软雅黑 UI", "Microsoft YaHei UI"), ("微软雅黑", "Microsoft YaHei"), ("等线", "DengXian"),
             ("思源黑体", "Source Han Sans SC"), ("思源宋体", "Source Han Serif SC"),
             ("更纱黑体", "Sarasa UI SC"), ("楷体", "KaiTi"), ("宋体", "SimSun"), ("Segoe UI", "Segoe UI"))


class FontBook:
    def __init__(self, root, family="Microsoft YaHei UI", chat_size=11):
        self.root = root
        bundled = register_bundled_fonts()
        installed = {f.casefold():f for f in tkfont.families(root)}
        aliases = {'LXGW WenKai Lite':'霞鹜文楷 轻便版', 'ZCOOL KuaiLe':'站酷快乐体', 'ZCOOL XiaoWei':'站酷小薇体 常规', 'Ma Shan Zheng':'马善政楷书'}
        self.choices = {}
        for entry in bundled:
            actual = installed.get(entry['family'].casefold()) or installed.get(aliases.get(entry['family'],'').casefold())
            if actual:
                self.choices[entry['label']] = actual
        self.choices.update({label:installed[name.casefold()] for label,name in PREFERRED if name.casefold() in installed})
        for label, system_family in (("微软雅黑","微软雅黑"),("等线","等线"),("楷体","楷体"),("宋体","宋体")):
            if system_family.casefold() in installed:
                self.choices[label]=installed[system_family.casefold()]
        if not self.choices:
            self.choices = {"系统默认":tkfont.nametofont("TkDefaultFont", root=root).actual("family")}
        self.family = installed.get(family.casefold(), next(iter(self.choices.values())))
        self.chat_size = chat_size
        self.cache = {}
        self.revision=0
        root._chat_font_book = self
        root.bind_all("<Map>", self.on_map, add="+")

    def font(self, size=10, bold=False, role="ui"):
        key = size, bold, role
        if key not in self.cache:
            actual = self.chat_size if role=="chat" else size
            self.cache[key] = tkfont.Font(root=self.root, family=self.family, size=actual, weight="bold" if bold else "normal")
        return self.cache[key]

    def set(self, family, chat_size):
        self.revision+=1
        self.family = family if family in self.choices.values() else next(iter(self.choices.values()))
        self.chat_size = chat_size
        for (size,bold,role), font in self.cache.items():
            font.configure(family=self.family, size=chat_size if role=="chat" else size)
        self.apply(self.root)

    def translate(self, current):
        if str(current) in {str(f) for f in self.cache.values()}:
            return current
        try:
            attributes = tkfont.Font(root=self.root, font=current).actual()
            return self.font(attributes["size"], attributes["weight"]=="bold")
        except tk.TclError:
            return self.font()

    def apply(self, widget):
        self.apply_one(widget)
        for child in widget.winfo_children():
            self.apply(child)

    def apply_one(self, widget):
        try:
            if "font" in widget.keys():
                widget.configure(font=self.translate(widget.cget("font")))
            if hasattr(widget,"refresh_font"):
                widget.refresh_font()
            if isinstance(widget,tk.Canvas):
                for item in widget.find_all():
                    if widget.type(item)=="text":
                        widget.itemconfigure(item,font=self.translate(widget.itemcget(item,"font")))
            widget._font_revision=(id(self),self.revision)
        except tk.TclError:
            pass

    def on_map(self, event):
        if isinstance(event.widget,tk.Misc) and getattr(event.widget,'_font_revision',None)!=(id(self),self.revision):
            self.apply_one(event.widget)


def ui_font(widget, size=10, bold=False, role="ui"):
    owner = widget
    while owner is not None:
        book = getattr(owner,"_chat_font_book",None)
        if book:
            return book.font(size,bold,role)
        owner = getattr(owner,"master",None)
    return ("Microsoft YaHei UI",size,"bold" if bold else "normal")
