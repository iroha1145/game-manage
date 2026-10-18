/** Keep the initial view near today until the reader starts interacting. */
export function createCalendarDefaultPosition(root, enabled = () => true) {
  let follow = true, disposed = false
  const align = () => {
    if (disposed || !follow || !enabled()) return
    const today = root?.querySelector?.('.date-cell.is-today')
    const width = root?.clientWidth
    if (!today || !width || !root.getBoundingClientRect) return
    const day = today.getBoundingClientRect()
    const label = root.querySelector('.header-label')?.getBoundingClientRect().width || 0
    const visibleDates = width - label
    if (day.width <= 0 || visibleDates <= 0) return
    const target = root.scrollLeft + day.left + day.width / 2
      - root.getBoundingClientRect().left - (root.clientLeft || 0) - label - visibleDates / 3
    root.scrollLeft = Math.min(Math.max(0, root.scrollWidth - width), Math.max(0, target))
  }
  const stopFollowing = () => { follow = false }
  const interactions = ['pointerdown', 'wheel', 'keydown']
  for (const event of interactions) root?.addEventListener?.(event, stopFollowing, { passive:true })
  const ResizeObserver = root?.ownerDocument?.defaultView?.ResizeObserver
  const observer = ResizeObserver ? new ResizeObserver(align) : null
  if (root) observer?.observe(root)
  const reset = () => {
    if (disposed || !root || !enabled()) return
    follow = true
    root.scrollLeft = 0
    root.scrollTop = 0
    align()
  }
  reset()
  return { reset, destroy() {
    disposed = true
    observer?.disconnect()
    for (const event of interactions) root?.removeEventListener?.(event, stopFollowing)
  } }
}
