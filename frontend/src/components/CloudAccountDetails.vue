<script setup>
import { ref, watch, onBeforeUnmount, computed } from 'vue'
import { getAccountDetail } from '../accounts-api.js'
import CloudDataTree from './CloudDataTree.vue'
import { cloudStateLabel } from '../cloud-display.js'
import CloudSklandProfile from './CloudSklandProfile.vue'
import CloudReadOnlyDetails from './CloudReadOnlyDetails.vue'
import { displayBeijing } from '../time.js'
const props = defineProps({ account: { type: Object, required: true }, role: { type: String, required: true }, snapshot: {type:Object,default:null} })
const kind = ref(props.account.provider === 'tajiduo' ? 'summary' : 'card'), itemId = ref(''), result = ref(null), error = ref(''), busy = ref(false), offset = ref(0)
const challengeKind = ref('war'), toolKind = ref('characters')
const challengeKinds = [['war','战争'],['monument','丰碑'],['crisis','危机']], toolKinds = [['characters','干员'],['weapons','武器'],['equipment','装备'],['tactical','战术物品'],['materials','养成材料']]
let generation = 0
const categories = { skland: [['card','档案与基地'],['attendance','签到记录（只读）'],['operators','干员配装'],['challenges','挑战记录'],['tools','官方工具'],['blueprints','蓝图收藏']], tajiduo: [['summary','逐抽账本汇总'],['records','逐抽记录'],['rules','已保存的规则']] }
const operators = computed(() => Array.isArray(props.snapshot?.payload?.operators) ? props.snapshot.payload.operators : [])
async function load(start = offset.value) {
  const version = ++generation, provider = props.account.provider
  result.value = null; error.value = ''; busy.value = true
  let path
  if (provider === 'skland') path = kind.value === 'blueprints' ? 'endfield/blueprints' : `endfield/skland/${kind.value}${kind.value === 'operators' ? '/' + encodeURIComponent(itemId.value) : kind.value === 'challenges' ? '?kind=' + challengeKind.value : kind.value === 'tools' ? '?kind=' + toolKind.value : ''}`
  else if (provider === 'tajiduo') path = `nte/gacha/${kind.value}${kind.value === 'records' ? `?limit=100&offset=${start}` : ''}`
  if (!path || kind.value === 'operators' && !itemId.value.trim()) { busy.value = false; error.value = '请输入干员标识'; return }
  try { const data = await getAccountDetail(props.account.account_id, props.role, path); if (version === generation) { result.value = data; offset.value = start } }
  catch (failure) { if (version === generation && failure.name !== 'AbortError') error.value = failure.message }
  finally { if (version === generation) busy.value = false }
}
watch(() => [props.account.account_id, props.role, kind.value, challengeKind.value, toolKind.value], () => { generation++; result.value = null; error.value = ''; busy.value = false; itemId.value = ''; offset.value = 0 }, {flush:'sync'})
watch(itemId, () => { generation++; result.value = null; error.value = ''; busy.value = false }, {flush:'sync'})
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <section v-if="categories[account.provider]" class="cap-card cloud-details"><h2>本人授权详情</h2>
    <div class="cloud-detail-controls"><label>数据类型<select v-model="kind"><option v-for="[key, label] in categories[account.provider]" :key="key" :value="key">{{ label }}</option></select></label><label v-if="kind === 'operators' && operators.length">选择干员<select v-model="itemId"><option value="">选择干员</option><option v-for="(operator,index) in operators" :key="operator.id" :value="operator.id">{{ operator.name || `干员 ${index+1}` }}</option></select></label><label v-else-if="kind === 'operators'">干员来源标识（尚无已同步目录）<input v-model="itemId" autocomplete="off" /></label><label v-if="kind === 'challenges'">挑战类型<select v-model="challengeKind"><option v-for="[value,label] in challengeKinds" :key="value" :value="value">{{ label }}</option></select></label><label v-if="kind === 'tools'">资料类别<select v-model="toolKind"><option v-for="[value,label] in toolKinds" :key="value" :value="value">{{ label }}</option></select></label><button class="ui-button" :disabled="busy" @click="load()">{{ busy ? '读取中…' : '读取详情' }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="!result && !busy && !error">选择类型后读取已保存的本人数据。</p>
    <template v-if="result"><p v-if="result.fetched_at">来源时间：{{ displayBeijing(result.fetched_at) }}（北京时间）</p><p v-if="result.state || result.error">{{ result.state ? cloudStateLabel(result.state) : '来源读取异常' }} {{ typeof result.error === 'string' ? result.error : '' }}</p><CloudSklandProfile v-if="account.provider === 'skland' && kind === 'card'" :payload="result.payload || {}" :fetched-at="result.fetched_at || ''" /><template v-else><CloudReadOnlyDetails :result="result" :kind="kind" :subtype="kind === 'tools' ? toolKind : challengeKind" /><details><summary>查看详情与来源字段</summary><CloudDataTree :value="result.payload ?? result" /></details></template><nav v-if="kind === 'records'" aria-label="逐抽记录分页"><button class="ui-button" :disabled="busy || !offset" @click="load(Math.max(0, offset - 100))">上一页</button><span>第 {{ Math.floor(offset / 100) + 1 }} 页</span><button class="ui-button" :disabled="busy || offset + 100 >= (result.total ?? 0)" @click="load(offset + 100)">下一页</button></nav></template>
  </section>
</template>
<style scoped>
.cloud-details{display:grid;gap:14px}.cloud-detail-controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.cloud-detail-controls label{display:grid;gap:6px}input,select{max-width:100%;padding:10px;background:var(--card-bg);color:var(--text);border:1px solid var(--border);border-radius:8px}h2,p{margin:0}
</style>
