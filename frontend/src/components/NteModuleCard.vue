<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { nteGuidePoints, nteModuleTitles } from '../nte-modules.js'
import { areaViews, catalogRole, gachaView, gauge, GLYPHS, houseView, officialPullIcon, progressView, roleBreakdown, rosterOrder, vehicleView } from '../nte-charts.js'
import { displayBeijing, monthDay } from '../time.js'
import { safeUrl } from '../calendar.js'
import { nteRoleIcon } from '../nte-icons.js'
import { friendlyDataError } from '../cloud-display.js'
import { vPop, vReveal } from '../motion.js'
import AppIcon from './AppIcon.vue'
import BarChart from './BarChart.vue'
import DonutChart from './DonutChart.vue'
import HRail from './HRail.vue'
import NteDetailDialog from './NteDetailDialog.vue'
import NteIcon from './NteIcon.vue'
import RingGauge from './RingGauge.vue'
const props=defineProps({capability:{type:String,required:true},snap:{default:null},accountId:{type:String,default:''}})
const opened=ref(false),title=computed(()=>nteModuleTitles[props.capability]||props.capability)
const inline=computed(()=>['stamina','record'].includes(props.capability))
// Cloud reads put a failure on the snapshot itself; local snapshots carry it in poll_status.
const error=computed(()=>props.snap?.error||props.snap?.poll_status?.error)
const readAt=computed(()=>props.capability==='stamina' ? props.snap?.payload?.updated_at || props.snap?.fetched_at : props.snap?.fetched_at)
watch(()=>props.accountId,()=>{opened.value=false})
watch(()=>props.capability,()=>{opened.value=false})

// Every picture is optional: one that fails to load drops out and its tile shows the letter instead.
const failed=reactive(new Set())
const usable=url=>{const safe=safeUrl(url);return safe && !failed.has(safe) ? safe : ''}
const broken=url=>{const safe=safeUrl(url);if(safe)failed.add(safe)}

const payload=computed(()=>props.snap?.payload?.schema_version===1 ? props.snap.payload : null)
const p=computed(()=>payload.value || {})
const show=value=>value===null || value===undefined || value==='' || (typeof value==='number' && !Number.isFinite(value)) ? '未知' : value
const percent=g=>g.known ? `${Math.round(g.pct)}%` : '—'
// A ring only draws from counts it knows; RingGauge takes numbers, the source may send numeric text.
const ring=g=>({value:g.known ? Number(g.current) : null,max:g.known ? Number(g.total) : null})
const guideRoles=['黑羽','残虹','灵可','伊洛伊','娜娜莉'].map(name=>({name,icon:nteRoleIcon(name)}))

const account=computed(()=>({
  name:show(p.value.nickname),initial:String(p.value.nickname||'异').slice(0,1),
  stats:[{label:'等级',value:show(p.value.level)},{label:'世界等级',value:show(p.value.world_level)},{label:'大亨等级',value:show(p.value.tycoon_level)},{label:'活跃天数',value:show(p.value.active_days),unit:'天'}],
  rings:[['成就',p.value.achievement_count,p.value.achievement_total,'var(--chart-1)'],['房产',p.value.house_count,p.value.house_total,'var(--chart-2)'],['载具',p.value.vehicle_count,p.value.vehicle_total,'var(--chart-3)']]
    .map(([label,current,total,color])=>({label,color,...gauge(current,total)})),
}))
const stamina=computed(()=>[['本性像素',p.value.current,p.value.maximum,'var(--chart-1)'],['都市活力',p.value.city_current,p.value.city_maximum,'var(--chart-2)'],['日常活跃',p.value.daily_activity,100,'var(--chart-3)']]
  .map(([label,current,total,color])=>({label,color,...gauge(current,total)})))
const progress=computed(()=>progressView(p.value))
const MEDAL={gold:'var(--chart-4)',silver:'color-mix(in srgb,var(--text-faint) 62%,var(--card-bg))',bronze:'var(--chart-2)'}
const medalBar=computed(()=>{const tiers=progress.value.medals,sum=tiers.reduce((total,tier)=>total+(tier.value||0),0);return sum>0 ? tiers.filter(tier=>tier.value>0).map(tier=>({...tier,share:tier.value/sum*100})) : []})

const QUALITY={S:'var(--chart-1)',A:'var(--chart-2)',B:'var(--chart-3)',C:'var(--chart-4)'}
const qualityColor=value=>QUALITY[value] || 'var(--chart-5)'
const breakdown=computed(()=>roleBreakdown(p.value.entries))
const roster=computed(()=>rosterOrder(p.value.entries).map(role=>({role,src:usable(role.icon_url)})))
const qualitySegments=computed(()=>breakdown.value.quality.map(row=>({...row,color:qualityColor(row.label)})))
const elementBars=computed(()=>breakdown.value.element.map(row=>({label:row.label,value:row.value})))

const areas=computed(()=>areaViews(p.value.areas))

