<script setup>
import { computed } from 'vue'
import { attendanceEnvelope, attendanceRows as rows, attendanceCount } from '../endfield-attendance.js'
import { displayBeijing } from '../time.js'
import { displayValue as display } from '../endfield-reports.js'
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
</script>
<template>
  <section class="ef-attendance" aria-label="每日签到">
    <header><div><p class="kicker">04 / ATTENDANCE</p><h2>每日签到</h2></div><span v-if="stale" class="badge badge-stale">{{ observed ? '已有签到资料待更新' : '签到状态未取得' }}</span></header>
    <p v-if="busy" class="note" role="status">正在读取签到状态…</p>
    <p v-if="errorText" class="error" role="alert">{{ errorText }}</p>
    <p v-if="data?.supported === false" class="note">当前账号暂不支持签到。</p>
    <template v-else>
      <div class="attendance-summary"><strong>{{ statusText }}</strong><span v-if="count.total != null">本期已签 {{ count.total }} 天</span><span v-else-if="count.known">已知已签 {{ count.known }} 天 · 本期总数未知</span><span v-else>本期已签天数未知</span></div>
      <p v-if="!observed && !busy" class="note">尚无可显示的签到资料，可刷新状态重试。</p>
      <p v-if="data?.today_award" class="note">今日奖励：{{ name(data.today_award) }}<template v-if="data.today_award.count != null"> × {{ display(data.today_award.count) }}</template></p>
      <div v-else-if="rows(data?.awards).length" class="award-results"><h3>已返回签到奖励</h3><p v-for="(award,index) in rows(data.awards)" :key="award.id ?? index">{{ name(award) }}<template v-if="award.count != null"> × {{ display(award.count) }}</template></p></div>
      <p v-if="data?.signed_at" class="note">签到于 {{ time(data.signed_at) }}（北京时间）</p>
      <details class="note"><summary>来源与更新时间</summary><p>状态观测于 {{ time(data?.updated_at) }}<template v-if="data?.fetched_at"> · 抓取于 {{ time(data.fetched_at) }}</template>（北京时间）</p></details>
      <p v-if="stale && observed" class="note">正在显示已有签到资料；当前状态请以重新读取结果为准。</p>
      <details v-if="calendar.length || rows(data?.records).length" class="attendance-records"><summary>查看签到日历与记录</summary>
        <ul v-if="calendar.length"><li v-for="(row,index) in calendar" :key="row.day ?? index"><strong>{{ day(row.day) }}</strong><span>{{ row.done === true ? '已签到' : row.done === false ? '未签到' : '状态未知' }}</span><span>{{ name(row) }}<template v-if="row.count != null"> × {{ display(row.count) }}</template></span><span v-if="row.signed_at">签到于 {{ time(row.signed_at) }}</span></li></ul>
        <div v-if="rows(data?.records).length" class="record-history"><h3>来源签到记录</h3><p v-for="(row,index) in rows(data.records)" :key="index">{{ time(row.signed_at) }} · {{ name(row) }}<template v-if="row.count != null"> × {{ display(row.count) }}</template></p></div>
      </details>
    </template>
    <footer><button type="button" class="ui-button" :disabled="busy" @click="emit('reload')">刷新签到状态</button><button v-if="allowSign && data?.supported !== false" type="button" class="ui-button" :disabled="busy || status === 'signed'" @click="emit('sign')">手动签到</button><span v-if="!allowSign" class="note">只读签到状态</span></footer>
  </section>
</template>
<style scoped>
.ef-attendance{--accent:var(--game-endfield);min-width:0;display:grid;gap:14px;padding:22px;border:1px solid var(--border);border-top:2px solid var(--game-endfield);background:var(--card-bg)}header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.kicker{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;color:var(--text-muted);margin-bottom:7px}h2{font-size:21px}h3{font-size:12px;font-weight:500;margin:0 0 8px}.note,.error,.award-results p,.record-history p{font-size:12px;line-height:1.8;overflow-wrap:anywhere}.note{color:var(--text-muted)}.error{color:var(--danger)}.attendance-summary{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}.attendance-summary strong{font-size:16px;font-weight:500}.attendance-summary span{font-size:12px;color:var(--text-muted)}footer{justify-content:flex-start;border-top:1px solid var(--border);padding-top:14px}.ui-button{min-height:40px;border-radius:0}.attendance-records{border-top:1px solid var(--border);padding-top:10px}.attendance-records summary{cursor:pointer;font-size:12px;color:var(--text-muted);padding:5px 0}.attendance-records li{display:flex;gap:8px 16px;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px;line-height:1.7;overflow-wrap:anywhere}.attendance-records li strong{font-weight:500}.attendance-records li span{color:var(--text-muted)}.record-history{margin-top:14px}@media(max-width:600px){.ef-attendance{padding:16px}h2{font-size:19px}footer .ui-button{flex:1}.attendance-records li{gap:5px 12px}.attendance-records li>span:nth-of-type(2){flex-basis:100%}}
</style>
