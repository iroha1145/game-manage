# game-manage 云端服务与 QQ 多设备看板实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. 用户已授权使用 GPT-6.1-sol high 子代理实现，主代理进行必要审查验收；生产切换仍需另行确认。

**Goal:** 为 5–20 人官服小群提供统一游戏授权、本人数据查询、QQ 官方机器人和外网多设备看板。

**Architecture:** game-manage 为唯一业务与授权中心，网页和 QQ 共用查询服务。单机 SQLite、唯一后台调度器、独立 QQ 接入进程，沿用 Caddy 与 systemd；游戏账号隔离覆盖所有私人存储和缓存。

**Tech Stack:** Python >=3.11、FastAPI、SQLite、Vue 3、现有 AES-GCM 凭据实现、Caddy、systemd；构建沿用 Node.js >=22.12 与锁文件。QQ Python SDK 优先通过任务 1 验证后锁定，图片优先使用 Pillow，网站密码使用 Argon2id。新依赖只在正式执行对应任务时引入。

**Spec:** [已确认的需求与设计](../specs/2026-10-12-cloud-qq-dashboard-design.md)，用户于 2026-10-12 确认其内容。

**状态（2026-10-12）:** 任务 2–11 的代码及任务 12 的部署、备份、恢复工具已在隔离分支实现；本地最终回归为后端 1343 通过、6 跳过，前端 336 通过。任务 1 的本机 QQ 探针及产品帮助指令真实收发通过，云端游戏授权、自然续期与生产验收仍待验证。下列原始检查项包含实现和真实运行条件，不能因代码完成而整批勾选；证据与差异见[实现验收记录](../../cloud-implementation-acceptance.md)。

## 1. 全局约束

- 范围：5–20 人、国服官服优先；每人每游戏一个默认账号，底层可表示多授权、多角色。
- 统一授权：不要求逐设备登录游戏社区，不在 QQ 程序保存第二份游戏凭据。
- 权限：本人数据；服务端校验对象归属；群内只返回本人主动查询摘要。
- 首期 QQ：@机器人查询、文字优先；图片随后；无需 @、主动推送、Markdown 和按钮不作为上线前置。
- 终末地：鹰角寻访与森空岛档案保持独立授权和角色身份。
- 数据：缺失为 null，失败保留旧快照；不补造日期、抽卡历史或保底。
- 运行：现有 Ubuntu 24.04、2 核约 2GB 服务器，Caddy、systemd、单机 SQLite；不引入 Docker、Redis、Kubernetes。
- 公共资讯统一采集，私人概览刷新间隔 10–15 分钟；默认采用 15 分钟，公共资讯 10 分钟，可配置。
- 本地 Windows 单用户使用继续支持；云端模式通过独立入口显式启动，不把原启动脚本改成公网服务。
- 云端不启动 LCU 扫描、旧单用户推送或游戏签到写接口；LOLhelper 保持独立。现有本地能力不删除。
- 真实验证码、人机验证、实名信息由用户处理；凭据不得进入日志、仓库或测试报告。
- 现有两份异环库存未跟踪文档不纳入本计划的提交。

## 2. 执行方式与阶段门槛

建议保留一份总计划，内部按三个可验收工作包串行交付：中央服务、网页入口、QQ 入口与上线。它们共享账号与查询契约，不宜分别设计身份系统。每个任务独立测试与提交，不能把整份计划作为一个大提交。

| 阶段 | 任务 | 放行条件 |
| --- | --- | --- |
| 外部验证 | 1 | QQ 测试群收发、SDK、云端游戏接口有真实证据；失败项明确阻塞范围 |
| 中央服务 | 2–7 | 身份、私人数据、令牌、刷新和迁移隔离测试通过 |
| 多设备网页 | 8 | 双用户、跨设备会话与社区授权复用通过 |
| QQ 查询 | 9–11 | QQ 与网页同源，绑定不可冒领，重投不重复执行；图片可降级 |
| 试运行与发布 | 12 | 恢复演练、资源测试与真实链路验收通过，另获生产切换授权 |

当前执行方式：用户指定的 GPT-6.1-sol high 子代理逐任务实现，主代理定向审查及最终集成验收。实现位于 `codex/cloud-qq-dashboard` 隔离工作树；不自动合并主分支或切换生产服务。

