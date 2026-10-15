# 稳定性观察与公网接入准备

状态：公网站点已按用户授权平滑加载，可信 HTTPS 和手机流量鸣潮/异环访问已验证。2026-10-13 01:52 +08 全部公共 news/events 单次验收后启用周期采集；01:54:49 启动有限24小时原生观察，首样本正常，旧站点健康与 PID 保持。没有开机启用或无期限 timer。当前尚无24小时稳定性结论；终末地用户账号验证待有账号时进行。

## 现状与证据边界

| 项目 | 当前结果 |
| --- | --- |
| API / 独立测试 TLS | 仅回环 `127.0.0.1:8020` / `127.0.0.1:8447` |
| 新 API、代理、QQ unit | active/running、NRestarts=0；static，未开机启用 |
| 旧 LOLhelper / Caddy | 本次检查 PID 与试运行基线一致；旧根路由状态仍为 302 / 404，404 只作前后对照 |
| 刷新模式 | 最新已验发布使用 periodic=True；worker/global/provider并发均1，私人900秒/公共600秒。手动模式历史结果不替代新周期模式稳定性观察 |
| 内存 / 磁盘 | 单次 Linux 样本 available 约 1168 MiB、swap used 78 MiB、根磁盘剩余约 39 GiB；不是容量结论 |
| 公网 Caddy | 实际版本 2.6.2；原进程监听 80 / 443；保留 `sync.rekibot.cloud` 和 `sync.rekibot.cloud:8443`，只追加 `game.rekibot.cloud` |
| DNS | 2026-10-13 01:04–01:05 +08，两个 DNSpod 权威服务器及 AliDNS/Google 外部递归均返回正确目标服务器 A，TTL600；没有 AAAA。此前 NXDOMAIN 已由用户添加记录解决，未使用 Windows fake-IP 作为证据 |
| 新 Caddy 片段 | 在服务器 2.6.2，stdin 加 `admin off` / `auto_https off` 后 validate 成功；没有加载到原进程，不是完整合并配置或 TLS 验收 |
| 完整公网候选 | 原配置受限备份、只追加新站点的完整候选已保存；真实 `caddy` 用户 validate 后，01:08 授权原子加载和平滑 reload 成功；可信证书服务器验证通过 |
| 公网边界 | 根页/health200、匿名401、internal及子路径404；错误 Host 未路由到应用，Caddy 空200，直达 API403，不宣称公网错误 Host403 |

主域名备案状态以用户确认的已备案为准。备份恢复另由服务器演练记录证明，不能用此表代替；生产前仍需数据备份、独立密钥备份及异机副本。

## 观察工具与人工命令

`scripts/cloud/observe.py` 仅单次运行，使用 Python 标准库，不安装组件，也没有循环或调度功能。它记录六个已知 unit 的状态、PID、重启计数、内存与 CPU 累计值、安全属性；主机可用内存、swap、磁盘与 load average；两个 trial 端口监听地址；指定私人目录的权限元数据；六个固定回环 HTTP 状态码。HTTP 不跟随重定向、不用系统代理、不读取正文或响应头，不请求已登录账户或游戏上游。

采集模式通过 `--collection-mode manual_only` 或 `--collection-mode periodic` 显式声明；省略时记为 `unverified`，不推断或继续写死手动。它是操作者对已核验运行配置的声明，工具不读取密钥/配置正文来判断。汇总保留各模式样本数，混合模式不能当同一模式的 24 小时结果。

不读取环境文件、配置正文、密钥、SQLite、QQ 消息、journal 原文或进程命令行。文件最长 8 MiB，达到上限报 `log_limit` 并保留已有样本；不自动轮转或删除。Linux 目录需本次操作者拥有且 0700，文件 0600，拒绝符号链接、硬链接及公开权限。建议 root 在独立 `/var/lib/game-manage-cloud-trial-observation` 保存；不要放在网站 dist 或世界可读目录。

先在仓库 PowerShell 执行一个**只读**样本（不保存、不启动后台进程）：

```powershell
Get-Content -LiteralPath scripts/cloud/observe.py -Raw |
  ssh -i C:/GPT/LOLhelper/reki2.pem -o BatchMode=yes -o StrictHostKeyChecking=yes ubuntu@SERVER_IPV4 'sudo python3 - sample --private-path /etc/game-manage-cloud-trial --private-path /etc/game-manage-cloud-trial-qq --private-path /var/lib/game-manage-cloud-trial --private-path /var/lib/game-manage-cloud-trial-qq'
```

同一命令添加以下参数会保存**一个**样本；本阶段未执行写入。最终目录可自动创建，父目录必须已存在，不接受共享目录。

