#!/usr/bin/env python3
"""
直接修补手机上已部署的 schema 产物，让标点映射立刻生效（不需要等部署）。

背景：
  Rime 的标点表在每个 schema 文件里。要改它只有两条路：
    1. 放 <schema>.custom.yaml 到用户目录，部署时由 Rime 合并 —— 但需要一次
       "完整部署"（fullCheck=true）才会重建 schema；只点「更新配置」不会。
    2. 直接改已部署的 build/<schema>.schema.yaml。
  两条路都做，效果一致：custom 文件保证以后每次完整部署都是对的，
  直接改产物保证现在立刻生效。

用法：
    python3 fix_punctuator.py            # 改手机上的 build 产物
    python3 fix_punctuator.py --check    # 只看命中多少处

处理两件事：
  1. punctuator/full_shape 和 half_shape 里 20 个 ASCII 符号 → {commit: 原字符}。
     符号集合见下面 SYMS（@ # $ % & - _ + = * ( ) ' " | \\ / ? ; :）。
     刻意不含 . 和 , —— 主键盘「。，」键点击出 。 正靠标点表把 . 转过去
  2. switches 里「简繁切换」那项的 states → ["繁体", "简体"]
"""
import subprocess
import sys

RIME = "/sdcard/Android/data/com.osfans.trime/files/rime"
SCHEMAS = ["luna_pinyin", "luna_pinyin_simp"]
SYMS = ['@', '#', '$', '%', '&', '-', '_', '+', '=',
        '*', '(', ')', "'", '"', '|', '\\',
        '/', '?', ';', ':']      # 后四个是数字面板/主键盘新用到的


def _q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


# YAML 里这些键/值多半需要引号（@ # % & * ' " \ ? : 等都是 YAML 的保留指示符），
# 统一用双引号 + 转义最稳。
QUOTE = {c: _q(c) for c in SYMS}
VALUE = {c: _q(c) for c in SYMS}


def sh(*args, check=True):
    r = subprocess.run(args, capture_output=True)
    if check and r.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(args)}\n{r.stderr.decode(errors='replace')}")
    return r.stdout.decode(errors="replace")


def read_key(line):
    """从 '    KEY: rest' 里取出 KEY（去掉 YAML 引号）"""
    body = line[4:]
    if body.startswith('"'):
        out = []
        i = 1
        while i < len(body):
            c = body[i]
            if c == "\\" and i + 1 < len(body):
                nxt = body[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                i += 2
                continue
            if c == '"':
                break
            out.append(c)
            i += 1
        return "".join(out)
    return body.split(":", 1)[0].strip()


def fix(text):
    lines = text.split("\n")
    out, inside, n = [], False, 0
    for line in lines:
        if not line.startswith(" ") and line.endswith(":"):
            inside = line.rstrip() == "punctuator:"
        if inside and line.startswith("    ") and ":" in line:
            key = read_key(line)
            if key in QUOTE:
                new = "    %s: {commit: %s}" % (QUOTE[key], VALUE[key])
                if new != line:
                    n += 1
                out.append(new)
                continue
        out.append(line)
    return "\n".join(out), n


def fix_switches(text):
    """把方案选单里「简繁切换」那一项的状态名改成简体。

    预设是 states: ["漢字", "汉字"]，两边转简体后会同名，失去区分，
    所以手动给一对 ["繁体", "简体"]。第 2 个 switch（下标 2）就是它，
    luna_pinyin 里叫 simplification，luna_pinyin_simp 里叫 zh_simp。
    """
    lines = text.split("\n")
    out, inside, n, want = [], False, 0, False
    for line in lines:
        if not line.startswith(" ") and line.endswith(":"):
            inside = line.rstrip() == "switches:"
        if inside and line.startswith("  - name: "):
            want = line.split(":", 1)[1].strip() in ("simplification", "zh_simp")
        if inside and want and line.startswith("    states:"):
            new = '    states: ["繁体", "简体"]'
            if new != line:
                n += 1
            out.append(new)
            want = False
            continue
        out.append(line)
    return "\n".join(out), n


def main():
    check_only = "--check" in sys.argv
    for schema in SCHEMAS:
        remote = f"{RIME}/build/{schema}.schema.yaml"
        text = sh("adb", "shell", "cat", remote)
        fixed, n = fix(text)
        fixed2, n2 = fix_switches(fixed)
        print(f"--- {schema}: 标点映射命中 {n} 处，开关状态名命中 {n2} 处")
        if n == 0 and n2 == 0:
            print("    （没有命中，可能已经改过）")
            continue
        if check_only:
            continue
        open(f"/tmp/{schema}.schema.yaml", "w").write(fixed2)
        sh("adb", "push", f"/tmp/{schema}.schema.yaml", remote)
        print(f"    已写回 {remote}")
    if not check_only:
        print("\n完成。手机上：切一下方案（或重启输入法）让它重新加载 schema。")


if __name__ == "__main__":
    main()
