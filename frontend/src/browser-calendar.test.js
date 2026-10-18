import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { formatBrowserDateTime } from './calendar.js'

test('browser timestamp display rejects finite values outside the Date range', () => {
  assert.equal(formatBrowserDateTime(1e20),'未知')
  assert.equal(formatBrowserDateTime(-1e20),'未知')
})

for (const zone of ['Asia/Tokyo','America/Los_Angeles']) {
  test(`browser calendar respects ${zone}, date precision and civil-day navigation`, () => {
    const result = spawnSync(process.execPath,['--input-type=module','-e', `
      import assert from 'node:assert/strict'
      import {browserTimeZone,formatBrowserDateTime,browserCalendarRange,browserCalendarPosition,browserDayStart,addBrowserDays,shiftBrowserCalendarAnchor,browserEventGeometry,browserEventStatus,browserCalendarBoundary,browserVersionCalendarRange,parseBeijingTime,formatBeijingDateTime} from './src/calendar.js'
      assert.equal(browserTimeZone(),${JSON.stringify(zone)})
      const now=Date.parse('2026-01-01T00:30:00Z')
      assert.equal(formatBrowserDateTime(now),${JSON.stringify(zone === 'Asia/Tokyo' ? '2026-01-01 09:30' : '2025-12-31 16:30')})
      assert.equal(formatBeijingDateTime(now),'2026-01-01 08:30')
      assert.equal(parseBeijingTime('2026-01-01T08:30:00'),now)
      assert.equal(browserCalendarBoundary({start_at:'2026-01-01T08:30:00'},'start'),formatBrowserDateTime(now))
      const month=browserCalendarRange(now,'month')
      assert.equal(month.days.length,31)
      assert.equal(month.days.find(d=>d.timestamp===browserDayStart(now)).day,${zone === 'Asia/Tokyo' ? 1 : 31})
      const next=shiftBrowserCalendarAnchor(now,'month',1)
      assert.equal(formatBrowserDateTime(next).slice(0,10),${JSON.stringify(zone === 'Asia/Tokyo' ? '2026-02-01' : '2026-01-01')})
      assert.equal(browserCalendarRange(next,'month').days[0].day,1)
      for (const mode of ['rolling','fortnight']) {
        const range=browserCalendarRange(now,mode)
        assert.equal(range.days.length,mode==='rolling'?30:14)
        assert.equal(shiftBrowserCalendarAnchor(range.start,mode,1),range.end)
      }
      const dateOnly={start_date:'2026-03-08',end_date:'2026-03-08',start_precision:'day',end_precision:'day'}
      const range=browserCalendarRange(new Date(2026,2,8).getTime(),'month')
      const geometry=browserEventGeometry(dateOnly,range)
      assert.equal(formatBrowserDateTime(geometry.start),'2026-03-08 00:00')
      assert.equal(formatBrowserDateTime(geometry.end),'2026-03-09 00:00')
      assert.equal(browserCalendarBoundary(dateOnly,'start',true),'2026-03-08')
      assert.match(browserCalendarBoundary(dateOnly,'start'),/时刻未确认/)
      assert.equal(browserEventStatus(dateOnly,new Date(2026,2,8,12).getTime()),'更新后开放')
      assert.equal(browserEventStatus(dateOnly,new Date(2026,2,9).getTime()),'已结束')
      assert.equal(browserEventStatus({start_at:now-3600000,end_at:now},now),'已结束')
      assert.equal(browserEventStatus({start_at:now+1},now),'未开始')
      const bare={start_at:'2026-03-08',end_at:'2026-03-08'}
      assert.equal(browserCalendarBoundary(bare,'start',true),'2026-03-08')
      assert.equal(browserEventGeometry(bare,range).end,geometry.end)
      const version=browserVersionCalendarRange([dateOnly],now)
      assert.equal(version.days.length,1)
      assert.equal(version.days[0].day,8)
      const exact={start_at:'2026-01-01T00:30:00+08:00',end_at:'2026-01-01T01:30:00+08:00'}
      const exactRange=browserVersionCalendarRange([exact],now)
      assert.equal(exactRange.days[0].day,${zone === 'Asia/Tokyo' ? 1 : 31})
      for (const [monthIndex,day,hours] of [[2,8,${zone === 'America/Los_Angeles' ? 23 : 24}],[10,1,${zone === 'America/Los_Angeles' ? 25 : 24}]]) {
        const start=new Date(2026,monthIndex,day).getTime(),end=addBrowserDays(start,1)
        assert.equal((end-start)/3600000,hours)
        const r=browserCalendarRange(start,'fortnight')
        assert.equal(r.days.length,14)
        assert.equal(r.days[1].timestamp,end)
        assert.ok(Math.abs(browserCalendarPosition(end,r)-100/14)<1e-8)
        const g=browserEventGeometry({start_at:start,end_at:end},r)
        assert.ok(Math.abs(g.width-100/14)<1e-8)
        assert.equal(g.left,0)
        assert.equal(shiftBrowserCalendarAnchor(start,'fortnight',1),r.end)
        const halfway=start+(end-start)/2
        assert.ok(Math.abs(browserCalendarPosition(halfway,r)-50/14)<1e-8)
      }
    `],{cwd:new URL('..',import.meta.url),env:{...process.env,TZ:zone},encoding:'utf8'})
    assert.equal(result.status,0,result.stderr || result.stdout)
  })
}
