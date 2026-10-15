# QQ 公开图标素材

`src/game_assistant/qq/public_asset_catalog.py` 只导出前端目录的公开名称、ID、图片 URL，并保留源文件 SHA-256、更新日期和来源页。它作为 Python 模块进入 wheel，无需额外包数据配置。内容来自 `frontend/src/wuwa-icon-catalog.js`、`nte-icon-catalog.js` 与 `endfield-icon-catalog.js`，不读取快照、凭据、账户导出或本机私有图标目录。目录别名不等于唯一图片数量。

| 游戏 | 名称及 ID 键 | 来源 |
| --- | --- | --- |
| 鸣潮 | 角色 111、武器 123、声骸 199、套装 34、属性 19、技能 644 | 库街区既有公开目录；详见 `docs/wuwa-guides.md` |
| 异环 | 角色 54、弧盘 106、套装 26、技能 418 | 塔吉多既有公开目录；详见 `docs/nte-icons.md` |
| 终末地 | 35 张干员头像与 35 张人物图，两类各 68 个官网 key / 唯一中文名键 | 2026-10-15 终末地官网公开资源的 avatar / portrait 映射；武器/装备/技能优先使用档案内审核域名 URL，无地址时占位 |

综合、鸣潮、异环、终末地各有一张本项目原创几何徽标 PNG，分别为网格、波形、环形闪电、工业六边形。它们不含文字，不是官方游戏美术或角色头像；创作者为 game-manage contributors，许可证 GPL-3.0-only。角色、武器和技能使用对应真实目录图片，缺图时由渲染器提供对应类别的语义 fallback。

`PublicAssetCache` 接口：`register_url(url)`、`ref_for(game, kind, id_or_name)`、`skill_ref(game, role_id, skill_name)` 返回不含路径或 URL 的 `qqasset_` 加 64 位小写 SHA-256 引用。种类包括 `game/role/portrait/weapon/echo/set/stat/skill`；技能目录键为 `角色ID::技能类别或名称`。`portrait` 仅接受已审核终末地人物图目录，尺寸策略独立进入引用指纹；普通调用不能把任意公开 URL 升级为人物图。`prefetch(refs, budget_seconds=...)` 在查询的整体截止时间内预取，最大 5 秒；`get_image(ref)` 和 `fingerprint(ref)` 只读取内存，渲染线程不访问网络。

远程 URL 仅允许 HTTPS、443、无凭据、无查询参数、无片段，扩展名仅 PNG/JPEG/WebP；精确 host 为 `web-static.kurobbs.com`、`prod-alicdn-community.kurobbs.com`、`webstatic.tajiduo.com`、`bbs-upload.tajiduo.com`、`web.hycdn.cn`、`bbs.hycdn.cn`，均由官方页面或既有真实图标来源确定。全部 DNS 结果必须为全球可路由单播地址，随后使用该 IP 直接建立 TLS，原 host 用于 SNI 和证书校验，防止 DNS 检查后连接再次解析。请求不使用代理、账号认证、Cookie 或重定向。

默认并发 6、上限 8；整个缓存最多 80 个在途任务、2048 个已注册引用。单次下载最大 2 MiB，响应头最大 16 KiB，DNS 至完整响应最大 5 秒；拒绝压缩响应、重复响应头、未知内容类型、SVG 和动画。解码前检查最大 400 万像素，普通图重采样至最长边 192，审核目录内的人物图最长边 512，重新编码无元数据 RGBA PNG。内存缓存默认 128 张、16 MiB、TTL 一小时；上限 256 张、32 MiB、TTL 一天。失败缓存 30 秒、最多 256 条，超时取消本次持有的连接；成功图片保留，后续请求只补缺失图。没有磁盘缓存。

## 公开素材的解析器配置

默认 `qq_asset_dns_resolver = "system"` 沿用系统 DNS。本机代理提供的 `198.18.0.0/15` FakeIP 不属于公网，仍会被拒绝；程序不会在拒绝后自动切换解析器。运营者如需在这类环境下载公开素材，可在配置文件顶层显式设置 `qq_asset_dns_resolver = "cloudflare"`，或设置环境变量 `GA_QQ_ASSET_DNS_RESOLVER=cloudflare`。其他值、任意解析器 URL 均不接受。正常系统 DNS 可用的服务器无需更改。

