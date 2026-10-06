#!/usr/bin/env python3
"""只读检查器：核对手机上的同文配置，并报告部署状态。

**不做任何写入。**

为什么只读：标点映射、开关状态名、simplifier 配置这些改动，都是写在
`<schema>.custom.yaml` 里、由 Rime 在运行时自动应用的
（`Config::Open` 会去读 `<config_id>.custom.yaml`）。所以手机上不需要、
也不应该去手改 `build/` 产物。

> 历史教训：这里原本有个 `fix_punctuator.py`，它会直接改手机上的
> `build/luna_pinyin*.schema.yaml`。那是错的设计——既多余（custom 文件已经覆盖），
> 又会留下过期的 `__build_info` 让部署器误判「没变化」而跳过重建。
> 已经删掉了，别再走那条路。

用法：
    python3 check.py            # 全量检查
    python3 check.py --quiet    # 只输出不一致的项，适合放进 deploy.sh
"""

import filecmp
import os
import subprocess
import sys
import tempfile

RIME = "/sdcard/Android/data/com.osfans.trime/files/rime"
FILES = [
    "trime.custom.yaml",
    "default.custom.yaml",
    "luna_pinyin.custom.yaml",
    "luna_pinyin_simp.custom.yaml",
]


def adb(*args, check=True):
    r = subprocess.run(["adb", *args], capture_output=True)
    if check and r.returncode != 0:
        raise SystemExit("adb 命令失败: adb %s\n%s" % (" ".join(args), r.stderr.decode(errors="replace")))
    return r.stdout.decode(errors="replace")


def main():
    quiet = "--quiet" in sys.argv
    src = os.path.dirname(os.path.abspath(__file__))
    problems = []

    if adb("get-state", check=False).strip() != "device":
        raise SystemExit("设备未就绪（unauthorized 或未插线）")

    # ---- ① 四个配置文件：手机 vs 本地，逐字节比对 ----------------------
    if not quiet:
        print("① 配置文件同步状态")
        print("   %-30s %9s %9s  %s" % ("文件", "本地", "手机", "一致"))
    with tempfile.TemporaryDirectory() as tmp:
        for name in FILES:
            local = os.path.join(src, name)
            remote_tmp = os.path.join(tmp, name)
            r = subprocess.run(["adb", "pull", "%s/%s" % (RIME, name), remote_tmp], capture_output=True)
            ok = r.returncode == 0 and os.path.exists(remote_tmp)
            same = ok and filecmp.cmp(local, remote_tmp, shallow=False)
            lsize = os.path.getsize(local)
            rsize = os.path.getsize(remote_tmp) if ok else -1
            if not same:
                problems.append(name)
            if not quiet:
                print("   %-30s %9d %9d  %s" % (name, lsize, rsize, "✓" if same else "✗ 不一致"))

    # ---- ② 部署状态（信息性，不算错）-----------------------------------
    if not quiet:
        print("\n② 部署产物时间戳")
        out = adb("shell", "ls", "-la", "%s/build/" % RIME, check=False)
        for line in out.splitlines():
            if any(k in line for k in ("trime.yaml", "default.yaml", "schema.yaml", "prism.bin")):
                parts = line.split()
                if len(parts) >= 8:
                    print("   %-34s %s %s" % (parts[-1].split("/")[-1], parts[5], parts[6]))

        print("\n③ 生效中的方案列表（来自 build/default.yaml）")
        out = adb("shell", "sed", "-n", "/^schema_list:/,/^[a-z]/p", "%s/build/default.yaml" % RIME, check=False)
        for line in out.splitlines():
            if "schema:" in line:
                print("   " + line.strip())

    # ---- ④ schema 级修正是否写在 custom 文件里 -------------------------
    needed = {
        "luna_pinyin.custom.yaml": ["simplifier/opencc_config", "punctuator/full_shape/_"],
        "luna_pinyin_simp.custom.yaml": ["simplifier/opencc_config", "punctuator/full_shape/_"],
    }
    if not quiet:
        print("\n④ schema 级修正（写在 custom 文件里，运行时生效）")
    for name, keys in needed.items():
        text = open(os.path.join(src, name)).read()
        for k in keys:
            if k not in text:
                problems.append("%s 缺少 %s" % (name, k))
                if not quiet:
                    print("   ✗ %s 缺少 %s" % (name, k))
        if not quiet:
            print("   %-30s %s" % (name, "✓" if all(k in text for k in keys) else "✗"))

    # ---- 结论 ----------------------------------------------------------
    print()
    if problems:
        print("✗ 有问题：")
        for p in problems:
            print("   -", p)
        print("\n提示：改完本地文件后跑 ./deploy.sh 推送；")
        print("      手机上仍需点一次 ↻（部署）或切一下方案，让 Rime 重新载入。")
        sys.exit(1)
    print("✓ 配置已同步，schema 级修正齐备。")


if __name__ == "__main__":
    main()
