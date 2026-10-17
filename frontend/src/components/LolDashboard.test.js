import test from 'node:test'
import assert from 'node:assert/strict'
import { h, ref, nextTick } from 'vue'
import { loadVue, mount, content, nodes, choose } from '../test-utils/vue.js'
const LolDashboard = await loadVue(new URL('./LolDashboard.vue', import.meta.url))
const flush = async () => { await new Promise(setImmediate); await nextTick() }
const response = value => new Response(JSON.stringify(value))
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const data = (name = '本地召唤师') => ({
  schema_version: 1, account: { nickname: name, level: 0 }, source: 'local_lcu_archive',
  overview: { games: 2, wins: 0, losses: 1, unknown_results: 1, winrate: 0, average_score: null, avg_kills: 0, avg_deaths: null, avg_assists: 0, play_minutes: 0 },
  coverage: { archived_games: 2, filtered_games: 2, detail_games: 1, score_games: 0, scope_note: '仅客户端采集窗口' },
  matches: [{ match_id: 'm1', champion_name: '测试英雄', win: null, kills: 0, deaths: null, assists: 0, score: null, kp: 0, damage_share: null, augments: [] }],
  trend: [{ date: '2026-09-25', games: 2, wins: 0, winrate: 0, average_score: null }],
  heatmap: [{ date: '2026-09-25', games: 2, wins: 0 }], champions: [], highlights: [],
  hextech: { games: 2, recorded_games: 1, augments: [], combinations: [], rating_status: 'unavailable' },
})
const button = (root, label) => nodes(root, 'button').find(n => content(n).includes(label))

test('esports is available offline and survives remount without personal controls', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('{}', { status: 503 }))
  const browseState = { section: 'esports', view: 'teams', family: 'lpl', date: '2026-10-04', returnTo: [] }
  const props = { esportsBrowse: browseState, snaps: { esports: { payload: { schema_version: 1, season_year: 2026, tournaments: [], teams: [], matches: [] } } } }
  const root = mount(t, LolDashboard, props)
  await flush()
  assert.match(content(root), /职业赛事/)
  assert.match(content(root), /当前赛事战队资料暂缺/)
  assert.doesNotMatch(content(root), /同步战绩|本机尚无归档|本地数据读取失败/)
  const remounted = mount(t, LolDashboard, props)
  await flush()
  assert.match(content(remounted), /当前赛事战队资料暂缺/)
})

test('announcements and news share one list and subject filters without an archive', async t => {
  t.mock.method(globalThis, 'fetch', async () => response({ ...data(), overview: { games: 0 }, coverage: { archived_games: 0 } }))
  const root = mount(t, LolDashboard, { snaps: {
    announcement: { payload: [{ title: '停服维护公告', url: 'https://example.com/announcement' }], stale: true },
    news: { payload: [{ title: '世界赛事日程', url: 'https://example.com/news' }] },
  } })
  await flush()
  button(root, '公告与资讯').props.onClick(); await flush()
  assert.match(content(root), /停服维护公告/)
  assert.match(content(root), /世界赛事日程/)
  assert.ok(nodes(root, 'span').some(node => String(node.props.class).includes('badge-stale') && content(node) === '数据可能过期'))
  button(root, '维护通知').props.onClick(); await flush()
  assert.match(content(root), /停服维护公告/)
  assert.doesNotMatch(content(root), /世界赛事日程/)
  button(root, '赛事资讯').props.onClick(); await flush()
  assert.match(content(root), /世界赛事日程/)
  assert.doesNotMatch(content(root), /停服维护公告/)
})

test('remakes display separately from unknown results and retain neutral detail labels', async t => {
  const archive = data()
  archive.overview = { ...archive.overview, games: 4, wins: 1, losses: 1, remakes: 1, unknown_results: 1, winrate: 50 }
  archive.matches = [{ ...archive.matches[0], remake: true, win: null }]
  t.mock.method(globalThis, 'fetch', async url => response(url.includes('/matches/')
    ? { payload: { remake: true, teams: [{ team_id: 100, win: false, participants: [] }] } } : archive))
  const root = mount(t, LolDashboard, {})
  await flush()
  assert.match(content(root), /1 重开/)
  assert.match(content(root), /1 胜 · 1 负/)
  button(root, '对局记录').props.onClick(); await flush()
  const row = nodes(root, 'article').find(node => node.props.class?.includes('lol-match'))
  assert.match(content(row), /重开/)
  assert.doesNotMatch(content(row), /胜负未知|失败/)
  assert.match(row.props.class, /remake/)
  button(root, '查看详情').props.onClick(); await flush()
  assert.match(content(row), /重开.*队伍 100/)
  assert.doesNotMatch(content(row), /失败/)
})

