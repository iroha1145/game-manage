<script setup>
import { computed, ref } from 'vue'
import { prepareArticles } from '../articles.js'
import { collectionState, hasFreshPublicFallback } from '../snapshot-state.js'
import { displayBeijing } from '../time.js'
import { vReveal } from '../motion.js'
import HRail from './HRail.vue'
const props=defineProps({ snapshots:{type:Array,default:()=>[]} })
const emit=defineEmits(['all'])
const snapshots=computed(()=>props.snapshots.filter(Boolean))
const articles=computed(()=>prepareArticles(snapshots.value).slice(0,5))
const failures=computed(()=>snapshots.value.filter(snap=>collectionState(snap)==='failed'))
const partial=computed(()=>failures.value.length>0 && failures.value.every(hasFreshPublicFallback))
const stale=computed(()=>snapshots.value.some(snap=>snap.stale))
const hasFailure=computed(()=>failures.value.length>0 || snapshots.value.some(snap=>snap.error || snap.poll_status?.error))
const fetchedAt=computed(()=>snapshots.value.map(snap=>snap.fetched_at).filter(Boolean).sort().at(-1))
const empty=computed(()=>!snapshots.value.length || snapshots.value.some(snap=>collectionState(snap)==='never')
  ? '暂无公告，可前往公告与资讯查看。'
  : snapshots.value.some(snap=>collectionState(snap)==='collected') ? '暂无公告与资讯。' : '暂时无法显示公告，请稍后重试。')
function published(value) {
  if (!value) return '发布时间未提供'
  const formatted=displayBeijing(value)
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? formatted.slice(0,10) : formatted
}
// The card's date tile reads the Beijing day straight from the formatted date: no extra time maths.
function day(value) {
  const match = value ? /^\d{4}-(\d{2})-(\d{2})/.exec(displayBeijing(value)) : null
  return match ? { month: `${Number(match[1])}月`, date: match[2] } : null
}
// An article image that fails to load falls back to the date tile.
const broken = ref(new Set())
const image = article => article.images?.find(url => !broken.value.has(url)) || null
const hide = url => { broken.value = new Set([...broken.value, url]) }
</script>
<template>
  <section v-reveal class="ef-news-summary" aria-label="最新公告">
    <header><div><h2>最新公告</h2></div><span v-if="stale" class="badge badge-stale">已有公告待更新</span></header>
    <p v-if="fetchedAt" class="note">更新于 {{ displayBeijing(fetchedAt) }}（北京时间）</p>
    <p v-if="hasFailure" class="error" role="status">{{ partial ? '部分公告暂未更新，先显示已有内容。' : articles.length ? '公告暂时无法更新，显示上次内容；稍后可前往公告与资讯重试。' : '公告暂时无法更新，稍后可前往公告与资讯重试。' }}</p>
    <HRail v-if="articles.length" label="最新公告">
      <!-- display:contents hands the cards to the rail while the list keeps its semantics. -->
      <ol class="news-rail" role="list"><li v-for="(article,index) in articles" :key="article.key" class="news-card" :class="{ latest: index === 0 }">
        <span class="news-thumb" :class="{ 'has-image': !!image(article) }"><img v-if="image(article)" :src="image(article)" alt="" loading="lazy" referrerpolicy="no-referrer" @error="hide(image(article))" /><span v-if="day(article.published_at)" class="news-date" aria-hidden="true"><b>{{ day(article.published_at).date }}</b><small>{{ day(article.published_at).month }}</small></span></span>
        <div class="news-copy"><h3><a v-if="article.url" :href="article.url" target="_blank" rel="noopener noreferrer">{{ article.title }} ↗</a><span v-else>{{ article.title }}</span></h3><p class="article-meta"><span>{{ article.categoryLabel }}</span><span v-if="article.source_stale" class="badge badge-stale">待更新</span><span>{{ published(article.published_at) }}</span></p><details v-if="article.source_name" class="article-source"><summary>公告来源</summary><span>{{ article.source_name }}</span></details></div>
      </li></ol>
    </HRail>
    <p v-else-if="!hasFailure" class="note">{{ empty }}</p>
    <footer><span class="note">最新 5 条</span><button type="button" class="ui-button" @click="emit('all')">查看全部公告 →</button></footer>
  </section>
</template>
<style scoped>
.ef-news-summary{--en-tone:var(--game-tone,var(--game-endfield-tone));--en-ink:var(--game-accent,var(--game-endfield));min-width:0;display:grid;gap:12px;align-content:start;padding:20px;border:1px solid var(--card-border);border-radius:var(--radius-card);background:var(--card-bg);box-shadow:var(--card-shadow)}
header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
h2{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.02em}
.note,.error{font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.note{color:var(--text-muted)}
.error{color:var(--danger)}
.ef-news-summary :deep(.h-rail){--rail-gap:16px;--rail-pad-block:8px;--rail-pad:2px}
.news-rail{display:contents;list-style:none;padding:0;margin:0}
/* Each item is a tone panel with the date, then its text on the card itself: no box inside the card. */
.news-card{flex:0 0 auto;scroll-snap-align:start;display:grid;grid-template-rows:auto 1fr;width:248px;min-width:0}
.news-thumb{position:relative;display:block;height:96px;overflow:hidden;border-radius:var(--radius-well);background:var(--en-tone)}
.news-thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.news-date{position:absolute;left:10px;bottom:10px;display:inline-flex;align-items:baseline;gap:4px;padding:2px 8px;border-radius:var(--radius-chip);background:var(--card-bg);color:var(--en-ink)}
.news-date b{font-size:18px;line-height:24px;font-weight:550;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.news-date small{font-size:12px;color:var(--text-muted)}
/* With no picture the date is the picture: large, in the tone's ink. */
.news-thumb:not(.has-image) .news-date{left:14px;top:12px;bottom:auto;padding:0;background:transparent}
.news-thumb:not(.has-image) .news-date b{font-size:32px;line-height:36px;letter-spacing:-.05em}
.news-thumb:not(.has-image) .news-date small{color:var(--en-ink)}
.news-copy{display:grid;align-content:start;gap:6px;padding:10px 2px 2px;min-width:0}
h3{font-size:14px;font-weight:500;line-height:1.55;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
h3 a{color:var(--text);text-decoration:none}
@media(hover:hover) and (pointer:fine){h3 a:hover{color:var(--en-ink)}}
.article-source{font-size:12px;line-height:1.7;color:var(--text-muted)}
.article-source summary{cursor:pointer}
.article-meta{display:flex;gap:2px 10px;flex-wrap:wrap;font-size:12px;line-height:1.7;color:var(--text-muted)}
footer{padding-top:2px}
@media(max-width:600px){.ef-news-summary{padding:16px;border-radius:22px}.news-card{width:224px}footer .ui-button{width:100%;justify-content:space-between}}
</style>
