import test from 'node:test'
import assert from 'node:assert/strict'
import { articleArtwork, gameBanner, gameRoster, roleArtwork } from './game-visuals.js'
import { officialGameBanners } from './game-artwork.js'

test('game banners prefer a running event source over newer unrelated news and future announcements', () => {
  const snapshots = {
    events: { payload: [{ name: '活动', start_at: '2026-10-01', end_at: '2026-10-30', source_url: 'https://example.com/current' }] },
    news: { payload: [
      { title: '版本更新说明', published_at: '2026-11-01', images: ['https://example.com/future.jpg'] },
      { title: '社区资讯', published_at: '2026-10-16', images: ['https://example.com/news.jpg'] },
      { title: '当前活动', url: 'https://example.com/current', published_at: '2026-10-01', images: ['https://example.com/current.jpg'] },
    ] },
  }
  const banners = gameBanner('nte', snapshots, Date.parse('2026-10-17T12:00:00+08:00'))
  assert.equal(banners[0], 'https://example.com/current.jpg')
  assert.ok(!banners.includes('https://example.com/future.jpg'))
  assert.deepEqual(banners.slice(-officialGameBanners.nte.length), officialGameBanners.nte)
  assert.deepEqual(gameBanner('unknown'), [])
})

test('article and character images reject unsafe URLs and preserve source-specific fallback order', () => {
  assert.deepEqual(articleArtwork({ images: ['javascript:alert(1)', 'https://example.com/a.jpg', 'https://example.com/a.jpg'] }), ['https://example.com/a.jpg'])
  assert.deepEqual(roleArtwork({ icon_url: 'javascript:bad', avatar_url: 'https://example.com/avatar.png', portrait_url: 'https://example.com/portrait.png' }), ['https://example.com/avatar.png', 'https://example.com/portrait.png'])
  assert.deepEqual(roleArtwork(null), [])
  assert.deepEqual(gameRoster({ roles: { payload: { entries: [null, { name: '角色' }] } } }), [{ name: '角色' }])
  assert.deepEqual(gameRoster({ operators: { payload: { entries: [{ name: '干员', avatar_url: 'https://example.com/operator.png' }] } } }).map(roleArtwork), [['https://example.com/operator.png']])
})
