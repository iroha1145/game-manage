import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { calendarRange, formatBeijingDateTime } from '../calendar.js'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'

const CalendarPage = await loadVue(new URL('./CalendarPage.vue', import.meta.url))
const games = [{ game_id: 'nte', display_name: '异环' }, { game_id: 'lol', display_name: '英雄联盟' }]
const snapshots = { nte: { events: { payload: [{ name: '待定的活动', category: '限时活动', source_title: '版本公告', source_post_id: '123', end_at: null }], fetched_at: '2026-09-14T10:00:00+08:00', stale: true } } }

test('multiple failed games share one alert and all version diagnostics live inside one closed source disclosure', t => {
  const rows=Object.fromEntries(games.map(game=>[game.game_id,{events:{state:'error',stale:true,version:'1.4',payload:[{name:`${game.display_name}活动`,version:'1.4'}]}}]))
  const root=mount(t,CalendarPage,{games,snapshots:rows,showSourceStatus:true})
  const alerts=nodes(root,'p').filter(n=>n.props.class==='calendar-read-error')
  assert.equal(alerts.length,1)
  assert.match(content(alerts[0]),/异环、英雄联盟.*正在显示已有活动/)
  const disclosures=nodes(root,'details').filter(n=>n.props.class==='calendar-source-states')
  assert.equal(disclosures.length,1)
  assert.ok(!disclosures[0].props.open)
  assert.equal(nodes(root,'details').filter(n=>n.props.class==='version-metadata').length,0)
  assert.match(content(disclosures[0]),/异环 · 1.4版本活动/)
  assert.match(content(disclosures[0]),/英雄联盟 · 1.4版本活动/)
  assert.match(content(root),/异环活动.*英雄联盟活动/)
})

