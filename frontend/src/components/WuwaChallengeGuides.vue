<script setup>
import MenuSelect from './MenuSelect.vue'
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { challengeGuides, challengeGuideUpdatedAt, selectChallengeGuides } from '../wuwa-challenge-guides.js'
import { guideSourceUrl } from '../wuwa-guides.js'
import { namedIcon } from '../wuwa-icons.js'
import WuwaIcon from './WuwaIcon.vue'
import WuwaGuideLineups from './WuwaGuideLineups.vue'
const props = defineProps({ mode: { type: String, required: true }, bosses: { type: Array, default: () => [] } })
const selectedBoss = ref('')
const now = ref(Date.now())
let clock
onMounted(() => { clock = setInterval(() => { now.value = Date.now() }, 30000) })
onUnmounted(() => clearInterval(clock))
const options = computed(() => [...new Set([...props.bosses, ...challengeGuides.filter(g=>g.modes.includes(props.mode)&&g.boss).map(g=>g.boss)])].sort())
const guides = computed(() => selectChallengeGuides(props.mode, selectedBoss.value, now.value))
</script>
<template>
  <section aria-label="挑战社区攻略" class="challenge-guides">
    <header class="wuwa-heading"><h3>社区攻略</h3><span class="wuwa-meta">核查于 {{ challengeGuideUpdatedAt }}</span></header>
    <p v-if="mode === 'tower'" class="wuwa-meta">仅展示当期图文攻略，按原帖标注的深塔周期筛选。</p>
    <label v-if="mode === 'hologram'" class="boss-filter">筛选首领
      <MenuSelect class="boss-filter-menu" label="筛选首领" v-model="selectedBoss" :options="[{value:'',label:'全部首领与入门资料'},...options.map(boss => ({value:boss,label:boss}))]" />
    </label>
    <p v-if="!guides.length" class="wuwa-muted">{{ mode === 'tower' ? '暂无当期图文攻略，待更新。' : '暂无该首领图文攻略，可选择“全部首领与入门资料”。' }}</p>
    <div class="challenge-guide-list">
      <article v-for="guide in guides" :key="guide.id" class="wuwa-inset challenge-guide-card" :class="{ 'has-lineups': guide.lineupImages?.length }">
        <div class="challenge-guide-title">
          <WuwaIcon v-if="guide.boss" :src="namedIcon('echoes',guide.boss)" :name="guide.boss" />
          <div><div class="challenge-badges"><span class="wuwa-tag">{{ guide.version ? `V${guide.version}` : '版本未确认' }}</span><span class="wuwa-meta">{{ guide.format }}</span></div><h4><template v-if="guide.boss">{{ guide.boss }} · </template>{{ guide.scope }}</h4></div>
        </div>
        <p>{{ guide.summary }}</p>
        <WuwaGuideLineups v-if="guide.lineupImages?.length" :guide="guide" />
        <details><summary>原帖标题</summary><p>{{ guide.title }}</p></details>
        <footer><span class="wuwa-meta">{{ guide.author }} · {{ guide.publishedAt }}</span><a v-if="guideSourceUrl(guide.url)" :href="guideSourceUrl(guide.url)" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">查看原帖 ↗</a></footer>
      </article>
    </div>
  </section>
</template>
<style scoped>
.challenge-guides > p { margin: 12px 0; line-height: 1.8; }
.boss-filter { display: flex; align-items: center; gap: 12px; margin: 16px 0; color: var(--text-muted); font-size: 13px; white-space: nowrap; }
.boss-filter-menu { max-width:100%; min-width:0; }.boss-filter-menu :deep(.menu-select-trigger) { min-height:34px; min-width:0; max-width:100%; font-size:13px; }
.challenge-guide-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.challenge-guide-card.has-lineups { grid-column: 1 / -1; }
.challenge-guide-title { display: flex; gap: 12px; align-items: center; }
.challenge-guide-title h4 { margin: 8px 0; font-size: 15px; font-weight: 600; line-height: 1.6; }
.challenge-guide-card > p { line-height: 1.8; font-size: 13px; color: var(--text-muted); margin: 12px 0; }
.challenge-guide-card details { font-size: 13px; color: var(--text-muted); }
.challenge-guide-card summary { cursor: pointer; }
.challenge-guide-card footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: 16px; }
.challenge-guide-card a { color: var(--accent); text-decoration: none; font-size: 13px; }
.challenge-badges { display: flex; gap: 8px; align-items: center; }
@media(max-width:720px) { .challenge-guide-list { grid-template-columns: minmax(0,1fr); } .boss-filter { flex-wrap: wrap; } }
</style>
