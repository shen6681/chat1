"""Collect release documentation / dependency notices and create a portable ZIP."""
from importlib import metadata
from pathlib import Path
import shutil
import sys
import zipfile
import hashlib
import json


root = Path(__file__).resolve().parent
dist_root = root / "dist"
shutil.copytree(root / 'assets' / 'fonts', dist_root / 'fonts', dirs_exist_ok=True)
for name in ("README.md", "THIRD_PARTY_NOTICES.md", "LICENSE"):
    shutil.copy2(root / name, dist_root / name)
licenses = dist_root / "licenses"
licenses.mkdir(exist_ok=True)
for distribution in metadata.distributions():
    name = distribution.metadata.get("Name", "unknown")
    for file in distribution.files or []:
        short = Path(str(file)).name.lower()
        if "/licenses/" in str(file).replace("\\", "/") or short.startswith(("license", "copying", "notice")):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                target = licenses / name / str(file).replace("..", "_").replace(":", "_")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
for name in ("LICENSE.txt", "LICENSE"):
    source = Path(sys.base_prefix) / name
    if source.exists():
        shutil.copy2(source, licenses / ("CPython-" + name))
tool_source = root / "tools"
tool_dist = dist_root / "tools"
if (tool_source / "QQNT_Export").exists():
    shutil.copytree(tool_source / "QQNT_Export", tool_dist / "QQNT_Export", dirs_exist_ok=True)
if (tool_source / "WeChatEXP").exists():
    shutil.copytree(tool_source / "WeChatEXP", tool_dist / "WeChatEXP", dirs_exist_ok=True)
if (tool_source / "QQChatExporter").exists():
    shutil.copytree(tool_source / "QQChatExporter", tool_dist / "QQChatExporter", dirs_exist_ok=True)
    sources = tool_dist / "source"
    sources.mkdir(parents=True, exist_ok=True)
    for name in ("QQChatExporter-source-v6.3.0.zip", "NapCat-source-v4.18.19.zip"):
        shutil.copy2(tool_source / name, sources / name)
    notice_folder = tool_dist / "licenses"
    notice_folder.mkdir(exist_ok=True)
    shutil.copy2(tool_source / "NapCat-LICENSE.txt", notice_folder / "NapCat-LICENSE.txt")
    with zipfile.ZipFile(tool_source / "QQChatExporter-source-v6.3.0.zip") as archive:
        member = next(name for name in archive.namelist() if name.count("/") == 1 and name.endswith("/LICENSE"))
        (notice_folder / "QQChatExporter-LICENSE.txt").write_bytes(archive.read(member))
    manifests = []
    for name, url in (
        ("QQChatExporter-v6.3.0.zip", "https://github.com/shuakami/qq-chat-exporter/releases/download/v6.3.0/NapCat-QCE-Windows-x64-v6.3.0.zip"),
        ("QQChatExporter-source-v6.3.0.zip", "https://github.com/shuakami/qq-chat-exporter/archive/refs/tags/v6.3.0.zip"),
        ("NapCat-source-v4.18.19.zip", "https://github.com/NapNeko/NapCatQQ/archive/refs/tags/v4.18.19.zip"),
    ):
        file = tool_source / name
        manifests.append({"file": name, "upstream_url": url, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "size": file.stat().st_size, "modified": False})
    (tool_dist / "provenance.json").write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    shutil.copy2(root / "HELPER_TOOLS.md", tool_dist / "README.md")
source_output = dist_root / "source"
source_output.mkdir(exist_ok=True)
with zipfile.ZipFile(source_output / "ChatReplyAssistant-source-v2.6.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    files = [root / name for name in ("main.py", "requirements.txt", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "HELPER_TOOLS.md", "setup.ps1", "build.ps1", "package_release.py", "deploy_chat1.py", "package_clean_portable.py", "verify_clean_portable.py", "fetch_fonts.py", "preview_v26.py", "preview_motion.py", "probe_transitions.py", "ChatReplyAssistant.spec", "启动程序.cmd")]
    for directory in ("chat_assistant", "tests"):
        files.extend((root / directory).glob("*.py"))
    files.extend(root / "assets" / name for name in ("icon.ico", "icon.png"))
    files.extend(p for p in (root/'assets'/'fonts').iterdir() if p.is_file())
    for file in files:
        if file.exists():
            archive.write(file, Path("ChatReplyAssistant") / file.relative_to(root))
output = root / "ChatReplyAssistant-Windows.zip"
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for file in sorted(dist_root.rglob("*")):
        if file.is_file() and (not file.name.startswith('ChatReplyAssistant-source-v') or file.name=='ChatReplyAssistant-source-v2.6.zip'):
            archive.write(file, Path("ChatReplyAssistant") / file.relative_to(dist_root))
print("Portable ZIP:", output)