`cloudflare` 模式仅将上述六个已审核素材主机的 A 查询发送到固定 `https://1.1.1.1/dns-query`，按照 [Cloudflare 官方 DNS JSON 接口](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/) 使用 HTTPS GET 和 `Accept: application/dns-json`。固定数字地址使用正常 IP 证书校验，不通过系统 DNS 解析解析器域名，也不使用环境代理、账号头或 Cookie；不会发送完整素材路径、账号接口或账号资料。它不修改系统 DNS 或代理配置。

DoH 响应限 16 KiB、32 条记录，检查成功状态、原查询名、A 类型、CNAME 链及所有 IPv4 公网单播地址，拒绝截断、关闭校验标记、压缩、重定向与无关记录。取得地址后仍由原下载器逐个检查全部答案，固定 IP 建立连接，以原 CDN 主机名执行 TLS/SNI 校验。DNS、CDN 握手和图片响应共享原有最多 5 秒截止时间。两种模式失败均按缺图回退，不尝试另一解析器；图片格式、像素、净化和缓存预算保持原限制。

2026-10-15 本机真实配装检查确认：武器、基质、四件装备、四项技能和战术道具均有合法官方 PNG URL，连同人物/头像共 13 个引用全部注册。系统 DNS 为两处终末地 CDN 提供 FakeIP，原下载器以 `qq_asset_dns_private` 拒绝。显式可信 DoH 与原下载器的单张武器图可达性确认后，使用生产 `PublicAssetCache(dns_resolver="cloudflare")` 从空缓存获取同一真实配装的全部13个引用，13/13成功，无手工素材注入；武器、基质、四件装备、四个技能、战术道具及人物/头像均显示在本地QQ成图。素材获取约2.004秒、渲染约0.251秒，1080×2159、209664字节。该账号本次成功不代表所有素材，也不代表腾讯平台已收图。按用户要求，后续解析器实现未追加或运行测试套件，真实QQ收图留给项目维护者在PR中验证。

`scripts/cloud/probe_public_qq_assets.py` 仅测试十个固定、目录内明确存在的鸣潮/异环角色、武器、技能及终末地头像/人物图 URL，再导出四张原创徽标及 manifest。需指定全新专用输出目录，不接受任意 URL 参数、不执行 SSH、不修改服务、不请求账号上游。本机 DNS 存在非公网/FakeIP 回答时，生产安全规则将拒绝抓取；这不等于官方 CDN 在正常云端 DNS 下不可用。公开素材预览不构成私人账号数据或 QQ 实际送达验收。

## 终末地核验记录（2026-10-15）

- [终末地官网](https://endfield.hypergryph.com/) 的 `6753-58bf72aace2b00ef.js` 明确用 `avatar:D[key]` 映射 35 个干员；`layout-5e0d6ffb320689c2.js` 的简体中文语言表提供对应名字。仅静态提取名称、官网 key 和 URL，没有执行下载脚本或复制页面实现；两个来源文件 SHA-256 存于前端目录 `sourceHashes`。
- 官网 key 不是游戏内 `char_id`。名称回退仅使用完全一致、唯一的中文名；`管理员` 对应两个头像，因此不建立泛名别名，不凭角色 ID 后缀猜性别。
- 同一公开 chunk 的 `portrait:T[key]` 明确提供35张人物图。佩丽卡与祀样本均为303×386透明 PNG，已下载验看并通过人物图清洗策略；详情使用人物图、列表使用头像，不把120像素头像放大为人物主视觉。未取得人物图时保留头像或明确缺图。
- [森空岛终末地工具](https://game.skland.com/endfield) 的公开页面与模块使用 `bbs.hycdn.cn` 静态图片。真实下载核验：佩丽卡、祀各为 120×120 PNG，森空岛站点图标为 64×64 PNG，均通过现有图片清洗器。此举验证地址与格式，不表示所有武器和装备地址均已逐一验证。
- 本机生产缓存探测为公开图 0/8、原创徽标 4/4；固定佩丽卡 URL 返回 `qq_asset_dns_private`，符合本机 DNS 返回非公网地址时的拒绝规则。未放宽 DNS 校验。另用已核验的公开 PNG 离线加载缓存生成合成账号预览，检查真实头像排版；云端实际下载与 QQ 送达仍需现有运行环境验收。
- 人物图迭代后，固定探测扩展至十张：公开图 0/10、原创徽标 4/4，仍为本机非公网 DNS 拒绝。记录位于 ignored `.superpowers/endfield-refinement/public-assets/manifest.json`；八类 QQ 排版预览位于 `.superpowers/endfield-visual-v2/qq/manifest.json`，后者使用核验过的公开文件离线装载，不绕过生产下载器。
