// Pure helpers that turn Wuwa payloads into chart input. Unknown stays unknown:
// a missing number never becomes a zero, and nothing here invents a maximum.
import { beijingDayStart, DAY_MS, parseBeijingTime } from './calendar.js'
import { stamp, starCount } from './wuwa-display.js'

const known = v => typeof v === 'number' && Number.isFinite(v)
const rows = v => (Array.isArray(v) ? v.filter(item => item != null) : [])

/** Experience toward the next level as { cur, max, pct }; null when the source gave neither side. */
export function expProgress(profile) {
  const cur = profile?.next_exp ?? null, max = profile?.exp_limit ?? null
  if (cur == null && max == null) return null
  const pct = known(cur) && known(max) && max > 0 ? Math.max(0, Math.min(100, Math.round((cur / max) * 100))) : 0
  return { cur, max, pct }
}

/** Whole days from today to a date, counted on Beijing calendar days; null for an unreadable date. */
export function daysUntil(value, now = Date.now()) {
  const time = parseBeijingTime(value)
  if (time == null) return null
  return Math.round((beijingDayStart(time) - beijingDayStart(now)) / DAY_MS)
}

/** "今日结束", "3 天后结束" and so on; null for an unreadable date. */
export function endLabel(value, now = Date.now()) {
  const time = parseBeijingTime(value)
  if (time == null) return null
  if (time <= now) return '已结束'
  const days = daysUntil(time, now)
  return days === 0 ? '今日结束' : days === 1 ? '明日结束' : `${days} 天后结束`
}

/** Roster counts: [{ label, value }] per attribute, most owned first; the tail beyond `limit` folds into 其他. */
export function attributeSplit(roles, limit = 6) {
  const counts = new Map()
  for (const role of rows(roles)) {
    const name = typeof role.attribute === 'string' ? role.attribute.trim() : ''
    if (name) counts.set(name, (counts.get(name) || 0) + 1)
  }
  const sorted = [...counts].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value)
  if (sorted.length <= limit) return sorted
  const rest = sorted.slice(limit - 1)
  return [...sorted.slice(0, limit - 1), { label: '其他', value: rest.reduce((sum, item) => sum + item.value, 0) }]
}

/** Roster levels in bands of ten, low to high, with empty bands between kept; unknown levels are left out. */
export function levelBands(roles) {
  const counts = new Map()
  for (const role of rows(roles)) {
    if (!known(role.level) || role.level < 0) continue
    const start = role.level >= 90 ? 90 : role.level >= 60 ? Math.floor(role.level / 10) * 10 : 0
    counts.set(start, (counts.get(start) || 0) + 1)
  }
  if (!counts.size) return []
  const label = start => (start === 0 ? '≤59' : start >= 90 ? '90+' : `${start}–${start + 9}`)
  const low = Math.min(...counts.keys()), high = Math.max(...counts.keys())
  const starts = [0, 60, 70, 80, 90].filter(start => start >= low && start <= high)
  return starts.map(start => ({ label: label(start), value: counts.get(start) || 0 }))
}

/** Headline numbers for the roster card. */
export function rosterSummary(roles) {
  const list = rows(roles)
  const stars = star => list.filter(role => starCount(role.star_level) === star).length
  return {
    total: list.length,
    five: stars(5),
    four: stars(4),
    maxLevel: list.filter(role => known(role.level) && role.level >= 90).length,
    fullChain: list.filter(role => known(role.chain) && role.chain >= 6).length,
  }
}

/** Stars over a list of tower areas: what was earned, the cap when every area states one, and whether anything is known. */
export function towerTotals(areas) {
  const list = rows(areas)
  const earned = list.filter(area => known(area.star))
  const capped = list.length > 0 && list.every(area => known(area.max_star))
  return {
    got: earned.length ? earned.reduce((sum, area) => sum + area.star, 0) : null,
    cap: capped ? list.reduce((sum, area) => sum + area.max_star, 0) : null,
  }
}