const owned=computed(()=>gauge(p.value.owned_count,p.value.total))
const entries=computed(()=>(Array.isArray(p.value.entries) ? p.value.entries : []).filter(entry=>entry && typeof entry==='object'))
const TINTS=['var(--game-vivid)','var(--game-vivid-2)','var(--chart-3)','var(--chart-4)']
const houses=computed(()=>props.capability==='realestate' ? entries.value.map(houseView) : [])
const vehicles=computed(()=>props.capability==='vehicles' ? entries.value.map(entry=>vehicleView(entry,p.value.show_id)) : [])
const OWNERSHIP={true:'已拥有',false:'未拥有',null:'状态未知'}
// Residents are listed by id; only ones the public catalog names get an avatar.
const residents=ids=>ids.map(catalogRole).filter(Boolean)
const teams=computed(()=>props.capability==='teams' ? entries.value.map((entry,index)=>{
  const images=(Array.isArray(entry.image_urls) ? entry.image_urls : []).map(safeUrl).filter(Boolean)
  return {key:entry.id ?? index,name:entry.name || '未命名配队',description:entry.description || '',icon:usable(entry.icon_url),images,cover:images.find(url=>!failed.has(url)) || ''}
}) : [])

const gacha=computed(()=>gachaView(p.value))
const TONE={short:'var(--chart-3)',medium:'var(--chart-4)',long:'var(--chart-8)',unknown:'var(--text-faint)'}
const luckSegments=computed(()=>[['short','欧 / 超欧'],['medium','普通 / 非'],['long','超非'],['unknown','未标注']].map(([tone,label])=>({label,value:gacha.value.tones[tone],color:TONE[tone]})).filter(row=>row.value>0))
const poolBars=computed(()=>gacha.value.pools.map(pool=>({label:pool.name,value:pool.draws})))
const pulls=computed(()=>gacha.value.recent.map(item=>({...item,
  src:(()=>{const url=safeUrl(officialPullIcon(item.entry.item_id));return url && !failed.has(url) ? url : ''})(),
  label:String(item.entry.name || item.entry.item_id || '?'),day:item.time==null ? '' : monthDay(item.time)})))
