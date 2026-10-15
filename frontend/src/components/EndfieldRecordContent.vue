<script setup>
import { computed } from 'vue'
import EndfieldOperatorLoadout from './EndfieldOperatorLoadout.vue'
import { formatTime } from '../dashboard.js'
const props=defineProps({snap:{default:null},capability:{type:String,default:'all'},fallbackName:{type:String,default:''},imageMode:Boolean})
const card=computed(()=>props.snap)
const cardPayload=computed(()=>props.snap?.payload || {})
const list=value=>Array.isArray(value)?value:[]
const display=value=>value==null || value===''?'未知':String(value)
const dateText=value=>value?formatTime(value):'未知'
const named=value=>typeof value==='string'?value:value?.name || value?.title || '未知'
const regionSummary=item=>`等级 ${display(item.level)} · ${Array.isArray(item.levels)?item.levels.length:'未知'} 个区域 · ${Array.isArray(item.settlements)?item.settlements.length:'未知'} 处据点`
const shipSummary=item=>`${item.name || '舱室'} · 等级 ${display(item.level)} · ${Array.isArray(item.operators)?item.operators.length:'未知'} 名干员`
const countPair=item=>`${display(item?.count)} / ${display(item?.total)}`
const groups={account:['overview','account','stamina'],progress:['overview','progress'],roles:['operators','roles'],exploration:['operators','exploration'],record:['operators','record']}
const show=cap=>props.capability==='all' || groups[cap].includes(props.capability)
</script>
<template><div class="endfield-record-content"><div v-if="show('account') || show('progress')" class="endfield-grid">
            <section v-if="show('account')" class="cap-card"><div class="cap-title">账号与理智<span v-if="card?.fetched_at" class="cap-meta">更新于 {{ dateText(card.fetched_at) }}</span></div><p class="identity">{{ cardPayload.base?.name || fallbackName || '未知昵称' }} · 等级 {{ display(cardPayload.base?.level) }}</p><dl class="fact-list"><div><dt>理智</dt><dd>{{ display(cardPayload.stamina?.current) }} / {{ display(cardPayload.stamina?.maximum) }}</dd></div><div><dt>预计回满</dt><dd>{{ dateText(cardPayload.stamina?.expected_full_at) }}</dd></div><div><dt>数据时间</dt><dd>{{ dateText(cardPayload.stamina?.updated_at) }}</dd></div></dl></section>
            <section v-if="show('progress')" class="cap-card"><div class="cap-title">每日与通行证进度</div><p v-if="!list(cardPayload.progress).length" class="empty">暂无进度数据</p><ul v-else class="plain-list"><li v-for="(item, i) in list(cardPayload.progress)" :key="i"><span>{{ named(item) }}</span><strong>{{ display(item.cur) }} / {{ display(item.total) }}</strong></li></ul></section>
          </div><section v-if="show('roles')" class="cap-card"><div class="cap-title">干员</div><p v-if="!list(cardPayload.operators).length" class="empty">暂无干员数据</p><div v-else class="operator-grid"><article v-for="(operator, i) in list(cardPayload.operators)" :key="operator.id || i" class="inner-card operator-item" :data-render-block="imageMode ? '' : undefined">
          <h3>{{ display(operator.name) }}<span class="muted">{{ display(operator.rarity) }}★</span></h3>
          <p>等级 {{ display(operator.level) }} · 潜能 {{ display(operator.potential) }}</p>
          <p v-if="operator.profession || operator.property">{{ display(operator.profession) }} · {{ display(operator.property) }}</p>
          <slot name="operator" :operator="operator">
            <EndfieldOperatorLoadout v-if="imageMode && (operator.weapon || operator.equipment || operator.skills)" :data="operator" />
          </slot>
        </article></div></section>
        <div v-if="show('exploration')" class="endfield-grid">
          <section class="cap-card"><div class="cap-title">地区探索与建设</div><p v-if="!list(cardPayload.regions).length" class="empty">暂无地区数据</p>
            <details v-for="(item, i) in list(cardPayload.regions)" :key="i" class="record-detail" open>
              <summary>{{ named(item) }}<span class="hint">{{ regionSummary(item) }}</span></summary>
              <p v-if="item.money?.count != null || item.money?.total != null" class="hint">调度券：{{ countPair(item.money) }}</p>
              <ul class="plain-list"><li v-for="settlement in list(item.settlements)" :key="settlement.id"><span>{{ settlement.name || settlement.id || '据点' }}</span><span>等级 {{ display(settlement.level) }} · 资金 {{ display(settlement.money) }} / {{ display(settlement.money_max) }}</span></li></ul>
              <div v-for="level in list(item.levels)" :key="level.id" class="inner-card"><h3>{{ level.name || level.id || '区域' }}</h3><p>谜质 {{ countPair(level.puzzles) }} · 储藏箱 {{ countPair(level.chests) }}</p><p>装备箱 {{ countPair(level.equipment_chests) }} · 维修点 {{ countPair(level.pieces) }} · 黑匣子 {{ countPair(level.blackboxes) }}</p></div>
              <p v-for="entry in list(item.collections)" :key="entry.level_id" class="hint">{{ entry.level_id || '区域收集' }}：谜质 {{ display(entry.puzzle_count) }} · 储藏箱 {{ display(entry.chest_count) }} · 维修点 {{ display(entry.piece_count) }} · 黑匣子 {{ display(entry.blackbox_count) }}</p>
            </details>
          </section>
          <section class="cap-card"><div class="cap-title">帝江号</div><p v-if="!list(cardPayload.ship).length" class="empty">暂无帝江号数据</p>
            <details v-for="(item, i) in list(cardPayload.ship)" :key="i" class="record-detail"><summary>{{ shipSummary(item) }}</summary><ul class="plain-list"><li v-for="(operator, index) in list(item.operators)" :key="index"><span>{{ operator.name || operator.charId || '驻守干员' }}</span><span>体力 {{ display(operator.physicalStrength) }} · 好感度 {{ display(operator.favorability) }}</span></li></ul><p v-if="!list(item.operators).length" class="hint">暂无驻守干员</p></details>
          </section>
        </div>
        <section v-if="show('record')" class="cap-card"><div class="cap-title">成就</div><p v-if="cardPayload.achievements?.count == null && !list(cardPayload.achievements?.medals).length" class="empty">暂无成就数据</p><ul v-else class="plain-list"><li><span>成就总数</span><strong>{{ display(cardPayload.achievements?.count) }}</strong></li><li><span>勋章</span><strong>{{ list(cardPayload.achievements?.medals).length }}</strong></li></ul></section></div></template>
