# Third-party notices

This application uses the following open-source projects. Upstream copyright,
license text and package notices apply to their respective components.

| Component | Upstream | License |
|---|---|---|
| CPython | https://www.python.org/ | Python Software Foundation License |
| Tcl / Tk | https://www.tcl.tk/ | Tcl/Tk license |
| Pillow | https://github.com/python-pillow/Pillow | MIT-CMU |
| python-mss | https://github.com/BoboTiG/python-mss | MIT |
| RapidOCR and bundled OCR models | https://github.com/RapidAI/RapidOCR | Apache-2.0; model sources and included notices apply |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT |
| OpenCV | https://github.com/opencv/opencv | Apache-2.0 |
| NumPy | https://github.com/numpy/numpy | BSD-3-Clause |
| Shapely | https://github.com/shapely/shapely | BSD-3-Clause; includes GEOS components under LGPL-2.1 |
| Pyclipper | https://github.com/fonttools/pyclipper | MIT; Clipper under Boost Software License |
| PyYAML | https://github.com/yaml/pyyaml | MIT |
| PyInstaller | https://github.com/pyinstaller/pyinstaller | GPL-2.0-or-later with bootloader exception |

The portable release includes a `licenses` folder with notices available from
installed dependency distributions. This document is an index, not a replacement
for their complete license texts. Additional transitive components have their
own notices in that folder.

The source checkout does not track WeChatEXP, QQNT_Export, QQChatExporter or
NapCat files. Optional helpers are installed locally under the Git-ignored
`tools/` directory; see `third_party/README.md` for expected paths and hashes.

Feature reference: https://github.com/FerryCorleone/crush-monitor (MIT).
No source files from that project are bundled in this independent implementation.

QQ database exporter: QQNT_Export v3.3.0 (upstream prerelease, GPL-3.0), downloaded
unchanged from https://github.com/Tealina28/QQNT_Export/releases/tag/v3.3.0.
It is invoked as an independent process to export already decrypted QQNT database
copies. Its executable, license and matching source are available from upstream.
No implementation code is incorporated into the assistant. The assistant's
license does not replace the GPL license.

Retained optional QQ connector bundle: QQChatExporter v6.3.0 (GPL-3.0), downloaded unchanged
from https://github.com/shuakami/qq-chat-exporter/releases/tag/v6.3.0. It runs as a
separate process only when the user clicks the QQ connector button. Exporting
through the new assistant UI uses an independently implemented OneBot HTTP client.
Its source and license are available from upstream. It is not included in the
source checkout.

The upstream helper includes NapCat v4.18.19, copyright 2024 Mlikiowa, under its
Limited Redistribution License (non-commercial use, license and attribution must
be retained). Consult its exact upstream license before distribution.
https://github.com/NapNeko/NapCatQQ/blob/v4.18.19/LICENSE
Do not describe this entire helper bundle as unrestricted open-source software.
Other helper dependencies retain their original upstream notices in its folder.
The assistant's MIT license does not replace these component licenses.

WeFlow (CC BY-NC-SA 4.0) is not bundled. Only its documented localhost HTTP API
and exported file formats are independently adapted. No WeFlow source code was
copied into the assistant. ChatLab's published interchange schema is supported
by an independent reader; no ChatLab application code is bundled.

User-selected WeChat exporter: sunhanaix/pc_wechat_exp (WeChat EXP)
v2.10.20260928, downloaded unchanged from its official GitHub release for this
user's local personal use. It is not in the source checkout. This version has no
declared license; do not infer unrestricted redistribution or commercial rights.
No implementation source is incorporated into the assistant. The assistant's MIT
license does not grant rights over this independent helper.

Bundled typefaces (unchanged originals, SIL Open Font License 1.1):
LXGW WenKai Lite, Copyright LXGW and Fontworks, https://github.com/lxgw/LxgwWenKai-Lite;
ZCOOL KuaiLe and ZCOOL XiaoWei, Copyright respective ZCOOL Project Authors;
Ma Shan Zheng, Copyright Ma Shan Zheng Project Authors.
The last three are obtained from the official Google Fonts repository,
https://github.com/google/fonts (ofl/zcoolkuaile, ofl/zcoolxiaowei, ofl/mashanzheng).
Exact pinned commits, original download URLs and SHA256 values are in fonts/provenance.json;
each font's complete original OFL copyright and license text is beside it as *-OFL.txt.
Fonts are loaded privately for the running application, with no system installation.
The application's MIT license does not replace the OFL font licenses.

Browser interface based on the repository UI branch contributed by Yangfan Hu.
React / React DOM, lucide-react, canvas-confetti, clsx, tailwind-merge and Tailwind CSS
retain their MIT licenses under web/licenses in source and licenses/web in the release.
The frontend uses the existing pinned package-lock.json; development dependencies
are not required to launch the portable program.

Native WebView2 shell adapts the UI branch contribution by Yangfan Hu, commit
f699a7cd5c1d195ed69d25415dddd551613fd2cd, using the existing authenticated backend.
pywebview 5.1, pythonnet 3.0.5, clr_loader, cffi and bottle retain their original
licenses in licenses/ in the Windows distribution. proxy-tools and typing_extensions
also retain their installed upstream license files. Microsoft Edge WebView2 and .NET
are system runtimes and are not redistributed by this application.

The full pythonnet/clr_loader license texts missing from their binary wheel metadata
are retained from hash-verified official PyPI source distributions under
assets/licenses in source and licenses/native-runtime in the release. proxy-tools
0.1.0 declares MIT but its sdist has no separate license file; its original package
metadata is retained there. Source URLs and SHA256 are in python-runtime-provenance.json.
pywebview 5.1 retains its upstream BSD 3-Clause license from the installed wheel.
