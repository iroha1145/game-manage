import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { ref, nextTick, h } from 'vue'
import { mount } from './test-utils/vue.js'
import { createFloatingNavigation, navigationBounds, projectNavigationCorner, useFloatingNavigation } from './floating-navigation.js'

const windows = []
after(() => Promise.all(windows.map(win => win.happyDOM.close())))
function setup(t, mobile = false, reduced = false) {
  const win = new Window({ width: mobile ? 390 : 1200, height: 800 }); windows.push(win)
  win.document.body.innerHTML = '<div id="root"><div id="surface"><button id="grip">Move</button><aside><button id="first">Games</button><button>Settings</button></aside><nav><button id="toggle">Menu</button></nav></div><main tabindex="-1">Content</main></div>'
  const $ = selector => win.document.querySelector(selector)
  const media = new win.EventTarget(); media.matches = reduced
  win.matchMedia = () => media
  let id = 0, time = 0; const frames = new Map()
  win.requestAnimationFrame = callback => { frames.set(++id, callback); return id }
  win.cancelAnimationFrame = key => frames.delete(key)
  Object.defineProperty($('#surface'), 'offsetWidth', { value: 220 })
  Object.defineProperty($('#surface'), 'offsetHeight', { value: 300 })
  Object.defineProperty($('aside'), 'offsetHeight', { value: 350 })
  const refs = { root: ref($('#root')), surface: ref($('#surface')), sidebar: ref($('aside')), menuToggle: ref($('#toggle')), menuOpen: ref(false), mobileNavigation: ref(mobile) }
  const controller = createFloatingNavigation(refs)
  $('#grip').addEventListener('pointerdown', controller.onGripPointerdown)
  $('#toggle').addEventListener('pointerdown', controller.onTogglePointerdown)
  $('#toggle').addEventListener('click', controller.onToggleClick)
  const pointer = (type, x, y, target = $('#grip')) => target.dispatchEvent(new win.PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 1, isPrimary: true, button: 0, clientX: x, clientY: y }))
  const flush = () => {
    for (let n = 0; n < 180 && frames.size; n++) {
      const callbacks = [...frames.values()]; frames.clear(); time += 16.67
      callbacks.forEach(fn => fn(time))
    }
    assert.equal(frames.size, 0)
  }
  t.after(() => controller.destroy())
  return { win, $, refs, controller, pointer, flush, frames, media }
}

test('inertia projects independently on each axis and bounds fit small viewports', () => {
  const b = navigationBounds(1200, 800, 220, 300)
  assert.deepEqual(b, { left: 16, top: 16, right: 964, bottom: 484 })
  assert.equal(projectNavigationCorner(450, 220, 1000, 1000, b), 'bottom-right')
  assert.equal(projectNavigationCorner(450, 220, -10000, -10000, b), 'top-left')
  assert.deepEqual(navigationBounds(100, 100, 200, 200), { left: 16, top: 16, right: 16, bottom: 16 })
})

test('desktop drag updates content reservation live and cancel returns to saved corner', t => {
  const { $, pointer, flush, win } = setup(t)
  pointer('pointerdown', 30, 30)
  pointer('pointermove', 34, 32)
  assert.equal($('#root').dataset.navDragging, 'false')
  pointer('pointermove', 800, 400)
  assert.equal($('#root').dataset.navDragging, 'true')
  assert.equal($('#root').style.getPropertyValue('--nav-reserve-left'), '0px')
  assert.equal($('#root').style.getPropertyValue('--nav-reserve-right'), '414px')
  pointer('pointercancel', 800, 400)
  flush()
  assert.equal($('#surface').style.transform, 'translate3d(16.00px, 16.00px, 0)')
  pointer('pointerdown', 30, 30)
  pointer('pointermove', 2000, 2000)
  pointer('pointerup', 2000, 2000)
  flush()
  assert.equal($('#surface').style.transform, 'translate3d(964.00px, 484.00px, 0)')
  assert.equal(win.localStorage.getItem('game-manage-navigation-corner'), 'bottom-right')
})

test('mobile drag opens, suppresses pointer click, traps focus, and external close preserves main focus', async t => {
  const { $, refs, pointer, flush, win, controller } = setup(t, true)
  win.document.body.style.overflow = 'clip'
  pointer('pointerdown', 100, 750, $('#toggle'))
  pointer('pointermove', 100, 500, $('#toggle'))
  pointer('pointerup', 100, 500, $('#toggle'))
  $('#toggle').dispatchEvent(new win.MouseEvent('click', { bubbles: true, detail: 1 }))
  assert.equal(refs.menuOpen.value, true)
  assert.equal(win.document.body.style.overflow, 'hidden')
  flush(); await nextTick()
  assert.equal($('#root').style.getPropertyValue('--drawer-progress'), '1')
  assert.equal(win.document.activeElement, $('#first'))
  $('#toggle').focus()
  const tab = new win.KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
  controller.handleKey(tab)
  assert.equal(tab.defaultPrevented, true)
  assert.equal(win.document.activeElement, $('#grip'))
  $('main').focus(); refs.menuOpen.value = false
  flush(); await nextTick()
  assert.equal(win.document.activeElement, $('main'))
  assert.equal(win.document.body.style.overflow, 'clip')
  assert.equal($('#root').style.getPropertyValue('--drawer-progress'), '0')
})

