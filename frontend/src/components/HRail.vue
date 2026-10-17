<script setup>
import { onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { prefersReducedMotion } from '../motion.js'

defineProps({ label: { type: String, required: true } })
const track = ref(null)
const overflow = ref(false)
const atStart = ref(true)
const atEnd = ref(false)
let frame = 0, resizer = null

function measure() {
  frame = 0
  const el = track.value
  if (!el?.getBoundingClientRect) return
  overflow.value = el.scrollWidth > el.clientWidth + 1
  atStart.value = el.scrollLeft <= 1
  atEnd.value = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1
}
const schedule = () => { if (!frame && typeof requestAnimationFrame === 'function') frame = requestAnimationFrame(measure) }
function page(direction) {
  const el = track.value
  el?.scrollBy({ left: direction * el.clientWidth * 0.85, behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
}

onMounted(() => {
  const el = track.value
  if (!el?.getBoundingClientRect) return
  el.addEventListener('scroll', schedule, { passive: true })
  if (typeof ResizeObserver === 'function') {
    resizer = new ResizeObserver(schedule)
    resizer.observe(el)
  }
  measure()
})
onUpdated(schedule)
onBeforeUnmount(() => {
  track.value?.removeEventListener?.('scroll', schedule)
  resizer?.disconnect()
  if (frame) cancelAnimationFrame(frame)
})
</script>

<template>
  <!-- Arrows exist only once the row is known to overflow, so a short row stays plain. -->
  <div class="h-rail" :data-overflow="overflow || undefined" :data-at-start="atStart || undefined" :data-at-end="atEnd || undefined">
    <div ref="track" class="h-rail-track" :role="overflow ? 'region' : undefined" :aria-label="overflow ? label : undefined" :tabindex="overflow ? 0 : undefined">
      <slot />
    </div>
    <template v-if="overflow">
      <button type="button" class="h-rail-nav prev" aria-label="向左滚动" :disabled="atStart" @click="page(-1)"><AppIcon name="arrow" :size="16" /></button>
      <button type="button" class="h-rail-nav next" aria-label="向右滚动" :disabled="atEnd" @click="page(1)"><AppIcon name="arrow" :size="16" /></button>
    </template>
  </div>
</template>

<style scoped>
.h-rail { position:relative; min-width:0; --rail-fade:48px; }
.h-rail-track { display:flex; gap:var(--rail-gap, 12px); overflow-x:auto; overscroll-behavior-x:contain; scroll-snap-type:x mandatory; scroll-padding-inline:var(--rail-pad, 0px); padding:var(--rail-pad-block, 6px) var(--rail-pad, 0px); margin:calc(var(--rail-pad-block, 6px) * -1) calc(var(--rail-pad, 0px) * -1); scrollbar-width:none; border-radius:var(--radius-card); }
.h-rail-track::-webkit-scrollbar { display:none; }
.h-rail-track > :deep(*) { flex:0 0 auto; scroll-snap-align:start; }
.h-rail-track:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
/* Edges fade only on the side that has more to show. */
.h-rail[data-overflow]:not([data-at-start]) .h-rail-track { -webkit-mask-image:linear-gradient(to right, transparent, #000 var(--rail-fade)); mask-image:linear-gradient(to right, transparent, #000 var(--rail-fade)); }
.h-rail[data-overflow]:not([data-at-end]) .h-rail-track { -webkit-mask-image:linear-gradient(to left, transparent, #000 var(--rail-fade)); mask-image:linear-gradient(to left, transparent, #000 var(--rail-fade)); }
.h-rail[data-overflow]:not([data-at-start]):not([data-at-end]) .h-rail-track { -webkit-mask-image:linear-gradient(to right, transparent, #000 var(--rail-fade), #000 calc(100% - var(--rail-fade)), transparent); mask-image:linear-gradient(to right, transparent, #000 var(--rail-fade), #000 calc(100% - var(--rail-fade)), transparent); }
.h-rail-nav { position:absolute; top:50%; z-index:2; display:grid; place-items:center; width:36px; height:36px; margin-top:-18px; padding:0; border:1px solid var(--glass-border, var(--border)); border-radius:999px; background:var(--glass-bg, var(--card-bg)); -webkit-backdrop-filter:var(--glass-filter, none); backdrop-filter:var(--glass-filter, none); box-shadow:var(--float-shadow, var(--popover-shadow)); color:var(--text); opacity:0; transition:opacity var(--duration-quick) var(--ease-smooth-out), transform var(--duration-quick) var(--ease-smooth-out); }
.h-rail-nav.prev { left:-6px; }
.h-rail-nav.prev svg { transform:rotate(180deg); }
.h-rail-nav.next { right:-6px; }
.h-rail-nav:disabled { opacity:0 !important; pointer-events:none; }
.h-rail-nav:active { transform:scale(var(--scale-large)); }
@media(hover:hover) and (pointer:fine) { .h-rail:hover .h-rail-nav, .h-rail:focus-within .h-rail-nav { opacity:1; } }
.h-rail-nav:focus-visible { opacity:1; }
@media(pointer:coarse) { .h-rail-nav { display:none; } }
</style>
