# -*- coding: utf-8 -*-
"""第 35 轮 —— 真机连续 10 分钟「用户视角」行为采集器。

设计原则（对应本项目铁律「不要只凭印象下结论」）：
    采样必须落成**可复核的数据**，再据此判读「动作是否合理」。
    因此本脚本只做两件事：
      ① 每 2 秒抓一次宠物窗口的真实几何 / 状态（经 win32gui 枚举，不依赖宠物内部 API）
      ② 增量读取产品自己的日志（E:\\RalseiMemory\\logs\\ralsei_pet.log）

    全部原始数据逐行写 UTF-8 文件，**不做任何过滤或解释** —— 解释留给报告。
    这样即使我判读有误，用户也能拿原始数据反推。

用法：
    C:\\Python311\\python.exe monitor_10min.py [分钟数，默认 10]
"""
import os
import sys
import time
import json
import traceback

import win32gui
import win32process
import psutil

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
LOG = r"E:\RalseiMemory\logs\ralsei_pet.log"

SAMPLE_SEC = 2
DURATION_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0


def find_pet_pids():
    """找出还在跑的宠物进程（按 cmdline 含 src/main.py 判定）。"""
    pids = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
            if "main.py" in cl and "src" in cl.replace("\\", "/"):
                pids.append(p.info["pid"])
        except Exception:
            pass
    return pids


def enum_pet_windows(pids):
    """枚举属于宠物进程的全部顶层窗口，取真实几何。

    这是「用户视角」的核心：用户看到的就是这个矩形。
    """
    out = []

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid not in pids:
                return
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            out.append({
                "hwnd": hwnd,
                "pid": pid,
                "title": win32gui.GetWindowText(hwnd),
                "cls": win32gui.GetClassName(hwnd),
                "rect": [l, t, r, b],
                "w": r - l,
                "h": b - t,
                "exstyle": win32gui.GetWindowLong(hwnd, -20),
                "style": win32gui.GetWindowLong(hwnd, -16),
            })
        except Exception:
            pass

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return out


def read_log_delta(pos):
    """从 pos 字节偏移读取日志增量，返回 (文本, 新偏移)。"""
    if not os.path.exists(LOG):
        return "", pos
    size = os.path.getsize(LOG)
    if size < pos:            # 被切割/重置
        pos = 0
    if size == pos:
        return "", pos
    with open(LOG, "rb") as f:
        f.seek(pos)
        data = f.read()
    return data.decode("utf-8", "replace"), size


def main():
    os.makedirs(EV, exist_ok=True)
    samples_path = os.path.join(EV, "10min_窗口采样.jsonl")
    log_path = os.path.join(EV, "10min_日志增量.txt")
    summary_path = os.path.join(EV, "10min_采集摘要.txt")

    t0 = time.time()
    log_pos = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    n_samples = 0
    n_log_lines = 0
    rect_changes = 0
    prev_signature = None
    pet_died = False

    with open(samples_path, "w", encoding="utf-8") as fs, \
         open(log_path, "w", encoding="utf-8") as fl:

        while time.time() - t0 < DURATION_MIN * 60:
            elapsed = round(time.time() - t0, 1)
            pids = find_pet_pids()
            if not pids:
                pet_died = True
                fs.write(json.dumps({
                    "t": round(time.time(), 3), "elapsed": elapsed,
                    "event": "PET_PROCESS_GONE",
                }, ensure_ascii=False) + "\n")
                break

            wins = enum_pet_windows(pids)
            rec = {
                "t": round(time.time(), 3),
                "elapsed": elapsed,
                "procs": pids,
                "windows": wins,
            }
            fs.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fs.flush()
            n_samples += 1

            sig = tuple((w["hwnd"], tuple(w["rect"])) for w in wins)
            if prev_signature is not None and sig != prev_signature:
                rect_changes += 1
            prev_signature = sig

            chunk, newpos = read_log_delta(log_pos)
            if chunk:
                log_pos = newpos
                for line in chunk.splitlines():
                    if line.strip():
                        fl.write(f"[+{elapsed:7.1f}s] {line}\n")
                        n_log_lines += 1
                fl.flush()

            time.sleep(SAMPLE_SEC)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("第35轮 真机用户视角 10 分钟监测 —— 采集摘要\n")
        f.write("=" * 60 + "\n")
        f.write(f"计划时长      : {DURATION_MIN} 分钟\n")
        f.write(f"实际时长      : {round((time.time()-t0)/60, 2)} 分钟\n")
        f.write(f"采样条数      : {n_samples}  (每 {SAMPLE_SEC}s 一条)\n")
        f.write(f"窗口几何变化  : {rect_changes} 次\n")
        f.write(f"日志增量行数  : {n_log_lines}\n")
        f.write(f"宠物中途退出  : {pet_died}\n")
        f.write(f"采样文件      : {samples_path}\n")
        f.write(f"日志文件      : {log_path}\n")

    print("DONE samples=%d loglines=%d rectchanges=%d pet_died=%s" %
          (n_samples, n_log_lines, rect_changes, pet_died))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open(os.path.join(EV, "10min_采集崩溃.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
