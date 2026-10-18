<script setup>
import { computed } from 'vue'
import { cloudStateLabel, capabilityLabel } from '../cloud-display.js'
import { displayBeijing } from '../time.js'
import { hasFreshPublicFallback } from '../snapshot-state.js'
const props = defineProps({ snapshots: { type:Object, default:()=>({}) }, capabilities: {type:Array,default:()=>[]}, labels: {type:Object,default:()=>({})} })
const sourceRows = snap => { const sources=snap?.source_statuses || snap?.poll_status?.source_statuses || {}; return Array.isArray(sources) ? sources : Object.entries(sources).map(([source,row]) => ({source,...row})) }
const sourceName = value => ({bilibili:'B站',community:'社区',official:'官方',news:'原生资讯',announcement:'原生公告'})[value] || value
const age = value => {
  const time = Date.parse(value), minutes = Math.floor((Date.now()-time)/60000)
  return !Number.isFinite(time) || minutes < 0 ? '' : minutes < 1 ? '刚刚' : minutes < 60 ? `${minutes} 分钟前` : minutes < 1440 ? `${Math.floor(minutes/60)} 小时前` : `${Math.floor(minutes/1440)} 天前`
}
const rows = computed(() => props.capabilities.map(cap => ({cap,snap:props.snapshots[cap]})))
</script>
<template>
  <details class="cloud-snapshot-states"><summary>更多信息</summary>
    <div v-for="{cap,snap} in rows" :key="cap"><p>{{ labels[cap] || capabilityLabel(cap) }}：{{ hasFreshPublicFallback(snap) ? '部分来源不可用，显示可用来源数据' : snap ? cloudStateLabel(snap.state) : '未读取' }}<span v-if="snap?.stale"> · 数据可能过期</span> · {{ snap?.fetched_at ? displayBeijing(snap.fetched_at) : '时间未提供' }}<span v-if="age(snap?.fetched_at)">（{{ age(snap.fetched_at) }}）</span><span v-if="snap?.complete === false"> · 数据尚不完整</span></p>
      <p v-if="snap?.error || snap?.poll_status?.error" role="status">{{ snap.error || snap.poll_status.error }}</p><p v-if="snap?.primary_source">主要来源：{{ sourceName(snap.primary_source) }}<span v-if="snap.version"> · 版本 {{ snap.version }}</span></p>
      <p v-for="(source,index) in sourceRows(snap)" :key="source.source || index">{{ source.source_name || sourceName(source.source) || '来源' }}：{{ cloudStateLabel(source.state) }}<span v-if="source.stale"> · 数据可能过期</span><span v-if="source.fetched_at || source.last_success_at"> · {{ displayBeijing(source.fetched_at || source.last_success_at) }}</span><span v-if="source.error"> · {{ source.error }}</span></p>
    </div>
  </details>
</template>
<style scoped>.cloud-snapshot-states{font-size:12px;color:var(--text-muted);overflow-wrap:anywhere}.cloud-snapshot-states>div{margin-top:12px}.cloud-snapshot-states p{line-height:1.7}summary{cursor:pointer}</style>
