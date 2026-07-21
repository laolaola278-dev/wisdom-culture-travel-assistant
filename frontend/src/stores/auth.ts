import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { APP_CONFIG } from '../constants/appConfig'
import * as authApi from '../api/auth'
import type { User } from '../types/auth'

export { type User }

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(localStorage.getItem(APP_CONFIG.tokenStorageKey) || '')
  const refreshToken = ref<string>(localStorage.getItem(APP_CONFIG.refreshTokenStorageKey) || '')
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem(APP_CONFIG.tokenStorageKey, access)
    localStorage.setItem(APP_CONFIG.refreshTokenStorageKey, refresh)
  }

  function clearAuth() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem(APP_CONFIG.tokenStorageKey)
    localStorage.removeItem(APP_CONFIG.refreshTokenStorageKey)
  }

  function setUser(u: User) {
    user.value = u
  }

  async function fetchMe() {
    if (!accessToken.value) return
    try {
      const data = await authApi.fetchMe()
      user.value = data
    } catch {
      clearAuth()
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* ignore */
    }
    clearAuth()
  }

  // 与 ApiClient 保持同步：401 刷新失败 / 刷新成功时更新 store 状态
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:expired', () => clearAuth())
    window.addEventListener('auth:refreshed', (e) => {
      const token = (e as CustomEvent<string>).detail
      if (token) accessToken.value = token
    })
  }

  return {
    accessToken,
    refreshToken,
    user,
    isLoggedIn,
    setTokens,
    clearAuth,
    setUser,
    fetchMe,
    logout,
  }
})
