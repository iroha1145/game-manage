import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue,mount,nodes,content } from '../test-utils/vue.js'
import { configureHttpClient,invalidateSession } from '../http-client.js'
const Panel=await loadVue(new URL('./QqBindingPanel.vue',import.meta.url))
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));await nextTick()}
const identity={app_id:'app',scene:'group',group_openid:'fixture-group',sender_openid:'fixture-sender'}
test('QQ generated command copies once and binding list unlinks with CSRF without receipt form',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  const calls=[],copied=[]
  t.mock.method(globalThis,'fetch',async(path,options)=>{calls.push([path,options]);return new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'csrf'}:path.endsWith('/link-codes')?{code:'single-use-fixture',expires_at:'soon'}:path.endsWith('/link-attempts')?{attempts:[{attempt_id:'legacy',identity,status:'pending'}],links:[{link_id:'link',identity}]}:{}))})
  const prior=globalThis.navigator
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async text=>copied.push(text)}}})
  t.after(()=>Object.defineProperty(globalThis,'navigator',{configurable:true,value:prior}))
  const root=mount(t,Panel);await tick();await tick()
  assert.equal(nodes(root,'form').length,0);assert.equal(nodes(root,'input').length,0)
  assert.match(content(root),/fixture-group/);assert.match(content(root),/2 分钟/)
  assert.match(content(root),/群内查询的游戏昵称、角色和记录对群成员可见/)
  assert.match(content(root),/解除关联后，此 QQ 无法继续查询，已有数据和聊天记录不会删除/)
  await nodes(root,'button').find(n=>content(n)==='生成或更换绑定码').props.onClick();await tick()
  assert.match(content(root),/绑定 single-use-fixture/)
  await nodes(root,'button').find(n=>content(n)==='复制绑定指令').props.onClick();await tick()
  assert.deepEqual(copied,['绑定 single-use-fixture'])
  await nodes(root,'button').find(n=>content(n)==='解除关联').props.onClick();await tick()
  const unlink=calls.find(x=>x[0].endsWith('/links/link'))
  assert.equal(unlink[1].method,'DELETE');assert.equal(unlink[1].headers['X-CSRF-Token'],'csrf')
  assert.equal(calls.some(x=>x[0].endsWith('/confirm')),false)
})
test('QQ code clears on website session invalidation',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path=>new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'csrf'}:path.endsWith('/link-codes')?{code:'single-use-fixture',expires_at:'soon'}:{attempts:[],links:[]})))
  const root=mount(t,Panel);await tick();await tick()
  assert.match(content(root),/群内查询的游戏昵称、角色和记录对群成员可见/)
  assert.match(content(root),/还没有绑定的 QQ/)
  await nodes(root,'button').find(n=>content(n)==='生成或更换绑定码').props.onClick();await tick()
  assert.match(content(root),/single-use-fixture/)
  invalidateSession();await tick()
  assert.doesNotMatch(content(root),/single-use-fixture/)
})
test('QQ copy failure is Chinese text whether the page has no clipboard or the browser refuses it',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path=>new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'csrf'}:path.endsWith('/link-codes')?{code:'single-use-fixture',expires_at:'soon'}:{attempts:[],links:[]})))
  const prior=globalThis.navigator
  t.after(()=>Object.defineProperty(globalThis,'navigator',{configurable:true,value:prior}))
  const root=mount(t,Panel);await tick();await tick()
  await nodes(root,'button').find(n=>content(n)==='生成或更换绑定码').props.onClick();await tick()
  for(const clipboard of [undefined,{writeText:async()=>{throw new DOMException('Document is not focused.','NotAllowedError')}}]){
    Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard}})
    await nodes(root,'button').find(n=>content(n)==='复制绑定指令').props.onClick();await tick()
    assert.match(content(nodes(root,'p').find(n=>n.props.role==='alert')),/无法自动复制，请手动复制绑定指令/)
    assert.doesNotMatch(content(root),/已复制/)
  }
})
test('QQ binding code shows its expiry in Beijing time',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path=>new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'csrf'}:path.endsWith('/link-codes')?{code:'single-use-fixture',expires_at:'2026-10-16T14:02:00.123456Z'}:{attempts:[],links:[]})))
  const root=mount(t,Panel);await tick();await tick()
  await nodes(root,'button').find(n=>content(n)==='生成或更换绑定码').props.onClick();await tick()
  assert.match(content(root),/到期 2026-10-16 22:02(?!:)/)
})
