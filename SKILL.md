---
name: pi-desktop-autostart
description: 排查并修复 Pi Desktop 的 PI 智能体不启动问题 —— 打开后提示"已停止/停止运行"、必须发一条消息才动、关掉后 agent 不跟随退出。同时让 agent 与 Telegram 桥接做到开关联动（打开自动起、关闭自动退）。只要用户提到 Pi Desktop、Pi agent、PI 智能体、pi-coding-agent、"PI 停止运行"、"PI 不在运行"、打开不启动、杀进程后 agent 不回来、Telegram 机器人不回消息，就应使用这个技能。
license: MIT
compatibility: Windows 10/11 + Git for Windows（bash.exe 用于 PATH 诊断）+ Python 3.8+（两个配置脚本）。无需管理员权限（计划任务用 /RL LIMITED）。
metadata:
  author: RiverFlowsInUUU
  version: "1.0"
  verified-on: Pi Desktop 0.1.9-alpha / pi-coding-agent 1.1.0
---

# Pi Desktop 智能体自启动与开关联动

修的是 **Pi Desktop GUI ↔ 它背后 `pi-coding-agent` 子进程**之间的关系。

两个核心诉求：

1. **打开 Pi Desktop → agent 自动运行**（不用先发"你好"去唤醒）
2. **关闭 Pi Desktop → agent 与 Telegram 桥接一起退出**（不留后台孤儿）

> 本文路径中的用户名一律写成 `<你的用户名>` / `%USERPROFILE%` / `$HOME`。
> **真实路径形如 `C:\Users\<你的用户名>\...`，不要照抄，也不要把真实用户名提交到仓库。**

---

## 0 · 先记住这个（判据与红线）

**唯一验收判据** —— agent 起没起来，只看这一条：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent' } |
  Select-Object ProcessId, ParentProcessId
```

- 有输出 = agent 在跑（`ParentProcessId` 应指向某个 `Pi Desktop.exe`）
- 无输出 = 没起来，GUI 才会显示"已停止"

**三条红线**：

1. **别改 `app.asar`。** Electron 打包产物且压缩混淆；改 `settings.json` 和 `.profile` 就够了，二者都在 asar 之外。
2. **凭据零容忍。** `telegram.json` 里的 `botToken` / `botId` / `allowedUserId` / `botUsername` 不得写入任何脚本、日志、文档。桥接脚本自己去读，token 不需要出现在命令行里。
3. **改前备份。** `settings.json` → `.bak`；`.profile` → `.bak-<时间戳>`。这是唯一退路。

> 仓库 CI 全绿 ≠ Pi Desktop 真的拉起了 agent。**验收只用上面那条命令。**

---

## 1 · 架构（先理解，再动手）

```
Pi Desktop.exe (Electron GUI)
├─ gpu-process / utility / renderer   ← GUI 自身子进程，与 agent 无关
└─ node.exe  ← 这才是 agent
   │  命令行形如：
   │  node …\@earendil-works\pi-coding-agent\dist\bundle\cli.js
   │       --mode rpc --provider … --model … --continue
   │       -e "…\resources\resources\pi-desktop-permissions.ts"
   └─ node.exe  billion-context 本地代理 ← agent 就绪的强信号
```

**关键事实**：agent 是 Pi Desktop 的**子进程**，只有 GUI 能 spawn 它。
外部脚本（含 `pi --mode rpc` 直连）**无法命令 GUI 重新拉起 agent**——实测确认。
agent 死了，**唯一恢复手段是重开 Pi Desktop**。别写"自动重生 agent"的守护，那是空转。

---

## 2 · 三步修好

### ① 修预检失败 → 对应"提示停止运行"

根因：Pi Desktop 启动时用 **login shell** 找 `pi`，而那个 shell 加载的 `.profile`
常常没把 `nodejs` / `npm 全局 bin` 加进 PATH → 预检失败。

```bash
# 诊断：模拟 GUI 的干净 login shell
/usr/bin/bash -lc 'echo PATH=$PATH; echo pi=$(command -v pi); echo node=$(command -v node)'
# pi= 与 node= 都为空 => 确认

# 铁证：%APPDATA%\pi-desktop\app-log.jsonl 里有 "Pre-flight failed"

python scripts/fix_profile.py     # 修复（自动备份，无 BOM 写，幂等）
```

### ② 打开即进工作区 → 对应"必须发你好"

```bash
python scripts/set_settings.py    # openToHomeOnLaunch -> false（自动备份，可 --revert）
```

### ③ 装开关联动守护 → 让 Telegram 也自动跟随（可选）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_watchdog.ps1
schtasks /Run /TN PiTelegramWatchdog   # 立即生效，不等下次登录
# 卸载： -Uninstall
```

> **改完任何一步都要：完全关闭 Pi Desktop → 重新打开。**

---

## 3 · 排查速查表

| 现象 | 成因 | 第一动作 |
|---|---|---|
| 打开就提示"PI 停止运行/已停止" | 预检失败（PATH） | 查 `app-log.jsonl` 有无 `Pre-flight failed` → ① |
| 不报停止但不动，发"你好"才启动 | 落在主页 launcher | → ② |
| 上次能跑这次不行 | agent 被外部杀过 | **重开 Pi Desktop**（外部拉不回来） |
| Telegram 不回消息 | 桥接没接上 | 确认 agent 在跑 → 跑 `start-bridge.sh` |
| `settings.json` 改了没生效 | 没重开 GUI | 重开 |

**通用第一动作**：关闭 Pi Desktop → 重新打开。

---

## 4 · 深入资料（按需查阅，不必全读）

- `references/diagnosis.md` —— 完整诊断链路、两个根因的原理与实测证据、feature/bug 定性
- `references/telegram.md` —— Telegram 桥接机制、成功判据、几十 MB 日志的正确读法
- `references/gotchas.md` —— 踩过的坑（PowerShell 转义、`$_` 索引歧义、BOM、反斜杠）

---

## 5 · 实测结论摘要

| 结论 | 状态 |
|---|---|
| 修好 `.profile` 后不再报"停止运行" | ✅ 实测 |
| `openToHomeOnLaunch: false` 后打开即 spawn agent | ✅ 实测 |
| 杀 Pi Desktop 主进程时 agent/桥接随其退出 | ✅ 实测 |
| 外部脚本能命令 GUI 重 spawn agent | ❌ 实测不可行 |
| botToken 未进入任何脚本/日志 | ✅ 已验证 |
