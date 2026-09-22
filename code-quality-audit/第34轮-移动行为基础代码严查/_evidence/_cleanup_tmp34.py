# -*- coding: utf-8 -*-
"""清理 E:\\Download\\_tmp 本轮临时件；显式点名，绝不写通配。"""
import os

TMP = r"E:\Download\_tmp"
mine = ["_commit_msg_34.md", "_push_result_34.txt", "_verify_msg_34.txt",
        "_mk_tmp.py", "_probe_tmp.py"]
for f in mine:
    p = os.path.join(TMP, f)
    if os.path.isfile(p):
        os.remove(p)
        print("deleted:", f)
rest = [f for f in os.listdir(TMP)] if os.path.isdir(TMP) else []
print("remaining in _tmp:", rest or "(none)")

# 脚本自身放在 _evidence 下，顺手清掉两个一次性脚本（保留 _push_round34.py 作为流程证据）
ev = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence"
for f in ["_mk_tmp.py", "_verify_msg_34.py"]:
    p = os.path.join(ev, f)
    if os.path.isfile(p):
        os.remove(p)
        print("deleted(ev):", f)
