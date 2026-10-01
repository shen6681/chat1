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
        shutil.copy2(file/"ChatReplyAssistant-source-v2.6.1.zip",target/"source"/"ChatReplyAssistant-source-v2.6.1.zip")
    elif file.is_dir():
        shutil.copytree(file, target / file.name, dirs_exist_ok=True)
    elif file.name != "README.md":
        try:
            shutil.copy2(file, target / file.name)
        except PermissionError:
            if file.name != "ChatReplyAssistant.exe":raise
            # Leave a running old process and its data alone; next launch uses the new executable.
            release_executable=target/"ChatReplyAssistant-v2.6.1.exe"
            shutil.copy2(file,release_executable)
readme = (root / "README.md").read_text(encoding="utf-8")
readme = readme.replace("dist/ChatReplyAssistant.exe", "ChatReplyAssistant.exe").replace(".\\dist\\ChatReplyAssistant.exe", ".\\ChatReplyAssistant.exe")
(target / "README.md").write_text(readme, encoding="utf-8")
(target / "启动程序.cmd").write_bytes(('@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0'+release_executable.name+'" %*\r\n').encode('ascii'))
manifest = {"version": "2.6.1", "tests_passed": 99, "tests_skipped": 2, "exe_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "modes": ["导入记录", "实时分析"], "qq_export": {"online":"OneBot HTTP · 读取好友历史并导出 ChatLab JSON", "offline":"QQNT_Export 3.3.0 · 已解密数据库", "prerelease": True}, "wechat_export":"sunhanaix/pc_wechat_exp v2.10.20260928", "features":["自由时间范围","微信文字气泡","十条批量评分与原子保存","无法判断自动继续和页码提醒","DeepSeek按需单条或多选解释","模型字体偏好统一保存","断点续做和跳过已处理","人物卡和攻略进度球","四款内置开源字体","六套可保存主题","日历弹窗与快捷日期筛选","三栏6px卡片和联系人悬浮高亮","可保存分区背景和悬浮说明","首次可跳过动态引导","位置稳定的平滑切换","页面常驻和样式刷新优化","隐藏页键盘焦点隔离"], "archive_location": "%LOCALAPPDATA%/ChatReplyAssistant/archives.sqlite3"}
manifest["exe_file"]=release_executable.name
(target / "VERSION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
(target / "快速开始.txt").write_text("""聊有据 2.6.1

首次启动跟着新手引导的“下一步”认识亮起的按钮；完成或跳过后不再重复。
需要重看：使用说明 → 重新查看新手引导。引导不自动分析，不调用API。
设置里选择字体、字号、六套主题和区块背景，点击保存设置。内置四款字体，无需手工安装。

1. 双击 启动程序.cmd。设置页选择模型、字体与偏好；接口子区域填写自己的 Key，点击保存设置。
2. 导入记录 → QQ 导出中心 / 微信 WeChatEXP / 导入文件 / SQLite / 粘贴。
   预览中确认会话与哪位是我，再保存联系人档案。
3. 选择联系人，点击开始/结束日期打开日历并确定，点筛选；今日 / 近7天 / 全部时间快捷选择，重置清除范围。
   点击开始评分。每10条保存后出现各条“已分析”和评级；无法判断自动继续并提示所在页码。
   图片和表情包跳过，攻略进度球显示六维文字互动信号，可按住拖动。
4. 未完成可暂停或退出；重启后选联系人，点击“继续上次任务”。
   每10条评分和任务检查点一起保存，末组不足10条也保存，默认不重复已处理消息。
   仅明确勾选“重新评分已完成记录”才重做。发送后未收到/保存的请求可能需要重试。
5. 档案分析与回复页 → 生成所选范围回复，或联系人标题“⋯” → 带档案进入实时分析 → 框选 → 开始。
   点击气泡多选后点解释所选，或右键解释一条；解释保存且不改变Jev评分。

微信：
  微信 WeChatEXP → 启动导出器，按其页面完成备份 → 聊天导出 → 一个私聊。
  推荐导出 ChatLab JSONL / JSON，TXT / 聊天 HTML 也可，回助手导入导出文件。
  指定工具及对应源码位于 tools/WeChatEXP；不自动备份、扫描或调用模型。

QQ 在线读取：
  QQ 导出中心 → 打开 QQ 连接器，登录后进入连接器的网络配置。
  新建并启用 HTTP 服务端，host=127.0.0.1，port=3000，设置 HTTP Token。
  回导出中心填写 http://127.0.0.1:3000 和同一个 HTTP Token。
  连接并加载好友 → 选择私聊 → 读取 → 预览存档 / 另存 JSON。
  WebUI 通常是 6099；登录 WebUI 不会自动启用 3000 的记录接口。
  已在用 NapCat / LLOneBot 时可直接连接，无须再次启动附带连接器。

QQ 数据库导出：
  QQNT 数据库导出页 → 选择已解密数据库副本目录 → 输出目录 → 导出私聊 JSON。
  附带 QQNT_Export 3.3.0（上游预发布版），不需要登录。
  加密的原始 nt_msg.db 不能直接导出，也不内置数据库密钥提取。

新消息续存档案可开关，重启后档案仍在。更换联系人请暂停并重新框选。
读取能力取决于连接器/数据库版本，不保证云端或其他设备记录齐全。
导入在本机执行；点击分析时向所选 API 发送最新消息及有限历史摘录。
详见 README.md；主程序源码在 source，工具许可证及对应源码在 tools。
""", encoding="utf-8-sig")
preview=target/"界面预览";preview.mkdir(exist_ok=True)
for name in ("v26-empty.png","v26-history.png","v26-history-small.png","v26-picker-in-app.png","v26-tooltip.png","v26-settings-small.png","v26-pink-mist.png","v26-guide.png","v26-kuaile-small.png","v26-switch.gif"):
    image=root/"assets"/name
    if not image.exists():image=root/"assets"/"screenshots"/name
    if image.is_file():shutil.copy2(image,preview/name)
print(json.dumps({"folder": str(target), "version": "2.6.1", "files": sum(f.is_file() for f in target.rglob("*"))}, ensure_ascii=False))
