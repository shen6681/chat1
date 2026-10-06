"""Launcher/import bridge for the user-selected, unmodified WeChat EXP."""
from __future__ import annotations

import subprocess
import tkinter as tk
import webbrowser
from tkinter import messagebox

from .qq_export import tool_root


def wechat_dialog(center):
    from .app import PANEL, TEXT, MUTED, label, button
    window = center.dialog("微信导出 · WeChat EXP", "850x610")
    label(window, "微信记录导出", 23, TEXT, True).pack(anchor="w", padx=24, pady=(24,8))
    label(window, "已改用 sunhanaix / pc_wechat_exp · v2.10.20260928", 10, MUTED).pack(anchor="w", padx=24, pady=(0,20))
    for title, description in [
        ("01  启动 WeChat EXP", "首次使用：保持你自己的微信已登录，打开导出器网页，按其“一键备份”流程准备数据。工具的配置和备份保存在 tools/WeChatEXP。"),
        ("02  导出一个私聊", "在“聊天导出”中选择联系人和日期范围，格式推荐 ChatLab JSONL 或 ChatLab JSON，然后下载导出文件。TXT / 聊天 HTML 也可导入。"),
        ("03  回这里导入文字", "确认双方身份后保存档案，选择分析时间范围。图片、表情包、视频和语音记录会跳过，不读取媒体文件或对其 OCR。"),
    ]:
        label(window, title, 12, TEXT, True).pack(anchor="w", padx=24, pady=(9,7))
        label(window, description, 10, MUTED, wraplength=790).pack(anchor="w", padx=24, pady=(0,14))
    note = tk.StringVar(value="导出器独立运行；导入文件本身不调用模型。")
    tk.Label(window, textvariable=note, bg=PANEL, fg=MUTED, anchor="w", wraplength=790).pack(fill="x", padx=24, pady=14)
    button(window, "已有 WeFlow：兼容本地 API 导入", lambda:(window.destroy(),center.weflow_dialog()), padx=10, pady=5).pack(anchor="w", padx=24)
    def launch():
        directory = tool_root()/"WeChatEXP"
        executable = directory/"wechat_exp_2.10.20260928.exe"
        if not executable.exists():
            messagebox.showerror("缺少导出器", "请将上游 WeChatEXP v2.10.20260928 的 EXE 放到 tools/WeChatEXP；源码安装说明见 third_party/README.md。", parent=window)
            return
        try:
            subprocess.Popen([str(executable)], cwd=str(directory), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            note.set("已启动导出器。它会打开本机网页；若未自动打开，可点击“打开导出页面”。按工具说明完成备份和导出。")
        except OSError:
            messagebox.showerror("启动失败", "无法启动 WeChat EXP，请检查完整文件夹和系统的程序运行提示。", parent=window)
    row = tk.Frame(window, bg=PANEL); row.pack(side="bottom", fill="x", padx=24, pady=20)
    button(row, "启动导出器", launch, True).pack(side="left")
    button(row, "打开导出页面", lambda:webbrowser.open("http://127.0.0.1:5000"), padx=10).pack(side="left", padx=8)
    button(row, "项目说明", lambda:webbrowser.open("https://github.com/sunhanaix/pc_wechat_exp"), padx=10).pack(side="left")
    button(row, "导入导出文件", lambda:(window.destroy(), center.pick_file()), True).pack(side="right")
