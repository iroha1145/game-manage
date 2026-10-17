# 云端看板问题合并与修复实施计划

> **状态：待用户审核。仅计划文档，尚未实施或部署。**
> **For agentic workers:** REQUIRED SUB-SKILL: 审核通过后使用 superpowers:executing-plans 逐任务实施。只有用户另行选择代理执行时才使用 superpowers:subagent-driven-development；本计划不自动授权派发代理。

**Goal:** 修复两轮已登录页面检查发现的加载、错误提示及数据展示问题，按用户指定基准统一角色模块和日历外观，接入有明确来源的异环资产图片。

**Architecture:** 沿用现有云端账号作用域、快照读取和共享 Vue 组件。优先改前端读取状态和展示层；角色保留游戏专用字段，统一信息层级与交互。图片只依据明确条目 ID 或来源关系匹配，不改变数据采集、账号权限和日期推导规则。

**Tech Stack:** Vue 3、Vite 8、Node 内置测试及现有 Vue 测试工具；FastAPI/Python 仅在证据明确指向现有读取层时做兼容性修复；既有离线 Chromium 渲染用于受影响共享组件检查。

**Spec:** 本文第 1、2 节为本计划的需求依据，合并本对话 2026-10-18 两轮页面核验及用户明确的角色、日历统一要求；计划审核通过前不得开始产品代码。

## Global Constraints

- 唯一操作仓库：C:\Zcode\game-manage-cloud-qq-public；分支 codex/cloud-qq-public。编写计划时 HEAD=d2fcc5b34767a19899faf6b588a123caee83cf1e，原工作区干净。
- C:\Zcode\game-manage、原 8010 服务、本地已有配置、凭据、登录状态、数据库和备份均受保护；不清理回退资源、Chromium 或字体。
- 保留隐私 pre-push hook，不直接修改或推送 main，不绕过检查或公开私有历史。
- d2fcc5b 的 final-acceptance.json 已通过，CI success，必需待办为空。原部署闭环不重新打开，历史 Pending 不作为本计划待办。
- 本计划的审核只授权其明确范围内的后续实施；当前轮只写文档。提交、推送、部署、真实 QQ 收图不在本轮授权范围。
- 后续预览沿用隔离方案；启动前核实实际端口和进程，不抢占线上 QQ 连接，不启动重复调度或通知，不原样重跑旧部署脚本。
- 不变更数据库结构、认证/授权规则、加密、邀请、密码、QQ 绑定、提醒、排行榜、抽卡导入规则、评分算法或全库存采集。
- 不覆盖或回填真实快照；展示修复优先兼容现有缓存。缺失不转为零，负值含义未经来源确认不解释成“无限”，预计时间不改成实际开放时间。
- 修复公用组件时覆盖网站和离线图片模式；不另建 QQ 模板、不发送 QQ 消息，不改变现有分页尺寸和续页协议。
- 只运行受影响的必要门禁；已通过且输入不变的门禁复用。共享底层广泛变化才扩大测试，视觉确认后无相关变化不反复验收。
- 每完成约 2–3 个独立功能，在最近闭环评估是否需要换窗；不自动创建新聊天。

## Review Focus

1. 延迟、失败、真空数据必须可区分；慢的角色快照不能阻塞已返回的体力或活动。
2. 切换用户、授权、角色或授权版本后，旧请求、旧缓存、收藏及比较对象不得串入新作用域。
3. 图片缺失或外部 CDN 失败时仍保留名称、状态和操作入口；不能靠图片加载成功才决定布局。
4. 目录、文字摘要和原图是不同覆盖层级；匹配不到角色形态或可靠来源时不得套用别人的攻略。
5. 网站重排不能使离线角色装备、日历首末项或续页指令遗漏；日期未知和来源不完整仍须如实展示。

---

## 1. 合并问题清单与证据边界

