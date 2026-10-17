import test from 'node:test'
import assert from 'node:assert/strict'
import { createRefreshFeedback, REFRESH_TURN_MS } from './refresh-feedback.js'

function fixture(t) {
  const button = new EventTarget(), reduced = new EventTarget(), calls = [], attrs = new Map()
  button.disabled = false; button.getAttribute = () => null; reduced.matches = false
  const body = { animate(frames, options) {
    const animation = { frames, options, cancelled: false, onfinish: null, cancel() { this.cancelled = true } }
    calls.push(animation); return animation
  } }
  const svg = {
    querySelector: () => body, closest: selector => selector === 'button' ? button : null,
    ownerDocument: { defaultView: { matchMedia: () => reduced } },
    setAttribute: (name, value) => attrs.set(name, value), removeAttribute: name => attrs.delete(name),
  }
  const motion = createRefreshFeedback(svg)
  t.after(() => motion.destroy())
  return { motion, calls, button, attrs, reduced,
    click: () => button.dispatchEvent(new Event('click')),
    finish: () => calls.at(-1).onfinish?.(),
    reduce(value) { reduced.matches = value; reduced.dispatchEvent(new Event('change')) },
  }
}

test('fast refresh keeps one full visible turn after data is ready', t => {
  const f = fixture(t)
  f.click(); f.motion.setBusy(true); f.motion.setBusy(false)
  assert.equal(f.calls.length, 1)
  assert.equal(f.calls[0].options.duration, REFRESH_TURN_MS)
  assert.ok(REFRESH_TURN_MS >= 1000)
  assert.equal(f.calls[0].cancelled, false, 'data completion must not abruptly stop the icon')
  assert.equal(f.button.disabled, false, 'animation must not change the action state')
  f.finish()
  assert.equal(f.attrs.has('data-refresh-motion'), false)
  assert.equal(f.calls.length, 1)
})

test('slow requests keep turning and settle on a full turn without stacking rapid clicks', t => {
  const f = fixture(t)
  f.motion.setBusy(true); f.click(); f.click(); f.finish()
  assert.equal(f.calls.length, 2)
  assert.equal(f.calls[0].cancelled, true)
  f.motion.setBusy(false)
  assert.equal(f.calls[1].cancelled, false)
  f.finish()
  assert.equal(f.calls.length, 2)
  assert.equal(f.attrs.has('data-refresh-motion'), false)
})

test('reduced motion immediately clears a running turn and stays quiet on click', t => {
  const f = fixture(t)
  f.motion.setBusy(true); f.reduce(true)
  assert.equal(f.calls[0].cancelled, true)
  assert.equal(f.attrs.has('data-refresh-motion'), false)
  f.click(); assert.equal(f.calls.length, 1)
  f.reduce(false); assert.equal(f.calls.length, 2, 'an ongoing request can resume visual feedback')
  f.motion.setBusy(false); f.finish()
})

test('disabled controls do not animate and unmount cancels motion and listeners', t => {
  const f = fixture(t)
  f.button.disabled = true; f.click(); assert.equal(f.calls.length, 0)
  f.button.disabled = false; f.click()
  f.motion.destroy()
  assert.equal(f.calls[0].cancelled, true)
  f.click(); f.reduce(false); f.motion.setBusy(true)
  assert.equal(f.calls.length, 1)
  assert.equal(f.attrs.has('data-refresh-motion'), false)
})

test('non-DOM rendering needs no animation APIs', () => {
  const motion = createRefreshFeedback({})
  motion.setBusy(true); motion.destroy()
})
