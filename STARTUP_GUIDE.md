# TradingAgents-CN 启动说明

本文档说明如何在本机启动完整项目，包括本次已经集成到 A 股 unified 工具链里的 FinanceMCP 和 China-Stock-MCP。

## 1. 前置要求

请先确认本机已安装：

- Python 3.10+
- Node.js 18+，以及 npm 或 yarn
- Docker Desktop
- Git

当前机器的 MCP 服务端口约定：

- FinanceMCP：`http://localhost:3030/mcp`
- China-Stock-MCP：`http://localhost:8081/mcp`

说明：本机 `3000` 端口已经被其他 Docker/WSL 服务占用，所以 FinanceMCP 使用 `3030`。

## 2. 初始化项目环境

进入项目根目录：

```powershell
cd E:\Code\java\mtagent\TradingAgents-CN
```

如果还没有 `.env`，从示例文件复制一份：

```powershell
Copy-Item .env.example .env
```

安装 Python 依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

项目已经在 `pyproject.toml` 和 `requirements.txt` 中声明了 MCP 客户端依赖：

```text
mcp>=1.24.0
```

## 3. 启动 MCP 服务

启动 FinanceMCP：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp\start_finance_mcp.ps1 -Port 3030
```

启动 China-Stock-MCP。优先使用 Docker 方式：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp\start_china_stock_mcp.ps1
```

如果 Docker 因镜像源、代理或 registry 权限问题无法拉取/构建镜像，使用本地 Python fallback：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp\start_china_stock_mcp_local.ps1
```

设置项目 MCP 环境变量：

```powershell
$env:MCP_ENABLED = "true"
$env:MCP_FINANCE_TRANSPORT = "streamable_http"
$env:MCP_FINANCE_URL = "http://localhost:3030/mcp"
$env:MCP_CHINA_STOCK_TRANSPORT = "streamable_http"
$env:MCP_CHINA_STOCK_URL = "http://localhost:8081/mcp"
```

验证两个 MCP 服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\mcp\check_mcp_servers.ps1 `
  -FinanceUrl http://localhost:3030/mcp `
  -FinanceHealthUrl http://localhost:3030/health
```

成功时应看到：

- FinanceMCP health 返回 HTTP 200。
- FinanceMCP tools 包含 `finance_news`、`hot_news_7x24`、`company_performance`、`money_flow`。
- China-Stock-MCP tools 包含 `get_hist_data`、`get_realtime_data`、`get_stock_basic_info`。

如果 FinanceMCP 输出 `Session termination failed: 404`，但 `tools/list` 是成功的，可以忽略。这个服务没有完整实现 MCP 客户端发出的 DELETE 结束会话请求，不影响工具调用。

## 4. 启动数据库服务

本地开发建议用 Docker 启动 MongoDB 和 Redis：

```powershell
docker compose up -d mongodb redis
```

检查容器状态：

```powershell
docker compose ps
```

## 5. 启动后端

在已激活虚拟环境、并已设置 MCP 环境变量的 PowerShell 窗口中执行：

```powershell
$env:PYTHONUTF8 = "1"
python -m app
```

后端地址：

- API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`

## 6. 启动前端

打开新的 PowerShell 窗口：

```powershell
cd E:\Code\java\mtagent\TradingAgents-CN\frontend
yarn install
yarn dev
```

如果没有安装 yarn，也可以使用 npm：

```powershell
npm install
npm run dev
```

前端地址：

- `http://localhost:5173`

注意：项目以 `yarn.lock` 作为前端锁文件，不建议提交 npm 自动生成的 `package-lock.json`。

## 7. Docker 全栈启动

如果希望用 Docker 启动完整应用栈，包括后端、前端、MongoDB 和 Redis：

```powershell
docker compose up -d --build
```

Docker 启动后的地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

如果后端运行在 Docker 容器里，而 MCP 服务运行在 Windows 宿主机上，后端容器里不能直接用 `localhost` 访问宿主机 MCP。请改用：

```powershell
MCP_FINANCE_URL=http://host.docker.internal:3030/mcp
MCP_CHINA_STOCK_URL=http://host.docker.internal:8081/mcp
```

可以把这些值写入 `.env.docker`，或写入 `docker-compose.yml` 的 backend 环境变量中。

注意：如果 China-Stock-MCP 正在使用 `8081`，不要启用 Docker 的 `management` profile，因为 Redis Commander 也会映射 `8081`。

## 8. 项目验证

运行 MCP 迁移测试：

```powershell
$env:PYTHONUTF8 = "1"
python -m pytest tests\test_mcp_migration.py -q
```

验证项目 MCP 网关：

```powershell
$env:PYTHONUTF8 = "1"
$env:MCP_ENABLED = "true"
$env:MCP_FINANCE_TRANSPORT = "streamable_http"
$env:MCP_FINANCE_URL = "http://localhost:3030/mcp"
$env:MCP_CHINA_STOCK_TRANSPORT = "streamable_http"
$env:MCP_CHINA_STOCK_URL = "http://localhost:8081/mcp"

python -c "from tradingagents.dataflows.mcp.gateway import MCPDataGateway; g=MCPDataGateway(); print(g.is_available()); print(g.list_tools('finance_mcp').ok); print(g.list_tools('china_stock_mcp').ok); r=g.call('news', symbol='000001', params={'limit':1}); print(r.ok, r.server, r.tool)"
```

期望输出包含：

```text
True
True
True
True finance_mcp finance_news
```

也可以用以下股票做业务验收：

- `000001`
- `600519`
- `300750`

建议分别验证市场、基本面、新闻、情绪四类 unified 工具是否能正常返回，并确认 MCP 不可用时不会中断旧的 Tushare / AKShare / BaoStock 回退链路。

## 9. 停止服务

停止 Docker 数据库服务：

```powershell
docker compose stop mongodb redis
```

如果 China-Stock-MCP 使用 Docker 模式启动：

```powershell
docker stop tradingagents-china-stock-mcp
```

FinanceMCP 和 China-Stock-MCP 本地 Python fallback 是隐藏本地进程。可以先查询监听端口对应的 PID：

```powershell
Get-NetTCPConnection -LocalPort 3030,8081 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

再停止明确的单个进程：

```powershell
Stop-Process -Id <PID>
```

## 10. 注意事项

- 本次部署暂未配置 `TUSHARE_TOKEN`。FinanceMCP 中依赖 Tushare 权限的工具可能返回空或失败，项目应继续回退到原有 Tushare、AKShare、BaoStock 链路。
- 不把外部 MCP 原始工具直接暴露给 LLM。LLM 仍只看到四个 unified 工具：
  - `get_stock_market_data_unified`
  - `get_stock_fundamentals_unified`
  - `get_stock_news_unified`
  - `get_stock_sentiment_unified`
- 外部 MCP 源码目录位于 `external/`，该目录已加入 `.gitignore`，不会纳入版本控制。