优先级：P1 为影响进入页面或信息判断的问题，先做；P2 为用户明确要求的结构、覆盖和视觉改进。本次未发现足以归为全站不可用的 P0。

| 编号 | 优先级 | 合并问题/需求 | 已有证据及边界 |
| --- | --- | --- | --- |
| I01 | P1 | 首次加载偏慢 | 页面曾空白十几至三十多秒；浏览器角色快照导航超过 10 秒后成功，另有一次公开 JS 获取约 7.5 秒。属于本次观测，不是持续性能统计，也未定位到服务器处理或上游网络。 |
| I02 | P1 | 动态组件失败提示失真 | 浏览器记录 CloudGameCard 动态 import 下载失败；页面统一提示“界面已更新”。同一资源另行 GET 可返回 200，故不能断言旧版本或资源被删。 |
| I03 | P1 | 加载中误显示为空数据 | 角色先显示 0 位、体力先显示未知、模块先显示未读取，之后恢复真实数据。应与成功返回空列表、从未采集和读取失败区分。 |
| I04 | P1 | 来源字段直接暴露、异常值无说明 | 异环说明出现 {0}、rn、</>、Effect5；抽卡出现 fork_butterfly、fork_jingmotingyuan；部分车辆耐久显示 -1。鸣潮历史另见 difficulty_list 字段名，作为同类标签问题一并收口。未经核实不重算评分/属性，不回写真实数据。 |
| I05 | P2 | 异环侧边栏正式图标未显示 | 侧边栏已回退 /game-icons/nte-mark.svg，其他位置的官网正式图标可加载；是显示不一致，不能写成所有异环图标都不存在。 |
| I06 | P2 | 异环攻略摘要覆盖少、更多角色不易发现 | 一级卡固定 5 人；弹窗有 23 人原图索引，只有 5 人标为 reviewed。已打开安魂曲验证其 original_only 状态及原图入口，不能把目录错误写成仅有 5 人。 |
| I07 | P2 | 角色模块和攻略入口统一 | 以鸣潮当前角色统计、搜索筛选、列表和单角色详情为基准；异环攻略不再独立成一级模块，优化一级信息，不丢失探索、装备、收藏和角色比较。 |
| I08 | P2 | 异环房产、载具未接入可用图片 | 当前摘要和详情主要使用 SVG 通用轮廓；官方战绩前端有明确条目 ID 路径。2 张房产及 2 张载具图片 GET=200、image/png、PNG 签名正确；各一张已在浏览器实际显示。仅为抽样，非全目录覆盖证明。 |
| I09 | P2 | 三款日历外观统一 | 三款已共用时间轴；有图/无图触发不同样式，终末地的图片活动条、截止图卡与鸣潮/异环紧凑纯色条明显不同。以终末地当前形式为基准统一外观，保留游戏色与日期语义。 |

### 不作为缺陷或新增待办的项目

- 鸣潮当前逐抽库未导入记录，不据此判断丢失数据；不补导入或回补。
- 终末地个人模块当前账号未授权，不按“未测”要求用户新增授权；本计划只涉及其公共日历外观。
- 网站会话、现有账号授权、日历筛选/详情、搜索跳转、角色读取、攻略原图和角色比较已能工作；不重做其后端。
- 本轮成功读取的角色数和活动数是时间点观测，测试使用合成数据，不能把真实数量硬编码为功能规则。

## 2. 拟实施结果与范围

### 2.1 读取体验及性能目标

- 路由组件加载、数据 GET、后台采集是三种状态；不把读取页面自动变成刷新采集。
- 组件开始加载后 200ms 可见加载反馈；15 秒仍未完成显示超时及恢复入口；失败文案用“页面模块加载失败，请重试；仍失败可刷新页面”，仅有版本变更证据才使用更新提示。
- 快照 GET 采用可取消的 20 秒读取上限；超时只结束本次观察，不清除同作用域成功数据，不替用户重新登录。原有 30 秒刷新跟踪边界和 POST 行为不变。
- 已返回的能力逐项展示；只有成功读取后才显示真实 0 或空态。同作用域再读时保留成功内容并标明正在更新；跨用户/账号/角色/授权版本不得复用。
- 诊断先区分浏览器下载、排队、HTTP 返回和 Vue 展示耗时，不把自动化工具导航超时当作服务器响应时间。冷、暖加载各做一次针对性对照，不做压测，不承诺无法证明的公网固定秒数。

