# -*- coding: utf-8 -*-
u"""check117_rec.py —— 对 `rec117.avi` / `rec117_frames.csv` / `fast117_writes.csv` 做**逐帧判据**。

它回答的问题（用户 10-18：「可以录屏逐帧检查了」）
------------------------------------------------
  · 四门在整个 14 s 里**一直在**吗（不是某一刻在）？
  · 门 A 是**一直是**黑光，还是某一帧闪回品红？
  · 「大一点都」放大之后，**几何会不会抖**（某些帧 rect 变化）？
  · 第116轮修掉的**对话框闪现 / 任务栏翻转**有没有被放大带回来？
  · 门 B 贴在底边，**对话框到底盖住它多少**？

三条独立证据链（**互相印证，不互相替代**）
------------------------------------------
  ① `rec117.avi` —— 画面本身（mp4 有损，用于"逐帧看 + 帧间稳定性"）；
  ② `rec117_frames.csv` —— 录制时的**精确像素统计**（未压缩）+ **内省状态**
     （四门 sprite/rect/alpha、对话框 opacity/vis、任务栏 z）；
  ③ `fast117_writes.csv` —— `_desktop_screen_doors` 的**调用序列**（写入路径插桩，
     精确、不抽样）⇒ 判"有没有闪"最硬的一条：闪烁必然表现为 alpha 向量反复变化。

★★★ 三种"口径"千万别混（本轮在自己的判据上连栽两次）
---------------------------------------------------
1. **`mean_lum` 必须只在贴图不透明区取**（掩膜 alpha≥250 再腐蚀 1 px）。
   整矩形平均会把壁纸算进去 —— 第一版把门 A 的 19.8 量成了 **65.1**。
2. **mp4 有损 ⇒ 逐像素比对会虚高**。实测门 B：逐像素 **17.08**，分块 8×8 均值只有 **5.14**
   （细网格品红线被 4:2:0 + 量化压糊）。⇒ 录像帧用**分块均值**当主判据（阈值 8），
   逐像素只作 INFO。这不是"放宽"：换一张图会差 30+（门 D 硬比是 34，因为它 alpha=0.29）。
3. **有渐显的门（C/D）不能与贴图硬比**：alpha<1 ⇒ 屏幕像素 = 贴图×alpha + 背景×(1-alpha)。
   实测门 D 帧 mean RGB (140,125,26) vs 贴图 (243,186,62) —— 差别**正是 alpha 造成的**，
   硬比会报假红。C/D 只判几何稳定 + alpha 序列平滑。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\check117_rec.py
"""
import csv
import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
ASSETS = os.path.join(PKG, 'assets', 'scenes')
OUT = os.path.join(ROUND, '_evidence', 'rec117')
AVI = os.path.join(OUT, 'rec117.avi')
CSV_F = os.path.join(OUT, 'rec117_frames.csv')
WR_F = os.path.join(OUT, 'fast117_writes.csv')

SPRITE = {'A': 'objs/desk_door_oneshot_black.png',
          'B': 'objs/niko_door_portal.png',
          'C': 'objs/desk_door_ut.png',
          'D': 'objs/desk_door_deltarune.png'}
CANVAS = (2560, 1528)

ok = fail = 0
L = []


def ck(name, cond, detail=''):
    global ok, fail
    ok += 1 if cond else 0
    fail += 0 if cond else 1
    L.append('[%s] %s  %s' % ('PASS' if cond else 'FAIL', name, detail))
    print(L[-1])


def info(msg):
    L.append('[INFO] %s' % msg)
    print(L[-1])


sys.path.insert(0, PKG)                       # ★ 是 PKG（`modules/` 的父目录），不是 PKG/src
try:
    from modules import desk_doors as DD
    ck('V0 能 import 产品模块 desk_doors（零依赖）', True)
except Exception as e:                                            # noqa: BLE001
    DD = None
    ck('V0 能 import 产品模块 desk_doors（零依赖）', False, repr(e))

# ---------------------------------------------------------------- CSV / avi
rows = []
if os.path.isfile(CSV_F):
    rows = list(csv.DictReader(io.open(CSV_F, 'r', encoding='utf-8')))
