import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { createElasticCards } from './elastic-cards.js'

const window = new Window()
after(() => window.happyDOM.close())
function setup(t, markup = '<section data-elastic-card><h2>Card title</h2><button><span>Save</span></button><input><div class="calendar"><span>Calendar</span></div></section>', options) {
  const root = window.document.createElement('main')
  root.innerHTML = markup
  window.document.body.append(root)
  let id = 0
  const frames = new Map()
  t.mock.method(window, 'requestAnimationFrame', callback => { frames.set(++id, callback); return id })
  t.mock.method(window, 'cancelAnimationFrame', key => frames.delete(key))
  const media = new window.EventTarget()
  media.matches = false
  t.mock.method(window, 'matchMedia', () => media)
  const registrations = []
  for (const target of [root, window, window.document]) {
    const add = target.addEventListener.bind(target)
    t.mock.method(target, 'addEventListener', (type, listener, settings) => {
      registrations.push({ type, settings })
      add(type, listener, settings)
    })
  }
  const controller = createElasticCards(root, options)
  t.after(() => { controller.destroy(); root.remove() })
  const card = root.querySelector('section')
  const pointer = (type, target = card, extra = {}) => {
    const event = new window.PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 1, isPrimary: true, pointerType: 'mouse', button: 0, clientX: 0, clientY: 0, ...extra })
    target.dispatchEvent(event)
    return event
  }
  const flush = () => {
    for (let i = 0; i < 150 && frames.size; i++) {
      const pending = [...frames.values()]; frames.clear()
      pending.forEach(callback => callback(i * 16.67))
    }
  }
  return { root, card, pointer, frames, media, controller, flush, registrations }
}

test('mouse feedback stays bounded, preserves transforms and restores prior individual styles', t => {
  const { card, pointer, flush, frames } = setup(t)
  card.style.transform = 'translateY(4px)'
  card.style.setProperty('rotate', '2deg', 'important')
  pointer('pointerdown')
  assert.equal(card.style.scale, '0.99400')
  pointer('pointermove', card, { clientX: 5000, clientY: -5000 })
  assert.equal(card.style.translate, '8.000px -8.000px')
  assert.equal(card.style.rotate, '0.400deg')
  assert.equal(card.style.transform, 'translateY(4px)')
  pointer('pointerup')
  assert.equal(frames.size, 1)
  flush()
  assert.equal(frames.size, 0)
  assert.equal(card.style.translate, '')
  assert.equal(card.style.scale, '')
  assert.equal(card.style.rotate, '2deg')
  assert.equal(card.style.getPropertyPriority('rotate'), 'important')
})

test('touch observes passively, cancels vertical intent and never captures pointers or scrolling', t => {
  const { card, pointer, frames, registrations } = setup(t)
  for (const { type, settings } of registrations.filter(({ type }) => /^(pointer|scroll)/.test(type))) {
    assert.equal(settings.passive, true, `${type} must be passive`)
  }
  const capture = t.mock.method(card, 'setPointerCapture', () => assert.fail('must never capture'))
  card.style.touchAction = 'pan-y'
  const down = pointer('pointerdown', card, { pointerType: 'touch' })
  const move = pointer('pointermove', card, { pointerType: 'touch', clientX: 2, clientY: 16 })
  assert.equal(down.defaultPrevented, false)
  assert.equal(move.defaultPrevented, false)
  assert.equal(card.style.scale, '')
  assert.equal(card.style.touchAction, 'pan-y')
  assert.equal(capture.mock.callCount(), 0)
  pointer('pointermove', card, { pointerType: 'touch', clientX: 80, clientY: 16 })
  assert.equal(card.style.translate, '', 'a cancelled gesture stays cancelled')
  pointer('pointerdown', card, { pointerType: 'touch' })
  pointer('pointermove', card, { pointerType: 'touch', clientX: 50, clientY: 1 })
  assert.match(card.style.translate, /px 0.000px$/)
  const scroll = new window.Event('scroll', { cancelable: true })
  card.dispatchEvent(scroll)
  assert.equal(scroll.defaultPrevented, false)
  assert.equal(card.style.translate, '')
  assert.equal(frames.size, 0)
})

test('a touch tap below the movement threshold releases without a delayed shrink or rebound', t => {
  const { card, pointer, frames } = setup(t)
  card.style.setProperty('scale', '1.5')
  pointer('pointerdown', card, { pointerType: 'touch' })
  pointer('pointermove', card, { pointerType: 'touch', clientX: 3, clientY: 1 })
  assert.equal(card.style.scale, '1.5')
  pointer('pointerup', card, { pointerType: 'touch', clientX: 3, clientY: 1 })
  assert.equal(frames.size, 0, 'no spring frame after an unpainted tap')
  assert.equal(card.style.scale, '1.5')
  assert.equal(card.style.translate, '')
  pointer('pointerdown', card, { pointerType: 'touch' })
  pointer('pointermove', card, { pointerType: 'touch', clientX: 40, clientY: 1 })
  pointer('pointerup', card, { pointerType: 'touch', clientX: 40, clientY: 1 })
  assert.equal(frames.size, 1, 'a painted touch drag still springs back')
})

