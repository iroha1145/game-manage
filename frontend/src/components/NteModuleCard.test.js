import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'

const Module = await loadVue(new URL('./NteModuleCard.vue', import.meta.url))
const snap = payload => ({ payload: { schema_version: 1, ...payload }, fetched_at: '2026-10-17T12:14:00+08:00', stale: false })
const card = (t, capability, payload, extra = {}) => mount(t, Module, { capability, snap: snap(payload), ...extra })
const byClass = (root, name) => {
  const hits = []
  const walk = node => { if (String(node.props?.class ?? '').split(/\s+/).includes(name)) hits.push(node); node.children.forEach(walk) }
  walk(root)
  return hits
}
const button = (root, label) => nodes(root, 'button').find(n => content(n) === label)

test('every summary says what is missing instead of inventing a value or a number', t => {
  const payloads = {
    account: { nickname: null }, stamina: { current: null }, progress: { completed: null, categories: [{ name: '主线' }] }, roles: { entries: [{ name: '甲' }] },
    exploration: { areas: [{ name: '区域', details: [{ name: '宝箱' }] }] }, realestate: { entries: [{ name: '房' }] }, vehicles: { entries: [{ name: '车' }] },
    teams: { entries: [{ name: '队' }] }, gacha: { pools: [{ name: '池' }] },
  }
  for (const [capability, payload] of Object.entries(payloads)) {
    const text = content(card(t, capability, payload))
    assert.doesNotMatch(text, /NaN|Infinity|undefined|null/, capability)
  }
  assert.match(content(card(t, 'account', { nickname: null })), /未知/)
})

test('a missing or outdated snapshot is told apart and still offers the details button', t => {
  assert.match(content(mount(t, Module, { capability: 'roles', snap: null })), /暂无数据，请刷新后查看/)
  const legacy = mount(t, Module, { capability: 'gacha', snap: { payload: { raw: true } } })
  assert.match(content(legacy), /数据格式已更新，请刷新/)
  assert.ok(button(legacy, '查看抽卡统计'))
})

test('account keeps the name, the four levels and the owned counts as rings, and leaves the UID to the details', t => {
  const root = card(t, 'account', { nickname: '零', role_id: '123456', server_name: '亚服', level: 52, world_level: 6, tycoon_level: 8, active_days: 131, character_count: 12,
    achievement_count: 286, achievement_total: 520, house_count: 3, house_total: null, vehicle_count: 0, vehicle_total: 12 })
  const text = content(root)
  for (const expected of ['零', '亚服', '等级 52', '世界等级 6', '大亨等级 8', '活跃天数 131 天', '角色数 12', '成就 286 / 520', '房产 3 / 未知', '载具 0 / 12']) assert.ok(text.includes(expected), expected)
  assert.doesNotMatch(text, /123456/)
  const meters = nodes(root, 'div').filter(n => n.props.role === 'meter')
  assert.deepEqual(meters.map(n => n.props['aria-label']), ['成就', '载具'], 'a ring needs both counts; zero still draws')
  assert.ok(button(root, '查看账号档案'))
})

test('stamina draws a ring per measurable resource, each with a hidden native progress, and offers no button', t => {
  const root = card(t, 'stamina', { current: 0, maximum: 320, city_current: null, city_maximum: 100, daily_activity: 50, weekly_remaining: 0 })
  assert.deepEqual(nodes(root, 'progress').map(n => [n.props['aria-label'], n.props.value, n.props.max]), [['本性像素', 0, 320], ['日常活跃', 50, 100]])
  assert.ok(nodes(root, 'progress').every(n => String(n.props.class).includes('sr-only')))
  assert.match(content(root), /0 \/ 320/)
  assert.match(content(root), /未知 \/ 100/)
  assert.match(content(root), /周本剩余 · 0/)
  assert.equal(nodes(root, 'button').length, 0)
  assert.match(content(card(t, 'stamina', { current: 1, maximum: 2, weekly_remaining: null })), /周本剩余 · 未提供/)
})

