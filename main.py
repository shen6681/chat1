"""聊有据 · 科学沟通辅助系统主入口

- 默认在浏览器本机端口启动 React 工作台
- 添加 --desktop / --legacy 参数可启动原 Tkinter 桌面程序
"""
from __future__ import annotations

import sys


def main():
    if '--wechat-no-browser' in sys.argv:
        return  # Child-only BROWSER handler; no app window, network or data access.
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
        parser.add_argument('--browser',action='store_true',help='在浏览器中打开同一工作台')
        parser.add_argument('--native',action='store_true',help='显式打开可选的 WebView2 窗口')
        parser.add_argument('--server-info',type=Path,help='写入本机服务地址与版本，不含令牌或私人数据')
        args = parser.parse_args()
        if args.no_browser or args.browser or not args.native:
            from chat_assistant.web_server import launch_web
            launch_web(open_browser=not args.no_browser,ready_file=args.server_info)
        else:
            from chat_assistant.desktop_app import start_desktop
            try: start_desktop(ready_file=args.server_info)
            except (RuntimeError,ImportError,OSError) as error:
                if sys.stderr: print(str(error),file=sys.stderr)
                from chat_assistant.web_server import launch_web
                launch_web(open_browser=True,ready_file=args.server_info)


if __name__ == "__main__":
    main()
