<script setup>
import { computed } from 'vue'
import { challengeReport, CHALLENGE_KINDS } from '../endfield-challenges.js'
import { displayValue as display, rows } from '../endfield-reports.js'
import { displayBeijing } from '../time.js'
import { vReveal } from '../motion.js'
import BarChart from './BarChart.vue'
import HRail from './HRail.vue'
import SummaryMetrics from './SummaryMetrics.vue'
import EndfieldChallengeGroups from './EndfieldChallengeGroups.vue'
const props = defineProps({ value: Object, imageMode:Boolean, kind: { type: String, default: 'war' }, busy: Boolean, error: String })
const emit = defineEmits(['select-kind', 'reload'])
const report = computed(() => challengeReport(props.value, props.kind))
const label = computed(() => CHALLENGE_KINDS.find(([id]) => id === props.kind)?.[1] || '挑战')
const errorText = computed(() => props.error || (typeof props.value?.error === 'string' ? props.value.error : ''))
const time = value => typeof value !== 'string' || !value ? '未知' : displayBeijing(value)
const pass = value => value === true ? '已通关' : value === false ? '未通关' : '状态未知'
const metrics = computed(() => [{label:'已记录',value:report.value.summary?.listed_count}, ...(props.kind === 'crisis' ? [{label:'历史最高值',value:report.value.summary?.highest},{label:'挑战次数',value:report.value.summary?.challenge_count}] : [])])
const known = value => typeof value === 'number' && Number.isFinite(value)
// Charts only where the report carries numbers to compare: stars per season (war) or the result of each round (crisis).
const seasonBars = computed(() => {
  const items = props.kind === 'war' ? report.value.records.map((record, index) => ({ label: record.name || `赛季 ${index + 1}`, value: record.stars }))
    : props.kind === 'crisis' ? report.value.records.map((record, index) => ({ label: record.name || `第 ${index + 1} 轮`, value: record.result })) : []
  return items.filter(item => known(item.value)).length >= 3 ? items : null
})
const weekBars = record => {
  const items = rows(record.weeks).map((week, index) => ({ label: week.name || `轮换 ${index + 1}`, value: week.stars }))
  return items.filter(item => known(item.value)).length >= 2 ? items : null
}
</script>
<template>
  <div class="endfield-challenges" :class="{ 'is-image': imageMode }">
    <section v-reveal class="challenge-report ch-top"><header class="report-heading"><div><h2>{{ imageMode ? label + ' · 挑战记录' : '挑战记录' }}</h2></div><button v-if="!imageMode" type="button" class="ui-button" :disabled="busy" @click="emit('reload')">{{ busy ? '读取中…' : `重新读取${label}` }}</button></header>
      <div class="ch-top-body">
        <div class="ch-top-left">
          <nav v-if="!imageMode" class="challenge-tabs segmented" aria-label="挑战类型"><button v-for="[id,name] in CHALLENGE_KINDS" :key="id" type="button" :aria-pressed="kind===id" :class="{ active: kind===id }" @click="emit('select-kind',id)">{{ name }}</button></nav>
          <details v-if="!imageMode" class="challenge-status"><summary>来源与更新时间</summary><span>{{ label }}抓取于 {{ time(report.fetched_at) }}（北京时间）</span><span v-if="report.stale && report.available" class="badge badge-stale">已有资料待更新</span><p v-if="report.available" class="challenge-note coverage">仅展示本次接口返回的赛季与记录，不代表完整历史；没有来源上限时不计算完成率。</p></details>
          <p v-else class="challenge-status" role="status"><span>{{ label }}观测时间 {{ time(report.fetched_at) }}（北京时间）</span><span v-if="report.available && (report.stale || errorText)" class="badge badge-stale">已有资料待更新</span></p>
        </div>
        <div class="ch-top-right">
          <p v-if="report.supported === false" class="challenge-empty">当前账号暂不支持{{ label }}挑战。</p>
          <template v-else>
            <p v-if="busy" class="challenge-note" role="status">正在读取{{ label }}记录<template v-if="report.available">，保留当前资料</template>…</p>
            <p v-if="errorText && !imageMode" class="challenge-error" role="alert">{{ errorText }}<span>{{ report.available ? '正在显示上次成功资料，抓取时间保持不变。' : '尚无可显示的已采集资料。' }}</span></p>
            <SummaryMetrics v-if="report.available" compact :metrics="metrics" />
            <p v-else-if="!busy && (!errorText || imageMode)" class="challenge-empty">尚未采集{{ label }}记录<template v-if="!imageMode">，请重新读取</template>。</p>
            <figure v-if="seasonBars" class="ch-chart"><figcaption>{{ kind === 'war' ? '各期星数' : '各轮结果' }}</figcaption><BarChart :items="seasonBars" :label="kind === 'war' ? '各期赛季星数' : '各轮挑战结果'" :unit="kind === 'war' ? ' 星' : ''" :highlight="0" :height="96" color="var(--ch-vivid)" /></figure>
          </template>
        </div>
      </div>
    </section>
    <template v-if="report.available && report.supported !== false">
      <p v-if="!report.records.length" class="challenge-report challenge-empty"><template v-if="imageMode">尚无已记录的{{ label }}挑战。</template><template v-else>本次返回没有{{ label }}记录。</template></p>
      <details v-for="(record,index) in report.records" :key="record.id ?? index" v-reveal class="challenge-report challenge-record" :open="imageMode || index===0"><summary><div><h3>{{ record.name || (record.id != null ? `记录 ${record.id}` : `挑战记录 ${index+1}`) }}</h3></div><span v-if="kind==='war'" class="record-result" :class="{ latest: index===0 }">{{ display(record.stars) }} 星</span><span v-else-if="kind==='crisis'" class="record-result" :class="{ latest: index===0 }">{{ display(record.result) }}</span><span class="record-toggle" aria-hidden="true">⌄</span></summary><div class="record-body">
        <p v-if="record.start_at || record.end_at" class="challenge-note period">{{ time(record.start_at) }} — {{ time(record.end_at) }}</p>
        <template v-if="kind==='war'"><p v-if="!rows(record.weeks).length" class="challenge-note">尚无轮换明细。</p>
          <div class="challenge-weeks"><figure v-if="weekBars(record)" class="ch-chart week-chart"><figcaption>每周星数</figcaption><BarChart :items="weekBars(record)" label="每周星数" unit=" 星" :height="88" color="var(--ch-vivid)" /></figure><article v-for="(week,weekIndex) in rows(record.weeks)" :key="week.id ?? weekIndex" class="challenge-week"><header><div><h4>{{ week.name || `轮换 ${weekIndex+1}` }}</h4></div><span>{{ display(week.stars) }} 星</span></header><EndfieldChallengeGroups :groups="week.groups" /></article></div></template>
        <EndfieldChallengeGroups v-else-if="kind==='monument'" class="monument-groups" :groups="record.groups" />
        <p v-else class="crisis-result">通关状态 <strong>{{ pass(record.passed) }}</strong></p>
      </div></details>
      <section v-if="kind==='war' && rows(report.honors).length" v-reveal class="challenge-report ch-honors"><header class="report-heading"><div><h3>已有荣誉</h3></div><span class="challenge-note">{{ report.honors.length }} 条</span></header>
        <HRail label="已有荣誉"><ul class="challenge-honors" role="list"><li v-for="(honor,index) in report.honors" :key="index"><div><strong>{{ honor.name || '未命名荣誉' }}</strong><p>首次通关 {{ time(honor.first_pass_at) }}</p></div><span>{{ display(honor.stars) }} 星</span></li></ul></HRail></section>
    </template>
  </div>
