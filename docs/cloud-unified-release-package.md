# 云端统一发布包与切换手册

2026-10-15：用户追加授权完成统一发布包后直接部署云端；允许必要的候选运行环境准备、备份恢复演练、安全切换和生产服务重启。朋友群真人验收后置，不作为部署前置；本轮不发送任何 QQ 测试消息。最终产物必须来自主任务确认的完整 40 位提交 SHA，覆盖日历和云端森空岛授权最终变更；工作树未提交内容不能混入产物。站内提醒保留，主动 QQ 提醒、主动订阅推送明确不实现，不是待平台验证或未来排期项。排行榜及原第二批已排除功能不纳入。

## 本地构建与产物

先完成适用回归，由主任务提交本批代码、打包脚本和本手册，再使用已确认的 SHA。示例 Python 是现有测试解释器，仅在新的忽略目录创建独立构建环境，不安装到该解释器或正式环境。

```powershell
& 'C:/Zcode/game-manage/.venv/Scripts/python.exe' scripts/cloud/package_release.py `
  --repo C:/Zcode/game-manage-cloud-qq-public `
  --commit <full-final-commit-sha> `
  --output-root .superpowers/cloud-skland-release/packaging/releases `
  --work-root .superpowers/cloud-skland-release/packaging/work `
  --npm 'C:/Program Files/nodejs/npm.cmd'