任务 1 的 QQ 条件未满足时，不默认改用非官方协议，也不把 QQ 首期视为完成。网站工作可以独立准备，但扩大为“网页先行交付”需说明范围变化。单款游戏实测失败只阻塞该游戏发布，不掩盖其余已验证结果。

## 3. 文件职责与共同接口

以下路径均相对仓库根目录 `C:/Zcode/game-manage`；新文件标为“新增”，其余为现有文件。执行前按当时 HEAD 核对，不依赖固定行号。

| 区域 | 文件与职责 |
| --- | --- |
| 云端入口 | 新增 `src/game_assistant/cloud_app.py`、`cloud_runtime.py`；组合安全的云端路由和单调度器 |
| 用户体系 | 新增 `src/game_assistant/identity/{models,store,service,routes,dependencies}.py` 与 `__init__.py`；用户、邀请、会话、恢复 |
| 账号运行上下文 | 新增 `src/game_assistant/accounts/{models,store,service,runtime,query,routes}.py` 与 `__init__.py`；授权归属、角色、独立适配器和统一查询 |
| 现有授权 | 修改 `auth/service.py`、`auth/store.py`、`auth/routes.py`、`auth/providers.py`；注入账号上下文，不共享可变 settings |
| 存储迁移 | 新增 `src/game_assistant/migrations/{__init__,cloud_v1,cli}.py`；增加范围字段、离线迁移与核对 |
| 主数据与任务 | 修改 `snapshots.py`、`scheduler.py`、`registry.py`；快照和任务增加完整账号范围 |
| 分散私人数据 | 修改 `wuwa_history.py`、`wuwa_gacha.py`、`nte_gacha.py`、`endfield_gacha.py`、`endfield_skland.py`、`endfield_blueprints.py` 及对应路由 |
| QQ 业务 | 新增 `src/game_assistant/qq/{__init__,models,bindings,internal_routes,client,transport,commands,rendering,runner}.py`；传输、身份关联、指令及卡片分离 |
| 前端 | 新增 `http-client.js`、`identity-api.js`、`accounts-api.js`、`components/SiteLogin.vue`、`AccountSettings.vue`、`QqBindingPanel.vue`；修改 `App.vue` 及现有 API 包装 |
| 运维 | 新增 `deploy/cloud/` 的服务模板、Caddy 片段；`scripts/cloud/` 的备份、恢复与验收工具；`docs/cloud-operations.md` |

新增契约类型集中定义，禁止后续任务各自发明第二套 user/account 标识：

| 类型或接口 | 定义与归属 |
| --- | --- |
| `Principal(user_id: str, is_admin: bool)` | `identity/models.py`；内部用户标识，不使用游戏 UID |
| `AccountScope(user_id: str, account_id: str, role_id: str)` | `accounts/models.py`；账号关联固定 game/channel/server；角色切换产生不同 scope |
| `GrantRef(grant_id: str, provider: str, version: int)` | `accounts/models.py`；授权与角色分别建模；终末地两份 grant 不合并 |
| `require_user(request: Request) -> Principal` | `identity/dependencies.py`；只接受有效网站会话 |
| `require_scope(principal: Principal, account_id: str, role_id: str) -> AccountScope` | `accounts/service.py`；不存在与非本人对象统一返回 404 |
| `QueryResult(payload: dict | list | None, fetched_at: str | None, state: str, complete: bool | None)` | `accounts/models.py`；时间为 ISO 8601；state 沿用现有失败语义 |
| `AccountQuery.read(scope: AccountScope, capability: str) -> QueryResult` | `accounts/query.py`；网页和机器人唯一读取入口 |
| `RefreshReceipt(job_id: str, state: str)` | `accounts/models.py`；state 为 queued/coalesced，业务失败另经查询状态返回 |
| `request_refresh(scope: AccountScope, capability: str) -> RefreshReceipt` | `accounts/query.py`；不直接阻塞请求等待上游 |
| `QqIdentity(app_id: str, scene: str, group_openid: str | None, sender_openid: str)` | `qq/models.py`；group/c2c 两种 scene，按完整元组唯一 |
| `InboundMessage(identity: QqIdentity, message_id: str, content: str, received_at: str, reply_deadline: str)` | `qq/models.py`；由已验证传输生成，网页不可构造 |

