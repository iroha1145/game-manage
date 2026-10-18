import { safeUrl } from './calendar.js'

// Pictures follow explicit source links; dates and nearby headlines are not ownership evidence.
function pictures(row) {
  if (!row || typeof row !== 'object') return []
  return [row.banner, row.image_url, ...(Array.isArray(row.image_urls) ? row.image_urls : []), ...(Array.isArray(row.images) ? row.images : [])].map(safeUrl).filter(Boolean)
}
const ident = value => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
function sourceKey(value) {
  const safe = safeUrl(value)
  if (!safe) return null
  const url = new URL(safe)
  if (url.hostname === 'www.tajiduo.com' && url.pathname === '/bbs/index.html' && url.hash.startsWith('#/post?')) {
    const id = new URLSearchParams(url.hash.slice(7)).get('postId')
    if (/^\d+$/.test(id || '')) return `tajiduo:${id}`
  }
  // NTE keeps the API URL in events and the public reading URL in announcements.
  if (url.hostname === 'bbs-api.tajiduo.com' && url.pathname === '/bbs/wapi/getPostFull') {
    const id = url.searchParams.get('postId')
    if (/^\d+$/.test(id || '')) return `tajiduo:${id}`
  }
  const post = url.hostname === 'bbs.tajiduo.com' && url.pathname.match(/^\/forum\/post\/(\d+)\/?$/)
  return post ? `tajiduo:${post[1]}` : safe
}
function sameSource(ref, article) {
  if (!ref || !article) return false
  if (ref.source && article.source && ref.source !== article.source) return false
  const version = ident(ref.version_id || ref.version), articleVersion = ident(article.version_id || article.version)
  if (version && articleVersion && version !== articleVersion) return false
  const url = sourceKey(ref.source_url || ref.url)
  const articleUrls = [article.url, ...(Array.isArray(article.original_links) ? article.original_links.map(link => link?.url) : [])].map(sourceKey).filter(Boolean)
  if (url && articleUrls.includes(url)) return true
  // A contradictory original URL must not be overridden by a coincidentally reused numeric ID.
  if (url && articleUrls.length) return false
  const id = ident(ref.source_post_id || ref.article_id || ref.post_id)
  return !!id && [article.id, article.article_id, article.post_id].some(value => ident(value) === id)
}

/** Ordered image candidates for one event. Snapshots use the dashboard's game -> capability shape. */
export function eventArtwork(event, snapshots = {}) {
  if (!event || typeof event !== 'object') return []
  const game = snapshots[event.gameId || event.game_id] || {}
  const articles = [...(Array.isArray(game.events?.artwork_sources) ? game.events.artwork_sources : []), ...['announcement', 'news'].flatMap(capability => Array.isArray(game[capability]?.payload) ? game[capability].payload : [])].filter(row => row && typeof row === 'object')
  const supplements = Array.isArray(event.supplement_sources) ? event.supplement_sources.filter(row => row && typeof row === 'object') : []
  const output = [...pictures(event), ...supplements.flatMap(pictures), ...articles.filter(article => sameSource(event, article)).flatMap(pictures)]
  const version = ident(event.version_id || event.version)
  const metadata = [event.version_metadata, game.events?.version_metadata].filter(meta => meta && typeof meta === 'object' && version && ident(meta.id || meta.version_id) === version)
  for (const meta of metadata) {
    output.push(...pictures(meta))
    // The start source is the declared version notice. Other sources may only describe maintenance.
    output.push(...articles.filter(article => sameSource(meta.start_source, article)).flatMap(pictures))
  }
  return [...new Set(output)]
}
