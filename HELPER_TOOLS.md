# QQ / 微信导出工具与连接器

主程序“QQ 导出中心”提供在线读取和已解密数据库导出。进入本程序的好友选择、读取、JSON 导出和存档流程；登录连接器本身不会导出记录。

## QQNT_Export：数据库导出器

`QQNT_Export/QQNT_Export_3.3.0.exe` 是 [Tealina28/QQNT_Export](https://github.com/Tealina28/QQNT_Export) 的 [v3.3.0 官方发行二进制](https://github.com/Tealina28/QQNT_Export/releases/tag/v3.3.0)，上游标记为预发布版。本包保留原文件，不修改其实现。在“QQNT 数据库导出”页选择已解密数据库副本目录、输出目录及可选 QQ 号；助手生成 TOML 配置，运行独立导出器，核对输出 JSON 后提供导入预览。

这个工具读取已解密 QQNT 数据库，不是登录工具，也不提供解密功能。原始加密的 `nt_msg.db` 会被助手拒绝。请保留副本目录中的相关数据库，例如 `profile_info.db`。数据库准备可参照 [QQDecrypt](https://qqbackup.github.io/QQDecrypt/) 文档；没有解密副本时使用在线读取。

GPL-3.0 完整许可证在 `QQNT_Export/LICENSE`；对应版本源码在 `QQNT_Export/QQNT_Export-source-v3.3.0.zip`；上游说明在 `QQNT_Export/README-upstream.md`；文件来源、版本、SHA256 和未修改标记在 `QQNT_Export/provenance.json`。

## 在线读取所需的 QQ 连接器

已在用 NapCat / LLOneBot 时直接启用其 OneBot HTTP 服务端，在助手中连接本机地址和 Token。新建服务端时可填 host=`127.0.0.1`、port=`3000`。随后加载好友、选一个私聊、读取历史、导出 JSON 或预览存档。NapCat WebUI 通常在 6099；WebUI 登录与启用 HTTP 服务是两个步骤。内嵌说明和 [官方设置文档](https://napneko.github.io/config/basic) 给出详细步骤。

为保留已有登录组件，`QQChatExporter/NapCat-QCE-Windows-x64` 的原始发行文件继续保留。“打开 QQ 连接器”仅启动其中的 `launcher-user.bat`；新版导出流程使用助手自身的 OneBot HTTP 读取界面。需要本机 QQNT 与连接器版本兼容。升级不会覆盖已有连接器文件及配置。

- QQChatExporter：[项目](https://github.com/shuakami/qq-chat-exporter)、[v6.3.0](https://github.com/shuakami/qq-chat-exporter/releases/tag/v6.3.0)。GPL-3.0 全文在 `licenses/QQChatExporter-LICENSE.txt`，对应源码在 `source/QQChatExporter-source-v6.3.0.zip`。
- NapCat v4.18.19：Copyright © 2024 Mlikiowa。[项目](https://github.com/NapNeko/NapCatQQ)、[发行页](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.19)。Limited Redistribution License 限制非商业使用并要求保留许可及来源；全文在 `licenses/NapCat-LICENSE.txt`，对应源码在 `source/NapCat-source-v4.18.19.zip`。该组件不是允许任意商业用途的开源许可。
- 原连接器包的文件来源和 SHA256 在本目录 `provenance.json`。第三方实现没有复制进主程序；其他依赖仍适用原目录中的许可。

连接器只在用户点击按钮时启动。测试只使用合成 SQLite / Protobuf 与本机模拟接口，没有登录 QQ 或读取私人记录。在线读取范围取决于连接器可返回的本机历史，不保证云端或其他设备记录完整。

## 微信

已按要求改用 [sunhanaix/pc_wechat_exp](https://github.com/sunhanaix/pc_wechat_exp)，附带未修改的官方 `wechat_exp_2.10.20260928.exe`、同版本源码 ZIP、上游说明和 SHA256 来源清单，位于 `WeChatEXP`。在新版导入中心可直接打开 WeChatEXP 仪表盘，也可使用一键流程：用户分别主动选择备份、文字导出目录（无默认地址）、选择账号后备份、选择私聊后分页提取文字、确认身份并保存。助手调用本机 backup/scan、backup/run、contacts 和 messages API，不使用上游 export/chat 的默认导出目录。上游工具执行备份；助手不导入图片或表情包。

消息读取运行独立的官方 serve 实例，隔离配置仅含本次选择的备份目录和已核验账号，避免上游备份切换目录但未切换账号状态的问题。不会复制或改动原工具密钥、登录配置。备份文件只写入用户选择的备份目录，文字 JSON 只写入用户选择的导出目录；助手内部 API 运行时不作为导出路径。

已核对可执行文件 SHA256 与 GitHub 发行资产 digest 相同：`000bc70437123d68c953d35d0f95dc0c12c2a5757686bd8f0f04717a9663bb6b`。上游该版本没有声明许可证；这是按用户指定下载到个人本机使用的原始工具，助手的 MIT 许可不覆盖它，也不能据此推定商业分发权。保留作者和来源，后续分发须按上游授权处理。

[WeFlow](https://github.com/hicccc77/WeFlow) 未随包分发，现为兼容入口：微信导出页中的“已有 WeFlow”可连接其本地 API，原有导出文件仍可导入。主程序不提取微信密钥。

API Key 和联系人档案仍存储在助手自己的用户数据目录，路径见主程序 README。
