# TradingAgents-CN MCP 替换方案

> 基于 TradingAgents-CN 项目现有工具链的深度分析，整理出适合替换为 MCP Server 的模块、推荐方案、收费情况及集成步骤。

---

## 一、项目工具全景与痛点分析

### 1.1 现有工具清单

| 模块 | 文件 | 行数 | 数据源 | 调用方式 | 核心痛点 |
|------|------|------|--------|---------|---------|
| AKShare 提供器 | `providers/china/akshare.py` | 1676 | 东方财富/新浪 | Python SDK + 爬虫 | 反爬严重，需 curl_cffi 模拟 TLS 指纹 |
| Tushare 提供器 | `providers/china/tushare.py` | 1609 | Tushare API | Python SDK | 无重试、无缓存、Token 管理复杂 |
| 美股数据提供器 | `providers/us/optimized.py` | 563 | yfinance/FinnHub/Alpha Vantage | Python SDK + HTTP | 多源降级逻辑复杂 |
| Alpha Vantage | `providers/us/alpha_vantage_common.py` | 317 | Alpha Vantage API | HTTP API | 规范，痛点少 |
| 港股提供器 | `providers/hk/improved_hk.py` | ~800 | AKShare/yfinance | Python SDK | 多源降级，财务指标获取不稳定 |
| Google 新闻 | `news/google_news.py` | 134 | Google News | 网页爬虫 | 爬虫，易被封、结构变化就挂 |
| 实时新闻 | `news/realtime_news.py` | 976 | FinnHub/AV/NewsAPI/财联社 | HTTP API + RSS | 5+源降级链，维护成本高 |
| 中国财经新闻 | `news/chinese_finance.py` | 331 | 东方财富等 | HTTP 爬虫 | **半成品**，核心方法返回模拟数据 |
| Reddit 新闻 | `news/reddit.py` | 135 | 本地 JSONL 文件 | 文件读取 | 数据过时 |
| 统一新闻工具 | `tools/unified_news_tool.py` | 588 | 聚合上述所有源 | 聚合层 | 聚合逻辑复杂，含数据库同步 |
| 技术指标计算 | `tools/analysis/indicators.py` | ~300 | 本地计算 | 纯计算 | 无外部依赖 |
| BaoStock | `providers/china/baostock.py` | ~200 | BaoStock API | Python SDK | 轻量稳定 |

### 1.2 痛点分级

- **🔴 严重**：反爬虫、爬虫被封、半成品代码
- **🟡 中等**：无重试/缓存、多源降级维护成本高
- **🟢 轻微**：代码规范、功能完整、稳定可靠

---

## 二、MCP 替换优先级评估

### 评估维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 痛点严重度 | 30% | 反爬、稳定性、半成品等 |
| MCP 可用性 | 25% | 是否有成熟的 MCP Server 可直接替换 |
| 替换收益 | 25% | 数据质量提升、维护成本降低 |
| 替换难度 | 20% | 接口兼容性、数据格式差异 |

### 优先级总表

```
优先级   模块                          痛点    MCP可用性  收益    难度    推荐 MCP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0🔴   新闻爬虫(google_news)          极高    ✅ 成熟    极高    低     OpenNews-MCP
P0🔴   中国财经(chinese_finance)      极高    ✅ 成熟    极高    低     财联社快讯 MCP
P0🔴   实时新闻聚合(realtime_news)    高      ✅ 成熟    高      中     FinanceMCP
P0🔴   AKShare 反爬层                高      ✅ 成熟    高      中     China-Stock-MCP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P1🟡   Tushare 提供器                中      ✅ 可用    中高    中     Tushare-MCP / FinanceMCP
P1🟡   美股数据提供器                中      ✅ 可用    中      中     Yahoo Finance MCP
P1🟡   港股提供器                    中      ✅ 可用    中      中     FinanceMCP / iFinD MCP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P2🟢   Alpha Vantage                 低      ⚠️ 有限    低      低     暂不替换
P2🟢   Reddit 新闻                   低      ⚠️ 可选    低      低     按需
P2🟢   技术指标计算                  无      ❌ 不适用  无      —      不替换（纯本地计算）
P2🟢   BaoStock                     低      ✅ 可用    低      低     按需
```

---

## 三、P0 级替换方案（强烈推荐）

### 3.1 新闻爬虫模块替换

**替换目标**：

