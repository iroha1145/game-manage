<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import CalendarTimelineContent from './CalendarTimelineContent.vue'
import VersionCalendarContent from './VersionCalendarContent.vue'
import VersionCalendarMetadata from './VersionCalendarMetadata.vue'
import AppIcon from './AppIcon.vue'
import MenuSelect from './MenuSelect.vue'
import { calendarRange, calendarBoundary, collectCalendarEvents, collectVersionCalendars, eventGeometry, eventStatus, formatBeijingDateTime, versionCalendarRange, safeUrl, shiftCalendarAnchor } from '../calendar.js'
import { gameStyle } from '../dashboard.js'
import { prefersReducedMotion, vGlide } from '../motion.js'
import { collectionState, hasFreshPublicFallback } from '../snapshot-state.js'
import CloudSnapshotStatus from './CloudSnapshotStatus.vue'

const props = defineProps({
  games: { type: Array, default: () => [] },
  snapshots: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  initialGameId: { type: String, default: '' },
  readErrors: { type: Object, default: () => ({}) },
  showSourceStatus: { type:Boolean, default:false },
})
const now = ref(Date.now())
const anchor = ref(now.value)
const mode = ref('version')
const filter = ref(props.initialGameId === 'all' ? '' : props.initialGameId)
const gameOptions = computed(() => [{ value: '', label: '全部游戏' }, ...props.games.map(game => ({ value: game.game_id, label: game.display_name }))])
const selectedId = ref(null)
const detailElement = ref(null)
let selectedTrigger = null
const boardElement = ref(null)
const boardTop = ref(240)
let layoutObserver
function fitWindow() {
  if (typeof window === 'undefined' || !boardElement.value?.getBoundingClientRect) return
  boardTop.value = Math.round(boardElement.value.getBoundingClientRect().top + window.scrollY)
}
let timer
onMounted(() => {
  timer = setInterval(() => { now.value = Date.now() }, 60000)
  fitWindow()
  if (typeof window !== 'undefined') window.addEventListener('resize', fitWindow)
  if (typeof ResizeObserver !== 'undefined' && boardElement.value?.parentElement) {
    layoutObserver = new ResizeObserver(fitWindow)
    layoutObserver.observe(boardElement.value.parentElement)
  }
})
onUnmounted(() => {
  clearInterval(timer)
  if (typeof window !== 'undefined') window.removeEventListener('resize', fitWindow)
  layoutObserver?.disconnect()
})
watch(() => props.initialGameId, (id) => { filter.value = id === 'all' ? '' : id })
watch(filter, () => { selectedId.value = null })

const versionCalendars = computed(() => collectVersionCalendars(props.games, props.snapshots, filter.value, now.value))
const range = computed(() => mode.value === 'version' ? versionCalendarRange(versionCalendars.value.flatMap(c => c.events), now.value) || calendarRange(anchor.value, 'rolling') : calendarRange(anchor.value, mode.value))
const rangeTitle = computed(() => mode.value === 'version' ? '版本活动汇总' : mode.value === 'month'
  ? formatBeijingDateTime(range.value.start).slice(0, 7).replace('-', ' 年 ') + ' 月'
  : `${formatBeijingDateTime(range.value.start).slice(5, 10)} — ${formatBeijingDateTime(range.value.end - 1).slice(5, 10)}`)