所有 POST/PUT/PATCH/DELETE 网站请求必须通过会话与 CSRF 校验；内部 QQ 接口使用独立服务鉴权，不接受网站 Cookie 替代。错误只返回稳定错误码和脱敏说明。

## 4. 重点审查条件

| 风险条件 | 期望行为 | 对应任务 |
| --- | --- | --- |
| A 的延迟请求在退出后以 B 登录时返回 | 浏览器丢弃旧响应，后台不写入新授权范围 | 4、6、8 |
| 猜测账号 ID、导出链接或共享图片缓存键 | 服务端拒绝跨用户访问，不泄露对象是否存在 | 3、5、11 |
| QQ 关联码被他人抢先使用、重投、跨群转发 | 未完成本人网页确认不建立关联，失效码不可复用 | 9 |
| 令牌续期与退出、换角色同时发生 | 授权版本校验生效，旧结果丢弃，不复活已撤销授权 | 4、6 |
| 迁移失败、磁盘满或缺少解密密钥 | 保留旧数据并停止切换，不回退到明文或空数据 | 2、7、12 |

## 5. 实现任务

### 任务 1：先验证外部前提

**文件：** 新增 `scripts/cloud/probe_qq.py`、`probe_games.py` 和 `docs/cloud-validation.md`；只记录脱敏结果。此任务在计划获准执行后才开展。

**输入：** 设计 V01/V03/V04/V05、用户创建的机器人与测试官服账号。
**输出：** 每款游戏、每个 QQ 环节分别为通过/失败/未测的证据表；锁定 SDK 名称与版本、接入方式和实际沙箱配置，更新本计划技术栈说明。

- [ ] 用户完成平台注册、实名、测试群准备；助手核对现行官网与账号实际权限，不索取群聊中的密钥。
- [ ] 优先验证官方 Python SDK 的 WebSocket、access_token、测试群收发、断线恢复。若 SDK 不支持现行接口，先报告差距并确定替代适配方式，不直接投入完整机器人开发。
- [ ] 在服务器独立测试目录运行最小探针，使用回环监听加 SSH 隧道提供人工授权页面，不暴露现有无用户鉴权的整个看板。运行前检查端口与资源，不停止 LOLhelper。
- [ ] 分别验证鸣潮、异环、鹰角寻访、森空岛档案的登录、查询、失效和续期；自然过期尚未观察到时保留“续期待测”，不能以模拟代替真实结论。
- [ ] 执行 `python scripts/cloud/probe_qq.py --help`、`python scripts/cloud/probe_games.py --help` 验证探针参数；真实运行输出仅含状态、耗时和错误类型，记录临时测试目录清理与凭据处置。
- [ ] 提交探针及脱敏验证文档；不提交任何配置、密钥、数据库。V01/V03 未通过则暂停 QQ 产品工作；对应游戏验证未通过则不得宣称该能力可上线。

### 任务 2：建立账号范围和版本化数据结构

**文件：** 新增 `identity/models.py`、`accounts/models.py`、`accounts/store.py`、`migrations/cloud_v1.py` 及包入口；新增 `tests/test_cloud_schema.py`。

**接口：** 定义第 3 节类型；`migrate_cloud_schema(connection: sqlite3.Connection) -> int` 返回 schema version；`AccountStore.resolve(principal: Principal, account_id: str, role_id: str) -> AccountScope`。

- [ ] 编写 `test_scope_rejects_other_owner`、`test_role_must_belong_to_account`、`test_migration_is_atomic`、`test_schema_upgrade_is_idempotent`：A/B 使用相同游戏 UID 也不串号；中途失败旧版本不变；重复升级不重复建数据。
- [ ] 执行 `python -m pytest tests/test_cloud_schema.py -q`，确认因缺少实现失败。
- [ ] 创建 users、sessions、invites、grants、accounts、roles、schema_migrations；外键关联和唯一约束在数据库实施，角色身份包含 game/channel/server/provider 范围。
- [ ] 重新运行该命令至通过，核查事务回滚；提交 `feat: add cloud identity and account schema`。

### 任务 3：网站登录和云端安全入口

**文件：** 新增 `identity/store.py`、`service.py`、`routes.py`、`dependencies.py`、`cloud_app.py`；修改 `api_security.py`、`config.py`、`pyproject.toml`、`uv.lock`；新增 `tests/test_identity.py`、`test_cloud_boundary.py`。

