<script setup>
import { fetchedLabel } from '../time.js'
import { computed } from 'vue'
import DonutChart from './DonutChart.vue'
import RingGauge from './RingGauge.vue'

const props = defineProps({
  snap: { type: Object, default: null },
  imageMode: Boolean,
  // The summary on the board: regions and the phantom total, without the area chips.
  compact: Boolean,
})

const payload = computed(() => props.snap?.payload ?? null)
// Levels are parts of one whole: they take the chart series in order.
const series = (n) => `var(--chart-${Math.min(n, 7) + 1})`

// 残象探寻汇总：已收录总数 + 按级计数（{"轻波级": n, ...}，按实测顺序渲染）
const detections = computed(() => payload.value?.detections ?? null)
const levels = computed(() =>
  Object.entries(detections.value?.by_level || {}).map(([name, count], i) => ({
    label: name,
    value: typeof count === 'number' ? count : null,
    color: series(i),
  })),
)

const groups = computed(() => {
  const list = payload.value?.country_groups
  return (Array.isArray(list) ? list : []).map((g) => {
    const progress = g.progress ?? null
    const areas = Array.isArray(g.areas) ? g.areas : []
    return {
      name: g.name || '-',
      progress: typeof progress === 'number' ? progress : null,
      pctText: progress == null ? '-' : `${progress}%`,
      areas: areas.map((a) => ({
        name: a.name || '-',
        pctText: a.progress == null ? '-' : `${a.progress}%`,
      })),
    }
  })
})

const hasData = computed(() =>
  groups.value.length > 0 || (detections.value && detections.value.total != null))

const fetchedAt = computed(() => fetchedLabel(props.snap?.fetched_at))
</script>

<template>
  <div class="cap-card">
    <div class="cap-title">
      探索度
      <span v-if="snap?.stale && !imageMode" class="badge badge-stale">
        数据可能过期
      </span>
      <span v-if="fetchedAt" class="cap-meta">更新于 {{ fetchedAt }}</span>
    </div>

    <p v-if="!hasData" class="empty">暂无数据</p>
    <div v-else class="explore-body">
      <ul v-if="groups.length > 0" class="region-rings">
        <li v-for="(g, i) in groups" :key="i" class="region">
          <RingGauge :value="g.progress" :max="100" :label="`${g.name} 探索度`" :size="compact ? 76 : 88" :stroke="8" color="var(--game-vivid, var(--accent))">
            <span class="ring-pct">{{ g.pctText }}</span>
          </RingGauge>
          <span class="region-name">{{ g.name }}</span>
          <ul v-if="!compact && g.areas.length" class="chip-list region-areas">
            <li v-for="(a, j) in g.areas" :key="j" class="chip">{{ a.name }} <b>{{ a.pctText }}</b></li>
          </ul>
        </li>
      </ul>

      <div v-if="detections?.total != null" class="detection">
        <DonutChart :segments="levels" label="残象按等级收录" :size="124" :stroke="14">
          <span class="detection-label">残象已收录</span>
          <b class="detection-total">{{ detections.total }}</b>
          <span class="detection-unit">只</span>
        </DonutChart>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cap-title {
  font-size: 16px;
  line-height: 24px;
}

.explore-body {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 20px 40px;
}

.region-rings {
  display: grid;
  flex: 1 1 340px;
  grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
  gap: 18px 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.region {
  display: grid;
  justify-items: center;
  align-content: start;
  gap: 8px;
  min-width: 0;
  text-align: center;
}

.ring-pct {
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.region-name {
  max-width: 100%;
  overflow: hidden;
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.region-areas {
  justify-content: center;
}

.detection {
  flex: 0 1 340px;
  min-width: 0;
}

.detection-label {
  color: var(--text-muted);
  font-size: 11px;
  line-height: 16px;
}

.detection-total {
  color: var(--text);
  font-size: 28px;
  line-height: 32px;
  font-weight: 550;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}

.detection-unit {
  color: var(--text-muted);
  font-size: 11px;
  line-height: 14px;
}
</style>
