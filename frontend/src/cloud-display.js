import { isCloudMode } from './http-client.js'

export const capabilityLabel = cap => ({ account:'账号档案',stamina:'体力',progress:'周期进度',stats:'统计',record:'社区名片',roles:'角色练度',exploration:'探索进度',calabash:'数据坞',combat:'挑战记录',activities:'玩法进度',resources:'资源简报',gacha:'抽卡记录',realestate:'房产',vehicles:'载具',teams:'配队',news:'公共资讯',events:'活动日历',match:'对局记录',announcement:'官方公告' })[cap] || '其他数据'
export function friendlyDataError(value, state = '') {
  if (!value && !['auth_expired','expired'].includes(state)) return ''
  const text = typeof value === 'string' ? value : ''
  if (/森空岛未接受通行证授权/.test(text)) return '森空岛未接受通行证授权，请改用手动连接。'
  if (/网站会话|重新登录网站/.test(text)) return '网站会话已失效，请重新登录。'
  if (['auth_expired','expired'].includes(state) || /授权|凭据|auth_expired|credential_unavailable/.test(text)) return `游戏授权不可用，请到「${isCloudMode() ? '账号与授权' : '社区账号'}」重新登录。`
  if (/请选择.*角色|请先.*角色|role_required|role_not_found/.test(text)) return '请先选择已授权的游戏角色。'
  if (/参数|检查输入|invalid_parameters/.test(text)) return '请检查输入后重试。'
  if (/频繁|rate_limit/.test(text)) return '请求过于频繁，请稍后重试。'
  if (/超时/.test(text)) return '读取超时，请重试；已有数据仍保留。'
  if (/无法连接|连接服务/.test(text)) return '无法连接服务，请稍后重试；已有数据仍保留。'
  return '暂时无法读取，请稍后重试。'
}
export function dataReadIssue(capability, snapshot) {
  const error=snapshot?.error || snapshot?.poll_status?.error
  const state=snapshot?.state || snapshot?.poll_status?.state
  if (!error && !['auth_expired','expired'].includes(state)) return null
  const message=friendlyDataError(error,state)
  const kind=/授权/.test(message)?'auth':/超时/.test(message)?'timeout':/连接/.test(message)?'network':snapshot?.error?'HTTP':'source'
  return {capability,kind,message,retained:snapshot?.payload!=null}
}
export const cloudStateLabel = state => ({ never:'尚未更新',ok:'已更新',fresh:'已更新',stale:'数据可能过期',error:'更新失败',source_error:'来源更新失败',auth_expired:'游戏授权失效',expired:'游戏授权失效',invalid_data:'来源数据异常',unconfigured:'尚未配置',offline:'来源离线',queued:'刷新已排队',running:'正在刷新',coalesced:'已有刷新任务',active:'已授权',revoked:'授权已撤销',unsupported:'云端尚未支持' })[state] || '状态未知'