const events = computed(() => (mode.value === 'version' ? versionCalendars.value.flatMap(c => c.events) : collectCalendarEvents(props.games, props.snapshots, filter.value)).map(event => {
  const geometry = eventGeometry(event, range.value)
  const status = eventStatus(event, now.value)
  return {...event, geometry, status}
}))
const visibleEvents = computed(() => mode.value === 'version' ? events.value : events.value.filter(event => event.geometry.visible))
const selected = computed(() => events.value.find(event => event.id === selectedId.value))
const sourceUrl = computed(() => safeUrl(selected.value?.source_url))
const filteredGames = computed(() => props.games.filter(game => !filter.value || game.game_id === filter.value))
const staleGames = computed(() => filteredGames.value.filter(game => props.snapshots[game.game_id]?.events?.stale).map(game => game.display_name))
const eventGames = computed(() => filteredGames.value.filter(game => !Array.isArray(game.capabilities) || game.capabilities.includes('events')))
const missingGames = computed(() => eventGames.value.filter(game => !collectionState(props.snapshots[game.game_id]?.events) && !Array.isArray(props.snapshots[game.game_id]?.events?.payload)).map(game => game.display_name))
const neverGames = computed(() => eventGames.value.filter(game => collectionState(props.snapshots[game.game_id]?.events) === 'never').map(game => game.display_name))
const failedCollections = computed(() => eventGames.value.filter(game => !props.readErrors[game.game_id] && collectionState(props.snapshots[game.game_id]?.events) === 'failed').map(game => ({ id: game.game_id, name: game.display_name, partial: hasFreshPublicFallback(props.snapshots[game.game_id]?.events), retained: Array.isArray(props.snapshots[game.game_id]?.events?.payload) })))
const failedCollectionAlerts = computed(() => failedCollections.value.filter(failure => !failure.partial))
const failedCollectionNames = computed(() => failedCollectionAlerts.value.map(failure => failure.name).join('、'))
const collectionRetainedMessage = computed(() => failedCollectionAlerts.value.every(failure => failure.retained) ? '正在显示已有活动。' : failedCollectionAlerts.value.some(failure => failure.retained) ? '部分游戏正在显示已有活动，其余暂无可显示活动。' : '暂无可显示活动。')
const partialCollections = computed(() => failedCollections.value.filter(failure => failure.partial))
const emptyTitle = computed(() => failedCollectionAlerts.value.length ? '活动更新暂不可用，等待更新' : neverGames.value.length ? '等待活动更新' : '暂无活动数据')
const failedReads = computed(() => filteredGames.value.filter(game => props.readErrors[game.game_id]).map(game => ({
  id: game.game_id, name: game.display_name, error: props.readErrors[game.game_id], retained: Array.isArray(props.snapshots[game.game_id]?.events?.payload),
})))
const failedReadNames = computed(() => failedReads.value.map(failure => failure.name).join('、'))
const readRetainedMessage = computed(() => failedReads.value.every(failure => failure.retained) ? '正在显示已有活动。' : failedReads.value.some(failure => failure.retained) ? '部分游戏正在显示已有活动，其余暂无可显示活动。' : '暂无可显示活动。')
function gameAccent(id) {
  return gameStyle(id === 'lol' ? 'league_of_legends' : id).color
}
function shift(direction) { anchor.value = shiftCalendarAnchor(anchor.value, mode.value, direction) }
function goToday() { now.value = Date.now(); anchor.value = now.value }
function setMode(value) { mode.value = value }
async function selectEvent(event, interaction) {
  selectedTrigger = interaction?.currentTarget ?? null
  selectedId.value = event.id
  await nextTick()
  detailElement.value?.scrollIntoView?.({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'nearest' })
  detailElement.value?.focus?.({ preventScroll: true })
}
async function closeDetail() {
  selectedId.value = null
  await nextTick()
  if (selectedTrigger?.isConnected) selectedTrigger.focus()
  selectedTrigger = null
}
</script>

