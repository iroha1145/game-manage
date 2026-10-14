# 云端管理员 B 站公共源授权

管理员在「账号与授权」直接输入本人 B 站登录后的 **SESSDATA 值**，点击「验证并加密保存」。只需要这一项，不需要整段 Cookie、bili_jct 或 buvid3；不要把凭据发送到聊天。现有 provider 可仅使用 SESSDATA 校验登录状态，并从 nav 响应补齐账号 UID。本地合成协议测试可证明这一输入契约，真实授权是否可用仍需本人操作及后续采集验证。

扫码保留为可选方式，需点击「扫码授权 B 站」后本人扫码并确认。该授权只供云端采集已配置的官方公共动态，公共采集结果供网站成员读取。登录不能保证解除 HTTP 412 或补齐历史收录；采集成功及完整性需另做有限验证。

## 边界

- 仅新增 `/api/admin/bilibili-source/login` 下的 status、sessions 创建/状态/取消、qr/poll、cookie、commit；sessions mode 仅允许 cookie/qr。cookie 提交只接收必填 sessdata（SecretStr，最多4096字符，拒绝其他字段），复用 normalize_cookie_input 和 provider 验证。云端不安装本地密码、短信或采集管理路由。
- 网站会话、CSRF、Host/Origin 与请求体上限保持。授权会话绑定管理员 user_id 和具体网站 session_id，另一网站会话或管理员无法继续操作；上游返回保存前及数据库写入事务内重新检查会话、管理员权限、禁用/撤销/过期状态。参数验证错误只返回 invalid_request，不回显输入。
- SESSDATA 输入框使用 password/autocomplete=off，默认显示但不自动提交。提交前立即清空；切换方式、取消、网站会话失效及组件卸载也清空。明文仅随 HTTPS POST 请求体提交，不进入 URL、日志、本地存储或状态响应；输入不回填保存的凭据。验证失败保留旧授权，可检查会话状态或重新输入。
- 复用现有 QR/provider 的三秒轮询间隔、180 秒二维码上限、候选凭据有效期、取消、繁忙/失败保留旧账号策略。扫码确认后验证并自动保存；commit 仅用于候选保存受阻时重试。前端网络失败停止自动轮询，可检查已有会话状态。
- 凭据保存在现有 identity.db 的 grants，provider 为 `bilibili-public-source`，owner 为授权管理员，不创建 accounts/roles。与个人游戏授权列表、个人调度、账号撤销流程隔离。
- 使用 CredentialStore.seal_grant/load_grant 的 AES-GCM 和 owner/grant/version AAD，复用运行配置指定的外置 cloud_credentials_key_path。部署入口已有 key_must_be_external 与 Linux owner-only 权限校验；不调用普通文件 load/save，不读取本机 Cookie，不新增凭据或同目录 key 文件，不返回/记录 token。
- 全站最多保留一个生效公共源授权：新授权保存事务成功后撤销之前所有该 provider 的 active grant，失败保留原授权。读取仅选取未禁用且仍为管理员的 active owner；撤销/降权后不回退到旧授权。已完成授权独立于浏览器会话，正常退出网站不会删除已保存公共源授权。
- 源账号状态仅管理员可见，普通成员仍只能读取公共资讯/日历快照。

## 备份与验证

没有 schema、sidefile 或 manifest 格式变化。现有备份包含 identity.db，并校验所有 active grant 的密文可读性；外置密钥继续不随数据备份复制。定向测试覆盖新增公共 grant 备份、新目录恢复与可读性，backup.py/restore.py 无需增加白名单。

本地验证为合成 SESSDATA/QR/provider、真实网站身份边界、真实 AES-GCM/SQLite 与备份恢复；不代表真实授权、真实 B 站登录、云端解密或 HTTP 412 已解除。SESSDATA 新增验证全部拒绝真实 httpx 上游发送；既有 provider 协议测试使用 respx mock。调度隔离测试关闭公共轮询，只核个人 scope。早期 QR 版本的该调度测试未关闭公共队列，可能发起公共 HTTP 请求，不能作为严格无网络证据。

