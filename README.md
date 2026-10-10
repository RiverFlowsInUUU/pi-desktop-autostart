# pi-desktop-autostart

让 **Pi Desktop** 的 PI 智能体做到**开关联动**：打开自动运行、关闭自动退出，并且 Telegram 桥接自动跟随。

> 这是一个 AI Agent Skill（`SKILL.md` 是给 Agent 看的操作手册），同时也完全可以由人手动执行。

---

## 解决什么问题

| 症状 | 根因 |
|---|---|
| 打开 Pi Desktop 提示 **"PI 停止运行 / 已停止"** | Pi Desktop 启动预检在 login shell 里找不到 `pi`（PATH 缺 nodejs / npm） |
| 打开后**不发消息就不动**，要发个"你好"才启动 | 默认落在"主页 launcher"、还没进工作区，因此不 spawn agent |
| 明明上次能跑，**这次怎么都起不来** | agent 是 Pi Desktop 的子进程，一旦被外部杀掉，**只能重开 Pi Desktop** 恢复 |
| Telegram 机器人不回消息 | 桥接没接上（新 agent 是新 PID，桥接要重跑一次） |

---

## 架构一图看懂

```
Pi Desktop.exe (Electron GUI)
├─ gpu / utility / renderer    ← GUI 自身子进程，与 agent 无关
└─ node.exe  ← 这才是 agent
   │  命令行含 @earendil-works/pi-coding-agent/.../cli.js --mode rpc
   └─ node.exe  billion-context 本地代理（agent 就绪的强信号）
```

**验收只看一条**：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent' } |
  Select-Object ProcessId, ParentProcessId
```

有输出 = agent 在跑；`ParentProcessId` 应指向某个 `Pi Desktop.exe`。

---

## 三步修好

### 1. 修预检失败（对应"停止运行"）

```bash
# 先诊断：模拟 GUI 的干净 login shell
/usr/bin/bash -lc 'echo PATH=$PATH; echo pi=$(command -v pi); echo node=$(command -v node)'
# pi= 和 node= 都为空 => 确认是这个病

python scripts/fix_profile.py          # 修复（自动备份）
```

> 也可以直接看 `%APPDATA%\pi-desktop\app-log.jsonl`，有 `"Pre-flight failed"` 就是铁证。

### 2. 打开即进工作区（对应"必须发你好"）

```bash
python scripts/set_settings.py         # openToHomeOnLaunch -> false（自动备份）
```

### 3. 装开关联动守护（可选，让 Telegram 也自动跟随）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_watchdog.ps1
schtasks /Run /TN PiTelegramWatchdog   # 立即跑一次，不等下次登录
```

卸载随时可以：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_watchdog.ps1 -Uninstall
```

> **每一步改完都要：完全关闭 Pi Desktop → 重新打开。**

---

## 生效之后

- 关闭 Pi Desktop → agent 与 Telegram 桥接作为子进程**一起退出**，不留后台孤儿
- 打开 Pi Desktop → agent **自动 spawn**；守护再把 Telegram 桥接接上
- 每 6 秒检查一次，只在"agent 在、桥接不在"时才动手，空闲不折腾

---

## feature 还是 bug？

- **主页时不预先拉起 agent** → feature（你还没选工作区，提前起进程纯属浪费）
- **让人以为坏了** → 默认交互的观感问题
- **提示"停止运行"** → 真的 bug（`.profile` PATH 缺失，本 skill 修的就是它）

改 `openToHomeOnLaunch: false` 之后**打开即 spawn**这件事，是实测确认的。

---

## 隐私红线

本仓库**不包含**任何敏感值：

- 不含 Telegram `botToken` / `botId` / `allowedUserId` / `botUsername`
- 路径全部用 `%USERPROFILE%` / `$HOME` / 占位符，不含真实用户名
- 桥接脚本自行读取 `~/.pi/agent/telegram.json`，token 从不出现在命令行、日志或本文档里

---

## 文件

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 给 AI Agent 看的操作手册（含完整判据与踩坑） |
| `scripts/fix_profile.py` | 修 `.profile` 的 PATH（无 BOM 写，幂等） |
| `scripts/set_settings.py` | 改 `openToHomeOnLaunch`（自动备份，可 `--revert`） |
| `scripts/PiTelegramWatchdog.ps1` | 开关联动守护 |
| `scripts/register_watchdog.ps1` | 注册/卸载/查看该守护（`ONLOGON`） |

---

## 环境要求

- Windows + Git for Windows（脚本用 `bash.exe` 做 PATH 诊断）
- Pi Desktop（`%APPDATA%\pi-desktop\settings.json` 存在）
- Python 3（两个配置脚本）
- 计划任务用 `/RL LIMITED`，**不需要管理员权限**
