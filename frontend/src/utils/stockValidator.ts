/**
 * A股代码格式验证工具。
 * 精简版只接受 6 位数字股票代码。
 */

export interface StockValidationResult {
  valid: boolean
  market?: 'A股'
  message?: string
  normalizedCode?: string
}

export function validateAStock(code: string): StockValidationResult {
  const cleanCode = code.trim()

  if (!/^\d{6}$/.test(cleanCode)) {
    return {
      valid: false,
      message: '精简版仅支持 6 位数字 A股代码'
    }
  }

  return {
    valid: true,
    market: 'A股',
    normalizedCode: cleanCode
  }
}

export function validateStockCode(code: string): StockValidationResult {
  if (!code || !code.trim()) {
    return {
      valid: false,
      message: '请输入股票代码'
    }
  }

  return validateAStock(code)
}

export function getStockCodeFormatHelp(): string {
  return '6位数字，如：000001（平安银行）、600519（贵州茅台）'
}

export function getStockCodeExamples(): string[] {
  return ['000001', '600519', '000858', '300750']
}

export function formatStockCode(code: string): string {
  const validation = validateStockCode(code)
  return validation.normalizedCode || code
}
