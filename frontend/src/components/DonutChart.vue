<script setup>
import { computed, ref } from 'vue'
import { donutArcs, roundedArc } from '../chart-math.js'

const props = defineProps({
  // [{ label, value, color }]; at most six parts read at a glance.
  segments: { type: Array, default: () => [] },
  label: { type: String, required: true },
  unit: { type: String, default: '' },
  size: { type: Number, default: 132 },
  stroke: { type: Number, default: 16 },
})
const active = ref(-1)
const radius = computed(() => (props.size - props.stroke) / 2)
const total = computed(() => props.segments.reduce((sum, part) => sum + (Number.isFinite(part.value) && part.value > 0 ? part.value : 0), 0))
// A 2px gap in the card colour separates neighbours, measured on the 100-unit circle.
const arcs = computed(() => donutArcs(props.segments.map(part => part.value), (2 / (2 * Math.PI * radius.value)) * 100))
const parts = computed(() => props.segments.map((part, index) => ({
  ...part, index, arc: arcs.value[index] ? roundedArc(arcs.value[index].start, arcs.value[index].length, radius.value, props.stroke) : null,
  share: total.value && Number.isFinite(part.value) && part.value > 0 ? Math.round((part.value / total.value) * 100) : 0,
})))
</script>

<template>
  <figure class="donut-chart" :aria-label="label">
    <div class="donut-ring" :style="{ '--donut-size': `${size}px` }">
      <svg :viewBox="`0 0 ${size} ${size}`" aria-hidden="true">
        <circle class="donut-track" :cx="size / 2" :cy="size / 2" :r="radius" :stroke-width="stroke" />
        <template v-for="part in parts" :key="part.label">
          <circle
            v-if="part.arc?.length"
            class="donut-part t-draw" :class="{ dim: active >= 0 && active !== part.index }"
            :cx="size / 2" :cy="size / 2" :r="radius" :stroke-width="part.arc.stroke" stroke-linecap="round"
            pathLength="100" :stroke-dasharray="`${part.arc.length} 100`" :stroke-dashoffset="-part.arc.start"
            :transform="`rotate(-90 ${size / 2} ${size / 2})`" :style="{ '--series': part.color, '--i': part.index }"
          />
        </template>
      </svg>
      <div class="donut-center"><slot /></div>
    </div>
    <ul v-if="segments.length > 1" class="donut-legend">
      <li v-for="part in parts" :key="part.label" tabindex="0" :style="{ '--series': part.color }" @pointerenter="active = part.index" @pointerleave="active = -1" @focus="active = part.index" @blur="active = -1">
        <span class="swatch" aria-hidden="true"></span><span class="name">{{ part.label }}</span><b>{{ Number.isFinite(part.value) ? `${part.value.toLocaleString('zh-CN')}${unit}` : '未知' }}</b><small>{{ part.share }}%</small>
      </li>
    </ul>
  </figure>
</template>

<style scoped>
.donut-chart { display:flex; align-items:center; gap:20px; margin:0; min-width:0; flex-wrap:wrap; }
.donut-ring { position:relative; display:grid; place-items:center; width:var(--donut-size); height:var(--donut-size); flex-shrink:0; }
.donut-ring svg { position:absolute; inset:0; width:100%; height:100%; }
.donut-track { fill:none; stroke:var(--track); }
.donut-part { fill:none; stroke:var(--series); transition:opacity var(--duration-quick) var(--ease-smooth-out); animation:donut-in var(--duration-very-slow) var(--ease-smooth-out) backwards; animation-delay:calc(min(var(--i, 0), 4) * 35ms); }
.donut-part.dim { opacity:.28; }
@keyframes donut-in { from { stroke-dasharray:0 100; } }
.donut-center { position:relative; display:grid; justify-items:center; text-align:center; line-height:1.15; }
.donut-legend { display:grid; gap:4px; flex:1 1 160px; min-width:0; margin:0; padding:0; list-style:none; }
.donut-legend li { display:grid; grid-template-columns:10px minmax(0, 1fr) auto 36px; align-items:center; gap:8px; padding:4px 6px; border-radius:var(--radius-control); font-size:13px; outline-offset:0; }
.donut-legend li:focus-visible { outline:2px solid var(--accent); }
@media(hover:hover) and (pointer:fine) { .donut-legend li:hover { background:var(--hover-bg); } }
.donut-legend .swatch { width:10px; height:10px; border-radius:3px; background:var(--series); }
.donut-legend .name { min-width:0; overflow:hidden; color:var(--text-body); text-overflow:ellipsis; white-space:nowrap; }
.donut-legend b { color:var(--text); font-weight:500; white-space:nowrap; }
.donut-legend small { color:var(--text-muted); font-size:12px; text-align:right; }
</style>
