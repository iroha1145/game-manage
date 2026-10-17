import test from 'node:test'
import assert from 'node:assert/strict'
import { getAccountSnapshot } from './accounts-api.js'
import { configureHttpClient } from './http-client.js'

test('snapshot API honors an optional deadline and leaves the three argument call compatible', async t => {
  t.mock.timers.enable({apis:['setTimeout','Date']})
  configureHttpClient({mode:'cloud'}); t.after(()=>configureHttpClient({mode:'local'}))
  let pending=false, outcome
  t.mock.method(globalThis,'fetch',async (_path,options)=>{
    if(!pending) return new Response(JSON.stringify({state:'ok',payload:[]}))
    return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}))
  })
  assert.deepEqual((await getAccountSnapshot('a','r','roles')).payload,[])
  pending=true
  getAccountSnapshot('a','r','roles',{timeoutMs:50}).catch(error=>{outcome=error})
  t.mock.timers.tick(50)
  for(let i=0;i<12;i++) await Promise.resolve()
  assert.equal(outcome?.name,'RequestTimeoutError')
})
