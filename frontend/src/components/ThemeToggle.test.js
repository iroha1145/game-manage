import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'

const window = new Window()
for (const key of ['document', 'Element', 'HTMLElement', 'SVGElement', 'Node']) globalThis[key] = window[key]
globalThis.window = window
globalThis.localStorage = window.localStorage
let prefersLight = true, reduced = false
globalThis.matchMedia = window.matchMedia = query => ({ matches: query.includes('reduced-motion') ? reduced : prefersLight })
after(() => window.happyDOM.close())
const { createApp, nextTick } = await import('vue')
const { loadVue } = await import('../test-utils/vue.js')
const { setThemeMode, themeMode, theme } = await import('../theme.js')
const Toggle = await loadVue(new URL('./ThemeToggle.vue', import.meta.url))

function mount(t, { mode = 'light', light = true, reduce = false, animate = false } = {}) {
  prefersLight = light; reduced = reduce
  setThemeMode(mode)
  const transitions = []
  window.document.startViewTransition = animate ? update => {
    let finish
    const transition = { ready: Promise.resolve(), finished: new Promise(resolve => { finish = resolve }),
      run: update, finish: () => finish(), skipped: false, skipTransition() { this.skipped = true; finish() } }
    transitions.push(transition)
    return transition
  } : undefined
  const root = document.createElement('div'); document.body.append(root)
  const app = createApp(Toggle); app.mount(root)
  t.after(() => { app.unmount(); root.remove(); transitions.forEach(item => item.finish()); delete document.startViewTransition })
  return { app, root, transitions, button: root.querySelector('button'),
    active: () => root.querySelector('svg[data-active="true"]')?.getAttribute('data-app-icon') }
}

test('one button cycles through all three modes and shows the current mode without a menu', async t => {
  const view = mount(t)
  assert.equal(view.root.querySelectorAll('button').length, 1)
  assert.equal(view.button.getAttribute('aria-haspopup'), null)
  assert.equal(view.active(), 'sun')
  for (const [mode, actual, icon] of [['dark', 'dark', 'moon'], ['auto', 'light', 'auto'], ['light', 'light', 'sun']]) {
    view.button.click(); await nextTick()
    assert.equal(themeMode.value, mode)
    assert.equal(theme.value, actual)
    assert.equal(view.active(), icon)
    assert.equal(localStorage.getItem('gm-theme'), mode)
  }
  assert.match(view.button.getAttribute('aria-label'), /当前为日间模式.*切换到夜间模式/)
  const auto = view.root.querySelector('[data-app-icon="auto"]')
  assert.ok(auto.querySelector('[data-icon-part="orbit"]'), 'automatic mode has its own drawn icon')
})

test('automatic mode is indicated even when browser appearance remains dark, without a redundant page wipe', async t => {
  const view = mount(t, { mode: 'dark', light: false, animate: true })
  view.button.click(); await nextTick()
  assert.equal(themeMode.value, 'auto')
  assert.equal(theme.value, 'dark')
  assert.equal(view.active(), 'auto')
  assert.match(view.button.getAttribute('aria-label'), /自动模式（跟随浏览器）.*日间模式/)
  assert.equal(view.transitions.length, 0)
})

test('rapid clicks commit each step immediately without a full-page transition', async t => {
  const view = mount(t, { animate: true })
  for (const mode of ['dark', 'auto', 'light', 'dark']) {
    view.button.click()
    assert.equal(themeMode.value, mode, 'each click updates the selection before another task runs')
  }
  await nextTick()
  assert.equal(theme.value, 'dark')
  assert.equal(view.active(), 'moon')
  assert.equal(view.transitions.length, 0, 'page snapshot layers must not intercept later clicks')
})

test('reduced motion and an unavailable page transition API keep the same three-state behavior', async t => {
  const view = mount(t, { reduce: true })
  let transitionCalls = 0
  document.startViewTransition = () => { transitionCalls++; throw new Error('transition unavailable') }
  view.button.click(); await nextTick()
  assert.equal(themeMode.value, 'dark')
  assert.equal(view.active(), 'moon')
  view.button.click(); await nextTick()
  assert.equal(themeMode.value, 'auto')
  assert.equal(view.active(), 'auto')
  assert.equal(transitionCalls, 0)
})
