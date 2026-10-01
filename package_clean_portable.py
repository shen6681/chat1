"""Create a shareable runtime from allowlisted files and pristine upstream assets."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOYED = Path("D:/chat1")
OUTPUT = Path(os.environ.get('CHAT1_PACKAGE_OUTPUT',"D:/chat1_便携版"))
ZIP = OUTPUT.with_suffix(".zip")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_file(source, relative):
    target = OUTPUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def extract_checked(archive_path, destination):
    destination = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            target = (destination/entry.filename).resolve()
            if not target.is_relative_to(destination) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Unsafe ZIP path")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def verify_upstream(folder):
    manifest = json.loads((folder/"provenance.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if sha256(folder/item["file"]) != item["sha256"]:
            raise ValueError("Upstream asset hash mismatch: " + item["file"])


def main():
    if OUTPUT.exists() or ZIP.exists():
        raise SystemExit("Output already exists; refusing to mix an old folder with a clean package.")
    OUTPUT.mkdir(parents=True)
    version = json.loads((DEPLOYED/"VERSION.json").read_text(encoding="utf-8"))
    deployed_exe=DEPLOYED/version.get("exe_file","ChatReplyAssistant.exe")
    if sha256(deployed_exe) != version["exe_sha256"]:
        raise ValueError("Application binary does not match its release manifest")
    copy_file(deployed_exe,"ChatReplyAssistant.exe")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        copy_file(DEPLOYED/name, name)
    shutil.copytree(ROOT/"dist"/"licenses", OUTPUT/"licenses")
    font_folder=ROOT/'assets'/'fonts'
    for entry in json.loads((font_folder/'provenance.json').read_text(encoding='utf-8')):
        if sha256(font_folder/entry['file']) != entry['sha256']:
            raise ValueError('Font provenance mismatch')
    shutil.copytree(font_folder, OUTPUT/'fonts')

    # An explicit list excludes account data, logs, exports and helper backups.
    for tool, files in {
        "QQNT_Export":("QQNT_Export_3.3.0.exe","QQNT_Export-source-v3.3.0.zip","LICENSE","README-upstream.md","provenance.json"),
        "WeChatEXP":("wechat_exp_2.10.20260928.exe","pc_wechat_exp-source-v2.10.20260928.zip","README-upstream.md","provenance.json"),
    }.items():
        folder = ROOT/"tools"/tool
        verify_upstream(folder)
        for name in files:
            copy_file(folder/name, Path("tools")/tool/name)

    manifest = json.loads((ROOT/"dist"/"tools"/"provenance.json").read_text(encoding="utf-8"))
    for item in manifest:
        original = ROOT/"tools"/item["file"]
        if sha256(original) != item["sha256"]:
            raise ValueError("Original connector/source archive hash mismatch")
        if item["file"] == "QQChatExporter-v6.3.0.zip":
            extract_checked(original, OUTPUT/"tools"/"QQChatExporter")
        else:
            copy_file(original, Path("tools")/"source"/item["file"])
    copy_file(ROOT/"dist"/"tools"/"provenance.json", "tools/provenance.json")
    shutil.copytree(ROOT/"dist"/"tools"/"licenses", OUTPUT/"tools"/"licenses")
    copy_file(ROOT/"HELPER_TOOLS.md", "tools/README.md")

    guide = """聊有据 2.8.1 · Windows 便携版

一、打开程序
完整解压 ZIP 到普通可写文件夹，再双击“启动程序.cmd”或 ChatReplyAssistant.exe。
主程序已内置 Python 和中文 OCR 模型，无需安装 Python、无需运行源码安装脚本。
面向 Windows 10 / 11 64位；不适用于 macOS、Linux 或32位Windows。
请完整保留 tools 和 licenses 文件夹，不要直接在压缩软件预览窗口内启动。

