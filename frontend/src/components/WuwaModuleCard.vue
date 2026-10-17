<script setup>
import { ref, inject, unref } from 'vue'
import WuwaRoleDialog from './WuwaRoleDialog.vue'
import WuwaStatus from './WuwaStatus.vue'
defineProps({ title: { type: String, required: true }, snap: { default: null }, buttonLabel: { type: String, default: '' }, inline: Boolean })
const opened = ref(false)
const imageMode = inject('wuwaImageMode', false)
</script>
<template>
  <!-- A card on the board. With a dialog the whole card opens it: the button is stretched over the card. -->
  <section class="wuwa-panel wuwa-module-card" :class="{ 'is-openable': !inline && !unref(imageMode) }">
    <header class="cap-title wuwa-module-heading"><h2>{{ title }}</h2><button v-if="!inline && !unref(imageMode)" type="button" class="ui-button small-button wuwa-open" @click="opened = true">{{ buttonLabel || `查看${title}` }}</button></header>
    <slot name="preview" />
    <div v-if="inline || unref(imageMode)" class="inline-content"><slot /></div>
    <WuwaStatus v-if="snap" :snap="snap" />
    <WuwaRoleDialog v-if="!inline && !unref(imageMode) && opened" :title="title" @close="opened = false"><slot /></WuwaRoleDialog>
  </section>
</template>
