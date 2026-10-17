<script setup>
import { computed } from 'vue'
import { share } from '../chart-math.js'

const props = defineProps({
  value: { type: Number, default: null },
  max: { type: Number, default: null },
  label: { type: String, required: true },
  size: { type: Number, default: 112 },
  stroke: { type: Number, default: 10 },
  color: { type: String, default: 'var(--accent)' },
})
const ratio = computed(() => share(props.value, props.max))
const center = computed(() => props.size / 2)
const radius = computed(() => (props.size - props.stroke) / 2)
</script>

<template>
  <!-- The ring is the picture; the meter role carries the value for assistive tech. -->
  <div
    class="ring-gauge"
    :style="{ '--ring-size': `${size}px`, '--ring-color': color }"
    :role="ratio == null ? undefined : 'meter'"
    :aria-label="label"
    :aria-valuenow="ratio == null ? undefined : value"
    :aria-valuemin="ratio == null ? undefined : 0"
    :aria-valuemax="ratio == null ? undefined : max"
  >
    <svg :viewBox="`0 0 ${size} ${size}`" aria-hidden="true">
      <circle class="ring-track" :cx="center" :cy="center" :r="radius" :stroke-width="stroke" />
      <circle
        v-if="ratio"
        class="ring-value t-draw"
        :cx="center" :cy="center" :r="radius" :stroke-width="stroke"
        pathLength="100" :stroke-dasharray="`${(ratio * 100).toFixed(2)} 100`"
        :transform="`rotate(-90 ${center} ${center})`"
      />
    </svg>
    <div class="ring-center"><slot /></div>
  </div>
</template>

<style scoped>
.ring-gauge { position:relative; display:grid; place-items:center; width:var(--ring-size); height:var(--ring-size); flex-shrink:0; }
.ring-gauge svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
.ring-track { fill:none; stroke:color-mix(in srgb, var(--ring-color) 14%, var(--track)); }
.ring-value { fill:none; stroke:var(--ring-color); stroke-linecap:round; transition:stroke-dasharray var(--duration-slow) var(--ease-smooth-out); animation:ring-draw 900ms var(--ease-smooth-out) backwards; }
@keyframes ring-draw { from { stroke-dasharray:0 100; } }
.ring-center { position:relative; display:grid; justify-items:center; gap:2px; text-align:center; line-height:1.1; }
</style>
