<script setup>
import { displayBeijing } from '../time.js'
import { computed } from 'vue'

const props = defineProps({
  snap: { type: Object, default: null },
  imageMode: Boolean,
})

function toLocal(value) {
  if (!value) return null
  return displayBeijing(value)
}

const payload = computed(() => props.snap?.payload ?? null)

// 简表行：null 显示「未知」；base_catch 自带 "%"，原样展示
const rows = computed(() => {
  const p = payload.value
  return [
    { label: '数据坞等级', value: p?.level ?? null },
    { label: '基础捕获率', value: p?.base_catch ?? null },
    { label: '捕获品质', value: p?.catch_quality ?? null },
    { label: '声骸经验', value: p?.cur_exp ?? null },
    { label: '收集数', value: p?.max_count ?? null },
  ]
})
const shown = v => (v == null || v === '' || (typeof v === 'number' && !Number.isFinite(v)) ? '未知' : typeof v === 'number' ? v.toLocaleString('zh-CN') : v)

const fetchedAt = computed(() => toLocal(props.snap?.fetched_at))
</script>

<template>
  <div class="cap-card calabash-card">
    <div class="cap-title">
      数据坞
      <span v-if="snap?.stale && !imageMode" class="badge badge-stale">
        数据可能过期
      </span>
    </div>

    <p v-if="payload == null" class="empty">暂无数据</p>
    <dl v-else class="calabash-grid">
      <div v-for="(row, i) in rows" :key="row.label" :class="{ 'is-main': i === 0 }">
        <dt>{{ row.label }}</dt>
        <dd>{{ shown(row.value) }}</dd>
      </div>
    </dl>

    <p v-if="fetchedAt" class="fetched-at">更新于 {{ fetchedAt }}</p>
  </div>
</template>

<style scoped>
.cap-title {
  font-size: 16px;
  line-height: 24px;
}

.calabash-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.calabash-grid > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: center;
  min-width: 0;
  padding: 12px 14px;
  border-radius: var(--radius-tile);
  background: var(--surface-soft);
  box-shadow: inset 0 0 0 1px var(--overlay-2);
}

/* The calabash level leads: one wide tile on the game tone, its label in the ink. */
.calabash-grid > .is-main {
  grid-column: 1 / -1;
  background: var(--game-tone, var(--surface-soft));
  box-shadow: none;
}

.calabash-grid dt {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
}

.calabash-grid > .is-main dt {
  color: var(--game-accent, var(--text-muted));
}

.calabash-grid dd {
  margin: 2px 0 0;
  overflow: hidden;
  color: var(--text);
  font-size: 20px;
  line-height: 26px;
  font-weight: 550;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.calabash-grid > .is-main dd {
  font-size: 34px;
  line-height: 40px;
  letter-spacing: -0.04em;
}

.fetched-at {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
