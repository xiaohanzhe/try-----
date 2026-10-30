# -*- coding: utf-8 -*-
u"""mutate118_rec.py —— 变异测试：**证明 `check118_rec.py` 的判据不是恒真**。

为什么必须做
------------
第118轮上半场刚吃过一次亏：`check118.py` 的 `check()` 把 `[FAIL]` 行藏进了
detail 里，导致 7 条变异**全判 MISSED**（假阴性）—— 判据"全绿"但根本没在守。
⇒ 规矩：**判据本身也是被测物**，必须能"故意弄坏 ⇒ 它报红"。

怎么变（都不碰仓库里的真证据）
------------------------------
把 `rec118_frames.csv` 复制到临时区，改一列；`avi` 默认仍指向真证据（只读）。
唯一需要动像素的是 M9（把模态帧涂黑），它单独造一个临时 avi。
然后以 `RALSEI_REC118_CSV` / `RALSEI_REC118_AVI` 覆盖输入跑 `check118_rec.py`，
断言：**该红的判据真的红了**，而且**未变异时它是绿的**（否则"红"没有意义）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\mutate118_rec.py
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence', 'rec118')
CSVP = os.path.join(EV, 'rec118_frames.csv')
AVI = os.path.join(EV, 'rec118.avi')
CK = os.path.join(HERE, 'check118_rec.py')
PY = sys.executable
TMP = tempfile.mkdtemp(prefix='mut118rec_')

if not (os.path.isfile(CSVP) and os.path.isfile(AVI)):
    sys.stdout.write('!! 缺证据\n')
    sys.exit(2)


def say(m):
    sys.stdout.write('[mut] %s\n' % m)
    sys.stdout.flush()


BASE = list(csv.DictReader(io.open(CSVP, encoding='utf-8', newline='')))
COLS = list(BASE[0].keys()) if BASE else []


def run(csv_path, avi_path=AVI):
    env = dict(os.environ)
    env['RALSEI_REC118_CSV'] = csv_path
    env['RALSEI_REC118_AVI'] = avi_path
    p = subprocess.run([PY, CK], capture_output=True, env=env,
                       cwd=os.path.dirname(ROUND), timeout=600)
    out = p.stdout.decode('utf-8', 'replace')
    fails = [ln.split('] ', 1)[1] for ln in out.splitlines()
             if ln.startswith('[FAIL] ')]
    return out, fails


def write_rows(rows, name, cols=None):
    p = os.path.join(TMP, name)
    cols = cols or COLS
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in cols})
    return p


def clone():
    return [dict(r) for r in BASE]


# ---------------------------------------------------------------- 基线
say('基线：未变异应全绿')
_, f0 = run(CSVP)
say('  基线 FAIL = %r' % (f0,))
if f0:
    say('!! 基线就不是全绿 ⇒ 下面的"变异报红"没有意义，先修判据')
    sys.exit(2)


CASES = []


def case(name, expect, rows=None, cols=None, avi=None):
    CASES.append((name, expect, rows, cols, avi))


# M1 门 A 往下挪 40 px（不再贴正上边）
def m1():
    rs = clone()
    for r in rs:
        if r.get('A_x', '') != '':
            r['A_y'] = str(int(float(r['A_y'])) + 40)
    return rs


# M2 门 C 往右挪 30 px（不再贴正左边）
def m2():
    rs = clone()
    for r in rs:
        if r.get('C_x', '') != '':
            r['C_x'] = str(int(float(r['C_x'])) + 30)
    return rs


# M3 门 D 整体左移（右边不再贴屏右）
def m3():
    rs = clone()
    for r in rs:
        if r.get('D_x', '') != '':
            r['D_x'] = str(int(float(r['D_x'])) - 80)
    return rs


# M4 门 B 上移 80 px（离屏底太远）
def m4():
    rs = clone()
    for r in rs:
        if r.get('B_y', '') != '':
            r['B_y'] = str(int(float(r['B_y'])) - 80)
    return rs


# M5 让门 C 的矩形在某几帧变一下（模拟"门跟着动画一跳一跳"）
def m5():
    rs = clone()
    n = 0
    for r in rs:
        if r.get('C_w', '') != '' and n % 40 == 7:
            r['C_w'] = str(int(float(r['C_w'])) + 9)
        n += 1
    return rs


# M6 把某扇门 hold 段的 alpha 压到 0.5（门没全显）
def m6():
    rs = clone()
    for r in rs:
        if r['step'] == 'P2_C_hold':
            r['C_alpha'] = '0.5000'
    return rs


# M7 把 ut 的帧全说成 desktop（"根本没进世界"）
def m7():
    rs = clone()
    for r in rs:
        if r.get('scene', '').startswith('ut.'):
            r['scene'] = 'desktop'
    return rs


# M8 把所有帧的 modal 置 0（"框一次都没出现"）
def m8():
    rs = clone()
    for r in rs:
        if r.get('modal', '') != '':
            r['modal'] = '0'
    return rs


# M10 把框挪回旧的"贴底"位置（与对话气泡重叠）
def m10():
    rs = clone()
    for r in rs:
        if r.get('modal', '') == '1':
            r['dlg_y'] = '1261'
    return rs


case('M1 门 A 下移 40px', 'R3a', m1())
case('M2 门 C 右移 30px', 'R3b', m2())
case('M3 门 D 左移 80px', 'R3c', m3())
case('M4 门 B 上移 80px', 'R3d', m4())
case('M5 门 C 矩形抖动', 'R2b', m5())
case('M6 门 C 的 alpha 压到 0.5', 'R4C', m6())
case('M7 ut 的帧说成 desktop', 'R6C', m7())
case('M8 modal 全置 0', 'C1', m8())
case('M10 框挪回旧的贴底位置', 'C10', m10())

# ---------------------------------------------------------------- M9（动像素）
say('造 M9 的临时 avi（把模态帧涂黑）')
import cv2                                                       # noqa: E402
import numpy as np                                              # noqa: E402

modal_idx = {i for i, r in enumerate(BASE) if r.get('modal') == '1'}
cap = cv2.VideoCapture(AVI)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
M9AVI = os.path.join(TMP, 'rec118_m9.avi')
vw = cv2.VideoWriter(M9AVI, cv2.VideoWriter_fourcc(*'mp4v'), 5.0, (w, h))
i = 0
while True:
    ok, fr = cap.read()
    if not ok:
        break
    if i in modal_idx:
        fr = np.zeros_like(fr)
    vw.write(fr)
    i += 1
cap.release()
vw.release()
say('  M9 avi = %s（%d 帧，涂黑 %d 帧）' % (M9AVI, i, len(modal_idx)))
case('M9 模态帧画面涂黑（红心不在）', 'C2', None, None, M9AVI)

# ---------------------------------------------------------------- 跑
say('')
caught = 0
missed = []
for name, expect, rows, cols, avi in CASES:
    if rows is None:
        p = CSVP
    else:
        p = write_rows(rows, 'mut_%s.csv' % name.split()[0])
    out, fails = run(p, avi or AVI)
    hit = any(f.startswith(expect) for f in fails)
    if hit:
        caught += 1
        say('CAUGHT  %-32s ⇒ %s 报红' % (name, expect))
    else:
        missed.append((name, expect, fails[:6]))
        say('MISSED  %-32s ⇒ 期望 %s 报红，实际 FAIL=%r'
            % (name, expect, fails[:6]))

say('')
say('==== mutate118_rec: %d / %d CAUGHT ====' % (caught, len(CASES)))
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:                                                # noqa: BLE001
    pass
sys.exit(0 if not missed else 1)
