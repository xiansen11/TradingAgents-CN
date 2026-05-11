import { ApiClient } from './request'

export type ToolTestStatus = 'success' | 'error' | 'partial'

export interface ToolTestSources {
  market_scope: string
  modules: string[]
  data_sources: string[]
  mcp_servers: string[]
  mcp_capabilities: string[]
}

export interface ToolTestRequest {
  code: string
  include_raw: boolean
  timeout_seconds: number
  modules: string[]
}

export interface ToolDiagnostic {
  source: string
  module: string
  status: 'success' | 'error' | 'skipped' | 'unsupported'
  latency_ms: number
  message: string
  sample?: unknown
  raw?: unknown
}

export interface ToolTestSummary {
  code: string
  name: string
  overall_status: ToolTestStatus
  success_count: number
  failure_count: number
  skipped_count?: number
  unsupported_count?: number
  total_count: number
  total_latency_ms: number
}

export interface StockSnapshot {
  quote?: Record<string, any> | null
  technical?: Record<string, any> | null
  fundamentals?: Record<string, any> | null
  news?: {
    count: number
    items: Array<Record<string, any>>
  } | null
}

export interface ToolTestResult {
  summary: ToolTestSummary
  snapshot: StockSnapshot
  diagnostics: ToolDiagnostic[]
}

export const toolTestsApi = {
  getSources() {
    return ApiClient.get<ToolTestSources>('/api/tool-tests/sources')
  },

  testStock(payload: ToolTestRequest) {
    return ApiClient.post<ToolTestResult>('/api/tool-tests/stock', payload, {
      timeout: Math.max(payload.timeout_seconds * 1000 * 12, 60000)
    })
  }
}
