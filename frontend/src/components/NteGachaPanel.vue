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
.nte-gacha-panel { display:grid; gap:20px; min-width:0 }
/* In the sheet the pool tiles are narrower than on a page: three across, their stats stacked under the count.
   (Phones already do this in the community card's own rules.) */
@media (min-width:561px) {
  .nte-gacha-panel :deep(.pool-overview) { grid-template-columns:repeat(auto-fit, minmax(min(100%, 190px), 1fr)); }
  .nte-gacha-panel :deep(.pool-stat) { grid-template-columns:minmax(0, 1fr); grid-template-areas:"name" "total" "stats"; padding:14px; }
  .nte-gacha-panel :deep(.pool-stat dl > div) { justify-content:space-between; }
}
/* The ledger is one hairline row until it is opened. */
.community-gacha > summary { display:flex; align-items:center; gap:8px; min-height:48px; padding:10px 16px; border:1px solid var(--border); border-radius:var(--radius-tile); background:var(--card-bg); color:var(--text); font-size:15px; font-weight:600; list-style:none; cursor:pointer }
.community-gacha > summary::-webkit-details-marker { display:none }
.community-gacha > summary > svg { margin-left:auto; color:var(--text-faint) }
.community-gacha > summary:active { transform:translateY(1px) }
.community-gacha > summary:focus-visible { border-radius:var(--radius-tile) }
.community-gacha[open] > summary { margin-bottom:16px }
@media (hover:hover) and (pointer:fine) { .community-gacha > summary:hover { background:var(--hover-bg); border-color:var(--border-strong) } .community-gacha > summary:hover > svg { color:var(--text-body) } }
</style>
