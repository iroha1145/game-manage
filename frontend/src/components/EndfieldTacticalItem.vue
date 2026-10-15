<script setup>
import { computed } from 'vue'
import { displayValue as display } from '../endfield-reports.js'
import EndfieldArtwork from './EndfieldArtwork.vue'
const props=defineProps({ item:Object })
const text = value => typeof value === 'string' && value.trim() ? value : null
const active=computed(()=>text(props.item?.active_effect)), passive=computed(()=>text(props.item?.passive_effect))
</script>
<template>
  <section class="ef-tactical"><h3>战术道具</h3><template v-if="item"><div class="tactical-heading"><EndfieldArtwork :src="item.icon_url" :name="text(item.name) || '战术道具'" /><div><strong>{{ text(item.name) || '名称未提供' }}</strong><p>稀有度 {{ display(item.rarity) }}</p></div></div><dl><div v-if="active"><dt>主动效果</dt><dd>{{ active }}</dd></div><div v-if="passive"><dt>被动效果</dt><dd>{{ passive }}</dd></div></dl><p v-if="!active && !passive" class="tactical-note">来源未提供效果说明。</p></template><p v-else class="tactical-note">来源未提供战术道具，无法判断当前装备状态。</p></section>
</template>
<style scoped>
.ef-tactical{min-width:0;padding-top:18px;margin-top:18px;border-top:1px solid var(--border)}h3{font-size:15px;margin:0 0 14px;font-weight:500}.tactical-heading{display:flex;gap:12px;align-items:center;min-width:0}.tactical-heading>div{min-width:0}.tactical-heading strong{font-size:14px;font-weight:500;overflow-wrap:anywhere}.tactical-heading p,.tactical-note{font-size:12px;color:var(--text-muted);line-height:1.8;margin:7px 0 0}dl{display:grid;gap:12px;margin:16px 0 0}dl:empty{display:none}dl>div{display:grid;grid-template-columns:65px minmax(0,1fr);gap:14px;font-size:12px;line-height:1.8}dt{color:var(--text-muted)}dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:600px){dl>div{grid-template-columns:1fr;gap:4px}}
</style>
