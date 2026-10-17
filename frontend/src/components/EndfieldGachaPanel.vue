<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { isCloudMode } from '../http-client.js'
import { fetchedLabel } from '../time.js'
import { exportRecords, getRecords, pityParts, pullDate, pullDay, rarityLabel } from '../endfield-gacha-api.js'
import { gachaPools, latestPoolIndex, poolSpans, poolTotal, recentSixStars, sixPullsParts } from '../endfield-gacha-summary.js'
import { vReveal } from '../motion.js'
import AppIcon from './AppIcon.vue'
import BarChart from './BarChart.vue'
import DonutChart from './DonutChart.vue'
import EndfieldArtwork from './EndfieldArtwork.vue'
import HRail from './HRail.vue'
import InfoHint from './InfoHint.vue'
import MenuSelect from './MenuSelect.vue'

const cloudMode = isCloudMode()
const props = defineProps({ snap: { type: Object, default: null }, accountId: { type: String, default: '' }, imageMode:Boolean })
const summary = computed(() => props.snap?.payload?.schema_version === 1 ? props.snap.payload : null)
const report = computed(() => summary.value?.report?.schema_version === 1 ? summary.value.report : null)
const show = value => value == null || value === '' ? '未知' : value
const pools = computed(() => gachaPools(summary.value))
const fetchedAt = computed(() => fetchedLabel(props.snap?.fetched_at))
const poolOptions = computed(() => [{ value: '', label: '全部卡池' }, ...pools.value.map(pool => ({ value: pool.key, label: pool.label }))])
const opened = ref(false), recordPool = ref(''), records = ref([]), total = ref(0), offset = ref(0), busy = ref(false), message = ref('')
const PAGE = 50
let generation = 0

// Rarity colours follow the chart order (6★ takes the game colour, 5★ the second series);
// 4★ is the quiet majority and an unknown share stays on the track colour.
const RARITY = [
  { field: 'six_star', label: '6★', series: 'var(--eg-six)' },
  { field: 'five_star', label: '5★', series: 'var(--eg-five)' },
  { field: 'four_star', label: '4★', series: 'var(--eg-four)' },
  { field: 'unknown_rarity', label: '未知 / 其他', series: 'var(--eg-unknown)' },
]
// Unknown rarity stays unknown; old snapshots do not prove a 4★ remainder.
const split = pool => RARITY.map(part => ({ label: part.label, count: pool[part.field], series: part.series }))
// All pools together: the report's own totals when it has them, else a sum only if every pool states the count.
const overall = computed(() => {
  if (!summary.value || !pools.value.length) return null
  const segments = RARITY.map(part => ({ label: part.label, value: report.value?.[part.field] ?? poolTotal(pools.value, part.field), color: part.series }))
  return segments.some(part => Number.isFinite(part.value)) ? segments : null
})
const grandTotal = computed(() => report.value?.total ?? summary.value?.total)
const tiles = computed(() => [
  { label: '6★ 记录', value: report.value?.six_star, tone: 'six' },
  { label: '5★ 记录', value: report.value?.five_star, tone: 'five' },
  { label: '免费寻访', value: report.value?.free, tone: '' },
])
const poolBars = computed(() => pools.value.map(pool => ({ label: pool.label, value: pool.total })))
const latestPool = computed(() => pools.value.length > 1 ? latestPoolIndex(pools.value) : -1)
const recent = computed(() => recentSixStars(pools.value, 12))
const pity = pool => pityParts(pool.since_last_six)
const spans = computed(() => poolSpans(pools.value.length))

