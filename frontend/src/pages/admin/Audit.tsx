import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Drawer,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'

import { apiClient } from '../../api/client'

const { Title, Text, Paragraph } = Typography

interface AuditLogOut {
  id: number
  event_type: string
  user_id: string | null
  input_type: string | null
  query_text: string | null
  decision: string | null
  deny_reason: string | null
  retrieved_doc_ids: string[]
  model_id: string | null
  latency_ms: number | null
  created_at: string
  record_hash: string | null
  [key: string]: unknown
}

interface ChainVerificationOut {
  ok: boolean
  rows_checked: number
  broken_at_id: number | null
  reason: string | null
}

export default function Audit() {
  const [logs, setLogs] = useState<AuditLogOut[]>([])
  const [loading, setLoading] = useState(false)
  const [eventType, setEventType] = useState<string | undefined>()
  const [decision, setDecision] = useState<string | undefined>()
  const [userId, setUserId] = useState('')
  const [selected, setSelected] = useState<AuditLogOut | null>(null)
  const [verification, setVerification] = useState<ChainVerificationOut | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { limit: '50' }
      if (eventType) params.event_type = eventType
      if (decision) params.decision = decision
      if (userId) params.user_id = userId
      const { data } = await apiClient.get<AuditLogOut[]>('/api/admin/audit/logs', { params })
      setLogs(data)
    } catch {
      message.error('加载审计日志失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onVerify = async () => {
    try {
      const { data } = await apiClient.get<ChainVerificationOut>('/api/admin/audit/verify')
      setVerification(data)
    } catch {
      message.error('校验失败')
    }
  }

  const onExport = (format: 'csv' | 'json') => {
    const token = localStorage.getItem('access_token')
    const params = new URLSearchParams({ format })
    if (eventType) params.set('event_type', eventType)
    if (decision) params.set('decision', decision)
    if (userId) params.set('user_id', userId)
    const url = `${apiClient.defaults.baseURL}/api/admin/audit/export?${params.toString()}`
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = `audit_logs.${format}`
        link.click()
      })
      .catch(() => message.error('导出失败'))
  }

  return (
    <div>
      <Title level={3}>审计日志</Title>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Card>
          <Space wrap>
            <Select
              style={{ width: 140 }}
              placeholder="事件类型"
              allowClear
              value={eventType}
              onChange={setEventType}
              options={[
                { value: 'query', label: 'query' },
                { value: 'role_grant', label: 'role_grant' },
                { value: 'role_revoke', label: 'role_revoke' },
              ]}
            />
            <Select
              style={{ width: 120 }}
              placeholder="决策"
              allowClear
              value={decision}
              onChange={setDecision}
              options={[
                { value: 'allow', label: 'allow' },
                { value: 'deny', label: 'deny' },
              ]}
            />
            <Input
              style={{ width: 280 }}
              placeholder="用户ID（可从角色管理页复制）"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
            <Button type="primary" loading={loading} onClick={load}>
              查询
            </Button>
            <Button onClick={() => onExport('csv')}>导出 CSV</Button>
            <Button onClick={() => onExport('json')}>导出 JSON</Button>
            <Button onClick={onVerify}>校验审计链完整性</Button>
          </Space>
        </Card>

        {verification && (
          <Alert
            type={verification.ok ? 'success' : 'error'}
            showIcon
            message={
              verification.ok
                ? `审计链完整，已校验 ${verification.rows_checked} 条记录，未发现篡改`
                : `审计链在第 ${verification.broken_at_id} 条记录处断裂：${verification.reason}`
            }
          />
        )}

        <Table
          rowKey="id"
          loading={loading}
          dataSource={logs}
          onRow={(row) => ({ onClick: () => setSelected(row) })}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 70 },
            { title: '时间', dataIndex: 'created_at', width: 180 },
            { title: '事件', dataIndex: 'event_type' },
            {
              title: '决策',
              dataIndex: 'decision',
              render: (v: string) =>
                v === 'deny' ? <Tag color="red">deny</Tag> : <Tag color="green">allow</Tag>,
            },
            { title: '查询内容', dataIndex: 'query_text', ellipsis: true },
            { title: '拒绝原因', dataIndex: 'deny_reason', ellipsis: true },
            { title: '延迟(ms)', dataIndex: 'latency_ms', width: 90 },
          ]}
        />
      </Space>

      <Drawer
        title={`审计日志详情 #${selected?.id ?? ''}`}
        open={!!selected}
        onClose={() => setSelected(null)}
        width={480}
      >
        {selected && (
          <Space direction="vertical">
            <Text strong>event_type</Text>
            <Text>{selected.event_type}</Text>
            <Text strong>user_id</Text>
            <Text copyable>{selected.user_id ?? '-'}</Text>
            <Text strong>decision</Text>
            <Text>{selected.decision}</Text>
            <Text strong>deny_reason</Text>
            <Text>{selected.deny_reason ?? '-'}</Text>
            <Text strong>query_text</Text>
            <Paragraph>{selected.query_text ?? '-'}</Paragraph>
            <Text strong>retrieved_doc_ids</Text>
            <Text>{selected.retrieved_doc_ids.join(', ') || '-'}</Text>
            <Text strong>record_hash</Text>
            <Paragraph copyable style={{ wordBreak: 'break-all' }}>
              {selected.record_hash}
            </Paragraph>
          </Space>
        )}
      </Drawer>
    </div>
  )
}
