# 维护脚本

从仓库根目录运行。日常安装和构建仍使用根目录的 `setup.ps1`、`build.ps1`。

- `package_release.py`：由 `build.ps1` 调用，整理发行文件。
- `package_clean_portable.py`、`verify_clean_portable.py`：制作和检查便携包；需要本机已准备相应工具及构建产物。
- `deploy_chat1.py`：更新本机 `D:/chat1`，会写入该目录，运行前先核对路径。
- `fetch_fonts.py`：从上游下载并核对字体。
- `dev/`：只使用合成数据的界面预览和切换诊断脚本。
