import { useState } from 'react'
import { Alert, Button, Card, Form, Select, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

const { Title } = Typography

// Keep in sync with backend/seed_data.py (see requirement/doc_permission_matrix.md)
const DEMO_USERS = [
  { username: 'alice', label: 'alice — compliance_officer（密级2 · aml）' },
  { username: 'carol', label: 'carol — compliance_officer + mlro（密级3 · aml）' },
  { username: 'dave', label: 'dave — risk_analyst（密级3 · credit）' },
  { username: 'erin', label: 'erin — card_ops（密级2）' },
  { username: 'frank', label: 'frank — customer_support（密级1）' },
  { username: 'gina', label: 'gina — finance_analyst（密级3 · finance）' },
  { username: 'henry', label: 'henry — hr_manager（密级3 · hr）' },
  { username: 'ivy', label: 'ivy — marketing_manager（密级2）' },
  { username: 'jack', label: 'jack — account_manager（密级2）' },
  { username: 'bob', label: 'bob — engineer（密级2）' },
  { username: 'kate', label: 'kate — security_engineer（密级3 · security）' },
  { username: 'leo', label: 'leo — legal_counsel（密级3 · legal）' },
  { username: 'vera', label: 'vera — exec（密级4 · board/hr/finance）' },
  { username: 'admin', label: 'admin — platform_admin（密级4）' },
]

const ADMIN_SITE = import.meta.env.MODE === 'admin'

export default function Login() {
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
      setError('登录失败：账号不存在')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 120 }}>
      <Card style={{ width: 420 }}>
        <Title level={3}>{ADMIN_SITE ? 'Aspire Internal Brain · 管理后台' : 'Aspire Internal Brain'}</Title>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="模拟 SSO 登录" rules={[{ required: true }]}>
            <Select
              placeholder="选择账号"
              showSearch
              optionFilterProp="label"
              options={DEMO_USERS.filter((u) => !ADMIN_SITE || u.username === 'admin').map((u) => ({ value: u.username, label: u.label }))}
            />
          </Form.Item>
          {error && <Alert style={{ marginBottom: 16 }} type="error" message={error} showIcon />}
          <Button type="primary" htmlType="submit" loading={submitting} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  )
}