### 2.2 角色与攻略

- 鸣潮作为交互基准，避免改写其已正常的数据逻辑；异环一级角色页面展示统计、品质/元素分布、等级分布、搜索筛选排序和紧凑角色卡。
- 每张角色卡显示头像、名称、品质、元素、等级及已知觉醒/混频信息；完整属性、弧盘、卡带/驱动、技能和来源补充字段进入单角色详情。
- 单角色详情提供“角色面板 / 培养攻略”切换；个人评分和 A/B 配装功能沿用现有入口与算法。异环原有最多 4 人比较及账号隔离收藏保留。
- 异环探索仍可从原角色与探索区域读取，不删除或塞入角色详情。通过 GameCard 的专用角色分支调整，不重构其他游戏的整个导航。
- 移除异环独立“角色攻略”一级页签；角色页内提供可展开的公开攻略浏览。旧 tab=guides 链接兼容跳转到角色页并展开攻略；旧 characters 入口继续有效。
- 攻略目录来自实际 catalog，不保留固定 5 人的一级展示。搜索与“只看已拥有”可用；目录、已整理摘要、仅原图和无可靠来源的状态分别标识。
- 将其余 18 个现有原图索引列为逐角色内容核对范围；有明确原图及版本依据才整理五类摘要并标 reviewed。缺失来源或新形态不得编造；未完成条目逐项保留缺口，不宣称全角色摘要已补齐。

### 2.3 图片、文字和日历

- 正式图标使用现有允许的来源链；保留用户自备本机图标优先级，公开仓库不提交本机私有图片。失败恢复只做有限重试，最终文字标识始终可读。
- 异环房产、载具在现有条目 ID 上建立严格官方 CDN 映射，摘要卡和详情共用；不需要为此增加数据库列或改资产接口 schema。
- 图片地址模板来自官方前端：realestate/detail/{id}.png、verhicle/wide/{id}.png。verhicle 为来源真实拼写。模型/涂装图本轮不扩大接入，已知路径留作证据。
- 异环描述按明确标记处理换行和富文本残留；模板参数必须先核对数值表的索引、突破/混频等级和单位，再替换。无法证明参数关系时显示“效果数值待核验”，原文和参数折叠保留；不盲目按数组位置填值。
- 已知 ID 从已有公开目录精确反查名称；同 ID 存在冲突时保留“名称待核验”及折叠来源 ID，不猜名称。-1 耐久未核实含义前显示“来源未说明”，保留原值，不映射成 0 或无限。
- 三款日历统一活动条高度、字体、标签、留白、侧栏截止卡和详情结构；有图/无图结构一致。无图使用同尺寸主题底纹，不能因缺图片退回另一套紧凑布局。
- 仅事件自身图片、明确同源公告、同版本且来源可核实的版本封面可作日历插图；不靠相邻日期、同游戏或相似标题强配图片。此次不改 public_content.py 日期推导或事件去重。

## 3. 文件边界与接口影响

