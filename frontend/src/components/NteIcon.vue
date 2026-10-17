<script setup>
import { computed, ref, watch } from 'vue'
import { safeNteIcon } from '../nte-icons.js'
const props=defineProps({src:{type:String,default:''},name:{type:String,default:''},size:{type:String,default:'medium'}})
const failed=ref(false),url=computed(()=>safeNteIcon(props.src))
// Big tiles carry one character, small ones two, so the letter never crowds the tile.
const letter=computed(()=>(['large','xl'].includes(props.size) ? props.name.slice(0,1) : props.name.slice(0,2)) || '?')
watch(url,()=>{failed.value=false})
</script>
<template><span class="nte-icon" :data-size="size" :title="name"><img v-if="url && !failed" :src="url" :alt="name" loading="lazy" referrerpolicy="no-referrer" @error="failed = true" /><span v-else class="icon-fallback" aria-hidden="true">{{ letter }}</span></span></template>
<style scoped>
/* A rounded square. Without art it is the game's tone with the name's letter in
   its ink, so a missing portrait still reads as a deliberate piece of the card. */
.nte-icon{--size:40px;display:inline-grid;place-items:center;flex-shrink:0;width:var(--size);height:var(--size);overflow:hidden;border-radius:30%;background:var(--game-tone,var(--control-track));vertical-align:middle}
.nte-icon img{width:100%;height:100%;object-fit:contain}
/* In a bot image a picture that could not be fetched is swapped for its name, which keeps the ink on the tone. */
.nte-icon :deep(.render-missing-image){color:var(--game-accent)}
.icon-fallback{color:var(--game-accent,var(--text));font-size:max(11px,calc(var(--size) * .34));font-weight:600;line-height:1;letter-spacing:-.01em}
.nte-icon[data-size=small]{--size:28px}
.nte-icon[data-size=large]{--size:56px}
.nte-icon[data-size=xl]{--size:72px}
.nte-icon[data-size=skill]{--size:36px;background:var(--surface-soft);box-shadow:inset 0 0 0 1px var(--overlay-2)}
</style>
