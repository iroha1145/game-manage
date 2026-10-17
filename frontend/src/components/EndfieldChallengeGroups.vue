<script setup>
import { displayValue as display, rows } from '../endfield-reports.js'
import { stageStates } from '../endfield-challenges.js'
defineProps({ groups: Array })
const passed = value => value === true ? '已通关' : value === false ? '未通关' : '状态未知'
const summary = group => { const state = stageStates([group]); return `已通关 ${state.passed}，未通关 ${state.failed}，状态未知 ${state.unknown}` }
</script>
<template>
  <div class="challenge-groups"><article v-for="(group,index) in rows(groups)" :key="index" class="challenge-group"><header><h4>{{ group.name || `关卡组 ${index+1}` }}</h4><span class="group-stars">星数 {{ display(group.stars) }}</span></header><p v-if="!rows(group.stages).length" class="challenge-note">尚无关卡明细。</p><template v-else><div class="stage-pips" role="img" :aria-label="summary(group)"><i v-for="(stage,stageIndex) in rows(group.stages)" :key="stageIndex" :class="{passed:stage.passed === true, incomplete:stage.passed === false}"></i></div><ul><li v-for="(stage,stageIndex) in rows(group.stages)" :key="stageIndex"><span class="difficulty">{{ stage.difficulty || '难度未知' }}</span><strong>{{ stage.name || '未命名关卡' }}</strong><span class="stage-state" :class="{passed:stage.passed === true, incomplete:stage.passed === false}">{{ passed(stage.passed) }}</span></li></ul></template></article></div>
</template>
<style scoped>
.challenge-groups{display:grid;gap:10px}
.challenge-group{padding:14px;border-radius:var(--radius-tile);background:var(--group-bg,var(--surface-soft));min-width:0}
.challenge-group>header{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-bottom:8px}
.challenge-group h4{margin:0;font-size:14px;font-weight:600;overflow-wrap:anywhere}
.group-stars{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:500;color:var(--text-muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.group-stars::before{content:'★';color:var(--game-endfield)}
/* One pip per stage, in order: cleared stages take the success colour, open ones the game colour. */
.stage-pips{display:flex;gap:4px;margin-bottom:6px}
.stage-pips>i{flex:1;height:6px;border-radius:999px;background:var(--track)}
.stage-pips>i.passed{background:var(--success)}
.stage-pips>i.incomplete{background:var(--game-vivid,var(--game-endfield-vivid))}
.challenge-group li{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;padding:8px 0;border-top:1px solid var(--border);font-size:13px}
.challenge-group li:first-child{border-top:0}
.difficulty{font-size:12px;color:var(--text-muted);min-width:28px}
.challenge-group li>strong{font-size:13px;font-weight:500;flex:1;min-width:80px;overflow-wrap:anywhere}
.stage-state{font-size:12px;color:var(--text-muted)}
.stage-state.passed{color:var(--success)}
.stage-state.incomplete{color:var(--game-endfield)}
.challenge-note{font-size:13px;color:var(--text-muted)}
</style>