**接口：** `create_cloud_app(settings: Settings, start_scheduler: bool = True) -> FastAPI`；实现 `require_user`。新增 `/api/identity/register`、`login`、`logout`、`me`、`sessions`、`csrf`；会话撤销用 `DELETE /api/identity/sessions/{session_id}`；管理员生成邀请和恢复码通过本机 CLI，不开放无认证引导接口。

- [ ] 编写 `test_invite_is_single_use`、`test_login_rotates_session`、`test_csrf_required_for_write`、`test_cloud_routes_fail_closed`、`test_recovery_revokes_sessions`：无 Cookie 为 401，非本人对象为 404，缺 CSRF 为 403，内部服务路径不能使用普通 Cookie。
- [ ] 执行 `python -m pytest tests/test_identity.py tests/test_cloud_boundary.py -q`，先确认失败。
- [ ] 使用 Argon2id；会话令牌只存摘要；Cookie 使用 Secure、HttpOnly、SameSite=Lax。提议默认会话 14 天、邀请 48 小时、恢复码 15 分钟且单次使用；管理员重置后撤销全部会话，密码不回显。
- [ ] 登录初值按账号和来源 IP 分别限流为 10 次/10 分钟，可信代理仅回环；限制真实流式请求体大小，不只检查 Content-Length。云端路由采用显式允许列表，不复用当前整套本地 app 后简单补一个登录页。
- [ ] 用未分类路由拒绝注册/访问的测试证明新增私人接口不能绕过鉴权；允许匿名健康检查只返回简要状态。重跑测试并回归 `tests/test_api_security.py`，提交 `feat: add authenticated cloud entrypoint`。

### 任务 4：社区授权与适配器实例按账号隔离

**文件：** 新增 `accounts/service.py`、`runtime.py`；修改 `auth/service.py`、`store.py`、`routes.py`、`providers.py`、`registry.py`；新增 `tests/test_account_auth.py`、`test_account_runtime.py`。

**接口：** 实现 `require_scope`；`AccountRuntime.for_scope(scope: AccountScope) -> GameRegistry` 返回该账号专属适配器上下文；`CredentialStore.load_grant(user_id: str, grant_id: str) -> dict`、`save_grant(user_id: str, grant_id: str, credentials: dict, version: int) -> None`。保留本地旧接口适配入口，云端禁止自动载入 legacy config 私人凭据。

账号管理路由在 `accounts/routes.py` 创建：`GET /api/accounts`；社区登录完成后由后端根据已验证的角色响应创建账号，客户端不能自由提交他人的 UID 作为授权证明；`PUT /api/accounts/{account_id}/default-role` 仅选择属于该账号的角色；`DELETE /api/accounts/{account_id}/authorization` 撤销授权、递增版本并清理私人快照，历史账本仍归属原账号。登录流程挂载 `/api/accounts/auth/{provider}/sessions`、`sms`、`login`，每一步都要求同一网站用户拥有该登录会话。

- [ ] 测试 `test_login_session_is_owned`、`test_two_accounts_do_not_share_settings`、`test_logout_invalidates_inflight_renewal`、`test_missing_key_fails_closed`：A 的登录 session_id 不能被 B 使用，两个适配器 token 不交叉，缺密钥不重建覆盖。
- [ ] 执行 `python -m pytest tests/test_account_auth.py tests/test_account_runtime.py -q`，确认失败。
- [ ] 将 LoginService 的可变账号状态放入独立授权上下文，供应商解析复用；按 grant 加续期锁与版本号。新密文验证绑定 user_id/grant_id/version，密钥通过独立受控文件注入，禁止明文降级。
- [ ] 将所有社区登录请求关联网站用户；手机号、验证码和 captcha 不写日志。适配器不复用带他人凭据的全局 settings，HTTP 连接池释放有生命周期。
- [ ] 回归新增测试与 `tests/test_auth_service.py tests/test_auth_store.py tests/test_auth_routes.py tests/test_auth_integration.py`；提交 `feat: isolate game grants and adapter runtime`。

### 任务 5：全部私人数据和路由隔离

