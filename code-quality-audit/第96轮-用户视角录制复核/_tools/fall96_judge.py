# -*- coding: utf-8 -*-
u"""fall96_judge.py —— 坠落专项判据（读 probe96_fall.txt）

背景：主录制 610 s 里 `is_falling=True` 只有 0 帧 ⇒ F7 无法验证。
     本判据处理**专项录制**（同时触发 `start_fall` 摔倒 与 `start_falling` 重力坠落）。

★★★ 关键教训（首版我犯的错）：
    `start_fall` 是**摔倒**（原地跌倒→摔扁→揉头→爬起），它自己就把 `is_moving=False`
    ⇒ **y 本来就不该大幅变化**。拿"y 应向下增大"去判摔倒 ⇒ 得出"向上 37/向下 9"的**假红**。
    ⇒ 两种坠落必须**分开判**，各用各的模型：
      · 摔倒   `is_falling`        ：判**相位链完整**（fall→splat→dazed→recovering）+ 能结束
      · 重力坠落 `is_gravity_falling`：判**单调向下** + **加速**（回应第90轮「只有跳没有上去」）

运行：C:/Python311/python.exe -X utf8 _tools/fall96_judge.py
输出：_evidence/fall96_judge.txt
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')

_LINE = re.compile(
    r'^\s*(?P<t>[\d.]+) y=\s*(?P<y>-?\d+) x=\s*(?P<x>-?\d+) (?P<anim>\S+)\s+'
    r'(?P<dir>\S+)\s+fall=(?P<fall>True|False)\s+grav=(?P<grav>True|False)\s+'
    r'splat=(?P<splat>True|False)\s+phase=(?P<phase>\S+)\s+vy=(?P<vy>\S+)', re.M)


def main():
    p = os.path.join(EV, 'probe96_fall.txt')
    txt = io.open(p, encoding='utf-8', newline='').read() if os.path.exists(p) else ''
    rows = []
    for m in _LINE.finditer(txt):
        g = m.groupdict()
        rows.append(dict(t=float(g['t']), y=int(g['y']), x=int(g['x']),
                         anim=g['anim'], dir=g['dir'],
                         fall=(g['fall'] == 'True'), grav=(g['grav'] == 'True'),
                         splat=(g['splat'] == 'True'), phase=g['phase']))
    out = []
    A = out.append
    A(u'# fall96_judge —— 坠落专项判据（读 probe96_fall.txt）')
    A(u'# 采样帧数：%d' % len(rows))
    A(u'=' * 84)

    n_pass = n_fail = 0

    def chk(ok, name, detail):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        A(u'[%s] %s  —— %s' % (u'PASS' if ok else u'FAIL', name, detail))

    # ---------- 1) 摔倒线（`is_falling`）----------
    A(u'')
    A(u'=== 摔倒线（`start_fall` ⇒ `is_falling`）：判**相位链完整 + 能结束** ===')
    fsegs, cur = [], []
    for r in rows:
        if r['fall']:
            cur.append(r)
        else:
            if cur:
                fsegs.append(cur)
                cur = []
    if cur:
        fsegs.append(cur)
    A(u'  摔倒段数：%d' % len(fsegs))
    phases_all = set()
    ended = 0
    for k, s in enumerate(fsegs, 1):
        ph = []
        for r in s:
            if not ph or ph[-1] != r['phase']:
                ph.append(r['phase'])
        an = []
        for r in s:
            if not an or an[-1] != r['anim']:
                an.append(r['anim'])
        phases_all.update([x for x in ph if x != 'None'])
        A(u'   段%d t=%.2f~%.2f 帧%d  相位=%s  动画=%s'
          % (k, s[0]['t'], s[-1]['t'], len(s), u'→'.join(ph), u'→'.join(an)))
        # 段结束 = 后一帧 fall=False（即不在摔倒态）
        idx_last = rows.index(s[-1])
        if idx_last + 1 < len(rows) and not rows[idx_last + 1]['fall']:
            ended += 1
    chk(len(fsegs) >= 1, u'F7s-a 摔倒确实触发过', u'%d 段' % len(fsegs))
    # 相位链：至少要看到 splat 与 recovering（摔扁 + 恢复）
    chk(u'splat' in phases_all and u'recovering' in phases_all,
        u'F7s-b 摔倒**相位链完整**（含 splat 摔扁 + recovering 爬起）',
        u'覆盖相位=%s' % sorted(phases_all))
    chk(ended == len(fsegs) and len(fsegs) >= 1,
        u'F7s-c 摔倒**能结束**（不卡在摔倒态）',
        u'%d / %d 段正常结束' % (ended, len(fsegs)))

    # ---------- 2) 重力坠落线（`is_gravity_falling`）----------
    A(u'')
    A(u'=== 重力坠落线（`start_falling` ⇒ `is_gravity_falling`）：判**单调向下 + 加速** ===')
    gsegs, cur = [], []
    for r in rows:
        if r['grav']:
            cur.append(r)
        else:
            if cur:
                gsegs.append(cur)
                cur = []
    if cur:
        gsegs.append(cur)
    A(u'  重力坠落段数：%d' % len(gsegs))
    all_mono = True
    all_accel = True
    for k, s in enumerate(gsegs, 1):
        ys = [r['y'] for r in s]
        ds = [ys[i] - ys[i - 1] for i in range(1, len(ys))]
        nd = len([d for d in ds if d > 0])
        nu = len([d for d in ds if d < 0])
        mono = all(d >= 0 for d in ds)
        accel = (ds == sorted(ds))
        A(u'   段%d t=%.2f~%.2f 帧%d  y %d→%d（Δ=%+d）  向下 %d / 向上 %d  '
          u'单调向下=%s 逐步加速=%s'
          % (k, s[0]['t'], s[-1]['t'], len(s), ys[0], ys[-1], ys[-1] - ys[0],
             nd, nu, mono, accel))
        A(u'        Δy 序列：%s' % ds)
        if not mono:
            all_mono = False
        if not accel:
            all_accel = False
    chk(len(gsegs) >= 1, u'F7g-a 重力坠落确实触发过', u'%d 段' % len(gsegs))
    chk(all_mono and len(gsegs) >= 1,
        u'F7g-b ★★★ 重力坠落 **单调向下**（Δy ≥ 0 全程）',
        u'全部 %d 段单调向下=%s' % (len(gsegs), all_mono))
    chk(all_accel and len(gsegs) >= 1,
        u'F7g-c ★★★ 重力坠落 **逐步加速**（Δy 递增 ⇒ 真的是"掉下去"）'
        u' —— 直接回应第90轮「**跳上去窗口也只有跳没有上去**」',
        u'全部 %d 段加速=%s' % (len(gsegs), all_accel))
    # 净下落幅度
    if gsegs:
        tot = sum(s[-1]['y'] - s[0]['y'] for s in gsegs)
        chk(tot > 50,
            u'F7g-d 重力坠落**净下落幅度**显著（> 50 px）',
            u'累计净下落 %d px' % tot)

    A(u'')
    A(u'=' * 84)
    A(u'合计：PASS=%d  FAIL=%d  判据=%d' % (n_pass, n_fail, n_pass + n_fail))
    A(u'=' * 84)
    body = u'\n'.join(out) + u'\n'
    io.open(os.path.join(EV, 'fall96_judge.txt'), 'w',
            encoding='utf-8', newline='\n').write(body)
    print(body)
    return 1 if n_fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
