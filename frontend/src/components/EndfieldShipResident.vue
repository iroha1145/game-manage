<script setup>
import { shipPercent } from '../endfield-ship.js'
import { displayValue as display } from '../endfield-reports.js'
import EndfieldArtwork from './EndfieldArtwork.vue'
import AppIcon from './AppIcon.vue'
defineProps({ operator: {type:Object,required:true}, imageMode:Boolean })
</script>
<template>
  <article class="ef-resident">
    <EndfieldArtwork role :operator-id="operator.id || operator.charId" :src="operator.avatar_url" :name="operator.name || operator.id || operator.charId || '干员'" />
    <div class="resident-copy"><h3>{{ operator.name || operator.id || operator.charId || '驻守干员' }}</h3>
      <div class="resident-meters"><div class="resident-meter"><div><span><AppIcon name="sun" :size="12" />心情</span><strong>{{ shipPercent(operator.mood_percent) }}</strong></div><progress v-if="operator.mood_percent != null" :value="operator.mood_percent" max="100" :aria-label="`${operator.name || '驻守干员'}心情`" /><span v-else class="unknown-meter">{{ operator.mood_raw > 10000 ? '超出模型范围' : '观测值未知' }}</span></div>
      <div class="resident-meter trust-meter"><div><span><AppIcon name="shield" :size="12" />信赖 <small>{{ operator.trust_level_name || '阶段未知' }}</small></span><strong>{{ shipPercent(operator.trust_percent) }}</strong></div><progress v-if="operator.trust_percent != null" :value="operator.trust_percent" max="200" :aria-label="`${operator.name || '驻守干员'}信赖`" /><span v-else class="unknown-meter">观测值未知</span></div></div>
      <details v-if="!imageMode" class="resident-raw"><summary>查看原始观测值</summary><dl><div><dt>心情观测值</dt><dd>{{ display(operator.mood_raw) }}</dd></div><div><dt>信赖观测值</dt><dd>{{ display(operator.trust_raw) }}</dd></div></dl></details>
    </div>
  </article>
</template>
<style scoped>
.ef-resident{display:flex;gap:16px;align-items:flex-start;padding:16px 0;border-bottom:1px solid var(--border);min-width:0}
.ef-resident:last-child{border-bottom:0;padding-bottom:0}
.ef-resident>.endfield-artwork{width:62px;height:70px}
.resident-copy{flex:1;min-width:0}
.resident-copy h3{font-size:14px;font-weight:500;line-height:1.7;overflow-wrap:anywhere;margin-bottom:8px}
.resident-meters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.resident-meter{position:relative;min-width:0}
.resident-meter>div{display:flex;justify-content:space-between;align-items:baseline;gap:6px;font-size:12px;color:var(--text-muted);flex-wrap:wrap}
.resident-meter>div>span{display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap;line-height:1.6}
.resident-meter strong{font-size:14px;font-weight:500;font-variant-numeric:tabular-nums;color:var(--text);white-space:nowrap}
.resident-meter small{font-size:12px}
.resident-meter svg{width:16px;height:16px;color:var(--text-muted)}
.resident-meter progress{display:block;appearance:none;width:100%;height:4px;border:0;border-radius:999px;overflow:hidden;background:var(--track);margin-top:7px;accent-color:var(--game-endfield)}
.resident-meter progress::-webkit-progress-bar{background:var(--track);border-radius:999px}
.resident-meter progress::-webkit-progress-value{background:var(--game-endfield);border-radius:999px}
.resident-meter progress::-moz-progress-bar{background:var(--game-endfield);border-radius:999px}
.trust-meter progress{accent-color:var(--ef-cyan)}
.trust-meter progress::-webkit-progress-value{background:var(--ef-cyan)}
.trust-meter progress::-moz-progress-bar{background:var(--ef-cyan)}
.unknown-meter{display:block;font-size:12px;color:var(--text-muted);border-bottom:1px dashed var(--border);padding:5px 0 0;line-height:1.6}
.resident-raw{margin-top:8px;font-size:12px;color:var(--text-muted)}
.resident-raw summary{cursor:pointer;padding:7px 0;min-height:28px}
.resident-raw dl{display:flex;gap:6px 12px;flex-wrap:wrap;margin:6px 0 0}
.resident-raw dl>div{display:flex;gap:6px}
.resident-raw dd{margin:0;overflow-wrap:anywhere}
.resident-raw dt{font-weight:400}
@media(max-width:600px){.ef-resident{gap:12px}.ef-resident>.endfield-artwork{width:48px;height:59px}.resident-meters{gap:12px}}
</style>
