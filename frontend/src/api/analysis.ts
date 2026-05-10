/**
 * A股单股分析 API。
 */

import { request, type ApiResponse } from './request'

export type AStockMarket = 'A股'
export type AnalysisStatus = 'pending' | 'running' | 'processing' | 'completed' | 'failed' | 'cancelled'
export type ExportFormat = 'markdown' | 'md' | 'docx' | 'pdf' | 'json'

export interface AnalysisRequest {
  market_type: AStockMarket
  stock_symbol: string
  analysis_date: string
  analysis_type: string
  data_sources: string[]
  analysis_depth: number
  include_news: boolean
  include_financials: boolean
  llm_provider?: string
  llm_model?: string
}

export interface SingleAnalysisRequest {
  symbol?: string
  stock_code?: string
  parameters?: {
    market_type?: AStockMarket
    analysis_date?: string
    research_depth?: string
    selected_analysts?: string[]
    custom_prompt?: string
    include_sentiment?: boolean
    include_risk?: boolean
    language?: 'zh-CN'
    quick_analysis_model?: string
    deep_analysis_model?: string
  }
}

export interface AnalysisStep {
  name?: string
  title?: string
  description?: string
  status?: string
  started_at?: string
  completed_at?: string
  duration?: number
  error_message?: string
}

export interface AnalysisProgress {
  analysis_id?: string
  task_id?: string
  status: AnalysisStatus
  progress: number
  current_step?: string | number
  current_step_name?: string
  current_step_description?: string
  step_detail?: string
  message?: string
  steps?: AnalysisStep[]
  started_at?: string
  updated_at?: string
  estimated_completion?: string
}

export interface AnalysisResult {
  analysis_id?: string
  task_id?: string
  symbol?: string
  stock_symbol?: string
  stock_code?: string
  stock_name?: string
  market_type?: AStockMarket
  analysis_date?: string
  analysis_type?: string
  summary?: string
  technical_analysis?: string
  fundamental_analysis?: string
  sentiment_analysis?: string
  news_analysis?: string
  recommendation?: string
  risk_assessment?: string
  confidence_score?: number
  risk_level?: string
  key_points?: string[]
  reports?: Record<string, string>
  decision?: Record<string, any>
  data_sources?: string[]
  llm_provider?: string
  llm_model?: string
  model_info?: string
  analysis_duration?: number
  execution_time?: number
  tokens_used?: number
  created_at?: string
  updated_at?: string
}

export interface AnalysisHistory {
  total: number
  page: number
  page_size: number
  analyses: AnalysisResult[]
}

const normalizeSingleRequest = (analysisRequest: SingleAnalysisRequest): SingleAnalysisRequest => {
  const symbol = String(analysisRequest.symbol || analysisRequest.stock_code || '').trim()
  return {
    ...analysisRequest,
    symbol,
    stock_code: symbol,
    parameters: {
      ...analysisRequest.parameters,
      market_type: 'A股',
      language: 'zh-CN'
    }
  }
}

