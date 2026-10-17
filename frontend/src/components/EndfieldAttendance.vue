<script setup>
import { computed } from 'vue'
import { attendanceEnvelope, attendanceRows as rows, attendanceCount } from '../endfield-attendance.js'
import { displayBeijing } from '../time.js'
import { displayValue as display } from '../endfield-reports.js'
import { vReveal } from '../motion.js'
import EndfieldArtwork from './EndfieldArtwork.vue'
import RingGauge from './RingGauge.vue'
const props=defineProps({ value:Object, busy:Boolean, error:String, allowSign:Boolean })
const emit=defineEmits(['reload','sign'])
const data=computed(()=>attendanceEnvelope(props.value))
const errorText=computed(()=>props.error || (typeof data.value?.error === 'string' ? data.value.error : ''))
const stale=computed(()=>!!data.value && !!(data.value.stale || errorText.value))
const calendar=computed(()=>rows(data.value?.calendar)), count=computed(()=>attendanceCount(calendar.value))
const status=computed(()=>data.value?.status)
const observed=computed(()=>!!(data.value?.updated_at || data.value?.signed_at || calendar.value.length || rows(data.value?.awards).length || rows(data.value?.records).length || ['signed','unsigned'].includes(status.value)))
const statusText=computed(()=>stale.value && observed.value
  ? ({signed:'上次状态：已签',unsigned:'上次状态：待签',unknown:'上次状态：未知'}[status.value] || '上次状态：未知')
  : ({signed:'今日已签',unsigned:'今日待签',unknown:'状态未知'}[status.value] || '尚未读取'))
const time=value=>value ? displayBeijing(value) : '未知'
const name=value=>typeof value === 'string' ? value : value?.name || '名称未提供'
const day=value=>Number.isInteger(value) && value > 0 ? `第 ${value} 日` : '签到日序未知'
// Today is the day the status points at: the last signed day once signed, the first open day while unsigned.
const today=computed(()=>{
  if (stale.value) return -1
  if (status.value === 'signed') return calendar.value.findLastIndex(row=>row.done === true)
  if (status.value === 'unsigned') return calendar.value.findIndex(row=>row.done === false)
  return -1
})
const dayState=(row,index)=>({done:row.done === true,open:row.done === false,unknown:typeof row.done !== 'boolean',today:index === today.value})
const dayTitle=(row,index)=>`${day(row.day ?? index + 1)} · ${row.done === true ? '已签到' : row.done === false ? '未签到' : '状态未知'}`
</script>
<template>
  <section v-reveal class="ef-attendance" aria-label="每日签到">
    <header><div><h2>每日签到</h2></div><span v-if="stale" class="badge badge-stale">{{ observed ? '已有签到资料待更新' : '签到状态未取得' }}</span></header>
    <p v-if="busy" class="note" role="status">正在读取签到状态…</p>
    <p v-if="errorText" class="error" role="alert">{{ errorText }}</p>
    <p v-if="data?.supported === false" class="note">当前账号暂不支持签到。</p>
    <template v-else>
      <div class="attendance-main">
        <RingGauge v-if="count.total != null && calendar.length" class="att-ring" :value="count.known" :max="calendar.length" label="本期已签到天数" :size="96" :stroke="11" color="var(--ea-vivid)"><span class="att-ring-num"><b>{{ count.known }}</b><small>/ {{ calendar.length }}</small></span></RingGauge>
        <div class="attendance-summary"><strong>{{ statusText }}</strong><span v-if="count.total != null">本期已签 {{ count.total }} 天</span><span v-else-if="count.known">已知已签 {{ count.known }} 天 · 本期总数未知</span><span v-else>本期已签天数未知</span></div>
      </div>
      <p v-if="!observed && !busy" class="note">尚无可显示的签到资料，可刷新状态重试。</p>
      <p v-if="data?.today_award" class="note award-line"><EndfieldArtwork :src="data.today_award.icon_url" :name="name(data.today_award)" /><span>今日奖励：{{ name(data.today_award) }}<template v-if="data.today_award.count != null"> × {{ display(data.today_award.count) }}</template></span></p>
      <div v-else-if="rows(data?.awards).length" class="award-results"><h3>已返回签到奖励</h3><p v-for="(award,index) in rows(data.awards)" :key="award.id ?? index">{{ name(award) }}<template v-if="award.count != null"> × {{ display(award.count) }}</template></p></div>
      <p v-if="data?.signed_at" class="note">签到于 {{ time(data.signed_at) }}（北京时间）</p>
      <ol v-if="calendar.length" class="att-days" aria-hidden="true"><li v-for="(row,index) in calendar" :key="row.day ?? index" class="att-day" :class="dayState(row,index)" :title="dayTitle(row,index)">{{ row.day ?? index + 1 }}</li></ol>
      <details class="note"><summary>来源与更新时间</summary><p>状态观测于 {{ time(data?.updated_at) }}<template v-if="data?.fetched_at"> · 抓取于 {{ time(data.fetched_at) }}</template>（北京时间）</p></details>
      <p v-if="stale && observed" class="note">正在显示已有签到资料；当前状态请以重新读取结果为准。</p>
      <details v-if="calendar.length || rows(data?.records).length" class="attendance-records"><summary>查看签到日历与记录</summary>
        <ul v-if="calendar.length"><li v-for="(row,index) in calendar" :key="row.day ?? index"><strong>{{ day(row.day) }}</strong><span>{{ row.done === true ? '已签到' : row.done === false ? '未签到' : '状态未知' }}</span><span>{{ name(row) }}<template v-if="row.count != null"> × {{ display(row.count) }}</template></span><span v-if="row.signed_at">签到于 {{ time(row.signed_at) }}</span></li></ul>
        <div v-if="rows(data?.records).length" class="record-history"><h3>来源签到记录</h3><p v-for="(row,index) in rows(data.records)" :key="index">{{ time(row.signed_at) }} · {{ name(row) }}<template v-if="row.count != null"> × {{ display(row.count) }}</template></p></div>
      </details>
    </template>
    <footer><button type="button" class="ui-button" :disabled="busy" @click="emit('reload')">刷新签到状态</button><button v-if="allowSign && data?.supported !== false" type="button" class="ui-button" :class="{ primary: status === 'unsigned' }" :disabled="busy || status === 'signed'" @click="emit('sign')">手动签到</button><span v-if="!allowSign" class="note">只读签到状态</span></footer>
  </section>
