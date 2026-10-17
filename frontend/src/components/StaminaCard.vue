<script setup>
import { displayBeijing } from '../time.js'
import { computed } from 'vue'
import RingGauge from './RingGauge.vue'

const props = defineProps({
  snap: { type: Object, default: null },
  imageMode: Boolean,
  label: { type: String, default: '体力' },
})

const payload = computed(() => props.snap?.payload ?? null)

function toLocal(value) {
  if (!value) return null
  return displayBeijing(value)
}

const expectedFullAt = computed(() => toLocal(payload.value?.expected_full_at))
const fetchedAt = computed(() => toLocal(props.snap?.fetched_at))
const shown = v => (v == null || v === '' || (typeof v === 'number' && !Number.isFinite(v)) ? '未知' : v)
const isFull = computed(() => Number.isFinite(payload.value?.current) && Number.isFinite(payload.value?.maximum) && payload.value.maximum > 0 && payload.value.current >= payload.value.maximum)
</script>

<template>
  <div class="cap-card">
    <div class="cap-title">
      体力
      <span v-if="snap?.stale && !imageMode" class="badge badge-stale">
        数据可能过期
      </span>
    </div>

    <p v-if="payload == null" class="empty">暂无数据</p>
    <div v-else class="stamina-body">
      <!-- The ring is the picture; its meter role carries current and maximum. -->
      <RingGauge :value="payload.current" :max="payload.maximum" :label="label" :size="144" :stroke="14" color="var(--game-vivid, var(--accent))">
        <b class="ring-value">{{ shown(payload.current) }}</b><small class="ring-cap">/ {{ shown(payload.maximum) }}</small>
      </RingGauge>
      <div class="stamina-copy">
        <span class="stamina-label">{{ label }}</span>
        <p v-if="expectedFullAt" class="stamina-eta">
          预计 {{ expectedFullAt }} 恢复满
        </p>
        <p v-else-if="isFull" class="stamina-eta">{{ label }}已满</p>
      </div>
    </div>

    <p v-if="fetchedAt" class="fetched-at">更新于 {{ fetchedAt }}</p>
  </div>
</template>

<style scoped>
.cap-title {
  font-size: 16px;
  line-height: 24px;
}

.stamina-body {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 24px;
}

.ring-value {
  color: var(--text);
  font-size: 40px;
  line-height: 42px;
  font-weight: 600;
  letter-spacing: -0.03em;
  font-variant-numeric: proportional-nums;
}

.ring-cap {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
}

.stamina-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.stamina-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
}

.stamina-eta {
  color: var(--text-body);
  font-size: 13px;
  line-height: 20px;
}

.fetched-at {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
