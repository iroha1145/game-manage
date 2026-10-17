import test from 'node:test'
import assert from 'node:assert/strict'
import { createEsportsBrowseState, selectEsportsMatches, esportsGroupLabel, officialEsportsUrl, esportsDayLabel, esportsDensity, esportsMonogram, esportsTeamForm } from './esports.js'
import { createDashboard } from './dashboard.js'

test('Beijing date selection, missing dates and chronological ordering', () => {
  const payload = { tournaments: [{ id: 't', family: 'lpl' }], matches: [
    { id: 'unknown', tournament_id: 't' },
    { id: 'late', tournament_id: 't', start_at: '2026-10-01T17:00:00Z' },
    { id: 'early', tournament_id: 't', start_at: '2026-10-01T16:00:00Z' },
  ] }
  assert.deepEqual(selectEsportsMatches(payload, { family: 'lpl', date: '2026-10-02' }).map(m => m.id), ['early', 'late'])
  assert.equal(selectEsportsMatches(payload, {}).at(-1).id, 'unknown')
  assert.equal(selectEsportsMatches(payload, { family: 'worlds' }).length, 0)
})
test('source and local timestamps remain distinct and untrusted links are rejected', () => {
  const label = esportsGroupLabel({ last_success_at: '2026-10-04T00:00:00Z', source_updated_at: '2026-07-02T00:00:00Z', source_lagging: true })
  assert.match(label, /10-04/); assert.match(label, /07-02/); assert.match(label, /滞后/)
  assert.equal(officialEsportsUrl('javascript:alert(1)'), '')
  assert.equal(officialEsportsUrl('https://lpl.qq.com.evil.com/web202301/live.html'), '')
  assert.equal(officialEsportsUrl('https://lpl.qq.com/web202301/live.html?bgid=238&bmid=1'), 'https://lpl.qq.com/web202301/live.html?bgid=238&bmid=1')
})
test('public browsing state survives account invalidation and factories do not share state', () => {
  const dashboard = createDashboard({})
  dashboard.state.esportsBrowse.league_of_legends.family = 'lpl'
  dashboard.state.snapshots.league_of_legends = { esports: { payload: { schema_version: 1 } }, account: {} }
  dashboard.invalidateGame('league_of_legends')
  assert.equal(dashboard.state.esportsBrowse.league_of_legends.family, 'lpl')
  assert.equal(dashboard.state.snapshots.league_of_legends.esports.payload.schema_version, 1)
  assert.equal(createEsportsBrowseState().family, '')
})

// Saturday 2026-10-17, 12:00 in Beijing.
const NOW = Date.parse('2026-10-17T12:00:00+08:00')

test('logo tiles fall back to a short mark that suits the script of the name', () => {
  assert.equal(esportsMonogram('BLG'), 'BLG')
  assert.equal(esportsMonogram('Top Esports'), 'TOP')
  assert.equal(esportsMonogram('Knight', 2), 'KN')
  assert.equal(esportsMonogram('哔哩哔哩电子竞技俱乐部'), '哔哩')
  assert.equal(esportsMonogram('  '), '?')
  assert.equal(esportsMonogram(undefined), '?')
})

test('match days read as month, day and weekday, with today and tomorrow named', () => {
  assert.equal(esportsDayLabel('2026-10-17', NOW), '10月17日 周六 · 今天')
  assert.equal(esportsDayLabel('2026-10-18', NOW), '10月18日 周日 · 明天')
  assert.equal(esportsDayLabel('2026-10-24', NOW), '10月24日 周六')
  assert.equal(esportsDayLabel('时间待公布', NOW), '时间待公布')
})

test('a team form counts only finished matches with a confirmed winner, from the team side, oldest first', () => {
  const payload = { matches: [
    { id: 'm3', status: 'completed', team_a_id: 'x', team_b_id: 'a', team_a_name: 'X', team_b_name: 'A', winner_team_id: 'a', start_at: '2026-10-03T10:00:00Z' },
    { id: 'm1', status: 'completed', team_a_id: 'a', team_b_id: 'y', team_a_name: 'A', team_b_name: 'Y', winner_team_id: 'y', start_at: '2026-10-01T10:00:00Z' },
    { id: 'm2', status: 'completed', team_a_id: 'a', team_b_id: 'z', team_a_name: 'A', team_b_name: 'Z', winner_team_id: 'nobody', start_at: '2026-10-02T10:00:00Z' },
    { id: 'm4', status: 'scheduled', team_a_id: 'a', team_b_id: 'z', start_at: '2026-10-09T10:00:00Z' },
  ] }
  assert.deepEqual(esportsTeamForm(payload, 'a'), [{ id: 'm1', win: false, opponent: 'Y' }, { id: 'm3', win: true, opponent: 'X' }])
  assert.deepEqual(esportsTeamForm(payload, 'a', 1), [{ id: 'm3', win: true, opponent: 'X' }])
  assert.deepEqual(esportsTeamForm({}, 'a'), [])
})

test('the density chart spans a week either side of today and counts matches by Beijing day', () => {
  const density = esportsDensity([
    { start_at: '2026-10-17T01:00:00Z' }, { start_at: '2026-10-17T15:30:00Z' }, // both on 10-17 in Beijing (23:30 included)
    { start_at: '2026-10-17T16:30:00Z' },                                     // 00:30 on 10-18
    { start_at: '2026-09-01T00:00:00Z' }, { start_at: null },
  ], NOW)
  assert.equal(density.length, 15)
  assert.deepEqual([density[0].date, density[7].date, density[14].date], ['2026-10-10', '2026-10-17', '2026-10-24'])
  assert.deepEqual(density.map(day => day.value).filter(Boolean), [2, 1])
  assert.deepEqual([density[7].today, density[7].value, density[8].value, density[7].label, density[7].day, density[0].day], [true, 2, 1, '10/17', 17, 10])
  assert.equal(density.filter(day => day.today).length, 1)
})
