import { useState } from 'react'
import {
  Alert, Button, Card, Checkbox, Col, Form, Input, InputNumber, Modal, Popconfirm, Row, Select,
  Space, Statistic, Switch, Table, Tag, Typography, message,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

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
  triggerKey: string
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
  { key: '1', at: '2026-10-06 10:40:03', triggerKey: 'admin.datasourceNas.triggerAuto', added: 0, updated: 0, archived: 0, removed: 0, skipped: 1, errors: 0 },
  { key: '2', at: '2026-10-06 09:12:47', triggerKey: 'admin.datasourceNas.triggerManual', added: 1, updated: 2, archived: 1, removed: 0, skipped: 0, errors: 0 },
  { key: '3', at: '2026-10-05 22:04:19', triggerKey: 'admin.datasourceNas.triggerAuto', added: 3, updated: 0, archived: 0, removed: 1, skipped: 2, errors: 1 },
]

const SKIPPED = [
  { key: '1', file: 'hr/Leave_Policy_Admin_Guide -v 2.0.docx:Zone.Identifier', reasonKey: 'admin.datasourceNas.skipReason' },
]

const FORMATS = ['pdf', 'docx', 'xlsx', 'pptx', 'md', 'txt']

/** NAS data source management: root path & scan strategy, directory-to-permission mapping, sync results. (UI only, not backend-connected) */
export default function DataSourceNas() {
  const { t } = useTranslation()
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
    message.success(t('admin.datasourceNas.savedDemo'))
    setEditing(null)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>{t('admin.datasourceNas.title')}</Title>
      <Alert type="info" showIcon message={t('admin.datasourceNas.prototypeNotice')} />

      <Card title={t('admin.datasourceNas.configTitle')} extra={<Button type="primary" onClick={() => message.success(t('admin.datasourceNas.configSavedDemo'))}>{t('admin.datasourceNas.saveConfig')}</Button>}>
        <Form form={cfgForm} layout="vertical" initialValues={{
          rootPath: '/data', scanIntervalSec: 60, formats: ['pdf', 'docx', 'xlsx', 'pptx', 'md'],
          archiveOldVersions: true, autoSync: true,
        }}>
          <Row gutter={24}>
            <Col span={10}><Form.Item name="rootPath" label={t('admin.datasourceNas.formRootPath')}><Input /></Form.Item></Col>
            <Col span={6}><Form.Item name="scanIntervalSec" label={t('admin.datasourceNas.formScanInterval')}><InputNumber min={10} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={4}><Form.Item name="autoSync" label={t('admin.datasourceNas.formAutoSync')} valuePropName="checked"><Switch /></Form.Item></Col>
            <Col span={4}><Form.Item name="archiveOldVersions" label={t('admin.datasourceNas.formArchiveOldVersions')} valuePropName="checked"><Switch /></Form.Item></Col>
          </Row>
          <Form.Item name="formats" label={t('admin.datasourceNas.formFormats')}><Checkbox.Group options={FORMATS} /></Form.Item>
        </Form>
      </Card>

      <Card
        title={t('admin.datasourceNas.mappingTitle')}
        extra={<Button icon={<PlusOutlined />} onClick={() => openEdit('new')}>{t('admin.datasourceNas.addMapping')}</Button>}
      >
        <Table<DirMapping>
          rowKey="key" dataSource={mappings} pagination={false} size="small"
          columns={[
            { title: t('admin.datasourceNas.colDir'), dataIndex: 'dir', render: (d: string) => <Text code>{d}</Text> },
            { title: t('admin.datasourceNas.colDept'), dataIndex: 'department' },
            { title: t('admin.datasourceNas.colRoles'), dataIndex: 'roles', render: (r: string[]) => r.map((x) => <Tag key={x}>{x}</Tag>) },
            { title: t('admin.datasourceNas.colClearance'), dataIndex: 'clearance', align: 'center' },
            { title: t('admin.datasourceNas.colCompartments'), dataIndex: 'compartments', render: (c: string[]) => (c.length ? c.map((x) => <Tag key={x} color="gold">{x}</Tag>) : '—') },
            {
              title: t('admin.datasourceNas.colOperation'),
              render: (_, m) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(m)}>{t('admin.datasourceNas.editBtn')}</Button>
                  <Popconfirm title={t('admin.datasourceNas.deleteMappingConfirm', { dir: m.dir })} okText={t('common.delete')} okButtonProps={{ danger: true }} cancelText={t('common.cancel')}
                    onConfirm={() => setMappings((p) => p.filter((x) => x.key !== m.key))}>
                    <Button size="small" danger icon={<DeleteOutlined />}>{t('common.delete')}</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          {t('admin.datasourceNas.mappingHint')}
        </Text>
      </Card>

      <Card title={t('admin.datasourceNas.syncTitle')} extra={
        <Button type="primary" icon={<SyncOutlined />} onClick={() => message.info(t('admin.datasourceNas.syncDemo'))}>{t('admin.datasourceNas.syncNow')}</Button>
      }>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statTotalDocs')} value={53} /></Col>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statArchived')} value={1} /></Col>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statLastAdded')} value={0} /></Col>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statLastUpdated')} value={0} /></Col>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statLastSkipped')} value={1} valueStyle={{ color: '#d48806' }} /></Col>
          <Col span={4}><Statistic title={t('admin.datasourceNas.statLastErrors')} value={0} /></Col>
        </Row>
        <Title level={5}>{t('admin.datasourceNas.recentSyncRecords')}</Title>
        <Table<SyncRecord>
          rowKey="key" dataSource={HISTORY} pagination={false} size="small"
          columns={[
            { title: t('admin.datasourceNas.colTime'), dataIndex: 'at' },
            { title: t('admin.datasourceNas.colTrigger'), dataIndex: 'triggerKey', render: (k: string) => t(k) },
            { title: t('admin.datasourceNas.colAdded'), dataIndex: 'added', align: 'right' },
            { title: t('admin.datasourceNas.colUpdated'), dataIndex: 'updated', align: 'right' },
            { title: t('admin.datasourceNas.colArchived'), dataIndex: 'archived', align: 'right' },
            { title: t('admin.datasourceNas.colRemoved'), dataIndex: 'removed', align: 'right' },
            { title: t('admin.datasourceNas.colSkipped'), dataIndex: 'skipped', align: 'right' },
            { title: t('admin.datasourceNas.colErrors'), dataIndex: 'errors', align: 'right', render: (n: number) => (n ? <Text type="danger">{n}</Text> : n) },
          ]}
        />
        <Title level={5} style={{ marginTop: 16 }}>{t('admin.datasourceNas.skippedFiles')}</Title>
        <Table
          rowKey="key" dataSource={SKIPPED} pagination={false} size="small"
          columns={[
            { title: t('admin.datasourceNas.colFile'), dataIndex: 'file', render: (f: string) => <Text code>{f}</Text> },
            { title: t('admin.datasourceNas.colReason'), dataIndex: 'reasonKey', render: (k: string) => t(k) },
          ]}
        />
      </Card>

      <Modal
        title={editing === 'new' ? t('admin.datasourceNas.addMappingTitle') : t('admin.datasourceNas.editMappingTitle')} open={!!editing}
        onOk={onSaveMapping} onCancel={() => setEditing(null)} okText={t('common.save')} cancelText={t('common.cancel')}
      >
        <Form form={mapForm} layout="vertical" initialValues={{ clearance: 1, roles: [], compartments: [] }}>
          <Form.Item name="dir" label={t('admin.datasourceNas.formDir')} rules={[{ required: true, message: t('admin.datasourceNas.formDirRequired') }]}><Input placeholder="legal/" /></Form.Item>
          <Form.Item name="department" label={t('admin.datasourceNas.formDept')} rules={[{ required: true, message: t('admin.datasourceNas.formDeptRequired') }]}><Input /></Form.Item>
          <Form.Item name="roles" label={t('admin.datasourceNas.colRoles')} rules={[{ required: true, message: t('admin.datasourceNas.formRolesRequired') }]}>
            <Select mode="multiple" options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="clearance" label={t('admin.datasourceNas.formClearanceRange')}><InputNumber min={1} max={4} /></Form.Item>
          <Form.Item name="compartments" label={t('admin.datasourceNas.formCompartments')}><Select mode="multiple" options={COMPARTMENT_OPTIONS} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