<style scoped>
.operator-item:has(.operator-detail){grid-column:1/-1}.operator-detail{margin-top:8px;border-top:1px solid var(--border);padding-top:8px;display:grid;gap:5px}
.endfield-record-content{display:grid;gap:12px;min-width:0}.endfield-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.operator-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}.identity{font-size:14px;color:var(--text);margin:10px 0}.hint,.muted{font-size:12px;color:var(--text-muted);line-height:1.6}.fact-list{display:grid;gap:8px;margin-top:12px}.fact-list div,.plain-list li{display:flex;justify-content:space-between;gap:12px;align-items:start;padding:9px 0;border-bottom:1px solid var(--border)}.fact-list dt,.plain-list span{color:var(--text-muted);font-size:12px}.fact-list dd{margin:0;color:var(--text);font-weight:600;font-size:13px}.plain-list strong{font-size:13px;font-weight:600;color:var(--text);text-align:right}.inner-card{border:1px solid var(--border);border-radius:9px;background:var(--panel-bg);padding:12px;min-width:0}.inner-card h3{font-size:13px;color:var(--text);margin:0 0 6px}.inner-card p{font-size:12px;color:var(--text-muted);line-height:1.5;overflow-wrap:anywhere}.record-detail{margin-top:10px}.record-detail>summary{display:flex;justify-content:space-between;gap:12px;font-size:13px;cursor:pointer}.record-detail>summary strong{color:var(--text)}@media(max-width:720px){.endfield-grid,.operator-grid{grid-template-columns:1fr}}
</style>