| 当前模块 | 行数 | 痛点 |
|---------|------|------|
| `google_news.py` | 134 | 网页爬虫，Google 随时改版就挂，429 限流频繁 |
| `chinese_finance.py` | 331 | 半成品，核心方法返回模拟数据 |
| `realtime_news.py` | 976 | 5+ 新闻源降级链，维护成本极高 |
| `unified_news_tool.py` | 588 | 聚合逻辑复杂 |

**推荐 MCP Server**：

#### FinanceMCP（首选）

- **收费**：免费（公共云服务）
- **功能**：
  - `finance_news`：财经新闻搜索（7+ 主流财经媒体）
  - `hot_news_7x24`：7×24 热点新闻（单次至多 1500 条，80% 去重）
- **接入方式**：
  ```json
  {
    "mcpServers": {
      "finance-mcp": {
        "disabled": false,
        "timeout": 600,
        "type": "sse",
        "url": "http://106.14.205.176:3101/sse"
      }
    }
  }
  ```

#### 财联社快讯 MCP（补充）

- **收费**：免费
- **功能**：分钟级突发公告、涨停利好、政策事件、盘中异动预警
- **适合**：情绪分析师实时监控

**替换后收益**：

- 删除 ~1629 行爬虫/半成品代码
- 解决 `chinese_finance.py` 半成品问题
- 84+ 专业财经信源替代 Google 爬虫
- 分钟级实时快讯能力
- 不再需要维护反爬虫代码

---

### 3.2 AKShare 反爬层替换

**替换目标**：

| 当前模块 | 行数 | 痛点 |
|---------|------|------|
| `akshare.py` 反爬处理 | ~150 | curl_cffi 模拟 Chrome 120 TLS 指纹 |
| `akshare.py` monkey-patch | ~100 | 拦截 requests.get，注入浏览器 Headers |
| `akshare.py` Docker 适配 | ~50 | Docker 环境 curl_cffi 兼容性问题 |

**推荐 MCP Server**：

#### China-Stock-MCP（魔搭官方）

- **收费**：免费，无需 API Key
- **底层**：AKShare 全家桶，东财/新浪/同花顺多源自动降级
- **功能**：实时 K 线、三大财报、30+ 技术指标、公告、资金
- **接入方式**：
  ```json
  {
    "mcpServers": {
      "china-stock": {
        "command": "uvx",
        "args": ["china-stock-mcp"]
      }
    }
  }
  ```

#### FinanceMCP（替代方案）

- **收费**：免费
- **功能**：Tushare + 东财 + 同花顺三合一，10 大市场覆盖
- **优势**：三源自动降级由 MCP 处理，项目无需关心反爬

**替换后收益**：

- 删除 ~300 行反爬代码（curl_cffi + monkey-patch + Docker 适配）
- 不再需要 `curl_cffi` 依赖
- 不再需要维护东方财富反爬策略
- 请求延迟由 MCP Server 内部优化

---

## 四、P1 级替换方案（推荐）

### 4.1 Tushare 提供器替换

**替换目标**：`providers/china/tushare.py`（1609 行）

**痛点**：无重试机制、无缓存、Token 双源管理复杂

**推荐 MCP Server**：

#### Tushare-MCP

- **收费**：MCP 免费，需 Tushare Token（免费注册）
- **功能**：高频因子、一致预期、北向资金、机构持仓、财报明细
- **适合**：量化策略 Agent、因子选股智能体
- **接入方式**：
  ```json
  {
    "mcpServers": {
      "tushare-mcp": {
        "command": "node",
        "args": ["./tushare_MCP/build/index.js"],
        "env": {
          "TUSHARE_TOKEN": "你的Token"
        }
      }
    }
  }
  ```

#### FinanceMCP（替代方案）

- **功能**：`company_performance`（A股财务分析，13 种数据类型）、`macro_econ`（11 个宏观指标）
- **优势**：Token 管理由 MCP 处理，自带重试和缓存

---

### 4.2 美股数据提供器替换

**替换目标**：`providers/us/optimized.py`（563 行）

**痛点**：三源降级（yfinance→Alpha Vantage→FinnHub）逻辑复杂

**推荐 MCP Server**：

#### Yahoo Finance MCP

- **收费**：免费
- **功能**：美股、期权、全球指数、外汇、大宗商品行情
- **适合**：全球市场数据统一入口

