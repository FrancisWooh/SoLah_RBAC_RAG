// UI-only mock data for the data source pages: nothing here talks to the backend.
// A tiny shared store keeps the overview page and the database page in step
// (add / delete on one page shows on the other) until the real API is wired in.
import { useSyncExternalStore } from 'react'

export type SourceType = 'nas' | 'postgresql'
export type SourceStatus = 'ok' | 'warning' | 'error' | 'pending'

export interface DbConfig {
  host: string
  port: number
  dbname: string
  user: string
  password: string
  schema?: string
  table: string
  idColumn: string
  titleColumn: string
  contentColumns: string[]
  categoryColumn?: string
  updatedAtColumn?: string
  attachRoles: string[]
  clearanceColumn?: string
  compartmentColumn?: string
  rolesColumn?: string
  defaultClearance: number
}

export interface NasConfig {
  rootPath: string
  scanIntervalSec: number
}

export interface DataSourceItem {
  id: number
  name: string
  type: SourceType
  status: SourceStatus
  recordCount: number
  lastSyncAt: string | null
  lastMessage?: string
  db?: DbConfig
  nas?: NasConfig
}

export const STATUS_META: Record<SourceStatus, { color: string; text: string }> = {
  ok: { color: 'green', text: '正常' },
  warning: { color: 'orange', text: '有警告' },
  error: { color: 'red', text: '同步失败' },
  pending: { color: 'default', text: '待同步' },
}

export const ROLE_OPTIONS = [
  'employee', 'compliance_officer', 'mlro', 'risk_analyst', 'card_ops', 'customer_support',
  'finance_analyst', 'hr_manager', 'marketing_manager', 'account_manager', 'engineer',
  'security_engineer', 'legal_counsel', 'exec',
].map((r) => ({ value: r, label: r }))

export const COMPARTMENT_OPTIONS = ['aml', 'credit', 'finance', 'hr', 'board', 'legal', 'security']
  .map((c) => ({ value: c, label: c }))

const dept = (
  id: number, name: string, dbname: string, role: string, count: number, status: SourceStatus = 'ok',
  lastMessage?: string,
): DataSourceItem => ({
  id, name, type: 'postgresql', status, recordCount: count, lastSyncAt: '2026-10-06 10:42:11', lastMessage,
  db: {
    host: 'postgres', port: 5432, dbname, user: 'rag_reader', password: 'rag_reader',
    table: 'knowledge_records', idColumn: 'record_code', titleColumn: 'title',
    contentColumns: ['content'], updatedAtColumn: 'updated_at',
    attachRoles: [role], clearanceColumn: 'required_clearance', compartmentColumn: 'compartment',
    rolesColumn: 'allowed_roles', defaultClearance: 1,
  },
})

const INITIAL: DataSourceItem[] = [
  {
    id: 1, name: 'NAS 文档库', type: 'nas', status: 'ok', recordCount: 53, lastSyncAt: '2026-10-06 10:40:03',
    nas: { rootPath: '/data', scanIntervalSec: 60 },
  },
  dept(2, 'HR Database', 'hr_db', 'hr_manager', 12),
  dept(3, 'Finance Database', 'finance_db', 'finance_analyst', 8),
  dept(4, 'Risk & Credit Database', 'risk_credit_db', 'risk_analyst', 8),
  dept(5, 'Compliance Database', 'compliance_db', 'compliance_officer', 8, 'warning',
    'CMP-Z09: unknown role(s): auditor; not indexed'),
  dept(6, 'Customer Support Database', 'support_db', 'customer_support', 6),
]

let items = INITIAL
let nextId = 7
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

export const sourceStore = {
  subscribe(l: () => void) {
    listeners.add(l)
    return () => listeners.delete(l)
  },
  getSnapshot: () => items,
  add(item: Omit<DataSourceItem, 'id' | 'status' | 'recordCount' | 'lastSyncAt'>) {
    items = [...items, { ...item, id: nextId++, status: 'pending', recordCount: 0, lastSyncAt: null }]
    emit()
  },
  update(id: number, patch: Partial<DataSourceItem>) {
    items = items.map((s) => (s.id === id ? { ...s, ...patch } : s))
    emit()
  },
  remove(id: number) {
    items = items.filter((s) => s.id !== id)
    emit()
  },
}

export function useDataSources(): DataSourceItem[] {
  return useSyncExternalStore(sourceStore.subscribe, sourceStore.getSnapshot)
}

export const NOW = () => new Date().toISOString().slice(0, 19).replace('T', ' ')
