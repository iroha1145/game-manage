import { onBeforeUnmount, onMounted, watch } from 'vue'

const CARD = '[data-elastic-card]'
const EXCLUDED = 'a, button, input, select, textarea, option, label, summary, dialog, [role="button"], [role="slider"], [contenteditable]:not([contenteditable="false"]), [draggable="true"], [data-elastic-ignore], .render-image, .calendar, .version-calendar, .h-rail-track'
const PROPERTIES = ['translate', 'rotate', 'scale']
const PASSIVE = { passive: true }

/** Decorative feedback only: never moves, reorders, captures or cancels input. */
export function createElasticCards(root, { selector = CARD } = {}) {
  const view = root?.ownerDocument?.defaultView
  if (!view || !root.addEventListener) return { reset() {}, destroy() {} }
  const doc = root.ownerDocument
  const media = view.matchMedia?.('(prefers-reduced-motion: reduce)')
  let gesture = null, frame = 0, disposed = false
  const listeners = []
  const listen = (target, type, handler) => {
    target.addEventListener(type, handler, PASSIVE)
    listeners.push(() => target.removeEventListener(type, handler, PASSIVE))
  }
  const reset = () => {
    if (frame) view.cancelAnimationFrame(frame)
    frame = 0
    if (!gesture) return
    const { card, previous } = gesture
    for (const [name, value, priority] of previous) {
      if (value) card.style.setProperty(name, value, priority)
      else card.style.removeProperty(name)
    }
    gesture = null
  }
  const available = () => !disposed && !media?.matches && !root.closest('.render-image, [data-bot-render], [data-render-image]')
  const paint = () => {
    if (!gesture) return
    if (!available() || !gesture.card.isConnected || !root.contains(gesture.card)) { reset(); return }
    const { card, x, y, scale } = gesture
    card.style.setProperty('translate', `${x.toFixed(3)}px ${y.toFixed(3)}px`)
    card.style.setProperty('rotate', `${(x * 0.05).toFixed(3)}deg`)
    card.style.setProperty('scale', scale.toFixed(5))
  }
  const release = event => {
    if (!gesture || (event?.pointerId != null && event.pointerId !== gesture.id)) return
    if (!available()) { reset(); return }
    gesture.released = true
    if (frame) view.cancelAnimationFrame(frame)
    let previousTime = null
    const spring = time => {
      frame = 0
      if (!gesture) return
      const dt = previousTime == null ? 1 / 60 : Math.min(0.032, Math.max(0.001, (time - previousTime) / 1000))
      previousTime = time
      for (const [position, velocity, target] of [['x', 'vx', 0], ['y', 'vy', 0], ['scale', 'vs', 1]]) {
        gesture[velocity] += ((target - gesture[position]) * 330 - gesture[velocity] * 29) * dt
        gesture[position] += gesture[velocity] * dt
      }
      if (Math.abs(gesture.x) + Math.abs(gesture.y) < 0.025 && Math.abs(1 - gesture.scale) < 0.0001) { reset(); return }
      paint()
      if (gesture) frame = view.requestAnimationFrame(spring)
    }
    frame = view.requestAnimationFrame(spring)
  }
  const down = event => {
    // A second finger always hands control back to native pinch/scroll handling.
    if (gesture && !gesture.released && event.pointerId !== gesture.id) { reset(); return }
    if (!available() || event.isPrimary === false || (event.pointerType === 'mouse' && event.button !== 0)) return
    const target = event.target?.nodeType === 1 ? event.target : event.target?.parentElement
    const card = target?.closest(selector)
    if (!card || !root.contains(card) || target.closest(EXCLUDED)) return
    const outerCard = card.parentElement?.closest(selector)
    if (outerCard && root.contains(outerCard)) return
    // Leave nested scrolling surfaces alone, including future calendar/rail variants.
    for (let el = target; el && el !== card; el = el.parentElement) {
      const style = view.getComputedStyle(el)
      if (/(auto|scroll)/.test(`${style.overflowX} ${style.overflowY}`)) return
    }
    if (doc.getSelection?.()?.isCollapsed === false) return
    reset()
    gesture = {
      card, id: event.pointerId, touch: event.pointerType !== 'mouse', startX: event.clientX, startY: event.clientY,
      x: 0, y: 0, scale: 0.994, vx: 0, vy: 0, vs: 0, released: false,
      previous: PROPERTIES.map(name => [name, card.style.getPropertyValue(name), card.style.getPropertyPriority(name)]),
    }
    paint()
  }
  const move = event => {
    if (!gesture || gesture.released || event.pointerId !== gesture.id) return
    if (doc.getSelection?.()?.isCollapsed === false) { reset(); return }
    const dx = event.clientX - gesture.startX, dy = event.clientY - gesture.startY
    if (gesture.touch && Math.abs(dy) > 5 && Math.abs(dy) >= Math.abs(dx) * 0.8) { reset(); return }
    if (gesture.touch && Math.max(Math.abs(dx), Math.abs(dy)) < 5) return
    gesture.x = 8 * Math.tanh(dx / 100)
    gesture.y = gesture.touch ? 0 : 8 * Math.tanh(dy / 100)
    paint()
  }
  listen(root, 'pointerdown', down)
  listen(view, 'pointermove', move)
  listen(view, 'pointerup', release)
  listen(view, 'pointercancel', release)
  listen(view, 'blur', reset)
  // Capture scroll notifications from nested scroll surfaces as well as the page.
  doc.addEventListener('scroll', reset, { passive: true, capture: true })
  // Chromium emits selectstart even when dragging blank card space. Only an
  // actual range selection hands the gesture back to text selection.
  listen(doc, 'selectionchange', () => {
    if (doc.getSelection?.()?.isCollapsed === false) reset()
  })
  listen(doc, 'dragstart', reset)
  const visibility = () => { if (doc.hidden) reset() }
  listen(doc, 'visibilitychange', visibility)
  media?.addEventListener?.('change', reset)
  const observer = new view.MutationObserver(() => {
    if (gesture && (!gesture.card.isConnected || !root.contains(gesture.card) || !available())) reset()
  })
  observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-bot-render', 'data-render-image'] })
  return { reset, destroy() {
    disposed = true
    reset()
    listeners.forEach(remove => remove())
    doc.removeEventListener('scroll', reset, true)
    media?.removeEventListener?.('change', reset)
    observer.disconnect()
  } }
}

/** Pass resetOn (e.g. () => route.value) when routes share the same root. */
export function useElasticCards(rootRef, { resetOn, selector = CARD } = {}) {
  let controller = null
  const reset = () => controller?.reset()
  const mount = root => { controller?.destroy(); controller = root ? createElasticCards(root, { selector }) : null }
  onMounted(() => mount(rootRef.value))
  watch(rootRef, mount, { flush: 'post' })
  if (resetOn) watch(resetOn, reset, { flush: 'sync' })
  onBeforeUnmount(() => { controller?.destroy(); controller = null })
  return { reset }
}
