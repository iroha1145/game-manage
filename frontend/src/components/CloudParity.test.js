import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
import { createCloudDashboard } from '../cloud-dashboard.js'
const Card = await loadVue(new URL('./CloudGameCard.vue', import.meta.url))
const App = await loadVue(new URL('../CloudApp.vue', import.meta.url))
const Details = await loadVue(new URL('./CloudAccountDetails.vue', import.meta.url))
const Profile = await loadVue(new URL('./CloudSklandProfile.vue', import.meta.url))
const Status = await loadVue(new URL('./CloudSnapshotStatus.vue', import.meta.url))
const Calendar = await loadVue(new URL('./CalendarPage.vue', import.meta.url))
const Articles = await loadVue(new URL('./AnnouncementList.vue', import.meta.url))
const tick = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const button = (root, label) => nodes(root, 'button').find(n => content(n) === label)
const account = (provider, id = provider) => ({ account_id: id, provider, state: 'active', capabilities: ['account', 'stamina'], roles: [{ role_id: `${id}-default`, display_name: `${id}默认角色`, is_default: true }, { role_id: `${id}-other`, display_name: `${id}另一角色` }] })
test('wuwa card forwards calendar and shows public news inside its existing tab', async t => {
  let opened = 0
  const root = mount(t, Card, { account: account('kuro'), role: 'kuro-default', publicSnapshots: { news: { state: 'ok', fetched_at: '2026-10-14T00:00:00Z', payload: [{ title: '公共卡池公告', content: '合成公告' }] } }, onCalendar: () => opened++ })
  button(root, '活动日历').props.onClick(); assert.equal(opened, 1)
  button(root, '公告与资讯').props.onClick(); await tick()
  assert.match(content(root), /公共卡池公告/)
})
test('nte uses original module summaries and restored guide entry', async t => {
  const root = mount(t, Card, { account: { ...account('tajiduo'), capabilities: ['account','stamina','roles','realestate','gacha'] }, role: 'tajiduo-default', snapshots: { stamina: { payload: { schema_version:1,current:0,maximum:120 } } } })
  assert.ok(button(root, '角色与探索')); assert.ok(button(root, '房产与载具'))
  assert.ok(nodes(root, 'section').some(n => n.props.class?.includes('nte-module-card')))
  assert.ok(button(root,'角色攻略'));assert.doesNotMatch(content(root), /暂未开放/)
  assert.doesNotMatch(content(root), /审核攻略|管理员来源配置/)
})
test('overview reads every owner default role and discards delayed results after user changes', async t => {
  const finishes=[]
  const d = createCloudDashboard({ getAccountSnapshot: (id, role, cap) => id === 'b' ? new Promise(resolve => { finishes.push(resolve) }) : Promise.resolve({ payload: { nickname: `${id}/${role}/${cap}` }, state:'ok' }) }); t.after(d.dispose)
  d.state.user = { user_id:'A' }; d.state.accounts = [account('kuro','a'), account('tajiduo','b')]; d.selectAccount(d.state.accounts[0], 'a-other')
  const pending = d.loadOverview(); await tick()
  assert.match(JSON.stringify(d.state.overview), /a-default/); assert.doesNotMatch(JSON.stringify(d.state.overview.a.snapshots), /a-other/)
  d.clear(); d.state.user = { user_id:'B' }; finishes.forEach(resolve=>resolve({ payload:{nickname:'迟到A'}, state:'ok' })); await pending
  assert.deepEqual(d.state.overview, {})
})
test('cloud owner overview navigates to wuwa and its calendar preselects the game', async t => {
  configureHttpClient({mode:'cloud'}); t.after(() => configureHttpClient({mode:'local'}))
  const paths = []
  t.mock.method(globalThis,'fetch', async path => { paths.push(path); return new Response(JSON.stringify(path === '/api/identity/me' ? {user_id:'A'} : path.endsWith('/csrf') ? {csrf_token:'fixture'} : path === '/api/accounts' ? {accounts:[account('kuro'),account('tajiduo')]} : {state:'ok',payload:path.endsWith('/news') ? [{title:'共用公共资讯'}] : path.endsWith('/events') ? [] : {schema_version:1,nickname:'本人昵称',current:0,maximum:120}})) })
  const root = mount(t,App); await tick(); await tick()
  assert.match(content(root), /今日总览/); assert.doesNotMatch(content(root), /数据保存在本机/)
  const overview = nodes(root,'button').find(n => n.props.class?.includes('game-summary') && content(n).includes('鸣潮')); assert.ok(overview)
  overview.props.onClick(); await tick(); await tick()
  assert.match(content(root), /kuro默认角色/)
  button(root,'公告与资讯').props.onClick(); await tick(); assert.match(content(root), /共用公共资讯/)
  nodes(root,'button').filter(n=>content(n)==='活动日历').at(-1).props.onClick(); await tick(); await tick()
  assert.ok(nodes(root,'button').some(n => n.props['aria-label'] === '筛选游戏' && content(n).includes('鸣潮')))
  assert.ok(paths.every(path => !path.startsWith('/api/games/') && !path.startsWith('/api/collection')))
})
test('skland detail selectors use every allowed challenge/tool kind and isolate late categories', async t => {
  configureHttpClient({mode:'cloud'}); t.after(() => configureHttpClient({mode:'local'}))
  const calls=[]; let delayed
  t.mock.method(globalThis,'fetch',async path => { calls.push(path); if(path.endsWith('kind=war')) return new Promise(resolve=>{delayed=()=>resolve(new Response(JSON.stringify({records:[{name:'过期战争'}]}))) }); return new Response(JSON.stringify(path.includes('/challenges') ? {records:[{name:'当前挑战'}]} : {payload:[{name:'工具目录'}]})) })
  const props=reactive({account:account('skland'),role:'skland-default'}), root=mount(t,Details,props)
  const type=nodes(root,'select')[0]; type.props['onUpdate:modelValue']('challenges'); await tick()
  const kind=nodes(root,'select')[1]; assert.equal(kind.children.filter(n=>n.type==='option').length,3)
  const pending=button(root,'读取详情').props.onClick(); await tick()
  kind.props['onUpdate:modelValue']('monument'); await tick(); await button(root,'读取详情').props.onClick(); await tick(); delayed(); await pending; await tick()
  assert.match(content(root),/当前挑战/); assert.doesNotMatch(content(root),/过期战争/)
  type.props['onUpdate:modelValue']('tools'); await tick(); const tools=nodes(root,'select')[1]; assert.equal(tools.children.filter(n=>n.type==='option').length,5)
  tools.props['onUpdate:modelValue']('materials'); await tick(); await button(root,'读取详情').props.onClick(); await tick()
  assert.ok(calls.some(p=>p.endsWith('kind=monument'))); assert.ok(calls.some(p=>p.endsWith('kind=materials')))
})
test('skland profile preserves structured exploration, assigned operators and zero counts', t => {
  const root=mount(t,Profile,{payload:{base:{name:'本人档案'},regions:[{name:'谷地',money:{count:0,total:10},levels:[{name:'矿区',puzzles:{count:0,total:3},chests:{count:2,total:4}}],settlements:[{name:'据点甲',level:0}]}],ship:[{name:'舱室甲',level:0,operators:[{name:'驻守甲',physicalStrength:0,favorability:1}]}],achievements:{count:0,medals:[{name:'勋章甲'}]}}})
  assert.match(content(root),/矿区.*谜质.*0.*3/); assert.match(content(root),/据点甲/); assert.match(content(root),/驻守甲.*体力.*0/); assert.match(content(root),/勋章甲/)
})
test('public source state uses nested source statuses and retains original Beijing content time',t=>{
  const root=mount(t,Status,{capabilities:['news'],snapshots:{news:{state:'ok',fetched_at:'2026-10-14T00:00:00Z',primary_source:'bilibili',version:'3.0',poll_status:{source_statuses:{community:{state:'error',last_success_at:'2026-10-13T00:00:00Z',error:'原生来源失败'},bilibili:{state:'ok',last_success_at:'2026-10-14T00:00:00Z'}}}}}})
  assert.match(content(root),/原生来源失败/);assert.match(content(root),/2026-10-14 08:00/);assert.match(content(root),/版本 3.0/)
})
test('operator changes clear details synchronously and prevent an old response being shown for new selection',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  let finish
  t.mock.method(globalThis,'fetch',async()=>new Promise(resolve=>{finish=()=>resolve(new Response(JSON.stringify({payload:{name:'旧干员',weapon:{name:'旧武器'}}}))) }))
  const root=mount(t,Details,{account:account('skland'),role:'skland-default',snapshot:{payload:{operators:[{id:'a',name:'干员甲'},{id:'b',name:'干员乙'}]}}})
  nodes(root,'select')[0].props['onUpdate:modelValue']('operators');await tick()
  nodes(root,'select')[1].props['onUpdate:modelValue']('a');await tick()
  const pending=button(root,'读取详情').props.onClick();await tick()
  nodes(root,'select')[1].props['onUpdate:modelValue']('b');await tick();finish();await pending;await tick()
  assert.doesNotMatch(content(root),/旧干员|旧武器/)
})
test('public partial-source failures distinguish fresh contributing fallback from retained stale data', t=>{
  for(const stale of [false,true]) {
    const snap={state:'error',stale,primary_source:'community',fetched_at:'2026-10-14T00:00:00Z',payload:[{name:'可用来源活动',title:'可用来源资讯',source:'community',source_stale:stale,start_at:null,end_at:null}],poll_status:{source_statuses:{community:{state:'ok',stale:false},bilibili:{state:'error',error:'B站412'}}}}
    const calendar=mount(t,Calendar,{games:[{game_id:'wuthering_waves',display_name:'鸣潮',capabilities:['events']}],snapshots:{wuthering_waves:{events:snap}}})
    const articles=mount(t,Articles,{snap}), status=mount(t,Status,{capabilities:['events'],snapshots:{events:snap}})
    if(!stale) {
      for(const view of [calendar,articles,status])assert.match(content(view),/部分来源不可用，显示可用来源数据/)
      assert.doesNotMatch(content(calendar),/活动采集失败|保留上次成功快照|数据可能过期/)
      assert.doesNotMatch(content(articles),/采集失败，保留上次成功数据|旧记录|数据可能过期/)
    } else {
      assert.match(content(calendar),/活动采集失败.*保留上次成功快照/)
      assert.match(content(articles),/采集失败，保留上次成功数据/)
      for(const view of [calendar,articles,status])assert.doesNotMatch(content(view),/部分来源不可用，显示可用来源数据/)
    }
  }
})
