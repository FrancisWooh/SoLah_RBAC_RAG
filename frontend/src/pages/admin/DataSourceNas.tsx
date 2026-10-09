import { useState } from 'react'
import {
  Alert, Button, Card, Checkbox, Col, Form, Input, InputNumber, Modal, Popconfirm, Row, Select,
  Space, Statistic, Switch, Table, Tag, Typography, message,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons'

import { COMPARTMENT_OPTIONS, ROLE_OPTIONS } from './dataSourceMock'

const { Title, Text } = Typography

interface DirMapping {
  key: string
  dir: string
  department: string
  roles: string[]
  clearance: number
  compartments: string[]
}

interface SyncRecord {
  key: string
  at: string
  trigger: string
  added: number
  updated: number
  archived: number
  removed: number
  skipped: number
  errors: number
}

const INITIAL_MAPPINGS: DirMapping[] = [
  { key: 'public', dir: 'public/', department: 'Public', roles: ['employee'], clearance: 1, compartments: [] },
  { key: 'compliance', dir: 'compliance/', department: 'Compliance', roles: ['compliance_officer'], clearance: 2, compartments: ['aml'] },
  { key: 'hr', dir: 'hr/', department: 'HR', roles: ['hr_manager'], clearance: 2, compartments: ['hr'] },
  { key: 'finance', dir: 'finance/', department: 'Finance', roles: ['finance_analyst'], clearance: 2, compartments: ['finance'] },
  { key: 'executive', dir: 'executive/', department: 'Executive', roles: ['exec'], clearance: 4, compartments: ['board'] },
  { key: 'proj_merger', dir: 'projects/proj_merger/', department: 'Projects', roles: ['proj_merger'], clearance: 2, compartments: [] },
]

const HISTORY: SyncRecord[] = [
  { key: '1', at: '2026-10-06 10:40:03', trigger: '自动', added: 0, updated: 0, archived: 0, removed: 0, skipped: 1, errors: 0 },
  { key: '2', at: '2026-10-06 09:12:47', trigger: '手动', added: 1, updated: 2, archived: 1, removed: 0, skipped: 0, errors: 0 },
  { key: '3', at: '2026-10-05 22:04:19', trigger: '自动', added: 3, updated: 0, archived: 0, removed: 1, skipped: 2, errors: 1 },
]

const SKIPPED = [
  { key: '1', file: 'hr/Leave_Policy_Admin_Guide -v 2.0.docx:Zone.Identifier', reason: '非文档附属文件，已忽略' },
]

const FORMATS = ['pdf', 'docx', 'xlsx', 'pptx', 'md', 'txt']

/** NAS 数据源管理：根目录与扫描策略、目录到权限的映射、同步结果。（仅界面，未对接后端） */
export default function DataSourceNas() {
  const [mappings, setMappings] = useState<DirMapping[]>(INITIAL_MAPPINGS)
  const [editing, setEditing] = useState<DirMapping | 'new' | null>(null)
  const [mapForm] = Form.useForm<DirMapping>()
  const [cfgForm] = Form.useForm()

  const openEdit = (m: DirMapping | 'new') => {
    mapForm.resetFields()
    if (m !== 'new') mapForm.setFieldsValue(m)
    setEditing(m)
  }

  const onSaveMapping = async () => {
    const v = await mapForm.validateFields()
    if (editing === 'new') setMappings((p) => [...p, { ...v, key: `m${Date.now()}` }])
    else if (editing) setMappings((p) => p.map((m) => (m.key === editing.key ? { ...m, ...v } : m)))
    message.success('已保存（界面演示）')
    setEditing(null)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>NAS 数据源管理</Title>
      <Alert type="info" showIcon message="当前页面仅为界面原型，数据为演示数据，保存/同步不会调用后端。" />

      <Card title="库配置" extra={<Button type="primary" onClick={() => message.success('配置已保存（演示）')}>保存配置</Button>}>
        <Form form={cfgForm} layout="vertical" initialValues={{
          rootPath: '/data', scanIntervalSec: 60, formats: ['pdf', 'docx', 'xlsx', 'pptx', 'md'],
          archiveOldVersions: true, autoSync: true,
        }}>
          <Row gutter={24}>
            <Col span={10}><Form.Item name="rootPath" label="根目录"><Input /></Form.Item></Col>
            <Col span={6}><Form.Item name="scanIntervalSec" label="扫描间隔（秒）"><InputNumber min={10} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={4}><Form.Item name="autoSync" label="自动同步" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col span={4}><Form.Item name="archiveOldVersions" label="新版本归档旧版" valuePropName="checked"><Switch /></Form.Item></Col>
          </Row>
          <Form.Item name="formats" label="支持的文件格式"><Checkbox.Group options={FORMATS} /></Form.Item>
        </Form>
      </Card>

      <Card
        title="目录权限映射"
        extra={<Button icon={<PlusOutlined />} onClick={() => openEdit('new')}>添加映射</Button>}
      >
        <Table<DirMapping>
          rowKey="key" dataSource={mappings} pagination={false} size="small"
          columns={[
            { title: '目录（相对根目录）', dataIndex: 'dir', render: (d: string) => <Text code>{d}</Text> },
            { title: '部门', dataIndex: 'department' },
            { title: '允许角色', dataIndex: 'roles', render: (r: string[]) => r.map((x) => <Tag key={x}>{x}</Tag>) },
            { title: '密级', dataIndex: 'clearance', align: 'center' },
            { title: '分区', dataIndex: 'compartments', render: (c: string[]) => (c.length ? c.map((x) => <Tag key={x} color="gold">{x}</Tag>) : '—') },
            {
              title: '操作',
              render: (_, m) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(m)}>编辑</Button>
                  <Popconfirm title={`删除映射 ${m.dir}？`} okText="删除" okButtonProps={{ danger: true }} cancelText="取消"
                    onConfirm={() => setMappings((p) => p.filter((x) => x.key !== m.key))}>
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          文件在 documents_index.csv 或文件头中另有声明时，以文件自身声明为准；此处是目录的默认权限。
        </Text>
      </Card>

      <Card title="同步" extra={
        <Button type="primary" icon={<SyncOutlined />} onClick={() => message.info('演示：已触发 NAS 同步')}>立即同步</Button>
      }>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}><Statistic title="文档总数" value={53} /></Col>
          <Col span={4}><Statistic title="已归档" value={1} /></Col>
          <Col span={4}><Statistic title="上次新增" value={0} /></Col>
          <Col span={4}><Statistic title="上次更新" value={0} /></Col>
          <Col span={4}><Statistic title="上次跳过" value={1} valueStyle={{ color: '#d48806' }} /></Col>
          <Col span={4}><Statistic title="上次错误" value={0} /></Col>
        </Row>
        <Title level={5}>最近同步记录</Title>
        <Table<SyncRecord>
          rowKey="key" dataSource={HISTORY} pagination={false} size="small"
          columns={[
            { title: '时间', dataIndex: 'at' },
            { title: '触发', dataIndex: 'trigger' },
            { title: '新增', dataIndex: 'added', align: 'right' },
            { title: '更新', dataIndex: 'updated', align: 'right' },
            { title: '归档', dataIndex: 'archived', align: 'right' },
            { title: '删除', dataIndex: 'removed', align: 'right' },
            { title: '跳过', dataIndex: 'skipped', align: 'right' },
            { title: '错误', dataIndex: 'errors', align: 'right', render: (n: number) => (n ? <Text type="danger">{n}</Text> : n) },
          ]}
        />
        <Title level={5} style={{ marginTop: 16 }}>被跳过的文件</Title>
        <Table
          rowKey="key" dataSource={SKIPPED} pagination={false} size="small"
          columns={[
            { title: '文件', dataIndex: 'file', render: (f: string) => <Text code>{f}</Text> },
            { title: '原因', dataIndex: 'reason' },
          ]}
        />
      </Card>

      <Modal
        title={editing === 'new' ? '添加目录映射' : '编辑目录映射'} open={!!editing}
        onOk={onSaveMapping} onCancel={() => setEditing(null)} okText="保存" cancelText="取消"
      >
        <Form form={mapForm} layout="vertical" initialValues={{ clearance: 1, roles: [], compartments: [] }}>
          <Form.Item name="dir" label="目录" rules={[{ required: true, message: '请输入目录' }]}><Input placeholder="legal/" /></Form.Item>
          <Form.Item name="department" label="部门" rules={[{ required: true, message: '请输入部门' }]}><Input /></Form.Item>
          <Form.Item name="roles" label="允许角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select mode="multiple" options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="clearance" label="密级（1-4）"><InputNumber min={1} max={4} /></Form.Item>
          <Form.Item name="compartments" label="分区（可空）"><Select mode="multiple" options={COMPARTMENT_OPTIONS} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
