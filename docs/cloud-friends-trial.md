# 第二名朋友的最短试用流程

范围：先邀请 1 名朋友，优先鸣潮、异环。网站邀请注册、用户范围查询和会话管理已实现；第二名真人尚未注册或授权，不能把合成双用户测试记成真人验收。24 小时服务观察的验收另见 [实现验收](cloud-implementation-acceptance.md)。

## 管理员生成邀请

管理员在自己的终端交互执行，下列路径适用于当前独立 trial 部署。现有 `identity-admin.toml` 是 Settings-only 配置，已经指向同一身份库；不得改用含 `[runtime]` 的运行配置，也不要重新执行 `bootstrap-admin`。

```powershell
ssh -t -i 'C:/GPT/LOLhelper/reki2.pem' -o StrictHostKeyChecking=yes ubuntu@111.229.64.119
```

进入服务器后：

```bash
release=$(systemctl show game-manage-cloud-trial.service -p WorkingDirectory --value)
case "$release" in /opt/game-manage-cloud-trial/releases/*) ;; *) exit 2 ;; esac
sudo -u game-manage-trial "$release/.venv/bin/python" -m game_assistant.identity.cli --config /etc/game-manage-cloud-trial/identity-admin.toml invite
```

本人输入管理员用户名和隐藏口令，取屏幕中的 `Invite code`，私下交付朋友。代理不代填、不记录口令或邀请码，不发送消息。邀请码单次使用，默认有效 48 小时；如果运行配置调整了有效期，以实际配置为准。无须共享管理员账号。服务器目前没有可用 `current` 发布软链，因此动态读取 API 的 `WorkingDirectory`。

## 朋友操作与验收