| 任务 | 拟修改/新增文件 | 现有责任与边界 |
| --- | --- | --- |
| T1 读取与组件状态 | frontend/src/lazy-page.js、cloud-dashboard.js、http-client.js、accounts-api.js、CloudApp.vue、components/CloudGameCard.vue、OverviewPage.vue、CloudSnapshotStatus.vue、GameCard.vue；受影响 WuwaDashboard/WuwaRoles 和 NteModuleCard/NteRolesPanel 只接收读取状态 | 不替换 AccountScope 或认证规则；加载 props 只增不破坏旧调用，图片模式保持默认就绪语义。 |
| T2 字段展示 | 新增 frontend/src/nte-display.js；修改 nte-charts.js、components/NteEquippedDetails.vue、NteModuleCard.vue、NteAssetsPanel.vue、NteCommunityGacha.vue；鸣潮仅补 wuwa-display.js 已知字段中文标签 | 统一显示函数，不回写快照、导入库和统计值，不改评分计算。 |
| T3 图标 | frontend/src/components/GameIcon.vue、game-artwork.js、public/game-icons/sources.json | 只改来源及有限恢复；不改 Vite 自备图标目录机制。 |
| T4 角色页面整合 | frontend/src/components/GameCard.vue、NteRolesPanel.vue；新增 NteRoleDialog.vue、NteRoleDetail.vue；接入已有 NteEquippedDetails.vue、RoleAssessment.vue、NteGuides.vue | 将现有详情字段移动到单角色视图，不重写数据采集。鸣潮角色作为基准，只做 T1 所需的小范围状态接入。 |
| T5 攻略覆盖 | frontend/src/components/NteGuides.vue、NteModuleCard.vue、frontend/src/guide-search.js；src/game_assistant/nte_guides_catalog.py；docs/nte-icons.md 中实际覆盖记录 | 保留 catalog 的 reviewed/original_only 契约、来源指纹和版本信息，不将待整理状态改为成功。 |
| T6 资产图片 | 新增 frontend/src/nte-artwork.js；修改 nte-charts.js、components/NteModuleCard.vue、NteAssetsPanel.vue；新增 docs/nte-asset-artwork.md | 当前资产 schema 已有条目 ID，前端派生图片地址；不改 adapters/neverness/assets.py。 |
| T7 日历统一 | frontend/src/components/CalendarTimelineContent.vue、CalendarPage.vue，必要时 VersionCalendarContent.vue、event-artwork.js；render.css 仅在受影响样式隔离需要时修改 | 延续现有选择、滚动、来源详情及 screen/image 模式；不改日期和 QQ 命令。 |

接口契约：

- 外部 HTTP 路由、响应 schema、快照版本、QQ 命令及角色数据模型保持不变。
- T1 如需超时参数：requestJson(path, options) 新增可选 options.timeoutMs；getAccountSnapshot(id, role, cap, options = {}) 仅扩展可选第四参，旧三参调用仍有效。超时配置不得透传为无效 fetch 属性。
- 前端新增 readStates[cap]，status 为 idle/loading/success/error，附 startedAt 和安全错误文案；来自 GET 运输层，不能覆盖快照本身 never/error/auth_expired 等来源状态。
- 超时使用独立 RequestTimeoutError 和固定中文文案；主动切换 scope 的 AbortError 继续静默取消。不得把超时当成 AbortError 吞掉，否则界面仍会停在“正在读取”。
- T2 拟新增 displayNteText(value)、nteItemLabel(id, suppliedName)、displayVehicleStat(stat)，由摘要和详情共用；原字段保留，不改变底层值。
- T4 新组件 NteRoleDialog 接收 role、scope、snap、initialTab，发出 close/guide；NteRoleDetail 接收 role、scope、imageMode。NteRolesPanel 原 snap/accountId/focusCharacterId/imageMode/detailMode 入参保留兼容；图片模式不依赖打开模态框。
- T6 新增 nteAssetImage(kind, id)，kind 仅 realestate/vehicles；非法或无 ID 返回空值，禁止路径穿越、任意域名和外部输入 URL 注入。
- 若 T1 定位到现有缓存 GET 的重复验证/序列化问题，只允许在 src/game_assistant/accounts/routes.py、query.py 保持相同权限及响应的读取优化；这是条件范围，必须先给出重复调用或耗时证据。需要改 schema、数据库或云端配置时先修订计划，不能直接扩展。

