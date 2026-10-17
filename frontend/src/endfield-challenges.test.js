import test from 'node:test'
import assert from 'node:assert/strict'
import { challengeReport, challengeEnvelope, retainedChallenge, stageStates } from './endfield-challenges.js'
const fetched_at='2026-10-15T01:02:00Z'
test('challenge projection distinguishes uncollected, unsupported, empty and wrong category',()=>{
 assert.equal(challengeReport({kind:'war',records:[]},'war').available,false)
 assert.equal(challengeReport({kind:'war',fetched_at,records:[]},'war').summary.listed_count,0)
 assert.equal(challengeReport({kind:'war',supported:false},'war').supported,false)
 assert.equal(challengeReport({kind:'war',fetched_at,records:[{name:'other'}]},'crisis').available,false)
 assert.equal(challengeReport({kind:'war',fetched_at,report:{schema_version:1,kind:'crisis'}},'war').available,false)
})
test('legacy projection preserves zero, false, strings and unknown without inventing maximums',()=>{
 const value={kind:'war',fetched_at,records:[{name:'赛季',stars:'0',weeks:[{stars:0,groups:[{name:'组',star:0,normalDungeon:{name:'普通',isPass:false},hardDungeon:{name:'困难'}}]}]}],summary:{honors:[{name:'荣誉',star:0,first_pass_at:fetched_at}]}}
 const report=challengeReport(value,'war'), group=report.records[0].weeks[0].groups[0]
 assert.equal(report.records[0].stars,0);assert.equal(group.stars,0);assert.equal(group.stages[0].passed,false);assert.equal(group.stages[1].passed,null)
 assert.equal(report.honors[0].stars,0);assert.equal(report.honors[0].first_pass_at,fetched_at)
 const crisis=challengeReport({kind:'crisis',fetched_at,records:[{isPass:false,score:0,grade:'A'}],summary:{highest:0,challenge_count:0}},'crisis')
 assert.equal(crisis.records[0].result,0);assert.equal(crisis.records[0].passed,false);assert.equal(crisis.summary.highest,0)
})
test('report is authoritative and outer retained failure keeps old observation time',()=>{
 const report={schema_version:1,kind:'monument',available:true,supported:true,fetched_at,records:[{name:'报告',groups:[]}],summary:{listed_count:1}}
 const old={payload:{kind:'monument',report,stale:false},fetched_at,stale:false}
 const result=challengeReport(challengeEnvelope(retainedChallenge(old,'失败')),'monument')
 assert.equal(result.records[0].name,'报告');assert.equal(result.stale,true);assert.equal(result.fetched_at,fetched_at);assert.equal(old.stale,false)
})

test('stage states count cleared, open and unobserved stages without treating missing as open', () => {
 const groups=[{stages:[{passed:true},{passed:false},{passed:null}]},{stages:[{passed:true}]},{}]
 assert.deepEqual(stageStates(groups),{passed:2,failed:1,unknown:1})
 assert.deepEqual(stageStates(undefined),{passed:0,failed:0,unknown:0})
})
