---
name: pi-desktop-autostart
description: 排查并修复 Pi Desktop（Electron GUI）"打开后 PI agent 不启动 / 提示已停止 / 必须发一条消息才动"的问题，并让 agent 与 Telegram 桥接做到开关联动（打开自动起、关闭自动退）。只要用户提到 Pi Desktop、Pi agent、PI 智能体、pi-coding-agent、"PI 停止运行"、"PI 不在运行"、打开不启动、taskill 后 agent 不回来，就应该使用这个技能。
---

# Pi Desktop 智能体自启动与开关联动

修的是 **Pi Desktop GUI 与它背后 `pi-coding-agent` 子进程**之间的关系。

核心目标（用户最常见的两个诉求）：

1. **打开 Pi Desktop → agent 自动运行**（不用先发一条"你好"去"唤醒"它）
2. **关闭 Pi Desktop → agent 与 Telegram 桥接一起退出**（不留后台孤儿）

> 本文所有路径中的用户名一律写成 `<你的用户名>` / `%USERPROFILE%` / `$HOME`。
> **真实路径形如 `C:\Users\<你的用户名>\...`，不要照抄，也不要把自己机器的真实用户名提交到任何仓库。**

---

## 0 · 三条底线

1. **这是 GUI ↔ 子进程的脆弱链路，别硬改 app.asar。** `app.asar` 是 Electron 打包产物、且被压缩混淆；直接改它既难维护也不是正解。改 `settings.json` 和 `.profile` 就够了，它们在asar 之外。
2. **绝对不要把 Telegram botToken 写进任何地方。** `telegram.json` 里有 `botToken` / `botId` / `allowedUserId` / `botUsername`。skill 的脚本、日志、README **一律不得**包含或回显这些值。你只需调用桥接脚本（它自己去读那份 JSON），token 不需要出现在任何命令行里。
3. **改文件前先备份。** `settings.json` 改前复制一份到 `settings.json.bak`；`.profile` 同理。这是能回滚的唯一保险。

> 判据：仓库/脚本 CI 全绿不代表 `Pi Desktop` 真的拉起了 agent。**最终验收只用一条**——任务管理器里有没有 `node.exe` 且命令行含 `pi-coding-agent`（见 §1 验收）。

---

## 1 · 一眼看懂架构（先理解再动手）

```
Pi Desktop.exe (Electron GUI)
├─ gpu-process / utility / renderer   ← GUI 自身的子进程，跟 agent 无关
└─ node.exe  <这才是 agent>            ← GUI 收到"要干活"的信号后 spawn
   │  命令行形如：
   │  node …\@earendil-works\pi-coding-agent\dist\bundle\cli.js
   │       --mode rpc --provider … --model … --continue
   │       -e "…\resources\resources\pi-desktop-permissions.ts"
   └─ node.exe  billion-context 本地代理（活 agent 的子进程，是"引擎就绪"的强信号）
```

**验收命令**（判断 agent 到底起没起来，只用这个）：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent' } |
  Select-Object ProcessId, ParentProcessId, StartTime
```

- 有输出 = agent 在跑（且 `ParentProcessId` 应指向某个 `Pi Desktop.exe`）
- 无输出 = agent 没起来，GUI 才会显示"已停止 / 停止运行"

**关键点**：agent 是 **Pi Desktop 的子进程**，只有 GUI 能 spawn 它。
外部脚本（包括 `pi --mode rpc` 直连）**无法命令 GUI 重新拉起 agent**——实测过，杀掉 agent 后从外部触发是拉不回来的，**唯一恢复手段是重开 Pi Desktop**。别在这上面浪费时间写"自动重生 agent"的守护。

---

## 2 · 两个真实成因（按出现频率排序）

### 成因 A：`.profile` 缺 nodejs / npm，导致启动预检失败 ★最常见

**症状**：打开 Pi Desktop 直接提示 **"PI 停止运行 / 已停止"**，或者报错文案类似
`Pre-flight failed … Pi binary not found. Searched the login shell PATH, npm's global prefix …`

**原理**：Pi Desktop 启动时会开一个 **login shell** 去找 `pi` 可执行文件。Windows 的用户 PATH 里虽然有 `nodejs` 和 `npm`，但**那个 login shell 加载的是 `.profile`（或 `.bash_profile`）**，而这两个文件常常只 source 了 `$HOME/.local/bin/env`，里面**没有** nodejs / npm → 预检失败 → GUI 认为 agent 起不来。

