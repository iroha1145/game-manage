<script setup>
import { computed, useId } from 'vue'
import { parseBeijingTime } from '../calendar.js'
const props = defineProps({ rows: { type: Array, default: () => [] }, metric: String, label: String, min: { type: Number, default: 0 }, max: { type: Number, default: 100 }, unit: { type: String, default: '' }, color: { type: String, default: 'var(--chart-1)' } })
const gradient = `lol-trend-${useId()}`
const ordered = computed(() => props.rows.filter(row => parseBeijingTime(row.date) != null).toSorted((a, b) => a.date.localeCompare(b.date)))
const points = computed(() => {
  const rows = ordered.value, first = parseBeijingTime(rows[0]?.date), last = parseBeijingTime(rows.at(-1)?.date)
  return rows.map(row => ({ ...row, value: row[props.metric],
    x: rows.length === 1 ? 240 : 36 + (parseBeijingTime(row.date) - first) / (last - first || 1) * 414,
    y: Number.isFinite(row[props.metric]) ? 138 - (row[props.metric] - props.min) / (props.max - props.min) * 112 : null,
  }))
})
const segments = computed(() => {
  const result = []; let segment = []
  for (const point of points.value) {
    if (point.y == null) { if (segment.length) result.push(segment); segment = [] }
    else segment.push(point)
  }
  if (segment.length) result.push(segment)
  return result
})
const known = computed(() => points.value.filter(p => p.y != null))
const latest = computed(() => known.value.at(-1) ?? null)
// A point with no neighbour has no line to carry it, so it keeps its dot.
const lone = computed(() => new Set(segments.value.filter(segment => segment.length === 1).map(segment => segment[0].date)))
// The newest day's value sits beside its dot: above it, or to its left when the dot is at the top of the chart.
const endLabel = computed(() => {
  const p = latest.value
  if (!p) return null
  if (p.y < 30) return { x: p.x - 10, y: p.y + 5, anchor: 'end' }
  return { x: p.x, y: p.y - 11, anchor: p.x > 400 ? 'end' : p.x < 80 ? 'start' : 'middle' }
})
const area = segment => `M${segment[0].x},138${segment.map(p => `L${p.x},${p.y}`).join('')}L${segment.at(-1).x},138Z`
const fmt = value => Number.isFinite(value) ? `${Number(value.toFixed(1))}${props.unit}` : '未知'
</script>
<template>
  <section class="lol-trend cap-card" :style="{ '--series': color }">
    <div class="chart-heading"><h3>{{ label }}</h3></div>
    <p v-if="metric === 'winrate'" class="chart-method">重开与未知胜负不计入胜率分母；对局数保留全部归档记录。</p>
    <svg v-if="known.length" viewBox="0 0 480 172" role="img" :aria-label="`${label}，${known.length} 个有效日期`">
      <defs><linearGradient :id="gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--series)" stop-opacity=".24" /><stop offset="1" stop-color="var(--series)" stop-opacity="0" /></linearGradient></defs>
      <g v-for="tick in [min, (min + max) / 2, max]" :key="tick" class="grid">
        <line x1="36" x2="450" :y1="138 - (tick-min)/(max-min)*112" :y2="138 - (tick-min)/(max-min)*112" />
        <text x="29" :y="142 - (tick-min)/(max-min)*112" text-anchor="end">{{ tick }}</text>
      </g>
      <template v-for="(segment, index) in segments" :key="index">
        <path v-if="segment.length > 1" class="trend-area" :d="area(segment)" :fill="`url(#${gradient})`" />
        <polyline :points="segment.map(p => `${p.x},${p.y}`).join(' ')" fill="none" class="trend-line" />
      </template>
      <circle v-for="p in known" :key="p.date" :cx="p.x" :cy="p.y" r="4" class="trend-point" :class="{ 'is-end': p === latest, 'is-lone': lone.has(p.date) }"><title>{{ p.date }} · {{ fmt(p.value) }} · {{ p.games }} 场</title></circle>
      <text v-if="endLabel" class="trend-end" :x="endLabel.x" :y="endLabel.y" :text-anchor="endLabel.anchor">{{ fmt(latest.value) }}</text>
      <text x="36" y="162">{{ ordered[0]?.date }}</text><text x="450" y="162" text-anchor="end">{{ ordered.at(-1)?.date }}</text>
    </svg>
    <p v-else class="chart-empty">暂无可计算的{{ label }}，缺失指标不会按 0 绘制。</p>
    <details v-if="ordered.length"><summary>查看每日数值</summary><div class="trend-table"><table><thead><tr><th>日期</th><th>对局</th><th>{{ label }}</th></tr></thead><tbody><tr v-for="row in ordered" :key="row.date"><td>{{ row.date }}</td><td>{{ row.games ?? '未知' }}</td><td>{{ fmt(row[metric]) }}</td></tr></tbody></table></div></details>
  </section>
</template>
<style scoped>
.lol-trend{min-width:0;container-type:inline-size}
.chart-heading{display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:space-between;align-items:baseline}
.chart-heading h3{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.01em;margin:0}
.chart-method{margin-top:6px;color:var(--text-muted);font-size:12px;line-height:1.7}
svg{width:100%;display:block;margin:12px 0 4px;overflow:visible}
svg text{fill:var(--text-faint);font-size:12px}
/* Hairlines only: the data is the line and its wash, the grid just says where 0, half and full are. */
.grid line{stroke:var(--border);stroke-width:1;vector-effect:non-scaling-stroke}
.trend-line{stroke:var(--series);stroke-width:2;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
.trend-area{stroke:none}
/* Dots wait for the pointer, except the newest day and any day that stands alone. */
.trend-point{fill:var(--series);stroke:var(--card-bg);stroke-width:2;opacity:0;transition:opacity var(--duration-quick,150ms) var(--ease-smooth-out,ease-out)}
.trend-point.is-end,.trend-point.is-lone,.trend-point:hover{opacity:1}
svg text.trend-end{fill:var(--text);font-weight:600;paint-order:stroke;stroke:var(--card-bg);stroke-width:4px;stroke-linejoin:round}
.chart-empty{min-height:140px;display:grid;align-content:center;color:var(--text-muted);font-size:13px;line-height:1.8}
details{margin-top:8px}summary{cursor:pointer;font-size:12px;color:var(--text-muted)}
.trend-table{max-height:190px;overflow:auto;margin-top:10px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border)}th{font-size:12px;font-weight:500;color:var(--text-muted)}
/* The chart scales with its card (viewBox 480 wide), so axis text is sized in chart units to land between 12 and 15px on screen. */
@container (max-width:479px){svg text{font-size:14px}}
@container (max-width:439px){svg text{font-size:16px}}
@container (max-width:359px){svg text{font-size:18px}}
@container (max-width:319px){svg text{font-size:20px}}
@container (max-width:287px){svg text{font-size:22px}}
</style>
