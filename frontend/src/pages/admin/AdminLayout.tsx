import { Layout, Menu, Space } from 'antd'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import UserBar from '../../components/UserBar'
import LanguageSwitcher from '../../components/LanguageSwitcher'

const { Sider, Content, Header } = Layout

export default function AdminLayout() {
  const { t } = useTranslation()
  const location = useLocation()

  const items = [
    { key: '/admin/roles', label: <Link to="/admin/roles">{t('admin.layout.roles')}</Link> },
    { key: '/admin/audit', label: <Link to="/admin/audit">{t('admin.layout.audit')}</Link> },
    {
      key: 'datasources',
      label: t('admin.layout.datasources'),
      children: [
        { key: '/admin/datasources/overview', label: <Link to="/admin/datasources/overview">{t('admin.layout.datasourceOverview')}</Link> },
        { key: '/admin/datasources/nas', label: <Link to="/admin/datasources/nas">{t('admin.layout.datasourceNas')}</Link> },
        { key: '/admin/datasources/databases', label: <Link to="/admin/datasources/databases">{t('admin.layout.datasourceDatabases')}</Link> },
      ],
    },
    { key: '/admin/dashboard', label: <Link to="/admin/dashboard">{t('admin.layout.dashboard')}</Link> },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light">
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={location.pathname.startsWith('/admin/datasources') ? ['datasources'] : []}
          items={items}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', borderBottom: '1px solid #f0f0f0', padding: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div />
          <Space style={{ paddingRight: 16 }}>
            <LanguageSwitcher />
            <UserBar />
          </Space>
        </Header>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
