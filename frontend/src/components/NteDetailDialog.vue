<script setup>
import { useId } from 'vue'
import { useDialog } from '../use-dialog.js'
defineProps({title:{type:String,required:true}})
const emit=defineEmits(['close']), titleId=`nte-detail-${useId()}`
const { dialog, closing, requestClose, backdropDown, backdropClick, animationEnded } = useDialog(() => emit('close'))
</script>
<template>
  <dialog ref="dialog" class="nte-dialog t-dialog" :data-closing="closing ? '' : undefined" aria-modal="true" :aria-labelledby="titleId" @cancel.prevent="requestClose" @pointerdown="backdropDown" @click="backdropClick" @animationend="animationEnded">
    <header class="nte-dialog-head"><div><h2 :id="titleId">{{ title }}</h2></div><button type="button" autofocus @click="requestClose">关闭详情</button></header>
    <div class="nte-dialog-body"><slot /></div>
  </dialog>
</template>
<style scoped>
.nte-dialog{position:fixed;inset:0;margin:auto;width:min(1200px,calc(100vw - 40px));max-width:none;max-height:calc(100dvh - 40px);padding:0;border:1px solid var(--border);border-radius:var(--radius-card);background:var(--bg);color:var(--text);box-shadow:var(--popover-shadow)}
.nte-dialog[open]{display:flex;flex-direction:column}
.nte-dialog::backdrop{background:var(--scrim)}
.nte-dialog-head{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:16px 24px;border-bottom:1px solid var(--border);flex-shrink:0}
.nte-dialog-head h2{font-size:18px;line-height:28px;font-weight:500}
.nte-dialog-head button{min-height:32px;padding:5px 12px;background:var(--card-bg);color:var(--text-body);border:1px solid var(--border);border-radius:var(--radius-control);font-size:13px;font-weight:500;line-height:20px;cursor:pointer}
.nte-dialog-body{padding:20px 24px 24px;overflow-y:auto;overscroll-behavior:contain;min-height:0}
.nte-dialog-body :deep(.guides-layout){grid-template-columns:170px minmax(0,1fr)}
@media(max-width:650px){.nte-dialog{width:calc(100vw - 16px);max-height:calc(100dvh - 16px)}.nte-dialog-head,.nte-dialog-body{padding:15px}.nte-dialog-body :deep(.guides-layout){grid-template-columns:minmax(0,1fr)}}
</style>
