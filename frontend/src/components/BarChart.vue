<script setup>
import { computed } from 'vue'
import { niceCeil } from '../chart-math.js'

const props = defineProps({
  // [{ label, value, color?, tick?, note? }]; a missing value keeps its slot and reads 未知. `tick` is the
  // text under the axis when it differs from the label (a month labels every fifth day); `note` joins the
  // value on hover and focus.
  items: { type: Array, default: () => [] },
  label: { type: String, required: true },
  unit: { type: String, default: '' },
  height: { type: Number, default: 128 },
  // The bar the story is about keeps the series colour; the others step back.
  highlight: { type: Number, default: -1 },
  color: { type: String, default: 'var(--game-vivid, var(--chart-1))' },
})
const known = value => typeof value === 'number' && Number.isFinite(value)
const separateAxis = computed(() => props.items.some(item => item.tick != null))
const ticks = computed(() => props.items.flatMap((item, index) => item.tick ? [{
  text: item.tick, index, position: `${(index + .5) / props.items.length * 100}%`,
}] : []))
const top = computed(() => niceCeil(Math.max(0, ...props.items.filter(item => known(item.value)).map(item => item.value))))
const peak = computed(() => props.items.reduce((best, item, index) => known(item.value) && (best < 0 || item.value > props.items[best].value) ? index : best, -1))
const bars = computed(() => props.items.map((item, index) => ({
  ...item,
  index,
  pct: known(item.value) ? (Math.max(0, item.value) / top.value) * 100 : null,
  text: known(item.value) ? `${item.value.toLocaleString('zh-CN')}${props.unit}` : '未知',
  // Direct labels only on the peak and the highlighted bar; the rest show on hover or focus.
  labelled: index === peak.value || index === props.highlight,
  muted: props.highlight >= 0 && index !== props.highlight,
})))
</script>

<template>
  <figure class="bar-chart" :style="{ '--plot-height': `${height}px`, '--bars': Math.max(1, items.length) }">
    <ol class="bar-plot" :aria-label="label">
      <li v-for="bar in bars" :key="`${bar.label}:${bar.index}`" class="bar-col" tabindex="0" :data-muted="bar.muted || undefined">
        <span class="bar-slot" :style="{ '--pct': `${bar.pct ?? 0}%` }">
          <span class="bar-value" :class="{ shown: bar.labelled }">{{ bar.text }}<small v-if="bar.note" class="bar-note"> · {{ bar.note }}</small></span>
          <span v-if="bar.pct > 0" class="bar-fill t-draw" :style="{ '--series': bar.color || color, '--i': bar.index }"></span>
          <span v-else-if="bar.pct == null" class="bar-unknown" aria-hidden="true"></span>
        </span>
        <span :class="separateAxis ? 'sr-only' : 'bar-label'">{{ bar.label }}</span>
      </li>
    </ol>
    <div v-if="separateAxis" class="bar-axis" aria-hidden="true">
      <span v-for="tick in ticks" :key="tick.index" class="bar-tick" :class="{ 'axis-start': tick.index === 0, 'axis-end': tick.index === items.length - 1 }" :style="{ left: tick.position }">{{ tick.text }}</span>
    </div>
  </figure>
</template>

<style scoped>
.bar-chart { margin:0; min-width:0; }
.bar-plot { display:grid; grid-template-columns:repeat(var(--bars), minmax(0, 1fr)); align-items:end; gap:2px; margin:0; padding:24px 0 0; list-style:none; }
.bar-col { display:grid; justify-items:center; gap:8px; min-width:0; border-radius:var(--radius-control); outline-offset:2px; }
.bar-slot { position:relative; display:flex; align-items:flex-end; justify-content:center; width:100%; height:var(--plot-height); border-bottom:1px solid var(--border); }
/* Thin columns: at most 24px, rounded only at the data end, rising from the baseline. */
.bar-fill { width:min(24px, 64%); height:var(--pct); min-height:2px; border-radius:4px 4px 0 0; background:var(--series); transform-origin:bottom; animation:bar-grow 700ms var(--ease-smooth-out) backwards; animation-delay:calc(min(var(--i, 0), 8) * 40ms); transition:background-color var(--duration-quick) var(--ease-smooth-out), filter var(--duration-quick) var(--ease-smooth-out); }
@keyframes bar-grow { from { transform:scaleY(0); } }
.bar-col[data-muted] .bar-fill { background:color-mix(in srgb, var(--series) 32%, var(--track)); }
.bar-unknown { width:min(24px, 64%); height:2px; background:var(--track); }
.bar-value { position:absolute; left:50%; bottom:calc(var(--pct) + 4px); transform:translateX(-50%); padding:1px 6px; border-radius:var(--radius-chip); color:var(--text); font-size:12px; font-weight:500; line-height:18px; white-space:nowrap; opacity:0; pointer-events:none; transition:opacity var(--duration-quick) var(--ease-smooth-out); }
.bar-value.shown { opacity:1; }
.bar-label { min-height:16px; max-width:100%; overflow:hidden; color:var(--text-muted); font-size:12px; line-height:16px; text-overflow:ellipsis; white-space:nowrap; }
/* Sparse dates share their own axis: text can use the space between ticks,
   while every daily bar keeps exactly the same baseline. */
.bar-axis { position:relative; height:16px; margin-top:8px; color:var(--text-muted); font-size:12px; line-height:16px; }
.bar-tick { position:absolute; width:max-content; white-space:nowrap; transform:translateX(-50%); }
.bar-tick.axis-start { left:0 !important; transform:none; }
.bar-tick.axis-end { left:auto !important; right:0; transform:none; }
.bar-col:is(:hover, :focus-visible) .bar-value { opacity:1; z-index:2; background:var(--text); color:var(--bg); }
.bar-note { display:none; font-size:12px; font-weight:400; }
.bar-col:is(:hover, :focus-visible) .bar-note { display:inline; }
.bar-col:is(:hover, :focus-visible) .bar-fill { filter:brightness(1.08) saturate(1.1); }
.bar-col:focus-visible { outline:2px solid var(--accent); }
</style>
