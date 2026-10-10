# 踩过的坑（Gotchas）

这些是**实测踩到并修好**的坑，不是理论推测。写/改这个 skill 的脚本前先看一遍。

---

## 1. `.profile` 写进 BOM → 整个文件失效

**现象**：文件看起来内容对，但 bash 报
`/c/Users/.../.profile: line 1: $'\357\273\277.': command not found`

**原因**：PowerShell 的 `Out-File`（默认 UTF-8 **带 BOM**）写出的文件，
bash 把开头的 BOM 字节当成一条命令 → 第 1 行就解析失败，后续全部不执行。

**修法**：用 Python 写，显式 `encoding='utf-8', newline='\n'`；
或用 bash heredoc。验证首字节：

```bash
head -c 3 ~/.profile | xxd    # 应是 2e20 22（". "），不是 efbb bf
```

---

## 2. PowerShell 传给 bash 的路径：反斜杠被吃掉

**现象**：`nohup bash "C:\Users\...\start-bridge.sh" > "C:\Users\...\log" 2>&1`
报 `C:Users...log: No such file or directory`

**原因**：`$env:USERPROFILE` 展开后是 `C:\Users\...`，
反斜杠在 **bash 双引号**里被当转义符吃掉 → 变成 `C:Users...`

**修法**：路径一律用 **bash 自己的 `$HOME` + 正斜杠**，并用**单引号**包住
让 PowerShell 不展开：

```powershell
$arg = 'nohup bash "$HOME/.pi/agent/tmp/pi-telegram/start-bridge.sh" > "$HOME/.pi/agent/tmp/pi-telegram/bridge-stdout.log" 2>&1 &'
Start-Process -FilePath $bash -ArgumentList '-c', $arg -WindowStyle Minimized
```

---

## 3. `taskkill /PID $_.ProcessId` → 解析成"数组索引"

**现象**：PowerShell 报错 `数组索引表达式丢失或无效`（行号指向后面，
容易误判成别处的错）

**原因**：`$.` 紧跟在 `/PID ` 后，解析器把 `$_` 当数组索引。

**修法**：包一层子表达式 → `taskkill /PID $($_.ProcessId) /F`

---

## 4. 含 `->` 的字符串 + 空引号 `Write-Host ""` → 连锁报错

**现象**：报 `字符串缺少终止符` / `缺少右"}"`，且**行号失真**
（指向 if 块之外），极难定位。

**原因**：`'...桥接不在 -> 自动接桥接'` 里的 `>` 被当重定向运算符，
打断字符串解析，连锁影响后续括号匹配。

**修法**：
- 去掉字符串里的 `->`（改中文表述，如"时，自动接桥接"）
- 不要用 `Write-Host ""` 这种**裸空字符串**，给点实际内容
- 长文本用字符串拼接：`'  line ' + $n + ': ' + $msg`

---

## 5. 语法校验不能只靠"跑一遍"

`New-Module`/`&` 粗测会**漏报**。装计划任务前务必用 Parser 严格校验：

```powershell
$tokens = $null; $errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) { $errors | Select-Object -First 5 | ForEach-Object {
    '  line ' + $_.Extent.StartLineNumber + ': ' + $_.Message } }
```

`scripts/register_watchdog.ps1` 已内置这一步 —— **语法不过就不给注册**。

---

## 6. `py_compile` 会生成含绝对路径的 `.pyc`

用 `py_compile` 做 Python 语法自检后，会留下 `__pycache__/*.pyc`，
里面**嵌入了本机绝对路径**（含用户名）→ 属于隐私泄露。

**修法**：自检后清理，且 `.gitignore` 里永久屏蔽：

```
__pycache__/
*.pyc
```

---

## 7. `env -i` 测"干净环境"会得到假阴性

`env -i HOME=... bash -lc 'which pi'` → 报 `which: no bash in ((null))`
因为 PATH 被清到连 `bash` 自己都找不到。

**正确模拟**：`/usr/bin/bash -lc '...'`（保留可执行的 bash，让它正常加载 `.profile`）。

---

## 8. 别去翻 `bridge-stdout.log` 全文

它几十 MB 且塞满会话 JSON 历史（会看到旧对话 replay）。
**取尾部短行**即可，见 `telegram.md`。