async function load(start = 0) {
  if (props.imageMode) return
  if (!props.accountId) return
  const request = ++generation
  busy.value = true; message.value = ''
  try {
    const page = await getRecords(recordPool.value, start, PAGE)
    if (request !== generation) return
    records.value = page.records || []; total.value = page.total || 0; offset.value = start
  } catch (error) {
    if (request === generation) message.value = error.message
  } finally {
    if (request === generation) busy.value = false
  }
}
// 逐条记录只在展开时读取本机账本。
watch(() => [props.accountId, recordPool.value, opened.value], () => { ++generation; records.value = []; total.value = 0; offset.value = 0; busy.value = false; message.value = ''; if (!props.imageMode && opened.value) load(0) })
onBeforeUnmount(() => { ++generation })
const range = computed(() => total.value ? `${offset.value + 1}–${Math.min(offset.value + PAGE, total.value)} / ${total.value}` : '0 条')

async function download() {
  const request = ++generation, account = props.accountId
  busy.value = true; message.value = ''
  try {
    const data = await exportRecords()
    if (request !== generation || account !== props.accountId) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url; link.download = `endfield-gacha-${props.accountId}.json`; link.click(); URL.revokeObjectURL(url)
    message.value = `已导出 ${data.records?.length || 0} 条记录。`
  } catch (error) {
    if (request === generation) message.value = error.message
  } finally {
    if (request === generation) busy.value = false
  }
}
</script>

