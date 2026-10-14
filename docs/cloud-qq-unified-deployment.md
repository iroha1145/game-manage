# QQ 统一指令与图片部署

2026-10-14 已部署 API 和 QQ 提交 `2f3fb350f3829c7fa39f14c170773ee203ca969a`，前端保持 `762769f`。本记录区分独立服务部署、合成 PNG 和真实 QQ 送图；真人沙箱验收仍待用户操作。

- 新独立 wheel 离线安装及 54 包兼容检查通过，query_routes、presentation、extras、rendering、client、commands、cards、card_rendering 等安装字节与该提交源码一致。wheel SHA-256 为 `5d38474b0cef2426893e129040bc92cf900b5abb35c5df4a15fac7d022da4a61`。
- API 配置图片启用、实际 Noto SC 字体路径及 512 KiB 上限；旧 wrapper 仅撤去图片禁用断言，URLs 禁用、单 worker、1/1 并发和 900/600 秒调度约束保持。QQ 从旧 `b5f327f` runner 独立升级，追加最后加载的图片专用 EnvironmentFile；原含密钥环境、群 allowlist、服务 token、state.db、grant 和备份计划未改动。
- 字体来自校验过 apt 元数据 SHA-256 的 Ubuntu `fonts-noto-cjk` 包，仅解包至独立 assets 并保留 copyright，未系统安装或运行维护脚本。使用 `NotoSansCJK-Regular.ttc` 的 SC index 2。一次禁止网络、纯合成的小卡片生成有效 PNG 26,349 字节，没有保存图片或读取真实载荷。
- 最终启动前两侧 Settings 检查：图片 true、URLs false、上限 524,288 字节；API 字体加载通过。QQ 仅传输服务器生成的图片，不在客户端渲染，字体配置为空符合该职责。初次 transient 预检因多 EnvironmentFile 路径兼容问题在执行前失败，业务进程未动；改为临时 oneshot 的两条指令后通过，未复制密钥内容。
- API 先一次停启并通过 HTTPS 就绪（第 3 次、4.129 秒），QQ 随后一次停启。API PID `4117391`、QQ PID `4117488`，均 active/enabled、自动重启计数 0；QQ 10 秒进程检查通过。该检查不证明网关 READY、心跳 ACK 或图片送达。
- 09:11（UTC+8）健康正常，匿名账号读取 401、内部路径公网 404，前端首页哈希仍为 `9c0f35c61d60b53be221613c9dbf2adfe4aabe51157f9040efa01979069d07b0`。原代理、Caddy、LOLhelper 两服务 PID 和旧根路径 302/404/302 保持，自启 drop-in 及备份 timer 保持。404 仅为既有根路径响应。
- 未触发回退。旧 API `762769f` 配置/unit/wrapper、QQ `b5f327f` unit/runner 保留；恢复旧 QQ 时移除新图片 drop-in，原环境仍为图片 false。去重状态库保持当前状态，不因回退丢弃新消息记录。未主动发送群消息、获取私人载荷或额外触发采集。

有限安全网关查询未获得直接证据，保留未验证，不继续翻日志。用户本人需在原沙箱群验证综合总览、鸣潮、异环及角色分页/详情的图片和文字回退；终末地暂无真实账号，继续保留待验证。没有扩大群范围、启用网址或主动推送。
