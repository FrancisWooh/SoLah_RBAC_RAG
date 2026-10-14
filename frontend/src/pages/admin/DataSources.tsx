import { useState } from 'react'
import {
  Alert, Button, Descriptions, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Radio,
  Select, Space, Table, Tag, Typography, message,
} from 'antd'
import { DeleteOutlined, EyeOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

import {
  NOW, ROLE_OPTIONS, STATUS_META, sourceStore, useDataSources,
  type DataSourceItem, type SourceType,
} from './dataSourceMock'

const { Title, Text } = Typography

const location = (s: DataSourceItem) =>
  s.type === 'nas' ? s.nas?.rootPath : `${s.db?.host}:${s.db?.port}/${s.db?.dbname}`

interface AddForm {
  type: SourceType
  name: string
  rootPath?: string
  scanIntervalSec?: number
  host?: string
  port?: number
  dbname?: string
  user?: string
  password?: string
  table?: string
  attachRoles?: string[]
}

/** Data source overview: list of all data sources, with add/view/delete. (UI only, not backend-connected) */
export default function DataSources() {
  const { t } = useTranslation()
  const sources = useDataSources()
  const [adding, setAdding] = useState(false)
  const [viewing, setViewing] = useState<DataSourceItem | null>(null)
  const [form] = Form.useForm<AddForm>()
  const type = Form.useWatch('type', form) ?? 'postgresql'

  const typeLabel = (tp: SourceType) => tp === 'nas' ? t('admin.datasources.typeNas') : t('admin.datasources.typePostgres')

  const onAdd = async () => {
    const v = await form.validateFields()
    if (v.type === 'nas') {
      sourceStore.add({ name: v.name, type: 'nas', nas: { rootPath: v.rootPath!, scanIntervalSec: v.scanIntervalSec ?? 60 } })
    } else {
      sourceStore.add({
        name: v.name, type: 'postgresql',
        db: {
          host: v.host!, port: v.port ?? 5432, dbname: v.dbname!, user: v.user!, password: v.password ?? '',
          table: v.table ?? 'knowledge_records', idColumn: 'record_code', titleColumn: 'title',
          contentColumns: ['content'], attachRoles: v.attachRoles ?? [], defaultClearance: 1,
        },
      })
    }
    message.success(t('admin.datasources.addedDemo'))
    setAdding(false)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>{t('admin.datasources.title')}</Title>
      <Alert type="info" showIcon message={t('admin.datasources.prototypeNotice')} />

      <Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setAdding(true) }}>
          {t('admin.datasources.addSource')}
        </Button>
        <Button icon={<SyncOutlined />} onClick={() => message.info(t('admin.datasources.syncAllDemo'))}>
          {t('admin.datasources.syncAll')}
        </Button>
      </Space>

      <Table<DataSourceItem>
        rowKey="id"
        dataSource={sources}
        pagination={false}
        columns={[
          { title: t('admin.datasources.colName'), dataIndex: 'name', render: (_, s) => s.nameKey ? t(s.nameKey) : s.name },
          { title: t('admin.datasources.colType'), dataIndex: 'type', render: (tp: SourceType) => <Tag color={tp === 'nas' ? 'blue' : 'purple'}>{typeLabel(tp)}</Tag> },
          { title: t('admin.datasources.colLocation'), render: (_, s) => <Text code>{location(s)}</Text> },
          {
            title: t('admin.datasources.colStatus'), dataIndex: 'status',
            render: (st: DataSourceItem['status']) => <Tag color={STATUS_META[st].color}>{t(STATUS_META[st].textKey)}</Tag>,
          },
          { title: t('admin.datasources.colDocCount'), dataIndex: 'recordCount', align: 'right' },
          { title: t('admin.datasources.colLastSync'), dataIndex: 'lastSyncAt', render: (v: string | null) => v ?? '—' },
          {
            title: t('admin.datasources.colOperation'),
            render: (_, s) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => setViewing(s)}>{t('admin.datasources.view')}</Button>
                <Button size="small" icon={<SyncOutlined />} onClick={() => {
                  sourceStore.update(s.id, { lastSyncAt: NOW(), status: 'ok' })
                  message.success(t('admin.datasources.syncedDemo', { name: s.nameKey ? t(s.nameKey) : s.name }))
                }}>{t('admin.datasources.sync')}</Button>
                <Popconfirm
                  title={t('admin.datasources.deleteConfirm', { name: s.nameKey ? t(s.nameKey) : s.name })}
                  description={t('admin.datasources.deleteDesc')}
                  okText={t('common.delete')} okButtonProps={{ danger: true }} cancelText={t('common.cancel')}
                  onConfirm={() => { sourceStore.remove(s.id); message.success(t('admin.datasources.deletedDemo')) }}
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>{t('common.delete')}</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal title={t('admin.datasources.addModalTitle')} open={adding} onOk={onAdd} onCancel={() => setAdding(false)} okText={t('admin.datasources.add')} cancelText={t('common.cancel')} width={560}>
        <Form form={form} layout="vertical" initialValues={{ type: 'postgresql', port: 5432, table: 'knowledge_records', scanIntervalSec: 60 }}>
          <Form.Item name="type" label={t('admin.datasources.formType')}>
            <Radio.Group optionType="button" options={[
              { value: 'postgresql', label: t('admin.datasources.typePostgres') },
              { value: 'nas', label: t('admin.datasources.typeNas') },
            ]} />
          </Form.Item>
          <Form.Item name="name" label={t('admin.datasources.formName')} rules={[{ required: true, message: t('admin.datasources.formNameRequired') }]}>
            <Input placeholder="Legal Database" />
          </Form.Item>
          {type === 'nas' ? (
            <>
              <Form.Item name="rootPath" label={t('admin.datasources.formRootPath')} rules={[{ required: true, message: t('admin.datasources.formRootPathRequired') }]}>
                <Input placeholder="/data" />
              </Form.Item>
              <Form.Item name="scanIntervalSec" label={t('admin.datasources.formScanInterval')}>
                <InputNumber min={10} style={{ width: 160 }} />
              </Form.Item>
            </>
          ) : (
            <>
              <Space align="start" size="middle">
                <Form.Item name="host" label={t('admin.datasources.formHost')} rules={[{ required: true, message: t('admin.datasources.formRequired') }]}><Input placeholder="postgres" style={{ width: 220 }} /></Form.Item>
                <Form.Item name="port" label={t('admin.datasources.formPort')}><InputNumber min={1} max={65535} style={{ width: 100 }} /></Form.Item>
                <Form.Item name="dbname" label={t('admin.datasources.formDbName')} rules={[{ required: true, message: t('admin.datasources.formRequired') }]}><Input style={{ width: 160 }} /></Form.Item>
              </Space>
              <Space align="start" size="middle">
                <Form.Item name="user" label={t('admin.datasources.formUser')} rules={[{ required: true, message: t('admin.datasources.formRequired') }]}><Input style={{ width: 200 }} /></Form.Item>
                <Form.Item name="password" label={t('admin.datasources.formPassword')}><Input.Password style={{ width: 200 }} /></Form.Item>
              </Space>
              <Form.Item name="table" label={t('admin.datasources.formTable')}><Input /></Form.Item>
              <Form.Item name="attachRoles" label={t('admin.datasources.formAttachRoles')} rules={[{ required: true, message: t('admin.datasources.formAttachRolesRequired') }]}>
                <Select mode="multiple" options={ROLE_OPTIONS} />
              </Form.Item>
              <Text type="secondary">{t('admin.datasources.fieldMappingHint')}</Text>
            </>
          )}
        </Form>
      </Modal>

      <Drawer title={viewing ? (viewing.nameKey ? t(viewing.nameKey) : viewing.name) : ''} open={!!viewing} onClose={() => setViewing(null)} width={520}>
        {viewing && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label={t('admin.datasources.drawerType')}>{typeLabel(viewing.type)}</Descriptions.Item>
            <Descriptions.Item label={t('admin.datasources.drawerStatus')}><Tag color={STATUS_META[viewing.status].color}>{t(STATUS_META[viewing.status].textKey)}</Tag></Descriptions.Item>
            <Descriptions.Item label={t('admin.datasources.drawerDocCount')}>{viewing.recordCount}</Descriptions.Item>
            <Descriptions.Item label={t('admin.datasources.drawerLastSync')}>{viewing.lastSyncAt ?? '—'}</Descriptions.Item>
            {viewing.lastMessage && <Descriptions.Item label={t('admin.datasources.drawerLastMessage')}><Text type="warning">{viewing.lastMessage}</Text></Descriptions.Item>}
            {viewing.nas && (<>
              <Descriptions.Item label={t('admin.datasources.drawerRootPath')}><Text code>{viewing.nas.rootPath}</Text></Descriptions.Item>
              <Descriptions.Item label={t('admin.datasources.drawerScanInterval')}>{viewing.nas.scanIntervalSec} {t('admin.datasources.drawerSeconds')}</Descriptions.Item>
            </>)}
            {viewing.db && (<>
              <Descriptions.Item label={t('admin.datasources.drawerConnection')}><Text code>{viewing.db.user}@{viewing.db.host}:{viewing.db.port}/{viewing.db.dbname}</Text></Descriptions.Item>
              <Descriptions.Item label={t('admin.datasources.drawerTable')}>{viewing.db.table}</Descriptions.Item>
              <Descriptions.Item label={t('admin.datasources.drawerAttachRoles')}>{viewing.db.attachRoles.map((r) => <Tag key={r}>{r}</Tag>)}</Descriptions.Item>
              <Descriptions.Item label={t('admin.datasources.drawerClearanceCompartment')}>{viewing.db.clearanceColumn ?? '—'} / {viewing.db.compartmentColumn ?? '—'}</Descriptions.Item>
            </>)}
          </Descriptions>
        )}
      </Drawer>
    </Space>
  )
}
