<script setup>
import { computed } from 'vue'
import { characterIcon, namedIcon, safeWuwaIcon } from '../wuwa-icons.js'
import WuwaIcon from './WuwaIcon.vue'

const props = defineProps({ role: { type: Object, required: true }, roleNames: { type: Object, default: () => ({}) } })
const name = computed(() => props.role.role_name || props.role.name || props.roleNames[props.role.role_id] || (props.role.role_id != null ? `角色 ${props.role.role_id}` : '未知角色'))
const icon = computed(() => safeWuwaIcon(props.role.role_icon_url) || characterIcon(props.role.role_id) || namedIcon('roles', name.value))
</script>

<template>
  <span class="combat-role">
    <WuwaIcon v-if="icon" :src="icon" :name="name" size="small" />
    <span>{{ name }}</span><small v-if="role.role_level != null">Lv.{{ role.role_level }}</small>
  </span>
</template>

<style scoped>
.combat-role { display: inline-flex; align-items: center; gap: 6px; min-width: 0; max-width: 100%; }
.combat-role > span:not(.wuwa-item-icon) { overflow-wrap: anywhere; }
.combat-role > small { color: var(--text-muted); white-space: nowrap; }
</style>
