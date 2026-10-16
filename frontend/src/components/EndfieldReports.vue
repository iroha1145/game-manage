<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { profileReport, rows, displayValue as display, sourceName as named, selectOperators, selectMedals } from '../endfield-reports.js'
import { displayBeijing } from '../time.js'
import { SHIP_CONVERSION_MODEL } from '../endfield-ship.js'
import SummaryMetrics from './SummaryMetrics.vue'
import EndfieldArtwork from './EndfieldArtwork.vue'
import EndfieldShipResident from './EndfieldShipResident.vue'
import EndfieldLoadout from './EndfieldLoadout.vue'
const props = defineProps({ payload: Object, imageMode:Boolean, view: { type: String, default: 'overview' }, fetchedAt: String, stale: Boolean,
  operatorDetail: Object, operatorDetailId: String, operatorBusy: Boolean, operatorError: String, operatorStale: Boolean, operatorFetchedAt: String })
const emit = defineEmits(['inspect', 'navigate', 'close-detail'])
const report = computed(() => profileReport(props.payload))
const overview = computed(() => report.value.overview || {})
const training = computed(() => report.value.training || {})
const regions = computed(() => rows(report.value.regions?.items))
const rooms = computed(() => rows(report.value.ship?.rooms))
const honor = computed(() => report.value.honor || { summary: { declared_count: props.payload?.achievements?.count }, items: [] })
const medalSearch=ref(''), medalCategory=ref(''), medalSort=ref('recent')
const medals=computed(()=>rows(honor.value.items))
const categories=computed(()=>[...new Set(medals.value.map(item=>item.category ?? null))].sort((a,b)=>a==null?1:b==null?-1:a.localeCompare(b,'zh-CN')))
const filteredMedals=computed(()=>selectMedals(medals.value,{search:medalSearch.value,category:medalCategory.value===''?undefined:JSON.parse(medalCategory.value),sort:medalSort.value}))
function clearMedalFilters(){medalSearch.value='';medalCategory.value=''}
const mainMission=computed(()=>typeof overview.value.base?.main_mission === 'string' ? overview.value.base.main_mission.trim() : '')
const search = ref(''), rarity = ref(''), profession = ref(''), sort = ref('level')
const operators = computed(() => rows(training.value.items))
const selected = computed(() => selectOperators(operators.value, { search: search.value, rarity: rarity.value, profession: profession.value, sort: sort.value }))
const rarities = computed(() => [...new Set(operators.value.map(item => item.rarity).filter(value => value != null))].sort((a,b) => b-a))
const professions = computed(() => [...new Set(operators.value.map(item => named(item.profession)).filter(value => value !== '未知'))])
const detailPanel = ref(null)
let detailOpener = null
function inspect(id, event) { detailOpener = event?.currentTarget || null; emit('inspect', id) }
watch(() => props.operatorDetailId, async id => {
  await nextTick()
  if (id) { detailPanel.value?.scrollIntoView?.({ block: 'start' }); detailPanel.value?.focus?.({ preventScroll: true }) }
  else detailOpener?.focus?.()
})
const time = value => value == null || value === '' ? '未知' : displayBeijing(value)
const pair = value => `${display(value?.current ?? value?.count)} / ${display(value?.total ?? value?.maximum)}`
const overviewMetrics = computed(() => [
  { label: '理智', current: overview.value.stamina?.current, total: overview.value.stamina?.maximum, note: Number.isFinite(overview.value.stamina?.current) && Number.isFinite(overview.value.stamina?.maximum) && overview.value.stamina.maximum > 0 && overview.value.stamina.current >= overview.value.stamina.maximum ? '该次观测理智已满' : `预计回满 ${time(overview.value.stamina?.expected_full_at)}` },
  { label: '已记录干员', value: training.value.summary?.listed_count },
  { label: '建设地区', value: report.value.regions?.summary?.region_count },
  { label: '帝江号房间', value: report.value.ship?.summary?.room_count },
])
const progressMetrics = computed(() => rows(overview.value.progress).map(item => ({ label: item.name || item.title || '进度', current: item.cur, total: item.total,
  note: item.remaining == null ? '' : item.remaining === 0 ? '已完成' : `还需 ${item.remaining}` })))
