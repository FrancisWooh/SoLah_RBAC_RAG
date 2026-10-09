import { useState } from 'react'
import {
  Alert, Button, Descriptions, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Radio,
  Select, Space, Table, Tag, Typography, message,
} from 'antd'
import { DeleteOutlined, EyeOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons'

import {
  NOW, ROLE_OPTIONS, STATUS_META, sourceStore, useDataSources,
  type DataSourceItem, type SourceType,
} from './dataSourceMock'

const { Title, Text } = Typography

const TYPE_LABEL: Record<SourceType, string> = { nas: 'NAS 文件库', postgresql: 'PostgreSQL 数据库' }

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

/** 数据源总览：全部数据源的列表，可新增、查看、删除。（仅界面，未对接后端） */
export default function DataSources() {
  const sources = useDataSources()
  const [adding, setAdding] = useState(false)
  const [viewing, setViewing] = useState<DataSourceItem | null>(null)
  const [form] = Form.useForm<AddForm>()
  const type = Form.useWatch('type', form) ?? 'postgresql'

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
    message.success('已添加（界面演示，未保存到后端）')
    setAdding(false)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>数据源总览</Title>
      <Alert type="info" showIcon message="当前页面仅为界面原型，数据为演示数据，增删操作不会写入后端。" />

      <Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setAdding(true) }}>
          添加数据源
        </Button>
        <Button icon={<SyncOutlined />} onClick={() => message.info('演示：已触发全部数据源同步')}>
          全部立即同步
        </Button>
      </Space>

      <Table<DataSourceItem>
        rowKey="id"
        dataSource={sources}
        pagination={false}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '类型', dataIndex: 'type', render: (t: SourceType) => <Tag color={t === 'nas' ? 'blue' : 'purple'}>{TYPE_LABEL[t]}</Tag> },
          { title: '位置', render: (_, s) => <Text code>{location(s)}</Text> },
          {
            title: '状态', dataIndex: 'status',
            render: (st: DataSourceItem['status']) => <Tag color={STATUS_META[st].color}>{STATUS_META[st].text}</Tag>,
          },
          { title: '文档/记录数', dataIndex: 'recordCount', align: 'right' },
          { title: '上次同步', dataIndex: 'lastSyncAt', render: (v: string | null) => v ?? '—' },
          {
            title: '操作',
            render: (_, s) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => setViewing(s)}>查看</Button>
                <Button size="small" icon={<SyncOutlined />} onClick={() => {
                  sourceStore.update(s.id, { lastSyncAt: NOW(), status: 'ok' })
                  message.success(`演示：${s.name} 已同步`)
                }}>同步</Button>
                <Popconfirm
                  title={`删除数据源「${s.name}」？`}
                  description="该数据源的全部记录会从知识库撤出。"
                  okText="删除" okButtonProps={{ danger: true }} cancelText="取消"
                  onConfirm={() => { sourceStore.remove(s.id); message.success('已删除（演示）') }}
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal title="添加数据源" open={adding} onOk={onAdd} onCancel={() => setAdding(false)} okText="添加" cancelText="取消" width={560}>
        <Form form={form} layout="vertical" initialValues={{ type: 'postgresql', port: 5432, table: 'knowledge_records', scanIntervalSec: 60 }}>
          <Form.Item name="type" label="类型">
            <Radio.Group optionType="button" options={[
              { value: 'postgresql', label: 'PostgreSQL 数据库' },
              { value: 'nas', label: 'NAS 文件库' },
            ]} />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：Legal Database" />
          </Form.Item>
          {type === 'nas' ? (
            <>
              <Form.Item name="rootPath" label="根目录" rules={[{ required: true, message: '请输入目录' }]}>
                <Input placeholder="/data" />
              </Form.Item>
              <Form.Item name="scanIntervalSec" label="扫描间隔（秒）">
                <InputNumber min={10} style={{ width: 160 }} />
              </Form.Item>
            </>
          ) : (
            <>
              <Space align="start" size="middle">
                <Form.Item name="host" label="主机" rules={[{ required: true, message: '必填' }]}><Input placeholder="postgres" style={{ width: 220 }} /></Form.Item>
                <Form.Item name="port" label="端口"><InputNumber min={1} max={65535} style={{ width: 100 }} /></Form.Item>
                <Form.Item name="dbname" label="数据库名" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 160 }} /></Form.Item>
              </Space>
              <Space align="start" size="middle">
                <Form.Item name="user" label="只读账号" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 200 }} /></Form.Item>
                <Form.Item name="password" label="密码"><Input.Password style={{ width: 200 }} /></Form.Item>
              </Space>
              <Form.Item name="table" label="数据表"><Input /></Form.Item>
              <Form.Item name="attachRoles" label="归属角色（可访问该库的默认角色）" rules={[{ required: true, message: '请选择角色' }]}>
                <Select mode="multiple" options={ROLE_OPTIONS} />
              </Form.Item>
              <Text type="secondary">字段映射和权限列映射可在“数据库连接”页面进一步配置。</Text>
            </>
          )}
        </Form>
      </Modal>

      <Drawer title={viewing?.name} open={!!viewing} onClose={() => setViewing(null)} width={520}>
        {viewing && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="类型">{TYPE_LABEL[viewing.type]}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={STATUS_META[viewing.status].color}>{STATUS_META[viewing.status].text}</Tag></Descriptions.Item>
            <Descriptions.Item label="文档/记录数">{viewing.recordCount}</Descriptions.Item>
            <Descriptions.Item label="上次同步">{viewing.lastSyncAt ?? '—'}</Descriptions.Item>
            {viewing.lastMessage && <Descriptions.Item label="最近提示"><Text type="warning">{viewing.lastMessage}</Text></Descriptions.Item>}
            {viewing.nas && (<>
              <Descriptions.Item label="根目录"><Text code>{viewing.nas.rootPath}</Text></Descriptions.Item>
              <Descriptions.Item label="扫描间隔">{viewing.nas.scanIntervalSec} 秒</Descriptions.Item>
            </>)}
            {viewing.db && (<>
              <Descriptions.Item label="连接"><Text code>{viewing.db.user}@{viewing.db.host}:{viewing.db.port}/{viewing.db.dbname}</Text></Descriptions.Item>
              <Descriptions.Item label="数据表">{viewing.db.table}</Descriptions.Item>
              <Descriptions.Item label="归属角色">{viewing.db.attachRoles.map((r) => <Tag key={r}>{r}</Tag>)}</Descriptions.Item>
              <Descriptions.Item label="密级列 / 分区列">{viewing.db.clearanceColumn ?? '—'} / {viewing.db.compartmentColumn ?? '—'}</Descriptions.Item>
            </>)}
          </Descriptions>
        )}
      </Drawer>
    </Space>
  )
}