```text
--log /var/lib/game-manage-cloud-trial-observation/samples.jsonl
```

汇总使用同一脚本 stdin，不在服务器安装或替换 release：

```powershell
Get-Content -LiteralPath scripts/cloud/observe.py -Raw |
  ssh -i C:/GPT/LOLhelper/reki2.pem -o BatchMode=yes -o StrictHostKeyChecking=yes ubuntu@SERVER_IPV4 'sudo python3 - summarize --log /var/lib/game-manage-cloud-trial-observation/samples.jsonl'
```

汇总区分 PID 变化、自动重启计数递增及计数归零，避免把人工 stop/start 漏掉。CPU 百分比只在 PID 和 boot ID 不变的相邻样本间计算，100% 对应一颗 CPU。`coverage_24h=true` 仅代表有序样本首尾覆盖至少 86400 秒、最大间隔不超过 600 秒；`stability_pass` 始终要求操作者审查，不自动给出稳定结论。缺失值保留 null，失败样本保留，不能删掉失败后重新计算通过率。

采样时 `/api/health` 的 `elapsed_ms` 是回环健康检查延迟，不是授权查询、QQ 回复、公网 TLS 或页面加载延迟。旧 sync 根路由 404 也不能当作同步业务通过。QQ 进程 active 不证明 gateway、heartbeat ACK、token 续期或业务回复；工具对此明确记录 `not_measured`。

## 有限 24 小时观察（已启动，待结束验收）

已按审查方案每5分钟采样一次、首尾覆盖至少24小时，最多289个样本。独立受限 transient 进程有截止时间，不创建 cron 或无期限 timer，只执行只读采样，不刷新游戏数据或发送 QQ 消息。

实际开始UTC `2026-10-12T17:54:49.468077+00:00` / 北京时间 `2026-10-13T01:54:49.468077+08:00`，末样本计划北京时间10月14日01:54:51，Python硬截止01:55:49，systemd外层最多再到约01:57:48。unit `game-manage-cloud-trial-observe-20261013T012533-7368cc76.service`，根目录 `/var/lib/game-manage-cloud-trial-observation/20261013T012533-7368cc76`；只记录 metadata，不运行应用调度器。首样本6个业务unit均active/NRestarts0，旧3 PID不变、健康302/404；这不等于24小时通过。

用户授权“单次公共 news/events 正常后启用周期采集与 24 小时观察”，root已确认两个前提并放行。原生有限 runner `scripts/cloud/observe_window.py` 实际运行模式为必填的 periodic；准备阶段 plan-only 没有启动。标准库实现最多289次：0秒首样本、每300秒一次、末样本在86402秒，Python硬截止86460秒；systemd 再以 RuntimeMaxSec86580 和 Restart=no 限制，没有无期限 timer 或开机启用。

运行使用新 root0700 的专用 tools/logs 目录、0600脚本与结果；独立受限 transient unit，MemoryMax64M、CPUQuota5%、TasksMax32、生产路径只读、仅logs可写，网络限制到回环。原 API/QQ/Caddy/LOLhelper 的 unit 参数不变。root 的 Codex heartbeat 只检查异常/完成并通知，与原生采样进程分开。

runner 生成 `window-plan.json`（实际UTC/+08开始及截止）、`samples.jsonl`（最多8MiB）及 `window-result.json`（停止原因、实际结束时点及汇总），均0600。采集异常写固定 `collection_failed` 样本并继续，不写异常正文；日志到上限或写失败立即退出，不删旧样本、不重试爆发。SIGTERM/SIGINT停止；操作者只停止独立 observer unit，不停止业务服务。若 systemd 强制截止/关机来不及写最终结果，以已有样本与 unit 状态判定中断，不能标通过，也不自动恢复或接续旧日志。

结束后可在独立tools目录执行 `python3 -B observe.py summarize --log <logs/samples.jsonl>`；覆盖时长、失败次数、内存/重启、安全边界与模式都要审查，窗口正常退出不等于稳定性通过。采样只读进程/HTTP元数据，QQ业务、授权查询和真实上游来源有效性仍依据各自验收；本轮不自动发消息或刷新游戏。

