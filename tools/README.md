# 第三方参考源码

本目录保存助手已经声明使用的四个项目的固定版本源码。`source` 下可直接浏览完整源码；ZIP 保留在现有工具约定的路径，供独立核对。源码按上游 Git 对象原样保存，没有改写第三方实现。

| 项目 | 版本 | 可浏览源码 | 对应源码 ZIP | 许可 |
|---|---|---|---|---|
| WeChatEXP / pc_wechat_exp | v2.10.20260928 | `source/pc_wechat_exp-v2.10.20260928/` | `WeChatEXP/pc_wechat_exp-source-v2.10.20260928.zip` | 该版本未声明许可证 |
| QQNT_Export | v3.3.0 | `source/QQNT_Export-v3.3.0/` | `QQNT_Export/QQNT_Export-source-v3.3.0.zip` | GPL-3.0 |
| QQChatExporter | v6.3.0 | `source/qq-chat-exporter-v6.3.0/` | `QQChatExporter-source-v6.3.0.zip` | GPL-3.0 |
| NapCatQQ | v4.18.19 | `source/NapCatQQ-v4.18.19/` | `NapCat-source-v4.18.19.zip` | 上游 Limited Redistribution License |

`source/provenance.json` 记录每个上游仓库、版本标签、实际提交、全部文件的 Git blob ID / SHA256、源码 ZIP 的 SHA256，以及原始说明和许可证的位置。ZIP 由固定提交的 Git 对象在本地生成，不是上游发行版二进制，也不冒充 GitHub 发行资产。源码快照保留上游原本跟踪的文件和资源，包括 WeChatEXP 的 SILK 解码辅助文件。

可浏览目录中的上游 `.gitignore` 文件保存为 `.gitignore.upstream`，内容保持原样，ZIP 中仍使用原始名称。这样上游针对自身构建产物的忽略规则不会把已经跟踪的参考文件排除出助手仓库；清单同时记录原始路径和保存路径。公开的上游构建配置和已跟踪辅助资源仅按具体文件路径加入本仓库的忽略例外。

QQChatExporter v6.3.0 还跟踪了 `plugins/qq-chat-exporter/.napcat-src` 的 Gitlink，但上游没有提供 `.gitmodules`。此处已按它引用的 NapCat 提交 `5bfbf92c215f2c83d9b672a1b296ca2ce37c055d` 补齐该目录，并将嵌套源码纳入 QQChatExporter 的源码 ZIP 和逐文件清单。它是历史开发源码引用，与完整便携版声明的 NapCat v4.18.19 独立保留，没有替换版本。

在项目根目录运行以下命令可离线核验所有源码、ZIP 和原始说明：

```powershell
.venv\Scripts\python.exe verify_reference_sources.py
```

WeChatEXP 和 QQNT_Export 的原始说明、独立来源记录位于各自工具目录；QQChatExporter 和 NapCat 的许可证在 `licenses/`。这些许可证仅适用于相应上游内容，助手自身的 MIT 许可不替代它们。

本次补齐范围为源码。独立运行工具的发行版 EXE、QQ 连接器运行目录及构建产物尚未恢复。`chat_assistant/wechat_client.py` / `wechat_reader.py` 仍通过独立官方工具提供微信备份和读取；保存参考源码不会自动使这些运行入口可用。运行目录约定和操作说明见根目录 `HELPER_TOOLS.md`。

crush-monitor 是功能设计参考；WeFlow 是 HTTP API / 导出格式兼容来源；ChatLab 是数据交换格式参考。助手对这些部分使用独立实现，未把它们作为随包工具，也无需复制它们的完整应用源码。
