# QQ 公开图标素材

`src/game_assistant/qq/public_asset_catalog.py` 只导出前端目录的公开名称、ID、图片 URL，并保留源文件 SHA-256、更新日期和来源页。它作为 Python 模块进入 wheel，无需额外包数据配置。内容来自 `frontend/src/wuwa-icon-catalog.js`、`nte-icon-catalog.js` 与 `endfield-icon-catalog.js`，不读取快照、凭据、账户导出或本机私有图标目录。目录别名不等于唯一图片数量。

| 游戏 | 名称及 ID 键 | 来源 |
| --- | --- | --- |
| 鸣潮 | 角色 111、武器 123、声骸 199、套装 34、属性 19、技能 644 | 库街区既有公开目录；详见 `docs/wuwa-guides.md` |
| 异环 | 角色 54、弧盘 106、套装 26、技能 418 | 塔吉多既有公开目录；详见 `docs/nte-icons.md` |
| 终末地 | 35 张干员头像，68 个官网 key / 唯一中文名键 | 2026-10-15 终末地官网公开资源的 avatar 映射；武器/装备/技能优先使用档案内审核域名 URL，无地址时占位 |

综合、鸣潮、异环、终末地各有一张本项目原创几何徽标 PNG，分别为网格、波形、环形闪电、工业六边形。它们不含文字，不是官方游戏美术或角色头像；创作者为 game-manage contributors，许可证 GPL-3.0-only。角色、武器和技能使用对应真实目录图片，缺图时由渲染器提供对应类别的语义 fallback。

`PublicAssetCache` 接口：`register_url(url)`、`ref_for(game, kind, id_or_name)`、`skill_ref(game, role_id, skill_name)` 返回不含路径或 URL 的 `qqasset_` 加 64 位小写 SHA-256 引用。种类为 `game/role/weapon/echo/set/stat/skill`；技能目录键为 `角色ID::技能类别或名称`。`prefetch(refs, budget_seconds=...)` 在查询的整体截止时间内预取，最大 5 秒；`get_image(ref)` 和 `fingerprint(ref)` 只读取内存，渲染线程不访问网络。

远程 URL 仅允许 HTTPS、443、无凭据、无查询参数、无片段，扩展名仅 PNG/JPEG/WebP；精确 host 为 `web-static.kurobbs.com`、`prod-alicdn-community.kurobbs.com`、`webstatic.tajiduo.com`、`bbs-upload.tajiduo.com`、`web.hycdn.cn`、`bbs.hycdn.cn`，均由官方页面或既有真实图标来源确定。全部 DNS 结果必须为全球可路由单播地址，随后使用该 IP 直接建立 TLS，原 host 用于 SNI 和证书校验，防止 DNS 检查后连接再次解析。请求不使用代理、账号认证、Cookie 或重定向。

默认并发 6、上限 8；整个缓存最多 80 个在途任务、2048 个已注册 URL。单次下载最大 2 MiB，响应头最大 16 KiB，DNS 至完整响应最大 5 秒；拒绝压缩响应、重复响应头、未知内容类型、SVG 和动画。解码前检查最大 400 万像素，重采样至最长边 192，重新编码无元数据 RGBA PNG。内存缓存默认 128 张、16 MiB、TTL 一小时；上限 256 张、32 MiB、TTL 一天。失败缓存 30 秒、最多 256 条，超时取消本次持有的连接；成功图片保留，后续请求只补缺失图。没有磁盘缓存。

`scripts/cloud/probe_public_qq_assets.py` 仅测试八个固定、目录内明确存在的鸣潮/异环角色、武器、技能及终末地头像 URL，再导出四张原创徽标及 manifest。需指定全新专用输出目录，不接受任意 URL 参数、不执行 SSH、不修改服务、不请求账号上游。本机 DNS 存在非公网/FakeIP 回答时，生产安全规则将拒绝抓取；这不等于官方 CDN 在正常云端 DNS 下不可用。公开素材预览不构成私人账号数据或 QQ 实际送达验收。

## 终末地核验记录（2026-10-15）

- [终末地官网](https://endfield.hypergryph.com/) 的 `6753-58bf72aace2b00ef.js` 明确用 `avatar:D[key]` 映射 35 个干员；`layout-5e0d6ffb320689c2.js` 的简体中文语言表提供对应名字。仅静态提取名称、官网 key 和 URL，没有执行下载脚本或复制页面实现；两个来源文件 SHA-256 存于前端目录 `sourceHashes`。
- 官网 key 不是游戏内 `char_id`。名称回退仅使用完全一致、唯一的中文名；`管理员` 对应两个头像，因此不建立泛名别名，不凭角色 ID 后缀猜性别。
- [森空岛终末地工具](https://game.skland.com/endfield) 的公开页面与模块使用 `bbs.hycdn.cn` 静态图片。真实下载核验：佩丽卡、祀各为 120×120 PNG，森空岛站点图标为 64×64 PNG，均通过现有图片清洗器。此举验证地址与格式，不表示所有武器和装备地址均已逐一验证。
- 本机生产缓存探测为公开图 0/8、原创徽标 4/4；固定佩丽卡 URL 返回 `qq_asset_dns_private`，符合本机 DNS 返回非公网地址时的拒绝规则。未放宽 DNS 校验。另用已核验的公开 PNG 离线加载缓存生成合成账号预览，检查真实头像排版；云端实际下载与 QQ 送达仍需现有运行环境验收。
