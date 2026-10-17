<script setup>
import { computed, ref, watch } from 'vue'
import { safeNteIcon } from '../nte-icons.js'
import { tintOf } from '../nte-charts.js'
const props=defineProps({src:{type:String,default:''},name:{type:String,default:''},size:{type:String,default:'medium'}})
const failed=ref(false),url=computed(()=>safeNteIcon(props.src))
// Big tiles carry one character, small ones two, so the letter never crowds the tile.
const letter=computed(()=>(['large','xl'].includes(props.size) ? props.name.slice(0,1) : props.name.slice(0,2)) || '?')
watch(url,()=>{failed.value=false})
</script>
<template><span class="nte-icon" :data-size="size" :data-tint="tintOf(name)" :title="name"><img v-if="url && !failed" :src="url" :alt="name" loading="lazy" referrerpolicy="no-referrer" @error="failed = true" /><span v-else class="icon-fallback" aria-hidden="true">{{ letter }}</span></span></template>
<style scoped>
/* A rounded square. Without art it is a tinted tile with the name's letter, so
   a missing portrait still reads as a deliberate piece of the card. */
.nte-icon{--size:40px;--tint:var(--game-vivid,var(--accent));display:inline-grid;place-items:center;flex-shrink:0;width:var(--size);height:var(--size);overflow:hidden;border-radius:30%;background:linear-gradient(150deg,color-mix(in srgb,var(--tint) 24%,var(--card-bg)),color-mix(in srgb,var(--tint) 9%,var(--card-bg)));vertical-align:middle}
.nte-icon[data-tint="1"]{--tint:var(--game-vivid-2,var(--accent))}
.nte-icon img{width:100%;height:100%;object-fit:contain}
.icon-fallback{color:color-mix(in srgb,var(--tint) 58%,var(--text));font-size:max(11px,calc(var(--size) * .34));font-weight:600;line-height:1;letter-spacing:-.01em}
.nte-icon[data-size=small]{--size:28px}
.nte-icon[data-size=large]{--size:56px}
.nte-icon[data-size=xl]{--size:72px}
.nte-icon[data-size=skill]{--size:36px;background:var(--surface-soft)}
</style>
