# 云端日历与五类 QQ 长图修复验证

本文记录源码和本地验证；基础修复已提交为 `9d30e00`，本轮紧凑布局源码待统一提交、发布。实际部署和 QQ 收图以独立发布证据为准。

## 最终行为

- 云端刷新 `#/calendar?game=nte` 后，在鉴权完成时自动读取公共活动。保留会话所有权、请求版本、登出与换用户晚响应丢弃保护。
- 时间轴不再被内部 flex 滚动层压到约 140px；完整内容不收缩，由 `.calendar-content` 统一滚动，游戏标签顶部对齐。版本、30 天、整月、14 天共用此布局。
- 来源状态默认折叠；版本只显示已知名称。活动条仅显示名称、活动类型、进行状态和剩余天数；去掉独立日期行、详细起止时间、阶段及跨版本文字。活动详情也不再直接显示冗长 `time_text` 和阶段；原数据仍保留，预计、常驻、未知语义和时间轴位置不变。剩余天数沿用已确认截止日期计算，不为未知日期造值。
- 网页与 QQ 共用紧凑活动模板。普通行高分别为 34px、36px；长标题自然增加行高，短活动的外置标签限制在时间轴内，并占用自身行高，避免覆盖邻行。
- 整页仅保留一个默认关闭的来源详情入口，集合状态和各游戏、版本来源说明合并在其中；QQ 不挂载该技术区。同类多游戏失败合并为一条友好提示，保留实际失败与已有活动语义。看板自然增高，网页时间轴滚动区至少 320px，不再被告警和详情入口挤成只有日期轴。
- 部分来源失败但仍有新鲜、实际贡献活动的来源时，不显示整体更新失败；来源质量留在关闭的详情中。只有非新鲜 fallback、旧活动或无可用活动时保留简洁失败提示，原始来源状态和活动数据不改变。空态与加载使用“活动”“正在读取活动”“等待活动更新”。
- `calendar / wuwa_role / nte_role / wuwa_gacha / nte_gacha` 五类共享出图全部复制同一 Vue 组件的完整 DOM，以真实内容高度生成一张长图。取消 2300px 分页、日历 30 天拆窗和每 12 条分组；`page>1` 明确超出范围。其他 legacy 卡保留原规则。
- 所有共享图在 PNG 超字节限制时，最多尝试 JPEG 90/85/80；保留原始 1080px 宽度与真实高度。超过实际 1MiB、16M 像素或 16000px 高度限制时明确拒绝，不裁剪、缩放或返回第一页假装完整。
- RenderQueue 仅透传两个稳定限额错误，其余异常及超时保留原 `None` 回退。查询回复在原授权复核后说明完整图片超限、未截断，并引导查看看板；单图标题不再带分页文字。

## 根因证据

初始日历路由在鉴权前已经是 calendar，鉴权恢复不改变 page，因此 `watch(page)` 未触发公共读取。真实云端 DOM 3162px 时间轴被压到约 147px；隔离 Chromium 复现 1649px→140px。QQ 另外四类也使用固定 2300px 分页，新增四类回归均先出现四页、修复后为一页。

## 基础修复验证记录

- 日历自身定向前端：36 passed。新增五类长图分页回归：`node --test src/render-pagination.test.js`，8 passed。
- 最新 fresh fallback 语义修正：`node --test src/components/CalendarPage.test.js src/components/CloudCalendar.test.js`，18 passed。新回归先复现错误红条，再验证 fresh 无整体告警、stale 有告警、活动不丢失、来源字段未改变且详情默认关闭。
- 先前真实 Chromium 浏览器链路：23 passed。新增共享小样本及非法第二页：7 passed；富字段 NTE 角色与大列表/抽卡整图：5 passed；鸣潮富字段角色整图另 1 passed；NTE 角色/抽卡超像素完整拒绝另 2 passed。均为各自独立定向命令，不混算为一次全量测试。
- 大列表整图验证包含首尾文本、所有 DOM 内容块、单页、实际图片尺寸、字节限制与浏览器上下文清理。160 个 NTE 角色与 400 条 NTE 抽卡的完整 DOM 被明确判定超像素限制，没有返回前 2300px。
- cloud 前端构建成功。隔离网页只调用身份、账号与 `/api/public/games/{game}/events`；四种时间范围均不再产生 140px 内层滚动条，来源详情默认关闭，无页面异常。

角色与抽卡下表记录基础修复当时的样本；后续统一主题与排版验收由主任务另记。

| 实际浏览器样本 | 完整图尺寸 | 大小 | 内容依据 |
|---|---:|---:|---|
| 三游戏日历（紧凑阶段、整页修复前） | 1080×2502 PNG | 681509B | 53 条真实原生官方/社区活动，61/61 DOM 块；不含 B 站合并的 4 条，不冒充线上 UI 57 条；随后 QQ 移除了来源折叠入口，最终发布图另验 |
| NTE 角色总览 | 1080×2773 PNG | 317059B | 21 个生产规模合成角色，首尾可见 |
| NTE 指定角色详情 | 1080×5494 PNG | 633398B | 单角色完整弧盘、套装、属性、6 个长技能与城区技能，8/8 DOM 块 |
| NTE 抽卡 | 1080×2876 PNG | 417064B | 40 条合成社区出 S 明细，首条与末条在同一图中 |
| 鸣潮抽卡 | 1080×4743 PNG | 368608B | 30 条五星、60 条逐抽合成明细，首尾完整 |

## 本轮紧凑布局验证