<template>
  <div class="calendar-page">
    <header class="page-heading">
      <div class="page-heading-copy"><h1>活动日历</h1><p class="page-description">查看各游戏的活动安排与截止时间。</p></div>
      <div class="page-meta calendar-timezone"><AppIcon name="clock" :size="14" /> 北京时间 <strong>UTC+8</strong></div>
    </header>

    <section ref="boardElement" class="calendar-board" aria-label="游戏活动时间轴" :aria-busy="loading" :style="{'--calendar-top':`${boardTop}px`}">
      <div class="calendar-toolbar">
        <div class="calendar-navigation">
          <div v-if="mode !== 'version'" class="calendar-arrows"><button type="button" aria-label="上一时间范围" @click="shift(-1)"><AppIcon name="chevron" :size="15" class="previous-arrow" /></button><button type="button" aria-label="下一时间范围" @click="shift(1)"><AppIcon name="chevron" :size="15" class="next-arrow" /></button></div>
          <h2 aria-live="polite">{{ rangeTitle }}</h2>
          <button v-if="mode !== 'version'" class="today-button" type="button" @click="goToday">今天</button>
        </div>
        <div class="calendar-filters">
          <div v-glide class="range-toggle segmented" aria-label="显示范围"><button type="button" :aria-pressed="mode === 'version'" @click="setMode('version')">版本</button><button type="button" :aria-pressed="mode === 'rolling'" @click="setMode('rolling')">近 30 天</button><button type="button" :aria-pressed="mode === 'month'" @click="setMode('month')">整月</button><button type="button" :aria-pressed="mode === 'fortnight'" @click="setMode('fortnight')">14 天</button></div>
          <MenuSelect v-model="filter" label="筛选游戏" align="end" :options="gameOptions" />
        </div>
      </div>
      <div class="calendar-meta"><span><strong>{{ visibleEvents.length }}</strong> 项活动<span v-if="events.length > visibleEvents.length"> · 共 {{ events.length }} 项</span></span><div class="calendar-legend"><span><i class="legend-range" />活动区间</span><span><i class="legend-point" />日期标记</span><span><i class="legend-today" />现在</span></div></div>
      <p v-if="failedCollectionAlerts.length" class="calendar-read-error" role="status">{{ failedCollectionNames }} · 活动更新暂不可用。{{ collectionRetainedMessage }}</p>
      <p v-if="failedReads.length" class="calendar-read-error" role="status">{{ failedReadNames }} · 活动读取失败。{{ readRetainedMessage }}</p>
      <p v-if="missingGames.length && !loading" class="calendar-missing" role="status">{{ missingGames.join('、') }} · 尚未取得活动，请稍后刷新。</p>
      <p v-if="neverGames.length && !loading" class="calendar-missing" role="status">{{ neverGames.join('、') }} · 等待活动更新。</p>
      <details v-if="showSourceStatus || staleGames.length || failedReads.length || partialCollections.length || versionCalendars.length" class="calendar-source-states"><summary>数据来源详情</summary><p v-if="staleGames.length" class="calendar-stale">数据可能过期 · {{ staleGames.join('、') }}</p><p v-for="failure in partialCollections" :key="failure.id">{{ failure.name }} · 部分来源不可用，显示可用来源数据。</p><p v-for="failure in failedReads" :key="failure.id">{{ failure.name }}：{{ failure.error }}</p><div v-if="showSourceStatus" v-for="game in filteredGames" :key="game.game_id"><strong>{{ game.display_name }}</strong><CloudSnapshotStatus :snapshots="snapshots[game.game_id] || {}" :capabilities="['events']" /></div><VersionCalendarMetadata :calendars="versionCalendars" /></details>
      <p v-if="loading && !events.length" class="calendar-empty" role="status">正在读取活动…</p>

      <VersionCalendarContent v-else-if="mode === 'version'" :calendars="versionCalendars" :as-of="now" :selected-id="selectedId" :empty-title="emptyTitle" :show-source-details="false" @select="selectEvent" />
      <CalendarTimelineContent v-else :events="events" :range="range" :as-of="now" :range-mode="mode" :selected-id="selectedId" :empty-title="emptyTitle" @select="selectEvent" />
      <div class="calendar-footer"><span>北京时间 UTC+8</span><span>↔ 可横向滚动</span></div>
    </section>



    <section v-if="selected" ref="detailElement" class="calendar-detail t-panel" aria-labelledby="calendar-detail-title" tabindex="-1" :style="{ '--game-accent': gameAccent(selected.gameId) }" @keydown.esc.stop="closeDetail">
      <div class="detail-heading"><div><p class="eyebrow">{{ selected.gameName }} / {{ selected.category }}</p><h2 id="calendar-detail-title">{{ selected.name || '未命名活动' }}</h2></div><button type="button" class="detail-close" aria-label="关闭活动详情" @click="closeDetail"><AppIcon name="close" :size="16" /></button></div>
      <div class="detail-status"><span>{{ selected.status }}</span><span v-if="selected.geometry.reason">{{ selected.geometry.reason }}</span><span v-if="selected.stale" class="calendar-stale">数据可能过期</span></div>
      <dl><div><dt>开始时间 · 北京时间</dt><dd>{{ calendarBoundary(selected, 'start') }}</dd><small v-if="selected.geometry.approximateStart">仅知开始日期 {{ selected.start_date }}，具体时刻未知</small><small v-if="selected.start_at && selected.geometry.start === null">原始值：{{ selected.start_at }}</small></div><div><dt>截止时间 · 北京时间</dt><dd>{{ calendarBoundary(selected, 'end') }}</dd><small v-if="selected.end_at && selected.geometry.end === null">原始值：{{ selected.end_at }}</small><small v-if="selected.end_at && selected.end_precision === 'version_end'">{{ selected.end_text }}，时刻取自下个版本的维护预告</small></div><div><dt>来源标题</dt><dd>{{ selected.source_name ? selected.source_name + ' · ' : '' }}{{ selected.source_title || '未提供' }}</dd></div><div><dt>快照抓取时间 · 北京时间</dt><dd>{{ formatBeijingDateTime(selected.fetchedAt) }}</dd></div></dl>
      <p v-if="selected.source_note" class="source-id">{{ selected.source_note }}</p>
      <p v-if="selected.geometry.clippedStart || selected.geometry.clippedEnd" class="clipping-note">时间条已按当前显示范围裁剪{{ selected.geometry.clippedStart ? '左侧' : '' }}{{ selected.geometry.clippedStart && selected.geometry.clippedEnd ? '和' : '' }}{{ selected.geometry.clippedEnd ? '右侧' : '' }}；以上为完整起止时间。</p>
      <p v-if="selected.source_post_id" class="source-id">来源标识：{{ selected.source_post_id }}</p><a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="source-link">查看原始公告 ↗</a>
    </section>
  </div>
