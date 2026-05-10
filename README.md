# TradingAgents-CN 简历精简版

TradingAgents-CN 简历精简版是一个聚焦 **A股单股智能分析与报告生成** 的全栈项目。项目保留多智能体协作、A股多数据源、智能新闻分析、多 LLM 配置、报告导出、Docker 部署、Redis/MongoDB 运维后台等核心工程能力，移除了学习中心、任务中心、股票筛选、自选股、模拟交易、批量分析和跨市场入口等外围产品功能。

> 本项目仅用于学习、研究和工程展示，不构成任何投资建议。

## 核心功能

- **A股单股分析**：输入 6 位 A股代码，选择分析日期、研究深度、分析师模块和模型配置，生成完整分析任务。
- **多智能体协作**：分析师、研究员、交易员、风险管理和管理层协同产出技术面、基本面、新闻、情绪、风险和最终建议。
- **智能新闻分析**：保留新闻过滤、新闻质量评估、相关性分析和新闻分析师工具链，新闻内容进入单股报告。
- **分析报告管理**：报告列表、搜索、日期筛选、详情展示、删除和 Markdown/JSON/Word/PDF 导出能力。
- **系统配置后台**：保留 LLM、多模型、A股数据源、缓存和运行参数配置。
- **系统管理后台**：保留 MongoDB、Redis、日志、数据同步、定时任务和使用统计等运维页面。
- **容器化部署**：保留 Docker 与 docker-compose 相关部署文件，便于演示完整工程链路。

## 技术架构

- **前端**：Vue 3、TypeScript、Vite、Element Plus。
- **后端**：FastAPI、Pydantic、APScheduler。
- **数据存储**：MongoDB 保存任务、报告、配置、日志和统计数据。
- **缓存与进度**：Redis 保存缓存、任务进度和实时状态。
- **AI 编排**：TradingAgents 多智能体图执行框架。
- **数据源**：Tushare、AKShare、BaoStock 等 A股数据源。
- **模型接入**：支持多 LLM 提供商和模型选择持久化。

## 精简后的页面

- `仪表盘`：最近报告、系统状态、核心能力和运维入口。
- `单股分析`：A股代码校验、分析参数、实时进度和报告跳转。
- `分析报告`：报告列表、详情、模块化内容和导出。
- `系统配置`：配置管理、缓存管理。
- `系统管理`：数据库管理、操作日志、系统日志、数据同步、定时任务、使用统计。
- `关于项目`：项目说明和风险提示。

## 已移除的外围功能

- 学习中心
- 任务中心
- 批量分析
- 股票筛选
- 我的自选股
- 模拟交易
- 前端港股/美股/跨市场入口
- 后端对应的自选股、模拟交易、筛选、批量分析、跨市场公开接口

## 运行方式

### 本地后端

```bash
python -m app.main
```

### 本地前端

```bash
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
docker compose up -d
```

具体配置项请参考 `.env.example` 和 `docker-compose.yml`。

## 演示流程

1. 登录系统并进入配置管理。
2. 配置 LLM Provider、模型和 A股数据源。
3. 进入单股分析，输入 `000001` 或 `600519`。
4. 等待 Redis 进度流和后台任务完成。
5. 在分析报告中查看技术面、基本面、新闻、情绪、风险和最终建议。
6. 导出 Markdown/JSON/Word/PDF 报告。
7. 打开系统管理查看 MongoDB、Redis、日志、同步和定时任务状态。

## 智能体文档

- [分析师团队](./docs/agents/analysts.md) - 各类分析师智能体详解
- [研究员团队](./docs/agents/researchers.md) - 研究员智能体设计
- [交易员](./docs/agents/trader.md) - 交易决策智能体
- [风险管理](./docs/agents/risk-management.md) - 风险管理智能体
- [管理层](./docs/agents/managers.md) - 管理层智能体

## 数据处理

- [数据源集成](./docs/data/data-sources.md) - 支持的数据源和 API
- [Tushare 数据接口集成](./docs/data/china_stock-api-integration.md) - A股数据源详解
- [数据处理流程](./docs/data/data-processing.md) - 数据获取和处理
- [缓存机制](./docs/data/caching.md) - 数据缓存策略

## 核心功能文档

- [智能新闻分析模块](./docs/features/NEWS_FILTERING_SOLUTION_DESIGN.md) - AI 驱动的新闻过滤与质量评估
- [新闻质量分析](./docs/features/NEWS_QUALITY_ANALYSIS_REPORT.md) - 新闻质量评估与相关性分析
- [新闻分析师工具修复](./docs/features/NEWS_ANALYST_TOOL_CALL_FIX_REPORT.md) - 工具调用修复报告
- [多 LLM 提供商集成](./docs/features/multi-llm-integration.md) - 多提供商、多模型支持
- [模型选择持久化](./docs/features/model-persistence.md) - 模型配置保持
- [报告导出功能](./docs/features/report-export.md) - Word/PDF/Markdown 多格式导出
- [Docker 容器化部署](./docs/features/docker-deployment.md) - 一键部署完整环境
- [新闻分析系统](./docs/features/news-analysis-system.md) - 多源实时新闻聚合与分析

## 简历亮点

- 将复杂交易分析项目收敛为聚焦清晰的 A股单股分析产品。
- 使用 FastAPI + Vue 3 构建完整前后端系统。
- 使用 MongoDB + Redis 支撑任务、报告、缓存和实时进度。
- 使用多智能体架构生成结构化投资研究报告。
- 保留系统配置与运维后台，体现工程化和可维护性。
- 支持 Docker 部署，便于演示和复现。
