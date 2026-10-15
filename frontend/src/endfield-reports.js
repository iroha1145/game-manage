import iconCatalog from './endfield-icon-catalog.js'

// Display helpers. Report calculations belong to the shared backend projection.
export const rows = value => Array.isArray(value) ? value : []
export const displayValue = value => value == null || value === '' || typeof value === 'number' && !Number.isFinite(value) ? '未知' : String(value)
export const sourceName = value => typeof value === 'object' && value !== null ? displayValue(value.name ?? value.value ?? value.key) : displayValue(value)

export function profileReport(payload) {
  if (payload?.report?.schema_version === 1) return payload.report
  // Previously saved profiles remain readable until their next normal refresh.
  return {
    overview: { base: payload?.base, stamina: payload?.stamina, progress: rows(payload?.progress), todos: null },
    training: { items: rows(payload?.operators), summary: { listed_count: rows(payload?.operators).length || null } },
    regions: { items: rows(payload?.regions), summary: { region_count: rows(payload?.regions).length || null } },
    ship: { rooms: rows(payload?.ship), summary: { room_count: rows(payload?.ship).length || null } },
  }
}

export function selectOperators(items, { search = '', rarity = '', profession = '', sort = 'level' } = {}) {
  const term = search.trim().toLocaleLowerCase('zh-CN')
  const numeric = (item, key) => typeof item[key] === 'number' && Number.isFinite(item[key]) ? item[key] : null
  return rows(items).filter(item => (!term || [item.name, item.id].some(value => String(value ?? '').toLocaleLowerCase('zh-CN').includes(term)))
    && (!rarity || String(item.rarity) === String(rarity))
    && (!profession || sourceName(item.profession) === profession))
    .map((item, index) => ({ item, index })).sort((a, b) => {
      if (sort === 'name') return sourceName(a.item.name).localeCompare(sourceName(b.item.name), 'zh-CN') || a.index - b.index
      const left = numeric(a.item, sort), right = numeric(b.item, sort)
      if (left === null || right === null) return left === right ? a.index - b.index : left === null ? 1 : -1
      return right - left || a.index - b.index
    }).map(({ item }) => item)
}

// Only reviewed public artwork hosts; profile URLs never become arbitrary requests.
export function operatorImage(value) {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search || url.hash) return null
    return ['bbs.hycdn.cn', 'web.hycdn.cn'].includes(url.hostname) && /\.(png|jpe?g|webp)$/i.test(url.pathname) ? url.href : null
  } catch { return null }
}

export function operatorArtwork(operator) {
  const supplied = operatorImage(operator?.avatar_url || operator?.icon_url)
  if (supplied) return supplied
  // Official website keys are deliberately not guessed from game-ID suffixes.
  for (const key of [operator?.char_id, operator?.id]) {
    if (key && iconCatalog.roles[key]) return operatorImage(iconCatalog.roles[key].icon)
  }
  const matches = Object.values(iconCatalog.roles).filter(item => item.name === operator?.name)
  return matches.length === 1 ? operatorImage(matches[0].icon) : null
}
