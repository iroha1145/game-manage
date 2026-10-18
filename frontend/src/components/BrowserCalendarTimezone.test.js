import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { formatBrowserDateTime } from '../calendar.js'
import { configureHttpClient } from '../http-client.js'

const Calendar = await loadVue(new URL('./CalendarPage.vue',import.meta.url))
const Status = await loadVue(new URL('./CloudSnapshotStatus.vue',import.meta.url))
const CloudApp = await loadVue(new URL('../CloudApp.vue',import.meta.url))

test('calendar source summary and individual source times use browser time while shared defaults retain Beijing', t => {
  const summary='2026-01-01T00:30:00Z', source='2025-12-31T23:30:00Z'
  const snap={state:'ok',fetched_at:summary,payload:[],source_statuses:{official:{state:'ok',fetched_at:source},community:{state:'ok',last_success_at:'broken'}}}
  const root=mount(t,Calendar,{games:[{game_id:'nte',display_name:'异环'}],snapshots:{nte:{events:snap}},showSourceStatus:true})
  const sourceStatus=nodes(root,'details').find(node=>node.props.class==='cloud-snapshot-states')
  assert.ok(sourceStatus)
  const rows=nodes(sourceStatus,'p')
  assert.ok(content(rows[0]).includes(formatBrowserDateTime(summary)))
  assert.ok(content(rows[1]).includes(formatBrowserDateTime(source)))
  assert.match(content(rows[2]),/未提供/)
  assert.doesNotMatch(content(rows[2]),/未知/)
  const original=mount(t,Status,{capabilities:['events'],snapshots:{events:snap}})
  const originalRows=nodes(original,'p')
  assert.match(content(originalRows[0]),/2026-01-01 08:30/)
  assert.match(content(originalRows[1]),/2026-01-01 07:30/)
  assert.match(content(originalRows[2]),/未提供/)
})

test('browser workspace top date follows the same local calendar date across midnight', async t => {
  const now=Date.parse('2026-01-01T00:30:00Z')
  t.mock.timers.enable({apis:['Date'],now})
  configureHttpClient({mode:'cloud'})
  t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path => new Response(JSON.stringify(
    path==='/api/identity/me'?{user_id:'timezone-fixture'}:path==='/api/accounts'?{accounts:[]}:path.endsWith('/csrf')?{csrf_token:'fixture'}:{state:'never',payload:null}
  )))
  const root=mount(t,CloudApp)
  for (let index=0;index<4;index++) { await new Promise(resolve=>setImmediate(resolve)); await nextTick() }
  const date=nodes(root,'span').find(node=>node.props.class==='topbar-date')
  const expected=new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long'}).format(now)
  assert.equal(content(date),expected)
})
