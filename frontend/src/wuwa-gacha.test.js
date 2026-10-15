import test from 'node:test'
import assert from 'node:assert/strict'
import { pityText, aggregateKind } from './wuwa-gacha.js'
test('unknown, exact zero and lower bound remain distinct', () => {
  assert.equal(pityText({status:'unknown',count:0}), '当前垫抽未知')
  assert.equal(pityText({status:'exact',count:0}), '当前垫抽 0')
  assert.equal(pityText({status:'lower_bound',count:2}), '当前垫抽至少 2')
  assert.equal(aggregateKind({kind:'current_count'}), '来源自报当前垫抽')
})
