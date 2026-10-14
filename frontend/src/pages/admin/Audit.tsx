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
import { useTranslation } from 'react-i18next'

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
  const { t } = useTranslation()
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
      message.error(t('admin.audit.loadError'))
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
      message.error(t('admin.audit.verifyError'))
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
      .catch(() => message.error(t('admin.audit.exportError')))
  }

  return (
    <div>
      <Title level={3}>{t('admin.audit.title')}</Title>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Card>
          <Space wrap>
            <Select
              style={{ width: 140 }}
              placeholder={t('admin.audit.phEventType')}
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
              placeholder={t('admin.audit.phDecision')}
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
              placeholder={t('admin.audit.phUserId')}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
            <Button type="primary" loading={loading} onClick={load}>
              {t('admin.audit.queryBtn')}
            </Button>
            <Button onClick={() => onExport('csv')}>{t('admin.audit.exportCsv')}</Button>
            <Button onClick={() => onExport('json')}>{t('admin.audit.exportJson')}</Button>
            <Button onClick={onVerify}>{t('admin.audit.verifyChain')}</Button>
          </Space>
        </Card>

        {verification && (
          <Alert
            type={verification.ok ? 'success' : 'error'}
            showIcon
            message={
              verification.ok
                ? t('admin.audit.chainOk', { count: verification.rows_checked })
                : t('admin.audit.chainBroken', { id: verification.broken_at_id, reason: verification.reason })
            }
          />
        )}

        <Table
          rowKey="id"
          loading={loading}
          dataSource={logs}
          onRow={(row) => ({ onClick: () => setSelected(row) })}
          columns={[
            { title: t('admin.audit.colId'), dataIndex: 'id', width: 70 },
            { title: t('admin.audit.colTime'), dataIndex: 'created_at', width: 180 },
            { title: t('admin.audit.colEvent'), dataIndex: 'event_type' },
            {
              title: t('admin.audit.colDecision'),
              dataIndex: 'decision',
              render: (v: string) =>
                v === 'deny' ? <Tag color="red">deny</Tag> : <Tag color="green">allow</Tag>,
            },
            { title: t('admin.audit.colQuery'), dataIndex: 'query_text', ellipsis: true },
            { title: t('admin.audit.colDenyReason'), dataIndex: 'deny_reason', ellipsis: true },
            { title: t('admin.audit.colLatency'), dataIndex: 'latency_ms', width: 90 },
          ]}
        />
      </Space>

      <Drawer
        title={t('admin.audit.drawerTitle', { id: selected?.id ?? '' })}
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
