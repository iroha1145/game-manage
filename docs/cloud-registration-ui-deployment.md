# 注册错误提示前端发布（2026-10-14）

前端已发布精确提交 `a04e18d597ce4466884d7f7a96e8350a21b861dc`。用户已确认失败输入的用户名不符合规则；本次把后端固定 `detail` 错误码映射为安全明确文案，并显示、校验 3–64 位英文字母、数字、下划线、点或短横线规则，不直接展示任意后端内容，也不泄露用户名是否已存在。

root 已审查变更与针对测试（前端最终 9 项及先前 21 项、后端 23 项通过）。工作树 frontend 与指定提交一致；既有 dist 未含 cloud marker，因此按现有依赖只补一次明确 cloud 构建，通过且保留既有 chunk 大小 warning。最终 `index.html` SHA256 为 `b738f4c010f766600baecec28a6712861d5616e6240ee6b43200df6a2dca9bda`。

独立静态目录为 `/opt/game-manage-cloud-trial/frontend-releases/a04e18d597ce4466884d7f7a96e8350a21b861dc/dist`。旧 762 前端的两个 hashed JS/CSS 原名、原字节保留，未改名覆盖 immutable 资源。配置仅 `runtime.frontend_dist` 变化；独立 API 代码仍 `6875e0ce4774a0692c3b7b8dd73472c7a21a32da`，仅一次停启以重建精确静态文件路由。

API PID `4153397`，HTTPS health 200/status=ok，第 3 次、`4.36` 秒就绪，NRestarts=0。首页、新 `assets/index-CFqKcWZr.js`（775648 字节）、`assets/index-DLGw--K5.css`（206916 字节）均 GET 200 且 SHA256 与本地构建匹配；新 JS 确认包含明确用户名规则与安全注册错误提示。未实际注册、消费邀请码、读取秘密或触发上游采集。

QQ 仍 d8bf、PID `4144927`，两群范围与全部环境覆盖未变。proxy PID `3624945`、LOLhelper 两服务 PID `3151077/3151078`、Caddy PID `3682839` 均未变；没有重启这些服务或修改身份库、授权、密钥及备份计划。

回退配置保留于 `/opt/game-manage-cloud-trial/operator/frontend-a04e18d597ce4466884d7f7a96e8350a21b861dc/cloud.previous.toml`，原 762 前端目录保留；失败路径恢复旧配置并有界验证 API 健康。本次未回退。受限脚本与公共构建清单在 ignored `.superpowers/sdd/2026-10-14-register-frontend/`。新注册文案和正确用户名的真人网页流程仍待用户刷新后验证；记录仅本地提交，未 push。
