#!/usr/bin/env bash
# 推送同文配置到手机，并先备份手机上的旧文件。
set -euo pipefail

RIME_DIR=/sdcard/Android/data/com.osfans.trime/files/rime
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BK="$SRC/backup/$STAMP"

adb wait-for-device
[ "$(adb get-state)" = device ] || { echo "设备未就绪（unauthorized？）"; exit 1; }

mkdir -p "$BK"
FILES="trime.custom.yaml default.custom.yaml luna_pinyin.custom.yaml luna_pinyin_simp.custom.yaml"
for f in $FILES; do
    if adb shell "[ -f $RIME_DIR/$f ]"; then
        adb pull "$RIME_DIR/$f" "$BK/$f" >/dev/null
        echo "备份 $f -> backup/$STAMP/$f"
    else
        echo "（手机上还没有 $f，跳过备份）"
    fi
done

for f in $FILES; do
    adb push "$SRC/$f" "$RIME_DIR/$f"
done

echo
echo "推送完成，核对一遍："
python3 "$SRC/check.py" --quiet || true

echo
echo "现在去手机上操作："
echo "  1. 打开同文 App -> 主题 -> 选中「預設」"
echo "  2. 同文 App 右上角 -> ↻ 圆形箭头（Deploy / 部署）"
