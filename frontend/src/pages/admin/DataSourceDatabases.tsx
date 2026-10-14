import { useState } from 'react'
import {
  Alert, Button, Divider, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag,
  Typography, message,
} from 'antd'
import { ApiOutlined, DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

import {
  NOW, ROLE_OPTIONS, STATUS_META, sourceStore, useDataSources,
  type DataSourceItem, type DbConfig,
} from './dataSourceMock'

const { Title, Text } = Typography

interface DbForm extends DbConfig {
  name: string
  syncIntervalSec: number
}

const EMPTY: Partial<DbForm> = {
  port: 5432, table: 'knowledge_records', idColumn: 'record_code', titleColumn: 'title',
  contentColumns: ['content'], updatedAtColumn: 'updated_at', clearanceColumn: 'required_clearance',
  compartmentColumn: 'compartment', rolesColumn: 'allowed_roles', defaultClearance: 1, syncIntervalSec: 30,
}

/** Database connection management: connection info, field mapping, permission column mapping, with test connection. (UI only, not backend-connected) */
export default function DataSourceDatabases() {
  const { t } = useTranslation()
  const dbs = useDataSources().filter((s) => s.type === 'postgresql')
  const [editing, setEditing] = useState<DataSourceItem | 'new' | null>(null)
  const [testing, setTesting] = useState(false)
  const [form] = Form.useForm<DbForm>()

  const openEdit = (s: DataSourceItem | 'new') => {
    form.resetFields()
    form.setFieldsValue(s === 'new' ? EMPTY : { ...s.db!, name: s.name, syncIntervalSec: 30 })
    setEditing(s)
  }

  const onTest = async () => {
    await form.validateFields(['host', 'port', 'dbname', 'user'])
    setTesting(true)
    setTimeout(() => {
      setTesting(false)
      message.success(t('admin.datasourceDatabases.testSuccess'))
    }, 800)
  }

  const onSave = async () => {
    const { name, syncIntervalSec: _interval, ...db } = await form.validateFields()
    if (editing === 'new') sourceStore.add({ name, type: 'postgresql', db })
    else if (editing) sourceStore.update(editing.id, { name, db })
    message.success(t('admin.datasourceDatabases.savedDemo'))
    setEditing(null)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>{t('admin.datasourceDatabases.title')}</Title>
      <Alert type="info" showIcon message={t('admin.datasourceDatabases.prototypeNotice')} />

      <Button type="primary" icon={<PlusOutlined />} style={{ alignSelf: 'flex-start' }} onClick={() => openEdit('new')}>
        {t('admin.datasourceDatabases.addConnection')}
      </Button>

      <Table<DataSourceItem>
        rowKey="id" dataSource={dbs} pagination={false}
        columns={[
          { title: t('admin.datasourceDatabases.colName'), dataIndex: 'name' },
          { title: t('admin.datasourceDatabases.colConnection'), render: (_, s) => <Text code>{s.db!.user}@{s.db!.host}:{s.db!.port}/{s.db!.dbname}</Text> },
          { title: t('admin.datasourceDatabases.colTable'), render: (_, s) => s.db!.table },
          { title: t('admin.datasourceDatabases.colAttachRoles'), render: (_, s) => s.db!.attachRoles.map((r) => <Tag key={r}>{r}</Tag>) },
          { title: t('admin.datasourceDatabases.colStatus'), render: (_, s) => <Tag color={STATUS_META[s.status].color}>{t(STATUS_META[s.status].textKey)}</Tag> },
          { title: t('admin.datasourceDatabases.colRecords'), dataIndex: 'recordCount', align: 'right' },
          { title: t('admin.datasourceDatabases.colLastSync'), dataIndex: 'lastSyncAt', render: (v: string | null) => v ?? '—' },
          {
            title: t('admin.datasourceDatabases.colOperation'),
            render: (_, s) => (
              <Space>
                <Button size="small" icon={<ApiOutlined />} onClick={() => {
                  sourceStore.update(s.id, { lastSyncAt: NOW(), status: 'ok' })
                  message.success(t('admin.datasourceDatabases.connectionNormalDemo', { name: s.name }))
                }}>{t('admin.datasourceDatabases.testConnection')}</Button>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(s)}>{t('admin.datasourceDatabases.editBtn')}</Button>
                <Popconfirm title={t('admin.datasourceDatabases.deleteConnectionConfirm', { name: s.name })} description={t('admin.datasourceDatabases.deleteDesc')}
                  okText={t('common.delete')} okButtonProps={{ danger: true }} cancelText={t('common.cancel')}
                  onConfirm={() => { sourceStore.remove(s.id); message.success(t('admin.datasourceDatabases.deletedDemo')) }}>
                  <Button size="small" danger icon={<DeleteOutlined />}>{t('common.delete')}</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
        expandable={{
          expandedRowRender: (s) => s.lastMessage
            ? <Text type="warning">{t('admin.datasourceDatabases.lastMessage', { message: s.lastMessage })}</Text>
            : <Text type="secondary">{t('admin.datasourceDatabases.noAlert')}</Text>,
        }}
      />

      <Modal
        title={editing === 'new' ? t('admin.datasourceDatabases.addModalTitle') : t('admin.datasourceDatabases.editModalTitle')} open={!!editing} width={720}
        onCancel={() => setEditing(null)} okText={t('common.save')} cancelText={t('common.cancel')} onOk={onSave}
        footer={(_, { OkBtn, CancelBtn }) => (
          <Space>
            <Button icon={<ApiOutlined />} loading={testing} onClick={onTest}>{t('admin.datasourceDatabases.testConnection')}</Button>
            <CancelBtn />
            <OkBtn />
          </Space>
        )}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('admin.datasourceDatabases.formName')} rules={[{ required: true, message: t('admin.datasourceDatabases.formNameRequired') }]}><Input placeholder="Legal Database" /></Form.Item>

          <Divider titlePlacement="start" plain>{t('admin.datasourceDatabases.sectionConnection')}</Divider>
          <Space align="start" size="middle" wrap>
            <Form.Item name="host" label={t('admin.datasourceDatabases.formHost')} rules={[{ required: true, message: t('admin.datasourceDatabases.formHostRequired') }]}><Input style={{ width: 220 }} /></Form.Item>
            <Form.Item name="port" label={t('admin.datasourceDatabases.formPort')} rules={[{ required: true, message: t('admin.datasourceDatabases.formPortRequired') }]}><InputNumber min={1} max={65535} style={{ width: 100 }} /></Form.Item>
            <Form.Item name="dbname" label={t('admin.datasourceDatabases.formDbName')} rules={[{ required: true, message: t('admin.datasourceDatabases.formDbNameRequired') }]}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="user" label={t('admin.datasourceDatabases.formUser')} rules={[{ required: true, message: t('admin.datasourceDatabases.formUserRequired') }]}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="password" label={t('admin.datasourceDatabases.formPassword')}><Input.Password style={{ width: 180 }} /></Form.Item>
            <Form.Item name="schema" label={t('admin.datasourceDatabases.formSchema')}><Input style={{ width: 140 }} /></Form.Item>
          </Space>

          <Divider titlePlacement="start" plain>{t('admin.datasourceDatabases.sectionFieldMapping')}</Divider>
          <Space align="start" size="middle" wrap>
            <Form.Item name="table" label={t('admin.datasourceDatabases.formTable')} rules={[{ required: true, message: t('admin.datasourceDatabases.formTableRequired') }]}><Input style={{ width: 200 }} /></Form.Item>
            <Form.Item name="idColumn" label={t('admin.datasourceDatabases.formIdColumn')} rules={[{ required: true, message: t('admin.datasourceDatabases.formIdColumnRequired') }]}><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="titleColumn" label={t('admin.datasourceDatabases.formTitleColumn')} rules={[{ required: true, message: t('admin.datasourceDatabases.formTitleColumnRequired') }]}><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="updatedAtColumn" label={t('admin.datasourceDatabases.formUpdatedAtColumn')}><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="categoryColumn" label={t('admin.datasourceDatabases.formCategoryColumn')}><Input style={{ width: 160 }} /></Form.Item>
          </Space>
          <Form.Item name="contentColumns" label={t('admin.datasourceDatabases.formContentColumns')} rules={[{ required: true, message: t('admin.datasourceDatabases.formContentColumnsRequired') }]}>
            <Select mode="tags" tokenSeparators={[',']} placeholder={t('admin.datasourceDatabases.formContentColumnsPlaceholder')} />
          </Form.Item>

          <Divider titlePlacement="start" plain>{t('admin.datasourceDatabases.sectionPermissionMapping')}</Divider>
          <Form.Item name="attachRoles" label={t('admin.datasourceDatabases.formAttachRoles')} rules={[{ required: true, message: t('admin.datasourceDatabases.formAttachRolesRequired') }]}>
            <Select mode="multiple" options={ROLE_OPTIONS} />
          </Form.Item>
          <Space align="start" size="middle" wrap>
            <Form.Item name="clearanceColumn" label={t('admin.datasourceDatabases.formClearanceColumn')}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="compartmentColumn" label={t('admin.datasourceDatabases.formCompartmentColumn')}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="rolesColumn" label={t('admin.datasourceDatabases.formRolesColumn')}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="defaultClearance" label={t('admin.datasourceDatabases.formDefaultClearance')}><InputNumber min={1} max={4} /></Form.Item>
          </Space>
          <Text type="secondary" style={{ display: 'block' }}>
            {t('admin.datasourceDatabases.permissionHint')}
          </Text>

          <Divider titlePlacement="start" plain>{t('admin.datasourceDatabases.sectionSync')}</Divider>
          <Form.Item name="syncIntervalSec" label={t('admin.datasourceDatabases.formSyncInterval')}><InputNumber min={5} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
