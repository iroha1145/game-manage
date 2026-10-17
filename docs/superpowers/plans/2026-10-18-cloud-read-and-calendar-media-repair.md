# 云端读取与日历图片修复实施计划（待审核）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after explicit user approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复鸣潮、异环网页读取异常与残留加载状态，降低公网活动读取负担，恢复可靠来源的日历图片。

**Architecture:** 保留现有云端账号隔离、缓存与采集边界，先修正请求生命周期并减少传输，再修正来源图片解析。活动响应随缓存返回轻量配图索引，使日历无需下载整篇资讯；图片归属仍由现有按游戏、公告和版本匹配的逻辑决定。

**Tech Stack:** Vue 3、Vite、FastAPI/Starlette、SQLite；复用现有依赖，不改变数据库 schema。

**Spec:** 本文件的“用户要求与约束”和“只读核实结果”为本轮修复依据；沿用 `2026-10-18-cloud-dashboard-repair-plan.md` 中日期语义、隔离和数据保护约束。执行入口为本文件，不重跑旧部署流程。

## 用户要求与约束

- 用户本轮仅授权核实原因、提交修复方案审核，暂不改产品代码、不部署。本文复选框均未执行。
- 唯一实施仓库：`C:/Zcode/game-manage-cloud-qq-public`，分支 `codex/cloud-qq-public`；当前 HEAD `fd5544f593647acf62baa0446180cf9209d53f2f`。
- 保留原配置、凭据、登录状态、私有数据、公开成功缓存和备份；不要求批量重新登录，不恢复或重建数据库。
- 不改主仓库/8010 主服务，不改云端 Caddy 配置、资源限额、鉴权策略或凭据；不推送、不触发 CI、不群测。
- 已通过的视觉布局和角色/攻略交互继续保留。本轮必要验收针对读取、传输及图片数据链，不重做无关视觉验收。
- 仍保留预计、常驻、缺失、历史版本和日期不确定性；不按图片、时间接近或跨游戏同名推断活动身份。
- 本轮只新增本计划文档；只读诊断运行于独立进程或现有页面，没有调用刷新采集 POST、修改云端文件或重启服务。页面正常定时 GET 和既有后台采集继续自行运行。

## 只读核实结果（2026-10-18 约 02:04–02:12，北京时间）

