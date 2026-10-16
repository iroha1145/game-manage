import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Panel = await loadVue(new URL('./SourceStatusPanel.vue', import.meta.url))

// The renderer has no DOM, so the <details> node gets the little the popover handlers touch. Its
// .source-body refuses non-Node arguments in contains() exactly like the browser's.
function openPopover(t) {
  const listeners = {}, saved = { window: globalThis.window, document: globalThis.document }
  globalThis.window = { addEventListener: (type, handler) => { listeners[type] = handler }, removeEventListener() {} }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  t.after(() => { for (const [key, value] of Object.entries(saved)) if (value === undefined) delete globalThis[key]; else globalThis[key] = value })
  const root = mount(t, Panel, { game: { game_id: 'nte', capabilities: ['account'] }, collection: [] })
  const inside = { nodeType: 1 }, details = nodes(root, 'details')[0]
  details.open = true
  details.querySelector = selector => selector !== '.source-body' ? null : {
    contains(target) {
      if (target !== null && typeof target?.nodeType !== 'number') throw new TypeError("Failed to execute 'contains' on 'Node': parameter 1 is not of type 'Node'.")
      return target === inside
    },
  }
  return { details, inside, listeners, open: () => details.props.onToggle() }
}
test('collection panel displays retained data, native capability and actual attempts', t => {
  const root = mount(t, Panel, { game: { game_id: 'nte', capabilities: ['progress', 'roles'] }, collection: [
    { game_id: 'nte', capability: 'progress', state: 'error', consecutive_failures: 3, error: '上游异常', last_success_at: '2026-09-14T12:00:00Z', last_attempt_at: '2026-09-14T17:00:00Z' },
  ] })
  const text = content(root)
  for (const expected of ['成就进度', '同步失败', '保留旧数据', '2026-09-14 20:00', '2026-09-15 01:00', '3', '上游异常', '角色练度', '尚未同步']) assert.ok(text.includes(expected), expected)
})

test('first offline attempt never claims an old snapshot was retained', t => {
  const root = mount(t, Panel, { game: { game_id: 'league_of_legends', capabilities: ['account'] },
    collection: [{ game_id: 'league_of_legends', capability: 'account', state: 'offline', last_success_at: null, consecutive_failures: 0 }] })
  assert.match(content(root), /客户端离线.*暂无已保存的数据/)
  assert.doesNotMatch(content(root), /已保留快照|保留旧数据/)
})

test('unconfigured items keep the summary from claiming everything is updated', t => {
  const row = (capability, state) => ({ game_id: 'nte', capability, state, consecutive_failures: 0, last_success_at: null })
  const chip = root => nodes(root, 'summary')[0]
  const unconfigured = mount(t, Panel, { game: { game_id: 'nte', capabilities: ['account', 'stamina', 'news'] },
    collection: [row('account', 'unconfigured'), row('stamina', 'unconfigured'), row('news', 'ok')] })
  assert.match(content(chip(unconfigured)), /2 项未配置/)
  assert.doesNotMatch(content(chip(unconfigured)), /各项状态已更新/)
  assert.equal(chip(unconfigured).props.class, 'warn')
  const healthy = mount(t, Panel, { game: { game_id: 'nte', capabilities: ['account', 'news'] },
    collection: [row('account', 'ok'), row('news', 'ok')] })
  assert.match(content(chip(healthy)), /各项状态已更新/)
  assert.equal(chip(healthy).props.class, 'good')
})

test('resizing the window closes the open popover although the event target is not a node', async t => {
  const { details, listeners, open } = openPopover(t)
  await open()
  assert.equal(typeof listeners.resize, 'function')
  listeners.resize({ type: 'resize', target: globalThis.window })
  assert.equal(details.open, false)
})

test('scrolling inside the popover keeps it open while scrolling the page closes it', async t => {
  const { details, inside, listeners, open } = openPopover(t)
  await open()
  listeners.scroll({ type: 'scroll', target: inside })
  assert.equal(details.open, true)
  listeners.scroll({ type: 'scroll', target: { nodeType: 9 } })
  assert.equal(details.open, false)
})
