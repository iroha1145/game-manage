# 云端外部前提验证

核查日：2026-10-12。Task 1 探针已实现；本地真实 QQ token、gateway、WebSocket READY、心跳、指定沙箱群事件接收及被动回复 API 已通过。**生产环境、断线恢复、云出口游戏授权与自然续期尚未测，V01/V03/V04/V05 尚未完整通过**。这份文档仅记录脱敏证据，不包含配置、账号、群 OpenID、密钥或原始响应。

## 当前证据

| 项目 | 状态 | 证据与边界 |
| --- | --- | --- |
| 两个 CLI 的帮助、默认离线运行 | 通过 | 默认不读取凭据，不联网，不建数据库 |
| 本地 QQ 配置 | 通过（离线测试） | 交互隐藏输入；Windows DPAPI；Linux AES-GCM 独立密钥；当前用户文件权限；默认拒绝覆盖 |
| 官方 Python SDK | 源码、导入及本地基础实网通过 | `qqbot-agent-sdk==1.2.2`，来自 `tencent-connect/qqbot-agent-sdk`；独立工作树虚拟环境基础群收发通过；已作为可选 `qq` 依赖锁定，云端及正式发布仍待验证 |
| access_token、网关、WebSocket READY | 本地真实通过 | 用户授权使用本地加密 QQ 配置；当前 `api.bot.qq.com` 鉴权、网关、READY 成功；不能当作服务器云出口通过 |
| 心跳、测试群消息 | 本地真实通过 | 60 秒只接收发现窗口返回心跳及群事件，正常退出；随后在明确选定同一群进行回复测试 |
| 单一测试群 | 基础实网通过，平台沙箱归类未独立核实 | 2026-10-14用户澄清：此前直接将机器人拉入测试群，没有额外在开放平台配置沙箱群。该群实际收发成功；旧问答“已配置沙箱群”不能作为后台配置证据，亦不证明正式发布或任意群可用 |
| 指定群被动回复 | 本地真实通过 | 用户发送 @ `/probe`，探针仅向指定群回复固定测试文字；接收与发送 API 均成功，60 秒窗口正常退出，无游戏数据发送 |
| 产品文字链路 | 本地真实帮助指令通过 | 独立回环身份服务与产品机器人运行 60 秒，用户确认收到 `@机器人 帮助` 回复；持久化发送状态成功，退出码 0，临时 API 端口已关闭。未包含游戏绑定、私人查询或图片 |
| 服务器 QQ HTTP 出口 | 真实通过 | 2026-10-12 隔离试运行期间，官方 token 和 gateway 请求均 HTTP 200；AppSecret 仅在内存使用、未落地、未发消息；Linux WebSocket 与群收发仍待验证 |
| 重连、真实重复事件、自然 token 续期 | 未测 | 重连仅在实际观察第二次 READY/RESUMED 时记录；离线去重测试不替代平台验证 |
| 鸣潮、异环 | 未测 | 独立官服测试会话的查询与手动续期探针已备好；短信/人机验证、自然失效未测 |
| 鹰角寻访 | 未测 | 验证绑定身份与一个特许寻访池首页；不回填历史，不宣称完整记录；通行证失效须重新人工登录 |
| 森空岛档案 | 未测 | 独立 cred，核对绑定角色/账号后查档案；获取签名 token 不等于 cred 自动续期 |
| 鹰角与森空岛身份匹配 | 未测 | 独立保存、独立探测；不凭昵称合并，不由单侧查询成功推断另一侧通过 |

## QQ SDK 与现行接口差异

现行[官方鉴权文档](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html)列出 `https://api.bot.qq.com/app/getAppAccessToken` 和统一 API 域名；[事件文档](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html)列出 WebSocket 的 Identify、Resume、Hello 和 Heartbeat ACK。

