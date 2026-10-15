<script setup>
import { isCloudMode } from '../http-client.js'
const cloudMode = isCloudMode()
import { onMounted, ref, watch } from 'vue'
import { useWuwaRequest } from '../wuwa-api.js'
import { fieldLabels, list, stamp, value } from '../wuwa-display.js'
import WuwaTower from './WuwaTower.vue'
import WuwaFields from './WuwaFields.vue'
import WuwaRoleDetail from './WuwaRoleDetail.vue'
import InfoHint from './InfoHint.vue'
import { vGlide } from '../motion.js'
const props = defineProps({
  roleNames: { type: Object, default: () => ({}) },
  accountKey: { type: String, default: '' },
})
const kind = ref('tower'),
  archive = ref(null),
  offset = ref(0),
  busy = ref(false),
  error = ref(''),
  outcome = ref(null)
function reset() {
  archive.value = null
  offset.value = 0
  busy.value = false
  error.value = ''
  outcome.value = null
}
const request = useWuwaRequest(() => props.accountKey, reset)
async function load(page = 0) {
  busy.value = true
  error.value = ''
  try {
    const result = await request.run(
      `history?kind=${kind.value}&limit=50&offset=${page}`,
    )
    if (!result) return
    archive.value = result
    offset.value = page
    busy.value = false
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}
function change(next) {
  request.cancel()
  kind.value = next
  archive.value = null
  return load()
}
async function backfill() {
  busy.value = true
  error.value = ''
  try {
    const result = await request.run('history/backfill', {})
    if (!result) return
    outcome.value = result
    await load()
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}
onMounted(() => load())
watch(
  () => props.accountKey,
  () => {
    kind.value = 'tower'
    load()
  },
)
// Delta keys are dotted source paths ("extra.total_skill_level"): label the leaf.
const deltaLabel = (key) =>
  fieldLabels[key] || fieldLabels[key.split('.').pop()] || key
const isScalar = (v) => v == null || typeof v !== 'object'
const scalarDeltas = (delta) =>
  Object.entries(delta || {}).filter(
    ([, d]) => isScalar(d?.before) && isScalar(d?.after),
  )
const nestedDeltas = (delta) =>
  Object.entries(delta || {}).filter(
    ([, d]) => !isScalar(d?.before) || !isScalar(d?.after),
  )
const signed = (n) => (typeof n === 'number' && n > 0 ? `+${n}` : n)
</script>
<template>
  <section class="wuwa-panel">
    <header class="cap-title">
      <h2>成长记录</h2>
      <InfoHint
        text="刷新数据后保存角色与玩法记录；完整角色面板需打开详情后记录。"
      />
      <button
        type="button"
        class="ui-button small-button wuwa-title-end"
        :disabled="busy"
        @click="backfill"
      >
        {{ cloudMode ? '回补本人快照' : '回补本地快照' }}
      </button>
    </header>
    <div class="wuwa-history-bar">
      <nav v-glide class="segmented" aria-label="历史类型">
        <button
          v-for="[key, name] in [
            ['tower', '跨期深塔'],
            ['roles', '角色练度变化'],
            ['role_detail', '完整面板变化'],
          ]"
          :key="key"
          type="button"
          :aria-pressed="kind === key"
          @click="change(key)"
        >
          {{ name }}
        </button>
      </nav>
      <p v-if="archive" class="wuwa-meta wuwa-bar-end">
        开始记录 {{ stamp(archive.archive_started_at) }}（北京时间） ·
        累计 {{ value(archive.total) }} 条记录
      </p>
    </div>
    <p v-if="busy" role="status" class="wuwa-meta">正在读取历史…</p>
    <p v-if="error" class="wuwa-error" role="alert">{{ error }}</p>
    <p v-if="outcome" class="wuwa-notice">
      回补新增 {{ value(outcome.inserted) }} 条。{{ outcome.message }}
    </p>
    <template v-if="archive"
      ><p v-if="!list(archive.items).length" class="wuwa-notice">
        暂无记录，请刷新数据或回补历史。
      </p>
      <ul v-else class="wuwa-history">
        <li v-for="item in list(archive.items)" :key="item.id">
          <header class="wuwa-history-head">
            <h3 v-if="kind === 'tower'">
              赛季结束 {{ stamp(item.season) }}（北京时间）
            </h3>
            <h3 v-else>
              {{
                item.payload?.name ||
                item.payload?.data?.role?.role_name ||
                item.payload?.role?.role_name ||
                `角色 ${item.subject}`
              }}
            </h3>
            <span
              class="badge"
              :class="item.delta == null ? 'wuwa-badge-off' : 'wuwa-badge-on'"
              >{{
                item.delta == null ? '首次记录' : '有变化'
              }}</span
            >
            <span class="wuwa-meta wuwa-history-times"
              >记录时间 {{ stamp(item.observed_at) }}（北京时间）</span
            >
          </header>
          <table
            v-if="scalarDeltas(item.delta).length"
            class="data-table wuwa-deltas"
          >
            <thead>
              <tr>
                <th>项目</th>
                <th class="num">之前</th>
                <th class="num">之后</th>
                <th class="num">变化量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[key, delta] in scalarDeltas(item.delta)" :key="key">
                <td>{{ deltaLabel(key) }}</td>
                <td class="num">{{ value(delta?.before) }}</td>
                <td class="num">{{ value(delta?.after) }}</td>
                <td class="num">
                  {{ delta?.delta == null ? '—' : signed(delta.delta) }}
                </td>
              </tr>
            </tbody>
          </table>
          <details
            v-for="[key, delta] in nestedDeltas(item.delta)"
            :key="key"
            class="wuwa-supplement"
            open
          >
            <summary>{{ deltaLabel(key) }}</summary>
            <div class="wuwa-compare">
              <section>
                <p class="wuwa-field-label" role="heading" aria-level="5">之前</p>
                <WuwaFields :data="delta?.before" />
              </section>
              <section>
                <p class="wuwa-field-label" role="heading" aria-level="5">之后</p>
                <WuwaFields :data="delta?.after" />
              </section>
            </div>
            <p v-if="delta?.delta != null" class="wuwa-meta">
              变化量 {{ delta.delta }}
            </p>
          </details>
          <details class="wuwa-supplement">
            <summary>查看本次记录详情</summary>
            <WuwaTower
              v-if="kind === 'tower'"
              :data="item.payload"
              :role-names="roleNames"
            /><WuwaRoleDetail
              v-else-if="kind === 'role_detail'"
              :data="item.payload?.data || item.payload"
            /><WuwaFields v-else :data="item.payload" />
          </details>
        </li>
      </ul>
      <nav class="wuwa-pager" aria-label="历史分页">
        <button
          type="button"
          class="ui-button small-button"
          :disabled="busy || offset === 0"
          @click="load(Math.max(0, offset - 50))"
        >
          上一页</button
        ><span>第 {{ Math.floor(offset / 50) + 1 }} 页</span
        ><button
          type="button"
          class="ui-button small-button"
          :disabled="busy || offset + 50 >= archive.total"
          @click="load(offset + 50)"
        >
          下一页
        </button>
      </nav></template
    ><button
      v-else-if="!busy"
      type="button"
      class="ui-button small-button"
      @click="load()"
    >
      刷新数据
    </button>
  </section>
</template>