test('cancelled drawer restores detent, reduced motion settles instantly, cleanup releases resources', async t => {
  const { $, refs, pointer, frames, win, controller } = setup(t, true, true)
  pointer('pointerdown', 100, 750)
  pointer('pointermove', 100, 550)
  assert.equal(refs.menuOpen.value, true)
  pointer('pointercancel', 100, 550)
  assert.equal(refs.menuOpen.value, false)
  assert.equal($('#root').style.getPropertyValue('--drawer-progress'), '0')
  controller.openMenu(); await nextTick()
  assert.equal(frames.size, 0)
  controller.closeMenu(); await nextTick()
  assert.equal(win.document.activeElement, $('#toggle'))
  controller.openMenu()
  controller.destroy(); await nextTick()
  assert.equal(win.document.body.style.overflow, '')
  assert.equal(frames.size, 0)
  assert.equal($('#root').style.getPropertyValue('--drawer-progress'), '')
  pointer('pointermove', 100, 100)
  assert.equal($('#root').style.getPropertyValue('--drawer-progress'), '')
})

test('page pointers do not intercept scrolling, keyboard click is not suppressed by a drag', t => {
  const { $, pointer, controller, refs, win } = setup(t, true, true)
  assert.equal(pointer('pointerdown', 10, 10, $('main')), true)
  assert.equal(pointer('pointermove', 10, 100, $('main')), true)
  assert.equal(refs.menuOpen.value, false)
  pointer('pointerdown', 100, 750)
  pointer('pointermove', 100, 500)
  pointer('pointerup', 100, 500)
  controller.onToggleClick(new win.MouseEvent('click', { detail: 0 }))
  assert.equal(refs.menuOpen.value, false)
})

test('external route close cancels an active drag and resize repositions a desktop corner', async t => {
  const mobile = setup(t, true, true)
  mobile.pointer('pointerdown', 100, 750)
  mobile.pointer('pointermove', 100, 500)
  mobile.refs.menuOpen.value = false
  mobile.pointer('pointerup', 100, 300)
  assert.equal(mobile.refs.menuOpen.value, false)
  assert.equal(mobile.$('#root').style.getPropertyValue('--drawer-progress'), '0')
  const desktop = setup(t, false, true)
  desktop.controller.onGripKeydown(new desktop.win.KeyboardEvent('keydown', { key: 'ArrowRight', cancelable: true }))
  desktop.win.happyDOM.setWindowSize({ width: 1000, height: 650 })
  desktop.win.dispatchEvent(new desktop.win.Event('resize'))
  assert.equal(desktop.$('#surface').style.transform, 'translate3d(764.00px, 16.00px, 0)')
  desktop.refs.mobileNavigation.value = true
  await nextTick()
  assert.equal(desktop.$('#surface').style.transform, '')
  assert.equal(desktop.$('#root').style.getPropertyValue('--nav-reserve-right'), '0px')
})


test('custom renderers without browser documents mount and dispose without DOM effects', async t => {
  let navigation
  const menuOpen = ref(false)
  const component = {
    setup() {
      const root = ref(null), surface = ref(null), sidebar = ref(null)
      navigation = useFloatingNavigation({ root, surface, sidebar, menuToggle: ref(null), menuOpen, mobileNavigation: ref(true) })
      return () => h('main', { ref: root }, [h('section', { ref: surface }, [h('aside', { ref: sidebar })])])
    },
  }
  assert.doesNotThrow(() => mount(t, component))
  await nextTick()
  navigation.openMenu()
  assert.equal(menuOpen.value, true)
  navigation.closeMenu()
  assert.equal(menuOpen.value, false)
  navigation.toggleMenu()
  assert.equal(menuOpen.value, true)
  navigation.onToggleClick()
  assert.equal(menuOpen.value, false)
  navigation.openMenu()
  assert.doesNotThrow(() => navigation.handleKey({ key: 'Escape' }))
  assert.equal(menuOpen.value, false)
  assert.doesNotThrow(() => navigation.onGripPointerdown({ button: 0 }))
})


test('drag compatibility click is suppressed but a fresh immediate tap is accepted', t => {
  const { $, pointer, refs, win, controller } = setup(t, true, true)
  controller.openMenu()
  pointer('pointerdown', 100, 400, $('#toggle'))
  pointer('pointermove', 100, 750, $('#toggle'))
  pointer('pointerup', 100, 750, $('#toggle'))
  assert.equal(refs.menuOpen.value, false)
  const ghost = new win.MouseEvent('click', { bubbles: true, cancelable: true, detail: 1 })
  $('#toggle').dispatchEvent(ghost)
  assert.equal(ghost.defaultPrevented, true)
  assert.equal(refs.menuOpen.value, false)
  pointer('pointerdown', 100, 750, $('#toggle'))
  pointer('pointerup', 100, 750, $('#toggle'))
  const deliberate = new win.MouseEvent('click', { bubbles: true, cancelable: true, detail: 1 })
  $('#toggle').dispatchEvent(deliberate)
  assert.equal(deliberate.defaultPrevented, false)
  assert.equal(refs.menuOpen.value, true)
})
