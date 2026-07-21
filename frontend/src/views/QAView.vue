<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { askQuestion, getAgents, getRecommendations } from '../api/qa'
import { api } from '../api/client'
import { useRating } from '../composables/useRating'
import { useSystemStatus } from '../composables/useSystemStatus'
import type { AgentInfo, Recommendation } from '../types/qa'

const question = ref('')
const messages = ref<{ role: string; content: string; historyId?: number }[]>([])
const loading = ref(false)
const sessionId = ref<string | undefined>()
const agents = ref<AgentInfo[]>([])
const recommendations = ref<Recommendation[]>([])
const routedAgent = ref('')
const notice = ref('')
const chatAreaRef = ref<HTMLElement | null>(null)

const { ratedIds, doRate } = useRating()
const { llmEnabled, llmProvider, checkHealth } = useSystemStatus()

onMounted(async () => {
  try {
    const a = await getAgents()
    agents.value = a.agents
  } catch {
    console.warn('获取智能体列表失败')
  }
  try {
    const data = await api.get<{ notice?: string }>('/notice')
    notice.value = data.notice || ''
  } catch {
    /* ignore */
  }
  // 后台检查 LLM 状态
  checkHealth()
})

async function send() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  messages.value.push({ role: 'user', content: q })
  question.value = ''
  await scrollToBottom()
  try {
    const res = await askQuestion(q, { session_id: sessionId.value, use_agent: true })
    sessionId.value = res.session_id
    routedAgent.value = res.routed_agent || res.agent || ''
    messages.value.push({ role: 'assistant', content: res.answer, historyId: res.history_id })
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求失败，请稍后重试。' })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
  // 推荐失败不影响问答结果，独立处理不落入上方 catch
  if (sessionId.value) {
    getRecommendations(sessionId.value)
      .then(recs => { recommendations.value = recs.recommendations || [] })
      .catch(() => { /* 推荐服务不可用时静默 */ })
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatAreaRef.value) {
    chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
  }
}

watch(messages, () => scrollToBottom(), { deep: true })

function useRec(name: string) {
  question.value = name
}
</script>

<template>
  <div class="qa-page">
    <!-- LLM 未配置提示 -->
    <Transition name="fade">
      <div v-if="!llmEnabled" class="llm-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div class="llm-banner-text">
          <strong>当前为本地知识图谱模式</strong>
          <span>问答将返回结构化检索结果，未启用 {{ llmProvider || 'DeepSeek' }} 自然语言生成。请在 <code>.env</code> 配置 <code>DEEPSEEK_API_KEY</code> 后重启后端以获得更智能的回答。</span>
        </div>
      </div>
    </Transition>

    <!-- 公告条 -->
    <div v-if="notice" class="notice">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 11l19-9-9 19-2-8-8-2z"/>
      </svg>
      <span>{{ notice }}</span>
    </div>

    <!-- 顶部标题区 -->
    <div class="qa-header">
      <div class="header-left">
        <h1 class="page-title">智能问答</h1>
        <p class="page-desc">多智能体驱动 · Hybrid RAG · 个性化推荐</p>
      </div>
      <div v-if="routedAgent" class="agent-chip">
        <span class="agent-dot"></span>
        <span>{{ routedAgent }}</span>
      </div>
    </div>

    <!-- 对话区 -->
    <div ref="chatAreaRef" class="chat-area">
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="empty-icon-wrap">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <h3 class="empty-title">开始对话</h3>
        <p class="empty-desc">输入您的问题，AI 智能助手将为您解答白云区文旅相关问题</p>
        <div class="empty-suggestions">
          <button v-for="s in ['白云山有什么历史文化？', '推荐一条文化体验路线', '白云区有哪些非遗项目？']" :key="s" class="suggestion-chip" @click="question = s; send()">
            {{ s }}
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-for="(msg, idx) in messages" :key="idx" :class="['msg', msg.role]">
        <!-- 头像 -->
        <div class="msg-avatar" :class="msg.role">
          <span v-if="msg.role === 'user'">你</span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 8V4H8"/><rect x="4" y="8" width="16" height="12" rx="2"/>
            <path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>
          </svg>
        </div>
        <div class="msg-content">
          <div class="msg-bubble">{{ msg.content }}</div>
          <!-- 评分 -->
          <div v-if="msg.role === 'assistant' && msg.historyId" class="msg-rating">
            <template v-if="!ratedIds.has(msg.historyId)">
              <span class="rating-label">有帮助吗？</span>
              <div class="rating-stars">
                <button v-for="n in 5" :key="n" class="star-btn" @click="doRate(msg.historyId!, n)" :title="`${n}星`">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                  </svg>
                </button>
              </div>
            </template>
            <span v-else class="rated-text">✓ 已评价</span>
          </div>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="loading" class="msg assistant">
        <div class="msg-avatar assistant">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 8V4H8"/><rect x="4" y="8" width="16" height="12" rx="2"/>
            <path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>
          </svg>
        </div>
        <div class="msg-content">
          <div class="typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 推荐区 -->
    <Transition name="fade">
      <div v-if="recommendations.length" class="recommendations">
        <span class="rec-label">相关推荐</span>
        <button v-for="r in recommendations" :key="r.name" class="rec-chip" @click="useRec(r.name)">{{ r.name }}</button>
      </div>
    </Transition>

    <!-- 输入区 -->
    <div class="input-area">
      <div class="input-wrap">
        <textarea
          v-model="question"
          placeholder="输入您的问题..."
          rows="1"
          class="chat-input"
          @keydown.enter.exact.prevent="!($event as KeyboardEvent).isComposing && send()"
        />
        <button class="send-btn" :disabled="loading || !question.trim()" @click="send">
          <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span v-else class="loading-spinner" style="width:16px;height:16px;border-width:2px;" />
        </button>
      </div>
      <p class="input-hint">按 Enter 发送 · Shift+Enter 换行</p>
    </div>
  </div>
