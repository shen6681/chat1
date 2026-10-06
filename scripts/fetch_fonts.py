"""Fetch original OFL fonts from pinned official repositories, never install them."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "assets" / "fonts"
GOOGLE = "9710da1eacb3be272583c3224dcb70f9da6eadbb"


def download(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"chat1-font-assets"}), timeout=60).read()


def main():
    lxgw = json.loads(download("https://api.github.com/repos/lxgw/LxgwWenKai-Lite/commits/main"))["sha"]
    sources = [("霞鹜文楷 · 温柔手写", "LXGW WenKai Lite", "lxgw/LxgwWenKai-Lite", lxgw, "fonts/TTF/LXGWWenKaiLite-Regular.ttf", "OFL.txt")]
    for label, family, folder, filename in (
        ("站酷快乐体 · 俏皮圆润", "ZCOOL KuaiLe", "zcoolkuaile", "ZCOOLKuaiLe-Regular.ttf"),
        ("站酷小薇体 · 清秀书卷", "ZCOOL XiaoWei", "zcoolxiaowei", "ZCOOLXiaoWei-Regular.ttf"),
        ("马善政楷书 · 笔墨手写", "Ma Shan Zheng", "mashanzheng", "MaShanZheng-Regular.ttf"),
    ):
        sources.append((label, family, "google/fonts", GOOGLE, f"ofl/{folder}/{filename}", f"ofl/{folder}/OFL.txt"))
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for label, family, repo, commit, file, license_path in sources:
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{file}"
        content = download(url)
        if content[:4] not in (b"\x00\x01\x00\x00", b"OTTO"):
            raise ValueError("Not an OpenType font")
        (ROOT/Path(file).name).write_bytes(content)
        license_url = f"https://raw.githubusercontent.com/{repo}/{commit}/{license_path}"
        license_text = download(license_url)
        if b"SIL OPEN FONT LICENSE Version 1.1" not in license_text:
            raise ValueError("Unexpected license")
        license_file = Path(file).stem + "-OFL.txt"
        (ROOT/license_file).write_bytes(license_text)
        manifest.append(dict(label=label,family=family,file=Path(file).name,sha256=hashlib.sha256(content).hexdigest(),
                             repository=f"https://github.com/{repo}",commit=commit,url=url,
                             license="SIL OFL 1.1",license_file=license_file,license_url=license_url,modified=False))
    (ROOT/"provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"fonts":len(manifest),"bytes":sum((ROOT/f['file']).stat().st_size for f in manifest)}))


if __name__ == "__main__":
    main()
