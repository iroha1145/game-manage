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

test('rapid clicks retain every step and delayed old callbacks cannot overwrite the latest choice', async t => {
  const view = mount(t, { animate: true })
  view.button.click()
  assert.equal(view.transitions.length, 1)
  view.button.click(); view.button.click(); view.button.click()
  assert.equal(view.transitions.length, 2)
  assert.equal(view.transitions[0].skipped, true)
  await view.transitions[1].run()
  await view.transitions[0].run()
  assert.equal(themeMode.value, 'dark', 'four clicks from light end in dark')
  assert.equal(theme.value, 'dark')
  assert.equal(view.active(), 'moon')
  view.transitions[1].finish(); await nextTick()
  assert.equal(document.documentElement.hasAttribute('data-theme-switching'), false)
})

test('reduced motion changes the mode immediately without a page transition', async t => {
  const view = mount(t, { animate: true, reduce: true })
  view.button.click(); await nextTick()
  assert.equal(themeMode.value, 'dark')
  assert.equal(view.active(), 'moon')
  assert.equal(view.transitions.length, 0)
})

test('a failed transition still applies the requested mode and clears temporary styles', async t => {
  const view = mount(t)
  document.startViewTransition = () => { throw new Error('transition unavailable') }
  view.button.click(); await nextTick()
  assert.equal(themeMode.value, 'dark')
  assert.equal(view.active(), 'moon')
  assert.equal(document.documentElement.hasAttribute('data-theme-switching'), false)
})

test('unmounting during a transition preserves the user choice and prevents a stale callback from changing it', async t => {
  const view = mount(t, { animate: true })
  view.button.click(); view.app.unmount()
  assert.equal(themeMode.value, 'dark')
  setThemeMode('auto')
  await view.transitions[0].run()
  assert.equal(themeMode.value, 'auto')
  assert.equal(document.documentElement.hasAttribute('data-theme-switching'), false)
  assert.equal(document.documentElement.style.getPropertyValue('--theme-r'), '')
})
