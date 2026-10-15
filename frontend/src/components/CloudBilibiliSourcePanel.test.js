import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { Window } from 'happy-dom'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient, invalidateSession } from '../http-client.js'
import { requestJson } from '../http-client.js'
const tick = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const ROOT = '/api/admin/bilibili-source/login'
function documentType(t) {
  const dom=new Window(),previous=new Map(['Document','ShadowRoot','document'].map(key=>[key,globalThis[key]]))
  for(const key of previous.keys())globalThis[key]=dom[key]
  t.after(()=>{for(const [key,value] of previous)if(value===undefined)delete globalThis[key];else globalThis[key]=value})
}

test('cloud source QR is explicit, csrf protected and contains no password or cookie inputs', async t => {
  configureHttpClient({ mode:'cloud' }); t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout']})
  const calls = []
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    calls.push([path,options])
    const data = path.endsWith('/csrf') ? {csrf_token:'fixture'} : path.endsWith('/status') ? {configured:false} : path.endsWith('/sessions') ? {session_id:'sid',state:'waiting_scan',qr_image:'data:image/png;base64,FAKE',qr_expires_in:180} : {state:'cancelled'}
    return new Response(JSON.stringify(data))
  })
  const Panel = await loadVue(new URL('./CloudBilibiliSourcePanel.vue', import.meta.url))
  const root = mount(t, Panel); await tick()
  assert.equal(calls.filter(([path])=>path.endsWith('/sessions')).length,0)
  assert.match(content(root), /管理员|公共/)
  await nodes(root,'button').find(n=>content(n)==='扫码授权 B 站').props.onClick(); await tick()
  assert.equal(nodes(root,'input').length,0)
  assert.doesNotMatch(content(root), /账号密码|Cookie 导入|手机号验证码/)
  assert.equal(nodes(root,'img').length,1)
  const start = calls.find(([path])=>path===ROOT+'/sessions')
  assert.equal(start[1].headers['X-CSRF-Token'],'fixture')
  assert.deepEqual(JSON.parse(start[1].body),{mode:'qr'})
  await nodes(root,'button').find(n=>content(n)==='取消扫码').props.onClick(); await tick()
  assert.equal(nodes(root,'img').length,0)
  assert.ok(calls.some(([path,options])=>path===ROOT+'/sessions/sid' && options.method==='DELETE'))
})

test('website invalidation discards a late QR response and schedules no polling', async t => {
  configureHttpClient({mode:'cloud'}); t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout']})
  let finish, polls = 0
  t.mock.method(globalThis,'fetch', async path => {
    if(path.endsWith('/csrf')) return new Response(JSON.stringify({csrf_token:'fixture'}))
    if(path.endsWith('/status')) return new Response(JSON.stringify({configured:false}))
    if(path.endsWith('/sessions')) return new Promise(resolve=>{finish=()=>resolve(new Response(JSON.stringify({session_id:'late',state:'waiting_scan',qr_image:'data:image/png;base64,LATE',qr_expires_in:180})))})
    if(path.endsWith('/qr/poll')) polls++
    return new Response(JSON.stringify({state:'cancelled'}))
  })
  const Panel = await loadVue(new URL('./CloudBilibiliSourcePanel.vue', import.meta.url))
  const root = mount(t,Panel); await tick()
  const pending = nodes(root,'button').find(n=>content(n)==='扫码授权 B 站').props.onClick(); await tick()
  invalidateSession(); finish(); await pending; await tick()
  t.mock.timers.tick(10000); await tick()
  assert.equal(nodes(root,'img').length,0); assert.equal(polls,0)
})

