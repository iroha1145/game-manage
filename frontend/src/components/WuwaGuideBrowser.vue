<script setup>
import { computed,ref,watch } from 'vue'
import catalog from '../wuwa-guides-catalog.js'
import { characterLabel,characterId } from '../character-search.js'
import { filterGuides,ownedGuideRoles } from '../guide-search.js'
import WuwaGuide from './WuwaGuide.vue'
const props=defineProps({roles:{type:Array,default:()=>[]}})
const emit=defineEmits(['role'])
const search=ref(''), selected=ref(''),ownedOnly=ref(false)
const available=computed(()=>catalog.guides.filter(guide=>!ownedOnly.value || ownedGuideRoles('wuthering_waves',guide,props.roles).length))
const guides=computed(()=>filterGuides('wuthering_waves',available.value,search.value))
const guide=computed(()=>guides.value.find(guide=>guide.id===selected.value))
const owned=computed(()=>guide.value?ownedGuideRoles('wuthering_waves',guide.value,props.roles):[])
watch(search,()=>{selected.value=''}, {flush:'sync'})
</script>
<template>
  <section class="wuwa-guide-browser" aria-label="鸣潮公开攻略搜索">
    <div class="wuwa-filters"><input type="search" aria-label="搜索攻略角色" placeholder="名称、别名、拼音或首字母" :value="search" @input="search=$event.target.value" /><label><input type="checkbox" v-model="ownedOnly" />只看已拥有</label><span>{{ guides.length }} 篇角色攻略</span></div>
    <p v-if="!guides.length" class="wuwa-muted">没有匹配攻略；该形态缺少攻略时不会套用同名角色资料。</p>
    <nav class="guide-candidates" aria-label="攻略角色候选"><button v-for="item in guides" :key="item.id" type="button" :aria-label="`查看${characterLabel('wuthering_waves',item)}攻略`" :aria-pressed="selected===item.id" @click="selected=item.id">{{ characterLabel('wuthering_waves',item) }} · {{ item.attribute }}</button></nav>
    <template v-if="guide"><button v-for="role in owned" :key="characterId(role)" type="button" :aria-label="`查看本人${characterLabel('wuthering_waves',role)}`" @click="emit('role',role)">查看本人 {{ characterLabel('wuthering_waves',role) }} 面板</button><WuwaGuide :character-id="guide.id" :character-name="guide.name" :attribute="guide.attribute" /></template>
  </section>
</template>
<style scoped>
.wuwa-guide-browser{margin:16px 0}
.wuwa-filters{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin-bottom:12px;font-size:13px;color:var(--text-body)}
.wuwa-filters input[type=search]{flex:1 1 220px;min-width:0;min-height:36px;padding:6px 14px;border:1px solid var(--border);border-radius:999px;background:var(--card-bg);box-shadow:var(--btn-shadow);color:var(--text);font-size:13px}
.wuwa-filters label{display:inline-flex;align-items:center;gap:6px}
.wuwa-filters>span{margin-left:auto;color:var(--text-muted);font-size:12px}
.guide-candidates{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;max-height:220px;overflow:auto}
.guide-candidates button{min-height:30px;padding:3px 12px;border:1px solid var(--border);background:var(--card-bg);color:var(--text-body);border-radius:999px;font-size:13px;line-height:20px;cursor:pointer}
.guide-candidates button[aria-pressed=true]{color:var(--accent-strong);background:var(--accent-soft);border-color:transparent;font-weight:500}
@media(hover:hover) and (pointer:fine){.guide-candidates button:not([aria-pressed=true]):hover{border-color:var(--border-strong);color:var(--text)}}
.wuwa-guide-browser>button{min-height:30px;padding:3px 12px;border:1px solid var(--border);background:var(--card-bg);color:var(--text-body);border-radius:999px;font-size:13px;font-weight:500;line-height:20px;cursor:pointer}
</style>
