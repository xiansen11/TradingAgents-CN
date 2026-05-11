param(
    [string]$RepoUrl = "https://github.com/xinkuang/china-stock-mcp",
    [string]$ExternalDir = "external",
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

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required but was not found in PATH."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ is required but was not found in PATH."
}

if (Test-PortOpen $Port) {
    Write-Host "China-Stock-MCP appears to already be listening on port $Port."
    Write-Host "Endpoint: http://localhost:$Port/mcp"
    exit 0
}

if ([System.IO.Path]::IsPathRooted($ExternalDir)) {
    $externalRoot = $ExternalDir
} else {
    $externalRoot = Join-Path (Get-Location) $ExternalDir
}
$sourceDir = Join-Path $externalRoot "china-stock-mcp"
$venvDir = Join-Path $sourceDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $externalRoot)) {
    New-Item -ItemType Directory -Path $externalRoot | Out-Null
}
if (-not (Test-Path -LiteralPath $sourceDir)) {
    git clone $RepoUrl $sourceDir
} elseif ($Update) {
    git -C $sourceDir pull --ff-only
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv $venvDir
}

& $pythonExe -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Python packaging dependencies for China-Stock-MCP."
}
& $pythonExe -m pip install -r (Join-Path $sourceDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install China-Stock-MCP requirements."
}

$pythonPath = Join-Path $sourceDir "src"
$escapedPythonPath = $pythonPath.Replace("'", "''")
$escapedPythonExe = $pythonExe.Replace("'", "''")
$startCommand = "`$env:PYTHONPATH='$escapedPythonPath'; & '$escapedPythonExe' -m china_stock_mcp --streamable-http --host 0.0.0.0 --port $Port"
$process = Start-Process `
    -FilePath "powershell" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $startCommand) `
    -WorkingDirectory $sourceDir `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 8
if (-not (Test-PortOpen $Port)) {
    Write-Warning "China-Stock-MCP local process started (PID $($process.Id)) but port $Port is not listening yet."
} else {
    Write-Host "China-Stock-MCP local server started. PID: $($process.Id)"
    Write-Host "MCP endpoint: http://localhost:$Port/mcp"
}