</script>
<template>
  <section v-reveal class="nte-module-card" :class="`module-${capability}`">
    <header class="mod-head"><h2>{{ title }}</h2><button v-if="!inline" type="button" class="ui-button small-button mod-open" @click="opened = true">查看{{ title }}<AppIcon name="arrow" :size="14" /></button></header>

    <div v-if="capability === 'record'" class="inline-content"><slot /></div>

    <div v-else-if="capability === 'guides'" class="guides-body">
      <ul class="guide-points">
        <li v-for="metric in nteGuidePoints" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></li>
        <li class="guide-kinds"><span class="chip-list"><span v-for="kind in ['弧盘', '配队', '套装', '属性', '技能']" :key="kind" class="chip">{{ kind }}</span></span></li>
      </ul>
      <HRail label="已整理攻略的角色" class="rail guide-rail"><figure v-for="role in guideRoles" :key="role.name" class="guide-role"><NteIcon :src="role.icon" :name="role.name" size="xl" /><figcaption>{{ role.name }}</figcaption></figure></HRail>
    </div>

    <p v-else-if="!payload" class="module-state">{{ snap?.payload && snap.payload.schema_version !== 1 ? '数据格式已更新，请刷新' : '暂无数据，请刷新后查看' }}</p>

    <div v-else-if="capability === 'account'" class="account-body">
      <div class="account-top">
        <div class="account-id"><span class="account-avatar" aria-hidden="true">{{ account.initial }}</span><div class="account-name"><strong>{{ account.name }}</strong><span v-if="p.server_name" class="chip">{{ p.server_name }}</span></div></div>
        <dl class="account-stats"><div v-for="stat in account.stats" :key="stat.label"><dt>{{ stat.label }}</dt><dd>{{ stat.value }}<small v-if="stat.unit && stat.value !== '未知'">{{ stat.unit }}</small></dd></div></dl>
      </div>
      <ul class="own-rings">
        <li v-for="item in account.rings" :key="item.label" class="own-ring">
          <RingGauge v-bind="ring(item)" :label="item.label" :size="64" :stroke="7" :color="item.color"><b class="ring-pct">{{ percent(item) }}</b></RingGauge>
          <span class="own-copy"><span class="kicker">{{ item.label }}</span><strong class="mid">{{ show(item.current) }}<small>/ {{ show(item.total) }}</small></strong></span>
        </li>
        <li class="own-ring plain"><span class="own-copy"><span class="kicker">角色数</span><strong class="mid">{{ show(p.character_count) }}</strong></span></li>
      </ul>
    </div>

    <div v-else-if="capability === 'stamina'" class="stamina-body">
      <div v-for="row in stamina" :key="row.label" class="ring-tile">
        <span class="kicker">{{ row.label }}</span>
        <progress v-if="row.known" class="sr-only" :value="row.current" :max="row.total" :aria-label="row.label" />
        <span aria-hidden="true"><RingGauge v-bind="ring(row)" :label="row.label" :size="88" :stroke="9" :color="row.color"><b class="ring-pct">{{ percent(row) }}</b></RingGauge></span>
        <span v-pop class="ring-value">{{ show(row.current) }} <small>/ {{ show(row.total) }}</small></span>
      </div>
    </div>

    <div v-else-if="capability === 'progress'" class="progress-body">
      <div class="progress-hero">
        <progress v-if="progress.ring.known" class="sr-only" :value="progress.ring.current" :max="progress.ring.total" aria-label="成就总进度" />
        <span aria-hidden="true"><RingGauge v-bind="ring(progress.ring)" label="成就总进度" :size="108" :stroke="11" color="var(--game-vivid)"><b class="ring-pct large">{{ percent(progress.ring) }}</b></RingGauge></span>
        <div class="hero-copy">
          <span class="kicker">成就</span>
          <strong class="big">{{ show(p.completed) }}<small>/ {{ show(p.total) }}</small></strong>
          <div v-if="medalBar.length" class="stack-bar" aria-hidden="true"><i v-for="tier in medalBar" :key="tier.key" :style="{ '--series': MEDAL[tier.key], width: `${tier.share}%` }" /></div>
          <ul class="legend medals"><li v-for="tier in progress.medals" :key="tier.key" :style="{ '--series': MEDAL[tier.key] }">{{ tier.label }}奖章 <b>{{ show(tier.value) }}</b></li></ul>
        </div>
      </div>
      <ul v-if="progress.categories.length" class="bar-list categories">
        <li v-for="item in progress.categories" :key="item.key" class="bar-row" :title="item.name">
          <span class="k">{{ show(item.name) }}</span>
          <span class="meter" aria-hidden="true"><i :style="{ '--pct': `${item.pct ?? 0}%` }" /></span>
          <span class="v">{{ show(item.current) }} <small>/ {{ show(item.total) }}</small></span>
        </li>
      </ul>
    </div>

    <div v-else-if="capability === 'roles'" class="roles-body">
      <div class="roles-summary">
        <div class="sum-panel"><DonutChart :segments="qualitySegments" label="角色品质分布" unit=" 名" :size="104" :stroke="14"><b class="donut-total">{{ breakdown.total }}</b><small>角色</small></DonutChart></div>
        <div v-if="elementBars.length" class="sum-panel"><span class="kicker">各元素角色数</span><BarChart :items="elementBars" label="各元素角色数" unit=" 名" :height="64" /></div>
        <dl v-if="breakdown.averageLevel != null" class="sum-panel sum-levels"><div><dt>平均等级</dt><dd>{{ breakdown.averageLevel }}</dd></div><div><dt>最高等级</dt><dd>{{ breakdown.maxLevel }}</dd></div></dl>
      </div>
      <HRail label="角色列表" class="rail roles-rail">
        <figure v-for="({ role, src }, index) in roster" :key="role.id ?? index" class="role-tile">
          <img v-if="src" class="role-avatar" :src="src" alt="" loading="lazy" referrerpolicy="no-referrer" @error="broken(src)" />
          <NteIcon v-else :src="nteRoleIcon(role.id)" :name="role.name || '角色'" size="xl" />
          <figcaption><strong :title="role.name">{{ role.name || '未命名' }}</strong><span class="meta"><i v-if="role.quality" class="rank" :style="{ '--q': qualityColor(role.quality) }">{{ role.quality }}</i><span v-if="role.level != null">Lv{{ role.level }}</span></span></figcaption>
        </figure>
      </HRail>
    </div>

    <div v-else-if="capability === 'exploration'" class="explore-body">
      <p v-if="!areas.length" class="module-state">暂无探索数据</p>
      <ul v-else class="area-grid">
        <li v-for="area in areas" :key="area.key" class="area-tile">
          <RingGauge v-bind="ring(area)" :label="area.name || '区域探索'" :size="68" :stroke="8" color="var(--game-vivid)"><b class="ring-pct">{{ percent(area) }}</b></RingGauge>
          <span class="own-copy"><strong class="area-name" :title="area.name">{{ show(area.name) }}</strong><span class="mid">{{ show(area.current) }}<small>/ {{ show(area.total) }}</small></span><em v-if="area.over" class="target-met">已达目标</em></span>
          <ul v-if="area.details.length" class="bar-list area-details">
            <li v-for="item in area.details" :key="item.key" class="bar-row" :title="item.name"><span class="k">{{ show(item.name) }}</span><span class="meter" aria-hidden="true"><i :style="{ '--pct': `${item.pct ?? 0}%` }" /></span><span class="v">{{ show(item.current) }}<small>/{{ show(item.total) }}</small></span></li>
          </ul>
        </li>
      </ul>
    </div>

    <div v-else-if="capability === 'realestate' || capability === 'vehicles'" class="assets-body">
      <div class="own-head">
        <RingGauge v-bind="ring(owned)" label="拥有" :size="64" :stroke="7" color="var(--game-vivid)"><b class="ring-pct">{{ percent(owned) }}</b></RingGauge>
        <span class="own-copy"><span class="kicker">拥有</span><strong class="big">{{ show(p.owned_count) }}<small>/ {{ show(p.total) }}</small></strong></span>
        <span v-if="capability === 'vehicles' && (p.show_name || p.show_id)" class="chip game">展示载具：{{ p.show_name || p.show_id }}</span>
      </div>
      <p v-if="!entries.length" class="module-state">{{ capability === 'vehicles' ? '暂无载具明细' : '暂无资产明细' }}</p>
      <HRail v-else :label="capability === 'vehicles' ? '载具列表' : '房产列表'" class="rail assets-rail">
        <article v-for="(house, index) in houses" :key="`h${index}`" class="asset-card" :class="{ off: house.owned !== true }" :style="{ '--tint': TINTS[index % TINTS.length] }">
          <div class="asset-cover"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="GLYPHS.house" /></svg><span class="glass asset-badge">{{ OWNERSHIP[house.owned] }}</span></div>
          <strong class="asset-name" :title="house.name">{{ house.name || '未命名房产' }}</strong>
          <div class="asset-meta">
            <span v-if="residents(house.residents).length" class="stack"><NteIcon v-for="resident in residents(house.residents).slice(0, 3)" :key="resident.name" :src="resident.icon" :name="resident.name" size="small" /></span>
            <span v-else-if="house.residents.length" class="muted">入住 {{ house.residents.length }}</span>
            <span v-else class="muted">暂无入住</span>
            <span v-if="house.furnitureTotal" class="muted"><b>{{ house.furnitureOwned }}</b>/{{ house.furnitureTotal }} 件家具</span>
          </div>
        </article>
        <article v-for="(car, index) in vehicles" :key="`v${index}`" class="asset-card" :class="{ off: car.owned !== true, showcase: car.showcase }" :style="{ '--tint': TINTS[index % TINTS.length] }">
          <div class="asset-cover"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="GLYPHS.car" /></svg><span class="glass asset-badge">{{ car.showcase ? '展示中' : OWNERSHIP[car.owned] }}</span></div>
          <strong class="asset-name" :title="car.name">{{ car.name || '未命名载具' }}</strong>
          <dl v-if="car.base.length" class="car-stats"><div v-for="stat in car.base.slice(0, 3)" :key="stat.name"><dt>{{ stat.name }}</dt><dd>{{ stat.value }}</dd></div></dl>
        </article>
      </HRail>
    </div>

    <div v-else-if="capability === 'teams'" class="teams-body">
      <p v-if="!teams.length" class="module-state">暂无官方配队推荐</p>
      <span v-else class="kicker">官方推荐 <b class="count">{{ teams.length }}</b></span>
      <HRail v-if="teams.length" label="官方配队推荐" class="rail teams-rail">
        <article v-for="(team, index) in teams" :key="team.key" class="team-card" :style="{ '--tint': TINTS[index % 2] }">
          <div class="team-pic">
            <img v-if="team.cover" :src="team.cover" :alt="`${team.name}配队图`" loading="lazy" referrerpolicy="no-referrer" @error="broken(team.cover)" />
            <span v-else class="team-fallback" aria-hidden="true">{{ String(team.name).slice(0, 1) }}</span>
            <span class="glass team-badge"><img v-if="team.icon" class="team-icon" :src="team.icon" alt="" loading="lazy" referrerpolicy="no-referrer" @error="broken(team.icon)" /><b>{{ team.name }}</b></span>
            <span v-if="team.images.length > 1" class="glass team-count">{{ team.images.length }} 张图</span>
          </div>
          <p v-if="team.description" class="team-desc">{{ team.description }}</p>
        </article>
      </HRail>
    </div>

    <div v-else-if="capability === 'gacha'" class="gacha-body">
      <div class="gacha-hero" :data-tone="gacha.titleTone">
        <span class="kicker">近期评价</span>
        <strong class="luck">{{ gacha.title || '暂无评价' }}</strong>
        <dl class="luck-nums"><div><dt>统计抽数</dt><dd>{{ show(gacha.totalDraws) }}</dd></div><div><dt>出 S 数</dt><dd>{{ show(gacha.totalS) }}</dd></div></dl>
      </div>
      <p v-if="!gacha.pools.length" class="module-state gacha-empty">暂无卡池统计</p>
      <template v-else>
        <div class="gacha-pools"><span class="kicker">各卡池统计抽数</span><BarChart :items="poolBars" label="各卡池统计抽数" unit=" 抽" :height="96" /></div>
        <div v-if="luckSegments.length" class="gacha-luck"><span class="kicker">出 S 评价分布</span><DonutChart :segments="luckSegments" label="出 S 评价分布" unit=" 次" :size="96" :stroke="14"><b class="donut-total">{{ gacha.pulls }}</b><small>次出 S</small></DonutChart></div>
        <ul v-if="gacha.pools.some(pool => pool.reach)" class="gacha-reach">
          <li v-for="pool in gacha.pools.filter(item => item.reach)" :key="pool.key" class="own-ring">
            <RingGauge v-bind="ring(pool.reach)" :label="`${pool.name}出 S 平均抽数`" :size="64" :stroke="7" color="var(--game-vivid)"><b class="ring-pct">{{ percent(pool.reach) }}</b></RingGauge>
            <span class="own-copy"><span class="kicker">{{ pool.name }}</span><strong class="mid">{{ pool.average }}<small>/ 保底 {{ pool.guarantee }} 抽</small></strong></span>
          </li>
        </ul>
        <div v-if="pulls.length" class="gacha-recent">
          <span class="kicker">最近出 S</span>
          <HRail label="最近出 S" class="rail pull-rail">
            <article v-for="(item, index) in pulls" :key="item.key" class="pull-card" :class="{ newest: index === 0 }" :data-tone="item.tone">
              <div class="pull-pic">
                <img v-if="item.src" :src="item.src" alt="" loading="lazy" referrerpolicy="no-referrer" @error="broken(item.src)" />
                <span v-else class="pull-letter" aria-hidden="true">{{ item.label.slice(0, 1) }}</span>
                <span v-if="item.rating" class="glass pull-rating">{{ item.rating }}</span>
              </div>
              <strong class="pull-name" :title="item.label">{{ item.label }}</strong>
              <span class="pull-meta"><template v-if="item.entry.pity != null"><b>{{ item.entry.pity }}</b> 抽 · </template>{{ item.pool }}</span>
              <time v-if="item.day" class="pull-day">{{ item.day }}</time>
            </article>
          </HRail>
        </div>
      </template>
    </div>

    <p v-if="capability === 'stamina'" class="module-state weekly"><AppIcon name="clock" :size="14" />周本剩余 · {{ snap?.payload?.schema_version === 1 ? snap.payload.weekly_remaining ?? '未提供' : '未提供' }}</p>
    <p v-if="error || snap?.state === 'auth_expired'" class="module-error" role="status">{{ friendlyDataError(error,snap?.state) }}</p>
    <footer><span v-if="snap?.stale" class="old">旧数据</span><span v-if="readAt">{{ displayBeijing(readAt) }}</span><span v-else-if="capability === 'guides' || capability === 'teams'">公开资料</span></footer>
    <NteDetailDialog v-if="!inline && opened" :title="title" @close="opened = false"><slot /></NteDetailDialog>
  </section>
