// 精简版仅支持 A股。
export const normalizeMarketForAnalysis = (_market?: unknown): 'A股' => 'A股'

export const exchangeCodeToMarket = (_exchangeCode?: string): 'A股' => 'A股'

export const getMarketByStockCode = (_stockCode: string): 'A股' => 'A股'

export default {
  normalizeMarketForAnalysis,
  exchangeCodeToMarket,
  getMarketByStockCode
}
