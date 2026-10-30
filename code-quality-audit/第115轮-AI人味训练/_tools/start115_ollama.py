# -*- coding: utf-8 -*-
"""
第115轮 · 拉起 Ollama 服务（detached，脱离本会话生命周期）

背景：probe115d 用成对控制定案 —— 11434 不是被沙箱拦，是**服务没在跑**
      （正控制 HTTP_PROXY 的 54715 OPEN；任务表里 ollama 进程 0 条）。
      没有服务 ⇒ 所有对话 A/B 都做不了 ⇒ 必须先拉起来。

做法：subprocess.Popen(creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP)
      ⇒ 子进程不进本 shell 的 job，本会话结束后仍在跑。
      日志落 E:\\Download\\_tmp\\（临时文件绝不放工作区）。

只读之外唯一动作 = 启动本机已安装的 ollama serve；不改任何工程文件。
"""
import io
import os
import socket
import subprocess
import sys
import time

OLLAMA_EXE = r"C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe"
LOG_PATH = r"E:\Download\_tmp\ollama_serve_115.log"
HOST, PORT = "127.0.0.1", 11434

BUF = io.StringIO()


def say(msg):
    print(msg)
    BUF.write(msg + "\n")


def port_open(timeout=0.8):
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout):
            return True
    except OSError:
        return False


def main():
    say("=== 1. 启动前状态 ===")
    say("  exe exists          = %s" % os.path.isfile(OLLAMA_EXE))
    say("  11434 before start  = %s" % ("OPEN" if port_open() else "closed"))

    if port_open():
        say("\n[OK] 服务已在跑，无需重复启动。")
        return 0

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logf = open(LOG_PATH, "ab", buffering=0)

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    say("\n=== 2. 拉起 ollama serve（detached）===")
    try:
        p = subprocess.Popen(
            [OLLAMA_EXE, "serve"],
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
            cwd=r"E:\Download\_tmp",
        )
    except Exception as exc:  # noqa: BLE001
        say("  [FAIL] Popen 抛异常: %r" % (exc,))
        return 2

    say("  pid                 = %s" % p.pid)
    say("  log                 = %s" % LOG_PATH)

    say("\n=== 3. 等待端口就绪（最多 60s）===")
    deadline = time.time() + 60
    waited = 0.0
    ok = False
    while time.time() < deadline:
        if port_open():
            ok = True
            break
        time.sleep(1.0)
        waited += 1.0
        if int(waited) % 5 == 0:
            say("  ... 已等 %ds，端口仍 closed（子进程 poll=%s）" % (int(waited), p.poll()))

    say("  端口 OPEN           = %s（耗时 %.0fs）" % (ok, waited))
    say("  子进程 poll()       = %s（None=仍在跑）" % (p.poll(),))

    say("\n=== 4. 启动日志尾部 ===")
    try:
        with open(LOG_PATH, "rb") as f:
            raw = f.read()
        txt = raw.decode("utf-8", "replace")
        tail = txt.strip().splitlines()[-12:]
        for ln in tail:
            say("  | " + ln.replace("\r", ""))
    except Exception as exc:  # noqa: BLE001
        say("  [WARN] 读日志失败: %r" % (exc,))

    return 0 if ok else 3


if __name__ == "__main__":
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        BUF.write("\n[EXCEPTION] %r\n" % (_exc,))
        BUF.write(traceback.format_exc())
        say("[EXCEPTION] %r" % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        # ★ 铁律：shell stdout 会被吞 ⇒ 结论必须落盘自证；写盘本身也不许再抛
        try:
            out_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(out_dir, "start115_ollama_out.txt"), "w",
                      encoding="utf-8", newline="") as f:
                f.write(BUF.getvalue())
        except BaseException as _e2:  # noqa: BLE001
            pass
    sys.exit(rc)
