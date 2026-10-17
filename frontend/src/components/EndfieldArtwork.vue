<script setup>
import { computed, ref, watch } from 'vue'
import { operatorImage, operatorArtwork } from '../endfield-reports.js'
const props = defineProps({ src: String, name: { type: String, default: '未知' }, operatorId: String, role: Boolean, portrait: Boolean })
const failedUrls = ref(new Set())
const candidates = computed(() => {
  const operator = { avatar_url: props.src, id: props.operatorId, name: props.name }
  return [...new Set((props.role ? [
    props.portrait ? operatorArtwork(operator, { portrait: true }) : null,
    operatorArtwork(operator),
  ] : [operatorImage(props.src)]).filter(Boolean))]
})
const image = computed(() => candidates.value.find(url => !failedUrls.value.has(url)) || null)
const initial = computed(() => [...props.name][0] ?? '')
function failImage(event) {
  const failed = event?.target?.currentSrc || event?.target?.src || image.value
  if (failed) failedUrls.value = new Set([...failedUrls.value, failed])
}
watch(() => [props.src, props.operatorId, props.name, props.portrait], () => { failedUrls.value = new Set() })
</script>
<template><span class="endfield-artwork" :class="{ 'is-portrait': portrait, 'has-image': !!image }"><img v-if="image" :src="image" :alt="name" loading="lazy" referrerpolicy="no-referrer" @error="failImage" /><span v-else aria-hidden="true">{{ initial }}</span></span></template>
<style scoped>
/* Art is network-only and often blocked, so the fallback is a designed tile:
   a wash of the game colours with the first character at a size that follows the tile. */
.endfield-artwork{--art-1:var(--game-vivid,var(--game-endfield-vivid));--art-2:var(--game-vivid-2,var(--game-endfield-2));container-type:size;display:grid;grid-template:minmax(0,1fr)/minmax(0,1fr);place-items:center;flex-shrink:0;min-width:0;min-height:0;width:54px;height:54px;border-radius:var(--radius-control);overflow:hidden;font-size:22px;font-weight:600;color:var(--game-endfield);background:linear-gradient(150deg,color-mix(in srgb,var(--art-1) 30%,var(--card-bg)),color-mix(in srgb,var(--art-2) 14%,var(--card-bg)));box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--art-1) 20%,transparent)}
.endfield-artwork>span{font-size:clamp(14px,46cqmin,64px);line-height:1;letter-spacing:0}
.endfield-artwork.has-image{background:var(--surface-soft);box-shadow:none}
.endfield-artwork img{display:block;min-width:0;min-height:0;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain}
.is-portrait.has-image{background:transparent}
.is-portrait img{object-fit:contain;object-position:center bottom}
</style>