```

脚本通过 Git 导出该提交，排除仓库跟踪的历史 `.superpowers`，拒绝符号链接、私有路径、数据库、密钥、非示例环境文件、依赖目录和源码映射。新目录执行 `npm ci`，复用 `build_frontend.py` 显式构建 cloud 模式，并调用 `validate_dist`。后端通过隔离的 setuptools/build 环境生成 wheel，逐字节核对其全部 Python/JSON 源文件。失败保留独立暂存和日志，已有最终目录不覆盖。

| 产物 | 用途 |
| --- | --- |
| `game_assistant-*.whl` | 本项目后端；不含运行依赖、浏览器或字体 |
| `game-manage-source-<SHA>.tar.gz` | 该提交源码、锁文件、公开文档与模板；不含工作树私有状态 |
| `game-manage-cloud-frontend-<SHA>.tar.gz` | cloud 前端 dist，含 `index.html`、`render.html` 和构建资源 |
| `game-manage-cloud-operations-<SHA>.tar.gz` | 现有运维脚本、待审核模板与本手册 |
| `manifest.json` / `SHA256SUMS` | 提交/tree、构建平台、工具版本、锁文件及产物 SHA-256、未完成部署门槛 |

`releases/<SHA>` 是可交付包目录；同级 `work` 是本机依赖/日志目录，禁止上传或发布。清单是完整性和来源记录，不是签名，也不代表测试、Linux 或生产验收通过。Windows 构建平台必须如实保留。

## 部署前技术门槛

1. 在独立新 release 和 Linux 专用虚拟环境安装 wheel 的 `qq,qq-render` extra；用同提交 `uv.lock` 准备/复核兼容的运行依赖，记录实际锁定版本和 `pip check`。不要只修改源码假设已有 wheel 自动更新。
2. Playwright 固定 **1.58.0**，安装该版本匹配的专用 Chromium 与 Linux 系统依赖（准备阶段执行 `python -m playwright install --with-deps chromium`），禁止运行时下载。Browser 可执行路径和缓存位置必须对实际 API 服务用户可读可执行。
3. 准备有许可的中文字体，例如独立安装的 Noto CJK；核对 `qq_image_font_path` 的服务读取权限与真实中文字形。包不带 Windows 字体或 Codex 浏览器运行时。
4. **Linux sandbox 实测门槛**：本轮已修改 `BrowserRenderer._start`，Linux 显式设置 `chromium_sandbox=True`，Windows 保持已有行为；不提供无 sandbox 回退。必须以实际服务用户、AppArmor/namespace/systemd 限制验证 sandbox 有效，不添加 `--no-sandbox`，不全局关闭 AppArmor 或 userns 安全策略；Windows PNG 和 mock 测试不能关闭此门槛。
5. 核对实际 unit/drop-in，而非直接安装模板。先前只读证据：API **768 MiB / 128 tasks / 1 CPU**；QQ **192 MiB / 64 tasks / 0.25 CPU**。仓库模板配额不同，不能据模板推断线上。运行 `systemd-analyze verify`，测完整长卡、并发队列、超时/崩溃、关停，记录峰值 memory/tasks、CPU、OOM 和相邻服务健康后才决定配额。
6. 完成备份/恢复/迁移演练及技术边界检查后，按本轮授权切换和重启；真实云端本人授权/角色匹配/撤销、朋友群被动 QQ 回复与读图由后续真人验收完成。部署记录继续标明真人验收未完成，不发送任何 QQ 测试消息。主动 QQ 推送没有验收任务。

## 配置、备份和迁移

实际 config、EnvironmentFile、grants.key、identity/private 数据库和 QQ state.db 都保留原路径与权限，不复制到 release 包，不覆盖为示例，不读取秘密写入日志。运行时 frontend 和 QQ render dist 路径必须同时指向本次构建；不修改原本机 8010 服务或其他独立服务。

先记录运行 release、实际解释器/wheel、配置/unit/drop-in 的路径及受控副本、DB schema 与服务状态。现网先前观察到的 release 为 `1db2b1617b27fbdc5ad0d5db2b9bbc2a522000bd`，这是历史只读证据，切换时必须重新核对。

沿用 [cloud-operations.md](cloud-operations.md) 的真实路径和 backup/restore 工具，不新建迁移协议：

```sh
python scripts/cloud/backup.py --source <existing-data-root> --identity <existing-identity.db> --destination <new-backup-directory> --key <existing-external-grants.key>
python scripts/cloud/restore.py --source <new-backup-directory> --destination <new-isolated-drill-root> --key <matching-separately-restored-key> --live-root <existing-data-root>
```

工具使用 SQLite backup API 并核验已知 schema、文件清单、SHA-256、quick_check 和启用授权可解密；不复制活动 WAL/SHM。在线备份是逐文件一致性，不能声称跨库事务快照。最后切换备份必须经授权停止 API、QQ 和所有写入者后记录停写事实，再完成备份和恢复演练。QQ state.db 单独用 SQLite backup API 保存，其去重/传输状态不在中央 data backup 中；grants.key 独立受控备份，不与数据或公开包合放。

在恢复的新目录上，以新程序初始化/升级并验证 identity schema（当前 dispatcher 到 v4）、私人账本、提醒与个人评分等已知库，核对所有者、角色、授权版本和加密关联。新派生森空岛的 `_parent` 关联保存在 grant 密文元数据中，不需要新 schema；但旧 release 的 CredentialStore/AccountService 不认识父子授权联动。相同 schema v4 不代表回退时授权语义兼容：直接让旧版读取新库可能使派生森空岛在父鹰角授权撤销后继续可用。不要为森空岛手工删除旧 grant、修改密文或重置 DB。云端原库不是本地单用户导入目标；`migrations.offline` 仅在明确需要且已授权的本地迁移场景使用。

`cloud_runtime --check` 只核对显式配置、外置密钥与 dist，不打开 DB、不执行迁移，不可当作迁移演练：

```sh
<new-release-venv>/bin/python -m game_assistant.cloud_runtime --config <reviewed-existing-or-isolated-config> --check
```

先在新目录完成实际 DB 初始化/升级与恢复核验，并保留原库和备份原件。真实账号验证后置，由用户本人处理密码、短信、验证码及平台交互；确认本人鹰角派生森空岛、手动备用、角色选择、失败保留旧授权、换号/撤销后网页与 QQ 不可读旧资料。部署前技术检查不替代这项真人验收。

## 切换与回退（本轮已授权）

核对 `SHA256SUMS`、manifest 提交及每个归档成员，再解包到新的 `/opt/.../releases/<SHA>`。frontend 归档根即 dist，配置的网页与 QQ render 路径应指向它。不运行源码归档中的旧启动脚本，也不整份覆盖 Caddy、systemd 或环境配置。完成上述技术门槛及主任务最终代码/产物核验后，按实际服务布局切换，先 API 就绪及边界检查，再 QQ 就绪；不发送任何测试消息，后续用户真实入站消息按既有被动回复流程处理。原配置和 unit/drop-in 保留受控副本，增量候选不替换无关服务。

回退前停新程序及写入者，保留失败现场、新记录、nonce 和当前 QQ 去重状态。恢复旧代码/venv、旧 frontend 和与其匹配的 config/unit/drop-in；兼容性必须同时覆盖 schema **及父子授权语义**，不得只看 v4 相同就让旧版读取新库。优先将切换前停写备份和原外置密钥恢复到新的恢复目录，再让旧版指向该目录。旧版恢复库中的会话/授权须按切换前备份事实重新核对，保留新库待人工核对新增/撤销记录。

另一选择是先经审查、单独授权的专用迁移禁用新派生森空岛授权，核验全部关联不再被旧版读取后再回退；本轮不实现或运行该自动迁移，也不以手工改密文代替。禁止旧程序直接读不兼容新库，禁止自动混入新记录、删除/清空现有库或 nonce、恢复旧 QQ state 导致重放。新记录另行核对和人工导出后再决策。

回退完成后复核 API HTTPS 健康、匿名私有接口拒绝、内部路径公网不可达、QQ 服务状态、相邻服务健康；记录回退 SHA、库版本、丢失/待恢复记录范围和凭据可读性。回退演练与真实切换分别记证据，构建 manifest 保留构建时 deployed=false；另写部署证据，不篡改已生成的包或把真实账号/QQ 人验标为通过。
