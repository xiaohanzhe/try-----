# -*- coding: utf-8 -*-
"""CRLF 感知的补丁工具：把文件中的 old 文本替换为 new 文本（支持多处 replace_all）。
用法：
    python apply_patch.py <file> <old> <new> [--all]
    python apply_patch.py <file> --list  # 打印行号辅助定位
文本从 stdin 或参数读取（参数用 base64 避免引号问题）。
"""
import sys
import os
import base64


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    if sys.argv[2] == "--list":
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                print(f"{i:5d} | {line.rstrip()}")
        sys.exit(0)

    old_b64 = sys.argv[2]
    new_b64 = sys.argv[3] if len(sys.argv) > 3 else ""
    replace_all = "--all" in sys.argv

    old = base64.b64decode(old_b64).decode("utf-8")
    new = base64.b64decode(new_b64).decode("utf-8")

    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")

    # 归一化比较：把 CRLF 转成 LF 再匹配，写回时按原行尾还原
    norm_text = text.replace("\r\n", "\n")
    norm_old = old.replace("\r\n", "\n")
    norm_new = new.replace("\r\n", "\n")

    if norm_old not in norm_text:
        print(f"ERROR: old text not found in {path}", file=sys.stderr)
        # 打印附近内容帮助定位
        idx = norm_text.find(norm_old[:40])
        if idx >= 0:
            print("...", norm_text[max(0, idx - 60): idx + 200], file=sys.stderr)
        sys.exit(2)

    count = norm_text.count(norm_old) if replace_all else 1
    norm_text = norm_text.replace(norm_old, norm_new) if replace_all else norm_text.replace(norm_old, norm_new, 1)
    if crlf:
        norm_text = norm_text.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(norm_text)
    print(f"OK: {path} replaced {count} occurrence(s)")


if __name__ == "__main__":
    main()