<template>
  <section class="endfield-gacha" :class="{ 'is-image': imageMode, 'is-split': !!overall }" aria-labelledby="endfield-gacha-title">
    <div v-reveal class="eg-card eg-hero">
      <header class="eg-head">
        <div class="gacha-heading"><h2 id="endfield-gacha-title">寻访记录</h2></div><span v-if="snap?.stale && !imageMode" class="badge badge-stale">待更新</span>
        <InfoHint v-if="!imageMode" :text="cloudMode ? '官方记录有查询时限，云端档案保留已同步数据；撤销授权会禁止读取。' : '官方可查询约 90 天记录；同步后保存在本机，退出登录不会删除本机记录。'" />
        <span class="cap-meta"><template v-if="summary && fetchedAt">同步于 {{ fetchedAt }}</template><button v-if="!imageMode" type="button" class="ui-button small-button" :disabled="busy || !accountId" @click="download">导出记录</button></span>
      </header>
      <p v-if="!accountId && !imageMode" class="notice">登录终末地后，点「刷新数据」开始同步寻访记录。</p>
      <p v-else-if="!summary" class="notice">尚未同步寻访记录，点「刷新数据」开始同步。</p>
      <template v-else>
        <div class="eg-numbers">
          <div class="eg-total"><span class="k">已记录寻访</span><strong class="eg-big">{{ show(grandTotal) }}<small v-if="grandTotal != null">抽</small></strong></div>
          <ul class="eg-tiles">
            <li v-for="tile in tiles" :key="tile.label" :class="tile.tone"><span class="k">{{ tile.label }}</span><strong>{{ show(tile.value) }}</strong></li>
          </ul>
        </div>
        <div v-if="report" class="gacha-coverage"><span>已知记录缺口 <b>{{ report.gaps ?? '未知' }}</b></span><span>同步状态 <b>{{ report.pending === true ? '部分待同步' : report.pending === false ? '本轮同步完成' : '未知' }}</b></span><span>记录内准确区间均值 <b>{{ report.average_exact_pulls == null ? '未知' : `${report.average_exact_pulls} 抽` }}</b></span></div>
        <p v-if="report?.average_exact_pulls != null" class="notice">均值仅来自当前展示历史中 {{ report.known_exact_intervals }} 个抽数准确的 6★ 区间，不代表完整生涯或未来出货。</p>
        <p v-if="summary.complete === false" class="notice warn" role="status">还有未同步完的记录，下次刷新会接着同步。</p>
        <p v-else-if="summary.complete !== true" class="notice warn" role="status">当前记录完整性未知，请留意各卡池的记录范围。</p>
      </template>
    </div>

    <template v-if="summary">
      <div v-if="overall" v-reveal class="eg-card eg-rarity">
        <h3 class="eg-title">稀有度占比</h3>
        <DonutChart :segments="overall" label="全部卡池的稀有度占比" unit=" 抽" :size="148" :stroke="18">
          <span class="donut-total"><strong>{{ show(grandTotal) }}</strong><small v-if="grandTotal != null">抽</small></span>
        </DonutChart>
      </div>

      <template v-if="pools.length">
        <div v-reveal class="eg-card eg-totals" :class="{ 'is-wide': imageMode || !recent.length }">
          <h3 class="eg-title">各卡池抽数<span v-if="latestPool >= 0" class="eg-sub">高亮为最近寻访的卡池</span></h3>
          <BarChart :items="poolBars" label="各卡池的寻访抽数" unit=" 抽" :highlight="latestPool" :height="116" color="var(--eg-six)" />
        </div>
        <div v-if="recent.length && !imageMode" v-reveal class="eg-card eg-recent">
          <h3 class="eg-title">最近的 6★<span class="eg-sub">按获得时间，新的在前</span></h3>
          <HRail label="最近的 6★ 记录">
            <article v-for="(item, index) in recent" :key="`${item.pool_key}:${index}`" class="six-card" :class="{ latest: index === 0 }" :title="`${item.pool_name || item.pool_label} · ${pullDate(item.obtained_at)}`">
              <div class="six-top"><EndfieldArtwork role :name="item.name || '未知'" /><span v-if="index === 0" class="six-badge">最新</span></div>
              <strong class="six-name">{{ item.name || '未知' }}</strong>
              <b class="six-pulls"><template v-if="sixPullsParts(item)">{{ sixPullsParts(item).prefix }}{{ sixPullsParts(item).count }}<small>{{ sixPullsParts(item).unit }}</small></template><template v-else>未知</template></b>
              <span class="six-meta">{{ item.pool_name || item.pool_label }} · {{ pullDay(item.obtained_at) }}</span>
            </article>
          </HRail>
        </div>
      </template>

      <p v-if="!pools.length" class="empty eg-card">{{ cloudMode ? '本人档案' : '本机' }}暂无寻访记录。</p>
      <div v-else class="pool-grid">
        <article v-for="(pool,index) in pools" :key="pool.key" v-reveal class="pool-card" :class="{ 'is-latest': index === latestPool }" :style="{ '--span': spans[index] }">
          <header class="pool-head">
            <h3>{{ pool.label }}</h3>
            <span v-if="index === latestPool && !imageMode" class="pool-latest">最近寻访</span>
            <span v-if="pool.gaps" class="chip warn">{{ pool.pending ? '部分待同步' : '记录有缺口' }}<InfoHint v-if="!imageMode" align="end" text="记录不连续时，跨缺口的抽数以 ≥ 表示已知最少值。" /></span>
          </header>
          <div class="pity">
            <span class="k">距上次 6★<InfoHint v-if="!imageMode && pool.since_last_six?.status === 'lower_bound'" text="≥ 表示已知最少抽数。记录缺口、更早记录缺失或免费寻访会影响统计；免费寻访是否计入保底尚不确定。" /></span>
            <strong><template v-if="pity(pool)">{{ pity(pool).prefix }}{{ pity(pool).count }}<small>{{ pity(pool).unit }}</small></template><template v-else>未知</template></strong>
          </div>
          <div class="stack-bar" role="img" :aria-label="split(pool).map(part => `${part.label} ${part.count ?? '未知'}`).join('，')">
            <i v-for="part in split(pool).filter(part => part.count)" :key="part.label" :style="{ '--series': part.series, flex: part.count }" />
          </div>
          <ul class="legend">
            <li v-for="part in split(pool)" :key="part.label" :style="{ '--series': part.series }">{{ part.label }} <b>{{ part.count ?? '未知' }}</b></li>
            <li class="plain">共 <b>{{ pool.total }}</b> 抽</li>
            <li v-if="pool.free" class="plain">免费 <b>{{ pool.free }}</b></li>
          </ul>
          <p class="notice history-coverage">6★ 历史：最近 {{ pool.history_available }} 条 / 账本 {{ pool.history_total ?? '未知' }} 条<span v-if="pool.history_limit != null"> · 最多展示 {{ pool.history_limit }} 条</span></p>
          <p v-if="pool.history_truncated === true" class="notice">此处未展示全部 6★ 历史；展开逐条记录或导出完整已保存账本查看。</p><p v-else-if="pool.history_truncated == null" class="notice">历史覆盖范围未知。</p>
          <ul v-if="pool.history?.length" class="chip-list" :aria-label="`${pool.label}的 6★ 记录`">
            <li v-for="(item, index) in pool.history" :key="index" class="chip six" :title="`${item.pool_name || pool.label} · ${pullDate(item.obtained_at)}`">{{ item.name || '未知' }} <b>{{ sixPullsParts(item) ? `${sixPullsParts(item).prefix}${sixPullsParts(item).count} ${sixPullsParts(item).unit}` : '未知' }}</b></li>
          </ul>
        </article>
      </div>

      <details v-if="!imageMode" class="panel record-list" @toggle="opened = $event.target.open">
        <summary>逐条记录（北京时间）<AppIcon name="chevron" :size="14" class="t-disclosure" /></summary>
        <div class="panel-body">
          <div class="toolbar">
            <MenuSelect v-model="recordPool" label="卡池" :options="poolOptions" :disabled="busy" />
            <span class="count">{{ range }}</span>
            <button type="button" class="ui-button small-button" :disabled="busy || offset === 0" @click="load(Math.max(0, offset - PAGE))">上一页</button>
            <button type="button" class="ui-button small-button" :disabled="busy || offset + PAGE >= total" @click="load(offset + PAGE)">下一页</button>
          </div>
          <div v-if="records.length" class="table-scroll">
            <table class="data-table records">
              <thead><tr><th>时间</th><th>名称</th><th>稀有度</th><th>卡池</th></tr></thead>
              <tbody>
                <tr v-for="row in records" :key="`${row.pool_key}-${row.seq_id}`" :class="{ six: row.rarity === 6, five: row.rarity === 5 }">
                  <td class="when">{{ pullDate(row.gacha_ts) }}</td>
                  <td class="name">{{ row.name || '未知' }}<span v-if="row.is_free" class="chip">免费</span></td>
                  <td class="rarity">{{ rarityLabel(row.rarity) }}</td>
                  <td>{{ row.pool_name || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else-if="!busy" class="empty">暂无记录。</p>
        </div>
      </details>
    </template>
    <p v-if="message" class="notice eg-message" role="status">{{ message }}</p>
  </section>
</template>

<style scoped>
/* One bento: a hero on the game tone, the rarity ring, the per-pool bars, a rail of recent 6★, a card per pool, and the ledger.
   Bot images set only --game-accent, so every game colour has a static fallback. */
.endfield-gacha { --eg-six:var(--game-vivid,var(--game-endfield-vivid)); --eg-tone:var(--game-tone,var(--game-endfield-tone)); --eg-ink:var(--game-accent,var(--game-endfield)); --eg-five:var(--chart-2); --eg-four:color-mix(in srgb,var(--text-faint) 34%,var(--card-bg)); --eg-unknown:var(--border-strong);
  display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:16px; min-width:0; }
.endfield-gacha > * { grid-column:1 / -1; min-width:0; }
.eg-card { position:relative; padding:20px; border:1px solid var(--card-border); border-radius:var(--radius-card); background:var(--card-bg); box-shadow:var(--card-shadow); }
/* The hero is the page's feature block (mockup .gacha-overview): the game tone, ink labels, the total large. */
.eg-hero { display:grid; gap:14px; align-content:start; overflow:hidden; border-color:transparent; background:var(--eg-tone); box-shadow:none; }
.is-split .eg-hero { grid-column:span 7; }
.is-split .eg-rarity { grid-column:span 5; }
.eg-totals { grid-column:span 5; }
.eg-totals.is-wide { grid-column:1 / -1; }
.eg-recent { grid-column:span 7; overflow:hidden; }
.eg-head { display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px; min-height:32px; }
.gacha-heading h2 { margin:0; font-size:16px; line-height:24px; font-weight:600; letter-spacing:-.02em; }
.eg-head .cap-meta { margin-left:auto; gap:10px; }
.eg-head .cap-meta .ui-button { margin-left:2px; }
.eg-hero .cap-meta { color:var(--text-muted); }
.notice { margin:0; color:var(--text-muted); font-size:13px; line-height:1.6; }
.notice.warn { color:var(--stale-text); }
.eg-message { grid-column:1 / -1; }
.eg-numbers { display:grid; grid-template-columns:auto minmax(0,1fr); align-items:end; gap:12px 28px; }
.eg-total { display:grid; gap:2px; }
.k { color:var(--text-muted); font-size:12px; line-height:18px; font-weight:500; }
.eg-hero .eg-total .k { color:var(--eg-ink); }
.eg-big { font-size:56px; line-height:60px; font-weight:500; letter-spacing:-.05em; font-variant-numeric:tabular-nums; }
.eg-big small, .pity strong small, .six-pulls small, .donut-total small { margin-left:4px; color:var(--text-muted); font-size:.5em; font-weight:500; letter-spacing:0; }
.eg-hero .eg-big small { color:var(--eg-ink); }
.eg-tiles { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.eg-tiles li { display:grid; gap:2px; padding:12px 14px; border-radius:var(--radius-well); background:var(--card-bg); }
.eg-tiles .k { display:inline-flex; align-items:center; gap:6px; }
.eg-tiles .six .k::before, .eg-tiles .five .k::before { content:''; width:8px; height:8px; border-radius:3px; background:var(--eg-six); }
.eg-tiles .five .k::before { background:var(--eg-five); }
.eg-tiles strong { font-size:26px; line-height:32px; font-weight:550; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
.gacha-coverage { display:flex; gap:6px 20px; flex-wrap:wrap; font-size:13px; color:var(--text-muted); }
.gacha-coverage b { margin-left:6px; color:var(--text); font-weight:500; }
.eg-hero .gacha-coverage, .eg-hero .notice { color:var(--text-body); }
.eg-hero .notice.warn { color:var(--stale-text); }
.eg-title { display:flex; flex-wrap:wrap; align-items:baseline; gap:2px 10px; margin:0 0 6px; font-size:16px; line-height:24px; font-weight:600; letter-spacing:-.02em; }
.eg-sub { color:var(--text-faint); font-size:12px; font-weight:400; letter-spacing:0; }
.eg-rarity :deep(.donut-chart) { margin-top:10px; gap:12px 22px; }
.donut-total { display:grid; justify-items:center; line-height:1; }
.donut-total strong { font-size:30px; font-weight:550; letter-spacing:-.04em; font-variant-numeric:tabular-nums; }
.donut-total small { margin:3px 0 0; font-size:12px; }

/* Recent 6★: tone-step cards; the newest takes the game tone. */
.eg-recent :deep(.h-rail) { --rail-gap:12px; --rail-pad-block:10px; --rail-pad:2px; margin-top:6px; }
.six-card { display:grid; align-content:start; gap:4px; width:176px; padding:14px; border-radius:var(--radius-tile); background:var(--surface-soft); color:var(--text); }
.six-top { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; margin-bottom:6px; }
.six-top .endfield-artwork { width:52px; height:52px; border-radius:var(--radius-control); }
.six-badge { padding:0 9px; border-radius:var(--radius-chip); background:var(--eg-ink); color:var(--accent-ink); font-size:12px; font-weight:500; line-height:20px; }
.six-name { overflow:hidden; font-size:15px; line-height:22px; font-weight:600; text-overflow:ellipsis; white-space:nowrap; }
.six-pulls { font-size:30px; line-height:34px; font-weight:550; letter-spacing:-.04em; font-variant-numeric:tabular-nums; }
.six-meta { color:var(--text-muted); font-size:12px; line-height:18px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.six-card.latest { background:var(--eg-tone); }
.six-card.latest .endfield-artwork { background:var(--card-bg); }

/* One card per pool; the pool pulled from last takes a light wash of the game tone. */
.pool-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:16px; }
.pool-card { grid-column:span var(--span,4); display:grid; gap:10px; align-content:start; min-width:0; padding:18px; border:1px solid var(--card-border); border-radius:var(--radius-card); background:var(--card-bg); box-shadow:var(--card-shadow); }
.pool-card.is-latest { background:color-mix(in srgb,var(--eg-tone) 55%,var(--card-bg)); }
.pool-head { display:flex; flex-wrap:wrap; align-items:center; gap:4px 8px; }
.pool-head h3 { margin:0; color:var(--text); font-size:15px; line-height:22px; font-weight:600; letter-spacing:-.01em; }
.pool-head .chip { margin-left:auto; }
.pool-latest { padding:0 9px; border-radius:var(--radius-chip); background:var(--eg-ink); color:var(--accent-ink); font-size:12px; font-weight:500; line-height:20px; }
.chip.warn { background:var(--stale-bg); color:var(--stale-text); box-shadow:none; }
.pity { display:grid; gap:0; }
.pity .k { display:inline-flex; align-items:center; }
.pity strong { color:var(--text); font-size:40px; line-height:46px; font-weight:550; letter-spacing:-.05em; font-variant-numeric:tabular-nums; }
.stack-bar { height:12px; gap:3px; }
.legend { margin:0; gap:4px 12px; }
.legend .plain::before { display:none; }
.legend > li:not(.plain)::before { border-radius:4px; }
.chip.six { background:var(--eg-tone); box-shadow:none; color:var(--text); }
.chip-list { gap:6px; }

.panel { border:1px solid var(--card-border); border-radius:var(--radius-card); background:var(--card-bg); box-shadow:var(--card-shadow); }
.panel > summary { display:flex; align-items:center; gap:8px; min-height:52px; padding:10px 14px 10px 20px; border-radius:var(--radius-card); color:var(--text); font-size:14px; font-weight:600; list-style:none; cursor:pointer; }
.panel > summary::-webkit-details-marker { display:none; }
.panel > summary > svg { margin-left:auto; color:var(--text-faint); }
.panel > summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.panel-body { display:grid; gap:10px; padding:4px 20px 18px; }
.panel-body .toolbar { margin:0; }
.table-scroll { overflow-x:auto; }
.records .when { width:10em; white-space:nowrap; font-variant-numeric:tabular-nums; color:var(--text-muted); }
.records .rarity { width:5em; }
.data-table .name { font-weight:500; }
.data-table .name .chip { margin-left:6px; }
.data-table tr.six .name, .data-table tr.six .rarity { color:var(--eg-ink); font-weight:500; }
.data-table tr.five .rarity { color:var(--text); font-weight:500; }
.data-table .rarity { white-space:nowrap; }

/* A bot image is one still frame: flat fills, no shadows (they inflate the PNG). */
.is-image .eg-card, .is-image .pool-card, .is-image .panel { box-shadow:none; border-color:var(--border); }
.is-image .eg-hero { border-color:transparent; }

@media (max-width:900px) {
  .is-split .eg-hero, .is-split .eg-rarity, .eg-totals, .eg-recent { grid-column:1 / -1; }
  .pool-card { grid-column:span 6; }
}
@media (max-width:600px) {
  .data-table th:last-child, .data-table td:last-child { display:none; }
  .eg-card { padding:16px; border-radius:22px; }
  .pool-card { grid-column:1 / -1; padding:16px; border-radius:22px; }
  .eg-numbers { grid-template-columns:1fr; }
  .eg-big { font-size:48px; line-height:52px; }
  .eg-head .cap-meta { gap:8px; }
  .eg-head .cap-meta .ui-button { margin-left:auto; }
  .six-card { width:156px; }
  .panel > summary { padding-left:16px; }
  .panel-body { padding:4px 14px 14px; }
}
</style>
