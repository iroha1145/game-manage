import test from 'node:test'
import assert from 'node:assert/strict'
import { calendarCategory, presentationGroups, activityBoundaryDays } from './calendar-presentation.js'
import { beijingDayStart, eventGeometry } from './calendar.js'

test('source categories separate character and equipment pools and retain unfamiliar labels', () => {
  assert.equal(calendarCategory({category:'武器活动唤取'}).label,'武器与装备')
  assert.equal(calendarCategory({category:'特许寻访'}).label,'寻访与角色')
  assert.equal(calendarCategory({category:'角色活动唤取'}).label,'寻访与角色')
  assert.equal(calendarCategory({category:'限时签到'}).label,'活动与玩法')
  assert.equal(calendarCategory({category:'区域探索'}).label,'活动与玩法')
  assert.equal(calendarCategory({category:'实验类型'}).label,'实验类型')
  assert.equal(calendarCategory({name:'武器寻访',category:'实验类型'}).label,'实验类型')
})
test('screen grouping retains game identity and each event exactly once; bot images keep the original grouping and order', () => {
  const events=[{gameId:'nte',gameName:'异环',category:'活动',id:'a'},{gameId:'nte',gameName:'异环',category:'特许寻访',id:'b'},{gameId:'nte',gameName:'异环',category:'武库申领',id:'c'},{gameId:'endfield',gameName:'终末地',category:'活动',id:'d'}]
  const screen=presentationGroups(events)
  assert.deepEqual(screen.map(group=>group.categoryLabel),['寻访与角色','武器与装备','活动与玩法','活动与玩法'])
  assert.deepEqual(screen.flatMap(group=>group.events.map(event=>event.id)).sort(),['a','b','c','d'])
  assert.ok(screen.slice(0,3).every(group=>group.gameId==='nte'&&group.gameName==='异环'))
  const image=presentationGroups(events,'image')
  assert.equal(image.length,2)
  assert.deepEqual(image[0].events,events.slice(0,3))
  assert.ok(image.every(group=>!group.categoryLabel))
})
test('axis emphasis uses only recorded valid boundaries and respects inclusive date-only deadlines', () => {
  const range={start:Date.parse('2026-10-01T00:00:00+08:00'),end:Date.parse('2026-11-01T00:00:00+08:00')}
  const events=[{start_at:'2026-10-15T12:00:00+08:00',end_date:'2026-10-20'},{start_at:'bad',end_at:'2026-10-29T12:00:00+08:00'},{}].map(event=>({...event,geometry:eventGeometry(event,range)}))
  assert.deepEqual([...activityBoundaryDays(events)].sort(),[beijingDayStart('2026-10-15'),beijingDayStart('2026-10-20')].sort())
})
