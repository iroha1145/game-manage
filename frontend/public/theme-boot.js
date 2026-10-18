// Runs before paint. Keep resolution aligned with src/theme.js.
(() => {
  let mode = 'auto'
  try { mode = localStorage.getItem('gm-theme') } catch { /* storage unavailable */ }
  if (mode !== 'light' && mode !== 'dark') mode = 'auto'
  let actual = mode
  if (mode === 'auto') {
    // Preserve the existing dark fallback when browser preference is unavailable.
    let prefersLight = false
    try { prefersLight = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: light)').matches }
    catch { /* color-scheme support unavailable */ }
    actual = prefersLight ? 'light' : 'dark'
  }
  document.documentElement.dataset.theme = actual
  document.documentElement.dataset.themeMode = mode
})()
