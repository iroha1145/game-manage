<script setup>
import { computed, ref } from 'vue'
import { gameStyle } from '../dashboard.js'
import { vGlide } from '../motion.js'
import { lazyPage } from '../lazy-page.js'
import AppIcon from './AppIcon.vue'
import GameIcon from './GameIcon.vue'
import SourceStatusPanel from './SourceStatusPanel.vue'
import AnnouncementList from './AnnouncementList.vue'
import NteDataCard from './NteDataCard.vue'
import NteAssetsPanel from './NteAssetsPanel.vue'
import NteRolesPanel from './NteRolesPanel.vue'
import NteGachaPanel from './NteGachaPanel.vue'
import EndfieldDashboard from './EndfieldDashboard.vue'
import WuwaDashboard from './WuwaDashboard.vue'
import NteGuides from './NteGuides.vue'
import NteModuleCard from './NteModuleCard.vue'

// Only the local workbench shows League of Legends; the cloud never loads this dashboard or its esports tables.
const LolDashboard = lazyPage(() => import('./LolDashboard.vue'))

const props = defineProps({
  cloudAccount: Object,
  authAccount: Object,
  cloudRole: String,
  cloudScope: Object,
  isAdmin: Boolean,
  showSourceStatus: { type: Boolean, default: false },
  esportsBrowse: Object,
  game: { type: Object, required: true },
  externalSnapshots: { type: Object, required: true },
  externalRefreshing: { type: Boolean, default: false },
  externalError: { type: String, default: '' },
  initialSection: { type: String, default: 'all' },
  collectionStatus: { type: Array, default: () => [] },
})
const emit = defineEmits(['refresh', 'calendar', 'esports-snapshot', 'esports-browse'])
const reauthorizationRequired = computed(() => props.cloudAccount?.state === 'expired' || props.collectionStatus.some(row => row.game_id === props.game.game_id && row.state === 'auth_expired'))
const errorNotice = computed(() => reauthorizationRequired.value ? '社区授权已失效，请到社区账号重新登录。' : props.externalError ? '暂时无法更新数据，请稍后重试。' : '')
const activeSection = ref(props.initialSection)
const nteGuideId=ref(''), nteFocusId=ref('')
function openNteGuide(id){nteGuideId.value=id;activeSection.value='guides'}
function openNteRole(id){nteFocusId.value=id;nteGuideId.value='';activeSection.value='characters'}
const style = computed(() => gameStyle(props.game.game_id))
const groups = computed(() => [
  { id: 'all', label: '全部', caps: props.game.capabilities },
  { id: 'overview', label: '概览', caps: ['account', 'stamina', 'progress', 'record'] },
  { id: 'characters', label: '角色与探索', caps: ['roles', 'exploration', 'calabash'] },
  { id: 'assets', label: '房产与载具', caps: ['realestate', 'vehicles'] },
  { id: 'teams', label: '官方配队', caps: ['teams'] },
  { id: 'guides', label: '角色攻略', caps: ['guides'] },
  { id: 'gacha', label: '抽卡统计', caps: ['gacha'] },
  { id: 'news', label: '公告与资讯', caps: ['announcement', 'news'] },
].filter(group => group.id === 'guides' ? props.game.game_id === 'nte' : group.caps.some(cap => cap !== 'events' && props.game.capabilities.includes(cap))))
// 「全部」按页签顺序排（概览类在前、对局和公告在后），不按后端能力列表的顺序。
const TAB_ORDER = groups => groups.filter(group => group.id !== 'all').flatMap(group => group.caps)
const visibleCaps = computed(() => {
  const current = groups.value.find(group => group.id === activeSection.value) || groups.value[0]
  const caps = props.game.capabilities.filter(cap => !['events', 'announcement', 'news'].includes(cap) && current?.caps.includes(cap))
  if (current?.id !== 'all') return caps
  const order = TAB_ORDER(groups.value)
  const rank = cap => (order.includes(cap) ? order.indexOf(cap) : order.length)
  return caps.map((cap, index) => ({ cap, index })).sort((a, b) => rank(a.cap) - rank(b.cap) || a.index - b.index).map(item => item.cap)
})

// Wuwa, LoL and Endfield have their own dashboards; this grid only serves NTE.
function capComponent(cap) {
  if (props.game.game_id !== 'nte') return null
  if (['realestate', 'vehicles', 'teams'].includes(cap)) return NteAssetsPanel
  if (cap === 'roles') return NteRolesPanel
  if (cap === 'gacha') return NteGachaPanel
  if (['account', 'stamina', 'progress', 'exploration', 'record'].includes(cap)) return NteDataCard
  return null
}

// Each panel gets only the props it declares; anything else would land on its
// root element as an attribute (roles="[object Object],…").
function capProps(cap) {
  const snaps = props.externalSnapshots
  const offered = {
    snap: snaps[cap],
    gameId: props.game.game_id,
    capability: cap,
    accountId: cap === 'roles' && props.cloudScope ? props.cloudScope : props.cloudScope ? `${props.cloudScope.account_id}:${props.cloudScope.role_id}` : ['nte', 'endfield'].includes(props.game.game_id) ? snaps.account?.payload?.role_id || '' : '',
    roles: snaps.roles?.payload?.entries || [],
  }
  const declared = capComponent(cap)?.props ?? {}
  return Object.fromEntries(Object.entries(offered).filter(([key]) => key in declared))
}
</script>

