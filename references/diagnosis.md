# 诊断链路与两个根因

按需查阅。主 `SKILL.md` 只给了结论，这里给**原理与证据**。

---

## 根因 A：`.profile` 缺 nodejs / npm → 启动预检失败

### 症状

打开 Pi Desktop 直接提示 **"PI 停止运行 / 已停止"**；
GUI 日志 `%APPDATA%\pi-desktop\app-log.jsonl` 里有：

```json
{"level":"error","scope":"pi","message":"Pre-flight failed",
 "detail":"Pi binary not found. Searched the login shell PATH, npm's global prefix,
           node version managers (nvm, fnm, volta, asdf, mise, nodenv, n)
           and common install locations..."}
```

### 原理

Pi Desktop 启动时会**新开一个 login shell** 去找 `pi` 可执行文件。

- Windows 的**用户/机器 PATH** 里确实有 `nodejs` 和 `npm`
  （实测：user PATH 含 `%APPDATA%\npm`，machine PATH 含 `C:\Program Files\nodejs\`）
- 但那个 login shell **只加载 `.profile`（或 `.bash_profile`）**
- 而 `.profile` 常常只有一行 `. "$HOME/.local/bin/env"` —— 这个脚本
  **只把 `$HOME/.local/bin` 加进 PATH**，不含 nodejs / npm
- ⇒ 干净 login shell 里 `PATH` 基本为空，`pi` 和 `node` 都找不到 → 预检失败

### 复现与验证（关键）

```bash
# 模拟 GUI 视角：干净 login shell
/usr/bin/bash -lc 'echo PATH=$PATH; echo pi=$(command -v pi); echo node=$(command -v node)'
```

修复前：`PATH=` 空、`pi=` 空、`node=` 空。
修复后：

```
PI=/c/Users/<用户名>/AppData/Roaming/npm/pi
NODE=/c/Program Files/nodejs/node
```

> ⚠️ 别用 `env -i` 去"清空环境"测试 —— 那会把 PATH 清到连 `bash` 自身都找不到，
> 得到的是假阴性。用 `/usr/bin/bash -lc` 才是真实模拟。

### 修复细节

用 `scripts/fix_profile.py`（或手写）：在 `.profile` 保留原内容基础上追加

```sh
case ":${PATH}:" in
  *":/c/Program Files/nodejs":*) ;;
  *) export PATH="/c/Program Files/nodejs:$PATH" ;;
esac
case ":${PATH}:" in
  *":$HOME/AppData/Roaming/npm":*) ;;
  *) export PATH="$HOME/AppData/Roaming/npm:$PATH" ;;
esac
```

**必须无 BOM**（见 `gotchas.md`）。

---

## 根因 B：默认落在"主页 launcher" → 不 spawn agent

### 症状

GUI 能开、预检也过了（**不再报"停止运行"**），但打开后停在
"最近项目/主页"那一屏，**必须发一条消息**（如"你好"）才出现"正在启动智能体…"。

### 机制

配置项 `openToHomeOnLaunch`（`%APPDATA%\pi-desktop\settings.json`）：

| 值 | 打开时 | agent 行为 |
|---|---|---|
| `true`（默认） | 停在主页 launcher（统计、最近会话） | 还没选定工作区 → **不 spawn** |
| `false` | 直接进工作区 | 有会话了 → **自动 spawn** |

配 `resumeLastSession: true` 一起用。

### 定性：feature 还是 bug

- **主页时不预先拉起 agent** → **feature**。你还没选工作区，提前起进程纯属浪费。
- **让人以为坏了** → 默认 UX 的观感问题（多一步操作）。
- **提示"停止运行"** → 真的 **bug**（根因 A）。

⚠️ **诚实边界**：我没能逐个状态对照验证"主页→不spawn / 工作区→spawn"这条完整因果链。
它是从 **「改开关后确实自动起来了」+ 官方 `openToHomeOnLaunch` 描述**推导的。
**开关生效这件事本身是实测确认过的**（改完重开，不发消息也捕获到了 agent 进程）。

---

## 为什么外部无法"自动重生 agent"

实测记录：

1. 杀掉 agent（PID 6760），确认子进程消失
2. 用 `pi --mode rpc` 通过 stdin 喂启动指令试图重新拉起
3. 等 12 秒 → **agent 未起来**

原因：agent 是 Pi Desktop 的**子进程 + stdio 通信**，GUI 和 agent 之间没有
网络端口/CLI 接口可供外部调用（实测无监听端口、无 pi 专用命名管道）。
外部 `pi --mode rpc` 只会另起一个独立引擎，**不是** GUI 管理的那个。

⇒ 结论：**别写"agent 死了自动重生"的守护**。唯一恢复是重开 Pi Desktop。
（Telegram 桥接不同——它是连到**已存在的**活引擎，这个外部可以自动接，见 `telegram.md`。）
