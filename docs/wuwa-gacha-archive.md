# 鸣潮离线抽卡档案

网页与 QQ 图片共用抽卡内容组件。逐抽总数/稀有度分布仅来自实际导入的逐条记录；mcgf/xhh 的五星周期和当前垫抽汇总存入独立表，不展开、不补三星或四星、不参与真实逐抽总数或保底。

## 导入与账号范围

本地路径 `/api/wuwa/gacha`；云端路径 `/api/accounts/{account_id}/roles/{role_id}/wuwa/gacha`，后续子路径相同。云端每次请求检查本人账号与授权，撤销授权后不能读取保留的历史。

1. POST `/preview`，文件参数为 `{records, source, latest_confirmed?, continuity_confirmed?}`；`source` 为 `json_import`、`mcgf` 或 `xhh`。授权链接参数仅为 `{url}`，只显式读取官方来源并产生预览，不写账本。
2. 核对数量、来源、警告及账号后 POST `/import`，参数仅为 `{preview_id}`。令牌绑定账号、区服、授权版本，十分钟失效且成功提交后不能重放；服务重启需重新预览。旧的 HTTP `{records}`/`{url}` 直接写入方式返回 422。
3. 文件每次最多 2 MiB、20000 条。UID 必须匹配；文件有区服时必须匹配，缺少区服的第三方摘要明确标记“按当前账号区服绑定”。同一显式流水 ID 内容冲突，整批拒绝；无 ID 的同秒相同记录按出现次数保留，重复导入幂等。

mcgf 按 `data.uid` 与 `data.card_analysis_json` 一级分区 `five_cards` 读取，不递归读取版本子统计。xhh 接收 `result` 本体的 `user_info.uid`、`gacha_record[].pool_type/records`。无名且 `idx` 为 int64 最大值（数字或字符串）是当前垫抽汇总标记。未知池/物品身份保留并诊断。来源自报周期数不按第三方 80 假设截断。没有在线 xhh 登录/签名实现或真实文件验收。

## 覆盖和用户规则

每次逐抽导入保存独立来源片段、流水引用、最新范围与连续性确认、来源时间和警告。用户确认仅证明其声明的本段范围，不证明完整账号历史；完全分离的片段不会自动拼成连续历史。来源已知缺口或失败不能被确认选项覆盖。自由文本警告转换为固定 `SOURCE_WARNING`，不持久化或回显潜在凭据原文。

POST `/rules` 接收 `{pool, hard_pity, reset_rarity:"5", version, sharing:"independent", basis:"user_configured"}`。仅支持明确配置的独立卡池五星重置规则，未核验官方规则，也不推断跨池共享或 UP 保证。规则、当前最新覆盖、连续性、排序/抽数语义均满足时，段内有已知五星重置返回 `exact`；没有重置锚点返回 `lower_bound`；缺依据/缺口/同时间先后不明等返回 `unknown`。保底表示导入时状态，并非实时账号状态。

## 查看与备份

GET 基路径支持 `limit=1..500`、`offset`，逐抽/五星/汇总列表各自分页，统计总数始终覆盖全部已导入资料。GET `/export?limit=1..20000&offset=N` 返回 `wuwa-gacha-archive` v1，保存记录、独立汇总、规则、来源覆盖与警告。`export_page.next_offset` 指向下一分段；超过 2 MiB 自动缩小分段。分段抽取记录降低覆盖声明并添加 `ARCHIVE_SEGMENTED`，重新导入不能靠勾选升级。SQLite 提交在 `BEGIN IMMEDIATE` 下重新检查冲突与整批写入。

QQ 当前读取最新 500 条逐抽/五星/汇总明细窗口，图片页码只分页这个窗口；画面明确列出窗口条数与全档案统计。窗口外明细通过网站分页或完整分段导出获取。用户/账号/授权元数据及原始流水引用不会进入渲染 DOM。
