import test from 'node:test'
import assert from 'node:assert/strict'
import { reactive, nextTick } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Component = await loadVue(new URL('./EsportsSchedule.vue', import.meta.url))
test('zero completed scores stay visible and unsafe links are not rendered', t => {
  const root = mount(t, Component, { filters: {}, payload: { matches: [{ id: 'm', status: 'completed', score_a: 0, score_b: 3, source_url: 'javascript:alert(1)' }] } })
  assert.match(content(root), /0 : 3/); assert.equal(nodes(root, 'a').length, 0)
})

test('linked match is brought into view and focused for keyboard return', async t => {
  const filters = reactive({ matchId: 'target' })
  const root = mount(t, Component, { filters, payload: { matches: [{ id: 'target', status: 'scheduled' }] } })
  const article = nodes(root, 'article')[0]
  let scrolled = false, focused = false
  article.scrollIntoView = () => { scrolled = true }
  article.focus = () => { focused = true }
  await nextTick(); await nextTick()
  assert.ok(scrolled && focused)
  assert.match(content(root), /比赛摘要/)
})

const byClass = (root, tag, name) => nodes(root, tag).filter(n => String(n.props.class ?? '').split(/\s+/).includes(name))
const league = { tournaments: [{ id: 't', name: 'LPL', family: 'lpl' }], teams: [{ id: 'a', name: 'Alpha', short_name: 'ALP', tournament_ids: ['t'] }, { id: 'b', name: 'Beta', short_name: 'BET', tournament_ids: ['t'] }],
  matches: [
    { id: 'live', tournament_id: 't', team_a_id: 'a', team_b_id: 'b', team_a_name: 'Alpha', team_b_name: 'Beta', status: 'live', start_at: '2026-10-17T04:00:00Z', score_a: 1, score_b: 1 },
    { id: 'next', tournament_id: 't', team_a_id: 'a', team_b_id: 'b', team_a_name: 'Alpha', team_b_name: 'Beta', status: 'scheduled', start_at: '2026-10-18T09:00:00Z' },
    { id: 'done', tournament_id: 't', team_a_id: 'a', team_b_id: 'b', team_a_name: 'Alpha', team_b_name: 'Beta', status: 'completed', start_at: '2026-10-10T09:00:00Z', score_a: 2, score_b: 0, winner_team_id: 'a' },
  ] }

test('matches still to come are cards in a rail for their day, finished ones a compact list, and a live card is marked', t => {
  const root = mount(t, Component, { filters: {}, payload: league })
  const cards = byClass(root, 'article', 'es-card'), rows = byClass(root, 'article', 'es-row')
  assert.equal(cards.length, 2)
  assert.equal(rows.length, 1)
  assert.ok(String(cards[0].props.class).includes('is-live') && !String(cards[1].props.class).includes('is-live'))
  assert.equal(byClass(root, 'div', 'h-rail').length, 2, 'one rail for each day with a match to come')
  assert.match(content(root), /10月18日 周日/)
})

test('a team logo that cannot load still leaves a lettered tile, and the winner is the one marked', t => {
  const root = mount(t, Component, { filters: { view: 'results' }, payload: league })
  const tiles = byClass(root, 'span', 'es-logo')
  assert.deepEqual(tiles.map(n => n.props['data-letter']), ['ALP', 'BET'])
  assert.equal(nodes(root, 'img').length, 0, 'no logo URL means no image element')
  const [teamA, teamB] = nodes(root, 'button').filter(n => String(n.props.class).includes('es-row-team'))
  assert.ok(String(teamA.props.class).includes('es-winner') && !String(teamB.props.class).includes('es-winner'))
})
