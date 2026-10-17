const STATUS = {
  never: ['尚未同步', 'muted'], ok: ['已同步', 'good'], offline: ['客户端离线', 'muted'],
  unconfigured: ['未配置', 'muted'], auth_expired: ['登录已失效', 'danger'], error: ['同步失败', 'danger'],
}
const PRIORITY = { auth_expired: 6, error: 5, offline: 4, unconfigured: 3, never: 2, ok: 1 }
export function describeSource(row) {
  const [label, tone] = STATUS[row?.state || 'never'] || ['状态未知', 'muted']
  return { ...row, label, tone, retained: !!row?.last_success_at && row.state !== 'ok' }
}
export function sourceForGame(gameId, rows = []) {
  const selected = rows.filter(row => row.game_id === gameId && row.scope !== 'public_source')
    .sort((a, b) => (PRIORITY[b.state] || 0) - (PRIORITY[a.state] || 0))[0]
  return selected ? describeSource(selected) : null
}
