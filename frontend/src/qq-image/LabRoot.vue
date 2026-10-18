<script setup>
import {computed} from 'vue'
import {viewModel} from './models.js'
import {schemes,imageWidth} from './designs.js'
import ReuseBody from './ReuseBody.vue'
const props=defineProps({input:Object})
const model=computed(()=>viewModel(props.input)),design=schemes[0]
const isExample=computed(()=>/合成|反馈示例|未绑定|未收录|无登录/.test(model.value.origin))
</script>
<template>
 <article class="lab-sheet dossier reuse" :class="'page-'+input.snapshot.kind" :style="{width:imageWidth(input)+'px'}">
  <header class="page-head head-dossier"><div class="dossier-brand"><span>游戏管家</span><span>{{model.game}} / {{design.label}}</span></div><h1>{{model.title}}</h1><div class="head-meta"><span class="command">{{model.command}}</span><span>{{model.asOf}}　快照</span></div></header>
  <p v-if="isExample" class="example-label">{{model.origin}}</p>
  <ReuseBody :input="input" />
  <footer class="page-footer"><span>游戏管家　{{model.game}}</span><span>发送“帮助”查看指令</span></footer>
 </article>
</template>
