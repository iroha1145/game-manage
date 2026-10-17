import test from 'node:test'
import assert from 'node:assert/strict'
import { formRecord, formStrip, heatmapDays, heatmapLayout, hourCounts, kdaBar, kdaRatio, kdaSplit, letterOf, meanOf, rankedSolo, resultParts, weeklyCounts } from './lol-charts.js'

test('letter tiles take the first visible character and never come out empty', () => {
  assert.equal(letterOf('疾风剑豪'), '疾')
  assert.equal(letterOf('  jinx'), 'J')
  assert.equal(letterOf(''), '?')
  assert.equal(letterOf(null, '队'), '队')
})

test('result parts keep real zeros and drop unknown counts instead of guessing', () => {
  const parts = resultParts({ wins: 33, losses: 30, unknown_results: 0, remakes: undefined })
  assert.deepEqual(parts.map(part => [part.key, part.value]), [['win', 33], ['loss', 30], ['unknown', 0], ['remake', 0]])
  assert.deepEqual(resultParts().map(part => part.value), [0, 0, 0, 0])
})

test('KDA is (K + A) / max(D, 1) and stays unknown when any number is unknown', () => {
  assert.equal(kdaRatio(6, 3, 12), 6)
  assert.equal(kdaRatio(7, 0, 5), 12)
  assert.equal(kdaRatio(0, 0, 0), 0)
  assert.equal(kdaRatio(0, null, 0), null)
  assert.equal(meanOf([{ kp: 40 }, { kp: null }, { kp: 60 }], 'kp'), 50)
  assert.equal(meanOf([{ kp: null }], 'kp'), null)
})

test('kill, death and assist shares sum to one; an empty line has no split', () => {
  const split = kdaSplit(5, 5, 10)
  assert.deepEqual(split, { k: 0.25, d: 0.25, a: 0.5 })
  assert.equal(kdaSplit(0, 0, 0), null)
  assert.equal(kdaSplit(1, null, 2), null)
})

test('KDA bars stop at the cap and say so', () => {
  assert.deepEqual(kdaBar(5), { pct: 50, clipped: false })
  assert.deepEqual(kdaBar(29), { pct: 100, clipped: true })
  assert.deepEqual(kdaBar(0), { pct: 4, clipped: false })
  assert.equal(kdaBar(null), null)
})

test('the form strip shows the newest games oldest first and counts only decided games', () => {
  const rows = [{ id: 1, k: 'win' }, { id: 2, k: 'loss' }, { id: 3, k: 'remake' }, { id: 4, k: 'win' }, { id: 5, k: 'unknown' }]
  const strip = formStrip(rows, row => row.k, 4)
  assert.deepEqual(strip.map(item => item.row.id), [4, 3, 2, 1])
  assert.deepEqual(strip.map(item => item.label), ['胜', '重', '负', '胜'])
  assert.deepEqual(formRecord(strip), { wins: 2, losses: 1, rate: 67 })
  assert.deepEqual(formRecord(formStrip([{ k: 'remake' }], row => row.k)), { wins: 0, losses: 0, rate: null })
})

test('ranked solo is read from the snapshot and an empty tier means unranked', () => {
  assert.deepEqual(rankedSolo({ extra: { ranked_solo: { tier: 'GOLD', division: 'II', league_points: 45, wins: 61, losses: 55 } } }),
    { tier: 'GOLD', division: 'II', points: 45, wins: 61, losses: 55 })
  assert.equal(rankedSolo({ extra: { ranked_solo: { tier: '' } } }), null)
  assert.equal(rankedSolo(null), null)
})

// 2026-10-17 12:00 Beijing, a Saturday.
const NOW = Date.parse('2026-10-17T12:00:00+08:00')

test('heat map days fill every date of the window, newest last, with zeros where nothing was played', () => {
  const days = heatmapDays([{ date: '2026-10-16', games: 3, wins: 2 }, { date: '2026-09-01', games: 9, wins: 9 }], 7, NOW)
  assert.deepEqual(days.map(day => day.date), ['2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16', '2026-10-17'])
  assert.deepEqual(days.map(day => day.games), [0, 0, 0, 0, 0, 3, 0])
})

test('the heat map lays dates into Monday-first weeks and labels the months', () => {
  const days = heatmapDays([{ date: '2026-10-16', games: 4, wins: 2 }, { date: '2026-10-15', games: 1, wins: 1 }, { date: '2026-10-14', games: 2, wins: 1 }], 90, NOW)
  const layout = heatmapLayout(days)
  // 2026-07-20 is a Monday, so the first cell sits in the top row.
  assert.equal(days[0].date, '2026-07-20')
  assert.equal(layout.first, 0)
  assert.equal(layout.weeks, 13)
  assert.deepEqual(layout.months.map(month => month.label), ['8月', '9月', '10月'])
  assert.deepEqual(layout.cells.filter(cell => cell.games).map(cell => [cell.date, cell.level]), [['2026-10-14', 2], ['2026-10-15', 1], ['2026-10-16', 4]])
  assert.equal(layout.busiest.date, '2026-10-16')
  assert.deepEqual([layout.total, layout.wins, layout.activeDays, layout.longest], [7, 4, 3, 3])
  // A window that starts midway through a week pushes its first cell down to that weekday.
  assert.equal(heatmapLayout(heatmapDays([], 30, NOW)).first, 4)
  assert.deepEqual(heatmapLayout([]), { cells: [], first: 0, weeks: 0, months: [], max: 0, total: 0, wins: 0, activeDays: 0, longest: 0, busiest: null })
})

test('weekly counts bucket dates by Beijing week and ignore what does not parse', () => {
  // The week of 10/12 is the current one (Saturday 10/17); Sunday night 10/11 still belongs to the week before.
  const counts = weeklyCounts(['2026-10-17T09:00:00+08:00', '2026-10-12', '2026-10-11T23:30:00+08:00', '2026-09-30', 'not a date', null, '2025-01-01'], 4, NOW)
  assert.deepEqual(counts, [{ label: '09/21', value: 0 }, { label: '09/28', value: 1 }, { label: '10/05', value: 1 }, { label: '10/12', value: 2 }])
})

test('hour counts use Beijing time whatever offset the start time carries', () => {
  const counts = hourCounts([
    { start_at: '2026-10-17T13:30:00+08:00' }, // 13:30 Beijing
    { start_at: '2026-10-17T05:59:00Z' },       // 13:59 Beijing
    { start_at: '2026-10-16T16:00:00Z' },       // midnight Beijing
    { start_at: null }, { start_at: 'garbage' },
  ])
  assert.equal(counts.length, 24)
  assert.deepEqual(counts.map((count, hour) => [hour, count]).filter(([, count]) => count), [[0, 1], [13, 2]])
  assert.deepEqual(hourCounts(), Array(24).fill(0))
})
