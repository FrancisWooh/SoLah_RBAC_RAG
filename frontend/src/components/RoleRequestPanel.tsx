import { useEffect, useState } from 'react'
import { Button, Collapse, Input, InputNumber, Select, Space, Table, Tag, message } from 'antd'
import { useTranslation } from 'react-i18next'

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
  const { t } = useTranslation()
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
      .catch(() => message.error(t('admin.roleRequest.loadRolesError')))
    loadMyRequests().catch(() => message.error(t('admin.roleRequest.loadRequestsError')))
  }, [])

  const onSubmit = async () => {
    if (!roleId || !reason.trim()) {
      message.warning(t('admin.roleRequest.selectRoleAndReason'))
      return
    }
    setSubmitting(true)
    try {
      await apiClient.post('/api/role-requests', {
        role_id: roleId,
        reason,
        requested_duration_hours: durationHours,
      })
      message.success(t('admin.roleRequest.submitSuccess'))
      setReason('')
      await loadMyRequests()
    } catch {
      message.error(t('admin.roleRequest.submitError'))
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
          label: t('admin.roleRequest.title'),
          children: (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space wrap>
                <Select
                  style={{ width: 200 }}
                  placeholder={t('admin.roleRequest.selectRole')}
                  value={roleId}
                  onChange={setRoleId}
                  options={roles.map((r) => ({ value: r.id, label: r.name }))}
                />
                <InputNumber
                  style={{ width: 160 }}
                  min={1}
                  addonAfter={t('admin.roleRequest.hours')}
                  value={durationHours}
                  onChange={setDurationHours}
                />
              </Space>
              <Input.TextArea
                placeholder={t('admin.roleRequest.reasonPlaceholder')}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 4 }}
              />
              <Button type="primary" loading={submitting} onClick={onSubmit}>
                {t('admin.roleRequest.submitBtn')}
              </Button>

              <Table
                style={{ marginTop: 16 }}
                size="small"
                rowKey="id"
                dataSource={myRequests}
                pagination={false}
                locale={{ emptyText: t('admin.roleRequest.noRecords') }}
                columns={[
                  { title: t('admin.roleRequest.colRole'), dataIndex: 'role_id' },
                  { title: t('admin.roleRequest.colReason'), dataIndex: 'reason', ellipsis: true },
                  {
                    title: t('admin.roleRequest.colStatus'),
                    dataIndex: 'status',
                    render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v}</Tag>,
                  },
                  { title: t('admin.roleRequest.colExpiry'), dataIndex: 'end_at', render: (v) => v ?? '-' },
                ]}
              />
            </Space>
          ),
        },
      ]}
    />
  )
}
