import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { installIconMotion } from './icon-motion.js'
import { loadVue, mount, nodes } from './test-utils/vue.js'

const windows = []
after(() => Promise.all(windows.map(win => win.happyDOM.close())))
const icon = (name, attrs = '') => `<svg data-app-icon="${name}" ${attrs}><g data-icon-part="body"><path data-icon-part="${name === 'check' ? 'stroke' : 'path'}" d="M5 12h14"/>${name === 'calendar' ? '<g data-icon-part="cells"><path/></g>' : ''}${name === 'grid' ? '<path data-icon-part="tile"/><path data-icon-part="tile"/>' : ''}</g></svg>`
function setup(t, markup = `<button>${icon('refresh')}</button>`) {
  const win = new Window(); windows.push(win)
  win.document.body.innerHTML = markup
  const media = new win.EventTarget(); media.matches = false
  win.matchMedia = () => media
  const calls = []
  win.Element.prototype.animate = function (frames, options) {
    const animation = { target: this, frames, options, cancelled: false, onfinish: null, oncancel: null,
      cancel() { this.cancelled = true; this.oncancel?.() }, finish() { this.onfinish?.() } }
    calls.push(animation); return animation
  }
  const controller = installIconMotion(win.document)
  t.after(() => controller.destroy())
  const $ = selector => win.document.querySelector(selector)
  const click = (target = $('button'), options = {}) => {
    const event = new win.MouseEvent('click', { bubbles: true, cancelable: true, detail: 1, ...options })
    target.dispatchEvent(event); return event
  }
  const flush = () => win.happyDOM.waitUntilComplete()
  return { win, $, media, calls, controller, click, flush }
}

test('click and keyboard activation animate only the inner group without changing navigation or outer transforms', async t => {
  const { $, click, calls, flush } = setup(t, `<a href="#calendar">${icon('refresh', 'style="transform:rotate(180deg)"')}</a>`)
  let actions = 0
  $('a').addEventListener('click', () => actions++)
  const event = click($('path'), { detail: 0 })
  assert.equal(event.defaultPrevented, false)
  assert.equal(actions, 1)
  assert.equal(calls.length, 0, 'action runs before deferred feedback')
  await flush()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].target, $('[data-icon-part="body"]'))
  assert.equal(calls[0].options.duration, 1000)
  assert.deepEqual(calls[0].frames.map(frame => frame.transform), ['rotate(0deg)', 'rotate(360deg)'])
  assert.equal($('svg').style.transform, 'rotate(180deg)')
  assert.equal($('a').getAttribute('href'), '#calendar')
  calls[0].finish()
  assert.equal($('[data-icon-part="body"]').getAttribute('style'), null)
})

test('disabled, busy, opt-out, spinning and decorative icons stay still', async t => {
  const { $, click, calls, flush, win } = setup(t, [
    `<button disabled>${icon('plus')}</button>`, `<button aria-disabled="true">${icon('plus')}</button>`,
    `<button aria-busy="true">${icon('refresh')}</button>`, `<button>${icon('refresh', 'class="spinning"')}</button>`,
    `<button data-icon-motion="off">${icon('refresh')}</button>`, `<button>${icon('refresh', 'data-icon-motion="off"')}</button>`,
    `<button>${icon('refresh', 'style="animation-name:custom-spinner"')}</button>`,
    `<div>${icon('calendar')}</div>`, `<fieldset disabled><button>${icon('plus')}</button></fieldset>`,
  ].join(''))
  for (const target of win.document.querySelectorAll('svg')) click(target)
  await flush(); assert.equal(calls.length, 0)
  assert.ok($('[data-icon-motion="off"]'))
})

test('busy flags set by the action prevent feedback and later changes cancel active instances', async t => {
  const { $, click, calls, flush } = setup(t)
  $('button').addEventListener('click', () => queueMicrotask(() => $('button').setAttribute('aria-busy', 'true')), { once: true })
  click(); await flush(); assert.equal(calls.length, 0)
  $('button').removeAttribute('aria-busy')
  click(); await flush(); assert.equal(calls.length, 1)
  $('svg').setAttribute('data-icon-motion', 'off'); await flush()
  assert.equal(calls[0].cancelled, true)
})

test('repeated clicks replace animation instances and stale finish events cannot remove replacements', async t => {
  const { click, calls, flush, controller } = setup(t)
  click(); await flush()
  const staleFinish = calls[0].onfinish
  click(); await flush()
  assert.equal(calls.length, 2)
  assert.equal(calls[0].cancelled, true)
  staleFinish()
  controller.destroy()
  assert.equal(calls[1].cancelled, true)
  click(); await flush(); assert.equal(calls.length, 2)
})

test('reduced-motion changes cancel all parts, prevent new feedback and can be switched back', async t => {
  const { click, calls, flush, media, win } = setup(t, `<button>${icon('calendar')}</button>`)
  click(); await flush(); assert.equal(calls.length, 2)
  media.matches = true; media.dispatchEvent(new win.Event('change'))
  assert.ok(calls.every(animation => animation.cancelled))
  click(); await flush(); assert.equal(calls.length, 2)
  media.matches = false; media.dispatchEvent(new win.Event('change'))
  click(); await flush(); assert.equal(calls.length, 4)
})

test('removed controls and destroyed pending clicks release all animation ownership', async t => {
  const { $, click, calls, flush, controller } = setup(t)
  click(); await flush()
  $('button').remove(); await flush()
  assert.equal(calls[0].cancelled, true)
  controller.destroy()
  const second = setup(t)
  second.click(); second.controller.destroy(); await second.flush()
  assert.equal(second.calls.length, 0)
})

