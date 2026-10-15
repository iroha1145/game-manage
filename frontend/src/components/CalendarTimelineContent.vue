<script setup>
import { computed } from 'vue'
import GameIcon from './GameIcon.vue'
import { beijingDayStart, eventGeometry, eventStatus, groupCalendarEvents } from '../calendar.js'
import { gameStyle } from '../dashboard.js'
const props = defineProps({ events:{type:Array,default:()=>[]}, range:{type:Object,default:null}, asOf:{type:Number,required:true}, rangeMode:{type:String,default:'rolling'}, mode:{type:String,default:'screen'}, selectedId:{type:String,default:null}, emptyTitle:{type:String,default:'暂无活动数据'}, showUnplaced:{type:Boolean,default:true} })
const emit = defineEmits(['select'])
const today = computed(() => beijingDayStart(props.asOf))
const todayPosition = computed(() => props.range ? (props.asOf-props.range.start)/(props.range.end-props.range.start)*100 : 0)
const todayVisible = computed(() => props.range && props.asOf>=props.range.start && props.asOf<props.range.end)
const events = computed(() => props.events.map(event => {
  const geometry = eventGeometry(event, props.range || {start:props.asOf,end:props.asOf+86400000})
  const status = eventStatus(event,props.asOf)
  let elapsed=null, remainingDays=null
  if (geometry.kind==='range' && status==='进行中' && props.range) {
    const start=Math.max(geometry.start,props.range.start), end=Math.min(geometry.end,props.range.end)
    if (end>start) elapsed=Math.min(100,Math.max(0,(props.asOf-start)/(end-start)*100))
    remainingDays=Math.max(0,Math.ceil((geometry.end-props.asOf)/86400000))
  }
  return {...event,geometry,status,elapsed,remainingDays}
}))
const groups = computed(() => groupCalendarEvents(events.value.filter(event => event.geometry.visible)))
const undated = computed(() => props.showUnplaced ? events.value.filter(event => event.geometry.kind==='undated') : [])
const invalid = computed(() => props.showUnplaced ? events.value.filter(event => event.geometry.kind==='invalid') : [])
const gameAccent = id => gameStyle(id==='lol' ? 'league_of_legends' : id).color
const barStyle = event => ({left:event.geometry.left+'%',width:event.geometry.kind==='range' ? event.geometry.width+'%' : undefined})
function stateLabel(event) {
  const state=event.status==='更新后开放' && event.start_precision!=='relative' ? '时刻待定' : event.status
  return state + (event.start_estimated ? ' · 预计' : event.geometry.approximateStart && ['未开始','进行中'].includes(state) ? ' · 时刻未知' : '')
}
const eventDescription = event => [event.name||'未命名活动',event.gameName,event.category,stateLabel(event),event.remainingDays != null ? `剩 ${event.remainingDays} 天` : ''].filter(Boolean).join(' · ')
function selectEvent(event, interaction) { if (props.mode!=='image') emit('select',event,interaction) }
</script>
<template>
  <div class="calendar-content" :class="{ 'image-mode': mode === 'image' }">