</template>

<style scoped>
.calendar-page { min-width: 0; display: grid; gap: 20px; color: var(--text); }
.calendar-page > .page-heading { margin-bottom: 0; }
.calendar-timezone { gap: 6px; white-space: nowrap; }
.calendar-timezone strong { color: var(--text); font-family: var(--font-mono); font-size: 12px; font-weight: 500; }
.calendar-board { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: visible; min-width: 0; box-shadow: var(--card-shadow); display:flex; flex-direction:column; min-height:max(460px,calc(100dvh - var(--calendar-top) - 24px)); }
.calendar-board > .version-calendars { flex:none; }
.calendar-board :deep(.calendar-content:not(.image-mode)) { flex:none; min-height:320px; max-height:max(320px,calc(100dvh - var(--calendar-top) - 180px)); overflow:auto; }
.calendar-board > :not(.calendar-content):not(.version-calendars){flex-shrink:0}
.calendar-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; padding: 18px 20px 12px; }
.calendar-navigation, .calendar-filters { display: flex; align-items: center; gap: 12px; }
.calendar-navigation h2 { font-size: 17px; font-weight: 600; letter-spacing: -.025em; font-variant-numeric: tabular-nums; }
.calendar-arrows { display: flex; gap: 4px; }
.calendar-page button, .calendar-page select { cursor: pointer; font-family: inherit; }
.calendar-arrows button, .today-button, .detail-close { border: 1px solid var(--border); background: var(--card-bg); color: var(--text-body); border-radius: 6px; transition: color var(--duration-quick) var(--ease-smooth-out), border-color var(--duration-quick) var(--ease-smooth-out), background-color var(--duration-quick) var(--ease-smooth-out), transform var(--duration-quick) var(--ease-smooth-out); }
@media (hover: hover) and (pointer: fine) { .calendar-arrows button:hover, .today-button:hover, .detail-close:hover { background: var(--button-hover-bg); color: var(--text); } }
.calendar-arrows button:active, .today-button:active, .detail-close:active { transform: scale(var(--scale-medium)); box-shadow: var(--btn-shadow-pressed); }
.calendar-arrows button { display: grid; place-items: center; height: 30px; width: 30px; padding: 0; }
.previous-arrow { transform: rotate(90deg); }
.next-arrow { transform: rotate(-90deg); }
.today-button { min-height: 32px; padding: 5px 12px; font-size: 12px; font-weight: 500; }
.calendar-meta { display: flex; justify-content: space-between; gap: 12px; padding: 0 20px 14px; font-size: 11px; color: var(--text-muted); }
.calendar-meta strong { color: var(--text); font-size: 13px; font-weight: 600; }
.calendar-legend { display: flex; gap: 16px; }
.calendar-legend span { display: flex; align-items: center; gap: 6px; }
.calendar-legend i { display: inline-block; }
.legend-range { width: 12px; height: 7px; border-radius: 2px; background: var(--text-faint); }
.legend-point { width: 6px; height: 6px; background: var(--text-muted); transform: rotate(45deg); }
.legend-today { width: 2px; height: 10px; background: var(--accent); }
.calendar-stale { color: var(--stale-text); font-size: 11px; }
.calendar-board > .calendar-stale { margin: 0 20px 16px; padding: 10px 12px; background: var(--stale-bg); border: 1px solid color-mix(in srgb, var(--stale-text) 22%, transparent); border-radius: 8px; font-size: 12px; }
.calendar-read-error, .calendar-missing { margin: 0 20px 10px; padding: 7px 10px; font-size: 12px; line-height: 1.6; border-radius: 8px; }
.calendar-source-states { margin:0 20px 12px; color:var(--text-muted); font-size:11px; }
.calendar-source-states > summary { cursor:pointer; }
.calendar-source-states > div { margin-top:10px; }
.calendar-read-error { background: var(--danger-bg); border: 1px solid var(--danger-border); color: var(--danger); }
.calendar-missing { color: var(--text-muted); border: 1px dashed var(--border-strong); }
.calendar-footer { padding: 12px 20px; display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid var(--border); font-size: 11px; color: var(--text-faint); }
.calendar-detail { background: var(--card-bg); border: 1px solid color-mix(in srgb, var(--game-accent) 38%, var(--border)); border-radius: 12px; padding: 24px; scroll-margin: 80px; box-shadow: var(--card-shadow); }
.detail-heading { display: flex; align-items: start; justify-content: space-between; gap: 20px; }
.detail-heading h2 { margin-top: 6px; font-size: 20px; font-weight: 600; line-height: 1.4; }
.detail-close { display: grid; place-items: center; height: 32px; width: 32px; padding: 0; flex-shrink: 0; }
.detail-status { display: flex; gap: 8px; margin: 14px 0 22px; color: var(--text-body); font-size: 11px; font-weight: 500; flex-wrap: wrap; }
.detail-status > span { background: var(--overlay-3); padding: 2px 8px; border-radius: 5px; line-height: 18px; }
.detail-status > span:first-child { background: color-mix(in srgb, var(--game-accent) 14%, transparent); color: var(--text); }
.calendar-detail dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px; margin: 0; }
.calendar-detail dt { color: var(--text-muted); font-size: 11px; margin-bottom: 6px; }
.calendar-detail dd { margin: 0; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.calendar-detail dl small { display: block; color: var(--text-muted); margin-top: 6px; }
.source-id { color: var(--text-muted); margin-top: 10px; font-size: 11px; overflow-wrap: anywhere; }
.source-link { display: inline-block; margin-top: 16px; color: var(--accent); font-size: 13px; font-weight: 500; text-decoration: none; }
.calendar-page button:focus-visible, .calendar-page select:focus-visible, .timeline-scroll:focus-visible, .calendar-detail:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (hover: hover) and (pointer: fine) { .unplaced-event:hover { background-color: var(--overlay-2); } .source-link:hover { color: var(--accent-strong); } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 760px) {
  .calendar-toolbar { padding: 16px; gap: 14px; }
  .calendar-navigation { gap: 8px; width: 100%; }
  .calendar-navigation h2 { font-size: 15px; }
  .today-button { margin-left: auto; }
  .calendar-filters { justify-content: space-between; width: 100%; }
  .calendar-meta { padding: 0 16px 16px; flex-direction: column; }
  .calendar-footer { padding: 12px 16px; flex-direction: column; }
  .calendar-detail { padding: 18px; }
  .calendar-detail dl { grid-template-columns: 1fr; }
}
@media (max-width: 400px) {
  .calendar-toolbar { padding: 12px; }
  .calendar-filters { gap: 6px; }
  .range-toggle > button { padding-left: 8px; padding-right: 8px; }
  .calendar-navigation h2 { font-size: 14px; }
  .calendar-arrows button { width: 26px; }
  .today-button { padding-left: 8px; padding-right: 8px; }
}

</style>
