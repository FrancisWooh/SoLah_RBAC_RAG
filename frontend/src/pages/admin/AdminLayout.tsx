import { Layout, Menu } from 'antd'
import { Link, Outlet, useLocation } from 'react-router-dom'

import UserBar from '../../components/UserBar'

const { Sider, Content, Header } = Layout

const ITEMS = [
  { key: '/admin/roles', label: <Link to="/admin/roles">角色管理</Link> },
  { key: '/admin/audit', label: <Link to="/admin/audit">审计日志</Link> },
  {
    key: 'datasources',
    label: '数据源',
    children: [
      { key: '/admin/datasources/overview', label: <Link to="/admin/datasources/overview">数据源总览</Link> },
      { key: '/admin/datasources/nas', label: <Link to="/admin/datasources/nas">NAS 数据源</Link> },
      { key: '/admin/datasources/databases', label: <Link to="/admin/datasources/databases">数据库连接</Link> },
    ],
  },
  { key: '/admin/dashboard', label: <Link to="/admin/dashboard">Dashboard</Link> },
]

export default function AdminLayout() {
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light">
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={location.pathname.startsWith('/admin/datasources') ? ['datasources'] : []}
          items={ITEMS}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', borderBottom: '1px solid #f0f0f0', padding: 0 }}>
          <UserBar />
        </Header>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
