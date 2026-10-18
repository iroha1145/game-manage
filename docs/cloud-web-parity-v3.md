# 网站 v3 本地一致性矩阵

基线：只读 C:/Zcode/game-manage，HEAD 9b3f49ea44a0180dc4d5b9764d5ee665a85db86c。实现：C:/Zcode/game-manage-cloud-qq。网站直接复用现有 Vue 组件，没有按 QQ 截图制作总览。

| 模块 | 本地原行为 | 云端对应行为 | 数据来源 | 差异原因与处置 | 验证状态 |
| --- | --- | --- | --- | --- | --- |
| 应用壳 | 侧栏、游戏导航、主题、手机抽屉 | 同workbench/sidebar/main CSS、图标与主题变量；遮罩、inert、Escape、焦点恢复 | 网站会话与本人授权 | 网站增加会话/退出/QQ绑定；手机按本地行为收纳 | DOM书签/焦点测试；root桌面/390px合成浏览器检查通过 |
| hash导航 | 总览/game/calendar?game/accounts | 复用readRoute，增加sessions；恢复前进/后退与刷新书签 | URL与本人授权 | 游戏只能选择本人授权，未知游戏不能读取其他账号 | 合成书签及日历游戏筛选通过 |
| 首页总览 | OverviewPage原卡片、公告、临近截止 | 原组件；每游戏单授权和默认角色 | 本人snapshot与公共快照 | 终末地不拼接两类身份；授权说明折叠，移除额外重复公共块 | root回看精简总览通过；真实字段覆盖待验 |
| 游戏壳/状态/布局 | GameCard采集状态、刷新、按页签排序及宽度 | CloudGameCard只作身份/运输适配，挂原GameCard | 当前user/account/role snapshot | 保留授权/角色选择；删除顶部重复刷新按钮；保留失败旧数据 | 定时刷新/收敛/撤销/原模块回归通过 |
| 鸣潮档案/角色/挑战/玩法 | WuwaDashboard面板和详情弹窗 | 原组件、本人scope运输映射 | 库街区授权snapshot及角色详情 | 缺字段保留未知，零/false保留 | 原Wuwa面板/角色回归通过；真实云载荷待验 |
| 鸣潮资源 | 周/月/版本切换 | 原WuwaResources及精确GET scoped resources | 当前本人原来源 | 不开放本地管理路由 | 原组件与HTTP回归通过 |
| 鸣潮攻略 | 指南、更新、来源图文 | 普通GET public updates；admin才显示检查/提炼 | 原版本化catalog与T5公共服务 | POST明确admin namespace；无新造审核/PUT接口 | 原组件/运输回归；后端证据见T5文档 |
| 鸣潮抽卡 | 分页、文件/授权链接导入、统计 | 恢复原WuwaGacha表单，POST本人scoped import | 本人archive及用户选择输入 | 仅点击导入用链接；用后清空，不反射敏感错误 | 原文件导入/账号变化回归及CSRF映射通过；真实导入待验 |
| 鸣潮成长记录 | 深塔/角色/完整面板历史及回补 | 原WuwaHistory；恢复回补本人快照 | 本人scoped archive及T5 backfill | 云只读本人当前授权snapshot，不扫描任意本机路径 | 原组件/运输回归；T5两用户隔离证据另见其文档 |
| 异环概览/探索/名片 | NteDataCard和模块弹窗 | 原GameCard/NteModuleCard/面板 | 哒哒社区本人snapshot | 保留原配色、摘要和弹窗 | 原NTE模块/详情回归通过 |
| 异环角色 | 过滤、排序、收藏、比较、配装 | 原NteRolesPanel；收藏按user/account/role分键 | 本人角色snapshot；当前浏览器收藏 | 不禁用所有云收藏，不读共享游戏UID键；切换清空比较 | 用户/角色收藏隔离及原角色回归通过 |
| 异环资产/配队 | 入住角色名、家具/拥有状态/搜索 | 原NteAssetsPanel，补齐roles props | 同本人角色及资产snapshot | 只映射当前角色；缺失ID不猜名称 | 合成入住名和名称搜索用例通过 |
| 异环攻略 | 原图索引、摘要、页码、来源及拥有筛选 | 原NteGuides；普通GET、admin刷新原帖 | 同catalog及T5 public source缓存 | 恢复入口，roles支持已拥有筛选，陈旧明确标注 | 原攻略回归及精确public/admin映射通过 |
| 异环社区抽卡 | 卡池/幸运色/图标/明细 | 原NteCommunityGacha由NteGachaPanel承载 | 社区本人snapshot | 不推导逐抽账本或当前垫抽 | 原卡池/颜色回归；root手机合成检查通过 |
| 异环逐抽账本 | JSON预览/确认、规则、分页/分段导出 | 原NteGachaLedger，精确summary/records/rules/export与preview/import/rules | 本人user/account/role账本 | 文案本人空间；作用域变化丢弃晚响应；保留连续范围和身份确认 | 合成完整preview→import携带ticket/CSRF；原规则/分页/导出回归通过 |
| 终末地壳/身份 | EndfieldDashboard七分区 | 原完整组件，顶部provider/role选择 | 当前单项授权 | 不自动合并；需要另一身份时说明切换 | hypergryph不发skland请求测试；root看到分界 |
| 终末地鹰角寻访 | 账号/抽卡/分页/导出 | 同角色合并页使用原EndfieldGachaPanel | 已验证同角色的鹰角snapshot及scoped archive | 未配对或身份不一致时不展示其他角色寻访 | 原gacha回归通过；真实授权待验 |
| 终末地森空岛档案 | 理智/干员/探索/据点/飞船/成就/配装 | 原面板；status由当前授权构造，GET当前scope card/operator | 当前skland授权/角色 | 不读全局status；隐藏本地连接/断开控件，在网站授权页管理 | 原配装/探索回归，未知不补零；真实档案待验 |
| 终末地挑战/图鉴 | 类型、分类/搜索/分页 | 原面板GET scoped challenges/tools | 当前skland原官方服务 | hypergryph不能调用skland私人接口 | 原分类/分页/竞态回归通过；真实字段待验 |
| 终末地地图 | 地图/区域/类型/搜索/分页、点位描述 | 原面板GET public map/marks | T5公开地图缓存 | 公共资料独立于私人身份，仍要求网站会话 | 原地图分页/选点回归；真实上游地图待验 |
| 终末地蓝图 | CRUD、复制、JSON导出 | 原界面映射同角色skland scope | 本人角色BlueprintStore | 未连接同角色森空岛时提示连接，不请求其他角色store | 合成create→edit→export→delete、CSRF与身份路由通过 |
| 公告/活动/日历 | 原折叠、来源、筛选与详情 | 原AnnouncementList/CalendarPage，保留游戏内入口 | 按游戏公共快照 | 首页无重复块；保留陈旧/成功空/未采集/失败区别；初次失败也存状态 | 三游戏、未知日期、旧数据保留及会话变化回归通过 |
| QQ绑定/网站会话 | 云必要新增 | 保留T1一步兑换和原会话撤销/退出 | identity/accounts/qq本人服务 | 未回退回执确认，未放开全局本地auth | 未修改T1文件；全套包含其测试通过 |