ck('V1 录屏 CSV 存在且有帧', len(rows) >= 20, '帧数=%d' % len(rows))
if not rows:
    print('\r\n'.join(L))
    sys.exit(1)

frames = None
try:
    import cv2
    cap = cv2.VideoCapture(AVI)
    tmp = []
    while True:
        got, f = cap.read()
        if not got:
            break
        tmp.append(f[:, :, ::-1])
    cap.release()
    frames = tmp
except Exception as e:                                            # noqa: BLE001
    frames = None
ck('V2 能逐帧解码 avi', bool(frames), '帧数=%d' % (len(frames) if frames else 0))
if frames:
    h, w = frames[0].shape[:2]
    ck('V3 avi 尺寸 == 整屏（画布在屏幕左上角对齐）', (h, w) == (1600, 2560), '%dx%d' % (w, h))
    ck('V3b avi 帧数 == CSV 行数（两路证据可逐帧对齐）',
       len(frames) == len(rows), '%d vs %d' % (len(frames), len(rows)))

# ---------------------------------------------------------------- 几何
RECT = {}
for Lt in 'ABCD':
    vals = set((r['%s_x' % Lt], r['%s_y' % Lt], r['%s_w' % Lt], r['%s_h' % Lt])
               for r in rows if r['%s_x' % Lt])
    ck('V4 门 %s 的 rect 全帧恒定' % Lt, len(vals) == 1, '%s' % (list(vals)[:2],))
    if vals:
        RECT[Lt] = tuple(int(v) for v in list(vals)[0])
ck('V5 四门 rect 都取到', len(RECT) == 4, sorted(RECT))

if DD is not None and len(RECT) == 4:
    pet_box = DD.pet_screen_box(DD.clamp_scale_factor_for_max_side(3.33125))
    sizes = {}
    for Lt, rel in SPRITE.items():
        with Image.open(os.path.join(ASSETS, rel.replace('/', os.sep))) as im:
            sizes[Lt] = im.size
    plan = dict(DD.plan_screen_doors(sizes, CANVAS[0], CANVAS[1], pet_box=pet_box))
    ck('V6 rect == 产品 plan_screen_doors 复算（同一把尺）', plan == RECT,
       '期望 %s 实际 %s' % (plan, RECT))
    k = DD.fit_doors_uniform_scale(sizes, pet_box)
    ck('V7 统一倍率 k 与第117轮一致（1.0116±0.001）', abs(k - 1.0116) < 0.001, 'k=%.6f' % k)

# ---------------------------------------------------------------- alpha
for Lt in 'AB':
    al = sorted(set(float(r['%s_alpha' % Lt]) for r in rows))
    ck('V8 门 %s alpha 恒 1.0（不参与渐显）' % Lt, al == [1.0], '取值=%s' % al[:4])
for Lt in 'CD':
    al = [float(r['%s_alpha' % Lt]) for r in rows]
    jumps = [abs(al[i] - al[i - 1]) for i in range(1, len(al))]
    ck('V9 门 %s alpha 最大跳变 <= 0.02（渐显平滑）' % Lt,
       (not jumps) or max(jumps) <= 0.02,
       '范围 %.4f~%.4f 最大跳变 %.4f' % (min(al), max(al), max(jumps) if jumps else 0))
    ck('V9b 门 %s alpha 在 (0,1) 内（确属渐显，不是漏画/全亮）' % Lt,
       0.0 < min(al) and max(al) < 1.0, '%.4f~%.4f' % (min(al), max(al)))

# ---------------------------------------------------------------- 像素（掩膜内 + 分块）
def load_pair(rel, w, h):
    with Image.open(os.path.join(ASSETS, rel.replace('/', os.sep))).convert('RGBA') as im:
        if im.size != (w, h):
            im = im.resize((w, h), Image.NEAREST)
        a = np.array(im)
    m = a[:, :, 3] >= 250
    e = m.copy()
    e[1:-1, 1:-1] = (m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1]
                     & m[1:-1, :-2] & m[1:-1, 2:])
    e[0, :] = e[-1, :] = False
    e[:, 0] = e[:, -1] = False
    return a[:, :, :3].astype(np.int16), e