export const analysisApi = {
  startAnalysis(analysisRequest: AnalysisRequest): Promise<ApiResponse<any>> {
    return request.post('/api/analysis/single', {
      symbol: analysisRequest.stock_symbol,
      stock_code: analysisRequest.stock_symbol,
      parameters: {
        market_type: 'A股',
        analysis_date: analysisRequest.analysis_date,
        research_depth: String(analysisRequest.analysis_depth),
        language: 'zh-CN',
        include_sentiment: analysisRequest.include_news,
        include_risk: true,
        quick_analysis_model: analysisRequest.llm_model,
        deep_analysis_model: analysisRequest.llm_model
      }
    })
  },

  startSingleAnalysis(analysisRequest: SingleAnalysisRequest): Promise<ApiResponse<any>> {
    return request.post('/api/analysis/single', normalizeSingleRequest(analysisRequest))
  },

  getTaskStatus(taskId: string): Promise<ApiResponse<any>> {
    return request.get(`/api/analysis/tasks/${taskId}/status`)
  },

  getProgress(analysisId: string): Promise<ApiResponse<AnalysisProgress>> {
    return request.get(`/api/analysis/${analysisId}/progress`)
  },

  getResult(analysisId: string): Promise<ApiResponse<AnalysisResult>> {
    return request.get(`/api/analysis/${analysisId}/result`)
  },

  getHistory(params?: {
    page?: number
    page_size?: number
    symbol?: string
    stock_code?: string
    start_date?: string
    end_date?: string
    status?: string
  }): Promise<ApiResponse<AnalysisHistory>> {
    return request.get('/api/analysis/user/history', {
      params: {
        ...params,
        market_type: 'A股'
      }
    })
  },

  getTaskList(params?: { status?: string; limit?: number; offset?: number }): Promise<ApiResponse<any>> {
    return request.get('/api/analysis/tasks', { params })
  },

  getTaskResult(taskId: string): Promise<ApiResponse<AnalysisResult>> {
    return request.get(`/api/analysis/tasks/${taskId}/result`)
  },

  deleteAnalysis(analysisId: string): Promise<ApiResponse<any>> {
    return request.delete(`/api/analysis/${analysisId}`)
  },

  deleteTask(taskId: string): Promise<ApiResponse<any>> {
    return request.delete(`/api/analysis/tasks/${taskId}`)
  },

  exportAnalysis(analysisId: string, format: ExportFormat = 'markdown'): Promise<Blob> {
    return request.get(`/api/analysis/${analysisId}/export`, {
      params: { format },
      responseType: 'blob'
    })
  },

  getStockInfo(symbol: string): Promise<ApiResponse<any>> {
    return request.get('/api/analysis/stock-info', {
      params: { symbol }
    })
  },

  searchStocks(query: string): Promise<ApiResponse<Array<{
    symbol: string
    name: string
    market: AStockMarket
    type: string
  }>>> {
    return request.get('/api/analysis/search', {
      params: { query }
    })
  }
}

export const MARKET_TYPES = {
  CN: 'A股'
} as const

export const ANALYSIS_TYPES = {
  BASIC: 'basic',
  DEEP: 'deep',
  TECHNICAL: 'technical',
  NEWS: 'news',
  COMPREHENSIVE: 'comprehensive'
} as const

export const DATA_SOURCES = {
  MONGODB: 'mongodb',
  TUSHARE: 'tushare',
  AKSHARE: 'akshare',
  BAOSTOCK: 'baostock'
} as const

export const ANALYSIS_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed'
} as const

export const STEP_STATUS = {
  PENDING: 'pending',
  ACTIVE: 'active',
  SUCCESS: 'success',
  ERROR: 'error'
} as const

export const validateAnalysisRequest = (analysisRequest: Partial<AnalysisRequest>): string[] => {
  const errors: string[] = []
  const symbol = String(analysisRequest.stock_symbol || '').trim()

  if (!symbol) {
    errors.push('请输入股票代码')
  } else if (!/^\d{6}$/.test(symbol)) {
    errors.push('精简版仅支持 6 位数字 A股代码')
  }

  if (analysisRequest.market_type && analysisRequest.market_type !== 'A股') {
    errors.push('精简版仅支持 A股市场')
  }
  if (!analysisRequest.analysis_date) errors.push('请选择分析日期')
  if (!analysisRequest.analysis_type) errors.push('请选择分析类型')

  return errors
}

export const formatAnalysisType = (type: string): string => {
  const typeMap: Record<string, string> = {
    basic: '基础分析',
    deep: '深度分析',
    technical: '技术分析',
    news: '新闻分析',
    comprehensive: '综合分析'
  }
  return typeMap[type] ?? type
}

export const formatMarketType = (_market: string): string => 'A股'

export const formatDataSource = (source: string): string => {
  const sourceMap: Record<string, string> = {
    mongodb: 'MongoDB',
    tushare: 'Tushare',
    akshare: 'AKShare',
    baostock: 'BaoStock'
  }
  return sourceMap[source] ?? source
}

export const getAnalysisHistory = async (params: {
  page?: number
  page_size?: number
  status?: string
}) => {
  const response = await analysisApi.getHistory(params)
  return response.data
}

export const getStockExamples = (): string[] => {
  return ['000001', '600519', '000002', '600036', '000858', '002415', '300059', '688981']
}

export const getStockPlaceholder = (): string => {
  return '请输入 6 位 A股代码，如 000001、600519'
}
