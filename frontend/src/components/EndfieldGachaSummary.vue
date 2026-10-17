<script setup>
import { computed } from 'vue'
import { displayBeijing } from '../time.js'
import { vReveal } from '../motion.js'
import DonutChart from './DonutChart.vue'
const props = defineProps({ view: {type:Object,required:true}, refreshing:Boolean })
const emit = defineEmits(['details','refresh'])
const summary = computed(()=>props.view.snapshot?.payload?.schema_version === 1 ? props.view.snapshot.payload : null)
const report = computed(()=>summary.value?.report?.schema_version === 1 ? summary.value.report : null)
const show = value => value == null || value === '' ? '未知' : value
const total = computed(()=>report.value?.total ?? summary.value?.total)
const tiles = computed(()=>[
  {label:'6★ 记录',value:report.value?.six_star,tone:'six'},{label:'5★ 记录',value:report.value?.five_star,tone:'five'},{label:'免费寻访',value:report.value?.free,tone:''},
])
// The ring shows 6★, 5★ and the rest of the record; it needs all three counts, since a partial split would read as the whole.
const segments = computed(()=>{
  const [all, six, five] = [total.value, report.value?.six_star, report.value?.five_star]
  if (![all, six, five].every(Number.isFinite) || six + five > all) return null
  return [{label:'6★',value:six,color:'var(--es-six)'},{label:'5★',value:five,color:'var(--es-five)'},{label:'其余',value:all - six - five,color:'var(--es-rest)'}]
})
</script>
<template>
  <section v-reveal class="ef-gacha-summary" aria-label="鹰角通行证寻访摘要">
    <header><div><h2>寻访摘要</h2></div><span v-if="view.snapshot?.stale" class="badge badge-stale">已有记录待更新</span></header>
    <div class="passport-identity"><strong>鹰角通行证 · {{ view.account?.nickname || '尚未读取' }}</strong><span v-if="view.account">角色编号 {{ view.account.role_id }}</span></div>
    <template v-if="summary">
      <div class="gs-body">
        <DonutChart v-if="segments" class="gs-donut" :segments="segments" label="已记录寻访的稀有度占比" :size="132" :stroke="16"><span class="gs-center"><span class="k">已记录寻访</span><strong>{{ show(total) }}</strong></span></DonutChart>
        <div v-else class="gs-center plain"><span class="k">已记录寻访</span><strong>{{ show(total) }}</strong></div>
        <ul class="gs-tiles">
          <li v-for="tile in tiles" :key="tile.label" :class="tile.tone"><span class="k">{{ tile.label }}</span><strong>{{ show(tile.value) }}</strong></li>
        </ul>
      </div>
      <div class="coverage"><span>同步于 {{ view.snapshot.fetched_at ? displayBeijing(view.snapshot.fetched_at) : '未知' }}（北京时间）</span><span>{{ report?.pending === true ? '部分待同步' : report?.pending === false ? '本轮同步完成' : '记录完整性未知' }}</span></div>
      <p v-if="report?.average_exact_pulls != null">已展示历史内 {{ report.known_exact_intervals ?? '未知' }} 个准确 6★ 区间均值 {{ report.average_exact_pulls }} 抽。</p>
    </template>
    <div v-else class="gs-empty"><span class="gs-ghost" aria-hidden="true"></span><p>{{ view.message || '尚未同步寻访记录，请刷新数据。' }}</p></div>
    <footer><button type="button" class="ui-button primary" @click="emit('details')">查看寻访详情 →</button><button type="button" class="ui-button" :disabled="refreshing" @click="emit('refresh')">{{ refreshing ? '同步中…' : '刷新寻访数据' }}</button></footer>
  </section>
</template>
<style scoped>
/* The one tinted card of the overview (like the main overview's pulls card): the game tone at half strength. */
.ef-gacha-summary{--es-six:var(--game-vivid,var(--game-endfield-vivid));--es-tone:var(--game-tone,var(--game-endfield-tone));--es-five:var(--chart-2);--es-rest:color-mix(in srgb,var(--text-faint) 34%,var(--card-bg));min-width:0;display:flex;flex-direction:column;gap:14px;padding:20px;border:1px solid var(--card-border);border-radius:var(--radius-card);background:color-mix(in srgb,var(--es-tone) 55%,var(--card-bg));box-shadow:var(--card-shadow)}
.ef-gacha-summary header{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.ef-gacha-summary h2{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.02em}
.passport-identity{display:flex;gap:4px 14px;flex-wrap:wrap;align-items:baseline;overflow-wrap:anywhere;margin-top:-6px}
.passport-identity strong{font-size:14px;font-weight:500;color:var(--text)}
.passport-identity span,.coverage,p{font-size:13px;line-height:1.7;color:var(--text-muted)}
.k{color:var(--text-muted);font-size:12px;line-height:18px;font-weight:500}
.gs-body{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:14px 24px}
.gs-donut{flex-wrap:nowrap}
.gs-donut :deep(.donut-legend){display:none}
.gs-center{display:grid;justify-items:center;gap:1px;line-height:1.1}
.gs-center strong{font-size:30px;line-height:34px;font-weight:550;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.gs-center.plain{justify-items:start;padding:8px 0}
.gs-center.plain strong{font-size:44px;line-height:48px;letter-spacing:-.05em}
.gs-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:8px}
.gs-tiles li{display:grid;gap:2px;padding:12px 14px;border-radius:var(--radius-well);background:var(--card-bg);min-width:0}
.gs-tiles .k{display:inline-flex;align-items:center;gap:6px}
.gs-tiles .six .k::before,.gs-tiles .five .k::before{content:'';width:8px;height:8px;border-radius:3px;background:var(--es-six)}
.gs-tiles .five .k::before{background:var(--es-five)}
.gs-tiles strong{font-size:26px;line-height:32px;font-weight:550;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.coverage{display:flex;gap:4px 20px;flex-wrap:wrap}
.gs-empty{display:flex;align-items:center;gap:18px;padding:6px 0}
.gs-ghost{flex:0 0 auto;width:72px;height:72px;border:10px solid var(--track);border-radius:50%}
.ef-gacha-summary footer{display:flex;gap:10px;flex-wrap:wrap;margin-top:auto;padding-top:2px}
@media(max-width:600px){.ef-gacha-summary{padding:16px;border-radius:22px}.passport-identity{align-items:start;flex-direction:column;gap:2px}.gs-body{grid-template-columns:1fr;justify-items:center}.gs-tiles{width:100%}.ef-gacha-summary footer .ui-button{flex:1}}
</style>
