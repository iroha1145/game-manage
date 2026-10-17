<script setup>
import { computed } from 'vue'
import { rows, displayValue as display, sourceName as named } from '../endfield-reports.js'
import { displayBeijing } from '../time.js'
import HRail from './HRail.vue'
import EndfieldArtwork from './EndfieldArtwork.vue'
import EndfieldTacticalItem from './EndfieldTacticalItem.vue'
const props=defineProps({operator:{type:Object,required:true},titleSuffix:{type:String,default:''}})
const slotDefinitions=[['bodyEquip','护甲'],['armEquip','护手'],['firstAccessory','配件一'],['secondAccessory','配件二']]
const equipment=computed(()=>rows(props.operator.equipment))
const slots=computed(()=>slotDefinitions.map(([id,label])=>({id,label,item:equipment.value.find(item=>item.slot===id)})))
// Older observations without a source slot remain visible without assigning one.
const extraEquipment=computed(()=>equipment.value.filter((item,index)=>!slotDefinitions.some(([id])=>id===item.slot) || equipment.value.findIndex(other=>other.slot===item.slot)!==index))
const time=value=>value == null || value === '' ? '未知' : displayBeijing(value)
</script>
<template>
  <div class="ef-loadout">
    <section class="loadout-hero" aria-label="干员档案">
      <EndfieldArtwork class="loadout-portrait" role portrait :operator-id="operator.char_id || operator.id" :src="operator.avatar_url" :name="operator.name || '干员'" />
      <div class="hero-identity"><p class="hero-class">{{ named(operator.profession) }} / {{ named(operator.property) }}</p><h3>{{ operator.name || '干员' }}{{ titleSuffix }}</h3>
        <dl class="operator-marks"><div><dt>等级</dt><dd><small>LV.</small>{{ display(operator.level) }}</dd></div><div><dt>潜能</dt><dd>{{ display(operator.potential) }}</dd></div><div><dt>精英阶段</dt><dd>{{ display(operator.evolve_phase ?? operator.phase) }}</dd></div></dl>
        <p class="obtained-time">获得时间 {{ time(operator.obtained_at) }}（北京时间）</p>
      </div>
    </section>
    <div class="loadout-assembly">
      <section class="loadout-module weapon-module" aria-label="武器与基质">
        <header><h3>武器与基质</h3></header>
        <div class="weapon-line"><EndfieldArtwork class="weapon-art" :src="operator.weapon?.icon_url" :name="named(operator.weapon)" /><div class="weapon-copy"><h4>{{ named(operator.weapon) }}</h4><dl class="item-marks"><div><dt>等级</dt><dd>LV. {{ display(operator.weapon?.level) }}</dd></div><div><dt>精炼</dt><dd>{{ display(operator.weapon?.refine_level) }}</dd></div><div><dt>突破</dt><dd>{{ display(operator.weapon?.breakthrough_level) }}</dd></div></dl></div></div>
        <div class="gem-line"><EndfieldArtwork :src="operator.weapon?.gem?.icon_url" :name="named(operator.weapon?.gem)" /><div><p><span>基质</span> {{ named(operator.weapon?.gem) }}</p><ul v-if="rows(operator.weapon?.gem?.terms).length" class="gem-terms"><li v-for="(term,index) in rows(operator.weapon.gem.terms)" :key="index">{{ named(term) }} <b>{{ display(term.cost) }}</b></li></ul></div></div>
      </section>
      <section class="loadout-module equipment-module" aria-label="四槽装备">
        <header><h3>装备</h3></header>
        <ul class="equipment-slots"><li v-for="slot in slots" :key="slot.id" :class="{'slot-unknown':!slot.item}"><span class="slot-label">{{ slot.label }}</span><EndfieldArtwork :src="slot.item?.icon_url" :name="slot.item ? named(slot.item) : slot.label" /><h4>{{ slot.item ? named(slot.item) : '资料未知' }}</h4><p v-if="slot.item" class="slot-level"><span>等级</span> LV. {{ display(slot.item.level) }}</p><p v-else class="slot-level">未提供该槽位资料</p></li></ul>
        <ul v-if="extraEquipment.length" class="extra-equipment"><li v-for="(item,index) in extraEquipment" :key="item.id || index"><EndfieldArtwork :src="item.icon_url" :name="named(item)" /><div><p class="slot-label">{{ item.slot_label || item.slot_name || item.slot || '来源未标槽位' }}</p><h4>{{ named(item) }}</h4><p class="slot-level">等级 LV. {{ display(item.level) }}</p></div></li></ul>
      </section>
    </div>
    <section class="loadout-module skills-module" aria-label="干员技能"><header><h3>技能</h3></header><p v-if="!rows(operator.skills).length" class="module-empty">技能资料未知</p>
      <HRail v-else label="干员技能"><ul class="skill-slots" role="list"><li v-for="(skill,index) in rows(operator.skills)" :key="skill.id || index"><div class="skill-art"><EndfieldArtwork :src="skill.icon_url" :name="named(skill)" /><span class="skill-level" :aria-label="`等级 ${display(skill.level)}`">LV. {{ display(skill.level) }}</span></div><div class="skill-copy"><h4>{{ named(skill) }}</h4><p v-if="skill.mastery != null" class="skill-mastery">专精 {{ display(skill.mastery) }}</p></div></li></ul></HRail></section>
    <EndfieldTacticalItem :item="operator.tactical_item" />
  </div>
