<script setup>
import { isCloudMode } from '../http-client.js'
const cloudMode = isCloudMode()
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useWuwaRequest } from '../wuwa-api.js'
import { value, list, stamp } from '../wuwa-display.js'
import WuwaDrawTable from './WuwaDrawTable.vue'
import InfoHint from './InfoHint.vue'
import WuwaGachaImport from './WuwaGachaImport.vue'
import WuwaGachaSummary from './WuwaGachaSummary.vue'
import { gachaSource } from '../wuwa-gacha.js'
const props = defineProps({ accountKey: { type: String, default: '' }, snapshot: {type:Object,default:null}, imageMode:{type:Boolean,default:false} })
const archive = ref(props.imageMode ? props.snapshot : null),
  url = ref(''),
  linkPreview = ref(null),
  outcome = ref(null),
  error = ref(''),
  busy = ref(false),
  offset = ref(0)
onBeforeUnmount(() => {
  clearInput()
})
function clearInput() {
  url.value = ''
}
function reset() {
  clearInput()
  archive.value = null
  outcome.value = null
  linkPreview.value = null
  error.value = ''
  busy.value = false
  offset.value = 0
}
const request = useWuwaRequest(() => props.accountKey, reset)
async function load(page = 0) {
  busy.value = true
  error.value = ''
  try {
    const result = await request.run(`gacha?limit=50&offset=${page}`)
    if (!result) return
    archive.value = result
    offset.value = page
    busy.value = false
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}
async function perform(body) {
  try {
    const result = await request.run('gacha/import', body)
    if (!result) return
    outcome.value = result
    await load(0)
  } catch (e) {
    error.value = e.message
    busy.value = false
  } finally {
    clearInput()
  }
}
async function importUrl() {
  if (busy.value || !url.value.trim()) return
  const submitted = url.value.trim()
  clearInput()
  outcome.value = null
  linkPreview.value = null
  error.value = ''
  busy.value = true
  try { linkPreview.value = await request.run('gacha/preview', { url: submitted }) }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function confirmUrl() {
  if (busy.value || !linkPreview.value) return
  const preview_id = linkPreview.value.preview_id
  linkPreview.value = null
  busy.value = true
  return perform({ preview_id })
}
onMounted(() => { if (!props.imageMode) load() })
watch(
  () => props.accountKey,
  () => {
    importDecided = false
    if (!props.imageMode) load()
  },
)
// The import form opens by itself only when the first archive read for an
// account is empty; after that it stays as the user left it, so a successful
// import does not fold it away mid-use.
const importOpen = ref(false)
let importDecided = false
watch(archive, (loaded) => {
  if (importDecided || !loaded) return
  importDecided = true
  importOpen.value = loaded.state === 'need_import' || !loaded.total
})
const poolNames = computed(() =>
  Object.fromEntries(
    list(archive.value?.pools)
      .filter((p) => p.pool != null && p.name)
      .map((p) => [p.pool, p.name]),
  ),
)
function byPool(rows) {
  const groups = new Map()
  for (const row of list(rows)) {
    const key = row.pool == null ? '' : String(row.pool)
    if (!groups.has(key)) groups.set(key, {key, name: poolNames.value[key] || (key ? `卡池 ${key}` : '未知卡池'), rows: []})
    groups.get(key).rows.push(row)
  }
  return [...groups.values()]
}
const goldGroups = computed(() => byPool(archive.value?.gold))
const recordGroups = computed(() => byPool(archive.value?.items))
// Coverage bounds are record times in the source time zone: reformat, never convert.
const SOURCE_TIME = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/
function sourceTime(v) {
  const match = typeof v === 'string' ? v.match(SOURCE_TIME) : null
  return match ? `${match[1]} ${match[2]}` : value(v)
}
const RARITY_SERIES = {
  3: 'var(--text-faint)',
  4: 'var(--chart-5)',
  5: 'var(--game-wuwa)',
}
function rarities(pool) {
  return Object.entries(pool.rarity_distribution || {})
    .map(([rarity, count]) => ({
      rarity,
      count,
      label: rarity === 'unknown' ? '稀有度未知' : `${rarity} 星`,
      size: typeof count === 'number' && count > 0 ? count : 0,
      series: RARITY_SERIES[rarity] || 'var(--border-strong)',
    }))
    .sort(
      (a, b) =>
        (a.rarity === 'unknown') - (b.rarity === 'unknown') ||
        Number(a.rarity) - Number(b.rarity),
    )
}
</script>
<template>
  <section class="wuwa-panel">
    <header class="cap-title">
      <h2>抽卡历史</h2>
    </header>
    <details v-if="!imageMode" class="wuwa-import" :open="importOpen" @toggle="importOpen = $event.target.open">
      <summary>导入记录</summary>
      <div class="wuwa-import-body">
        <p class="wuwa-meta">授权链接仅用于本次导入，用后清空；记录保存在本机。</p>
        <form class="toolbar wuwa-import-row" @submit.prevent="importUrl">
          <input
            class="grow"
            type="password"
            autocomplete="off"
            spellcheck="false"
            aria-label="官方记录授权链接"
            :value="url"
            @input="url = $event.target.value;linkPreview = null"
            placeholder="粘贴官方记录授权链接，不保存到浏览器"
          /><button
            type="submit"
            class="ui-button small-button primary"
            :disabled="busy || !url.trim()"
            @click.prevent="importUrl"
          >
            预览链接
          </button>
        </form>
        <div v-if="linkPreview" class="wuwa-notice">
          <p>官方记录预览 · 收到 {{ linkPreview.received }} 条 · 新增 {{ linkPreview.new_records }} 条 · 重复 {{ linkPreview.duplicates }} 条；尚未写入。</p>
          <p v-if="linkPreview.failed_pools?.length" class="wuwa-warning">部分卡池读取失败 {{ linkPreview.failed_pools.join('、') }}，本次仅确认成功部分。</p>
          <button class="ui-button small-button primary" :disabled="busy" @click="confirmUrl">确认导入链接预览</button>
        </div>
        <WuwaGachaImport :account-key="accountKey" @imported="outcome=$event;load(0)" />
      </div>
    </details>
    <p v-if="busy" role="status" class="wuwa-meta">正在处理记录…</p>
    <p v-if="error" class="wuwa-error" role="alert">{{ error }}</p>
    <div v-if="outcome" class="wuwa-notice" role="status">
      <p>
        收到 {{ value(outcome.received) }} 条 · 新增
        {{ value(outcome.inserted) }} 条
      </p>
      <p v-if="outcome.state === 'need_import'">
        本次未获得记录；已有档案保持不变。
      </p>
      <p v-if="list(outcome.failed_pools).length" class="wuwa-warning">
        部分卡池导入失败：{{
          outcome.failed_pools.join('、')
        }}。仅保存成功部分。
      </p>
    </div>
    <p v-if="imageMode" class="wuwa-meta">已导入记录 {{ archive?.total ?? '未知' }} 抽 · 本次明细 {{ list(archive?.items).length }} 条；更多明细可在看板查看。</p>
    <template v-if="archive"
      ><p v-if="archive.state === 'need_import'" class="wuwa-notice">
        暂无抽卡记录，请通过上方链接或文件导入。
      </p>
      <details v-if="!imageMode" data-render-collapsed><summary>导入详情</summary><p class="wuwa-coverage">
        <span class="wuwa-meta" role="heading" aria-level="3">覆盖范围</span>
        <span class="badge badge-stale">不完整历史</span>
        <span class="wuwa-range"
          >{{ sourceTime(archive.coverage?.earliest) }} —
          {{ sourceTime(archive.coverage?.latest) }}</span
        >
        <InfoHint
          text="仅统计已导入记录，未导入或已过保留期的记录不在其中。记录时间沿用原始时区，导入时间为北京时间。"
        />
        <span class="wuwa-meta wuwa-coverage-end"
          >最近导入 {{ stamp(archive.coverage?.imported_at) }} · 来源
          {{ gachaSource(archive.coverage?.source) }}</span
        >
        <span
          v-if="list(archive.coverage?.failed_pools).length"
          class="badge badge-danger"
          >未完整获取卡池 {{ archive.coverage.failed_pools.join('、') }}</span
        >
      </p></details>
      <WuwaGachaSummary :archive="archive" :image-mode="imageMode" />
      <section class="wuwa-section">
        <h3 class="wuwa-subhead">
          各池统计<span class="wuwa-meta"
            >已导入记录 {{ value(archive.total) }} 抽</span
          >
        </h3>
        <div v-if="list(archive.pools).length" class="wuwa-tiles wuwa-pools">
          <article
            v-for="pool in list(archive.pools)"
            :key="pool.pool"
            class="wuwa-tile"
          >
            <header class="wuwa-tile-head">
              <h4>{{ pool.name || `卡池 ${pool.pool}` }}</h4>
              <span class="wuwa-tile-end wuwa-pool-total"
                ><b>{{ value(pool.total) }}</b> 抽</span
              >
            </header>
            <template v-if="rarities(pool).length">
              <div class="stack-bar" aria-hidden="true">
                <i
                  v-for="r in rarities(pool)"
                  v-show="r.size"
                  :key="r.rarity"
                  :style="{ flex: r.size, '--series': r.series }"
                ></i>
              </div>
              <ul class="legend">
                <li
                  v-for="r in rarities(pool)"
                  :key="r.rarity"
                  :style="{ '--series': r.series }"
                >
                  {{ r.label }} <b>{{ r.count }}</b>
                </li>
              </ul>
            </template>
          </article>
        </div>
      </section>
      <section class="wuwa-section">
        <h3 class="wuwa-subhead">
          五星记录<span class="wuwa-meta"
            >共 {{ value(archive.gold_total) }} 条</span
          >
        </h3>
        <template v-if="imageMode"><section v-for="group in goldGroups" :key="group.key" class="wuwa-section wuwa-pool-records"><h4 class="wuwa-subhead">{{ group.name }}</h4><WuwaDrawTable :rows="group.rows" :pool-names="poolNames" /></section><p v-if="!goldGroups.length" class="empty">暂无五星记录</p></template>
        <WuwaDrawTable v-else :rows="list(archive.gold)" :pool-names="poolNames" />
      </section>
      <details open class="wuwa-section wuwa-records-all">
        <summary>{{ imageMode ? '已导入记录（本次读取）' : '全部记录（当前页）' }}</summary>
        <template v-if="imageMode"><section v-for="group in recordGroups" :key="group.key" class="wuwa-section wuwa-pool-records"><h4 class="wuwa-subhead">{{ group.name }}</h4><WuwaDrawTable :rows="group.rows" :pool-names="poolNames" /></section><p v-if="!recordGroups.length" class="empty">暂无记录</p></template>
        <WuwaDrawTable v-else :rows="list(archive.items)" :pool-names="poolNames" />
      </details>
      <nav v-if="!imageMode" class="wuwa-pager" aria-label="抽卡档案分页">
        <button
          type="button"
          class="ui-button small-button"
          :disabled="busy || offset === 0"
          @click="load(Math.max(0, offset - 50))"
        >
          上一页</button
        ><span
          >第 {{ Math.floor(offset / 50) + 1 }} 页<InfoHint
            text="五星记录与全部记录两个列表分别分页。"
        /></span
        ><button
          type="button"
          class="ui-button small-button"
          :disabled="
            busy ||
            offset + 50 >= Math.max(archive.total || 0, archive.gold_total || 0, archive.aggregates?.total || 0)
          "
          @click="load(offset + 50)"
        >
          下一页
        </button>
      </nav></template
    ><button
      v-else-if="!busy && !imageMode"
      type="button"
      class="ui-button small-button"
      @click="load()"
    >
      刷新数据
    </button>
  </section>
</template>
