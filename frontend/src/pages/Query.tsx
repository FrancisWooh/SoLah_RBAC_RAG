import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowUpOutlined,
  DeleteOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PaperClipOutlined,
  PlusCircleOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons'
import { Alert, Dropdown, Modal, Popconfirm, Tag, message } from 'antd'
import type { UploadRequestOption } from '@rc-component/upload'
import { Upload } from 'antd'
import { isAxiosError } from 'axios'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Space } from 'antd'

import { apiClient } from '../api/client'
import { deleteSession, getSession, listSessions } from '../api/chat'
import type { ChatCitation, ChatSessionSummary } from '../api/chat'
import { streamTextQuery } from '../api/queryStream'
import { useAuth } from '../auth/AuthContext'
import RoleRequestPanel from '../components/RoleRequestPanel'
import LanguageSwitcher from '../components/LanguageSwitcher'

interface Turn {
  role: 'user' | 'assistant'
  content: string
  decision?: 'allow' | 'deny' | null
  deny_reason?: string | null
  citations?: ChatCitation[]
  recognized_text?: string
}

interface ImageResponse {
  decision: 'allow' | 'deny'
  answer: string | null
  citations: ChatCitation[]
  deny_reason: string | null
  recognized_text: string
}

const DAY = 24 * 3600 * 1000

function groupSessions(sessions: ChatSessionSummary[]) {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  const groups: [string, ChatSessionSummary[]][] = [
    ['query.today', []],
    ['query.yesterday', []],
    ['query.last7Days', []],
    ['query.earlier', []],
  ]
  for (const s of sessions) {
    // the API returns naive UTC timestamps
    const t = new Date(s.updated_at + 'Z').getTime()
    const i = t >= startOfToday ? 0 : t >= startOfToday - DAY ? 1 : t >= startOfToday - 7 * DAY ? 2 : 3
    groups[i][1].push(s)
  }
  return groups.filter(([, items]) => items.length > 0)
}

