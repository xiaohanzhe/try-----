# -*- coding: utf-8 -*-
"""最终清理本轮临时件（E:\\Download\\_tmp）—— 显式点名，绝不写通配。"""
import os

TMP = r"E:\Download\_tmp"
mine = ["_commit_msg_34.md", "_push_result_34.txt", "_verify_msg_34.txt",
        "_commit_msg_34b.md", "_push_result_34b.txt",
        "_commit_msg_34c.md", "_push_result_34c.txt",
        "_log_append_34c.md", "_log_append_result.txt"]
for f in mine:
    p = os.path.join(TMP, f)
    if os.path.isfile(p):
        os.remove(p)
        print("deleted:", f)

rest = sorted(f for f in os.listdir(TMP)) if os.path.isdir(TMP) else []
print("\nremaining count =", len(rest))
print("remaining (first 60):")
for f in rest[:60]:
    print("  ", f)
