<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { login as apiLogin, register as apiRegister } from '../api/auth'
import { useTheme } from '../composables/useTheme'
import Modal from './Modal.vue'

defineProps<{ activeTab: string }>()

const auth = useAuthStore()
const { theme, toggleTheme } = useTheme()

const showLogin = ref(false)
const showRegister = ref(false)
const username = ref('')
const password = ref('')
const email = ref('')
const errorMsg = ref('')
const loading = ref(false)

onMounted(() => {
  auth.fetchMe()
})

async function doLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    const data = await apiLogin(username.value, password.value)
    auth.setTokens(data.access_token, data.refresh_token)
    auth.setUser(data.user)
    showLogin.value = false
    username.value = ''
    password.value = ''
  } catch (e) {
    // 透传后端真实错误（限流/账户禁用/服务不可用等），避免误导为密码错误
    errorMsg.value = (e as Error).message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  errorMsg.value = ''
  loading.value = true
  try {
    await apiRegister(username.value, email.value, password.value)
    showRegister.value = false
    showLogin.value = true
    errorMsg.value = '注册成功，请登录'
  } catch (e) {
    errorMsg.value = (e as Error).message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}

function logout() {
  auth.logout()
}

function switchToRegister() {
  showLogin.value = false
  showRegister.value = true
  errorMsg.value = ''
}

function switchToLogin() {
  showRegister.value = false
  showLogin.value = true
  errorMsg.value = ''
}
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <!-- Logo -->
      <router-link to="/" class="logo">
        <span class="logo-mark">白</span>
        <div class="logo-text">
          <span class="logo-title">白云文旅</span>
          <span class="logo-sub">智慧文旅智能问答平台</span>
        </div>
      </router-link>

      <!-- 导航 -->
      <nav class="nav">
        <router-link to="/" class="nav-item" :class="{ active: activeTab === 'qa' }">问答</router-link>
        <router-link to="/graph" class="nav-item" :class="{ active: activeTab === 'graph' }">知识图谱</router-link>
        <router-link to="/explore" class="nav-item" :class="{ active: activeTab === 'explore' }">探索</router-link>
        <router-link to="/map3d" class="nav-item" :class="{ active: activeTab === 'map3d' }">3D地图</router-link>
        <router-link to="/stats" class="nav-item" :class="{ active: activeTab === 'stats' }">数据</router-link>
        <router-link to="/history" class="nav-item" :class="{ active: activeTab === 'history' }">历史</router-link>
        <router-link to="/favorites" class="nav-item" :class="{ active: activeTab === 'favorites' }">收藏</router-link>
      </nav>

      <!-- 右侧操作 -->
      <div class="actions">
        <!-- 主题切换 -->
        <button class="icon-btn" @click="toggleTheme" :title="theme === 'dark' ? '切换到浅色' : '切换到深色'">
          <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>

        <!-- 用户区 -->
        <template v-if="auth.isLoggedIn && auth.user">
          <div class="user-chip">
            <div class="avatar">{{ auth.user.username.charAt(0).toUpperCase() }}</div>
            <span class="user-name">{{ auth.user.username }}</span>
          </div>
          <button class="btn btn-secondary btn-sm" @click="logout">退出</button>
        </template>
        <template v-else>
          <button class="btn btn-primary btn-sm" @click="showLogin = true">登录</button>
        </template>
      </div>
    </div>
  </header>

  <!-- 登录 Modal -->
  <Modal v-model="showLogin" title="登录" width="380px">
    <div class="form-stack">
      <div class="form-field">
        <label class="form-label">用户名</label>
        <input v-model="username" placeholder="请输入用户名" class="input" @keyup.enter="doLogin" />
      </div>
      <div class="form-field">
        <label class="form-label">密码</label>
        <input v-model="password" type="password" placeholder="请输入密码" class="input" @keyup.enter="doLogin" />
      </div>
      <p v-if="errorMsg" class="form-error">{{ errorMsg }}</p>
    </div>
    <template #footer>
      <button class="btn btn-secondary" @click="switchToRegister">注册账号</button>
      <button class="btn btn-primary" @click="doLogin" :disabled="loading">
        <span v-if="loading" class="loading-spinner" style="width:14px;height:14px;border-width:2px;" />
        {{ loading ? '登录中' : '登录' }}
      </button>
    </template>
  </Modal>

  <!-- 注册 Modal -->
  <Modal v-model="showRegister" title="注册账号" width="380px">
    <div class="form-stack">
      <div class="form-field">
        <label class="form-label">用户名</label>
        <input v-model="username" placeholder="请输入用户名" class="input" />
      </div>
      <div class="form-field">
        <label class="form-label">邮箱</label>
        <input v-model="email" type="email" placeholder="请输入邮箱" class="input" />
      </div>
      <div class="form-field">
        <label class="form-label">密码</label>
        <input v-model="password" type="password" placeholder="至少8位" class="input" />
      </div>
      <p v-if="errorMsg" class="form-error">{{ errorMsg }}</p>
    </div>
    <template #footer>
      <button class="btn btn-secondary" @click="switchToLogin">已有账号？登录</button>
      <button class="btn btn-primary" @click="doRegister" :disabled="loading">
        <span v-if="loading" class="loading-spinner" style="width:14px;height:14px;border-width:2px;" />
        {{ loading ? '注册中' : '注册' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: var(--z-header);
  height: var(--header-height);
  background: var(--bg-canvas);
  border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(12px);
}

.header-inner {
  max-width: var(--content-max-width);
  height: 100%;
  margin: 0 auto;
  padding: 0 var(--space-6);
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.logo-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--primary-500);
  color: var(--text-on-primary);
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  border-radius: var(--radius-md);
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.logo-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
}

.logo-sub {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: var(--tracking-wide);
}

/* 导航 */
.nav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}
.nav::-webkit-scrollbar { display: none; }

.nav-item {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-default);
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
}

.nav-item.active {
  color: var(--primary-600);
  background: var(--surface-selected);
}
.dark .nav-item.active {
  color: var(--primary-300);
}

/* 右侧操作 */
.actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-default);
}
.icon-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2) var(--space-1) var(--space-1);
  border-radius: var(--radius-full);
  transition: background var(--duration-fast) var(--ease-default);
}
.user-chip:hover {
  background: var(--surface-hover);
}

.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: var(--primary-500);
  color: var(--text-on-primary);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-full);
}

.user-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

/* 表单 */
.form-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.form-error {
  font-size: var(--text-sm);
  color: var(--error-text);
  background: var(--error-bg);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--error-border);
}
</style>