test('controls, calendar regions, editable text and scroll surfaces remain untouched', t => {
  const { card, root, pointer } = setup(t, '<section data-elastic-card><button><span>Save</span></button><input><a href="#">Link</a><div contenteditable>Text</div><div class="calendar"><span>Day</span></div><div style="overflow-y:auto"><span>Scroll</span></div></section>')
  for (const target of root.querySelectorAll('button span, input, a, [contenteditable], .calendar span, [style] span')) {
    pointer('pointerdown', target)
    pointer('pointermove', target, { clientX: 80 })
    assert.equal(card.style.scale, '', target.outerHTML)
  }
})

test('cancel, route reset, blur and disposal clean active feedback and pending frames', t => {
  const { card, pointer, controller, frames } = setup(t)
  pointer('pointerdown'); pointer('pointercancel')
  assert.equal(frames.size, 1)
  controller.reset()
  assert.equal(frames.size, 0)
  assert.equal(card.style.scale, '')
  pointer('pointerdown'); window.dispatchEvent(new window.Event('blur'))
  assert.equal(card.style.scale, '')
  pointer('pointerdown'); pointer('pointerup'); controller.destroy()
  assert.equal(frames.size, 0)
  assert.equal(card.style.scale, '')
  pointer('pointerdown')
  assert.equal(card.style.scale, '')
})

test('reduced motion disables feedback immediately and bot image roots stay excluded', t => {
  const { root, card, pointer, media, frames } = setup(t)
  pointer('pointerdown'); pointer('pointerup')
  media.matches = true
  media.dispatchEvent(new window.Event('change'))
  assert.equal(card.style.scale, '')
  assert.equal(frames.size, 0)
  pointer('pointerdown')
  assert.equal(card.style.scale, '')
  media.matches = false
  root.className = 'render-image'
  pointer('pointerdown')
  assert.equal(card.style.scale, '')
})

test('explicit selectors scope feedback and nested candidates cannot move a parent card', t => {
  const { root, card, pointer } = setup(t, '<section class="surface"><div class="surface">Nested</div></section><article>Other</article>', { selector: '.surface' })
  pointer('pointerdown', root.querySelector('article'))
  assert.equal(card.style.scale, '')
  pointer('pointerdown', card.querySelector('div'))
  assert.equal(card.style.scale, '')
  pointer('pointerdown')
  assert.equal(card.style.scale, '0.99400')
})

test('removing an active card restores its styles and multitouch returns to native handling', async t => {
  const { root, card, pointer, frames } = setup(t)
  pointer('pointerdown', card, { pointerType: 'touch' })
  pointer('pointerdown', card, { pointerType: 'touch', pointerId: 2, isPrimary: false })
  assert.equal(card.style.scale, '')
  pointer('pointerdown'); pointer('pointerup')
  card.remove()
  await new Promise(resolve => window.setTimeout(resolve, 5))
  assert.equal(card.style.scale, '')
  assert.equal(frames.size, 0)
  assert.equal(root.children.length, 0)
})


test('blank-card selectstart preserves mouse feedback; an actual text selection restores styles', t => {
  const { card, pointer, frames } = setup(t)
  const selection = window.document.getSelection()
  selection.removeAllRanges()
  t.after(() => selection.removeAllRanges())
  card.style.translate = '1px 2px'
  pointer('pointerdown')
  card.dispatchEvent(new window.Event('selectstart', { bubbles: true }))
  window.document.dispatchEvent(new window.Event('selectionchange'))
  assert.equal(selection.isCollapsed, true)
  assert.equal(card.style.scale, '0.99400', 'collapsed selection must leave a blank-card gesture active')
  pointer('pointermove', card, { clientX: 50, clientY: 20 })
  assert.notEqual(card.style.translate, '1px 2px')
  const range = window.document.createRange()
  range.selectNodeContents(card.querySelector('h2'))
  selection.addRange(range)
  assert.equal(selection.isCollapsed, false)
  window.document.dispatchEvent(new window.Event('selectionchange'))
  assert.equal(card.style.scale, '')
  assert.equal(card.style.translate, '1px 2px')
  assert.equal(frames.size, 0)
  pointer('pointermove', card, { clientX: 100 })
  assert.equal(card.style.translate, '1px 2px', 'selection cancellation cannot revive the gesture')
})

test('cards inside horizontal rails and button-cards receive elastic feedback while nested controls stay excluded', t => {
  const { root, pointer } = setup(
    t,
    '<div class="h-rail-track"><article class="ov-game"><h3>鸣潮</h3><button class="inner">详情</button></article><button class="event-card"><span>限时活动</span></button></div>',
    { selector: '.ov-game, .event-card' },
  )
  const gameCard = root.querySelector('.ov-game')
  const innerBtn = root.querySelector('.inner')
  const eventCard = root.querySelector('.event-card')

  pointer('pointerdown', innerBtn)
  assert.equal(gameCard.style.scale, '', 'nested button inside rail card must not trigger card elasticity')
  pointer('pointerup', innerBtn)

  pointer('pointerdown', gameCard.querySelector('h3'))
  assert.equal(gameCard.style.scale, '0.99400', 'card inside .h-rail-track must receive elastic feedback')
  pointer('pointerup', gameCard)

  pointer('pointerdown', eventCard.querySelector('span'))
  assert.equal(eventCard.style.scale, '0.99400', 'button-card itself must receive elastic feedback')
  pointer('pointerup', eventCard)
})