| 观察项 | 审查标准与动作 |
| --- | --- |
| 服务 | API、proxy、QQ 与旧 LOLhelper 均 running；任何异常退出、OOM、PID 改变或重启计数变化需查明；5 分钟采样可能漏掉短暂事件，不能声称无瞬时故障 |
| 资源 | 新服务不触发 MemoryHigh / MemoryMax；关注 CPU 持续接近配置限额、swap 增量、available 趋势；建议 available 持续低于 300 MiB 或磁盘低于 5 GiB 时暂停新增负载，由 root 判断 |
| 安全 | trial 端口保持回环；匿名/内部无 bearer/错误 Host 维持 401/401/403；新 unit 保持独立用户与既定沙箱，私人目录权限不放宽 |
| 旧服务 | 比较开始与结束 PID、重启计数、资源与 302/404 根路由基线；用户可额外确认 LOLhelper 实际业务，代理不触发旧同步写入 |
| QQ 功能 | 用户在开始、中段、结束按需发送 `/ww`、`/yh`，与网页本人的同源缓存比对；只记时点、成功/失败与耗时，不保存消息正文、用户/群 ID；不能自动发测试消息 |
| 自然续期 / 重连 | 保持原沙箱范围，等待自然事件并人工核对；未遇到事件就标未验证，不主动重启 QQ 制造结论，不开启原始 SDK 日志 |
| 网站 | 两用户、两设备验证身份隔离、退出撤销、来源日期与手动刷新；公网启用后手机流量验证，用户完成登录、短信与人机验证 |

之前手动刷新检查只证明当时模式；本次窗口明确观察**周期采集**模式，不能混用两个阶段的结果。

周期采集已按 root 审查方案启用：已授权范围、单 API worker/单调度器，`cloud_poll_concurrency=1`、`cloud_provider_concurrency=1`、`cloud_private_poll_seconds=900`、`cloud_public_poll_seconds=600`，保留失败退避与旧缓存；trial wrapper periodic=True，不另起应用 runner。新发布单次公共源验收后只重启 API 一次，其余 PID 保持；QQ 图片、网址及沙箱范围保持现状。自动采集后的长期资源和上游稳定性以本次未结束观察为准，异常由 root 判断是否切回 periodic=False，采样工具不擅自改服务。

## 公网 DNS 与 TLS 执行记录

A 记录已由用户添加，并通过上述权威和外部递归核验。以下字段保留作审查依据，无需重复添加。01:04 +08 只读复核原配置与受限备份 SHA 相同、完整候选 SHA 未变；原 Caddy PID3682839、active/running、NRestarts0。DNS 核验阶段没有 reload，随后经用户明确批准执行下述公网加载。

01:07:56 +08 再次核对配置无漂移及旧健康302/404/302；01:08:39 将完整候选在原位置原子替换、保留 owner/mode，调用原 unit `systemctl reload caddy` exit0。01:08:59 使用 Python 默认 TLS 链及主机名校验，`https://game.rekibot.cloud` 根页200、health200、匿名401、`/internal`及子路径404；证书为 Let's Encrypt YE2、SAN game.rekibot.cloud，有效期 2026-10-12 至 2027-01-10。原 Caddy/LOLhelper 三 PID 不变、active/running、NRestarts0，旧健康仍302/404/302。没有重启或改动 LOLhelper。

错误 HTTP Host 在 Caddy 未匹配路由返回200；根任务独立核对正文长度0且无 cloud marker，直达 API 的同样错误 Host 返回403。准确边界为“未路由到应用”，不把200当业务成功，也不宣称公网返回403；未增加全局或 SNI fallback。根任务另行检查正常站点不可信 Origin403。服务器侧可信 TLS 通过不替代手机流量真实登录和会话验收。

用户在当前主域名的 DNS 管理页面添加：

| 字段 | 值 |
| --- | --- |
| 主机记录 | `game` |
| 记录类型 | `A` |
| 记录值 | 当前同一服务器的公网 IPv4；与现有 sync 服务的目标服务器一致，由 root 私下提供现值 |
| TTL | 可先选管理页面允许的较短值，例如 600 秒 |
| AAAA | 暂不创建；只有已核验服务器 IPv6、路由及 80/443 到达才添加 |

添加 A 记录不代表公网已切换。完成后检查 DNSpod 权威结果及至少一处外部递归结果均指向目标；若本机走 fake-IP 代理，须用权威查询和手机流量交叉验证。错误 AAAA 可能把验证或客户端导向不可达地址。

