#requires -Version 5.1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Baiyun Culture Smart Q&A - Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 0: Clean environment
Write-Host "[0/5] Cleaning environment..." -ForegroundColor Yellow
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backendDir "showcase.db") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backendDir "baiyun_culture.db") -ErrorAction SilentlyContinue
Write-Host "  Done" -ForegroundColor Green

# Step 1: Check .env
Write-Host "[1/5] Checking environment config..." -ForegroundColor Yellow
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "  ERROR: .env file not found!" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  .env exists" -ForegroundColor Green

# Step 2: Install Python dependencies
Write-Host "[2/5] Installing Python dependencies..." -ForegroundColor Yellow
Push-Location $backendDir
try {
    # 临时放宽错误策略，避免 pip 的 stderr 警告被误判为终止错误
    $prevPolicy = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $pipOutput = & pip install -r requirements.txt --no-cache-dir 2>&1
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $prevPolicy
    if ($pipExit -ne 0) {
        Write-Host "  Failed: pip exit code $pipExit" -ForegroundColor Red
        $pipOutput | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        Pop-Location
        pause
        exit 1
    }
    Write-Host "  Done" -ForegroundColor Green
} catch {
    Write-Host "  Failed: $_" -ForegroundColor Red
    Pop-Location
    pause
    exit 1
}

# Step 3: Initialize database
Write-Host "[3/5] Initializing database..." -ForegroundColor Yellow
try {
    python init_db.py
    Write-Host "  Done" -ForegroundColor Green
} catch {
    Write-Host "  Failed: $_" -ForegroundColor Red
    Pop-Location
    pause
    exit 1
}
Pop-Location

# Step 4: Build frontend
Write-Host "[4/5] Building frontend..." -ForegroundColor Yellow
Push-Location $frontendDir
try {
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Host "  Installing npm packages..." -ForegroundColor Yellow
        npm install 2>&1 | Out-Null
    }
    npx vite build
    Write-Host "  Done" -ForegroundColor Green
} catch {
    Write-Host "  Failed: $_" -ForegroundColor Red
    Pop-Location
    pause
    exit 1
}
Pop-Location

# Step 5: Start server
Write-Host "[5/5] Starting server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  URL: http://localhost:5000" -ForegroundColor Cyan
Write-Host "  Health: http://localhost:5000/api/health" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Cyan
Write-Host ""

Push-Location $backendDir
python app.py
Pop-Location
