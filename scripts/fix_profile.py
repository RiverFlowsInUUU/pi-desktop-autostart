#!/usr/bin/env python3
"""
fix_profile.py — 修复 Pi Desktop "PI 停止运行 / Pi binary not found" 的根因。

Pi Desktop 启动时用 login shell 找 `pi` 可执行文件。Windows 用户 PATH 里虽有
nodejs/npm，但 login shell 加载的是 .profile，里面常常没把它们加进 PATH，
导致预检失败、GUI 显示"已停止"。

本脚本给 .profile 追加 nodejs 与 npm 全局 bin，保留原有内容。

安全：
  - 改前自动备份到 .profile.bak-<时间戳>
  - 以 utf-8 无 BOM 写入（BOM 会让 bash 把第 1 行当命令，整个文件失效）
  - 幂等：重复运行不会产生重复行

用法：
  python fix_profile.py            # 修复当前用户的 .profile
  python fix_profile.py --check    # 只诊断，不修改
"""

import io
import os
import sys
import shutil
from datetime import datetime

# ---- 按你的系统调整这两个路径（默认值适用于 Git for Windows + 官方 node 安装包）----
NODEJS_BIN = "/c/Program Files/nodejs"
NPM_GLOBAL = "$HOME/AppData/Roaming/npm"

MARKER = "# Added by pi-desktop-autostart skill"


def get_profile_path():
    # 优先 HOME；Windows 上退到 USERPROFILE
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if not home:
        print("ERROR: 找不到 HOME / USERPROFILE 环境变量")
        sys.exit(1)
    return os.path.join(home, ".profile")


def snippet(npm_global):
    return f"""
{MARKER}
# Ensure Node.js and the npm global bin are on PATH for Pi Desktop agent pre-flight.
case ":${{PATH}}:" in
  *":{NODEJS_BIN}":*) ;;
  *) export PATH="{NODEJS_BIN}:$PATH" ;;
esac
case ":${{PATH}}:" in
  *":{npm_global}":*) ;;
  *) export PATH="{npm_global}:$PATH" ;;
esac
"""


def read_text(path):
    if not os.path.exists(path):
        return ""
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    check_only = "--check" in sys.argv
    profile = get_profile_path()
    content = read_text(profile)

    already = MARKER in content

    print(f"[i] .profile: {profile}")

    if already:
        print("[OK] 已包含本 skill 的 PATH 补充，无需修改。")
    elif check_only:
        print("[!] 缺少 nodejs/npm 的 PATH 补充 —— 这正是预检失败的原因。")
        print("    去掉 --check 再运行即可修复。")
        return

    print("\n[i] 诊断复现（GUI 的干净 login shell 视角）：")
    print('    /usr/bin/bash -lc \'echo PATH=$PATH; echo pi=$(command -v pi); echo node=$(command -v node)\'')
    print("    pi= 和 node= 都为空  =>  确认是此问题\n")

    if already or check_only:
        return

    # 备份
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    bak = f"{profile}.bak-{stamp}"
    if os.path.exists(profile):
        shutil.copy2(profile, bak)
        print(f"[OK] 已备份到 {bak}")

    new_content = content.rstrip("\n") + "\n" + snippet(NPM_GLOBAL)
    write_text(profile, new_content)
    print(f"[OK] 已写入 {profile}（utf-8 无 BOM）")

    print("\n[i] 验证：重开一个 login shell 应该能看到 pi / node：")
    print('    /usr/bin/bash -lc \'command -v pi; command -v node\'')
    print("\n[i] 最后一步：完全关闭 Pi Desktop 再重新打开，让 GUI 重跑预检。")


if __name__ == "__main__":
    main()
