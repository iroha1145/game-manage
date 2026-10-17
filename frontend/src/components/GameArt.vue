<script setup>
import { computed, useId } from 'vue'

// Original geometric artwork for hero cards (not game assets): each game gets
// a motif in its own colours. Layers carry plx-layer so a v-parallax ancestor
// moves them at different depths; everything is decorative.
const props = defineProps({ variant: { type: String, default: 'orbit' } })
const id = useId()
const uid = name => `${name}-${id}`
const motif = computed(() => ({ wuthering_waves: 'waves', nte: 'halo', league_of_legends: 'hex', endfield: 'grid' })[props.variant] || props.variant)
// The planets sit in the right half of the frame: hero text runs along the left.
const planets = [
  { game: 'wuwa', x: 236, y: 110, r: 17, delay: 0 },
  { game: 'nte', x: 438, y: 162, r: 13, delay: -2 },
  { game: 'lol', x: 300, y: 254, r: 10, delay: -4 },
  { game: 'endfield', x: 392, y: 82, r: 8, delay: -6 },
]
// Hexagon corners for a flat-topped cell of radius r at (x, y).
const hex = (x, y, r) => Array.from({ length: 6 }, (_, i) => {
  const a = (Math.PI / 3) * i
  return `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)}`
}).join(' ')
const cells = [[300, 120, 1], [345, 146, 0], [345, 94, 2], [390, 120, 0], [255, 146, 0], [300, 172, 2], [390, 172, 1], [435, 146, 0], [345, 198, 0], [255, 94, 0]]
</script>