const knownTasks = computed(() => rows(overview.value.progress).some(item => ['daily','weekly'].includes(item.id) && item.remaining != null))
const trainingMetrics = computed(() => [
  { label: '已记录干员', value: training.value.summary?.listed_count },
  { label: '来源干员数', value: training.value.summary?.declared_count },
  { label: '已知等级均值', value: training.value.summary?.average_level == null ? null : Number(training.value.summary.average_level.toFixed(1)), note: `${display(training.value.summary?.known_levels)} 名有等级记录` },
  { label: '最高已知等级', value: training.value.summary?.max_level },
])
function collections(area) {
  if (Array.isArray(area.collections)) return area.collections
  return [['puzzles','醚质'],['chests','宝箱'],['equipment_chests','装备制造模板'],['pieces','维修灵感点'],['blackboxes','协议采录桩']]
    .map(([key,label]) => ({ key, label, current: area[key]?.count, total: area[key]?.total }))
}
const detail = computed(() => props.operatorDetail)
const detailName = computed(() => detail.value?.name || operators.value.find(item => String(item.id) === props.operatorDetailId)?.name || '干员配装')
</script>

<template>
  <div class="endfield-reports">
    <template v-if="view === 'overview'">
      <section class="ef-report ef-hero"><header><div><h2>今日档案</h2></div><span v-if="stale && !imageMode" class="badge badge-stale">待更新</span><span v-else class="ef-state">森空岛档案</span></header>
        <div class="ef-identity"><EndfieldArtwork :src="overview.base?.avatar_url" :name="overview.base?.name || '管理员'" /><div><h3>{{ overview.base?.name || '未知昵称' }}</h3><p v-if="!imageMode">UID {{ display(overview.base?.role_id) }}</p></div><dl><div><dt>账号等级</dt><dd>{{ display(overview.base?.level) }}</dd></div><div><dt>探索等级</dt><dd>{{ display(overview.base?.world_level) }}</dd></div></dl></div>
        <p v-if="mainMission" class="ef-main-mission"><span>主线进度</span><strong>{{ mainMission }}</strong></p>
        <SummaryMetrics :metrics="overviewMetrics" />
      </section>
      <div class="ef-columns">
        <section class="ef-report"><header><div><h2>每日与通行证进度</h2></div></header><SummaryMetrics v-if="progressMetrics.length" rows :metrics="progressMetrics" /><p v-else class="ef-empty">尚未采集进度。</p></section>
        <section class="ef-report"><header><div><h2>已知待办</h2></div></header>
          <ul v-if="rows(overview.todos).length" class="ef-todos"><li v-for="(item,index) in overview.todos" :key="item.id || index"><span>{{ item.name }}</span><strong>还需 {{ display(item.remaining) }}</strong></li></ul>
          <p v-else class="ef-empty">{{ overview.todos == null || !knownTasks ? '尚未采集到可判断的每日或每周任务进度。' : '已采集的每日与每周任务没有已知未完成项。' }}</p>
          <p class="ef-note">待办仅依据这次档案中的明确进度；未提供的任务状态仍未知。</p>
        </section>
      </div>
      <div v-if="!imageMode" class="ef-shortcuts"><button v-for="[key,label] in [['operators','查看全员练度'],['regions','查看地区建设'],['ship','查看帝江号']]" :key="key" type="button" class="ui-button" @click="emit('navigate',key)">{{ label }} →</button></div>
    </template>

    <template v-else-if="view === 'operators' || view === 'detail'">
      <section v-if="view === 'operators'" v-show="!operatorDetailId" class="ef-report"><header><div><h2>全员练度</h2></div><span class="ef-note">显示 {{ selected.length }} / {{ operators.length }} 名</span></header>
        <SummaryMetrics compact :metrics="trainingMetrics" />
        <div class="ef-distribution"><span v-for="(count,key) in training.summary?.rarity_counts" :key="`r${key}`">{{ key }}★ <b>{{ count }}</b></span><span v-for="(count,key) in training.summary?.phase_counts" :key="`p${key}`">精英阶段 {{ key }} <b>{{ count }}</b></span></div>
        <p v-if="imageMode" class="ef-note">武器、装备、技能与战术道具详情：发送「终末地 角色 干员名」，按精确名称查看单干员配装。</p>
        <div v-if="!imageMode" class="ef-filters"><label>查找干员<input :value="search" @input="search = $event.target.value" type="search" placeholder="姓名或编号" /></label><label>稀有度<select v-model="rarity"><option value="">全部稀有度</option><option v-for="value in rarities" :key="value" :value="String(value)">{{ value }}★</option></select></label><label>职业<select v-model="profession"><option value="">全部职业</option><option v-for="value in professions" :key="value" :value="value">{{ value }}</option></select></label><label>排序<select v-model="sort"><option value="level">等级从高到低</option><option value="rarity">稀有度从高到低</option><option value="potential">潜能从高到低</option><option value="name">姓名</option></select></label></div>
        <p v-if="!selected.length" class="ef-empty">{{ operators.length ? '没有匹配的干员，可调整筛选。' : '尚无干员资料。' }}</p>
        <div v-else class="ef-roster"><article v-for="(operator,index) in selected" :key="operator.id || index" class="ef-operator">
          <div class="ef-portrait"><EndfieldArtwork role :operator-id="operator.char_id || operator.id" :src="operator.avatar_url" :name="operator.name || '干员'" /><small>{{ display(operator.rarity) }}★</small></div>
          <div class="ef-operator-copy"><h3>{{ display(operator.name) }}</h3><p class="ef-operator-level">Lv. {{ display(operator.level) }} <span>潜能 {{ display(operator.potential) }}</span></p><p>精英阶段 {{ display(operator.evolve_phase ?? operator.phase) }}</p><p class="ef-note">{{ named(operator.profession) }} · {{ named(operator.property) }}</p></div>
          <button v-if="!imageMode" type="button" class="ui-button" :disabled="operatorBusy && operatorDetailId === String(operator.id) || !operator.id" :aria-expanded="operatorDetailId === String(operator.id)" @click="inspect(operator.id,$event)">查看配装</button>
        </article></div>
      </section>
      <section v-if="operatorDetailId" ref="detailPanel" class="ef-report ef-detail" tabindex="-1" aria-label="干员配装详情" aria-live="polite"><div v-if="!imageMode" class="ef-detail-toolbar"><button type="button" class="text-link" @click="emit('close-detail')">← 返回全员练度</button><span v-if="operatorStale" class="badge badge-stale">配装待更新</span></div><header><div><h2>干员配装<span v-if="!detail"> · {{ detailName }}</span></h2></div><button v-if="!imageMode" type="button" class="ui-button" :disabled="operatorBusy" @click="emit('inspect',operatorDetailId)">重新读取配装</button></header>
        <p v-if="operatorBusy" class="ef-empty" role="status">正在读取干员配装…</p><p v-if="operatorError" class="ef-error" role="alert">{{ operatorError }}</p>
        <p v-if="!imageMode" class="ef-detail-time">配装同步于 {{ time(operatorFetchedAt) }}<span v-if="operatorStale"> · 正在显示上次成功读取的配装</span><span v-else-if="!operatorFetchedAt"> · 来源未提供独立更新时间</span></p>
        <EndfieldLoadout v-if="detail" :operator="detail" />
      </section>
    </template>

    <template v-else-if="view === 'regions'">
      <section class="ef-report ef-section-intro"><header><div><h2>地区建设</h2></div><span class="ef-note">地区数 {{ display(report.regions?.summary?.region_count) }}</span></header><p v-if="!regions.length" class="ef-empty">尚无地区建设资料。</p><p class="ef-note">调度券、据点派驻与探索收集。</p></section>
      <section v-for="(region,index) in regions" :key="region.id || index" class="ef-report"><header><div><h2>{{ named(region) }}</h2></div><span>等级 {{ display(region.level) }}</span></header>
        <SummaryMetrics :metrics="[{label:'地区调度券',current:region.money?.current ?? region.money?.count,total:region.money?.total},{label:'据点',value:region.settlements_available === false ? null : region.settlements_available === true || rows(region.settlements).length ? rows(region.settlements).length : null}]" />
        <div class="ef-settlements"><article v-for="(settlement,number) in rows(region.settlements)" :key="settlement.id || number" class="ef-subsection"><h3>{{ settlement.name || '据点' }} <small>等级 {{ display(settlement.level) }}</small></h3><p>基地调度券 <strong>{{ pair(settlement.coupon || {current:settlement.money,total:settlement.money_max}) }}</strong></p><p class="ef-note">派驻干员：{{ rows(settlement.officers).map(item => item.name || item.id || '未知').join('、') || (settlement.officers_available === true ? '无派驻' : '未提供') }}</p><div v-if="rows(settlement.officers).length" class="ef-assigned"><EndfieldArtwork v-for="(officer,officerIndex) in rows(settlement.officers)" :key="officer.id || officerIndex" role :operator-id="officer.id" :src="officer.avatar_url" :name="officer.name || officer.id || '干员'" /></div></article></div>
        <div class="ef-areas"><article v-for="(area,number) in rows(region.areas || region.levels)" :key="area.id || number" class="ef-subsection"><h3>{{ area.name || '区域' }}</h3><ul class="ef-facts"><li v-for="item in collections(area)" :key="item.key"><span>{{ item.label }}</span><strong>{{ pair(item) }}<small v-if="item.remaining != null"> · 剩余 {{ item.remaining }}</small></strong><progress v-if="Number.isFinite(item.percent)" :value="item.percent" max="100" :aria-label="`${area.name || '区域'}${item.label}`" /></li></ul></article></div>
      </section>
    </template>

    <template v-else-if="view === 'ship'">
      <section class="ef-report ef-ship-intro"><header><div><h2>帝江号</h2></div><span class="ef-state">快照换算</span></header><dl class="ef-ship-counts"><div><dt>房间数</dt><dd>{{ display(report.ship?.summary?.room_count) }}</dd></div><div><dt>有驻守记录的房间</dt><dd>{{ display(report.ship?.summary?.staffed_rooms) }}</dd></div><div><dt>驻守席位记录</dt><dd>{{ display(report.ship?.summary?.operator_slots) }}</dd></div></dl><p v-if="!imageMode" class="ef-note ef-ship-time">游戏观测于 {{ time(report.observed_at) }} · 抓取于 {{ time(fetchedAt || report.fetched_at) }}（北京时间）</p><details v-if="!imageMode" class="ef-model-note"><summary>查看换算依据</summary><p>心情与信赖采用原站 API v3.5.0 参考模型换算该次快照，不外推当前状态。心情以 100% 为上限，信赖最高 200%。</p><p>模型声明心情原始值为 0–10000；超出范围时保留原值，百分比显示未知。信赖按来源阈值分为友好、亲近、信任。换算结果不是官方实时状态，也未计入时间或房间加成。</p><a :href="SHIP_CONVERSION_MODEL.source_url" target="_blank" rel="noopener noreferrer">公开模型说明 ↗</a></details></section>
      <p v-if="!rooms.length" class="ef-empty ef-report">尚无帝江号资料。</p>
      <div class="ef-columns ef-ship-rooms"><section v-for="(room,index) in rooms" :key="room.id || index" class="ef-report ef-ship-room"><header><div><h2>{{ room.name || '舱室' }}</h2></div><span class="ef-room-level"><span>等级</span> LV. {{ display(room.level) }}</span></header><p v-if="!rows(room.operators).length" class="ef-empty">{{ room.operators_available === true ? '当前没有驻守干员记录。' : '尚未采集驻守干员资料。' }}</p><EndfieldShipResident v-for="(operator,number) in rows(room.operators)" :key="operator.id || operator.charId || number" :operator="operator" :image-mode="imageMode" /></section></div>
    </template>
    <template v-else-if="view === 'honor'">
      <section class="ef-report"><header><div><h2>光荣之路</h2></div><span v-if="medals.length" class="ef-note" role="status">显示 {{ filteredMedals.length }} / {{ medals.length }} 条已记录奖章</span></header><SummaryMetrics compact :metrics="[{label:'来源成就总数',value:honor.summary?.declared_count},{label:'已记录奖章',value:honor.summary?.listed_count}]" /><p class="ef-note">展示档案提供的奖章，不推断未获得的奖章或全收集进度。</p><div v-if="medals.length && !imageMode" class="ef-filters ef-medal-filters"><label>查找奖章<input :value="medalSearch" @input="medalSearch=$event.target.value" type="search" placeholder="输入奖章名称" /></label><label>奖章分类<select v-model="medalCategory"><option value="">全部分类</option><option v-for="category in categories" :key="JSON.stringify(category)" :value="JSON.stringify(category)">{{ category || '未提供分类' }}</option></select></label><label>获得时间排序<select v-model="medalSort"><option value="recent">最近获得优先</option><option value="oldest">最早获得优先</option><option value="source">来源顺序</option></select></label></div></section>
      <p v-if="!medals.length" class="ef-report ef-empty">{{ honor.available === true ? '当前档案没有奖章记录。' : '尚未采集奖章详情，请刷新档案。' }}</p>
      <section v-else-if="!filteredMedals.length" class="ef-report ef-empty"><p>没有匹配的奖章；可调整名称或分类筛选。</p><button type="button" class="ui-button" @click="clearMedalFilters">清除奖章筛选</button></section>
      <div v-else class="ef-medals"><article v-for="(medal,index) in filteredMedals" :key="medal.id ?? index" class="ef-report ef-medal"><EndfieldArtwork :src="medal.icon_url" :name="medal.name || '奖章'" /><div><h3>{{ medal.name || '未命名奖章' }}</h3><span class="ef-medal-category">{{ medal.category || '未提供分类' }}</span><p>等级 {{ display(medal.level) }} <span class="ef-medal-plated">{{ medal.is_plated === true ? '已镀层' : medal.is_plated === false ? '未镀层' : '镀层未知' }}</span></p><p class="ef-note">获得于 {{ time(medal.obtained_at) }}</p></div></article></div>
    </template>
    <footer v-if="!imageMode" class="ef-source"><details><summary>{{ stale ? '档案来源 · 待更新' : '档案来源' }}</summary><p>森空岛档案 · {{ stale ? '正在显示已有资料，等待更新' : '已采集资料' }} · 观测于 {{ time(report.observed_at) }} · 同步于 {{ time(fetchedAt || report.fetched_at) }}（北京时间）</p></details></footer>
  </div>
