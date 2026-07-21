/**
 * 系统状态 Composable
 * 启动时检查后端是否启用了真实 LLM（DeepSeek）
 */
import { ref } from 'vue'
import { api } from '../api/client'

const llmEnabled = ref(true)
const llmChecked = ref(false)
const llmProvider = ref('')

export function useSystemStatus() {
  async function checkHealth(): Promise<void> {
    try {
      const data = await api.get<{
        llm_enabled?: boolean
        llm_provider?: string
      }>('/health', undefined)
      llmEnabled.value = data.llm_enabled ?? true
      llmProvider.value = data.llm_provider || ''
    } catch {
      // 后端不可用时保持默认
    } finally {
      llmChecked.value = true
    }
  }

  return { llmEnabled, llmChecked, llmProvider, checkHealth }
}
