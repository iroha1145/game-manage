<script setup>
import { isCloudMode } from '../http-client.js'
const cloudMode = isCloudMode()
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { fetchedLabel } from '../time.js'
import { exportRecords, getRecords, pityText, pullDate, rarityLabel } from '../endfield-gacha-api.js'
import AppIcon from './AppIcon.vue'
import InfoHint from './InfoHint.vue'
import MenuSelect from './MenuSelect.vue'
import SummaryMetrics from './SummaryMetrics.vue'

const props = defineProps({ snap: { type: Object, default: null }, accountId: { type: String, default: '' } })
const summary = computed(() => props.snap?.payload?.schema_version === 1 ? props.snap.payload : null)
const report = computed(() => summary.value?.report?.schema_version === 1 ? summary.value.report : null)
const reportMetrics = computed(() => [
  { label: '已记录寻访', value: report.value?.total ?? summary.value?.total },
  { label: '6★ 记录', value: report.value?.six_star },
  { label: '5★ 记录', value: report.value?.five_star },
  { label: '免费寻访', value: report.value?.free },
])
const pools = computed(() => Array.isArray(summary.value?.pools) ? summary.value.pools : [])
const fetchedAt = computed(() => fetchedLabel(props.snap?.fetched_at))
const poolOptions = computed(() => [{ value: '', label: '全部卡池' }, ...pools.value.map(pool => ({ value: pool.key, label: pool.label }))])
const opened = ref(false), recordPool = ref(''), records = ref([]), total = ref(0), offset = ref(0), busy = ref(false), message = ref('')
const PAGE = 50
let generation = 0

// Rarity split of a pool: 6★, 5★ and the rest, as flex weights for the stacked bar
// (colours as in the Wuwa panel: game colour, purple, then grey for the common tier).
function split(pool) {
  const rest = Math.max(0, (pool.total || 0) - (pool.six_star || 0) - (pool.five_star || 0))
  return [
    { label: '6★', count: pool.six_star || 0, series: 'var(--game-endfield)' },
    { label: '5★', count: pool.five_star || 0, series: 'var(--chart-5)' },
    { label: '4★', count: rest, series: 'var(--text-faint)' },
  ]
}
const sixPulls = item => item.pulls == null ? '未知' : item.status === 'exact' ? `${item.pulls} 抽` : item.status === 'lower_bound' ? `≥${item.pulls} 抽` : '未知'

