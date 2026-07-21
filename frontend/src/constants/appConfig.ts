/** 应用级常量 */

export const APP_CONFIG = {
  /** 请求超时（毫秒） */
  requestTimeout: 15000,
  /** 默认分页大小 */
  defaultPageSize: 20,
  /** Token 存储键名 */
  tokenStorageKey: 'access_token',
  refreshTokenStorageKey: 'refresh_token',
  /** 匿名设备指纹存储键名 */
  fingerprintStorageKey: 'device_fingerprint',
  /** 问答限流（每分钟） */
  qaRateLimit: 10,
} as const