<div v-if="range" class="timeline-scroll" :tabindex="mode === 'image' ? undefined : 0" role="region" aria-label="活动日期横轴，可横向和纵向滚动" :style="{ '--day-count': range.days.length, '--timeline-min': `${184 + range.days.length * (rangeMode === 'fortnight' ? 39 : 26)}px` }">
        <div :key="range.start" class="timeline-canvas t-panel">
          <div class="timeline-header" data-render-block><div class="timeline-label header-label"><span>游戏</span><small>{{ rangeMode === 'month' ? '当月时间轴' : rangeMode === 'rolling' ? '近 30 天时间轴' : rangeMode === 'version' ? '版本活动时间轴' : '14 天时间轴' }}</small></div><div class="date-track"><div v-for="day in range.days" :key="day.timestamp" class="date-cell" :class="{ weekend: day.weekend, 'is-today': day.timestamp === today, 'is-month-start': day.day === 1 }" :title="`${day.month} 月 ${day.day} 日`"><small>{{ day.weekday }}</small><strong><template v-if="day.day===1 && mode==='image'">{{ day.month }}/<br>1</template><template v-else>{{ day.day === 1 ? `${day.month}/1` : day.day }}</template></strong><span v-if="day.timestamp === today" class="day-today">今天</span></div></div></div>
          <template v-if="groups.length">
            <div v-for="group in groups" :key="group.key" class="timeline-group" data-render-block :style="{ '--game-accent': gameAccent(group.gameId) }">
              <div class="timeline-label group-label"><GameIcon class="game-monogram" :game-id="group.gameId" :name="group.gameName" /><div><strong>{{ group.gameName }}</strong><small>{{ group.events.length }} 项活动</small></div></div>
              <div class="group-track">
                <div class="grid-backdrop" aria-hidden="true"><div v-for="day in range.days" :key="day.timestamp" :class="{ weekend: day.weekend, 'today-column': day.timestamp === today }" /></div>
                <div v-if="todayVisible" class="today-line" :style="{ left: `${todayPosition}%` }" aria-hidden="true" />
                <div v-for="event in group.events" :key="event.id" class="event-lane" data-render-block>
                  <component :is="mode === 'image' ? 'article' : 'button'" :type="mode === 'image' ? undefined : 'button'" class="timeline-event" :class="{ 'is-point': event.geometry.kind === 'point', 'is-short': event.geometry.kind === 'range' && event.geometry.width < 30, 'label-left': event.geometry.left >= 50, 'is-ended': event.status === '已结束', 'clipped-start': event.geometry.clippedStart, 'clipped-end': event.geometry.clippedEnd, 'is-selected': selectedId === event.id }" :style="barStyle(event)" :title="eventDescription(event)" :aria-label="`查看活动详情：${event.name || '未命名活动'}`" :aria-pressed="selectedId === event.id" @click="selectEvent(event, $event)">
                    <template v-if="event.geometry.kind === 'range'"><i v-if="event.elapsed != null" class="event-elapsed" :style="{width:`${event.elapsed}%`}" aria-hidden="true" /><span class="event-summary"><span class="event-heading"><span class="event-bar-title">{{ event.geometry.clippedStart ? '‹ ' : '' }}{{ event.name || '未命名活动' }}{{ event.geometry.clippedEnd ? ' ›' : '' }}</span><small class="event-category">{{ event.category }}</small><small class="event-status">{{ stateLabel(event) }}</small><small v-if="event.remainingDays != null" class="event-remaining" :class="{urgent:event.remainingDays<=3}">剩 {{ event.remainingDays }} 天</small></span></span></template>
                    <template v-else><span class="point-diamond" aria-hidden="true" /><span class="point-label" :class="{ 'point-label-left': event.geometry.left >= 50 }"><span class="event-heading"><strong>{{ event.name || '未命名活动' }}</strong><small class="event-category">{{ event.category }}</small><small class="event-status">{{ stateLabel(event) }}</small></span></span></template>
                  </component>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="calendar-empty timeline-empty"><span aria-hidden="true">◇</span><strong>{{ events.length ? '当前范围没有可定位的活动' : emptyTitle }}</strong><p>{{ events.length ? '可切换时间范围，或查看下方未确定日期的活动。' : '采集到的活动公告将在这里按真实日期展示。' }}</p></div>
        </div>
      </div>
    <p v-if="!range && !events.length" class="calendar-empty">{{ emptyTitle }}</p>
