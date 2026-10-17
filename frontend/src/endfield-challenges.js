export const CHALLENGE_KINDS = [['war', '战争'], ['monument', '丰碑'], ['crisis', '危机']]
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
const rows = value => Array.isArray(value) ? value.filter(item => item && typeof item === 'object' && !Array.isArray(item)) : []
const scalar = value => typeof value === 'string' || typeof value === 'number' && Number.isFinite(value) ? value : null
const number = value => (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null
const boolean = value => typeof value === 'boolean' ? value : null
const timestamp = value => typeof value === 'string' && value ? value : null

function groups(value) {
  return rows(value).map(group => ({ name: scalar(group.name), stars: number(group.star),
    stages: [['normalDungeon', '普通'], ['hardDungeon', '困难'], ['cruelDungeon', '险境']].flatMap(([key, difficulty]) => {
      const stage = object(group[key])
      return Object.keys(stage).length ? [{ name: scalar(stage.name), difficulty, passed: boolean(stage.isPass) }] : []
    }) }))
}

// Same allowlisted observation as the backend projection. An array alone does
// not prove collection; old normalized responses need their own fetch time.
export function challengeReport(value, kind) {
  const data = object(value), supplied = object(data.report)
  const requested = CHALLENGE_KINDS.some(([id]) => id === kind)
  if (requested && supplied.schema_version === 1 && supplied.kind === kind && (data.kind == null || data.kind === kind)) {
    const available = supplied.available === true && !!timestamp(supplied.fetched_at)
    return { ...supplied, available, stale: !!(supplied.stale || data.stale || data.error),
      fetched_at: available ? supplied.fetched_at : null,
      records: available && supplied.supported !== false ? rows(supplied.records) : [],
      honors: available && supplied.supported !== false ? rows(supplied.honors) : [],
      summary: available && supplied.supported !== false ? object(supplied.summary) : {} }
  }
  const valid = requested && data.kind === kind && (supplied.schema_version !== 1 || supplied.kind === kind)
  const fetchedAt = valid ? timestamp(data.fetched_at) : null
  const available = !!fetchedAt, supported = valid ? boolean(data.supported) : null
  const summary = object(data.summary)
  const records = available && supported !== false ? rows(data.records).map(raw => {
    const base = { id: scalar(raw.id), name: scalar(raw.name), start_at: scalar(raw.start_at), end_at: scalar(raw.end_at) }
    if (kind === 'war') return { ...base, stars: number(raw.stars), weeks: rows(raw.weeks).map(week => ({ id: scalar(week.id), name: scalar(week.name), stars: number(week.stars), groups: groups(week.groups) })) }
    if (kind === 'monument') return { ...base, groups: groups(raw.groups) }
    return { ...base, passed: boolean(raw.isPass), result: [raw.score, raw.grade, raw.result].map(scalar).find(item => item !== null) ?? null }
  }) : []
  return { schema_version: 1, kind: requested ? kind : null, available, supported, stale: !!(valid && (data.stale || data.error)), fetched_at: fetchedAt,
    records, honors: available && kind === 'war' && supported !== false ? rows(summary.honors).map(item => ({ name: scalar(item.name), stars: number(item.star), first_pass_at: scalar(item.first_pass_at) })) : [],
    summary: { listed_count: available && supported !== false ? records.length : null,
      highest: available && kind === 'crisis' ? number(summary.highest) : null,
      challenge_count: available && kind === 'crisis' ? number(summary.challenge_count) : null } }
}

export function retainedChallenge(previous, error) {
  return previous ? { ...previous, stale: true, error } : null
}

export function challengeEnvelope(value) {
  if (!value?.payload || typeof value.payload !== 'object') return value
  return {...value,...value.payload,stale:!!(value.stale || value.payload.stale),error:value.error || value.payload.error}
}

/** How many stages in the (already projected) groups are cleared, open, or not observed. */
export function stageStates(groups) {
  const states = { passed: 0, failed: 0, unknown: 0 }
  for (const group of rows(groups)) for (const stage of rows(group.stages)) states[stage.passed === true ? 'passed' : stage.passed === false ? 'failed' : 'unknown']++
  return states
}
