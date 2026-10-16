<script setup>
import { computed, provide } from 'vue'
import VersionCalendarContent from './VersionCalendarContent.vue'
import WuwaRoleDetail from './WuwaRoleDetail.vue'
import NteRolesPanel from './NteRolesPanel.vue'
import WuwaGacha from './WuwaGacha.vue'
import NteCommunityGacha from './NteCommunityGacha.vue'
import NteGachaLedger from './NteGachaLedger.vue'
import { collectVersionCalendars } from '../calendar.js'
import { displayBeijing } from '../time.js'
import { gameStyle } from '../dashboard.js'
import RenderGameSnapshot from './RenderGameSnapshot.vue'
import RenderNotice from './RenderNotice.vue'
const props = defineProps({ snapshot: {type:Object,required:true} })
// The whole page is an image: components that ask for image mode (GameIcon in the calendar) get it for every kind.
provide('wuwaImageMode', true)
const data = computed(() => props.snapshot.display_data)
const gameTheme = computed(() => ({ '--game-accent': gameStyle(props.snapshot.game).color }))
const calendars = computed(() => props.snapshot.kind === 'calendar' ? collectVersionCalendars(data.value.games, data.value.snapshots, '', Date.parse(props.snapshot.as_of)) : [])
</script>
<template>
  <div id="render-content" class="render-image game-theme" :style="gameTheme">
    <VersionCalendarContent v-if="snapshot.kind === 'calendar'" :calendars="calendars" :as-of="Date.parse(snapshot.as_of)" mode="image" />
    <template v-else-if="snapshot.kind === 'wuwa_role'"><p class="render-observation">更新于 {{ displayBeijing(data.fetched_at) }}</p><WuwaRoleDetail :data="data.detail" image-mode /></template>
    <NteRolesPanel v-else-if="snapshot.kind === 'nte_role'" :snap="data.snapshot" :detail-mode="data.snapshot.display_mode === 'detail'" image-mode />
    <WuwaGacha v-else-if="snapshot.kind === 'wuwa_gacha'" :snapshot="data.archive" image-mode />
    <template v-else-if="snapshot.kind === 'nte_gacha'">
      <NteCommunityGacha :snap="data.snapshot" :roles="data.roles || []" image-mode />
      <NteGachaLedger v-if="data.ledger" :snapshot="data.ledger" image-mode />
    </template>
    <template v-else-if="snapshot.kind === 'game_snapshot'">
      <RenderGameSnapshot v-for="(panel,index) in data.panels" :key="index" :panel="panel" :as-of="Date.parse(snapshot.as_of)" />
      <p v-for="(notice,index) in data.notices || []" :key="index" class="render-observation">{{ notice }}</p>
    </template>
    <RenderNotice v-else-if="snapshot.kind === 'notice'" :data="data" />
  </div>
  <div id="render-pages" class="render-image game-theme" :style="gameTheme" />
</template>
