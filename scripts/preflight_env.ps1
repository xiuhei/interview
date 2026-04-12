param(
    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function New-CheckResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Message,
        [string]$NextStep = ''
    )

    [PSCustomObject]@{
        name = $Name
        status = $Status
        message = $Message
        next_step = $NextStep
    }
}

function Test-CommandExists {
    param([string]$CommandName)
    [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Get-CommandVersion {
    param(
        [string]$Executable,
        [string[]]$Arguments = @('--version')
    )

    try {
        (& $Executable @Arguments 2>&1 | Out-String).Trim()
    }
    catch {
        $_.Exception.Message
    }
}

function Get-Python312Executable {
    if (Test-CommandExists 'py') {
        $py312Exe = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $py312Exe) {
            return $py312Exe
        }
    }

    if (Test-CommandExists 'python') {
        $pythonExe = (& python -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        $pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null | Out-String).Trim()
        if ($pythonExe -and $pythonVersion -eq '3.12') {
            return $pythonExe
        }
    }

    return $null
}

$results = New-Object System.Collections.Generic.List[object]
$python312Exe = Get-Python312Executable

if (Test-CommandExists 'python') {
    $pythonSource = (Get-Command python -ErrorAction SilentlyContinue).Source

    if ($pythonSource -like '*WindowsApps*') {
        $results.Add((New-CheckResult -Name 'python' -Status 'warn' -Message "python currently resolves to the WindowsApps alias [$pythonSource]." -NextStep 'Reopen the terminal so the updated Python 3.12 PATH is picked up.'))
    }
    else {
        $pythonExe = (& python -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        $pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null | Out-String).Trim()

        if (-not $pythonExe) {
            $results.Add((New-CheckResult -Name 'python' -Status 'fail' -Message 'python command exists but executable path could not be resolved.' -NextStep 'Install official CPython 3.12 and reopen the terminal.'))
        }
        elseif ($pythonExe -match 'msys64') {
            $results.Add((New-CheckResult -Name 'python' -Status 'fail' -Message "python currently points to MSYS2: $pythonExe" -NextStep 'Install official CPython 3.12 and make it win over msys64 in PATH.'))
        }
        elseif (-not $pythonVersion.StartsWith('3.12.')) {
            $results.Add((New-CheckResult -Name 'python' -Status 'fail' -Message "python currently resolves to $pythonVersion [$pythonExe]; this project requires Python 3.12." -NextStep 'Reopen the terminal or use py -3.12 directly.'))
        }
        else {
            $results.Add((New-CheckResult -Name 'python' -Status 'ok' -Message "python -> $pythonVersion [$pythonExe]"))
        }
    }
}
else {
    $results.Add((New-CheckResult -Name 'python' -Status 'warn' -Message 'python command is not currently available in this shell.' -NextStep 'If Python 3.12 was just installed, reopen the terminal; the project scripts will prefer py -3.12.'))
}

if (Test-CommandExists 'py') {
    $pyList = (& py -0p 2>&1 | Out-String).Trim()
    if ($pyList -match 'No installed Pythons found') {
        $results.Add((New-CheckResult -Name 'py-launcher' -Status 'fail' -Message 'py.exe exists but no registered Python 3.12 was found.' -NextStep 'Install official CPython 3.12 and confirm py -0p lists it.'))
    }
    else {
        $results.Add((New-CheckResult -Name 'py-launcher' -Status 'ok' -Message $pyList))
    }
}
else {
    $results.Add((New-CheckResult -Name 'py-launcher' -Status 'fail' -Message 'py.exe was not found.' -NextStep 'Install official CPython 3.12 for Windows so py.exe is available.'))
}

if ($python312Exe) {
    $results.Add((New-CheckResult -Name 'python-3.12' -Status 'ok' -Message "Detected Python 3.12 at $python312Exe"))

    $pipProbe = (& $python312Exe -c "import importlib.util; print('present' if importlib.util.find_spec('pip') else 'missing')" 2>$null | Out-String).Trim()
    if ($pipProbe -eq 'present') {
        $pipVersion = (& $python312Exe -m pip --version 2>&1 | Out-String).Trim()
        $results.Add((New-CheckResult -Name 'pip' -Status 'ok' -Message $pipVersion))
    }
    else {
        $results.Add((New-CheckResult -Name 'pip' -Status 'fail' -Message 'pip was not found for Python 3.12.' -NextStep 'Run py -3.12 -m ensurepip --upgrade.'))
    }
}
else {
    $results.Add((New-CheckResult -Name 'python-3.12' -Status 'fail' -Message 'No usable official Python 3.12 interpreter was found.' -NextStep 'Install official CPython 3.12 and confirm py -3.12 works.'))
    $results.Add((New-CheckResult -Name 'pip' -Status 'fail' -Message 'pip check was skipped because Python 3.12 is unavailable.' -NextStep 'Fix Python 3.12 first, then rerun preflight.'))
}

if (Test-CommandExists 'node') {
    $results.Add((New-CheckResult -Name 'node' -Status 'ok' -Message (Get-CommandVersion -Executable 'node')))
}
else {
    $results.Add((New-CheckResult -Name 'node' -Status 'fail' -Message 'node command was not found.' -NextStep 'Install Node.js 20/22/24 LTS.'))
}

if (Test-CommandExists 'npm') {
    $results.Add((New-CheckResult -Name 'npm' -Status 'ok' -Message (Get-CommandVersion -Executable 'npm')))
}
else {
    $results.Add((New-CheckResult -Name 'npm' -Status 'fail' -Message 'npm command was not found.' -NextStep 'Reinstall Node.js and make sure npm is available.'))
}

if (Test-CommandExists 'docker') {
    $dockerComposeVersion = (& cmd /c "docker compose version 2>nul" | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $dockerComposeVersion) {
        $results.Add((New-CheckResult -Name 'docker-compose' -Status 'ok' -Message $dockerComposeVersion))
    }
    else {
        $results.Add((New-CheckResult -Name 'docker-compose' -Status 'warn' -Message 'docker command exists but compose could not be confirmed.' -NextStep 'Start Docker Desktop if you want Docker deployment.'))
    }

    & cmd /c "docker info >nul 2>nul"
    if ($LASTEXITCODE -eq 0) {
        $results.Add((New-CheckResult -Name 'docker-daemon' -Status 'ok' -Message 'Docker daemon is running.'))
    }
    else {
        $results.Add((New-CheckResult -Name 'docker-daemon' -Status 'warn' -Message 'docker command exists but the daemon is not running.' -NextStep 'Start Docker Desktop before using docker compose build or up.'))
    }
}
else {
    $results.Add((New-CheckResult -Name 'docker-compose' -Status 'warn' -Message 'docker command was not found.' -NextStep 'Install Docker Desktop if you want Docker deployment.'))
}

if ($AsJson) {
    $results | ConvertTo-Json -Depth 4
}
else {
    foreach ($item in $results) {
        $prefix = switch ($item.status) {
            'ok' { '[OK]' }
            'warn' { '[WARN]' }
            default { '[FAIL]' }
        }
        Write-Host "$prefix $($item.name): $($item.message)"
        if ($item.next_step) {
            Write-Host "       Next: $($item.next_step)"
        }
    }
}
