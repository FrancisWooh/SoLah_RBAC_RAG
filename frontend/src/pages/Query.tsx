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
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'

import { apiClient } from '../api/client'
import { deleteSession, getSession, listSessions } from '../api/chat'
import type { ChatCitation, ChatSessionSummary } from '../api/chat'
import { streamTextQuery } from '../api/queryStream'
import { useAuth } from '../auth/AuthContext'
import RoleRequestPanel from '../components/RoleRequestPanel'

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
    ['今天', []],
    ['昨天', []],
    ['7 天内', []],
    ['更早', []],
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
      message.error('会话加载失败')
      refreshSessions()
    }
  }

  const removeSession = async (id: string) => {
    try {
      await deleteSession(id)
      if (id === sessionId) newChat()
      refreshSessions()
    } catch {
      message.error('删除失败')
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
        setError('查询失败，请稍后重试')
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
        { role: 'user', content: `🖼 ${(file as File).name ?? '图片'}` },
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
      setError('图片识别/查询失败，请稍后重试')
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
        placeholder="向知识库提问，例如：KYC/AML 审核标准是什么？"
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
          <button type="button" className="icon-btn" title="上传图片查询" disabled={busy}>
            <PaperClipOutlined />
          </button>
        </Upload>
        <button type="button" className="send-btn" onClick={send} disabled={busy || !question.trim()} title="发送">
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
            <SafetyCertificateOutlined /> RBAC 知识库
          </span>
          <button type="button" className="icon-btn" onClick={() => setCollapsed(true)} title="收起侧栏">
            <MenuFoldOutlined />
          </button>
        </div>
        <button type="button" className="new-chat-btn" onClick={newChat}>
          <PlusCircleOutlined /> New chat
        </button>
        <div className="chat-history">
          {grouped.length === 0 && <div className="chat-history-empty">暂无历史会话</div>}
          {grouped.map(([label, items]) => (
            <div key={label}>
              <div className="chat-history-group">{label}</div>
              {items.map((s) => (
                <div
                  key={s.id}
                  className={`chat-history-item${s.id === sessionId ? ' active' : ''}`}
                  onClick={() => openSession(s.id)}
                  title={s.title}
                >
                  <span className="chat-history-title">{s.title}</span>
                  <Popconfirm
                    title="删除这个会话？"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={(e) => {
                      e?.stopPropagation()
                      removeSession(s.id)
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <button type="button" className="icon-btn del" onClick={(e) => e.stopPropagation()} title="删除">
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
                { key: 'roles', icon: <UserSwitchOutlined />, label: '申请角色' },
                ...(user.effective_roles.includes('platform_admin')
                  ? [{ key: 'admin', icon: <SettingOutlined />, label: '管理后台' }]
                  : []),
                { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
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
          <button type="button" className="icon-btn chat-expand" onClick={() => setCollapsed(false)} title="展开侧栏">
            <MenuUnfoldOutlined />
          </button>
        )}

        {isEmpty ? (
          <div className="chat-empty">
            <h1>
              <SafetyCertificateOutlined /> 想了解点什么？
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

      <Modal title="申请角色" open={roleModal} onCancel={() => setRoleModal(false)} footer={null} width={720} destroyOnClose>
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

function AssistantMessage({ turn, streaming, waiting }: { turn: Turn; streaming: boolean; waiting: boolean }) {
  if (turn.decision === 'deny') {
    return (
      <div className="msg-assistant">
        <Alert
          type="error"
          showIcon
          message="无权限访问该内容"
          description={turn.deny_reason ?? '当前角色未被授权查看相关文档，此次尝试已记录到审计日志。'}
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
          message="图片识别结果"
          description={turn.recognized_text || '（未识别出文字）'}
        />
      )}
      <div className="answer-md" data-testid="answer">
        {turn.content ? <ReactMarkdown>{inlineFilenames(turn.content, names)}</ReactMarkdown> : waiting ? '正在生成回答…' : ''}
        {streaming && turn.content ? <span className="answer-cursor">▍</span> : null}
      </div>
      {sources.length > 0 && (
        <div className="msg-sources">
          <span>来源：</span>
          {sources.map(([id, name]) => (
            <Tag key={id}>{name}</Tag>
          ))}
        </div>
      )}
    </div>
  )
}