**诊断**（关键一步，直接复现 GUI 的视角）：

```bash
# 模拟 GUI 的干净 login shell，看 PATH 里到底有没有 node / pi
/usr/bin/bash -lc 'echo PATH=$PATH; echo pi=$(command -v pi); echo node=$(command -v node)'
```

如果 `pi=` 和 `node=` 都是空 → 确认是成因 A。

另外可以直接查 GUI 的启动日志（不要去翻那个几十 MB 的 `bridge-stdout.log`，那是 agent 会话日志）：

```
%APPDATA%\pi-desktop\app-log.jsonl
```

里面有 `"Pre-flight failed"` 就是铁证。

**修复**：给 `.profile` 补上 nodejs 与 npm 全局 bin（保留原有内容）。见 `scripts/fix_profile.py`。

> 写文件时务必 `encoding=utf-8` 且 **`newline='\n'`（无 BOM）**。
> 实测：PowerShell `Out-File` 会写 UTF-8 BOM，bash 会把 BOM 当命令 → `.profile` 整个解析失败，第 1 行就报 `command not found`。用 Python 或 bash heredoc 写最稳。

### 成因 B：默认落在"主页 launcher"，未进工作区 → 不 spawn agent

**症状**：GUI 能开、预检也过了（不再报"停止运行"），但打开后停在"最近项目/主页"那一屏，**必须发一条消息**（比如"你好"）才出现"正在启动智能体…"。

**这不是"必须发消息"的硬性要求，而是：**
- `openToHomeOnLaunch: true`（默认）→ 打开停在主页 launcher，**还没选定工作区**，所以不 spawn agent（省资源，属于 feature）
- `openToHomeOnLaunch: false` → 打开**直接进工作区**，配 `resumeLastSession: true`，**实测 agent 会自动 spawn**，不发消息也起来了

配置文件：

```
%APPDATA%\pi-desktop\settings.json
```

改这两个字段（改前备份）：

```json
{
  "openToHomeOnLaunch": false,
  "resumeLastSession": true
}
```

见 `scripts/set_settings.py`。改完**必须重开 Pi Desktop** 才生效。

> 关于 feature/bug 的定性（别对用户瞎断言）：
> - "主页时不预先拉起 agent" = **feature**（合理省资源）
> - "让人以为坏了" = 默认 UX 的**观感问题**
> - "提示停止运行" = **真的 bug**（成因 A，已修）
>
> 但我没能逐个对照验证"主页→不spawn / 工作区→spawn"这条完整因果链，只是从"改开关后自动起来了 + 官方 `openToHomeOnLaunch` 描述"推导的。**开关生效这件事本身是实测确认过的。**

---

## 3 · 开关联动（可选但推荐）

改完成因 A + B 之后：

- **关闭 Pi Desktop** → agent 和桥接都是它的子进程，**天然一起退出**，不需要任何清理脚本 ✅
- **打开 Pi Desktop** → 自动 spawn agent ✅
- **但 Telegram 桥接不会自动接**（新 agent 是新 PID，`start-bridge.sh` 得重新跑一次）

要补齐最后一环，装一个轻量 watchdog：**只在"agent 在跑、但桥接不在"时**，自动拉起桥接。

```powershell
# 注册为登录自启（当前用户），每 6 秒检查一次，无 agent 时不动作
schtasks /Create /TN PiTelegramWatchdog `
  /TR "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"%USERPROFILE%\PiTelegramWatchdog.ps1`"" `
  /SC ONLOGON /RL LIMITED /F