</template>
<style scoped>
/* A bento in its own right: the portrait card, the weapon and equipment cards beside it, then skills and the tactical item. */
.ef-loadout{--accent:var(--game-endfield);--accent-soft:color-mix(in srgb,var(--game-endfield) 8%,var(--card-bg));--lo-vivid:var(--game-vivid,var(--game-endfield-vivid));display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;min-width:0}
.ef-loadout>*{grid-column:1/-1;min-width:0}
.loadout-hero,.loadout-module{position:relative;min-width:0;border:1px solid var(--card-border);border-radius:var(--radius-card);background:var(--card-bg);box-shadow:var(--card-shadow)}
.loadout-module{padding:20px}
.loadout-module>header{display:flex;gap:10px;align-items:center;margin-bottom:12px}
.loadout-module h3{font-size:15px;font-weight:600;letter-spacing:-.01em}
.loadout-hero{grid-column:span 5;overflow:hidden;display:grid;grid-template-rows:auto 1fr;background:radial-gradient(90% 60% at 50% 18%,color-mix(in srgb,var(--lo-vivid) 22%,transparent),transparent 72%),var(--card-bg)}
.loadout-hero::before{content:'';position:absolute;left:22px;top:0;z-index:1;width:64px;height:6px;border-radius:0 0 6px 6px;background:repeating-linear-gradient(135deg,var(--lo-vivid) 0 6px,color-mix(in srgb,var(--lo-vivid) 28%,transparent) 6px 12px)}
.loadout-portrait{width:100%;height:320px;border-radius:0;box-shadow:none}
.hero-identity{position:relative;display:grid;gap:4px;padding:6px 22px 22px}
.hero-class{font-size:12px;color:var(--text-muted);line-height:1.7}
.hero-identity h3{font-size:24px;font-weight:600;line-height:1.3;letter-spacing:-.02em;overflow-wrap:anywhere;margin:0 0 10px}
.operator-marks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.operator-marks>div{padding:10px 12px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.operator-marks dt{font-size:12px;color:var(--text-muted);margin-bottom:2px}
.operator-marks dd{margin:0;font-size:28px;font-weight:600;line-height:32px;letter-spacing:-.03em;font-variant-numeric:proportional-nums}
.operator-marks small{font-size:13px;font-weight:500;letter-spacing:0;color:var(--text-muted);margin-right:3px}
.obtained-time{font-size:12px;line-height:1.8;color:var(--text-muted);margin-top:10px;overflow-wrap:anywhere}
.loadout-assembly{grid-column:span 7;display:grid;gap:16px;align-content:start;min-width:0}
.weapon-line{display:flex;gap:18px;align-items:center;min-width:0}
.weapon-art{width:96px;height:96px;border-radius:26%}
.weapon-copy{min-width:0;flex:1}
.ef-loadout h4{margin:0;font-size:13px;font-weight:500;line-height:1.6;overflow-wrap:anywhere}
.weapon-copy h4{font-size:18px;font-weight:600;letter-spacing:-.01em;margin-bottom:8px}
.item-marks{display:flex;gap:8px;flex-wrap:wrap}
.item-marks>div{display:grid;gap:0;min-width:76px;padding:6px 12px;border-radius:var(--radius-well);background:var(--surface-soft)}
.item-marks dt{font-size:12px;color:var(--text-muted)}
.item-marks dd{margin:0;font-size:16px;font-weight:600;line-height:22px;font-variant-numeric:tabular-nums}
.gem-line{display:flex;align-items:center;gap:12px;margin-top:14px;padding:12px;border-radius:var(--radius-tile);background:var(--surface-soft);min-width:0}
.gem-line>.endfield-artwork{width:38px;height:38px;border-radius:30%}
.gem-line>div{min-width:0}
.gem-line p{font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.gem-line p>span{color:var(--text-muted);margin-right:6px}
.gem-terms{display:flex;gap:4px 8px;flex-wrap:wrap;font-size:12px;line-height:1.8;color:var(--text-muted);margin-top:4px}
.gem-terms li{padding:0 10px;border-radius:var(--radius-chip);background:var(--card-bg)}
.gem-terms b{color:var(--text);font-weight:500;margin-left:4px}
.equipment-slots{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.equipment-slots>li{position:relative;min-width:0;padding:10px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.slot-label{font-size:12px;line-height:1.6;color:var(--text-muted)}
.equipment-slots .endfield-artwork{width:100%;height:68px;margin:6px 0 8px;border-radius:var(--radius-well)}
.equipment-slots h4{font-size:13px;min-height:21px}
.slot-level{font-size:12px;line-height:1.7;color:var(--text-muted);margin-top:2px;overflow-wrap:anywhere}
.slot-level>span{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.equipment-slots>li.slot-unknown{background:transparent;box-shadow:inset 0 0 0 1px var(--border-strong)}
.slot-unknown .endfield-artwork{opacity:.45}
.slot-unknown h4{color:var(--text-muted);font-weight:400}
.extra-equipment{display:grid;gap:10px;margin-top:12px}
.extra-equipment>li{display:flex;align-items:center;gap:12px;min-width:0;padding:10px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.extra-equipment .endfield-artwork{width:44px;height:44px;border-radius:28%}
.extra-equipment>li>div{min-width:0}
.skills-module{grid-column:span 8;overflow:hidden}
.ef-loadout>.ef-tactical{grid-column:span 4}
.skills-module :deep(.h-rail){--rail-gap:12px;--rail-pad-block:6px;--rail-pad:2px}
.skill-slots{display:contents;list-style:none;padding:0;margin:0}
.skill-slots>li{flex:0 0 auto;scroll-snap-align:start;display:flex;gap:12px;align-items:center;width:208px;padding:12px;border-radius:var(--radius-tile);background:var(--surface-soft);min-width:0}
.skill-art{position:relative;flex-shrink:0;padding-bottom:10px}
.skill-art>.endfield-artwork{width:54px;height:54px;border-radius:28%}
.skill-level{position:absolute;bottom:0;left:50%;transform:translateX(-50%);min-width:44px;padding:0 6px;border-radius:var(--radius-chip);text-align:center;background:color-mix(in srgb,var(--lo-vivid) 34%,var(--card-bg));color:var(--text);box-shadow:0 0 0 2px var(--surface-soft);font-size:12px;font-weight:600;line-height:20px;white-space:nowrap;font-variant-numeric:tabular-nums}
.skill-copy{min-width:0}
.skill-slots h4{font-size:13px;font-weight:600}
.skill-mastery{font-size:12px;color:var(--text-muted);margin-top:2px}
.module-empty{font-size:13px;color:var(--text-muted);line-height:1.7;padding:8px 0}
/* A bot image is one still frame: flat fills, no shadows or washes (they inflate the PNG). */
:global(.render-image) .loadout-hero,:global(.render-image) .loadout-module{box-shadow:none;border-color:var(--border)}
:global(.render-image) .loadout-hero{background:var(--card-bg)}
:global(.render-image) .loadout-hero::before{background:var(--lo-vivid)}
@media(max-width:900px){
  .loadout-hero,.loadout-assembly,.skills-module,.ef-loadout>.ef-tactical{grid-column:1/-1}
  .loadout-portrait{height:280px}
}
@media(max-width:600px){
  .loadout-module{padding:16px;border-radius:20px}
  .loadout-hero{border-radius:20px}
  .equipment-slots{grid-template-columns:repeat(2,minmax(0,1fr))}
  .weapon-art{width:76px;height:76px}
  .weapon-line{gap:14px}
  .skill-slots>li{width:188px}
}
</style>