#### FinanceMCP（替代方案）

- **功能**：`company_performance_us`（美股 4 大财务报表 + 综合财务指标）、`stock_data`（10 大市场 + 加密货币）
- **优势**：一个 MCP 覆盖 A/H/美股

#### Alpaca-MCP（实盘交易）

- **收费**：免费（纸盘）/ 按交易量收费（实盘）
- **功能**：下单、撤单、账户持仓、盈亏查询
- **适合**：AI 自动交易闭环

---

### 4.3 港股提供器替换

**替换目标**：`providers/hk/improved_hk.py`（~800 行）

**痛点**：依赖 AKShare 新浪财经接口，财务指标获取不稳定

**推荐 MCP Server**：

#### FinanceMCP

- **功能**：`company_performance_hk`（港股利润表、资产负债表、现金流量表）
- **优势**：港股数据更稳定，PE/PB 自动计算

#### 同花顺 iFinD MCP（机构级）

- **收费**：3.8万~4.2万/年/席
- **功能**：2026 年新增港股全套投研工具
- **适合**：机构投资者

---

## 五、P2 级替换方案（可选）

| 模块 | 推荐 MCP | 收费 | 建议 |
|------|---------|------|------|
| Alpha Vantage | 暂无成熟 MCP | — | 当前实现已规范，暂不替换 |
| Reddit 新闻 | Reddit MCP | 免费 | 如需实时数据可替换，离线数据无需替换 |
| 技术指标计算 | ❌ 不适用 | — | 纯本地计算，MCP 反而增加延迟，**不建议替换** |
| BaoStock | BaoStock-MCP | 免费 | 当前方案稳定，按需替换 |

---

## 六、推荐 MCP Server 收费一览

### 6.1 免费 MCP Server

| MCP Server | 收费 | 数据源 | 功能覆盖 | 接入方式 |
|-----------|------|--------|---------|---------|
| **FinanceMCP** | ✅ 免费 | Tushare+东财+同花顺 | A/H/美股+基金+债券+宏观+新闻（14个工具） | SSE 公共云 / 本地部署 |
| **China-Stock-MCP** | ✅ 免费 | AKShare 全家桶 | A股行情+财报+技术指标+新闻 | stdio / HTTP |
| **东方财富妙想 Skills** | ✅ 免费 | 东方财富官方 | 行情+财务+龙虎榜+资金+研报+舆情 | OpenClaw 平台 |
| **BaoStock-MCP** | ✅ 免费 | BaoStock | A股历史行情+复权+指数成分 | stdio |
| **A-Stock-MCP-Server** | ✅ 免费 | AKShare | A股实时行情+财务数据 | stdio |
| **实时股票分析 MCP** | ✅ 免费 | 东方财富 | 实时行情+查找股票 | stdio / HTTP |
| **Finance-MCP (FlowLLM)** | ✅ 免费 | Tushare+同花顺爬虫+DashScope | 20+ 投研流程+同花顺爬虫 | stdio / SSE / HTTP |

### 6.2 需要 Token 但免费的 MCP Server

| MCP Server | 收费 | 需要的凭证 | 获取方式 |
|-----------|------|-----------|---------|
| **Tushare-MCP** | MCP 免费 | Tushare Token | https://tushare.pro 免费注册 |
| **FinanceMCP (带 Token)** | MCP 免费 | Tushare Token | 同上，无速率限制 |

### 6.3 收费 MCP Server

| MCP Server | 收费 | 适合 | 说明 |
|-----------|------|------|------|
| **同花顺 iFinD MCP** | 3.8万~4.2万/年/席 | 机构投资者 | 全市场数据，申万行业分类，龙虎榜，研报 |
| **News-MCP-Server** | 免费 1000次/月，专业版 $49/月 | 英文新闻 | 7+ 新闻 API，7300+ 免费日请求 |

---

## 七、替换后代码量变化估算

