# TradingAgents-CN A股 MCP 迁移细化方案

## Summary

结论：本项目适合迁移到 MCP，但不是“把所有自定义工具都换成 MCP”。正确做法是保留现有四个 unified LangChain 工具作为分析师稳定入口，只把底层数据获取、新闻聚合、反爬和第三方 API 调用迁到 MCP Server。

当前应升级为 MCP 的是：A股行情、A股基本面、A股新闻、资金/情绪数据。  
不应升级的是：本地技术指标计算、分析师提示词、决策逻辑、报告生成、MongoDB 缓存读写。

调研依据：  
[China-Stock-MCP](https://github.com/xinkuang/china-stock-mcp) 覆盖 A股历史行情、实时行情、新闻、三大财报、资金流、估值、技术榜单、指数和行业数据。  
[FinanceMCP](https://github.com/guangxiangdebizi/FinanceMCP) 覆盖 `finance_news`、`stock_data`、`company_performance`、`money_flow`、`dragon_tiger_inst`、`hot_news_7x24` 等。  
[@tushare/mcp](https://www.npmjs.com/package/%40tushare/mcp) 提供 100+ Tushare 接口，通过 `sdk_call`、`sdk_schema`、`sdk_search` 统一调用。  
[a-share-mcp-server](https://github.com/firmmaple/a-share-mcp-server) 基于 Baostock，适合作为免费历史行情和财务备份源。

## Key Changes

### 1. 第三方 MCP Server 选型

| MCP Server | 用途 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| China-Stock-MCP | A股行情、财报、新闻、资金、估值、行业 | A股覆盖最贴近项目，支持 stdio/HTTP，内置缓存和多源降级 | 底层仍依赖 AKShare/网页源，质量需实测 | P0 主力数据源 |
| FinanceMCP | 新闻、资金流、龙虎榜、宏观、公司财务 | 工具分层清晰，新闻和资金类工具比本项目自研更完整 | 生产建议配置自己的 Tushare Token，公共云不可作为唯一依赖 | P0 新闻/情绪主源 |
| @tushare/mcp | 标准 Tushare 数据接口 | 100+ API，接口通用，适合精确财务字段 | 需要 Token，部分高级接口有积分门槛 | P1 精准财务补充 |
| a-share-mcp-server | Baostock 历史行情、财务、指数 | 免费、A股专用、无 Token | 实时性弱，新闻/资金覆盖不足 | P2 备用源 |

不采用：Yahoo Finance MCP、Reddit MCP、Finnhub MCP、美股/港股 MCP，因为项目已限定 A股。iFinD MCP 暂不采用，除非后续明确接受机构级付费数据。

### 2. 哪些自定义工具替换为 MCP

| 当前入口 | 处理方式 | MCP 替换目标 |
|---|---|---|
| `get_stock_market_data_unified` | 保留函数名和 LangChain 工具定义，内部改走 MCP 数据源 | China-Stock-MCP: `get_hist_data`, `get_realtime_data`, `get_stock_a_code_name`, `get_cni_index_hist` |
| `get_stock_fundamentals_unified` | 保留入口，内部先 MCP，再本地降级 | FinanceMCP: `company_performance`; China-Stock-MCP: `get_balance_sheet`, `get_income_statement`, `get_cash_flow`, `get_financial_metrics`, `get_stock_value`; @tushare/mcp: `income`, `balancesheet`, `cashflow`, `fina_indicator` |
| `get_stock_news_unified` | 保留入口，重写新闻源优先级 | FinanceMCP: `finance_news`, `hot_news_7x24`; China-Stock-MCP: `get_news_data`, `get_stock_research_report` |
| `get_stock_sentiment_unified` | 保留入口，改为资金/交易行为情绪 | FinanceMCP: `money_flow`, `dragon_tiger_inst`, `block_trade`, `margin_trade`; China-Stock-MCP: `get_fund_flow`, `get_investor_sentiment`, `get_stock_technical_rank` |
| `AKShareProvider` 反爬逻辑 | 不立即删除，逐步旁路 | 行情、新闻、财报优先走 MCP，AKShare 只作为最后降级 |
| `google_news.py`, `chinese_finance.py`, `realtime_news.py` | 不再作为 A股主链路 | 被 FinanceMCP/China-Stock-MCP 替代 |
| 本地技术指标 `indicators.py`、stockstats | 保留 | MCP 不替代，除非只获取原始行情 |
| BaoStock/Tushare 本地 Provider | 保留为降级 | 可逐步由 a-share-mcp-server / @tushare/mcp 接管 |

### 3. 目标技术架构

新的调用链：

```text
Market/Fundamentals/News/Social Analysts
        ↓
现有四个 unified LangChain 工具
        ↓
A股数据门面 AShareDataFacade
        ↓
MCPDataGateway
        ↓
FinanceMCP / China-Stock-MCP / @tushare/mcp / 本地降级源
        ↓
标准化输出 + MongoDB/本地缓存
```

实现上新增一个 MCP 网关层，而不是让 LLM 直接看到第三方 MCP 的几十个工具。这样可以避免工具爆炸、提示词污染和调用不可控。

新增接口约定：

- `MCPDataGateway.call(capability, symbol, params)`：按能力路由到白名单 MCP 工具。
- `ChinaMCPProvider(BaseStockDataProvider)`：适配现有 `connect/get_stock_quotes/get_historical_data/get_financial_data/get_stock_basic_info`。
- `MCPCallResult`：统一记录 `server/tool/arguments/content/latency_ms/error/cached`。
- `DataSourceCode.MCP_CHINA`：加入数据源枚举。
- 默认优先级：`MongoDB cache -> MCP_CHINA -> Tushare -> AKShare -> BaoStock`。

配置默认值：

```env
MCP_ENABLED=true
MCP_LEGACY_FALLBACK_ENABLED=true
MCP_TIMEOUT_SECONDS=30
MCP_CHINA_STOCK_TRANSPORT=stdio
MCP_FINANCE_TRANSPORT=streamable_http
MCP_PRIMARY_NEWS=finance_mcp
MCP_PRIMARY_MARKET=china_stock_mcp
TUSHARE_TOKEN=optional
```

`trading_graph.py` 的 A股模式下只保留四个 unified 工具给分析师使用；YFinance、Finnhub、SimFin、Reddit、Google News 从活跃 ToolNode 中移除或配置关闭，但不批量删除文件。

## Implementation Plan

1. 新增 MCP 基础设施：实现 MCP 客户端、连接池、超时、工具发现、白名单路由、统一错误包装。
2. 新增 `ChinaMCPProvider`：把 China-Stock-MCP 和 FinanceMCP 的返回结果标准化成现有 provider 格式。
3. 改造数据源管理器：加入 `MCP_CHINA`，把 MCP 放到 A股默认优先级第一位，但保留本地 Tushare/AKShare/BaoStock 降级。
4. 改造四个 unified 工具内部逻辑：入口函数名、参数和分析师提示词不变，只替换内部数据来源。
5. 精简 A股 ToolNode：A股项目不再暴露美股、港股、Reddit、Finnhub、SimFin、Google News 备份工具。
6. 新闻链路重写：优先 `finance_news` 和 `hot_news_7x24`，其次个股新闻/研报，最后才走本地旧逻辑。
7. 情绪链路重写：从“社交媒体情绪”改成更适合 A股的“资金流 + 龙虎榜 + 大宗交易 + 融资融券 + 技术榜单”。
8. 保留旧文件作为降级和回滚，不做批量删除；稳定后再单独整理依赖和废弃模块。

## Test Plan

- 单元测试：MCP 工具路由、字段标准化、错误包装、超时降级、缓存命中。
- 集成测试：用 `000001`、`600519`、`300750` 覆盖行情、财报、新闻、资金流。
- 降级测试：关闭 FinanceMCP，新闻应降到 China-Stock-MCP；关闭全部 MCP，应降到本地旧数据源。
- A股边界测试：输入美股/港股代码时，在 A股模式下明确拒绝或提示不支持。
- 回归测试：四个分析师仍然只调用原来的 unified 工具名，最终报告结构不变。
- 质量验收：同一股票的收盘价、交易日期、财报期、新闻时间必须可追踪到数据源；MCP 失败不能导致整个分析流程崩溃。

## Assumptions

默认项目只服务 A股。  
默认优先使用本地/自托管 MCP Server，公共云 MCP 只用于开发验证。  
默认不把第三方 MCP 工具直接暴露给 LLM。  
默认不删除旧 provider，先旁路、验证、回滚可用后再清理。
