/**
 * 错误处理 Composable
 * 抽取自各 View 中重复的 try/catch + error ref 模式
 */
import { ref } from 'vue'

export function useErrorHandler() {
  const error = ref('')
  const loading = ref(false)

  function setError(msg: string) {
    error.value = msg
  }

  function clearError() {
    error.value = ''
  }

  /**
   * 包装异步操作，自动管理 loading 和 error 状态
   * @param fn 异步函数
   * @param errorMsg 失败时的默认错误信息
   */
  async function withError<T>(fn: () => Promise<T>, errorMsg = '操作失败'): Promise<T | null> {
    loading.value = true
    error.value = ''
    try {
      return await fn()
    } catch (e) {
      error.value = errorMsg
      console.error(errorMsg, e)
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    error,
    loading,
    setError,
    clearError,
    withError,
  }
}