| 现象 | 已核实证据 | 判断与边界 |
| --- | --- | --- |
| 两款游戏“暂时无法读取” | 总览复现两款提示。鸣潮游戏页来源详情显示 9 项私有能力成功，公共资讯及活动均为“读取超时”；异环显示 8 项私有能力成功，角色、公共资讯、活动读取超时。 | 至少本次复现主要是网页 GET 传输超时，不能据此认定这两个授权都过期。后台另有历史异环 `auth_expired` 状态行，不以未对应的其他账号记录解释当前页面。 |
| 错误提示覆盖范围过大 | `overviewErrors` 对混合后的全部快照取任意错误；`friendlyDataError` 把读取超时转成“暂时无法读取”。 | 公共活动/资讯失败会连带把游戏卡标为“读取异常”，掩盖仍可用的账号和体力数据。 |
| 页面模块加载失败 | 鸣潮页控制台出现 `Failed to fetch dynamically imported module`，指向 `CloudGameCard-DRsh2zPQ.js`。该文件存在，服务器回环 HTTP 200，内容哈希一致；网页重载后可恢复模块。 | 不是已证实的漏文件部署。依赖下载慢/失败与 15 秒模块时限共同造成首开失败。 |
| 公网传输慢 | 必需的 `AnnouncementList-CzjBdB6K.js` 为 561,367 B；服务器回环读取 0.032 秒。Windows 直连公网，首字节 0.372 秒，25 秒仅收到 497,536 B，约 19,891 B/s 后超时。小模块回环 0.030 秒，同次服务器公网读取约 4.926 秒。 | 明确存在传输段耗时，不能用服务器计算快或重试恢复证明公网问题解决。带宽限制、丢包、线路抖动中哪项主导，本轮尚未确定。 |
| 传输负担 | 当前响应未启用内容压缩；携带 `Accept-Encoding: gzip` 的本机大 JS 响应仍为 identity，云端 Caddy 配置没有 encode。CloudGameCard 静态 JS 依赖合计约 849 KB，其中最大文件 561 KB。 | 可在应用范围内降低传输量，无需修改原 Caddy 配置。下列 gzip 数值是离线压缩估算，不是已实现的传输效果。 |
| 私有角色和公共响应大小 | 最新鸣潮角色缓存约 59,275 B → gzip 4,995 B；异环角色 234,265 B → 43,395 B。三款活动缓存约 48/52/17 KB → 2.8/3.2/2.1 KB；三款完整资讯约 136/237/56 KB → 20/42/16 KB。 | 角色页和日历均可从压缩获益。公共缓存计算仅 0.004–0.016 秒；这些数值不等于完整鉴权 HTTP 请求的耗时。 |
| 无关请求与重复请求风险 | `CloudApp.vue` 在非总览 dataKey 变化时无条件读私有能力；60 秒任务在日历/授权页也读私有快照；日历同时读三游戏 events + news，资讯响应包含全文。公共 GET 缺少进行中请求合并。 | 代码路径已确认存在额外流量；本轮没有浏览器完整网络瀑布，不编造实际重复次数。 |
| 长时间“正在读取” | 用现有 `createCloudDashboard` 进行一次无文件修改的合成调用：开始快照 GET → 同账号 initialize → 返回成功快照。结果 `readState=loading`、没有写入快照。原因是 initialize 无条件 `++epoch`，旧结果失效却没有结束对应加载状态。 | 生命周期缺陷已独立复现；不能声称实际页面每一次残留加载都由此造成。 |
| B站图片丢失 | 直接读取两款当前版本动态，均为 `MAJOR_TYPE_OPUS`，`major.opus.pics[].url` 是 `http://i0.hdslb.com/...`；`_body` 仅保留 https，故缓存图片为空。同一地址升级为 HTTPS，HEAD 均 200、image/jpeg。 | 不是来源完全没图，而是采集器丢图。异环封面约 466 KB，鸣潮封面约 2.15 MB，页面应延迟加载，不将大图放入 JSON 或构建包。 |
| 异环社区图片丢失 | 匿名读取官方资讯列表 5 条中的一条：列表 `images` 含 2 张 HTTPS 图片，但 content 无 img 标签，解析结果图片为 0；同帖详情 HTML 含 2 张 img。 | `parse_official_posts` 只解析 content，漏读结构化 images。无需为这类列表图片额外逐篇拉全文。该样例证明解析缺陷，不把社区宣传图当成当前版本封面。 |
| 鸣潮合并时图片丢失 | 原生公告缓存 15 条均有图片；合并后仅 3 条原生独立资讯保留图片。`merge_news` 两条 full 正文同 rank 时，不补入另一个来源的图片，即使已建立 original_links。 | 修复正文选择与图片保留相互绑死的问题；仅对既有可靠同文合并结果补图，不放宽跨文匹配。 |

图片来源核实入口：

- 异环官方版本动态：<https://t.bilibili.com/1251145718800842753>。
- 鸣潮官方版本动态：<https://t.bilibili.com/1253680342191046665>。
- 两个版本动态的 Opus 正文段落本次均没有正文图片，不能从作者头像、挂件、分享组件中取图。已确认的版本封面来自动态自身 `major.opus.pics`。
- 异环结构化图片样例：官方社区帖子 516712，公开 API `https://bbs-api.tajiduo.com/bbs/wapi/getPostFull?postId=516712`。
- 原部署记录：`.superpowers/dashboard-release-20261018/final-acceptance.json`。其中“真实缓存无可靠图片”的现象成立，但不能再沿用“来源本身没有图”的解释；本轮已经定位到解析遗漏。

