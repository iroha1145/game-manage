<script setup>
import { displayValue as display, rows } from '../endfield-reports.js'
defineProps({ groups: Array })
const passed = value => value === true ? '已通关' : value === false ? '未通关' : '状态未知'
</script>
<template>
  <div class="challenge-groups"><article v-for="(group,index) in rows(groups)" :key="index" class="challenge-group"><header><h4>{{ group.name || `关卡组 ${index+1}` }}</h4><span>星数 {{ display(group.stars) }}</span></header><p v-if="!rows(group.stages).length" class="challenge-note">尚无关卡明细。</p><ul v-else><li v-for="(stage,stageIndex) in rows(group.stages)" :key="stageIndex"><span class="difficulty">{{ stage.difficulty || '难度未知' }}</span><strong>{{ stage.name || '未命名关卡' }}</strong><span class="stage-state" :class="{passed:stage.passed === true, incomplete:stage.passed === false}">{{ passed(stage.passed) }}</span></li></ul></article></div>
</template>
<style scoped>
.challenge-groups{display:grid;gap:12px}
.challenge-group{padding:14px;border-radius:var(--radius-well);background:var(--surface-soft);min-width:0}
.challenge-group>header{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-bottom:10px}
.challenge-group h4{margin:0;font-size:14px;font-weight:500;overflow-wrap:anywhere}
.challenge-group header>span{font-size:12px;color:var(--text-muted);white-space:nowrap}
.challenge-group li{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;padding:10px 0;border-top:1px solid var(--border-strong);font-size:13px}
.difficulty{font-size:12px;color:var(--text-muted);min-width:28px}
.challenge-group li>strong{font-size:13px;font-weight:500;flex:1;min-width:80px;overflow-wrap:anywhere}
.stage-state{font-size:12px;color:var(--text-muted)}
.passed{color:var(--success)}
.incomplete{color:var(--game-endfield)}
.challenge-note{font-size:13px;color:var(--text-muted)}
</style>