export default function Query() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [roleModal, setRoleModal] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listSessions())
    } catch {
      /* the sidebar is best effort */
    }
  }, [])

  useEffect(() => {
    refreshSessions()
    return () => abortRef.current?.abort()
  }, [refreshSessions])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [turns])

  const newChat = () => {
    abortRef.current?.abort()
    setSessionId(null)
    setTurns([])
    setError(null)
    setBusy(false)
    setStreaming(false)
  }

  const openSession = async (id: string) => {
    if (id === sessionId) return
    abortRef.current?.abort()
    setBusy(false)
    setStreaming(false)
    setError(null)
    try {
      const detail = await getSession(id)
      setSessionId(id)
      setTurns(
        detail.messages.map((m) => ({
          role: m.role,
          content: m.content,
          decision: m.decision,
          deny_reason: m.deny_reason,
          citations: m.citations ?? [],
        })),
      )
    } catch {
      message.error(t('query.errorSessionLoad'))
      refreshSessions()
    }
  }

  const removeSession = async (id: string) => {
    try {
      await deleteSession(id)
      if (id === sessionId) newChat()
      refreshSessions()
    } catch {
      message.error(t('query.errorDelete'))
    }
  }

  const send = async () => {
    const text = question.trim()
    if (!text || busy) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setQuestion('')
    setError(null)
    setBusy(true)
    setTurns((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '', decision: null }])
    const patchLast = (fn: (t: Turn) => Turn) =>
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? fn(t) : t)))
    try {
      await streamTextQuery(text, {
        sessionId,
        signal: controller.signal,
        // meta arrives before any text: show the decision and the sources right away
        onMeta: (meta) => {
          setSessionId(meta.session_id)
          patchLast((t) => ({ ...t, decision: meta.decision, deny_reason: meta.deny_reason, citations: meta.citations }))
          setStreaming(meta.decision === 'allow')
        },
        onDelta: (delta) => patchLast((t) => ({ ...t, content: t.content + delta })),
      })
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setTurns((prev) => prev.slice(0, -1))
        setError(t('query.errorQuery'))
      }
    } finally {
      if (abortRef.current === controller) {
        setBusy(false)
        setStreaming(false)
        refreshSessions()
      }
    }
  }

  // Image queries are one-shot (not part of the stored conversation).
  const onUploadImage = async (options: UploadRequestOption) => {
    const { file, onSuccess, onError } = options
    setBusy(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file as Blob)
      // No explicit Content-Type: the browser must set its own multipart boundary.
      const { data } = await apiClient.post<ImageResponse>('/api/query/image', formData)
      setTurns((prev) => [
        ...prev,
        { role: 'user', content: `🖼 ${(file as File).name ?? t('query.imageLabel')}` },
        {
          role: 'assistant',
          content: data.answer ?? '',
          decision: data.decision,
          deny_reason: data.deny_reason,
          citations: data.citations,
          recognized_text: data.recognized_text,
        },
      ])
      onSuccess?.(data)
    } catch (err) {
      setError(t('query.errorImageQuery'))
      onError?.(err as Error)
    } finally {
      setBusy(false)
    }
  }

  const grouped = useMemo(() => groupSessions(sessions), [sessions])
  const isEmpty = turns.length === 0

  const composer = (
    <div className="chat-composer">
      <textarea
        value={question}
        rows={2}
        placeholder={t('query.placeholder')}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div className="chat-composer-actions">
        <Upload accept="image/*" showUploadList={false} customRequest={onUploadImage} disabled={busy}>
          <button type="button" className="icon-btn" title={t('query.uploadImage')} disabled={busy}>
            <PaperClipOutlined />
          </button>
        </Upload>
        <button type="button" className="send-btn" onClick={send} disabled={busy || !question.trim()} title={t('query.send')}>
          <ArrowUpOutlined />
        </button>
      </div>
    </div>
  )

  return (
    <div className="chat-shell">
      <aside className={`chat-sidebar${collapsed ? ' collapsed' : ''}`}>
        <div className="chat-sidebar-top">
          <span className="chat-brand">
            <SafetyCertificateOutlined /> {t('query.brand')}
          </span>
          <Space size={0}>
            <LanguageSwitcher />
            <button type="button" className="icon-btn" onClick={() => setCollapsed(true)} title={t('query.collapseSidebar')}>
              <MenuFoldOutlined />
            </button>
          </Space>
        </div>
        <button type="button" className="new-chat-btn" onClick={newChat}>
          <PlusCircleOutlined /> {t('query.newChat')}
        </button>
        <div className="chat-history">
          {grouped.length === 0 && <div className="chat-history-empty">{t('query.noHistory')}</div>}
          {grouped.map(([key, items]) => (
            <div key={key}>
              <div className="chat-history-group">{t(key)}</div>
              {items.map((s) => (
                <div
                  key={s.id}
                  className={`chat-history-item${s.id === sessionId ? ' active' : ''}`}
                  onClick={() => openSession(s.id)}
                  title={s.title}
                >
                  <span className="chat-history-title">{s.title}</span>
                  <Popconfirm
                    title={t('query.deleteSessionConfirm')}
                    okText={t('common.delete')}
                    cancelText={t('common.cancel')}
                    onConfirm={(e) => {
                      e?.stopPropagation()
                      removeSession(s.id)
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <button type="button" className="icon-btn del" onClick={(e) => e.stopPropagation()} title={t('common.delete')}>
                      <DeleteOutlined />
                    </button>
                  </Popconfirm>
                </div>
              ))}
            </div>
          ))}
        </div>
        {user && (
          <Dropdown
            placement="topLeft"
            trigger={['click']}
            menu={{
              items: [
                { key: 'info', disabled: true, label: `clearance ${user.clearance} · ${user.effective_roles.join(', ')}` },
                { key: 'roles', icon: <UserSwitchOutlined />, label: t('query.applyRole') },
                ...(user.effective_roles.includes('platform_admin')
                  ? [{ key: 'admin', icon: <SettingOutlined />, label: t('query.adminConsole') }]
                  : []),
                { key: 'logout', icon: <LogoutOutlined />, label: t('common.logout') },
              ],
              onClick: ({ key }) => {
                if (key === 'roles') setRoleModal(true)
                else if (key === 'admin') window.open(`${location.protocol}//${location.hostname}:5174`, '_blank') // management console is its own site
                else if (key === 'logout') {
                  logout()
                  navigate('/login')
                }
              },
            }}
          >
            <div className="chat-user">
              <span className="chat-avatar">{user.username.slice(0, 1).toUpperCase()}</span>
              <span className="chat-username">{user.username}</span>
              <span className="chat-user-dots">···</span>
            </div>
          </Dropdown>
        )}
      </aside>

      <main className="chat-main">
        {collapsed && (
          <button type="button" className="icon-btn chat-expand" onClick={() => setCollapsed(false)} title={t('query.expandSidebar')}>
            <MenuUnfoldOutlined />
          </button>
        )}

        {isEmpty ? (
          <div className="chat-empty">
            <h1>
              <SafetyCertificateOutlined /> {t('query.emptyHeading')}
            </h1>
            {composer}
            {error && <Alert style={{ marginTop: 16 }} type="error" message={error} showIcon />}
          </div>
        ) : (
          <>
            <div className="chat-thread">
              <div className="chat-thread-inner">
                {turns.map((t, i) =>
                  t.role === 'user' ? (
                    <div key={i} className="msg-user">
                      <div className="msg-user-bubble">{t.content}</div>
                    </div>
                  ) : (
                    <AssistantMessage key={i} turn={t} streaming={streaming && i === turns.length - 1} waiting={busy && i === turns.length - 1} />
                  ),
                )}
                {error && <Alert type="error" message={error} showIcon />}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className="chat-footer">{composer}</div>
          </>
        )}
      </main>

      <Modal title={t('query.roleModalTitle')} open={roleModal} onCancel={() => setRoleModal(false)} footer={null} width={720} destroyOnClose>
        <RoleRequestPanel />
      </Modal>
    </div>
  )
}

/** Swap inline `[doc_id]` / `【doc_id,第7节】` citations for the real file name
 *  (ids come from the turn's citations; unknown ids are left untouched). */
function inlineFilenames(text: string, names: Map<string, string>): string {
  return text.replace(/[[【]\s*(doc_[\w-]+)\s*(?:[,，]\s*([^\]】]*))?[\]】]/g, (m, id: string, extra?: string) => {
    const name = names.get(id)
    if (!name) return m
    return `[${name.replace(/_/g, '\\_')}${extra ? `，${extra.trim()}` : ''}]`
  })
}

