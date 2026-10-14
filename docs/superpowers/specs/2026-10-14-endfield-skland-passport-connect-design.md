# 终末地森空岛随鹰角通行证一键连接设计

日期：2026-10-14
状态：用户已评审，第 10 节三个决策点均采用推荐方案；已按本文实现。
基线：main / 095eea7。开发环境为 macOS，官服真实账号由用户本人操作。

## 1. 目标与边界

目标：用户在「社区账号」完成终末地鹰角短信登录后，不再从浏览器开发者工具复制 `cred`，即可在终末地页面一键连接森空岛，并自动选中与通行证登录相同的角色。现有“粘贴会话凭据与设备标识”的连接方式保留为备用。

边界：

- 不生成、不伪造数美设备标识（`dId`），不复现风控 SDK 加密；通行证换取的会话按实测不带 `dId` 请求。需求文档第 20 行的边界不变。
- 签到仍只在用户点击时提交，不新增自动签到。
- 寻访链路、官网公告、地图和蓝图不改。
- 不在本次加入理智定时采集与提醒、寻访首次同步预算调整、B 服登录，见第 9 节。

## 2. 实测依据（2026-10-14，用户本人官服账号）

此前文档（`endfield-feasibility.md`、`endfield-implementation-guide.md`）依据社区资料判断“换取森空岛会话必须带 `dId`”，因此只做了手动粘贴。本次用临时脚本实测，凭据只在本机内存使用，脚本已删除：

| 项目 | 结果 |
| --- | --- |
| 鹰角短信登录（`EndfieldLoginProvider`） | 成功 |
| 寻访链路 grant(type 1) → binding_list → u8_token → record | 成功；首次同步 120 页预算全部用于特许寻访（595 条），其他卡池待后续轮次 |
| 现有手动连接（浏览器 `cred` + `dId`） | 角色卡、签到日历与记录、图鉴、挑战记录均成功 |
| 通行证令牌 → `as.hypergryph.com/user/oauth2/v2/grant`（appCode `4ca99fa6b56cc2ba`，type 0）→ 授权码 | 成功 |
| 授权码 → `zonai.skland.com/api/v1/user/auth/generate_cred_by_code`（`{kind: 1, code}`，不带 `dId`） | 成功，返回 `cred` |
| 新 `cred` 不带 `dId`：refresh、user、binding、card/detail | 全部成功，为同一角色，理智有值 |
| 新 `cred` 不带 `dId`：`/web/v1` 签到日历与记录、图鉴；挑战记录 | 全部成功 |
| 新会话是否使已有会话失效 | 否：连续换取 3 次后，浏览器会话仍可读取 |
| 签到提交（写操作） | 未测 |

与社区资料的冲突（skyland-auto-sign 记录 2024-09 起登录需 `dId`；EndUID 注释 2026-08-19 起空 `dId` 返回 10001；arknights-mower PR #967）说明服务端校验可能按条件触发或已调整。本次只是一个账号、一天、一个网络的样本，实现必须在换取被拒时明确提示并退回手动连接。

## 3. 选定方案与修改范围

采用“一键连接”：通行证已登录且森空岛未连接时，概览页显示「用鹰角通行证连接」按钮；点击后由后端用已保存的通行证令牌换取森空岛会话。不在登录或页面加载时自动发起换取，原因是每次换取都会在服务端新建一个森空岛会话，应由用户明确触发（替代方案见第 10 节决策点 1）。

| 位置 | 修改 |
| --- | --- |
| `adapters/endfield/endpoints.py` | 新增 `SKLAND_APP_CODE = "4ca99fa6b56cc2ba"`，注释写明公开协议常量与 2026-10-14 实测 |
| `adapters/endfield/hypergryph.py` | `HypergryphClient.skland_code(token)`：POST grant `{token, appCode: SKLAND_APP_CODE, type: 0}`，返回 `data.code`；沿用 `request_data` 的失效识别与安全错误文案 |
| `adapters/endfield/skland_client.py` | 新增 `CRED_BY_CODE` 路径与 `SklandClient.cred_by_code(code)`：POST JSON `{kind: 1, code}`，不带 `cred`、签名和 `dId`；`_request` 支持可选 JSON 请求体，并把新路径加入白名单 |
| `endfield_skland.py` | 会话增加来源与通行证身份锚；新增 `connect_with_passport()`、`on_passport_changed()`；读取时校验身份、会话过期时自动重换（第 5、6 节） |
| `endfield_skland_routes.py` | 新增 `POST /api/endfield/skland/passport`；`status` 增加字段；服务注入通行证身份读取函数 |
| `auth/service.py` | `LoginService.add_account_listener()`；登录、退出成功后通知监听方（第 6 节） |
| `api.py` | 装配：把读取通行证身份的函数传给森空岛服务，并注册账号变更监听 |
| `frontend/src/endfield-tools-api.js` | `connectSklandWithPassport()` |
| `frontend/src/components/EndfieldDashboard.vue` | 概览页「森空岛游戏档案」卡片的三种状态（第 7 节） |
| `frontend/src/components/LoginPanel.vue` | 终末地登录提示补一句“登录后可在终末地页面一键连接森空岛” |
| 测试与文档 | 第 8 节 |

