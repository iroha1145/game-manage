import { eventStatus, parseBeijingTime, safeUrl } from './calendar.js'
import { prepareArticles } from './articles.js'
import { eventArtwork } from './event-artwork.js'
import { officialGameBanners } from './game-artwork.js'

const uniqueImages = values => [...new Set(values.map(safeUrl).filter(Boolean))]

export function articleArtwork(article) {
  return uniqueImages([article?.banner, article?.image_url, ...(Array.isArray(article?.images) ? article.images : [])])
}

/** Game decoration, never used to identify an event's version or its dates. */
export function gameBanner(gameId, snapshots = {}, now = Date.now()) {
  const events = Array.isArray(snapshots.events?.payload) ? snapshots.events.payload : []
  const active = events.filter(event => event && ['进行中', '常驻开放'].includes(eventStatus(event, now)))
  const linked = active.flatMap(event => eventArtwork({ ...event, gameId }, { [gameId]: snapshots }))
  const articles = prepareArticles([snapshots.news, snapshots.announcement]).filter(article => {
    const time = parseBeijingTime(article.published_at)
    return time == null || time <= now
  })
  return uniqueImages([
    ...linked,
    ...articles.filter(article => article.categoryId === 'version').flatMap(articleArtwork),
    ...articles.flatMap(articleArtwork),
    ...(officialGameBanners[gameId] || []),
  ])
}

/** Keep supplied pictures attached to their own character; never substitute another role. */
export function roleArtwork(role) {
  return uniqueImages([role?.icon_url, role?.avatar_url, role?.role_icon_url, role?.portrait_url])
}

export function gameRoster(snapshots = {}) {
  const payload = snapshots.roles?.payload || snapshots.operators?.payload
  const rows = Array.isArray(payload) ? payload : payload?.entries
  return Array.isArray(rows) ? rows.filter(row => row && typeof row === 'object') : []
}