</template>

<style scoped>
.endfield-reports { --ef-cyan:#79c9d1; --accent:var(--game-endfield); --accent-soft:color-mix(in srgb,var(--game-endfield) 12%,var(--card-bg)); display:grid; gap:16px; min-width:0; }
:global([data-theme="light"]) .endfield-reports { --ef-cyan:#147c88; }
.ef-report { min-width:0; padding:20px; border:1px solid var(--border); border-radius:var(--radius-card); background:var(--card-bg); }
.ef-report>header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:16px; flex-wrap:wrap; }
.ef-report h2 { font-size:16px; line-height:24px; font-weight:500; }

.ef-state { padding:0 6px; border-radius:var(--radius-chip); background:var(--overlay-3); color:var(--text-body); font-size:12px; line-height:20px; }
.ef-identity { display:flex; gap:16px; align-items:center; margin-bottom:16px; flex-wrap:wrap; }
.ef-identity>.endfield-artwork { width:70px; height:70px; }
.ef-identity h3 { font-size:16px; line-height:24px; font-weight:500; overflow-wrap:anywhere; }
.ef-identity p { font-family:var(--font-mono); font-size:12px; color:var(--text-muted); margin-top:4px; }
.ef-identity dl { display:flex; gap:28px; margin:0 0 0 auto; }
.ef-identity dt { font-size:12px; color:var(--text-muted); }
.ef-identity dd { margin:4px 0 0; font-size:22px; line-height:28px; font-weight:600; font-variant-numeric:tabular-nums; }
.ef-columns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
.ef-ship-rooms { align-items:start; }
.ef-empty { color:var(--text-muted); padding:24px 0; line-height:1.7; }
.ef-empty.ef-report { padding:24px; }
.ef-note { font-size:13px; color:var(--text-muted); line-height:1.7; }
.ef-source { font-size:12px; color:var(--text-muted); line-height:1.7; }
.ef-todos { margin-bottom:16px; }
.ef-todos li,.ef-facts li { display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; padding:12px 0; border-bottom:1px solid var(--border); }
.ef-todos strong { color:var(--game-endfield); font-weight:500; }
.ef-shortcuts { display:flex; gap:12px; flex-wrap:wrap; }
.ef-shortcuts .ui-button { flex:1; justify-content:space-between; min-height:40px; padding:8px 14px; }
.ef-distribution { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }
.ef-distribution>span { font-size:12px; line-height:20px; padding:0 8px; border-radius:var(--radius-chip); background:var(--overlay-3); }
.ef-distribution b { margin-left:8px; color:var(--text); font-weight:500; }
.ef-filters { display:grid; grid-template-columns:minmax(150px,2fr) repeat(3,minmax(100px,1fr)); gap:12px; margin:16px 0; }
.ef-filters:last-child { margin-bottom:0; }
.ef-filters label { display:grid; gap:6px; font-size:12px; color:var(--text-muted); }
.ef-filters input,.ef-filters select { min-width:0; width:100%; min-height:36px; padding:7px 10px; background:var(--card-bg); color:var(--text); border:1px solid var(--border); border-radius:var(--radius-control); font-size:13px; }
.ef-roster { display:grid; grid-template-columns:repeat(auto-fill,minmax(185px,1fr)); gap:12px; }
.ef-operator { min-width:0; border-radius:var(--radius-well); background:var(--surface-soft); display:flex; flex-direction:column; overflow:hidden; }
.ef-portrait { height:134px; position:relative; display:grid; place-items:center; overflow:hidden; }
.ef-portrait>.endfield-artwork { width:100%; height:100%; border-radius:0; background:transparent; font-size:28px; }
.ef-portrait small { position:absolute; right:8px; top:8px; padding:0 6px; border-radius:var(--radius-chip); color:var(--game-endfield); background:var(--card-bg); font-size:12px; font-weight:500; line-height:20px; }
.ef-operator-copy { padding:12px 14px 0; flex:1; }
.ef-operator h3 { font-size:14px; line-height:1.5; font-weight:500; overflow-wrap:anywhere; }
.ef-operator p { font-size:13px; margin-top:6px; }
.ef-operator .ef-operator-level { font-size:14px; font-weight:500; font-variant-numeric:tabular-nums; }
.ef-operator-level span { color:var(--text-muted); font-size:12px; font-weight:400; margin-left:5px; }
.ef-operator button { margin:14px; justify-content:center; }
.ef-subsection { padding:16px; border-radius:var(--radius-well); background:var(--surface-soft); min-width:0; }
.ef-subsection h3 { font-size:14px; font-weight:500; margin-bottom:12px; }
.ef-subsection h3 small { font-size:12px; color:var(--text-muted); font-weight:400; margin-left:6px; }
.ef-subsection p { font-size:13px; line-height:1.7; overflow-wrap:anywhere; }
.ef-subsection p strong { font-weight:500; }
.ef-facts { font-size:13px; }
.ef-facts strong { font-weight:500; font-variant-numeric:tabular-nums; }
.ef-facts small { font-size:12px; color:var(--text-muted); }
.ef-subsection .ef-facts li { border-bottom-color:var(--border-strong); }
.ef-facts progress { flex-basis:100%; width:100%; height:4px; appearance:none; border:0; border-radius:999px; overflow:hidden; background:var(--track); accent-color:var(--ef-cyan); }
.ef-facts progress::-webkit-progress-bar { background:var(--track); border-radius:999px; }
.ef-facts progress::-webkit-progress-value { background:var(--ef-cyan); border-radius:999px; }
.ef-facts progress::-moz-progress-bar { background:var(--ef-cyan); border-radius:999px; }
.ef-detail { scroll-margin-top:80px; padding:0; border:0; background:transparent; }
.ef-detail:focus { outline:none; }
.ef-detail-toolbar { display:flex; justify-content:space-between; gap:10px; margin-bottom:16px; }
.ef-detail-time { font-size:12px; line-height:1.8; color:var(--text-muted); margin:-8px 0 24px; }
.ef-ship-intro,.ef-ship-room { padding:0; border:0; border-radius:0; background:transparent; }
.ef-ship-counts { display:flex; gap:38px; flex-wrap:wrap; margin:0 0 20px; }
.ef-ship-counts dt { font-size:12px; color:var(--text-muted); line-height:1.7; }
.ef-ship-counts dd { font-size:22px; line-height:28px; font-weight:600; font-variant-numeric:tabular-nums; margin:4px 0 0; }
.ef-ship-time { font-size:12px; }
.ef-ship-rooms { gap:30px 38px; }
.ef-ship-room { padding-top:20px; border-top:1px solid var(--border); }
.ef-ship-room>header { margin-bottom:0; }
.ef-ship-room h2 { font-size:14px; }
.ef-room-level { font-size:12px; color:var(--text-muted); font-variant-numeric:tabular-nums; }
.ef-room-level>span { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
.ef-settlements,.ef-areas { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr)); gap:12px; margin-top:16px; }
.ef-assigned { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
.ef-assigned>.endfield-artwork { width:42px; height:42px; font-size:18px; }
.ef-main-mission { display:flex; gap:16px; align-items:baseline; margin:0 0 16px; font-size:13px; line-height:1.8; }
.ef-main-mission>span { color:var(--text-muted); white-space:nowrap; }
.ef-main-mission>strong { font-weight:500; overflow-wrap:anywhere; }
.ef-model-note { margin-top:12px; font-size:12px; line-height:1.8; color:var(--text-muted); }
.ef-model-note summary { cursor:pointer; padding:6px 0; }
.ef-model-note p { margin:7px 0; }
.ef-medal-category { display:inline-block; padding:0 6px; border-radius:var(--radius-chip); background:var(--overlay-3); color:var(--text-body); font-size:12px; margin-top:8px; line-height:20px; overflow-wrap:anywhere; }
.ef-medal-filters { grid-template-columns:2fr 1fr 1fr; }
.ef-empty .ui-button { margin-top:14px; }
.ef-medals { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(310px,100%),1fr)); gap:16px; }
.ef-medal { display:flex; gap:16px; align-items:center; }
.ef-medal>.endfield-artwork { width:78px; height:88px; background:transparent; }
.ef-medal>div { min-width:0; }
.ef-medal h3 { font-size:14px; line-height:1.6; font-weight:500; overflow-wrap:anywhere; }
.ef-medal p { margin-top:6px; font-size:13px; }
.ef-medal-plated { color:var(--ef-cyan); margin-left:8px; }
.ef-source { display:flex; gap:5px 14px; flex-wrap:wrap; padding:12px 0 0; border-top:1px solid var(--border); }
.ef-source details { min-width:0; width:100%; }
.ef-source summary { cursor:pointer; padding:6px 0; }
.ef-source details p { padding:6px 0; overflow-wrap:anywhere; }
.ef-error { color:var(--danger); font-size:13px; padding:12px; border-radius:var(--radius-control); background:var(--danger-bg); margin-bottom:16px; }
.endfield-reports :deep(.summary-metrics.rows progress::-webkit-progress-value) { background:var(--ef-cyan); }
.endfield-reports :deep(.summary-metrics.rows progress::-moz-progress-bar) { background:var(--ef-cyan); }
@media(max-width:760px) {
  .ef-columns { grid-template-columns:1fr; }
  .ef-filters { grid-template-columns:1fr 1fr; }
  .ef-report { padding:16px; }
  .ef-detail,.ef-ship-intro { padding:0; }
  .ef-ship-room { padding:18px 0 0; }
  .ef-roster { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .ef-shortcuts { display:grid; grid-template-columns:1fr; }
  .ef-shortcuts .ui-button { width:100%; }
}
@media(max-width:550px) {
  .ef-report>header { margin-bottom:12px; }
  .ef-identity { gap:12px; }
  .ef-identity dl { width:100%; margin-left:0; padding-top:12px; gap:30px; }
  .ef-portrait { height:110px; }
  .ef-operator-copy { padding:12px 10px 0; }
  .ef-operator button { margin:12px 10px; min-height:40px; }
  .ef-ship-counts { gap:20px; }
  .ef-medal { gap:12px; }
  .ef-medal>.endfield-artwork { width:60px; height:70px; }
}
</style>