test('achievements split the medals by tier, keep an unknown tier unknown, and list every category', t => {
  const root = card(t, 'progress', { completed: 286, total: 520, gold: 40, silver: null, bronze: 150, categories: [{ id: 'a', name: '主线', current: 60, total: 60 }, { id: 'b', name: '支线', current: 88, total: 120 }] })
  const text = content(root)
  assert.match(text, /金奖章 40/)
  assert.match(text, /银奖章 未知/)
  assert.match(text, /铜奖章 150/)
  assert.match(text, /主线 60 \/ 60/)
  assert.match(text, /支线 88 \/ 120/)
  assert.equal(nodes(root, 'progress').length, 1)
  assert.equal(nodes(byClass(root, 'stack-bar')[0], 'i').length, 2, 'the stack holds only the tiers that are known and above zero')
})

test('the roster lists the strongest roles first, counts them by quality, and falls back to a letter tile', async t => {
  const entries = [
    { id: '1', name: '乙', quality: 'A', element: '光', level: 60, icon_url: 'https://example.com/b.png' },
    { id: '2', name: '甲', quality: 'S', element: '光', level: 40, icon_url: 'javascript:alert(1)' },
    { id: '3', name: '丙', quality: 'S', element: '魂', level: 55, icon_url: 'https://example.com/c.png' },
  ]
  const root = card(t, 'roles', { entries })
  assert.deepEqual(byClass(root, 'role-tile').map(n => content(nodes(n, 'strong')[0])), ['丙', '甲', '乙'])
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), ['https://example.com/c.png', 'https://example.com/b.png'], 'an unsafe address is never loaded')
  assert.match(content(root), /S\s+2 名.*A\s+1 名/)
  assert.match(content(root), /平均等级 52/)
  const first = nodes(root, 'img')[0]
  first.props.onError(); await nextTick()
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), ['https://example.com/b.png'])
  assert.match(content(byClass(root, 'role-tile')[0]), /丙/)
  assert.ok(button(root, '查看角色练度'))
})

test('exploration shows each area as a ring with its detail lines and marks an area beyond its target', t => {
  const root = card(t, 'exploration', { areas: [
    { id: 'a', name: '中心区', current: 96, total: 100, details: [{ name: '宝箱', current: 48, total: 50 }, { name: '壁画', current: null, total: 10 }] },
    { id: 'b', name: '轨外', current: 105, total: 100, details: [] },
    { id: 'c', name: '无分母', current: 2, total: 0, details: [] },
  ] })
  const text = content(root)
  assert.match(text, /中心区 96 \/ 100/)
  assert.match(text, /宝箱 48 \/50/)
  assert.match(text, /壁画 未知 \/10/)
  assert.equal((text.match(/已达目标/g) || []).length, 1)
  assert.doesNotMatch(text, /105%/)
  assert.deepEqual(nodes(root, 'div').filter(n => n.props.role === 'meter').map(n => n.props['aria-label']), ['中心区', '轨外'])
  assert.match(content(card(t, 'exploration', { areas: [] })), /暂无探索数据/)
})

test('houses and vehicles show ownership, name only residents the catalog knows, and mark the vehicle on show', t => {
  const houses = card(t, 'realestate', { owned_count: 3, total: 8, entries: [
    { name: '滨海公寓', owned: true, resident_ids: ['1004', '9999'], furniture: [{ owned: true }, { owned: false }] },
    { name: '旧城阁楼', owned: false, resident_ids: [], furniture: [] },
    { name: '工作室', owned: null },
  ] })
  const text = content(houses)
  assert.match(text, /拥有 3 \/ 8/)
  assert.match(text, /滨海公寓 1 \/2 件家具/)
  assert.match(text, /已拥有/); assert.match(text, /未拥有/); assert.match(text, /状态未知/)
  assert.match(text, /暂无入住/)
  assert.equal(nodes(houses, 'span').filter(n => n.props['data-size'] === 'small').length, 1, 'only the resident the catalog names gets a tile')
  const cars = card(t, 'vehicles', { owned_count: 1, total: 4, show_id: 'v2', show_name: '街道之星', entries: [
    { id: 'v1', name: '甲', owned: true, base: [{ name: '极速', value: '146 km/h' }] }, { id: 'v2', name: '乙', owned: true, base: [] },
  ] })
  assert.match(content(cars), /展示载具：街道之星/)
  assert.deepEqual(byClass(cars, 'showcase').map(n => content(nodes(n, 'strong')[0])), ['乙'])
  assert.match(content(cars), /展示中/)
  assert.match(content(cars), /极速 146 km\/h/)
})

