import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick,ref,h } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient, invalidateSession, requestJson } from '../http-client.js'
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));await nextTick()}
const ROOT='/api/admin/bilibili-source'
const source={game_id:'wuthering_waves',uid:'123',queue_state:'idle',status:'idle',pages:0,failures:0,history_complete:false}

test('collection is explicit, shares CSRF and observes completion without repeating POST',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout','Date']})
  let row={...source},reads=0
  const calls=[]
  t.mock.method(globalThis,'fetch',async(path,options)=>{
    calls.push([path,options])
    if(path.endsWith('/csrf'))return new Response(JSON.stringify({csrf_token:'fixture'}))
    if(options.method==='POST'){row={...source,queue_state:'queued'};return new Response(JSON.stringify({state:'queued'}))}
    reads++;return new Response(JSON.stringify({sources:[row]}))
  })
  const Panel=await loadVue(new URL('./CloudBilibiliCollectionControls.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  assert.equal(calls.filter(([,o])=>o.method==='POST').length,0)
  assert.match(content(root),/自动.*历史/)
  await nodes(root,'button').find(n=>content(n)==='回补60天').props.onClick();await tick()
  const post=calls.find(([,o])=>o.method==='POST')
  assert.equal(post[0],ROOT+'/wuthering_waves/refresh')
  assert.deepEqual(JSON.parse(post[1].body),{backfill:true})
  assert.equal(post[1].headers['X-CSRF-Token'],'fixture')
  assert.ok(nodes(root,'button').find(n=>content(n)==='采集新动态').props.disabled)
  row={...source,queue_state:'cooldown',status:'ok',last_success:'2026-10-14T12:00:00+00:00',pages:2,history_complete:true,next_retry:Date.now()/1000+30}
  t.mock.timers.tick(2500);await tick()
  assert.match(content(root),/刷新.*资讯/)
  assert.match(content(root),/2.*页|页.*2/)
  assert.ok(nodes(root,'button').find(n=>content(n)==='回补60天').props.disabled)
  t.mock.timers.tick(3600000);await tick()
  const endReads=reads
  t.mock.timers.tick(3600000);await tick()
  assert.equal(reads,endReads)
  assert.equal(calls.filter(([,o])=>o.method==='POST').length,1)
})

test('website invalidation clears source state and discards late status without timers',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout']})
  let release,reads=0
  t.mock.method(globalThis,'fetch',async()=>{reads++;return new Promise(resolve=>{release=()=>resolve(new Response(JSON.stringify({sources:[source]})))})})
  const Panel=await loadVue(new URL('./CloudBilibiliCollectionControls.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  invalidateSession();release();await tick()
  assert.doesNotMatch(content(root),/UID 123/)
  t.mock.timers.tick(100000);await tick()
  assert.equal(reads,1)
})

test('only exact cloud collection routes are allowed and failure retains visible previous state',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  const calls=[]
  t.mock.method(globalThis,'fetch',async(path,options)=>{
    calls.push(path)
    return new Response(JSON.stringify(path.endsWith('/csrf')?{csrf_token:'fixture'}:options.method==='POST'?{detail:'source_busy'}:{sources:[source]}),{status:options.method==='POST'?409:200})
  })
  const Panel=await loadVue(new URL('./CloudBilibiliCollectionControls.vue',import.meta.url))
  const root=mount(t,Panel);await tick()
  await nodes(root,'button').find(n=>content(n)==='采集新动态').props.onClick();await tick()
  assert.match(content(root),/UID 123/)
  assert.match(content(root),/排队|进行中/)
  for(const path of [ROOT+'/status?raw=true',ROOT+'/wuthering_waves/audit',ROOT+'/wuthering_waves/refresh?backfill=true','/api/sources/bilibili'])await assert.rejects(requestJson(path),/尚未提供云端接口/)
  assert.equal(calls.filter(path=>path.includes('audit')||path.includes('?')).length,0)
})

test('fast collection failure retains counts, reports failure and departure stops status reads',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  t.mock.timers.enable({apis:['setTimeout']})
  let row={...source,total:12,article_count:4},reads=0
  t.mock.method(globalThis,'fetch',async(path,options)=>{
    if(path.endsWith('/csrf'))return new Response(JSON.stringify({csrf_token:'fixture'}))
    if(options.method==='POST'){row={...row,status:'error',queue_state:'backoff',failures:1,http_status:412,next_retry:Date.now()/1000+120};return new Response(JSON.stringify({state:'queued'}))}
    reads++;return new Response(JSON.stringify({sources:[row]}))
  })
  const Panel=await loadVue(new URL('./CloudBilibiliCollectionControls.vue',import.meta.url)),visible=ref(true)
  const root=mount(t,{setup:()=>()=>visible.value?h(Panel):null});await tick()
  await nodes(root,'button').find(n=>content(n)==='采集新动态').props.onClick();await tick()
  assert.match(content(root),/采集失败.*保留/)
  assert.match(content(root),/已保存 12 条/)
  assert.match(content(root),/HTTP 412/)
  visible.value=false;await tick()
  const count=reads;t.mock.timers.tick(100000);await tick()
  assert.equal(reads,count)
})