## 优先级与实施顺序

| 顺序 | 优先级 | 交付 |
| --- | --- | --- |
| A | P0 | 修复读取生命周期和提示归因；应用内压缩；按页面组织读取、合并公共 GET；减小游戏页静态依赖。 |
| B | P1 | 修复 B站 HTTP 图片规范化、异环结构化图片、同文合并图片；制定并实现受控旧缓存配图补齐能力。 |
| C | P1 | 日历只读轻量配图索引，停止为配图下载整篇资讯；必要验收后提供本地检查版。 |

## Review Focus

1. 同账号定时初始化与快照回包交错：请求最终有状态，成功可见；切换账号、角色、授权版本或退出后旧数据仍不得回流（A）。
2. 日期成功但图片/资讯失败：日期和私有账号状态仍可用，提示指出失败能力，不把可用数据报成整体异常（A/C）。
3. 同标题/同数字 ID/同版本字符串出现在不同游戏或不同公告：图片不串用，未知保持中性（B/C）。
4. 历史缓存无图、来源返回空图或受限：不擦掉已有图片/正文，不更新虚假的正文采集时间，不触发全历史回补（B）。
5. 压缩、冷加载和慢速回包：数据解压等价、鉴权和缓存头不变；慢响应不产生卡死或无边界重试（A/C）。

## A：读取与传输（P0）

**文件范围**

- 修改：`frontend/src/cloud-dashboard.js`、`frontend/src/CloudApp.vue`、`frontend/src/cloud-display.js`、`frontend/src/components/OverviewPage.vue`。
- 修改：`frontend/src/components/GameCard.vue`、`frontend/src/lazy-page.js`（只调整必要的模块边界/可恢复加载，不改已验收布局）。
- 新增：`src/game_assistant/cloud_compression.py`；接入 `src/game_assistant/cloud_app.py`，复用 Starlette GZipMiddleware，不新增依赖、不改 Caddy。
- 测试：`frontend/src/cloud-dashboard.test.js`、`frontend/src/http-client.test.js`、`frontend/src/components/CloudApp.test.js`、`frontend/src/components/CloudCalendar.test.js`、`frontend/src/lazy-page.test.js`、`tests/test_cloud_compression.py`（新增）、`tests/test_cloud_boundary.py`。

**接口与决策**

- 分离初始化请求序号 `initializeGeneration` 与私有作用域 `epoch`。同一用户/账号的定时会话核验不再无条件作废快照读取；clear/退出/账号、角色或授权版本变化仍作废对应请求。旧 initialize 回包不得恢复已退出的用户。
- HTTP 读取上限继续为 20 秒，模块加载仍有明确失败出口；本轮不靠无限等待或全局调大超时掩盖问题。
- 将总览私有能力错误与公共资讯/活动错误分开，错误记录保留 capability、类别（timeout/network/HTTP/auth/source）与是否保留数据；界面使用固定中文，详情不输出任意 SDK 错误或凭据。
- 公共 GET 的进行中请求按用户代际、game、capability 合并；终止/失败后释放，不做跨用户长期内存缓存。
- 初始加载、路由切换与 60 秒读取走同一页面计划：日历不读取私有能力，授权/会话页不后台读取游戏快照；游戏页保留当前应显示的能力，总览不重复启动同一轮读取。定时任务增加重入保护。
- GameCard 对三游戏面板、攻略和目录改为按需引入，首开某游戏不强制等待其他游戏的大目录；保持共享渲染入口和路由兼容。若最大共享 chunk 仍包含必需目录，依据构建依赖图继续精确拆分，不改无关构建策略。
- `CloudReadCompression`（新 ASGI middleware）只压缩云端 `/assets/` 文本资源、已有公共 games GET 和授权快照 GET 的成功响应。阈值 1 KiB，gzip level 5；不压缩图片/字体、身份/CSRF、写请求或流式/范围响应。放在 CloudBoundary 内，仍由其鉴权与缓存策略包围。保留 no-store、静态 immutable、Vary、MIME，并正确处理压缩后的长度/ETag；不开放任何新路径。

