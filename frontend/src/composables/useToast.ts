/**
 * 轻量级 Toast 提示 Composable
 * 替代各 View 中分散的 errorMsg ref + 模板渲染模式
 */
import { ref, readonly } from 'vue'

export type ToastType = 'error' | 'success' | 'warning' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
}

let toastId = 0
// 模块级单例：所有调用方共享同一列表，ToastContainer 才能渲染到各视图推送的 toast
const toasts = ref<ToastItem[]>([])

export function useToast(autoDismissMs = 3000) {
  function show(message: string, type: ToastType = 'info') {
    const id = ++toastId
    toasts.value.push({ id, type, message })
    if (autoDismissMs > 0) {
      setTimeout(() => dismiss(id), autoDismissMs)
    }
    return id
  }

  function error(message: string) { return show(message, 'error') }
  function success(message: string) { return show(message, 'success') }
  function warning(message: string) { return show(message, 'warning') }
  function info(message: string) { return show(message, 'info') }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function clear() {
    toasts.value = []
  }

  return {
    toasts: readonly(toasts),
    show,
    error,
    success,
    warning,
    info,
    dismiss,
    clear,
  }
}
