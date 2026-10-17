// Finish the current turn after a request settles. The extra visual feedback
// never delays data, disables a button, or claims that the request succeeded.
export const REFRESH_TURN_MS = 1100

export function createRefreshFeedback(svg) {
  const body = svg?.querySelector?.('[data-icon-part="body"]')
  const button = svg?.closest?.('button')
  const view = svg?.ownerDocument?.defaultView
  if (!body?.animate || !button || !view || svg.closest('.render-image')) {
    return { setBusy() {}, destroy() {} }
  }
  const reduced = view.matchMedia('(prefers-reduced-motion: reduce)')
  let busy = false, animation = null, disposed = false
  function stop() {
    const current = animation
    animation = null
    if (current) { current.onfinish = null; current.cancel() }
    svg.removeAttribute('data-refresh-motion')
  }
  function turn() {
    if (disposed || reduced.matches || animation) return
    svg.setAttribute('data-refresh-motion', 'running')
    const current = body.animate([
      { transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' },
    ], { duration: REFRESH_TURN_MS, easing: 'cubic-bezier(.45, 0, .55, 1)' })
    animation = current
    current.onfinish = () => {
      if (animation !== current || disposed) return
      stop()
      if (busy) turn()
    }
  }
  function click(event) {
    if (!event.defaultPrevented && !button.disabled && button.getAttribute('aria-disabled') !== 'true') turn()
  }
  function mediaChanged() {
    if (reduced.matches) stop()
    else if (busy) turn()
  }
  button.addEventListener('click', click)
  reduced.addEventListener('change', mediaChanged)
  return {
    setBusy(value) { busy = Boolean(value); if (busy) turn() },
    destroy() {
      disposed = true
      button.removeEventListener('click', click)
      reduced.removeEventListener('change', mediaChanged)
      stop()
    },
  }
}

export const vRefreshFeedback = {
  mounted(el, binding) {
    el.__refreshFeedback = createRefreshFeedback(el)
    el.__refreshFeedback.setBusy(binding.value)
  },
  updated(el, binding) { el.__refreshFeedback?.setBusy(binding.value) },
  unmounted(el) { el.__refreshFeedback?.destroy(); delete el.__refreshFeedback },
}