test('network failure stops automatic QR retries and offers status recovery', async t => {
  configureHttpClient({mode:'cloud'}); t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout']})
  let polls=0
  t.mock.method(globalThis,'fetch',async path=> {
    if(path.endsWith('/qr/poll')){polls++;throw new Error('network fixture')}
    const data=path.endsWith('/csrf')?{csrf_token:'fixture'}:path.endsWith('/status')?{configured:false}:path.endsWith('/sessions')?{session_id:'sid',state:'waiting_scan',qr_image:'data:image/png;base64,FAKE',qr_expires_in:180}:{state:'complete',account:{configured:true}}
    return new Response(JSON.stringify(data))
  })
  const Panel=await loadVue(new URL('./CloudBilibiliSourcePanel.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  await nodes(root,'button').find(n=>content(n)==='扫码授权 B 站').props.onClick()
  t.mock.timers.tick(3000);await tick()
  t.mock.timers.tick(9000);await tick()
  assert.equal(polls,1)
  await nodes(root,'button').find(n=>content(n)==='检查授权状态').props.onClick();await tick()
  assert.match(content(root),/已在云端加密保存/)
})

test('SESSDATA is the default single secret input and is cleared before sending', async t => {
  documentType(t)
  configureHttpClient({mode:'cloud'}); t.after(()=>configureHttpClient({mode:'local'}))
  let resolveSubmit
  const calls=[]
  t.mock.method(globalThis,'fetch',async (path,options)=> {
    calls.push([path,options])
    if(path.endsWith('/cookie'))return new Promise(resolve=>{resolveSubmit=()=>resolve(new Response(JSON.stringify({state:'complete',account:{configured:true}})))})
    const data=path.endsWith('/csrf')?{csrf_token:'fixture'}:path.endsWith('/status')?{configured:false}:path.endsWith('/sessions')?{session_id:'cookie-sid',mode:'cookie',state:'ready'}:{state:'cancelled'}
    return new Response(JSON.stringify(data))
  })
  const Panel=await loadVue(new URL('./CloudBilibiliSourcePanel.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  assert.equal(nodes(root,'input').length,1)
  const input=nodes(root,'input')[0]
  assert.equal(input.props.type,'password');assert.equal(input.props.autocomplete,'off')
  input.props['onUpdate:modelValue']('SYNTHETIC_SESSDATA');await nextTick()
  const pending=nodes(root,'form')[0].props.onSubmit({preventDefault(){}});await tick()
  assert.equal(input.value,'')
  assert.ok(calls.every(([path])=>!path.includes('SYNTHETIC')))
  const create=calls.find(([path])=>path===ROOT+'/sessions')
  assert.deepEqual(JSON.parse(create[1].body),{mode:'cookie'})
  const submit=calls.find(([path])=>path.endsWith('/cookie'))
  assert.deepEqual(JSON.parse(submit[1].body),{sessdata:'SYNTHETIC_SESSDATA'})
  assert.equal(submit[1].headers['X-CSRF-Token'],'fixture')
  assert.doesNotMatch(content(root),/SYNTHETIC_SESSDATA/)
  resolveSubmit();await pending;await tick()
  assert.equal(input.value,'');assert.match(content(root),/已在云端加密保存/)
})

test('switching authorization mode or invalidating website clears the secret input', async t => {
  documentType(t)
  configureHttpClient({mode:'cloud'}); t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path=>new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'fixture'}:path.endsWith('/sessions')?{session_id:'qr',state:'waiting_scan',qr_image:'data:image/png;base64,FAKE',qr_expires_in:180}:{configured:false})))
  const Panel=await loadVue(new URL('./CloudBilibiliSourcePanel.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  nodes(root,'input')[0].props['onUpdate:modelValue']('SYNTHETIC_SESSDATA');await nextTick()
  await nodes(root,'button').find(n=>content(n)==='扫码授权 B 站').props.onClick();await tick()
  nodes(root,'button').find(n=>content(n)==='使用 SESSDATA').props.onClick();await tick()
  assert.equal(nodes(root,'input')[0].value,'')
  nodes(root,'input')[0].props['onUpdate:modelValue']('SYNTHETIC_AGAIN');await nextTick()
  invalidateSession();await tick()
  assert.equal(nodes(root,'input')[0].value,'')
})

test('cloud cookie path is explicitly allowed while unsupported administrator tools are blocked', async t => {
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  const calls=[]
  t.mock.method(globalThis,'fetch',async(path,options)=>{calls.push(path);return new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'fixture'}:{ok:true}))})
  await requestJson(ROOT+'/sessions/sid/cookie',{method:'POST',body:{sessdata:'SYNTHETIC'}})
  assert.ok(calls.includes(ROOT+'/sessions/sid/cookie'))
  for(const suffix of ['password','captcha','sms/send','cookie/export','collect']) await assert.rejects(requestJson(ROOT+'/sessions/sid/'+suffix,{method:'POST'}),/尚未提供云端接口/)
  assert.ok(!calls.some(path=>path.includes('password')||path.includes('export')))
})

test('failed SESSDATA validation leaves the input empty and previous account visible', async t => {
  documentType(t)
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.method(globalThis,'fetch',async path=> {
    if(path.endsWith('/cookie'))return new Response(JSON.stringify({detail:'原授权已保留',error_code:'INVALID_CREDENTIALS',state:'failed'}),{status:400})
    const data=path.endsWith('/csrf')?{csrf_token:'fixture'}:path.endsWith('/status')?{configured:true,nickname:'原来源账号'}:path.endsWith('/sessions')?{session_id:'cookie',mode:'cookie',state:'ready'}:{state:'cancelled'}
    return new Response(JSON.stringify(data))
  })
  const Panel=await loadVue(new URL('./CloudBilibiliSourcePanel.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  nodes(root,'input')[0].props['onUpdate:modelValue']('SYNTHETIC_BAD');await nextTick()
  await nodes(root,'form')[0].props.onSubmit({preventDefault(){}});await tick()
  assert.equal(nodes(root,'input')[0].value,'')
  assert.match(content(root),/原来源账号.*原授权已保留/)
  assert.doesNotMatch(content(root),/SYNTHETIC_BAD/)
})
