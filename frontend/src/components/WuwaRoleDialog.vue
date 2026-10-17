<script setup>
import { computed, useId } from 'vue'
import { useDialog } from '../use-dialog.js'
// width: the sheet's reading width in px (--sheet-width); the shared default suits short pages.
const props = defineProps({ title: { type: String, required: true }, width: { type: Number, default: 0 } })
const headingId = `wuwa-dialog-${useId()}`
const emit = defineEmits(['close'])
const { dialog, closing, requestClose, backdropDown, backdropClick, animationEnded } = useDialog(() => emit('close'))
const sheetStyle = computed(() => (props.width ? { '--sheet-width': `${props.width}px` } : undefined))
</script>

<template>
  <dialog ref="dialog" class="wuwa-role-dialog t-dialog sheet-dialog" :style="sheetStyle" :data-closing="closing ? '' : undefined" aria-modal="true" :aria-labelledby="headingId" @cancel.prevent="requestClose" @pointerdown="backdropDown" @click="backdropClick" @animationend="animationEnded">
    <header class="role-dialog-heading">
      <div><h2 :id="headingId">{{ title }}</h2></div>
      <button type="button" class="ui-button small-button" autofocus @click="requestClose">关闭详情</button>
    </header>
    <div class="role-dialog-body"><slot /></div>
  </dialog>
</template>

<style scoped>
/* The sheet itself is the shared .sheet-dialog (style.css); this is what is inside it.
   The heading stays put while the page scrolls under it. */
.role-dialog-heading { position: sticky; top: 0; z-index: 3; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 24px 14px; border-bottom: 1px solid var(--border); background: var(--card-bg); }
.role-dialog-heading h2 { margin: 0; font-size: 20px; line-height: 28px; font-weight: 600; letter-spacing: -.03em; }
.role-dialog-body { padding: 20px 24px 28px; }
/* The dialog is the card: the page it hosts loses its own frame. Cards a page
   draws for itself (a bento inside) keep theirs. */
.role-dialog-body > :deep(:is(.wuwa-panel, .cap-card)),
.role-dialog-body > :deep(.wuwa-board > .wuwa-panel) { padding: 0; border: 0; border-radius: 0; background: none; box-shadow: none; }
.role-dialog-body :deep(.wuwa-panel .cap-title > :where(h2, h3)) { font-size: 16px; line-height: 24px; }
/* The sheet's own heading already names the page: a page that opens with the same title alone
   drops it, and a record page keeps just its status line. */
.role-dialog-body :deep(.cap-title:has(> h2:only-child)),
.role-dialog-body :deep(.wuwa-board > .wuwa-panel > .cap-title > h2) { display: none; }
@media (max-width: 720px) {
  .role-dialog-heading { padding: 14px 16px 12px; }
  .role-dialog-heading h2 { font-size: 18px; line-height: 26px; }
  .role-dialog-body { padding: 16px 16px 24px; }
}
</style>
