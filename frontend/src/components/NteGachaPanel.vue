<script setup>
import NteGachaLedger from './NteGachaLedger.vue'
import NteCommunityGacha from './NteCommunityGacha.vue'
import AppIcon from './AppIcon.vue'
import { ref } from 'vue'
import { isCloudMode } from '../http-client.js'
const cloudMode = isCloudMode()
defineProps({ snap: { type: Object, default: null }, accountId: { type: String, default: '' }, roles: { type: Array, default: () => [] } })
const ledgerOpen = ref(false)
</script>
<template>
  <div class="nte-gacha-panel"><NteCommunityGacha :snap="snap" :roles="roles" /><details class="community-gacha" @toggle="ledgerOpen = $event.target.open"><summary><span class="ledger-name">{{ cloudMode ? '本人逐抽账本' : '本地逐抽账本' }}</span><AppIcon name="chevron" :size="14" class="t-disclosure" /></summary><NteGachaLedger v-if="ledgerOpen" :account-id="accountId" /></details></div>
</template>
<style scoped>
.nte-gacha-panel { display:grid; gap:16px; min-width:0 }
.community-gacha > summary { display:flex; align-items:center; gap:8px; min-height:40px; padding:8px 14px; border:1px solid var(--border); border-radius:var(--radius-card); background:var(--card-bg); color:var(--text); font-size:14px; font-weight:500; list-style:none; cursor:pointer }
.community-gacha > summary::-webkit-details-marker { display:none }
.community-gacha > summary > svg { margin-left:auto; color:var(--text-faint) }
.community-gacha[open] > summary { margin-bottom:8px }
@media (hover:hover) and (pointer:fine) { .community-gacha > summary:hover { background:var(--button-hover-bg) } .community-gacha > summary:hover > svg { color:var(--text-body) } }
</style>
