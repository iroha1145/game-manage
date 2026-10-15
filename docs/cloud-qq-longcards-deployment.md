# QQ 长图 v2 部署记录（2026-10-14）

当前 API 为 `6875e0ce4774a0692c3b7b8dd73472c7a21a32da`，PID `4153397`；QQ 保持 `d8bf68e9d677a05afafd6316780f1a92a57b7720`，PID `4144927`。QQ、其他服务及两群范围未变；前端已更新 a04e18d，见 [注册提示发布](cloud-registration-ui-deployment.md)。指定新群帮助已获用户确认；私人总览及新群绑定的真人流程仍待验证。

后端与 QQ 已从 `2f3fb350f3829c7fa39f14c170773ee203ca969a` 切换至 `d8bf68e9d677a05afafd6316780f1a92a57b7720`。前端保持 `762769f4e21bf34b5355ad108feeeeb33654fd3e`。安装 wheel SHA256：`9a17ce26acc4204f67bf089fc751a86d641fcb3bae9f6a476dd36c7f3fdff6b9`；新增素材模块、卡片、渲染、客户端、传输和查询模块均核对安装字节与精确提交源码一致，54 个依赖兼容。

上线前仅运行一次无网络合成 46 角色长图：现有公开 PNG、Noto SC TTC index 2；`valid_reply_image=true`，JPEG `960×4245`、`985107` 字节、耗时 `0.703` 秒，满足 8 秒、1600 万像素、1 MiB 预算。此结果不代表真实账号数据或 QQ 送图通过。

API 候选配置仅修改 `qq_image_max_bytes=1048576`；QQ 新增 `60-longcards-d8bf68e9d677a05afafd6316780f1a92a57b7720.conf` 及最后加载的图片专用 EnvironmentFile。无网络 Settings 预检确认两侧 images=true、maxbytes=1048576、URLs=false。API 保留 Noto SC 路径 `/opt/game-manage-cloud-trial/assets/fonts/noto-cjk-20230817-repack1-3/NotoSansCJK-Regular.ttc`；QQ 不渲染字体。原 secret 环境文件和 `50-images-2f3…` 文件保留。

API 一次停启后 HTTPS `/api/health` 返回 200 且 JSON status=ok，第 3 次检查就绪，耗时 `4.37` 秒；随后 QQ 一次停启并通过 10 秒进程 guard。API PID `4132496`、QQ PID `4132583`，均 active/enabled、NRestarts=0；这不证明网关连接或真实图片发送成功，需真人沙箱测试。

proxy PID `3624945`、LOLhelper dashboard PID `3151077`、sync PID `3151078`、Caddy PID `3682839` 均未变；backup timer active/enabled。原群范围、会话、grant、密钥、源缓存、数据库、autostart drop-in 原样保留；没有主动 QQ 消息、账号读取或额外上游刷新。

回退材料位于 `/opt/game-manage-cloud-trial/operator/d8bf68e9d677a05afafd6316780f1a92a57b7720/`：`cloud.previous.toml`、`api.previous.service`、`qq.previous.service`。脚本失败路径恢复 `2f3…` API/QQ，并仅移除本次 `60-longcards` drop-in，使旧 `50-images` 覆盖继续生效；此次未触发回退。受限本地脚本在 ignored `.superpowers/sdd/2026-10-14-qq-longcards/`。

切换完成后 root 发现图像超时文本回退可能修改仍在渲染线程读取的共享 card。经 25 项针对测试及两行变更审查，独立 API 已补发 `c5b8ea2d77890126419620324416184f3908c755`，文本回退使用新的卡片副本。安装代码与该提交字节一致，wheel SHA256 `4b6040e0151d6911dd738fd55f641b231cff55c0eb834810b965ff58624a33d0`，54 个依赖兼容。API 仅一次停启，HTTPS 200/status=ok 就绪第 3 次通过，耗时 `4.131` 秒；QQ PID 未变。此次全部配置、前端、字体、素材和其他服务保持原样，没有重复素材获取、长图渲染、全套测试、真实 QQ 消息或上游刷新。

API 小修回退独立保留 `/opt/game-manage-cloud-trial/operator/c5b8ea2d77890126419620324416184f3908c755/api.previous.service`，可将 API 恢复 `d8bf…`，无需修改 QQ 或配置。本次小修未触发回退，本地受限脚本在 ignored `.superpowers/sdd/2026-10-14-qq-fallback-api/`；文档仅本地提交，未 push。

随后仅 API 发布 `6875e0ce4774a0692c3b7b8dd73472c7a21a32da`，将未绑定查询显示为明确的独立提示卡片。26 项针对测试经 root 审查通过；部署未重复整套测试、素材获取或长图验证。安装源码字节匹配，wheel SHA256 `18365b93f2a07db7f4e3fcaeb9c0e6c7b65140f7a2696c5c988b56bba55237dc`，54 个依赖兼容。API HTTPS 200/status=ok 在第 3 次、`4.134` 秒就绪；operator 同提交目录保留 `api.previous.service`，失败可回退 `c5b8…`，本次未触发回退。

临时 QQ 入口观察已结束，QQ unit 与诊断前备份逐字节一致，额外写目录权限随原 unit 恢复移除；同 d8bf 代码短重启后确认当前 PID 的 `QQ gateway connected` 安全日志。原图片环境文件和 `70-friends-group` 两群覆盖保留；所有 API 配置、前端、字体、素材、源缓存、私有授权、密钥、备份和其他服务均未变。没有部署非数字 mention 的猜测修复；真实入口和绑定数量证据见 [新群记录](cloud-qq-friends-group-deployment.md)。


## 2026-10-14 用户实际验收

用户针对原沙箱群「鸣潮 角色」「我的总览」的收图与视觉检查回复：“收到长图，显示正常，风格可以”。本轮v2长图实际接收、正常展示及样式认可已通过用户验收；此前待用户反馈状态以本条为准。不扩大为全部指令、所有角色字段逐一核对、异环/终末地详情或第二名用户隔离已通过。评分功能仍不实施；正式群权限仍受平台发布状态限制。本次只记录验收，不部署、不连接服务器或重启任何服务。
