# 本机第三方工具

GitHub 源码分支不跟踪 `tools/`、第三方源码副本或工具压缩包。本机安装的文件会留在 `tools/`，切换同一工作目录的 Git 分支不会删除它们。新克隆仓库后需要自行安装。

## 微信 WeChatEXP

从 [pc_wechat_exp v2.10.20260928](https://github.com/sunhanaix/pc_wechat_exp/releases/tag/v2.10.20260928) 获取 Windows 程序，放在：

```text
tools/WeChatEXP/wechat_exp_2.10.20260928.exe
```

本机已核对的该版本 EXE SHA256：`000bc70437123d68c953d35d0f95dc0c12c2a5757686bd8f0f04717a9663bb6b`。该上游版本未声明许可证；本项目的 MIT 许可不适用于此工具。

## QQNT_Export

从 [QQNT_Export v3.3.0](https://github.com/Tealina28/QQNT_Export/releases/tag/v3.3.0) 获取 Windows 程序，放在：

```text
tools/QQNT_Export/QQNT_Export_3.3.0.exe
```

本机已核对的该版本 EXE SHA256：`27e73c827c9ce7df4045c33d17d00d1460c6d1cc2a1a2dab121bc710a781acbd`。该工具用于已经解密的 QQNT 数据库；许可与源码请查看上游发行页。

## QQ 在线读取

已有 NapCat 或 LLOneBot 时，在本机启用 OneBot HTTP 服务即可。若使用 QQChatExporter 自带连接器，程序会查找 `tools/QQChatExporter/NapCat-QCE-Windows-x64/launcher-user.bat`。连接器是可选项，来源和安装方式见 [QQChatExporter](https://github.com/shuakami/qq-chat-exporter/releases/tag/v6.3.0)。

PowerShell 校验示例：

```powershell
Get-FileHash -Algorithm SHA256 .\tools\WeChatEXP\wechat_exp_2.10.20260928.exe
Get-FileHash -Algorithm SHA256 .\tools\QQNT_Export\QQNT_Export_3.3.0.exe
```
