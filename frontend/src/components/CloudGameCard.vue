<script setup>
import { computed, provide } from 'vue'
import { collectionState } from '../snapshot-state.js'
import { accountCapabilities } from '../accounts-api.js'
import GameCard from './GameCard.vue'
import CloudSnapshotStatus from './CloudSnapshotStatus.vue'
const props = defineProps({ account: {type:Object,required:true}, role: {type:String,required:true}, userId: {type:String,default:''}, snapshots: {type:Object,default:()=>({})}, readStates: {type:Object,default:()=>({})}, sources: Object, sourceSnapshots: {type:Object,default:()=>({})}, publicSnapshots: {type:Object,default:()=>({})}, refreshing: Boolean, isAdmin: Boolean, section: {type:String,default:'overview'} })
const emit = defineEmits(['calendar','refresh'])
provide('cloudPermissions', computed(()=>({isAdmin:props.isAdmin})))
const endfield = computed(() => ['hypergryph', 'skland'].includes(props.account.provider))
const caps = computed(() => endfield.value && Object.keys(props.sources || {}).length ? [...new Set(Object.values(props.sources || {}).flatMap(source => accountCapabilities(source.account)))] : accountCapabilities(props.account))
const combined = computed(()=>({...Object.fromEntries(caps.value.map(cap => [cap, {
  ...props.snapshots[cap],
  reading: props.readStates[cap]?.status === 'loading' || (!props.snapshots[cap] && !props.readStates[cap]),
  readError: props.readStates[cap]?.status === 'error' ? props.readStates[cap].error : '',
}])),...props.publicSnapshots}))
const game = computed(()=>({game_id:({kuro:'wuthering_waves',tajiduo:'nte',hypergryph:'endfield',skland:'endfield'})[props.account.provider], display_name:({kuro:'鸣潮',tajiduo:'异环',hypergryph:'终末地',skland:'终末地'})[props.account.provider], capabilities:[...caps.value,'news','events'],credentials_configured:props.account.state!=='revoked'}))
const collection = computed(()=>Object.entries(combined.value).map(([cap,snap])=>({game_id:game.value.game_id,capability:cap,state:collectionState(snap)==='failed'?'error':snap?.state || 'never',last_success_at:snap?.fetched_at,error:snap?.error || snap?.poll_status?.error})))
const sourceLabels = { hypergryph_account: '鹰角角色资料', skland_account: '森空岛档案' }
const statusSnapshots = computed(() => {
  if (!endfield.value || !Object.keys(props.sources || {}).length) return combined.value
  const values = { ...props.publicSnapshots }
  for (const [provider, snapshots] of Object.entries(props.sourceSnapshots)) for (const [cap, snapshot] of Object.entries(snapshots)) values[cap === 'account' ? `${provider}_account` : cap] = snapshot
  return values
})
const statusCaps = computed(() => endfield.value && Object.keys(props.sources || {}).length ? [...Object.entries(props.sources || {}).flatMap(([provider, source]) => accountCapabilities(source.account).map(cap => cap === 'account' ? `${provider}_account` : cap)), 'news', 'events'] : [...caps.value, 'news', 'events'])
const scope = computed(()=>({user_id:props.userId,account_id:props.account.account_id,role_id:props.role,provider:props.account.provider}))
</script>
<template>
  <p v-if="!caps.length" class="cap-card">此授权尚未提供云端数据能力，请到「账号与授权」检查。</p>
  <template v-else><GameCard :game="game" :collection-status="collection" :external-snapshots="combined" :external-refreshing="refreshing" :cloud-account="account" :cloud-role="role" :cloud-sources="sources" :source-snapshots="sourceSnapshots" :cloud-scope="scope" :is-admin="isAdmin" :initial-section="section" @calendar="emit('calendar')" @refresh="emit('refresh')" /><CloudSnapshotStatus :snapshots="statusSnapshots" :capabilities="statusCaps" :labels="sourceLabels" /></template>
</template>
