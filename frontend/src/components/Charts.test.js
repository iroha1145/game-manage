import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'

const find = (root, predicate) => {
  const walk = n => [...(predicate(n) ? [n] : []), ...n.children.flatMap(walk)]
  return walk(root)
}
// Vue hands the renderer one normalised class string.
const byClass = (root, name) => find(root, n => String(n.props.class ?? '').split(/\s+/).includes(name))

test('a ring gauge exposes its value as a meter and draws nothing for an unknown value', async t => {
  const Ring = await loadVue(new URL('./RingGauge.vue', import.meta.url))
  const known = mount(t, Ring, { value: 168, max: 240, label: '结晶波片' })
  const meter = find(known, n => n.props.role === 'meter')[0]
  assert.equal(meter.props['aria-valuenow'], 168)
  assert.equal(meter.props['aria-valuemax'], 240)
  assert.equal(meter.props['aria-label'], '结晶波片')
  assert.equal(nodes(known, 'circle').length, 2)
  const unknown = mount(t, Ring, { value: null, max: 240, label: '结晶波片' })
  assert.equal(find(unknown, n => n.props.role === 'meter').length, 0)
  assert.equal(nodes(unknown, 'circle').length, 1)
  const empty = mount(t, Ring, { value: 0, max: 240, label: '体力' })
  assert.equal(find(empty, n => n.props.role === 'meter')[0].props['aria-valuenow'], 0)
  assert.equal(nodes(empty, 'circle').length, 1, 'zero draws only the track')
})

test('bar charts label the peak and the highlighted bar, and keep unknown slots', async t => {
  const Bars = await loadVue(new URL('./BarChart.vue', import.meta.url))
  const root = mount(t, Bars, { label: '每期抽数', unit: ' 抽', highlight: 0, items: [
    { label: '本期', value: 12 }, { label: '上期', value: 78 }, { label: '更早', value: null },
  ] })
  assert.equal(nodes(root, 'li').length, 3)
  const shown = byClass(root, 'bar-value').filter(n => n.props.class.split(' ').includes('shown'))
  assert.deepEqual(shown.map(content), ['12 抽', '78 抽'])
  assert.match(content(root), /未知/)
  assert.equal(byClass(root, 'bar-fill').length, 2)
  assert.equal(byClass(root, 'bar-unknown').length, 1)
})

test('trend charts skip unknown points and list every known one for screen readers', async t => {
  const Trend = await loadVue(new URL('./TrendChart.vue', import.meta.url))
  const root = mount(t, Trend, { label: '胜率', unit: '%', min: 0, max: 100, points: [
    { label: '第 1 场', value: 40 }, { label: '第 2 场', value: null }, { label: '第 3 场', value: 62.5 },
  ] })
  const list = nodes(root, 'ol')[0]
  assert.deepEqual(nodes(list, 'li').map(content), ['第 1 场：40%', '第 3 场：62.5%'])
  assert.match(find(root, n => n.props.tabindex === '0' || n.props.tabindex === 0)[0].props['aria-label'], /最新 62\.5%/)
})

test('donuts show a legend with shares only when there is more than one part', async t => {
  const Donut = await loadVue(new URL('./DonutChart.vue', import.meta.url))
  const root = mount(t, Donut, { label: '星级分布', segments: [
    { label: '五星', value: 3, color: 'var(--chart-1)' }, { label: '四星', value: 9, color: 'var(--chart-2)' },
  ] })
  assert.deepEqual(nodes(root, 'li').map(content), ['五星 3 25%', '四星 9 75%'])
  const single = mount(t, Donut, { label: '星级分布', segments: [{ label: '五星', value: 3, color: 'var(--chart-1)' }] })
  assert.equal(nodes(single, 'ul').length, 0)
})

test('a rail without layout renders its cards and no arrows', async t => {
  const { h } = await import('vue')
  const Rail = await loadVue(new URL('./HRail.vue', import.meta.url))
  const root = mount(t, { setup: () => () => h(Rail, { label: '临近截止' }, { default: () => [h('article', '甲'), h('article', '乙')] }) }, {})
  assert.equal(nodes(root, 'article').length, 2)
  assert.equal(nodes(root, 'button').length, 0)
})
