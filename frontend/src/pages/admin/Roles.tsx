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
    loadLists().catch(() => message.error('加载用户/角色列表失败'))
    loadPendingRequests().catch(() => message.error('加载待审批申请失败'))
  }, [])

  const onApproveRequest = async (id: number) => {
    try {
      await apiClient.post(`/api/admin/role-requests/${id}/approve`)
      message.success('已批准')
      await loadPendingRequests()
      if (selectedUserId) await loadUserRoles(selectedUserId)
    } catch {
      message.error('批准失败')
    }
  }

  const onRejectRequest = async (id: number) => {
    try {
      await apiClient.post(`/api/admin/role-requests/${id}/reject`)
      message.success('已拒绝')
      await loadPendingRequests()
    } catch {
      message.error('拒绝失败')
    }
  }

  useEffect(() => {
    if (selectedUserId) {
      loadUserRoles(selectedUserId).catch(() => message.error('加载用户角色失败'))
    } else {
      setUserRoles([])
    }
  }, [selectedUserId])

  const onGrant = async () => {
    if (!selectedUserId || !grantRoleId) {
      message.warning('请先选择用户和角色')
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
      message.success('已授予角色')
      await loadUserRoles(selectedUserId)
    } catch {
      message.error('授予失败')
    }
  }

  const onRevoke = async (userRoleId: number) => {
    try {
      await apiClient.post('/api/admin/roles/revoke', { user_role_id: userRoleId })
      message.success('已撤销')
      if (selectedUserId) await loadUserRoles(selectedUserId)
    } catch {
      message.error('撤销失败')
    }
  }

  const onProjectJoin = async () => {
    if (!selectedUserId || !projectRole) {
      message.warning('请先选择用户和项目角色')
      return
    }
    try {
      await apiClient.post('/api/admin/projects/join', {
        project_id: projectId,
        user_id: selectedUserId,
        project_role: projectRole,
        project_end_at: projectEndAt ? projectEndAt.toISOString() : null,
      })
      message.success(`已加入项目 ${projectId}，自动授予 ${projectRole}`)
      await loadUserRoles(selectedUserId)
    } catch {
      message.error('加入项目失败')
    }
  }

  const onProjectLeave = async () => {
    if (!selectedUserId) return
    try {
      await apiClient.post('/api/admin/projects/leave', {
        project_id: projectId,
        user_id: selectedUserId,
      })
      message.success(`已移出项目 ${projectId}，相关临时角色已撤销`)
      await loadUserRoles(selectedUserId)
    } catch {
      message.error('移出项目失败（可能该用户本不在此项目中）')
    }
  }

  return (
    <div>
      <Title level={3}>角色管理</Title>

      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Card title="1. 选择用户">
          <Select
            style={{ width: 320 }}
            placeholder="选择用户"
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

        <Card title="2. 当前角色授予记录">
          <Table
            rowKey="id"
            dataSource={userRoles}
            pagination={false}
            locale={{ emptyText: selectedUserId ? '暂无角色记录' : '请先选择用户' }}
            columns={[
              { title: '角色', dataIndex: 'role_id' },
              { title: '来源', dataIndex: 'source' },
              { title: '来源引用', dataIndex: 'source_ref' },
              { title: '到期时间', dataIndex: 'end_at', render: (v) => v ?? '永久' },
              { title: '状态', dataIndex: 'status' },
              {
                title: '操作',
                render: (_, row: UserRoleOut) =>
                  row.status === 'active' ? (
                    <Popconfirm title="确认撤销该角色？" onConfirm={() => onRevoke(row.id)}>
                      <Button size="small" danger>
                        撤销
                      </Button>
                    </Popconfirm>
                  ) : null,
              },
            ]}
          />
        </Card>

        <Card title="3. 直接授予角色">
          <Space wrap>
            <Select
              style={{ width: 180 }}
              placeholder="角色"
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
              placeholder="来源引用（可选）"
              value={grantSourceRef}
              onChange={(e) => setGrantSourceRef(e.target.value)}
            />
            <DatePicker
              showTime
              placeholder="到期时间（留空=永久）"
              value={grantEndAt}
              onChange={setGrantEndAt}
            />
            <Button type="primary" onClick={onGrant}>
              授予
            </Button>
          </Space>
        </Card>

        <Card title="3.5 项目成员（加入自动授权 / 移出自动撤销）">
          <Space wrap>
            <Input
              style={{ width: 200 }}
              placeholder="项目ID"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            />
            <Select
              style={{ width: 180 }}
              placeholder="项目角色"
              value={projectRole}
              onChange={setProjectRole}
              showSearch
              optionFilterProp="label"
              options={roles.map((r) => ({ value: r.id, label: r.id }))}
            />
            <DatePicker
              showTime
              placeholder="项目结束时间（可选）"
              value={projectEndAt}
              onChange={setProjectEndAt}
            />
            <Button type="primary" onClick={onProjectJoin}>
              加入项目
            </Button>
            <Button danger onClick={onProjectLeave}>
              移出项目
            </Button>
          </Space>
        </Card>

        <Card title="4. 待审批申请">
          <Table
            rowKey="id"
            dataSource={pendingRequests}
            pagination={false}
            locale={{ emptyText: '暂无待审批申请' }}
            columns={[
              { title: '申请人', render: (_, row: RoleRequestOut) => usernameById(row.requester_id) },
              { title: '角色', dataIndex: 'role_id' },
              { title: '理由', dataIndex: 'reason', ellipsis: true },
              { title: '申请时长(h)', dataIndex: 'requested_duration_hours', render: (v) => v ?? '永久' },
              { title: '提交时间', dataIndex: 'created_at' },
              {
                title: '操作',
                render: (_, row: RoleRequestOut) => (
                  <Space>
                    <Button size="small" type="primary" onClick={() => onApproveRequest(row.id)}>
                      批准
                    </Button>
                    <Button size="small" danger onClick={() => onRejectRequest(row.id)}>
                      拒绝
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
        提示：演示场景三——先"加入项目"（自动授予角色），到 /app/query 验证可以查询；
        再"移出项目"，验证立即被拒绝（权限缓存TTL 30秒，但撤销接口会主动清缓存，
        所以是立即生效，不用等）。
      </Typography.Text>
    </div>
  )
}
