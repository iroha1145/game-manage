// Explicit collection state only: legacy local snapshots without a state keep
// their existing display semantics. Empty payloads alone never prove failure.
export function collectionState(snapshot) {
  const state = snapshot?.state || snapshot?.poll_status?.state
  if (['error', 'source_error', 'invalid_data', 'offline', 'auth_expired', 'expired'].includes(state) || snapshot?.error || snapshot?.poll_status?.error) return 'failed'
  if (state === 'never') return 'never'
  return state === 'ok' ? 'collected' : ''
}

// A failed auxiliary public source does not make fresh contributing content old.
// Require explicit freshness and a matching successful source; private snapshots
// and source statuses without contribution evidence keep the failure wording.
export function hasFreshPublicFallback(snapshot) {
  const sources = snapshot?.source_statuses || snapshot?.poll_status?.source_statuses
  if (!sources || snapshot.stale !== false || !Array.isArray(snapshot.payload) || !snapshot.payload.length) return false
  const rows = Array.isArray(sources) ? sources.map(row => [row.source, row]) : Object.entries(sources)
  return rows.some(([, row]) => collectionState(row) === 'failed') && rows.some(([source, row]) =>
    row?.state === 'ok' && !row.stale && snapshot.payload.some(item => item && !item.source_stale && (item.source || snapshot.primary_source) === source))
}