| 模块 | 当前行数 | 替换后行数 | 可减少 | 原因 |
|------|---------|-----------|--------|------|
| `google_news.py` | 134 | 0 | **-134** | 完全由 OpenNews-MCP / FinanceMCP 替代 |
| `chinese_finance.py` | 331 | 0 | **-331** | 半成品，完全由 FinanceMCP 替代 |
| `realtime_news.py` | 976 | ~100 | **-876** | 5+源降级链由 MCP 替代，仅保留 MCP 调用封装 |
| `unified_news_tool.py` | 588 | ~80 | **-508** | 聚合逻辑由 MCP 替代 |
| `akshare.py` 反爬部分 | 1676 | ~1400 | **-276** | 删除 curl_cffi/monkey-patch/反爬代码 |
| `tushare.py` Token 管理 | 1609 | ~1500 | **-109** | Token 管理简化 |
| `optimized.py` 降级链 | 563 | ~400 | **-163** | 多源降级由 MCP 处理 |
| **合计** | **5877** | **~2480** | **-3397** | **减少约 58%** |

---

## 八、渐进式迁移路线图

### 阶段 1：新闻模块替换（1-2 周，收益最大）

```
替换目标：google_news.py + chinese_finance.py + realtime_news.py
使用 MCP：FinanceMCP（finance_news + hot_news_7x24）
预期收益：
  - 删除 ~1341 行爬虫代码
  - 解决半成品问题（chinese_finance.py）
  - 7+ 专业财经信源替代 Google 爬虫
  - 7×24 热点新闻能力
```

### 阶段 2：A股数据源替换（2-3 周）

```
替换目标：akshare.py 反爬层 + tushare.py
使用 MCP：China-Stock-MCP + FinanceMCP
预期收益：
  - 删除 ~276 行反爬代码
  - 不再需要 curl_cffi
  - Token 管理简化
  - 量化因子数据更丰富
```

### 阶段 3：港美股数据源替换（2-3 周）

```
替换目标：optimized.py + improved_hk.py
使用 MCP：FinanceMCP + Yahoo Finance MCP
预期收益：
  - 多源降级逻辑简化
  - 港股财务数据更稳定
  - 全球市场数据统一入口
```

### 阶段 4：保留本地降级（持续）

```
保留模块：indicators.py（纯计算）+ BaoStock（回测备用）
策略：MCP 不可用时自动降级到本地工具
```

---

## 九、集成架构示意

```
┌─────────────────────────────────────────────────────────────────┐
│ TradingAgents-CN 多智能体系统                                    │
│                                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ 基本面分析师│ │ 技术分析师 │ │ 新闻分析师 │ │ 情绪分析师 │  │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘  │
│        │              │              │              │          │
│        ▼              ▼              ▼              ▼          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              MCP Client (统一工具网关)                    │  │
│  │  - 工具发现：自动注册 MCP Server 工具                     │  │
│  │  - 路由分发：按工具名路由到对应 MCP Server                │  │
│  │  - 降级策略：MCP 不可用时回退到本地工具                   │  │
│  └────────────────────────┬─────────────────────────────────┘  │
└───────────────────────────┼────────────────────────────────────┘
                            │ stdio / SSE / HTTP
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ FinanceMCP       │ │ China-Stock  │ │ Tushare-MCP      │
│ (主力数据源)     │ │ -MCP         │ │ (量化因子)        │
│                  │ │ (AKShare)    │ │                   │
│ • stock_data     │ │              │ │ • 高频因子        │
│ • company_perf   │ │ • A股行情    │ │ • 一致预期        │
│ • finance_news   │ │ • 财务数据   │ │ • 北向资金        │
│ • hot_news_7x24  │ │ • 技术指标   │ │ • 机构持仓        │
│ • macro_econ     │ │ • 新闻公告   │ │ • 财报明细        │
│ • money_flow     │ │ • 资金流向   │ │ • 指数权重        │
│ • dragon_tiger   │ │              │ │                   │
│ • margin_trade   │ │              │ │                   │
│ • block_trade    │ │              │ │                   │
│ • fund_data      │ │              │ │                   │
│ • index_data     │ │              │ │                   │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

---

## 十、具体集成步骤

### 10.1 安装 MCP 客户端库

```bash
pip install langchain-mcp mcp
```

### 10.2 创建 MCP 工具适配器

```python
# tradingagents/tools/mcp_adapter.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class FinanceMCPAdapter:
    """FinanceMCP 适配器 - 通过 MCP 协议获取金融数据"""

    def __init__(self, tushare_token: str = None):
        self.tushare_token = tushare_token
        self.server_params = StdioServerParameters(
            command="uvx",
            args=["finance-mcp", "config=default", "mcp.transport=stdio"],
            env={"TUSHARE_API_TOKEN": tushare_token} if tushare_token else {}
        )

    async def get_tools(self):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                from langchain_mcp import MCPToolkit
                toolkit = MCPToolkit(session=session)
                tools = await toolkit.get_tools()
                return tools
