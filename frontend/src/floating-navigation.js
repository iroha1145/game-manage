import { onBeforeUnmount, onMounted, watch, nextTick } from 'vue'

const corners = ['top-left', 'top-right', 'bottom-right', 'bottom-left']
const storageKey = 'game-manage-navigation-corner'
const scrollLocks = new WeakMap()
const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
export function navigationBounds(width, height, navWidth, navHeight) {
  return { left: 16, top: 16, right: Math.max(16, width - navWidth - 16), bottom: Math.max(16, height - navHeight - 16) }
}
export function projectNavigationCorner(x, y, vx, vy, bounds) {
  const px = clamp(x + vx * 0.07, bounds.left, bounds.right)
  const py = clamp(y + vy * 0.07, bounds.top, bounds.bottom)
  return `${py > (bounds.top + bounds.bottom) / 2 ? 'bottom' : 'top'}-${px > (bounds.left + bounds.right) / 2 ? 'right' : 'left'}`
}
function lockScroll(document) {
  let lock = scrollLocks.get(document)
  if (!lock) {
    lock = { count: 0, overflow: document.body.style.overflow }
    scrollLocks.set(document, lock)
    document.body.style.overflow = 'hidden'
  }
  lock.count++
  return () => {
    if (--lock.count === 0) {
      document.body.style.overflow = lock.overflow
      scrollLocks.delete(document)
    }
  }
}

