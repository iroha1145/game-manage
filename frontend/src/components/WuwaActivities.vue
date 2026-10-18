<script setup>
import { computed,inject,unref } from 'vue'
import { fieldLabels, value } from '../wuwa-display.js'
import { endLabel } from '../wuwa-charts.js'
import { vReveal } from '../motion.js'
import WuwaFields from './WuwaFields.vue'
import WuwaStatus from './WuwaStatus.vue'
import WuwaModuleCard from './WuwaModuleCard.vue'
import RingGauge from './RingGauge.vue'
const imageMode = inject('wuwaImageMode',false)
const props = defineProps({ snap: { default: null } })
const sections = computed(() =>
  Object.entries(props.snap?.payload?.sections || {}).sort(
    (a, b) => (a[1]?.sort ?? 999) - (b[1]?.sort ?? 999),
  ),
)
const countable = (v) => v == null || typeof v === 'number'
// Sections arrive with arbitrary keys. Only an explicit X / max_X pair of plain
// numbers is shown as "current / limit" with a meter; everything else stays a
// labelled field.
const tiles = computed(() => {
  return sections.value.map(([key, raw]) => {
    const section = raw && typeof raw === 'object' ? raw : {}
    const pairs = []
    for (const [k, cur] of Object.entries(section)) {
      if (cur && typeof cur === 'object' && !Array.isArray(cur) && typeof cur.count === 'number' && typeof cur.total === 'number' && cur.total > 0) { pairs.push({key:k,label:fieldLabels[k]||k,cur:cur.count,cap:cur.total,pct:Math.max(0,Math.min(100,Math.round(cur.count/cur.total*100)))}); continue }

      const capKey = `max_${k}` in section ? `max_${k}` : k === 'card_num' ? 'card_total_num' : k === 'exp' ? 'next_exp' : `max_${k}`
      if (k.startsWith('max_') || !(capKey in section)) continue
      const cap = section[capKey]
      if (!countable(cur) || !countable(cap) || (cur == null && cap == null))
        continue
      pairs.push({
        key: k,
        label: fieldLabels[k] || k,
        cur,
        cap,
        pct:
          typeof cur === 'number' && typeof cap === 'number' && cap > 0
            ? Math.max(0, Math.min(100, Math.round((cur / cap) * 100)))
            : null,
      })
    }
    const rank =
      section.rank != null && typeof section.rank !== 'object'
        ? section.rank
        : null
    // A section with a deadline is a limited-time one: it leads the board with a countdown.
    const ends = typeof section.end_time === 'string' ? endLabel(section.end_time) : null
    return { key, section, title: section.title || '未命名玩法', pairs, rank, ends }
  })
})
</script>
<template>
  <section class="wuwa-board">
    <header class="wuwa-board-head">
      <h2>玩法进度</h2>
      <WuwaStatus :snap="snap" />
    </header>
    <div v-if="tiles.length" class="wuwa-bento">
      <WuwaModuleCard
        v-for="tile in tiles"
        :key="tile.key"
        v-reveal
        :class="[tile.pairs.length > 1 ? 'span-8' : 'span-4', { 'is-hero': tile.ends }]"
        :title="tile.title"
        button-label="查看详情"
        :sheet-width="560"
      >
        <template #preview>
          <div v-if="tile.rank != null || tile.ends || tile.section.level != null" class="activity-tags">
            <span v-if="tile.section.level != null" class="chip">等级 {{ tile.section.level }}<span v-if="tile.section.level_name"> · {{ tile.section.level_name }}</span></span>
            <span v-if="tile.rank != null" class="badge wuwa-rank">{{ fieldLabels.rank }} {{ tile.rank }}</span>
            <span v-if="tile.ends" class="chip">{{ tile.ends }}</span>
          </div>
          <div v-if="tile.pairs.length" class="activity-pairs">
            <div v-for="p in tile.pairs" :key="p.key" class="activity-pair">
              <RingGauge v-if="p.pct != null" :value="p.cur" :max="p.cap" :label="p.label" :size="unref(imageMode) ? 104 : 72" :stroke="unref(imageMode) ? 10 : 8" color="var(--wuwa-vivid)">
                <span class="ring-pct">{{ p.pct }}%</span>
              </RingGauge>
              <p class="activity-copy">
                <span class="k">{{ p.label }}</span>
                <span class="v"><b>{{ value(p.cur) }}</b> / {{ value(p.cap) }}</span>
              </p>
            </div>
          </div>
        </template>
        <WuwaFields v-if="!unref(imageMode)" :data="tile.section" :exclude="['title']" />
        <WuwaStatus :snap="snap" />
      </WuwaModuleCard>
    </div>
    <p v-else class="wuwa-panel wuwa-empty">暂无玩法记录，请刷新数据。</p>
  </section>
</template>
