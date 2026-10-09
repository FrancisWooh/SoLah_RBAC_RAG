import { ConfigProvider } from 'antd'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import Login from './pages/Login'
import Query from './pages/Query'

function App() {
  return (
    <ConfigProvider>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/app/query"
            element={
              <ProtectedRoute>
                <Query />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </ConfigProvider>
  )
}

export default App
