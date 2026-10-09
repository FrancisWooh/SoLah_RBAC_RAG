import { Button, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export default function UserBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const onLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <Space style={{ padding: '8px 16px', justifyContent: 'space-between', width: '100%' }}>
      <Space>
        <Typography.Text strong>{user.username}</Typography.Text>
        <Typography.Text type="secondary">clearance {user.clearance}</Typography.Text>
        {user.effective_roles.map((role) => (
          <Tag key={role} color="blue">
            {role}
          </Tag>
        ))}
      </Space>
      <Button size="small" onClick={onLogout}>
        退出登录
      </Button>
    </Space>
  )
}
