/**
 * 统一 API 客户端
 * 所有 HTTP 请求的唯一入口，自动处理 Token 注入、401 刷新、错误提示
 */
import { APP_CONFIG } from '../constants/appConfig'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

interface RequestOptions {
  params?: Record<string, string | number | boolean | undefined>
  body?: unknown
  headers?: Record<string, string>
  /** 跳过自动 Token 注入 */
  skipAuth?: boolean
}

class ApiClient {
  private baseURL: string
  /** 单飞刷新：并发 401 共享同一个 refresh 请求 */
  private refreshPromise: Promise<boolean> | null = null

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  private getToken(): string | null {
    return localStorage.getItem(APP_CONFIG.tokenStorageKey)
  }

  /** 匿名设备指纹：后端按 X-Device-Fingerprint 关联匿名会话/历史 */
  private getFingerprint(): string {
    let fp = localStorage.getItem(APP_CONFIG.fingerprintStorageKey)
    if (!fp) {
      fp = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`)
      localStorage.setItem(APP_CONFIG.fingerprintStorageKey, fp)
    }
    return fp
  }

  private buildURL(path: string, params?: RequestOptions['params']): string {
    const url = new URL(`${this.baseURL}${path}`, window.location.origin)
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null) {
          url.searchParams.set(key, String(val))
        }
      })
    }
    return url.pathname + url.search
  }

  async request<T = unknown>(
    method: HttpMethod,
    path: string,
    options?: RequestOptions,
  ): Promise<T> {
    const url = this.buildURL(path, options?.params)
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Device-Fingerprint': this.getFingerprint(),
      ...options?.headers,
    }

    if (!options?.skipAuth) {
      const token = this.getToken()
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
    }

    const res = await fetch(url, {
      method,
      headers,
      body: options?.body ? JSON.stringify(options.body) : undefined,
    })

    // 401: 尝试刷新 Token
    if (res.status === 401 && !options?.skipAuth) {
      const refreshed = await this._tryRefreshToken()
      if (refreshed) {
        // 重试原请求；重试失败按真实错误处理，不能误判为会话过期
        const newToken = this.getToken()
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`
        }
        const retryRes = await fetch(url, {
          method,
          headers,
          body: options?.body ? JSON.stringify(options.body) : undefined,
        })
        if (retryRes.ok) {
          if (retryRes.status === 204) return undefined as T
          return retryRes.json()
        }
        if (retryRes.status !== 401) {
          const err = await retryRes.json().catch(() => ({ error: `API ${retryRes.status}` }))
          throw new Error(err.error || `API ${retryRes.status}`)
        }
      }
      // 刷新失败，清除认证并通知 store（避免 Pinia 状态与 localStorage 脱同步）
      localStorage.removeItem(APP_CONFIG.tokenStorageKey)
      localStorage.removeItem(APP_CONFIG.refreshTokenStorageKey)
      window.dispatchEvent(new CustomEvent('auth:expired'))
      throw new Error('登录已过期，请重新登录')
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `API ${res.status}` }))
      throw new Error(err.error || `API ${res.status}`)
    }

    // 204 No Content
    if (res.status === 204) return undefined as T
    return res.json()
  }

  private _tryRefreshToken(): Promise<boolean> {
    // 并发 401 复用同一次刷新请求
    if (!this.refreshPromise) {
      this.refreshPromise = this._doRefresh().finally(() => {
        this.refreshPromise = null
      })
    }
    return this.refreshPromise
  }

  private async _doRefresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem(APP_CONFIG.refreshTokenStorageKey)
    if (!refreshToken) return false
    try {
      const res = await fetch(`${this.baseURL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${refreshToken}`,
        },
      })
      if (res.ok) {
        const data = await res.json()
        localStorage.setItem(APP_CONFIG.tokenStorageKey, data.access_token)
        window.dispatchEvent(new CustomEvent('auth:refreshed', { detail: data.access_token }))
        return true
      }
    } catch {
      /* refresh failed */
    }
    return false
  }

  // 便捷方法
  get<T = unknown>(path: string, params?: RequestOptions['params']): Promise<T> {
    return this.request<T>('GET', path, { params })
  }

  post<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, { body })
  }

  put<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PUT', path, { body })
  }

  delete<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('DELETE', path, { body })
  }
}

export const api = new ApiClient('/api')
