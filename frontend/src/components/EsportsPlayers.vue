<script setup>
import { computed } from 'vue'
import { esportsGroupLabel, esportsImage, esportsMonogram, officialEsportsUrl } from '../esports.js'
const props = defineProps({ payload: Object, filters: Object })
const emit = defineEmits(['select-player', 'select-team', 'back'])
const selected = computed(() => props.payload.players?.find(p => p.id === props.filters.playerId))
const team = id => props.payload.teams?.find(t => t.id === id)
const memberships = id => (props.payload.roster_memberships || []).filter(r => r.player_id === id)
const players = computed(() => (props.payload.players || []).filter(p => !props.filters.family || memberships(p.id).some(r => team(r.team_id)?.tournament_ids?.some(id => props.payload.tournaments?.find(t => t.id === id)?.family === props.filters.family))))
</script>
<template>
  <section aria-label="职业选手">
    <template v-if="filters.playerId"><button class="es-back ui-button small-button" @click="emit('back')">← 返回</button><template v-if="selected"><div class="es-profile cap-card"><span class="es-logo xxl" :data-letter="esportsMonogram(selected.nickname, 2)"><img v-if="esportsImage(selected.image_url)" :src="esportsImage(selected.image_url)" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><div class="es-profile-copy"><h3 tabindex="-1">{{ selected.nickname }}</h3><a v-if="officialEsportsUrl(selected.source_url)" class="ui-button small-button es-official" :href="officialEsportsUrl(selected.source_url)" target="_blank" rel="noopener noreferrer">官方选手资料 ↗</a></div></div><h4>队伍与位置</h4><article v-for="r in memberships(selected.id)" :key="`${r.team_id}:${r.scope}`" class="es-match cap-card"><button :id="'es-membership-' + r.team_id + '-' + r.scope" class="es-chip-button" @click="emit('select-team', r.team_id, 'es-membership-' + r.team_id + '-' + r.scope)">{{ team(r.team_id)?.name || '队伍资料暂缺' }}</button> · {{ r.position || '位置未提供' }}<p class="es-note">{{ r.scope === 'source_current' ? '当前阵容' : r.scope === 'season_registered' ? '赛季报名阵容' : '单场登场阵容' }} · {{ esportsGroupLabel(payload.coverage?.[`roster:${r.team_id}`]) }}</p></article><p v-if="!memberships(selected.id).length" class="es-empty">队伍与位置资料暂缺。</p></template><p v-else class="es-empty">该选手资料暂缺。</p></template>
    <template v-else><h3 tabindex="-1">已收录选手</h3><div class="es-grid"><button v-for="player in players" :id="'es-player-card-' + player.id" :key="player.id" class="es-tile" @click="emit('select-player', player.id, 'es-player-card-' + player.id)"><span class="es-logo xl" :data-letter="esportsMonogram(player.nickname, 2)"><img v-if="esportsImage(player.image_url)" :src="esportsImage(player.image_url)" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><strong>{{ player.nickname }}</strong><span>{{ memberships(player.id).map(r => team(r.team_id)?.name || '队伍未知').join(' / ') || '队伍暂缺' }}</span><span>{{ memberships(player.id).map(r => r.position || '位置未提供').join(' / ') || '位置未提供' }}</span></button></div><p v-if="!players.length" class="es-empty">选手资料暂缺。</p></template>
  </section>
</template>