## 4. 本地 API 契约

`GET /api/endfield/skland/status` 在现有字段上增加：

```json
{"connected": true, "source": "passport", "passport_available": true,
 "roles": [...], "selected_role_id": "...", "selected_server_id": "...", "error": null}
```

- `source`：`"passport"`（由通行证换取）、`"manual"`（用户粘贴）或 `null`（未连接）。现有已保存会话没有该字段，按 `"manual"` 读取。
- `passport_available`：当前存在终末地通行证登录（令牌与角色编号均非空）。
- 状态接口不发网络请求。来源为 `passport` 但与当前通行证身份不一致的会话，在状态中报告为未连接。

`POST /api/endfield/skland/passport`（需 `X-Game-Assistant: 1`，无请求体）：

1. 读取当前通行证令牌、`uid`、`role_id`；为空时返回 409「请先在「社区账号」登录终末地」。
2. `skland_code` → `cred_by_code` → 沿用现有连接校验：refresh → binding → user，得到角色列表与森空岛账号标识。
3. 角色列表中有与通行证 `role_id` 相同的角色时自动选中；没有时保存连接但不选角色，返回提示“森空岛绑定角色与通行证登录角色不同，请确认后手动选择”。
4. 全部校验通过后才替换现有会话（无论原来源）；任一步失败保留原会话。
5. 返回与 `status` 相同的结构。

错误映射沿用 `_http_error`：通行证失效为 401「鹰角通行证登录已失效，请在「社区账号」重新登录」；换取被拒（非 0 业务码，如 10001）为 502「森空岛未接受通行证授权，请改用手动连接」（`_http_error` 现只把「森空岛暂时」「森空岛响应」开头映射为 502，需加上这一前缀）；网络与格式异常为 502。错误信息不含令牌、授权码、`cred` 或响应正文。

## 5. 会话存储与身份锚

森空岛凭据文件路径与加密方式不变（`*.endfield-skland.credentials.json`，`CredentialStore`）。来源为通行证的会话增加：

```json
{"source": "passport", "passport_uid": "...", "passport_role_id": "...",
 "cred": "...", "device_id": "", "roles": [...], "user_id": "...", "role_id": "...", "server_id": "..."}
```

- 身份锚为通行证的 `uid` 与 `role_id`，不保存通行证令牌（令牌只在 `LoginService` 的凭据文件中）。
- 换取的会话持久化保存，重启后继续使用，避免每次启动都在服务端新建会话。
- 手动会话不写身份锚，行为与现在一致。

## 6. 生命周期、并发与账号隔离

- **退出或切换通行证账号**：`LoginService.login()`、`logout()` 在 `_persist(..., clear_snapshots=True)` 成功并释放本游戏锁之后，依次 `await` 账号变更监听；监听异常只记录类型，不影响登录或退出结果。森空岛服务的监听在自己的锁内执行：来源为 `passport` 且身份锚与当前通行证不一致（含已退出）时清除会话与全部缓存。与现有 `test_concurrent_account_change_cannot_publish_old_card` 相同，进行中的读取完成后才清除。
- **兜底校验**：所有读取在锁内取会话时再比对一次身份锚，不一致即清除并返回「鹰角通行证账号已变化，请重新连接森空岛」，覆盖监听未触发的情况（如手改配置后重启）。
- **同一账号重新登录**：身份锚不变，保留森空岛会话。
- **手动会话**：不受通行证登录、退出影响，与现在一致（决策点 2）。
- **会话过期**：来源为 `passport` 的会话在 refresh 返回失效（HTTP 401/403，业务码 220/10002，即 `SklandError.expired`）时，用当前通行证令牌重换一次并保留所选角色，然后重试本次读取；重换失败返回错误，保留上次成功的档案并标记待更新。手动会话过期仍提示重新连接。每次读取最多重换一次，不做自动循环重试。
- **断开**：清除会话，不自动重连；用户可再次点击一键连接。

