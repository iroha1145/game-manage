# 本机拉取云端数据备份

目的地为本机 NTFS 磁盘 `C:/Zcode/game-manage-cloud-backups/data`。本机在线且当前用户登录时，可拉取服务器最新的完整备份集合；用户离线时不保证执行，重新登录后可补拉最新一份。无需新增云端服务或存储费用。2026-10-14 已审查并完成首次真实下载、Windows 任务注册及独立 CurrentUser DPAPI 密钥副本；重装后的独立密钥恢复与完整异机灾难恢复仍未验收。

## 使用与边界

固定可信解释器为 `C:/Zcode/game-manage-cloud-qq/.venv/Scripts/python.exe`，从工作树运行模块。工具仅依赖 Python 标准库，不依赖测试环境的 `PYTHONPATH` 或其他项目包。备份运行位置应保持此工作树和解释器可用；迁移路径时须更新操作命令和任务配置。

```powershell
Set-Location C:/Zcode/game-manage-cloud-qq
# 默认只读 complete.json、manifest.json、文件名及大小；不读数据库字节、不打包或下载载荷。
.venv/Scripts/python.exe -m scripts.cloud.local_pull
# 显式下载最新集合，已存在同名有效副本只复核，不重复下载。
.venv/Scripts/python.exe -m scripts.cloud.local_pull --execute
```

SSH 固定使用 Windows 内置 OpenSSH、现有 `C:/GPT/LOLhelper/reki2.pem` 和 `ubuntu@111.229.64.119`，要求既有可信主机记录、`BatchMode=yes`、`StrictHostKeyChecking=yes`、禁用 agent 转发。远端仅通过非交互 `sudo -n /usr/bin/python3` 读取 `/var/lib/game-manage-cloud-trial-backups`；不会修改服务器、启动服务、删除云端副本或下载 `grants.key`。不会自动接受新主机指纹。主机信任、sudo 权限或网络不可用即失败，管理员需核对原因。

只选择名称符合时间戳规则且带成功标记的最新集合。未完成 `.pending-*` 不候选；损坏的已标记集合会阻止本次运行，不悄悄回退为旧备份成功。最多 4096 文件、2 GiB 解包数据、2 GiB 加 16 MiB 归档，元数据每文件最多 2 MiB；连接超时 15 秒、列表总超时 60 秒、下载总超时 15 分钟。超出限额需另行评估，不能自动扩大。

数据落地流程为：检查专用根及子树权限 → 拉到 `.pending-随机值` → 拒绝路径遍历、NTFS ADS、设备名、符号链接、reparse point、特殊文件、重复或大小写别名 → 核对成功标记、manifest、精确文件清单、大小、SHA256、列表与归档体积 → Windows 原子不覆盖发布。已存在同名副本通过哈希检查后只报告 `already_present`，不重复下载。暂存失败不发布、成功副本不覆盖；并发锁阻止两个拉取写入者。工具不执行本机保留清理，现有副本持续保留，磁盘不足即失败。

新建数据根禁用继承，仅当前用户、SYSTEM、Administrators 拥有完整控制。子项仅允许这三个主体的完整控制，并须由当前用户所有且允许当前用户访问；支持继承 ACL 和 Windows `mkdir(0700)` 生成的显式或受保护 ACL。该 API 的标准 OWNER RIGHTS 规则仅在 owner 为当前用户时按当前用户权限核验。额外主体、拒绝规则、其他所有者、reparse point、未知顶层文件会阻止继续，不修改已有 ACL 或删除原数据。脚本不需要管理员提权。失败暂存和异常中断留下的 `.pull.lock` 必须确认无运行进程后人工检查；只处理此专用根内的明确目标，不递归删除计算得到的任意路径。子树安全检查最多 65536 项；长时间积累后可由用户人工归档，工具不自行清理。

终端日志仅包含状态、集合名称、数量、体积和 `key_included=false`。失败统一 `local_pull_failed`，不会打印原始异常、SSH stderr、数据库行、社区授权或凭据。文件校验不打开 SQLite 查询或解密 grant；它验证传输完整性，不能替代 SQLite/schema/授权实际恢复检查。备份仍是 `per_file_online`，不是跨库同一事务的整机快照。

## Windows 计划任务

任务 `GameManageCloudLocalBackup` 已注册：每天北京时间 05:00（晚于云端 04:30 加最多 10 分钟备份窗口）和当前用户登录后触发，同一任务禁止并行。使用当前用户交互登录令牌、普通权限、不保存账户密码；Windows PowerShell 以 `-WindowStyle Hidden -ExecutionPolicy RemoteSigned` 启动 [任务入口](../scripts/cloud/local_pull_task.ps1)，由其从固定工作目录调用固定 Python 路径。网络可用才运行，最长 20 分钟，错过计划后可补跑；允许电池供电执行，脚本内子进程使用隐藏创建标志。进程执行策略参数不修改机器策略。不能使用随机 PATH 的 Python/SSH，不能注册为 SYSTEM，也不能把无登录会话的离线运行描述为保证执行。同名已有任务不覆盖。

登录补拉与每日触发均只查询最新集合，已有副本不重复下载。网络不可用可能延后执行。手动启动任务一次已取得结果码 0；每日自然触发、真实重新登录补拉、长期稳定运行仍需后续证据。这是本机部署任务，没有创建 Codex heartbeat/云端自动化。