/** Open the original file behind a citation. The window is opened synchronously (inside the
 *  click) so popup blockers allow it, then pointed at the short-lived link the API returns
 *  after its own permission check. */
async function openSource(docId: string, t: (k: string) => string) {
  const win = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<{ url: string }>(`/api/documents/${encodeURIComponent(docId)}/link`)
    if (win) win.location.href = data.url
    else window.location.href = data.url
  } catch (e) {
    win?.close()
    message.error(isAxiosError(e) && e.response?.status === 503 ? t('query.sourceNotConfigured') : t('query.sourceUnavailable'))
  }
}

function AssistantMessage({ turn, streaming, waiting }: { turn: Turn; streaming: boolean; waiting: boolean }) {
  const { t } = useTranslation()

  if (turn.decision === 'deny') {
    return (
      <div className="msg-assistant">
        <Alert
          type="error"
          showIcon
          message={t('query.noAccess')}
          description={turn.deny_reason ?? t('query.noAccessDesc')}
        />
      </div>
    )
  }
  const sources = [...new Map((turn.citations ?? []).map((c) => [c.doc_id, c.filename || c.doc_id])).entries()]
  const names = new Map(sources)
  return (
    <div className="msg-assistant">
      {turn.recognized_text !== undefined && (
        <Alert
          style={{ marginBottom: 8 }}
          type="info"
          showIcon
          message={t('query.imageRecognition')}
          description={turn.recognized_text || t('query.noTextRecognized')}
        />
      )}
      <div className="answer-md" data-testid="answer">
        {turn.content ? <ReactMarkdown>{inlineFilenames(turn.content, names)}</ReactMarkdown> : waiting ? t('query.generatingAnswer') : ''}
        {streaming && turn.content ? <span className="answer-cursor">▍</span> : null}
      </div>
      {sources.length > 0 && (
        <div className="msg-sources">
          <span>{t('query.sources')}</span>
          {sources.map(([id, name]) => (
            <Tag key={id} style={{ cursor: 'pointer' }} title={t('query.viewSource')} onClick={() => void openSource(id, t)}>
              {name}
            </Tag>
          ))}
        </div>
      )}
    </div>
  )
}
