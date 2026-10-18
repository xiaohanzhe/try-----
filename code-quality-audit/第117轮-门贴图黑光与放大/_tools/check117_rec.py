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
# ★ 第117轮修：原来写成 `try: ... ck(..., True)` —— 判据条件是个**字面量 True**，
#   被自己的复检 `④ 无恒真判据` 抓到（"恒真判据比不写还危险"）。改成先把结果落到
#   变量、再判变量 ⇒ 条件真的由"import 成没成"决定。
try:
    from modules import desk_doors as DD
    _dd_ok, _dd_err = True, ''
except Exception as e:                                            # noqa: BLE001
    DD, _dd_ok, _dd_err = None, False, repr(e)
ck('V0 能 import 产品模块 desk_doors（零依赖）', _dd_ok, _dd_err)

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

# ---------------------------------------------------------------- 渐显下限（本轮改动）
# ★★★ 第117轮：`MIN_ALPHA` 0.14 → **0.50**（由 `alpha117_pick.py` 反解背景测 ΔL 定的）。
#   这两条把改动**钉在真机数据上**，而不是只钉源码常量 —— 若哪天产品改回 0.14，
#   就算源码常量被同步改了，真机录屏里门 C 的 alpha 也会立刻落回 0.14 ⇒ 报红。
try:
    from modules import door_reveal as _DRM
    _MIN = float(_DRM.MIN_ALPHA)
except Exception as _e:                                          # noqa: BLE001
    _DRM = None
    _MIN = None
    info('取不到 door_reveal.MIN_ALPHA（%r）⇒ V19/V19b 直接判红' % (_e,))
_c_al = set(float(r['C_alpha']) for r in rows)
_d_al = set(float(r['D_alpha']) for r in rows)
ck('V19 门 C 在真机上的 alpha == 产品 MIN_ALPHA（%.2f）' % (_MIN if _MIN else -1),
   _MIN is not None and len(_c_al) == 1 and abs(list(_c_al)[0] - _MIN) < 1e-6,
   '录制取值=%s' % sorted(_c_al))
