# -*- coding: utf-8 -*-
"""时钟注入器自检：**先证明探针本身是真的**，再去测套件。

为什么必须自检（2026-10-01 实测教训）
------------------------------------
v1 的注入器把 `time.localtime` 换成了普通函数 ⇒ 被 `logging` 当成描述符绑定
⇒ `Formatter.formatTime` 抛 TypeError ⇒ `handleError` 静默吞掉 ⇒ **日志全灭**。
当时直接拿它去测套件，得到的结论是"7 个套件依赖时钟" —— **全是假问题**。
所以：探针本身也要有 A/B 锚点，跑之前先自检。

A/B 锚点：
  A1 平移量正确（与**独立子进程**的真实时钟比对，不是自己跟自己比）
  A2 `logging.Formatter.converter(record.created)` **不抛**（v1 就是死在这条）
  A3 真发一条 INFO 能落到流上（探针没把日志打死）
  A4 datetime.now() 跟着平移
  A5 **刻意不动**的两个：perf_counter / monotonic 计的是耗时，不是绝对时刻
  A6 局限②如实成立：新写文件 mtime ≈ 真实时钟（**没**被平移）
"""
import io
import os
import sys
import time
import logging

OFF = float(os.environ.get('CLOCK_SHIFT_SEC') or 0)
fails = []


def ck(name, cond, extra=''):
    print(('  [PASS] ' if cond else '  [FAIL] ') + name + '  ' + str(extra))
    if not cond:
        fails.append(name)


print('=' * 70)
print('时钟注入器 v2 自检    CLOCK_SHIFT_SEC=%r' % os.environ.get('CLOCK_SHIFT_SEC'))
print('=' * 70)

# ★ A1 的硬判据必须来自"另一个进程"：同进程里比较是自说自话。
import subprocess
_py = sys.executable
_env = dict(os.environ)
_env.pop('CLOCK_SHIFT_SEC', None)
_env.pop('PYTHONPATH', None)
_real = float(subprocess.run([_py, '-c', 'import time;print(time.time())'],
                             stdout=subprocess.PIPE, env=_env).stdout.decode().strip())
_shifted = time.time()
delta = _shifted - _real
print('  真实（无注入子进程）= %.3f' % _real)
print('  本进程  time.time() = %.3f' % _shifted)
print('  差值 = %.3f  （期望 ≈ %.3f，容差 5s）' % (delta, OFF))

ck('A1 ★ 平移量正确（与独立子进程的真实时钟比对）', abs(delta - OFF) < 5.0,
   'delta=%.3f off=%.3f' % (delta, OFF))

rec = logging.LogRecord('probe', logging.INFO, 'p', 1, 'hello %s', ('x',), None)
fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
err = None
try:
    s = fmt.format(rec)
except Exception as e:                                   # noqa: BLE001
    err = '%s: %s' % (type(e).__name__, e)
    s = ''
ck('A2 ★★ Formatter.format() 不抛（v1 就在这里 TypeError ⇒ 日志全灭）',
   err is None, err or repr(s))

buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setFormatter(fmt)
lg = logging.getLogger('probe_root')
lg.handlers = [h]
lg.setLevel(logging.INFO)
lg.propagate = False
lg.info('注入器自检：这条必须看得见')
ck('A3 ★ 真发一条 INFO 能落到流上（探针没把日志打死）',
   '注入器自检' in buf.getvalue(), repr(buf.getvalue().strip()))

import datetime as _dt
# ★ 这里差点又踩"判据写错"：第一版写成 abs(now - real) 再和 OFF 比 ——
#   外层 abs() 把**符号**吃掉了，OFF 为负时恒判否（自检自己的假红）。
_d_signed = _dt.datetime.now().timestamp() - _real
ck('A4 datetime.now() 跟着平移', abs(_d_signed - OFF) < 5.0, 'delta=%.3f' % _d_signed)

p1, m1 = time.perf_counter(), time.monotonic()
time.sleep(0.05)
p2, m2 = time.perf_counter(), time.monotonic()
ck('A5 ★ 刻意不动的两个（perf_counter/monotonic 计的是耗时，不是绝对时刻）',
   abs((p2 - p1) - 0.05) < 0.05 and abs((m2 - m1) - 0.05) < 0.05,
   'perf=%.3f mono=%.3f' % (p2 - p1, m2 - m1))

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_mtime_probe.txt')
io.open(_p, 'w', encoding='utf-8').write('x')
_mt = os.path.getmtime(_p)
ck('A6 ★ 局限②如实成立：新写文件 mtime ≈ 真实时钟（**没**被平移）',
   abs(_mt - _real) < 5.0, 'mtime-real=%.3f' % (_mt - _real))
try:
    os.remove(_p)
except Exception:
    pass

print('-' * 70)
print('自检结论：%d PASS / %d FAIL' % (6 - len(fails), len(fails)))
for f in fails:
    print('  FAIL: ' + f)
print('=' * 70)
sys.exit(1 if fails else 0)
