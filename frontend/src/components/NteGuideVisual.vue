<script setup>
import { computed } from 'vue'
import { tokenizeNteGuide } from '../nte-icons.js'
import NteIcon from './NteIcon.vue'
const props=defineProps({text:{type:String,default:''},sectionKey:{type:String,required:true},roleName:{type:String,required:true}})
const tokens=computed(()=>tokenizeNteGuide(props.text,props.sectionKey,props.roleName))
</script>
<template><div class="nte-visual-flow" :class="sectionKey"><template v-for="(token,index) in tokens" :key="index"><span v-if="token.entity" class="visual-token" :title="token.name"><NteIcon :src="token.icon" :name="token.name" :size="sectionKey === 'skills' ? 'skill' : 'medium'" /><span>{{ token.text }}</span></span><span v-else class="plain-token">{{ token.text }}</span></template></div></template>
<style scoped>
.nte-visual-flow{display:flex;align-items:center;flex-wrap:wrap;gap:6px 8px;line-height:1.8;white-space:pre-wrap;font-size:13px}
.visual-token{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;padding:8px 8px 7px;min-width:56px;border-radius:var(--radius-well);background:var(--surface-soft);box-shadow:inset 0 0 0 1px var(--overlay-2);color:var(--text)}
.visual-token .nte-icon{--size:44px}
.visual-token>span:last-child{font-size:12px;max-width:105px;text-align:center;line-height:1.5;overflow-wrap:anywhere}
.plain-token{color:var(--text-muted)}
.teams .visual-token{min-width:64px}
@media(max-width:650px){.nte-visual-flow{gap:5px}.visual-token{padding:6px;min-width:44px}.visual-token>span:last-child{max-width:84px}}
</style>