ck('V19b 门 D（按距离更实一档）alpha 也 >= MIN_ALPHA（渐显只剩半档）',
   _MIN is not None and bool(_d_al) and min(_d_al) >= _MIN - 1e-9,
   '%.4f~%.4f' % (min(_d_al), max(_d_al)))

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

    # ---- 门 B：只在 P2 **且对话框确实不在**的帧判 ----
    # ★ 第117轮补：Ralsei 会自己说话，对话框可能在 P2 里再弹出来（实测 t=9.185）。
    #   那一帧门 B 是**被不透明 UI 整块盖住**的（V13 量到 100%）⇒ 拿它比像素是
    #   **口径错了**（比的是对话框的底色，不是门）。⇒ 只在 `dlg_vis == '0'` 的帧判。
    #   ★ 这不是放宽：仍然要求**每一张干净帧**都 ≤ 8，并且**干净帧数 ≥ 5**（否则"没有
    #     干净帧"会被判成通过）。被排除的帧数如实 INFO 打印。
    p2 = [i for i, r in enumerate(rows) if r['phase'] == 'P2']
    p2c = [i for i in p2 if rows[i]['dlg_vis'] == '0']
    n_skip = len(p2) - len(p2c)
    if n_skip:
        info('P2 共 %d 帧，其中 %d 帧对话框可见（门 B 被整块盖住）⇒ 像素判据只用剩下的 '
             '%d 帧（盖住时比的是对话框底色，不是门）' % (len(p2), n_skip, len(p2c)))
    ck('V11a P2 里"对话框不在"的干净帧足够多（>= 5）', len(p2c) >= 5, '%d 帧' % len(p2c))
    resB = [(i, cmp_at(frames[i], RECT['B'], SPRITE['B'])) for i in p2c]
    okB = [r for _, r in resB if r is not None]
    bdB = [r[1] for r in okB]
    pdB = [r[0] for r in okB]
    ck('V11 门 B 在 P2 **逐帧**分块均值比对（block8 <= 8）',
       bool(bdB) and max(bdB) <= 8.0,
       '干净帧 %d，max=%.2f 中位 %.2f' % (len(bdB), max(bdB) if bdB else -1,
                                         float(np.median(bdB)) if bdB else -1))
    if pdB:
        info('门 B 逐像素 mean|Δ|≈%.1f，分块口径 %.1f ⇒ 差值来自 mp4 对细线的高频损失，'
             '不是内容不对（换图会差 30+，见门 D 硬比的 34）'
             % (float(np.median(pdB)), float(np.median(bdB))))

    # ---- 帧间稳定性（只在"同一相位、且门已出现"的区间内判）----
    seqA = [float(r['A_lum']) for r in rows][1:]           # 跳过首帧（淡入前是壁纸）
    wA = max(abs(seqA[i] - seqA[i - 1]) for i in range(1, len(seqA)))
    ck('V12 门 A（除首帧）帧间无跳变（<=3）', wA <= 3.0, 'max=%.2f' % wA)

    # ★ 第117轮补：同样只看"对话框不在"的帧 —— 否则对话框一弹一收，B_lum 从 91.7
    #   跳到 5.6（实测），把"UI 出现"误判成"门在闪"。
    seqB = [float(rows[i]['B_lum']) for i in p2c if rows[i]['B_lum']]
    wB = max(abs(seqB[i] - seqB[i - 1]) for i in range(1, len(seqB))) if len(seqB) > 1 else 0.0
    ck('V12b 门 B 在 P2 帧间无跳变（<=12）', wB <= 12.0,
       'max=%.2f（%d 个干净帧）' % (wB, len(seqB)))

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
# ★★★ 第117轮改钉：`MIN_ALPHA` 那次是我误判（已回退），但"门 B 被对话框整块盖住"
#   这条是**实测事实**（1:1 对照 `ab117_doorB.png`：面板不透明黑）。
#   修法 = 让对话框让位（`dialogue_ui._avoided_bottom_y`）。
#   ⇒ 判据从"遮挡 100% 如实量化"改成 **"避让后遮挡必须为 0"**，并且**同时**算出
#     "不避让时会遮多少"，用来证明①这个问题真实存在 ②判据有鉴别力（不是恒真）。
if dlg and len(RECT) == 4:
    # 只在"对话框真的可见"的帧上量（隐藏帧的几何是上一次的残留，不该混进来）
    vis = [(int(r['dlg_x']), int(r['dlg_y']), int(r['dlg_w']), int(r['dlg_h']))
           for r in rows
           if r['dlg_w'] and r.get('dlg_vis') == '1' and float(r.get('dlg_op') or 0) > 0.9]
    vis = vis or []
    if vis:
        cv = [inter(RECT['B'], rr) / float(RECT['B'][2] * RECT['B'][3]) for rr in vis]
        COVER['B'] = round(max(cv), 4)
        info('对话框可见 %d 帧；门 B 被遮挡 最大 %.1f%% / 中位 %.1f%%'
             % (len(vis), max(cv) * 100, sorted(cv)[len(cv) // 2] * 100))
        # 反事实：把这块面板放回"贴底"老位置 ⇒ 应该 100% 盖住门 B
        hypo = []
        for (dx, dy, dw, dh) in vis:
            hypo.append(inter(RECT['B'], (dx, CANVAS[1] - dh - 4, dw, dh))
                        / float(RECT['B'][2] * RECT['B'][3]))
        # ★ 期望值不是 100% 而是 **推导出来的上界**：老定位是 `bottom - dh - 4`
        #   ⇒ 面板底边离屏幕底 4 px ⇒ 门 B（高 129、贴底）**最下面 4 px 永远露着**
        #   ⇒ 最大遮挡 = (129-4)/129 = **96.9%**。写成 0.99 会是一条**恒假判据**。
        _cap = (RECT['B'][3] - 4.0) / float(RECT['B'][3])
        COVER['B_unlifted'] = round(max(hypo), 4)
        ck('V13 ★★★ 门 B 在对话框可见时**一点没被挡**（避让生效）',
           max(cv) <= 0.0, '最大 %.1f%%（对话框 rect 取值 %d 种）'
           % (max(cv) * 100, len(vis)))
        ck('V13b ★★ 反事实：若不避让、面板仍贴底 ⇒ 门 B 几乎全被盖住（问题真实 + 判据有鉴别力）',
           min(hypo) >= _cap - 1e-3,
           '不避让时遮挡 %.1f%%（上界 %.1f%% = (门高129-贴底4)/129）'
           % (min(hypo) * 100, _cap * 100))
    else:
        info('本轮没有"对话框可见"的帧 ⇒ 无法量遮挡（不是通过，是没数据）')
        ck('V13 门 B 遮挡率可量（需要至少一帧对话框可见）', False, 'vis=0')

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