</template>
<style scoped>
/* A white card with a faint wash of the game colour in its corner, like the
   game cards on the overview. Cards that share a row stretch to one height and
   keep their footer at the bottom. */
.nte-module-card{--hot:linear-gradient(160deg,color-mix(in srgb,var(--game-vivid) 80%,black),color-mix(in srgb,var(--game-vivid-2) 72%,black));position:relative;isolation:isolate;display:flex;flex-direction:column;gap:16px;min-width:0;align-self:stretch;grid-column:1/-1;padding:22px;overflow:hidden;background:var(--card-bg);border:1px solid var(--card-border);border-radius:var(--radius-card);box-shadow:var(--card-shadow)}
.nte-module-card::before{content:'';position:absolute;z-index:-1;right:-90px;top:-110px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--game-vivid) 14%,transparent),transparent 70%);pointer-events:none}
/* Stamina with progress, and houses with vehicles, sit side by side; alone they take the full row. */
.nte-module-card.module-stamina,.nte-module-card.module-progress,.nte-module-card.module-realestate,.nte-module-card.module-vehicles{grid-column:auto}
.nte-module-card.module-stamina:not(:has(+ .module-progress)),.nte-module-card.module-progress:not(.module-stamina + .module-progress),.nte-module-card.module-realestate:not(:has(+ .module-vehicles)),.nte-module-card.module-vehicles:not(.module-realestate + .module-vehicles){grid-column:1/-1}
.module-record{flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px 32px}
.module-record>.mod-head{min-width:96px}
.module-record>.inline-content{flex:1 1 360px;min-width:0}
.nte-module-card.module-record footer{margin:0 0 0 auto}
.module-account{background:linear-gradient(150deg,color-mix(in srgb,var(--game-vivid) 16%,var(--card-bg)),var(--card-bg) 62%)}
.mod-head{display:flex;align-items:center;gap:12px;min-height:32px}
.mod-head h2{font-size:16px;line-height:24px;font-weight:600;letter-spacing:-.01em;color:var(--text)}
.mod-open{margin-left:auto}
.inline-content :deep(.cap-card){margin:0;padding:0;border:0;border-radius:0;background:none;box-shadow:none}
.inline-content :deep(.cap-title),.inline-content :deep(.fetched-at){display:none}
.module-state{color:var(--text-muted);font-size:13px;line-height:1.7}
.module-state.weekly{display:inline-flex;align-items:center;gap:6px;align-self:flex-start;padding:2px 12px 2px 10px;border-radius:var(--radius-chip);background:var(--surface-soft);color:var(--text-body);font-size:12px;font-weight:500;line-height:22px}
.module-error{color:var(--danger);font-size:13px;line-height:1.7}
.nte-module-card footer{display:flex;gap:10px;margin-top:auto;min-height:12px;color:var(--text-faint);font-size:12px}
.old{color:var(--stale-text)}
.kicker{color:var(--text-muted);font-size:12px;line-height:18px;font-weight:500}
.kicker .count{margin-left:2px;color:var(--text);font-size:13px;font-weight:600}
/* Big numerals carry a small unit at about half their size. */
.big,.mid{font-weight:600;letter-spacing:-.03em;font-variant-numeric:proportional-nums;white-space:nowrap}
.big{font-size:32px;line-height:38px}
.mid{font-size:20px;line-height:26px;letter-spacing:-.02em}
.big small,.mid small,.ring-value small{margin-left:4px;color:var(--text-muted);font-size:13px;font-weight:500;letter-spacing:0}
.ring-pct{color:var(--text);font-size:14px;font-weight:600;letter-spacing:-.01em}
.ring-pct.large{font-size:20px;letter-spacing:-.02em}
.own-copy{display:grid;gap:1px;min-width:0}
.rail{--rail-gap:12px;--rail-pad:2px;--rail-pad-block:10px}
.teams-rail{--rail-gap:16px}

