from __future__ import annotations

import argparse
import ctypes
import json
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from PIL import Image, ImageTk

from .analysis import Analysis, DIMENSIONS, analyze, check_connection, endpoint, grade
from .capture import CaptureTarget, CaptureUnavailable, LocalOCR, enable_dpi_awareness, grab
from .core import MODES, Region, Settings, StableGate, Transcript, parse_manual
from .storage import SettingsStore
from .archives import ArchiveStore
from .import_ui import ImportCenter
from .ui_fonts import FontBook, ui_font
from .ui_themes import ThemeBook, THEMES, SURFACE_SCHEMES, theme_color, theme_canvas
from .ui_widgets import rounded_rect, Tooltip, blend_color
from .onboarding import BeginnerGuide, GuideState
from .page_transition import PageTransition

BG = "#F4F6FB"
PANEL = "#FFFFFF"
SURFACE = "#EEF1FA"
BORDER = "#DFE5F0"
TEXT = "#24304A"
MUTED = "#586880"
TEAL = "#6658D9"
AMBER = "#A56B14"
ACCENT_LIGHT = "#EBE8FC"
FONT = "Microsoft YaHei UI"


def label(parent, text, size=10, color=TEXT, bold=False, **options):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, font=ui_font(parent,size,bold), anchor="w", justify="left", **options)


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, primary=False, **options):
        self.caption, self.command = text, command
        self.primary, self.hover, self.selected = primary, False, False
        self.selection_progress=None
        self.widget_state = options.pop("state", "normal")
        self.anchor = options.pop("anchor", "center")
        self.xpad, self.ypad = options.pop("padx", 15), options.pop("pady", 10)
        self.font = options.pop("font",ui_font(parent,10,primary))
        if not isinstance(self.font,tkfont.Font):
            self.font = tkfont.Font(root=parent,font=self.font)
        self.fill = options.pop("bg", TEAL if primary else SURFACE)
        self.foreground = options.pop("fg", "#FFFFFF" if primary else TEXT)
        super().__init__(parent, bg=parent.cget("bg"), width=self.font.measure(text)+2*self.xpad+4, height=self.font.metrics("linespace")+2*self.ypad, highlightthickness=0, bd=0, takefocus=1, cursor="hand2", **options)
        self.bind("<Configure>", lambda e:self.paint())
        self.bind("<Enter>",lambda e:self.set_hover(True));self.bind("<Leave>",lambda e:self.set_hover(False))
        self.bind("<ButtonRelease-1>",lambda e:self.invoke());self.bind("<Return>",lambda e:self.invoke());self.bind("<space>",lambda e:self.invoke())
        self.bind("<FocusIn>",lambda e:self.paint());self.bind("<FocusOut>",lambda e:self.paint())

    def set_hover(self,value):self.hover=value;self.paint()

    def refresh_font(self):
        super().configure(width=self.font.measure(self.caption)+2*self.xpad+4,height=self.font.metrics("linespace")+2*self.ypad)
        self.paint()

    def invoke(self):
        if self.widget_state != "disabled":self.command()

    def configure(self, cnf=None, **options):
        values = dict(cnf or {});values.update(options)
        if "text" in values:
            self.caption=values.pop("text")
            values["width"]=self.font.measure(self.caption)+2*self.xpad+4
        if "state" in values:self.widget_state=values.pop("state")
        if "bg" in values:self.fill=values.pop("bg")
        if "fg" in values:self.foreground=values.pop("fg")
        if values:super().configure(**values)
        self.paint()
    config=configure

    def cget(self,key):
        if key=="text":return self.caption
        if key=="state":return self.widget_state
        return super().cget(key)

    def paint(self):
        if not self.winfo_exists():return
        self.delete("all");w=self.winfo_width() if self.winfo_width()>1 else int(super().cget("width"));h=int(super().cget("height"))
        fill=("#574BC4" if self.primary else "#E4E7F3") if self.hover else self.fill
        foreground=self.foreground
        if self.widget_state=="disabled":fill="#EFF1F6";foreground="#A5AEBD"
        fill=theme_color(self,fill);foreground=theme_color(self,foreground)
        if self.selected or self.selection_progress is not None:
            progress=1 if self.selection_progress is None else self.selection_progress
            fill=blend_color(self,fill,theme_color(self,ACCENT_LIGHT),progress)
            foreground=blend_color(self,foreground,theme_color(self,TEAL),progress)
        rounded_rect(self,1,1,w-1,h-1,fill,theme_color(self,TEAL) if self.focus_get()==self else fill,6)
        self.create_text(self.xpad if self.anchor=="w" else w/2,h/2,text=self.caption,font=self.font,fill=foreground,anchor="w" if self.anchor=="w" else "center")
        theme_canvas(self)


def button(parent, text, command, primary=False, **options):
    return RoundedButton(parent,text,command,primary,**options)


def text_box(parent, height=8, readonly=False, **options):
    box = tk.Text(parent, height=height, bg=BG, fg=TEXT, insertbackground=TEAL, selectbackground="#DED9F8", relief="flat", bd=0, padx=16, pady=14, spacing1=3, spacing3=6, wrap="word", font=ui_font(parent,10), undo=not readonly, **options)
    if readonly:
        box.configure(state="disabled")
    return box


def set_text(widget, value, readonly=False):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.edit_modified(False)
    widget.configure(state="disabled" if readonly else "normal")


class ScrollPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=PANEL)
        self.canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=PANEL)
        self.item = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.item, width=event.width))
        self.canvas.bind("<MouseWheel>", self._scroll)

    def _scroll(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)

    def bind_children(self):
        def visit(widget):
            if not isinstance(widget, tk.Text):
                widget.bind("<MouseWheel>", self._scroll)
            for child in widget.winfo_children():
                visit(child)
        visit(self.inner)


