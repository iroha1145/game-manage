<script setup>
import { computed, nextTick, onBeforeUnmount } from 'vue'
import AppIcon from './AppIcon.vue'
import { theme, themeMode, nextThemeMode, resolveThemeMode, setThemeMode } from '../theme.js'

const names = { light: '日间模式', dark: '夜间模式', auto: '自动模式（跟随浏览器）' }
const label = computed(() => `当前为${names[themeMode.value]}，点击切换到${names[nextThemeMode()]}`)
let pendingMode = null, transition = null, generation = 0
const root = globalThis.document?.documentElement
function toggle(event) {
  const next = nextThemeMode(pendingMode ?? themeMode.value)
  pendingMode = next
  const ticket = ++generation
  transition?.skipTransition?.()
  transition = null
  const apply = () => {
    if (ticket !== generation) return
    setThemeMode(next)
    pendingMode = null
  }
  const settle = () => {
    if (ticket !== generation) return
    if (root) delete root.dataset.themeSwitching
    transition = null
  }
  const doc = globalThis.document, view = doc?.defaultView
  if (!root || !doc.startViewTransition || theme.value === resolveThemeMode(next) ||
      view?.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches || !event?.currentTarget?.getBoundingClientRect) {
    apply(); settle(); return
  }
  const box = event.currentTarget.getBoundingClientRect()
  const x = box.left + box.width / 2, y = box.top + box.height / 2
  root.style.setProperty('--theme-x', `${x}px`)
  root.style.setProperty('--theme-y', `${y}px`)
  root.style.setProperty('--theme-r', `${Math.hypot(Math.max(x, view.innerWidth - x), Math.max(y, view.innerHeight - y))}px`)
  root.dataset.themeSwitching = ''
  try {
    transition = doc.startViewTransition(async () => { apply(); await nextTick() })
    transition.finished.then(settle, settle)
    transition.ready.catch(() => {})
  } catch {
    apply(); settle()
  }
}
onBeforeUnmount(() => {
  ++generation
  transition?.skipTransition?.()
  if (pendingMode) setThemeMode(pendingMode)
  if (root) {
    delete root.dataset.themeSwitching
    for (const key of ['--theme-x', '--theme-y', '--theme-r']) root.style.removeProperty(key)
  }
})
</script>

<template>
  <button class="icon-button theme-toggle" type="button" :data-theme-mode="themeMode" :aria-label="label" :title="label" @click="toggle">
    <span class="icon-swap">
      <AppIcon name="sun" :size="16" :data-active="themeMode === 'light'" />
      <AppIcon name="moon" :size="16" :data-active="themeMode === 'dark'" />
      <AppIcon name="auto" :size="16" :data-active="themeMode === 'auto'" />
    </span>
  </button>
</template>