- [ ] 先加入上述 initialize 交错回包回归：同作用域成功不残留 loading；另覆盖退出、切角色、授权版本变化及晚回包不得写回。
- [ ] 加入“只公共活动/资讯失败而私有能力成功”的提示断言；真实私有 auth_expired 仍显示重新授权，timeout 不显示授权过期。
- [ ] 加入页面读取矩阵、公共 GET 合并、定时任务不重入的调用断言；不得新增采集 POST 或失败后的自动轮询风暴。
- [ ] 实施最小生命周期/读取安排与提示修正，运行这些定向测试。
- [ ] 接入压缩并验证 GET 解压前后内容相同，未接受 gzip 时保持原行为，未登录仍 401，HEAD/304/范围响应和缓存头不被破坏。
- [ ] 根据实际 cloud build 依赖图拆分 GameCard 首屏依赖，构建通过；比对压缩前后体积，确认鸣潮首开不引入异环/终末地非必需目录。

## B：来源图片与旧缓存（P1）

**文件范围**

- 修改：`src/game_assistant/sources/bilibili.py`、`src/game_assistant/adapters/neverness/tajiduo.py`、`src/game_assistant/sources/article_content.py`、`src/game_assistant/sources/public_content.py`。
- 如需旧记录定向补图：修改 `src/game_assistant/sources/bilibili_service.py`、`src/game_assistant/sources/bilibili_store.py`。
- 测试：`tests/test_bilibili_source.py`、`tests/adapters/test_tajiduo_parse.py`、`tests/test_article_content.py`、`tests/test_public_content.py`、`tests/test_bilibili_store.py`、`tests/test_bilibili_integration.py`。

**接口与决策**

- 统一提取明确的图片字段，处理字符串、`{url}`/`{src}`、协议相对地址；去重并拒绝非法 URL。B站已实测的 `http://i0.hdslb.com/` 规范化为同 host/path 的 HTTPS；不对任意 HTTP 域名盲目升级，不把 HTTP 直接交给 HTTPS 页面。
- `_body` 继续读取动态自身 `opus.pics`/draw 图片；其他样式只有实测证明后才扩展。不得递归扫描整份响应，从头像、分享组件、挂件或广告抓图。
- `parse_official_posts` 合并 `images[].url` 与正文解析出的图片，保持原顺序、去重。此次图片修复不要求为每条公告增加全文 HTTP 请求。
- `merge_news` 仅在已经可靠合并为同一文章时独立补齐图片，正文 rank 决策不变；保留 original_links 及每张补图的来源链接（可选 `image_sources` 元数据），失败不清除旧图片。不同文章、不同版本不因同名强行补图。
- 只修解析器无法恢复窗口外的旧版本封面：新增 `BilibiliService.repair_cached_media(game, post_ids)`，只允许当前 source UID 已存在、且由当前版本 start_source/当前活动 source_post_id 引用的记录，每游戏最多 20 个，单轮并发最多 2，沿用来源节流；超过上限保留缺口。
- 定向补图通过作者/动态 ID 验证后，仅更新该记录媒体字段及 `media_revision/media_checked_at`；不改正文、活动日期、decision、版本、正文 fetched_at、history_complete 或源采集 last_success。读取失败保留已有资料，并给出媒体缺口状态。
- 不提高全局 RULE_VERSION 触发所有游戏全历史回补，不增加新的公开写接口。该能力先在临时库验收；本计划的本地实施完成不等于已授权在云端执行补采。

