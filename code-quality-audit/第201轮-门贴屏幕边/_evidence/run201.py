# -*- coding: utf-8 -*-
"""真机验证启动脚本：起 main.py、捕获 stdout 落盘、帧30后短暂停留再 kill。"""
import os
import sys
import io
import time
import subprocess

import psutil

SRC = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src"
PY = r"C:\Python311\python.exe"
OUT = r"D:\_tmp\real201"
LOG = os.path.join(OUT, "app.log")
PROC = os.path.join(OUT, "proc.txt")
READY = os.path.join(OUT, "ready.txt")
DONE = os.path.join(OUT, "done.txt")

FRAME30 = "场景层指令（第30帧）"


def kill_residual():
    killed = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = (p.info.get("cmdline") or [])
        except Exception:
            continue
        if any("main.py" in (c or "") for c in cmd):
            try:
                p.kill()
                killed.append(p.pid)
            except Exception:
                pass
    return killed


def main():
    for d in ("mem", "legacy", "desk"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    # 1) 杀残留
    killed = kill_residual()
    time.sleep(0.5)

    # 2) 隔离环境
    env = os.environ.copy()
    env["RALSEI_MEMORY_DIR"] = os.path.join(OUT, "mem")
    env["RALSEI_LEGACY_MEMORY"] = os.path.join(OUT, "legacy")
    env["RALSEI_DESKTOP"] = os.path.join(OUT, "desk")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # 3) 起进程
    proc = subprocess.Popen(
        [PY, "main.py"],
        cwd=SRC,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    with io.open(PROC, "w", encoding="utf-8", newline="\n") as f:
        f.write("pid=%d\nkilled_before=%s\n" % (proc.pid, killed))

    logf = io.open(LOG, "w", encoding="utf-8", newline="\n")
    frame30_seen = False
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            logf.write(line + "\n")
            logf.flush()
            if FRAME30 in line and not frame30_seen:
                frame30_seen = True
                with io.open(READY, "w", encoding="utf-8", newline="\n") as rf:
                    rf.write("frame30_seen\n")
                # 给截图留窗口
                time.sleep(5)
    finally:
        logf.flush()
        logf.close()
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        with io.open(DONE, "w", encoding="utf-8", newline="\n") as df:
            df.write("frame30_seen=%s\n" % frame30_seen)

    # 4) 复核残留
    leftover = kill_residual()
    with io.open(DONE, "a", encoding="utf-8", newline="\n") as df:
        df.write("leftover_after_kill=%s\n" % leftover)
    print("DONE frame30_seen=%s leftover=%s" % (frame30_seen, leftover))


if __name__ == "__main__":
    main()
