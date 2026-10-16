<script setup>
import { displayBeijing, resetLabel } from '../time.js'
import { computed } from 'vue'
import SummaryMetrics from './SummaryMetrics.vue'

const props = defineProps({
  snap: { type: Object, default: null },
  imageMode: Boolean,
})

function toLocal(value) {
  if (!value) return null
  return displayBeijing(value)
}

// refresh_at 重置提示：负数=已可重置，同日=今日重置，否则 X天后重置
function refreshText(value) {
  return resetLabel(value)
}

const rows = computed(() => {
  const payload = props.snap?.payload
  const items = Array.isArray(payload) ? payload : []
  return items.map(it => ({ label:it.name || '未命名项目',
    ...(it.total > 0 ? {current:it.cur,total:it.total} : {value:it.cur}),
    icon:'calendar',note:refreshText(it.refresh_at),
  }))
})

const fetchedAt = computed(() => toLocal(props.snap?.fetched_at))
</script>

<template>
  <div class="cap-card">
    <div class="cap-title">
      周期进度
      <span v-if="snap?.stale && !imageMode" class="badge badge-stale">
        数据可能过期
      </span>
    </div>

    <p v-if="rows.length === 0" class="empty">暂无数据</p>
    <SummaryMetrics v-else rows :metrics="rows" />

    <p v-if="fetchedAt" class="fetched-at">更新于 {{ fetchedAt }}</p>
  </div>
</template>
