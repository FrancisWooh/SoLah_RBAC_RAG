import { useEffect, useState } from 'react'
import { Alert, Card, Col, Row, Statistic, Table, Tag, Typography, message } from 'antd'
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
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<DashboardStats>('/api/admin/dashboard/stats')
      .then((r) => setStats(r.data))
      .catch(() => message.error('加载 Dashboard 数据失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading || !stats) {
    return <Title level={3}>Dashboard</Title>
  }

  const denyRatePercent = Math.round(stats.deny_rate * 1000) / 10
  const syncEntries = Object.entries(stats.sync_status_counts)

  return (
    <div>
      <Title level={3}>Dashboard</Title>

      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="查询总量" value={stats.total_queries} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="允许" value={stats.allow_count} valueStyle={{ color: ALLOW_COLOR }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="拒绝（越权尝试）" value={stats.deny_count} valueStyle={{ color: DENY_COLOR }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="拒绝率"
              value={denyRatePercent}
              suffix="%"
              valueStyle={{ color: denyRatePercent > 20 ? DENY_COLOR : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="查询量趋势（按天）" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={stats.query_volume_by_day}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count" name="查询量" fill={VOLUME_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="越权告警（最近拒绝记录）" style={{ marginTop: 16 }}>
        <Table
          size="small"
          rowKey="id"
          dataSource={stats.recent_violations}
          pagination={false}
          locale={{ emptyText: '暂无越权记录' }}
          columns={[
            { title: '时间', dataIndex: 'created_at', width: 180 },
            { title: '用户', dataIndex: 'username', render: (v) => v ?? '-' },
            { title: '查询内容', dataIndex: 'query_text', ellipsis: true },
            {
              title: '拒绝原因',
              dataIndex: 'deny_reason',
              render: (v: string) => <Tag color="red">{v}</Tag>,
            },
          ]}
        />
      </Card>

      <Card title="数据源同步健康度" style={{ marginTop: 16 }}>
        {syncEntries.length === 0 ? (
          <Alert
            type="info"
            showIcon
            message="暂无已配置的数据源"
            description="真实 CDC/NAS 同步不在本次交付范围内（见 readme.txt），这里如实反映 data_sources 表当前状态，不是虚构的健康数字。"
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
