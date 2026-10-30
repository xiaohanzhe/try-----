# -*- coding: utf-8 -*-
u"""live116_sandbox.py —— 端到端：**真跑一次录屏**，再用外部尺子量用户记忆库。

为什么不能只靠 `check116.py`
----------------------------
  `check116` 只验"闸门在源码里**真的赋了值**"（AST 层）。但**赋了值 ≠ 拦住了**：
  本轮最初就是"看着设了闸、照样写了 `E:\\RalseiMemory\\memory.json`"。
  ⇒ 必须真机跑一次、用**独立的**指纹尺子量。

★★★ 防"恒真"的两道锁（这是本脚本的要害）
----------------------------------------
  如果脚本根本没跑起来（崩了 / 没起窗 / 没写盘），用户记忆库**自然**也不会变
  —— 那样"一致 ✓"就是**假绿**（什么都没发生，却被当成"沙箱有效"）。
  ⇒ 因此判 PASS 必须**同时**满足：
     ① 子进程 `rc == 0`；
     ② 它**真录到了**帧（`frames >= 10`）且**真落了**关键帧 PNG（`keypng >= 1`）；
     ③ 用户记忆库指纹**逐字节一致**（`added/removed/changed` 全空）。
     三条缺一即 FAIL。

用法
----
  C:\\Python311\\python.exe code-quality-audit\\第116轮-退出期崩溃定位与沙箱补漏\\_tools\\live116_sandbox.py
  （`--secs 12` 可调；默认 12 s —— 够跑满一条 tick 链路，又不拖长）
"""
import io
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CQA = os.path.join(ROOT, 'code-quality-audit')
EV = os.path.join(ROUND, '_evidence')
DIAG = os.path.join(CQA, '第96轮-用户视角录制复核', '_tools', 'diag96_exit.py')
PY = sys.executable

SECS = 12
if '--secs' in sys.argv:
    SECS = int(sys.argv[sys.argv.index('--secs') + 1])

sys.path.insert(0, os.path.join(CQA, '_shared'))
import vault_guard as vg                                      # noqa: E402

ok = fail = 0
_NAMES = []


def check(name, cond, detail=None):
    global ok, fail
    _NAMES.append(name)
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


print(u'=== live116 · 端到端沙箱实测（secs=%d）===' % SECS)
print(u'  记忆库 = %s' % vg.DEFAULT_ROOT)

# ---- 1) 跑前拍指纹 ----
before = vg.snapshot()
if before is None:
    print('★ 记忆库根不存在 ⇒ 无法比对，本次如实报 FAIL')
    check(u'L0 记忆库根存在且可拍指纹', False)
    sys.exit(1)
check(u'L0 记忆库根存在且可拍指纹', len(before) > 0,
      detail=u'%d 个文件' % len(before))

# ---- 2) 真跑一次（开着沙箱）----
env = dict(os.environ)
env['DIAG96_MODE'] = 'full'
env['DIAG96_SECS'] = str(SECS)
env['DIAG96_SANDBOX'] = '1'
env['PYTHONFAULTHANDLER'] = '1'
t0 = time.time()
p = subprocess.run([PY, DIAG], cwd=ROOT, env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                   timeout=max(120, SECS * 6))
wall = round(time.time() - t0, 1)
out = p.stdout.decode('utf-8', 'replace')
rc = p.returncode

# ★ 防恒真第 ①、② 条：它必须**真的跑成了、真的录到了**
m_fr = re.search(r'STEP-1 exec returned rc=(\d+)\s+frames=(\d+)\s+keypng=(\d+)', out)
frames = int(m_fr.group(2)) if m_fr else -1
keypng = int(m_fr.group(3)) if m_fr else -1
print(u'  子进程 rc=%s 墙钟=%.1fs  frames=%d  keypng=%d'
      % (rc, wall, frames, keypng))
for l in out.splitlines():
    if l.startswith('[diag96]') or 'Windows fatal' in l:
        print(u'      | %s' % l[:160])

check(u'L1 子进程正常收尾（rc=0，不是崩了/没跑起来）', rc == 0,
      detail=u'rc=%s' % rc)
check(u'L2 它**真的录到了**帧（frames>=10，否则"没变"是假绿）', frames >= 10,
      detail=u'frames=%d' % frames)
check(u'L3 它**真的落了**关键帧 PNG（keypng>=1）', keypng >= 1,
      detail=u'keypng=%d' % keypng)
check(u'L4 沙箱自证：记忆目录落在临时区（不是 E:\\RalseiMemory）',
      (u'memory_store.default_memory_dir()' in out)
      and (r'E:\RalseiMemory' not in
           out.split(u'memory_store.default_memory_dir()')[1].split('\n')[0]),
      detail=u'见上方 [diag96] 行')

# ---- 3) 跑后比对指纹 ----
after = vg.snapshot()
added, removed, changed = vg.compare(before, after)
_total = len(added) + len(removed) + len(changed)
print(u'\n[vault_guard] before=%d after=%d 差异=%d'
      % (len(before), len(after or {}), _total))
for k in added[:20]:
    print(u'   + 新增 %s' % k)
for k in removed[:20]:
    print(u'   - 消失 %s' % k)
for k, _o, _n in changed[:20]:
    print(u'   ~ 变化 %s' % k)

check(u'L5 ★ 用户记忆库**逐字节一致**（沙箱真的拦住了）', _total == 0,
      detail=u'+%d -%d ~%d' % (len(added), len(removed), len(changed)))

print(u'\n合计 PASS=%d FAIL=%d（共 %d 条）' % (ok, fail, ok + fail))
try:
    with io.open(os.path.join(EV, 'LIVE116.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'live116_sandbox  rc=%s frames=%d keypng=%d 差异=%d\n'
                 % (rc, frames, keypng, _total))
        fh.write(u'PASS=%d FAIL=%d\n' % (ok, fail))
        fh.write(u'--- 子进程输出 ---\n')
        fh.write(out)
except Exception as e:
    print(u'写 LIVE116.txt 失败: %r' % (e,))
sys.exit(1 if fail else 0)
