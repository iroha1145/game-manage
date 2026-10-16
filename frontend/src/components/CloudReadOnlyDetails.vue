<script setup>
import { computed, ref, watch } from 'vue'
import { challengeEnvelope } from '../endfield-challenges.js'
import EndfieldChallenges from './EndfieldChallenges.vue'
import EndfieldLoadout from './EndfieldLoadout.vue'
import EndfieldAttendance from './EndfieldAttendance.vue'
import { poolLabel, pityLabel, ledgerDate, resultLabel, requirementLabel } from '../nte-gacha-api.js'
const props=defineProps({result:{type:Object,required:true},kind:{type:String,required:true},subtype:{type:String,default:''},busy:Boolean,error:String})
const emit=defineEmits(['reload','select-challenge-kind'])
const challengeValue=computed(()=>challengeEnvelope(props.result))
const object=value=>value && typeof value==='object' && !Array.isArray(value) ? value : {}
const data=computed(()=>{
  const result=props.result, payload=result.payload ?? result
  if(props.kind!=='operators')return payload
  // The live operator endpoint returns {operator, fetched_at, stale, error}.
  // An explicit null means no detail; never borrow fields from its envelope.
  if(Object.prototype.hasOwnProperty.call(result,'operator'))return object(result.operator)
  if(Object.prototype.hasOwnProperty.call(object(payload),'operator'))return object(payload.operator)
  return object(payload)
}), list=v=>Array.isArray(v)?v:[], show=v=>v==null||v===''?'未提供':typeof v==='object' ? v.name ?? v.value ?? v.key ?? '未提供' : String(v)
const named=v=>typeof v==='string'?v:v?.name || v?.title || '未提供'
const query=ref(''), page=ref(0)
const toolRows=computed(()=>{
  const payload=data.value
  if(Array.isArray(payload))return payload
  if(props.subtype==='materials') {
    const rows=['materials','charExpMaterials','weaponExpMaterials'].flatMap(key=>Object.values(payload?.[key] || {})).filter(row=>row && typeof row==='object')
    const seen=new Set(); return rows.filter(row=>!row.id || !seen.has(row.id) && seen.add(row.id))
  }
  return list(payload?.[{characters:'chars',weapons:'weapons',equipment:'equips',tactical:'tacticalItems'}[props.subtype]])
})
const filtered=computed(()=>toolRows.value.filter(row=>[row.name,row.id].some(v=>String(v??'').toLowerCase().includes(query.value.toLowerCase()))))
watch(()=>[props.result,props.kind,props.subtype,query.value],()=>{page.value=0})
</script>
<template>
  <div class="readonly-details">
    <EndfieldLoadout v-if="kind==='operators'" :operator="data" title-suffix=" · 干员配装" />
    <EndfieldChallenges v-else-if="kind==='challenges'" :value="challengeValue" :kind="subtype" :busy="busy" :error="error" @reload="emit('reload')" @select-kind="emit('select-challenge-kind',$event)" />
    <template v-else-if="kind==='tools'"><p v-if="result.supported===false">这类资料暂时无法读取。</p><label>筛选资料<input v-model="query" type="search" /></label><p v-if="!filtered.length">暂无匹配资料，请留意来源状态。</p><div class="readonly-grid"><article v-for="(item,i) in filtered.slice(page*20,(page+1)*20)" :key="item.id || i"><h3>{{ named(item) }}</h3><p>稀有度 {{ show(item.rarity) }} · {{ show(item.type || item.property) }}</p><p v-if="item.description || item.function">{{ item.description || item.function }}</p><p v-if="item.activeEffect">主动效果：{{ item.activeEffect }}</p><p v-if="item.passiveEffect">被动效果：{{ item.passiveEffect }}</p><p v-if="item.exp!=null">经验：{{ item.exp }}</p><p v-if="item.startLevel!=null || item.maxLevel!=null">适用等级：{{ show(item.startLevel) }}–{{ show(item.maxLevel) }}</p><ul><li v-for="(skill,j) in list(item.skills || item.properties)" :key="j">{{ show(skill) }}<span v-if="skill.desc"> · {{ skill.desc }}</span></li></ul></article></div><nav v-if="filtered.length>20" aria-label="资料分页"><button class="ui-button" :disabled="!page" @click="page--">上一页</button><span>{{ page*20+1 }}–{{ Math.min((page+1)*20,filtered.length) }} / {{ filtered.length }}</span><button class="ui-button" :disabled="(page+1)*20>=filtered.length" @click="page++">下一页</button></nav></template>
    <template v-else-if="kind==='blueprints'"><p>已保存 {{ list(data.blueprints || data.items).length }} 份蓝图</p><article v-for="(item,i) in list(data.blueprints || data.items)" :key="item.id || i"><h3>{{ named(item) }}</h3><code>{{ item.code || '分享码未提供' }}</code><p v-if="item.notes">{{ item.notes }}</p></article></template>
    <template v-else-if="kind==='summary'"><p>已保存 {{ show(data.total_records) }} 条逐抽记录，范围以导入文件为准。</p><div class="readonly-grid"><article v-for="item in list(data.pools)" :key="item.pool_id"><h3>{{ poolLabel(item.pool_id) }}</h3><p>当前垫抽：{{ pityLabel(item.pity) }} · 距所设 S 保底：{{ show(item.pity?.hard_pity_remaining) }}</p><p>计数抽取 {{ show(item.total_pulls) }}</p><p v-if="item.pity?.basis">{{ requirementLabel(item.pity.basis) }}</p><ul><li v-for="(note,i) in list(item.pity?.missing_requirements)" :key="i">{{ requirementLabel(note) }}</li></ul></article></div><p v-if="!list(data.pools).length">暂无已保存的卡池统计</p></template>
    <template v-else-if="kind==='records'"><p>共 {{ show(data.total) }} 条记录</p><div class="record-table"><table><thead><tr><th>时间（源文件）</th><th>卡池</th><th>物品</th><th>品质</th><th>数量</th><th>计数信息</th></tr></thead><tbody><tr v-for="(row,i) in list(data.records)" :key="row.uid || i"><td>{{ ledgerDate(row.timestamp) }}</td><td>{{ poolLabel(row.pool_group_id) }}</td><td>{{ row.reward_name || row.reward_id }}</td><td>{{ show(row.reward_rank) }}</td><td>{{ show(row.quantity) }}</td><td>{{ resultLabel(row.result_type) }}</td></tr></tbody></table></div><p v-if="!list(data.records).length">暂无逐抽记录</p></template>
    <template v-else-if="kind==='rules'"><article v-for="(rule,i) in list(data.rules)" :key="rule.pool_id || i"><h3>{{ poolLabel(rule.pool_id) }}</h3><p>用户设置保底：{{ show(rule.s_hard_pity) }} · {{ rule.note || '说明未提供' }}</p></article><p v-if="!list(data.rules).length">暂无已保存规则</p></template>
    <EndfieldAttendance v-else-if="kind==='attendance'" :value="result" :busy="busy" :error="error" @reload="emit('reload')" />
  </div>
</template>
<style scoped>.readonly-details{display:grid;gap:12px;min-width:0}.readonly-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}article,details{padding:12px;border-radius:var(--radius-well);background:var(--surface-soft);min-width:0}p{line-height:1.7;font-size:13px}h3,h4{font-size:14px;font-weight:500;margin:0 0 8px}code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font-family:var(--font-mono);font-size:13px}.record-table{overflow-x:auto}td,th{white-space:nowrap;padding:8px;text-align:left}td{font-size:13px}th{font-size:12px;font-weight:500;color:var(--text-muted)}nav{display:flex;gap:12px;align-items:center}input{max-width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius-control);background:var(--card-bg);color:var(--text)}@media(max-width:720px){.readonly-grid{grid-template-columns:1fr}}</style>
