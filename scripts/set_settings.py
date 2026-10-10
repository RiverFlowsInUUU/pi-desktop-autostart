#!/usr/bin/env python3
"""
set_settings.py — 让 Pi Desktop 打开后直接进工作区，从而自动 spawn agent。

改 openToHomeOnLaunch 为 false：
  true (默认) -> 打开停在主页 launcher，没选定工作区 => 不 spawn agent，
                体感就是"必须发一条消息才启动"
  false       -> 打开直接进工作区，配合 resumeLastSession => 实测 agent 自动spawn

改前自动备份 settings.json 到 settings.json.bak-<时间戳>。

用法：
  python set_settings.py              # 改为 false（打开即进工作区）
  python set_settings.py --revert     # 改回 true（恢复主页 launcher）
  python set_settings.py --path <file># 指定 settings.json 路径

注意：改完必须完全关闭 Pi Desktop 再重新打开才生效。
"""

import io
import json
import os
import shutil
import sys
from datetime import datetime


def default_settings_path():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("ERROR: 找不到 APPDATA 环境变量（本 skill 面向 Windows 上的 Pi Desktop）")
        sys.exit(1)
    return os.path.join(appdata, "pi-desktop", "settings.json")


def backup(path):
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak-{stamp}"
    shutil.copy2(path, bak)
    print(f"[OK] 已备份 {os.path.basename(path)} -> {os.path.basename(bak)}")
    return bak


def load(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    revert = "--revert" in sys.argv
    path = default_settings_path()
    if "--path" in sys.argv:
        i = sys.argv.index("--path")
        if i + 1 < len(sys.argv):
            path = sys.argv[i + 1]

    if not os.path.exists(path):
        print(f"ERROR: 配置文件不存在: {path}")
        print("Pi Desktop 至少启动过一次才会生成它。")
        sys.exit(1)

    target_value = True if revert else False
    verb = "恢复主页 launcher" if revert else "打开即进工作区"

    data = load(path)
    old = data.get("openToHomeOnLaunch")

    if old == target_value:
        print(f"[OK] openToHomeOnLaunch 已经是 {target_value}，无需修改。")
    else:
        backup(path)
        data["openToHomeOnLaunch"] = target_value
        # resumeLastSession 保持 true，让打开时续上次会话
        if data.get("resumeLastSession") is False:
            print("[i] resumeLastSession 为 false，建议改为 true 以便自动续会话")
            data["resumeLastSession"] = True
        save(path, data)
        print(f"[OK] openToHomeOnLaunch: {old} -> {target_value}  ({verb})")

    print("\n[i] 当前关键字段：")
    print(f"    openToHomeOnLaunch = {data.get('openToHomeOnLaunch')}")
    print(f"    resumeLastSession  = {data.get('resumeLastSession')}")

    print("\n[i] 验收（必须重开 Pi Desktop 后再看）：")
    print("    Get-CimInstance Win32_Process | Where-Object {")
    print("      $_.Name -eq 'node.exe' -and $_.CommandLine -match 'pi-coding-agent' }")
    print("    有输出 => agent 自动起来了；仍然没有 => 再重开一次，或查 app-log.jsonl")


if __name__ == "__main__":
    main()
