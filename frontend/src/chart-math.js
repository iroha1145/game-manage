// Geometry shared by the SVG and CSS charts. Pure functions, so the tests pin the maths.

const round = value => Math.round(value * 100) / 100

/** How much of a gauge a value fills, 0–1; null when either side is unknown or the maximum is not positive. */
export function share(value, max) {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0 || value < 0) return null
  return Math.min(1, value / max)
}

/** A round axis top at or above `value`: 1, 2, 2.5 or 5 times a power of ten. */
export function niceCeil(value) {
  if (!Number.isFinite(value) || value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  return [1, 2, 2.5, 5, 10].find(step => step * power >= value - 1e-9) * power
}

/** Monotone cubic path (Fritsch–Carlson) through points, so the curve never swings past the data. */
export function smoothPath(points) {
  const n = points.length
  if (!n) return ''
  let path = `M${round(points[0].x)},${round(points[0].y)}`
  if (n === 1) return path
  const dx = [], slope = []
  for (let i = 0; i < n - 1; i++) {
    dx[i] = points[i + 1].x - points[i].x
    slope[i] = dx[i] ? (points[i + 1].y - points[i].y) / dx[i] : 0
  }
  const tangent = [slope[0]]
  for (let i = 1; i < n - 1; i++) tangent[i] = slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2
  tangent[n - 1] = slope[n - 2]
  for (let i = 0; i < n - 1; i++) {
    if (!slope[i]) { tangent[i] = 0; tangent[i + 1] = 0; continue }
    const a = tangent[i] / slope[i], b = tangent[i + 1] / slope[i], length = a * a + b * b
    if (length > 9) {
      const k = 3 / Math.sqrt(length)
      tangent[i] = k * a * slope[i]
      tangent[i + 1] = k * b * slope[i]
    }
  }
  for (let i = 0; i < n - 1; i++) {
    const third = dx[i] / 3, from = points[i], to = points[i + 1]
    path += `C${round(from.x + third)},${round(from.y + tangent[i] * third)},${round(to.x - third)},${round(to.y - tangent[i + 1] * third)},${round(to.x)},${round(to.y)}`
  }
  return path
}

/**
 * Donut segments on a circle measured as 100 units (SVG pathLength="100").
 * Each segment gives up `gap` units at its end so neighbours never touch;
 * zero, negative and unknown values take no room.
 */
export function donutArcs(values, gap = 0) {
  const parts = values.map(value => (Number.isFinite(value) && value > 0 ? value : 0))
  const total = parts.reduce((sum, value) => sum + value, 0)
  if (!total) return []
  const shown = parts.filter(Boolean).length
  let start = 0
  return parts.map(value => {
    const length = (value / total) * 100
    const arc = { start: round(start), length: round(Math.max(0, shown > 1 ? length - gap : length)) }
    start += length
    return arc
  })
}
