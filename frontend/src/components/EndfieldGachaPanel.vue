<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { isCloudMode } from '../http-client.js'
import { fetchedLabel } from '../time.js'
import { exportRecords, getRecords, pityParts, pullDate, pullDay, rarityLabel } from '../endfield-gacha-api.js'
import { gachaPools, poolGroups, poolPace, poolTotal, pullRuler, rarityShares, sixPullsParts, syncStatus } from '../endfield-gacha-summary.js'
import { gachaArtwork } from '../endfield-reports.js'
import { vReveal } from '../motion.js'
import AppIcon from './AppIcon.vue'
import EndfieldArtwork from './EndfieldArtwork.vue'
import InfoHint from './InfoHint.vue'
import MenuSelect from './MenuSelect.vue'

const cloudMode = isCloudMode()
const props = defineProps({ snap: { type: Object, default: null }, accountId: { type: String, default: '' }, imageMode:Boolean })
const summary = computed(() => props.snap?.payload?.schema_version === 1 ? props.snap.payload : null)
const report = computed(() => summary.value?.report?.schema_version === 1 ? summary.value.report : null)
const show = value => value == null || value === '' ? '未知' : value
const pools = computed(() => gachaPools(summary.value))
const groups = computed(() => poolGroups(pools.value))
const fetchedAt = computed(() => fetchedLabel(props.snap?.fetched_at))
const poolOptions = computed(() => [{ value: '', label: '全部卡池' }, ...pools.value.map(pool => ({ value: pool.key, label: pool.label }))])
const opened = ref(false), recordPool = ref(''), records = ref([]), total = ref(0), offset = ref(0), busy = ref(false), message = ref('')
const PAGE = 50
let generation = 0

// The headline: the report's own totals, else a sum only when every pool states the count.
const grandTotal = computed(() => report.value?.total ?? summary.value?.total)
const count = field => report.value?.[field] ?? poolTotal(pools.value, field)
const kpis = computed(() => [
  { label: '6★', value: count('six_star'), tone: 'six' },
  { label: '5★', value: count('five_star'), tone: 'five' },
  { label: '平均出 6★', value: report.value?.average_exact_pulls, unit: '抽',
    hint: report.value?.average_exact_pulls != null ? `只统计已展示历史中 ${report.value.known_exact_intervals} 次抽数准确的 6★；跨缺口或含免费寻访的区间不计入。` : '' },
])
const status = computed(() => syncStatus(summary.value, report.value))
const statusHint = computed(() => {
  const gaps = report.value?.gaps ?? poolTotal(pools.value, 'gaps')
  return [gaps == null ? '已知记录缺口数未知。' : gaps ? `已知记录缺口 ${gaps} 处。` : '',
    '跨缺口、更早记录缺失或含免费寻访时，抽数以 ≥ 表示已知最少值；免费寻访是否计入保底尚不确定。'].join('')
})