async function load(start = 0) {
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
watch(() => [props.accountId, recordPool.value, opened.value], () => { ++generation; records.value = []; total.value = 0; offset.value = 0; busy.value = false; message.value = ''; if (opened.value) load(0) })
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
  <section class="cap-card endfield-gacha" aria-labelledby="endfield-gacha-title">
    <header class="cap-title">
      <div class="gacha-heading"><p>05 / HEADHUNTING ARCHIVE</p><h2 id="endfield-gacha-title">寻访记录</h2></div><span v-if="snap?.stale" class="badge badge-stale">待更新</span>
      <InfoHint :text="cloudMode ? '官方记录有查询时限，云端档案保留已同步数据；撤销授权会禁止读取。' : '官方可查询约 90 天记录；同步后保存在本机，退出登录不会删除本机记录。'" />
      <span class="cap-meta"><template v-if="summary">共 <b>{{ summary.total }}</b> 抽<template v-if="fetchedAt"> · 同步于 {{ fetchedAt }}</template></template><button type="button" class="ui-button small-button" :disabled="busy || !accountId" @click="download">导出记录</button></span>
    </header>
    <p v-if="!accountId" class="notice">登录终末地后，点「刷新数据」开始同步寻访记录。</p>
    <p v-else-if="!summary" class="notice">尚未同步寻访记录，点「刷新数据」开始同步。</p>
    <template v-else>
      <SummaryMetrics compact :metrics="reportMetrics" />
      <div v-if="report" class="gacha-coverage"><span>已知记录缺口 <b>{{ report.gaps ?? '未知' }}</b></span><span>同步状态 <b>{{ report.pending === true ? '部分待同步' : report.pending === false ? '本轮同步完成' : '未知' }}</b></span><span>记录内准确区间均值 <b>{{ report.average_exact_pulls == null ? '未知' : `${report.average_exact_pulls} 抽` }}</b></span></div>
      <p v-if="report?.average_exact_pulls != null" class="notice">均值仅来自当前展示历史中 {{ report.known_exact_intervals }} 个抽数准确的 6★ 区间，不代表完整生涯或未来出货。</p>
      <p v-if="summary.complete === false" class="notice warn" role="status">还有未同步完的记录，下次刷新会接着同步。</p>
      <p v-else-if="summary.complete !== true" class="notice warn" role="status">当前记录完整性未知，请留意各卡池的记录范围。</p>
      <p v-else class="notice">当前可同步范围已读取；更早的历史仍以已保存记录为准。</p>
      <p v-if="!pools.length" class="empty">{{ cloudMode ? '本人档案' : '本机' }}暂无寻访记录。</p>
      <div v-else class="pool-grid">
        <article v-for="(pool,index) in pools" :key="pool.key" class="pool-card"><p class="pool-index">POOL {{ String(index+1).padStart(2,'0') }}</p>
          <header class="pool-head">
            <h3>{{ pool.label }}</h3>
            <span v-if="pool.gaps" class="chip warn">{{ pool.pending ? '部分待同步' : '记录有缺口' }}<InfoHint align="end" text="记录不连续时，跨缺口的抽数以 ≥ 表示已知最少值。" /></span>
          </header>
          <div class="pity">
            <span class="k">距上次 6★<InfoHint v-if="pool.since_last_six?.status === 'lower_bound'" text="≥ 表示已知最少抽数。记录缺口、更早记录缺失或免费寻访会影响统计；免费寻访是否计入保底尚不确定。" /></span>
            <strong>{{ pityText(pool.since_last_six) }}</strong>
          </div>
          <div class="stack-bar" role="img" :aria-label="split(pool).map(part => `${part.label} ${part.count}`).join('，')">
            <i v-for="part in split(pool).filter(part => part.count)" :key="part.label" :style="{ '--series': part.series, flex: part.count }" />
          </div>
          <ul class="legend">
            <li v-for="part in split(pool)" :key="part.label" :style="{ '--series': part.series }">{{ part.label }} <b>{{ part.count }}</b></li>
            <li class="plain">共 <b>{{ pool.total }}</b> 抽</li>
            <li v-if="pool.free" class="plain">免费 <b>{{ pool.free }}</b></li>
          </ul>
          <ul v-if="pool.history?.length" class="chip-list" :aria-label="`${pool.label}的 6★ 记录`">
            <li v-for="(item, index) in pool.history" :key="index" class="chip six" :title="`${item.pool_name || pool.label} · ${pullDate(item.obtained_at)}`">{{ item.name || '未知' }} <b>{{ sixPulls(item) }}</b></li>
          </ul>
        </article>
      </div>
      <details class="panel record-list" @toggle="opened = $event.target.open">
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
    <p v-if="message" class="notice" role="status">{{ message }}</p>
  </section>
</template>

<style scoped>
.endfield-gacha { display: grid; gap: 12px; }
.endfield-gacha > .cap-title { margin-bottom: 0; }
.cap-title h2 { margin: 0; font-size: inherit; font-weight: inherit; }
.cap-meta b { color: var(--text); font-weight: 600; }
.cap-meta .ui-button { margin-left: 4px; }
.notice { margin: 0; color: var(--text-muted); font-size: 12px; }
.notice.warn { color: var(--stale-text); }
.gacha-coverage { display:flex;gap:10px 20px;flex-wrap:wrap;padding:12px 0;border-block:1px solid var(--border);font-size:12px;color:var(--text-muted); }
.gacha-coverage b { margin-left:6px;color:var(--text);font-weight:500; }
.pool-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr)); gap: 8px; }
.pool-card { display: grid; gap: 8px; align-content: start; min-width: 0; padding: 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--panel-bg); }
.pool-head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.pool-head h3 { margin: 0; color: var(--text); font-size: 13px; font-weight: 600; }
.pool-head .chip { margin-left: auto; }
.chip.warn { background: var(--stale-bg); color: var(--stale-text); }
.pity { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.pity .k { display: inline-flex; align-items: center; color: var(--text-muted); font-size: 12px; }
.pity strong { color: var(--text); font-size: 22px; font-weight: 600; line-height: 28px; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }
.legend { margin: 0; }
.legend .plain::before { display: none; }
.chip.six { background: color-mix(in srgb, var(--game-endfield) 16%, transparent); color: var(--text); }
.panel { border: 1px solid var(--border); border-radius: 9px; }
.panel > summary { display: flex; align-items: center; gap: 8px; min-height: 36px; padding: 6px 10px 6px 12px; border-radius: 8px; color: var(--text); font-size: 13px; font-weight: 600; list-style: none; cursor: pointer; }
.panel > summary::-webkit-details-marker { display: none; }
.panel > summary > svg { margin-left: auto; color: var(--text-faint); }
.panel > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.panel-body { display: grid; gap: 10px; padding: 10px 12px 12px; border-top: 1px solid var(--border); }
.panel-body .toolbar { margin: 0; }
.table-scroll { overflow-x: auto; }
.records .when { width: 10em; white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--text-muted); }
.records .rarity { width: 5em; }
.data-table .name { font-weight: 500; }
.data-table .name .chip { margin-left: 6px; }
.data-table tr.six .name, .data-table tr.six .rarity { color: var(--game-endfield); font-weight: 600; }
.data-table tr.five .rarity { color: var(--chart-5); }
.data-table .rarity { white-space: nowrap; }
@media (max-width: 600px) { .data-table th:last-child, .data-table td:last-child { display: none; } }
.endfield-gacha { border-radius:0; box-shadow:none; border-top:2px solid var(--game-endfield); padding:22px; }
.endfield-gacha>.cap-title { padding-bottom:16px; border-bottom:1px solid var(--border); margin-bottom:20px; gap:12px; }
.gacha-heading>p,.pool-index { font-family:var(--font-mono); font-size:10px; letter-spacing:.14em; color:var(--text-muted); margin-bottom:7px; font-weight:400; }
.gacha-heading h2 { font-size:21px; letter-spacing:.03em; line-height:1.35; }
.endfield-gacha :deep(.summary-metric),.endfield-gacha .pool-card,.endfield-gacha .panel,.endfield-gacha .panel>summary,.endfield-gacha .ui-button { border-radius:0; }
.endfield-gacha :deep(.metric-symbol) { border-radius:0; }
.endfield-gacha :deep(.metric-copy>strong),.endfield-gacha .pity>strong { font-family:var(--font-mono); font-weight:500; }
.endfield-gacha .pool-card { padding:18px; background:var(--panel-bg); border-top:2px solid color-mix(in srgb,var(--game-endfield) 45%,var(--border)); }
.endfield-gacha .pool-head { margin-bottom:18px; }
.endfield-gacha .pool-head h3 { font-size:16px; }
.endfield-gacha .chip { border-radius:0; }
.gacha-coverage { border-bottom:1px solid var(--border); padding-bottom:14px; }
@media(max-width:600px) { .endfield-gacha { padding:16px; }.gacha-heading h2 { font-size:19px; }.endfield-gacha .pool-card { padding:14px; }.endfield-gacha .cap-meta { gap:8px; }.endfield-gacha .cap-meta .ui-button { margin-left:auto; } }
</style>
