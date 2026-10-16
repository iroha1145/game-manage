<script setup>
defineProps({data:{type:Object,required:true}})
</script>
<template>
 <div class="render-notice">
  <section class="cap-card" data-render-block><header class="cap-title"><h2>{{ data.title || '查询提示' }}</h2></header>
   <section v-for="(section,i) in data.sections || []" :key="i" class="notice-section" data-render-block>
    <h3 v-if="section.title" class="notice-heading">{{ section.title }}</h3>
    <ul class="item-list"><li v-for="(item,j) in section.items || []" :key="j" class="item" data-render-block><p class="notice-text">{{ item }}</p></li></ul>
   </section>
   <p v-for="(notice,i) in data.notices || []" :key="i" class="notice-text">{{ notice }}</p>
  </section>
 </div>
</template>
<style scoped>
.render-notice{display:grid;gap:12px}.notice-section{margin-top:12px}.notice-heading{font-size:14px;font-weight:500;color:var(--text)}.notice-text{font-size:13px;line-height:1.8;color:var(--text-body);overflow-wrap:anywhere}.item{padding:8px 0;border-bottom:1px solid var(--border)}.cap-title h2{font-size:15px;font-weight:500}
</style>
