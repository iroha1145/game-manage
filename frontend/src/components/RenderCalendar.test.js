import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { collectVersionCalendars } from '../calendar.js'

const Calendar = await loadVue(new URL('./RenderCalendar.vue', import.meta.url))
const asOf = Date.parse('2026-10-17T12:00:00+08:00')
const games = [{ game_id:'nte', display_name:'异环' }, { game_id:'endfield', display_name:'终末地' }]
const activity = (name, dates = {}) => ({ name, source_name:'官方公告', source_title:'版本活动预告', ...dates })
const snapshots = {
  nte: { events: { version:'1.4', fetched_at:asOf, version_metadata:{ coverage:'partial', source_stale:true, diagnostics:['有界来源列表可能遗漏公告'] }, payload:[
    activity('未来活动', { start_at:'2026-10-20T10:00:00+08:00', end_at:'2026-10-22T10:00:00+08:00' }),
    activity('正在进行', { start_at:'2026-10-10T10:00:00+08:00', end_at:'2026-10-22T10:00:00+08:00' }),
    activity('已经结束', { start_date:'2026-10-01', end_date:'2026-10-03' }),
    activity('日期待定', { start_text:'维护完成后开放，具体日期与时刻请等待后续公告确认', start_precision:'relative' }),
    activity('无效日期', { start_at:'2026-99-99', end_at:'2026-10-01' }),
    activity('先结束后开始', { start_at:'2026-10-20', end_at:'2026-10-01' }),
  ] } },
  endfield: { events: { version:'1.2', payload:[activity('终末地独有活动', { start_at:'2026-11-01', end_at:'2026-11-02' })] } },
}

test('QQ calendar counts every dated, undated and invalid activity and retains dates with clear states', t => {
  const calendars = collectVersionCalendars(games, snapshots, '', asOf)
  const root = mount(t, Calendar, { calendars, asOf })
  const cards = nodes(root, 'article')
  assert.equal(cards.length, 7)
  assert.ok(cards.every(card => Object.hasOwn(card.props, 'data-render-block') && Object.hasOwn(card.props, 'data-calendar-event')))
  const text = content(root)
  for (const label of ['未开始', '进行中', '已结束', '时间待定', '日期异常', '2026-10-20 10:00', '2026-10-03', '2026-99-99（待核对）', '截止早于开始', '截止未知', '时刻未确认', '维护完成后开放，具体日期与时刻请等待后续公告确认']) assert.ok(text.includes(label), label)
  assert.match(text, /部分来源不可用/)
  assert.match(text, /来源快照可能过期/)
  assert.match(text, /公告列表可能遗漏补充内容/)
  assert.match(text, /来源：官方公告 · 版本活动预告/)
  assert.match(text, /读取：2026-10-17 12:00/)
  assert.equal(nodes(root, 'button').length, 0)
  assert.equal(nodes(root, 'details').length, 0)
  assert.equal(nodes(root, 'img').length, 0)
})

test('game and version groups keep activities separate and provide repeatable headings', t => {
  const root = mount(t, Calendar, { calendars:collectVersionCalendars(games, snapshots, '', asOf), asOf })
  const groups = nodes(root, 'section')
  assert.equal(groups.length, 2)
  assert.match(content(groups[0]), /异环 · 1.4 版本/)
  assert.doesNotMatch(content(groups[0]), /终末地独有活动/)
  assert.match(content(groups[1]), /终末地 · 1.2 版本.*终末地独有活动/)
  assert.doesNotMatch(content(groups[1]), /正在进行/)
  assert.ok(groups.every(group => nodes(group, 'h2').some(heading => Object.hasOwn(heading.props, 'data-render-heading'))))
})

test('events compatibility groups versions without hiding out-of-range records', t => {
  const events = [
    { name:'旧版本活动', gameId:'nte', gameName:'异环', version:'1.3', start_at:'2020-01-01', end_at:'2020-01-02' },
    { name:'常驻活动', gameId:'nte', gameName:'异环', version:'1.4', start_date:'2026-10-01', permanent:true, end_precision:'permanent' },
    { name:'未知开始', gameId:'endfield', gameName:'终末地', end_at:'2026-10-22' },
  ]
  const root = mount(t, Calendar, { events, range:{ start:asOf, end:asOf+86400000 }, asOf })
  assert.equal(nodes(root, 'section').length, 3)
  assert.equal(nodes(root, 'article').length, events.length)
  assert.match(content(root), /旧版本活动.*已结束/)
  assert.match(content(root), /常驻活动.*常驻开放.*永久开放/)
  assert.match(content(root), /未知开始.*开始未知/)
})

test('empty calendar and a game with no activities show readable empty states', t => {
  const empty = mount(t, Calendar, { asOf })
  assert.match(content(empty), /暂无活动数据/)
  const root = mount(t, Calendar, { calendars:[{ gameId:'nte', gameName:'异环', version:{}, events:[] }], asOf })
  assert.match(content(root), /异环 · 已公布活动.*0 项活动.*暂无活动数据/)
  assert.equal(nodes(root, 'article').length, 0)
})