发布时按现有独立新看板发布/回退步骤执行，保留数据、外置密钥和会话。上线后管理员本人输入 SESSDATA（或选择扫码）；授权完成后由获准运维进行有限公共采集并核对来源状态、历史完整性和旧记录保留。QQ 仍限沙箱，LOLhelper 不在修改/重启范围。

## 复用本地已保存授权的受信运维迁移

`scripts/cloud/bilibili_migrate.py` 默认只读核验本地看板是否已保存可解密 SESSDATA。仅读取配置指定数据库旁的 `*.bilibili.credentials.json`，使用既有 CredentialStore（Windows 当前用户 DPAPI）解密；不读取浏览器 Cookie 或其他凭据。真实执行需审查后明确提供 `--execute --remote-python <当前独立release的Python> --remote-config <云端配置>`，不得把 SESSDATA 放入参数或聊天。

迁移只在进程内提取 SESSDATA，经既有固定主机、StrictHostKeyChecking=yes 的 SSH stdin 传输。远端以 `sudo -n -u game-manage-trial`（与 API 相同身份）运行，避免 SQLite WAL/journal 产生 root owner 差异。`bilibili_migrate_remote.py` 代码经 `-c` 传递，编码中仅包含代码；明文不进入参数、环境变量、日志、临时文件或结果。远端禁用日志/core dump；本地不转发 stderr，只接受安全结果/错误代码。超时或返回无法核验时报告 `remote_result_unconfirmed`，不自动重试或宣称未保存，须由运维核对。

受信运维权限与网站权限分开：不伪造网站用户会话，不创建 sessions。远端只选取唯一未禁用管理员，记录现有公共源授权版本清单，仅调用既有 provider 的一次 nav 验证。成功后写事务内重新检查管理员和版本，使用既有外置 key/AAD 保存 `bilibili` 及安全 meta，同时原子撤销旧公共授权；失败或并发变化保留旧授权。多个管理员时拒绝猜测归属。不会重置源退避、触发全量回补或采集，也无需重启 API；之后是否有限采集由 root 决定。

2026-10-14：root 审查及放行后，已使用提交 `4fafd6da829fcd46729148bd1b8d469f4f4e69a4` 的脚本执行唯一一次真实迁移。受信服务用户运行当前 `3a9e476` release Python，安全结果为 `status=saved, configured=true`（exit 0）：nav 验证及加密 grant 原子保存成功。未重启服务、触发动态采集或修改退避；未输出或落地明文。该成功只证明登录验证与保存，不证明公共动态 HTTP 412 已解除或收录完整。

同日，经 root 审查放行 ignored 运维脚本 `.superpowers/sdd/2026-10-14-bilibili-list-probe.py`，以相同服务身份及受信 SSH 执行唯一一次鸣潮官方 UID 的首屏列表诊断。使用 live 配置及已保存云端 grant，调用 `user.get_dynamics_new(offset='')`（单次逻辑列表、35 秒请求上限、SDK WBI 重试次数限制为 1、外层 SSH 总超时 60 秒），禁用 SDK/raw 日志，stderr 不透传，stdout 仅接受标量字段白名单。

真实安全结果：`success=true, items_count=13, has_more=true`（exit 0）。本次带授权的鸣潮首屏列表访问成功，没有返回 HTTP 412；不代表所有来源、后续分页或以后请求均成功。未调用 `page()` 或读取正文，不回补、不持久化列表、不改 next_retry/cache、不重试，不手工尝试其他接口或来源。由于 `has_more=true`，尚不能确认历史/正文/资讯收录完整，也不能将既有公共快照标为已更新；后续采集需另按授权范围验证。

## 2026-10-14 云端发布

已发布提交 `57422d3879c8ae41a93466438ee8be50b3ea3ff8` 的独立后端 wheel 和 cloud 前端。锁内 52 项运行依赖哈希核验、54 个已安装包兼容检查通过；授权模块等安装代码与该提交源码字节一致。只改前端产物路径及 API unit 的独立 release 引用，原配置、数据、外置密钥、会话、三公共 UID、自启 drop-in 和备份 timer 保留。只有 API 一次停启，PID 为 `4095838`、自动重启计数 0；QQ、代理、Caddy、LOLhelper 两服务 PID 均保持。

