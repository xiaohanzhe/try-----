# -*- coding: utf-8 -*-
"""独立验证 desktop_interaction 的三个疑似缺陷"""
import os, sys
import win32com.client, pythoncom
import ctypes
from ctypes import wintypes

print("=== S1: Shell 详细信息列的索引是否用错 ===")
try:
    pythoncom.CoInitialize()
    shell = win32com.client.Dispatch("Shell.Application")
    ns = shell.NameSpace(0)   # 桌面
    items = ns.Items()
    print("桌面条目数:", items.Count)
    print("第15列列名 =", repr(ns.GetDetailsOf(None, 15)), " 第2列列名 =", repr(ns.GetDetailsOf(None, 2)))
    n15, n2, dirs = 0, 0, 0
    for i in range(min(items.Count, 60)):
        it = items.Item(i)
        if it.IsFolder: dirs += 1
        if ns.GetDetailsOf(it, 15) == "文件夹": n15 += 1
        if ns.GetDetailsOf(it, 2) == "文件夹": n2 += 1
    print(f"真实文件夹数={dirs}  用索引15判为文件夹={n15}  用索引2判为文件夹={n2}")
    print("结论:", "索引 15 判据失效（恒为0）" if n15 == 0 and dirs > 0 else "索引15可用")
except Exception as e:
    print("跳过（COM 不可用）:", repr(e))

print()
print("=== S3: SHFileOperation 删除失败是否被静默当成功 ===")
try:
    from win32com.shell import shell, shellcon
    fake = r"C:\__definitely_not_exist_ralsei_test__\nope.txt"
    rc = shell.SHFileOperation((0, shellcon.FO_DELETE, fake, None,
                                shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION,
                                None, None))
    print("对不存在路径的返回值 =", rc, " (0=成功)")
    print("结论:", "不抛异常且 errcode != 0 → 若代码不检查返回值就会误报成功" if rc[0] != 0 else "正常")
except Exception as e:
    print("异常:", repr(e))

print()
print("=== S2: ctypes kernel32 默认 restype 是否截断 64 位地址 ===")
k = ctypes.windll.kernel32
print("VirtualAllocEx.restype =", k.VirtualAllocEx.restype)
print("OpenProcess.restype    =", k.OpenProcess.restype)
print("（64 位下 HANDLE/LPVOID 必须显式设为 c_void_p，否则被当 32 位 long 截断）")