// The web page details one chosen pool at a time; a bot image prints every pool in turn.
const selected = ref('')
const current = computed(() => pools.value.find(pool => pool.key === selected.value) || pools.value[0] || null)
const rulers = computed(() => ({ character: pullRuler(pools.value, 'character'), weapon: pullRuler(pools.value, 'weapon') }))
const views = computed(() => (props.imageMode ? pools.value : current.value ? [current.value] : []).map(pool => {
  const pace = poolPace(pool)
  // Unknown/other is only listed when it is not a plain zero.
  const shares = rarityShares(pool).filter(part => part.field !== 'unknown_rarity' || part.count !== 0)
  // Pulls of unstated rarity stay as empty track, so the bar has the legend's scale: shares of the total.
  const counted = shares.reduce((sum, part) => sum + (part.count ?? 0), 0), pulls = Number(pool.total)
  return { pool, pace, ruler: rulers.value[pool.kind === 'weapon' ? 'weapon' : 'character'], shares,
    rest: Number.isFinite(pulls) && pulls > counted ? pulls - counted : 0,
    range:Number.isFinite(pool.oldest_at) && Number.isFinite(pool.newest_at) ? `${pullDay(pool.oldest_at)} – ${pullDay(pool.newest_at)}` : '' }
}))
function select(key) { selected.value = key; recordPool.value = key }
// A pool that is gone after a sync no longer filters the ledger either.
watch(pools, list => { if (selected.value && !list.some(pool => pool.key === selected.value)) { selected.value = ''; if (!list.some(pool => pool.key === recordPool.value)) recordPool.value = '' } })
const pity = pool => pityParts(pool.since_last_six)
const percent = share => `${(share * 100).toFixed(share < .1 ? 1 : 0)}%`
const banner = (item, pool) => item.pool_name && item.pool_name !== pool.label ? item.pool_name : ''
const barWidth = (item, ruler) => { const parts = sixPullsParts(item); return parts && ruler ? `${Math.min(100, Math.round(parts.count / ruler * 10000) / 100)}%` : '0%' }
const tag = (item, pace) => item === pace.fastest ? { label: '最欧', tone: 'lucky' } : item === pace.slowest ? { label: '最非', tone: 'unlucky' } : null
// Ledger rows carry their kind; older exports only say it through a weapon pool key.
const recordKind = row => row.kind || (String(row.pool_key || '').startsWith('weapon:') ? 'weapon' : 'character')
const RARITY_COLOR = { six_star: 'var(--eg-six)', five_star: 'var(--eg-five)', four_star: 'var(--eg-four)', unknown_rarity: 'var(--eg-unknown)' }

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
  <section class="endfield-gacha" :class="{ 'is-image': imageMode }" aria-labelledby="endfield-gacha-title">
    <div v-reveal class="eg-card eg-hero">
      <header class="eg-head">
        <h2 id="endfield-gacha-title">寻访分析</h2>
        <InfoHint v-if="!imageMode" :text="cloudMode ? '官方记录有查询时限，云端档案保留已同步数据；撤销授权会禁止读取。' : '官方可查询约 90 天记录；同步后保存在本机，退出登录不会删除本机记录。'" />
        <span v-if="summary" class="eg-status" :class="status.tone">{{ status.label }}<InfoHint v-if="!imageMode" align="end" :text="statusHint" /></span>
        <span v-if="snap?.stale && !imageMode" class="badge badge-stale">待更新</span>
        <span class="cap-meta"><template v-if="summary && fetchedAt">同步于 {{ fetchedAt }}</template><button v-if="!imageMode" type="button" class="ui-button small-button" :disabled="busy || !accountId" @click="download">导出记录</button></span>
      </header>
      <p v-if="!accountId && !imageMode" class="notice">登录终末地后，点「刷新数据」开始同步寻访记录。</p>
      <p v-else-if="!summary" class="notice">尚未同步寻访记录，点「刷新数据」开始同步。</p>
      <template v-else>
        <dl class="eg-kpis">
          <div class="kpi-total"><dt>累计寻访</dt><dd>{{ show(grandTotal) }}<small v-if="grandTotal != null">抽</small></dd></div>
          <div v-for="kpi in kpis" :key="kpi.label" :class="kpi.tone"><dt>{{ kpi.label }}<InfoHint v-if="kpi.hint && !imageMode" :text="kpi.hint" /></dt><dd>{{ show(kpi.value) }}<small v-if="kpi.unit && kpi.value != null">{{ kpi.unit }}</small></dd></div>
        </dl>
        <p v-if="summary.complete === false" class="notice warn" role="status">还有记录未同步完，下次刷新会接着同步。</p>
      </template>
    </div>

    <template v-if="summary">
      <p v-if="!pools.length" class="empty eg-card">暂无寻访记录。</p>
      <nav v-else-if="!imageMode" class="eg-pools" aria-label="选择卡池">
        <div v-for="group in groups" :key="group.kind" class="eg-group">
          <h3 class="eg-group-title">{{ group.label }}</h3>
          <div class="pool-tiles">
            <button v-for="pool in group.pools" :key="pool.key" type="button" class="pool-tile" :class="{ active: current?.key === pool.key }" :aria-pressed="current?.key === pool.key" @click="select(pool.key)">
              <span class="tile-name">{{ pool.label }}<i v-if="pool.gaps || pool.pending" class="tile-flag" :title="pool.pending ? '部分待同步' : '记录有缺口'" /></span>
              <span class="tile-pity"><small>已垫</small><b><template v-if="pity(pool)">{{ pity(pool).prefix }}{{ pity(pool).count }}</template><template v-else>?</template></b></span>
              <span class="tile-meta">{{ pool.total }} 抽 · 6★ {{ pool.six_star }}</span>
            </button>
          </div>
        </div>
      </nav>

      <article v-for="view in views" :key="view.pool.key" v-reveal class="eg-card pool-detail">
        <header class="detail-head">
          <h3>{{ view.pool.label }}</h3>
          <span class="chip">{{ view.pool.kind === 'weapon' ? '武器申领' : '干员寻访' }}</span>
          <span v-if="view.pool.gaps || view.pool.pending" class="chip warn">{{ view.pool.pending ? '部分待同步' : '记录有缺口' }}<InfoHint v-if="!imageMode" align="end" text="记录不连续时，跨缺口的抽数以 ≥ 表示已知最少值。" /></span>
          <span v-if="view.range" class="detail-range">{{ view.range }}</span>
        </header>

        <div class="detail-top">
          <div class="pity-block">
            <span class="k">已垫<InfoHint v-if="!imageMode && view.pool.since_last_six?.status === 'lower_bound'" text="≥ 表示已知最少抽数。记录缺口、更早记录缺失或免费寻访会影响统计；免费寻访是否计入保底尚不确定。" /></span>
            <strong><template v-if="pity(view.pool)">{{ pity(view.pool).prefix }}{{ pity(view.pool).count }}<small>{{ pity(view.pool).unit }}</small></template><template v-else>未知</template></strong>
            <span class="k-sub">距上次 6★</span>
          </div>
          <dl class="detail-stats">
            <div><dt>总抽数</dt><dd>{{ view.pool.total }}<small>抽</small></dd><dd v-if="view.pool.free" class="stat-sub">含免费 {{ view.pool.free }}</dd></div>
            <div class="six"><dt>6★</dt><dd>{{ view.pool.six_star }}</dd></div>
            <div class="five"><dt>5★</dt><dd>{{ view.pool.five_star }}</dd></div>
            <div><dt>平均出 6★</dt><dd><template v-if="view.pace.average != null">{{ view.pace.average }}<small>抽</small></template><template v-else>—</template></dd></div>
            <div><dt>最欧</dt><dd><template v-if="view.pace.fastest">{{ view.pace.fastest.pulls }}<small>抽</small></template><template v-else>—</template></dd><dd v-if="view.pace.fastest" class="stat-sub">{{ view.pace.fastest.name || '未知' }}</dd></div>
            <div><dt>最非</dt><dd><template v-if="view.pace.slowest">{{ view.pace.slowest.pulls }}<small>抽</small></template><template v-else>—</template></dd><dd v-if="view.pace.slowest" class="stat-sub">{{ view.pace.slowest.name || '未知' }}</dd></div>
          </dl>
        </div>

        <div class="rarity">
          <div class="stack-bar" role="img" :aria-label="`${view.pool.label}的稀有度：` + view.shares.map(part => `${part.label} ${part.count ?? '未知'}`).join('，')">
            <i v-for="part in view.shares.filter(part => part.count)" :key="part.field" :style="{ '--series': RARITY_COLOR[part.field], flex: part.count }" />
            <i v-if="view.rest" class="stack-rest" :style="{ flex: view.rest }" />
          </div>
          <ul class="legend">
            <li v-for="part in view.shares" :key="part.field" :style="{ '--series': RARITY_COLOR[part.field] }">{{ part.label }} <b>{{ part.count ?? '未知' }}</b><small v-if="part.share != null">{{ percent(part.share) }}</small></li>
          </ul>
        </div>

        <div class="six-head">
          <h4>6★ 出货记录</h4>
          <span>{{ view.pool.history_total ?? view.pool.history.length }} 次</span>
          <InfoHint v-if="!imageMode && view.ruler" align="end" :text="`横条按${view.pool.kind === 'weapon' ? '武器' : '干员'}卡池中最长的一次 6★ 绘制（标尺 ${view.ruler} 抽），不代表保底；斜纹表示已知最少抽数。`" />
        </div>
        <p v-if="!view.pool.history.length" class="empty">该卡池暂无 6★ 记录。</p>
        <ol v-else class="pull-list" :aria-label="`${view.pool.label}的 6★ 记录`">
          <li v-for="(item, index) in view.pool.history" :key="index" class="pull-row" :class="{ lower: item.status === 'lower_bound' }" :title="`${item.pool_name || view.pool.label} · ${pullDate(item.obtained_at)}`">
            <EndfieldArtwork class="pull-art" :src="gachaArtwork(item, view.pool.kind)" :name="item.name || '未知'" />
            <div class="pull-who"><strong>{{ item.name || '未知' }}</strong><span><template v-if="banner(item, view.pool)">{{ banner(item, view.pool) }} · </template>{{ pullDay(item.obtained_at) }}</span></div>
            <div class="pull-track">
              <i class="pull-fill" :style="{ width: barWidth(item, view.ruler) }" />
              <span class="pull-value"><template v-if="sixPullsParts(item)">{{ sixPullsParts(item).prefix }}{{ sixPullsParts(item).count }}<small>{{ sixPullsParts(item).unit }}</small></template><template v-else>抽数未知</template></span>
              <span v-if="tag(item, view.pace)" class="pull-tag" :class="tag(item, view.pace).tone">{{ tag(item, view.pace).label }}</span>
            </div>
          </li>
        </ol>
        <p v-if="view.pool.history_truncated === true" class="notice">仅显示最近 {{ view.pool.history_available }} 次 6★（账本共 {{ view.pool.history_total }} 次）；{{ imageMode ? '完整记录请在网页查看。' : '更早的可在逐条记录中查看或导出。' }}</p>
        <p v-else-if="view.pool.history_truncated == null" class="notice">6★ 历史的覆盖范围未知。</p>
      </article>

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
                  <td class="name"><span class="name-cell"><EndfieldArtwork class="row-art" :src="gachaArtwork(row, recordKind(row))" :name="row.name || '未知'" />{{ row.name || '未知' }}<span v-if="row.is_free" class="chip">免费</span></span></td>
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
/* Laid out like a community gacha analysis page: a headline strip, a tile per pool,
   then the chosen pool's pity, pace, rarity split and 6★ bars. Rarity takes the
   in-game hues (6★ orange, 5★ gold, 4★ purple); selection takes the game colour.
   The 5★ gold is lighter than the chart amber, so it stays apart from the 6★ orange
   beside it (dataviz validator, both themes).
   Bot images set only --game-accent, so every colour has a static fallback. */
