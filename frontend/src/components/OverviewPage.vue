<script setup>
import { computed, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import GameIcon from './GameIcon.vue'
import GameArt from './GameArt.vue'
import HRail from './HRail.vue'
import RingGauge from './RingGauge.vue'
import BarChart from './BarChart.vue'
import MenuSelect from './MenuSelect.vue'
import { gameStyle, summaryFor, upcomingEvents, recentNews, formatTime } from '../dashboard.js'
import { DAY_MS, parseBeijingTime } from '../calendar.js'
import { sourceForGame } from '../source-status.js'
import { friendlyDataError } from '../cloud-display.js'
import { share } from '../chart-math.js'
import { vParallax, vPop, vReveal, vSpotlight } from '../motion.js'

const props = defineProps({ games: { type: Array, default: () => [] }, snapshots: { type: Object, default: () => ({}) },
  accounts: { type: Object, default: () => ({}) }, readErrors: { type: Object, default: () => ({}) }, refreshErrors: { type: Object, default: () => ({}) },
  refreshing: { type: Object, default: () => ({}) }, collection: { type: Array, default: () => [] }, now: { type: Number, required: true }, loading: Boolean, refreshLabel: {type:String,default:'刷新数据'} })
const emit = defineEmits(['navigate', 'refresh'])
const newsFilter = ref('')
const sourceFilter = ref('')
const newsGameOptions = computed(() => [{ value: '', label: '全部游戏' }, ...props.games.map(g => ({ value: g.game_id, label: g.display_name }))])
const newsSourceOptions = [{ value: '', label: '全部来源' }, { value: 'bilibili', label: 'B站官方动态' }]
const cards = computed(() => props.games.map(game => ({ ...game, style: gameStyle(game.game_id), summary: summaryFor(game, props.snapshots[game.game_id]), auth: props.accounts[game.game_id], source: sourceForGame(game.game_id, props.collection) })))
const events = computed(() => upcomingEvents(props.games, props.snapshots, props.now))
const nearEvents = computed(() => events.value.filter(event => event.remainingDays <= 3))
const fullGames = computed(() => cards.value.filter(card => card.summary.hasStamina && card.summary.percent >= 90 && !card.summary.stale && !props.readErrors[card.game_id] && (!card.source || card.source.state === 'ok')))
const allNews = computed(() => recentNews(props.games, props.snapshots))
const news = computed(() => allNews.value.filter(item => (!newsFilter.value || item.gameId === newsFilter.value) && (!sourceFilter.value || item.source === sourceFilter.value)).slice(0, 6))
const anyRefreshing = computed(() => Object.values(props.refreshing).some(Boolean))
const notices = computed(() => cards.value.filter(g => props.readErrors[g.game_id] || props.refreshErrors[g.game_id]))
const dateLabel = computed(() => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long' }).format(props.now))

// How far through its window an event is (0–1); unknown without a start time.
function elapsed(event) {
  const start = parseBeijingTime(event.start_at || event.start_date)
  return start == null || event.upcoming ? null : share(props.now - start, event.endTime - start)
}
const next = computed(() => events.value[0] || null)
const nextStyle = computed(() => next.value ? gameStyle(next.value.gameId) : null)
// Deadlines per Beijing calendar day for the coming week, today first.
const beijingDay = time => Math.floor((time + 8 * 3600000) / DAY_MS)
const weekday = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', weekday: 'short' })
const week = computed(() => {
  const today = beijingDay(props.now)
  return Array.from({ length: 7 }, (_, i) => ({
    label: i === 0 ? '今天' : i === 1 ? '明天' : weekday.format(props.now + i * DAY_MS),
    value: events.value.filter(event => beijingDay(event.endTime) === today + i).length,
  }))
})
const weekTotal = computed(() => week.value.reduce((sum, day) => sum + day.value, 0))

function status(card) {
  if (props.readErrors[card.game_id]) return '读取异常'
  if (card.auth?.state === 'expired') return '登录已失效'
  if (card.summary.stale) return '待更新'
  if (card.game_id === 'league_of_legends') return '本机客户端'
  return ({ connected: '已登录', configured: '已登录', unconfigured: '未登录' })[card.auth?.state] || (card.credentials_configured ? '已登录' : '未登录')
}
const METRIC_UNITS = { stats: '%', gacha: '抽' }
const PLATFORMS = { league_of_legends: 'PC / 国服', endfield: '官服 / 鹰角通行证' }
const platform = id => PLATFORMS[id] || '手游 / 社区数据'
function metricLabel(card) {
  return ({ stamina: card.style.resource, gacha: '距上次 6★' })[card.summary.metric] || '最近对局胜率'
}
function resourceNote(card) {
  const s = card.summary
  if (s.metric === 'gacha') return `特许寻访 · ${s.value == null ? '等待寻访记录更新' : s.pityStatus === 'exact' ? '按连续记录计算' : '有缺口或免费寻访，为最少值'}`
  // 胜率不含重开和结果未知的对局；分母和总场数不同时写出来，免得按总场数去算。
  if (!s.hasStamina) return s.totalGames == null ? '等待对局数据' : `最近 ${s.totalGames} 场 · ${s.wins == null ? '胜场未知' : `${s.wins} 胜`}${s.decided != null && s.decided !== s.totalGames ? ` · 胜率按 ${s.decided} 场计` : ''}`
  if (s.percent >= 100) return '体力已满'
  if (s.expectedFullAt) return `预计 ${formatTime(s.expectedFullAt)} 回满`
  return '回满时间未知'
}
// The ring shows stamina against its cap, or a win rate out of 100.
const ring = card => card.summary.metric === 'stamina' ? { value: card.summary.value, max: card.summary.maximum } : card.summary.metric === 'stats' ? { value: card.summary.value, max: 100 } : null
const accentVars = style => ({ '--game-color': style.color, '--game-accent': style.color, '--game-vivid': style.vivid, '--game-vivid-2': style.vivid2 })
</script>

<template>
  <div class="overview-page">
    <div class="ov-top">
      <section v-parallax class="ov-hero">
        <GameArt variant="orbit" />
        <div class="ov-hero-copy">
          <h1 class="ov-title">今日总览</h1>
          <p class="ov-date">{{ dateLabel }}</p>
          <ul class="ov-stats">
            <li><b v-pop>{{ games.length }}</b><span>游戏</span></li>
            <li><b v-pop>{{ events.length }}</b><span>进行中的活动</span></li>
            <li :class="{ hot: nearEvents.length }"><b v-pop>{{ nearEvents.length }}</b><span>3 天内截止</span></li>
          </ul>
          <p v-if="fullGames.length" class="ov-alert"><AppIcon name="clock" :size="16" />{{ fullGames.map(g => g.display_name).join('、') }}体力已达 90%</p>
          <div class="ov-hero-actions">
            <button class="ui-button ov-refresh" :disabled="loading || anyRefreshing || !games.length" @click="emit('refresh')"><AppIcon name="refresh" :size="15" :class="{ spinning: anyRefreshing }" /><span :class="{ 't-shimmer': anyRefreshing }">{{ anyRefreshing ? '刷新中…' : refreshLabel }}</span></button>
            <button class="text-link ov-calendar-link" @click="emit('navigate', 'calendar')">查看日历 <AppIcon name="arrow" :size="15" /></button>
          </div>
        </div>
      </section>

      <button v-if="next" class="ov-next" :style="accentVars(nextStyle)" @click="emit('navigate', 'calendar', next.gameId)">
        <span class="ov-next-head"><span class="ov-kicker">最近截止</span><span class="ov-next-game"><GameIcon class="ov-next-mark" :game-id="next.gameId" :name="next.gameName" />{{ next.gameName }}</span></span>
        <strong class="ov-next-name">{{ next.name }}</strong>
        <span class="ov-next-foot">
          <span class="ov-next-days"><b>{{ next.remainingDays }}</b><small>{{ next.upcoming ? '天 · 未开始' : '天后结束' }}</small></span>
          <RingGauge v-if="elapsed(next) != null" :value="Math.round(elapsed(next) * 100)" :max="100" label="活动已进行" :size="64" :stroke="7" :color="nextStyle.vivid"><small class="ov-next-pct">{{ Math.round(elapsed(next) * 100) }}%</small></RingGauge>
        </span>
        <span class="ov-next-end">{{ next.category || '限时活动' }} · {{ formatTime(next.end_at) }} 截止<span v-if="next.stale"> · 待更新</span></span>
      </button>
      <section v-else class="ov-next is-empty"><span class="ov-kicker">最近截止</span><p>{{ loading ? '加载中…' : '暂无临近截止的活动。' }}</p></section>

      <section class="ov-week cap-card">
        <div class="ov-card-head"><h2>未来 7 天截止</h2><span class="ov-card-meta">{{ weekTotal }} 项</span></div>
        <BarChart v-if="weekTotal" :items="week" label="未来 7 天每天截止的活动数" unit=" 项" :highlight="week[0].value ? 0 : -1" :height="96" color="var(--accent-fill)" />
        <p v-else class="ov-empty">{{ loading ? '加载中…' : '这一周没有活动截止。' }}</p>
      </section>
    </div>

    <div v-for="game in notices" :key="game.game_id" class="inline-warning" role="status"><strong>{{ game.display_name }}</strong> · {{ friendlyDataError(refreshErrors[game.game_id] || readErrors[game.game_id],accounts[game.game_id]?.state) }}</div>

    <div class="section-heading ov-section"><h2>我的游戏</h2></div>
    <div class="game-summary-grid" :class="{ many: cards.length > 3 }" :style="{ '--cards': Math.min(cards.length, 4) }">
      <button v-for="(card, index) in cards" :key="card.game_id" v-spotlight v-reveal class="game-summary game-theme t-item t-glare" :style="{ ...accentVars(card.style), '--i': index }" @click="emit('navigate', 'game', card.game_id)">
        <div class="summary-header"><GameIcon class="game-monogram" :game-id="card.game_id" :name="card.display_name" /><div class="game-identity"><h3>{{ card.display_name }}</h3><p>{{ card.platform || platform(card.game_id) }}</p></div><span class="summary-state" :class="{ warn: card.summary.stale || card.auth?.state === 'expired' || readErrors[card.game_id] || card.source?.tone === 'danger' }"><i></i>{{ status(card) }}</span></div>
        <div class="summary-body">
          <RingGauge v-if="ring(card)" class="summary-ring" :value="ring(card).value" :max="ring(card).max" :label="metricLabel(card)" :size="92" :stroke="9" :color="card.style.vivid"><span class="ring-pct">{{ card.summary.percent == null ? '—' : `${Math.round(card.summary.percent)}%` }}</span></RingGauge>
          <div class="summary-metric"><p>{{ metricLabel(card) }}</p><div class="summary-number" v-pop>{{ card.summary.metric === 'gacha' && card.summary.pityStatus === 'lower_bound' && card.summary.value != null ? '≥' : '' }}{{ card.summary.value ?? '—' }}<small>{{ card.summary.hasStamina ? `/ ${card.summary.maximum ?? '—'}` : METRIC_UNITS[card.summary.metric] }}</small></div><p class="summary-note">{{ resourceNote(card) }}</p></div>
        </div>
        <div class="summary-account"><span>{{ card.summary.nickname || '暂无账号数据' }}<small v-if="card.summary.level != null">Lv.{{ card.summary.level }}</small></span><span class="summary-updated">{{ card.summary.fetchedAt ? `更新于 ${formatTime(card.summary.fetchedAt)}` : '尚未更新' }}</span><AppIcon name="arrow" :size="15" /></div>
      </button>
    </div>
    <div v-if="!games.length && loading" class="game-summary-grid" aria-busy="true"><span class="sr-only">加载中…</span><div v-for="n in 3" :key="n" class="game-summary is-skeleton" aria-hidden="true"><span class="t-skel-block" style="width:42%;height:16px"></span><span class="t-skel-block" style="width:36%;height:30px;margin-top:18px"></span><span class="t-skel-block" style="width:100%;height:6px;margin-top:12px"></span><span class="t-skel-block" style="width:64%;height:12px;margin-top:16px"></span></div></div>
    <p v-else-if="!games.length" class="empty-page">暂无已启用的游戏。</p>

    <section v-reveal class="ov-events">
      <div class="section-heading ov-section"><h2>临近截止</h2><button class="text-link" @click="emit('navigate', 'calendar')">全部活动 <AppIcon name="arrow" :size="15" /></button></div>
      <p v-if="!events.length" class="empty-page ov-panel">{{ loading ? '加载中…' : '暂无临近截止的活动。' }}</p>
      <HRail v-else label="临近截止">
        <button v-for="event in events.slice(0, 12)" :key="event.id" class="event-card" :class="{ urgent: event.remainingDays <= 3 }" :style="accentVars(gameStyle(event.gameId))" @click="emit('navigate', 'calendar', event.gameId)">
          <span class="event-card-game"><i aria-hidden="true"></i>{{ event.gameName }}<span>{{ event.category || '限时活动' }}</span></span>
          <strong class="event-card-name">{{ event.name }}</strong>
          <span class="event-card-days"><small>剩</small><b>{{ event.remainingDays }}</b><small>天</small><span v-if="event.upcoming" class="deadline-label">未开始</span><span v-else-if="event.remainingDays <= 3" class="deadline-label urgent">即将截止</span></span>
          <span v-if="elapsed(event) != null" class="event-card-track" aria-hidden="true"><i :style="{ width: `${Math.round(elapsed(event) * 100)}%` }"></i></span>
          <span class="event-card-end">{{ formatTime(event.end_at) }} 截止<span v-if="event.stale"> · 待更新</span></span>
        </button>
      </HRail>
    </section>

    <section v-reveal class="ov-news cap-card">
      <div class="section-heading"><h2>公告与资讯</h2><div class="news-filters"><MenuSelect v-model="newsFilter" label="公告游戏筛选" :options="newsGameOptions" /><MenuSelect v-model="sourceFilter" label="资讯来源" align="end" :options="newsSourceOptions" /></div></div>
      <div class="news-list"><p v-if="!news.length" class="empty-page">{{ loading ? '加载中…' : '暂无公告。' }}</p><article v-for="(item, i) in news" :key="`${item.gameId}:${item.title}:${i}`" class="news-summary t-row" :style="accentVars(gameStyle(item.gameId))"><GameIcon class="news-mark" :game-id="item.gameId" :name="item.gameName" /><div class="news-copy"><a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title }} <span>↗</span></a><p v-else>{{ item.title }}</p><div class="news-source">{{ item.gameName }}<span> / {{ item.source_name || (item.capability === 'news' ? '资讯' : '官方公告') }}</span><time v-if="item.published_at">{{ formatTime(item.published_at) }}</time></div></div></article></div>
    </section>
    <footer class="overview-footer"><span>时间均为北京时间</span></footer>
  </div>