二、首次使用
第一次打开在浏览器本机端口显示新版工作台，跟着新手指南的“下一步”即可。
可以随时跳过；完成或跳过后不再自动出现。“使用说明”或Ctrl+K → 重新查看新手指南，可以再看。
引导期间不自动导出记录、不调用模型、不扣 API 额度；直接关软件则下次仍会引导。
设置 → 模型、字体 / 主色 / 区块背景；点“保存设置”后生效并重启保留。
内置霞鹜文楷、站酷快乐体、站酷小薇体、马善政楷书，无须安装字体；六套主题自由切换；区块背景也可独立选择，点击保存后保留。

1. 设置 → 选择模型、字体字号与使用偏好，接口子区域填写自己的 Key，点击保存设置。
   Jev / 组合模式由 Jev 批量评分；DeepSeek 仅在勾选单条或多选解释或生成回复时调用。
   启动、文件导入、查看历史和离线自检不需要 API Key；调用模型分析需要联网和对应API额度。
2. 微信可在导入中心一键备份导入，必须自己选择两个目录。QQ导出工具也在导入中心，其他文字文件可直接选择导入。
   确认会话与哪位是我，再保存联系人档案。仅提取文字，跳过图片和表情包。
3. 选择联系人，点击开始/结束日期在日历里选择，确定后点筛选，再开始评分。今日 / 近7天 / 全部时间直接筛选；重置恢复全部时间。
   每10条一组请求与保存，再显示各条评分；无法判断自动继续，仅提示页码。
   记录每页100条，评分会处理整个所选时间范围。暂时断连选择重连原任务。
4. 分析未完成可暂停或退出，重启后选联系人，点“继续上次任务”。默认跳过已完成消息。
   仅主动勾选“重新评分已完成记录”才重做。尚未收到并保存成功响应的请求可能重试。
5. 人物卡六维互动指标与好感度分别计算，仅供理解文字线索，不表示对方真实喜欢的概率。
6. 点击生成回复获取所选范围建议；右上角“屏幕读取”打开OCR窗口，QQ导出在导入中心，选择同一联系人再框选聊天区。
   校对发言人，开始实时读取；建议需由使用者复制、修改和发送。
7. 好感度从50起，每次点击“分析接下来的100条”只计算一组并保存，继续要再次点击；你自行决定分析几组。

退出程序：Ctrl+K → 退出程序。只关闭浏览器不会停止本机服务。

三、QQ / 微信导出
QQ：先安装并登录自己的 QQNT。附带连接器是原始干净发行文件，没有打包作者的登录配置。
按QQ导出中心内嵌说明启用本机 OneBot HTTP 服务、设置自己的 Token，再加载好友和读取私聊。
已有 NapCat / LLOneBot 时可直接使用，不必再次启动附带连接器。
QQNT数据库导出器处理已解密副本，原始加密数据库需要先准备解密副本。
微信：先登录自己的微信，在导入中心使用一键向导。备份目录、文字导出目录必须自己分别选择，无默认地址。选账号备份、选私聊提取文字、确认身份后保存；也可直接打开WeChatEXP仪表盘。
推荐 ChatLab JSONL / JSON，TXT / 聊天 HTML 也可导入。导出器配置与备份由各自工具保存。
原有 WeFlow 导出文件和本地 API 兼容入口仍可用。
QQ / 微信客户端不包含在此包中，导出兼容性取决于客户端和第三方工具版本。

四、数据和密钥
此包没有私人聊天、API Key、用户账号登录状态、原配置、备份、项目测试报告或旧版本EXE。
使用者自己的设置和聊天档案保存于：
%LOCALAPPDATA%\\ChatReplyAssistant\\settings.json
%LOCALAPPDATA%\\ChatReplyAssistant\\archives.sqlite3
API Key 用当前 Windows 用户的 DPAPI 加密；聊天文字、评分及续做任务存于本机SQLite。
在另一台电脑使用不会自动携带当前电脑的聊天档案或密钥。导入不调用模型，分析会向所选API发文字。
不要把使用后的工具备份、账号配置、日志或密钥再次打包分享。