def blocks_means(arr, mask, b=8):
    hh, ww = arr.shape[:2]
    out = []
    for by in range(0, hh - b + 1, b):
        for bx in range(0, ww - b + 1, b):
            if mask[by:by + b, bx:bx + b].mean() > 0.5:
                out.append(arr[by:by + b, bx:bx + b].reshape(-1, 3).mean(axis=0))
    return np.array(out) if out else np.zeros((0, 3))


def cmp_at(frame, rect, rel):
    u"""⇒ (逐像素 mean|Δ|, 分块8 均值 mean|Δ|)；取不到 ⇒ None。"""
    x, y, w, h = rect
    sub = frame[max(0, y):y + h, max(0, x):x + w]
    if sub.shape[0] != h or sub.shape[1] != w:
        return None
    sp, m = load_pair(rel, w, h)
    if m.shape != sub.shape[:2] or not m.any():
        return None
    sub = sub.astype(np.int16)
    px = float(np.abs(sub[m] - sp[m]).mean())
    bl = blocks_means(sub, m)
    bs = blocks_means(sp, m)
    bd = float(np.abs(bl - bs).mean()) if len(bl) else 999.0
    return px, bd


if frames and len(RECT) == 4 and len(frames) == len(rows):
    # ---- 门 A：每一帧都要是黑光 ----
    resA = [cmp_at(f, RECT['A'], SPRITE['A']) for f in frames]
    pdA = [r[0] if r else 999 for r in resA]
    bdA = [r[1] if r else 999 for r in resA]
    ck('V10 门 A **逐帧**分块均值比对（block8 <= 8）',
       max(bdA[1:]) <= 8.0,
       '除首帧外 max=%.2f（全 %d 帧）' % (max(bdA[1:]) if len(bdA) > 1 else -1, len(bdA)))
    ck('V10b 门 A 逐像素（除首帧）<= 8（mp4 有损上限）',
       max(pdA[1:]) <= 8.0, 'max=%.2f / 中位 %.2f' % (max(pdA[1:]), float(np.median(pdA[1:]))))
    ck('V10c 首帧确实不同 ⇒ 录到了"门出现"的那一刻（不是从头就在）',
       pdA[0] > 20.0, '首帧 %.2f' % pdA[0])

    # ---- 门 B：只在 P2（对话框已隐藏）判 ----
    p2 = [i for i, r in enumerate(rows) if r['phase'] == 'P2']
    resB = [(i, cmp_at(frames[i], RECT['B'], SPRITE['B'])) for i in p2]
    okB = [r for _, r in resB if r is not None]
    bdB = [r[1] for r in okB]
    pdB = [r[0] for r in okB]
    ck('V11 门 B 在 P2 **逐帧**分块均值比对（block8 <= 8）',
       bool(bdB) and max(bdB) <= 8.0,
       'P2 %d 帧，max=%.2f 中位 %.2f' % (len(bdB), max(bdB) if bdB else -1,
                                        float(np.median(bdB)) if bdB else -1))
    if pdB:
        info('门 B 逐像素 mean|Δ|≈%.1f，分块口径 %.1f ⇒ 差值来自 mp4 对细线的高频损失，'
             '不是内容不对（换图会差 30+，见门 D 硬比的 34）'
             % (float(np.median(pdB)), float(np.median(bdB))))

    # ---- 帧间稳定性（只在"同一相位、且门已出现"的区间内判）----
    seqA = [float(r['A_lum']) for r in rows][1:]           # 跳过首帧（淡入前是壁纸）
    wA = max(abs(seqA[i] - seqA[i - 1]) for i in range(1, len(seqA)))
    ck('V12 门 A（除首帧）帧间无跳变（<=3）', wA <= 3.0, 'max=%.2f' % wA)

    seqB = [float(r['B_lum']) for r in rows if r['phase'] == 'P2' and r['B_lum']]
    wB = max(abs(seqB[i] - seqB[i - 1]) for i in range(1, len(seqB))) if len(seqB) > 1 else 0.0
    ck('V12b 门 B 在 P2 帧间无跳变（<=12）', wB <= 12.0, 'max=%.2f' % wB)