test('offline empty archive exposes collection directly without a popup', async t => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, opts) => {
    calls.push({ url, opts })
    if (opts.method === 'POST') return new Response('{}', { status: 503 })
    return response({ ...data(), account: null, overview: { games: 0 }, matches: [], coverage: { archived_games: 0 } })
  })
  const root = mount(t, LolDashboard, { snaps: { account: { error: 'offline' } } })
  await flush()
  assert.match(content(root), /本机尚无归档/)
  assert.equal(calls.length, 1)
  button(root, '同步战绩').props.onClick(); await flush()
  assert.equal(calls[1].url, '/api/lol/collect')
  assert.equal(calls[1].opts.headers['X-Game-Assistant'], '1')
  assert.match(content(root), /客户端/)
})

test('real zero and unknown remain distinct; unknown result never becomes a loss', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(data()))
  const root = mount(t, LolDashboard, {})
  await flush()
  assert.match(content(root), /0(?:\.0)?%/)
  assert.match(content(root), /0 胜 · 1 负 · 1 未知/)
  assert.match(content(root), /LOLhelper v3/)
  assert.match(content(root), /0 胜 · 1 负/)
  button(root, '对局记录').props.onClick(); await flush()
  assert.match(content(root), /胜负未知/)
  assert.match(content(root), /0 \/ 未知 \/ 0/)
  assert.match(content(root), /参团 0(?:\.0)?%/)
  button(root, '海克斯').props.onClick(); await flush()
  assert.match(content(root), /2 场/)
  assert.match(content(root), /1 场/)
  assert.match(content(root), /重开与胜负未知不计入胜率/)
})

test('filter changes abort old requests and late responses cannot replace current data', async t => {
  const old = deferred(), fresh = deferred(), calls = []
  t.mock.method(globalThis, 'fetch', (url, opts) => { calls.push({ url, opts }); return calls.length === 1 ? old.promise : fresh.promise })
  const root = mount(t, LolDashboard, {})
  choose(root, '时间', 7); await nextTick()
  assert.equal(calls[0].opts.signal.aborted, true)
  assert.match(calls[1].url, /days=7/)
  fresh.resolve(response(data('当前数据'))); await flush()
  old.resolve(response(data('过时数据'))); await flush()
  assert.match(content(root), /当前数据/)
  assert.match(content(root), /当前展示：近 7 天/)
  assert.doesNotMatch(content(root), /过时数据/)
})

test('failed reload preserves old records and their filter label', async t => {
  let count = 0
  t.mock.method(globalThis, 'fetch', async () => ++count === 1 ? response(data()) : new Response('{}', { status: 502 }))
  const root = mount(t, LolDashboard, {})
  await flush()
  choose(root, '时间', 7); await flush()
  assert.match(content(root), /保留上次成功读取/)
  assert.match(content(root), /当前展示：近 90 天/)
  assert.match(content(root), /本地召唤师/)
})

test('match details read archived records and preserve unknown participant metrics', async t => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async url => { calls.push(url); return response(url.includes('/matches/') ? { payload: { teams: [{ team_id: 100, win: null, participants: [{ champion_name: '详情英雄', kills: null, deaths: 0, assists: null }] }] } } : data()) })
  const root = mount(t, LolDashboard, {})
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  button(root, '查看详情').props.onClick(); await flush()
  assert.equal(calls[1], '/api/lol/matches/m1')
  assert.match(content(root), /详情英雄/)
  assert.match(content(root), /未知 \/ 0 \/ 未知/)
})