test('official teams lead with their first usable picture and fall back to a letter when it breaks', async t => {
  const root = card(t, 'teams', { entries: [
    { id: 't1', name: '光魂速攻队', description: '主 C 与治疗。', icon_url: 'javascript:bad', image_urls: ['data:image/png,bad', 'https://example.com/team.png', 'https://example.com/second.png'] },
    { id: 't2', name: '无图队', image_urls: [] },
  ] })
  const pictures = nodes(root, 'img')
  assert.deepEqual(pictures.map(n => n.props.src), ['https://example.com/team.png'])
  assert.equal(pictures[0].props.alt, '光魂速攻队配队图')
  assert.match(content(root), /2 张图/)
  assert.match(content(root), /主 C 与治疗。/)
  pictures[0].props.onError(); await nextTick()
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), ['https://example.com/second.png'], 'the next usable picture takes over')
  assert.equal(byClass(root, 'team-fallback').length, 1, 'a team without any picture shows its letter')
  assert.match(content(card(t, 'teams', { entries: [] })), /暂无官方配队推荐/)
})

test('gacha leads with the rating, charts the pools, and lists the newest S pull first as the saturated card', t => {
  const root = card(t, 'gacha', { luck_title: '欧气冲天', luck_type: 3, total_draws: 638, total_s: 3, pools: [
    { name: '限定', total_draws: 412, s_count: 2, average: 45, guarantee: 90, details: [
      { item_id: '1001', name: '旧', pity: 34, obtained_at: '2026-09-01 10:00:00', lucky_type: 1 },
      { item_id: '1002', name: '新', pity: 88, obtained_at: '2026-09-20 10:00:00', lucky_type: 4 },
    ] },
    { name: '常驻', total_draws: 130, s_count: 1, average: null, details: [{ item_id: 'x', name: '未配图', pity: null, obtained_at: null }] },
  ] })
  const text = content(root)
  for (const expected of ['近期评价', '欧气冲天', '统计抽数 638', '出 S 数 3', '限定', '常驻', '最近出 S']) assert.ok(text.includes(expected), expected)
  assert.match(text, /45 \/ 保底 90 抽/)
  const cards = byClass(root, 'pull-card')
  assert.deepEqual(cards.map(n => content(nodes(n, 'strong')[0])), ['新', '旧', '未配图'], 'newest first, a pull without a time last')
  assert.deepEqual(cards.map(n => String(n.props.class).includes('newest')), [true, false, false])
  assert.match(content(cards[0]), /超非/)
  assert.match(content(cards[0]), /88 抽/)
  assert.equal(nodes(cards[2], 'img').length, 0, 'an id with no official art keeps the letter tile')
  assert.match(content(card(t, 'gacha', { pools: [] })), /暂无评价/)
  assert.match(content(card(t, 'gacha', { pools: [] })), /暂无卡池统计/)
})

test('guides list what a guide holds and the roles that have a summary, without reading any snapshot', t => {
  const root = mount(t, Module, { capability: 'guides' })
  const text = content(root)
  for (const expected of ['培养方案', '5 类推荐', '摘要 + 原图', '弧盘', '配队', '套装', '属性', '技能', '完整角色攻略目录已并入角色练度', '公开资料']) assert.ok(text.includes(expected), expected)
  assert.ok(button(root, '查看角色攻略'))
})

test('the community card renders the slot in place, with no button and no title of its own twice', t => {
  const root = card(t, 'record', {})
  assert.equal(nodes(root, 'button').length, 0)
  assert.equal(nodes(root, 'h2').length, 1)
})
