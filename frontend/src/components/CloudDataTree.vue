<script setup>
import { dataFieldLabel, cloudStateLabel } from '../cloud-display.js'
defineProps({ value: { default: null }, level: { type: Number, default: 0 } })
const scalar = value => value == null || value === '' ? '未提供' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)
</script>
<template>
  <span v-if="value === null || typeof value !== 'object'">{{ scalar(value) }}</span>
  <p v-else-if="Array.isArray(value) && !value.length">暂无条目</p>
  <div v-else-if="Array.isArray(value)" class="cloud-data-list"><details v-for="(row, index) in value" :key="index"><summary>{{ row?.name || row?.display_name || row?.title || `条目 ${index + 1}` }}</summary><CloudDataTree :value="row" :level="level + 1" /></details></div>
  <dl v-else class="cloud-data-fields"><div v-for="(item, key) in value" :key="key"><dt>{{ dataFieldLabel(key) }}</dt><dd><span v-if="key === 'state'">{{ cloudStateLabel(item) }}</span><CloudDataTree v-else :value="item" :level="level + 1" /></dd></div></dl>
</template>
<style scoped>
.cloud-data-list{display:grid;gap:8px}.cloud-data-fields{margin:0;display:grid;gap:0}.cloud-data-fields>div{display:grid;grid-template-columns:minmax(70px,1fr) minmax(0,3fr);gap:8px;padding:8px 0;border-bottom:1px solid var(--border)}dt{color:var(--text-muted);font-size:13px;overflow-wrap:anywhere}dd{margin:0;min-width:0;font-size:13px;overflow-wrap:anywhere}summary{cursor:pointer;padding:8px 0}details{min-width:0}@media(max-width:540px){.cloud-data-fields>div{grid-template-columns:1fr}dd{padding-left:6px}}
</style>
