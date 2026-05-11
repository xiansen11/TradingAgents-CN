# Local MCP Deployment

This project keeps the LLM-facing surface stable: analysts still use only the
four unified tools. FinanceMCP and China-Stock-MCP run as external local MCP
servers and are called through `MCPDataGateway`.

## Layout

- FinanceMCP source: `external/FinanceMCP`
- China-Stock-MCP source: `external/china-stock-mcp`
- China-Stock-MCP runtime: local Docker image `tradingagents/china-stock-mcp:local` and container `tradingagents-china-stock-mcp`
- Scripts: `scripts/mcp/`

`external/` is ignored by git because it contains upstream source snapshots.

## Start Servers

```powershell
powershell -ExecutionPolicy Bypass -File scripts/mcp/start_finance_mcp.ps1
powershell -ExecutionPolicy Bypass -File scripts/mcp/start_china_stock_mcp.ps1
```

If port 3000 is already used by another local service, start FinanceMCP on a
free port and update the project URL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/mcp/start_finance_mcp.ps1 -Port 3030
$env:MCP_FINANCE_URL = "http://localhost:3030/mcp"
```

FinanceMCP starts at:

- MCP endpoint: `http://localhost:3000/mcp`
- Health check: `http://localhost:3000/health`

China-Stock-MCP starts at:

- MCP endpoint: `http://localhost:8081/mcp`

If Docker cannot pull the base image because of registry/proxy permissions,
use the local Python fallback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/mcp/start_china_stock_mcp_local.ps1
```

## Project Environment

Set these variables before running TradingAgents-CN:

```powershell
$env:MCP_ENABLED = "true"
$env:MCP_FINANCE_TRANSPORT = "streamable_http"
$env:MCP_FINANCE_URL = "http://localhost:3000/mcp"
$env:MCP_CHINA_STOCK_TRANSPORT = "streamable_http"
$env:MCP_CHINA_STOCK_URL = "http://localhost:8081/mcp"
```

FinanceMCP can use `TUSHARE_TOKEN`, `X-Tushare-Token`, `Authorization`, or
`X-Api-Key`. This local setup intentionally does not configure a token. Tools
that need Tushare permission may fail, and the project must fall back to the
legacy Tushare/AKShare/BaoStock chain.

## Check Servers

```powershell
powershell -ExecutionPolicy Bypass -File scripts/mcp/check_mcp_servers.ps1
```

This checks FinanceMCP health and attempts MCP `tools/list` through the Python
`mcp` package. The script automatically uses
`external/china-stock-mcp/.venv/Scripts/python.exe` when it exists, because the
local China-Stock-MCP fallback already installs the MCP client dependencies.
You can override this with `-PythonExe`.

FinanceMCP also supports a raw JSON-RPC HTTP fallback in this check script,
which helps diagnose older hand-written streamable HTTP implementations.

## Stop Servers

FinanceMCP is started as a hidden local process. Stop the process listening on
port 3000 from Task Manager or PowerShell.

China-Stock-MCP can be stopped without deleting anything:

```powershell
docker stop tradingagents-china-stock-mcp
```

Do not remove external directories or Docker resources in bulk. If cleanup is
needed, delete only explicit single files or ask the user to remove directories.
