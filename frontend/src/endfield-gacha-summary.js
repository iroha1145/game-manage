const id = value => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
const blocked = value => ['expired', 'auth_expired', 'revoked', 'unconfigured', 'disabled'].includes(value)
const expired = snapshot => blocked(snapshot?.state) || blocked(snapshot?.poll_status?.state)

// The passport ledger retains its own authorization even on a combined role page.
// The cloud envelope proves that grant; payload role IDs prove its ledger owner.
export function gachaView({ snaps = {}, cloudAccount, cloudRole, configured, authAccount } = {}) {
  const unavailable = message => ({ account: null, snapshot: null, accountId: '', message })
  if (cloudAccount) {
    if (cloudAccount.provider !== 'hypergryph') return unavailable('此角色尚未连接鹰角寻访，请到「账号与授权」登录。')
    if (cloudAccount.state !== 'active' || !cloudAccount.roles?.some(role => id(role.role_id) === id(cloudRole))) return unavailable('当前鹰角授权或角色不可用，请重新授权。')
  } else if (configured === false || authAccount?.configured === false || blocked(authAccount?.state)) {
    return unavailable('请登录有效的鹰角通行证后刷新寻访数据。')
  }
  const account = snaps.account, snapshot = snaps.gacha
  if (expired(account) || expired(snapshot)) return unavailable('鹰角身份已失效，请重新登录并刷新。')
  const role = id(account?.payload?.role_id)
  if (!role) return unavailable('尚未读取鹰角通行证角色，请刷新数据。')
  if (cloudAccount && (id(account.account_id) !== id(cloudAccount.account_id) || id(account.role_id) !== id(cloudRole))) return unavailable('当前授权与账号快照不一致，请重新读取。')
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

// How many pulls a 6★ took, in the wording the ledger can prove: exact, a known minimum, or unknown (null).
export function sixPullsParts(item) {
  if (item?.pulls == null || (item.status !== 'exact' && item.status !== 'lower_bound')) return null
  return { prefix: item.status === 'exact' ? '' : '≥', count: item.pulls, unit: '抽' }
}
export const sixPullsText = item => { const parts = sixPullsParts(item); return parts ? `${parts.prefix}${parts.count} ${parts.unit}` : '未知' }

// 6★ across all pools, newest first. An unknown time sorts last; equal times keep their pool order.
export function recentSixStars(pools, limit = Infinity) {
  const items = []
  for (const pool of rows(pools)) for (const item of rows(pool.history)) items.push({ ...item, pool_key: pool.key, pool_label: pool.label })
  return items
    .map((item, index) => ({ item, index, at: Number.isFinite(item.obtained_at) ? item.obtained_at : null }))
    .sort((a, b) => (a.at == null) - (b.at == null) || (b.at ?? 0) - (a.at ?? 0) || a.index - b.index)
    .slice(0, limit).map(({ item }) => item)
}

// One count summed over every pool. A single pool without it makes the whole total unknown, never a partial sum.
export function poolTotal(pools, field) {
  const values = rows(pools).map(pool => number(pool[field]))
  return values.length && values.every(value => value != null) ? values.reduce((sum, value) => sum + value, 0) : null
}

// The pool that was pulled from most recently, as an index into `pools`; -1 when no pool says when.
export function latestPoolIndex(pools) {
  const list = rows(pools)
  let best = -1
  list.forEach((pool, index) => {
    const at = number(pool.newest_at)
    if (at != null && (best < 0 || at > number(list[best].newest_at))) best = index
  })
  return best
}

// Column spans (of 12) for pool cards so every row fills the width: up to three to a row
// (four when there are only four), the cards shared out as evenly as the count allows.
export function poolSpans(count) {
  const total = Number.isInteger(count) && count > 0 ? count : 0
  if (!total) return []
  const perRow = total <= 4 ? total : 3, rows = Math.ceil(total / perRow)
  const base = Math.floor(total / rows), extra = total % rows
  return Array.from({ length: rows }, (_, row) => Array(base + (row < extra ? 1 : 0)).fill(12 / (base + (row < extra ? 1 : 0)))).flat()
}
