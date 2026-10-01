"""Update only packaged app files in the user-requested chat1 folder."""
import hashlib
import json
import shutil
from pathlib import Path


root = Path(__file__).resolve().parent
source = root / "dist"
target = Path("D:/chat1")
target.mkdir(exist_ok=True)
executable = source / "ChatReplyAssistant.exe"
if not executable.exists():
    raise SystemExit("Build the executable first.")
old = target / "ChatReplyAssistant.exe"
release_executable = target / "ChatReplyAssistant.exe"
# The user requested removing old program versions; private data snapshots are separate.
for file in source.iterdir():
    if file.name == "tools" and file.is_dir():
        (target/"tools").mkdir(exist_ok=True)
        for helper in file.iterdir():
            destination=target/"tools"/helper.name
            # The old connector binaries are unchanged; keep its existing login/config files.
            if helper.name=="QQChatExporter" and destination.exists():continue
            if helper.name=="WeChatEXP" and destination.exists():
                # Only our distribution files; never overwrite an exporter's backup/settings.
                for name in ("wechat_exp_2.10.20260928.exe","pc_wechat_exp-source-v2.10.20260928.zip","README-upstream.md","provenance.json"):
                    existing=destination/name
                    if existing.is_file() and hashlib.sha256(existing.read_bytes()).digest()==hashlib.sha256((helper/name).read_bytes()).digest():
                        continue
                    shutil.copy2(helper/name,destination/name)
                continue
            if helper.is_dir():shutil.copytree(helper,destination,dirs_exist_ok=True)
            else:shutil.copy2(helper,destination)
    elif file.name == "source" and file.is_dir():
        (target/"source").mkdir(exist_ok=True)
        shutil.copy2(file/"ChatReplyAssistant-source-v2.7.0.zip",target/"source"/"ChatReplyAssistant-source-v2.7.0.zip")
    elif file.is_dir():
        shutil.copytree(file, target / file.name, dirs_exist_ok=True)
    elif file.name != "README.md":
        try:
            shutil.copy2(file, target / file.name)
        except PermissionError:
            if file.name != "ChatReplyAssistant.exe":raise
            # Leave a running old process and its data alone; next launch uses the new executable.
            release_executable=target/"ChatReplyAssistant-v2.7.0.exe"
            shutil.copy2(file,release_executable)
readme = (root / "README.md").read_text(encoding="utf-8")
readme = readme.replace("dist/ChatReplyAssistant.exe", "ChatReplyAssistant.exe").replace(".\\dist\\ChatReplyAssistant.exe", ".\\ChatReplyAssistant.exe")
(target / "README.md").write_text(readme, encoding="utf-8")
(target / "启动程序.cmd").write_bytes(('@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0'+release_executable.name+'" %*\r\n').encode('ascii'))
manifest = {"version": "2.7.0", "tests_passed": 117, "tests_skipped": 0, "frontend_tests_passed": 3, "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "modes": ["导入记录", "实时分析"], "qq_export": {"online":"OneBot HTTP · 读取好友历史并导出 ChatLab JSON", "offline":"QQNT_Export 3.3.0 · 已解密数据库", "prerelease": True}, "wechat_export":"sunhanaix/pc_wechat_exp v2.10.20260928", "features":["自由时间范围","微信文字气泡","十条批量评分与原子保存","无法判断自动继续和页码提醒","DeepSeek按需单条或多选解释","模型字体偏好统一保存","断点续做和跳过已处理","人物卡和攻略进度球","四款内置开源字体","六套可保存主题","日历弹窗与快捷日期筛选","三栏6px卡片和联系人悬浮高亮","可保存分区背景和悬浮说明","首次可跳过动态引导","位置稳定的平滑切换","页面常驻和样式刷新优化","隐藏页键盘焦点隔离"], "archive_location": "%LOCALAPPDATA%/ChatReplyAssistant/archives.sqlite3"}
manifest["exe_file"]=release_executable.name
(target / "VERSION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
(target / "快速开始.txt").write_text("""聊有据 2.7.0

1. 双击启动程序.cmd，会在浏览器打开新版工作台。
2. 设置里填写接口和选择字体、主题、偏好，然后保存。
3. 导入中心选择文件，确认哪位是我，保存档案。
4. 选择联系人和日期，开始评分。每10条自动保存，无法判断会跳过并提醒页码。
5. 想知道原因时勾选消息，点解释所选；生成回复后自行核对、复制和发送。

首次新手指南可以跳过，完成后不重复；使用说明或Ctrl+K可重看。
右上角屏幕 / 导出工具打开原生窗口，保留真实OCR、QQ与微信导出。
退出：Ctrl+K → 退出程序。只关闭浏览器不会停止服务。
未完成的评分可重启后继续；暂时断连选择重连原任务。
字体与主题保存后重启保留；原有账号、密钥与聊天仍保存在本机。
完整分享包为chat1_便携版.zip，解压后即可运行，新用户填写自己的API。
""", encoding="utf-8-sig")
preview=target/"界面预览";preview.mkdir(exist_ok=True)
for name in ("v27-workspace.jpg","v27-settings.jpg","v27-mobile.jpg"):
    image=root/"assets"/name
    if not image.exists():image=root/"assets"/"screenshots"/name
    if image.is_file():shutil.copy2(image,preview/name)
print(json.dumps({"folder": str(target), "version": "2.7.0", "files": sum(f.is_file() for f in target.rglob("*"))}, ensure_ascii=False))