/**
 * Sources of an income report as donut parts, largest first. Parts beyond `limit`
 * fold into 其他; a source without a number keeps its row and reads as unknown.
 */
export function sourceShares(sources, limit = 6) {
  const parts = rows(sources).map(row => ({ label: row.type || '未知来源', value: known(row.num) ? row.num : null }))
  const counted = parts.filter(part => part.value != null).sort((a, b) => b.value - a.value)
  const unknown = parts.filter(part => part.value == null)
  if (counted.length + unknown.length <= limit) return [...counted, ...unknown]
  const keep = counted.slice(0, Math.max(0, limit - 1))
  const rest = counted.slice(keep.length)
  return [...keep, { label: '其他', value: rest.reduce((sum, part) => sum + part.value, 0) || null }]
}

const timeKey = v => (typeof v === 'string' ? v.replace('T', ' ') : '')

/** Rarity counts over every pool, five stars first; empty buckets are left out. */
export function rarityTotals(pools) {
  const totals = new Map()
  for (const pool of rows(pools)) {
    for (const [rarity, count] of Object.entries(pool.rarity_distribution || {})) {
      if (known(count) && count > 0) totals.set(rarity, (totals.get(rarity) || 0) + count)
    }
  }
  const order = rarity => (rarity === 'unknown' ? -1 : Number(rarity))
  return [...totals].map(([rarity, value]) => ({ rarity, value })).sort((a, b) => order(b.rarity) - order(a.rarity))
}

/** Pulls per pool in the order the archive lists the pools; an unknown total keeps its slot. */
export function poolPulls(pools) {
  return rows(pools).map(pool => ({ label: pool.name || `卡池 ${pool.pool ?? '未知'}`, value: known(pool.total) ? pool.total : null }))
}

/** The newest five-star records first, as many as `limit`; the order of equal times is kept. */
export function recentGold(records, limit = 12) {
  return rows(records)
    .map((row, index) => ({ row, index }))
    .sort((a, b) => timeKey(b.row.time).localeCompare(timeKey(a.row.time)) || a.index - b.index)
    .slice(0, limit)
    .map(item => item.row)
}

/** A pity ring only when the count is exact and the user's rule says how far the cap is. */
export function pityGauge(pity) {
  if (pity?.status !== 'exact' || !known(pity.count) || !known(pity.hard_pity_remaining)) return null
  return { value: pity.count, max: pity.count + pity.hard_pity_remaining }
}

const observed = item => parseBeijingTime(item?.observed_at)

/** The role a history record is about. */
export const historySubject = item => String(item?.subject ?? item?.payload?.role_id ?? '')

/**
 * Role level over time for every role seen at least twice: a Map from the role to
 * its points in time order and the id of its newest record (the one that carries
 * the chart). A single observation draws nothing.
 */
export function levelSeries(items) {
  const bySubject = new Map()
  for (const item of rows(items)) {
    const level = item.payload?.level ?? item.payload?.data?.role?.level ?? item.payload?.role?.level
    const at = observed(item)
    if (!known(level) || at == null) continue
    const key = historySubject(item)
    bySubject.set(key, [...(bySubject.get(key) || []), { at, id: item.id, label: stamp(item.observed_at), value: level }])
  }
  const series = new Map()
  for (const [key, points] of bySubject) {
    if (points.length < 2) continue
    points.sort((a, b) => a.at - b.at)
    series.set(key, { id: points.at(-1).id, points: points.map(({ label, value }) => ({ label, value })) })
  }
  return series
}

/** Stars in the deep zone per season, oldest first; seasons without a known total are left out. */
export function seasonStars(items) {
  return rows(items)
    .map(item => {
      const zone = rows(item.payload?.difficulty_list).find(z => String(z.difficulty) === '3')
      const { got } = towerTotals(zone?.tower_area_list)
      const at = parseBeijingTime(item.season)
      return got == null || at == null ? null : { at, label: stamp(item.season).slice(5, 10), value: got }
    })
    .filter(Boolean)
    .sort((a, b) => a.at - b.at)
    .map(({ label, value }) => ({ label, value }))
}
