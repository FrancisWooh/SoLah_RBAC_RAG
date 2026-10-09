import { useEffect, useState } from 'react'
import { Button, Collapse, Input, InputNumber, Select, Space, Table, Tag, message } from 'antd'

import { apiClient } from '../api/client'

interface RoleSummary {
  id: string
  name: string
}

interface RoleRequestOut {
  id: number
  role_id: string
  reason: string
  requested_duration_hours: number | null
  status: string
  end_at: string | null
  created_at: string
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  approved: 'green',
  rejected: 'red',
}

export default function RoleRequestPanel() {
  const [roles, setRoles] = useState<RoleSummary[]>([])
  const [myRequests, setMyRequests] = useState<RoleRequestOut[]>([])
  const [roleId, setRoleId] = useState<string | undefined>()
  const [reason, setReason] = useState('')
  const [durationHours, setDurationHours] = useState<number | null>(24)
  const [submitting, setSubmitting] = useState(false)

  const loadMyRequests = async () => {
    const { data } = await apiClient.get<RoleRequestOut[]>('/api/role-requests/me')
    setMyRequests(data)
  }

  useEffect(() => {
    apiClient
      .get<RoleSummary[]>('/api/roles')
      .then((r) => setRoles(r.data))
      .catch(() => message.error('加载角色列表失败'))
    loadMyRequests().catch(() => message.error('加载我的申请记录失败'))
  }, [])

  const onSubmit = async () => {
    if (!roleId || !reason.trim()) {
      message.warning('请选择角色并填写申请理由')
      return
    }
    setSubmitting(true)
    try {
      await apiClient.post('/api/role-requests', {
        role_id: roleId,
        reason,
        requested_duration_hours: durationHours,
      })
      message.success('已提交申请，等待管理员审批')
      setReason('')
      await loadMyRequests()
    } catch {
      message.error('提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Collapse
      style={{ marginTop: 24 }}
      items={[
        {
          key: 'role-request',
          label: '申请临时角色',
          children: (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space wrap>
                <Select
                  style={{ width: 200 }}
                  placeholder="选择角色"
                  value={roleId}
                  onChange={setRoleId}
                  options={roles.map((r) => ({ value: r.id, label: r.name }))}
                />
                <InputNumber
                  style={{ width: 160 }}
                  min={1}
                  addonAfter="小时"
                  value={durationHours}
                  onChange={setDurationHours}
                />
              </Space>
              <Input.TextArea
                placeholder="申请理由"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 4 }}
              />
              <Button type="primary" loading={submitting} onClick={onSubmit}>
                提交申请
              </Button>

              <Table
                style={{ marginTop: 16 }}
                size="small"
                rowKey="id"
                dataSource={myRequests}
                pagination={false}
                locale={{ emptyText: '暂无申请记录' }}
                columns={[
                  { title: '角色', dataIndex: 'role_id' },
                  { title: '理由', dataIndex: 'reason', ellipsis: true },
                  {
                    title: '状态',
                    dataIndex: 'status',
                    render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v}</Tag>,
                  },
                  { title: '到期时间', dataIndex: 'end_at', render: (v) => v ?? '-' },
                ]}
              />
            </Space>
          ),
        },
      ]}
    />
  )
}
