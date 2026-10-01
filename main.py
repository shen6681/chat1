"""聊有据 · 科学沟通辅助系统主入口

- 默认启动现代化高精 UI 前端工作台 (React + Tailwind CSS)
- 添加 --desktop / --legacy 参数可启动原 Tkinter 桌面程序
"""
from __future__ import annotations

import sys


def main():
    desktop_flags = ("--desktop", "--legacy", "--tk")
    if any(arg in sys.argv for arg in (*desktop_flags, "--self-test", "--smoke-test")):
        sys.argv = [arg for arg in sys.argv if arg not in desktop_flags]
        from chat_assistant.app import main as desktop_main
        desktop_main()
    else:
        import argparse
        from pathlib import Path
        parser = argparse.ArgumentParser(description='聊有据 · 本机工作台')
        parser.add_argument('--no-browser',action='store_true',help='仅启动本机服务')
        parser.add_argument('--server-info',type=Path,help='写入本机服务地址与版本，不含令牌或私人数据')
        args = parser.parse_args()
        from chat_assistant.web_server import launch_web
        launch_web(open_browser=not args.no_browser,ready_file=args.server_info)


if __name__ == "__main__":
    main()
