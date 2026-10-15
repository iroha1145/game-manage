const id = value => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
const blocked = value => ['expired', 'auth_expired', 'revoked', 'unconfigured', 'disabled'].includes(value)
const expired = snapshot => blocked(snapshot?.state) || blocked(snapshot?.poll_status?.state)

// A passport ledger and a Skland profile have separate identities. The cloud
// envelope proves the selected grant; payload role IDs prove its ledger owner.
export function gachaView({ snaps = {}, cloudAccount, cloudRole, configured, authAccount } = {}) {
  const unavailable = message => ({ account: null, snapshot: null, accountId: '', message })
  if (cloudAccount) {
    if (cloudAccount.provider !== 'hypergryph') return unavailable('寻访数据需要单独选择鹰角授权。')
    if (cloudAccount.state !== 'active' || !cloudAccount.roles?.some(role => id(role.role_id) === id(cloudRole))) return unavailable('当前鹰角授权或角色不可用，请重新授权。')
  } else if (configured === false || authAccount?.configured === false || blocked(authAccount?.state)) {
    return unavailable('请登录有效的鹰角通行证后刷新寻访数据。')
  }
  const account = snaps.account, snapshot = snaps.gacha
  if (expired(account) || expired(snapshot)) return unavailable('鹰角身份已失效，请重新登录并刷新。')
  const role = id(account?.payload?.role_id)
  if (!role) return unavailable('尚未读取鹰角通行证角色，请刷新数据。')
  if (cloudAccount && (id(account.account_id) !== id(cloudAccount.account_id) || id(account.role_id) !== id(cloudRole) || role !== id(cloudRole))) return unavailable('当前授权与账号快照不一致，请重新读取。')
  const identity = { account: account.payload, accountId: cloudAccount ? `${cloudAccount.account_id}:${cloudRole}` : role }
  if (!snapshot) return { ...identity, snapshot: null, message: '尚未同步该鹰角角色的寻访记录。' }
  if (id(snapshot.payload?.role_id) !== role || (snapshot.payload?.report?.role_id != null && id(snapshot.payload.report.role_id) !== role) || cloudAccount && (id(snapshot.account_id) !== id(cloudAccount.account_id) || id(snapshot.role_id) !== id(cloudRole))) {
    return { ...identity, snapshot: null, accountId: '', message: '寻访快照与当前鹰角身份不一致，请刷新后查看。' }
  }
  return { ...identity, snapshot, message: '' }
}

const number = value => (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null
const rows = value => Array.isArray(value) ? value.filter(item=>item && typeof item==='object' && !Array.isArray(item)) : []
export function gachaPools(summary) {
  const values = summary?.report?.schema_version === 1 && Array.isArray(summary.report.pools) ? summary.report.pools : summary?.pools
  return rows(values).map(pool => {
    const history = rows(pool.history), available = history.length
    const declared = number(pool.history_total) ?? number(pool.six_star)
    const total = declared != null && declared >= available ? declared : null
    return { ...pool, history, history_available: available, history_total: total,
      history_truncated: total == null ? null : total > available,
      history_limit: number(pool.history_limit), four_star:number(pool.four_star), unknown_rarity:number(pool.unknown_rarity) }
  })
}
