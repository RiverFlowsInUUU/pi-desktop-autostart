# PiTelegramWatchdog.ps1
# Pi Desktop 开关联动守护：让 Telegram 桥接跟随 Pi Desktop / agent 自动上下线。
#
# 设计前提（务必先读 SKILL.md）：
#   - agent(node cli.js) 只能由 Pi Desktop GUI spawn；外部脚本拉不回来。
#     外部唯一常用手法是重开 Pi Desktop。
#   - 关闭 Pi Desktop 时，agent 与桥接作为其子进程一起退出（天然满足"关闭即关闭"）。
#   - 所以本守护只做一件事：agent 在跑、但 Telegram 桥接不在时，把桥接接上。
#
# 两条踩过的坑（改这个文件时务必保留）：
#   1. 传给 bash 的路径一律用 $HOME 正斜杠。绝不能用 $env:USERPROFILE 展开后
#      传进去 —— 反斜杠在 bash 双引号里会被吃掉，变成 C:Users... 导致文件找不到。
#   2. Write-Log 用 param() + Add-Content，别写 "$($(Get-Date ...))]" 这种嵌套，
#      PowerShell 括号错误会让整个脚本 ParseException。
#
# 用法：见 scripts/register_watchdog.ps1 注册为登录自启。

$ErrorActionPreference = 'SilentlyContinue'

$log = "$env:USERPROFILE\.pi\agent\tmp\pi-telegram\watchdog.log"
$bash = 'C:\Program Files\Git\bin\bash.exe'
$triggerFlag = "$env:USERPROFILE\.pi\agent\tmp\pi-telegram\.tg-triggered"

function Write-Log {
    param([string]$msg)
    $stamp = Get-Date -Format 'yyyy/MM/dd HH:mm:ss'
    $line = $stamp + ' ' + $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

function Get-AgentPid {
    $a = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent'
    } | Select-Object -First 1
    if ($a) { return $a.ProcessId } else { return $null }
}

function Get-BridgePid {
    $b = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match 'start-bridge.sh'
    } | Select-Object -First 1
    if ($b) { return $b.ProcessId } else { return $null }
}

while ($true) {
    $agent = Get-AgentPid
    $bridgePid = Get-BridgePid

    if ($agent -and -not $bridgePid) {
        if (-not (Test-Path $triggerFlag)) {
            Set-Content -Path $triggerFlag -Value '1' -ErrorAction SilentlyContinue
            Write-Log "agent PID=$agent detected, bridge missing, connecting Telegram"
            # 单引号包住 -> PowerShell 不展开；$HOME 交给 bash 自己展开（正斜杠）
            $arg = 'nohup bash "$HOME/.pi/agent/tmp/pi-telegram/start-bridge.sh" > "$HOME/.pi/agent/tmp/pi-telegram/bridge-stdout.log" 2>&1 & echo launched'
            Start-Process -FilePath $bash -ArgumentList '-c', $arg -WindowStyle Minimized -ErrorAction SilentlyContinue
        }
    } else {
        Remove-Item $triggerFlag -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 6
}
