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
.ef-news-summary{--en-vivid:var(--game-vivid,var(--game-endfield-vivid));--en-vivid-2:var(--game-vivid-2,var(--game-endfield-2));min-width:0;display:grid;gap:12px;align-content:start;padding:20px;border:1px solid var(--card-border);border-radius:var(--radius-card);background:var(--card-bg);box-shadow:var(--card-shadow)}
header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
h2{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.01em}
.note,.error{font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.note{color:var(--text-muted)}
.error{color:var(--danger)}
.ef-news-summary :deep(.h-rail){--rail-gap:12px;--rail-pad-block:8px;--rail-pad:2px}
.news-rail{display:contents;list-style:none;padding:0;margin:0}
.news-card{flex:0 0 auto;scroll-snap-align:start;display:grid;grid-template-rows:auto 1fr;width:248px;overflow:hidden;border-radius:var(--radius-tile);background:var(--surface-soft);min-width:0}
.news-thumb{position:relative;display:block;height:96px;overflow:hidden;background:linear-gradient(135deg,color-mix(in srgb,var(--en-vivid) 24%,var(--card-bg)),color-mix(in srgb,var(--en-vivid-2) 12%,var(--card-bg)));box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--en-vivid) 14%,transparent)}
.news-thumb::before{content:'';position:absolute;inset:0;opacity:.55;background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--en-vivid) 14%,transparent) 0 8px,transparent 8px 16px)}
.news-thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.news-thumb.has-image::before{display:none}
.news-date{position:absolute;left:12px;bottom:10px;display:inline-flex;align-items:baseline;gap:4px;padding:2px 10px;border-radius:var(--radius-chip);background:var(--glass-strong);-webkit-backdrop-filter:var(--glass-filter);backdrop-filter:var(--glass-filter);color:var(--text);box-shadow:var(--glass-edge)}
.news-date b{font-size:18px;line-height:24px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:proportional-nums}
.news-date small{font-size:12px;color:var(--text-muted)}
.news-card.latest .news-thumb{background:linear-gradient(135deg,var(--en-vivid),var(--en-vivid-2));box-shadow:none}
.news-card.latest .news-thumb::before{opacity:.35;background:repeating-linear-gradient(135deg,rgba(255,255,255,.35) 0 8px,transparent 8px 16px)}
.news-copy{display:grid;align-content:start;gap:6px;padding:12px 14px 14px;min-width:0}
h3{font-size:14px;font-weight:500;line-height:1.55;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
h3 a{color:var(--text);text-decoration:none}
h3 a:hover{color:var(--game-endfield)}
.article-source{font-size:12px;line-height:1.7;color:var(--text-muted)}
.article-source summary{cursor:pointer}
.article-meta{display:flex;gap:2px 10px;flex-wrap:wrap;font-size:12px;line-height:1.7;color:var(--text-muted)}
footer{padding-top:2px}
@media(max-width:600px){.ef-news-summary{padding:16px;border-radius:20px}.news-card{width:224px}footer .ui-button{width:100%;justify-content:space-between}}
</style>
