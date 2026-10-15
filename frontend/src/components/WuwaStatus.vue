<script setup>
import { stamp } from '../wuwa-display.js'
import { friendlyDataError } from '../cloud-display.js'
import { inject, unref } from 'vue'
const imageMode=inject('wuwaImageMode',false)
defineProps({ snap: { default: null } })
</script>
<template>
  <!-- Header meta: sits on a card's title line (margin-left:auto in wuwa.css). -->
  <span class="wuwa-status">
    <span v-if="!unref(imageMode) && (snap?.stale || snap?.state === 'stale')" class="badge badge-stale"
      >旧数据</span
    ><span v-if="snap?.fetched_at"
      >更新于 {{ stamp(snap.fetched_at) }}</span
    ><span v-else>尚未更新</span
    ><span v-if="snap?.error" class="badge badge-danger wuwa-status-error" role="status">{{
      friendlyDataError(snap.error,snap?.state)
    }}</span>
  </span>
</template>
