<script setup>
import { computed, ref, watch } from 'vue'
import { safeWuwaIcon } from '../wuwa-icons.js'
const props = defineProps({ src: { type: String, default: '' }, name: { type: String, default: '' }, size: { type: String, default: 'normal' } })
const failed = ref(false)
const url = computed(() => safeWuwaIcon(props.src))
watch(url, () => { failed.value = false }, { flush: 'sync' })
</script>
<template>
  <span class="wuwa-item-icon" :class="`icon-${size}`" :title="name" aria-hidden="true">
    <img v-if="url && !failed" :src="url" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="failed = true" />
    <span v-else class="icon-fallback">{{ name?.slice(0, 1) || '·' }}</span>
  </span>
</template>
<style scoped>
/* Art keeps a quiet tile; a letter standing in for missing art gets the game colour. */
.wuwa-item-icon { width: 48px; height: 48px; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; border-radius: 28%; background: var(--overlay-3); overflow: hidden; vertical-align: middle; }
.wuwa-item-icon img { width: 100%; height: 100%; object-fit: contain; }
.icon-fallback { display: grid; place-items: center; width: 100%; height: 100%; background: linear-gradient(145deg, color-mix(in srgb, var(--game-vivid, var(--accent)) 28%, var(--card-bg)), color-mix(in srgb, var(--game-vivid, var(--accent)) 10%, var(--card-bg))); color: color-mix(in srgb, var(--game-vivid, var(--accent)) 55%, var(--text)); font-size: 18px; font-weight: 600; }
.icon-small { width: 24px; height: 24px; border-radius: var(--radius-chip); }
.icon-small .icon-fallback { font-size: 12px; }
.icon-large { width: 76px; height: 76px; border-radius: 28%; }
.icon-large .icon-fallback { font-size: 30px; }
</style>
