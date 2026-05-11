param(
    [string]$RepoUrl = "https://github.com/guangxiangdebizi/FinanceMCP",
    [string]$ExternalDir = "external",
    [int]$Port = 3000,
    [switch]$Update
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path (Get-Location) $Path)
}

function Test-PortOpen {
    param([int]$Port)
    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

$root = (Get-Location).Path
$externalRoot = Resolve-RepoPath $ExternalDir
$financeDir = Join-Path $externalRoot "FinanceMCP"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required but was not found in PATH."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 18+ is required but was not found in PATH."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required but was not found in PATH."
}

if (-not (Test-Path -LiteralPath $externalRoot)) {
    New-Item -ItemType Directory -Path $externalRoot | Out-Null
}

if (-not (Test-Path -LiteralPath $financeDir)) {
    git clone $RepoUrl $financeDir
} elseif ($Update) {
    git -C $financeDir pull --ff-only
}

Push-Location $financeDir
try {
    if (-not (Test-Path -LiteralPath "node_modules")) {
        npm install
    }

    if (Test-Path -LiteralPath "package.json") {
        npm run build --if-present
    }

    if (Test-PortOpen $Port) {
        Write-Host "FinanceMCP source and npm dependencies are ready."
        Write-Host "Port $Port is already listening; leaving the existing process untouched."
        try {
            $health = Invoke-WebRequest -Uri "http://localhost:$Port/health" -UseBasicParsing -TimeoutSec 5
            if ($health.Content -notmatch "healthy|streamable-http") {
                Write-Warning "Port $Port responded to /health but does not look like FinanceMCP. Use -Port with a free port, then set MCP_FINANCE_URL accordingly."
            }
        } catch {
            Write-Warning "Port $Port is listening but /health could not be verified: $($_.Exception.Message)"
        }
        Write-Host "Endpoint: http://localhost:$Port/mcp"
        exit 0
    }

    $npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
    if ($npmCmd) {
        $filePath = $npmCmd.Source
    } else {
        $filePath = (Get-Command npm).Source
    }

    $escapedNpm = $filePath.Replace("'", "''")
    $startCommand = "`$env:PORT='$Port'; & '$escapedNpm' run start:http"
    $process = Start-Process `
        -FilePath "powershell" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $startCommand) `
        -WorkingDirectory $financeDir `
        -WindowStyle Hidden `
        -PassThru

    Start-Sleep -Seconds 5
    if (-not (Test-PortOpen $Port)) {
        Write-Warning "FinanceMCP process started (PID $($process.Id)) but port $Port is not listening yet."
        Write-Warning "Check the FinanceMCP logs/terminal output or run: npm run start:http"
    } else {
        Write-Host "FinanceMCP started. PID: $($process.Id)"
        Write-Host "MCP endpoint: http://localhost:$Port/mcp"
        Write-Host "Health check: http://localhost:$Port/health"
    }
} finally {
    Pop-Location
}
