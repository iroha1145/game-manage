<script setup>
import { useId } from 'vue'
import { useDialog } from '../use-dialog.js'
import AppIcon from './AppIcon.vue'
defineProps({title:{type:String,required:true}})
const emit=defineEmits(['close']), titleId=`nte-detail-${useId()}`
const { dialog, closing, requestClose, backdropDown, backdropClick, animationEnded } = useDialog(() => emit('close'))
</script>
<template>
  <dialog ref="dialog" class="nte-dialog t-dialog sheet-dialog" :data-closing="closing ? '' : undefined" aria-modal="true" :aria-labelledby="titleId" @cancel.prevent="requestClose" @pointerdown="backdropDown" @click="backdropClick" @animationend="animationEnded">
    <header class="nte-dialog-head"><div><h2 :id="titleId">{{ title }}</h2></div><button type="button" class="icon-button" title="关闭详情" autofocus @click="requestClose"><AppIcon name="close" :size="16" /><span class="sr-only">关闭详情</span></button></header>
    <div class="nte-dialog-body"><slot /></div>
  </dialog>
</template>
<style scoped>
/* Placement, size, radius, backdrop and the slide-in come from .sheet-dialog; this is the inside.
   The panels in the slot are white cards on the page, so inside the white sheet they drop their
   frame and sit apart by space instead. */
.nte-dialog{--sheet-width:720px}
.nte-dialog-head{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 18px 14px 28px;background:var(--card-bg);border-bottom:1px solid var(--border)}
.nte-dialog-head h2{font-size:21px;line-height:28px;font-weight:600;letter-spacing:-.03em}
.nte-dialog-body{padding:22px 28px 28px}
.nte-dialog-body :deep(.cap-card){padding:0;border:0;border-radius:0;background:none;box-shadow:none}
/* The header above already names the panel, so a panel's own title steps aside (bot images, which have no
   sheet, keep it); its chips, notes and update time stay. */
.nte-dialog-body :deep(.cap-title){font-size:0}
.nte-dialog-body :deep(.cap-title > h3){position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.nte-dialog-body :deep(.guides-layout){grid-template-columns:minmax(0,1fr)}
@media(max-width:720px){.nte-dialog-head{padding:14px 14px 12px 20px}.nte-dialog-head h2{font-size:19px;line-height:26px}.nte-dialog-body{padding:18px 16px 24px}}
</style>