## 4. 执行顺序及任务

所有下列命令均为审核通过后的实施/验收命令，本轮没有运行。

### 阶段 A：读取可靠性与准确展示（T1 → T2 → T3）

### T1：加载、超时、局部完成和错误恢复（I01–I03）

**Interfaces:** 使用现有 AccountScope、GET snapshot 和 refresh 202 契约；产生第 3 节 readStates 及可选 timeoutMs。作用域键包含 user/account/role/provider/version/grant，合并并发请求只能在完全相同键下进行。

- [ ] 记录一次冷加载及一次暖加载的模块下载/GET/显示边界；不记录 Cookie、令牌、角色完整 payload。核对 GET 只读，不在加载时偷偷 POST refresh。
- [ ] 在 lazy-page.test.js、cloud-dashboard.test.js、http-client.test.js、components/CloudApp.test.js、OverviewPage.test.js 补失败用例；新增 frontend/src/accounts-api.test.js 覆盖可选四参。用例包括延迟 200ms、15 秒模块超时、20 秒 GET 超时、逐项返回、成功空数组、读取失败保旧数据、账号切换晚回包、60 秒会话检查、并发相同 scope。
- [ ] 关键断言包括：待返回时不出现“已记录 0 位”；角色 pending 不阻塞已返回体力；同 scope 重读失败仍保留 payload；切到 B 后 A 的晚结果不显示；无构建版本证据的 import 失败不显示“界面已更新”。
- [ ] 先运行上述受影响测试确认新用例暴露缺陷，再按 2.1 和第 3 节实现；保留原有刷新队列 30 秒跟踪，不添加无限自动重试。
- [ ] 重跑受影响用例；合成慢请求验证 200ms 反馈、模块 15 秒和 GET 20 秒的可退出状态，不将网络不佳伪装成成功。若证据指向后端读取层，再增加 tests/test_cloud_boundary.py、test_cloud_schema.py 对应回归。

建议定向命令（工作目录 frontend）：

    node --test src/lazy-page.test.js src/cloud-dashboard.test.js src/http-client.test.js src/accounts-api.test.js src/components/CloudApp.test.js src/components/OverviewPage.test.js src/components/CloudCalendar.test.js

### T2：来源文字、名称和特殊值（I04）

**Interfaces:** 产生第 3 节三个纯展示函数；保留原始数值和来源字段，不改变统计总数、rareCount、评分或模型。

- [ ] 新增 nte-display.test.js；在 nte-charts.test.js、NteDataCard.test.js、NteAssetsPanel.test.js、NteCommunityGacha.test.js 补断言：转义换行/已知标签被正确显示、普通英文不被误删、缺值仍未知、0 仍为 0、负耐久有说明、来源原值可查看。
- [ ] 用已有目录验证 fork_butterfly → 现实避难所、fork_jingmotingyuan → 茶花会；相冲突的 suppliedName 不静默覆盖，没有映射时只显示待核验名称及来源 ID。
- [ ] Effect5 等编码只有已确认对应说明才显示译文；缺失关系提示待核验。{0} 等参数替换必须有等级/单位的来源用例，否则不做猜测替换。
- [ ] 先确认新增测试失败，再实现 nte-display.js 并接入摘要与详情；鸣潮 difficulty_list 仅补“难度记录”等精确字段标签，不对历史差异重算。
- [ ] 测试通过后检查旧 schema_version=1 快照直接可显示，不需要用户刷新覆盖数据。

建议命令（frontend）：

    node --test src/nte-display.test.js src/nte-charts.test.js src/components/NteDataCard.test.js src/components/NteAssetsPanel.test.js src/components/NteCommunityGacha.test.js src/components/WuwaPanels.test.js

### T3：正式图标显示及失败恢复（I05）

**Interfaces:** 保持 GameIcon 的 gameId/name 和自备图片优先级；复用现有官方图标配置和文字回退。