**文件：** 修改 `snapshots.py`、`wuwa_history.py`、`wuwa_gacha.py`、`nte_gacha.py`、`endfield_gacha.py`、`endfield_skland.py`、`endfield_blueprints.py`；对应 `wuwa_archive_routes.py`、`nte_gacha_routes.py`、`endfield_gacha_routes.py`、`endfield_skland_routes.py`、`endfield_blueprint_routes.py`、`adapters/wuthering_waves/routes.py`；新增 `tests/test_private_data_isolation.py`。

**接口：** 所有私人 store 的云端调用显式接收 `scope: AccountScope`；SnapshotStore 新增 `get_scoped(scope, capability)`、`save_scoped(scope, capability, payload_json, grant_version)`，旧签名仅服务本地模式。数据库键包含 user/account/role，去重键也必须包含该范围。

- [ ] 为每类私人存储建立 A/B 参数化测试：相同游戏、相同 UID、相同抽卡记录 ID 仍分别保存；跨账号查询、详情、删除、导入、导出均被拒绝；历史范围不会因退出误归属新角色。
- [ ] 编写 `test_skland_and_hypergryph_identity_stay_separate`：不同角色不得汇总；未开放字段维持 null，不能用另一授权补齐。新增 `test_cloud_disables_game_write_actions`：签到等超出首期范围的写操作不可达。
- [ ] 执行 `python -m pytest tests/test_private_data_isolation.py -q`，确认失败；逐存储添加范围字段、查询条件和外键，不只在返回结果中筛选。
- [ ] 从 `app.routes` 生成完整路由分类清单作为测试参数：私人查询/私人修改/公共只读/管理员来源配置/内部 QQ/禁用路由；有未分类项即失败。B站授权和回补仅管理员操作，普通用户只读公共资讯。
- [ ] 重跑新增测试及现有三个游戏账本、蓝图、森空岛、历史测试；提交 `feat: enforce ownership across private game data`。

### 任务 6：统一查询与账号级调度

**文件：** 新增 `accounts/query.py`、`routes.py`；修改 `scheduler.py`、`cloud_app.py`、`sources/bilibili_service.py` 的云端组合；新增 `tests/test_account_queries.py`、`test_account_scheduler.py`。

**接口：** 实现第 3 节 AccountQuery 与 RefreshReceipt；`GET /api/accounts/{account_id}/roles/{role_id}/snapshot/{capability}`；`POST .../refresh/{capability}` 返回 202。公共查询用 `/api/public/games/{game_id}/{news|events}`，不携带私人授权。

- [ ] 编写 `test_refresh_coalesces_same_scope`、`test_old_grant_result_discarded`、`test_failed_poll_keeps_snapshot`、`test_public_source_polled_once`、`test_second_scheduler_cannot_start`；公共内容不会按人数重复采集。
- [ ] 执行 `python -m pytest tests/test_account_queries.py tests/test_account_scheduler.py -q`，确认失败。
- [ ] 单个 cloud 进程、一个 API worker、一个调度器；进程锁避免第二实例重复调度。私人概览 900 秒，公共资讯 600 秒，增加错峰；初值上游总并发 4、每 provider 并发 1，可配置。
- [ ] 请求刷新只排队或合并，不让 QQ 等待上游。token 续期和结果写入检查 grant version；429、超时与上游异常退避，auth_expired 暂停私人轮询直至重新授权。
- [ ] 重跑新增测试和 `tests/test_poll_reliability.py tests/test_public_content.py tests/test_event_calendar.py`，检验未知截止日期、完整性标记；提交 `feat: unify account queries and polling`。

### 任务 7：旧数据离线迁移与恢复

**文件：** 新增 `migrations/cli.py`、`tests/test_cloud_migration.py`；更新 `migrations/cloud_v1.py`。

**接口：** `python -m game_assistant.migrations.cli preview --source <dir> --mapping <json> --output <report>`；`apply --source <dir> --mapping <json> --destination <new-dir>`。映射列出源数据集、目标用户、账号和角色；报告含迁移数、重复数、无法归属数及校验结果。