```

### 10.3 替换分析师工具绑定

```python
# 修改 fundamentals_analyst.py 示例

# 原来：
# tools = [toolkit.get_stock_fundamentals_unified]

# 替换为：
mcp_adapter = FinanceMCPAdapter(tushare_token="your_token")
mcp_tools = await mcp_adapter.get_tools()
tools = [t for t in mcp_tools if t.name in [
    "company_performance",
    "stock_data",
    "macro_econ"
]]
```

### 10.4 添加降级策略

```python
# MCP 不可用时回退到本地工具
try:
    mcp_tools = await mcp_adapter.get_tools()
    tools = mcp_tools
except Exception as e:
    logger.warning(f"MCP 不可用，回退到本地工具: {e}")
    tools = [toolkit.get_stock_fundamentals_unified]
```

---

## 十一、推荐零成本方案

```
┌─────────────────────────────────────────────────────────────┐
│ TradingAgents-CN 零成本 MCP 方案                             │
│                                                              │
│  基本面分析师 ──→ FinanceMCP (company_performance)           │
│  技术分析师   ──→ FinanceMCP (stock_data + 技术指标)        │
│  新闻分析师   ──→ FinanceMCP (finance_news + hot_news_7x24) │
│  情绪分析师   ──→ FinanceMCP (money_flow + dragon_tiger)    │
│                                                              │
│  备用数据源：China-Stock-MCP (AKShare 免费降级)             │
│  量化因子：Tushare-MCP (免费 Token)                         │
└─────────────────────────────────────────────────────────────┘

总费用：0 元

需要注册的免费账号：
1. Tushare Token（免费注册）：https://tushare.pro
2. 阿里百炼 API Key（免费额度，可选）：https://dashscope.aliyun.com
```

---

## 十二、MCP Server 快速参考

### FinanceMCP

| 项目 | 信息 |
|------|------|
| GitHub | https://github.com/LoliWolf/FinanceMCP |
| npm | `npm install finance-mcp` |
| 在线体验 | https://finvestai.top/ |
| 公共云 SSE | `http://106.14.205.176:3101/sse` |
| 公共云 HTTP | `https://finvestai.top/mcp` |
| 协议 | stdio / SSE / streamableHttp |
| 收费 | 免费 |
| 工具数 | 14 个 |

### China-Stock-MCP

| 项目 | 信息 |
|------|------|
| GitHub | https://github.com/xinkuang/china-stock-mcp |
| 魔搭 | https://www.modelscope.cn/mcp/servers/postback/china-stock-mcp |
| 安装 | `pip install china-stock-mcp` |
| 协议 | stdio / HTTP |
| 收费 | 免费，无需 API Key |

### Tushare-MCP

| 项目 | 信息 |
|------|------|
| GitHub | https://github.com/buuzzy/tushare_MCP |
| npm | `npm install tushare-mcp-server` |
| 协议 | stdio |
| 收费 | MCP 免费，需 Tushare Token（免费注册） |
| Token 获取 | https://tushare.pro |

### Finance-MCP (FlowLLM)

| 项目 | 信息 |
|------|------|
| GitHub | https://github.com/FlowLLM-AI/finance-mcp |
| 安装 | `pip install finance-mcp` |
| 协议 | stdio / SSE / HTTP |
| 收费 | 免费，需 API Key（Tushare/DashScope/Tavily） |
| 特色 | 20+ 投研流程、同花顺爬虫工具、零代码 YAML 配置 |

### 同花顺 iFinD MCP

| 项目 | 信息 |
|------|------|
| 官方平台 | iFinD MCP 官方平台已上线 |
| 收费 | 3.8万~4.2万/年/席 |
| 功能 | 全市场数据、申万行业、龙虎榜、资金、研报 |
| 适合 | 机构投资者 |

### 东方财富妙想 Skills

| 项目 | 信息 |
|------|------|
| 平台 | 东方财富 APP → 搜索「skills」 |
| 收费 | 全功能免费，API Key 永久免费 |
| 适配 | OpenClaw 平台 |
| 功能 | 行情+财务+龙虎榜+资金+板块+研报+舆情 |
