<script setup>
defineProps({ role:{type:Object,required:true}, imageMode:{type:Boolean,default:false} })
const show = value => value == null || value === '' ? '未提供' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const rows = value => Array.isArray(value) ? value : []
</script>
<template>
  <div class="nte-equipped-details">
    <section><h4>觉醒效果</h4><p v-for="(effect,i) in rows(role.awaken_effects)" :key="i">{{ effect }}</p><p v-if="!rows(role.awaken_effects).length">未提供</p></section>
    <section v-if="role.weapon"><h4>弧盘资料</h4><p>{{ show(role.weapon.name) }} · 突破 {{ show(role.weapon.breakthrough_level) }}</p><p>{{ show(role.weapon.description) }}</p><p>{{ show(role.weapon.buff_name) }}：{{ show(role.weapon.buff_description) }}</p><dl><div v-for="(p,i) in rows(role.weapon.properties)" :key="i"><dt>{{ show(p.name) }}</dt><dd>{{ show(p.value) }}</dd></div></dl></section>
    <section v-for="group in [{title:'战技说明',rows:role.skills},{title:'城区技能说明',rows:role.city_skills}]" :key="group.title"><h4>{{ group.title }}</h4><div v-for="(s,i) in rows(group.rows)" :key="i"><p>{{ show(s.name) }}</p><p v-for="(item,j) in rows(s.items)" :key="j">{{ show(item.title) }}：{{ show(item.desc) }}</p></div></section>
    <section><h4>已装备套装</h4><template v-if="role.suit"><p>{{ show(role.suit.name) }} · 激活数 {{ show(role.suit.activation_count) }}</p><p>二件：{{ show(role.suit.description_two) }}</p><p>四件：{{ show(role.suit.description_four) }}</p><section v-for="group in ['core','pie']" :key="group"><div v-for="(item,i) in rows(role.suit[group])" :key="i"><p>{{ show(item.name) }} · Lv{{ show(item.level) }}</p><dl v-for="kind in ['main_properties','properties']" :key="kind"><div v-for="(p,j) in rows(item[kind])" :key="j"><dt>{{ kind==='main_properties'?'主':'副' }} · {{ show(p.name) }}</dt><dd>{{ show(p.value) }}</dd></div></dl></div></section></template><p v-else>未提供</p></section>
    <details v-if="!imageMode" data-render-collapsed><summary>补充资料</summary><p>角色命途来源值：{{ show(role.group_type) }}</p><p v-if="role.weapon">来源 ID {{ show(role.weapon.id) }} · 命途来源值 {{ show(role.weapon.group_type) }} · 效果数值表（未替换模板）：{{ show(role.weapon.lbd) }}</p><template v-if="role.suit"><p>来源条件：{{ show(role.suit.conditions) }}</p><p>装备品质、面积、完整副词条完成标记未得到来源验证。</p><p v-for="group in ['core','pie']" :key="group">{{ group }}：{{ rows(role.suit[group]).map(item=>show(item.id)).join('、') }}</p></template></details>
  </div>
</template>
<style scoped>
.nte-equipped-details{display:grid;gap:10px;font-size:13px;line-height:1.6;overflow-wrap:anywhere}
/* Each block is a soft tile with a hairline inside the role's white card. */
.nte-equipped-details>section{margin:0;padding:12px 14px;border-radius:var(--radius-well);background:var(--surface-soft);box-shadow:inset 0 0 0 1px var(--overlay-2)}
.nte-equipped-details section section{margin-top:8px;padding:0;background:none;box-shadow:none}
.nte-equipped-details h4,.nte-equipped-details h5{margin:0 0 4px;color:var(--text-muted);font-size:12px;font-weight:500}
.nte-equipped-details p{margin:4px 0;white-space:pre-wrap}
.nte-equipped-details dl>div{display:flex;justify-content:space-between;gap:12px}
.nte-equipped-details dd{margin:0}
.nte-equipped-details details{padding:4px 14px}
</style>
