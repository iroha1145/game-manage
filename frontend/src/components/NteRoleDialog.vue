<script setup>
import { ref,watch } from 'vue'
import NteDetailDialog from './NteDetailDialog.vue'
import NteRoleDetail from './NteRoleDetail.vue'
import NteGuides from './NteGuides.vue'
import { roleId } from '../nte-roles.js'
const props=defineProps({role:Object,roles:{type:Array,default:()=>[]},accountId:{type:[String,Object],default:''},initialTab:{type:String,default:'panel'},characterId:{type:String,default:''},canMaintain:{type:Boolean,default:true}})
const emit=defineEmits(['close','role'])
const tab=ref(props.role?props.initialTab:'guide')
watch(()=>[props.role,props.initialTab],()=>{tab.value=props.role?props.initialTab:'guide'})
</script>
<template>
 <NteDetailDialog :title="role?.name || '角色攻略'" @close="emit('close')">
  <nav v-if="role" class="segmented" aria-label="角色详情分区"><button type="button" :aria-pressed="tab==='panel'" @click="tab='panel'">本人面板</button><button type="button" :aria-pressed="tab==='guide'" @click="tab='guide'">培养攻略</button></nav>
  <template v-if="role && tab==='panel'"><p>Lv{{ role.level ?? '未知' }} · 觉醒 {{ role.awaken_level ?? '未知' }} · 混频 {{ role.mix_level ?? '未知' }}</p><NteRoleDetail :role="role" :account-id="accountId" /></template>
  <NteGuides v-else :roles="roles" :character-id="role ? roleId(role) : characterId" :can-maintain="canMaintain" @role="emit('role',$event);tab='panel'" />
 </NteDetailDialog>
</template>