test('collection failure keeps the previously loaded archive visible', async t => {
  t.mock.method(globalThis, 'fetch', async (_url, opts) => opts.method === 'POST' ? new Response('{}', { status: 503 }) : response(data('保留的账号')))
  const root = mount(t, LolDashboard, {})
  await flush(); button(root, '同步战绩').props.onClick(); await flush()
  assert.match(content(root), /保留的账号/)
  assert.match(content(root), /已有分析数据仍保留/)
  assert.match(content(root), /0 胜 · 1 负 · 1 未知/)
})

test('changing the expanded archive match ignores a late earlier detail', async t => {
  const first = deferred(), second = deferred(), archive = data()
  archive.matches.push({ ...archive.matches[0], match_id: 'm2' })
  t.mock.method(globalThis, 'fetch', url => url.endsWith('/m1') ? first.promise : url.endsWith('/m2') ? second.promise : Promise.resolve(response(archive)))
  const root = mount(t, LolDashboard, {})
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  button(root, '查看详情').props.onClick(); await flush()
  button(root, '查看详情').props.onClick(); await flush()
  const teams = name => ({ payload: { teams: [{ team_id: 100, participants: [{ champion_name: name }] }] } })
  second.resolve(response(teams('正确详情'))); await flush()
  first.resolve(response(teams('过时详情'))); await flush()
  assert.match(content(root), /正确详情/)
  assert.doesNotMatch(content(root), /过时详情/)
})

test('unmount aborts outstanding analysis and discards its late response', async t => {
  const pending = deferred(), visible = ref(true); let signal
  t.mock.method(globalThis, 'fetch', (_url, options) => { signal = options.signal; return pending.promise })
  const root = mount(t, { setup: () => () => visible.value ? h(LolDashboard) : h('p', '已关闭') }, {})
  visible.value = false; await nextTick()
  assert.equal(signal.aborted, true)
  pending.resolve(response(data('不应出现'))); await flush()
  assert.equal(content(root), '已关闭')
})

test('account identity change clears prior analysis and aborts details even when the new read fails', async t => {
  const snaps = ref({ account: { payload: { extra: { puuid: 'account-a' } }, fetched_at: 'first' } })
  const pending = deferred(); let detailSignal, reads = 0
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.includes('/matches/')) { detailSignal = options.signal; return pending.promise }
    return ++reads === 1 ? response(data('账号甲')) : new Response('{}', { status: 502 })
  })
  const root = mount(t, { setup: () => () => h(LolDashboard, { snaps: snaps.value }) }, {})
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  button(root, '查看详情').props.onClick(); await flush()
  snaps.value = { account: { payload: { extra: { puuid: 'account-b' } }, fetched_at: 'second' } }
  await flush()
  assert.equal(detailSignal.aborted, true)
  assert.equal(reads, 2)
  assert.doesNotMatch(content(root), /账号甲|测试英雄|保留上次成功/)
  pending.resolve(response({ payload: { teams: [{ team_id: 100, participants: [{ champion_name: '账号甲详情' }] }] } })); await flush()
  assert.doesNotMatch(content(root), /账号甲详情/)
})

test('an in-flight analysis from a previous account cannot replace the new account', async t => {
  const snaps = ref({ account: { payload: { extra: { puuid: 'account-a' } } } }), old = deferred(), fresh = deferred(), signals = []
  t.mock.method(globalThis, 'fetch', (_url, options) => { signals.push(options.signal); return signals.length === 1 ? old.promise : fresh.promise })
  const root = mount(t, { setup: () => () => h(LolDashboard, { snaps: snaps.value }) }, {})
  snaps.value = { account: { payload: { extra: { puuid: 'account-b' } } } }; await nextTick()
  assert.equal(signals[0].aborted, true)
  fresh.resolve(response(data('账号乙'))); await flush()
  old.resolve(response(data('账号甲'))); await flush()
  assert.match(content(root), /账号乙/)
  assert.doesNotMatch(content(root), /账号甲/)
})

