<script setup>
defineProps({data:{type:Object,required:true}})
const list=value=>Array.isArray(value)?value:[]
const display=value=>value==null || value===''?'未知':String(value)
const named=value=>typeof value==='string'?value:value?.name || value?.title || '未知'
</script>
<template>            <div class="operator-detail" data-render-block>
              <p>武器：{{ named(data.weapon) }} · 等级 {{ display(data.weapon?.level) }} · 精炼 {{ display(data.weapon?.refine_level) }}</p>
              <p v-if="data.weapon?.gem">镶嵌：{{ named(data.weapon.gem) }}<span v-if="list(data.weapon.gem.terms).length"> · {{ list(data.weapon.gem.terms).map(term => `${display(term.name)} ${display(term.cost)}`).join('、') }}</span></p>
              <p>装备：{{ list(data.equipment).length ? list(data.equipment).map(item => `${named(item)}（等级 ${display(item.level)}）`).join('、') : '未知' }}</p>
              <p>技能：{{ list(data.skills).length ? list(data.skills).map(skill => `${named(skill)}（等级 ${display(skill.level)}）`).join('、') : '未知' }}</p>
            </div></template>
<style scoped>
.operator-detail{margin-top:8px;border-top:1px solid var(--border);padding-top:8px;display:grid;gap:5px}
.operator-detail p{font-size:13px;color:var(--text-muted);line-height:1.5;overflow-wrap:anywhere}
</style>
