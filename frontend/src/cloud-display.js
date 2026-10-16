export const capabilityLabel = cap => ({ account:'账号档案',stamina:'体力',progress:'周期进度',stats:'统计',record:'社区名片',roles:'角色练度',exploration:'探索进度',calabash:'数据坞',combat:'挑战记录',activities:'玩法进度',resources:'资源简报',gacha:'抽卡记录',realestate:'房产',vehicles:'载具',teams:'配队',news:'公共资讯',events:'活动日历',match:'对局记录',announcement:'官方公告' })[cap] || '其他数据'
export function friendlyDataError(value, state = '') {
  if (!value && !['auth_expired','expired'].includes(state)) return ''
  const text = typeof value === 'string' ? value : ''
  if (/森空岛未接受通行证授权/.test(text)) return '森空岛未接受通行证授权，请改用手动连接。'
  if (/网站会话|重新登录网站/.test(text)) return '网站会话已失效，请重新登录。'
  if (['auth_expired','expired'].includes(state) || /授权|凭据|auth_expired|credential_unavailable/.test(text)) return '游戏授权不可用，请到「账号与授权」重新登录。'
  if (/请选择.*角色|请先.*角色|role_required|role_not_found/.test(text)) return '请先选择已授权的游戏角色。'
  if (/参数|检查输入|invalid_parameters/.test(text)) return '请检查输入后重试。'
  if (/频繁|rate_limit/.test(text)) return '请求过于频繁，请稍后重试。'
  return '暂时无法读取，请稍后重试。'
}
export const cloudStateLabel = state => ({ never:'尚未更新',ok:'已更新',fresh:'已更新',stale:'数据可能过期',error:'更新失败',source_error:'来源更新失败',auth_expired:'游戏授权失效',expired:'游戏授权失效',invalid_data:'来源数据异常',unconfigured:'尚未配置',offline:'来源离线',queued:'刷新已排队',running:'正在刷新',coalesced:'已有刷新任务',active:'已授权',revoked:'授权已撤销',unsupported:'云端尚未支持' })[state] || '状态未知'
export const dataFieldLabel = key => ({ base:'账号档案',nickname:'昵称',name:'名称',title:'标题',level:'等级',stamina:'体力',progress:'日常与周期进度',operators:'干员',regions:'区域探索',ship:'帝江号',achievements:'成就',current:'当前值',maximum:'上限',cur:'当前进度',total:'总数',expected_full_at:'预计恢复时间',updated_at:'更新时间',fetched_at:'来源时间',weapon:'武器',equipment:'装备',skills:'技能',rarity:'稀有度',potential:'潜能',evolve_phase:'突破阶段',profession:'职业',property:'属性',refine_level:'精炼等级',breakthrough_level:'突破等级',gem:'源石',terms:'词条',cost:'消耗',slot:'部位',items:'条目',records:'记录',pools:'卡池',pool:'卡池',pool_id:'卡池标识',count:'数量',complete:'记录完整性',state:'数据状态',calendar:'签到日历',done:'已完成',date:'日期',url:'来源链接',code:'蓝图代码',notes:'备注',created_at:'创建时间',role_id:'角色标识',server_id:'服务器标识',id:'来源标识',game_uid:'游戏 UID',icon_url:'图标来源',avatar_url:'头像来源',value:'来源值',rules:'已保存规则' })[key] || `来源字段 ${key}`