/* Account: a name and four numerals, then what is owned as rings. */
.account-body{display:grid;gap:18px}
.account-top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px 32px}
.account-id{display:flex;align-items:center;gap:16px;min-width:0}
.account-avatar{display:grid;place-items:center;flex-shrink:0;width:68px;height:68px;border-radius:22px;color:#fff;font-size:28px;font-weight:600;background:var(--hot);box-shadow:0 16px 28px -16px var(--game-vivid),inset 0 1px 0 rgba(255,255,255,.32)}
.account-name{display:grid;justify-items:start;gap:6px;min-width:0}
.account-name strong{font-size:26px;line-height:32px;font-weight:600;letter-spacing:-.02em;overflow-wrap:anywhere}
.account-stats{display:flex;flex-wrap:wrap;gap:12px 36px;margin:0}
.account-stats>div{display:grid;align-content:start;gap:2px}
.account-stats dt{color:var(--text-muted);font-size:12px;line-height:18px}
.account-stats dd{margin:0;font-size:32px;line-height:38px;font-weight:600;letter-spacing:-.03em;font-variant-numeric:proportional-nums;white-space:nowrap}
.account-stats dd small{margin-left:3px;color:var(--text-muted);font-size:14px;font-weight:500;line-height:1;letter-spacing:0}
.own-rings{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0;padding:0;list-style:none}
.own-ring{display:flex;align-items:center;gap:14px;min-width:0;padding:14px 16px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.own-ring.plain{justify-content:flex-start;padding-left:20px}

/* Stamina: three rings, one per resource. */
.stamina-body{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;flex:1}
.ring-tile{position:relative;display:grid;justify-items:center;align-content:center;gap:10px;min-width:0;padding:16px 8px 14px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.ring-value{color:var(--text);font-size:19px;line-height:24px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:proportional-nums;white-space:nowrap}
.ring-value small{font-size:12px}

/* Achievements: the ring and its medals, then one thin bar per category. */
.progress-body{display:grid;gap:18px}
.progress-hero{position:relative;display:flex;align-items:center;gap:20px;min-width:0}
.hero-copy{display:grid;gap:6px;min-width:0;flex:1}
.hero-copy .stack-bar{height:8px;margin-top:2px}
.legend.medals{margin:2px 0 0}
.categories{--bar-label:26%;gap:4px;margin:0;padding:0}

/* Roles: counts and levels in a row of tone panels, every role as a portrait below. */
.roles-body{display:grid;gap:16px;min-width:0}
.roles-summary{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.2fr) minmax(0,.7fr);gap:12px}
.sum-panel{display:grid;align-content:center;gap:6px;min-width:0;padding:16px 18px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.sum-levels{grid-auto-flow:column;grid-auto-columns:1fr;align-content:center;gap:12px;margin:0}
.sum-levels dt{color:var(--text-muted);font-size:12px;line-height:18px}
.sum-levels dd{margin:0;font-size:32px;line-height:38px;font-weight:600;letter-spacing:-.03em;font-variant-numeric:proportional-nums}
.donut-total{font-size:24px;line-height:26px;font-weight:600;letter-spacing:-.03em;font-variant-numeric:proportional-nums}
.donut-total + small{color:var(--text-muted);font-size:12px}
.role-tile{display:grid;justify-items:center;gap:8px;width:96px;margin:0;text-align:center}
.role-avatar{width:72px;height:72px;border-radius:30%;object-fit:cover;background:var(--surface-soft)}
.role-tile figcaption{display:grid;justify-items:center;gap:3px;max-width:100%}
.role-tile strong{max-width:100%;overflow:hidden;color:var(--text);font-size:13px;line-height:18px;font-weight:500;text-overflow:ellipsis;white-space:nowrap}
.meta{display:inline-flex;align-items:center;gap:6px;color:var(--text-muted);font-size:12px;font-variant-numeric:tabular-nums}
.rank{padding:0 6px;border-radius:var(--radius-chip);background:color-mix(in srgb,var(--q) 16%,transparent);color:color-mix(in srgb,var(--q) 55%,var(--text));font-size:12px;font-style:normal;font-weight:600;line-height:18px}

/* Exploration: one tile per area, its detail lines as thin bars. */
.area-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:12px;margin:0;padding:0;list-style:none}
.area-tile{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:8px 14px;align-content:start;min-width:0;padding:16px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.area-name{overflow:hidden;color:var(--text);font-size:14px;line-height:20px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}
.target-met{justify-self:start;margin-top:2px;padding:0 8px;border-radius:var(--radius-chip);background:var(--success-bg);color:var(--success);font-size:12px;font-style:normal;font-weight:500;line-height:18px}
.area-details{--bar-label:34%;grid-column:1/-1;gap:0;margin-top:6px;padding-top:8px;border-top:1px solid var(--border)}
.area-details .bar-row{min-height:24px;font-size:12px}
.area-details .v small{margin-left:1px}

/* Houses and vehicles: cover tiles in a rail; the one on show is the saturated card. */
.assets-body{display:grid;gap:16px;min-width:0}
.own-head{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.asset-card{display:grid;align-content:start;gap:8px;width:172px}
.asset-cover{position:relative;display:grid;place-items:center;height:100px;overflow:hidden;border-radius:var(--radius-tile);color:color-mix(in srgb,var(--tint) 72%,var(--text));background:linear-gradient(150deg,color-mix(in srgb,var(--tint) 34%,var(--card-bg)),color-mix(in srgb,var(--tint) 10%,var(--card-bg)))}
.asset-cover svg{width:48px;height:48px}
.asset-card.off .asset-cover{color:var(--text-faint);background:var(--surface-soft)}
.asset-card.showcase .asset-cover{color:#fff;background:var(--hot);box-shadow:0 18px 32px -20px var(--game-vivid)}
.asset-badge{position:absolute;left:8px;top:8px;padding:1px 10px;border-radius:var(--radius-chip);color:var(--text);font-size:12px;font-weight:500;line-height:20px}
.asset-name{overflow:hidden;color:var(--text);font-size:14px;line-height:20px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}
.asset-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:28px;font-size:12px}
.asset-meta .muted{color:var(--text-muted)}
.asset-meta b{color:var(--text);font-weight:600}
.stack{display:inline-flex}
.stack>*{box-shadow:0 0 0 2px var(--card-bg)}
.stack>*+*{margin-left:-8px}
.car-stats{display:grid;gap:2px;margin:0;font-size:12px}
.car-stats>div{display:flex;justify-content:space-between;gap:8px}
.car-stats dt{color:var(--text-muted)}
.car-stats dd{margin:0;color:var(--text);font-weight:500;font-variant-numeric:tabular-nums;white-space:nowrap}

/* Official teams: the picture leads, with glass badges over it. */
.team-card{display:grid;align-content:start;gap:12px;width:clamp(260px,calc((100% - 32px) / 3),420px)}
.team-pic{position:relative;aspect-ratio:16/9;overflow:hidden;border-radius:var(--radius-tile);background:linear-gradient(150deg,color-mix(in srgb,var(--tint) 30%,var(--card-bg)),color-mix(in srgb,var(--tint) 10%,var(--card-bg)))}
.team-pic>img{display:block;width:100%;height:100%;object-fit:cover}
.team-fallback{display:grid;place-items:center;height:100%;color:color-mix(in srgb,var(--tint) 60%,var(--text));font-size:48px;font-weight:600}
.team-badge{position:absolute;left:10px;bottom:10px;display:inline-flex;align-items:center;gap:8px;max-width:calc(100% - 20px);padding:4px 14px 4px 4px;border-radius:var(--radius-chip);color:var(--text);font-size:13px;line-height:22px}
.team-badge:not(:has(img)){padding-left:14px}
.team-badge b{overflow:hidden;font-weight:600;text-overflow:ellipsis;white-space:nowrap}
.team-icon{width:26px;height:26px;border-radius:30%;object-fit:cover}
.team-count{position:absolute;right:10px;top:10px;padding:1px 10px;border-radius:var(--radius-chip);color:var(--text);font-size:12px;font-weight:500;line-height:20px}
.team-desc{display:-webkit-box;overflow:hidden;color:var(--text-body);font-size:13px;line-height:1.65;-webkit-line-clamp:2;-webkit-box-orient:vertical}

/* Gacha: the rating and totals, pools as bars, the luck split, then the newest S pulls. */
.gacha-body{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px}
.gacha-body>*{min-width:0}
.gacha-hero{grid-column:span 4;display:grid;align-content:space-between;gap:10px;padding:18px 20px;border-radius:var(--radius-tile);background:linear-gradient(150deg,color-mix(in srgb,var(--game-vivid) 22%,var(--card-bg)),color-mix(in srgb,var(--game-vivid-2) 12%,var(--card-bg)) 80%)}
.luck{font-size:30px;line-height:36px;font-weight:600;letter-spacing:-.03em;overflow-wrap:anywhere}
.luck-nums{display:flex;gap:28px;margin:0}
.luck-nums dt{color:var(--text-muted);font-size:12px;line-height:18px}
.luck-nums dd{margin:0;font-size:24px;line-height:30px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:proportional-nums}
.gacha-pools{grid-column:span 5;display:grid;align-content:start;gap:2px;padding:16px 18px 12px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.gacha-luck{grid-column:span 3;display:grid;align-content:start;gap:10px;padding:16px 18px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.gacha-empty{grid-column:span 8;align-self:center}
.gacha-reach{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:12px;margin:0;padding:0;list-style:none}
.gacha-reach .mid small{font-size:12px}
.gacha-recent{grid-column:1/-1;display:grid;gap:4px}
.pull-card{position:relative;display:grid;align-content:start;gap:4px;width:136px;padding:8px 8px 12px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.pull-pic{position:relative;display:grid;place-items:center;aspect-ratio:3/4;overflow:hidden;border-radius:calc(var(--radius-tile) - 6px);background:linear-gradient(160deg,color-mix(in srgb,var(--game-vivid) 22%,var(--card-bg)),color-mix(in srgb,var(--game-vivid-2) 10%,var(--card-bg)))}
.pull-pic>img{width:100%;height:100%;object-fit:cover;object-position:top}
.pull-letter{color:color-mix(in srgb,var(--game-vivid) 60%,var(--text));font-size:40px;font-weight:600}
.pull-rating{position:absolute;left:6px;top:6px;padding:0 9px;border-radius:var(--radius-chip);color:var(--text);font-size:12px;font-weight:500;line-height:20px}
.pull-name{overflow:hidden;margin-top:4px;color:var(--text);font-size:13px;line-height:18px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}
.pull-meta{overflow:hidden;color:var(--text-muted);font-size:12px;line-height:18px;text-overflow:ellipsis;white-space:nowrap}
.pull-meta b{color:var(--text);font-weight:600}
.pull-day{color:var(--text-faint);font-size:12px;line-height:16px;font-variant-numeric:tabular-nums}
/* Only the newest pull is saturated. */
.pull-card.newest{background:var(--hot);box-shadow:0 20px 38px -22px var(--game-vivid)}
.pull-card.newest :is(.pull-name,.pull-meta,.pull-meta b,.pull-day){color:#fff}
.pull-card.newest .pull-pic{background:rgba(255,255,255,.2)}
.pull-card.newest .pull-letter{color:#fff}

/* Guides: what a guide holds, and the roles that have a summary. */
.guides-body{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:20px;align-items:center}
.guide-points{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.guide-points li{display:grid;gap:2px;padding:14px 16px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.guide-points span{color:var(--text-muted);font-size:12px;line-height:18px}
.guide-points strong{font-size:18px;line-height:26px;font-weight:600;letter-spacing:-.02em}
.guide-kinds{padding-block:12px !important}
.guide-role{display:grid;justify-items:center;gap:10px;width:clamp(120px,calc((100% - 48px) / 5),190px);margin:0;padding:18px 8px 14px;border-radius:var(--radius-tile);background:var(--surface-soft)}
.guide-role figcaption{color:var(--text);font-size:13px;line-height:18px;font-weight:500}

@media(max-width:1240px){.gacha-hero{grid-column:span 5}.gacha-pools{grid-column:span 7}.gacha-luck{grid-column:1/-1}}
@media(max-width:1000px){.roles-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.sum-levels{grid-column:1/-1}.own-rings{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:860px){
  .guides-body{grid-template-columns:minmax(0,1fr)}
  .gacha-hero,.gacha-pools,.gacha-luck,.gacha-empty{grid-column:1/-1}
}
@media(max-width:650px){
  .roles-summary{grid-template-columns:minmax(0,1fr)}
  .account-body .own-ring{flex-direction:column;align-items:flex-start;gap:10px;padding:14px}
  .nte-module-card{padding:16px;gap:14px;border-radius:20px}
  .account-avatar{width:56px;height:56px;border-radius:18px;font-size:24px}
  .account-name strong{font-size:22px;line-height:28px}
  .account-stats{gap:10px 24px}
  .account-stats dd{font-size:26px;line-height:32px}
  .progress-hero{gap:14px}
  .big{font-size:28px;line-height:34px}
}
@media(max-width:420px){
  .stamina-body{gap:8px}
  .ring-tile{padding:14px 4px 12px}
}
</style>
