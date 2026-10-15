<script setup>
import { computed, ref, watch } from 'vue'
import { operatorImage, operatorArtwork } from '../endfield-reports.js'
const props = defineProps({ src: String, name: { type: String, default: '未知' }, operatorId: String, role: Boolean })
const failed = ref(false)
const image = computed(() => failed.value ? null : props.role ? operatorArtwork({ avatar_url: props.src, id: props.operatorId, name: props.name }) : operatorImage(props.src))
watch(() => [props.src, props.operatorId, props.name], () => { failed.value = false })
</script>
<template><span class="endfield-artwork"><img v-if="image" :src="image" :alt="name" loading="lazy" referrerpolicy="no-referrer" @error="failed = true" /><span v-else aria-hidden="true">{{ name.slice(0,1) }}</span></span></template>
<style scoped>
.endfield-artwork{display:grid;place-items:center;flex-shrink:0;width:54px;height:54px;border-radius:6px;background:var(--accent-soft);overflow:hidden;color:var(--game-endfield);font-size:24px}.endfield-artwork img{width:100%;height:100%;object-fit:contain}
</style>
