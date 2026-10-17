<script setup>
import { computed, inject, onBeforeUnmount, ref, unref, watch } from 'vue'
import { gameStyle } from '../dashboard.js'
import { theme } from '../theme.js'
import { officialGameIcons, officialGameIconFallbacks } from '../game-artwork.js'

const props = defineProps({ gameId: { type: String, required: true }, name: { type: String, default: '' } })
const failed = ref(0)
// The QQ renderer serves no /game-icons/* file and aborts the request, which would leave the alt text; its pages show the mark.
const imageMode = inject('wuwaImageMode', false)
const style = computed(() => gameStyle(props.gameId))
const icons = computed(() => [...new Set([
  typeof __LOCAL_GAME_ICONS__ !== 'undefined' ? __LOCAL_GAME_ICONS__[props.gameId] : null,
  officialGameIcons[props.gameId],
  ...(officialGameIconFallbacks[props.gameId] || []),
  theme.value === 'light' && style.value.iconLight || style.value.icon,
].filter(Boolean))])
let recoveryTimer, recovered = false
function imageFailed() {
  const officialFailed = icons.value[failed.value] === officialGameIcons[props.gameId]
  failed.value++
  if (officialFailed && !recovered) {
    recovered = true
    recoveryTimer = setTimeout(() => { failed.value = 0 }, 1500)
  }
}
watch([() => props.gameId, theme], () => {
  clearTimeout(recoveryTimer)
  recovered = false
  failed.value = 0
})
onBeforeUnmount(() => clearTimeout(recoveryTimer))
</script>

<template>
  <span class="game-icon" :style="{ color: style.color }">
    <img v-if="icons[failed] && !unref(imageMode)" :src="icons[failed]" :alt="`${name || gameId}图标`" decoding="async" referrerpolicy="no-referrer" @error="imageFailed" />
    <span v-else aria-hidden="true">{{ style.mark }}</span>
  </span>
</template>

<style scoped>
.game-icon { display: inline-grid; place-items: center; flex-shrink: 0; overflow: hidden; vertical-align: middle; }
.game-icon img { display: block; width: 100%; height: 100%; object-fit: cover; }
</style>