test('same-account snapshot revisions reload analysis and preserve prior data on failure', async t => {
  const snaps = ref({ account: { payload: { extra: { puuid: 'account-a' } }, fetched_at: 'a1' }, match: { fetched_at: 'm1' }, stats: { fetched_at: 's1' } })
  let reads = 0
  t.mock.method(globalThis, 'fetch', async () => {
    reads++
    return reads === 3 ? new Response('{}', { status: 502 }) : response(data(`账号甲版本${reads}`))
  })
  const root = mount(t, { setup: () => () => h(LolDashboard, { snaps: snaps.value }) }, {})
  await flush()
  snaps.value.match.fetched_at = 'm2'; await flush()
  assert.equal(reads, 2)
  assert.match(content(root), /账号甲版本2/)
  snaps.value.stats.fetched_at = 's2'; await flush()
  assert.equal(reads, 3)
  assert.match(content(root), /账号甲版本2/)
  assert.match(content(root), /保留上次成功读取/)
  snaps.value.account.fetched_at = 'a2'; await flush()
  assert.equal(reads, 4)
  assert.match(content(root), /账号甲版本4/)
})

test('a snapshot refresh keeps the open match detail; a filter change closes it', async t => {
  const snaps = ref({ account: { payload: { extra: { puuid: 'account-a' } }, fetched_at: 'a1' }, match: { fetched_at: 'm1' }, stats: { fetched_at: 's1' } })
  t.mock.method(globalThis, 'fetch', async url => response(url.includes('/matches/') ? { payload: { teams: [{ team_id: 100, win: true, participants: [{ champion_name: '详情英雄', kills: 1, deaths: 0, assists: 2 }] }] } } : data()))
  const root = mount(t, { setup: () => () => h(LolDashboard, { snaps: snaps.value }) }, {})
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  button(root, '查看详情').props.onClick(); await flush()
  assert.match(content(root), /详情英雄/)
  snaps.value.match.fetched_at = 'm2'; await flush()
  assert.match(content(root), /详情英雄/, 'the hourly snapshot refresh must not collapse the open detail')
  choose(root, '时间', 30); await flush()
  assert.doesNotMatch(content(root), /详情英雄/)
})

test('the recent-match snapshot gets champion names and record chips from the stats snapshot', async t => {
  // The pre-archive snapshot list is shown while the local archive is still empty.
  t.mock.method(globalThis, 'fetch', async () => response({ ...data(), overview: { games: 0 }, coverage: { archived_games: 0 }, matches: [] }))
  const snaps = {
    match: { fetched_at: '2026-10-16T04:00:00Z', payload: [{ match_id: 'g1', champion_id: 7, champion_name: null, win: true, kills: 9, deaths: 1, assists: 5, start_at: '2026-10-15 20:00' }] },
    stats: { fetched_at: '2026-10-16T04:00:00Z', payload: { top_champions: [{ champion_id: 7, champion_name: '诡术妖姬' }], records: [{ match_id: 'g1', label: '单场最多击杀' }] } },
  }
  const root = mount(t, LolDashboard, { snaps })
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  assert.match(content(root), /诡术妖姬/)
  assert.match(content(root), /最多击杀/)
})

// A fuller archive: 25 games, newest first, every third one lost, plus augments for the hex view.
const rich = () => {
  const matches = Array.from({ length: 25 }, (_, i) => ({
    match_id: `r${i}`, champion_name: `英雄${i}`, mode: 'CLASSIC', queue_id: 420, start_at: `2026-09-${String(25 - Math.floor(i / 2)).padStart(2, '0')}T12:${String(i).padStart(2, '0')}:00+08:00`,
    duration_seconds: 1800, win: i % 3 !== 0, remake: false, kills: 6, deaths: i % 5 === 0 ? 0 : 2, assists: 8, damage: 20000, score: 8, kp: 50, damage_share: 20, augments: [], highlights: [],
  }))
  return { ...data(), overview: { games: 25, wins: 16, losses: 9, unknown_results: 0, remakes: 0, winrate: 64, average_score: 8, avg_kills: 6, avg_deaths: 1.5, avg_assists: 8, play_minutes: 750, current_streak: { kind: 'loss', count: 1 } },
    coverage: { archived_games: 25, filtered_games: 25, detail_games: 25, score_games: 25, scope_note: '仅客户端采集窗口' }, matches,
    hextech: { games: 12, recorded_games: 9, rating_note: '', combinations: [{ names: ['甲', '乙'], games: 3, wins: 2, winrate: 66.7 }],
      augments: Array.from({ length: 12 }, (_, i) => ({ id: i + 1, name: `强化 #${i + 1}`, games: 12 - i, wins: 6 - Math.floor(i / 3), winrate: 50 })) } }
}
const byClass = (root, tag, name) => nodes(root, tag).filter(n => String(n.props.class ?? '').split(/\s+/).includes(name))
const meter = root => nodes(root, 'div').find(n => n.props.role === 'meter')