</template>
<style scoped>
.ef-attendance{--ea-vivid:var(--game-vivid,var(--game-endfield-vivid));--ea-tone:var(--game-tone,var(--game-endfield-tone));--ea-ink:var(--game-accent,var(--game-endfield));min-width:0;display:grid;gap:12px;align-content:start;padding:20px;border:1px solid var(--card-border);border-radius:var(--radius-card);background:var(--card-bg);box-shadow:var(--card-shadow)}
header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
h2{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.02em}
h3{font-size:14px;font-weight:500;margin:0 0 8px}
.note,.error,.award-results p,.record-history p{font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.note{color:var(--text-muted)}
.error{color:var(--danger)}
.attendance-main{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.att-ring-num{display:grid;justify-items:center;line-height:1.05}
.att-ring-num b{font-size:24px;font-weight:550;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.att-ring-num small{font-size:12px;color:var(--text-muted);font-weight:500}
.attendance-summary{display:grid;gap:2px;min-width:0}
.attendance-summary strong{font-size:22px;line-height:28px;font-weight:600;letter-spacing:-.02em}
.attendance-summary span{font-size:13px;color:var(--text-muted)}
.award-line{display:flex;align-items:center;gap:10px;padding:8px 12px 8px 8px;border-radius:var(--radius-well);background:var(--surface-soft);color:var(--text)}
.award-line .endfield-artwork{width:34px;height:34px;border-radius:var(--radius-control)}
/* One cell per day of the period: signed days take the game tone, today is the one solid cell. */
.att-days{display:grid;grid-template-columns:repeat(auto-fill,minmax(30px,1fr));gap:6px;margin:2px 0;padding:0;list-style:none}
.att-day{display:grid;place-items:center;aspect-ratio:1;border-radius:var(--radius-chip);background:var(--surface-soft);color:var(--text-muted);font-size:12px;font-weight:500;font-variant-numeric:tabular-nums;line-height:1}
.att-day.done{background:var(--ea-tone);color:var(--ea-ink)}
.att-day.unknown{background:transparent;outline:1px dashed var(--border-strong);outline-offset:-1px}
.att-day.today,.att-day.done.today{background:var(--ea-ink);color:var(--accent-ink)}
.ef-attendance details.note{margin-top:2px}
.ef-attendance details summary{cursor:pointer;color:var(--text-muted);font-size:13px;padding:4px 0}
footer{justify-content:flex-start;margin-top:2px}
.attendance-records summary{cursor:pointer;font-size:13px;color:var(--text-muted);padding:5px 0}
.attendance-records li{display:flex;gap:8px 16px;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.attendance-records li strong{font-weight:500}
.attendance-records li span{color:var(--text-muted)}
.record-history{margin-top:14px}
@media(max-width:600px){.ef-attendance{padding:16px;border-radius:22px}footer .ui-button{flex:1}.attendance-records li{gap:5px 12px}.attendance-records li>span:nth-of-type(2){flex-basis:100%}}
</style>