</template>
<style scoped>
.endfield-challenges{--ch-vivid:var(--game-vivid,var(--game-endfield-vivid));--ch-tone:var(--game-tone,var(--game-endfield-tone));--ch-ink:var(--game-accent,var(--game-endfield));--accent:var(--ch-ink);--accent-soft:var(--ch-tone);--accent-hover:var(--ch-ink);--accent-strong:var(--ch-ink);display:grid;gap:16px;min-width:0}
.challenge-report{position:relative;border:1px solid var(--card-border);border-radius:var(--radius-card);background:var(--card-bg);box-shadow:var(--card-shadow);padding:20px;min-width:0}
.report-heading{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:14px}
.report-heading h2,.report-heading h3{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.02em}
.ch-top-body{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:6px 24px;align-items:start}
.ch-top-left{display:grid;gap:4px;justify-items:start;min-width:0}
.ch-top-right{min-width:0}
.challenge-tabs{margin-bottom:2px}
.challenge-status{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0 0;color:var(--text-muted);font-size:12px;line-height:1.7}
details.challenge-status{display:block}
details.challenge-status>summary{cursor:pointer;padding:2px 0}
details.challenge-status>span{display:inline-block;margin-top:6px;margin-right:10px}
.challenge-note{font-size:13px;color:var(--text-muted);line-height:1.7}
.coverage{margin-top:8px}
.challenge-empty{font-size:13px;color:var(--text-muted);line-height:1.7}
p.challenge-empty.challenge-report{padding:24px}
.challenge-error{padding:12px;border-radius:var(--radius-control);background:var(--danger-bg);color:var(--danger);font-size:13px;line-height:1.7;overflow-wrap:anywhere;margin-top:12px}
.challenge-error>span{display:block;color:var(--text-muted)}
.ch-top :deep(.summary-metrics){grid-template-columns:repeat(auto-fit,minmax(150px,220px));margin:0}
.ch-chart{margin:12px 0 0;padding:14px 16px 8px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.ch-chart figcaption{font-size:13px;font-weight:600;color:var(--text);margin-bottom:-8px}
.week-chart{margin:0;align-self:start}
.challenge-record{padding:0;overflow:hidden}
.challenge-record>summary{display:flex;gap:12px;align-items:center;padding:16px 20px;cursor:pointer;list-style:none}
.challenge-record>summary::-webkit-details-marker{display:none}
.challenge-record>summary>div{min-width:0;flex:1}
.challenge-record h3{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.02em;overflow-wrap:anywhere}
.record-result{padding:0 14px;border-radius:var(--radius-chip);background:var(--control-track);color:var(--text);font-size:18px;font-weight:550;line-height:34px;letter-spacing:-.02em;overflow-wrap:anywhere;max-width:45%;font-variant-numeric:tabular-nums}
/* The newest season or round takes the game tone. */
.record-result.latest{background:var(--ch-tone);color:var(--ch-ink)}
.record-toggle{font-size:18px;color:var(--text-muted);transform:rotate(-90deg);transition:transform var(--duration-spring-smooth,260ms) var(--ease-spring-smooth,ease)}
details[open]>.record-toggle,details[open]>summary>.record-toggle{transform:none}
.record-body{padding:0 20px 20px}
.period{margin-bottom:12px}
.challenge-weeks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:12px}
.challenge-week{padding:14px;border-radius:var(--radius-tile);background:var(--surface-soft);--group-bg:var(--card-bg);min-width:0}
.challenge-week>header{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}
.challenge-week h4{margin:0;font-size:14px;font-weight:600}
.challenge-week>header>span{color:var(--text);font-size:14px;font-weight:600;font-variant-numeric:tabular-nums}
.monument-groups{grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr))}
.ch-honors{overflow:hidden}
.ch-honors :deep(.h-rail){--rail-gap:12px;--rail-pad-block:6px;--rail-pad:2px}
.challenge-honors{display:contents;list-style:none;padding:0;margin:0}
.challenge-honors li{flex:0 0 auto;scroll-snap-align:start;display:grid;gap:8px;width:200px;padding:14px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.challenge-honors strong{font-size:14px;font-weight:600;overflow-wrap:anywhere}
.challenge-honors p{font-size:12px;color:var(--text-muted);margin-top:4px;line-height:1.6}
.challenge-honors li>span{justify-self:start;padding:0 12px;border-radius:var(--radius-chip);background:var(--ch-tone);color:var(--ch-ink);font-size:14px;font-weight:550;line-height:26px;font-variant-numeric:tabular-nums;white-space:nowrap}
.crisis-result{display:flex;justify-content:space-between;padding-top:4px;font-size:13px;color:var(--text-muted)}
.crisis-result strong{font-weight:500;color:var(--text)}
/* A bot image is one still frame: no shadows (they inflate the PNG). */
.is-image .challenge-report{box-shadow:none;border-color:var(--border)}
@media(max-width:900px){.ch-top-body{grid-template-columns:1fr}}
@media(max-width:600px){.challenge-report{padding:16px;border-radius:22px}.challenge-record{padding:0}.challenge-record>summary{padding:14px 16px}.record-body{padding:0 16px 16px}.challenge-honors li{width:176px}}
</style>