- [ ] 编写 `test_source_unchanged_after_migration`、`test_unknown_owner_requires_mapping`、`test_duplicate_import_is_idempotent`、`test_interrupted_migration_not_promoted`、`test_dpapi_not_copied_as_linux_grant`。
- [ ] 执行 `python -m pytest tests/test_cloud_migration.py -q`，确认失败。
- [ ] 默认只 preview；apply 写入新目录，以一致性备份为源，不直接复制运行中 SQLite 主文件。每个旧数据库都登记，未知私人表不能静默跳过；无法归属项目输出人工清单，不自动归给所有人。
- [ ] 对源与目标按账号/表核对数量及内容摘要；新实例启用前检查 schema 和密钥可读性，凭据迁移默认跳过并标记需重新授权。
- [ ] 重跑测试，通过后仅用用户数据的受控备份做预演，报告不含明细。提交 `feat: add auditable cloud data migration`。

### 任务 8：网页登录与多设备账号设置

**文件：** 新增前述前端文件及 `http-client.test.js`、`identity-api.test.js`、`components/SiteLogin.test.js`、`AccountSettings.test.js`；修改 `App.vue`、`api.js`、`auth-api.js`、`wuwa-api.js`、`nte-gacha-api.js`、`endfield-gacha-api.js`、`endfield-tools-api.js` 以及通过搜索发现的其余 fetch 包装。

**接口：** `requestJson(path, options = {})` 统一会话、CSRF 与 401 处理；`getAccountSnapshot(accountId, roleId, capability)` 对接任务 6；网站与社区登录使用不同组件和文案。

- [ ] 编写 `test_site_login_does_not_request_game_credentials`、`test_logout_clears_private_state`、`test_late_response_from_previous_user_is_ignored`、`test_csrf_added_to_mutations`；测试完整 UID 默认不出现在共享摘要。
- [ ] 在 frontend 目录执行 `node --test src/http-client.test.js src/identity-api.test.js src/components/SiteLogin.test.js src/components/AccountSettings.test.js`，确认失败。
- [ ] 实现邀请注册、网站登录、会话撤销、账号状态和默认角色；保留现有游戏详情展示。每次用户/账号变化递增请求代次并取消旧请求，忽略无法取消的旧返回；不使用共享 localStorage 保存私人 payload 或 token。
- [ ] 普通用户隐藏并禁止管理员来源配置；终末地两份授权分别展示。云端游戏列表不显示依赖本机 LCU 的入口；本地原模式保持回归。
- [ ] 执行 `npm test`、`npm run build`；用独立测试账号 A/B 在手机尺寸和桌面检查。真实手机流量与生产域名验证留到任务 12，提交 `feat: add cloud login and account dashboard`。

### 任务 9：QQ 身份双向确认关联

**文件：** 新增 `qq/models.py`、`bindings.py`、`internal_routes.py`、前端 `QqBindingPanel.vue` 及测试；新增 `tests/test_qq_bindings.py`、`test_qq_internal_auth.py`。

**接口：** 网站 `POST /api/qq/link-codes`、`GET /api/qq/link-attempts`、`POST /api/qq/link-attempts/{id}/confirm`、`DELETE /api/qq/links/{id}`；内部 `POST /internal/qq/link-attempts` 接收 `QqIdentity` 与 code；`resolve_qq_identity(identity: QqIdentity) -> Principal` 只返回已确认关联。

- [ ] 编写 `test_link_requires_site_confirmation`、`test_replayed_code_rejected`、`test_other_user_cannot_confirm`、`test_forwarded_code_does_not_grant_access`、`test_cross_scene_ids_not_merged`、`test_service_key_required`。
- [ ] 执行 `python -m pytest tests/test_qq_bindings.py tests/test_qq_internal_auth.py -q`，确认失败。
- [ ] 提议关联码有效 10 分钟、单次使用，每发送者与网站用户各限 5 次尝试/10 分钟；仅存摘要。首次尝试进入 pending，不自动关联；网页需展示群/场景及可核对的尝试信息，用户不认可可拒绝并换码。
- [ ] 确认事务检查用户、有效期和唯一归属；撤销后立即拒绝 QQ 私人查询。内部服务凭据只允许 QQ 路径，限制来源回环；它不是网站登录凭据。
- [ ] 完成面板测试与后端测试，提交 `feat: add confirmed QQ identity linking`。

### 任务 10：QQ 传输和文字指令

**文件：** 新增 `qq/client.py`、`transport.py`、`commands.py`、`runner.py`，扩展 `internal_routes.py`；新增 `tests/test_qq_transport.py`、`test_qq_commands.py`；依赖按任务 1 的结论锁定。

