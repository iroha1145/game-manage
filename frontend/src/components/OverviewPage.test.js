import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'

const Overview = await loadVue(new URL('./OverviewPage.vue', import.meta.url))
const now = Date.parse('2026-10-17T12:00:00+08:00')
const wuwa = { game_id: 'wuthering_waves', display_name: '鸣潮', capabilities: ['stamina', 'roles', 'events'], credentials_configured: true }
const role = (name, level, icon = true) => ({ role_id: name, name, level, icon_url: icon ? `https://web-static.kurobbs.com/r${level}.png` : '' })
const byClass = (root, name) => {
  const walk = n => [...(String(n.props.class ?? '').split(/\s+/).includes(name) ? [n] : []), ...n.children.flatMap(walk)]
  return walk(root)
}

test('game cards show the five highest-level pictured roles and the whole roster count', t => {
  const roles = [role('甲', 60), role('乙', 90), role('丙', 70), role('丁', 80, false), role('戊', 50), role('己', 40), role('庚', 85)]
  const root = mount(t, Overview, { games: [wuwa], now, snapshots: { wuthering_waves: { roles: { payload: roles } } } })
  const faces = nodes(byClass(root, 'roster-faces')[0], 'img').map(img => img.props.src)
  assert.deepEqual(faces, [90, 85, 70, 60, 50].map(level => `https://web-static.kurobbs.com/r${level}.png`))
  assert.match(content(byClass(root, 'summary-roster')[0]), /7 名角色/)
  const none = mount(t, Overview, { games: [wuwa], now, snapshots: { wuthering_waves: { roles: { payload: [role('甲', 60, false)] } } } })
  assert.equal(byClass(none, 'summary-roster').length, 0, 'no row without a picture')
})

test('the first deadline leads, and the week chart counts deadlines per Beijing day', t => {
  const events = [
    { name: '明日截止', start_at: '2026-10-10 10:00', end_at: '2026-10-18 03:59', category: '限时活动' },
    { name: '今晚截止', start_at: '2026-10-12 10:00', end_at: '2026-10-17 23:59', category: '限时活动' },
    { name: '下月截止', start_at: '2026-10-12 10:00', end_at: '2026-11-20 03:59' },
  ]
  const root = mount(t, Overview, { games: [wuwa], now, snapshots: { wuthering_waves: { events: { payload: events } } } })
  assert.match(content(byClass(root, 'ov-next')[0]), /最近截止.*今晚截止.*1.*天后结束/)
  const bars = nodes(byClass(root, 'bar-chart')[0], 'li').map(content)
  assert.equal(bars.length, 7)
  assert.match(bars[0], /今天/); assert.match(bars[0], /1 项/)
  assert.match(bars[1], /明天/); assert.match(bars[1], /1 项/)
  assert.ok(bars.slice(2).every(bar => /0 项/.test(bar)), 'events beyond the week are not counted')
  assert.match(content(byClass(root, 'ov-stats')[0]), /3.*进行中的活动.*2.*3 天内截止/)
})
