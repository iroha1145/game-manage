<script setup>
import { computed } from 'vue'
import { esportsDayLabel, esportsGroupLabel, esportsImage, esportsMonogram, esportsTeamForm, officialEsportsUrl, esportsSections } from '../esports.js'
import { vReveal } from '../motion.js'
import EsportsMatchRow from './EsportsMatchRow.vue'
import HRail from './HRail.vue'
const props = defineProps({ payload: Object, filters: Object })
const emit = defineEmits(['select-team', 'select-player', 'select-match', 'back'])
const selected = computed(() => props.payload.teams?.find(t => t.id === props.filters.teamId))
const teams = computed(() => (props.payload.teams || []).filter(t => !props.filters.family || t.tournament_ids?.some(id => props.payload.tournaments?.find(e => e.id === id)?.family === props.filters.family)))
const roster = computed(() => (props.payload.roster_memberships || []).filter(r => r.team_id === selected.value?.id))
const player = id => props.payload.players?.find(p => p.id === id)
const related = computed(() => esportsSections(props.payload, { family: props.filters.family, teamId: selected.value?.id }, 12).flatMap(s => s.groups).slice(0, 12))
const form = computed(() => selected.value ? esportsTeamForm(props.payload, selected.value.id) : [])
const mark = team => esportsMonogram(team?.short_name || team?.name)
</script>
<template>
  <section aria-label="职业战队">
    <template v-if="filters.teamId"><button class="es-back ui-button small-button" @click="emit('back')">← 返回</button>
      <template v-if="selected"><div class="es-profile cap-card"><span class="es-logo xxl" :data-letter="mark(selected)"><img v-if="esportsImage(selected.logo_url)" :src="esportsImage(selected.logo_url)" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><div class="es-profile-copy"><h3 tabindex="-1">{{ selected.name }}</h3><p>{{ selected.kind === 'national' ? '国家／地区代表队' : selected.kind === 'club' ? '职业俱乐部' : '队伍类型未提供' }}</p>
          <div v-if="form.length" class="es-form-row"><span class="es-eyebrow">近期战绩</span><ul class="es-form" :aria-label="`近 ${form.length} 场已确认胜负的比赛，较早的在左`"><li v-for="result in form" :key="result.id" :class="result.win ? 'win' : 'loss'" :title="`对阵 ${result.opponent || '待定'}`">{{ result.win ? '胜' : '负' }}</li></ul></div></div></div>
        <p v-if="selected.description" class="es-note es-about">{{ selected.description }}</p>
        <a v-if="officialEsportsUrl(selected.source_url)" class="ui-button small-button es-official" :href="officialEsportsUrl(selected.source_url)" target="_blank" rel="noopener noreferrer">官方战队资料 ↗</a>
        <h4>当前阵容</h4><p class="es-note">{{ esportsGroupLabel(payload.coverage?.[`roster:${selected.id}`]) }}</p>
        <HRail v-if="roster.length" label="当前阵容" class="es-roster"><button v-for="r in roster" :id="'es-roster-' + r.player_id + '-' + r.scope" :key="`${r.player_id}:${r.scope}`" class="es-tile es-person" @click="emit('select-player', r.player_id, 'es-roster-' + r.player_id + '-' + r.scope)"><span class="es-logo xl" :data-letter="esportsMonogram(player(r.player_id)?.nickname, 2)"><img v-if="esportsImage(player(r.player_id)?.image_url)" :src="esportsImage(player(r.player_id)?.image_url)" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><strong>{{ player(r.player_id)?.nickname || '选手资料暂缺' }}</strong><span>{{ r.position || '位置未提供' }} · {{ r.scope === 'source_current' ? '当前阵容' : r.scope === 'season_registered' ? '赛季报名阵容' : '单场登场阵容' }}</span></button></HRail><p v-else class="es-empty">阵容资料暂缺。</p>
        <h4>相关赛程与近期赛果</h4><div v-for="(group, index) in related" :key="index" v-reveal class="es-date-group is-list"><h4>{{ esportsDayLabel(group.date) }}</h4><EsportsMatchRow v-for="m in group.matches" :key="m.id" :match="m" :payload="payload" @select-match="(id, focus) => emit('select-match', id, focus)" @select-team="(id, focus) => emit('select-team', id, focus)" /></div><p v-if="!related.length" class="es-empty">暂未收录该队相关赛程。</p>
      </template><p v-else class="es-empty">该战队资料暂缺，可返回赛程。</p>
    </template>
    <template v-else><h3 tabindex="-1">已收录战队</h3><div class="es-grid"><button v-for="team in teams" :id="'es-team-card-' + team.id" :key="team.id" class="es-tile" @click="emit('select-team', team.id, 'es-team-card-' + team.id)"><span class="es-logo xl" :data-letter="mark(team)"><img v-if="esportsImage(team.logo_url)" :src="esportsImage(team.logo_url)" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><strong>{{ team.name }}</strong><span>{{ team.short_name || '简称未提供' }}</span></button></div><p v-if="!teams.length" class="es-empty">当前赛事战队资料暂缺。</p></template>
  </section>
</template>
