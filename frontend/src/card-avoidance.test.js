import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { cardAvoidance, createCardAvoidance } from './card-avoidance.js'

const viewport = { left: 0, right: 1440 }
const box = (left, top, width, height = 200) => ({ left, top, width, height, right: left + width, bottom: top + height })
const menuAt = left => box(left, 20, 220, 400)
const wide = box(24, 100, 1392)

test('cards react independently, with no response outside the menu rectangle', () => {
  const menu = menuAt(16)
  const affected = cardAvoidance(box(24, 100, 900), menu, viewport)
  assert.ok(affected.loss > 0)
  for (const rect of [box(1000, 100, 400), box(24, 500, 900), box(24, -250, 900)]) {
    const result = cardAvoidance(rect, menu, viewport)
    assert.equal(result.loss, 0)
    assert.equal(result.inset, 0)
  }
})

test('edge docking clears a card when there is room, but central travel adds only a limited response', () => {
  const edge = cardAvoidance(wide, menuAt(16), viewport)
  assert.equal(edge.covered, false)
  assert.ok(wide.left + edge.inset >= menuAt(16).right)
  let previous = edge
  for (const x of [150, 300, 500, 650]) {
    const result = cardAvoidance(wide, menuAt(x), viewport, previous.side)
    assert.ok(result.loss - edge.loss <= (x - 16) / 3 + 0.01, 'extra squeezing cannot follow full menu travel')
    assert.ok(result.loss < wide.width / 3 + 0.01, 'the response remains bounded')
    assert.equal(result.side, edge.side, 'crossing the middle must not flip the response direction')
    previous = result
  }
  assert.equal(previous.covered, true, 'a central menu may cover a card once its response is exhausted')
})

test('both small and large cards allow overlap when clearing the menu would squeeze them too far', () => {
  for (const width of [240, 320, 600, 1392]) {
    const rect = box(24, 100, width)
    const menu = menuAt(width < 400 ? 40 : 300)
    const result = cardAvoidance(rect, menu, viewport, 'left')
    assert.equal(result.covered, true, `width ${width}: overlap must remain allowed`)
    assert.ok(result.loss <= width / 3)
    assert.ok(width - result.loss >= Math.min(width, 272), 'a readable card cannot be reduced indefinitely')
    assert.equal(result.inset, result.loss)
  }
})

test('reaching the opposite edge restores a clear response on that side', () => {
  const start = cardAvoidance(wide, menuAt(16), viewport)
  const middle = cardAvoidance(wide, menuAt(600), viewport, start.side)
  const end = cardAvoidance(wide, menuAt(1204), viewport, middle.side)
  assert.equal(middle.side, start.side)
  assert.equal(end.side, 'right')
  assert.equal(end.covered, false)
  assert.equal(end.inset, 0)
  assert.ok(wide.right - end.loss <= menuAt(1204).left)
})

const window = new Window()
after(() => window.happyDOM.close())
function setup(t) {
  const root = window.document.createElement('main')
  root.innerHTML = '<section class="ov-hero"></section><section class="ov-tasks"></section>'
  window.document.body.append(root)
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
  Object.defineProperty(window, 'scrollY', { configurable: true, value: 0, writable: true })
  let nextId = 0, now = 0
  const frames = new Map()
  t.mock.method(window, 'requestAnimationFrame', callback => { frames.set(++nextId, callback); return nextId })
  t.mock.method(window, 'cancelAnimationFrame', id => frames.delete(id))
  const geometries = [box(24, 100, 900), box(1000, 100, 400)]
  const reads = [0, 0]
  const cards = [...root.children]
  cards.forEach((el, i) => { el.getBoundingClientRect = () => { reads[i]++; return geometries[i] } })
  const controller = createCardAvoidance(root)
  const step = () => {
    const callbacks = [...frames.values()]; frames.clear(); now += 16.67
    callbacks.forEach(callback => callback(now))
  }
  const flush = () => {
    for (let i = 0; i < 240 && frames.size; i++) {
      step()
    }
    assert.equal(frames.size, 0, 'animation must settle')
  }
  t.after(() => { controller.destroy(); root.remove() })
  return { root, cards, geometries, reads, controller, flush, step, frames }
}

