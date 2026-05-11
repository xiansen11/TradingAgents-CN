param(
    [string]$FinanceUrl = "http://localhost:3000/mcp",
    [string]$FinanceHealthUrl = "http://localhost:3000/health",
    [string]$ChinaStockUrl = "http://localhost:8081/mcp",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Continue"

function Test-Http {
    param([string]$Url, [string]$Name)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 10
        Write-Host "$Name OK: HTTP $($response.StatusCode)"
        return $true
    } catch {
        Write-Warning "$Name failed: $($_.Exception.Message)"
        return $false
    }
}

function Test-McpTools {
    param([string]$Url, [string]$Name)

    $script = @"
import asyncio
import json
import sys

async def main():
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"mcp package unavailable: {exc}"}, ensure_ascii=False))
        return 2

    try:
        async with streamablehttp_client("$Url") as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [tool.name for tool in getattr(tools, "tools", [])]
                print(json.dumps({"ok": True, "tools": names}, ensure_ascii=False))
                return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

raise SystemExit(asyncio.run(main()))
"@

    $output = $script | & $PythonExe -
    Write-Host "$Name tools/list: $output"
    return ($LASTEXITCODE -eq 0)
}

function Test-RawJsonRpcTools {
    param([string]$Url, [string]$Name)

    $payload = @{
        jsonrpc = "2.0"
        id = 1
        method = "tools/list"
        params = @{}
    } | ConvertTo-Json -Depth 5

    try {
        $response = Invoke-RestMethod -Uri $Url -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 10
        $tools = @($response.result.tools | ForEach-Object { $_.name })
        Write-Host "$Name raw tools/list: $($tools -join ', ')"
        return ($tools.Count -gt 0)
    } catch {
        Write-Warning "$Name raw tools/list failed: $($_.Exception.Message)"
        return $false
    }
}

if (-not $PythonExe) {
    $chinaVenvPython = Join-Path (Get-Location) "external\china-stock-mcp\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $chinaVenvPython) {
        $PythonExe = $chinaVenvPython
    } else {
        $PythonExe = "python"
    }
}

Write-Host "MCP check Python: $PythonExe"
Test-Http -Url $FinanceHealthUrl -Name "FinanceMCP health" | Out-Null
$financeMcpOk = Test-McpTools -Url $FinanceUrl -Name "FinanceMCP"
if (-not $financeMcpOk) {
    Test-RawJsonRpcTools -Url $FinanceUrl -Name "FinanceMCP" | Out-Null
}
Test-McpTools -Url $ChinaStockUrl -Name "China-Stock-MCP" | Out-Null

Write-Host ""
Write-Host "Expected project environment:"
Write-Host "  MCP_ENABLED=true"
Write-Host "  MCP_FINANCE_TRANSPORT=streamable_http"
Write-Host "  MCP_FINANCE_URL=$FinanceUrl"
Write-Host "  MCP_CHINA_STOCK_TRANSPORT=streamable_http"
Write-Host "  MCP_CHINA_STOCK_URL=$ChinaStockUrl"
