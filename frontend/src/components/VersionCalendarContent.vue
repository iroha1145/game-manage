<script setup>
import { computed } from 'vue'
import CalendarTimelineContent from './CalendarTimelineContent.vue'
import VersionCalendarMetadata from './VersionCalendarMetadata.vue'
import { formatBeijingDateTime, versionCalendarRange } from '../calendar.js'

const props = defineProps({ calendars:{type:Array,default:()=>[]}, snapshots:{type:Object,default:()=>({})}, asOf:{type:Number,required:true}, mode:{type:String,default:'screen'}, selectedId:{type:String,default:null}, emptyTitle:{type:String,default:'暂无活动数据'}, showSourceDetails:{type:Boolean,default:true} })
defineEmits(['select'])
const events = computed(() => props.calendars.flatMap(calendar => calendar.events))
const range = computed(() => versionCalendarRange(events.value, props.asOf))
const dateLabel = range => `${formatBeijingDateTime(range.start).slice(0,10)} — ${formatBeijingDateTime(range.end-1).slice(0,10)}`
</script>
<template>
  <div class="version-calendars" :class="{'image-mode':mode==='image'}">
    <header class="version-summary" data-render-block>
      <p class="version-axis"><strong>活动日期范围</strong><span>{{ range ? dateLabel(range) : '暂无可定位的活动日期' }}</span></p>
    </header>
    <section class="version-window-content">
      <CalendarTimelineContent :events="events" :snapshots="snapshots" :range="range" :as-of="asOf" range-mode="version" :mode="mode" :selected-id="selectedId" :empty-title="emptyTitle" @select="(event,interaction)=>$emit('select',event,interaction)" />
    </section>
    <details v-if="mode !== 'image' && showSourceDetails && calendars.length" class="version-details" data-render-collapsed><summary>数据来源详情</summary><VersionCalendarMetadata :calendars="calendars" /></details>
  </div>
</template>
<style scoped>
.version-calendars { min-width:0; min-height:0; display:flex; flex-direction:column; flex:1; }
.version-details { padding:12px 20px; font-size:12px; color:var(--text-muted); flex-shrink:0; }
.version-details > summary { cursor:pointer; }
.version-summary { flex-shrink:0; padding:0 20px 12px; font-size:12px; color:var(--text-muted); }
.version-axis { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 0; }
.version-axis small { font-size:inherit; }
.version-window-content { display:flex; flex-direction:column; flex:1; min-height:0; }
.image-mode { display:block; }
.image-mode .version-summary { padding:0 0 12px; }
.image-mode .version-details { order:0; padding:12px 0; font-size:14px; }
.image-mode .version-summary { font-size:14px; }
@media(max-width:760px) { .version-summary { padding-left:16px; padding-right:16px; } }
</style>
