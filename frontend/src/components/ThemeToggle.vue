<script setup>
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { themeMode, nextThemeMode, setThemeMode } from '../theme.js'

const names = { light: '日间模式', dark: '夜间模式', auto: '自动模式（跟随浏览器）' }
const label = computed(() => `当前为${names[themeMode.value]}，点击切换到${names[nextThemeMode()]}`)
// Commit on every click; a full-page snapshot transition can intercept later clicks.
function toggle() { setThemeMode(nextThemeMode()) }
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
