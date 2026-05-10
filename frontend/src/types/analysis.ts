export enum AnalysisStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export interface AnalysisParameters {
  market_type: 'A股'
  analysis_date?: string
  research_depth: '快速' | '基础' | '标准' | '深度' | '全面' | string
  selected_analysts: string[]
  custom_prompt?: string
  include_sentiment?: boolean
  include_risk?: boolean
  include_charts?: boolean
  language: 'zh-CN'
  quick_analysis_model?: string
  deep_analysis_model?: string
}

export interface AnalysisResult {
  analysis_id?: string
  summary?: string
  recommendation?: string
  confidence_score?: number
  risk_level?: string
  key_points: string[]
  detailed_analysis?: Record<string, any>
  reports?: Record<string, string>
  charts: string[]
  tokens_used: number
  execution_time: number
  error_message?: string
}

export interface AnalysisTask {
  id?: string
  task_id: string
  user_id?: string
  symbol?: string
  stock_code?: string
  stock_name?: string
  status: AnalysisStatus
  progress: number
  created_at: string
  started_at?: string
  completed_at?: string
  worker_id?: string
  parameters: AnalysisParameters
  result?: AnalysisResult
  retry_count?: number
  max_retries?: number
  last_error?: string
}

export interface StockInfo {
  symbol: string
  code?: string
  full_symbol?: string
  name: string
  market: 'A股' | string
  industry?: string
  area?: string
  board?: string
  exchange?: string
  total_mv?: number
  circ_mv?: number
  pe?: number
  pb?: number
  pe_ttm?: number
  pb_mrq?: number
  roe?: number
  close?: number
  pct_chg?: number
  amount?: number
  turnover_rate?: number
  volume_ratio?: number
  ma20?: number
  rsi14?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
  dif?: number
  dea?: number
  macd_hist?: number
}

export interface SingleAnalysisRequest {
  symbol?: string
  stock_code?: string
  parameters?: AnalysisParameters
}

export interface AnalysisTaskResponse {
  task_id: string
  symbol?: string
  stock_code?: string
  stock_name?: string
  status: AnalysisStatus
  progress: number
  created_at: string
  started_at?: string
  completed_at?: string
  result?: AnalysisResult
}

export interface AnalysisHistoryQuery {
  status?: AnalysisStatus
  start_date?: string
  end_date?: string
  symbol?: string
  stock_code?: string
  page: number
  page_size: number
}

export interface AnalysisHistoryResponse {
  tasks: AnalysisTask[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface TaskProgress {
  task_id: string
  status: AnalysisStatus
  progress: number
  message?: string
  updated_at: string
}

export interface AnalysisStats {
  total_analyses: number
  successful_analyses: number
  failed_analyses: number
  success_rate: number
  average_execution_time: number
  total_tokens_used: number
  daily_analyses: number
  monthly_analyses: number
}

export interface QueueStatus {
  pending: number
  processing: number
  completed: number
  failed: number
  queue_size: number
}

export interface UserQueueStatus {
  pending: number
  processing: number
  concurrent_limit: number
  available_slots: number
}

export interface AnalysisReport {
  id: string
  task_id?: string
  title: string
  content: string
  format: 'html' | 'pdf' | 'markdown' | 'json'
  created_at: string
  download_url?: string
}
