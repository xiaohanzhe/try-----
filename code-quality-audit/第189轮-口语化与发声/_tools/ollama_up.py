# -*- coding: utf-8 -*-
"""把本机 Ollama 服务拉起来（后台常驻，供夜间训练用）。

为什么要脚本、不直接 `ollama serve &`：
  · Bash 里起的长驻进程会随会话结束被带走（项目铁律：不许 nohup/setsid）；
  · 本机实测 `ollama.exe` 必须 `DETACHED_PROCESS` 才不会被父进程回收；
  · 需要一个**可复算的就绪判据**（`/api/tags` 真返回 JSON），而不是"看起来起好了"。

用法：
    python ollama_up.py            # 需要时启动，已就绪则直接返回
    python ollama_up.py --check    # 只检查，不启动
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EXE = r'C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe'
LOG = r'D:\_tmp189\ollama_serve.log'
URL = 'http://127.0.0.1:11434/api/tags'


def tags(timeout=3):
    try:
        with urllib.request.urlopen(URL, timeout=timeout) as fh:
            return json.loads(fh.read().decode('utf-8'))
    except Exception:  # noqa: BLE001
        return None


def main():
    check_only = '--check' in sys.argv
    d = tags()
    if d:
        print('已就绪：%d 个模型' % len(d.get('models') or []))
        return 0
    if check_only:
        print('未就绪（--check 不启动）')
        return 1

    if not os.path.isfile(EXE):
        print('[失败] 找不到 %s' % EXE)
        return 2
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    flags = 0
    if os.name == 'nt':
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        flags = 0x00000008 | 0x00000200 | 0x08000000
    fh = open(LOG, 'ab')
    p = subprocess.Popen([EXE, 'serve'], stdout=fh, stderr=fh,
                         stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    print('已拉起 ollama serve pid=%d（日志 %s）' % (p.pid, LOG))

    for i in range(60):
        time.sleep(2)
        d = tags()
        if d:
            print('就绪，用时 %ds：%d 个模型' % ((i + 1) * 2, len(d.get('models') or [])))
            return 0
    print('[失败] 120s 内没等到 /api/tags')
    return 3


if __name__ == '__main__':
    sys.exit(main())
