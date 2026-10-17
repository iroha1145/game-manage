<script setup>
import { ref, inject, unref } from 'vue'
import WuwaRoleDialog from './WuwaRoleDialog.vue'
import WuwaStatus from './WuwaStatus.vue'
// primary: the card's open button is the one filled action of its page (a launcher).
// sheetWidth: the reading width of its dialog in px.
defineProps({ title: { type: String, required: true }, snap: { default: null }, buttonLabel: { type: String, default: '' }, inline: Boolean, primary: Boolean, sheetWidth: { type: Number, default: 0 } })
const opened = ref(false)
const imageMode = inject('wuwaImageMode', false)
</script>
<template>
  <!-- A card on the board. With a dialog the whole card opens it: the button is stretched over the card. -->
  <section class="wuwa-panel wuwa-module-card" :class="{ 'is-openable': !inline && !unref(imageMode) }">
    <header class="cap-title wuwa-module-heading"><h2>{{ title }}</h2><button v-if="!inline && !unref(imageMode)" type="button" class="ui-button small-button wuwa-open" :class="{ primary }" @click="opened = true">{{ buttonLabel || `查看${title}` }}</button></header>
    <p v-if="snap?.reading && !snap?.payload" role="status">正在读取{{ title }}…</p>
    <p v-else-if="snap?.readError && !snap?.payload" role="status">{{ snap.readError }}</p>
    <template v-else><slot name="preview" />
    <div v-if="inline || unref(imageMode)" class="inline-content"><slot /></div></template>
    <WuwaStatus v-if="snap" :snap="snap" />
    <WuwaRoleDialog v-if="!inline && !unref(imageMode) && opened" :title="title" :width="sheetWidth" @close="opened = false"><slot /></WuwaRoleDialog>
  </section>
</template>
