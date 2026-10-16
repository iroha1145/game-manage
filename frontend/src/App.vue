<script setup>
import { defineAsyncComponent } from 'vue'
import { isCloudMode } from './http-client.js'
// A deployment runs in one mode for its whole life, so load only that interface.
const Interface = defineAsyncComponent(() => isCloudMode() ? import('./CloudApp.vue') : import('./LocalApp.vue'))
</script>
<template><Interface /></template>
