<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import HeaderNav from './components/HeaderNav.vue'
import ToastContainer from './components/ToastContainer.vue'

const route = useRoute()
const activeTab = computed(() => route.name as string || 'qa')
</script>

<template>
  <div class="app-container">
    <HeaderNav :active-tab="activeTab" />
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>
    <ToastContainer />
  </div>
</template>

<style>
/* App 级别样式由 styles/index.css 全局提供 */
</style>
