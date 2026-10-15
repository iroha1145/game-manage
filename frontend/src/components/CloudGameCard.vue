<script setup>
import { computed, provide } from 'vue'
import { collectionState } from '../snapshot-state.js'
import { accountCapabilities } from '../accounts-api.js'
import GameCard from './GameCard.vue'
import CloudSnapshotStatus from './CloudSnapshotStatus.vue'
const props = defineProps({ account: {type:Object,required:true}, role: {type:String,required:true}, userId: {type:String,default:''}, snapshots: {type:Object,default:()=>({})}, publicSnapshots: {type:Object,default:()=>({})}, refreshing: Boolean, isAdmin: Boolean })
const emit = defineEmits(['calendar','refresh'])
provide('cloudPermissions', computed(()=>({isAdmin:props.isAdmin})))
const caps = computed(()=>accountCapabilities(props.account))
const combined = computed(()=>({...props.snapshots,...props.publicSnapshots}))
const game = computed(()=>({game_id:({kuro:'wuthering_waves',tajiduo:'nte',hypergryph:'endfield',skland:'endfield'})[props.account.provider], display_name:({kuro:'鸣潮',tajiduo:'异环',hypergryph:'终末地',skland:'终末地'})[props.account.provider], capabilities:[...caps.value,'news','events'],credentials_configured:props.account.state!=='revoked'}))
const collection = computed(()=>Object.entries(combined.value).map(([cap,snap])=>({game_id:game.value.game_id,capability:cap,state:collectionState(snap)==='failed'?'error':snap?.state || 'never',last_success_at:snap?.fetched_at,error:snap?.error || snap?.poll_status?.error})))
const scope = computed(()=>({user_id:props.userId,account_id:props.account.account_id,role_id:props.role,provider:props.account.provider}))
</script>
<template>
  <p v-if="!caps.length" class="cap-card">此授权尚未提供云端数据能力，请在账号设置检查授权状态。</p>
  <template v-else><GameCard :game="game" :show-source-status="false" :collection-status="collection" :external-snapshots="combined" :external-refreshing="refreshing" :cloud-account="account" :cloud-role="role" :cloud-scope="scope" :is-admin="isAdmin" initial-section="overview" @calendar="emit('calendar')" @refresh="emit('refresh')" /><CloudSnapshotStatus :snapshots="combined" :capabilities="[...caps,'news','events']" /></template>
</template>
