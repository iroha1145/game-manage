<script setup>
import { computed } from 'vue'
import { displayBeijing } from '../time.js'
import SummaryMetrics from './SummaryMetrics.vue'
const props = defineProps({ view: {type:Object,required:true}, refreshing:Boolean })
const emit = defineEmits(['details','refresh'])
const summary = computed(()=>props.view.snapshot?.payload?.schema_version === 1 ? props.view.snapshot.payload : null)
const report = computed(()=>summary.value?.report?.schema_version === 1 ? summary.value.report : null)
const metrics = computed(()=>[
  {label:'已记录寻访',value:report.value?.total ?? summary.value?.total},
  {label:'6★ 记录',value:report.value?.six_star},{label:'5★ 记录',value:report.value?.five_star},{label:'免费寻访',value:report.value?.free},
])
</script>
<template>
  <section class="ef-gacha-summary" aria-label="鹰角通行证寻访摘要">
    <header><div><p class="kicker">05 / PASSPORT · HEADHUNTING</p><h2>寻访摘要</h2></div><span v-if="view.snapshot?.stale" class="badge badge-stale">已有记录待更新</span></header>
    <div class="passport-identity"><strong>鹰角通行证 · {{ view.account?.nickname || '尚未读取' }}</strong><span v-if="view.account">角色编号 {{ view.account.role_id }}</span><span>与森空岛档案分别管理</span></div>
    <template v-if="summary"><SummaryMetrics compact :metrics="metrics" /><div class="coverage"><span>同步于 {{ view.snapshot.fetched_at ? displayBeijing(view.snapshot.fetched_at) : '未知' }}（北京时间）</span><span>{{ report?.pending === true ? '部分待同步' : report?.pending === false ? '本轮同步完成' : '记录完整性未知' }}</span></div><p v-if="report?.average_exact_pulls != null">已展示历史内 {{ report.known_exact_intervals ?? '未知' }} 个准确 6★ 区间均值 {{ report.average_exact_pulls }} 抽；不代表完整生涯或未来出货。</p><p>统计仅覆盖已保存的记录；各池范围和逐抽明细见寻访详情。</p></template>
    <p v-else>{{ view.message || '尚未同步寻访记录，请刷新数据。' }}</p>
    <footer><button type="button" class="ui-button" @click="emit('details')">查看寻访详情 →</button><button type="button" class="ui-button" :disabled="refreshing" @click="emit('refresh')">{{ refreshing ? '同步中…' : '刷新寻访数据' }}</button></footer>
  </section>
</template>
<style scoped>
.ef-gacha-summary{border:1px solid var(--border);border-top:2px solid var(--game-endfield);padding:22px;background:var(--card-bg);min-width:0;display:grid;gap:18px}.ef-gacha-summary header{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.kicker{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;color:var(--text-muted);margin-bottom:7px}.ef-gacha-summary h2{font-size:21px}.passport-identity{display:flex;gap:8px 18px;flex-wrap:wrap;align-items:center;border-block:1px solid var(--border);padding:12px 0;overflow-wrap:anywhere}.passport-identity strong{font-size:13px;font-weight:500}.passport-identity span,.coverage,p:not(.kicker){font-size:12px;line-height:1.8;color:var(--text-muted)}.coverage{display:flex;gap:8px 20px;flex-wrap:wrap}.ef-gacha-summary footer{display:flex;gap:10px;flex-wrap:wrap}.ui-button{border-radius:0;min-height:40px}.ef-gacha-summary :deep(.summary-metric),.ef-gacha-summary :deep(.metric-symbol){border-radius:0}@media(max-width:600px){.ef-gacha-summary{padding:16px}.ef-gacha-summary h2{font-size:19px}.passport-identity{align-items:start;flex-direction:column;gap:4px}.ef-gacha-summary footer .ui-button{flex:1}}
</style>
