<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getFavorites, removeFavorite } from '../api/favorites'
import EmptyState from '../components/EmptyState.vue'
import type { Favorite } from '../types/common'

const auth = useAuthStore()
const favorites = ref<Favorite[]>([])
const loading = ref(false)
const error = ref('')

async function loadFavorites() {
  error.value = ''
  if (!auth.isLoggedIn) {
    return
  }
  loading.value = true
  try {
    const data = await getFavorites()
    favorites.value = data.favorites || []
  } catch {
    error.value = '加载收藏失败'
  } finally {
    loading.value = false
  }
}

async function doRemove(item: Favorite) {
  error.value = ''
  try {
    await removeFavorite({ type: item.type, id: item.id })
    favorites.value = favorites.value.filter(f => f.id !== item.id)
  } catch {
    error.value = '取消收藏失败'
  }
}

onMounted(loadFavorites)
</script>

<template>
  <div class="favorites-page">
    <!-- 页头 -->
    <div class="page-header">
      <h1 class="page-title">我的收藏</h1>
      <p class="page-desc">{{ favorites.length > 0 ? `共 ${favorites.length} 项收藏` : '管理您感兴趣的景点与问答' }}</p>
    </div>

    <!-- 错误横幅独立渲染，不遮蔽列表/空态/登录提示 -->
    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- 未登录 -->
    <EmptyState
      v-if="!auth.isLoggedIn"
      icon="🔒"
      title="请先登录"
      description="登录后可收藏和管理您感兴趣的景点与问答"
    />

    <!-- 加载骨架 -->
    <div v-else-if="loading" class="fav-grid">
      <div v-for="i in 4" :key="i" class="fav-card">
        <div class="skeleton" style="height:20px;width:60px;margin-bottom:12px;"></div>
        <div class="skeleton" style="height:16px;width:70%;"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <EmptyState
      v-else-if="favorites.length === 0"
      icon="⭐"
      title="暂无收藏"
      description="去探索页面发现有趣的内容吧"
    />

    <!-- 收藏列表 -->
    <div v-else class="fav-grid">
      <div v-for="item in favorites" :key="item.id" class="fav-card">
        <div class="fav-card-header">
          <span class="fav-type">{{ item.type || '收藏' }}</span>
          <button class="remove-btn" @click="doRemove(item)" title="取消收藏">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
        <div class="fav-name">{{ item.name || item.type }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.favorites-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.page-header { margin-bottom: var(--space-1); }
.page-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.page-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.error-banner {
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: var(--radius-md);
}

.fav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-4);
}

.fav-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  transition: all var(--duration-fast) var(--ease-default);
}
.fav-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.fav-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.fav-type {
  display: inline-block;
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--primary-600);
  background: var(--surface-selected);
  border-radius: var(--radius-xs);
}
.dark .fav-type { color: var(--primary-300); }

.remove-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-xs);
  color: var(--text-quaternary);
  transition: all var(--duration-fast) var(--ease-default);
}
.remove-btn:hover {
  color: var(--error-text);
  background: var(--error-bg);
}

.fav-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  line-height: var(--leading-relaxed);
}
</style>