**接口：** `handle_message(message: InboundMessage) -> None`；内部 `POST /internal/qq/query` 由 `identity` 解析 Principal 后调用 AccountQuery，禁止调用者直接指定 user_id。`send_text(message: InboundMessage, text: str, sequence: int) -> str` 返回平台消息 ID。

- [ ] 编写 `test_retry_does_not_repeat_refresh`、`test_unbound_user_gets_help_only`、`test_self_query_cannot_target_other_account`、`test_expired_reply_not_sent`、`test_url_removed_when_not_approved`、`test_web_and_qq_share_snapshot`。
- [ ] 执行 `python -m pytest tests/test_qq_transport.py tests/test_qq_commands.py -q`，确认失败。
- [ ] 实现 AppID/AppSecret 凭证生命周期、WebSocket 心跳与重连，忽略机器人自身消息；将传输与业务分离。仅消费允许的测试群或正式群，默认处理 @ 消息。
- [ ] 落地帮助、绑定、我的账号、三游戏查询、鸣潮角色、活动、公告、刷新、看板指令；无权限能力明确提示。敏感信息不回显，未报备域名不发送任何外链。
- [ ] 持久化入站去重与发送状态；同一消息重投复用任务结果和出站序号。网络发送结果不明时不能盲目递增序号重新发，避免重复回复；群 5 分钟/最多 5 次限制作为上限，产品通常只回 1 次。
- [ ] 先用模拟传输测试故障与重投，再在已授权测试群核对真实回复与网页一致；提交 `feat: connect QQ official text queries`。

### 任务 11：图片摘要与文字降级

**文件：** 新增 `qq/rendering.py`、`tests/test_qq_rendering.py`；修改 `qq/commands.py`、`client.py`，图片依赖纳入锁文件。

**接口：** `render_summary(scope: AccountScope, result: QueryResult) -> bytes` 返回 PNG；`send_image(message: InboundMessage, image: bytes, sequence: int) -> str`。图片上传仅在任务 1/真实联调确认可用时启用。

- [ ] 编写 `test_cache_includes_account_and_snapshot`、`test_missing_fields_render_unknown`、`test_upload_failure_falls_back_to_text`、`test_render_queue_does_not_exceed_reply_window`。
- [ ] 执行 `python -m pytest tests/test_qq_rendering.py -q`，确认失败。
- [ ] 使用自有简单模板和可合法分发字体，不复制参考插件模板；渲染并发 1、宽度上限 1080 像素、初始队列上限 10，超限直接文字回复。平台上传大小按已验证接口限制另行约束，不假定 1080 像素保证可上传。
- [ ] 缓存键包含账号/角色/快照版本/模板版本；私图不放到匿名静态目录。媒体 file_info 按平台 TTL 过期重新上传；授权撤销后清理对应缓存。
- [ ] 检查实际生成图片与失败降级，记录内存峰值；测试通过后提交 `feat: add bounded QQ summary images`。

### 任务 12：云端试运行、备份及生产切换准备

**文件：** 新增 `cloud_runtime.py`、`deploy/cloud/game-manage.service`、`game-manage-qq.service`、`Caddyfile.fragment`、`scripts/cloud/backup.py`、`restore.py`、`verify.py`、`docs/cloud-operations.md`、`tests/test_cloud_operations.py`；修改 `README.md`、`SECURITY.md`，准确区分本地模式与已验证云端模式。

**接口：** `python -m game_assistant.cloud_runtime --config <path>`；内部健康检查包括 DB 可用性和调度状态，公开健康检查保持简要。运维工具支持 `--help`，备份和恢复以显式输入输出目录工作，不自行发现并删除其他项目目录。