<section v-if="undated.length || invalid.length" class="calendar-unplaced" aria-label="待确认的时间"><div class="unplaced-heading"><h2>待确认的时间</h2></div><div class="unplaced-grid"><div v-for="bucket in [{ title: '日期未提供', events: undated }, { title: '日期异常', events: invalid }]" v-show="bucket.events.length" :key="bucket.title" class="unplaced-bucket"><h3>{{ bucket.title }} <span>{{ bucket.events.length }}</span></h3><component :is="mode === 'image' ? 'article' : 'button'" v-for="event in bucket.events" :key="event.id" data-render-block :type="mode === 'image' ? undefined : 'button'" class="unplaced-event" :aria-label="`查看活动详情：${event.name || '未命名活动'}`" @click="selectEvent(event, $event)"><span><strong>{{ event.name || '未命名活动' }}</strong><small>{{ event.category }} · {{ stateLabel(event) }}</small></span></component></div></div></section>
  </div>
</template>
<style scoped>
.timeline-scroll { overflow:visible; flex:none; min-height:140px; scrollbar-color: var(--scrollbar) var(--bg); scrollbar-width: thin; }
.timeline-canvas { min-width: var(--timeline-min); }
.timeline-header, .timeline-group { display: grid; grid-template-columns: 184px minmax(0, 1fr); }
.timeline-header { position: sticky; top: 0; z-index: 5; background: var(--card-bg); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.timeline-label { position: sticky; left: 0; z-index: 3; background: var(--card-bg); border-right: 1px solid var(--border); }
.header-label { display: flex; flex-direction: column; justify-content: center; gap: 4px; padding: 18px 20px; color: var(--text-muted); font-size: 12px; font-weight: 500; }
.header-label small { color: var(--text-faint); font-size: 10px; font-weight: 400; }
.date-track, .grid-backdrop { display: grid; grid-template-columns: repeat(var(--day-count), minmax(0, 1fr)); }
.date-cell { min-height: 78px; display: grid; grid-template-rows: 14px 26px 14px; justify-items: center; align-content: center; gap: 3px; padding: 8px 0; border-right: 1px solid var(--overlay-1); font-family: var(--font-sans); }
.date-cell small { font-size: 10px; line-height: 14px; color: var(--text-faint); }
.date-cell strong { display: grid; place-items: center; min-width: 26px; height: 26px; padding: 0 2px; border-radius: 13px; font-variant-numeric: tabular-nums; font-size: 14px; font-weight: 500; line-height: 1; }
.date-cell.is-month-start strong { font-size: 12px; }
.date-cell.weekend { background: var(--overlay-1); }
.date-cell.is-today { color: var(--accent); background: color-mix(in srgb, var(--accent) 5%, transparent); }
.date-cell.is-today strong { background: var(--accent); color: var(--accent-ink); }
.day-today { font-size: 9px; font-weight: 500; line-height: 14px; white-space: nowrap; color: var(--accent); }
.timeline-group { border-bottom: 1px solid var(--border); }
.timeline-group:last-child { border-bottom: 0; }
.group-label { display:flex; align-items:flex-start; gap:10px; padding:18px 16px; }
.game-monogram { width: 28px; height: 28px; background: color-mix(in srgb, var(--game-accent) 13%, transparent); border-radius: 7px; font-size: 15px; }
.group-label strong { display: block; font-size: 13px; font-weight: 600; line-height: 18px; }
.group-label small { display: block; color: var(--text-faint); font-size: 11px; line-height: 15px; }
.group-track { position:relative; overflow:hidden; container-type:inline-size; }
.grid-backdrop { position: absolute; inset: 0; pointer-events: none; }
.grid-backdrop > div { border-right: 1px solid var(--overlay-2); }
.grid-backdrop .weekend { background: var(--overlay-1); }
.grid-backdrop .today-column { background: color-mix(in srgb, var(--accent) 3%, transparent); }
.today-line { position: absolute; top: 0; bottom: 0; width: 1px; background: color-mix(in srgb, var(--accent) 46%, transparent); z-index: 2; pointer-events: none; }
.event-lane { min-height:34px; padding-bottom:2px; position:relative; }
.timeline-event { position:relative; top:0; min-height:32px; min-width:0; border:0; box-shadow:inset 0 -1px 0 color-mix(in srgb, var(--game-accent) 20%, transparent); border-radius:0; color:var(--text); background:repeating-linear-gradient(125deg, transparent, transparent 12px, var(--overlay-1) 12px, var(--overlay-1) 14px), linear-gradient(100deg, color-mix(in srgb, var(--game-accent) 26%, var(--card-bg)), color-mix(in srgb, var(--game-accent) 9%, var(--card-bg))); padding:4px 10px; display:block; text-align:left; overflow:hidden; transition:filter var(--duration-quick) var(--ease-smooth-out), transform var(--duration-quick) var(--ease-smooth-out); }
.timeline-event:not(.is-point)::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--game-accent); }
@media (hover: hover) and (pointer: fine) { .timeline-event:hover { filter: brightness(1.12) saturate(1.08); } }
.timeline-event:not(.is-point):active { transform: scaleY(0.94); }
.timeline-event.is-ended { opacity: .7; }
.event-summary { display:grid; gap:2px; min-width:0; width:100%; position:relative; }
.event-heading { display:flex; flex-wrap:wrap; align-items:center; gap:2px 6px; min-width:0; }
.event-summary,.point-label {font-family:inherit;line-height:1.4;text-shadow:0 1px 3px var(--bg),0 0 6px var(--card-bg)}
.event-elapsed{position:absolute;inset:0 auto 0 0;background:color-mix(in srgb,var(--game-accent) 20%,transparent);border-right:1px solid var(--game-accent);pointer-events:none}
.event-remaining{flex-shrink:0;font-size:10px;color:var(--text-muted);border:1px solid var(--border-strong);border-radius:4px;padding:1px 5px;background:var(--card-bg)}
.event-remaining.urgent{color:var(--stale-text);background:var(--stale-bg)}
.timeline-event.is-short { overflow:visible; padding:4px 0; }
.is-short .event-summary { position:relative; left:10px; width:min(420px,45cqw); background:color-mix(in srgb,var(--card-bg) 92%,transparent); padding:0 5px; border-radius:3px; }
.is-short.label-left .event-summary { left:100%; transform:translateX(-100%); }
.timeline-event.is-short::after { content: ''; position: absolute; right: 0; top: 0; bottom: 0; width: 1px; background: var(--game-accent); opacity: .5; }
.event-bar-title { display:block; flex:1 1 80px; font-size:11px; font-weight:600; min-width:0; white-space:normal; overflow-wrap:anywhere; line-height:14px; }
.event-category, .event-status { flex-shrink: 0; font-size: 10px; white-space: nowrap; }
.event-category { color: var(--text-muted); }
.event-status { color: var(--game-accent); }
.timeline-event.clipped-start { border-top-left-radius: 0; border-bottom-left-radius: 0; }
.timeline-event.clipped-start::before { background: repeating-linear-gradient(to bottom, var(--game-accent) 0 3px, transparent 3px 6px); }
.timeline-event.clipped-end { border-top-right-radius: 0; border-bottom-right-radius: 0; }
.timeline-event.clipped-end::after { content: ''; position: absolute; inset: 0 0 0 auto; width: 2px; background: repeating-linear-gradient(to bottom, var(--game-accent) 0 3px, transparent 3px 6px); }
.timeline-event.is-selected { outline: 2px solid var(--accent); outline-offset: 2px; z-index: 2; }
.timeline-event.is-point { width: 16px; transform: translateX(-50%); padding: 0; background: transparent; border: 0; box-shadow: none; overflow: visible; justify-content: center; }
.point-diamond { position:absolute; left:3px; top:16px; display:block; height:9px; width:9px; background:var(--game-accent); transform:translateY(-50%) rotate(45deg); border:2px solid var(--card-bg); box-shadow:0 0 0 1px var(--game-accent); }
.point-label { position:relative; left:20px; width:min(420px,45cqw); display:grid; gap:2px; min-height:32px; color:var(--text); padding:4px 7px; background:color-mix(in srgb,var(--card-bg) 92%,transparent); }
.point-label strong { flex:1 1 80px; min-width:0; font-size:11px; font-weight:600; white-space:normal; overflow-wrap:anywhere; line-height:14px; }
.point-label-left { left:0; transform:translateX(calc(-100% - 20px)); }
.calendar-empty { padding: 42px 24px; text-align: center; color: var(--text-muted); font-size: 12px; }
.timeline-empty { display: grid; gap: 13px; justify-items: center; min-height: 245px; align-content: center; }
.timeline-empty > span { font-size: 27px; color: var(--accent); opacity: .7; }
.timeline-empty strong { color: var(--text); font-size: 14px; font-weight: 500; }
.calendar-unplaced { border: 1px solid var(--border); padding: 20px; border-radius: 12px; background: var(--card-bg); box-shadow: var(--card-shadow); }
.unplaced-heading { display: flex; gap: 16px; align-items: baseline; margin-bottom: 20px; flex-wrap: wrap; }
.unplaced-heading h2 { font-size: 15px; font-weight: 600; }
.unplaced-heading p { font-size: 12px; color: var(--text-muted); }
.unplaced-grid { display: grid; gap: 24px; }
.unplaced-bucket h3 { font-size: 12px; color: var(--text-muted); margin: 0 0 10px; font-weight: 500; }
.unplaced-bucket h3 span { margin-left: 6px; color: var(--text); font-family: var(--font-mono); }
.unplaced-event { transition:background-color var(--duration-quick) var(--ease-smooth-out); display:flex; justify-content:space-between; gap:20px; align-items:center; padding:8px 0; width:100%; border:0; border-top:1px solid var(--overlay-3); color:var(--text); background:transparent; text-align:left; }
.unplaced-event > span:first-child { display:flex; flex-wrap:wrap; align-items:center; gap:3px 8px; }
.unplaced-event strong { font-weight: 500; font-size: 13px; }
.unplaced-event small, .unknown-reason { color: var(--text-muted); font-size: 11px; }
.unknown-reason b { margin-left: 18px; color: var(--accent); }

