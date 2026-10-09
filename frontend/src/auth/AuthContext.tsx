import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { apiClient } from '../api/client'
import type { CurrentUser } from './types'

interface AuthContextValue {
  user: CurrentUser | null
  loading: boolean
  login: (username: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = async () => {
    const { data } = await apiClient.get<CurrentUser>('/api/auth/me')
    setUser(data)
  }

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    fetchMe()
      .catch(() => {
        localStorage.removeItem('access_token')
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string) => {
    const { data } = await apiClient.post<{ access_token: string }>('/api/auth/login', {
      username,
    })
    localStorage.setItem('access_token', data.access_token)
    await fetchMe()
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
