<script setup>
import { computed } from 'vue'
import { fieldLabels, stamp, value, list, count } from '../wuwa-display.js'
import { expProgress } from '../wuwa-charts.js'
import WuwaStatus from './WuwaStatus.vue'
import WuwaFields from './WuwaFields.vue'
import DonutChart from './DonutChart.vue'
import RingGauge from './RingGauge.vue'
const props = defineProps({ snap: { default: null }, imageMode:Boolean })
const profile = computed(() => props.snap?.payload?.extra?.profile || {})
const server = computed(() => props.snap?.payload?.extra?.server_id)
const metrics = Object.fromEntries(['world_level', 'active_days', 'achievement_count', 'achievement_star', 'big_count', 'small_count'].map((key) => [key, fieldLabels[key]]))
const collections = {
  box_list: '奇藏箱（基础统计）',
  treasure_box_list: '奇藏箱（分类统计）',
  phantom_box_list: '潮汐之遗',
}
// 等级名称、下一级经验、经验上限与解锁标记合成等级一格：等级数值 + 经验环。
const levelKeys = ['unlock', 'level_name', 'next_exp', 'exp_limit']
const exp = computed(() => expProgress(profile.value))
const excluded = [
  ...Object.keys(metrics),
  ...Object.keys(collections),
  ...levelKeys,
  'creat_time',
]
const hasRest = computed(() =>
  Object.keys(profile.value).some(
    (k) =>
      !excluded.includes(k) &&
      !/(?:icon|pic|image|_url|^sort$|^provenance$)/.test(k),
  ),
)
// A collection as rows: the name, the count, and the bar against the largest count.
function rowsOf(key) {
  const rows = list(profile.value[key]).map((row, i) => ({
    name: row?.box_name || row?.name || `分类 ${row?.id ?? i + 1}`,
    num: row?.num,
  }))
  const top = Math.max(0, ...rows.map((row) => (typeof row.num === 'number' ? row.num : 0)))
  return rows.map((row) => ({ ...row, pct: typeof row.num === 'number' && top > 0 ? Math.round((row.num / top) * 100) : 0 }))
}
// The base box tiers are parts of one whole, so two or more of them read best as a donut.
const tiers = computed(() => rowsOf('box_list'))
const tierParts = computed(() => tiers.value.map((row, i) => ({ label: row.name, value: typeof row.num === 'number' ? row.num : null, color: `var(--chart-${Math.min(i, 7) + 1})` })))
const tierTotal = computed(() => tiers.value.reduce((sum, row) => sum + (typeof row.num === 'number' ? row.num : 0), 0))
</script>
<template>
  <section class="wuwa-panel">
    <header class="cap-title">
      <h2 class="wuwa-name">{{ snap?.payload?.nickname || '漂泊者档案' }}</h2>
      <span v-if="profile.unlock === false" class="badge badge-stale">未解锁</span>
      <WuwaStatus :snap="snap" />
    </header>
    <div class="wuwa-bento">
      <section class="wuwa-panel span-5 is-hero profile-level">
        <div class="account-hero">
          <p v-if="imageMode" class="wuwa-level-label">{{ profile.level_name || '联觉等级' }}</p>
          <RingGauge :value="exp?.cur" :max="exp?.max" :label="`${profile.level_name || '联觉等级'}经验`" :size="104" :stroke="10" color="var(--wuwa-vivid)">
            <small v-if="!imageMode" class="ring-cap">{{ profile.level_name || '联觉等级' }}</small>
            <b class="ring-value">{{ value(snap?.payload?.level) }}</b>
          </RingGauge>
          <p v-if="exp" class="wuwa-exp" :title="`下一级经验 ${value(exp.cur)} / 经验上限 ${value(exp.max)}`">经验 {{ count(exp.cur) }} / {{ count(exp.max) }}</p>
        </div>
        <dl class="kv-grid wuwa-idgrid">
          <div v-if="!imageMode">
            <dt>UID</dt>
            <dd class="mono">{{ value(snap?.payload?.extra?.role_id) }}</dd>
          </div>
          <div v-if="!imageMode">
            <dt>区服</dt>
            <dd class="mono" :title="server == null ? undefined : String(server)">
              {{ value(server) }}
            </dd>
          </div>
          <div>
            <dt>注册日期</dt>
            <dd>{{ stamp(profile.creat_time) }}</dd>
          </div>
        </dl>
      </section>
      <dl class="kv-grid tiles wuwa-metrics span-7">
        <div v-for="(text, key) in metrics" :key="key">
          <dt>{{ text }}</dt>
          <dd>{{ count(profile[key]) }}</dd>
        </div>
      </dl>
      <section class="wuwa-panel span-12 profile-collections">
        <h3 class="wuwa-subhead">
          收集记录
        </h3>
        <div class="wuwa-columns">
          <div v-for="(text, key) in collections" :key="key">
            <h4 class="wuwa-colhead">{{ text }}</h4>
            <p v-if="!list(profile[key]).length" class="wuwa-muted">未提供</p>
            <DonutChart v-else-if="key === 'box_list' && tierParts.length > 1" :segments="tierParts" label="奇藏箱基础统计" :size="108" :stroke="14">
              <b class="donut-total">{{ count(tierTotal) }}</b><small class="ring-cap">个</small>
            </DonutChart>
            <ul v-else class="bar-list">
              <li v-for="(row, i) in rowsOf(key)" :key="i" class="bar-row">
                <span class="k">{{ row.name }}</span>
                <span class="meter"><i :style="{ '--pct': `${row.pct}%` }"></i></span>
                <span class="v">{{ value(row.num) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
    <section v-if="hasRest" class="wuwa-section">
      <WuwaFields :data="profile" :exclude="excluded" />
    </section>
  </section>
</template>
