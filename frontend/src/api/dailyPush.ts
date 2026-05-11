import { ApiClient } from './request'

export type DailyPushRunStatus =
  | 'queued'
  | 'generating'
  | 'waiting_to_push'
  | 'sending'
  | 'sent'
  | 'failed'

export interface DailyPushAnalysisParameters {
  research_depth: string
  selected_analysts: string[]
  quick_analysis_model?: string
  deep_analysis_model?: string
}

export interface DailyPushFeishuConfig {
  app_id: string
  app_secret?: string
  chat_id: string
  domain?: string
  has_app_secret?: boolean
}

export interface DailyPushSubscription {
  id: string
  name: string
  enabled: boolean
  stock_symbols: string[]
  analysis_time: string
  push_time: string
  timezone: string
  analysis_parameters: DailyPushAnalysisParameters
  feishu: DailyPushFeishuConfig
  next_run_at?: string
  created_at?: string
  updated_at?: string
}

export interface DailyPushSubscriptionPayload {
  name: string
  enabled: boolean
  stock_symbols: string[]
  analysis_time: string
  push_time: string
  timezone: string
  analysis_parameters: DailyPushAnalysisParameters
  feishu: DailyPushFeishuConfig
}

export interface DailyPushRun {
  id: string
  subscription_id: string
  subscription_name?: string
  stock_symbol: string
  run_type: 'scheduled' | 'manual' | 'test'
  run_date: string
  status: DailyPushRunStatus
  task_id?: string
  report_id?: string
  analysis_id?: string
  error_message?: string
  created_at?: string
  started_at?: string
  sent_at?: string
  completed_at?: string
  updated_at?: string
}

export interface DailyPushRunList {
  items: DailyPushRun[]
  total: number
  limit: number
  offset: number
}

export interface DailyPushRunStart {
  run_id: string
  task_id?: string
  stock_symbol: string
  status: string
}

export interface DailyPushRunNowResponse {
  started: DailyPushRunStart[]
  skipped: Array<{
    stock_symbol: string
    reason: string
    run_id?: string
  }>
}

export const dailyPushApi = {
  getSubscriptions() {
    return ApiClient.get<DailyPushSubscription[]>('/api/daily-push/subscriptions')
  },

  createSubscription(payload: DailyPushSubscriptionPayload) {
    return ApiClient.post<DailyPushSubscription>('/api/daily-push/subscriptions', payload)
  },

  updateSubscription(id: string, payload: Partial<DailyPushSubscriptionPayload>) {
    return ApiClient.put<DailyPushSubscription>(`/api/daily-push/subscriptions/${id}`, payload)
  },

  deleteSubscription(id: string) {
    return ApiClient.delete<void>(`/api/daily-push/subscriptions/${id}`)
  },

  testSend(id: string, stockSymbol?: string) {
    return ApiClient.post<DailyPushRunStart>(`/api/daily-push/subscriptions/${id}/test-send`, {
      stock_symbol: stockSymbol || undefined
    })
  },

  runNow(id: string) {
    return ApiClient.post<DailyPushRunNowResponse>(`/api/daily-push/subscriptions/${id}/run-now`)
  },

  getRuns(params?: {
    subscription_id?: string
    status?: string
    limit?: number
    offset?: number
  }) {
    return ApiClient.get<DailyPushRunList>('/api/daily-push/runs', params)
  }
}