五、离线检查和文件说明
可双击“离线自检.cmd”检查内置 OCR、Windows密钥加密和聊天档案检查点，使用合成数据且不联网。
ChatReplyAssistant.exe：主程序；tools：导出器、QQ连接器及必要的对应源码；licenses：依赖许可。
VERSION.json：版本；文件清单.json：逐文件SHA256；THIRD_PARTY_NOTICES.md：第三方说明。
第三方工具保留对应源码和许可，助手的MIT许可不替代它们。WeChatEXP上游该版本未声明许可证，
不要由此推定任意商业分发权，详见 tools/README.md。第三方账号均由使用者本人配置。
"""
    (OUTPUT/"使用说明.txt").write_text(guide, encoding="utf-8-sig")
    (OUTPUT/"README.md").write_text("# 聊有据 2.8.1 便携版\n\n完整解压后双击 **启动程序.cmd**。无需安装 Python。\n\n"+guide, encoding="utf-8")
    (OUTPUT/"启动程序.cmd").write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nstart "" "%~dp0ChatReplyAssistant.exe" %*\r\n')
    (OUTPUT/"离线自检.cmd").write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nset "CHAT1_CHECK=%TEMP%\\chat1-check-%RANDOM%-%RANDOM%.json"\r\nstart "" /wait "%~dp0ChatReplyAssistant.exe" --self-test "%CHAT1_CHECK%"\r\nif exist "%CHAT1_CHECK%" type "%CHAT1_CHECK%"\r\necho.\r\npause\r\n')
    version.update(distribution="clean-portable", contains_personal_data=False, python_install_required=False,
                   platform="Windows 10/11 x64", first_use="Supply your own API keys for model requests",exe_file="ChatReplyAssistant.exe")
    (OUTPUT/"VERSION.json").write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding="utf-8")

    # Check the connector came from upstream, with only its public default configurations.
    connector = OUTPUT/"tools"/"QQChatExporter"/"NapCat-QCE-Windows-x64"
    defaults={"napcat.json","onebot11.json","plugins.json","plugins/napcat-plugin-builtin/config.json"}
    configs={p.relative_to(connector/"config").as_posix() for p in (connector/"config").rglob("*") if p.is_file()}
    if configs != defaults:
        raise ValueError("Unexpected connector account configuration")
    forbidden={"settings.json","auth.json","archives.sqlite3","qq_path.txt","webui.json"}
    for path in OUTPUT.rglob("*"):
        if path.is_file() and (path.name.lower() in forbidden or path.suffix.lower() in {".sqlite3",".log"}):
            raise ValueError("Unexpected user-state file in the clean package")
    entries=[{"file":p.relative_to(OUTPUT).as_posix(),"size":p.stat().st_size,"sha256":sha256(p)}
             for p in sorted(OUTPUT.rglob("*")) if p.is_file()]
    file_manifest={"version":"2.8.1","file_count":len(entries)+1,"runtime_bytes":sum(e["size"] for e in entries),
                   "assembly":"allowlist plus verified pristine upstream archives","files":entries}
    (OUTPUT/"文件清单.json").write_text(json.dumps(file_manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    with zipfile.ZipFile(ZIP,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(OUTPUT.rglob("*")):
            if path.is_file():
                archive.write(path, Path(OUTPUT.name)/path.relative_to(OUTPUT))
    with zipfile.ZipFile(ZIP) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("ZIP CRC failed: "+bad)
    print(json.dumps({"folder":str(OUTPUT),"zip":str(ZIP),"files":len(entries)+1,"zip_bytes":ZIP.stat().st_size,
                      "zip_sha256":sha256(ZIP),"privacy_audit":"passed","crc":"passed"},ensure_ascii=False))


if __name__ == "__main__":
    main()
