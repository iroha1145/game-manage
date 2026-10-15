# QQ 统一交互与卡片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. User approved implementation of the preceding in-chat design; continue without duplicate approval.

**Goal:** 综合总览与鸣潮、异环、终末地共用指令、数据卡片及文字回退，保持本人账号隔离。

**Architecture:** 缓存查询投影为有限、明确字段的卡片文档；同一文档产生文字和PNG。统一解析器和分页，不从消息触发登录或任意上游请求。沿用QQ上传、幂等、撤销检查、队列预算及失败回退。

**Tech Stack:** Python/FastAPI/Pydantic/Pillow，既有官方QQ SDK、SQLite及账号快照。

**Spec:** 用户2026-10-14提供的五张参考图及已确认的四类共用模板/指令方案。参考信息层级，不复制参考项目素材或布局。

## Global Constraints

- 用户指定 gpt-6.1-sol high 子代理开发，root仅必要审查；现有隔离worktree，不改主仓库，不push/merge。
- 不改动或重启LOLhelper、Caddy及其站点；独立API与QQ服务可分批更新并保留回退。
- 不实现评分、评级、排名、伤害估算或推荐配装；未知不可补零，装备缓存不冒充完整库存。
- 只查绑定用户默认账号/角色；终末地两种授权分开标识，不跨角色拼接。脱敏UID，不泄露凭据。
- 公共数据与私人数据使用同一模板但权限按现有边界。图片上传未获实测前不能称QQ图片验收通过。
- 真实QQ消息由用户本人发送，代理不主动群发；不扩大群allowlist，不开主动推送或任意链接。
- 现有测试命令：worktree .venv Python；PYTHONPATH=worktree/src;C:/Zcode/game-manage/.venv/Lib/site-packages。不可新装随机测试环境。

## Shared Card Contract

卡片是纯显示数据，禁止原始上游字典或URL直接送渲染器。renderer负责 `qq/cards.py` 校验及文字序列化；query负责构造。

文档字段：version=1，kind（overview/summary/list/detail/help/status），game（三游戏或all），title，subtitle，sections，notices，footer，page（可选current/total）。

section字段：title，fields（label/value字符串），rows；row字段：title、subtitle、fields（label/value）。空集合可省略。所有字符串、列表及总显示量有上限；文字/PNG共享页码、数据状态及更新时间。图片不使用评分色阶。

首期沿用安全无远程素材渲染，使用原创颜色、模块和游戏标识。角色头像如无已验证本地资源则使用统一占位，不将截图或不可信URL下载进渲染流程；真实资产接入范围单独如实记录。

## Review Focus

- 综合卡片包含多个授权：渲染完成后必须重验全部引用的grant版本和绑定身份，缓存按用户及全部快照指纹隔离。
- 长角色名/字段与长列表：明确分页和文字预算，无静默截掉页码或来源状态。
- 多种授权/未知字段：不猜数值，不把终末地寻访身份合成森空岛档案。
- 图片上传失败前可文字回退；发送结果不确定不得重复发送。
- 冷缓存、授权撤销、未知指令和超过末页均给出可执行提示，不自动开始第三方登录。

## Tasks

- [x] A：指令与查询。修改qq/commands.py、query_routes.py、client.py及新增presentation模块；综合/单游戏总览、三游戏角色列表/缓存详情、现有体力/探索/挑战/抽卡/公告/日历的能力适配；明确分页、帮助和不支持状态。保留旧指令别名与绑定流程。只用已存在本人范围缓存，新增接口由测试固定权限/撤销/预算边界。
- [x] B：共用卡片模型和Pillow模板。新增qq/cards.py、card_rendering.py；扩展rendering.py支持文档同时保留旧text兼容。总览、摘要、列表、详情与帮助同风格；内存缓存与硬像素/字节/时间预算，文字回退。使用合成数据输出至少三游戏与综合预览，root视觉检查一次，修明显问题即可。
- [x] C：集成验证。A/B各自定向测试后合并运行QQ相关回归；确认新parser字段过客户端/内部API、全部grant重验、身份隔离、分页和无评分。保存已实现/待验证清单，必要审查后提交。
- [ ] D：独立部署及沙箱验收。先读取QQ进程使用的实际release、图片开关与字体安全元数据；复用API发布流程，为QQ单独准备新runner release，不改凭据/状态库/批准群。图片配置与字体可用才启用；正确缺字体/上传失败降级。用户本人发送总览、三游戏和角色分页/详情指令，收集脱敏结果；终末地无真实账号仍保留待验证。

## Acceptance

本地测试/预览、云端部署/匿名边界、真实沙箱消息三类证据分开。图片或第二用户/终末地缺少真人条件时明确告知所需操作，不虚报通过。游戏资产图片覆盖有限如实说明，不以未验证远程图片扩大本轮范围。
