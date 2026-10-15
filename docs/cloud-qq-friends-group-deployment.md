# 指定朋友群接入记录（2026-10-14）

用户明确授权接入本人管理的新朋友群。云端 QQ 允许范围从 1 群追加到 2 群，原群保留；未扩大到其他群，未修改平台权限。群 OpenID 只保留服务器受限文件，未输出或加入仓库。

生产 runner 不支持热加载或安全发现，因此先启用独立于 SSH 的 230 秒自动恢复 timer，确认 active 后短停 QQ，再启动只收不发的临时 SDK 网关。平台 READY 后才请用户在指定新群发送唯一标记，监听 150 秒；临时进程完全停止后恢复生产，未同时运行两个网关。没有自动 QQ 消息或业务 API 查询。

窗口完整结束，脱敏结果为 `matched_groups=1/new_groups=1/old_group_matched=false`。首次收尾因 Python 尝试 chmod systemd 创建的 root-owned `status.log` 失败，先 fail-closed 恢复原 QQ、原范围。权限错误已复现，工具改为仅 chmod 自身创建文件；复用已完成的受限发现结果，没有重开窗口或让用户重复发送。以生产 runner 当前有效允许组核对候选严格等于旧组与唯一新组的并集，确认 `1+1=2` 后追加。

QQ 仅新增最后加载的 `70-friends-group-20261014.conf` 及 owner-only 组范围 EnvironmentFile；原 secret、图片覆盖、state.db 与旧组不变。重启失败路径撤销本次覆盖恢复旧范围；恢复 timer 和异常路径必须先 stop probe 并确认 PID=0，才可启动 QQ。结果目录独立于现有 QQ 状态备份目录。正常完成后两个恢复 timer 已停止。

接入完成时 QQ 为 `d8bf68e9d677a05afafd6316780f1a92a57b7720`，PID `4139945`，active/NRestarts=0；该 PID 的精确安全日志确认 `QQ gateway connected`。当时 API 为 `c5b8ea2d77890126419620324416184f3908c755`、PID `4134265`；代理、LOLhelper 两服务和 Caddy PID 均未变。接入未修改 API、前端、字体、公开素材、私有授权和密钥。

用户已确认新群“帮助”成功；“我的总览”和绑定指令仍返回帮助，需要诊断。一次 readonly SQLite 检查：近期 5 条状态均 sent，正文分类均 other；BotState 完成发送时会清空 text，因此不能据此判断回复类型。两个已批准群的有效链接分别 old=1/new=0；绑定请求状态 old={pending0, confirmed1, expired0, rejected0}、new 四项均 0。未读取凭证、原始日志或输出正文与标识，这些统计不否定用户实际操作。

同 d8bf 云端已安装 commands 字节与精确源码匹配；固定合成数字 mention 可解析 overview，非数字 mention 合成形式解析 help，但不能据此猜测真实入口。经授权临时 wrapper 原样委托生产 gate/runner，仅新群最多 3 事件、持久截止 5 分钟输出固定分类，不影响正常回复。一条真人“我的总览”入口明确解析 overview；前导数字/opaque mention、与 ready bot/app ID 匹配、零宽字符检测均 false，实际证据不支持 mention 导致该次帮助图。

现已发布明确未绑定提示 API `6875e0ce4774a0692c3b7b8dd73472c7a21a32da`、PID `4144753`；未发布任何 parser 猜测修复。QQ 原 unit 已从诊断前备份原样恢复，临时入口和额外写目录权限移除，仍使用 d8bf 代码及原所有环境文件、两群覆盖；PID `4144927`、active/NRestarts=0，网关连接安全日志已确认。原 unit 备份保留在 `/opt/game-manage-cloud-trial/operator/qq-entry-diag-20261014/qq.previous.service`。API readiness、回退与安装核验见 [长图部署记录](cloud-qq-longcards-deployment.md)。

新群绑定请求为何未进入记录仍待真人步骤验证；私人总览、图像发送、朋友独立网站绑定及隔离尚未完成验收。网关连接和进程 active 不等于端到端测试通过。一次性运维脚本及针对性测试保留于 ignored `.superpowers/sdd/2026-10-14-qq-friends/`，没有 push。


## 用户复验结果

2026-10-14用户确认“现在绑定成功了，总览查询也正常”。新群中现有用户绑定与总览被动查询通过人工验收；朋友独立网站账号及双用户隔离仍待验证。用户进一步提出绑定应跟随QQ账号、无需按群重复绑定；现有群维度关联为首期保守设计，跨群统一身份策略需单独核查，不把它表述为平台强制要求。本次仅记录结果，未更改绑定范围或服务配置。