test('the overview shows the win rate as a ring and keeps the unsplit figure readable, with averages to one decimal', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(rich()))
  const root = mount(t, LolDashboard, {})
  await flush()
  assert.equal(meter(root).props['aria-valuenow'], 64)
  assert.match(content(meter(root)), /64%/)
  // The split bar draws only results that happened; the legend names all four with their counts.
  assert.equal(nodes(byClass(root, 'div', 'stack-bar')[0], 'i').length, 2)
  assert.match(content(byClass(root, 'ul', 'legend')[0]), /胜利 16 失败 9 胜负未知 0 重开 0/)
  assert.match(content(root), /最近连续失利 1 场/)
  assert.match(content(root), /1\.5/) // average deaths keep their decimal
  assert.match(content(root), /8\.0/) // and so does the average score
})

test('the history strip lists the newest twenty results oldest first, each with a letter and the row stays an article', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(rich()))
  const root = mount(t, LolDashboard, {})
  await flush(); button(root, '对局记录').props.onClick(); await flush()
  const strip = byClass(root, 'li', 'form-col')
  assert.equal(strip.length, 20)
  // Newest game (index 0) is a loss and sits last; the oldest of the twenty (index 19) is a win and sits first.
  assert.deepEqual([content(strip[0]), content(strip.at(-1))], ['胜', '负'])
  assert.ok(strip.every(item => item.props.title && item.props['aria-label']), 'every bar names its game for pointer and screen reader')
  assert.equal(nodes(root, 'article').filter(n => String(n.props.class).includes('lol-match')).length, 25, 'the list still has every game')
  assert.equal(meter(root).props['aria-valuenow'], 65) // 13 wins among the 20 newest games (seven of them are lost)
})

test('the hex view charts the ten most chosen augments above the complete table and keeps its caveat', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(rich()))
  const root = mount(t, LolDashboard, {})
  await flush(); button(root, '海克斯').props.onClick(); await flush()
  assert.equal(byClass(root, 'li', 'bar-col').length, 10)
  assert.equal(nodes(nodes(root, 'table')[0], 'tr').length, 13) // header plus all twelve
  assert.match(content(root), /重开与胜负未知不计入胜率/)
  assert.equal(meter(root).props['aria-valuenow'], 9) // 9 of 12 hex games recorded their augments
})

test('the news tab has no archive filters and says how much was published', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(rich()))
  const root = mount(t, LolDashboard, { snaps: { news: { payload: [{ title: '甲', url: 'https://example.com/a', published_at: '2026-10-12T10:00:00+08:00' }] } } })
  await flush()
  assert.equal(nodes(root, 'button').filter(n=>n.props.role==='combobox').length, 2)
  button(root, '公告与资讯').props.onClick(); await flush()
  assert.equal(nodes(root, 'button').filter(n=>n.props.role==='combobox').length, 0)
  assert.match(content(root), /发布概况/)
  assert.equal(byClass(root, 'li', 'bar-col').length, 8)
})

test('the header names the account and its rank from the snapshot while the archive is empty', async t => {
  t.mock.method(globalThis, 'fetch', async () => response({ ...data(), account: null, overview: { games: 0 }, matches: [], coverage: { archived_games: 0 } }))
  const root = mount(t, LolDashboard, { snaps: { account: { payload: { nickname: '快照召唤师', level: 312, extra: { puuid: 'p', ranked_solo: { tier: 'GOLD', division: 'II', league_points: 45, wins: 61, losses: 55 } } } } } })
  await flush()
  const header = nodes(root, 'header')[0]
  assert.match(content(header), /快照召唤师/)
  assert.match(content(header), /等级 312/)
  assert.match(content(header), /GOLD II · 45 LP/)
  assert.match(content(header), /单双排 61 胜 55 负/)
  assert.match(content(root), /本机尚无归档/)
})