// The controller is independent of component lifetime so pointer and cleanup behavior
// can be exercised with real DOM events in tests.
export function createFloatingNavigation(refs) {
  const { root, surface, sidebar, menuToggle, menuOpen, mobileNavigation } = refs
  const win = root.value.ownerDocument.defaultView
  const doc = root.value.ownerDocument
  const media = win.matchMedia('(prefers-reduced-motion: reduce)')
  let destroyed = false, frame = 0, lastTime = 0, gesture = null, suppressClickUntil = 0
  let unlock = null, generation = 0, corner = 'top-left', height = 300
  let x = 16, y = 16, vx = 0, vy = 0, progress = menuOpen.value ? 1 : 0, pv = 0
  let tx = x, ty = y, tp = progress
  try { const saved = win.localStorage.getItem(storageKey); if (corners.includes(saved)) corner = saved } catch { /* Private browsing can disable storage. */ }
  const bounds = () => navigationBounds(win.innerWidth, win.innerHeight, surface.value?.offsetWidth || 0, surface.value?.offsetHeight || 0)
  function targetCorner() {
    const b = bounds()
    tx = corner.endsWith('right') ? b.right : b.left
    ty = corner.startsWith('bottom') ? b.bottom : b.top
  }
  function paint() {
    if (!root.value || !surface.value) return
    root.value.dataset.navDragging = String(Boolean(gesture?.moved))
    if (mobileNavigation.value) {
      surface.value.style.removeProperty('transform')
      root.value.style.setProperty('--nav-reserve-left', '0px')
      root.value.style.setProperty('--nav-reserve-right', '0px')
      for (const el of [root.value, surface.value]) {
        el.style.setProperty('--drawer-progress', String(clamp(progress, 0, 1)))
        el.style.setProperty('--nav-open-height', `${height}px`)
      }
    } else {
      const b = bounds()
      x = clamp(x, b.left, b.right); y = clamp(y, b.top, b.bottom)
      surface.value.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0)`
      const left = x + surface.value.offsetWidth / 2 < win.innerWidth / 2
      root.value.dataset.navSide = left ? 'left' : 'right'
      root.value.style.setProperty('--nav-reserve-left', `${left ? x + surface.value.offsetWidth : 0}px`)
      root.value.style.setProperty('--nav-reserve-right', `${left ? 0 : win.innerWidth - x}px`)
    }
  }
  function stop() { if (frame) win.cancelAnimationFrame(frame); frame = 0; lastTime = 0 }
  function settle() {
    stop(); x = tx; y = ty; vx = vy = pv = 0; progress = tp; paint()
  }
  function animate(time) {
    frame = 0
    const dt = Math.min(0.032, lastTime ? (time - lastTime) / 1000 : 1 / 60)
    lastTime = time
    if (mobileNavigation.value) {
      pv += ((tp - progress) * 280 - pv * 30) * dt
      progress += pv * dt
    } else {
      vx += ((tx - x) * 260 - vx * 28) * dt
      vy += ((ty - y) * 260 - vy * 28) * dt
      x += vx * dt; y += vy * dt
    }
    paint()
    const done = mobileNavigation.value
      ? Math.abs(tp - progress) < 0.001 && Math.abs(pv) < 0.01
      : Math.hypot(tx - x, ty - y) < 0.1 && Math.hypot(vx, vy) < 1
    if (done) settle()
    else frame = win.requestAnimationFrame(animate)
  }
  function start() {
    if (destroyed || gesture) return
    if (media.matches) settle()
    else if (!frame) frame = win.requestAnimationFrame(animate)
  }
  function controls() {
    return [...(surface.value?.querySelectorAll('button, a[href], input, select, textarea, [tabindex]') || [])]
      .filter(el => !el.disabled && el.tabIndex >= 0 && !el.closest('[inert], [hidden]') && win.getComputedStyle(el).visibility !== 'hidden' && win.getComputedStyle(el).display !== 'none')
  }
  function syncOpen() {
    const ticket = ++generation
    if (mobileNavigation.value && menuOpen.value) {
      if (!unlock) unlock = lockScroll(doc)
      nextTick(() => {
        if (!destroyed && ticket === generation && menuOpen.value && !gesture) {
          const first = controls().find(el => sidebar.value?.contains(el)) || controls()[0]
          first?.focus({ preventScroll: true })
        }
      })
    } else if (unlock) { unlock(); unlock = null }
    tp = mobileNavigation.value && menuOpen.value ? 1 : 0
    if (!gesture) start()
  }
  function openMenu() { menuOpen.value = true; syncOpen() }
  function closeMenu(restoreFocus = true) {
    const ownedFocus = surface.value?.contains(doc.activeElement)
    menuOpen.value = false; syncOpen()
    if (restoreFocus && ownedFocus) nextTick(() => { if (!destroyed && !menuOpen.value && (surface.value?.contains(doc.activeElement) || doc.activeElement === doc.body)) menuToggle.value?.focus({ preventScroll: true }) })
  }
  function toggleMenu() { if (menuOpen.value) closeMenu(); else openMenu() }
  function chooseCorner(value) {
    corner = value; targetCorner(); start()
    try { win.localStorage.setItem(storageKey, corner) } catch { /* Optional preference. */ }
  }
  function releaseCapture(g) {
    try { if (g.target.hasPointerCapture?.(g.id)) g.target.releasePointerCapture(g.id) } catch { /* Detached handles may no longer own capture. */ }
  }
  function end(event, cancelled = false) {
    const g = gesture
    if (!g || (event?.pointerId !== undefined && event.pointerId !== g.id)) return
    gesture = null
    releaseCapture(g)
    if (win.performance.now() - g.time > 100) vx = vy = pv = 0
    if (g.moved) suppressClickUntil = win.performance.now() + 700
    if (mobileNavigation.value) {
      const open = cancelled ? g.wasOpen : g.moved ? progress + pv * 0.07 > 0.5 : g.wasOpen
      menuOpen.value = open; syncOpen()
    } else if (cancelled) chooseCorner(g.corner)
    else if (g.moved) chooseCorner(projectNavigationCorner(x, y, vx, vy, bounds()))
    else start()
    paint()
  }
  function move(event) {
    const g = gesture
    if (!g || event.pointerId !== g.id) return
    const dx = event.clientX - g.startX, dy = event.clientY - g.startY
    if (!g.moved && Math.hypot(dx, dy) < 6) return
    g.moved = true
    event.preventDefault()
    const now = win.performance.now(), dt = Math.max(0.008, (now - g.time) / 1000)
    if (mobileNavigation.value) {
      const travel = Math.max(1, height - 84)
      progress = clamp(g.progress - dy / travel, 0, 1)
      pv = clamp(-(event.clientY - g.lastY) / dt / travel, -8, 8)
      if (progress > 0.03 && !menuOpen.value) { menuOpen.value = true; syncOpen() }
    } else {
      const b = bounds()
      x = clamp(g.x + dx, b.left, b.right); y = clamp(g.y + dy, b.top, b.bottom)
      vx = clamp((event.clientX - g.lastX) / dt, -4000, 4000)
      vy = clamp((event.clientY - g.lastY) / dt, -4000, 4000)
    }
    g.lastX = event.clientX; g.lastY = event.clientY; g.time = now
    paint()
  }
  function down(event) {
    if (gesture || event.button !== 0 || event.isPrimary === false) return
    // A fresh physical press is intentional; only the prior drag's compatibility
    // click is suppressed, never a subsequent quick tap.
    suppressClickUntil = 0
    stop()
    gesture = { id: event.pointerId, target: event.currentTarget, startX: event.clientX, startY: event.clientY,
      lastX: event.clientX, lastY: event.clientY, time: win.performance.now(), x, y, progress, corner, wasOpen: menuOpen.value, moved: false }
    try { event.currentTarget.setPointerCapture?.(event.pointerId) } catch { /* Window listeners remain a fallback. */ }
  }
  function onToggleClick(event) {
    if (win.performance.now() < suppressClickUntil && event.detail !== 0) { event.preventDefault(); return }
    toggleMenu()
  }
  function onGripKeydown(event) {
    if (mobileNavigation.value) {
      if (event.key === 'ArrowUp') { event.preventDefault(); openMenu() }
      else if (event.key === 'ArrowDown') { event.preventDefault(); closeMenu() }
      else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggleMenu() }
      return
    }
    let value = corner
    if (event.key === 'ArrowLeft') value = corner.replace('right', 'left')
    else if (event.key === 'ArrowRight') value = corner.replace('left', 'right')
    else if (event.key === 'ArrowUp') value = corner.replace('bottom', 'top')
    else if (event.key === 'ArrowDown') value = corner.replace('top', 'bottom')
    else if (event.key === 'Enter' || event.key === ' ') value = corners[(corners.indexOf(corner) + 1) % 4]
    else return
    event.preventDefault(); chooseCorner(value)
  }
  function handleKey(event) {
    if (!mobileNavigation.value || !menuOpen.value) return
    if (event.key === 'Escape') { event.preventDefault(); closeMenu(); return }
    if (event.key !== 'Tab') return
    const items = controls(), first = items[0], last = items.at(-1)
    if (!first) return
    if (!items.includes(doc.activeElement) || (event.shiftKey && doc.activeElement === first) || (!event.shiftKey && doc.activeElement === last)) {
      event.preventDefault(); (event.shiftKey ? last : first).focus({ preventScroll: true })
    }
  }
  function refresh() {
    if (gesture) end(null, true)
    height = Math.max(84, Math.min(win.innerHeight - 24, (sidebar.value?.offsetHeight || 216) + 84))
    targetCorner(); syncOpen(); paint()
  }
  const up = event => end(event)
  const cancel = event => end(event, true)
  const blur = () => end(null, true)
  const reduce = () => { if (media.matches && !gesture) settle() }
  win.addEventListener('pointermove', move, { passive: false })
  win.addEventListener('pointerup', up)
  win.addEventListener('pointercancel', cancel)
  win.addEventListener('lostpointercapture', cancel)
  win.addEventListener('blur', blur)
  win.addEventListener('resize', refresh)
  media.addEventListener?.('change', reduce)
  const observer = win.ResizeObserver ? new win.ResizeObserver(() => {
    const newHeight = Math.max(84, Math.min(win.innerHeight - 24, (sidebar.value?.offsetHeight || 216) + 84))
    if (newHeight !== height) { height = newHeight; paint() }
    if (!mobileNavigation.value && !gesture) { targetCorner(); start() }
  }) : null
  if (sidebar.value) observer?.observe(sidebar.value)
  if (surface.value) observer?.observe(surface.value)
  const stopOpen = watch(menuOpen, value => {
    // A route change can close the drawer before an active pointer is released.
    if (!value && gesture) {
      const g = gesture; gesture = null
      if (g.moved) suppressClickUntil = win.performance.now() + 700
      releaseCapture(g)
    }
    syncOpen()
  }, { flush: 'sync' })
  const stopMobile = watch(mobileNavigation, refresh, { flush: 'post' })
  targetCorner(); x = tx; y = ty; refresh()
  return {
    openMenu, closeMenu, toggleMenu, onGripPointerdown: down, onGripKeydown,
    onTogglePointerdown: event => { if (mobileNavigation.value) down(event) }, onToggleClick,
    onToggleKeydown: event => { if (event.key === 'ArrowUp' && mobileNavigation.value) { event.preventDefault(); openMenu() } }, handleKey,
    destroy() {
      destroyed = true; generation++; stop(); stopOpen(); stopMobile(); observer?.disconnect()
      if (gesture) { const g = gesture; gesture = null; releaseCapture(g) }
      unlock?.(); unlock = null
      for (const [type, listener] of [['pointermove', move], ['pointerup', up], ['pointercancel', cancel], ['lostpointercapture', cancel], ['blur', blur], ['resize', refresh]]) win.removeEventListener(type, listener)
      media.removeEventListener?.('change', reduce)
      surface.value?.style.removeProperty('transform')
      for (const el of [root.value, surface.value]) for (const key of ['--nav-reserve-left', '--nav-reserve-right', '--drawer-progress', '--nav-open-height']) el?.style.removeProperty(key)
      if (root.value) { delete root.value.dataset.navDragging; delete root.value.dataset.navSide }
    },
  }
}

export function useFloatingNavigation(refs) {
  let controller, stopRefs
  onMounted(() => {
    stopRefs = watch([refs.root, refs.surface, refs.sidebar], () => {
      controller?.destroy(); controller = undefined
      if (refs.root.value?.ownerDocument?.defaultView && refs.surface.value?.ownerDocument?.defaultView) {
        controller = createFloatingNavigation(refs)
      }
    }, { immediate: true, flush: 'post' })
  })
  onBeforeUnmount(() => { stopRefs?.(); controller?.destroy() })
  // Keep navigation state meaningful in custom renderers without a DOM.
  const fallback = {
    openMenu: () => {
      refs.menuOpen.value = true
      nextTick(() => {
        if (refs.menuOpen.value && refs.mobileNavigation.value) refs.sidebar.value?.querySelector?.('button, a[href], [tabindex]')?.focus?.({ preventScroll: true })
      })
    },
    closeMenu: () => {
      refs.menuOpen.value = false
      if (refs.mobileNavigation.value) refs.menuToggle.value?.focus?.({ preventScroll: true })
    },
    toggleMenu: () => refs.menuOpen.value ? fallback.closeMenu() : fallback.openMenu(),
    onToggleClick: () => fallback.toggleMenu(),
    handleKey: event => {
      if (event.key === 'Escape' && refs.mobileNavigation.value && refs.menuOpen.value) {
        event.preventDefault?.(); fallback.closeMenu()
      }
    },
  }
  return Object.fromEntries(['openMenu', 'closeMenu', 'toggleMenu', 'onGripPointerdown', 'onGripKeydown', 'onTogglePointerdown', 'onToggleClick', 'onToggleKeydown', 'handleKey']
    .map(name => [name, (...args) => controller ? controller[name](...args) : fallback[name]?.(...args)]))
}
