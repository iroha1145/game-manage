<script setup>
import { computed, ref, watch } from 'vue'
import { safeUrl } from '../calendar.js'
const props = defineProps({ candidates: { type: Array, default: () => [] }, alt: { type: String, default: '' }, decorative: { type: Boolean, default: false } })
const emit = defineEmits(['loaded', 'exhausted'])
const failed = ref(new Set())
const urls = computed(() => [...new Set(props.candidates.map(safeUrl).filter(Boolean))])
const current = computed(() => urls.value.find(url => !failed.value.has(url)))
watch(() => urls.value.join('\n'), () => { failed.value = new Set() })
watch(current, value => { if (!value) emit('exhausted') }, { immediate: true })
function onError(event) {
  const url = event?.target?.getAttribute?.('src') || current.value
  failed.value = new Set([...failed.value, url])
}
</script>
<template><img v-if="current" :src="current" :alt="decorative ? '' : alt" :aria-hidden="decorative ? 'true' : undefined" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="onError" @load="$emit('loaded', $event)" /></template>
<style scoped>img { display:block; object-fit:cover; }</style>
