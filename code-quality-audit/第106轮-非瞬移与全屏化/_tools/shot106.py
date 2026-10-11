# -*- coding: utf-8 -*-
u"""shot106.py —— 第106轮录制的**分析端**（用户口径「一定要看录像而不是只读后台输出」）。

读 `_evidence/rec106_frames.csv`（录制端每 250 ms 一行，列由**产品代码自己**填）
+ `rec106_hops.txt`（换场景那一刻的 HOP 行）+ `rec106_inject.txt` + `rec106_raw.avi`：

  1. `rec106_timeline.txt` —— 只列**场景变化**的那些帧，人眼一眼读完；
  2. 断言块 —— 把「**逐门走过去（不是直达）**」「**全屏化真生效（相机成对放大、
     逻辑窗口仍 320×240）**」「人物等比放大」「既有 Deltarune 未受影响」
     在**录像数据**上再证一次（判据只看产品字段）；
  3. `rec106_contact_sheet.png` —— 从录像里取"起点 / 中途各房间 / 终点 / Deltarune
     对照"若干帧拼成一张对照图（★ `imencode` + 手写，`cv2.imwrite` 在中文路径下
     静默失败）。

★ 与第105轮 `shot105.py` 的关系（**同一段注入，靶心换了**）
----------------------------------------------------------
第105轮的 `A3「逐门走过」` **报红了**（INIT → S1 一步到位，中间 16 间房一帧没出现）
⇒ 那就是本轮 #28 的立项证据。本轮**同一判据必须转 PASS**：
`travel_to()` 现在逐跳走完 `plan['steps']`；同时**追加**全屏化判据（B 段）。

★ 纪律：判据**只看产品字段**，不从像素里"猜"状态；像素只用来给人眼看。
★ 判据不可恒真：每条都要有**失败的可能**（负控制见各条注释）。
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.environ.get('REC106_EVDIR') or os.path.join(ROUND, '_evidence')
CSV = os.path.join(EV, 'rec106_frames.csv')
HOPS = os.path.join(EV, 'rec106_hops.txt')
INJ = os.path.join(EV, 'rec106_inject.txt')
RAW = os.path.join(EV, 'rec106_raw.avi')
OUT = os.path.join(EV, 'rec106_timeline.txt')
SHEET = os.path.join(EV, 'rec106_contact_sheet.png')

# 本轮要证的场景标签（与 rec106.py 的注入参数保持一致）
OS_FROM = os.environ.get('REC106_OS_FROM', 'oneshot.mainline.INIT')
OS_TO = os.environ.get('REC106_OS_TO', 'oneshot.mainline.S1')
DL_FROM = os.environ.get('REC106_DL_FROM', 'ch1.kris_room.kris_s_room')
DL_TO_SID = 'ch1.hometown.town_church'      # 教堂（产品自己解析出来的 scene_id）

# ★ 全屏化的期望值 —— **从产品真值现推**，不写死（第106轮的教训：
#   check89 把 40×40 / 640×480 写死 ⇒ 全屏化后假红）。
EXPECT_SCOPED = (320, 240)                  # 逻辑窗口恒 320×240（可见范围不变）
EXPECT_MIN_SCALE = 2.0                      # 改前基线 scale=2.0 ⇒ 全屏化只许 >= 它
EXPECT_MIN_OUT_W = 640                      # 改前基线输出宽 640 ⇒ 只许 >= 它

R = []
F = []


def _read_rows(path):
    """★ 字节忠实读取（`newline=''`）再逐格剥 `\\r` ⇒ 换行风格变了也不会取不到键。"""
    rows = []
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            rows.append({(k or '').strip(): (v.strip() if isinstance(v, str) else v)
                         for k, v in r.items()})
    return rows


def ok(name, cond, detail=u''):
    R.append((name, bool(cond)))
    print(u'[%s] %s%s' % (u'PASS' if cond else u'FAIL', name,
                          (u'  —— ' + detail) if detail else u''))


def _f(v, d=None):
    try:
        return float(v)
    except Exception:
        return d


def _i(v, d=-1):
    try:
        return int(float(v))
    except Exception:
        return d


def main():
    if not os.path.isfile(CSV):
        print('[shot106] 缺 %s' % CSV)
        return 2
    rows = _read_rows(CSV)
    print('[shot106] 帧数 = %d' % len(rows))
    if not rows:
        return 2

    hops = []
    if os.path.isfile(HOPS):
        for ln in io.open(HOPS, encoding='utf-8', newline=''):
            ln = ln.rstrip('\r\n')
            if ln.strip():
                hops.append(ln)

    # ---- 1. 场景变化时间线（人眼可读）----
    lines = [u'# t / frame / scene / chapter / rid / canvas / cam / scale / pos']
    prev = None
    for r in rows:
        cur = (r.get('scene'), r.get('chapter'), r.get('rid'), r.get('canvas_vis'),
               r.get('anim'), r.get('cam_w'), r.get('cam_h'), r.get('cam_scale'))
        if cur != prev:
            lines.append(u'f=%-5s t=%-8s scene=%-34s ch=%-8s rid=%-5s vis=%-6s '
                         u'anim=%-16s cam=%sx%s scale=%s cw=%s pos=(%s,%s)'
                         % (r.get('frame'), r.get('t'), r.get('scene') or u'<none>',
                            r.get('chapter'), r.get('rid'), r.get('canvas_vis'),
                            r.get('anim'), r.get('cam_w'), r.get('cam_h'),
                            r.get('cam_scale'), r.get('cw'), r.get('wx'), r.get('wy')))
            prev = cur
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'\n'.join(lines) + '\n')
    print(u'[shot106] 场景变化行数 = %d ⇒ %s' % (len(lines) - 1, OUT))

    # ---- 2. 从 CSV 里抽出"见过的场景序列"（产品字段）----
    seen = []
    for r in rows:
        s = r.get('scene')
        if s and (not seen or seen[-1] != s):
            seen.append(s)

    os_seen = [s for s in seen if s.startswith('oneshot.')]
    dl_seen = [s for s in seen if s.startswith('ch1.')]

    print()
    print(u'--- 录像里（产品报出的）场景序列 ---')
    for i, s in enumerate(seen, 1):
        print(u'  %2d. %s' % (i, s))
    print()

    # ---- 3. A 段 断言：非瞬移（每条都能失败）----
    # A1 起点确实摆到了 oneshot INIT
    ok(u'A1 录像中出现起点房间 %s' % OS_FROM, OS_FROM in seen,
       u'实际首见 oneshot 场景=%r' % (os_seen[:1],))

    # A2 终点到达
    ok(u'A2 录像中出现终点房间 %s' % OS_TO, OS_TO in seen)

    # A3 ★★★ **本轮靶心**：逐门走过（中间房间必须出现）。
    #   第105轮**同一条判据报红**（`INIT → S1` 一步到位）⇒ 本轮必须转 PASS。
    #   负控制：若退化成直达，`mid` 为空 ⇒ 必红。
    mid = [s for s in os_seen if s not in (OS_FROM, OS_TO)]
    ok(u'A3 ★★★ 逐门走过（oneshot 途经房间数 >= 1 —— 第105轮此条为 FAIL，'
       u'本轮应转 PASS）', len(mid) >= 1,
       u'途经 %d 间=%r' % (len(mid), mid[:8]))

    # A4 HOP 行数 >= 3（多跳 ⇒ 逐跳真的在换场景）
    ok(u'A4 HOP 行数 >= 3（INIT → … → S1 的多跳）', len(hops) >= 3,
       u'HOP=%d 行；首=%r；末=%r'
       % (len(hops), hops[0] if hops else u'', hops[-1] if hops else u''))

    # A4b ★ 逐跳数必须与产品日志的 hops 同量级（不是"走了两步意思一下"）
    #   实测产品报 18 跳（含首末）；录像里至少要看得到其中的一段。
    ok(u'A4b HOP 行数 >= 5（17 跳的路线至少要看得到 5 次换场景）', len(hops) >= 5,
       u'HOP=%d' % len(hops))

    # A5 既有 Deltarune 未受影响
    ok(u'A5 Deltarune 对照：起点 %s 出现' % DL_FROM, DL_FROM in seen)
    ok(u'A5b Deltarune 对照：终点（教堂）%s 出现' % DL_TO_SID, DL_TO_SID in seen)

    # A6 oneshot 房间里画布真的显示过
    vis_os = set()
    for r in rows:
        s = r.get('scene') or ''
        if s.startswith('oneshot.') and r.get('canvas_vis') in ('True', 'true'):
            vis_os.add(s)
    ok(u'A6 oneshot 房间里有 canvas_vis=True 的帧', len(vis_os) >= 1,
       u'可见房间=%r' % (sorted(vis_os)[:6],))

    # A7 场景确实换过（负控制：只停在起点则必红）
    ok(u'A7 本次录像换过场景（seen >= 4）', len(seen) >= 4,
       u'seen=%d 个' % len(seen))

    # ---- 4. B 段 断言：全屏化（**成对**放大 + 逻辑窗口不变）----
    cam_ws = [_i(r.get('cam_w')) for r in rows if _i(r.get('cam_w')) > 0]
    cam_hs = [_i(r.get('cam_h')) for r in rows if _i(r.get('cam_h')) > 0]
    scales = [_f(r.get('cam_scale')) for r in rows if _f(r.get('cam_scale')) is not None]

    ok(u'B1 相机 size 真被读到（>0）', bool(cam_ws) and bool(cam_hs),
       u'cam_w 取值集=%r' % (sorted(set(cam_ws))[:6],))
    ok(u'B2 相机 scale 真被读到（>0）', bool(scales),
       u'scale 取值集=%r' % (sorted(set(scales))[:6],))
    if cam_ws and scales:
        ok(u'B3 ★ 输出宽度 >= 改前基线 %d（全屏化只许更大）'
           % EXPECT_MIN_OUT_W, max(cam_ws) >= EXPECT_MIN_OUT_W,
           u'max(cam_w)=%d' % max(cam_ws))
        ok(u'B4 ★ scale >= 改前基线 %.1f（人物等比放大的唯一发生点）'
           % EXPECT_MIN_SCALE, max(scales) >= EXPECT_MIN_SCALE,
           u'max(scale)=%.3f' % max(scales))
        # ★★ B5 **逻辑窗口恒 320×240**：`scoped = size / scale`
        #   ⇒ 这是"相机可见范围不变、只是画得更大"的硬证据（成对写才对）。
        bad = []
        for r in rows:
            cw_, sc_ = _i(r.get('cam_w')), _f(r.get('cam_scale'))
            if cw_ > 0 and sc_:
                scoped_w = cw_ / sc_
                if abs(scoped_w - EXPECT_SCOPED[0]) > 0.5:
                    bad.append((r.get('frame'), cw_, sc_, round(scoped_w, 2)))
        ok(u'B5 ★★★ 逻辑窗口恒 %dx%d（size/scale ⇒ 可见范围不变）'
           % EXPECT_SCOPED, not bad,
           u'越界帧=%r' % (bad[:4],))
        # ★ B6 成对：cam_w/cam_h 与 scoped 两轴**同时**满足比例
        ratios = []
        for r in rows:
            cw_, ch_ = _i(r.get('cam_w')), _i(r.get('cam_h'))
            if cw_ > 0 and ch_ > 0:
                ratios.append(round(cw_ / float(ch_), 3))
        ok(u'B6 输出宽高比 = 4:3（1.333，禁非等比拉伸）',
           bool(ratios) and all(abs(x - 4.0 / 3.0) < 0.02 for x in ratios),
           u'归一化比值集=%r' % (sorted(set(ratios))[:5],))
    else:
        ok(u'B3~B6 相机字段可用', False, u'读不到 cam_w/scale ⇒ 无法验全屏化')

    # B7 画布尺寸与相机输出一致（画布真的按相机输出铺开）
    pairs = []
    for r in rows:
        cw_, ch_, cw2, ch2 = (_i(r.get('cam_w')), _i(r.get('cam_h')),
                              _i(r.get('cw')), _i(r.get('chh')))
        if cw_ > 0 and cw2 > 0:
            pairs.append((cw_, ch_, cw2, ch2))
    ok(u'B7 画布尺寸 == 相机输出尺寸（像素级同值）',
       bool(pairs) and all(a == c and b == d for a, b, c, d in pairs),
       u'样本=%r' % (pairs[:3],))

    # ---- 5. 注入日志（供人核对"我让它去哪 / 产品回报什么"）----
    if os.path.isfile(INJ):
        print()
        print(u'--- 注入日志（产品回报的 ret）---')
        for ln in io.open(INJ, encoding='utf-8', newline=''):
            ln = ln.rstrip('\r\n')
            if ln.strip():
                print(u'  ' + ln)

    # ---- 6. 对照图（录像取帧，人眼验收）----
    try:
        _make_sheet(rows, seen)
    except Exception as e:
        print(u'[shot106] 对照图生成失败（不致命）：%r' % (e,))

    npass = sum(1 for _n, c in R if c)
    nfail = len(R) - npass
    print()
    print(u'==== shot106 判据：%d PASS / %d FAIL ====' % (npass, nfail))
    return 0 if nfail == 0 else 1


def _make_sheet(rows, seen):
    u"""从 mp4 取"每个新场景的第一帧"拼成对照图（人眼验收）。"""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(RAW)
    if not cap.isOpened():
        print(u'[shot106] 打不开 %s（跳过对照图）' % RAW)
        return

    want = {}
    for r in rows:
        s = r.get('scene')
        if s and s not in want:
            try:
                want[s] = int(r.get('frame'))
            except Exception:
                pass
    picks = [(s, want[s]) for s in seen if s in want][:15]

    frames = []
    allf = []
    idx = 0
    maxf = max([f for _s, f in picks], default=-1)
    while idx <= maxf:
        got, fr = cap.read()
        if not got:
            break
        allf.append(fr)
        idx += 1
    cap.release()

    for s, f in picks:
        if 0 <= f < len(allf):
            frames.append((s, allf[f]))
    if not frames:
        print(u'[shot106] 取不到帧（跳过对照图）')
        return

    th = 150
    tiles = []
    for s, fr in frames:
        h, w = fr.shape[:2]
        tw = max(1, int(w * (th / float(h))))
        t = cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA)
        t = cv2.copyMakeBorder(t, 18, 0, 0, 2, cv2.BORDER_CONSTANT,
                               value=(30, 30, 30))
        tag = s.replace('oneshot.mainline.', 'os.').replace('ch1.', 'c1.')
        cv2.putText(t, tag[:26], (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                    (255, 230, 120), 1, cv2.LINE_AA)
        tiles.append(t)

    cols = 3
    rows_n = (len(tiles) + cols - 1) // cols
    cw = max(t.shape[1] for t in tiles)
    chh = max(t.shape[0] for t in tiles)
    sheet = np.full((rows_n * chh, cols * cw, 3), 24, np.uint8)
    for i, t in enumerate(tiles):
        rr, cc = divmod(i, cols)
        sheet[rr * chh:rr * chh + t.shape[0], cc * cw:cc * cw + t.shape[1]] = t

    _okc, buf = cv2.imencode('.png', sheet)
    if _okc:
        with open(SHEET, 'wb') as fh:
            fh.write(buf.tobytes())
        print(u'[shot106] 对照图 %s  (%d 格)' % (SHEET, len(tiles)))
    else:
        print(u'[shot106] 对照图编码失败')


if __name__ == '__main__':
    sys.exit(main())
