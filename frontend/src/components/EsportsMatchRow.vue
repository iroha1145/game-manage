<script setup>
import { computed } from 'vue'
import { esportsTime, esportsImage, esportsMonogram, esportsOutcome, ESPORTS_STATUS } from '../esports.js'
// `row` is the compact list line (results, a team's matches); `card` is the match card the schedule rails use.
const props = defineProps({ match: Object, payload: Object, variant: { type: String, default: 'row' } })
const emit = defineEmits(['select-match', 'select-team'])
const tournament = computed(() => props.payload.tournaments?.find(t => t.id === props.match.tournament_id))
const team = side => props.payload.teams?.find(t => t.id === props.match['team_' + side + '_id'])
const image = side => esportsImage(team(side)?.logo_url)
const mark = side => esportsMonogram(team(side)?.short_name || props.match['team_' + side + '_name'])
const score = computed(() => ['completed', 'live'].includes(props.match.status) && props.match.score_a != null && props.match.score_b != null)
const label = computed(() => (props.match.team_a_name || '待定') + ' 对 ' + (props.match.team_b_name || '待定') + '，' + (score.value ? props.match.score_a + ' : ' + props.match.score_b : '比分待定') + '，查看比赛摘要')
</script>
<template>
  <article :class="variant === 'card' ? ['es-card', { 'is-live': match.status === 'live' }] : 'es-row'" :id="'es-row-' + match.id" :data-status="match.status">
    <div class="es-row-time"><time>{{ match.start_at ? esportsTime(match.start_at).slice(11, 16) : '待公布' }}</time><span :class="{ 'es-live': match.status === 'live' }">{{ ESPORTS_STATUS[match.status] || ESPORTS_STATUS.unknown }}</span></div>
    <div class="es-row-versus">
      <button :id="'es-team-' + match.id + '-a'" class="es-row-team es-team-a" :class="{ 'es-winner': esportsOutcome(match, 'a') === '胜' }" :disabled="!match.team_a_id" @click="emit('select-team', match.team_a_id, 'es-team-' + match.id + '-a')"><span>{{ match.team_a_name || '待定' }}</span><span class="es-logo" :data-letter="mark('a')"><img v-if="image('a')" :src="image('a')" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span></button>
      <button :id="'es-open-' + match.id" class="es-row-score" :data-open-match="match.id" :aria-label="label" @click="emit('select-match', match.id, 'es-open-' + match.id)">
        <strong v-if="score"><span :class="{ 'es-score-win': esportsOutcome(match, 'a') === '胜', 'es-score-loss': esportsOutcome(match, 'a') === '负' }">{{ match.score_a }}</span> : <span :class="{ 'es-score-win': esportsOutcome(match, 'b') === '胜', 'es-score-loss': esportsOutcome(match, 'b') === '负' }">{{ match.score_b }}</span></strong><strong v-else>VS</strong>
        <small v-if="match.status === 'completed'">{{ esportsOutcome(match, 'a') ? esportsOutcome(match, 'a') + ' / ' + esportsOutcome(match, 'b') : '胜者未确认' }}</small><small v-else-if="!score">比分待定</small>
      </button>
      <button :id="'es-team-' + match.id + '-b'" class="es-row-team es-team-b" :class="{ 'es-winner': esportsOutcome(match, 'b') === '胜' }" :disabled="!match.team_b_id" @click="emit('select-team', match.team_b_id, 'es-team-' + match.id + '-b')"><span class="es-logo" :data-letter="mark('b')"><img v-if="image('b')" :src="image('b')" alt="" referrerpolicy="no-referrer" @error="$event.target.hidden = true"></span><span>{{ match.team_b_name || '待定' }}</span></button>
    </div>
    <button class="es-row-context" :aria-label="label" @click="emit('select-match', match.id, 'es-open-' + match.id)"><span>{{ tournament?.name || '赛事资料暂缺' }}</span><small>{{ match.stage || '阶段待公布' }}</small></button>
    <span class="es-row-bo">{{ match.best_of ? 'BO' + match.best_of : '赛制待定' }}</span>
  </article>
</template>
