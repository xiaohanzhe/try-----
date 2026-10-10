# -*- coding: utf-8 -*-
u"""shot105.py —— 第105轮录制的**分析端**（用户口径「一定要看录像而不是只读后台输出」）。

读 `_evidence/rec105_frames.csv`（录制端每 250 ms 一行，列由**产品代码自己**填）
+ `rec105_hops.txt`（换场景那一刻的 HOP 行）+ `rec105_raw.avi`，输出：

  1. `rec105_timeline.txt` —— 只列**场景变化**的那些帧，人眼一眼读完；
  2. 断言块 —— 把"逐门走过去（不是直达）/ 既有 Deltarune 未受影响"在**录像数据**
     上再证一次（判据只看产品字段：`scene` / `hops` 行 / `canvas_vis`）；
  3. `rec105_contact_sheet.png` —— 从录像里取"起点房间 / 中途各房间 / 终点 / Deltarune
     对照"若干帧拼成一张对照图（★ 走 `imencode` + 手写，`cv2.imwrite` 在中文路径
     下静默失败）。

★ 纪律：判据**只看产品字段**，不从像素里"猜"状态；像素只用来给人眼看。
★ 判据不可恒真：每条都要有**失败的可能**（负控制见 §"负控制"注释）。
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.environ.get('REC105_EVDIR') or os.path.join(ROUND, '_evidence')
CSV = os.path.join(EV, 'rec105_frames.csv')
HOPS = os.path.join(EV, 'rec105_hops.txt')
INJ = os.path.join(EV, 'rec105_inject.txt')
RAW = os.path.join(EV, 'rec105_raw.avi')
OUT = os.path.join(EV, 'rec105_timeline.txt')
SHEET = os.path.join(EV, 'rec105_contact_sheet.png')

# 本轮要证的两个场景标签（与 rec105.py 的注入参数保持一致）
OS_FROM = os.environ.get('REC105_OS_FROM', 'oneshot.mainline.INIT')
OS_TO = os.environ.get('REC105_OS_TO', 'oneshot.mainline.S1')
DL_FROM = os.environ.get('REC105_DL_FROM', 'ch1.kris_room.kris_s_room')
DL_TO_SID = 'ch1.hometown.town_church'      # 教堂（产品自己解析出来的 scene_id）

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


def main():
    if not os.path.isfile(CSV):
        print('[shot105] 缺 %s' % CSV)
        return 2
    rows = _read_rows(CSV)
    print('[shot105] 帧数 = %d' % len(rows))
    if not rows:
        return 2

    hops = []
    if os.path.isfile(HOPS):
        for ln in io.open(HOPS, encoding='utf-8', newline=''):
            ln = ln.rstrip('\r\n')
            if ln.strip():
                hops.append(ln)

    # ---- 1. 场景变化时间线（人眼可读）----
    lines = [u'# t / frame / scene / chapter / rid / canvas_vis / pos / size']
    prev = None
    for r in rows:
        cur = (r.get('scene'), r.get('chapter'), r.get('rid'), r.get('canvas_vis'),
               r.get('anim'))
        if cur != prev:
            lines.append(u'f=%-5s t=%-8s scene=%-34s ch=%-8s rid=%-5s vis=%-6s '
                         u'anim=%-16s pos=(%s,%s) %sx%s'
                         % (r.get('frame'), r.get('t'), r.get('scene') or u'<none>',
                            r.get('chapter'), r.get('rid'), r.get('canvas_vis'),
                            r.get('anim'), r.get('wx'), r.get('wy'),
                            r.get('ww'), r.get('wh')))
            prev = cur
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'\n'.join(lines) + '\n')
    print(u'[shot105] 场景变化行数 = %d ⇒ %s' % (len(lines) - 1, OUT))

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

    # ---- 3. 断言（每条都能失败）----
    # A1 起点确实摆到了 oneshot INIT
    ok('A1 录像中出现起点房间 %s' % OS_FROM, OS_FROM in seen,
       u'实际首见 oneshot 场景=%r' % (os_seen[:1],))

    # A2 终点到达 —— 这是本轮的核心（图接上了才走得到）
    ok('A2 录像中出现终点房间 %s' % OS_TO, OS_TO in seen)

    # A3 ★ 逐门：中途必须经过 >=1 个 oneshot 房间。
    #    ★★★ 第105轮实测要证的就是这一条，而它**报红了**（这才是录屏的价值）：
    #      产品日志写「route=path，18 跳」—— 路线**算对了**；但 HOP 行里
    #      INIT → S1 是**一步到位**，中间 16 间房一帧都没出现过。
    #      根因：`scene_controller.travel_to()` 拿到 `plan['steps']` 后，
    #      **只调了一次 `switch(sid)`**（第892行），`steps` 抄进返回值就没了
    #      消费方（AST 实证：全仓无任何 `route_plan['steps']` 的遍历执行）。
    #      ⇒ 这是「**路径算出来了，但没人走**」—— 与第45轮 `follow_route`
    #      零调用是同一类坑的**第二形态**（那次是"没调用方"，这次是"调用方
    #      只走了一步"）。**如实报红，不粉饰。**
    #    负控制：若退化成直达，os_seen 长度 == 2 ⇒ 本判据必红（当轮正是如此）。
    mid = [s for s in os_seen if s not in (OS_FROM, OS_TO)]
    ok('A3 逐门走过（oneshot 途经房间数 >= 1）', len(mid) >= 1,
       u'途经=%r ｜ 产品日志 route=path 但 steps 无消费方（见 rec105_stdout.txt）'
       % (mid[:6],))

    # A4 HOP 行数与"看见的场景变化"对得上（同一件事的两处留痕，互为对账）
    ok('A4 HOP 行数 >= 3（INIT → … → S1 的多跳）', len(hops) >= 3,
       u'HOP=%d 行；首行=%r' % (len(hops), hops[0] if hops else u''))

    # A5 既有 Deltarune 未受影响：ch1 起点与教堂都出现过
    ok('A5 Deltarune 对照：起点 %s 出现' % DL_FROM, DL_FROM in seen)
    ok('A5b Deltarune 对照：终点（教堂）%s 出现' % DL_TO_SID, DL_TO_SID in seen)

    # A6 画布真的显示过（canvas_vis True 至少出现在 oneshot 房间里）
    vis_os = set()
    for r in rows:
        s = r.get('scene') or ''
        if s.startswith('oneshot.') and r.get('canvas_vis') in ('True', 'true'):
            vis_os.add(s)
    ok('A6 oneshot 房间里有 canvas_vis=True 的帧', len(vis_os) >= 1,
       u'可见房间=%r' % (sorted(vis_os)[:6],))

    # A7 场景确实换过（不是一动不动）—— 负控制：只停在起点则必红
    ok('A7 本次录像换过场景（seen >= 4）', len(seen) >= 4,
       u'seen=%d 个' % len(seen))

    # ---- 4. 读出注入日志（供人核对"我让它去哪 / 产品回报什么"）----
    if os.path.isfile(INJ):
        print()
        print(u'--- 注入日志（产品回报的 ret）---')
        for ln in io.open(INJ, encoding='utf-8', newline=''):
            ln = ln.rstrip('\r\n')
            if ln.strip():
                print(u'  ' + ln)

    # ---- 5. 对照图（录像取帧）----
    try:
        _make_sheet(rows, seen)
    except Exception as e:
        print(u'[shot105] 对照图生成失败（不致命）：%r' % (e,))

    npass = sum(1 for _n, c in R if c)
    nfail = len(R) - npass
    print()
    print(u'==== shot105 判据：%d PASS / %d FAIL ====' % (npass, nfail))
    return 0 if nfail == 0 else 1


def _make_sheet(rows, seen):
    u"""从 mp4 取"每个新场景的第一帧"拼成对照图（人眼验收）。"""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(RAW)
    if not cap.isOpened():
        print(u'[shot105] 打不开 %s（跳过对照图）' % RAW)
        return

    # 采样点：每个"场景第一次出现"对应的帧号
    want = {}
    for r in rows:
        s = r.get('scene')
        if s and s not in want:
            try:
                want[s] = int(r.get('frame'))
            except Exception:
                pass
    picks = [(s, want[s]) for s in seen if s in want][:12]

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
        print(u'[shot105] 取不到帧（跳过对照图）')
        return

    # 缩到 1/4 宽，横排 4 列
    th = 160
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
        print(u'[shot105] 对照图 %s  (%d 格)' % (SHEET, len(tiles)))
    else:
        print(u'[shot105] 对照图编码失败')


if __name__ == '__main__':
    sys.exit(main())
