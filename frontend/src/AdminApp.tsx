import { ConfigProvider } from 'antd'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import Login from './pages/Login'
import AdminLayout from './pages/admin/AdminLayout'
import Roles from './pages/admin/Roles'
import Audit from './pages/admin/Audit'
import DataSources from './pages/admin/DataSources'
import DataSourceNas from './pages/admin/DataSourceNas'
import DataSourceDatabases from './pages/admin/DataSourceDatabases'
import Dashboard from './pages/admin/Dashboard'

/** The management console as its own site (port 5174, `vite --mode admin`):
 *  no employee Q&A page, only the platform_admin pages. */
export default function AdminApp() {
  return (
    <ConfigProvider>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/admin" replace />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireRoles={['platform_admin']}>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/admin/dashboard" replace />} />
            <Route path="roles" element={<Roles />} />
            <Route path="audit" element={<Audit />} />
            <Route path="datasources">
              <Route index element={<Navigate to="/admin/datasources/overview" replace />} />
              <Route path="overview" element={<DataSources />} />
              <Route path="nas" element={<DataSourceNas />} />
              <Route path="databases" element={<DataSourceDatabases />} />
            </Route>
            <Route path="dashboard" element={<Dashboard />} />
          </Route>
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </AuthProvider>
    </ConfigProvider>
  )
}
