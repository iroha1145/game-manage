<script setup>
import { isCloudMode } from './http-client.js'
import LocalApp from './LocalApp.vue'
import CloudApp from './CloudApp.vue'
const cloudMode = isCloudMode()
</script>
<template><CloudApp v-if="cloudMode" /><LocalApp v-else /></template>