| 受限模块 | 本地原行为 | 云对应行为 | 原因/来源 | 处置 | 验证状态 |
| --- | --- | --- | --- | --- | --- |
| LCU | 本机客户端/对局采集 | 无远端私人LCU替代 | 服务器无用户PC会话 | 需另行批准本地代理；不改LOLhelper/Caddy | 不可直接迁移 |
| 窗口/截图/OCR/文件路径 | 本机前台、截图和路径 | 不开放任意远端窗口/文件读取 | 云服务器无游戏前台 | 需本地代理/真实样本授权，不称合成样本为真实OCR | 不可直接迁移，未执行 |
| 终末地手动签到 | 显式上游写 | 只读签到状态，无云签到按钮 | 后端明确禁用POST | 缺status显示尚未读取；不把缺失当待签 | fixture明确unsigned时才显示待签；真实签到未验 |
| 公开源维护 | 更新/提炼/刷新 | 普通用户阅读，管理员操作 | 公共源影响所有用户 | 精确admin路由+后端admin/CSRF，不仅靠隐藏按钮 | 前端回归；T5后端权限另见cloud-public-tools-v3.md |
| 真人/平台覆盖 | 真人授权、原来源 | 作用域及late-response保护已实现 | 合成不能证明两名真人或完整EF来源 | 用户验证第二身份、真实导入/EF；不代登录 | 待真实验证 |

验证：新增CloudV3Parity最初4项在缺功能处失败，CloudNavigation书签恢复前失败；完整 npm --prefix frontend test 为395 passed、0 failed。python scripts/cloud/build_frontend.py --frontend frontend 成功，index带data-service-mode=cloud；单JS chunk超过500kB提示不是构建失败。

root已实际检查桌面总览、390px抽屉/抽卡/账本无横溢出及EF身份分界；首页重复块/刷新双入口已修，root回看总览通过。ignored frontend/.private-cloud-probes/ fixture仅合成fetch，不接触秘密/云端/上游，不入提交/发行物，不作为真实数据验收。本轮未push/merge、未改主仓、未触碰真实登录/部署服务。