同一份 53 条公开原生输入包含 49 条有日期活动和 4 条时间待定活动。网页行高中位数/最大值为 34/34px，QQ 为 36/49.39px；时间轴高度分别为 1748px、1899.56px。两侧活动条详细日期行均为 0，外置标签跨行或越出轨道均为 0。额外 7 个边界样本覆盖左右边界、极短色条、长标题、未知截止、预计和常驻，最长标题自然增至 82px，文字越界仍为 0。核验使用实际 Chromium 文本矩形与行、轨道边界，不能只依赖 DOM 块数量。

- 前端定向命令：`node --test src/components/CalendarTemplate.test.js src/components/CalendarPage.test.js src/components/SharedRenderContent.test.js`，19 passed、0 failed。记录：`.superpowers/calendar-compact/frontend-focused-result.txt`。
- 真实 Chromium 命令：`python -m pytest tests/test_qq_browser_rendering.py -q -k 'complete_calendar or calendar_byte_limit' --basetemp=.superpowers/calendar-compact/pytest-minimal`，3 passed、26 deselected。包含完整单图、查询服务链路以及明确拒绝超字节完整图；记录：`.superpowers/calendar-compact/browser-focused-result.txt`。
- 当前指标：`.superpowers/calendar-compact/minimal-metrics.json`；完整图：`minimal-long.png`；网页截图：`minimal-web.png`；边界指标与截图：`synthetic-edge-metrics.json`、`synthetic-edge.png`。布局脚本为同目录 `verify_layout.py`、`edge_qa.py`，cloud 构建成功。

两份结果文件为本任务已成功执行的终端结果摘要转录，非完整原始日志；为避免重复回归，没有为补日志重新运行。前端回归后只移除了待定活动重复游戏名，最终浏览器构建已包含该改动。

前一版 56px 网页 / 112px QQ 行高、1080×6401 JPEG 图属于历史布局，保存在 `before-metrics.json`、`before-long.jpeg`。中间两行日期方案的 `after-*` 和旧 `threeway-*` 图片已被最终四字段方案替代，不作为当前验收材料。上述两项定向结果来自本轮独立执行，不能与历史套件数字相加宣称一次全量通过。

## 整页滚动预算补修

主任务在隔离本地预览 18010 的真实整页发现：`calendar-content` 可见高度仅 66.3px，完整时间轴仍有 1952px。原因是固定高度看板上方的多个失败提示与四行版本来源入口占满预算，内部 `min-height:0` 和 `overflow:hidden` 继续压缩内容。此问题与活动行几何无关。

修复将各版本元数据抽为 `VersionCalendarMetadata.vue`，放入页面唯一关闭的来源区；同类失败合并，未删除真实失败信息。看板改自然高度，内容区依据屏幕预算滚动且最小高度 320px，普通页面仍可向下滚动。活动四字段、原日期、行高与轨道位置未改。

- `node --test src/components/CalendarPage.test.js src/components/CalendarTemplate.test.js src/components/SharedRenderContent.test.js`：22 passed。原始输出：`.superpowers/calendar-compact/page-budget-frontend.log`。新增回归先复现多告警，再验证单告警、单关闭来源入口、各版本说明和活动保留；QQ 不再挂载来源技术区。
- 独占 cloud 构建成功，输出在 `.superpowers/calendar-compact/page-budget-cloud-dist/`，日志 `page-budget-build.log`；没有覆盖本地预览的 v1 静态目录。
- Chromium 整页使用相同 53 条公开活动并模拟保留活动的失败状态：768px 高屏幕内容区 338px，初始可见 7 行；600px 高屏幕内容区 320px，初始可见 2 行，页面正常滚动 184px 后可见 8 行。两侧仅一个可见来源入口、一个合并告警、日期独立行 0、行高中位数 34px、页面异常 0。展开来源详情不压缩时间轴。
- 最终整页指标：`.superpowers/calendar-compact/page-budget-metrics.json`；截图：`page-budget-768.png`、`page-budget-600.png`、`page-budget-600-scrolled.png`；原始输出：`page-budget-browser.log`；脚本：`page_budget_qa.py`。

以上为隔离 cloud 构建的整页验证；18010 新 v2 构建和真实整页验收由主任务统一执行，不能把旧 v1 页面当作新源码证据。本轮需要新的统一提交和发布产物。

## 输入与执行边界

长图完整指完整展示传入的缓存/归档数据，不能推导为覆盖账号全部历史。鸣潮 QQ 查询仍受现有 500 条读取窗口约束；NTE ledger summary 未加载逐抽记录时不补造记录。日历原生公开样本不含 B 站合并；图标未配置匿名缓存时使用占位。

证据在忽略目录 `.superpowers/calendar-hotfix/`：四种网页截图与 `cloud-calendar-metrics.json`、完整日历图及 `native-public-render.json`、`pytest-shared-accepted/` 长图样本、`shared-long-summary.json`、鸣潮角色样本 `pytest-wuwa-detail-accepted/`。脚本 `browser_qa.py` 与 `render_qa.py` 保留可复现输入路径和浏览器流程。

验证环境为 `C:/Zcode/game-manage/.venv/Scripts/python.exe`，并设置 `PYTHONPATH=src;.superpowers/task-01-deps;.superpowers/task-02-deps`；测试运行依赖放在隔离工作树，不向原虚拟环境安装。Chromium 为 `C:/Users/PublicUser/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe`，中文字体为 `C:/Windows/Fonts/NotoSansSC-VF.ttf`。

本报告证明 Windows 隔离 Chromium 下实际布局和完整出图；Linux 候选运行、生产部署、QQ 发送及群内读图验收由父任务另行处理。没有重复执行全量前端或全仓 Python 套件，最终合并回归由父任务统一执行。
