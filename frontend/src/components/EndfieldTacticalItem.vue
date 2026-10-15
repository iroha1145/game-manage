<script setup>
import { computed } from 'vue'
import { displayValue as display } from '../endfield-reports.js'
import EndfieldArtwork from './EndfieldArtwork.vue'
const props=defineProps({ item:Object })
const text = value => typeof value === 'string' && value.trim() ? value : null
// These three paired color markers were observed in live game effect text.
// Remove only a complete flat pair; retain unknown tags and source parameters.
const effect = value => text(value)?.replace(/<@(ba\.vup|tips\.purple|tips\.orange)>([^<>]*)<\/>/g,'$2') ?? null
const active=computed(()=>effect(props.item?.active_effect)), passive=computed(()=>effect(props.item?.passive_effect))
const hasParameters=computed(()=>[active.value,passive.value].some(value=>value && /\{[^{}]+\}/.test(value)))
</script>
<template>
  <section class="ef-tactical"><header><span aria-hidden="true">04</span><h3>战术道具</h3></header><template v-if="item"><div class="tactical-heading"><EndfieldArtwork :src="item.icon_url" :name="text(item.name) || '战术道具'" /><div><strong>{{ text(item.name) || '名称未提供' }}</strong><p>稀有度 {{ display(item.rarity) }}</p></div></div><details v-if="active || passive" class="tactical-effects"><summary>查看效果说明</summary><dl><div v-if="active"><dt>主动效果</dt><dd>{{ active }}</dd></div><div v-if="passive"><dt>被动效果</dt><dd>{{ passive }}</dd></div></dl><p v-if="hasParameters" class="tactical-note">效果包含来源参数，未代入数值。</p></details><p v-else class="tactical-note">来源未提供效果说明。</p></template><p v-else class="tactical-note">来源未提供战术道具，无法判断当前装备状态。</p></section>
</template>
<style scoped>
.ef-tactical{min-width:0;padding:0;margin-top:24px}header{display:flex;gap:10px;align-items:center;padding-bottom:12px;border-bottom:1px solid var(--border);margin-bottom:16px}header>span{font:10px var(--font-mono);color:var(--game-endfield)}h3{font-size:13px;letter-spacing:.1em;margin:0;font-weight:500}.tactical-heading{display:flex;gap:12px;align-items:center;min-width:0}.tactical-heading>.endfield-artwork{width:44px;height:44px;border:0;background:transparent}.tactical-heading>div{min-width:0}.tactical-heading strong{font-size:13px;font-weight:500;overflow-wrap:anywhere}.tactical-heading p,.tactical-note{font-size:11px;color:var(--text-muted);line-height:1.8;margin:5px 0 0}.tactical-effects{margin-top:12px}.tactical-effects summary{font-size:11px;color:var(--text-muted);cursor:pointer;padding:8px 0;min-height:32px}.tactical-effects[open] summary{color:var(--text)}dl{display:grid;gap:12px;margin:10px 0 0}dl>div{display:grid;grid-template-columns:65px minmax(0,1fr);gap:14px;font-size:12px;line-height:1.8}dt{color:var(--text-muted)}dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:600px){dl>div{grid-template-columns:1fr;gap:4px}}
</style>
