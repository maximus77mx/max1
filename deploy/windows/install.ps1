<#
  Thai flood dashboard - one-shot installer for Windows Server + IIS.

  Run in an elevated PowerShell from the repository folder:
      powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
  Options:
      -WebDir C:\inetpub\wwwroot\flood   folder IIS serves (index.html + geo\)
      -Minutes 15                        how often to refresh
      -Python py                         python launcher/executable to use
      -SkipIis                           do not create the IIS application
      -SkipTask                          do not register the scheduled task
#>
param(
    [string]$WebDir = "C:\inetpub\wwwroot\flood",
    [int]$Minutes = 15,
    [string]$Python = "",
    [switch]$SkipIis,
    [switch]$SkipTask
)
$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $AppDir
Write-Host "App folder: $AppDir"
Write-Host "Web folder: $WebDir"

# 1. Python virtual environment + package
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $Python = "py" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
    else { throw "Python 3.10+ not found. Install it from python.org (tick 'Add to PATH') and run again." }
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $Python -m venv .venv
}
Write-Host "Installing thaiflood..."
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install . --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed (check internet / HTTPS_PROXY)." }

# 2. .env with API keys (never overwritten)
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warning ".env created from .env.example - fill in GISTDA_API_KEY and SPHERE_API_KEY, then run thaiflood-update.bat again."
}

# 3. Web folder + IIS config
New-Item -ItemType Directory -Force -Path $WebDir | Out-Null
Copy-Item "deploy\iis\web.config" (Join-Path $WebDir "web.config") -Force
if (-not $SkipIis) {
    if (Get-Module -ListAvailable -Name WebAdministration) {
        Import-Module WebAdministration
        $name = Split-Path $WebDir -Leaf
        if (-not (Get-WebApplication -Site "Default Web Site" -Name $name)) {
            New-WebApplication -Site "Default Web Site" -Name $name -PhysicalPath $WebDir | Out-Null
            Write-Host "IIS application created: http://localhost/$name/"
        } else {
            Write-Host "IIS application already exists: http://localhost/$name/"
        }
    } else {
        Write-Warning "IIS (WebAdministration) not found - create a site pointing to $WebDir manually."
    }
}

# 4. Scheduled task (runs as SYSTEM, so no user needs to stay logged on)
$bat = Join-Path $AppDir "deploy\windows\thaiflood-update.bat"
if (-not $SkipTask) {
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"`"$bat`" `"$WebDir`"`"" -WorkingDirectory $AppDir
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $Minutes) -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew -StartWhenAvailable
    Register-ScheduledTask -TaskName "Thai flood dashboard" -Action $action -Trigger $trigger -Settings $settings `
        -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Write-Host "Scheduled task 'Thai flood dashboard' runs every $Minutes minutes."
}

# 5. First run (downloads boundaries + collects every source; may take several minutes)
Write-Host "First run... (log: $AppDir\data\update.log)"
& cmd.exe /c "`"$bat`" `"$WebDir`""
Write-Host ""
Write-Host "Done. Open http://localhost/$(Split-Path $WebDir -Leaf)/  - per-source results are at the end of data\update.log"
