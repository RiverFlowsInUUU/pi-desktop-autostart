# Telegram 桥接

按需查阅。桥接是**可选**的；要不要接由用户决定。

---

## 机制

桥接脚本：`~/.pi/agent/tmp/pi-telegram/start-bridge.sh`

```sh
#!/usr/bin/env bash
cd "/c/Users/<用户名>/Documents/pi"
{
  printf '%s\n' '{"id":"connect","type":"prompt","message":"/telegram-connect"}'
  sleep 86400
} | pi --mode rpc
```

即：把一条 `/telegram-connect` 通过 **stdin** 喂给 `pi --mode rpc`，
从而连上**已经在跑的** agent 引擎，之后接管 Telegram 长轮询。

### 前提

**必须先有一个活的 agent 在跑。** 没有活引擎，桥接连不上——
这正是 `PiTelegramWatchdog.ps1` 要先判断 `$agent` 存在的原因。

---

## 成功判据

```
~/.pi/agent/tmp/pi-telegram/bridge-stdout.log
末尾出现：  "telegram" … "connected"
```

也可看 `~/.pi/agent/tmp/pi-telegram/state.json` 里的
`pollingActive` / `lastSuccessfulResponseAtMs`。

---

## ⚠️ 那个日志会涨到几十 MB

`bridge-stdout.log` 里塞了完整会话 JSON（实测 58 MB+）。**别直接 `cat`**，
会刷屏且拖慢。取尾部短行：

```powershell
Get-Content bridge-stdout.log -Tail 15 | Where-Object { $_.Length -lt 260 }
```

---

## 开关联动（要不要自动接）

新 agent 每次都是新 PID，桥接不会自动跟随 —— 所以装守护：

```
agent 在跑 且 桥接不在  ->  自动跑 start-bridge.sh
agent 不在             ->  不动作（等用户重开 Pi Desktop）
```

注册：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_watchdog.ps1
schtasks /Run /TN PiTelegramWatchdog    # 立即生效
```

卸载：`-Uninstall`。查看：`-Status`。

---

## 隐私红线（写脚本时务必遵守）

`~/.pi/agent/telegram.json` 含：

- `botToken`
- `botId`
- `allowedUserId`
- `botUsername`

**这些值不得出现在任何脚本、命令行、日志、文档里。**
桥接脚本自己去读那份 JSON，你只需要调用它 —— **token 不需要你传**。

本仓库所有文件均不含上述任何值；路径全部占位符化。
