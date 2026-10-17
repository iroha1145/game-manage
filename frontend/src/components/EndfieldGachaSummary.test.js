import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
const Summary = await loadVue(new URL('./EndfieldGachaSummary.vue', import.meta.url))
const snapshot = report => ({ stale: false, fetched_at: '2026-10-15T01:02:00Z', payload: { schema_version: 1, role_id: 'r', total: report.total, report: { schema_version: 1, role_id: 'r', ...report } } })
const view = report => ({ account: { nickname: '本人', role_id: 'r' }, accountId: 'r', snapshot: snapshot(report), message: '' })
const ring = root => nodes(root, 'figure').find(node => node.props['aria-label'] === '已记录寻访的稀有度占比')
const hasClass = (node, name) => String(node.props.class).split(' ').includes(name)

test('the ring splits the record into 6★, 5★ and the rest, with the same totals the tiles state', t => {
  const root = mount(t, Summary, { view: view({ total: 120, six_star: 3, five_star: 12, free: 10, pending: false }) })
  assert.ok(ring(root))
  assert.match(content(ring(root)), /6★ 3 3%/); assert.match(content(ring(root)), /5★ 12 10%/); assert.match(content(ring(root)), /其余 105 88%/)
  assert.match(content(root), /已记录寻访 120/); assert.match(content(root), /6★ 记录 3/); assert.match(content(root), /5★ 记录 12/); assert.match(content(root), /免费寻访 10/)
})

test('without all three counts, or when they contradict each other, there is no ring and the numbers stay plain', t => {
  for (const report of [{ total: 120, six_star: 3, five_star: null }, { total: null, six_star: 3, five_star: 12 }, { total: 10, six_star: 8, five_star: 8 }]) {
    const root = mount(t, Summary, { view: view(report) })
    assert.equal(ring(root), undefined)
    assert.match(content(root), /已记录寻访/)
  }
  assert.match(content(mount(t, Summary, { view: view({ total: 120, six_star: 3, five_star: null }) })), /5★ 记录 未知/)
})

test('an unsynced account gets a quiet placeholder and both actions keep working', t => {
  const events = []
  const root = mount(t, Summary, { view: { account: null, accountId: '', snapshot: null, message: '请登录有效的鹰角通行证后刷新寻访数据。' }, refreshing: false, onDetails: () => events.push('details'), onRefresh: () => events.push('refresh') })
  assert.match(content(root), /鹰角通行证 · 尚未读取/); assert.match(content(root), /请登录有效的鹰角通行证后刷新寻访数据/)
  assert.ok(nodes(root, 'span').some(node => hasClass(node, 'gs-ghost') && node.props['aria-hidden'] === 'true'))
  const buttons = nodes(root, 'button')
  assert.deepEqual(buttons.map(content), ['查看寻访详情 →', '刷新寻访数据'])
  buttons.forEach(button => button.props.onClick())
  assert.deepEqual(events, ['details', 'refresh'])
  assert.equal(content(mount(t, Summary, { view: view({ total: 1 }), refreshing: true }).children[0]).includes('同步中…'), true)
})
