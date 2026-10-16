import { apiClient } from './client'

export interface ChatCitation {
  doc_id: string
  snippet: string
  filename?: string | null
  source_type?: 'file' | 'db' | null
}

export interface ChatSessionSummary {
  id: string
  title: string
  updated_at: string
}

export interface ChatMessageOut {
  id: number
  role: 'user' | 'assistant'
  content: string
  decision: 'allow' | 'deny' | null
  deny_reason: string | null
  citations: ChatCitation[] | null
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessageOut[]
}

export const listSessions = async () => (await apiClient.get<ChatSessionSummary[]>('/api/chat/sessions')).data
export const getSession = async (id: string) => (await apiClient.get<ChatSessionDetail>(`/api/chat/sessions/${id}`)).data
export const deleteSession = async (id: string) => {
  await apiClient.delete(`/api/chat/sessions/${id}`)
}