[旧官方 botpy 源码](https://github.com/tencent-connect/botpy/blob/master/botpy/http.py)仍默认 `api.sgroup.qq.com` / `sandbox.api.sgroup.qq.com`，Token 源码仍使用 `bots.qq.com`。本轮 PyPI 元数据返回其版本 `1.2.1`。不照搬旧默认值。

[新版官方组织 SDK](https://github.com/tencent-connect/qqbot-agent-sdk)、[1.2.2 源码版本](https://github.com/tencent-connect/qqbot-agent-sdk/blob/main/pyproject.toml)支持独立 WebSocket 回调、会话恢复和 API 客户端。实际安装的 1.2.2 包也仍默认旧 API 与 token 域名。探针只在 live receive/discover 内导入 SDK，将其 API 客户端的 `API_BASE`、`TOKEN_URL` 显式改为当前官网地址；不更写 SDK 文件，不重写传输层。离线导入与接口结构可用不代表实际平台权限或兼容性已通过。

`environment=sandbox` 只是本地记录，**不切换 API 域名，也不替代平台后台的真实沙箱配置**；不推测新的 sandbox 域名，不在失败后回退旧域名。产品当前锁定同一 SDK 和端点适配；探针实测不替代产品绑定、查询、云端出口与正式发布验收。

## 本地安全配置与运行

在工作树根目录用现有游戏环境执行，无需安装 SDK 即可配置/验证：

```powershell
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --configure
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --validate-config
```

仅在用户终端隐藏输入 AppID、AppSecret，不在聊天或命令行参数中填写秘密。默认存储于 `.private-cloud-probes/qq.credentials.json`，目录已加入 `.gitignore`；所有 `*.credentials.json` 和旁边 `.key` 原本也被忽略。Windows 使用当前用户 DPAPI 和仅当前 SID 的 DACL；POSIX 使用 0700 目录/0600 文件，复用现有 CredentialStore AES-GCM。不能把 Windows 密文直接迁移到 Linux。创建失败会停止，不降级为明文。覆盖须显式 `--replace`；自定义 `--config` 的直接父目录必须名为 `.private-cloud-probes`，文件须为 `.credentials.json` 后缀，不修改其他任意父目录权限；路径链上的 symlink/junction/reparse point 会被拒绝。

可选 SDK 仅装在独立工作树环境，不修改主环境。开发时已在本工作树 `.venv` 正常安装 1.2.2 及其运行依赖，并完成 `pip check`、导入和本地真实握手；新机器使用：

```powershell
python -m venv .venv
& '.venv/Scripts/python.exe' -m pip install httpx pycryptodome 'qqbot-agent-sdk==1.2.2'
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live token
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live gateway
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live handshake --duration 20
```

本地凭据输入、SDK 导入、默认运行不代表 QQ 鉴权通过。`handshake` 只测传输，忽略群内容、不发消息，也不要求配置测试群。要继续消息测试，先在后台核实个人主体权限、出网 IP 白名单和**仅用户选定的测试沙箱群**。因为数字 QQ 群号不是 group_openid，可显式使用只读发现模式，再指定其输出的 OpenID 收发：

```powershell
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live discover --duration 60
# 用户在已配置的沙箱测试群 @机器人发送 /probe；只输出 group_openid，不发消息。
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live receive --group-openid '<已选测试群OpenID>' --duration 60
# 只在用户确认选择的测试群执行；仅被动回复 @机器人 /probe，不发送网址或私人信息。
& '.venv/Scripts/python.exe' scripts/cloud/probe_qq.py --live receive --group-openid '<已选测试群OpenID>' --reply-test --duration 60
```

发现输出只供用户本地选择测试群，避免保存到公共报告；不打印成员 OpenID、消息内容、token、请求头或 SDK 原始日志。普通 receive 默认不发消息；`--reply-test` 只能配合 receive，按群 + 消息 ID 去重且每条最多发送一次固定文本，失败不盲重发。运行时限 5–300 秒；收到 READY 后记录握手，观察 ACK 后记录心跳，未观察的环节留未测。初次进入也可能受平台会话限制；不要连续反复重跑。

首轮 discovery 曾只记录 token/gateway 后等待 60 秒，最终 `NotObserved`；定位为本地 SDK 用 `--no-deps` 安装后缺少延迟加载的 `aiohttp`，初始 WebSocket 线程导入异常被 SDK 原始日志路径吞掉。此结果不是平台权限拒绝。补齐 SDK 元数据中的 `aiohttp`、`httpx`、`cryptography` 后，本地 20 秒无消息握手成功。探针现在在发网络请求前检查这些运行依赖，失败仅输出固定依赖步骤和异常类型，不输出路径、秘密或异常正文。

## 游戏探针边界

```powershell
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_games.py --help
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_games.py --provider wuwa --configure
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_games.py --provider wuwa --validate-config
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_games.py --provider wuwa --live query
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/probe_games.py --provider nte --live renew
```

provider 为 `wuwa`、`nte`、`endfield`、`skland`。配置仅隐藏导入**本人已通过人工授权获得的独立测试会话**，保存在 `.private-cloud-probes/games.credentials.json` 的独立 provider 中；新增 provider 保留其他会话，覆盖同 provider 要 `--replace`。不自动读取主 config、主凭据、数据库或浏览器存储。鸣潮导入当前 APP 登录流程取得的 ios token/roleBox 会话；旧 h5 会话不由此配置入口宣称已验证。

query 为有界私有读请求，不执行签到、鸣潮 refreshData、抽卡历史回填或数据库写入。Skland 查询必需临时签名 token，仍将 cred 自然续期列为未测。`--live renew` 只支持鸣潮 roleBox 票据与异环 refresh token，成功后原子保存更新再查询；接口失败保留原文件。异环 token 可能轮换，不能共享本地正式会话来测试。鹰角通行证没有现成续期，森空岛 cred 自动续期也未实现，此标志不会把它们伪造为通过。

导入已有会话无法验证“服务器登录成功”，所以每次 probe 的 login 与 natural_expiry 仍为未测；renew 成功仅证明本次显式续期，不证明自然过期恢复。要测失效，使用独立测试文件的过期会话并观察错误路径，勿篡改现有有效授权；不会故意提交大量伪造 token。输出仅包含步骤、通过/失败/未测、耗时和异常类型，禁止记录异常正文、原始游戏数据和完整 URL。

## 服务器实测由主执行者完成

本任务未访问或修改服务器，未读取真实游戏凭据；真实 QQ 仅经用户授权使用本地加密配置进行了上述验证。主执行者需检查资源、端口与现有 LOLhelper 状态，创建独立目录/虚拟环境/数据目录，以独立配置启动人工游戏授权入口。监听仅 `127.0.0.1`，使用 SSH 本地转发；不得公开现有无网站用户鉴权的完整看板，也不得停止 LOLhelper。验证码、人机验证、实名由用户在本人页面操作；探针 CLI 不代办登录。

随后从**真实服务器云出口**分别测四条独立授权的登录、查询、失效，记录失败类型与人工恢复；需完整测试寻访池/分页时另补证据，单页通过不得当成完整功能通过。自然过期尚未发生时保留续期待测。QQ 与游戏可以分别失败，不相互推断成功。V01/V03 未通过前暂停 QQ 产品验收；V04/V05 对应游戏未通过前不能宣称可上线。

结束后记录临时目录是否保留、凭据是否撤销/删除、AES-GCM key 是否一并处置；工作树 `.venv` 已补齐独立运行依赖，主执行者为用户准备的真实 QQ 加密配置保留在忽略目录中。共享报告不得包含 discovery 的群标识。Windows/Linux 环境和网络不同，不能把本地测试结果写成云端通过。