.calendar-content { min-width:0; display:flex; flex-direction:column; flex:1; min-height:0; }
.calendar-content:not(.image-mode) { overflow:auto; }
.calendar-unplaced { margin:12px 16px; }
.calendar-content button { cursor:pointer; font-family:inherit; }
.calendar-content button:focus-visible,.timeline-scroll:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
.image-mode .timeline-scroll { overflow:visible; flex:none; }
.image-mode .timeline-canvas { min-width:0; }
.image-mode .timeline-header,.image-mode .timeline-label { position:static; }
.image-mode .date-cell strong { min-width:0; padding:0; font-size:9px; white-space:nowrap; }
.image-mode .date-cell.is-month-start strong { font-size:8px; }
.image-mode .date-cell small,.image-mode .day-today { font-size:8px; }
.image-mode .timeline-event { cursor:default; }
.image-mode .event-lane { min-height:36px; }
.image-mode .timeline-event,.image-mode .point-label { min-height:34px; }
.image-mode .event-bar-title,.image-mode .point-label strong { font-size:13px; line-height:18px; }
.image-mode .event-category,.image-mode .event-status,.image-mode .event-remaining { font-size:11px; }
.image-mode .point-diamond { top:17px; }
.image-mode .calendar-unplaced { margin:12px 0; }
@media(max-width:760px) {
  .timeline-header,.timeline-group { grid-template-columns:142px minmax(0,1fr); }
  .header-label { padding:15px; }
  .group-label { padding:0 10px; gap:7px; }
  .game-monogram { width:24px; height:24px; font-size:12px; }
  .group-label strong { font-size:11px; }
  .calendar-unplaced { padding:18px; }
  .unplaced-event { gap:10px; align-items:start; }
  .unknown-reason { max-width:100px; line-height:1.6; flex-shrink:0; }
}
@media(prefers-reduced-motion:reduce) { .timeline-event { transition:none; } }
</style>
