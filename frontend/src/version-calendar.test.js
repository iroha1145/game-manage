import test from 'node:test'
import assert from 'node:assert/strict'
import { collectVersionCalendars } from './calendar.js'

test('each game keeps its own version and all source backed dates across months and years', () => {
  const games = [{game_id:'nte', display_name:'异环'}, {game_id:'wuthering_waves', display_name:'鸣潮'}]
  const snapshots = {nte:{events:{version:'1.6', version_metadata:{id:'1.6', status:'current'}, payload:[
    {name:'已结束',version:'1.6',start_at:'2026-11-01T10:00:00+08:00',end_at:'2026-11-02T10:00:00+08:00'},
    {name:'未来',version:'1.6',start_at:'2027-01-01T10:00:00+08:00',end_at:null},
    {name:'日期未知',version:'1.6'}, {name:'旧版',version:'1.5'}]}},
    wuthering_waves:{events:{payload:[{name:'可用汇总'}]}}}
  const result = collectVersionCalendars(games, snapshots)
  assert.deepEqual(result[0].events.map(e => e.name), ['已结束','未来','日期未知'])
  assert.equal(result[0].version.id,'1.6')
  assert.equal(result[1].version.status,'unknown')
  assert.equal(result[1].events[0].name,'可用汇总')
})

test('cached metadata changes status after exact end, date-only end remains uncertain that day', () => {
  const games = [{game_id:'nte'}]
  const now = Date.parse('2026-12-29T12:00:00+08:00')
  const get = meta => collectVersionCalendars(games,{nte:{events:{payload:[],version_metadata:meta}}},'',now)[0].version.status
  const meta = {id:'1.6',status:'current',start_date:'2026-12-01',start_precision:'day',end_at:'2026-12-29T10:00:00+08:00',end_precision:'minute'}
  assert.equal(get(meta),'historical')
  assert.equal(get({...meta,end_at:null,end_date:'2026-12-29',end_precision:'day'}),'unverified')
})

test('cross-version intersection agrees with backend and missing version bounds exclude proven other versions', () => {
  const games = [{game_id:'nte'}]
  const meta = {id:'1.6',start_date:'2026-12-20',end_at:'2027-01-30T06:00:00+08:00'}
  const event = {name:'延续活动',version:'1.5',start_at:'2026-12-01T10:00:00+08:00',end_at:'2026-12-25T10:00:00+08:00'}
  const get = metadata => collectVersionCalendars(games,{nte:{events:{payload:[event],version_metadata:metadata}}})[0].events
  assert.equal(get(meta)[0].cross_version,true)
  assert.deepEqual(get({...meta,end_at:null}),[])
})