class RegionSelector:
    def __init__(self, root: tk.Tk, callback):
        import mss
        self.root = root
        self.callback = callback
        self.start = None
        with mss.mss() as screen:
            self.virtual = dict(screen.monitors[0])
            primary = dict(screen.monitors[1])
        self.overlay = tk.Toplevel(root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", .42)
        self.overlay.configure(bg="black")
        self.overlay.geometry(f"{self.virtual['width']}x{self.virtual['height']}+0+0")
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        self.overlay.update_idletasks()
        # Tk negative geometry offsets mean distance from the right edge. Win32
        # positions the virtual desktop correctly even for a monitor on the left.
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        hwnd = user32.GetAncestor(self.overlay.winfo_id(), 2)
        user32.SetWindowPos(hwnd, ctypes.c_void_p(-1), self.virtual["left"], self.virtual["top"], self.virtual["width"], self.virtual["height"], 0x0040)
        self.canvas.create_text(primary["left"] - self.virtual["left"] + primary["width"] // 2, primary["top"] - self.virtual["top"] + 70, text="拖动框选消息气泡区域 · 排除联系人列表和输入框 · Esc 取消", fill="white", font=(FONT, 18, "bold"))
        self.rectangle = self.canvas.create_rectangle(0, 0, 0, 0, outline="#70FFDA", width=3)
        self.overlay.bind("<Escape>", lambda event: self.close(None))
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.overlay.focus_force()

    def press(self, event):
        self.start = (event.x_root, event.y_root)

    def drag(self, event):
        if self.start:
            x, y = self.start
            self.canvas.coords(self.rectangle, x - self.virtual["left"], y - self.virtual["top"], event.x_root - self.virtual["left"], event.y_root - self.virtual["top"])

    def release(self, event):
        if self.start:
            x, y = self.start
            left, top = min(x, event.x_root), min(y, event.y_root)
            width, height = abs(x - event.x_root), abs(y - event.y_root)
            if width < 120 or height < 80:
                self.canvas.itemconfigure(self.rectangle, outline="#FFBD7A")
                return
            self.close(Region(left, top, width, height))

    def close(self, region):
        self.overlay.destroy()
        self.root.after(250, lambda: self.callback(region))


class AssistantApp:
    def __init__(self, root: tk.Tk, store: SettingsStore | None = None, *, show_guide=True):
        self.root = root
        self.store = store or SettingsStore()
        self.archives = ArchiveStore(self.store.directory)
        self.active_profile = None
        try:
            self.settings = self.store.load()
            load_error = ""
        except Exception:
            self.settings = Settings()
            load_error = "配置未能读取，已使用默认设置，请重新填写密钥。"
        self.fonts = FontBook(root,self.settings.font_family,self.settings.chat_font_size)
        self.themes = ThemeBook(root,self.settings.theme,self.settings.surface_scheme)
        self.guide = None
        self.events = queue.Queue()
        self.ocr = LocalOCR()
        self.target = None
        self.transcript = None
        self.image = None
        self.result = None
        self.result_transcript = None
        self.gate = StableGate()
        self.generation = 0
        self.job_sequence = 0
        self.capture_job = None
        self.analysis_job = None
        self.connection_job = None
        self.cancel_analysis = None
        self.monitoring = False
        self.next_capture = 0.0
        self.closed = False
        self.floating = None
        self.preview_photo = None
        self.selector = None
        self.status = tk.StringVar(value=load_error or "就绪 · 先设置接口，再框选聊天区")
        self.mode_var = tk.StringVar(value=self.settings.mode)
        self.auto_var = tk.BooleanVar(value=self.settings.auto_analyze)
        self.right_var = tk.BooleanVar(value=self.settings.self_on_right)
        self.float_var = tk.BooleanVar(value=True)
        self.archive_var = tk.BooleanVar(value=True)
        self.archive_label_var = tk.StringVar(value="历史背景：未关联档案")
        self.root.title("聊有据 · QQ / 微信回复助手")
        self.root.configure(bg=BG)
        self.root.geometry("1360x920")
        self.root.minsize(1100, 760)
        self._theme()
        self._build()
        self.fonts.apply(root)
        self.themes.apply(root)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(120, self.poll)
        if show_guide:
            self.root.after(700,self.maybe_start_guide)

    def _theme(self):
        self.root.option_add("*Font", ui_font(self.root,10))
        self.themes.styles()

    def _build(self):
        sidebar = tk.Frame(self.root, bg=PANEL, width=208, highlightthickness=1, highlightbackground=BORDER)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        mark=tk.Canvas(sidebar,width=48,height=46,bg=PANEL,highlightthickness=0)
        mark.pack(anchor="w",padx=25,pady=(28,13))
        mark.create_oval(2,2,43,43,fill=ACCENT_LIGHT,outline="")
        mark.create_rectangle(12,12,34,29,fill=TEAL,outline="")
        mark.create_polygon(14,28,14,34,22,28,fill=TEAL,outline="")
        for x in [17,23,29]:mark.create_oval(x,19,x+2,21,fill=PANEL,outline="")
        label(sidebar, "聊有据", 25, TEXT, True).pack(anchor="w", padx=25, pady=(0, 3))
        label(sidebar, "把下一句话说清楚", 9, MUTED).pack(anchor="w", padx=25, pady=(5, 30))
        label(sidebar,"工作空间",8,MUTED).pack(anchor="w",padx=25,pady=(0,10))
        self.main_area = tk.Frame(self.root, bg=BG)
        self.main_area.pack(side="right", fill="both", expand=True)
        self.pages = {}
        self.nav_buttons={}
        for title in ("导入记录", "实时分析", "设置", "使用说明"):
            nav=button(sidebar, title, lambda key=title: self.show_page(key), anchor="w",bg=PANEL,padx=18,pady=13)
            nav.pack(fill="x", padx=15, pady=4);self.nav_buttons[title]=nav
        bottom = tk.Frame(sidebar, bg=PANEL)
        bottom.pack(side="bottom", fill="x", padx=18, pady=24)
        label(bottom, "●  本地档案 · 本地 OCR", 9, TEAL).pack(anchor="w")
        label(bottom, "分析时使用你选择的 API\n聊天档案保存在这台电脑", 8, MUTED).pack(anchor="w", pady=(9, 12))
        label(bottom,"聊有据  2.8.1",8,MUTED).pack(anchor="w")
        statusbar = tk.Frame(self.main_area, bg=PANEL,highlightthickness=1,highlightbackground=BORDER)
        statusbar.pack(side="bottom", fill="x", padx=18, pady=(0, 14))
        tk.Label(statusbar, textvariable=self.status, bg=PANEL, fg=MUTED, anchor="w", font=(FONT, 9), padx=12, pady=10, wraplength=870).pack(fill="x")
        self.page_container = tk.Frame(self.main_area, bg=BG)
        self.page_container.pack(fill="both", expand=True, padx=24, pady=(26, 16))
        self.pages["实时分析"] = self._dashboard()
        self.import_center = ImportCenter(self)
        self.pages["导入记录"] = self.import_center.page
        self.pages["设置"] = self._settings_page()
        self.pages["使用说明"] = self._help_page()
        self.page_transition=PageTransition(self.page_container,self.pages,self.nav_buttons)
        self.show_page("导入记录",animate=False)

    def show_page(self, name, animate=True):
        if name == "接口设置":
            name = "设置"
        if name == "工作台":
            name = "实时分析"
        self.current_page = name
        if name == "导入记录" and self.monitoring:
            self.stop_monitor(show_main=True)
        self.page_transition.show(name,animate=animate)

    def _dashboard(self):
        page = tk.Frame(self.page_container, bg=BG)
        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", pady=(0, 16))
        title = tk.Frame(header, bg=BG)
        title.pack(side="left")
        label(title, "实时分析", 25, TEXT, True).pack(anchor="w")
        label(title, "看清语境 · 理解逻辑 · 找到合适的回应", 10, MUTED).pack(anchor="w", pady=(5, 0))
        self.live_button = button(header, "开始实时分析", self.toggle_monitor, True)
        self.live_button.pack(side="right", padx=(8, 0))
        self.manual_button = button(header, "分析当前文字", self.analyze_manual)
        self.manual_button.pack(side="right")
        controls = tk.Frame(page, bg=PANEL, padx=12, pady=10)
        controls.pack(fill="x", pady=(0, 12))
        self._check(controls, "我在右侧", self.right_var, self.mapping_changed).pack(side="left", padx=13)
        self._check(controls, "自动分析", self.auto_var, self.auto_changed).pack(side="left")
        self._check(controls, "悬浮建议窗", self.float_var).pack(side="right")
        archive_row = tk.Frame(page, bg=PANEL, padx=12, pady=8)
        archive_row.pack(fill="x", pady=(0, 10))
        tk.Label(archive_row, textvariable=self.archive_label_var, bg=PANEL, fg=TEAL, anchor="w", font=(FONT, 9), wraplength=475).pack(side="left", fill="x", expand=True)
        self._check(archive_row, "新消息续存档案", self.archive_var).pack(side="left", padx=8)
        button(archive_row, "选择档案", lambda: self.show_page("导入记录"), padx=9, pady=4).pack(side="left")
        button(archive_row, "解除关联", lambda: self.activate_profile(None), padx=9, pady=4).pack(side="left", padx=(5, 0))
        columns = tk.PanedWindow(page, orient="horizontal", bg=BG, sashwidth=9, bd=0, sashrelief="flat")
        columns.pack(fill="both", expand=True)
        left = tk.Frame(columns, bg=PANEL, padx=14, pady=14)
        right = tk.Frame(columns, bg=PANEL)
        columns.add(left, minsize=345, width=380)
        columns.add(right, minsize=465)
        action = tk.Frame(left, bg=PANEL)
        action.pack(fill="x")
        label(action, "聊天记录", 13, TEXT, True).pack(side="left")
        button(action, "示例", self.load_demo, padx=10, pady=5).pack(side="right")
        capture_controls = tk.Frame(left, bg=PANEL)
        capture_controls.pack(fill="x", pady=(12, 8))
        button(capture_controls, "框选聊天区", self.select_region, True, padx=10, pady=7).pack(side="left")
        button(capture_controls, "读取一次", self.capture_once, padx=10, pady=7).pack(side="left", padx=(6, 0))
        button(capture_controls, "清空", self.clear, padx=10, pady=7).pack(side="right")
        self.region_label = label(left, "未选择聊天区域", 8, MUTED, wraplength=345)
        self.region_label.pack(fill="x", pady=(0, 8))
        self.preview = tk.Label(left, text="框选后在这里预览读取区域\n只选消息气泡，避开联系人和输入框", bg=BG, fg=MUTED, font=(FONT, 9), height=7)
        self.preview.pack(fill="x", pady=(0, 10))
        editor_frame = tk.Frame(left, bg=BG)
        editor_frame.pack(fill="both", expand=True)
        self.editor = text_box(editor_frame, 10)
        editor_scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview)
        self.editor.configure(yscrollcommand=editor_scroll.set)
        editor_scroll.pack(side="right", fill="y")
        self.editor.pack(side="left", fill="both", expand=True)
        self.editor.insert("1.0", "")
        self.editor.edit_modified(False)
        self.editor.bind("<<Modified>>", self.editor_modified)
        label(left, "可按“我：/对方：”粘贴或校对；实时读取时请先暂停。", 8, MUTED, wraplength=340).pack(fill="x", pady=(8, 0))
        self.ocr_note = label(left, "OCR 只识别当前可见文字；分析会发送至所选 API。", 8, MUTED, wraplength=340)
        self.ocr_note.pack(fill="x", pady=(5, 0))
        result_header = tk.Frame(right, bg=PANEL, padx=16, pady=14)
        result_header.pack(fill="x")
        label(result_header, "对话洞察", 13, TEXT, True).pack(side="left")
        button(result_header, "导出报告", self.export_report, padx=10, pady=5).pack(side="right")
        self.result_source = label(right, "等待分析 · 每条建议都可编辑后复制", 8, MUTED, wraplength=480)
        self.result_source.pack(fill="x", padx=16, pady=(0, 9))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        self.reply_panel = ScrollPanel(notebook)
        self.logic_panel = ScrollPanel(notebook)
        self.sentence_panel = ScrollPanel(notebook)
        for panel, name in ((self.reply_panel, "下一句回复"), (self.logic_panel, "逻辑与指标"), (self.sentence_panel, "逐句分析")):
            notebook.add(panel, text=name)
        self.render_empty()
        return page

    def _check(self, parent, text, variable, command=None):
        return tk.Checkbutton(parent, text=text, variable=variable, command=command, bg=parent.cget("bg"), fg=MUTED, selectcolor=BG, activebackground=parent.cget("bg"), activeforeground=TEXT, bd=0, highlightthickness=0, font=(FONT, 9), cursor="hand2")

    def _settings_page(self):
        page = tk.Frame(self.page_container, bg=BG)
        label(page, "设置", 25, TEXT, True).pack(anchor="w")
        label(page, "模型、字体与使用偏好统一管理，修改后点击保存。", 10, MUTED).pack(anchor="w", pady=(6, 14))
        panel = ScrollPanel(page)
        self.settings_panel = panel
        panel.pack(fill="both", expand=True)
        body = panel.inner
        self.fields = {}
        appearance = tk.Frame(body,bg=PANEL,padx=18,pady=12,highlightthickness=1,highlightbackground=BORDER)
        appearance.pack(fill="x",padx=2,pady=6)
        label(appearance,"模型 · 字体显示 · 读取与表达偏好",12,TEAL,True).pack(anchor="w",pady=(0,9))
        row = tk.Frame(appearance,bg=PANEL);row.pack(fill="x",pady=(0,10))
        label(row,"分析模型",9,MUTED,width=10).pack(side="left")
        self.mode_combo = ttk.Combobox(row,textvariable=self.mode_var,values=MODES,state="readonly",width=20)
        self.mode_combo.pack(side="left")
        label(appearance,"Jev / 组合模式：Jev 批量评分，DeepSeek 仅按需解释消息或生成回复。",9,MUTED).pack(anchor="w",pady=(0,10))
        row = tk.Frame(appearance,bg=PANEL);row.pack(fill="x")
        label(row,"界面字体",9,MUTED,width=10).pack(side="left")
        selected = next((k for k,v in self.fonts.choices.items() if v==self.fonts.family),next(iter(self.fonts.choices)))
        self.font_var = tk.StringVar(value=selected)
        self.font_combo = ttk.Combobox(row,textvariable=self.font_var,values=list(self.fonts.choices),state="readonly",width=18)
        self.font_combo.pack(side="left")
        label(row,"聊天字号",9,MUTED).pack(side="left",padx=(22,8))
        self.chat_size_var = tk.IntVar(value=self.settings.chat_font_size)
        sizes = ttk.Combobox(row,textvariable=self.chat_size_var,values=list(range(10,17)),state="readonly",width=5)
        sizes.pack(side="left")
        self.font_combo.bind("<<ComboboxSelected>>",lambda e:self.preview_font())
        sizes.bind("<<ComboboxSelected>>",lambda e:self.preview_font())
        label(appearance,"预览：每次十条，读清对话，保存进度。Aa 123",11,TEXT).pack(anchor="w",pady=(10,3))
        label(appearance,"内置四款手写 / 圆润 / 书卷字体；选择即预览，点击保存后重启保留。",8,MUTED).pack(anchor="w")
        row=tk.Frame(appearance,bg=PANEL);row.pack(fill="x",pady=(12,0))
        label(row,"主色",9,MUTED,width=10).pack(side="left")
        self.theme_var=tk.StringVar(value=next(k for k,v in THEMES.items() if v==self.settings.theme))
        self.theme_combo=ttk.Combobox(row,textvariable=self.theme_var,values=list(THEMES),state="readonly",width=18)
        self.theme_combo.pack(side="left")
        self.theme_combo.bind("<<ComboboxSelected>>",lambda e:self.preview_theme())
        label(row,"区块背景",9,MUTED).pack(side="left",padx=(20,8))
        self.surface_var=tk.StringVar(value=next(k for k,v in SURFACE_SCHEMES.items() if v==self.settings.surface_scheme))
        self.surface_combo=ttk.Combobox(row,textvariable=self.surface_var,values=list(SURFACE_SCHEMES),state="readonly",width=12)
        self.surface_combo.pack(side="left")
        self.surface_combo.bind("<<ComboboxSelected>>",lambda e:self.preview_theme())
        Tooltip(self.theme_combo,"主色改变按钮、选中状态和进度球。选择后即时预览，点击保存设置后重启保留。")
        Tooltip(self.surface_combo,"区块背景控制卡片之间的分隔区、消息预览和人物区域。可以单独选择，也可跟随主色主题。")
        options = tk.Frame(appearance, bg=PANEL)
        options.pack(fill="x", pady=(12,0))
        numeric = tk.Frame(options,bg=PANEL);numeric.pack(fill="x",pady=5)
        for name, caption in (("interval","读取间隔 / 秒"),("cooldown","请求间隔 / 秒"),("timeout","超时 / 秒")):
            label(numeric,caption,9,MUTED).pack(side="left",padx=(0,6))
            self.fields[name]=tk.StringVar(value=str(getattr(self.settings,name)))
            tk.Entry(numeric,textvariable=self.fields[name],bg=BG,fg=TEXT,relief="flat",width=6).pack(side="left",ipady=6,padx=(0,16))
        for name, caption in (("style","回复风格"),("goal","沟通目标")):
            row=tk.Frame(options,bg=PANEL);row.pack(fill="x",pady=5)
            label(row,caption,9,MUTED,width=10).pack(side="left")
            self.fields[name]=tk.StringVar(value=str(getattr(self.settings,name)))
            tk.Entry(row,textvariable=self.fields[name],bg=BG,fg=TEXT,insertbackground=TEAL,relief="flat").pack(side="left",fill="x",expand=True,ipady=7)
        self.vision_var = tk.BooleanVar(value=self.settings.vision)
        self.json_var = tk.BooleanVar(value=self.settings.json_mode)
        self.remember_var = tk.BooleanVar(value=self.settings.remember_keys)
        self._check(options,"实时图片辅助（档案评分与消息解释始终只发送文字）",self.vision_var).pack(anchor="w",pady=(8,3))
        self._check(options,"文字模型使用 JSON 模式",self.json_var).pack(anchor="w",pady=3)
        api_area=tk.Frame(body,bg=PANEL,padx=18,pady=12,highlightthickness=1,highlightbackground=BORDER)
        api_area.pack(fill="x",padx=2,pady=8)
        label(api_area,"接口设置",12,TEAL,True).pack(anchor="w",pady=(0,8))
        api_tabs=ttk.Notebook(api_area);api_tabs.pack(fill="x")
        self.api_tabs=api_tabs
        for title, names in (("TypeSafe Jev", (("jev_url", "接口地址"), ("jev_model", "模型名称"), ("jev_key", "API Key"))), ("DeepSeek / 兼容接口", (("chat_url", "接口地址"), ("chat_model", "模型名称"), ("chat_key", "API Key")))):
            card = tk.Frame(api_tabs, bg=PANEL, padx=12, pady=10)
            api_tabs.add(card,text=title)
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x", pady=(0, 9))
            label(row, title, 12, TEAL, True).pack(side="left")
            provider = "jev" if names[0][0] == "jev_url" else "chat"
            button(row, "测试连接", lambda p=provider: self.test_connection(p), padx=10, pady=6).pack(side="right")
            for name, caption in names:
                row = tk.Frame(card, bg=PANEL)
                row.pack(fill="x", pady=5)
                label(row, caption, 9, MUTED, width=10).pack(side="left")
                variable = tk.StringVar(value=str(getattr(self.settings, name)))
                self.fields[name] = variable
                entry = tk.Entry(row, textvariable=variable, bg=BG, fg=TEXT, insertbackground=TEAL, relief="flat", font=(FONT, 10), show="●" if name.endswith("key") else "")
                entry.pack(side="left", fill="x", expand=True, ipady=7)
            if provider == "jev":
                label(card, "Jev 不生成新句子。单独使用时按判断方向提供预设表达。", 8, MUTED).pack(anchor="w", pady=(8, 0))
        self._check(api_area,"记住 API Key（Windows 当前用户 DPAPI 加密）",self.remember_var).pack(anchor="w",pady=6)
        api_tabs.select(1 if self.settings.mode=='DeepSeek' else 0)
        label(api_area,"测试连接使用当前草稿；日常分析使用已保存设置。",9,MUTED).pack(anchor="w")
        footer=tk.Frame(page,bg=BG);footer.pack(fill="x",pady=(12,0))
        self.settings_note=tk.StringVar(value="设置已保存")
        tk.Label(footer,textvariable=self.settings_note,bg=BG,fg=MUTED,font=ui_font(footer,9)).pack(side="left")
        self.save_button=button(footer,"保存设置",self.save_settings,True)
        self.save_button.pack(side="right")
        for variable in [self.mode_var,self.font_var,self.chat_size_var,self.theme_var,self.surface_var,self.vision_var,self.json_var,self.remember_var,*self.fields.values()]:
            variable.trace_add("write",lambda *_:self.settings_note.set("有未保存的更改 · 点击保存后用于后续分析"))
        panel.bind_children()
        return page

    def _help_page(self):
        page = tk.Frame(self.page_container, bg=BG)
        header=tk.Frame(page,bg=BG);header.pack(fill="x",pady=(0,18))
        label(header, "三步开始", 21, TEXT, True).pack(side="left")
        button(header,"重新查看新手引导",self.start_guide,True).pack(side="right")
        content = """1  在“设置”选择模型、字体与读取表达偏好，接口子区域填写API Key，保存设置。
    DeepSeek 默认地址 https://api.deepseek.com，模型 deepseek-flash。
    TypeSafe 默认地址 https://api.typesafe.ai，模型 jev-latest。
    Jev 使用原生 /v1/systemone；不会将其当成聊天生成接口。

2  打开电脑版 QQ / 微信的一对一聊天，点击“框选聊天区”。
    只框消息气泡，包含左右两侧；避开联系人列表、标题栏和输入框。
    检查预览与“我在右侧”开关，校对 OCR 说话人和文字。
    可粘贴“我：内容 / 对方：内容”，也可先点“示例”了解界面。

3  点击“开始实时分析”，将聊天窗口保持可见。
    稳定读取两次后才分析，默认每 2 秒读取，API 请求至少间隔 8 秒。
    聊天未变化不会重复请求；失败会暂停自动分析，修正后重新开启。
    悬浮窗显示回复建议；复制后由你粘贴、修改并发送。

窗口移动时选区会跟随；窗口大小改变时需要重新框选。
遮挡或最小化时暂缓读取。遮挡检测抽查选区中的 9 个点，不能保证
检测所有小面积覆盖。切换聊天对象时请停止、清空，再重新框选。
分析最新最多 40 条记录；关联档案后同时发送有限历史摘录，最多约 12000 字。
“导入记录”支持第三方导出文件、已解密 SQLite，微信默认改用 WeChat EXP。
先确认会话与“哪位是我”再保存。点击开始/结束日期打开日历，可选今日、近7天、全部时间。
选日期后点击筛选；重置恢复全部时间。日历中可以勾选精确到时间，结束日期包括当天。
范围分析仅发送所选范围内本条及此前有限文字，不读取图片和表情包。
每10条一组请求并保存，末组不足10条也保存；显示各条评级。
无法判断自动记录并继续，聊天页只提示所在页码；点击提醒可跳转。
Jev / 组合模式的档案评分只调用Jev，不自动向DeepSeek请求解释。
右键单条消息或点击气泡多选，再请求DeepSeek解释，解释保存且不覆盖评分。
人物卡旁的可拖动“攻略进度”来自六维文字互动信号，点击人物卡查看指标。
未分析完可暂停、退出，重新选择联系人点击“继续上次任务”。默认跳过已完成和已标记无法判断的条目。
仅勾选“重新评分已完成记录”才重新请求这些记录；新导入内容另建任务。
“档案分析与回复”页可生成所选范围的回复，也可带档案进入实时分析。
QQ 导出中心支持从本机 OneBot HTTP 接口读取好友历史，直接导出 JSON 或导入档案。
启用 NapCat / LLOneBot 的 HTTP 服务后连接；QQ WebUI 登录地址不是记录 API 地址。
也可用随包的 QQNT_Export 从已解密的数据库副本导出私聊 JSON。
加密数据库必须先由对应工具解密或导出；本程序不直接解密原数据库。
切换联系人前先暂停，更换档案并重新框选。开启“新消息续存档案”时，
稳定 OCR 记录按连续重叠去重后存入所选档案；OCR 无时间 / ID，去重可能有误。

“互动积极度”参照六项文字线索，证据不足不计分；不是喜欢你的概率。
Jev 显示原生判断概率；DeepSeek 的概率为模型自评。OCR、语境缺失和
模型判断都可能造成误差，先检查原文和逻辑解释再使用建议。
开启图片辅助后，仅所选区域截图会发送给文字模型，Jev 仅收到文字。
停止后不再发起新请求；已发出的请求可能仍由服务端完成。

配置位于 %LOCALAPPDATA%\\ChatReplyAssistant\\settings.json。
档案保存在同目录 archives.sqlite3（明文，仅本机），重启后仍可继续。
截图保留在内存；未关联档案的临时文字退出后清除。清空不会删除联系人档案。
导入只在本机解析；点击分析时会发送最新消息与选定档案的历史摘录。
密钥属于各服务商账号，订阅聊天会员通常不等于拥有 API 额度。

功能参考 FerryCorleone/crush-monitor，参考链接和接口文档见 README。
此程序为独立实现，适合本人参与的两人聊天。版本 2.3.0。
"""
        box = text_box(page, readonly=True)
        box.pack(fill="both", expand=True)
        set_text(box, content, True)
        return page

    def render_empty(self):
        if hasattr(self, "import_center"):
            self.import_center.analyzed_profile = None
            self.import_center.copy_button.pack_forget()
            set_text(self.import_center.result, "请分析当前档案，以获取对应最新消息的回复。", True)
        for panel in (self.reply_panel, self.logic_panel, self.sentence_panel):
            panel.clear()
            card = tk.Frame(panel.inner, bg=PANEL, padx=22, pady=28)
            card.pack(fill="x")
            label(card, "从一句话开始", 16, TEAL, True).pack(anchor="w")
            label(card, "读取或粘贴记录后，查看对话逻辑、\n互动线索和三种可编辑的回复。\n\n也可以点击左侧“示例”，预览完整效果。", 10, MUTED, wraplength=410).pack(anchor="w", pady=(14, 0))

    def set_status(self, text, warning=False):
        self.status.set(text)
        if self.floating and self.floating.winfo_exists():
            self.float_status.configure(text=text, fg=AMBER if warning else MUTED)

    def activate_profile(self, profile_id):
        self.stop_monitor(show_main=True)
        self.target = None
        self.clear_records()
        self.active_profile = profile_id
        self.region_label.configure(text="未选择聊天区域 · 请框选当前档案对应的联系人")
        self.update_archive_label()

    def update_archive_label(self):
        if self.active_profile:
            profile = self.archives.profile(self.active_profile)
            self.archive_label_var.set(f"历史背景：{profile.name} · {profile.count} 条 · 请确认屏幕为同一联系人")
        else:
            self.archive_label_var.set("历史背景：未关联档案 · 可从导入记录页选择")

    def editor_modified(self, event=None):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        if self.monitoring:
            return
        if self.analysis_job:
            self.generation += 1
            if self.cancel_analysis:
                self.cancel_analysis.set()
        if self.result and self.editor.get("1.0", "end-1c").strip() != self.result_transcript.text:
            self.result = None
            self.result_transcript = None
            self.render_empty()
            self.result_source.configure(text="文字已修改，请重新分析。")
            self.render_floating()

    def _read_settings(self):
        result = replace(self.settings, mode=self.mode_var.get(), auto_analyze=self.auto_var.get(), self_on_right=self.right_var.get(), vision=self.vision_var.get(), json_mode=self.json_var.get(), remember_keys=self.remember_var.get(),font_family=self.fonts.choices[self.font_var.get()],chat_font_size=self.chat_size_var.get(),theme=THEMES[self.theme_var.get()],surface_scheme=SURFACE_SCHEMES[self.surface_var.get()])
        for name, variable in self.fields.items():
            value = variable.get().strip()
            if name in ("interval", "cooldown"):
                try:
                    value = float(value)
                except ValueError:
                    raise ValueError("读取和请求间隔应填写数字。") from None
            elif name == "timeout":
                try:
                    value = int(value)
                except ValueError:
                    raise ValueError("请求超时应填写整数秒。") from None
            setattr(result, name, value)
        result.validate(require_keys=False)
        endpoint(result.chat_url, "/chat/completions")
        endpoint(result.jev_url, "/v1/systemone")
        return result

    def preview_font(self):
        self.page_transition.finish()
        self.fonts.set(self.fonts.choices[self.font_var.get()],self.chat_size_var.get())
        self.themes.styles()
        self.import_center.history.render()
        self.set_status("字体预览已更新；点击保存设置即可在重启后保留。")

    def preview_theme(self):
        self.page_transition.finish()
        self.themes.set(THEMES[self.theme_var.get()],SURFACE_SCHEMES[self.surface_var.get()])
        self.import_center.history.render()
        if self.guide:
            self.guide.show()
        self.set_status("主题预览已更新；点击保存设置即可在重启后保留。")

    def maybe_start_guide(self):
        if not self.closed and not self.guide and not GuideState(self.store.directory).done:
            self.start_guide()

    def start_guide(self):
        if self.guide:
            self.guide.close()
        self.guide=BeginnerGuide(self)

    def saved_settings(self):
        return replace(self.settings)

    def save_settings(self):
        try:
            settings = self._read_settings()
            self.store.save(settings)
            self.stop_monitor(show_main=True)
            self.settings = settings
            self.settings_note.set("设置已保存")
            self.page_transition.finish()
            self.fonts.set(settings.font_family,settings.chat_font_size)
            self.themes.set(settings.theme,settings.surface_scheme)
            self.import_center.history.render()
            self.gate = StableGate()
            self.set_status("设置已保存。测试连接可以确认 Key 和账号权限。")
        except Exception as error:
            self.show_error(str(error))

    def mode_changed(self):
        self.settings_note.set("模型草稿已更改，点击保存后用于后续分析。")

    def mapping_changed(self):
        self.stop_monitor(show_main=True)
        self.settings.self_on_right = self.right_var.get()
        self.clear_records()
        self.set_status("说话人左右已调整，请重新读取并校对。")

    def auto_changed(self):
        self.settings.auto_analyze = self.auto_var.get()
        self.gate = StableGate()
        if not self.auto_var.get() and self.cancel_analysis:
            self.cancel_analysis.set()
            self.generation += 1
        self.set_status("自动分析已开启。" if self.auto_var.get() else "仅本地读取；可暂停后分析当前文字。")

    def test_connection(self, provider):
        if self.connection_job:
            self.set_status("正在测试连接，请等待。")
            return
        try:
            settings = self._read_settings()
            key = settings.jev_key if provider == "jev" else settings.chat_key
            if not key:
                raise ValueError("请先填写该服务的 API Key。")
        except Exception as error:
            self.show_error(str(error))
            return
        self.job_sequence += 1
        job = self.job_sequence
        self.connection_job = job
        self.set_status("正在测试连接（只发送测试文字）…")
        def worker():
            try:
                self.events.put((job, self.generation, "connection", check_connection(settings, provider)))
            except Exception as error:
                self.events.put((job, self.generation, "connection_error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def select_region(self):
        if self.capture_job:
            self.set_status("正在识别文字，完成后再框选。")
            return
        self.stop_monitor(show_main=False)
        self.clear_records()
        if self.floating:
            self.floating.destroy()
            self.floating = None
        self.root.withdraw()
        self.root.after(250, lambda: setattr(self, "selector", RegionSelector(self.root, self.region_selected)))

    def region_selected(self, region):
        self.selector = None
        try:
            if region:
                self.target = CaptureTarget.bind(region)
                self.region_label.configure(text=f"{self.target.title[:36]} · {region.width} × {region.height}")
                self.set_status("选区已绑定窗口。先检查文字，再开始实时分析。")
                self.capture_once(restore_after=True)
            else:
                self.set_status("已取消框选。")
        except Exception as error:
            self.target = None
            self.set_status(str(error), True)
        finally:
            self.root.after(400, self.root.deiconify)

    def capture_once(self, restore_after=False):
        if self.capture_job:
            self.set_status("本地文字识别中，请稍候…")
            return
        if not self.target:
            self.set_status("请先框选聊天区域。", True)
            return
        self.job_sequence += 1
        job, generation = self.job_sequence, self.generation
        target, right = self.target, self.right_var.get()
        self.capture_job = job
        def worker():
            try:
                region = target.resolve()
                image = grab(region)
                # Check visibility again after capture to avoid common focus races.
                if target.resolve() != region:
                    raise CaptureUnavailable("读取时窗口移动，稍后重新读取。")
                transcript = self.ocr.recognize(image, right)
                self.events.put((job, generation, "capture", (image, transcript)))
            except CaptureUnavailable as error:
                self.events.put((job, generation, "unavailable", str(error)))
            except Exception:
                self.events.put((job, generation, "capture_error", "本地识别失败。请确认选区有效；必要时按 README 重新安装依赖。"))
        self.set_status("本地识别中…首次加载 OCR 模型可能需要几秒。")
        threading.Thread(target=worker, daemon=True).start()

    def toggle_monitor(self):
        if self.monitoring:
            self.stop_monitor(show_main=True)
            self.set_status("已暂停。现在可以校对文字或切换聊天对象。")
            return
        if not self.target:
            self.set_status("请先框选 QQ / 微信聊天区。", True)
            return
        try:
            self.settings = self.saved_settings()
            self.settings.validate(require_keys=self.auto_var.get())
        except Exception as error:
            self.show_error(str(error))
            self.show_page("接口设置")
            return
        self.generation += 1
        self.gate = StableGate()
        self.monitoring = True
        self.next_capture = 0
        self.editor.configure(state="disabled")
        self.live_button.configure(text="暂停并校对")
        self.set_status("实时读取已开启；文字稳定两次后自动分析。" if self.auto_var.get() else "实时本地读取已开启（自动分析关闭）。")
        if self.float_var.get():
            self.show_floating()

    def stop_monitor(self, show_main=False):
        self.monitoring = False
        self.generation += 1
        if self.cancel_analysis:
            self.cancel_analysis.set()
        if hasattr(self, "editor"):
            self.editor.configure(state="normal")
            self.live_button.configure(text="开始实时分析")
        if show_main:
            if self.floating:
                self.floating.destroy()
                self.floating = None
            self.root.deiconify()

    def analyze_manual(self):
        if self.monitoring:
            self.stop_monitor(show_main=True)
        try:
            settings = self.saved_settings()
            settings.validate()
            transcript = parse_manual(self.editor.get("1.0", "end-1c"))
            same_capture = self.transcript is not None and transcript.text == self.transcript.text
            image = self.image if same_capture else None
            if same_capture:
                transcript = self.transcript
            self.settings = settings
            self.submit_analysis(transcript, image)
        except Exception as error:
            self.show_error(str(error))

    def submit_analysis(self, transcript, image, use_archive_context=True):
        if self.import_center.history.busy:
            self.set_status("逐条分析仍在处理，先暂停并等待当前条保存，再发起其他模型请求。")
            return
        if self.analysis_job:
            self.set_status("上一条请求仍在处理，请等待完成后再分析。")
            return
        if self.active_profile and use_archive_context:
            try:
                transcript = self.archives.context(self.active_profile, transcript)
            except Exception as error:
                self.show_error(str(error))
                return
        self.job_sequence += 1
        job, generation = self.job_sequence, self.generation
        self.analysis_job = job
        self.manual_button.configure(state="disabled")
        settings = replace(self.settings)
        cancel = threading.Event()
        self.cancel_analysis = cancel
        self.gate.submitted(time.monotonic(), settings.cooldown)
        self.set_status(f"{settings.mode} 正在分析…")
        def worker():
            try:
                result = analyze(settings, transcript, image, cancel=cancel)
                self.events.put((job, generation, "analysis", (transcript.fingerprint, transcript, result)))
            except Exception as error:
                self.events.put((job, generation, "analysis_error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                job, generation, kind, payload = self.events.get_nowait()
                if kind in {"capture", "unavailable", "capture_error"} and job == self.capture_job:
                    self.capture_job = None
                if kind in {"analysis", "analysis_error"} and job == self.analysis_job:
                    self.analysis_job = None
                    self.manual_button.configure(state="normal")
                if kind in {"connection", "connection_error"} and job == self.connection_job:
                    self.connection_job = None
                    self.set_status(payload, kind == "connection_error")
                    continue
                if generation != self.generation:
                    continue
                if kind == "capture":
                    image, transcript = payload
                    self.image, self.transcript = image, transcript
                    self.update_preview(image)
                    previous_text = self.editor.get("1.0", "end-1c")
                    if previous_text != transcript.text:
                        set_text(self.editor, transcript.text, self.monitoring)
                        # A response to older visible text must no longer be offered.
                        if self.result:
                            self.result = None
                            self.result_transcript = None
                            self.render_empty()
                            self.result_source.configure(text="聊天已变化，等待新分析。")
                            self.render_floating()
                    if transcript.messages:
                        self.gate.observe(transcript.fingerprint)
                        if self.monitoring and self.active_profile and self.archive_var.get() and self.gate.count == 2:
                            added = self.archives.append_live(self.active_profile, transcript)
                            if added:
                                self.import_center.refresh(self.active_profile)
                                self.update_archive_label()
                        self.ocr_note.configure(text=" · ".join(transcript.warnings[:2]))
                        self.set_status(f"识别到 {len(transcript.messages)} 条可见记录；" + ("等待稳定或新变化。" if self.monitoring else "可校对后分析。"))
                    else:
                        self.gate = StableGate()
                        self.ocr_note.configure(text="未识别到文字。请重新框选，或改用手动粘贴。")
                        self.set_status("当前选区未识别到文字。", True)
                elif kind == "analysis":
                    fingerprint, transcript, result = payload
                    if self.monitoring:
                        current = self.transcript.fingerprint if self.transcript else ""
                    else:
                        current = parse_manual(self.editor.get("1.0", "end-1c")).fingerprint if self.editor.get("1.0", "end-1c").strip() else ""
                    if fingerprint == current:
                        self.result = result
                        self.result_transcript = transcript
                        self.gate.succeeded(fingerprint)
                        self.render_result(result)
                        self.import_center.show_result(result, self.active_profile)
                        self.set_status("分析完成 · 点击复制，修改确认后发送。")
                    else:
                        self.set_status("聊天已变化，旧结果已忽略；等待新记录稳定后分析。")
                elif kind == "unavailable":
                    # Do not analyze the last successful crop while currently hidden.
                    self.generation += 1
                    if self.cancel_analysis:
                        self.cancel_analysis.set()
                    self.gate = StableGate()
                    self.transcript = None
                    self.image = None
                    self.result = None
                    self.result_transcript = None
                    self.render_empty()
                    self.result_source.configure(text="当前聊天区域不可读，已清除上一轮建议。")
                    self.render_floating()
                    self.set_status(payload, True)
                elif kind in {"capture_error", "analysis_error"}:
                    if kind == "capture_error":
                        self.stop_monitor(show_main=True)
                    else:
                        self.auto_var.set(False)
                        self.settings.auto_analyze = False
                    self.set_status(payload + " 自动分析已暂停，请修正后重新开启。", True)
        except queue.Empty:
            pass
        except Exception:
            self.set_status("处理结果时发生异常，请清空当前记录后重试。", True)
            self.auto_var.set(False)
        now = time.monotonic()
        if self.monitoring:
            if now >= self.next_capture and not self.capture_job:
                self.next_capture = now + self.settings.interval
                self.capture_once()
            if self.auto_var.get() and self.transcript and self.gate.ready(now) and not self.analysis_job and not self.capture_job:
                self.submit_analysis(self.transcript, self.image)
        self.root.after(120, self.poll)

    def update_preview(self, image):
        thumbnail = image.copy()
        thumbnail.thumbnail((max(300, self.preview.winfo_width()), 142))
        self.preview_photo = ImageTk.PhotoImage(thumbnail)
        self.preview.configure(image=self.preview_photo, text="", height=142)

    def _paragraph(self, parent, title, content, color=TEXT):
        frame = tk.Frame(parent, bg=PANEL, padx=16, pady=12)
        frame.pack(fill="x", padx=4, pady=4)
        label(frame, title, 10, TEAL, True).pack(anchor="w")
        label(frame, content, 10, color, wraplength=450).pack(fill="x", pady=(8, 0))

    def render_result(self, result):
        for panel in (self.reply_panel, self.logic_panel, self.sentence_panel):
            panel.clear()
        scope = self.result_transcript
        context = f" · 档案 {scope.archive_name}：历史摘录 {len(scope.history)} 条 / 总 {scope.archive_count} 条" if scope and scope.archive_name else ""
        self.result_source.configure(text=result.source + context)
        self._paragraph(self.reply_panel.inner, "当前语境", result.summary)
        if result.should_wait:
            self._paragraph(self.reply_panel.inner, "节奏建议", "可以先等待或简短收尾，避免连续追问。", AMBER)
        for index, reply in enumerate(result.replies):
            card = tk.Frame(self.reply_panel.inner, bg=SURFACE, padx=14, pady=12)
            card.pack(fill="x", padx=12, pady=6)
            top = tk.Frame(card, bg=SURFACE)
            top.pack(fill="x")
            label(top, f"0{index + 1}  " + reply["style"] + (" · 推荐" if index == 0 else ""), 10, TEAL if index == 0 else TEXT, True).pack(side="left")
            editor = text_box(card, height=max(2, min(5, len(reply["text"]) // 28 + 1)))
            editor.insert("1.0", reply["text"])
            editor.pack(fill="x", pady=(10, 8))
            button(top, "复制", lambda e=editor: self.copy(e.get("1.0", "end-1c")), padx=10, pady=4).pack(side="right")
            label(card, reply["reason"], 8, MUTED, wraplength=420).pack(fill="x")
        if result.cautions:
            self._paragraph(self.reply_panel.inner, "使用前核对", "\n".join("· " + text for text in result.cautions), MUTED)
        self._paragraph(self.logic_panel.inner, "我方表达逻辑", result.self_logic)
        self._paragraph(self.logic_panel.inner, "对方表达逻辑", result.other_logic)
        score = result.signal_score
        quality = result.reply_quality
        self._paragraph(self.logic_panel.inner, "互动积极度 · " + (f"{score}/100" if score is not None else "证据不足"), "只衡量这段文字中的互动表现，不代表对方喜欢你的概率。")
        self._paragraph(self.logic_panel.inner, "最近我方回复 · " + grade(quality["score"]), (f"表达质量 {quality['score']:.0f}/100；确定度 {quality['confidence']:.0%}\n" if quality["score"] is not None else "缺少足够证据\n") + quality["evidence"])
        for key, (name, _, _) in DIMENSIONS.items():
            metric = result.dimensions[key]
            card = tk.Frame(self.logic_panel.inner, bg=PANEL, padx=16, pady=10)
            card.pack(fill="x", pady=3)
            value = f"{metric['score']:.0f}/100" if metric["score"] is not None else "证据不足"
            label(card, name + "   " + value + f"   · 确定度 {metric['confidence']:.0%}", 10).pack(anchor="w")
            ttk.Progressbar(card, style="Signal.Horizontal.TProgressbar", maximum=100, value=metric["score"] or 0).pack(fill="x", pady=8)
            label(card, metric["evidence"], 8, MUTED, wraplength=440).pack(fill="x")
        if not result.sentences:
            self._paragraph(self.sentence_panel.inner, "逐句分析", "模型未提供逐句标签。")
        for row in result.sentences:
            card = tk.Frame(self.sentence_panel.inner, bg=SURFACE, padx=14, pady=12)
            card.pack(fill="x", padx=12, pady=6)
            label(card, f"{row['index']:02d}  {row['speaker']}", 9, TEAL, True).pack(anchor="w")
            label(card, row["text"], 10, TEXT, wraplength=420).pack(fill="x", pady=(8, 10))
            for kind, caption in (("emotion", "情绪"), ("intent", "意图")):
                values = "  /  ".join(f"{v['label']} {v['probability']:.0%}" for v in row[kind])
                label(card, caption + "  " + values, 8, MUTED, wraplength=420).pack(fill="x", pady=3)
        for panel in (self.reply_panel, self.logic_panel, self.sentence_panel):
            panel.bind_children()
        self.render_floating()

    def show_floating(self):
        self.root.withdraw()
        if self.floating and self.floating.winfo_exists():
            return
        window = tk.Toplevel(self.root)
        self.floating = window
        window.title("聊有据 · 回复建议")
        window.configure(bg=PANEL)
        window.attributes("-topmost", True)
        window.resizable(False, False)
        width, height = 370, 590
        import mss
        with mss.mss() as screen:
            monitors = [dict(m) for m in screen.monitors[1:]]
        try:
            region = self.target.resolve() if self.target else None
        except CaptureUnavailable:
            region = self.target.region if self.target else None
        positions = []
        for monitor in monitors:
            for x in (monitor["left"] + monitor["width"] - width - 18, monitor["left"] + 18):
                y = monitor["top"] + 48
                overlap = region and x < region.left + region.width and x + width > region.left and y < region.top + region.height and y + height > region.top
                if not overlap:
                    positions.append((x, y))
        x, y = positions[0] if positions else (monitors[0]["left"] + monitors[0]["width"] - width - 18, monitors[0]["top"] + 48)
        window.geometry(f"{width}x{height}+0+0")
        window.update_idletasks()
        user32 = ctypes.WinDLL("user32")
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SetWindowPos(user32.GetAncestor(window.winfo_id(), 2), ctypes.c_void_p(-1), x, y, width, height, 0x0040)
        top = tk.Frame(window, bg=PANEL, padx=14, pady=12)
        top.pack(fill="x")
        label(top, "聊有据", 17, TEAL, True).pack(side="left")
        button(top, "暂停 / 工作台", self.float_back, padx=9, pady=6).pack(side="right")
        self.float_status = label(window, self.status.get(), 8, MUTED, wraplength=340)
        self.float_status.pack(fill="x", padx=14, pady=(0, 8))
        self.float_body = ScrollPanel(window)
        self.float_body.pack(fill="both", expand=True, padx=7, pady=(0, 9))
        window.protocol("WM_DELETE_WINDOW", self.float_back)
        self.render_floating()

    def float_back(self):
        self.stop_monitor(show_main=True)
        self.set_status("已暂停读取和后续请求，可以校对文字。")

    def render_floating(self):
        if not self.floating or not self.floating.winfo_exists():
            return
        self.float_body.clear()
        if not self.result:
            label(self.float_body.inner, "等待聊天内容稳定…\n请露出已选聊天区域。", 11, MUTED, wraplength=320).pack(fill="x", padx=14, pady=20)
            return
        if self.result.should_wait:
            label(self.float_body.inner, "建议先等待或简短收尾", 10, AMBER).pack(fill="x", padx=12, pady=8)
        for i, reply in enumerate(self.result.replies):
            card = tk.Frame(self.float_body.inner, bg=SURFACE, padx=12, pady=12)
            card.pack(fill="x", padx=6, pady=6)
            row = tk.Frame(card, bg=SURFACE)
            row.pack(fill="x")
            label(row, f"0{i + 1} · " + reply["style"], 9, TEAL, True).pack(side="left")
            editor = text_box(card, height=4)
            editor.insert("1.0", reply["text"])
            editor.pack(fill="x", pady=(10, 0))
            button(row, "复制", lambda e=editor: self.copy(e.get("1.0", "end-1c")), padx=8, pady=4).pack(side="right")
        self.float_body.bind_children()

    def copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.set_status("已复制。请检查、修改后再发送。")

    def show_error(self, text):
        self.set_status(text, True)
        messagebox.showerror("聊有据", text, parent=self.floating or self.root)

    def clear_records(self):
        self.transcript = None
        self.image = None
        self.result = None
        self.result_transcript = None
        self.gate = StableGate()
        set_text(self.editor, "")
        self.preview.configure(image="", text="只选消息气泡，避开联系人和输入框", height=7)
        self.preview_photo = None
        self.result_source.configure(text="等待分析 · 每条建议都可编辑后复制")
        self.render_empty()
        self.render_floating()

    def clear(self):
        self.stop_monitor(show_main=True)
        self.target = None
        self.region_label.configure(text="未选择聊天区域")
        self.clear_records()
        self.set_status("已清空当前记录、分析和选区。")

    def load_demo(self):
        self.active_profile = None
        self.update_archive_label()
        self.clear()
        text = "对方：今天终于把手头的事情忙完了，有点累。\n我：辛苦啦，晚上打算怎么放松一下？\n对方：想看个电影，你有推荐吗？"
        self.transcript = parse_manual(text)
        set_text(self.editor, text)
        self.result_transcript = self.transcript
        values = (76, 83, 65, 72, None, None)
        self.result = Analysis("对方分享疲惫，接着向你征求电影建议。先回答问题，再给一个轻松的选择。", "你先回应对方的辛苦，再询问放松方式，接话方向连贯。", "对方从忙完后的疲惫，转到看电影的计划，并提出具体问题。", {k: {"score": v, "confidence": .78 if v is not None else .3, "evidence": "示例：对方主动分享近况并向你提出问题。" if v is not None else "示例中没有足够证据。"} for k, v in zip(DIMENSIONS, values)}, {"score": 84, "confidence": .8, "evidence": "示例：回应了疲惫感受，也给了对方表达空间。"}, [{"index": 3, "speaker": "对方", "text": self.transcript.messages[-1].text, "emotion": [{"label": "好奇", "probability": .74}, {"label": "平静", "probability": .2}], "intent": [{"label": "征求建议", "probability": .86}, {"label": "延续话题", "probability": .12}]}], [{"style": "自然简短", "text": "想看轻松一点的，还是剧情比较有意思的？我帮你一起挑。", "reason": "先确认偏好，避免随便推荐对方不喜欢的类型。"}, {"style": "体贴一点", "text": "忙一天辛苦啦，今晚就挑个轻松的吧。你平时喜欢哪种类型？", "reason": "接住疲惫，也回应了选电影的需要。"}, {"style": "轻松接话", "text": "那今晚安排个电影放松一下。喜剧、悬疑还是动画，你先选个方向？", "reason": "给出容易回答的选择，降低接话成本。"}], ["这是本地演示数据，未调用任何模型。", "不能由这三句话判断恋爱好感。"], False, .02, "演示数据 · 未调用 API")
        self.render_result(self.result)
        self.ocr_note.configure(text="本地示例，用于展示界面；标签与分数为演示值。")
        self.set_status("演示已载入（未调用 API）。填写 Key 后可分析你的记录。")

    def export_report(self):
        if not self.result:
            self.set_status("请先分析当前记录。", True)
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="导出聊天分析报告", defaultextension=".md", initialfile="聊天分析报告.md", filetypes=[("Markdown 报告", "*.md")])
        if not path:
            return
        result = self.result
        lines = ["# 聊天分析报告", "", "来源：" + result.source, "", "本报告含聊天原文。互动分数不代表真实好感或喜欢的概率。", "", "## 当前语境", result.summary, "", "## 双方逻辑", "我：" + result.self_logic, "对方：" + result.other_logic, "", "## 下一句建议"]
        for reply in result.replies:
            lines.extend(["", "### " + reply["style"], reply["text"], "理由：" + reply["reason"]])
        lines.extend(["", "## 互动维度", "", "| 维度 | 得分 | 确定度 | 证据 |", "|---|---:|---:|---|"])
        for key, (name, _, _) in DIMENSIONS.items():
            metric = result.dimensions[key]
            evidence = metric["evidence"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {name} | {metric['score'] if metric['score'] is not None else '证据不足'} | {metric['confidence']:.0%} | {evidence} |")
        lines.extend(["", "## 逐句标签"])
        for row in result.sentences:
            lines.extend(["", f"{row['index']} · {row['speaker']}：{row['text']}", "情绪：" + " / ".join(f"{v['label']} {v['probability']:.0%}" for v in row["emotion"]), "意图：" + " / ".join(f"{v['label']} {v['probability']:.0%}" for v in row["intent"])])
        lines.extend(["", "## 注意事项", *["- " + c for c in result.cautions], "", "## 当前分析原文", "", self.result_transcript.text])
        if self.result_transcript.archive_name:
            scope = self.result_transcript
            lines.extend(["", "## 本轮使用的历史背景", f"联系人档案：{scope.archive_name}；总 {scope.archive_count} 条；本轮历史摘录 {len(scope.history)} 条。", "未提供的历史未在本轮分析中读取。", ""])
            lines.extend(f"{m.timestamp} {m.speaker}：{m.text}" for m in scope.history)
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            self.set_status("报告已导出至你选择的文件。")
        except OSError:
            self.show_error("报告未能保存，请检查目录权限。")

    def close(self):
        self.page_transition.close()
        if self.guide:
            self.guide.close()
        self.import_center.history.pause()
        self.closed = True
        self.stop_monitor()
        for token in self.root.tk.call("after", "info"):
            self.root.after_cancel(token)
        self.root.update_idletasks()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="QQ / 微信屏幕回复助手")
    parser.add_argument("--smoke-test", type=Path, help="显示本地示例，截图自己的测试窗口后退出，不读取聊天或调用 API")
    parser.add_argument("--self-test", type=Path, help="使用合成图片与虚构密钥验证 OCR 和加密，写入结果后退出")
    arguments = parser.parse_args()
    if arguments.self_test:
        from .diagnostics import run_self_test
        raise SystemExit(0 if run_self_test(arguments.self_test) else 1)
    enable_dpi_awareness()
    root = tk.Tk()
    try:
        app = AssistantApp(root,show_guide=not arguments.smoke_test)
        if arguments.smoke_test:
            app.show_page("实时分析")
            app.load_demo()
            root.attributes("-topmost", True)
            def snapshot():
                try:
                    arguments.smoke_test.parent.mkdir(parents=True, exist_ok=True)
                    root.update_idletasks()
                    grab(Region(root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height())).save(arguments.smoke_test)
                finally:
                    app.close()
            root.after(1000, snapshot)
        root.mainloop()
    except Exception:
        # Never dump credentials / transcripts in a startup traceback.
        messagebox.showerror("聊有据", "启动失败，请用启动脚本重新安装依赖，或联系开发者检查运行环境。", parent=root)
        root.destroy()
        raise SystemExit(1)
