<script setup>
import { computed, ref, watch } from 'vue'
import { formatTime } from '../dashboard.js'
import { ARTICLE_CATEGORIES, prepareArticles, contentNote } from '../articles.js'
import { collectionState, hasFreshPublicFallback } from '../snapshot-state.js'
import ArticleDetailDialog from './ArticleDetailDialog.vue'
import ArtworkImage from './ArtworkImage.vue'
import { articleArtwork } from '../game-visuals.js'
const props = defineProps({ snap: { type: Object, default: null }, extraSnaps: { type: Array, default: () => [] }, gameId: { type: String, default: '' }, imageMode:Boolean })
const category = ref('all'), selectedKey = ref('')
const snapshots = computed(() => [props.snap, ...props.extraSnaps].filter(Boolean))
const rows = computed(() => prepareArticles(snapshots.value).map(row=>props.imageMode?{...row,excerpt:row.excerpt.replace(/\[图片\]/g,'').replace(/\s+/g,' ').trim()}:row))
const selected = computed(() => rows.value.find(row => row.key === selectedKey.value))
const categories = computed(() => ARTICLE_CATEGORIES.map(rule => ({ ...rule, count: rows.value.filter(row => row.categoryId === rule.id).length })).filter(rule => rule.count))
const filtered = computed(() => category.value === 'all' ? rows.value : rows.value.filter(row => row.categoryId === category.value))
const stale = computed(() => snapshots.value.some(snap => snap.stale))
const errors = computed(() => [...new Set(snapshots.value.map(snap => snap.error || snap.poll_status?.error).filter(error => typeof error === 'string' && error))])
const fetchedAt = computed(() => snapshots.value.map(snap => snap.fetched_at).filter(Boolean).sort().at(-1))
const failed = computed(() => snapshots.value.some(snap => collectionState(snap) === 'failed'))
const partialFailure = computed(() => failed.value && snapshots.value.filter(snap => collectionState(snap) === 'failed').every(hasFreshPublicFallback))
const retained = computed(() => snapshots.value.some(snap => Array.isArray(snap.payload)))
const emptyText = computed(() => snapshots.value.some(snap => collectionState(snap) === 'never') ? '尚未采集公告与资讯。' : snapshots.value.some(snap => collectionState(snap) === 'collected') ? '已采集，暂无公告与资讯' : '暂无公告与资讯')
function date(value) { return value ? formatTime(value, { hour: undefined, minute: undefined }) : '' }
watch(categories, value => { if (category.value !== 'all' && !value.some(item => item.id === category.value)) category.value = 'all' })
watch(() => props.gameId, () => { selectedKey.value = ''; category.value = 'all' })
</script>
<template>
  <section class="cap-card article-list" :class="{'article-image':imageMode}">
    <div class="cap-title article-heading"><h2>公告与资讯</h2><span v-if="stale && !imageMode" class="badge badge-stale">数据可能过期</span><span v-if="fetchedAt" class="cap-meta">更新于 {{ formatTime(fetchedAt) }}</span><slot name="actions" /></div>
    <p v-if="imageMode" class="article-excerpt-note">摘要，全文请查看原文。</p>
    <template v-if="!imageMode"><p v-for="error in errors" :key="error" class="article-error" role="status">{{ error }}</p>
    <p v-if="failed" class="article-error" role="status">{{ partialFailure ? '部分来源不可用，显示可用来源数据。' : `采集失败，${retained ? '保留上次成功数据。' : '尚无公告与资讯。'}` }}</p></template>
    <nav v-if="rows.length && !imageMode" class="article-filters" aria-label="文章内容分类"><button type="button" :aria-pressed="category === 'all'" @click="category = 'all'">全部 <span>{{ rows.length }}</span></button><button v-for="item in categories" :key="item.id" type="button" :aria-pressed="category === item.id" @click="category = item.id">{{ item.label }} <span>{{ item.count }}</span></button></nav>
    <p v-if="!rows.length && !failed" class="empty" role="status">{{ emptyText }}</p>
    <ul v-if="rows.length" class="item-list">
      <li v-for="it in filtered" :key="it.key" class="item" :data-render-block="imageMode ? '' : undefined">
        <div v-if="imageMode && articleArtwork(it).length" class="article-cover qq-article-cover"><ArtworkImage :candidates="articleArtwork(it)" decorative /></div>
        <button v-if="!imageMode && articleArtwork(it).length" type="button" class="article-cover" :aria-label="`查看公告：${it.title}`" @click="selectedKey = it.key"><ArtworkImage :candidates="articleArtwork(it)" decorative /></button>
        <p class="item-title"><span v-if="imageMode" class="item-link">{{ it.title }}</span><button v-else type="button" class="item-link" @click="selectedKey = it.key">{{ it.title }}</button></p>
        <p class="item-meta"><span class="chip article-category">{{ it.categoryLabel }}</span><span v-if="it.source_name && !imageMode" class="item-source">{{ it.source_name }}</span><span v-if="it.source_stale && !imageMode" class="badge badge-stale">来源异常，保留旧记录</span><span v-if="date(it.published_at)" class="item-date">{{ date(it.published_at) }}</span></p>
        <p v-if="it.excerpt" class="item-summary">{{ it.excerpt }}</p><p v-else class="item-summary article-missing">{{ imageMode ? '正文请查看原文。' : contentNote(it) || '正文仅含图片，点击查看详情。' }}</p>
        <div v-if="it.tags.length" class="item-tags"><span v-for="tag in it.tags" :key="tag" class="chip">{{ tag }}</span></div>
        <div class="item-actions"><button v-if="!imageMode" type="button" @click="selectedKey = it.key">查看详情</button><a v-if="it.url" :href="it.url" target="_blank" rel="noopener noreferrer">原文 ↗</a></div>
      </li>
    </ul>
    <ArticleDetailDialog v-if="selected" :key="selected.key" :article="selected" @close="selectedKey = ''" />
  </section>
