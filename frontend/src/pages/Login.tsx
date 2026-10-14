import { useState } from 'react'
import { Alert, Button, Card, Form, Select, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../auth/AuthContext'

const { Title } = Typography

// Keep in sync with backend/seed_data.py (see requirement/doc_permission_matrix.md)
const DEMO_USER_KEYS = [
  'alice', 'carol', 'dave', 'erin', 'frank', 'gina', 'henry',
  'ivy', 'jack', 'bob', 'kate', 'leo', 'vera', 'admin',
] as const

const ADMIN_SITE = import.meta.env.MODE === 'admin'

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onFinish = async (values: { username: string }) => {
    setError(null)
    setSubmitting(true)
    try {
      await login(values.username)
      navigate(ADMIN_SITE ? '/admin' : '/app/query')
    } catch {
      setError(t('login.errorNotFound'))
    } finally {
      setSubmitting(false)
    }
  }

  const options = DEMO_USER_KEYS
    .filter((u) => !ADMIN_SITE || u === 'admin')
    .map((u) => ({ value: u, label: t(`login.demoUsers.${u}`) }))

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 120 }}>
      <Card style={{ width: 420 }}>
        <Title level={3}>{ADMIN_SITE ? t('login.adminTitle') : t('login.title')}</Title>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label={t('login.ssoLabel')} rules={[{ required: true }]}>
            <Select
              placeholder={t('login.selectAccount')}
              showSearch
              optionFilterProp="label"
              options={options}
            />
          </Form.Item>
          {error && <Alert style={{ marginBottom: 16 }} type="error" message={error} showIcon />}
          <Button type="primary" htmlType="submit" loading={submitting} block>
            {t('login.submit')}
          </Button>
        </Form>
      </Card>
    </div>
  )
}
