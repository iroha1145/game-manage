import test from 'node:test'
import assert from 'node:assert/strict'
import { donutArcs, niceCeil, roundedArc, share, smoothPath } from './chart-math.js'

test('share keeps unknowns unknown and only clamps values above the maximum', () => {
  assert.equal(share(null, 240), null)
  assert.equal(share(3, 0), null)
  assert.equal(share(-1, 10), null)
  assert.equal(share(0, 240), 0)
  assert.equal(share(120, 240), 0.5)
  assert.equal(share(300, 240), 1)
})

test('axis tops round up to 1, 2, 2.5 or 5 times a power of ten', () => {
  assert.deepEqual([0, 0.7, 1, 7, 18, 21, 240, 1234, 99999].map(niceCeil), [1, 1, 1, 10, 20, 25, 250, 2000, 100000])
})

test('the smoothed line passes through every point and never swings past its neighbours', () => {
  const points = [{ x: 0, y: 50 }, { x: 10, y: 10 }, { x: 20, y: 10 }, { x: 30, y: 60 }, { x: 40, y: 55 }]
  const path = smoothPath(points)
  assert.match(path, /^M0,50C/)
  const segments = path.slice(path.indexOf('C') + 1).split('C').map(part => part.split(',').map(Number))
  assert.equal(segments.length, points.length - 1)
  segments.forEach((numbers, i) => {
    const [, c1y, , c2y, x, y] = numbers
    assert.deepEqual([x, y], [points[i + 1].x, points[i + 1].y])
    const low = Math.min(points[i].y, points[i + 1].y), high = Math.max(points[i].y, points[i + 1].y)
    // Monotone control points stay inside each segment's own range, so a flat run stays flat.
    for (const c of [c1y, c2y]) assert.ok(c >= low - 1e-9 && c <= high + 1e-9, `segment ${i}: ${c} outside ${low}…${high}`)
  })
  assert.equal(smoothPath([]), '')
  assert.equal(smoothPath([{ x: 3, y: 4 }]), 'M3,4')
})

test('donut parts leave a gap between neighbours and give empty parts no room', () => {
  assert.deepEqual(donutArcs([1, 1, 2], 1), [{ start: 0, length: 24 }, { start: 25, length: 24 }, { start: 50, length: 49 }])
  assert.deepEqual(donutArcs([5, 0, null, 5], 2).map(arc => arc.length), [48, 0, 0, 48])
  assert.deepEqual(donutArcs([7], 2), [{ start: 0, length: 100 }])
  assert.deepEqual(donutArcs([0, null]), [])
})

test('round caps stay within the true progress span, including tiny and nearly complete values', () => {
  for (const length of [0.01, 1, 25, 50, 99.99]) {
    const arc = roundedArc(7, length, 28, 7)
    const cap = Math.asin(arc.stroke / (2 * 28)) / Math.PI * 100
    assert.ok(arc.stroke > 0 && arc.stroke <= 7)
    assert.ok(Math.abs(arc.start - cap / 2 - 7) < 1e-9)
    assert.ok(Math.abs(arc.start + arc.length + cap / 2 - (7 + length)) < 0.000002)
  }
  assert.equal(roundedArc(0, 0, 28, 7), null)
  assert.deepEqual(roundedArc(0, 100, 28, 7), { start: 0, length: 100, stroke: 7 })
})

test('rounded donut caps preserve the visible separation and skip unknown parts', () => {
  const arcs = donutArcs([1, 0, null, 3], 1).map(arc => roundedArc(arc.start, arc.length, 58, 16))
  assert.equal(arcs[1], null)
  assert.equal(arcs[2], null)
  const cap = Math.asin(16 / (2 * 58)) / Math.PI * 100
  assert.ok(Math.abs((arcs[3].start - cap / 2) - (arcs[0].start + arcs[0].length + cap / 2) - 1) < 1e-9)
})