</template>
<style scoped>
.article-image .qq-article-cover { float:none; width:100%; height:140px; margin:0 0 12px; cursor:default; }
.article-image .qq-article-cover :deep(img) { width:100%; height:140px; object-fit:cover; }
.article-cover { display:block; float:right; width:clamp(140px,28%,240px); margin:0 0 12px 20px; padding:0; border:0; border-radius:var(--radius-well); overflow:hidden; background:var(--game-tone,var(--surface-soft)); cursor:pointer; }
.article-cover img { width:100%; aspect-ratio:16/9; }
.article-cover:not(:has(img)) { display:none; }
.item::after { content:''; display:block; clear:both; }
@media(max-width:600px) { .article-cover { float:none; width:100%; margin:0 0 12px; }.article-cover img { aspect-ratio:16/7; } }
.article-image .item-summary{display:block;-webkit-line-clamp:unset;overflow:visible;white-space:pre-wrap}
.article-excerpt-note{font-size:12px;line-height:1.8;color:var(--text-muted)}
.article-list{min-width:0}.article-heading{flex-wrap:wrap;gap:8px}.article-heading h2{font-size:16px;font-weight:600;letter-spacing:-.01em;margin:0}.article-heading .cap-meta{margin-left:auto}.article-filters{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 6px}.article-filters button{font:inherit;font-size:13px;font-weight:500;border:1px solid var(--border);border-radius:10px;padding:6px 14px;background:var(--card-bg);box-shadow:var(--btn-shadow);color:var(--text-muted);cursor:pointer;transition:color var(--duration-quick) var(--ease-smooth-out),background-color var(--duration-quick) var(--ease-smooth-out),border-color var(--duration-quick) var(--ease-smooth-out),transform var(--duration-quick) var(--ease-smooth-out)}.article-filters button:active{transform:translateY(1px)}.article-filters button[aria-pressed=true]{color:var(--accent-ink);background:var(--accent-fill);border-color:var(--accent-fill)}.article-filters button span{font-size:12px;margin-left:4px}.item-list{display:flex;flex-direction:column}.item{padding:16px 12px;margin:0 -12px;border-bottom:1px solid var(--border);transition:background-color var(--duration-quick) var(--ease-smooth-out)}.item:last-child{border-bottom:0}.item-title{margin:0;font-size:15px;font-weight:600;letter-spacing:-.005em;line-height:1.55}.item-link{padding:0;border:0;background:none;text-align:left;color:var(--text);font:inherit;cursor:pointer;overflow-wrap:anywhere}.item-link:hover{color:var(--accent)}.item-meta{display:flex;align-items:center;flex-wrap:wrap;gap:7px;margin:8px 0 0}.item-source,.item-date{font-size:12px;color:var(--text-muted)}.item-date{margin-left:auto}.item-summary{margin:8px 0 0;font-size:13px;line-height:1.75;color:var(--text-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}.item-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}.item-tags .chip{font-size:12px;color:var(--text-muted)}.item-actions{display:flex;align-items:center;gap:16px;margin-top:12px}.item-actions button,.item-actions a{border:0;background:none;padding:0;font:inherit;font-size:12px;color:var(--accent);cursor:pointer;text-decoration:none}.item-actions button:hover,.item-actions a:hover{text-decoration:underline}.article-error{font-size:12px;color:var(--danger);line-height:1.7;margin-top:10px}.article-list :focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:3px}.article-missing{font-size:12px}@media(hover:hover) and (pointer:fine){.item:hover{background:var(--overlay-2)}}.article-image .item{margin:0;padding:16px 0;border-radius:0}@media(max-width:600px){.item-date{margin-left:0}.article-heading .cap-meta{margin-left:0}.item{padding:16px 0}}
</style>