test('DOM updates change only overlapping cards and leave elastic transforms untouched', t => {
  const { cards, controller, flush } = setup(t)
  cards[0].style.translate = '4px 2px'
  cards[0].style.rotate = '.2deg'
  cards[0].style.scale = '.994'
  cards[0].style.transform = 'translateY(6px)'
  const before = ['translate', 'rotate', 'scale', 'transform'].map(key => cards[0].style[key])
  controller.update(menuAt(16), true); flush()
  assert.ok(parseFloat(cards[0].style.width) < 900)
  assert.ok(parseFloat(cards[0].style.marginLeft) > 0)
  assert.equal(cards[1].style.cssText, '', 'unaffected cards retain their original styles')
  assert.deepEqual(['translate', 'rotate', 'scale', 'transform'].map(key => cards[0].style[key]), before)
})

test('page and nested-rail scrolling, resize and explicit refresh measure the layout again', t => {
  const { cards, geometries, reads, controller, flush } = setup(t)
  controller.update(menuAt(16), true); flush()
  let previous = reads[0]
  geometries[0] = box(400, 100, 900)
  cards[0].dispatchEvent(new window.Event('scroll'))
  flush()
  assert.ok(reads[0] > previous)
  assert.equal(cards[0].style.width, '', 'a card scrolled away from the menu returns to its normal width')
  previous = reads[0]
  window.document.dispatchEvent(new window.Event('scroll')); flush()
  assert.ok(reads[0] > previous)
  previous = reads[0]
  window.dispatchEvent(new window.Event('resize')); flush()
  assert.ok(reads[0] > previous)
  previous = reads[0]
  geometries[0] = box(24, 100, 900)
  controller.refresh(); flush()
  assert.ok(reads[0] > previous)
  assert.ok(parseFloat(cards[0].style.width) < 900)
})

test('route content replacement is discovered and removed cards recover original styles', async t => {
  const { root, cards, controller, flush } = setup(t)
  cards[0].style.width = '80%'
  controller.update(menuAt(16), true); flush()
  const replacement = window.document.createElement('section')
  replacement.className = 'cap-card'
  replacement.getBoundingClientRect = () => box(24, 100, 800)
  cards[0].replaceWith(replacement)
  await new Promise(resolve => window.setTimeout(resolve, 0))
  flush()
  assert.equal(cards[0].style.width, '80%')
  assert.ok(parseFloat(replacement.style.width) < 800)
  assert.equal(root.contains(replacement), true)
})

test('mobile disable and destruction restore exact inline values and priorities', t => {
  const { cards, controller, flush, frames } = setup(t)
  const card = cards[0]
  card.style.setProperty('width', '80%', 'important')
  card.style.setProperty('margin-left', '3px', 'important')
  card.style.marginRight = '7px'
  card.style.color = 'red'
  const saved = card.style.cssText
  controller.update(menuAt(16), true); flush()
  assert.notEqual(card.style.cssText, saved)
  controller.update(menuAt(16), false)
  assert.equal(card.style.cssText, saved)
  assert.equal(card.hasAttribute('data-menu-avoidance'), false)
  controller.update(menuAt(16), true); flush()
  controller.update(menuAt(300), true)
  assert.ok(frames.size)
  controller.destroy()
  assert.equal(card.style.cssText, saved)
  assert.equal(frames.size, 0)
  window.dispatchEvent(new window.Event('resize'))
  assert.equal(frames.size, 0)
})

test('remeasuring after scroll or resize preserves the approach side while the menu remains central', t => {
  const { cards, geometries, controller, flush } = setup(t)
  geometries[0] = wide
  controller.update(menuAt(16), true); flush()
  controller.update(menuAt(720), true); flush()
  assert.ok(parseFloat(cards[0].style.marginLeft) > 0, 'central travel retains its left-edge approach')
  window.document.dispatchEvent(new window.Event('scroll')); flush()
  assert.ok(parseFloat(cards[0].style.marginLeft) > 0, 'scroll measurement must not switch to the other side')
  window.dispatchEvent(new window.Event('resize')); flush()
  assert.ok(parseFloat(cards[0].style.marginLeft) > 0, 'resize measurement must retain the same approach')
})

test('cards moved by text wrapping in earlier rows use their actual vertical position', t => {
  const { cards, geometries, controller, flush } = setup(t)
  geometries[1] = box(1000, 500, 400)
  controller.update(menuAt(1100), true); flush()
  assert.equal(cards[1].style.width, '')
  // Layout changed without a route mutation, scroll, or viewport resize.
  geometries[1] = box(1000, 100, 400)
  controller.update(menuAt(1100), true); flush()
  assert.ok(parseFloat(cards[1].style.width) < 400)
  geometries[1] = box(1000, 500, 400)
  controller.update(menuAt(1100), true); flush()
  assert.equal(cards[1].style.width, '')
})