## 独立 DPAPI 密钥副本

数据集合和日常拉取不含服务器 `grants.key`。用户明确授权后，独立工具 [local_key_backup.py](../scripts/cloud/local_key_backup.py) 已经将密钥保存为 `C:/Zcode/game-manage-cloud-backups/key/grants.key.dpapi`，与数据目录分离；密文 262 字节，CurrentUser DPAPI 加密及本机解密复核通过。

该工具经既有受信 SSH、BatchMode 和 StrictHostKeyChecking，从固定 `/etc/game-manage-cloud-trial/grants.key` 读取一次到本机内存；父链仅允许 root 或既定 `game-manage-trial` 所有的普通目录，禁止 group/other 写；密钥必须为该信任范围内所有、owner-only、单链接普通文件、32 字节，拒绝符号链接。传输最多读取 33 字节，任何额外输出或非零退出均拒绝，超时 60 秒。初始空 key 根 ACL 和服务所有权兼容检查的两次前置失败均未读取密钥；兼容修正后一次成功读取和保存，没有修改服务器密钥、权限、服务或 LOLhelper。

密钥原文仅用于内存加密和往返比较，应用缓冲区尽力清零；未写入明文临时文件、参数、环境变量、日志、聊天或哈希记录。key 根当前用户所有、禁用继承，仅当前用户/SYSTEM/Administrators；文件所有者和有效 ACL 复核通过。只写 DPAPI 密文暂存，核对落盘密文解密后才原子不覆盖发布；现有或异常文件均拒绝自动覆盖。该操作没有加入每日备份任务或数据归档，不会自动重新读取或轮换密钥。

```powershell
Set-Location C:/Zcode/game-manage-cloud-qq
# 只在本机复核现有密文与 ACL，不读取服务器或打印明文/hash。
.venv/Scripts/python.exe -m scripts.cloud.local_key_backup --verify
```

保存命令为 `--execute`，默认无参数只说明需显式操作；已有目标时在服务器读取之前拒绝。密钥更换和恢复需要另行处理，本工具不提供明文导出。

DPAPI `CurrentUser` 依赖原 Windows 用户及其 DPAPI 主密钥/恢复材料。同账号同系统的可用性不代表换机、重装、管理员重置密码后的可恢复性；单独复制 DPAPI 密文不能作为跨账户恢复方案。用户仍需选择独立可信的离线恢复方式及联系人，例如用户自行掌握口令的加密恢复包和受控离线介质。明确该方式并做新目录真实恢复演练后，才能宣称完整灾难恢复可用；本轮只确认当前用户可解密，未做授权数据库恢复。

## 本地验证

`tests/test_cloud_local_pull.py` 使用合成字节和真实临时 NTFS ACL，覆盖哈希错误不发布、路径/链接/别名拒绝、数量与体积限额、进程超时/非零退出、并发锁、默认元数据不读载荷及脱敏输出。传输进程测试为本机子进程，无服务器连接。它不替代首次真实下载、真实库恢复、密钥恢复、计划任务或离线补拉验收。

## 2026-10-14 部署证据

| 项目 | 结果与边界 |
| --- | --- |
| 首次真实拉取 | 集合 `20261013T204001Z-d7779ae6`，9 文件、985029 字节；标记、清单、大小和 SHA256 通过；原子发布，未下载密钥或删除云端副本 |
| 本机权限 | 根当前用户所有、保护 ACL，仅当前用户/SYSTEM/Administrators；子树所有者及允许主体通过；首拉前仅经专项授权收紧已核为空的专用根 |
| 重复校验 | `already_present`、相同集合/数量/体积，重算哈希通过，未重复下载；Windows OWNER RIGHTS 识别有真实 `mkdir(0700)` 回归，未调整已下载文件 ACL |
| 任务设置 | Interactive / Limited、Hidden 与隐藏窗口参数、IgnoreNew、PT20M、网络必需、StartWhenAvailable、每日 05:00 和登录两触发 |
| 任务运行 | 2026-10-14 07:53:49（UTC+8）手动启动一次，Ready / LastTaskResult=0；下一次每日计划 2026-10-15 05:00（UTC+8） |
| 测试 | 拉取专项最终 27 项通过；首次相关运维回归 92 通过、2 跳过、2 项既有依赖警告；无实际 SQLite/schema/授权恢复或密钥恢复验收 |
| 独立密钥 | `grants.key.dpapi`，CurrentUser / verified=true，32 字节原文只在内存往返，262 字节密文落盘；本机 `--verify` 通过，无密钥/hash输出，服务器读取成功一次 |
| 密钥测试 | 9 项合成 DPAPI/NTFS/管道限额测试通过；与 27 项数据拉取回归合计 36 通过。密钥专项在非 Windows 显式跳过，不伪装支持该平台 |

初次数据检查拒绝未保护的空根，以及重复检查拒绝 Windows 的标准 OWNER RIGHTS ACL，均发生在发布安全门槛处；没有据此放宽允许用户/组或 SSH 信任，也没有删除失败暂存。数据与 DPAPI 密钥副本已分离保存，完整重装/异机灾难恢复仍待验收。
