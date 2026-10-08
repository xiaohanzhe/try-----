# -*- coding: utf-8 -*-
u"""第98轮：检查「漫游目标点是否落在可达区内」。

背景（本轮实证）：
  `run_inj_bow` f45-66 命中了「原地踏步」（11s 只挪 2px、动画 `walk_right`、
  `is_moving=True`）——但**那是我的注入夹具造的**：`REC98_INJECT_BOW` 的
  "边走边触发"分支直接写 `window.target_pos = QPoint(cur.x()+260, cur.y()-40)`，
  **没有做屏幕内夹紧** ⇒ 目标 (2635,1430) 落在 2560 宽的屏幕**外面** ⇒ 宠物一路
  向右、被 `update_movement` 的屏幕夹紧钉住 ⇒ 永远到不了目标 ⇒ 永远 `is_moving`。
  ⇒ **夹具不保真 = 报假问题**（第98轮教训）。

于是本脚本回答真正的问题：**产品自己选的漫游目标会不会落到可达区外？**
  可达区 = `[screen.left(), screen.right()-w] x [screen.top(), screen.bottom()-h]`
  （`update_movement` 用的就是这套夹紧，见 main.py L7220-7221）。
  判据只用**产品自己写进 CSV 的 `tx/ty`**（`target_pos`）+ 当时的窗口尺寸。

输出：每个录制里"目标不可达"的帧数与明细；自然录像（`run_natural*`）单独结论。
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


def screen_of(run_dir):
    """从 meta 里取屏幕尺寸（"屏幕 = 2560x1600"）。"""
    p = os.path.join(run_dir, 'rec97_meta.txt')
    if not os.path.exists(p):
        return None
    m = re.search(r'(\d{3,5})\s*x\s*(\d{3,5})', rd(p))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def load_rows(path):
    txt = rd(path)
    lines = [l for l in txt.split('\n') if l.strip()]
    hdr = [h.strip() for h in lines[0].split(',')]
    out = []
    for l in lines[1:]:
        parts = l.split(',')
        if len(parts) != len(hdr):
            continue
        d = dict(zip(hdr, parts))
        try:
            d['frame'] = int(d['frame'])
            d['t'] = float(d['t'])
            d['ww'] = float(d['ww'])
            d['wh'] = float(d['wh'])
            d['tx'] = float(d['tx'])
            d['ty'] = float(d['ty'])
        except Exception:
            continue
        out.append(d)
    return out


def main():
    runs = sorted(os.listdir(EV))
    grand_unreach = 0
    natural_rows = []
    print('=' * 96)
    print(u'第98轮 · 漫游目标可达性检查（不可达 = `tx/ty` 落在'
          u' [0, SW-w]x[0, SH-h] 之外）')
    print('=' * 96)
    for r in runs:
        d = os.path.join(EV, r)
        csvp = os.path.join(d, 'rec97_frames.csv')
        if not os.path.isdir(d) or not os.path.exists(csvp):
            continue
        scr = screen_of(d)
        rows = load_rows(csvp)
        if not scr or not rows:
            continue
        sw, sh = scr
        bad = []
        for x in rows:
            # ★★ 只在"正在走"时判可达：到达目标后 `is_moving=False` 而
            #    `target_pos` **不会重置**（见 main.py L7283-7295 的到达分支），
            #    残留的旧目标当然可能越界 ⇒ 不筛 `moving` 会造出大批**假阳性**
            #    （本脚本首版正是如此：`run_natural_postfix` 报 47 帧，
            #     逐帧核对后发现全部 `moving=False`）。
            if x.get('moving') != 'True':
                continue
            if not (0 <= x['tx'] <= sw - x['ww'] and 0 <= x['ty'] <= sh - x['wh']):
                bad.append(x)
        print('')
        print(u'--- %-24s 屏幕=%dx%d  采样=%d  行走中不可达帧=%d'
              % (r, sw, sh, len(rows), len(bad)))
        if bad:
            grand_unreach += len(bad)
            for x in bad[:6]:
                print(u'    frame %-4d t=%.2f  target=(%.0f,%.0f)  窗口=%.0fx%.0f'
                      u'  ⇒ 越界 x:%+.0f y:%+.0f'
                      % (x['frame'], x['t'], x['tx'], x['ty'], x['ww'], x['wh'],
                         max(x['tx'] - (sw - x['ww']), 0 - x['tx']),
                         max(x['ty'] - (sh - x['wh']), 0 - x['ty'])))
            if len(bad) > 6:
                print(u'    ...（其余 %d 帧同类）' % (len(bad) - 6))
        if r.startswith('run_natural'):
            natural_rows.append((r, len(rows), len(bad)))
    print('')
    print('=' * 96)
    print(u'合计不可达帧 = %d' % grand_unreach)
    for r, n, b in natural_rows:
        print(u'  ★ 自然录像 %-24s %d 帧中不可达 %d 帧  ⇒  %s'
              % (r, n, b, u'产品选目标安全' if b == 0 else u'产品会选到到不了的点'))
    print('=' * 96)
    return 0


if __name__ == '__main__':
    sys.exit(main())
