import { onBeforeUnmount, onMounted, watch } from 'vue'

/** Mouse-only horizontal panning. Touch and wheel scrolling remain native. */
export function createCalendarPan(root) {
  const view = root?.ownerDocument?.defaultView
  if (!view || !root.addEventListener) return { reset() {}, destroy() {} }
  let gesture = null, suppressClick = false, suppressionTimer = null, disposed = false
  const listeners = []
  const listen = (target, name, handler, options) => {
    target.addEventListener(name, handler, options)
    listeners.push(() => target.removeEventListener(name, handler, options))
  }
  const clearSuppression = () => {
    suppressClick = false
    if (suppressionTimer !== null) view.clearTimeout(suppressionTimer)
    suppressionTimer = null
  }
  const release = () => {
    const previous = gesture
    gesture = null
    root.classList.remove('is-panning')
    if (previous && root.hasPointerCapture?.(previous.id)) root.releasePointerCapture?.(previous.id)
  }
  const reset = () => { release(); clearSuppression() }
  const available = () => !disposed && !root.closest('.image-mode, .render-image, [data-bot-render], [data-render-image]')
  const down = event => {
    reset()
    if (!available() || event.pointerType !== 'mouse' || event.button !== 0 || event.isPrimary === false) return
    const target = event.target?.nodeType === 1 ? event.target : event.target?.parentElement
    if (!target?.closest('.timeline-scroll') || target.closest('input, textarea, select, a, [contenteditable="true"]')) return
    if (root.scrollWidth <= root.clientWidth) return
    gesture = { id:event.pointerId, x:event.clientX, y:event.clientY, left:root.scrollLeft, dragging:false }
  }
  const move = event => {
    if (!gesture || event.pointerId !== gesture.id) return
    if (!available() || event.buttons === 0) { reset(); return }
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y
    if (!gesture.dragging) {
      if (Math.abs(dy) > 6 && Math.abs(dy) >= Math.abs(dx)) { reset(); return }
      if (Math.abs(dx) <= 6 || Math.abs(dx) <= Math.abs(dy)) return
      gesture.dragging = true
      root.classList.add('is-panning')
      try { root.setPointerCapture?.(gesture.id) } catch { /* Pointer may already have been released. */ }
    }
    event.preventDefault()
    root.scrollLeft = Math.min(Math.max(0, root.scrollWidth-root.clientWidth), Math.max(0, gesture.left-dx))
  }
  const finish = event => {
    if (!gesture || event.pointerId !== gesture.id) return
    const dragged = gesture.dragging
    release()
    if (dragged && event.type === 'pointerup') {
      suppressClick = true
      // A pointer's click follows pointerup before the next task; never retain a stale block.
      suppressionTimer = view.setTimeout(clearSuppression, 0)
    }
  }
  const click = event => {
    if (!suppressClick || event.detail === 0) return
    clearSuppression()
    event.preventDefault()
    event.stopImmediatePropagation()
  }
  const nativeDrag = event => { if (gesture) event.preventDefault() }
  listen(root, 'pointerdown', down, { passive:true })
  listen(view, 'pointermove', move, { passive:false })
  listen(view, 'pointerup', finish, { passive:true })
  listen(view, 'pointercancel', finish, { passive:true })
  // Normal pointerup releases capture before the synthetic click. Keep its one-click guard.
  listen(root, 'lostpointercapture', () => { if (gesture) reset() }, { passive:true })
  listen(root, 'click', click, true)
  listen(root, 'dragstart', nativeDrag)
  listen(view, 'blur', reset)
  const doc = root.ownerDocument
  const visibility = () => { if (doc.hidden) reset() }
  listen(doc, 'visibilitychange', visibility)
  return { reset, destroy() { disposed = true; reset(); listeners.forEach(remove => remove()) } }
}

export function useCalendarPan(rootRef, enabled) {
  let controller = null
  const mount = () => {
    controller?.destroy()
    controller = enabled() && rootRef.value ? createCalendarPan(rootRef.value) : null
  }
  onMounted(mount)
  watch([rootRef, enabled], mount, { flush:'post' })
  onBeforeUnmount(() => { controller?.destroy(); controller = null })
  return { reset() { controller?.reset() } }
}
