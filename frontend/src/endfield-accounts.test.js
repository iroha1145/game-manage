import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveEndfieldSources, endfieldRoleChoices } from './endfield-accounts.js'
const make = (provider, changes = {}) => ({ account_id: provider, provider, game: 'endfield', state: 'active', channel: 'bilibili', server: '1', user_id: 'user', roles: [{ role_id: `${provider}-opaque`, game_uid: '9001', display_name: 'same name' }], ...changes })
const sources = rows => resolveEndfieldSources(rows, rows[0], rows[0].roles[0].role_id)

test('a verified Bilibili character has one choice, canonical Hypergryph, from either source', () => {
  const h = make('hypergryph'), s = make('skland'), rows = [s, h]
  const resolved = sources(rows)
  assert.equal(resolved.hypergryph.account, h); assert.equal(resolved.hypergryph.role, 'hypergryph-opaque')
  assert.equal(resolved.skland.account, s); assert.equal(resolved.skland.role, 'skland-opaque')
  assert.deepEqual(endfieldRoleChoices(rows), [{ key: 'hypergryph:hypergryph-opaque', account: h, role: 'hypergryph-opaque', sources: resolved }])
})
for (const [name, changes] of Object.entries({
  uid: { roles: [{ role_id: 's', game_uid: '9002', display_name: 'same name' }] }, server: { server: '2' }, channel: { channel: 'official' },
  unknownChannel: { channel: 'unknown' }, missingServer: { server: '' }, owner: { user_id: 'another-user' }, inactive: { state: 'revoked' }, otherGame: { game: 'nte' },
})) test(`identity mismatch (${name}) cannot pair equal display names`, () => {
  const rows = [make('hypergryph'), make('skland', changes)]
  assert.deepEqual(Object.keys(sources(rows)), ['hypergryph'])
  assert.equal(endfieldRoleChoices(rows).length, name === 'otherGame' ? 1 : 2)
})
test('orphaned roles and ambiguous provider identities stay separate', () => {
  const h = make('hypergryph'), s = make('skland'), second = make('skland', { account_id: 'second' })
  assert.deepEqual(Object.keys(sources([h])), ['hypergryph'])
  assert.deepEqual(Object.keys(sources([h, s, second])), ['hypergryph'])
  assert.deepEqual(Object.keys(resolveEndfieldSources([h, s, second], s, s.roles[0].role_id)), ['skland'])
  assert.equal(endfieldRoleChoices([h, s, second]).length, 3)
})
test('legacy passport data needs one child role and an exact parent pointer with a known matching channel/server', () => {
  const h = make('hypergryph', { roles: [{ role_id: 'h' }] })
  const s = make('skland', { roles: [{ role_id: 's' }], authorization_source: 'passport', parent_account_id: h.account_id, parent_role_id: 'h' })
  assert.equal(endfieldRoleChoices([h, s]).length, 1)
  for (const changes of [{ parent_role_id: 'other' }, { parent_account_id: 'other' }, { authorization_source: 'manual' }, { channel: 'unknown' }, { roles: [{ role_id: 's' }, { role_id: 's2' }] }]) {
    assert.deepEqual(Object.keys(sources([h, { ...s, ...changes }])), ['hypergryph'])
  }
  const knownH = { ...h, roles: [{ role_id: 'h', game_uid: '1' }] }, knownS = { ...s, roles: [{ role_id: 's', game_uid: '2' }] }
  assert.equal(endfieldRoleChoices([knownH, knownS]).length, 2, 'a parent pointer must not override conflicting verified UIDs')
})
test('a stale selection and inactive grants never resolve a usable source', () => {
  const h = make('hypergryph')
  assert.deepEqual(resolveEndfieldSources([], h, h.roles[0].role_id), {})
  assert.deepEqual(resolveEndfieldSources([{ ...h, state: 'revoked' }], h, h.roles[0].role_id), {})
  assert.deepEqual(resolveEndfieldSources([h], h, 'unknown-role'), {})
})

test('other games are absent from Endfield choices; legacy provider-only Endfield rows remain usable', () => {
  const h = make('hypergryph'), s = make('skland')
  delete h.game; delete s.game
  const other = [{ account_id: 'k', provider: 'kuro', roles: [{ role_id: 'kr' }] }, { account_id: 't', provider: 'tajiduo', game: 'nte', roles: [{ role_id: 'tr' }] }]
  assert.equal(endfieldRoleChoices([h, s, ...other]).length, 1)
  assert.equal(resolveEndfieldSources([h, s], h, h.roles[0].role_id).skland.account, s)
  assert.equal(endfieldRoleChoices(other).length, 0)
})