- [ ] 用本次公开样例的字段形状加入失败回归：B站 HTTP URL 经批准域名升级、异环独立 images 字段、HTML/数组重复图片、非法 URL 和无图文章。
- [ ] 加入同文 full/full 场景的补图断言；正文仍按原优先级，来源链接可追溯，不同文不合并。
- [ ] 修正解析与合并，运行对应 Python 定向测试。
- [ ] 临时库验证旧缓存补图：只修改指定记录媒体，版本外记录不动，失败不清空，业务分类/日期/完整性元数据不变。
- [ ] 以两篇版本动态的真实公开封面做一次浏览器解码检查；同时核对原帖、游戏和版本。没有合法对应图片的活动继续使用中性底纹，不填演示图。

## C：日历轻量索引与必要验收（P1）

**文件范围**

- 修改：`src/game_assistant/sources/public_snapshot.py`、`src/game_assistant/accounts/query.py`（PublicQueryResult 新增可选媒体元数据）。
- 修改：`frontend/src/event-artwork.js`、`frontend/src/CloudApp.vue`、`frontend/src/components/CloudSnapshotStatus.vue`，仅按需要调整 CalendarPage 的媒体来源状态。
- 测试：`tests/test_cloud_public_sources.py`、`tests/test_public_content.py`、`tests/test_account_queries.py`、`frontend/src/event-artwork.test.js`、`frontend/src/components/CloudCalendar.test.js`、`frontend/src/components/CalendarTemplate.test.js`、`frontend/src/components/SharedDashboardRender.test.js`。

**接口与决策**

- events 响应增加可选 `artwork_sources: list[dict]`，每行只包含来源 ID/URL/原文链接、source、明确版本和图片 URL 字段；可选 `artwork_status` 表示媒体缓存的成功/缺口/失败。不包含全文、summary 或私有账号字段。
- 索引由同游戏现有 news/announcement/B站缓存生成，GET 期间绝不联网补采。媒体缓存读取失败仍返回已读取的日期；不得因图片索引失败导致 events 失败。
- `eventArtwork(event, snapshots)` 同时读取本游戏 events.artwork_sources 与已有 news/announcement，沿用明确来源链接及版本约束；没有该新增字段的旧快照仍正常工作。
- 日历首次加载每游戏只读一次 events，不再为配图并发下载三份完整 news。资讯页按需读取原接口；新增索引同样享受公共 GET 合并和压缩。
- 先显示日期，图片使用现有 lazy/失败退回，尺寸和布局不变；图片失败单独标注，不制造“活动读取失败”。

- [ ] 索引响应验证：不含正文/私有字段，未登录仍 401，GET 不触发采集；缺失/失败媒体不丢日期。
- [ ] 三游戏相同公告 ID/版本字符串的隔离测试，以及版本不符、错误 URL、404 图片和空图片回退测试。
- [ ] 入口测试断言日历只发三个 events GET；资讯页仍能独立读取全文；不因进入日历启动私有游戏请求。
- [ ] 构建候选 cloud/local 预览；使用去敏公开样例和受控慢响应，验证 15 秒模块/20 秒快照限制下有明确成功或失败状态，不残留 loading。
- [ ] 单次核对两游戏角色/总览和三款日历：账号/角色切换不串数据，旧成功数据保留，图片来自正确游戏/版本，来源详情明确区分失败层次。保留现有已通过视觉结论，不重复逐页群测。
- [ ] 对共享渲染只核对受影响的异步模块 ready 与分页回归；必要时各取一页角色/日历合成输出，不发送 QQ，不重跑既有全套 Linux 运维门禁。
- [ ] 跑受影响的定向测试、构建及 diff 检查，记录新证据及复用结论；交用户检查后停止，不自动部署。

## 必要验收边界与完成定义

