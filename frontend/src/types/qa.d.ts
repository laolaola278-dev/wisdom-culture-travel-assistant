export interface QAResponse {
  question: string
  answer: string
  source: string
  agent?: string
  session_id?: string
  history_id?: number
  related_entities?: { name: string; type: string }[]
  routed_agent?: string
  version?: string
  agents_enabled?: boolean
}

export interface AgentInfo {
  name: string
  description: string
  confidence: number
}

export interface Recommendation {
  name: string
  type: string
  reason: string
}

export interface QAHistoryItem {
  id: number
  question: string
  answer: string
  agent_used: string | null
  sources: unknown
  rating?: number
  created_at: string
}

export interface QASession {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface QASessionDetail extends QASession {
  messages: QAHistoryItem[]
}
