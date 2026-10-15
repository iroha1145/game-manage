# 云端看板与 QQ v3 发布记录（2026-10-14）

独立 API、QQ 和前端已一次发布精确产品提交 `1db2b1617b27fbdc5ad0d5db2b9bbc2a522000bd`。root 完成必要代码、测试、浏览器、字体验证及候选产物审查后，以 `root-reviewed-schema4-1db2b1617b27fbdc5ad0d5db2b9bbc2a522000bd` 放行迁移与切换。仅本地提交记录，未 push/merge。

本次包括一步绑定、三类活动查询、QQ v3 版式、网站本地界面及本人接口接线、公共攻略/地图服务和本人历史回补。产品源码经 `git archive` 从指定提交导出，未打包工作树中未提交的计划或验收文档。QQ 集成 314 项、前端 395 项及相关后端定向测试由 root 审查；本发布环节未重复全仓、QQ 回归或上游图片取证。业务与界面验收边界见 [v3 验收记录](cloud-qq-v3-acceptance.md)。

## 产物与候选环境

| 产物 | SHA256 / 验证 |
| --- | --- |
| 精确提交源码 archive | `a1f38f010dfbd238eadf5326a2fc8879394c39ce03c37db8219caff1d4e0ab25` |
| 前端 archive | `7e2e896fbb5a408d9a88e7f34ea3ca0fba9f48d028974d1a31de8d3c796ef5ae` |
| cloud `index.html` | `ff40385ede26c5e3bb9703560ed43cb8876ea60739e644541edccfe1adc8cc92` |
| 已安装 wheel | `9df4ac9ecc24361d8dbd6548d1571b89be9f1b9772ffc258fa26869011c6288d` |
| 源码字节核验 | 149 个安装 Python 模块与指定提交逐字节相同 |
| 离线依赖 | 52 个缓存依赖哈希一致，54 个安装包兼容 |

前端在独立导出目录执行 `scripts/cloud/build_frontend.py --frontend frontend`，180 个模块构建成功，cloud marker 已验证；既有大 chunk warning 保留。服务器仅使用既有锁定 wheel，无网络安装。新前端目录 `/opt/game-manage-cloud-trial/frontend-releases/1db2b1617b27fbdc5ad0d5db2b9bbc2a522000bd/dist` 保留旧版 4 个非 index 静态文件的原名与原字节，没有覆盖同路径不同内容的 immutable 资源。

一次真实字体脱敏长图验证使用精确 `424483a1d177e25752c1eddd87ac85083020811e` 的 v3 渲染源码、线上同字节 Noto CJK SC 字体（TTC face index 2）和既有公共 PNG。合成角色长图为 JPEG `1080×5342`、`943096` 字节、`0.312` 秒，`valid_reply_image=true`，满足 1 MiB、1600 万像素、8 秒预算。渲染无网络、无私人数据；不能作为真实 QQ 送图验收。

## 迁移、保留与上线结果

切换前 API 为 `6875e0ce4774a0692c3b7b8dd73472c7a21a32da`、PID `4153397`；QQ 为 `d8bf68e9d677a05afafd6316780f1a92a57b7720`、PID `4144927`；前端为 `a04e18d597ce4466884d7f7a96e8350a21b861dc`。只读核验确认 identity schema 3、QQ state `user_version=0`，运行配置的 identity/data/key 路径与固定备份路径一致。

发布先短暂停独立 backup timer，再停 QQ 与 API 两个写者。迁移前备份覆盖 identity、private、snapshots、已知 public 数据库和 QQ state，完成 manifest/完整性/当前密钥授权可读性验证后才迁移。schema 3→4 成功；users、sessions、invites、grants、accounts、roles、preauth_sessions、recoveries、identity_rate_limits、qq_links、qq_rate_limits 的既有行逐项保持相同；旧 pending 绑定退役，旧未消费绑定码撤销。已确认 QQ 关联保留。

配置仅更新 `runtime.frontend_dist`，两个服务单元仅替换 release 引用。原 QQ 环境、两群允许范围、外部凭据密钥、QQ 非数据库文件及全部 service drop-in 逐字节保留。图片仍为 images=true、1 MiB、URLs=false，字体和来源素材沿用既有配置。

| 检查 | 结果 |
| --- | --- |
| HTTPS `/api/health` | 200 / status=ok，第 3 次、4.081 秒就绪 |
| 新首页、JS、CSS、theme-boot.js | 4 个 GET 200，SHA256 与本地 cloud 构建一致 |
| 未登录 `/api/identity/me`、`/api/accounts` | 拒绝访问，无认证或上游采集 |
| API | PID `4180039`，active/enabled，NRestarts=0 |
| QQ | PID `4180076`，active/enabled，NRestarts=0，10 秒进程 guard 通过 |
| QQ 连接 | 仅检查当前 PID 的已知安全标记，`gateway_connected=true`，未输出原始日志 |
| proxy / LOLhelper / Caddy | PID `3624945` / `3151077,3151078` / `3682839` 保持不变 |
| 独立 backup timer | 恢复 active/enabled |

`backup.py`、`restore.py`、`local_pull_remote.py`、`bilibili_migrate_remote.py`、`nightly_backup.py` 已同步到既有 operator 目录，字节与精确 release 相同；schema 4 支持与新 public 攻略缓存 inventory 随本批保留。

上线后仅额外执行一次 v4 新备份与隔离新目录恢复：`identity_schema_version=4`、`v4_backup_validated=true`、`v4_isolated_restore_validated=true`、`credential_readability=verified`、`live_data_overwritten=false`。当前密钥能解密原有效授权，未输出明文、密钥或私人数据库内容，密钥未包含在备份。该运行中备份仍是 `per_file_online`，不是全系统一致快照。

## 回退与证据

回退材料根目录为 `/opt/game-manage-cloud-trial/operator/v3-1db2b1617b27fbdc5ad0d5db2b9bbc2a522000bd/`，包含 `cloud.previous.toml`、`api.previous.service`、`qq.previous.service`、`operator.previous/`、经验证的 `pre-migration/`，以及 `offline-migration-safe.json`、`api-ready.json`、`public-static.json`、`post-verify-safe.json`。v4 新备份与隔离恢复目录分别为 `post-v4-backup/`、`post-v4-restored/`，均不覆盖 live 数据。

旧程序拒绝 schema 4，回退必须离线恢复迁移前 schema 3 备份后再启动旧版本。迁移后、API 首次启动前发生失败可自动恢复，并保留完整失败数据库副本；API 已启动后的 guard 失败则停止 API/QQ，保留 schema 4，不自动覆盖可能的新用户写入。人工回退须 root 明确确认无新用户写入或完成数据处理，以 `root-confirmed-no-new-user-writes-实际SHA` 放行；恢复过程仍保留整个较新 live 目录、QQ DB 及 WAL/SHM/journal 侧文件，外部密钥和 QQ 非 DB 文件原位保留。本次未触发回退。

受限脚本与构建清单在 ignored `.superpowers/sdd/2026-10-14-qq-v3/`。没有修改、重启或迁移 LOLhelper/Caddy/proxy，没有主动 QQ 消息、真实绑定、注册或上游刷新。服务 active、连接标记与合成字体测试不代替新一步绑定、各业务查询、真实图片接收、第二名用户隔离或终末地真实私人数据验收。