test('fresh contributing fallback keeps activity visible without an overall failure alert and preserves source state in closed details', async t => {
  const snapshot={state:'error',stale:false,primary_source:'official',error:'辅助来源失败',payload:[{name:'可用来源新活动',source:'official'}],
    source_statuses:{official:{state:'ok',stale:false},bilibili:{state:'error',stale:true}}}
  const original=JSON.stringify(snapshot)
  const props=reactive({games:[games[0]],snapshots:{nte:{events:snapshot}}})
  const root=mount(t,CalendarPage,props)
  assert.match(content(root),/可用来源新活动/)
  assert.equal(nodes(root,'p').filter(n=>n.props.class==='calendar-read-error').length,0)
  assert.doesNotMatch(content(root),/活动更新暂不可用/)
  const details=nodes(root,'details').find(n=>n.props.class==='calendar-source-states')
  assert.ok(details && !details.props.open)
  assert.match(content(details),/部分来源不可用/)
  assert.equal(JSON.stringify(snapshot),original)
  props.snapshots={nte:{events:{...snapshot,stale:true}}};await nextTick()
  assert.equal(nodes(root,'p').filter(n=>n.props.class==='calendar-read-error').length,1)
  assert.match(content(root),/活动更新暂不可用.*正在显示已有活动/)
})
test('cloud event collection state distinguishes never, failed retained data and collected empty events', async t => {
  const props = reactive({ games, snapshots: { nte: { events: { state: 'never', payload: null } } }, initialGameId: 'nte' })
  const root = mount(t, CalendarPage, props)
  assert.match(content(root), /等待活动更新/)
  assert.doesNotMatch(content(root), /暂无活动数据/)
  props.snapshots = { nte: { events: { ...snapshots.nte.events, state: 'error' } } }; await nextTick()
  assert.match(content(root), /活动更新暂不可用.*正在显示已有活动/)
  assert.match(content(root), /待定的活动/)
  props.snapshots = { nte: { events: { state: 'error', payload: null } } }; await nextTick()
  assert.match(content(root), /活动更新暂不可用.*暂无可显示活动/)
  assert.doesNotMatch(content(root), /等待活动更新/)
  props.snapshots = { nte: { events: { state: 'ok', payload: [] } } }; await nextTick()
  assert.match(content(root), /暂无活动数据/)
  assert.doesNotMatch(content(root), /等待活动更新|更新暂不可用/)
})
test('calendar filters by initial game, keeps unknown events and exposes accessible source details', async (t) => {
  const props = reactive({ games, snapshots, initialGameId: 'nte' })
  const root = mount(t, CalendarPage, props)
  assert.match(content(root), /待定的活动/)
  assert.match(content(root), /时间待定/)
  assert.match(content(root), /数据可能过期/)
  const trigger = nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：待定的活动')
  assert.ok(trigger)
  await trigger.props.onClick()
  await nextTick()
  assert.match(content(root), /版本公告/)
  assert.match(content(root), /2026-09-14 10:00/)
  assert.ok(nodes(root, 'section').some(n => n.props['aria-labelledby'] === 'calendar-detail-title'))
  props.initialGameId = 'lol'
  await nextTick()
  assert.doesNotMatch(content(root), /待定的活动/)
  assert.match(content(root), /暂无活动数据/)
})
test('an event ending before the next version update shows the notice wording until its time is announced', async (t) => {
  const start = new Date(Date.now() - 86400000).toISOString()
  const events = (end_at) => ({ endfield: { events: { payload: [{ name: '绚丽异彩', category: '角色寻访', start_at: start, end_at,
    end_text: '版本更新维护前', end_precision: 'version_end', source_title: '「雪凇幽梦」版本更新说明' }], fetched_at: start } } })
  const props = reactive({ games: [{ game_id: 'endfield', display_name: '终末地' }], snapshots: events(null), initialGameId: 'endfield' })
  const root = mount(t, CalendarPage, props)
  const open = async () => { await nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：绚丽异彩').props.onClick(); await nextTick() }
  await open()
  const boundary = () => nodes(root, 'dl').flatMap(list=>nodes(list,'div')).find(row=>nodes(row,'dt').some(term=>content(term).startsWith('截止时间')))
  assert.equal(content(nodes(boundary(),'dd')[0]), '版本更新维护前')
  props.snapshots = events('2026-10-15T06:00:00+08:00')
  await nextTick(); await open()
  assert.match(content(nodes(boundary(),'dd')[0]), /2026-10-15 06:00/)
  assert.match(content(boundary()), /时刻取自下个版本的维护预告/)
})

test('navigation changes displayed time range and allows returning to today', async (t) => {
  const root = mount(t, CalendarPage, { games: [], snapshots: {} })
  assert.ok(nodes(root, 'button').find(n => n.text === '版本').props['aria-pressed'])
  nodes(root, 'button').find(n => n.text === '近 30 天').props.onClick()
  await nextTick()
  assert.ok(nodes(root, 'button').find(n => n.text === '近 30 天').props['aria-pressed'])
  const initial = content(root)
  const next = nodes(root, 'button').find(n => n.props['aria-label'] === '下一时间范围')
  next.props.onClick()
  await nextTick()
  assert.notEqual(content(root), initial)
  nodes(root, 'button').find(n => n.text === '今天').props.onClick()
  await nextTick()
  assert.equal(content(root), initial)
  nodes(root, 'button').find(n => n.text === '14 天').props.onClick()
  await nextTick()
  assert.ok(nodes(root, 'button').find(n => n.text === '14 天').props['aria-pressed'])
})
test('closing calendar details restores the event trigger and clears its selected state', async (t) => {
  const now = Date.now()
  const root = mount(t, CalendarPage, { games, snapshots: { nte: { events: { payload: [
    { name: '限时活动', start_at: new Date(now - 86400000).toISOString(), end_at: new Date(now + 86400000).toISOString() },
  ] } } } })
  const eventButton = nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：限时活动')
  let focusCount = 0
  await eventButton.props.onClick({ currentTarget: { isConnected: true, focus() { focusCount++ } } })
  assert.equal(eventButton.props['aria-pressed'], true)
  await nodes(root, 'button').find(n => n.props['aria-label'] === '关闭活动详情').props.onClick()
  assert.equal(focusCount, 1)
  assert.equal(eventButton.props['aria-pressed'], false)
  assert.equal(nodes(root, 'section').some(n => n.props['aria-labelledby'] === 'calendar-detail-title'), false)
})
test('calendar puts different activity types in one game group and includes type and status on each bar', async (t) => {
  const now = Date.now()
  const iso = delta => new Date(now + delta * 86400000).toISOString()
  const root = mount(t, CalendarPage, { games, snapshots: { nte: { events: { payload: [
    { name: '签到活动', category: '签到', start_at: iso(-2), end_at: iso(5) },
    { name: '限时卡池', category: '卡池', start_at: iso(-2), end_at: iso(-1) },
  ] } } } })
  nodes(root, 'button').find(n => n.text === '近 30 天').props.onClick()
  await nextTick()
  assert.equal(nodes(root, 'div').filter(n => n.props.class === 'timeline-group').length, 1)
  const bars = nodes(root, 'button').filter(n => n.props.class?.includes('timeline-event'))
  assert.equal(bars.length, 2)
  assert.match(content(bars[0]), /签到活动 签到 进行中/)
  assert.match(content(bars[1]), /限时卡池 卡池 已结束/)
})
test('timeline renders exact range proportions, a separate single-date marker and clipped detail', async (t) => {
  const range = calendarRange(Date.now(), 'month')
  const iso = time => new Date(time).toISOString()
  const span = range.end - range.start
  const root = mount(t, CalendarPage, { games, snapshots: { nte: { events: { payload: [
    { name: '半月活动', start_at: iso(range.start + span / 4), end_at: iso(range.start + span * 3 / 4) },
    { name: '只有截止', end_at: iso(range.start + span / 2) },
    { name: '跨月活动', start_at: iso(range.start - 86400000), end_at: iso(range.end + 86400000) },
    { name: '异常活动', start_at: iso(range.end), end_at: iso(range.start) },
  ] } } } })
  nodes(root, 'button').find(n => n.text === '整月').props.onClick()
  await nextTick()
  const bar = nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：半月活动')
  assert.equal(bar.props.style.left, '25%')
  assert.equal(bar.props.style.width, '50%')
  const point = nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：只有截止')
  assert.equal(point.props.style.left, '50%')
  assert.equal(point.props.style.width, undefined)
  assert.match(content(point), /开始未知/)
  assert.match(content(root), /日期异常/)
  await nodes(root,'button').find(n=>n.props['aria-label']==='查看活动详情：异常活动').props.onClick()
  await nextTick()
  assert.match(content(root),/截止早于开始/)
  await nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：跨月活动').props.onClick()
  await nextTick()
  const detail = nodes(root, 'section').find(n => n.props['aria-labelledby'] === 'calendar-detail-title')
  assert.ok(content(detail).includes(formatBeijingDateTime(range.start - 86400000)))
  assert.ok(content(detail).includes(formatBeijingDateTime(range.end + 86400000)))
})
test('missing event snapshots and failed reads distinguish uncollected data from retained snapshots', async (t) => {
  const props = reactive({ games, snapshots: {}, readErrors: {}, initialGameId: 'nte' })
  const root = mount(t, CalendarPage, props)
  assert.match(content(root), /尚未取得活动/)
  props.snapshots = snapshots
  props.readErrors = { nte: '网络连接失败' }
  await nextTick()
  assert.match(content(root), /活动读取失败/)
  assert.match(content(root), /网络连接失败/)
  assert.match(content(root), /正在显示已有活动/)
  assert.match(content(root), /待定的活动/)
  props.initialGameId = 'lol'
  await nextTick()
  assert.doesNotMatch(content(root), /网络连接失败/)
  assert.match(content(root), /尚未取得活动/)
})

test('default version view retains ended and future cross-year entries and responds to version refresh', async t => {
  const game = {game_id:'nte',display_name:'异环'}
  const snap = (id, stale = false) => ({nte:{events:{version:id, stale, payload:[
    {name:'已结束版本活动',version:id,start_at:'2025-11-01T10:00:00+08:00',end_at:'2025-11-02T10:00:00+08:00'},
    {name:'未来跨年活动',version:id,start_at:'2030-01-01T10:00:00+08:00',end_at:'2030-01-02T10:00:00+08:00'},
    {name:'旧版本活动',version:'0.1'}, {name:'时间待定版本活动',version:id},
  ]}}})
  const props = reactive({games:[game],snapshots:snap('1.4')})
  const root = mount(t,CalendarPage,props)
  assert.match(content(root),/已结束版本活动/)
  assert.match(content(root),/未来跨年活动/)
  assert.match(content(root),/时间待定版本活动/)
  assert.doesNotMatch(content(root),/旧版本活动/)
  assert.match(content(root),/1.4版本活动/)
  assert.doesNotMatch(content(root),/覆盖待核验/)
  props.snapshots = snap('1.5',true); await nextTick()
  assert.match(content(root),/1.5版本活动/)
  assert.match(content(root),/已结束版本活动/)
})
