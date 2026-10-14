import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  DatePicker,
  Divider,
  Input,
  message,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useTranslation } from 'react-i18next'

import { apiClient } from '../../api/client'

const { Title } = Typography

interface RoleOut {
  id: string
  name: string
  is_permanent: boolean
}

interface UserOut {
  id: string
  username: string
  department: string | null
}

interface UserRoleOut {
  id: number
  role_id: string
  source: string
  source_ref: string | null
  start_at: string
  end_at: string | null
  status: string
}

interface RoleRequestOut {
  id: number
  requester_id: string
  role_id: string
  reason: string
  requested_duration_hours: number | null
  status: string
  created_at: string
}

export default function Roles() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<UserOut[]>([])
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>()
  const [userRoles, setUserRoles] = useState<UserRoleOut[]>([])

  const [grantRoleId, setGrantRoleId] = useState<string | undefined>()
  const [grantSource, setGrantSource] = useState('temporary')
  const [grantSourceRef, setGrantSourceRef] = useState('')
  const [grantEndAt, setGrantEndAt] = useState<Dayjs | null>(null)

  const [projectId, setProjectId] = useState('proj_card_program')
  const [projectRole, setProjectRole] = useState<string | undefined>('card_ops')
  const [projectEndAt, setProjectEndAt] = useState<Dayjs | null>(null)

  const [pendingRequests, setPendingRequests] = useState<RoleRequestOut[]>([])
  const usernameById = (id: string) => users.find((u) => u.id === id)?.username ?? id

  const loadLists = async () => {
    const [usersResp, rolesResp] = await Promise.all([
      apiClient.get<UserOut[]>('/api/admin/users'),
      apiClient.get<RoleOut[]>('/api/admin/roles'),
    ])
    setUsers(usersResp.data)
    setRoles(rolesResp.data)
  }

  const loadUserRoles = async (userId: string) => {
    const { data } = await apiClient.get<UserRoleOut[]>(`/api/admin/users/${userId}/roles`)
    setUserRoles(data)
  }

  const loadPendingRequests = async () => {
    const { data } = await apiClient.get<RoleRequestOut[]>(
      '/api/admin/role-requests?status_filter=pending',
    )
    setPendingRequests(data)
  }

  useEffect(() => {
    loadLists().catch(() => message.error(t('admin.roles.loadUsersError')))
    loadPendingRequests().catch(() => message.error(t('admin.roles.loadPendingError')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onApproveRequest = async (id: number) => {
    try {
      await apiClient.post(`/api/admin/role-requests/${id}/approve`)
      message.success(t('admin.roles.approveSuccess'))
      await loadPendingRequests()
      if (selectedUserId) await loadUserRoles(selectedUserId)
    } catch {
      message.error(t('admin.roles.approveError'))
    }
  }

  const onRejectRequest = async (id: number) => {
    try {
      await apiClient.post(`/api/admin/role-requests/${id}/reject`)
      message.success(t('admin.roles.rejectSuccess'))
      await loadPendingRequests()
    } catch {
      message.error(t('admin.roles.rejectError'))
    }
  }

  useEffect(() => {
    if (selectedUserId) {
      loadUserRoles(selectedUserId).catch(() => message.error(t('admin.roles.loadUserRolesError')))
    } else {
      setUserRoles([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUserId])

  const onGrant = async () => {
    if (!selectedUserId || !grantRoleId) {
      message.warning(t('admin.roles.selectUserAndRole'))
      return
    }
    try {
      await apiClient.post('/api/admin/roles/grant', {
        user_id: selectedUserId,
        role_id: grantRoleId,
        source: grantSource,
        source_ref: grantSourceRef || null,
        end_at: grantEndAt ? grantEndAt.toISOString() : null,
      })
      message.success(t('admin.roles.grantSuccess'))
      await loadUserRoles(selectedUserId)
    } catch {
      message.error(t('admin.roles.grantError'))
    }
  }

  const onRevoke = async (userRoleId: number) => {
    try {
      await apiClient.post('/api/admin/roles/revoke', { user_role_id: userRoleId })
      message.success(t('admin.roles.revokeSuccess'))
      if (selectedUserId) await loadUserRoles(selectedUserId)
    } catch {
      message.error(t('admin.roles.revokeError'))
    }
  }

  const onProjectJoin = async () => {
    if (!selectedUserId || !projectRole) {
      message.warning(t('admin.roles.selectUserAndProjectRole'))
      return
    }
    try {
      await apiClient.post('/api/admin/projects/join', {
        project_id: projectId,
        user_id: selectedUserId,
        project_role: projectRole,
        project_end_at: projectEndAt ? projectEndAt.toISOString() : null,
      })
      message.success(t('admin.roles.joinProjectSuccess', { projectId, projectRole }))
      await loadUserRoles(selectedUserId)
    } catch {
      message.error(t('admin.roles.joinProjectError'))
    }
  }

  const onProjectLeave = async () => {
    if (!selectedUserId) return
    try {
      await apiClient.post('/api/admin/projects/leave', {
        project_id: projectId,
        user_id: selectedUserId,
      })
      message.success(t('admin.roles.leaveProjectSuccess', { projectId }))
      await loadUserRoles(selectedUserId)
    } catch {
      message.error(t('admin.roles.leaveProjectError'))
    }
  }

  return (
    <div>
      <Title level={3}>{t('admin.roles.title')}</Title>

      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Card title={t('admin.roles.step1')}>
          <Select
            style={{ width: 320 }}
            placeholder={t('admin.roles.selectUser')}
            showSearch
            optionFilterProp="label"
            value={selectedUserId}
            onChange={setSelectedUserId}
            options={users.map((u) => ({
              value: u.id,
              label: `${u.username}${u.department ? ` (${u.department})` : ''}`,
            }))}
          />
        </Card>

        <Card title={t('admin.roles.step2')}>
          <Table
            rowKey="id"
            dataSource={userRoles}
            pagination={false}
            locale={{ emptyText: selectedUserId ? t('admin.roles.noRoles') : t('admin.roles.selectUserFirst') }}
            columns={[
              { title: t('admin.roles.colRole'), dataIndex: 'role_id' },
              { title: t('admin.roles.colSource'), dataIndex: 'source' },
              { title: t('admin.roles.colSourceRef'), dataIndex: 'source_ref' },
              { title: t('admin.roles.colExpiry'), dataIndex: 'end_at', render: (v) => v ?? t('common.permanent') },
              { title: t('admin.roles.colStatus'), dataIndex: 'status' },
              {
                title: t('admin.roles.colOperation'),
                render: (_, row: UserRoleOut) =>
                  row.status === 'active' ? (
                    <Popconfirm title={t('admin.roles.revokeConfirm')} onConfirm={() => onRevoke(row.id)}>
                      <Button size="small" danger>
                        {t('admin.roles.revokeBtn')}
                      </Button>
                    </Popconfirm>
                  ) : null,
              },
            ]}
          />
        </Card>

        <Card title={t('admin.roles.step3')}>
          <Space wrap>
            <Select
              style={{ width: 180 }}
              placeholder={t('common.role')}
              value={grantRoleId}
              onChange={setGrantRoleId}
              showSearch
              optionFilterProp="label"
              options={roles.map((r) => ({ value: r.id, label: r.id }))}
            />
            <Select
              style={{ width: 140 }}
              value={grantSource}
              onChange={setGrantSource}
              options={[
                { value: 'permanent', label: 'permanent' },
                { value: 'temporary', label: 'temporary' },
                { value: 'project', label: 'project' },
              ]}
            />
            <Input
              style={{ width: 160 }}
              placeholder={t('admin.roles.sourceRefPlaceholder')}
              value={grantSourceRef}
              onChange={(e) => setGrantSourceRef(e.target.value)}
            />
            <DatePicker
              showTime
              placeholder={t('admin.roles.expiryPlaceholder')}
              value={grantEndAt}
              onChange={setGrantEndAt}
            />
            <Button type="primary" onClick={onGrant}>
              {t('admin.roles.grantBtn')}
            </Button>
          </Space>
        </Card>

        <Card title={t('admin.roles.step3_5')}>
          <Space wrap>
            <Input
              style={{ width: 200 }}
              placeholder={t('admin.roles.projectIdPlaceholder')}
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            />
            <Select
              style={{ width: 180 }}
              placeholder={t('admin.roles.projectRolePlaceholder')}
              value={projectRole}
              onChange={setProjectRole}
              showSearch
              optionFilterProp="label"
              options={roles.map((r) => ({ value: r.id, label: r.id }))}
            />
            <DatePicker
              showTime
              placeholder={t('admin.roles.projectEndPlaceholder')}
              value={projectEndAt}
              onChange={setProjectEndAt}
            />
            <Button type="primary" onClick={onProjectJoin}>
              {t('admin.roles.joinProject')}
            </Button>
            <Button danger onClick={onProjectLeave}>
              {t('admin.roles.leaveProject')}
            </Button>
          </Space>
        </Card>

        <Card title={t('admin.roles.step4')}>
          <Table
            rowKey="id"
            dataSource={pendingRequests}
            pagination={false}
            locale={{ emptyText: t('admin.roles.noPending') }}
            columns={[
              { title: t('admin.roles.colApplicant'), render: (_, row: RoleRequestOut) => usernameById(row.requester_id) },
              { title: t('admin.roles.colRole'), dataIndex: 'role_id' },
              { title: t('admin.roles.colReason'), dataIndex: 'reason', ellipsis: true },
              { title: t('admin.roles.colDuration'), dataIndex: 'requested_duration_hours', render: (v) => v ?? t('common.permanent') },
              { title: t('admin.roles.colSubmittedAt'), dataIndex: 'created_at' },
              {
                title: t('admin.roles.colOperation'),
                render: (_, row: RoleRequestOut) => (
                  <Space>
                    <Button size="small" type="primary" onClick={() => onApproveRequest(row.id)}>
                      {t('common.approve')}
                    </Button>
                    <Button size="small" danger onClick={() => onRejectRequest(row.id)}>
                      {t('common.reject')}
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      </Space>

      <Divider />
      <Typography.Text type="secondary">
        {t('admin.roles.hintText')}
      </Typography.Text>
    </div>
  )
}
