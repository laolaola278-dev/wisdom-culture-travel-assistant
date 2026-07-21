/**
 * 评分逻辑 Composable
 * 抽取自 QAView.vue 和 HistoryView.vue 中重复的评分代码
 */
import { ref } from 'vue'
import { rateAnswer } from '../api/qa'

export function useRating() {
  const ratedIds = ref<Set<number>>(new Set())
  const ratingLoading = ref(false)
  const ratingError = ref('')

  async function doRate(historyId: number, rating: number) {
    if (!historyId || ratedIds.value.has(historyId)) return
    ratingLoading.value = true
    ratingError.value = ''
    try {
      await rateAnswer(historyId, rating)
      ratedIds.value.add(historyId)
      // 触发响应式更新
      ratedIds.value = new Set(ratedIds.value)
    } catch (e) {
      ratingError.value = '评价失败'
      console.warn('评价失败', e)
    } finally {
      ratingLoading.value = false
    }
  }

  function isRated(historyId: number): boolean {
    return ratedIds.value.has(historyId)
  }

  return {
    ratedIds,
    ratingLoading,
    ratingError,
    doRate,
    isRated,
  }
}