<template>
  <div class="game-art" :data-motif="motif" aria-hidden="true">
    <svg viewBox="0 0 480 320" preserveAspectRatio="xMaxYMid slice">
      <defs>
        <radialGradient :id="uid('glow')"><stop offset="0" stop-color="#fff" stop-opacity=".9" /><stop offset=".35" style="stop-color:var(--art-1)" stop-opacity=".55" /><stop offset="1" style="stop-color:var(--art-1)" stop-opacity="0" /></radialGradient>
        <linearGradient :id="uid('stroke')" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--art-1)" /><stop offset="1" style="stop-color:var(--art-2)" /></linearGradient>
        <radialGradient v-for="p in planets" :id="uid(`planet-${p.game}`)" :key="p.game" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#fff" /><stop offset=".3" :style="{ stopColor: `var(--game-${p.game}-vivid)` }" /><stop offset="1" :style="{ stopColor: `var(--game-${p.game}-2)` }" /></radialGradient>
      </defs>

      <template v-if="motif === 'orbit'">
        <g class="plx-layer" style="--plx-range:-26px">
          <circle v-for="p in planets" :key="`g-${p.game}`" :cx="p.x" :cy="p.y" :r="p.r * 4.2" :style="{ fill: `var(--game-${p.game}-vivid)` }" opacity=".22" class="art-blur" />
        </g>
        <g class="plx-layer" style="--plx-range:14px" fill="none" stroke="rgba(255,255,255,.16)" stroke-width="1.2">
          <ellipse cx="336" cy="170" rx="112" ry="44" transform="rotate(-16 336 170)" />
          <ellipse cx="336" cy="170" rx="168" ry="70" transform="rotate(-16 336 170)" />
          <ellipse cx="336" cy="170" rx="226" ry="98" transform="rotate(-16 336 170)" stroke="rgba(255,255,255,.1)" />
        </g>
        <circle cx="336" cy="170" r="70" :fill="`url(#${uid('glow')})`" opacity=".55" />
        <circle cx="336" cy="170" r="16" fill="#fff" opacity=".92" />
        <g class="plx-layer" style="--plx-range:36px">
          <g v-for="p in planets" :key="p.game" class="art-float" :style="{ animationDelay: `${p.delay}s` }">
            <circle :cx="p.x" :cy="p.y" :r="p.r" :fill="`url(#${uid(`planet-${p.game}`)})`" />
          </g>
        </g>
      </template>

      <template v-else-if="motif === 'waves'">
        <circle cx="400" cy="250" r="150" :fill="`url(#${uid('glow')})`" opacity=".45" class="plx-layer" style="--plx-range:-20px" />
        <g class="plx-layer" style="--plx-range:18px" fill="none" :stroke="`url(#${uid('stroke')})`">
          <circle v-for="(r, i) in [40, 76, 112, 148, 184, 220]" :key="r" cx="400" cy="250" :r="r" :stroke-width="2.4 - i * .3" :opacity="0.85 - i * .12" />
        </g>
        <path class="plx-layer" style="--plx-range:40px" d="M0 196 C60 150 100 236 160 196 S260 146 320 196 S420 240 480 190" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="2" stroke-linecap="round" />
        <g class="plx-layer" style="--plx-range:-34px" fill="#fff"><circle cx="236" cy="96" r="3" opacity=".7" /><circle cx="312" cy="62" r="2" opacity=".5" /><circle cx="186" cy="58" r="2" opacity=".4" /></g>
      </template>

      <template v-else-if="motif === 'halo'">
        <circle cx="330" cy="160" r="160" :fill="`url(#${uid('glow')})`" opacity=".4" class="plx-layer" style="--plx-range:-22px" />
        <g class="plx-layer" style="--plx-range:22px" fill="none" :stroke="`url(#${uid('stroke')})`" stroke-linecap="round">
          <circle cx="292" cy="160" r="92" stroke-width="14" opacity=".9" />
          <circle cx="388" cy="160" r="92" stroke-width="3" opacity=".75" />
          <ellipse cx="340" cy="160" rx="170" ry="36" stroke-width="1.5" opacity=".5" transform="rotate(-12 340 160)" />
        </g>
        <g class="plx-layer" style="--plx-range:-36px" fill="#fff"><path d="M206 70l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" opacity=".8" /><circle cx="452" cy="250" r="3" opacity=".6" /><circle cx="230" cy="262" r="2" opacity=".5" /></g>
      </template>

      <template v-else-if="motif === 'hex'">
        <circle cx="345" cy="146" r="150" :fill="`url(#${uid('glow')})`" opacity=".4" class="plx-layer" style="--plx-range:-22px" />
        <g class="plx-layer" style="--plx-range:20px">
          <polygon v-for="([x, y, kind], i) in cells" :key="i" :points="hex(x, y, 28)" :fill="kind === 2 ? `url(#${uid('stroke')})` : 'none'" :fill-opacity="kind === 2 ? .85 : 0" :stroke="kind === 1 ? '#c8aa6e' : 'rgba(255,255,255,.22)'" :stroke-width="kind === 1 ? 2 : 1.2" />
        </g>
        <circle class="plx-layer" style="--plx-range:38px" cx="345" cy="146" r="64" fill="none" stroke="#c8aa6e" stroke-opacity=".7" stroke-width="1.5" />
      </template>

      <template v-else-if="motif === 'grid'">
        <circle cx="360" cy="150" r="150" :fill="`url(#${uid('glow')})`" opacity=".38" class="plx-layer" style="--plx-range:-20px" />
        <g class="plx-layer" style="--plx-range:12px" fill="rgba(255,255,255,.28)">
          <template v-for="row in 7" :key="row"><circle v-for="col in 10" :key="col" :cx="210 + col * 26" :cy="20 + row * 38" r="1.4" /></template>
        </g>
        <g class="plx-layer" style="--plx-range:30px" fill="none" :stroke="`url(#${uid('stroke')})`" stroke-width="3">
          <rect x="300" y="70" width="140" height="140" rx="6" transform="rotate(12 370 140)" />
          <path d="M248 250 L300 166 L352 250 Z" stroke-width="2" opacity=".8" />
        </g>
        <g class="plx-layer" style="--plx-range:-30px"><path d="M408 214 l56 -56 M424 230 l56 -56 M440 246 l40 -40" style="stroke:var(--art-1)" stroke-width="6" stroke-linecap="round" opacity=".9" /></g>
      </template>
    </svg>
  </div>
</template>

<style scoped>
.game-art { position:absolute; inset:0; overflow:hidden; pointer-events:none; --art-1:var(--game-vivid, #8b7bff); --art-2:var(--game-vivid-2, #f472b6); }
.game-art svg { position:absolute; inset:-24px 0 -24px auto; width:min(100%, 640px); height:calc(100% + 48px); }
.art-blur { filter:blur(18px); }
.art-float { animation:art-float 7s var(--ease-in-out) infinite alternate; transform-box:fill-box; transform-origin:center; }
@keyframes art-float { from { transform:translateY(-4px); } to { transform:translateY(5px); } }
</style>
