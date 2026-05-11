param(
    [string]$RepoUrl = "https://github.com/xinkuang/china-stock-mcp",
    [string]$ExternalDir = "external",
    [string]$Image = "tradingagents/china-stock-mcp:local",
    [string]$ContainerName = "tradingagents-china-stock-mcp",
    [int]$Port = 8081,
    [switch]$Update
)

$ErrorActionPreference = "Stop"

function Test-PortOpen {
    param([int]$Port)
    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required but was not found in PATH."
}

if ([System.IO.Path]::IsPathRooted($ExternalDir)) {
    $externalRoot = $ExternalDir
} else {
    $externalRoot = Join-Path (Get-Location) $ExternalDir
}
$sourceDir = Join-Path $externalRoot "china-stock-mcp"

$existing = docker ps -a --filter "name=^/$ContainerName$" --format "{{.Names}}"
$running = docker ps --filter "name=^/$ContainerName$" --format "{{.Names}}"

if ($running -eq $ContainerName) {
    Write-Host "China-Stock-MCP container is already running."
    Write-Host "MCP endpoint: http://localhost:$Port/mcp"
    exit 0
}

if (Test-PortOpen $Port -and -not $existing) {
    throw "Port $Port is already in use by another process. Stop that process or choose another port."
}

if ($existing -eq $ContainerName) {
    docker start $ContainerName | Out-Null
} else {
    if (-not (Test-Path -LiteralPath $externalRoot)) {
        New-Item -ItemType Directory -Path $externalRoot | Out-Null
    }
    if (-not (Test-Path -LiteralPath $sourceDir)) {
        git clone $RepoUrl $sourceDir
    } elseif ($Update) {
        git -C $sourceDir pull --ff-only
    }

    docker build -t $Image $sourceDir
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed for $Image. Check Docker registry/proxy access, then rerun this script."
    }
    docker run -d --name $ContainerName -p "${Port}:8081" $Image | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker run failed for $Image."
    }
}

Start-Sleep -Seconds 5
if (-not (Test-PortOpen $Port)) {
    Write-Warning "China-Stock-MCP container started but port $Port is not listening yet."
    Write-Warning "Check logs with: docker logs $ContainerName"
} else {
    Write-Host "China-Stock-MCP is running."
    Write-Host "MCP endpoint: http://localhost:$Port/mcp"
    Write-Host "Logs: docker logs $ContainerName"
}
