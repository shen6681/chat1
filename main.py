"""聊有据 · 科学沟通辅助系统主入口

- 默认启动现代化高精 UI 前端工作台 (React + Tailwind CSS)
- 添加 --desktop / --legacy 参数可启动原 Tkinter 桌面程序
"""
from __future__ import annotations

import sys


def main():
    if any(arg in sys.argv for arg in ("--desktop", "--legacy", "--tk")):
        from chat_assistant.app import main as desktop_main
        desktop_main()
    else:
        from chat_assistant.web_server import launch_web
        launch_web()


if __name__ == "__main__":
    main()
