<script setup>
defineProps({ metrics: { type: Array, default: () => [] }, compact: Boolean, rows: Boolean })
const display = value => value == null || value === '' || (typeof value === 'number' && !Number.isFinite(value)) ? '未知' : value
const ratio = metric => Object.hasOwn(metric, 'current')
const measurable = metric => Number.isFinite(metric.current) && metric.current >= 0 && Number.isFinite(metric.total) && metric.total > 0
</script>

<template>
  <div class="summary-metrics" :class="{ compact, rows }">
    <div v-for="metric in metrics" :key="metric.label" class="summary-metric">
      <div class="metric-copy"><span>{{ metric.label }}</span>
        <strong v-if="ratio(metric)">{{ display(metric.current) }} <small>/ {{ display(metric.total) }}</small></strong>
        <strong v-else>{{ display(metric.value) }}</strong>
        <p v-if="metric.note">{{ metric.note }}</p>
      </div>
      <progress v-if="measurable(metric)" :value="metric.current" :max="metric.total" :aria-label="metric.label" />
      <div v-else-if="ratio(metric)" class="unknown-track" aria-hidden="true" />
    </div>
  </div>
</template>

<style scoped>
/* Tiles sit inside a card: a tone step and no outline. The bar is the only
   progress mark, so the tile carries no icon or ring. */
.summary-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(160px,100%),1fr));gap:8px;margin:16px 0 4px}
.summary-metric{display:grid;align-content:start;gap:10px;padding:14px 16px;background:var(--surface-soft);border-radius:var(--radius-control);min-width:0}
.metric-copy{min-width:0}.metric-copy>span{display:block;color:var(--text-muted);font-size:12px;line-height:18px;margin-bottom:4px}.metric-copy>strong{display:block;font-size:22px;font-weight:600;line-height:28px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.metric-copy small{font-size:13px;font-weight:400;color:var(--text-muted)}.metric-copy p{font-size:12px;color:var(--text-muted);margin-top:4px;line-height:1.6}
progress,.unknown-track{width:100%;height:4px;border:0;border-radius:999px;overflow:hidden;background:var(--track);appearance:none}progress::-webkit-progress-bar{background:var(--track)}progress::-webkit-progress-value{background:var(--accent);border-radius:999px}progress::-moz-progress-bar{background:var(--accent);border-radius:999px}.unknown-track{opacity:.5}
.compact{grid-template-columns:repeat(auto-fit,minmax(min(140px,100%),1fr))}.compact .summary-metric{padding:12px}.compact .metric-copy>strong{font-size:18px;line-height:24px;font-weight:500}
.rows{grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))}.rows .summary-metric{padding:12px 14px;gap:8px}.rows .metric-copy{display:flex;align-items:baseline;justify-content:space-between;gap:6px;flex-wrap:wrap}.rows .metric-copy>span{margin:0;flex:1;min-width:95px}.rows .metric-copy strong{font-size:16px;line-height:24px;font-weight:500}.rows .metric-copy p{width:100%;margin:0}
@media(max-width:500px){.summary-metrics{grid-template-columns:1fr}.compact{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