启动同秒 07:53:01（UTC+8）首次 HTTPS 健康检查返回 502；07:53:45 重验首请求返回正常，无须请求重试。观测就绪上界为 44 秒，实际完成时刻未测，不将 active 状态直接当作健康。正常可信 TLS 下首页及新 JS/CSS 的 SHA-256 与最终本地产物一致：index 为 `07a746b5fc70c89c054b94e8cfdcae21173c3ce2f84104a74abf277b6c9a85de`。匿名请求管理员状态接口 401；本地授权路径未公开（404），内部接口公网 404，不可信 Origin 403；旧服务根路径基线 302/404/302 保持。

未触发回退。原后端 `6b3d77c`、前端 `0eff73e` 及原配置/unit 保留为回退材料。本次未发起二维码、代扫码、手动触发额外上游采集或输出凭据；真实扫码授权、云端授权可读性及 HTTP 412 是否解除仍待管理员本人完成操作后再验证。线上未使用真实管理员/成员会话测试权限，相关角色和会话边界的既有合成测试不能外推为真人验收。

## 管理员公共动态采集控制（本地候选，未发布）

「账号与授权」现有 B 站卡增加按游戏「采集新动态」「回补60天」及状态。新接口为管理员 `GET /api/admin/bilibili-source/status`、`POST /api/admin/bilibili-source/{game}/refresh`；POST 仅接受严格布尔字段 `backfill`，拒绝其他字段。沿用网站会话、CSRF、Host/Origin 和请求体上限，普通成员403、未配置游戏404；不安装本地 sources/audit/refresh 路由，前端只允许精确云端路径。

手动任务复用公共调度 `('public', game)` 队列及既有 provider/global 并发限制。同游戏公共任务已排队或运行时返回409 `source_busy`，回补不会静默升级或丢失后却声称完成；下一可请求时间未到时返回409 `source_backoff`，排队后执行也重新检查退避。手动只调用 B 站采集，不额外请求原生公告来源，也不推迟其既有定时到期时间。公共队列任务登记至 B 站服务，授权更新也能识别采集繁忙。

`backfill=true` 明确覆盖60天；新动态保留既有规则：历史不完整或规则版本更新会自动回补配置的历史窗口，完整时按最近成功时间采集增量。历史完成标记及最近成功时间保留既有事实；失败不清除旧记录或把不完整历史标成完成。

状态仅返回选定的游戏/UID、排队/运行、页数、连续失败、历史完成、最近尝试/成功及收录计数等标量；HTTP状态/业务码另按整数范围白名单提供。不会返回凭据、原始载荷、诊断字典、筛选理由或任意上游错误文本。成功后30秒正常冷却与失败退避分别显示，进行中及冷却/退避按钮禁用并说明原因。

前端仅真人按钮POST。状态GET每轮最多120次且不超过10分钟（空闲30秒、公共任务进行中2.5秒）；网络失败停止自动读取，可手动检查。离开组件清理计时器，网站会话失效清空来源状态并丢弃晚到响应。通过任务前后最近成功时间判断快速完成，成功提示刷新游戏资讯/日历以读取公共结果，失败保留旧计数。

本地验证：新增5项真实网站身份/公共调度/B站服务集成测试及相关授权/调度回归共57项通过（2个既有依赖警告）；前端按钮、CSRF、精确allowlist、快速完成/失败、有限刷新、卸载及会话失效等相关18项通过。新增采集测试只使用合成页回调，fixture拒绝真实httpx上游发送，不使用真实账号、动态或凭据。cloud构建及HTML marker通过，保留既有主包超过500kB提示；未进行真人视觉、真实上游、SSH、部署、push或merge。

候选dist SHA256：index `9c0f35c61d60b53be221613c9dbf2adfe4aabe51157f9040efa01979069d07b0`；`assets/index-CPSsMiYW.js` `b3cf12d01436f35f74e349f2b8c4f7d13af0d06044d43a215273157a6c5fad4a`；`assets/index-ZWOUJTeq.css` `2822f29d69a7611a7ad20819d92760e7ba83bf176e6e70e5cad05d9dad46884e`。该候选不改变文中既有线上发布和迁移结果。
