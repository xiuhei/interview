param(
    [ValidateSet('local-core', 'docker-full')]
    [string]$Mode = 'local-core'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Fail-Step {
    param(
        [string]$Message,
        [string]$NextStep = ''
    )
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    if ($NextStep) {
        Write-Host "       Next: $NextStep" -ForegroundColor Yellow
    }
    exit 1
}

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Action,
        [string]$NextStep = ''
    )
    Write-Host "[STEP] $Title" -ForegroundColor Cyan
    try {
        & $Action
        Write-Host "[OK]   $Title" -ForegroundColor Green
    }
    catch {
        Fail-Step -Message ("{0}: {1}" -f $Title, $_.Exception.Message) -NextStep $NextStep
    }
}

function Resolve-ProjectPython {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $py312Exe = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $py312Exe -and $py312Exe -notmatch 'msys64') {
            return $py312Exe
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonExe = (& python -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        $pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null | Out-String).Trim()
        if (-not $pythonExe) {
            Fail-Step 'python exists but its executable path could not be resolved.' 'Make sure official CPython 3.12 is installed correctly.'
        }
        if ($pythonExe -match 'msys64') {
            Fail-Step "python currently points to MSYS2: $pythonExe" 'Install official CPython 3.12 and make it win over msys64 in PATH.'
        }
        if ($pythonVersion -eq '3.12') {
            return $pythonExe
        }
    }

    Fail-Step 'No usable official Python 3.12 interpreter was found.' 'Install official CPython 3.12 and confirm py -3.12 works.'
}

function Assert-DockerDaemon {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail-Step 'docker command was not found.' 'Install Docker Desktop or use local-core mode.'
    }

    & cmd /c "docker info >nul 2>nul"
    if ($LASTEXITCODE -ne 0) {
        Fail-Step 'Docker daemon is not running.' 'Start Docker Desktop before using docker-full mode.'
    }
}

function Ensure-DotEnv {
    $envFile = Join-Path $Root '.env'
    $envExample = Join-Path $Root '.env.example'
    if (-not (Test-Path $envFile)) {
        Copy-Item $envExample $envFile -Force
        Write-Host '[INFO] Created .env from .env.example'
    }
}

function Get-VenvPython {
    return Join-Path $Root '.venv\Scripts\python.exe'
}

function Test-FrontendCliHealthy {
    $viteCmd = Join-Path $Root 'frontend\node_modules\.bin\vite.cmd'
    $vitePackage = Join-Path $Root 'frontend\node_modules\vite\package.json'
    return (Test-Path $viteCmd) -and (Test-Path $vitePackage)
}

Write-Host '== AI Interview Platform Bootstrap ==' -ForegroundColor Magenta
Write-Host "Mode: $Mode"
Write-Host ''

Run-Step -Title 'Run preflight checks' -Action {
    & (Join-Path $PSScriptRoot 'preflight_env.ps1')
}

if ($Mode -eq 'docker-full') {
    Assert-DockerDaemon

    Run-Step -Title 'Validate docker compose config' -Action {
        Set-Location $Root
        docker compose config | Out-Null
    } -NextStep 'Make sure Docker Desktop is running and accessible.'

    Ensure-DotEnv

    Run-Step -Title 'Start full Docker environment' -Action {
        Set-Location $Root
        docker compose up --build
    } -NextStep 'If the build fails, run docker compose build separately to inspect the failing image step.'

    exit 0
}

$pythonExe = Resolve-ProjectPython
Ensure-DotEnv

Run-Step -Title 'Bootstrap pip' -Action {
    Set-Location $Root
    & $pythonExe -m ensurepip --upgrade | Out-Host
} -NextStep 'Confirm the interpreter is official CPython 3.12.'

Run-Step -Title 'Create project virtual environment' -Action {
    Set-Location $Root
    if (Test-Path '.venv') {
        Remove-Item '.venv' -Recurse -Force
    }
    & $pythonExe -m venv .venv
} -NextStep 'Confirm CPython 3.12 includes the venv module.'

$venvPython = Get-VenvPython
if (-not (Test-Path $venvPython)) {
    Fail-Step 'The virtual environment was created but .venv\Scripts\python.exe was not found.' 'Delete .venv and rerun the script.'
}

Run-Step -Title 'Upgrade pip, setuptools, and wheel' -Action {
    Set-Location $Root
    & $venvPython -m pip install --upgrade pip setuptools wheel
} -NextStep 'Check network access and Python package index settings.'

Run-Step -Title 'Install backend dependencies' -Action {
    Set-Location $Root
    & $venvPython -m pip install -r backend/requirements.txt
} -NextStep 'If a specific Python package fails, keep the error output and adjust requirements accordingly.'

Run-Step -Title 'Install frontend dependencies' -Action {
    Set-Location (Join-Path $Root 'frontend')
    if (Test-Path 'node_modules') {
        Remove-Item 'node_modules' -Recurse -Force
    }
    if (Test-Path '.npm-cache') {
        Remove-Item '.npm-cache' -Recurse -Force
    }
    npm ci
    if ($LASTEXITCODE -ne 0) {
        throw 'npm ci failed.'
    }
    npm ls vite | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'vite dependency check failed after npm ci.'
    }
    if (-not (Test-FrontendCliHealthy)) {
        throw 'vite executable is still missing after npm ci. node_modules may be corrupted.'
    }
} -NextStep 'Make sure Node 20+ is installed and this repo has write access.'

Run-Step -Title 'Show next local-core steps' -Action {
    Set-Location $Root
    Write-Host ''
    Write-Host 'Next local-core steps:' -ForegroundColor Yellow
    Write-Host '1. docker compose -f docker-compose.yml -f docker-compose.local.yml up -d mysql redis etcd minio milvus-standalone'
    Write-Host '2. .\.venv\Scripts\python.exe scripts\init_db.py'
    Write-Host '3. .\.venv\Scripts\python.exe scripts\seed_demo.py'
    Write-Host '4. .\.venv\Scripts\python.exe scripts\build_kb.py'
    Write-Host '5. .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000'
    Write-Host '6. cd frontend; npm run dev'
} -NextStep 'Use docker-full mode if you want the entire stack in containers.'