- [ ] 编写 `test_backup_is_consistent_with_wal`、`test_restore_requires_matching_key`、`test_invalid_destination_rejected`、`test_cloud_starts_one_scheduler`，先运行 `python -m pytest tests/test_cloud_operations.py -q` 确认失败。
- [ ] 独立运行用户和数据目录；不复用 LOLhelper 密钥、数据库或服务端口。绑定回环，新端口实施前检查未占用；Caddy 以独立站点片段接入并先验证配置。
- [ ] 提议初值：中央服务 MemoryHigh 512MiB/MemoryMax 768MiB，QQ 服务 192MiB/256MiB；在试运行测量后调整。日志轮转，缓存有上限，禁止反复 OOM 自动重启而不报告。
- [ ] 每日在线一致性备份，提议保留 7 日和 4 周；密钥独立备份。备份目的地必须在生产切换前由用户确定，只有同机备份不得标为灾难恢复通过。恢复在新目录演练，不覆盖运行库。
- [ ] 在隔离测试实例运行后端 `python -m pytest -q`，前端 `npm test` 与 `npm run build`；Linux 单独验证安装、启动、加密、关停和重启。本地 Windows 启动测试按原环境运行，平台跳过项须列明。
- [ ] 用 20 个模拟用户、每用户三游戏数据执行缓存查询与刷新合并负载测试；不让合成压力请求直接冲击真实社区。提议缓存查询 P95 <2 秒、HTTP 错误率 <1%、无 OOM/写锁失败；真实 QQ 端到端延迟单独测量，不混为 API 延迟。
- [ ] 使用至少两名真实用户、两设备、手机流量核对账号隔离、会话撤销、游戏授权复用；验证云端资讯来源、失败保留及日历日期。先少量请求，随后 24 小时试运行观察资源和 LOLhelper 健康；合成压力测试不能替代 24 小时观察。
- [ ] 准备版本化发布产物、迁移报告、备份恢复证据、待验证项及回滚步骤。正式 QQ 上线审核与生产访问切换在材料齐备后交用户确认，不因通过本计划就自动提交或切换。
- [ ] 生产切换前冻结旧库写入，保留最终一致性备份；回退使用旧程序与旧库，新系统新增记录另行导出核对，禁止让旧程序读取新 schema。记录域名报备未完成等功能降级。
- [ ] 提交 `ops: prepare cloud deployment and recovery`；只有实际执行并验收成功后才把文档状态改为已部署。

## 6. 验证与提交约定

测试命令均是未来执行命令，本轮不运行产品测试或下载依赖。Windows 从仓库根目录使用虚拟环境 Python 替代命令中的 `python`；前端命令在 frontend 目录执行。失败先确认是期望行为缺失，而不是环境错误；已有失败记录基线，不声称全部回归通过。

每个任务按“行为测试失败 → 最小实现 → 相关测试通过 → 精确暂存该任务文件 → 提交”完成。避免 `git add .`，尤其不能纳入用户数据及无关未跟踪文件。任务结束只运行相关测试；跨层里程碑和最终候选执行完整回归。

## 7. 设计覆盖与验证映射

| 设计要求 | 计划覆盖 |
| --- | --- |
| R01–R03 人数、本人数据、三游戏 | 1–6、12 |
| R04 资讯日历与参考展示 | 6、8、10、11 |
| R05 QQ 官方优先 | 1、9、10 |
| R06–R07 授权共用、多设备 | 3–6、8–10、12 |
| R08 原服务器全天运行 | 1、12 |
| R09–R10 规划边界与单份设计 | 本轮只保存此实现计划；原总体设计保持为单份，不拆出 QQ 文档 |
| V01/V03 QQ 实际权限与 SDK | 1、10 |
| V02 域名、备案、URL | 10 处理无链接降级；12 在发布前核验 |
| V04/V05 游戏真实接口 | 1 验证，4–6 实现，12 复验 |
| V06 全面隔离 | 2–6、8、9、11 |
| V07 Linux、迁移与恢复 | 4、7、12 |
| V08 跨网络设备 | 8、12 |
| V09 资源与共存 | 11、12 |
| V10 公共来源 | 6、12 |
| V11 可选平台能力 | 1 记录可用性；11 图片单独验证；全量消息和主动推送不进入本轮实现 |

## 8. 确认时需要关注的选择

1. 是否按“外部验证 → 中央服务隔离 → 网页 → QQ 文字 → 图片与试运行”的顺序执行。
2. 本计划提出的具体初值可在实现确认时接受，实测不满足则记录依据调整：会话/关联码期限、刷新并发、资源限制、备份保留和性能目标。它们不是此前实测结论。
3. 执行方式建议主代理串行实现，因为账号、授权、路由和存储契约关联紧密；在多人隔离完成与上线候选时安排独立代码审查。也可以选择子代理逐任务实现及审核，执行前选定即可。

域名、备份目的地和真实平台账号尚未确定，只阻塞依赖它们的验证与上线，不要求现在提供密钥。本计划确认前，所有实现任务保持未开始。
