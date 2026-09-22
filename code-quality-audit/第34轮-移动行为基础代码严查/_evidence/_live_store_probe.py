# -*- coding: utf-8 -*-
"""真机验证：启动桌宠 40s，抓 .log 文件里的 Traceback/ERROR/Logging error。"""
import os, subprocess, time, sys, signal

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(REPO, "ralsei_pet")
PY = r"C:\Python311\python.exe"
OUTDIR = os.path.join(REPO, "code-quality-audit", "第34轮-移动行为基础代码严查", "_evidence")
LOG = os.path.join(OUTDIR, "_live_store_run.log")

# 先找到日志落在哪（data_store 决定的）
sys.path.insert(0, os.path.join(PET, "modules"))
import data_store
d = data_store.artifact_path('logs', ensure_dir=False)
logfile = os.path.join(d, "ralsei_pet.log")
before = os.path.getsize(logfile) if os.path.exists(logfile) else 0

proc = subprocess.Popen([PY, "src/main.py"], cwd=PET,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
t0 = time.time()
secs = 40
peak_rss = 0
try:
    import psutil
    ps = psutil.Process(proc.pid)
except Exception:
    ps = None
while time.time() - t0 < secs:
    if proc.poll() is not None:
        break
    if ps:
        try:
            peak_rss = max(peak_rss, ps.memory_info().rss)
        except Exception:
            pass
    time.sleep(1)

alive = proc.poll() is None
if alive:
    try:
        proc.terminate(); proc.wait(timeout=10)
    except Exception:
        try: proc.kill()
        except Exception: pass

lines = []
lines.append("真机验证（第34轮 task#13 存储/配置层修复后）")
lines.append("存活=%s  时长=%.1fs  峰值RSS=%.1fMB" % (alive, time.time() - t0, peak_rss / 1048576.0))
lines.append("日志文件=%s" % logfile)

# 抓日志新增段
seg = ""
if os.path.exists(logfile):
    with open(logfile, "rb") as f:
        f.seek(min(before, os.path.getsize(logfile)))
        seg = f.read().decode("utf-8", "replace")
lines.append("新增日志 %d 字节" % len(seg))
bad = [l for l in seg.splitlines()
       if ("Traceback" in l) or (" ERROR " in l) or ("Logging error" in l) or ("CRITICAL" in l)]
lines.append("问题行数 = %d" % len(bad))
for l in bad[:40]:
    lines.append("  !! " + l[:300])

# 也看进程 stdout
try:
    out = proc.stdout.read().decode("utf-8", "replace")
except Exception:
    out = ""
so_bad = [l for l in out.splitlines()
          if ("Traceback" in l) or ("Logging error" in l) or ("ERROR" in l)]
lines.append("stdout 问题行数 = %d" % len(so_bad))
for l in so_bad[:20]:
    lines.append("  !! " + l[:300])

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