1. 打开 [公网站点](https://game.rekibot.cloud)，点「使用邀请码注册」。用户名为 3–64 个英文字母、数字、`_`、`.` 或 `-`，不区分大小写；自行设置 12–128 字符网站密码。网站密码与游戏社区授权分开。
2. 在「账号与授权」自行完成鸣潮、异环各自登录，密码、短信、极验或其他人机验证由本人处理。不要导入管理员授权或分享账号。核对「本人游戏看板」的数据、来源时间及失败提示。
3. 用第二个浏览器或手机登录本人网站账号，查询同一授权，确认授权复用正常。保持这两个会话创建时间不同，在一台设备的「网站会话」撤销另一台对应会话；另一台刷新后应要求重新登录。撤销当前会话也应立即失效。
4. 两名用户分别核对仅有自己的授权。交叉访问须另做状态码验证：由操作者用各自已登录浏览器读取对方同意用于本次验收的账号、角色和能力快照路径，预期 404；只记录状态码，不记录 Cookie、私有响应或原始角色数据。先在本人会话同一路径核对 200，再换另一名用户会话请求，两方向都验证。不要用不存在的路由测 404，也不要把账号列表不同当作交叉访问已通过。
5. 网页朋友试用达到下表要求后再记通过。2026-10-14 用户已明确授权接入本人管理的新朋友群；云端 QQ 允许范围现为 2 群，旧群保留，指定新群通过唯一标记发现后追加。新群网关已连接，“帮助/总览”真实回复仍待用户验证；未调整 QQ 平台权限，网站成功不代表 QQ 正式群或朋友隔离验收通过。继续扩大其他群需另行授权，见 [新群接入记录](cloud-qq-friends-group-deployment.md)。

```javascript
// 在各自登录的浏览器操作，填入对方同意提供的本人有效账号、角色和能力路径。
fetch('/api/accounts/OTHER_ACCOUNT_ID/roles/OTHER_ROLE_ID/snapshot/stamina', { credentials: 'same-origin' }).then(r => console.log(r.status))
```

| 项目 | 当前依据 | 两名真人还需记录 |
| --- | --- | --- |
| 独立网站身份 | 现有单次邀请及注册实现；合成身份测试 | 朋友注册成功；不共享管理员身份 |
| 独立社区授权 | 第一名用户鸣潮、异环已人工确认 | 第二名用户自行授权、各自真实查询 |
| 用户间隔离 | 现有按用户范围访问拒绝及合成测试 | 两方向对方账号请求 404；本人请求正常 |
| 会话撤销 | 现有会话 API 和页面 | 第二设备撤销后请求失效；重登可恢复 |
| 手机访问 | 第一名用户手机流量人工确认 | 朋友手机访问及本人授权复用 |
| QQ | 既有测试群第一名用户绑定和同源查询 | 平台准许后第二名用户双向确认；各自被动查询一致 |

QQ 获准后，朋友在本人网站生成 10 分钟单次绑定码，在许可群中本人 `@机器人 绑定 绑定码`，回到网站输入本人 QQ 回复中的核对回执，再确认开放身份属于本人。两人分别发送 `/mc`、`/yh` 等已支持的被动指令，核对与各自网页一致。解除本人关联后该 QQ 身份应失去私人查询权限；不由代理主动发送测试消息。

## 密码恢复与试用收尾

目前有管理员 `recovery USER_ID` CLI 和 `/api/identity/recover` 接口，**登录页没有密码恢复表单**。本轮最短邀请流程不依赖它；朋友需妥善保存自己的网站密码。忘记密码时联系管理员生成一次恢复码（默认 15 分钟），本人完成恢复接口交互；恢复成功会撤销该用户全部既有网站会话。界面补齐和用户身份核验流程保留后续事项，不把已有 API 描述成完整自助恢复体验。

试用问题只记录时间、游戏、操作、错误提示和脱敏状态；不收集密码、验证码、邀请码、绑定回执或社区 token。试用结束可撤销网站会话、解除 QQ 关联并撤销游戏授权。不要自动删除源数据或将未经许可的私人数据打包给他人。

## 运维交付边界

运维准备及恢复规则见 [运维说明](cloud-operations.md)。自启工具为 `deploy/cloud/activate-trial-autostart.sh`，每日备份工具为 `scripts/cloud/nightly_backup.py`、`deploy/cloud/run-nightly-backup.sh` 和独立 backup service/timer。它们专用于现有 trial 路径与 unit，不直接套到其他部署。

2026-10-14 02:14（UTC+8），审阅后仅为 API、QQ、回环代理三个新 unit 安装自启 drop-in 并 enable，未重启服务或整机。首次受 systemd 资源和禁止网络限制的真实备份成功；新目录恢复 schema 3、启用授权实际解密通过，QQ 副本 quick_check 和哈希一致，恢复副本未启动，原库未覆盖、原密钥未复制。随后启用每日 backup timer，首次定时计划为当天 04:34（随机延迟后）。LOLhelper 两服务、原 Caddy 和三个新服务 PID 均保持；健康接口正常。每日自动执行及实际到期删除尚需后续运行证据，不能把首次手动备份视为长期已验证。

同机备份目录为 `/var/lib/game-manage-cloud-trial-backups`，root/0700；每天北京时间 04:30 加最多 10 分钟随机延迟，在线备份中央库和 QQ 状态库，最近 7 天及随后 4 周每周保留一份。整组成功发布后才清理，失败暂存人工检查。备份服务 root、UMask 0077、ProtectSystem strict、仅专用备份根可写、MemoryMax 192M、CPUQuota 25%、15 分钟硬超时，RestrictAddressFamilies AF_UNIX 且 IPAddressDeny any。密钥不包含在数据备份中。异机数据目的地已确认为本机 `C:/Zcode/game-manage-cloud-backups/data`；2026-10-14 首次真实拉取 9 文件、985029 字节，清单与哈希通过，重复检查未重新下载。当前用户普通权限的隐藏任务 `GameManageCloudLocalBackup` 已注册为每日 05:00 及登录触发，手动启动一次结果码 0；自然定时/重新登录补拉及长期运行尚未验收，离线不保证执行。详见 [本机备份证据与方案](cloud-local-backup.md)。经用户授权，独立 `key/grants.key.dpapi` CurrentUser 密文副本已保存且本机复核通过；服务器原密钥未修改，副本未加入日常数据拉取。重装/换机恢复方式与联系人仍需明确，当前用户 DPAPI 往返通过不能替代完整密钥灾难恢复或整机重启恢复验收。
