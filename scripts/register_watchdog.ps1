# register_watchdog.ps1
# 把 PiTelegramWatchdog.ps1 注册为登录自启的计划任务（当前用户，无需管理员）。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File register_watchdog.ps1          注册
#   powershell -ExecutionPolicy Bypass -File register_watchdog.ps1 -Uninstall  卸载
#   powershell -ExecutionPolicy Bypass -File register_watchdog.ps1 -Status      查看状态

param(
    [switch]$Uninstall,
    [switch]$Status
)

$ErrorActionPreference = 'SilentlyContinue'
$taskName = 'PiTelegramWatchdog'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$watchdog = Join-Path $scriptDir 'PiTelegramWatchdog.ps1'

# ---- 卸载 ----
if ($Uninstall) {
    schtasks /End /TN $taskName 2>&1 | Out-Null
    schtasks /Delete /TN $taskName /F 2>&1 | Out-Null
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'PiTelegramWatchdog.ps1' } |
        ForEach-Object { taskkill /PID $($_.ProcessId) /F 2>&1 | Out-Null }
    Write-Host '[Uninstall] done'
    return
}

# ---- 状态 ----
if ($Status) {
    $info = schtasks /Query /TN $taskName /FO LIST 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[Status] registered'
        $info | Select-String 'TaskName|Status|Logon Mode' | ForEach-Object {
            Write-Host ('  ' + $_.ToString())
        }
    } else {
        Write-Host '[Status] NOT registered'
    }
    $proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'PiTelegramWatchdog.ps1' } |
        Select-Object -First 1
    if ($proc) {
        Write-Host ('[Status] running PID=' + $proc.ProcessId)
    } else {
        Write-Host '[Status] not running'
    }
    return
}

# ---- 注册前：严格校验 watchdog 语法（不能省）----
if (-not (Test-Path $watchdog)) {
    Write-Host ('[Error] watchdog not found: ' + $watchdog)
    exit 1
}

$tokens = $null
$errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($watchdog, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
    Write-Host ('[Error] watchdog has ' + $errors.Count + ' syntax error(s), fix first:')
    $errors | Select-Object -First 5 | ForEach-Object {
        Write-Host ('  line ' + $_.Extent.StartLineNumber + ': ' + $_.Message)
    }
    exit 1
}
Write-Host '[Check] watchdog syntax OK'

# ---- 注册（先删同名旧任务）----
schtasks /Delete /TN $taskName /F 2>&1 | Out-Null

$tr = 'powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $watchdog + '"'
schtasks /Create /TN $taskName /TR $tr /SC ONLOGON /RL LIMITED /F 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host '[OK] registered: PiTelegramWatchdog (ONLOGON)'
    Write-Host '[Info] checks every 6s: if agent runs and bridge is missing, connect bridge'
    Write-Host '[Info] run now without waiting for next logon:'
    Write-Host '         schtasks /Run /TN PiTelegramWatchdog'
    Write-Host '[Info] uninstall: powershell -File register_watchdog.ps1 -Uninstall'
} else {
    Write-Host '[Error] register failed; rerun as current user (LIMITED needs no admin)'
}
