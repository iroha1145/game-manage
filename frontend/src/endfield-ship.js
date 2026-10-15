export const SHIP_CONVERSION_MODEL = Object.freeze({
  id: 'endfield-plugin-spaceship-v3.5.0', kind: 'static_observation',
  source_url: 'https://github.com/Entropy-Increase-Team/endfield-plugin/blob/main/API.md#L6089-L6123',
})
const owns = (value, key) => Object.prototype.hasOwnProperty.call(value, key)
const decimal = /^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/
const number = value => (typeof value === 'number' || typeof value === 'string' && decimal.test(value.trim())) && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null
const bounded = (value, maximum) => { const result = number(value); return result != null && result <= maximum ? result : null }
const rows = value => Array.isArray(value) ? value.filter(item => item && typeof item === 'object' && !Array.isArray(item)) : []

// Compatibility for saved observations predating the shared backend fields.
// Explicit values (including null) from the new report remain authoritative.
export function shipResident(operator) {
  const mood = number(owns(operator, 'mood_raw') ? operator.mood_raw : operator.physicalStrength)
  const trust = number(owns(operator, 'trust_raw') ? operator.trust_raw : operator.favorability)
  const trustPercent = trust == null ? null : trust < 300 ? Math.floor(trust / 3) : trust < 1500 ? 100 + Math.floor((trust - 300) / 12) : 200
  const trustLevel = trust == null ? null : trust < 300 ? '友好' : trust < 1500 ? '亲近' : '信任'
  return { ...operator, mood_raw: mood, trust_raw: trust,
    mood_percent: owns(operator, 'mood_percent') ? bounded(operator.mood_percent, 100) : mood != null && mood <= 10000 ? mood / 100 : null,
    trust_percent: owns(operator, 'trust_percent') ? bounded(operator.trust_percent, 200) : trustPercent,
    trust_level_name: owns(operator, 'trust_level_name') ? ['友好', '亲近', '信任'].includes(operator.trust_level_name) ? operator.trust_level_name : null : trustLevel,
  }
}

export function shipReport(value, operators = []) {
  if (!value) return value
  const index = new Map()
  for (const operator of rows(operators)) for (const key of ['id', 'char_id']) if (operator[key] != null) index.set(String(operator[key]), operator)
  const rooms = rows(value.rooms).map(room => ({ ...room,
    operators_available: typeof room.operators_available === 'boolean' ? room.operators_available : rows(room.operators).length ? true : null,
    operators: rows(room.operators).map(operator => {
      const id = operator.id ?? operator.charId ?? operator.char_id
      const record = index.get(String(id))
      return shipResident({ ...operator, id, name: operator.name || operator.charData?.name || record?.name,
        avatar_url: operator.avatar_url || record?.avatar_url || operator.charData?.avatarSqUrl })
    }) }))
  const available = typeof value.available === 'boolean' ? value.available : rooms.length ? true : null
  const staffAvailable = available === true && rooms.every(room => room.operators_available === true)
  return { ...value, available, conversion_model: value.conversion_model ?? SHIP_CONVERSION_MODEL, rooms,
    summary: { room_count: available === true ? rooms.length : null,
      staffed_rooms: staffAvailable ? rooms.filter(room => room.operators.length).length : null,
      operator_slots: staffAvailable ? rooms.reduce((total, room) => total + room.operators.length, 0) : null,
      ...value.summary } }
}

// Match the report/QQ display rule, including half-up decimal boundaries.
export function shipPercent(value) {
  const percent = number(value)
  return percent == null ? '未知' : `${Math.floor(percent * 10 + 0.5) / 10}%`
}
