import { Result, Spin } from 'antd'
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from './AuthContext'

export default function ProtectedRoute({
  children,
  requireRoles,
}: {
  children: ReactNode
  /** If set, the user's effective_roles must include at least one of these. */
  requireRoles?: string[]
}) {
  const { t } = useTranslation()
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
        title={t('admin.protectedRoute.forbidden')}
        subTitle={t('admin.protectedRoute.forbiddenDesc')}
      />
    )
  }

  return <>{children}</>
}