</template>

<style scoped>
.qa-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* LLM 未配置提示 */
.llm-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
  color: var(--warning-text);
}
.llm-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.llm-banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}
.llm-banner-text strong {
  font-weight: var(--font-semibold);
  color: var(--warning-text);
}
.llm-banner-text code {
  padding: 0 var(--space-1);
  background: var(--bg-muted);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

/* 公告 */
.notice {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--warning-bg);
  color: var(--warning-text);
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--warning-border);
}

/* 标题 */
.qa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}

.page-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}

.page-desc {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--surface-selected);
  color: var(--primary-600);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  border-radius: var(--radius-full);
}
.dark .agent-chip { color: var(--primary-300); }

.agent-dot {
  width: 6px;
  height: 6px;
  background: var(--primary-500);
  border-radius: var(--radius-full);
  animation: pulse 2s infinite;
}

/* 对话区 */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}

/* 空状态 */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.empty-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: var(--surface-selected);
  color: var(--primary-500);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
}

.empty-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.empty-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-5);
}

.empty-suggestions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.suggestion-chip {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: var(--surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-default);
}
.suggestion-chip:hover {
  color: var(--primary-600);
  border-color: var(--primary-500);
  background: var(--surface-selected);
}
.dark .suggestion-chip:hover { color: var(--primary-300); }

/* 消息 */
.msg {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  animation: fadeInUp var(--duration-slow) var(--ease-out);
}
.msg.user { flex-direction: row-reverse; }

.msg-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}
.msg-avatar.user {
  background: var(--primary-500);
  color: var(--text-on-primary);
}
.msg-avatar.assistant {
  background: var(--bg-muted);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
}

.msg-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
}
.msg.user .msg-content { align-items: flex-end; }

.msg-bubble {
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.user .msg-bubble {
  background: var(--primary-500);
  color: var(--text-on-primary);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-xs) var(--radius-lg);
}
.msg.assistant .msg-bubble {
  background: var(--surface-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-xs);
}

/* 评分 */
.msg-rating {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: 0 var(--space-1);
}

.rating-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.rating-stars {
  display: flex;
  gap: 2px;
}

.star-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-xs);
  color: var(--text-quaternary);
  transition: all var(--duration-fast) var(--ease-default);
}
.star-btn:hover {
  color: #f59e0b;
  background: var(--warning-bg);
}

.rated-text {
  font-size: var(--text-xs);
  color: var(--success-text);
}

/* 打字动画 */
.typing {
  display: flex;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
  background: var(--surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-xs);
}
.typing span {
  width: 6px;
  height: 6px;
  background: var(--text-quaternary);
  border-radius: var(--radius-full);
  animation: bounce 1.4s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }

/* 推荐 */
.recommendations {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-top: 1px solid var(--border-subtle);
  overflow-x: auto;
  scrollbar-width: none;
}
.recommendations::-webkit-scrollbar { display: none; }

.rec-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
}

.rec-chip {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-default);
}
.rec-chip:hover {
  color: var(--primary-600);
  border-color: var(--primary-500);
}
.dark .rec-chip:hover { color: var(--primary-300); }

/* 输入区 */
.input-area {
  padding: var(--space-3) var(--space-5) var(--space-4);
  border-top: 1px solid var(--border-default);
}

.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  background: var(--surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-1);
  transition: border-color var(--duration-fast) var(--ease-default);
}
.input-wrap:focus-within {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-focus);
}

.chat-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  max-height: 120px;
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--primary-500);
  color: var(--text-on-primary);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-default);
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  background: var(--primary-600);
}
.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-hint {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
  text-align: right;
  margin-top: var(--space-2);
}
</style>
