const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : null
export const attendanceRows = value => Array.isArray(value) ? value.filter(object) : []

// Cloud detail responses may wrap the same observation in a snapshot envelope.
// Keep observation/signing timestamps separate from the outer fetch timestamp.
export function attendanceEnvelope(value) {
  if (!object(value) || !Object.keys(value).length) return null
  const payload = object(value.payload)
  return payload ? { ...value, ...payload, stale: !!(value.stale || payload.stale), error: value.error || payload.error } : value
}

export function attendanceCount(calendar) {
  const items = attendanceRows(calendar)
  const known = items.filter(item => item.done === true).length
  const complete = items.length > 0 && items.every(item => typeof item.done === 'boolean')
  return { known, total: complete ? known : null }
}