正常可信 TLS 需要正确的公网 DNS、可从公网到达的 80/443、对应 challenge 路径及 Caddy 用户的证书存储权限/网络条件。当前原站点可用不证明新站点已签发；云安全组与主机防火墙仅在检查发现确有问题后另行审查，不开放 8020/8447。[Caddy 自动 HTTPS 文档](https://caddyserver.com/docs/automatic-https)说明证书自动管理的条件，实际以本机 2.6.2 验证和签发结果为准。

仅使用 `deploy/cloud/Caddyfile.fragment` 追加一个新站点。Host 明确传 `game.rekibot.cloud`，阻断 `/internal` 及子路径，反代仍是回环 8020。不替换原文件，不改 `sync.rekibot.cloud` 或其 8443 站点，也不升级 Caddy。2.6.2 已通过该片段隔离校验；先前 trial 发现该版本不支持 `persist_config off`，不要把新版本指令塞进生产合并配置。

合并前由 root 在受控目录保存原配置备份和候选，权限至少 owner-only；diff 只在服务器内审查，不把含 token 的原配置、JSON adapt 产物或完整输出写进报告。确认原站点块字节未变，新站点只有上述明确变更，没有全局配置改变、重复 host、通配 route 或内部路径绕过。配置引用的文件与权限需用真实 Caddy 运行用户核对。

对**完整候选**使用现有二进制 `caddy validate --config <candidate> --adapter caddyfile`；validate 会加载和 provision 模块但不运行配置，不能只用 adapt 成功替代。[Caddy 命令行文档](https://caddyserver.com/docs/command-line#caddy-validate)说明两者区别。当前 stdin `admin off` / `auto_https off` 校验仅覆盖片段，不要把这个测试全局块合入原站点。

完整材料已于 2026-10-13 00:15 +08 准备到服务器 `/var/lib/game-manage-cloud-trial-public-prep/20261013T001502-947c4bd3`：目录 root/0700，原配置 `Caddyfile.original`、候选 `Caddyfile.candidate` 及脱敏结果均 root/0600。服务器内断言候选完整前缀与原文件字节相同、余下仅两个换行和仓库新站点片段；原配置内容、owner/mode/mtime 未变。没有将这些含现有配置的文件下载或纳入仓库。

已用原 `/usr/bin/caddy`、真实运行用户 `caddy` 完整 validate，通过 exit 0。执行是一次性受限 unit（禁网络、生产文件系统只读、128MiB/CPU20%/30秒，结束收集），候选直接通过 stdin，未赋予 caddy 对备份目录的读取权。原进程状态/PID 一致；没有 reload。首次 `/dev/stdin` 路径权限阻断后，改用该版本原生 `--config -` 读取已打开的 stdin 成功，未放宽沙箱或生产文件权限。

已核对 [2.6.2 Validate 实现](https://github.com/caddyserver/caddy/blob/v2.6.2/caddy.go)的 `run(cfg,false)` 在 App.Start 前返回；HTTP 自动证书管理及 TLS.Manage 位于 Start。校验另外禁网，因此不能发出 ACME 签发请求；这不是已有或新站点的证书签发、DNS、路由或手机流量证明。正式切换前仍须复核原配置未漂移，并按批准窗口加载候选。

只有候选审查、DNS 与备份准备齐备，且用户明确放行公网切换后，才用原服务的常规 reload 方式载入；不要另启一个抢占 80/443 的 Caddy。随即以正常证书验证检查新 HTTPS 主页/health、匿名 401、内部 404、错误 Host 拒绝及来源日期，再检查旧 HTTPS 302 与旧业务，最后由用户用手机流量完成真实登录/查询。不用 `-k` 或浏览器忽略证书错误代替公网验收。

## 公网切回

若新站点/TLS/原服务检查异常，停止进一步开放；由获授权的操作者 validate 原配置备份后，用同一原 Caddy 服务 reload 回原配置，确认原站点与 PID/健康对照。保留隔离 API/QQ、回环 TLS 与 SSH 隧道入口，先恢复访问入口，不改业务数据库或停旧 LOLhelper。DNS A 记录可随后移除；DNS 缓存不会立刻清除，所以移除记录不能替代原 Caddy 配置回退。

若异常来自新 API 版本或数据，按 `cloud-operations.md` 的程序/库版本与备份恢复步骤单独处理，不让旧程序直接打开新 schema。没有执行公网 reload 就无需为本次准备做 Caddy 回退。

## 用户操作与单独确认清单

1. `game` A 记录已添加并核验；无需重复操作或向代理提供 DNS 账号、密钥。
2. 完整候选审查、备份准备和 DNS 核验后，已按用户批准窗口完成公网 reload 与服务器 TLS 检查。
3. 手机流量鸣潮/异环访问已由用户确认；两用户会话隔离等剩余验收按根任务记录处理，口令、验证码与人机验证由用户输入。
4. 周期采集与有限24小时观察已按用户授权启用，等待结束后审查汇总；root用独立Codex heartbeat跟进异常和完成，采样进程不会无期限运行。
