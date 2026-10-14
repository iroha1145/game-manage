import test from 'node:test'
import assert from 'node:assert/strict'
import { configureHttpClient } from './http-client.js'
import { registerSite } from './identity-api.js'

for (const [code,expected] of [
  ['invalid_username',/用户名.*3.*64.*英文字母/],
  ['invalid_password',/密码.*12.*128/],
  ['invalid_invite',/邀请码不可用/],
  ['registration_unavailable',/注册信息.*无法使用/],
]) {
  test(`registration maps allowlisted ${code} to a safe actionable message`,async t=>{
    configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
    const calls=[]
    t.mock.method(globalThis,'fetch',async(url,options)=>{
      calls.push(url)
      return new Response(JSON.stringify(url.endsWith('/csrf')?{csrf_token:'fixture-csrf'}:{detail:code}),
        {status:url.endsWith('/csrf')?200:400})
    })
    await assert.rejects(registerSite({username:'friend',password:'Fixture-password-123',invite:'fixture-invite'}),error=>{
      assert.match(error.message,expected)
      assert.doesNotMatch(error.message,/用户名已存在|已注册|fixture-invite|Fixture-password/)
      assert.equal(error.status,400)
      return true
    })
    assert.deepEqual(calls,['/api/identity/csrf','/api/identity/register'])
  })
}

test('registration never displays unknown backend detail or weakens rate-limit feedback',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  let status=400,detail='private database exception token'
  t.mock.method(globalThis,'fetch',async url=>new Response(JSON.stringify(url.endsWith('/csrf')?{csrf_token:'fixture-csrf'}:{detail}),
    {status:url.endsWith('/csrf')?200:status}))
  const body={username:'friend',password:'Fixture-password-123',invite:'fixture-invite'}
  await assert.rejects(registerSite(body),error=>error.message==='请求失败，请稍后重试'&&!error.message.includes('private'))
  status=429;detail='rate_limited'
  await assert.rejects(registerSite(body),error=>error.status===429&&error.message==='请求过于频繁，请稍后重试')
})

test('invalid registration username explains the rule before CSRF or registration I/O',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  let invalid=true
  t.mock.method(globalThis,'fetch',async url=>{
    if(invalid)assert.fail('Invalid username must not submit an invite')
    return new Response(JSON.stringify(url.endsWith('/csrf')?{csrf_token:'fixture-csrf'}:{user_id:'fixture-user'}))
  })
  for (const username of ['朋友账号','ab','a'.repeat(65),'friend name']) {
    await assert.rejects(registerSite({username,password:'Fixture-password-123',invite:'fixture-invite'}),error=>{
      assert.match(error.message,/用户名.*3.*64.*英文字母/)
      assert.equal(error.code,'invalid_username')
      return true
    })
  }
  invalid=false
  for (const username of ['abc','Friend_1.test-name','a'.repeat(64)]) {
    assert.equal((await registerSite({username,password:'Fixture-password-123',invite:'fixture-invite'})).user_id,'fixture-user')
  }
})

test('registration error mapping excludes inherited object properties',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  let code='toString'
  t.mock.method(globalThis,'fetch',async url=>new Response(JSON.stringify(url.endsWith('/csrf')?{csrf_token:'fixture-csrf'}:{error_code:code}),
    {status:url.endsWith('/csrf')?200:400}))
  for (code of ['toString','constructor','__proto__']) {
    await assert.rejects(registerSite({username:'friend',password:'Fixture-password-123',invite:'fixture-invite'}),error=>{
      assert.equal(error.message,'请求失败，请稍后重试')
      return true
    })
  }
})
