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
  <!-- Arrows exist only once the row is known to overflow, so a short row stays plain. With a head
       slot they sit at the right of the row's heading (game-manage-ui-v1); without one they float
       over the row's edges. -->
  <div class="h-rail" :data-overflow="overflow || undefined" :data-at-start="atStart || undefined" :data-at-end="atEnd || undefined">
    <div v-if="$slots.head" class="h-rail-head">
      <div class="h-rail-title"><slot name="head" /></div>
      <div v-if="overflow" class="h-rail-controls">
        <button type="button" class="icon-button" aria-label="向左滚动" :disabled="atStart" @click="page(-1)"><AppIcon class="flip" name="arrow" :size="15" /></button>
        <button type="button" class="icon-button" aria-label="向右滚动" :disabled="atEnd" @click="page(1)"><AppIcon name="arrow" :size="15" /></button>
      </div>
    </div>
    <div ref="track" class="h-rail-track" :role="overflow ? 'region' : undefined" :aria-label="overflow ? label : undefined" :tabindex="overflow ? 0 : undefined">
      <slot />
    </div>
    <template v-if="overflow && !$slots.head">
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
.h-rail-nav { position:absolute; top:50%; z-index:2; display:grid; place-items:center; width:40px; height:40px; margin-top:-20px; padding:0; border:1px solid var(--border); border-radius:var(--radius-control); background:var(--card-bg); box-shadow:var(--float-shadow); color:var(--text); opacity:0; transition:opacity var(--duration-quick) var(--ease-smooth-out), background-color var(--duration-quick) var(--ease-smooth-out); }
.h-rail-nav.prev { left:-6px; }
.h-rail-nav.prev svg { transform:rotate(180deg); }
.h-rail-nav.next { right:-6px; }
.h-rail-nav:disabled { opacity:0 !important; pointer-events:none; }
.h-rail-nav:active { transform:translateY(1px); }
@media(hover:hover) and (pointer:fine) { .h-rail:hover .h-rail-nav, .h-rail:focus-within .h-rail-nav { opacity:1; } }
.h-rail-nav:focus-visible { opacity:1; }
@media(pointer:coarse) { .h-rail-nav { display:none; } }
/* Heading row: the section's title on the left, the two arrows on the right. */
.h-rail-head { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:44px; margin-bottom:12px; }
.h-rail-title { display:flex; align-items:center; gap:10px; min-width:0; }
.h-rail-controls { display:flex; gap:7px; flex-shrink:0; }
.h-rail-controls .icon-button:disabled { opacity:.4; }
.flip { transform:rotate(180deg); }
@media(pointer:coarse) { .h-rail-controls { display:none; } }
</style>