test('shared official notice image appears once in the game heading and independent artwork stays with its activity', t => {
  const shared='https://example.com/nte-version.jpg'
  const unique='https://example.com/nte-event.jpg'
  const other='https://example.com/endfield-version.jpg'
  const calendars=[
    {gameId:'nte',gameName:'异环',version:{id:'1.4'},events:[
      {name:'共图活动甲',image_urls:[shared]},
      {name:'共图活动乙',image_urls:[shared]},
      {name:'独立配图活动',image_urls:[unique]},
      {name:'无图活动'},
    ]},
    {gameId:'endfield',gameName:'终末地',version:{id:'1.2'},events:[{name:'另一游戏活动',image_urls:[other]}]},
  ]
  const root=mount(t,Calendar,{calendars,asOf})
  const groups=nodes(root,'section')
  assert.deepEqual(nodes(groups[0],'img').map(img=>img.props.src),[shared,unique])
  const heading=nodes(groups[0],'header')[0]
  assert.deepEqual(nodes(heading,'img').map(img=>img.props.src),[shared])
  assert.ok(Object.hasOwn(heading.props,'data-render-block'))
  assert.ok(nodes(heading,'h2').some(h=>Object.hasOwn(h.props,'data-render-heading')))
  const cards=nodes(groups[0],'article')
  assert.deepEqual(cards.map(card=>nodes(card,'img').length),[0,0,1,0])
  assert.equal(nodes(cards[2],'img')[0].props.src,unique)
  assert.deepEqual(nodes(groups[1],'img').map(img=>img.props.src),[other])
  assert.equal(nodes(root,'article').length,5)
})

test('unsafe image URLs are omitted and failed image candidates fall back without losing activity text', async t => {
  const root=mount(t,Calendar,{events:[
    {gameId:'nte',gameName:'异环',name:'错误图片活动',image_urls:['javascript:alert(1)','file:///tmp/image.png','https://user:password@example.com/private.jpg']},
    {gameId:'nte',gameName:'异环',name:'配图重试活动',image_urls:['https://example.com/broken.jpg','https://example.com/fallback.jpg']},
  ],asOf})
  const cards=nodes(root,'article')
  assert.equal(nodes(cards[0],'img').length,0)
  let picture=nodes(cards[1],'img')[0]
  assert.equal(picture.props.src,'https://example.com/broken.jpg')
  picture.props.onError({target:{getAttribute:()=>picture.props.src}})
  await nextTick()
  picture=nodes(cards[1],'img')[0]
  assert.equal(picture.props.src,'https://example.com/fallback.jpg')
  picture.props.onError({target:{getAttribute:()=>picture.props.src}})
  await nextTick()
  assert.equal(nodes(cards[1],'img').length,0)
  assert.match(content(cards[1]),/配图重试活动.*时间待定.*开始未知.*截止未知/)
})

test('precise at plus date fields do not claim unknown times and equivalent slash date text is not repeated', t => {
  const root=mount(t,Calendar,{events:[{
    gameId:'nte',gameName:'异环',name:'真实分钟形状',
    start_at:'2026-10-17T12:00:00+08:00',start_date:'2026-10-17',start_precision:'minute',start_text:'2026/10/17 12:00',
    end_at:'2026-11-05T11:59:00+08:00',end_date:'2026-11-05',end_precision:'minute',end_text:'2026/11/05 11:59',
  }],asOf})
  const text=content(nodes(root,'article')[0])
  assert.match(text,/开始 2026-10-17 12:00/)
  assert.match(text,/结束 2026-11-05 11:59/)
  assert.doesNotMatch(text,/时刻未确认|2026\/10\/17|2026\/11\/05/)
  assert.equal(text.split('2026-11-05 11:59').length-1,1)
})

test('day and relative precision retain uncertainty and meaningful extra boundary explanations', t => {
  const root=mount(t,Calendar,{events:[
    {gameId:'nte',name:'日期未确认时刻',start_at:'2026-10-17T00:00:00+08:00',start_date:'2026-10-17',start_precision:'day'},
    {gameId:'nte',name:'维护开放活动',start_at:'2026-10-17T12:00:00+08:00',start_date:'2026-10-17',start_precision:'relative',start_text:'维护完成后开放',end_text:'第3次挑战后结束',end_precision:'dependent'},
    {gameId:'nte',name:'分钟但有补充',start_at:'2026-10-17T12:00:00+08:00',start_date:'2026-10-17',start_precision:'minute',start_text:'维护后开放，以实际完成时间为准'},
  ],asOf})
  const cards=nodes(root,'article')
  assert.match(content(cards[0]),/2026-10-17 · 时刻未确认/)
  assert.match(content(cards[1]),/时刻未确认.*维护完成后开放.*第3次挑战后结束/)
  assert.match(content(cards[2]),/2026-10-17 12:00 · 维护后开放，以实际完成时间为准/)
  assert.doesNotMatch(content(cards[2]),/时刻未确认/)
})

test('calendar starts at single-game heading and shows only one compact total for multiple games', t => {
  const single=mount(t,Calendar,{calendars:collectVersionCalendars(games,snapshots,'nte',asOf),asOf})
  assert.equal(nodes(single,'header').length,1)
  assert.doesNotMatch(content(single),/活动日历|款游戏|北京时间/)
  assert.equal(nodes(single,'p').filter(p=>p.props.class==='qq-calendar-summary').length,0)
  const multiple=mount(t,Calendar,{calendars:collectVersionCalendars(games,snapshots,'',asOf),asOf})
  const summaries=nodes(multiple,'p').filter(p=>p.props.class==='qq-calendar-summary')
  assert.equal(summaries.length,1)
  assert.equal(content(summaries[0]),'2 款游戏 · 共 7 项')
  const versions=mount(t,Calendar,{events:[{gameId:'nte',version:'1.3',name:'旧版'},{gameId:'nte',version:'1.4',name:'新版'}],asOf})
  assert.equal(nodes(versions,'p').filter(p=>p.props.class==='qq-calendar-summary').length,0)
})
