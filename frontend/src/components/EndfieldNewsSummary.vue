<script setup>
import { computed } from 'vue'
import { prepareArticles } from '../articles.js'
import { collectionState, hasFreshPublicFallback } from '../snapshot-state.js'
import { displayBeijing } from '../time.js'
const props=defineProps({ snapshots:{type:Array,default:()=>[]} })
const emit=defineEmits(['all'])
const snapshots=computed(()=>props.snapshots.filter(Boolean))
const articles=computed(()=>prepareArticles(snapshots.value).slice(0,5))
const failures=computed(()=>snapshots.value.filter(snap=>collectionState(snap)==='failed'))
const partial=computed(()=>failures.value.length>0 && failures.value.every(hasFreshPublicFallback))
const stale=computed(()=>snapshots.value.some(snap=>snap.stale))
const errors=computed(()=>[...new Set(snapshots.value.map(snap=>snap.error || snap.poll_status?.error).filter(error=>typeof error==='string' && error))])
const fetchedAt=computed(()=>snapshots.value.map(snap=>snap.fetched_at).filter(Boolean).sort().at(-1))
const empty=computed(()=>!snapshots.value.length || snapshots.value.some(snap=>collectionState(snap)==='never')
  ? '尚未采集公告快照，可前往公告与资讯查看来源状态。'
  : snapshots.value.some(snap=>collectionState(snap)==='collected') ? '已采集，暂无公告与资讯。' : '尚无可显示的公告快照。')
function published(value) {
  if (!value) return '发布时间未提供'
  const formatted=displayBeijing(value)
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? formatted.slice(0,10) : formatted
}
</script>
<template>
  <section class="ef-news-summary" aria-label="最新公告">
    <header><div><p class="kicker">06 / PUBLIC BULLETIN</p><h2>最新公告</h2></div><span v-if="stale" class="badge badge-stale">已有公告待更新</span></header>
    <p v-if="fetchedAt" class="note">快照更新于 {{ displayBeijing(fetchedAt) }}（北京时间）</p>
    <p v-for="error in errors" :key="error" class="error" role="status">{{ error }}</p>
    <p v-if="failures.length" class="error" role="status">{{ partial ? '部分来源不可用，显示可用来源数据。' : articles.length ? '采集失败，保留上次成功公告，请留意更新时间。' : '采集失败，尚无可显示的公告快照。' }}</p>
    <ol v-if="articles.length"><li v-for="(article,index) in articles" :key="article.key"><span class="article-number">{{ String(index+1).padStart(2,'0') }}</span><div><h3><a v-if="article.url" :href="article.url" target="_blank" rel="noopener noreferrer">{{ article.title }} ↗</a><span v-else>{{ article.title }}</span></h3><p class="article-meta"><span>{{ article.source_name || '来源未提供' }}</span><span>{{ article.categoryLabel }}</span><span v-if="article.source_stale" class="badge badge-stale">待更新</span><span>{{ published(article.published_at) }}</span></p></div></li></ol>
    <p v-else-if="!failures.length" class="note">{{ empty }}</p>
    <footer><span class="note">仅展示已有快照中的最新 5 条</span><button type="button" class="ui-button" @click="emit('all')">查看全部公告 →</button></footer>
  </section>
</template>
<style scoped>
.ef-news-summary{min-width:0;display:grid;gap:14px;padding:22px;border:1px solid var(--border);border-top:2px solid var(--game-endfield);background:var(--card-bg)}header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.kicker{font-family:var(--font-mono);font-size:10px;letter-spacing:.12em;color:var(--text-muted);margin-bottom:7px}h2{font-size:21px}.note,.error{font-size:12px;line-height:1.8;overflow-wrap:anywhere}.note{color:var(--text-muted)}.error{color:var(--danger)}ol{list-style:none;padding:0;margin:0}li{display:flex;gap:16px;padding:15px 0;border-top:1px solid var(--border);min-width:0}li>div{min-width:0;flex:1}.article-number{font-family:var(--font-mono);font-size:12px;color:var(--game-endfield);line-height:1.8}h3{font-size:13px;font-weight:500;line-height:1.8;overflow-wrap:anywhere}h3 a{color:var(--text);text-decoration:none}h3 a:hover{color:var(--game-endfield)}.article-meta{display:flex;gap:5px 12px;flex-wrap:wrap;margin-top:7px;font-size:11px;line-height:1.7;color:var(--text-muted)}footer{border-top:1px solid var(--border);padding-top:14px}.ui-button{border-radius:0;min-height:40px}@media(max-width:600px){.ef-news-summary{padding:16px}h2{font-size:19px}li{gap:12px}footer .ui-button{width:100%;justify-content:space-between}}
</style>
