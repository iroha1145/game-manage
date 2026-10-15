import test from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { nextTick } from 'vue'
import { loadVue,mount,nodes,content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
const App=await loadVue(new URL('../CloudApp.vue',import.meta.url))
const tick=async()=>{await new Promise(r=>setImmediate(r));await nextTick()}
test('local hash navigation restores bookmarked game and calendar filter, mobile shell exposes drawer',async t=>{
 const browser=new Window({url:'http://fixture/#/game/nte',width:390});const old=globalThis.window,oldDocument=globalThis.document;globalThis.window=browser;globalThis.document=browser.document;t.after(()=>{globalThis.window=old;globalThis.document=oldDocument;browser.happyDOM.abort()})
 configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
 t.mock.method(globalThis,'fetch',async path=>new Response(JSON.stringify(path==='/api/identity/me'?{user_id:'u'}:path==='/api/accounts'?{accounts:[{account_id:'a',provider:'tajiduo',state:'active',capabilities:['account'],roles:[{role_id:'r',display_name:'角色甲'}]}]}:path.endsWith('/csrf')?{csrf_token:'fixture'}:{payload:[],state:'ok'})))
 const root=mount(t,App);await tick();await tick();assert.ok(nodes(root,'button').some(n=>content(n)==='概览'))
 const toggle=nodes(root,'button').find(n=>n.props['aria-controls']==='workspace-sidebar'),aside=nodes(root,'aside')[0],main=nodes(root,'main')[0]
 assert.ok(toggle);let focused='';const first={focus(){focused='first'}},last={focus(){focused='last'}}
 aside.querySelector=()=>first;aside.querySelectorAll=()=>[first,last];toggle.focus=()=>{focused='toggle'};main.focus=()=>{focused='main'}
 await toggle.props.onClick();await tick();assert.equal(toggle.props['aria-expanded'],true);assert.equal(focused,'first')
 browser.dispatchEvent(new browser.KeyboardEvent('keydown',{key:'Escape'}));await tick();assert.equal(toggle.props['aria-expanded'],false);assert.equal(focused,'toggle')
 browser.location.hash='/calendar?game=nte';browser.dispatchEvent(new browser.Event('hashchange'));await tick();await tick()
 assert.ok(nodes(root,'button').some(n=>n.props['aria-label']==='筛选游戏'&&content(n).includes('异环')))
})
