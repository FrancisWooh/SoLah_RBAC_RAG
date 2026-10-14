import { useEffect, useState } from 'react'
import { Alert, Card, Col, Row, Statistic, Table, Tag, Typography, message } from 'antd'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { apiClient } from '../../api/client'

const { Title } = Typography

// Consistent with the green/red allow-deny convention already used in
// Audit.tsx — status colors stay reserved for that meaning everywhere in
// this admin UI, never reused for anything else.
const ALLOW_COLOR = '#52c41a'
const DENY_COLOR = '#ff4d4f'
const VOLUME_COLOR = '#1677ff'

interface ViolationItem {
  id: number
  username: string | null
  query_text: string | null
  deny_reason: string | null
  created_at: string
}

interface VolumePoint {
  date: string
  count: number
}

interface DashboardStats {
  total_queries: number
  allow_count: number
  deny_count: number
  deny_rate: number
  recent_violations: ViolationItem[]
  query_volume_by_day: VolumePoint[]
  sync_status_counts: Record<string, number>
}

export default function Dashboard() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<DashboardStats>('/api/admin/dashboard/stats')
      .then((r) => setStats(r.data))
      .catch(() => message.error(t('admin.dashboard.loadError')))
      .finally(() => setLoading(false))
  }, [t])

  if (loading || !stats) {
    return <Title level={3}>{t('admin.dashboard.title')}</Title>
  }

  const denyRatePercent = Math.round(stats.deny_rate * 1000) / 10
  const syncEntries = Object.entries(stats.sync_status_counts)

  return (
    <div>
      <Title level={3}>{t('admin.dashboard.title')}</Title>

      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title={t('admin.dashboard.totalQueries')} value={stats.total_queries} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title={t('admin.dashboard.allow')} value={stats.allow_count} valueStyle={{ color: ALLOW_COLOR }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title={t('admin.dashboard.deny')} value={stats.deny_count} valueStyle={{ color: DENY_COLOR }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('admin.dashboard.denyRate')}
              value={denyRatePercent}
              suffix="%"
              valueStyle={{ color: denyRatePercent > 20 ? DENY_COLOR : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <Card title={t('admin.dashboard.volumeTrend')} style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={stats.query_volume_by_day}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count" name={t('admin.dashboard.volumeSeries')} fill={VOLUME_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title={t('admin.dashboard.violationAlerts')} style={{ marginTop: 16 }}>
        <Table
          size="small"
          rowKey="id"
          dataSource={stats.recent_violations}
          pagination={false}
          locale={{ emptyText: t('admin.dashboard.noViolations') }}
          columns={[
            { title: t('admin.dashboard.colTime'), dataIndex: 'created_at', width: 180 },
            { title: t('admin.dashboard.colUser'), dataIndex: 'username', render: (v) => v ?? '-' },
            { title: t('admin.dashboard.colQuery'), dataIndex: 'query_text', ellipsis: true },
            {
              title: t('admin.dashboard.colDenyReason'),
              dataIndex: 'deny_reason',
              render: (v: string) => <Tag color="red">{v}</Tag>,
            },
          ]}
        />
      </Card>

      <Card title={t('admin.dashboard.syncHealth')} style={{ marginTop: 16 }}>
        {syncEntries.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message={t('admin.dashboard.noDataSources')}
            description={t('admin.dashboard.noDataSourcesDesc')}
          />
        ) : (
          syncEntries.map(([status, count]) => (
            <Tag key={status} color={status === 'failed' ? 'red' : status === 'running' ? 'blue' : 'default'}>
              {status}: {count}
            </Tag>
          ))
        )}
      </Card>
    </div>
  )
}