test('image rendering and non-browser renderers never start animations', async t => {
  assert.doesNotThrow(() => installIconMotion(undefined).destroy())
  assert.doesNotThrow(() => installIconMotion({}).destroy())
  const { win, click, calls, flush } = setup(t)
  win.__RENDER_STATE__ = { state: 'ready' }
  click(); await flush(); assert.equal(calls.length, 0)
})

test('theme feedback follows the newly active icon and includes summary and role buttons', async t => {
  const { $, click, calls, flush, win } = setup(t, `<button>${icon('sun', 'data-active="false"')}${icon('moon', 'data-active="true"')}</button><details><summary>${icon('chevron')}</summary></details><div role="button">${icon('search')}</div>`)
  $('button').addEventListener('click', () => queueMicrotask(() => {
    $('[data-app-icon="sun"]').setAttribute('data-active', 'true')
    $('[data-app-icon="moon"]').setAttribute('data-active', 'false')
  }))
  click(); await flush()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].target.closest('svg').getAttribute('data-app-icon'), 'sun')
  click($('summary')); click($('[role="button"]')); await flush()
  assert.equal(calls.length, 3)
  win.document.dispatchEvent(new win.MouseEvent('mouseover', { bubbles: true })); await flush()
  assert.equal(calls.length, 3)
})

test('AppIcon retains the existing geometry and exposes stable internal motion parts', async t => {
  const AppIcon = await loadVue(new URL('./components/AppIcon.vue', import.meta.url))
  for (const name of ['refresh', 'calendar', 'grid', 'menu', 'check', 'unknown']) {
    const root = mount(t, AppIcon, { name, size: 20 })
    const svg = nodes(root, 'svg')[0]
    assert.equal(svg.props.width, 20)
    assert.equal(svg.props['data-app-icon'], name === 'unknown' ? 'grid' : name)
    assert.equal(svg.props['aria-hidden'], 'true')
    assert.equal(nodes(root,'g')[0].props['data-icon-part'], 'body')
    assert.ok(nodes(root, 'path').every(path => path.props.d))
    if (name === 'grid') assert.equal(nodes(root,'path').length, 4)
    if (name === 'menu') assert.equal(nodes(root,'path').length, 3)
    if (name === 'check') assert.equal(nodes(root,'path')[0].props.pathLength, 1)
  }
})

test('a delayed theme swap animates the new icon once and cancels the old one', async t => {
  const { $, click, calls, flush } = setup(t, `<button>${icon('sun', 'data-active="false"')}${icon('moon', 'data-active="true"')}</button>`)
  click(); await flush()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].target.closest('svg').getAttribute('data-app-icon'), 'moon')
  // startViewTransition can run its update callback in a later browser task.
  await new Promise(resolve => setTimeout(resolve, 0))
  $('[data-app-icon="moon"]').setAttribute('data-active', 'false')
  $('[data-app-icon="sun"]').setAttribute('data-active', 'true')
  await flush()
  assert.equal(calls[0].cancelled, true)
  assert.equal(calls.length, 2)
  assert.equal(calls[1].target.closest('svg').getAttribute('data-app-icon'), 'sun')
  $('[data-app-icon="sun"]').setAttribute('data-active', 'true')
  $('[data-app-icon="sun"]').setAttribute('data-app-icon', 'sun')
  await flush()
  assert.equal(calls.length, 2, 'duplicate observer records do not restart the animation')
})

test('automatic theme changes and expired click records never authorize feedback', async t => {
  const { $, click, calls, flush, win } = setup(t, `<button>${icon('sun', 'data-active="false"')}${icon('moon', 'data-active="true"')}</button>`)
  let now = 0
  t.mock.method(win.performance, 'now', () => now)
  $('[data-app-icon="moon"]').setAttribute('data-active', 'false')
  $('[data-app-icon="sun"]').setAttribute('data-active', 'true')
  await flush(); assert.equal(calls.length, 0)
  click(); await flush(); assert.equal(calls.length, 1)
  now = 1300
  $('[data-app-icon="sun"]').setAttribute('data-active', 'false')
  $('[data-app-icon="moon"]').setAttribute('data-active', 'true')
  await flush(); assert.equal(calls.length, 1)
  assert.equal(calls[0].cancelled, true)
})

test('delayed replacement honors reduced motion, opt-out, disabled and destroyed controllers', async t => {
  for (const boundary of ['reduced', 'disabled', 'off', 'destroy']) {
    const { $, click, calls, flush, media, win, controller } = setup(t, `<button>${icon('moon')}</button>`)
    click(); await flush()
    if (boundary === 'reduced') {
      media.matches = true; media.dispatchEvent(new win.Event('change'))
      media.matches = false; media.dispatchEvent(new win.Event('change'))
    } else if (boundary === 'disabled') $('button').disabled = true
    else if (boundary === 'off') $('svg').setAttribute('data-icon-motion', 'off')
    else controller.destroy()
    await new Promise(resolve => setTimeout(resolve, 0))
    $('svg').setAttribute('data-app-icon', 'sun')
    await flush()
    assert.equal(calls.length, 1, boundary)
    assert.equal(calls[0].cancelled, true, boundary)
  }
})

test('a clicked control whose icon name changes later receives only one replacement animation', async t => {
  const { $, click, calls, flush } = setup(t, `<button>${icon('moon')}</button>`)
  click(); await flush()
  await new Promise(resolve => setTimeout(resolve, 0))
  $('svg').setAttribute('data-app-icon', 'sun'); await flush()
  assert.equal(calls[0].cancelled, true)
  assert.equal(calls.length, 2)
  assert.deepEqual(calls[1].frames.map(frame => frame.transform), ['rotate(0deg)', 'rotate(90deg)'])
  $('svg').setAttribute('data-app-icon', 'sun'); await flush()
  assert.equal(calls.length, 2)
})
