import { Result, Spin } from 'antd'
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'

import { useAuth } from './AuthContext'

export default function ProtectedRoute({
  children,
  requireRoles,
}: {
  children: ReactNode
  /** If set, the user's effective_roles must include at least one of these. */
  requireRoles?: string[]
}) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 120 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (requireRoles && !requireRoles.some((r) => user.effective_roles.includes(r))) {
    return (
      <Result
        status="403"
        title="权限不足"
        subTitle="该页面需要管理员角色。"
      />
    )
  }

  return <>{children}</>
}
