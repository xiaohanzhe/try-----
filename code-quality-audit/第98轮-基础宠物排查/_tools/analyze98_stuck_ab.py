# -*- coding: utf-8 -*-
u"""第98轮 A/B：『目标不可达兜底』到底有没有用。

夹具 = `REC98_INJECT_FAR`（把目标设到屏幕右边界外 200px，模拟"图标落在屏外 /
`set_target_pos` 给了越界坐标"）。判据只看**产品自己写进 CSV 的字段**：

  段 = 连续 `tx` 落在可达区外的帧（`tx > 屏宽 - 窗口宽`）；
  段内"还在走"的时长 = 最后一个 `moving=True` 帧的时刻 - 段起点时刻。

期望：
  · 修复**前**（`run_far_before`）：一直走 —— 只有注入下一次覆盖（18s）或
    AI 换目标才会停 ⇒ 单次卡住 **≥ 17s**；
  · 修复**后**（`run_far_after`）：连续 60 帧（≈1.8s @30ms）没位移就放弃
    ⇒ 单次卡住 **≤ ~2.5s**。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))


def rd(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def screen_of(d):
    m = re.search(r'(\d{3,5})\s*x\s*(\d{3,5})', rd(os.path.join(d, 'rec97_meta.txt')))
    return (int(m.group(1)), int(m.group(2))) if m else (2560, 1600)


def rows(d):
    txt = rd(os.path.join(d, 'rec97_frames.csv'))
    lines = [l for l in txt.split('\n') if l.strip()]
    hdr = [h.strip() for h in lines[0].split(',')]
    out = []
    for l in lines[1:]:
        p = l.split(',')
        if len(p) != len(hdr):
            continue
        x = dict(zip(hdr, p))
        try:
            x['frame'] = int(x['frame'])
            x['t'] = float(x['t'])
            x['ww'] = float(x['ww'])
            x['tx'] = float(x['tx'])
        except Exception:
            continue
        out.append(x)
    return out


def report(run):
    d = os.path.join(EV, run)
    if not os.path.isdir(d):
        print(u'  （缺 %s）' % run)
        return None
    sw, _sh = screen_of(d)
    rs = rows(d)
    segs = []
    cur = []
    for x in rs:
        if x['tx'] > sw - x['ww']:
            cur.append(x)
        else:
            if cur:
                segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    print(u'--- %s（%d 帧，屏宽 %d）' % (run, len(rs), sw))
    durs = []
    for s in segs:
        mv = [x for x in s if x.get('moving') == 'True']
        t0 = s[0]['t']
        t_end = mv[-1]['t'] if mv else t0
        dur = t_end - t0
        durs.append(dur)
        print(u'    target x=%.0f  越界 %+.0f px  段 %d 帧/%.1fs  其中"还在走" %.2fs'
              u'  动画=%s'
              % (s[0]['tx'], s[0]['tx'] - (sw - s[0]['ww']), len(s),
                 s[-1]['t'] - t0, dur,
                 ','.join(sorted(set(x['anim'] for x in mv)))))
    if durs:
        print(u'    ⇒ 单次卡住时长：max=%.2fs  min=%.2fs  段数=%d'
              % (max(durs), min(durs), len(durs)))
    return durs


def main():
    print('=' * 96)
    print(u'第98轮 A/B · 不可达目标注入（REC98_INJECT_FAR：目标设在屏外 200px）')
    print('=' * 96)
    a = report('run_far_before')
    print('')
    b = report('run_far_after')
    print('')
    print('=' * 96)
    if a and b:
        print(u'修复前 max=%.2fs  →  修复后 max=%.2fs   （判据：修复后应 <= 3s）'
              % (max(a), max(b)))
    elif b:
        print(u'修复后 max=%.2fs' % max(b))
    print('=' * 96)
    return 0


if __name__ == '__main__':
    sys.exit(main())
