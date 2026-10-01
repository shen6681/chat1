# chat1 v2.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, one fresh whole-branch review at the end.

**Goal:** 原生新UI中实现强制自选目录的微信一键流程和独立100条好感度分析。

**Architecture:** LocalService保留单一真实后端。WechatClient封装上游loopback/SSE，WechatWorkflow处理用户选择与任务状态；AffinityStore持久化100条批次和子分析，affinity_runner只调DeepSeek。WebView2壳使用相同受鉴权HTTP后端，避免另建不兼容档案模型。

**Tech Stack:** Python/SQLite/urllib、React/TypeScript/Vite、pywebview5.1/pythonnet3.0.5、现有PyInstaller。

**Spec:** docs/superpowers/specs/2026-10-02-wechat-affinity.md

## Global Constraints

- 初始好感度50，范围0–100；用户主动选择、每100条。
- 备份和导出目录初始为空，必须分别由用户选择，无默认目录。
- 保留API/账号/原文；测试仅合成；不破坏coauthor分支。

## Review Focus

- 导出未知发言人/群聊/空文字不得错误归类或分析。
- 同账号跨批次相同local_id不同分片，不丢掉不同消息。
- SSE结束无done/错误/重定向不当成成功，不写默认路径。
- 重启/重叠范围/失效租约不重复计分，失败保存不标记100条已完成。
- 长消息/弱或伪造证据保持完整记录，收费子分析恢复不重复。

### Task 1: 微信API工作流
Files: chat_assistant/wechat_client.py, wechat_workflow.py; tests/test_wechat_api.py; web_backend.py/web_server.py.
- [x] 写先失败的合成本机SSE测试：强制目录、账号、群聊、媒体跳过、未知发言人、分页去重、失败不存档。
- [x] 实现客户端与任务：scan/start backup/choose contact/export preview，目录token，job轮询；API测试GREEN。

### Task 2: 独立好感度
Files: affinity.py, affinity_runner.py; tests/test_affinity.py; web_backend.py.
- [x] RED：99不请求、100一次、初始/边界/置信度/有效证据、200条第二批失败与重启不重算第一批、重叠范围、事务失败。
- [x] 实现存储schema、stage、严格结果验证和DeepSeek预算分组，复用现有互斥；GREEN。

### Task 3: 原生壳和React接入
Files: desktop_app.py（参考coauthor）、main.py/spec/requirements；WechatImport.tsx/AffinityPanel.tsx/ImportHub/Header/Inspector/AppContext/types/settings/docs.
- [x] 新UI直达仪表盘、一键向导两目录必选、账号/联系人/身份选择；不再微信打开旧窗口。
- [x] 好感度独立面板/用户按钮/100条进度/依据与断点，主头部无大搜索框、菜单仍可退出。
- [x] Native目录选择+安全导航+关闭保存；保持--browser/--no-browser可测；稳定背景与尺寸。
- [x] 合成浏览器行为和视觉、Python/前端完整测试（141项全套139隐藏+2实际屏幕补测，另3项Node）。

### Task 4: 交付
- [x] 一次新上下文复核及必要RED→GREEN修复。
- [x] EXE构建、全新目录ZIP解压/启动与功能验证，原14配置/2原文表hash保留比对通过。
- [ ] 本地与干净便携ZIP已更新核验；最后提交发布、源码同步和GitHub附件digest待完成。
- [ ] 全部完成后删除automation chat1，向用户给出明确交付版本与限制。