# ---------------------------------------------------------------- 遮挡量化
def inter(a, b):
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[0] + a[2], b[0] + b[2])
    y1 = min(a[1] + a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


dlg = set((int(r['dlg_x']), int(r['dlg_y']), int(r['dlg_w']), int(r['dlg_h']))
          for r in rows if r['dlg_w'])
COVER = {}
if dlg and len(RECT) == 4:
    dr = sorted(dlg)[0]
    for Lt in 'ABCD':
        COVER[Lt] = round(inter(RECT[Lt], dr) / float(RECT[Lt][2] * RECT[Lt][3]), 4)
        info('门 %s 被对话框遮挡 %.1f%%（对话框 rect=%s，%d 种取值）'
             % (Lt, COVER[Lt] * 100, dr, len(dlg)))
ck('V13 门 B 遮挡率被如实量化（门 B 在底边正中 ⇒ 有消息时会被整块盖住）',
   'B' in COVER and COVER['B'] >= 0.9, '%.1f%%' % (COVER.get('B', -1) * 100))

# ---------------------------------------------------------------- 对话框 / 任务栏
p1 = [r for r in rows if r['phase'] == 'P1']
if p1:
    ops = [float(r['dlg_op']) for r in p1]
    steady = [o for o in ops if o >= 0.9]
    drops = sum(1 for i in range(1, len(ops)) if ops[i - 1] >= 0.9 and ops[i] < 0.5)
    ck('V14 对话框只淡入一次、稳态不二次塌陷',
       bool(steady) and drops == 0,
       'P1 %d 帧，稳态 %d 帧，塌陷 %d 次，末值 %.3f' % (len(ops), len(steady), drops, ops[-1]))
ck('V15 对话框 P2 已隐藏（hide 不改几何 ⇒ 相位切换不污染几何判据）',
   all(r['dlg_vis'] == '0' for r in rows if r['phase'] == 'P2'))
zs = set(r['tb_z'] for r in rows if r['tb_z'])
ck('V16 任务栏 z 名次全帧恒定（第116轮 5.72 Hz 翻转未回归）',
   len(zs) == 1, '取值=%s' % sorted(zs))

# ---------------------------------------------------------------- 写入路径（精确，不抽样）
if os.path.isfile(WR_F):
    wr = list(csv.DictReader(io.open(WR_F, 'r', encoding='utf-8')))
    ck('V17 写入路径有样本', len(wr) >= 10, '%d 次调用' % len(wr))
    chg = 0
    prev = None
    for r in wr:
        cur = tuple(r[k] for k in sorted(r) if k.startswith('a'))
        if prev is not None and cur != prev:
            chg += 1
        prev = cur
    ck('V18 8 s 内 alpha 向量**零变化** ⇒ 不存在闪烁', chg == 0,
       '变化 %d 次 / %d 次调用' % (chg, len(wr)))
    ts = [float(r['t']) for r in wr]
    gaps = sorted(ts[i] - ts[i - 1] for i in range(1, len(ts)))
    if gaps:
        info('重绘调用间隔 中位 %.0f ms（≈%.1f Hz）' % (gaps[len(gaps) // 2] * 1000,
                                              1.0 / gaps[len(gaps) // 2]))
else:
    ck('V17 写入路径 CSV 存在', False, '缺 %s（先跑 fast117.py）' % os.path.basename(WR_F))

# ---------------------------------------------------------------- 汇总
print('\r\n' + '=' * 60)
print('rec117：%d 条 / %d PASS / %d FAIL' % (len([x for x in L if not x.startswith('[INFO')]), ok, fail))
stats = {'ok': ok, 'fail': fail, 'rects': {k: list(v) for k, v in RECT.items()},
         'cover': COVER, 'frames': len(frames) if frames else 0, 'rows': len(rows)}
_s = os.path.join(OUT, 'check117_rec.txt')
io.open(_s, 'w', encoding='utf-8', newline='').write('\r\n'.join(L) + '\r\n')
io.open(os.path.join(OUT, 'check117_rec.json'), 'w', encoding='utf-8', newline='').write(
    json.dumps(stats, ensure_ascii=False, indent=1))
print('证据 = %s' % _s)
sys.exit(1 if fail else 0)