</template>

<style scoped>
/* Bento top row: the hero spans two rows; the next deadline and the week sit beside it. */
.ov-top { display:grid; grid-template-columns:minmax(0, 1.75fr) minmax(280px, 1fr); grid-template-rows:auto auto; gap:20px; }
.ov-hero { position:relative; grid-row:span 2; min-height:340px; overflow:hidden; isolation:isolate; padding:30px 32px; border-radius:var(--radius-card); color:#fff; background:radial-gradient(120% 140% at 0% 0%, #2a2f4d 0%, #151827 46%, #0f111a 100%); box-shadow:0 1px 2px rgba(20, 24, 40, .2), 0 28px 60px -30px rgba(15, 17, 26, .7); }
.ov-hero::after { content:''; position:absolute; inset:0; z-index:-1; opacity:.18; mix-blend-mode:overlay; pointer-events:none; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"); }
.ov-hero :deep(.game-art) { z-index:-1; }
.ov-hero-copy { position:relative; display:flex; flex-direction:column; align-items:flex-start; height:100%; max-width:min(440px, 62%); }
.ov-title { display:inline-flex; align-items:center; padding:3px 12px; border-radius:999px; background:rgba(255, 255, 255, .12); border:1px solid rgba(255, 255, 255, .16); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); font-size:13px; line-height:20px; font-weight:500; letter-spacing:0; }
.ov-date { margin-top:18px; font-size:40px; line-height:46px; font-weight:600; letter-spacing:-.03em; text-wrap:balance; }
.ov-stats { display:flex; flex-wrap:wrap; gap:10px 28px; margin-top:22px; }
.ov-stats li { display:grid; gap:2px; }
.ov-stats b { font-size:28px; line-height:32px; font-weight:600; letter-spacing:-.02em; font-variant-numeric:proportional-nums; }
.ov-stats span { color:rgba(255, 255, 255, .68); font-size:12px; }
.ov-stats li.hot b { color:#ffd27a; }
.ov-alert { display:inline-flex; align-items:center; gap:8px; margin-top:18px; padding:6px 12px; border-radius:999px; background:rgba(255, 210, 122, .14); color:#ffe2a6; font-size:13px; }
.ov-hero-actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px 16px; margin-top:auto; padding-top:24px; }
.ov-refresh { background:rgba(255, 255, 255, .14); border-color:rgba(255, 255, 255, .22); color:#fff; box-shadow:inset 0 1px 0 rgba(255, 255, 255, .18); -webkit-backdrop-filter:blur(14px) saturate(160%); backdrop-filter:blur(14px) saturate(160%); }
@media(hover:hover) and (pointer:fine) { .ov-refresh:hover:not(:disabled) { background:rgba(255, 255, 255, .22); border-color:rgba(255, 255, 255, .3); color:#fff; } }
.ov-refresh .t-shimmer { background-image:linear-gradient(90deg, rgba(255, 255, 255, .6) 0%, #fff 45%, rgba(255, 255, 255, .6) 65%); }
.ov-calendar-link { color:rgba(255, 255, 255, .86); }
@media(hover:hover) and (pointer:fine) { .ov-calendar-link:hover { color:#fff; } }
.ov-hero :focus-visible { outline-color:#fff; }

/* The one saturated card in the row: the deadline that comes first, in its game's colours. */
.ov-next { position:relative; display:flex; flex-direction:column; gap:10px; min-width:0; padding:22px; overflow:hidden; text-align:left; border:0; border-radius:var(--radius-card); color:var(--text); background:linear-gradient(150deg, color-mix(in srgb, var(--game-vivid) 26%, var(--card-bg)), color-mix(in srgb, var(--game-vivid-2) 16%, var(--card-bg)) 70%); box-shadow:var(--card-shadow), inset 0 0 0 1px color-mix(in srgb, var(--game-vivid) 22%, transparent); transition:transform var(--duration-spring) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-smooth-out); }
.ov-next::before { content:''; position:absolute; right:-40px; top:-60px; width:200px; height:200px; border-radius:50%; background:radial-gradient(circle, color-mix(in srgb, var(--game-vivid) 45%, transparent), transparent 70%); pointer-events:none; }
@media(hover:hover) and (pointer:fine) { button.ov-next:hover { transform:translateY(-2px); box-shadow:var(--card-hover-shadow), 0 18px 40px -22px var(--game-vivid), inset 0 0 0 1px color-mix(in srgb, var(--game-vivid) 30%, transparent); } }
button.ov-next:active { transform:scale(var(--scale-small)); }
.ov-next-head { position:relative; display:flex; align-items:center; justify-content:space-between; gap:8px; }
.ov-kicker { color:var(--text-muted); font-size:12px; font-weight:500; }
.ov-next-game { display:inline-flex; align-items:center; gap:6px; padding:2px 10px 2px 3px; border-radius:999px; background:var(--glass-strong); color:var(--text-body); font-size:12px; font-weight:500; }
.ov-next-mark { width:20px; height:20px; border-radius:999px; font-size:11px; }
.ov-next-name { position:relative; font-size:18px; line-height:26px; font-weight:600; letter-spacing:-.01em; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.ov-next-foot { position:relative; display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-top:auto; }
.ov-next-days { display:flex; align-items:baseline; gap:6px; }
.ov-next-days b { font-size:44px; line-height:46px; font-weight:600; letter-spacing:-.04em; font-variant-numeric:proportional-nums; }
.ov-next-days small { color:var(--text-muted); font-size:13px; }
.ov-next-pct { font-size:12px; font-weight:600; color:var(--text); }
.ov-next-end { position:relative; color:var(--text-muted); font-size:12px; }
.ov-next.is-empty { justify-content:center; background:var(--card-bg); box-shadow:var(--card-shadow); border:1px solid var(--card-border); }
.ov-next.is-empty p { color:var(--text-muted); font-size:13px; }

.ov-week { display:flex; flex-direction:column; gap:10px; }
.ov-card-head { display:flex; align-items:baseline; justify-content:space-between; gap:8px; }
.ov-card-head h2 { font-size:15px; line-height:22px; font-weight:600; }
.ov-card-meta { color:var(--text-faint); font-size:12px; }
.ov-empty { margin:auto 0; color:var(--text-muted); font-size:13px; }

.ov-section { margin:32px 0 14px; }
/* Up to four games in a row; four fall to 2 × 2 before they get too narrow. */
.game-summary-grid { display:grid; grid-template-columns:repeat(var(--cards, 3),minmax(0,1fr)); gap:20px; }
@media(max-width:1280px) { .game-summary-grid.many { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.game-summary { position:relative; display:flex; flex-direction:column; text-align:left; border:1px solid var(--card-border); border-radius:var(--radius-card); padding:20px; background:var(--card-bg); color:var(--text); min-width:0; overflow:hidden; box-shadow:var(--card-shadow); transition:transform var(--duration-spring) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-smooth-out), border-color var(--duration-quick) var(--ease-smooth-out); cursor:pointer; }
/* A faint wash of the game colour in the corner. */
.game-summary::before { content:''; position:absolute; right:-70px; top:-90px; width:220px; height:220px; border-radius:50%; background:radial-gradient(circle, color-mix(in srgb, var(--game-vivid) 22%, transparent), transparent 70%); pointer-events:none; }
.game-summary:focus-visible { border-color:var(--game-color); outline-color:var(--game-color); }
@media(hover:hover) and (pointer:fine) { .game-summary:hover { transform:translateY(-3px); box-shadow:var(--card-hover-shadow), 0 20px 44px -28px var(--game-vivid); } }
.game-summary:active { transform:scale(var(--scale-small)); }.game-summary.is-skeleton { pointer-events:none; }
.summary-header { position:relative; display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
.game-monogram { display:grid; place-items:center; flex-shrink:0; width:40px; height:40px; border-radius:12px; color:var(--game-color); font-size:18px; box-shadow:0 6px 14px -8px var(--game-vivid); }
.game-identity { min-width:0; flex:1; }.game-identity h3 { font-size:16px; line-height:22px; font-weight:600; white-space:nowrap; }.game-identity p { color:var(--text-faint); font-size:12px; line-height:18px; }
.summary-state { display:flex; align-items:center; gap:5px; flex-shrink:0; padding:1px 10px 1px 8px; border-radius:999px; background:var(--success-bg); color:var(--success); font-size:12px; font-weight:500; line-height:22px; }.summary-state.warn { background:var(--stale-bg); color:var(--stale-text); }.summary-state i { width:6px; height:6px; background:currentColor; border-radius:50%; }
.summary-body { position:relative; display:flex; align-items:center; gap:18px; margin:20px 0 18px; }
.ring-pct { font-size:15px; font-weight:600; letter-spacing:-.01em; }
.summary-metric { min-width:0; flex:1; }
.summary-metric p { font-size:12px; color:var(--text-muted); }
.summary-number { margin-top:2px; font-size:32px; line-height:38px; font-weight:600; letter-spacing:-.03em; font-variant-numeric:proportional-nums; white-space:nowrap; }.summary-number small { font-size:14px; color:var(--text-muted); font-weight:500; margin-left:4px; letter-spacing:0; }
.summary-note { margin-top:2px; font-size:12px; line-height:18px; color:var(--text-muted); text-wrap:pretty; }
.summary-account { position:relative; display:flex; align-items:center; gap:6px; margin-top:auto; padding-top:14px; border-top:1px solid var(--border); color:var(--text); font-size:13px; font-weight:500; }.summary-account>span:first-child { min-width:0; margin-right:auto; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.summary-account small { margin-left:6px; color:var(--text-muted); font-size:12px; font-weight:400; }.summary-updated { color:var(--text-faint); font-size:12px; font-weight:400; white-space:nowrap; }.summary-account svg { color:var(--text-faint); transition:transform var(--duration-medium) var(--ease-smooth-out), color var(--duration-quick) var(--ease-smooth-out); }
@media(hover:hover) and (pointer:fine) { .game-summary:hover .summary-account svg { color:var(--game-color); transform:translateX(3px); } }

/* Horizontal rail of deadline cards; the urgent ones carry a warm wash. */
.ov-events .h-rail { --rail-pad:4px; --rail-pad-block:10px; --rail-gap:14px; }
.event-card { position:relative; display:flex; flex-direction:column; gap:8px; width:268px; min-height:178px; padding:18px; text-align:left; border:1px solid var(--card-border); border-radius:var(--radius-tile); background:var(--card-bg); color:var(--text); box-shadow:var(--card-shadow); overflow:hidden; transition:transform var(--duration-spring) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-smooth-out); }
.event-card::before { content:''; position:absolute; inset:0 0 auto; height:3px; background:linear-gradient(90deg, var(--game-vivid), var(--game-vivid-2)); }
.event-card.urgent { background:linear-gradient(170deg, color-mix(in srgb, var(--game-vivid) 12%, var(--card-bg)), var(--card-bg) 60%); }
@media(hover:hover) and (pointer:fine) { .event-card:hover { transform:translateY(-3px); box-shadow:var(--card-hover-shadow); } }
.event-card:active { transform:scale(var(--scale-small)); }
.event-card-game { display:flex; align-items:center; gap:6px; color:var(--text-body); font-size:12px; font-weight:500; }
.event-card-game i { width:7px; height:7px; border-radius:50%; background:var(--game-vivid); box-shadow:0 0 0 3px color-mix(in srgb, var(--game-vivid) 22%, transparent); }
.event-card-game span { margin-left:auto; color:var(--text-faint); font-weight:400; }
.event-card-name { font-size:15px; line-height:22px; font-weight:600; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.event-card-days { display:flex; align-items:baseline; gap:4px; margin-top:auto; }
.event-card-days b { font-size:30px; line-height:34px; font-weight:600; letter-spacing:-.03em; font-variant-numeric:proportional-nums; }
.event-card-days small { color:var(--text-muted); font-size:12px; }
.event-card-days .deadline-label { margin-left:auto; }
.deadline-label { flex-shrink:0; padding:1px 9px; border-radius:999px; background:var(--overlay-3); font-size:12px; font-weight:500; line-height:20px; color:var(--text-body); white-space:nowrap; }.deadline-label.urgent { background:var(--stale-bg); color:var(--stale-text); }
.event-card-track { height:4px; border-radius:999px; background:var(--track); overflow:hidden; }
.event-card-track i { display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg, var(--game-vivid), var(--game-vivid-2)); }
.event-card-end { color:var(--text-faint); font-size:12px; }
.ov-panel { border-radius:var(--radius-card); background:var(--card-bg); box-shadow:var(--card-shadow); }

.ov-news { margin-top:32px; padding:22px 24px 12px; }
.ov-news .section-heading { margin-bottom:8px; }
.news-filters { display:flex; gap:8px; margin-left:auto; min-width:0; }
.news-list { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(420px, 100%), 1fr)); column-gap:28px; }
.news-summary { display:flex; align-items:center; gap:12px; min-width:0; padding:12px 8px; margin:0 -8px; border-bottom:1px solid var(--border); border-radius:var(--radius-control); }
.news-mark { width:34px; height:34px; border-radius:10px; font-size:14px; }
.news-copy { flex:1; min-width:0; }
.news-summary a,.news-summary .news-copy>p { display:block; color:var(--text); text-decoration:none; font-size:14px; font-weight:500; line-height:20px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.news-summary a span { color:var(--text-faint); }
.news-source { display:flex; align-items:center; gap:6px; margin-top:2px; color:var(--text-muted); font-size:12px; line-height:18px; min-width:0; }.news-source>span { color:var(--text-faint); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.news-source time { margin-left:auto; flex-shrink:0; color:var(--text-faint); }
@media(hover:hover) and (pointer:fine) { .news-summary a:hover,.news-summary a:hover span { color:var(--accent); } }
.overview-footer { margin-top:20px; display:flex; justify-content:space-between; gap:12px; color:var(--text-faint); font-size:12px; }.overview-footer>span { display:flex; align-items:center; gap:7px; }

@media(max-width:1180px) { .ov-top { grid-template-columns:repeat(2, minmax(0, 1fr)); }.ov-hero { grid-column:1 / -1; grid-row:auto; } }
@media(max-width:940px) { .game-summary-grid,.game-summary-grid.many { grid-template-columns:1fr; } }
@media(max-width:720px) { .ov-top { grid-template-columns:1fr; gap:14px; }.ov-hero { padding:24px 20px; min-height:300px; }.ov-hero-copy { max-width:100%; }.ov-date { font-size:32px; line-height:38px; }.ov-hero :deep(.game-art) { opacity:.42; }.ov-hero :deep(.game-art svg) { inset:auto -38% -22% auto; width:150%; height:auto; aspect-ratio:3 / 2; }.event-card { width:236px; }.ov-news { padding:18px 16px 8px; } }
@media(max-width:600px) { .summary-number { font-size:28px; line-height:34px; }.overview-footer { flex-wrap:wrap; } }
@media(max-width:400px) { .ov-news .section-heading { flex-wrap:wrap; gap:8px; }.news-filters { width:100%; margin-left:0; } }
@media(prefers-reduced-motion:reduce) { .game-summary:active,.event-card:active,button.ov-next:active { transform:none; } }
</style>
