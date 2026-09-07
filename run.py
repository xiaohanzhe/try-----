#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ralsei 桌面宠物 - 总启动脚本
用法：python run.py
"""
import sys
import os
import subprocess

# 项目根目录（本脚本所在目录）
ROOT = os.path.dirname(os.path.abspath(__file__))
# 源码目录
SRC_DIR = os.path.join(ROOT, "ralsei_pet", "src")
MODULES_DIR = os.path.join(ROOT, "ralsei_pet", "modules")

# 需要的第三方依赖
REQUIRED = {
    "PyQt5": "PyQt5",
    "win32event": "pywin32",
    "requests": "requests",
    "psutil": "psutil",
}


def check_and_install_deps():
    """检查依赖是否安装，缺失的自动 pip install"""
    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"缺少依赖: {', '.join(missing)}，正在自动安装...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing
            )
        except Exception as e:
            print(f"依赖安装失败: {e}")
            print("请手动执行以下命令安装依赖后重试：")
            print(f"  {sys.executable} -m pip install {' '.join(missing)}")
            input("按回车键退出...")
            sys.exit(1)
        # 修复：安装完成后复检，防止"装了一半/被策略拦截"仍继续运行
        still_missing = []
        for mod, pkg in REQUIRED.items():
            try:
                __import__(mod)
            except ImportError:
                still_missing.append(pkg)
        if still_missing:
            print(f"以下依赖仍不可用: {', '.join(still_missing)}，请手动安装后重试。")
            input("按回车键退出...")
            sys.exit(1)
        print("依赖安装完成。")
    else:
        print("依赖检查通过。")


def main():
    old_cwd = os.getcwd()
    # 1. 检查依赖
    check_and_install_deps()

    # 2. 把源码目录加入 sys.path，保证 import 能找到 modules
    for p in (SRC_DIR, MODULES_DIR, os.path.join(ROOT, "ralsei_pet")):
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        # 3. 切换工作目录到 ralsei_pet（与 README/旧教程一致，让相对路径脚本行为可预期）
        os.chdir(os.path.join(ROOT, "ralsei_pet"))

        # 4. 启动主程序（用 runpy 以 __main__ 方式执行，保证 if __name__=="__main__" 块运行）
        print("正在启动 Ralsei 桌面宠物...")
        import runpy
        runpy.run_path(os.path.join(SRC_DIR, "main.py"), run_name="__main__")
    finally:
        # 修复：无论启动成功失败都恢复工作目录，避免在 REPL/被调用场景下污染 cwd
        try:
            os.chdir(old_cwd)
        except Exception:
            pass


if __name__ == "__main__":
    main()
