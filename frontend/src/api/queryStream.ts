import { apiClient } from './client'

export interface StreamCitation {
  doc_id: string
  snippet: string
  filename?: string | null
}

export interface StreamMeta {
  session_id: string
  decision: 'allow' | 'deny'
  deny_reason: string | null
  citations: StreamCitation[]
}

interface Handlers {
  sessionId?: string | null
  onMeta: (meta: StreamMeta) => void
  onDelta: (text: string) => void
  signal?: AbortSignal
}

/**
 * POST /api/query/text/stream and read the Server-Sent Events as they arrive:
 * `meta` (decision + citations, sent before any generation), `delta` (answer
 * text pieces) and `done`. axios cannot stream in the browser, so this uses fetch.
 */
export async function streamTextQuery(question: string, { sessionId, onMeta, onDelta, signal }: Handlers): Promise<void> {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`${apiClient.defaults.baseURL}/api/query/text/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ question, session_id: sessionId ?? null }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`stream request failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const dispatch = (block: string) => {
    let event = ''
    let data = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!event || !data) return
    const payload = JSON.parse(data)
    if (event === 'meta') onMeta(payload as StreamMeta)
    else if (event === 'delta') onDelta((payload as { text: string }).text)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      dispatch(buffer.slice(0, sep))
      buffer = buffer.slice(sep + 2)
      sep = buffer.indexOf('\n\n')
    }
  }
  if (buffer.trim()) dispatch(buffer)
}