## 7. 前端交互

概览页「森空岛游戏档案」卡片：

| 状态 | 显示 |
| --- | --- |
| 未连接，`passport_available` | 说明“使用已登录的鹰角通行证连接，无需复制凭据。”与「用鹰角通行证连接」主按钮；下方折叠「手动连接（备用）」，内为现有表单 |
| 未连接，无通行证登录 | 提示“在「社区账号」登录终末地后，可一键连接森空岛。”；手动连接表单直接展开 |
| 已连接 | 现有角色选择、刷新档案、断开；角色栏旁标注来源“鹰角通行证”或“手动连接” |

一键连接失败时在卡片内显示错误，并展开手动连接表单。连接成功后若已选中角色，沿用现有 `watch(roleValue)` 读取档案和签到状态。

## 8. 测试与验收

后端（`tests/test_endfield_skland.py`，以及 `LoginService` 相关测试）：

1. `skland_code` 请求体为 type 0 与森空岛 appCode；失效与业务错误映射；错误信息不含令牌。
2. `cred_by_code` 不带 `cred`、`sign`、`dId` 请求头，请求体为 `{kind: 1, code}`；非 0 业务码与缺少 `cred` 均报错。
3. 一键连接成功：来源为 `passport`，自动选中同一角色，身份锚写入加密存储，通行证令牌不写入森空岛文件。
4. 未登录通行证返回 409；换取失败保留原手动会话；绑定中无同一角色时连接但不选角色。
5. 通行证退出或切换后监听清除通行证来源会话与缓存；手动会话不受影响；监听异常不影响登录与退出。
6. 兜底校验：身份锚不一致时读取被拒且会话被清除。
7. 过期重换：通行证来源会话 refresh 失效一次后自动重换成功；手动会话不重换；重换失败保留旧档案并标记待更新。
8. 并发：读取进行中发生通行证退出，读取完成后会话被清除，之后不再返回旧账号数据。
9. 旧格式会话（无 `source`）按手动会话读取。
10. 路由：经 `create_app` 验证 `POST /passport` 缺少 `X-Game-Assistant` 时被拒；`status` 新字段。

前端（`EndfieldDashboard.test.js`）：三种状态的渲染；点击一键连接调用 `POST /skland/passport` 并在选中角色后读取档案；失败时显示错误并展开手动表单；来源标注。

验收：`pytest -q`、`npm test`、`npm run build` 全部通过；用户用真实账号在页面完成一键连接、读取档案、断开后重连、退出通行证后森空岛来源会话被清除、手动连接仍可用。

## 9. 文档与范围外事项

本次一并更新：

- `docs/endfield-toolbox.md`「连接森空岛」与验证范围；`docs/endfield-data.md` 森空岛段落。
- `docs/endfield-implementation-guide.md`「实测记录」表填入第 2 节结果。
- `README.md` 第 7、16 行补充一键连接；第 235 行“森空岛暂未接入”的过时说法改正。
- `CHANGELOG.md` Unreleased 增加条目。

范围外，后续另行设计：理智等字段接入调度器与体力提醒；寻访首次同步预算在卡池间分配；B 服；签到自动化。

## 10. 待评审决策点

1. **触发方式**：推荐“一键连接”（用户点击后换取）。替代方案“零点击”：登录通行证或打开终末地页面时自动换取，需要额外记录“本账号已尝试/用户已断开”的持久状态，避免反复在服务端新建会话，状态更多、行为也更难预期。
2. **手动会话与通行证的关系**：推荐保持独立（退出通行证不清除手动会话，与现在一致）。替代方案是退出通行证时清除所有森空岛会话。
3. **自动选中角色**：推荐只在角色编号与通行证一致时自动选中；不一致时不自动选，避免把两个账号的数据拼在一起。

## 11. 回退

一个提交即可回滚。旧代码读取新格式会话时忽略新增字段，按手动会话使用 `cred`，不会读错账号；若需彻底回到旧状态，可在页面断开森空岛后重新手动连接。
