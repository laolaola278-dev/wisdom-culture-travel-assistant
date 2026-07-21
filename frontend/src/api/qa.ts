import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { QAResponse, AgentInfo, Recommendation } from '../types/qa'

export async function askQuestion(question: string, options?: {
  session_id?: string
  use_agent?: boolean
}): Promise<QAResponse> {
  return api.post<QAResponse>(API_ENDPOINTS.qa.ask, { question, ...options })
}

export async function getAgents(): Promise<{ agents: AgentInfo[] }> {
  return api.get(API_ENDPOINTS.qa.agents)
}

export async function rateAnswer(historyId: number, score: number): Promise<void> {
  return api.post(API_ENDPOINTS.qa.feedback, { history_id: historyId, rating: score })
}

export async function getRecommendations(sessionId?: string): Promise<{
  recommendations: Recommendation[]
  user_profile?: Record<string, unknown>
}> {
  return api.get(API_ENDPOINTS.qa.recommend, sessionId ? { session_id: sessionId } : undefined)
}

export async function getHotQuestions(): Promise<{ questions: string[] }> {
  return api.get(API_ENDPOINTS.qa.hotQuestions)
}
