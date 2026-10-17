<script setup>
import MenuSelect from './MenuSelect.vue'
import { ref, watch, onBeforeUnmount } from 'vue'
import { getReminderRule, saveReminderRule, getReminderInbox } from '../reminders-api.js'
const props = defineProps({ account: { type: Object, required: true } })
const role = ref(''), rule = ref(null), messages = ref([]), error = ref(''), status = ref(''), busy = ref(false)
const thresholdOn = ref(false), cityOn = ref(false), threshold = ref(90), cityThreshold = ref(90)
let generation = 0, controller
const active = () => ['active','connected'].includes(props.account.state)
async function load() {
  const ticket = ++generation
  controller?.abort(); controller = new AbortController()
  rule.value = null; messages.value = []; error.value = ''; status.value = ''
  if (!role.value) return
  busy.value = true
  try {
    const data = await getReminderRule(props.account.account_id,role.value,controller.signal)
    if (ticket !== generation) return
    rule.value = data.rule
    thresholdOn.value = data.rule.threshold_percent != null; threshold.value = data.rule.threshold_percent ?? 90
    cityOn.value = data.rule.city_threshold_percent != null; cityThreshold.value = data.rule.city_threshold_percent ?? 90
    if (active()) {
      const inbox = await getReminderInbox(props.account.account_id,role.value,controller.signal)
      if (ticket === generation) messages.value = inbox.messages || []
    }
  } catch (failure) { if (ticket === generation && failure.name !== 'AbortError') error.value = failure.message }
  finally { if (ticket === generation) busy.value = false }
}
watch(() => [props.account.account_id,props.account.version,props.account.state], () => {
  role.value = props.account.roles?.find(r=>r.is_default)?.role_id || props.account.roles?.[0]?.role_id || ''
  load()
}, {immediate:true})
async function choose(value) { role.value = value; await load() }
async function save() {
  if (busy.value || !rule.value) return
  const ticket = generation, account = props.account.account_id, selected = role.value
  busy.value = true; error.value = ''; status.value = ''
  const body = {...rule.value, threshold_percent:thresholdOn.value ? threshold.value : null,
    city_threshold_percent:props.account.game === 'nte' && cityOn.value ? cityThreshold.value : null,
    quiet_start:rule.value.quiet_start || null, quiet_end:rule.value.quiet_end || null}
  try {
    await saveReminderRule(account,selected,body)
    if (ticket === generation) status.value = '提醒规则已保存；下次成功采集时评估。'
  } catch (failure) { if (ticket === generation) error.value = failure.message }
  finally { if (ticket === generation) busy.value = false }
}
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<template>
  <section class="reminder-settings" aria-label="本人角色提醒">
    <h4>站内提醒</h4><p>成功采集后写入本人站内收件箱；QQ 主动推送不实现。提醒不会广播到群。社区数据可能延迟，陈旧或未知数值不触发。</p>
    <label>提醒角色<MenuSelect class="reminder-role-menu" label="提醒角色" :model-value="role" :disabled="busy" :options="(account.roles || []).map((r,index) => ({value:r.role_id,label:r.display_name || `角色 ${index+1}`}))" @change="choose" /></label>
    <p v-if="!active()">授权已失效或撤销；后续提醒停止。可关闭现有规则。</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
    <form v-if="rule" @submit.prevent="save">
      <label><input v-model="rule.enabled" aria-label="启用本人角色提醒" type="checkbox" :disabled="!active() && !rule.enabled" />启用本人角色提醒（新规则默认关闭）</label>
      <label><input v-model="rule.notify_full" type="checkbox" />满体力提醒</label>
      <label><input v-model="thresholdOn" type="checkbox" />体力阈值提醒<input v-model.number="threshold" aria-label="体力阈值百分比" type="number" min="1" max="99" :disabled="!thresholdOn" />%</label>
      <label v-if="account.game === 'nte'"><input v-model="cityOn" type="checkbox" />都市活力阈值提醒<input v-model.number="cityThreshold" aria-label="都市活力阈值百分比" type="number" min="1" max="100" :disabled="!cityOn" />%</label>
      <label>每条规则冷却（秒）<input v-model.number="rule.cooldown_seconds" type="number" min="60" max="604800" required /></label>
      <label>每条规则每日成功上限<input v-model.number="rule.daily_cap" type="number" min="1" max="24" required /></label>
      <label>来源读取最大年龄（秒）<input v-model.number="rule.max_source_age_seconds" type="number" min="60" max="3600" required /></label>
      <label>静默开始<input v-model="rule.quiet_start" type="time" /></label><label>静默结束<input v-model="rule.quiet_end" type="time" /></label>
      <p>时区 Asia/Shanghai；静默区间可跨午夜。开始与结束须同时填写，留空表示无静默时段。</p>
      <button class="ui-button primary" :disabled="busy">保存提醒规则</button>
    </form>
    <button class="ui-button" :disabled="busy" @click="load">读取规则与站内消息</button>
    <div v-if="active()" aria-label="站内提醒收件箱"><p v-if="!messages.length">暂无站内提醒；查看消息不会触发采集或发送。</p><article v-for="message in messages" :key="message.id"><strong>{{ message.title }}</strong><p>{{ message.body }}</p><small>写入时间 {{ message.delivered_at }}</small></article></div>
  </section>
</template>
<style scoped>
.reminder-settings,form{display:grid;gap:10px}.reminder-settings>button,form>button{justify-self:start}.reminder-settings{padding-top:12px;border-top:1px solid var(--border)}h4,p{margin:0}h4{font-size:14px;font-weight:500}label{display:flex;align-items:center;flex-wrap:wrap;gap:8px}input{padding:7px 10px;background:var(--card-bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius-control)}.reminder-role-menu{max-width:100%;min-width:0}.reminder-role-menu :deep(.menu-select-trigger){min-height:36px}input[type=number]{width:100px}article{padding:10px;background:var(--surface-soft);border-radius:var(--radius-control)}article+article{margin-top:8px}article strong{font-weight:500}small{font-size:12px;color:var(--text-muted)}
</style>
