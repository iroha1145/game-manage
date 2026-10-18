<script setup>
import { pityText, aggregateKind, gachaReason } from '../wuwa-gacha.js'
import { pityGauge } from '../wuwa-charts.js'
import { gachaItemIcon } from '../wuwa-icons.js'
import WuwaIcon from './WuwaIcon.vue'
import RingGauge from './RingGauge.vue'
defineProps({ archive: { type:Object, default:null }, imageMode:{type:Boolean,default:false} })
</script>
<template>
  <section v-if="archive" class="wuwa-section">
    <h3 class="wuwa-subhead">抽卡进度</h3>
    <div class="wuwa-tiles gacha-pity-list">
      <article v-for="pool in archive.pools || []" :key="pool.pool" class="wuwa-tile gacha-pity">
        <!-- A ring only where the user's own rule gives a cap and the count is exact. -->
        <RingGauge v-if="pityGauge(pool.pity)" :value="pityGauge(pool.pity).value" :max="pityGauge(pool.pity).max" :label="`${pool.name} 当前垫抽`" :size="76" :stroke="8" color="var(--wuwa-vivid)">
          <b class="ring-value">{{ pool.pity.count }}</b>
        </RingGauge>
        <div class="gacha-pity-copy">
          <b>{{ pool.name }}</b> · {{ pityText(pool.pity) }}
          <p class="wuwa-meta">UP 保证未知。</p>
          <p v-if="pool.pity?.hard_pity_remaining != null">按配置距上限 {{ pool.pity.hard_pity_remaining }} 抽</p>
          <details v-if="!imageMode" data-render-collapsed><summary>计算详情</summary><p class="wuwa-meta">{{ pool.pity?.rule_basis === 'user_configured' ? '用户配置规则 · ' + pool.pity.rule_version : '池别重置/共享规则未配置' }}</p><p v-if="pool.pity?.missing_requirements?.length" class="wuwa-meta">缺少判断依据：{{ pool.pity.missing_requirements.map(gachaReason).join('、') }}</p></details>
        </div>
      </article>
    </div>
    <template v-if="archive.aggregates?.total">
      <h3 class="wuwa-subhead">第三方五星汇总 · {{ archive.aggregates.total }} 条</h3>
      <p class="wuwa-meta">五星汇总记录，未计入逐抽统计。</p>
      <div class="wuwa-tiles">
        <article v-for="(item,index) in archive.aggregates.items || []" :key="index" class="wuwa-tile">
          <span class="gacha-summary-item"><WuwaIcon v-if="gachaItemIcon(item)" :src="gachaItemIcon(item)" :name="item.name" size="small" /><b>{{ item.name || '当前垫抽标记' }}</b></span> · 卡池 {{ item.pool }} · {{ aggregateKind(item) }} {{ item.period_count }} 抽
          <details v-if="!imageMode" data-render-collapsed><summary>记录详情</summary><p class="wuwa-meta">{{ item.source }} · 来源时间 {{ item.source_time }}（{{ item.time_basis === 'source_unix_timestamp' ? '来源 Unix 时间值' : '来源显示时间' }}）</p><p v-if="item.diagnostics?.length" class="wuwa-meta">{{ item.diagnostics.map(gachaReason).join('、') }}</p></details>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.gacha-summary-item { display: inline-flex; align-items: center; gap: 6px; vertical-align: middle; }
</style>