<template>
  <section class="game-card game-theme" :class="`game-${game.game_id}`" :style="{ '--game-accent': style.color, '--game-vivid': style.vivid, '--game-vivid-2': style.vivid2 }">
    <div v-if="errorNotice" class="error-bar" role="alert">
      {{ errorNotice }}
    </div>

    <header class="card-head">
      <div class="game-heading"><GameIcon class="detail-monogram" :game-id="game.game_id" :name="game.display_name" /><div><h1 class="game-name">{{ game.display_name }}</h1></div></div>
      <span
        v-if="!game.credentials_configured && game.game_id !== 'endfield'"
        class="badge badge-danger"
      >
        未配置凭据
      </span>
      <SourceStatusPanel v-if="showSourceStatus" :game="game" :collection="collectionStatus" />
      <button
        type="button"
        class="ui-button refresh-btn"
        :disabled="externalRefreshing"
        @click="emit('refresh')"
      >
        <AppIcon name="refresh" :size="15" :class="{ spinning: externalRefreshing }" /><span :class="{ 't-shimmer': externalRefreshing }">{{ externalRefreshing ? '刷新中…' : '刷新数据' }}</span>
      </button>
    </header>
    <div v-if="!['wuthering_waves','league_of_legends','endfield'].includes(game.game_id)" class="detail-navigation"><nav v-glide class="detail-tabs segmented" aria-label="游戏数据分区"><button v-for="group in groups" :key="group.id" type="button" :aria-pressed="activeSection === group.id" :class="{ active: activeSection === group.id }" @click="activeSection = group.id">{{ group.label }}</button></nav><button v-if="game.capabilities.includes('events')" class="text-link" @click="emit('calendar')"><AppIcon name="calendar" :size="15" />活动日历 <AppIcon name="arrow" :size="15" /></button></div>
    <WuwaDashboard v-if="game.game_id === 'wuthering_waves'" :snaps="externalSnapshots" :configured="game.credentials_configured" :initial-section="initialSection" @calendar="emit('calendar')" />
    <LolDashboard v-else-if="game.game_id === 'league_of_legends'" :snaps="externalSnapshots" :esports-browse="esportsBrowse" @esports-snapshot="emit('esports-snapshot', $event)" @esports-browse="emit('esports-browse', $event)" @refresh="emit('refresh')" />
    <EndfieldDashboard v-else-if="game.game_id === 'endfield'" :snaps="externalSnapshots" :configured="game.credentials_configured" :auth-account="authAccount" :refreshing="externalRefreshing" :initial-section="initialSection" :cloud-account="cloudAccount" :cloud-role="cloudRole" :is-admin="isAdmin" @calendar="emit('calendar')" @refresh="emit('refresh')" />
    <NteModuleCard v-else-if="game.game_id === 'nte' && activeSection === 'guides'" capability="guides"><NteGuides :roles="externalSnapshots.roles?.payload?.entries || []" :can-maintain="!cloudAccount || isAdmin" :character-id="nteGuideId" @role="openNteRole" /></NteModuleCard>
    <div v-else class="cap-list">
      <template v-for="cap in visibleCaps" :key="cap">
        <NteModuleCard v-if="capComponent(cap)" :capability="cap" :snap="externalSnapshots[cap]" :account-id="externalSnapshots.account?.payload?.role_id || ''" :class="['detail-cap', `detail-cap-${cap}`]">
          <component :is="capComponent(cap)" v-bind="{...capProps(cap),...(cap==='roles' ? {focusCharacterId:nteFocusId,detailMode:!!nteFocusId,onGuide:openNteGuide} : {})}" />
        </NteModuleCard>
      </template>
      <AnnouncementList v-if="['all', 'news'].includes(activeSection) && game.capabilities.some(cap => ['announcement', 'news'].includes(cap))" class="detail-articles" :game-id="game.game_id" :snap="externalSnapshots.news?.payload ? externalSnapshots.news : externalSnapshots.announcement" />
    </div>
  </section>
</template>

<style scoped>
.detail-articles{grid-column:1/-1}
.detail-cap-realestate, .detail-cap-vehicles, .detail-cap-teams, .detail-cap-roles, .detail-cap-gacha, .detail-cap-exploration { grid-column: 1 / -1; }
.game-card {
  min-width: 0;
}

.error-bar {
  background: var(--danger-bg);
  border: 1px solid var(--danger-border);
  color: var(--danger);
  padding: 12px 16px;
  font-size: 13px;
  border-radius: var(--radius-well);
  margin-bottom: 20px;
  overflow-wrap: anywhere;
}

.card-head { display:flex; align-items:center; gap:8px 12px; margin-bottom:24px; flex-wrap:wrap; }
.game-heading { display:flex; align-items:center; gap:12px; margin-right:auto; min-width:0; }
.detail-monogram { display:grid; place-items:center; font-size:22px; width:42px; height:42px; border-radius:var(--radius-well); }
.game-name { font-size:24px; line-height:32px; font-weight:600; }

.cap-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}
.detail-navigation { display:flex; justify-content:space-between; gap:10px 16px; align-items:center; margin:0 0 16px; flex-wrap:wrap; }
@media(max-width:950px) { .cap-list { grid-template-columns:1fr; } }
@media(max-width:600px) { .card-head { margin-bottom:16px; gap:12px; }.game-heading { gap:10px; flex-basis:100%; }.game-name { font-size:22px; line-height:28px; }.detail-monogram { width:36px; height:36px; font-size:20px; }.detail-tabs button { padding:4px 9px; } }
</style>
