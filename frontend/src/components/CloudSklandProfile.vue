<script setup>
import { computed } from 'vue'
import AccountCard from './AccountCard.vue'
import StaminaCard from './StaminaCard.vue'
import CloudDataTree from './CloudDataTree.vue'
import EndfieldReports from './EndfieldReports.vue'
const props=defineProps({payload:{type:Object,default:()=>({})},fetchedAt:{type:String,default:''},stale:Boolean})
const profile=computed(()=>({payload:{nickname:props.payload.base?.name,level:props.payload.base?.level},fetched_at:props.fetchedAt}))
const list=value=>Array.isArray(value)?value:[]
const named=value=>typeof value === 'string' ? value : value?.name || value?.title || '未提供'
const pair=value=>`${show(value?.count)} / ${show(value?.total)}`
const show=value=>value==null||value===''?'未提供':String(value)
</script>
<template>
  <div class="cloud-skland-profile"><AccountCard :snap="profile" /><StaminaCard :snap="{payload:payload.stamina ?? null,fetched_at:fetchedAt}" label="理智" />
    <section class="cap-card"><h3 class="cap-title">日常与周期进度</h3><p v-if="!list(payload.progress).length">尚无日常进度</p><p v-for="(row,index) in list(payload.progress)" :key="index">{{ row.name || '周期进度' }}：{{ show(row.cur) }} / {{ show(row.total) }}</p></section>
    <section class="cap-card"><h3 class="cap-title">干员档案</h3><p v-if="!list(payload.operators).length">尚无干员目录</p><div class="profile-grid"><article v-for="(operator,index) in list(payload.operators)" :key="operator.id || index" class="inner-card"><h4>{{ operator.name || `干员 ${index+1}` }} · {{ show(operator.rarity) }}★</h4><p>等级 {{ show(operator.level) }} · 潜能 {{ show(operator.potential) }}</p><p v-if="operator.profession || operator.property">{{ show(operator.profession) }} · {{ show(operator.property) }}</p><p v-if="operator.weapon">武器：{{ named(operator.weapon) }} · 等级 {{ show(operator.weapon.level) }}</p></article></div></section>
    <section class="cap-card"><h3 class="cap-title">区域探索</h3><p v-if="!list(payload.regions).length">尚无区域资料</p><details v-for="(region,index) in list(payload.regions)" :key="region.id || index" open><summary>{{ region.name || `区域 ${index+1}` }} · 等级 {{ show(region.level) }}</summary><p v-if="region.money">调度券：{{ pair(region.money) }}</p><p v-for="settlement in list(region.settlements)" :key="settlement.id || settlement.name">{{ named(settlement) }} · 等级 {{ show(settlement.level) }} · 资金 {{ show(settlement.money) }} / {{ show(settlement.money_max) }}</p><div class="profile-grid"><article v-for="level in list(region.levels)" :key="level.id || level.name" class="inner-card"><h4>{{ named(level) }}</h4><p>醚质 {{ pair(level.puzzles) }} · 宝箱 {{ pair(level.chests) }}</p><p>装备制造模板 {{ pair(level.equipment_chests) }} · 维修灵感点 {{ pair(level.pieces) }} · 协议采录桩 {{ pair(level.blackboxes) }}</p></article></div><p v-for="(entry,i) in list(region.collections)" :key="entry.level_id || i">{{ entry.level_id || '区域收集' }}：醚质 {{ show(entry.puzzle_count) }} · 宝箱 {{ show(entry.chest_count) }} · 维修灵感点 {{ show(entry.piece_count) }} · 协议采录桩 {{ show(entry.blackbox_count) }}</p></details></section>
    <EndfieldReports :payload="payload" :fetched-at="fetchedAt" :stale="stale" view="ship" />
    <EndfieldReports :payload="payload" :fetched-at="fetchedAt" :stale="stale" view="honor" />
    <details class="cap-card"><summary>查看来源字段</summary><CloudDataTree :value="payload" /></details>
  </div>
</template>
<style scoped>
.cloud-skland-profile{display:grid;gap:16px;min-width:0}
p{line-height:1.6}
ul{padding-left:20px;display:grid;gap:8px}
summary{cursor:pointer;padding:8px 0}
.profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.inner-card{padding:14px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.inner-card h4{margin:0 0 8px;font-size:14px;font-weight:600}
.inner-card p{color:var(--text-muted);font-size:13px}
@media(max-width:720px){.profile-grid{grid-template-columns:1fr}}
</style>
