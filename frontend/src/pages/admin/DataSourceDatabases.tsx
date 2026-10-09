import { useState } from 'react'
import {
  Alert, Button, Divider, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag,
  Typography, message,
} from 'antd'
import { ApiOutlined, DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'

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

/** 数据库连接管理：连接信息、字段映射、权限列映射，可测试连接。（仅界面，未对接后端） */
export default function DataSourceDatabases() {
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
      message.success('演示：连接成功，找到数据表，读取到 12 条记录')
    }, 800)
  }

  const onSave = async () => {
    const { name, syncIntervalSec: _interval, ...db } = await form.validateFields()
    if (editing === 'new') sourceStore.add({ name, type: 'postgresql', db })
    else if (editing) sourceStore.update(editing.id, { name, db })
    message.success('已保存（界面演示，未写入后端）')
    setEditing(null)
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>数据库连接管理</Title>
      <Alert type="info" showIcon message="当前页面仅为界面原型，数据为演示数据，保存/测试不会调用后端。" />

      <Button type="primary" icon={<PlusOutlined />} style={{ alignSelf: 'flex-start' }} onClick={() => openEdit('new')}>
        添加数据库连接
      </Button>

      <Table<DataSourceItem>
        rowKey="id" dataSource={dbs} pagination={false}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '连接', render: (_, s) => <Text code>{s.db!.user}@{s.db!.host}:{s.db!.port}/{s.db!.dbname}</Text> },
          { title: '数据表', render: (_, s) => s.db!.table },
          { title: '归属角色', render: (_, s) => s.db!.attachRoles.map((r) => <Tag key={r}>{r}</Tag>) },
          { title: '状态', render: (_, s) => <Tag color={STATUS_META[s.status].color}>{STATUS_META[s.status].text}</Tag> },
          { title: '记录数', dataIndex: 'recordCount', align: 'right' },
          { title: '上次同步', dataIndex: 'lastSyncAt', render: (v: string | null) => v ?? '—' },
          {
            title: '操作',
            render: (_, s) => (
              <Space>
                <Button size="small" icon={<ApiOutlined />} onClick={() => {
                  sourceStore.update(s.id, { lastSyncAt: NOW(), status: 'ok' })
                  message.success(`演示：${s.name} 连接正常`)
                }}>测试连接</Button>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(s)}>编辑</Button>
                <Popconfirm title={`删除连接「${s.name}」？`} description="该库的全部记录会从知识库撤出。"
                  okText="删除" okButtonProps={{ danger: true }} cancelText="取消"
                  onConfirm={() => { sourceStore.remove(s.id); message.success('已删除（演示）') }}>
                  <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
        expandable={{
          expandedRowRender: (s) => s.lastMessage
            ? <Text type="warning">最近提示：{s.lastMessage}</Text>
            : <Text type="secondary">无告警</Text>,
        }}
      />

      <Modal
        title={editing === 'new' ? '添加数据库连接' : '编辑数据库连接'} open={!!editing} width={720}
        onCancel={() => setEditing(null)} okText="保存" cancelText="取消" onOk={onSave}
        footer={(_, { OkBtn, CancelBtn }) => (
          <Space>
            <Button icon={<ApiOutlined />} loading={testing} onClick={onTest}>测试连接</Button>
            <CancelBtn />
            <OkBtn />
          </Space>
        )}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}><Input placeholder="Legal Database" /></Form.Item>

          <Divider titlePlacement="start" plain>连接信息</Divider>
          <Space align="start" size="middle" wrap>
            <Form.Item name="host" label="主机" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 220 }} /></Form.Item>
            <Form.Item name="port" label="端口" rules={[{ required: true, message: '必填' }]}><InputNumber min={1} max={65535} style={{ width: 100 }} /></Form.Item>
            <Form.Item name="dbname" label="数据库名" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="user" label="只读账号" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="password" label="密码"><Input.Password style={{ width: 180 }} /></Form.Item>
            <Form.Item name="schema" label="Schema（可空）"><Input style={{ width: 140 }} /></Form.Item>
          </Space>

          <Divider titlePlacement="start" plain>表与字段映射</Divider>
          <Space align="start" size="middle" wrap>
            <Form.Item name="table" label="数据表" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 200 }} /></Form.Item>
            <Form.Item name="idColumn" label="主键列" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="titleColumn" label="标题列" rules={[{ required: true, message: '必填' }]}><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="updatedAtColumn" label="更新时间列"><Input style={{ width: 160 }} /></Form.Item>
            <Form.Item name="categoryColumn" label="分类列（可空）"><Input style={{ width: 160 }} /></Form.Item>
          </Space>
          <Form.Item name="contentColumns" label="内容列（可多个）" rules={[{ required: true, message: '至少一列' }]}>
            <Select mode="tags" tokenSeparators={[',']} placeholder="输入列名后回车" />
          </Form.Item>

          <Divider titlePlacement="start" plain>权限映射</Divider>
          <Form.Item name="attachRoles" label="归属角色（记录未单独指定角色时的默认角色）" rules={[{ required: true, message: '请选择角色' }]}>
            <Select mode="multiple" options={ROLE_OPTIONS} />
          </Form.Item>
          <Space align="start" size="middle" wrap>
            <Form.Item name="clearanceColumn" label="密级列"><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="compartmentColumn" label="分区列"><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="rolesColumn" label="记录角色列"><Input style={{ width: 180 }} /></Form.Item>
            <Form.Item name="defaultClearance" label="默认密级（1-4）"><InputNumber min={1} max={4} /></Form.Item>
          </Space>
          <Text type="secondary" style={{ display: 'block' }}>
            密级列为空值时使用默认密级；分区列为空表示普通记录；角色列为空时继承归属角色。角色未知或密级非法的记录不会入库。
          </Text>

          <Divider titlePlacement="start" plain>同步</Divider>
          <Form.Item name="syncIntervalSec" label="同步间隔（秒）"><InputNumber min={5} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
