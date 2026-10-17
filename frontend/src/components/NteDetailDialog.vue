<script setup>
import { useId } from 'vue'
import { useDialog } from '../use-dialog.js'
import AppIcon from './AppIcon.vue'
defineProps({title:{type:String,required:true}})
const emit=defineEmits(['close']), titleId=`nte-detail-${useId()}`
const { dialog, closing, requestClose, backdropDown, backdropClick, animationEnded } = useDialog(() => emit('close'))
</script>
<template>
  <dialog ref="dialog" class="nte-dialog t-dialog" :data-closing="closing ? '' : undefined" aria-modal="true" :aria-labelledby="titleId" @cancel.prevent="requestClose" @pointerdown="backdropDown" @click="backdropClick" @animationend="animationEnded">
    <header class="nte-dialog-head"><div><h2 :id="titleId">{{ title }}</h2></div><button type="button" class="ui-button small-button" autofocus @click="requestClose"><AppIcon name="close" :size="14" />关闭详情</button></header>
    <div class="nte-dialog-body"><slot /></div>
  </dialog>
</template>
<style scoped>
/* A rounded sheet on the grey canvas: the panels inside are white cards, and
   the header is frosted glass that the content slides under. */
.nte-dialog{position:fixed;inset:0;margin:auto;width:min(1200px,calc(100vw - 40px));max-width:none;max-height:calc(100dvh - 40px);padding:0;overflow-y:auto;overscroll-behavior:contain;border:1px solid var(--glass-border);border-radius:var(--radius-shell);background:var(--bg);color:var(--text);box-shadow:var(--popover-shadow)}
.nte-dialog::backdrop{background:var(--scrim);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.nte-dialog-head{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:20px;padding:14px 20px 14px 28px;background:var(--glass-strong);-webkit-backdrop-filter:var(--glass-filter);backdrop-filter:var(--glass-filter);box-shadow:var(--glass-edge),0 1px 0 var(--border)}
.nte-dialog-head h2{font-size:18px;line-height:28px;font-weight:600;letter-spacing:-.01em}
.nte-dialog-body{padding:20px 24px 28px}
.nte-dialog-body :deep(.guides-layout){grid-template-columns:minmax(0,1fr)}
@media(max-width:650px){.nte-dialog{width:calc(100vw - 16px);max-height:calc(100dvh - 16px);border-radius:24px}.nte-dialog-head{padding:12px 14px 12px 18px}.nte-dialog-body{padding:14px 14px 20px}}
</style>
