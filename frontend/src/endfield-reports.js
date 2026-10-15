import iconCatalog from './endfield-icon-catalog.js'
import { shipReport } from './endfield-ship.js'
import { parseBeijingTime } from './calendar.js'

// Display helpers. Report calculations belong to the shared backend projection.
export const rows = value => Array.isArray(value) ? value : []
export const displayValue = value => value == null || value === '' || typeof value === 'number' && !Number.isFinite(value) ? '未知' : String(value)
export const sourceName = value => typeof value === 'object' && value !== null ? displayValue(value.name ?? value.value ?? value.key) : displayValue(value)

export function profileReport(payload) {
  if (payload?.report?.schema_version === 1) return { ...payload.report,
    honor: categorizedHonor(payload.report.honor, payload), regions: labeledRegions(payload.report.regions),
    ship: shipReport(payload.report.ship, payload.report.training?.items || payload.operators) }
  // Previously saved profiles remain readable until their next normal refresh.
  return {
    observed_at: payload?.observed_at,
    overview: { base: payload?.base, stamina: payload?.stamina, progress: rows(payload?.progress), todos: null },
    training: { items: rows(payload?.operators), summary: { listed_count: rows(payload?.operators).length || null } },
    regions: labeledRegions({ items: rows(payload?.regions), summary: { region_count: rows(payload?.regions).length || null } }),
    ship: shipReport({ rooms: rows(payload?.ship), available: payload?.availability?.ship ?? (rows(payload?.ship).length ? true : null),
      summary: { room_count: payload?.availability?.ship === false ? null : payload?.availability?.ship === true || rows(payload?.ship).length ? rows(payload?.ship).length : null } }, payload?.operators),
    honor: honorReport(payload),
  }
}

const areaNames = {map01_lv001:'枢纽区',map01_lv002:'谷地通道',map01_lv003:'阿伯莉采石场',
  map01_lv005:'源石研究园',map01_lv006:'矿脉源区',map01_lv007:'供能高地',
  map02_lv001:'景玉谷',map02_lv002:'武陵城',map02_lv003:'清波寨'}

function labeledRegions(report) {
  if (!report) return report
  return {...report,items:rows(report.items).map(region=>{
    const levels=rows(region.levels), collections=rows(region.collections)
    const areas=Array.isArray(region.areas) ? region.areas : [...levels,...collections
      .filter(item=>!levels.some(level=>level.id===item.level_id)).map(item=>({id:item.level_id,name:item.name,
        chests:{count:item.chest_count},puzzles:{count:item.puzzle_count},blackboxes:{count:item.blackbox_count},
        equipment_chests:{count:item.equipment_chest_count},pieces:{count:item.piece_count}}))]
    return {...region,money:region.money ? {...region.money,count:region.money.count ?? region.money.conut} : region.money,areas:areas.map(area=>({...area,name:
      levels.find(level=>level.id===area.id)?.name || collections.find(item=>item.level_id===area.id)?.name ||
      area.name || areaNames[area.id] || area.id}))}
  })}
}

// Older stored profiles predate the honor projection. Only the explicitly
// observed medal fields are lifted; an empty legacy array cannot prove zero.
function honorReport(payload) {
  const number = value => value == null || typeof value === 'boolean' || value === '' || !Number.isFinite(Number(value)) || Number(value) < 0 ? null : Number(value)
  const medals = rows(payload?.achievements?.medals).filter(item => item && typeof item === 'object' && !Array.isArray(item))
  const flag = payload?.availability?.honor
  const available = typeof flag === 'boolean' ? flag : medals.length ? true : null
  return { available, summary: { declared_count: number(payload?.achievements?.count), listed_count: available === true ? medals.length : null },
    items: medals.map(item => {
      const data = item.achievementData || {}, level = number(item.level), plated = typeof item.isPlated === 'boolean' ? item.isPlated : null
      let icon = data.initIcon
      if (level >= 2 && data.reforge2Icon) icon = data.reforge2Icon
      if (level >= 3 && data.reforge3Icon) icon = data.reforge3Icon
      if (plated === true && data.platedIcon) icon = data.platedIcon
      const timestamp = number(item.obtainTs), date = timestamp ? new Date(timestamp * 1000) : null
      return { id:data.id, name:data.name, category:categoryName(data.cateName), level, is_plated:plated,
        obtained_at:date && Number.isFinite(date.getTime()) ? date.toISOString() : null, icon_url:typeof icon === 'string' ? icon : null }
    }) }
}

const categoryName = value => typeof value === 'string' && value.trim() ? value.trim() : null
function categorizedHonor(report, payload) {
  if (!report) return honorReport(payload)
  const legacy = honorReport(payload).items
  return {...report,items:rows(report.items).map(item=>{
    if (Object.prototype.hasOwnProperty.call(item,'category')) return {...item,category:categoryName(item.category)}
    const matches = item.id == null ? [] : legacy.filter(raw=>raw.id != null && String(raw.id) === String(item.id))
    return {...item,category:matches.length === 1 ? matches[0].category : null}
  })}
}

export function selectMedals(items, {search='',category=undefined,sort='recent'}={}) {
  const term=search.trim().toLocaleLowerCase('zh-CN')
  return rows(items).filter(item=>(!term || String(item.name ?? '').toLocaleLowerCase('zh-CN').includes(term))
    && (category === undefined || categoryName(item.category) === category))
    .map((item,index)=>({item,index,time:parseBeijingTime(item.obtained_at)})).sort((a,b)=>{
      if (sort==='source') return a.index-b.index
      if (a.time == null || b.time == null) return a.time == null && b.time == null ? a.index-b.index : a.time == null ? 1 : -1
      return (sort==='oldest' ? a.time-b.time : b.time-a.time) || a.index-b.index
    }).map(({item})=>item)
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

export function operatorArtwork(operator, { portrait = false } = {}) {
  if (portrait) {
    for (const key of [operator?.char_id, operator?.id]) {
      const url = key && operatorImage(iconCatalog.roles[key]?.portrait)
      if (url) return url
    }
    const portraits = Object.values(iconCatalog.roles).filter(item => item.name === operator?.name)
    if (portraits.length === 1) {
      const url = operatorImage(portraits[0].portrait)
      if (url) return url
    }
  }
  const supplied = operatorImage(operator?.avatar_url || operator?.icon_url)
  if (supplied) return supplied
  // Official website keys are deliberately not guessed from game-ID suffixes.
  for (const key of [operator?.char_id, operator?.id]) {
    if (key && iconCatalog.roles[key]) return operatorImage(iconCatalog.roles[key].icon)
  }
  const matches = Object.values(iconCatalog.roles).filter(item => item.name === operator?.name)
  return matches.length === 1 ? operatorImage(matches[0].icon) : null
}
