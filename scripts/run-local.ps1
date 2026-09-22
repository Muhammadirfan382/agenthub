<#
.SYNOPSIS
  Runs AgentHub on this computer for testing: the backend API and the web app.

.DESCRIPTION
  From the repository root:

      powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1

  (-ExecutionPolicy Bypass applies to this one command only; it changes no
  system setting.)

  It prepares what is missing - Python environment, npm packages, a local
  .env, the SQLite database schema - offers to create your own sign-in
  account, then opens the backend and the web app in two new windows and
  your browser at http://127.0.0.1:5173. Close those two windows to stop.

  Local mode: SQLite, no Docker. Runs are recorded as simulations unless a
  container runtime and a model key (AGENTHUB_ANTHROPIC_API_KEY in .env) exist.
  Nothing here is reachable from other machines: both servers listen on
  127.0.0.1 only.
#>
[CmdletBinding()]
param(
    # Skip the "create your own account" question.
    [switch]$NoAccount
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }

# --- Prerequisites ------------------------------------------------------------
foreach ($tool in 'python', 'node', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is not installed or not on PATH. See README.md, 'Local development requirements'."
    }
}

# --- Backend environment --------------------------------------------------------
if (-not (Test-Path $Python)) {
    Step 'Creating the Python environment (first run only)'
    & python -m venv (Join-Path $Backend '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'python -m venv failed' }
    & $Python -m pip install --disable-pip-version-check -r (Join-Path $Backend 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
}

# --- Frontend packages ----------------------------------------------------------
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Step 'Installing web app packages (first run only)'
    Push-Location $Frontend
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    } finally { Pop-Location }
}

# --- Local configuration (never committed) ---------------------------------------
$EnvFile = Join-Path $Root '.env'
if (-not (Test-Path $EnvFile)) {
    Step 'Creating .env for local development'
    Copy-Item (Join-Path $Root '.env.example') $EnvFile
}
$FrontendEnv = Join-Path $Frontend '.env.local'
if (-not (Test-Path $FrontendEnv)) {
    Step 'Pointing the web app at the local backend'
    # Start on the real (local) API instead of demonstration data. Switch back
    # any time in Settings -> API.
    Set-Content -Path $FrontendEnv -Value 'VITE_DATA_SOURCE=api' -Encoding ascii
}

# --- Database ------------------------------------------------------------------
Step 'Bringing the local database up to date'
Push-Location $Backend
try {
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'database migration failed' }

    # --- Your account ---------------------------------------------------------
    if (-not $NoAccount) {
        Write-Host ''
        $answer = Read-Host 'Create your own sign-in account now? (y/N)'
        if ($answer -match '^(y|yes)$') {
            $email = Read-Host 'Email'
            $name = Read-Host 'Your name'
            $organization = Read-Host 'Organization name'
            # The password is typed at the script's own prompt, never passed
            # as an argument.
            & $Python -m scripts.create_user --email $email --name $name `
                --organization $organization --role owner
            if ($LASTEXITCODE -ne 0) { Write-Warning 'The account was not created; you can re-run this script.' }
        }
    }
} finally { Pop-Location }

# --- Start whichever server is not already running, each in its own window --------
# Re-running the script after closing one window restarts only that one; a
# second copy on a busy port would just fail.
function Test-Listening([int]$Port) {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Listening 8000) {
    Step 'The backend is already running at http://127.0.0.1:8000'
} else {
    Step 'Starting the backend at http://127.0.0.1:8000'
    $backendCommand = "Set-Location -LiteralPath '$Backend'; `$host.UI.RawUI.WindowTitle = 'AgentHub backend'; " +
        "& '$Python' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand | Out-Null
}

if (Test-Listening 5173) {
    Step 'The web app is already running at http://127.0.0.1:5173'
} else {
    Step 'Starting the web app at http://127.0.0.1:5173'
    $frontendCommand = "Set-Location -LiteralPath '$Frontend'; `$host.UI.RawUI.WindowTitle = 'AgentHub web app'; npm run dev"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand | Out-Null
}

# --- Wait until it answers, then open the browser ---------------------------------
Step 'Waiting for the backend to answer'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/api/v1/health/ready'
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) {
    Write-Warning 'The backend did not answer within a minute. Look at the "AgentHub backend" window for the error.'
} else {
    Start-Sleep -Seconds 2
    Start-Process 'http://127.0.0.1:5173'
    Write-Host ''
    Write-Host 'AgentHub is running:' -ForegroundColor Green
    Write-Host '  Web app      http://127.0.0.1:5173'
    Write-Host '  API docs     http://127.0.0.1:8000/api/docs'
    Write-Host '  Close the two AgentHub windows to stop it.'
}
