<script setup>
import { computed } from 'vue'
import { tokenizeGuide } from '../wuwa-icons.js'
import WuwaIcon from './WuwaIcon.vue'
import {guideAtoms} from '../qq-image/guide-presentation.js'
const props = defineProps({ text: { type: String, default: '' }, sectionKey: { type: String, required: true }, characterId: { type: [String, Number], required: true },imageMode:Boolean })
const tokens = computed(() => {const raw=tokenizeGuide(props.text, props.sectionKey, props.characterId);return props.imageMode?guideAtoms(raw):raw})
</script>
<template>
  <div class="guide-visual-flow" :class="`visual-${sectionKey}`">
    <template v-for="(token, i) in tokens" :key="i">
      <span v-if="token.entity" class="guide-atom"><span class="guide-entity" :title="token.name">
        <WuwaIcon :src="token.icon" :name="token.name" :size="sectionKey === 'echo_stats' ? 'small' : 'normal'" />
        <span>{{ token.text }}</span>
      </span><span v-if="token.trailing" class="guide-punctuation">{{token.trailing}}</span></span>
      <span v-else class="guide-connector">{{ token.text }}</span>
    </template>
  </div>
</template>
<style scoped>
.guide-visual-flow { line-height: 2; padding: 12px 0; color: var(--text); overflow-wrap: anywhere; }
.guide-entity { display: inline-flex; flex-direction: column; align-items: center; justify-content: center; vertical-align: middle; gap: 4px; padding: 6px 8px; margin: 3px; border-radius: var(--radius-well); background: var(--card-bg); font-size: 12px; line-height: 1.5; text-align: center; max-width: 126px; }
.guide-connector { font-size: 13px; color: var(--text-muted); white-space: pre-wrap; }
.visual-echo_stats .guide-entity { flex-direction: row; padding: 3px 8px 3px 4px; }
.visual-skill_priority .guide-entity { min-width: 72px; }
@media (max-width:640px) { .guide-entity { max-width: 112px; margin: 2px; padding: 4px; } }
</style>
