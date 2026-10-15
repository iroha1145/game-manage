<script setup>
import { shipPercent } from '../endfield-ship.js'
import { displayValue as display } from '../endfield-reports.js'
import EndfieldArtwork from './EndfieldArtwork.vue'
defineProps({ operator: {type:Object,required:true} })
</script>
<template>
  <article class="ef-resident">
    <EndfieldArtwork role :operator-id="operator.id || operator.charId" :src="operator.avatar_url" :name="operator.name || operator.id || operator.charId || '干员'" />
    <div class="resident-copy"><h3>{{ operator.name || operator.id || operator.charId || '驻守干员' }}</h3>
      <div class="resident-meter"><div><span>心情</span><strong>{{ shipPercent(operator.mood_percent) }}</strong></div><progress v-if="operator.mood_percent != null" :value="operator.mood_percent" max="100" :aria-label="`${operator.name || '驻守干员'}心情`" /><span v-else class="unknown-meter">来源值缺失或超出模型范围</span></div>
      <div class="resident-meter trust-meter"><div><span>信赖 <small>{{ operator.trust_level_name || '阶段未知' }}</small></span><strong>{{ shipPercent(operator.trust_percent) }}</strong></div><progress v-if="operator.trust_percent != null" :value="operator.trust_percent" max="200" :aria-label="`${operator.name || '驻守干员'}信赖`" /><span v-else class="unknown-meter">尚无可换算的来源值</span></div>
      <details class="resident-raw"><summary>查看原始观测值</summary><dl><div><dt>心情观测值</dt><dd>{{ display(operator.mood_raw) }}</dd></div><div><dt>信赖观测值</dt><dd>{{ display(operator.trust_raw) }}</dd></div></dl></details>
    </div>
  </article>
</template>
<style scoped>
.ef-resident{display:flex;gap:14px;align-items:flex-start;padding:18px 0;border-bottom:1px solid var(--border);min-width:0}.ef-resident:last-child{border-bottom:0;padding-bottom:0}.resident-copy{flex:1;min-width:0}.resident-copy h3{font-size:14px;font-weight:500;line-height:1.7;overflow-wrap:anywhere;margin-bottom:14px}.resident-meter{margin-top:12px}.resident-meter>div{display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:12px;color:var(--text-muted)}.resident-meter strong{font-family:var(--font-mono);font-size:16px;font-weight:500;color:var(--game-endfield);white-space:nowrap}.trust-meter strong,.trust-meter small{color:var(--ef-cyan,#79c9d1)}.resident-meter small{font-size:10px;margin-left:6px}.resident-meter progress{display:block;appearance:none;width:100%;height:5px;border:0;background:var(--border);margin-top:8px;accent-color:var(--game-endfield)}.resident-meter progress::-webkit-progress-bar{background:var(--border)}.resident-meter progress::-webkit-progress-value{background:var(--game-endfield)}.resident-meter progress::-moz-progress-bar{background:var(--game-endfield)}.trust-meter progress{accent-color:var(--ef-cyan,#79c9d1)}.trust-meter progress::-webkit-progress-value{background:var(--ef-cyan,#79c9d1)}.trust-meter progress::-moz-progress-bar{background:var(--ef-cyan,#79c9d1)}.unknown-meter{display:block;font-size:10px;color:var(--text-muted);border-bottom:1px dashed var(--border);padding:7px 0;line-height:1.6}.resident-raw{margin-top:13px;font-size:10px;color:var(--text-muted)}.resident-raw summary{cursor:pointer;padding:5px 0;min-height:26px}.resident-raw dl{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 0}.resident-raw dl>div{display:flex;gap:6px}.resident-raw dd{margin:0;font-family:var(--font-mono);overflow-wrap:anywhere}.resident-raw dt{font-weight:400}@media(max-width:600px){.ef-resident{gap:12px}.ef-resident>.endfield-artwork{width:44px;height:44px}.resident-copy h3{font-size:13px}.resident-meter strong{font-size:15px}}
</style>