.endfield-gacha { --eg-six:var(--chart-2,#d95926); --eg-five:#dba11c; --eg-four:color-mix(in srgb,var(--chart-7,#9085e9) 42%,var(--track)); --eg-unknown:var(--border-strong);
  --eg-tone:var(--game-tone,var(--game-endfield-tone)); --eg-ink:var(--game-accent,var(--game-endfield));
  --eg-bar:color-mix(in srgb,var(--eg-six) 30%,var(--card-bg)); --eg-bar-end:color-mix(in srgb,var(--eg-six) 50%,var(--card-bg));
  display:grid; gap:16px; min-width:0; }
:root[data-theme="light"] .endfield-gacha { --eg-five:#dcab4b; }
.endfield-gacha > * { min-width:0; }
.eg-card { position:relative; padding:20px; border:1px solid var(--card-border); border-radius:var(--radius-card); background:var(--card-bg); box-shadow:var(--card-shadow); }
.notice { margin:0; color:var(--text-muted); font-size:13px; line-height:1.6; }
.notice.warn { color:var(--stale-text); }
.k { display:inline-flex; align-items:center; color:var(--text-muted); font-size:12px; line-height:18px; font-weight:500; }
small { margin-left:3px; color:var(--text-muted); font-size:.5em; font-weight:500; letter-spacing:0; }

/* Headline strip on the game tone: four numbers, the sync state as one chip. */
.eg-hero { display:grid; gap:16px; border-color:transparent; background:var(--eg-tone); box-shadow:none; }
.eg-head { display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px; min-height:32px; }
.eg-head h2 { margin:0; font-size:16px; line-height:24px; font-weight:600; letter-spacing:-.02em; }
.eg-head .cap-meta { gap:10px; color:var(--text-muted); }
.eg-status { display:inline-flex; align-items:center; gap:2px; padding:0 8px; border-radius:var(--radius-chip); background:var(--card-bg); color:var(--text-body); font-size:12px; font-weight:500; line-height:22px; }
.eg-status::before { content:''; width:6px; height:6px; margin-right:5px; border-radius:50%; background:var(--text-faint); }
.eg-status.done::before { background:var(--success); }
.eg-status.warn { color:var(--stale-text); }
.eg-status.warn::before { background:var(--stale-text); }
.eg-kpis { display:grid; grid-template-columns:minmax(0,1.3fr) repeat(3,minmax(0,1fr)); gap:8px; margin:0; }
.eg-kpis > div { display:grid; align-content:start; gap:2px; padding:12px 16px; border-radius:var(--radius-well); background:var(--card-bg); }
.eg-kpis dt { display:inline-flex; align-items:center; gap:6px; color:var(--text-muted); font-size:12px; line-height:18px; font-weight:500; white-space:nowrap; }
.eg-kpis :is(.six,.five) dt::before { content:''; width:8px; height:8px; border-radius:3px; background:var(--eg-six); }
.eg-kpis .five dt::before { background:var(--eg-five); }
.eg-kpis dd { margin:0; font-size:28px; line-height:34px; font-weight:550; letter-spacing:-.03em; font-variant-numeric:tabular-nums; white-space:nowrap; }
.eg-kpis .kpi-total { background:transparent; padding-left:2px; }
.eg-kpis .kpi-total dt { color:var(--eg-ink); }
.eg-kpis .kpi-total dd { font-size:40px; line-height:34px; letter-spacing:-.05em; }
.eg-kpis .kpi-total small { color:var(--eg-ink); }

/* Pool tiles: the chosen one is filled with the game tone. */
.eg-pools { display:grid; gap:14px; }
.eg-group { display:grid; gap:8px; }
.eg-group-title { margin:0; padding-left:4px; color:var(--text-muted); font-size:12px; line-height:18px; font-weight:500; }
.pool-tiles { display:grid; grid-template-columns:repeat(auto-fill,minmax(156px,1fr)); gap:10px; }
.pool-tile { display:grid; gap:2px; min-width:0; padding:12px 14px; border:1px solid var(--card-border); border-radius:var(--radius-tile); background:var(--card-bg); color:var(--text); text-align:left; font:inherit; cursor:pointer; transition:background-color var(--duration-fast,.15s) ease, border-color var(--duration-fast,.15s) ease; }
.pool-tile:hover { border-color:color-mix(in srgb,var(--eg-ink) 40%,var(--card-border)); }
.pool-tile:focus-visible { outline:2px solid var(--eg-ink); outline-offset:2px; }
.pool-tile.active { border-color:var(--eg-ink); background:var(--eg-tone); }
.tile-name { display:flex; align-items:center; gap:6px; overflow:hidden; color:var(--text-body); font-size:13px; font-weight:600; line-height:20px; white-space:nowrap; text-overflow:ellipsis; }
.pool-tile.active .tile-name { color:var(--eg-ink); }
.tile-flag { flex:0 0 auto; width:6px; height:6px; border-radius:50%; background:var(--stale-text); }
.tile-pity { display:flex; align-items:baseline; gap:6px; }
.tile-pity small { margin:0; font-size:12px; }
.tile-pity b { font-size:26px; line-height:32px; font-weight:550; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
.tile-meta { color:var(--text-muted); font-size:12px; line-height:18px; font-variant-numeric:tabular-nums; white-space:nowrap; }

/* The chosen pool. */
.pool-detail { display:grid; gap:18px; align-content:start; }
.detail-head { display:flex; flex-wrap:wrap; align-items:center; gap:6px 8px; }
.detail-head h3 { margin:0 4px 0 0; font-size:18px; line-height:26px; font-weight:600; letter-spacing:-.02em; }
.chip.warn { background:var(--stale-bg); color:var(--stale-text); box-shadow:none; }
.detail-range { margin-left:auto; color:var(--text-faint); font-size:12px; font-variant-numeric:tabular-nums; white-space:nowrap; }
.detail-top { display:grid; grid-template-columns:minmax(180px,220px) minmax(0,1fr); gap:12px; }
.pity-block { display:grid; align-content:center; gap:0; padding:16px 20px; border-radius:var(--radius-tile); background:var(--eg-tone); }
.pity-block .k { color:var(--eg-ink); }
.pity-block strong { font-size:52px; line-height:58px; font-weight:550; letter-spacing:-.05em; font-variant-numeric:tabular-nums; white-space:nowrap; }
.pity-block strong small { color:var(--eg-ink); }
.k-sub { color:var(--text-muted); font-size:12px; line-height:18px; }
.detail-stats { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:0; }
.detail-stats > div { display:grid; align-content:start; gap:0; min-width:0; padding:10px 14px; border-radius:var(--radius-well); background:var(--surface-soft); }
.detail-stats dt { display:inline-flex; align-items:center; gap:6px; color:var(--text-muted); font-size:12px; line-height:18px; font-weight:500; }
.detail-stats :is(.six,.five) dt::before { content:''; width:8px; height:8px; border-radius:3px; background:var(--eg-six); }
.detail-stats .five dt::before { background:var(--eg-five); }
.detail-stats dd { margin:0; font-size:22px; line-height:30px; font-weight:550; letter-spacing:-.02em; font-variant-numeric:tabular-nums; white-space:nowrap; }
.detail-stats dd small { font-size:12px; }
.detail-stats .stat-sub { overflow:hidden; color:var(--text-muted); font-size:12px; line-height:16px; font-weight:400; letter-spacing:0; text-overflow:ellipsis; }

.rarity .stack-bar { height:10px; gap:2px; }
.rarity .stack-rest { background:transparent; }
.rarity .legend { gap:4px 16px; margin-top:8px; }
.legend li { font-variant-numeric:tabular-nums; }
.legend b { color:var(--text); font-weight:500; }
.legend small { margin-left:2px; font-size:12px; color:var(--text-faint); }

/* 6★ bars: one row each, the fill measured on a shared ruler of its kind. */
.six-head { display:flex; align-items:center; gap:8px; margin-bottom:-6px; }
.six-head h4 { margin:0; font-size:14px; line-height:22px; font-weight:600; }
.six-head > span { color:var(--text-muted); font-size:12px; }
.pull-list { display:grid; gap:8px; margin:0; padding:0; list-style:none; }
.pull-row { display:grid; grid-template-columns:40px minmax(96px,168px) minmax(0,1fr); align-items:center; gap:12px; min-width:0; }
.pull-art { width:40px; height:40px; border-radius:var(--radius-control); }
.pull-who { display:grid; min-width:0; }
.pull-who strong { overflow:hidden; font-size:14px; line-height:20px; font-weight:600; text-overflow:ellipsis; white-space:nowrap; }
.pull-who span { overflow:hidden; color:var(--text-muted); font-size:12px; line-height:18px; text-overflow:ellipsis; white-space:nowrap; }
.pull-track { position:relative; display:flex; align-items:center; gap:8px; min-width:0; height:32px; padding:0 12px; overflow:hidden; border-radius:var(--radius-control); background:var(--track); }
.pull-fill { position:absolute; inset:0 auto 0 0; border-radius:inherit; background:linear-gradient(90deg,var(--eg-bar),var(--eg-bar-end)); transition:width var(--duration-slow,.4s) var(--ease-smooth-out,ease-out); }
.pull-row.lower .pull-fill { background:repeating-linear-gradient(135deg,var(--eg-bar) 0 6px,color-mix(in srgb,var(--eg-bar) 45%,var(--track)) 6px 10px); }
.pull-value { position:relative; color:var(--text); font-size:15px; line-height:1; font-weight:600; font-variant-numeric:tabular-nums; white-space:nowrap; }
.pull-value small { font-size:12px; }
.pull-tag { position:relative; padding:0 7px; border-radius:var(--radius-chip); background:var(--card-bg); font-size:12px; font-weight:500; line-height:20px; white-space:nowrap; }
.pull-tag.lucky { color:var(--success); }
.pull-tag.unlucky { color:var(--danger); }
.empty { margin:0; padding:14px 0; color:var(--text-muted); font-size:13px; text-align:center; }
.eg-message { padding:0 4px; }

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
.name-cell { display:inline-flex; align-items:center; gap:10px; }
.row-art { width:30px; height:30px; border-radius:9px; }
.data-table .name .chip { margin-left:-4px; }
.data-table tr.six td { background:color-mix(in srgb,var(--eg-six) 9%,transparent); }
/* Text keeps the text colour; the row tint carries the rarity hue. */
.data-table tr.six :is(.name,.rarity) { color:var(--text); font-weight:600; }
.data-table tr.five .rarity { color:var(--text); font-weight:500; }
.data-table .rarity { white-space:nowrap; }

/* A bot image is one still frame: flat fills, no shadows (they inflate the PNG). */
.is-image .eg-card, .is-image .panel { box-shadow:none; border-color:var(--border); }
.is-image .eg-hero { border-color:transparent; }

@media (max-width:760px) {
  .eg-kpis { grid-template-columns:repeat(3,minmax(0,1fr)); }
  .eg-kpis .kpi-total { grid-column:1 / -1; }
  .detail-top { grid-template-columns:1fr; }
}
@media (max-width:600px) {
  .eg-card { padding:16px; border-radius:22px; }
  .eg-kpis > div { padding:10px; }
  .eg-kpis dt { gap:4px; }
  .eg-kpis dd { font-size:22px; line-height:28px; }
  .eg-kpis .kpi-total dd { font-size:36px; line-height:40px; }
  .eg-head .cap-meta { margin-left:0; width:100%; justify-content:space-between; }
  /* Phones keep each group to one swipeable row so the chosen pool stays near the top. */
  .pool-tiles { display:flex; gap:8px; margin:0 -16px; padding:0 16px 4px; overflow-x:auto; scroll-snap-type:x proximity; scroll-padding:0 16px; scrollbar-width:none; }
  .pool-tiles::-webkit-scrollbar { display:none; }
  .pool-tile { flex:0 0 132px; padding:10px 12px; scroll-snap-align:start; }
  .tile-pity b { font-size:22px; line-height:28px; }
  .detail-range { margin-left:0; width:100%; }
  .pity-block { grid-template-columns:auto 1fr; align-items:baseline; gap:0 10px; padding:12px 16px; }
  .pity-block .k { grid-row:1; }
  .pity-block strong { grid-row:1 / span 2; grid-column:2; justify-self:end; font-size:44px; line-height:50px; }
  .pity-block .k-sub { grid-row:2; }
  .detail-stats { grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
  .detail-stats > div { padding:8px 10px; }
  .detail-stats dd { font-size:18px; line-height:26px; }
  .pull-row { grid-template-columns:40px minmax(0,1fr); grid-template-areas:"art who" "art bar"; gap:4px 10px; }
  .pull-art { grid-area:art; align-self:start; }
  .pull-who { grid-area:who; grid-auto-flow:column; justify-content:space-between; gap:8px; }
  .pull-track { grid-area:bar; height:28px; }
  .data-table th:last-child, .data-table td:last-child { display:none; }
  .panel > summary { padding-left:16px; }
  .panel-body { padding:4px 14px 14px; }
}
</style>