test('independent card movement does not resnap every sibling in a horizontal rail', async t => {
  const { root, cards, controller, flush } = setup(t)
  const rail = window.document.createElement('div')
  rail.className = 'h-rail-track'
  rail.style.setProperty('scroll-snap-type', 'x mandatory', 'important')
  rail.style.overflowAnchor = 'auto'
  root.append(rail); rail.append(cards[0])
  await new Promise(resolve => window.setTimeout(resolve, 0))
  controller.update(menuAt(16), true); flush()
  assert.equal(rail.style.scrollSnapType, 'none')
  assert.equal(rail.style.overflowAnchor, 'none')
  controller.update(menuAt(1100), true); flush()
  assert.equal(rail.style.scrollSnapType, 'x mandatory')
  assert.equal(rail.style.getPropertyPriority('scroll-snap-type'), 'important')
  assert.equal(rail.style.overflowAnchor, 'auto')
  controller.update(menuAt(16), true); flush()
  controller.update(null, false)
  assert.equal(rail.style.scrollSnapType, 'x mandatory')
})

test('standalone game navigation, identity and status rows follow the same edge rule as cards', async t => {
  const { root, controller, flush } = setup(t)
  const page = window.document.createElement('section')
  page.className = 'game-card'
  page.innerHTML = '<div class="detail-navigation"><nav>游戏分区</nav></div><header class="lol-header">账号</header><div class="lol-toolbar"><nav>时间与模式</nav></div><p class="coverage-line">当前展示</p><section class="cap-card"><header>卡片里的标题</header></section>'
  for (const el of page.children) el.getBoundingClientRect = () => box(24, 100, 1392)
  root.append(page)
  await new Promise(resolve => window.setTimeout(resolve, 0))
  controller.update(menuAt(16), true); flush()
  for (const el of page.children) {
    assert.ok(parseFloat(el.style.marginLeft) > 0, el.className)
    assert.equal(el.dataset.menuAvoidance, 'clear', el.className)
  }
  assert.equal(page.style.width, '', 'the multi-card page remains in its original layout')
  assert.equal(page.querySelector('.cap-card header').style.width, '', 'content inside a card follows its card once')
})

test('scroll approach grows continuously before the card border reaches the menu', () => {
  const menu = menuAt(16)
  const losses = [1, 12, 32, 64, 96].map(depth => cardAvoidance(box(24, menu.bottom+64-depth, 900), menu, viewport).loss)
  assert.ok(losses[0] < 1)
  assert.ok(losses[1] < losses.at(-1) / 10)
  assert.ok(losses.every((value, i) => !i || value > losses[i-1]))
})

test('scroll and remeasurement keep the current spring position rather than snapping to its target', t => {
  const { cards, geometries, controller, flush, step } = setup(t)
  geometries[0] = box(24, 500, 900)
  controller.update(menuAt(16), true); flush()
  geometries[0] = box(24, 100, 900)
  window.document.dispatchEvent(new window.Event('scroll')); step()
  const first = parseFloat(cards[0].style.marginLeft)
  assert.ok(first > 0 && first < 40, 'the first scroll frame only begins the response')
  controller.refresh(); step()
  const second = parseFloat(cards[0].style.marginLeft)
  assert.ok(second > first && second < 80, 'measurement retains both position and momentum')
  flush()
  const full = parseFloat(cards[0].style.marginLeft)
  assert.ok(full > 200)
  geometries[0] = box(24, 500, 900)
  window.document.dispatchEvent(new window.Event('scroll')); step()
  const returning = parseFloat(cards[0].style.marginLeft)
  assert.ok(returning > 150 && returning < full, 'leaving the menu also returns through the spring')
  flush(); assert.equal(cards[0].style.width, '')
})

test('account panel frames and Wuwa section headings participate without double-moving their children', async t => {
  const { root, controller, flush } = setup(t)
  const panel = window.document.createElement('section')
  panel.className = 'login-panel'; panel.innerHTML='<header class="panel-header">账号</header><div class="account-row">鸣潮</div>'
  const heading=window.document.createElement('header');heading.className='wuwa-board-head';heading.textContent='玩法进度'
  for(const el of [panel, heading]){el.getBoundingClientRect=()=>box(24,100,1392);root.append(el)}
  await new Promise(resolve=>window.setTimeout(resolve,0));controller.update(menuAt(16),true);flush()
  assert.equal(panel.dataset.menuAvoidance,'clear');assert.equal(heading.dataset.menuAvoidance,'clear')
  assert.ok(parseFloat(panel.style.marginLeft)>200)
  assert.equal(panel.querySelector('.account-row').style.width,'')
})