- [ ] GameIcon.test.js 补：一次 CDN 失败后可有限恢复、持续失败后不循环请求、本机自备图优先、主题切换、图片渲染模式不请求网站图标。
- [ ] 先确认新增用例失败，再修正候选和失败状态恢复。最多一次自动恢复；不在每次渲染/每分钟会话检查时重试，不加新的构建依赖或公开上传用户本机图片。
- [ ] 测试与浏览器各验证一次侧栏正式图和离线 fallback；失败时保留“异”字标识，不让整个导航空白。

    node --test src/components/GameIcon.test.js src/game-visuals.test.js

阶段 A 完成后做一次差异检查和必要审查；保留诊断结论，避免阶段 B 再全量重跑 A。

### 阶段 B：角色与攻略整合（T4 → T5，依赖 T1/T2）

### T4：异环角色一级列表与单角色详情（I07）

**Interfaces:** 新组件签名见第 3 节；继续使用现有 NteRoles schema、filterRoles/comparisonGroups 和按 scope 隔离的收藏，不新增通用角色后端模型。

- [ ] 在 NteRolesPanel.test.js、NteDialogs.test.js、CharacterSearch.test.js、IntegratedGameCard.test.js 补行为用例：一级有统计/筛选/紧凑列表；单角色点击才出现详细装备；攻略与本人面板双向一次跳转；关闭恢复触发焦点；无角色数据时仍能看公开攻略。
- [ ] 覆盖旧 tab=guides 和 characters 深链、不同角色形态不混用、切账号清空对比、最多 4 人比较、原收藏键不变；测试“查看本人黑羽”直接定位详情，不先跳摘要再要求点击一次。
- [ ] 在旧实现确认新用例失败后，拆出 NteRoleDetail/NteRoleDialog；NteRolesPanel 承载一级列表及既有图片模式。移除 GameCard 独立 guides 页签，保留探索及其他资产入口。
- [ ] imageMode 保留角色完整内容的静态展开，不能因为网站改为详情弹窗导致 QQ 空白；不修改评分模型，只保留入口。
- [ ] 通过定向测试后，一次桌面及窄屏查看列表、详情、切换和关闭；不要求用户再验收未改变的其他游戏页面。

    node --test src/nte-roles.test.js src/components/NteRolesPanel.test.js src/components/NteDialogs.test.js src/components/CharacterSearch.test.js src/components/IntegratedGameCard.test.js src/components/SharedRenderContent.test.js

### T5：攻略入口、目录覆盖与摘要核对（I06，配合 I07）

**Interfaces:** 继续消费 getGuideCatalog/getGuideSource；保留 reviewed/original_only、source_id、version、pages、reviewed_at 及来源变更提示。

- [ ] NteGuides.test.js、guide-search.test.js 增加：目录由 catalog 驱动、5 名摘要不等于仅 5 名目录、搜索可到非首屏角色、无摘要有原图入口、目录水平溢出可发现、无来源的新角色有缺口说明。
- [ ] 不再使用固定 5 人数组作为一级覆盖依据；在整合后的公开攻略区保留完整搜索和明确数量说明。新增角色不能因“未收录攻略”而消失于本人角色列表。
- [ ] 对现有其余 18 项逐条核对原图页、版本和五类内容，在 nte_guides_catalog.py 整理可证实摘要；来源不可读/信息冲突的条目保留 original_only 并逐项记录原因。不得将未完成项标为“已修复全部摘要”。
- [ ] 覆盖目录与持有角色不同形态、最新版新增角色可能不在旧目录、原帖变化后的摘要待复核；不爬取无关站点或启动无人值守自动提取任务。
- [ ] 定向测试、攻略来源页对应关系抽查各一次；保留作者与原图水印。只有改动目录后端数据才运行攻略 Python 专项。

    node --test src/guide-search.test.js src/components/NteGuides.test.js src/components/NteDialogs.test.js