| 验收 | 最低通过标准 |
| --- | --- |
| 生命周期 | 合成复现不再残留 loading；同账号正常回包可见，退出/切角色/授权版本变动的旧数据仍被隔离。 |
| HTTP | 目标成功响应接受 gzip 时确实压缩，解压结果相同；静态/私有缓存头和鉴权保持原行为；图片/身份/写请求无意外压缩。 |
| 传输负担 | 大 JS/角色/活动 JSON 有实际 gzip 传输证据；每次日历最多三个 events GET，响应不携带整篇资讯；体积与当前基线比较。 |
| 慢速读取 | 使用一次受控约 20 KiB/s、300 ms 延迟的冷加载场景或等效响应分段复现；状态最终收敛，避免盲目扩大超时。若仍不能达到原超时预算，报告具体剩余依赖再调整方案，不无限重试。 |
| 图片 | 两款版本封面的 HTTPS URL 可解码并与各自版本动态一致；同文补图保留出处，跨游戏/版本不能串图；源端真实无图仍保留缺口。 |
| 旧缓存 | 临时库媒体定向补齐可用，不重置成功正文和采集元数据，不触发全历史回补；云端执行需未来发布授权。 |
| 用户检查 | 提供本地真实公开样例预览，用户只需快速确认两个版本图片和错误提示；此前已通过的布局无需再逐页验收。 |

本轮不运行全套旧门禁，不将离线带宽估算等同于真实公网验收。以后若获准发布，才补做发布特有的备份、保护与真实登录 GET 轻量检查；首次公网读取若仍失败，不以“重试一次恢复”作为全部通过标准。

## 执行时的定向命令

以下命令仅供批准后使用，本轮未运行这些门禁。Python 使用隔离仓库已验证解释器；node 命令从 frontend 目录执行。

- A 前端：`node --test src/cloud-dashboard.test.js src/http-client.test.js src/lazy-page.test.js src/components/CloudApp.test.js src/components/CloudCalendar.test.js`。
- A 服务端：`python -m pytest tests/test_cloud_compression.py tests/test_cloud_boundary.py -q`。
- B：`python -m pytest tests/test_bilibili_source.py tests/adapters/test_tajiduo_parse.py tests/test_article_content.py tests/test_public_content.py tests/test_bilibili_store.py tests/test_bilibili_integration.py -q`。
- C 服务端：`python -m pytest tests/test_cloud_public_sources.py tests/test_account_queries.py -q`；若 C 改到已在 B 验过的 public_content，才补跑受影响测试。
- C 前端：`node --test src/event-artwork.test.js src/components/CloudCalendar.test.js src/components/CalendarTemplate.test.js src/components/SharedDashboardRender.test.js`；若实际修改 OverviewPage，补其对应原有组件回归。
- 构建：独立子进程分别设置 `VITE_SERVICE_MODE=cloud` / `local`，执行 `npm run build -- --outDir ../.superpowers/read-media-repair/cloud` / `../.superpowers/read-media-repair/local`；不得覆盖现有 dist 或运行中的发布目录。
- 差异：`git diff --check`，确认仅批准文件变动。通过标准是定向测试 0 failed、构建退出 0、差异检查无输出；不把构建警告或模拟带宽结果伪装成真实公网验收。

## 当前状态与续接

- 方案待审核，所有实施任务未开始。当前云端仍为 fd5544f，API/QQ 未重启；本轮未修改配置、凭据或数据库。
- 公网具体慢因仍未定性到运营商线路/带宽限额/丢包；本计划先修已证实的状态缺陷、图片解析和传输放大因素。保留一项发布时的轻量公网观察，不先做机器扩容或网络配置变更。
- 若批准，按 A → B → C 在本隔离仓库本地实施，完成必要验收后先交用户检查。可直接以本文件和 fd5544f 部署记录换窗续接，无需复制完整历史或重复旧门禁。

## 后续授权

用户已批准 A→B→C 并明确要求必要验收完成后部署，覆盖本文原先的待审/再次检查后停止条款；仍保留保护范围、不群测和仅必要验收要求。实施与最终部署证据见 `docs/cloud-read-media-acceptance-2026-10-18.md` 及其运行态记录入口。
