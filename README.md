# pi-desktop-autostart

让 **Pi Desktop** 的 PI 智能体做到**开关联动**：打开自动运行、关闭自动退出，
Telegram 桥接自动跟随。

> 这是一个 AI Agent Skill（`SKILL.md` 是给 Agent 看的手册），也可由人手动执行。
> 遵循 [Agent Skills 规范](https://agentskills.io/specification)。

---

## 解决什么

| 症状 | 根因 |
|---|---|
| 打开提示 **"PI 停止运行 / 已停止"** | 启动预检在 login shell 里找不到 `pi`（PATH 缺 nodejs / npm） |
| 打开后**不发消息就不动**，要发个"你好" | 默认落在"主页 launcher"、还没进工作区，因此不 spawn agent |
| 上次能跑，**这次怎么都起不来** | agent 是 Pi Desktop 子进程，被外部杀掉后**只能重开**恢复 |
| Telegram 机器人不回消息 | 桥接没接上（新 agent 是新 PID，桥接要重跑） |

---

## 三步修好

```bash
# ① 修预检失败（对应"停止运行"）
/usr/bin/bash -lc 'echo pi=$(command -v pi); echo node=$(command -v node)'  # 诊断
python scripts/fix_profile.py

# ② 打开即进工作区（对应"必须发你好"）
python scripts/set_settings.py

# ③ 装开关联动守护（让 Telegram 也自动跟随，可选）
powershell -ExecutionPolicy Bypass -File scripts/register_watchdog.ps1
schtasks /Run /TN PiTelegramWatchdog
```

> **每改一步都要：完全关闭 Pi Desktop → 重新打开。**

---

## 验收（只看这一条）

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent' } |
  Select-Object ProcessId, ParentProcessId
```

有输出 = agent 在跑，且 `ParentProcessId` 指向某个 `Pi Desktop.exe`。

---

## 生效之后

- 关闭 Pi Desktop → agent 与桥接作为子进程**一起退出**，不留孤儿
- 打开 Pi Desktop → agent **自动 spawn**；守护把 Telegram 桥接接上
- 守护每 6 秒检查，只在"agent 在、桥接不在"时动手，空闲不折腾

---

## feature 还是 bug

- **主页时不预先拉起 agent** → feature（没选工作区，提前起进程是浪费）
- **让人以为坏了** → 默认 UX 的观感问题
- **提示"停止运行"** → 真的 bug（`.profile` PATH 缺失，本 skill 修的就是它）

改 `openToHomeOnLaunch: false` 后**打开即 spawn**，是实测确认的。
（"主页→不spawn / 工作区→spawn"的完整因果链属推导，详见 `references/diagnosis.md`。）

---

## 目录结构

```
pi-desktop-autostart/
├── SKILL.md              # Agent 手册（精简，结论优先）
├── README.md             # 本文件（面向人）
├── LICENSE               # MIT
├── scripts/              # 可执行脚本
│   ├── fix_profile.py          修 .profile PATH
│   ├── set_settings.py         改 openToHomeOnLaunch
│   ├── PiTelegramWatchdog.ps1  开关联动守护
│   └── register_watchdog.ps1   注册/卸载/查看守护
└── references/           # 按需深入（progressive disclosure）
    ├── diagnosis.md     原理、证据、feature/bug 定性
    ├── telegram.md      桥接机制、判据、隐私红线
    └── gotchas.md       踩过的坑（BOM/转义/索引歧义…）
```

---

## 隐私

本仓库**不含**任何敏感值：

- 无 Telegram `botToken` / `botId` / `allowedUserId` / `botUsername`
- 路径用 `%USERPROFILE%` / `$HOME` / `<你的用户名>` 占位，无真实用户名
- 桥接脚本自行读取 `~/.pi/agent/telegram.json`，token 从不进命令行/日志/文档
- `.gitignore` 屏蔽 `*.pyc` / `*.bak` / `*.log` / `telegram.json`

---

## 环境

- Windows 10/11 + Git for Windows + Python 3.8+
- Pi Desktop（`%APPDATA%\pi-desktop\settings.json` 存在）
- 计划任务用 `/RL LIMITED`，**不需要管理员**
- 实测版本：Pi Desktop 0.1.9-alpha / pi-coding-agent 1.1.0