工作目录仓库根，目录数据发生修改时：

    .\.venv\Scripts\python.exe -m pytest tests/test_nte_guides.py -q

阶段 B 完成后请用户快速确认一次“鸣潮基准是否达到、异环攻略合并是否顺手”；相关实现不变则复用该视觉结论。到此已有多个独立功能，评估换窗并提供简短交接，不自动建新聊天。

### 阶段 C：资产图片及日历外观（T6 → T7，复用 T3 图片失败处理经验）

### T6：房产与载具图片（I08）

**Interfaces:** nteAssetImage(kind, id) 根据严格 ID 生成明确官方 CDN URL，摘要/详情共用；houseView/vehicleView 增加派生 image 值，不修改存储 schema。

- [ ] 新增 nte-artwork.test.js，在 NteAssetsPanel.test.js 补：真实样例 ID 正确、非法 ID 返回空、图片 404 fallback、已拥有/未拥有/未知三态不变、原条目信息不丢失。
- [ ] 审核通过后先逐项验证当前目录的图片可用性并记录覆盖表；本轮 4 张抽样不等于全覆盖。只做一次 GET/图片有效性检查，避免反复探测。
- [ ] 接入摘要和详情图片，采用稳定宽高比、按需加载与失败 fallback；不把通用房子图当成每个房产的真实图片，不用相似车型替代缺图。
- [ ] 文档记录 URL 规则、来源前端版本、条目覆盖及缺口。官方素材不复制进公开仓库；资源不可用仍可看名称、属性、入住和家具数据。
- [ ] 定向测试及一处房产、一处载具浏览器图片检查通过即可，不重新验证全部账号授权。

    node --test src/nte-artwork.test.js src/nte-charts.test.js src/components/NteAssetsPanel.test.js src/components/NteModuleCard.test.js

### T7：以终末地为基准统一日历（I09）

**Interfaces:** 保持 CalendarPage/VersionCalendarContent/CalendarTimelineContent 现有 props、select 事件和事件 ID；eventArtwork(event, snapshots) 仍只返回可靠匹配的候选 URL。

- [ ] 在 event-artwork.test.js、CalendarPage.test.js、CalendarTemplate.test.js、calendar-presentation.test.js 增加：三游戏同一结构；有图/无图/图失败高度一致；同源公告图可用；跨游戏、不同来源和不同版本不能串图。
- [ ] 用终末地现有活动条及截止卡为参考统一 screen 样式；图片失败仍保留固定结构，主题色区分游戏。保留开始未知/截止未知/预计/常驻开放及“待确认的时间”区块。
- [ ] 只有明确 URL 等价或同版本来源关系有证据时补 eventArtwork 匹配；否则使用中性底纹，不通过放松到“同游戏任选图片”补图。此项不能改事件日期来迎合布局。
- [ ] 验证版本、14 天、整月范围，三游戏筛选、横向拖动、跨月短活动、当前日期定位和详情来源；网站样式限定 screen，image 分支继续使用原有分页约束。
- [ ] 一次桌面及窄屏三游戏对照；用户一次确认基准。共享截图只做离线合成检查，不启动网关、不群测。

    node --test src/event-artwork.test.js src/calendar.test.js src/calendar-presentation.test.js src/components/CalendarPage.test.js src/components/CalendarTemplate.test.js src/components/SharedRenderContent.test.js

## 5. 必要验收与证据复用

