<script setup>
import { computed } from 'vue'
import { fetchedLabel } from '../time.js'

const props = defineProps({
  snap: { type: Object, default: null },
  imageMode: Boolean,
})

const payload = computed(() => props.snap?.payload ?? null)
const fetchedAt = computed(() => fetchedLabel(props.snap?.fetched_at))

// The first character of the name, drawn by CSS as the avatar tile.
const initial = computed(() => [...String(payload.value?.nickname || '?')][0].toUpperCase())

const rankedSolo = computed(() => {
  const rs = payload.value?.extra?.ranked_solo ?? null
  // 空赛季/未打排位时后端会给出 tier 为空串的数据，视同无段位
  return rs && rs.tier ? rs : null
})
</script>

<template>
  <div class="cap-card">
    <div class="cap-title">
      账号
      <span v-if="snap?.stale && !imageMode" class="badge badge-stale">数据可能过期</span>
      <span v-if="fetchedAt" class="cap-meta">更新于 {{ fetchedAt }}</span>
    </div>

    <p v-if="payload == null" class="empty">暂无数据</p>
    <div v-else class="identity">
      <p class="identity-name" :data-initial="initial">{{ payload.nickname || '未知' }}</p>
      <ul class="chip-list">
        <li class="chip">Lv{{ payload.level ?? '未知' }}</li>
        <li v-if="rankedSolo" class="chip"><b>{{ rankedSolo.tier }}</b>{{ rankedSolo.division ? ' ' + rankedSolo.division : '' }} · {{ rankedSolo.league_points }}LP</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
/* A letter tile, the name, then the chips; the card reads as an identity strip. */
.identity {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.identity-name {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -.01em;
  line-height: 24px;
  color: var(--text);
}

.identity-name::before {
  content: attr(data-initial);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 30%;
  background: linear-gradient(145deg, color-mix(in srgb, var(--game-vivid, var(--accent)) 28%, var(--card-bg)), color-mix(in srgb, var(--game-vivid-2, var(--game-vivid, var(--accent))) 20%, var(--card-bg)));
  color: var(--text);
  font-size: 18px;
  font-weight: 600;
}
</style>