```

脚本见 `scripts/PiTelegramWatchdog.ps1`。

**两个踩过的坑**：

1. **路径别用 `$env:USERPROFILE` 展开后传给 bash。** PowerShell 展开成 `C:\Users\…`，反斜杠在 bash 双引号里会被吃掉，变成 `C:Users…` → `No such file or directory`。
   一律写 `$HOME/.pi/agent/...`（正斜杠），让 **bash 自己**展开。
2. **PowerShell 语法特别容易写错，** `New-Module` 那种粗测会漏报。装任务前用这个严格校验：

```powershell
$t=$null; $e=$null
[System.Management.Automation.Language.Parser]::ParseFile($script,[ref]$t,[ref]$e)
if($e.Count -gt 0){ $e | Select-Object -First 5 }
```

尤其注意：
- `Write-Log` 别写成 `"$($(Get-Date -Format '…')] $msg"` —— 括号嵌套错，整个脚本崩
- 传给 bash 的命令里含 `&&` `<` `&`，在 PowerShell 双引号里会被当成重定向/分隔符 → **改用单引号包住**，内含 `$HOME`

---

## 4 · Telegram 桥接（可选）

桥接靠 `~/.pi/agent/tmp/pi-telegram/start-bridge.sh`，它把一条 `/telegram-connect` 通过 stdin 喂给 `pi --mode rpc`，从而连上**已经在跑的** agent 引擎。

**前提**：必须先有一个活的 agent 在跑（见 §1 验收）。没有活引擎，桥接连不上——这就是为什么 §3 的 watchdog 要先判断 `$agent` 存在。

桥接成功的标志：

```
~/.pi/agent/tmp/pi-telegram/bridge-stdout.log
末尾出现："telegram" … "connected"
```

**那个 `bridge-stdout.log` 会长到几十 MB**（里面塞了完整会话 JSON），别直接 `cat`。要取尾部短行：

```powershell
Get-Content bridge-stdout.log -Tail 15 | Where-Object { $_.Length -lt 260 }
```

---

## 5 · 排查速查表

| 现象 | 最可能成因 | 第一动作 |
|---|---|---|
| 打开就提示"PI 停止运行/已停止" | 成因 A（预检失败） | 查 `app-log.jsonl` 有无 `Pre-flight failed`；跑成因 A 的诊断命令 |
| 不报停止，但不动，发"你好"才启动 | 成因 B（落在主页） | 改 `openToHomeOnLaunch: false`，重开 GUI |
| 上次能跑，这次不行了 | agent 被外部杀过 | 重开 Pi Desktop（外部拉不回来，别挣扎） |
| GUI 开着但 agent 进程一会儿没了 | — | 同上，重开；若频繁发生才需深挖 |
| Telegram 不回消息 | 桥接没接上 | 确认 agent 在跑，再手动跑一次 `start-bridge.sh` |
| agent 在，但被自己的调度/日志干扰 | 排查时误杀 | 重开最简单 |

**通用第一动作（几乎所有场景）**：

> **关闭 Pi Desktop → 重新打开。**

改完任何配置都必须重开才生效；误杀了 agent 也只有这条路能恢复。

---

## 6 · 隐私与交付红线（做成本 skill 时尤其注意）

仓库里**绝对不能出现**：

- Telegram `botToken`、`botId`、`allowedUserId`、`botUsername`（在 `~/.pi/agent/telegram.json` 里）
- 真实用户名 / home 绝对路径（一律用 `%USERPROFILE%`、`$HOME`、`<your-user>` 占位）
- 具体 PID / 端口经验值（那是本次会话的瞬时值，不是知识）

可以出现：

- 配置字段名与取值（`openToHomeOnLaunch: false` 这类）
- 诊断命令、脚本、判据
- 架构图与 parent-child 关系

---

## 7 · 文件清单

| 文件 | 作用 |
|---|---|
| `scripts/fix_profile.py` | 修复 `.profile`：补 nodejs / npm 进 login shell PATH（无 BOM 写） |
| `scripts/set_settings.py` | 改 `settings.json`：`openToHomeOnLaunch=false`（自动备份） |
| `scripts/PiTelegramWatchdog.ps1` | 开关联动守护：agent 在、桥接不在时自动接 Telegram |
| `scripts/register_watchdog.ps1` | 把上面那个守护注册成登录自启计划任务 |
| `README.md` | 面向人的说明（安装/使用/排查） |

---

## 8 · 本次修复的实测结论摘要

- 修好 `.profile` 后，Pi Desktop 打开**不再报"停止运行"**（预检通过）
- `openToHomeOnLaunch: false` 后，**打开即 spawn agent**，无需发"你好"
- 杀掉 Pi Desktop 主进程时，agent 与桥接**随其一起退出**（天然满足"关闭即关闭"）
- 外部脚本**无法**命令 GUI 重新 spawn agent（实测确认，别写这种守护）
- botToken 全程未进入任何脚本/日志，桥接脚本自己去读 `telegram.json`