| 时点 | 必做 | 不机械重复 |
| --- | --- | --- |
| 各任务 | 上述缺陷回归先失败后通过；改动差异和接口检查 | 其他无关模块测试、所有 Python 版本、已接受的其他真机流程 |
| 阶段结束 | 汇总受影响测试，一次 git diff --check；一轮必要代码审查 | 每个细步骤重新整支审查、相同输入重复构建 |
| 最终本地验收 | npm run build --prefix frontend；隔离预览完成相应页面及慢网/失败场景；检查无新控制台错误 | 不重启 8010，不接入线上 QQ，不导入真实抽卡、不回补真实历史 |
| 共享渲染受影响 | 一次受影响的真实离线 Chromium 角色/日历分页验证，覆盖首末内容、装备字段和续页；720 宽、页高不超过 1440、无遗漏；合成数据 | 不重跑旧云端资源压测，不发送 QQ 收图 |
| 后端未修改 | 复用 d2fcc5b 的原后端及部署验收为基线 | 不声称它能证明新前端改动；不补跑无关全量后端 |
| 后续若获发布授权 | 针对新提交查 CI、构建输入与哈希；复用仍有效的本地验收，补新版本健康/静态资源/保护检查 | 旧 CI success 不冒充新提交 CI；不把历史 Pending 恢复为待办，不原样重跑旧部署脚本 |

离线 Chromium 检查复用现有 tests/test_qq_browser_rendering.py 和 tests/test_qq_nte_role_rendering.py 中受影响用例；明确设置 QQ_RENDER_TEST_EXECUTABLE、QQ_RENDER_TEST_FONT。若用例因环境 skip，报告“未验证”，不把 skip 当通过。只在本次确实需要 Linux 特有行为且本地不能覆盖时，后续另行安排针对性环境验证；不把旧 d2fcc5b 的部署门禁当新版本待办。

性能验收采用同一环境的冷/暖对照及受控延迟用例：

- 受控延迟下，200ms 后已有加载反馈；15 秒模块超时、20 秒快照超时均可恢复，没有无提示无限空白。
- 快的能力先显示，慢或失败能力独立提示；成功为空才出现 0 或无记录。
- 同 scope 返回页面不因无关重读闪成空态；切 scope 后无旧用户数据，重试不创建后台采集任务。
- 如公网仍存在十几秒下载，报告保留其实际耗时和定位结果，不能仅凭加了 spinner 就宣称性能问题已解决；I01 需有对应瓶颈改进证据，否则保留未关闭。

## 6. 原始证据入口与当前授权

- 当前基线记录：.superpowers/pr16-release-20261018/final-acceptance.json。passed=true、CI success、outstanding_required_work=[]；该文件是本机证据，不提交公开仓库。
- 两轮已登录浏览器观察是问题现象依据；本计划编写时仅核对仓库和现有记录，没有重跑浏览器检查、测试、部署或群测。
- 房产/载具图片的来源入口为 https://webstatic.tajiduo.com/bbs/yh-game-record/index.html，当时入口脚本 assets/index-C32LCXjN.js。后续接入前核对版本，不猜新的资源路径。
- 已抽查例子：realestate/detail/bigword_l_1.png、realestate/detail/bigword_ll_2.png、verhicle/wide/vehicle008.png、verhicle/wide/vehicle007.png，均位于 https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/ 下；其中各一张浏览器解码成功。
- 没有把账号 ID、凭据、真实完整 payload、QQ 标识或操作脚本写入本计划。

## 7. 审核后才进入实施

- [ ] 用户确认第 1 节合并清单、2.2 的角色信息层级及其余 18 项摘要核对范围。
- [ ] 用户确认第 2.3 节日历“有图/无图同结构”的统一方向及阶段顺序。
- [ ] 默认建议由主代理在当前隔离仓库逐任务实施，阶段闭环只做必要审查；如用户选择代理，再按既有不超过 GPT-6.1-sol high 的约束执行。
- [ ] 当前仅交付此计划，不提交、不推送、不部署。审批意见并入计划后，再开始对应阶段。

计划自查：两轮问题均已映射到 T1–T7；正常空数据及未授权模块不误报缺陷；读取性能根因与来源模板关系仍要求证据；目录覆盖不冒充摘要覆盖；旧 API、账号隔离、QQ 图片和原服务保护均有验收项。未执行任何计划内产品变更。
