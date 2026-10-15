<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { profileReport, rows, displayValue as display, sourceName as named, selectOperators, operatorArtwork } from '../endfield-reports.js'
import { formatTime } from '../dashboard.js'
import SummaryMetrics from './SummaryMetrics.vue'
import EndfieldArtwork from './EndfieldArtwork.vue'
const props = defineProps({ payload: Object, view: { type: String, default: 'overview' }, fetchedAt: String, stale: Boolean,
  operatorDetail: Object, operatorDetailId: String, operatorBusy: Boolean, operatorError: String, operatorStale: Boolean })
const emit = defineEmits(['inspect', 'navigate'])
const report = computed(() => profileReport(props.payload))
const overview = computed(() => report.value.overview || {})
const training = computed(() => report.value.training || {})
const regions = computed(() => rows(report.value.regions?.items))
const rooms = computed(() => rows(report.value.ship?.rooms))
const search = ref(''), rarity = ref(''), profession = ref(''), sort = ref('level')
const operators = computed(() => rows(training.value.items))
const selected = computed(() => selectOperators(operators.value, { search: search.value, rarity: rarity.value, profession: profession.value, sort: sort.value }))
const rarities = computed(() => [...new Set(operators.value.map(item => item.rarity).filter(value => value != null))].sort((a,b) => b-a))
const professions = computed(() => [...new Set(operators.value.map(item => named(item.profession)).filter(value => value !== '未知'))])
const failedImages = ref(new Set())
const detailPanel = ref(null)
watch(() => props.operatorDetailId, async id => { if (id) { await nextTick(); detailPanel.value?.scrollIntoView?.({ block: 'start' }) } })
watch(() => props.payload, () => { failedImages.value = new Set() })
const portrait = item => failedImages.value.has(item.id) ? null : operatorArtwork(item)
function imageFailed(id) { failedImages.value = new Set([...failedImages.value, id]) }
const time = value => value == null || value === '' ? '未知' : formatTime(value)
const pair = value => `${display(value?.current ?? value?.count)} / ${display(value?.total ?? value?.maximum)}`
const overviewMetrics = computed(() => [
  { label: '理智', current: overview.value.stamina?.current, total: overview.value.stamina?.maximum, note: `预计回满 ${time(overview.value.stamina?.expected_full_at)}` },
  { label: '已记录干员', value: training.value.summary?.listed_count, icon: 'user' },
  { label: '建设地区', value: report.value.regions?.summary?.region_count, icon: 'grid' },
  { label: '帝江号房间', value: report.value.ship?.summary?.room_count, icon: 'grid' },
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
  return [['puzzles','谜质'],['chests','储藏箱'],['equipment_chests','装备箱'],['pieces','维修点'],['blackboxes','黑匣子']]
    .map(([key,label]) => ({ key, label, current: area[key]?.count, total: area[key]?.total }))
}
const detail = computed(() => props.operatorDetail)
</script>

<template>
  <div class="endfield-reports">
    <template v-if="view === 'overview'">
      <section class="ef-report ef-hero"><header><div><p class="ef-kicker">01 / DAILY REPORT</p><h2>今日档案</h2></div><span v-if="stale" class="badge badge-stale">待更新</span></header>
        <p class="ef-identity">{{ overview.base?.name || '未知昵称' }} <span>等级 {{ display(overview.base?.level) }}</span></p>
        <SummaryMetrics :metrics="overviewMetrics" />
      </section>
      <div class="ef-columns">
        <section class="ef-report"><header><div><p class="ef-kicker">02 / PROGRESS</p><h2>每日与通行证进度</h2></div></header><SummaryMetrics v-if="progressMetrics.length" rows :metrics="progressMetrics" /><p v-else class="ef-empty">尚未采集进度。</p></section>
        <section class="ef-report"><header><div><p class="ef-kicker">03 / TO DO</p><h2>已知待办</h2></div></header>
          <ul v-if="rows(overview.todos).length" class="ef-todos"><li v-for="(item,index) in overview.todos" :key="item.id || index"><span>{{ item.name }}</span><strong>还需 {{ display(item.remaining) }}</strong></li></ul>
          <p v-else class="ef-empty">{{ overview.todos == null || !knownTasks ? '尚未采集到可判断的每日或每周任务进度。' : '已采集的每日与每周任务没有已知未完成项。' }}</p>
          <p class="ef-note">待办仅依据这次档案中的明确进度；未提供的任务状态仍未知。</p>
        </section>
      </div>
      <div class="ef-shortcuts"><button v-for="[key,label] in [['operators','查看全员练度'],['regions','查看地区建设'],['ship','查看帝江号']]" :key="key" type="button" class="ui-button" @click="emit('navigate',key)">{{ label }} →</button></div>
    </template>

    <template v-else-if="view === 'operators' || view === 'detail'">
      <section v-if="view === 'operators'" class="ef-report"><header><div><p class="ef-kicker">01 / OPERATORS</p><h2>全员练度</h2></div><span class="ef-note">显示 {{ selected.length }} / {{ operators.length }} 名</span></header>
        <SummaryMetrics compact :metrics="trainingMetrics" />
        <div class="ef-distribution"><span v-for="(count,key) in training.summary?.rarity_counts" :key="`r${key}`">{{ key }}★ <b>{{ count }}</b></span><span v-for="(count,key) in training.summary?.phase_counts" :key="`p${key}`">精英阶段 {{ key }} <b>{{ count }}</b></span></div>
        <div class="ef-filters"><label>查找干员<input :value="search" @input="search = $event.target.value" type="search" placeholder="姓名或编号" /></label><label>稀有度<select v-model="rarity"><option value="">全部稀有度</option><option v-for="value in rarities" :key="value" :value="String(value)">{{ value }}★</option></select></label><label>职业<select v-model="profession"><option value="">全部职业</option><option v-for="value in professions" :key="value" :value="value">{{ value }}</option></select></label><label>排序<select v-model="sort"><option value="level">等级从高到低</option><option value="rarity">稀有度从高到低</option><option value="potential">潜能从高到低</option><option value="name">姓名</option></select></label></div>
        <p v-if="!selected.length" class="ef-empty">{{ operators.length ? '没有匹配的干员，可调整筛选。' : '尚无干员资料。' }}</p>
        <div v-else class="ef-roster"><article v-for="(operator,index) in selected" :key="operator.id || index" class="ef-operator">
          <div class="ef-portrait"><img v-if="portrait(operator)" :src="portrait(operator)" :alt="operator.name || '干员'" loading="lazy" referrerpolicy="no-referrer" @error="imageFailed(operator.id)" /><span v-else aria-hidden="true">{{ (operator.name || '干员').slice(0,1) }}</span><small>{{ display(operator.rarity) }}★</small></div>
          <h3>{{ display(operator.name) }}</h3><p>等级 {{ display(operator.level) }} · 潜能 {{ display(operator.potential) }}</p><p>精英阶段 {{ display(operator.evolve_phase ?? operator.phase) }}</p><p class="ef-note">{{ named(operator.profession) }} · {{ named(operator.property) }}</p>
          <button type="button" class="ui-button" :disabled="operatorBusy && operatorDetailId === String(operator.id) || !operator.id" :aria-expanded="operatorDetailId === String(operator.id)" @click="emit('inspect',operator.id)">查看配装</button>
        </article></div>
      </section>
      <section v-if="operatorDetailId" ref="detailPanel" class="ef-report ef-detail" aria-live="polite"><header><div><p class="ef-kicker">02 / OPERATOR DETAIL</p><h2>{{ detail?.name || operators.find(item => String(item.id) === operatorDetailId)?.name || '干员配装' }}</h2></div><span v-if="operatorStale" class="badge badge-stale">配装待更新</span></header>
        <p v-if="operatorBusy" class="ef-empty" role="status">正在读取干员配装…</p><p v-if="operatorError" class="ef-error" role="alert">{{ operatorError }}</p>
        <template v-if="detail"><div class="ef-detail-heading"><EndfieldArtwork class="ef-detail-portrait" role :operator-id="detail.char_id || detail.id" :src="detail.avatar_url" :name="detail.name || '干员'" /><SummaryMetrics compact :metrics="[{label:'等级',value:detail.level},{label:'潜能',value:detail.potential},{label:'精英阶段',value:detail.evolve_phase ?? detail.phase}]" /></div>
          <div class="ef-columns"><section class="ef-subsection"><h3>武器与基质</h3><div class="ef-media-line"><EndfieldArtwork :src="detail.weapon?.icon_url" :name="named(detail.weapon)" /><div><p><strong>{{ named(detail.weapon) }}</strong> · 等级 {{ display(detail.weapon?.level) }} · 精炼 {{ display(detail.weapon?.refine_level) }}</p><p>突破 {{ display(detail.weapon?.breakthrough_level) }}</p></div></div><div class="ef-media-line"><EndfieldArtwork :src="detail.weapon?.gem?.icon_url" :name="named(detail.weapon?.gem)" /><p>基质：{{ named(detail.weapon?.gem) }}</p></div><ul class="ef-facts"><li v-for="(term,index) in rows(detail.weapon?.gem?.terms)" :key="index"><span>{{ named(term) }}</span><strong>{{ display(term.cost) }}</strong></li></ul></section>
          <section class="ef-subsection"><h3>装备</h3><p v-if="!rows(detail.equipment).length" class="ef-note">尚未采集装备。</p><ul class="ef-equipment-list"><li v-for="(item,index) in rows(detail.equipment)" :key="item.id || index" class="ef-media-line"><EndfieldArtwork :src="item.icon_url" :name="named(item)" /><div><p class="ef-note">{{ item.slot_label || item.slot_name || item.slot || `装备位 ${index+1}` }}</p><strong>{{ named(item) }}（等级 {{ display(item.level) }}）</strong></div></li></ul></section></div>
          <section class="ef-subsection"><h3>技能</h3><p v-if="!rows(detail.skills).length" class="ef-note">尚未采集技能。</p><ul class="ef-skill-list"><li v-for="(skill,index) in rows(detail.skills)" :key="skill.id || index" class="ef-media-line"><EndfieldArtwork :src="skill.icon_url" :name="named(skill)" /><span>{{ named(skill) }}（等级 {{ display(skill.level) }}）<span v-if="skill.mastery != null"> · 专精 {{ display(skill.mastery) }}</span></span></li></ul></section>
        </template>
      </section>
    </template>

    <template v-else-if="view === 'regions'">
      <section class="ef-report"><header><div><p class="ef-kicker">01 / REGIONAL DEVELOPMENT</p><h2>地区建设</h2></div><span class="ef-note">{{ regions.length }} 个地区</span></header><p v-if="!regions.length" class="ef-empty">尚无地区建设资料。</p><p class="ef-note">调度券与收集进度分别展示；来源未提供上限时不计算比例。</p></section>
      <section v-for="(region,index) in regions" :key="region.id || index" class="ef-report"><header><div><p class="ef-kicker">REGION {{ String(index+1).padStart(2,'0') }}</p><h2>{{ named(region) }}</h2></div><span>等级 {{ display(region.level) }}</span></header>
        <SummaryMetrics :metrics="[{label:'地区调度券',current:region.money?.current ?? region.money?.count,total:region.money?.total},{label:'据点',value:region.settlements_available === false ? null : region.settlements_available === true || rows(region.settlements).length ? rows(region.settlements).length : null}]" />
        <div class="ef-settlements"><article v-for="(settlement,number) in rows(region.settlements)" :key="settlement.id || number" class="ef-subsection"><h3>{{ settlement.name || '据点' }} <small>等级 {{ display(settlement.level) }}</small></h3><p>基地调度券 {{ pair(settlement.coupon || {current:settlement.money,total:settlement.money_max}) }}</p><p>派驻干员：{{ rows(settlement.officers).map(item => item.name || item.id || '未知').join('、') || '未提供' }}</p></article></div>
        <div class="ef-areas"><article v-for="(area,number) in rows(region.areas || region.levels)" :key="area.id || number" class="ef-subsection"><h3>{{ area.name || '区域' }}</h3><ul class="ef-facts"><li v-for="item in collections(area)" :key="item.key"><span>{{ item.label }}</span><strong>{{ pair(item) }}<small v-if="item.remaining != null"> · 剩余 {{ item.remaining }}</small></strong><progress v-if="Number.isFinite(item.percent)" :value="item.percent" max="100" :aria-label="`${area.name || '区域'}${item.label}`" /></li></ul></article></div>
      </section>
    </template>

    <template v-else-if="view === 'ship'">
      <section class="ef-report"><header><div><p class="ef-kicker">01 / DIJIANG</p><h2>帝江号</h2></div></header><SummaryMetrics compact :metrics="[{label:'房间数',value:report.ship?.summary?.room_count},{label:'有驻守记录的房间',value:report.ship?.summary?.staffed_rooms},{label:'驻守席位记录',value:report.ship?.summary?.operator_slots}]" /><p class="ef-note">心情、信赖展示来源观测值；未换算百分比，也不预测当前状态。</p></section>
      <p v-if="!rooms.length" class="ef-empty ef-report">尚无帝江号资料。</p>
      <div class="ef-columns"><section v-for="(room,index) in rooms" :key="room.id || index" class="ef-report"><header><div><p class="ef-kicker">ROOM {{ String(index+1).padStart(2,'0') }}</p><h2>{{ room.name || '舱室' }}</h2></div><span>等级 {{ display(room.level) }}</span></header><p v-if="!rows(room.operators).length" class="ef-empty">{{ room.operators_available === true ? '当前没有驻守干员记录。' : '尚未采集驻守干员资料。' }}</p><div v-for="(operator,number) in rows(room.operators)" :key="operator.id || number" class="ef-resident"><h3>{{ operator.name || operator.id || operator.charId || '驻守干员' }}</h3><dl><div><dt>心情观测值</dt><dd>{{ display(operator.mood_raw ?? operator.physicalStrength) }}</dd></div><div><dt>信赖观测值</dt><dd>{{ display(operator.trust_raw ?? operator.favorability) }}</dd></div></dl></div></section></div>
    </template>
    <footer class="ef-source">森空岛档案 · {{ stale ? '正在显示已有资料，等待更新' : '已采集资料' }}<span>观测于 {{ time(report.observed_at) }}</span><span>同步于 {{ time(fetchedAt || report.fetched_at) }}（北京时间）</span></footer>
  </div>
</template>

<style scoped>
.endfield-reports{display:grid;gap:18px;min-width:0}.ef-report{position:relative;padding:22px;border:1px solid var(--border);border-radius:10px;background:var(--card-bg);min-width:0}.ef-report:before{content:'';position:absolute;left:-1px;top:-1px;width:19px;height:19px;border-left:2px solid var(--game-endfield);border-top:2px solid var(--game-endfield);border-radius:10px 0 0}.ef-report>header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}.ef-report h2{font-size:19px;line-height:1.4}.ef-kicker{font-family:var(--font-mono);font-size:10px;letter-spacing:.1em;color:var(--text-muted);margin-bottom:5px}.ef-identity{font-size:24px;font-weight:600}.ef-identity span{font-size:13px;color:var(--text-muted);font-weight:400;margin-left:8px}.ef-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.ef-empty{color:var(--text-muted);padding:20px 0}.ef-note,.ef-source{font-size:12px;color:var(--text-muted);line-height:1.7}.ef-todos li,.ef-facts li{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:11px 0;border-bottom:1px solid var(--border)}.ef-todos{margin-bottom:15px}.ef-todos strong{color:var(--game-endfield)}.ef-shortcuts{display:flex;gap:10px;flex-wrap:wrap}.ef-distribution{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.ef-distribution>span{font-size:12px;padding:5px 9px;border:1px solid var(--border);border-radius:5px}.ef-distribution b{margin-left:8px;color:var(--game-endfield)}.ef-filters{display:grid;grid-template-columns:minmax(150px,2fr) repeat(3,minmax(100px,1fr));gap:12px;margin:18px 0}.ef-filters label{display:grid;gap:5px;font-size:11px;color:var(--text-muted)}.ef-filters input,.ef-filters select{min-width:0;width:100%;padding:9px 10px;background:var(--panel-bg);color:var(--text);border:1px solid var(--border);border-radius:6px}.ef-roster{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:12px}.ef-operator{min-width:0;padding:12px;background:var(--panel-bg);border:1px solid var(--border);border-radius:8px}.ef-portrait{height:132px;position:relative;display:grid;place-items:center;background:linear-gradient(150deg,var(--accent-soft),var(--card-bg));border-radius:6px;overflow:hidden;margin-bottom:12px}.ef-portrait img{width:100%;height:100%;object-fit:contain}.ef-portrait>span{font-size:46px;color:var(--game-endfield);opacity:.7}.ef-portrait small{position:absolute;right:8px;top:8px;padding:2px 6px;background:var(--card-bg);color:var(--game-endfield);border-radius:3px}.ef-operator h3{font-size:16px;overflow-wrap:anywhere}.ef-operator p{font-size:12px;margin-top:5px}.ef-operator button{width:100%;margin-top:14px}.ef-subsection{padding:16px;background:var(--panel-bg);border:1px solid var(--border);border-radius:7px;min-width:0}.ef-subsection h3{font-size:15px;margin-bottom:10px}.ef-subsection h3 small{font-size:11px;color:var(--text-muted);font-weight:400}.ef-subsection p{font-size:13px;line-height:1.8;overflow-wrap:anywhere}.ef-facts{font-size:12px}.ef-facts strong{font-weight:500}.ef-facts small{font-size:11px;color:var(--text-muted)}.ef-facts progress{flex-basis:100%;width:100%;height:4px;accent-color:var(--game-endfield)}.ef-detail>.ef-subsection{margin-top:16px}.ef-skill-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;font-size:13px}.ef-settlements,.ef-areas{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:12px;margin-top:16px}.ef-resident{padding:15px 0;border-top:1px solid var(--border)}.ef-resident h3{font-size:15px;margin-bottom:10px}.ef-resident dl{display:grid;grid-template-columns:1fr 1fr;gap:15px}.ef-resident dt{font-size:11px;color:var(--text-muted)}.ef-resident dd{margin:5px 0 0;font-size:20px;font-variant-numeric:tabular-nums}.ef-source{display:flex;gap:5px 14px;flex-wrap:wrap}.ef-error{color:var(--danger);font-size:13px}@media(max-width:760px){.ef-columns{grid-template-columns:1fr}.ef-filters{grid-template-columns:1fr 1fr}.ef-report{padding:16px}.ef-roster{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
.ef-detail-heading{display:flex;align-items:center;gap:18px;margin-bottom:20px}.ef-detail-heading>.summary-metrics{flex:1;margin:0}.ef-detail-portrait{width:116px;height:148px;font-size:48px}.ef-media-line{display:flex;gap:12px;align-items:center;margin:12px 0;min-width:0}.ef-media-line>div,.ef-media-line>span{min-width:0;overflow-wrap:anywhere}.ef-equipment-list strong{font-size:13px;font-weight:500}@media(max-width:550px){.ef-detail-heading{align-items:flex-start;flex-direction:column}.ef-detail-heading>.summary-metrics{width:100%}.ef-detail-portrait{width:86px;height:100px}}
</style>
