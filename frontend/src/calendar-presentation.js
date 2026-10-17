import { beijingDayStart, groupCalendarEvents } from './calendar.js'

/** Category labels use source data only; activity names do not determine ownership. */
export function calendarCategory(event) {
  const category = typeof event.category === 'string' ? event.category.trim() : ''
  if (/武器|装备|武库|申领|弧盘/.test(category)) return { key:'equipment', label:'武器与装备', order:1 }
  if (/寻访|角色|卡池|唤取|棋盘|招募|研募/.test(category)) return { key:'characters', label:'寻访与角色', order:0 }
  if (/活动|玩法|签到|挑战|探索|区域|叙事/.test(category)) return { key:'activities', label:'活动与玩法', order:2 }
  return { key:`other:${category}`, label:category || '其他活动', order:3 }
}

export function presentationGroups(events, mode = 'screen') {
  const games = groupCalendarEvents(events)
  if (mode === 'image') return games
  return games.flatMap(game => {
    const buckets = new Map()
    for (const event of game.events) {
      const category = calendarCategory(event)
      if (!buckets.has(category.key)) buckets.set(category.key, { ...game, key:`${game.key}:${category.key}`, categoryLabel:category.label, order:category.order, events:[] })
      buckets.get(category.key).events.push(event)
    }
    return [...buckets.values()].sort((a,b) => a.order-b.order)
  })
}

/** Emphasize recorded boundaries, without inventing release dates or changing the date axis. */
export function activityBoundaryDays(events) {
  const days = new Set()
  for (const event of events) {
    const geometry = event.geometry
    if (!geometry || !['range','point'].includes(geometry.kind)) continue
    if (geometry.start !== null) days.add(beijingDayStart(geometry.start))
    if (geometry.end !== null) days.add(beijingDayStart(geometry.end - (!event.end_at && event.end_date ? 1 : 0)))
  }
  return days
}
