import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { QASession, QASessionDetail } from '../types/qa'

export async function getSessions(): Promise<{ sessions: QASession[]; total: number }> {
  return api.get(API_ENDPOINTS.history.sessions)
}

export async function getSessionDetail(id: string): Promise<QASessionDetail> {
  return api.get<QASessionDetail>(API_ENDPOINTS.history.sessionDetail(id))
}

export async function deleteSession(id: string): Promise<void> {
  return api.delete(API_ENDPOINTS.history.deleteSession(id))
}

export async function updateSessionTitle(id: string, title: string): Promise<void> {
  return api.put(API_ENDPOINTS.history.updateTitle(id), { title })
}
