/**
 * 主题管理 Composable
 * 支持 light / dark / system 三种模式
 * 持久化到 localStorage，监听系统主题变化
 */
import { ref, watch, onMounted } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'app-theme'
const theme = ref<ThemeMode>('system')

function applyTheme(mode: ThemeMode) {
  const isDark = mode === 'dark' || (
    mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches
  )
  document.documentElement.classList.toggle('dark', isDark)
}

export function useTheme() {
  onMounted(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
    if (saved) theme.value = saved
    applyTheme(theme.value)

    // 监听系统主题变化
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', () => {
      if (theme.value === 'system') applyTheme('system')
    })
  })

  watch(theme, (val) => {
    localStorage.setItem(STORAGE_KEY, val)
    applyTheme(val)
  })

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark')
    theme.value = isDark ? 'light' : 'dark'
  }

  function setTheme(mode: ThemeMode) {
    theme.value = mode
  }

  return {
    theme,
    toggleTheme,
    setTheme,
  }
}
