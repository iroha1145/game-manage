import test from 'node:test'
import assert from 'node:assert/strict'
import { eventArtwork } from './event-artwork.js'
const image = name => `https://images.example.com/${name}.jpg`
const article = { id:'123', url:'https://official.example.com/post/123', source:'official', images:[image('notice')] }
const snapshots = { nte:{announcement:{payload:[article]},news:{payload:[{id:'else',published_at:'2026-10-17',images:[image('unrelated')]}]}} }

test('three games with identical notice and version IDs still select their own artwork', () => {
  const games = ['nte', 'wuthering_waves', 'endfield']
  const rows = Object.fromEntries(games.map(game => [game, {
    news: { payload: [{ id:'123', images:[image(game)] }] },
    events: { version_metadata:{ id:'1.4', banner:image(`${game}-version`), start_source:{post_id:'123'} } },
  }]))
  for (const game of games) {
    assert.deepEqual(eventArtwork({gameId:game,post_id:'123'},rows),[image(game)])
    assert.deepEqual(eventArtwork({gameId:game,version:'1.4'},rows),[image(`${game}-version`),image(game)])
    assert.deepEqual(eventArtwork({gameId:game,post_id:'missing',version:'missing'},rows),[])
  }
})

test('explicitly contradictory versions cannot share artwork even at the same source ID',()=>{
  const rows={nte:{news:{payload:[{id:'123',version:'1.3',images:[image('old')]}]}}}
  assert.deepEqual(eventArtwork({gameId:'nte',source_post_id:'123',version:'1.4'},rows),[])
})
test('verified Tajiduo hash-route reading URLs share only the exact numeric post ID',()=>{
  const rows={nte:{news:{payload:[{url:'https://www.tajiduo.com/bbs/index.html#/post?postId=123&id=2',images:[image('exact')]}]}}}
  assert.deepEqual(eventArtwork({gameId:'nte',source_url:'https://bbs-api.tajiduo.com/bbs/wapi/getPostFull?postId=123'},rows),[image('exact')])
})
test('event artwork prefers direct event pictures and exact original notice matches without mutating input', () => {
  const event = { gameId:'nte',source_url:article.url, banner:image('banner'),image_urls:[image('event'),image('event')] }
  const before = JSON.stringify({ event,snapshots })
  assert.deepEqual(eventArtwork(event,snapshots),[image('banner'),image('event'),image('notice')])
  assert.equal(JSON.stringify({ event,snapshots }),before)
})
test('post and article identities match only within the same game and compatible source', () => {
  assert.deepEqual(eventArtwork({gameId:'nte',source_post_id:'123',source:'official'},snapshots),[image('notice')])
  assert.deepEqual(eventArtwork({gameId:'nte',article_id:123},snapshots),[image('notice')])
  assert.deepEqual(eventArtwork({gameId:'other',source_post_id:'123'},snapshots),[])
  assert.deepEqual(eventArtwork({gameId:'nte',source_post_id:'123',source:'other'},snapshots),[])
  assert.deepEqual(eventArtwork({gameId:'nte',source_post_id:'123',source_url:'https://other.example.com/123'},snapshots),[])
  assert.deepEqual(eventArtwork({gameId:'nte',name:'活动',start_date:'2026-10-17',source_title:'官方公告'},snapshots),[])
})
test('version fallback follows matching version metadata and its declared version notice only', () => {
  const rows={nte:{...snapshots.nte,events:{version_metadata:{id:'1.4',banner:image('version'),start_source:{post_id:'123'},sources:[{post_id:'else'}]}}}}
  assert.deepEqual(eventArtwork({gameId:'nte',version:'1.4'},rows),[image('version'),image('notice')])
  assert.deepEqual(eventArtwork({gameId:'nte',version:'1.3'},rows),[])
  assert.deepEqual(eventArtwork({gameId:'nte'},rows),[])
})
test('unsafe and malformed image candidates never reach an image element', () => {
  assert.deepEqual(eventArtwork({ image_urls:['javascript:alert(1)','data:image/png,bad','/image.png','https://user:pass@example.com/x','https://example.com/\nx'],images:[null,{},image('safe')] }),[image('safe')])
  for (const value of [null,undefined,'text',42]) assert.deepEqual(eventArtwork(value,snapshots),[])
})
test('NTE API and public notice links share the verified post identity', () => {
  const rows={nte:{announcement:{payload:[{id:'123',url:'https://bbs.tajiduo.com/forum/post/123',source:'community',images:[image('nte')]}]}}}
  assert.deepEqual(eventArtwork({gameId:'nte',source_url:'https://bbs-api.tajiduo.com/bbs/wapi/getPostFull?postId=123',source:'community'},rows),[image('nte')])
  assert.deepEqual(eventArtwork({gameId:'nte',source_url:'https://unrelated.example.com/bbs/wapi/getPostFull?postId=123',source_post_id:'123'},rows),[])
})


test('lean calendar artwork sources preserve game and version ownership without news bodies',()=>{
  const snapshot={nte:{events:{artwork_sources:[{...article,version:'1.4'}]}}}
  assert.deepEqual(eventArtwork({gameId:'nte',source_url:article.url,source:'official',version:'1.4'},snapshot),[image('notice')])
  assert.deepEqual(eventArtwork({gameId:'nte',source_url:article.url,source:'official',version:'1.3'},snapshot),[])
  assert.deepEqual(eventArtwork({gameId:'endfield',source_url:article.url,source:'official',version:'1.4'},snapshot),[])
})

test('matched supplementary notice pictures survive public calendar merging without unrelated news', () => {
  const event = { gameId:'nte', source:'bilibili', source_url:'https://www.bilibili.com/read/cv123',
    supplement_sources:[{source:'community', source_post_id:'42', image_urls:[image('supplement'), 'javascript:bad']} ] }
  assert.deepEqual(eventArtwork(event,snapshots),[image('supplement')])
})
