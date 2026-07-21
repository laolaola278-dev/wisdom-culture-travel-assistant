<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getSessions, getSessionDetail, deleteSession } from '../api/history'
import { useRating } from '../composables/useRating'
import EmptyState from '../components/EmptyState.vue'
import type { QASession, QASessionDetail } from '../types/qa'

const auth = useAuthStore()
const sessions = ref<QASession[]>([])
const currentSession = ref<QASessionDetail | null>(null)
const loading = ref(false)
const error = ref('')

const { doRate, isRated } = useRating()

async function loadSessions() {
  loading.value = true
  error.value = ''
  try {
    const data = await getSessions()
    sessions.value = data.sessions || []
  } catch {
    error.value = '加载会话列表失败'
  } finally {
    loading.value = false
  }
}

async function loadSessionDetail(id: string) {
  try {
    currentSession.value = await getSessionDetail(id)
  } catch {
    error.value = '加载会话详情失败'
  }
}

async function doDeleteSession(id: string) {
  if (!confirm('确定删除此会话？')) return
  try {
    await deleteSession(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSession.value?.id === id) currentSession.value = null
  } catch {
    error.value = '删除失败'
  }
}

/** 评分并同步本地消息状态（模板按 msg.rating 渲染） */
async function rateMessage(msg: { id: number; rating?: number | null }, n: number) {
  await doRate(msg.id, n)
  if (isRated(msg.id)) {
    msg.rating = n
  }
}

onMounted(loadSessions)
</script>

<template>
  <div class="history-page">
    <!-- 页头 -->
    <div class="page-header">
      <h1 class="page-title">问答历史</h1>
      <p class="page-desc">查看您的历史问答记录</p>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div class="layout">
      <!-- 会话列表 -->
      <aside class="session-list">
        <!-- 加载骨架 -->
        <template v-if="loading">
          <div v-for="i in 4" :key="i" class="session-skeleton">
            <div class="skeleton" style="height:16px;width:80%;margin-bottom:8px;"></div>
            <div class="skeleton" style="height:12px;width:50%;"></div>
          </div>
        </template>

        <!-- 空状态 -->
        <EmptyState
          v-else-if="sessions.length === 0"
          :icon="auth.isLoggedIn ? '💬' : '🔒'"
          :title="auth.isLoggedIn ? '暂无历史记录' : '请先登录'"
          :description="auth.isLoggedIn ? '去首页开始提问吧' : '登录后可保存和查看历史问答记录'"
        />

        <!-- 会话卡片 -->
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentSession?.id === s.id }"
          @click="loadSessionDetail(s.id)"
        >
          <div class="session-info">
            <div class="session-title">{{ s.title }}</div>
            <div class="session-meta">
              <span>{{ new Date(s.updated_at).toLocaleDateString() }}</span>
              <span class="dot">·</span>
              <span>{{ s.message_count || 0 }} 条对话</span>
            </div>
          </div>
          <button class="delete-btn" @click.stop="doDeleteSession(s.id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </aside>

      <!-- 详情面板 -->
      <main class="detail-panel">
        <EmptyState
          v-if="!currentSession"
          icon="📋"
          title="选择一个会话"
          description="从左侧列表中选择会话查看详细对话内容"
        />

        <template v-else>
          <div class="detail-header">
            <h2 class="detail-title">{{ currentSession.title }}</h2>
            <span class="badge">{{ currentSession.messages?.length || 0 }} 条对话</span>
          </div>

          <div class="messages">
            <div v-for="msg in currentSession.messages" :key="msg.id" class="message">
              <!-- 问题 -->
              <div class="msg-row">
                <div class="msg-label user">问</div>
                <div class="msg-text">{{ msg.question }}</div>
              </div>
              <!-- 回答 -->
              <div class="msg-row">
                <div class="msg-label assistant">答</div>
                <div class="msg-text">{{ msg.answer }}</div>
              </div>
              <!-- 评分 -->
              <div class="msg-rating">
                <template v-if="msg.rating">
                  <span class="rated-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                    {{ msg.rating }}
                  </span>
                </template>
                <template v-else>
                  <span class="rating-prompt">评价回答：</span>
                  <div class="rating-stars">
                    <button v-for="n in 5" :key="n" class="star" @click="rateMessage(msg, n)" :title="`${n}星`">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.history-page {
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

.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--space-4);
  min-height: 500px;
}

/* 会话列表 */
.session-list {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.session-skeleton {
  padding: var(--space-3);
  margin-bottom: var(--space-2);
}

.session-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-default);
  margin-bottom: var(--space-1);
}
.session-item:hover {
  background: var(--surface-hover);
}
.session-item.active {
  background: var(--surface-selected);
}
.session-item.active .session-title {
  color: var(--primary-600);
}
.dark .session-item.active .session-title {
  color: var(--primary-300);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.dot { opacity: 0.5; }

.delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-xs);
  color: var(--text-quaternary);
  opacity: 0;
  transition: all var(--duration-fast) var(--ease-default);
  flex-shrink: 0;
}
.session-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover {
  color: var(--error-text);
  background: var(--error-bg);
}

/* 详情面板 */
.detail-panel {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  min-height: 400px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: var(--space-5);
}

.detail-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.messages {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.message {
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.message:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.msg-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.msg-label {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}
.msg-label.user {
  background: var(--surface-selected);
  color: var(--primary-600);
}
.dark .msg-label.user { color: var(--primary-300); }
.msg-label.assistant {
  background: var(--success-bg);
  color: var(--success-text);
}

.msg-text {
  flex: 1;
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
  white-space: pre-wrap;
}

.msg-rating {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-left: 36px;
  margin-top: var(--space-2);
}

.rating-prompt {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.rating-stars {
  display: flex;
  gap: 2px;
}

.star {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-xs);
  color: var(--text-quaternary);
  transition: all var(--duration-fast) var(--ease-default);
}
.star:hover {
  color: #f59e0b;
  background: var(--warning-bg);
}

.rated-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: #f59e0b;
  background: var(--warning-bg);
  border-radius: var(--radius-xs);
}
</style>
