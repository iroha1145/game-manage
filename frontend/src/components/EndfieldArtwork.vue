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
function failImage(event) {
  const failed = event?.target?.currentSrc || event?.target?.src || image.value
  if (failed) failedUrls.value = new Set([...failedUrls.value, failed])
}
watch(() => [props.src, props.operatorId, props.name, props.portrait], () => { failedUrls.value = new Set() })
</script>
<template><span class="endfield-artwork" :class="{ 'is-portrait': portrait }"><img v-if="image" :src="image" :alt="name" loading="lazy" referrerpolicy="no-referrer" @error="failImage" /><span v-else aria-hidden="true">{{ name.slice(0,1) }}</span></span></template>
<style scoped>
.endfield-artwork{display:grid;grid-template:minmax(0,1fr)/minmax(0,1fr);place-items:center;flex-shrink:0;min-width:0;min-height:0;width:54px;height:54px;background:var(--accent-soft);border:1px solid var(--border);overflow:hidden;color:var(--game-endfield);font-family:var(--font-mono);font-size:24px}.endfield-artwork img{display:block;min-width:0;min-height:0;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain}.is-portrait{background:linear-gradient(150deg,var(--accent-soft),transparent);border:0}.is-portrait img{object-fit:contain;object-position:center bottom}
</style>
