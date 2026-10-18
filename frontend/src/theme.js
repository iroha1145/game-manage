import { ref } from 'vue'

// Keep this resolution policy aligned with public/theme-boot.js, which runs
// before paint. A browser without color-scheme support falls back to dark.
const KEY = 'gm-theme'
const SYSTEM_QUERY = '(prefers-color-scheme: light)'
const root = typeof document === 'undefined' ? null : document.documentElement
const normalizeMode = mode => mode === 'light' || mode === 'dark' ? mode : 'auto'

function systemMedia() {
  try { return typeof matchMedia === 'function' ? matchMedia(SYSTEM_QUERY) : null }
  catch { return null }
}

export function resolveThemeMode(mode) {
  return mode === 'light' || mode === 'dark' ? mode : systemMedia()?.matches ? 'light' : 'dark'
}

function initialMode() {
  try { return normalizeMode(localStorage.getItem(KEY)) }
  catch { return 'auto' }
}

// Storage is read once. The in-memory choice then owns this session, including
// when a write fails and storage still contains an older, different choice.
export const themeMode = ref(initialMode())
export const theme = ref(resolveThemeMode(themeMode.value))

function applyTheme(actual) {
  theme.value = actual
  if (root) {
    root.dataset.theme = actual
    root.dataset.themeMode = themeMode.value
  }
}
applyTheme(theme.value)

export function setThemeMode(next) {
  themeMode.value = normalizeMode(next)
  applyTheme(resolveThemeMode(themeMode.value))
  try { localStorage.setItem(KEY, themeMode.value) } catch { /* storage unavailable */ }
}

// Compatibility for existing callers that select a concrete light/dark theme.
export const setTheme = setThemeMode

export function nextThemeMode(mode = themeMode.value) {
  return mode === 'light' ? 'dark' : mode === 'dark' ? 'auto' : 'light'
}

/** Follow browser preference only in automatic mode; return a listener cleanup. */
export function followSystem() {
  const media = systemMedia()
  if (!media) return () => {}
  const changed = () => {
    if (themeMode.value === 'auto') applyTheme(media.matches ? 'light' : 'dark')
  }
  changed()
  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', changed)
    return () => media.removeEventListener?.('change', changed)
  }
  // Older browser versions expose the same notification through addListener.
  media.addListener?.(changed)
  return () => media.removeListener?.(changed)
}
