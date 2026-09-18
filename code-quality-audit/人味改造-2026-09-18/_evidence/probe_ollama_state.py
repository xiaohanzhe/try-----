# -*- coding: utf-8 -*-
"""只读探针：Ollama 现状（已装模型 / 存储位置 / 磁盘余量 / 版本）。

走 REST API（不走 PowerShell 管道 —— 中文元数据经管道会变 GBK 乱码，见 MEMORY 环境铁律 10）。
"""
import io
import json
import os
import shutil
import subprocess
import urllib.request

OUT = r"E:\Download\_tmp\ollama_state.txt"
lines = []


def log(s=""):
    lines.append(str(s))


try:
    d = json.load(urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5))
    models = d.get("models", [])
    log("Ollama 在线，已安装 %d 个模型：" % len(models))
    for m in sorted(models, key=lambda x: -(x.get("size") or 0)):
        det = m.get("details") or {}
        log("  %-24s %7.2f GB   params=%s  quant=%s  family=%s"
            % (m.get("name"), (m.get("size") or 0) / 1024.0 ** 3,
               det.get("parameter_size"), det.get("quantization_level"),
               det.get("family")))
except Exception as e:
    log("!! Ollama REST 取不到: %r" % e)

log()
log("OLLAMA_MODELS 环境变量 = %r" % os.environ.get("OLLAMA_MODELS"))
default_dir = os.path.join(os.path.expanduser("~"), ".ollama", "models")
log("默认模型目录 = %s（存在=%s）" % (default_dir, os.path.isdir(default_dir)))
if os.path.isdir(default_dir):
    tot = 0
    for root, dirs, files in os.walk(default_dir):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    log("  已占用 %.2f GB" % (tot / 1024.0 ** 3))

log()
for drv in ("C:\\", "D:\\", "E:\\"):
    try:
        u = shutil.disk_usage(drv)
        log("磁盘 %s 可用 %.1f GB / 共 %.1f GB" % (drv, u.free / 1024.0 ** 3, u.total / 1024.0 ** 3))
    except Exception as e:
        log("磁盘 %s 读取失败: %r" % (drv, e))

log()
try:
    exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    r = subprocess.run([exe, "--version"], capture_output=True, timeout=15)
    log("ollama --version = %s" % (r.stdout.decode("utf-8", "replace").strip()
                                   or r.stderr.decode("utf-8", "replace").strip()))
except Exception as e:
    log("ollama --version 失败: %r" % e)

io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("WROTE", OUT)
