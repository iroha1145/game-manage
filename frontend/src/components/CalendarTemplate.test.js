import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { collectVersionCalendars } from '../calendar.js'

const Page = await loadVue(new URL('./CalendarPage.vue', import.meta.url))
const Version = await loadVue(new URL('./VersionCalendarContent.vue', import.meta.url))
const games = [{ game_id: 'nte', display_name: '异环' }]
const snapshots = { nte: { events: { version: '1.4', payload: [
  { name: '跨年活动', version: '1.4', start_at: '2026-12-20T10:00:00+08:00', end_at: '2027-02-05T10:00:00+08:00' },
  { name: '异常日期', version: '1.4', start_at: '2027-02-05T10:00:00+08:00', end_at: '2026-12-20T10:00:00+08:00' },
  { name: '未公布日期', version: '1.4' },
] } } }

test('screen and image compact bars retain category, uncertain states and confirmed remaining days without detailed dates', t => {
  const asOf=Date.parse('2026-10-15T12:00:00+08:00')
  const rows=[
    {name:'完整活动',start_at:'2026-10-01T10:00:00+08:00',end_at:'2026-11-01T12:00:00+08:00'},
    {name:'短时间活动',start_at:'2026-10-29T10:00:00+08:00',end_at:'2026-10-30T12:00:00+08:00'},
    {name:'仅知日期',start_date:'2026-10-03',start_precision:'day',end_date:'2026-10-04',end_precision:'day'},
    {name:'预计更新活动',start_date:'2026-10-12',start_precision:'relative',start_estimated:true,end_at:'2026-11-01T12:00:00+08:00'},
    {name:'永久活动',start_date:'2026-10-05',start_precision:'day',permanent:true,end_precision:'permanent'},
    {name:'开始未知',end_at:'2026-10-16T12:00:00+08:00'},
  ]
  const calendars=collectVersionCalendars(games,{nte:{events:{payload:rows}}},'',asOf)
  for(const mode of ['screen','image']) {
    const root=mount(t,Version,{calendars,asOf,mode})
    const bars=nodes(root,mode==='screen'?'button':'article').filter(node=>node.props.class?.includes('timeline-event'))
    assert.equal(bars.length,rows.length)
    assert.ok(bars.every(bar=>!nodes(bar,'small').some(node=>node.props.class==='event-boundaries')))
    const byName=name=>bars.find(bar=>bar.props['aria-label']===`查看活动详情：${name}`)
    assert.doesNotMatch(content(root),/2026-10-03|2026-10-04|10:00 —|12:00/)
    assert.match(content(byName('完整活动')),/剩 17 天/)
    assert.match(content(byName('预计更新活动')),/预计/)
    assert.match(content(byName('永久活动')),/常驻开放/)
    assert.equal(nodes(byName('永久活动'),'small').filter(n=>n.props.class?.includes('event-remaining')).length,0)
    assert.match(content(byName('开始未知')),/开始未知/)
    assert.ok(byName('短时间活动').props.class.includes('is-short'))
  }
})

test('version uses daily grid across the full cross-year source range and retains unplaced dates', async t => {
  const root = mount(t, Page, { games, snapshots })
  const days = nodes(root, 'div').filter(n => n.props.class?.includes('date-cell'))
  assert.equal(days.length, 48, 'Dec 20 through Feb 5 inclusive, without a 30-day cutoff')
  assert.equal(nodes(root, 'div').filter(n => n.props.class === 'timeline-group').length, 1)
  const bar = nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：跨年活动')
  assert.ok(bar.props.class.includes('timeline-event'))
  assert.ok(nodes(root, 'button').find(n => n.props['aria-label'] === '查看活动详情：异常日期'))
  assert.match(content(root), /日期异常/)
  assert.match(content(root), /未公布日期/)
  assert.doesNotMatch(content(root), /覆盖待核验|当前性待核验|不代表版本边界/)
  for (const label of ['近 30 天', '整月', '14 天']) {
    nodes(root, 'button').find(n => n.text === label).props.onClick()
    await nextTick()
    assert.equal(nodes(root, 'div').filter(n => n.props.class === 'timeline-header').length, 1)
    assert.ok(nodes(root, 'div').some(n => n.props.class?.includes('date-cell')))
  }
})

test('image calendar uses the full website date axis once and preserves unknown dates', t => {
  const asOf = Date.parse('2027-01-01T12:00:00+08:00')
  const calendars = collectVersionCalendars(games, snapshots, '', asOf)
  const root = mount(t, Version, { calendars, asOf, mode: 'image' })
  const headers = nodes(root, 'div').filter(n => n.props.class === 'timeline-header')
  assert.equal(headers.length, 1)
  assert.equal(nodes(headers[0], 'div').filter(d => d.props.class?.includes('date-cell')).length, 48)
  assert.equal(nodes(root, 'button').length, 0)
  const blocks = nodes(root, 'div').filter(n => n.props.class === 'event-lane')
  assert.equal(blocks.length, 1, 'the activity appears once on the full source date axis')
  assert.ok(blocks.every(n => Object.hasOwn(n.props, 'data-render-block')))
  assert.match(content(root), /异常日期.*日期异常/)
  assert.match(content(root), /未公布日期/)
  assert.doesNotMatch(content(root), /覆盖待核验|时间窗口|当前性待核验|不代表版本边界/)
})

test('image presents its date axis and activities without technical source disclosures', t => {
  const calendars = collectVersionCalendars(games, snapshots, '', Date.parse('2027-01-01T12:00:00+08:00'))
  const root = mount(t, Version, { calendars, asOf:Date.parse('2027-01-01T12:00:00+08:00'), mode:'image' })
  const text = content(root)
  assert.match(text,/跨年活动/)
  assert.match(text,/版本活动时间轴/)
  assert.doesNotMatch(text,/数据来源详情|来源与读取状态|来源未提供/)
  assert.equal(nodes(root,'details').length,0)
})
