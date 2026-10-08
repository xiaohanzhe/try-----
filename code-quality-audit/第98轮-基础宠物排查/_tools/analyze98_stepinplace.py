# -*- coding: utf-8 -*-
u"""第98轮：扫描全部录制，找「原地踏步」。

用户第98轮口径（第 3 条）：
  「他还有**原地踏步**的问题，你自己看看」

定义（用户视角）：走路/跑步动画在播（`is_moving=True`），但宠物的屏幕位置**不动**
  ⇒ 屏幕上是"腿在迈、人没走"。

★ 判据的两次自我修正（都写下来，免得后人再踩）
------------------------------------------------
  **第一次（v1）**：按"连续 `walk_*` 帧"切段，再看**整段**的窗口位置跨度 ≤3px。
    ⚠️ 漏报：一整段里只要**夹过一次移动**（AI 换了目标、走向别处），整段跨度就被
    撑大 ⇒ **段内局部静止被淹没**。
    实证：`run_far_before` f24-f49 明明是"wx=2521 / wy=1374 **完全不动** 12.5 秒、
    动画 `walk_right`、`is_moving=True`、target 越界 237px"的原地踏步，v1 却报"无"
    ——因为它把 f11-f109 合成一段（跨度 x=614 y=483）。
    ⇒ **判据也是被测物**（本项目第 N 次栽在判据侧）。

  **第二次（v2，本文件）**：改成**与动画无关**的"静止段"判据：
    ① 按"逐帧窗口位移 ≤ `TOL`(1px)"把帧切成**静止段**（位置不动才续段）；
    ② 段内**走路家族动画占比 ≥ `WALK_RATIO`(0.3)** 且段时长 ≥ `MIN_SEC`(1.0s)
       ⇒ 判「原地踏步」。
    为什么加"占比"：**正常待机**也是"位置不动"，但动画是 `idle` ⇒ 占比 0 ⇒ 不报；
    而"到达目标瞬间夹了 1 帧 `walk_*`"（真实录像里常见）占比 ~4% ⇒ 也不报。

量取用**窗口中心** `cx = wx + ww/2`（避开容器尺寸变化带来的"保中心 resize"抖动）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
TOL = 1.0          # 逐帧窗口位移 <= 1px 视为"没动"
MIN_SEC = 1.0      # 静止段最短时长
WALK_RATIO = 0.3   # 段内走路动画占比下限
WALK_PREFIX = ('walk_', 'run_')


def rd(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def load_rows(path):
    txt = rd(path)
    lines = [l for l in txt.split('\n') if l.strip()]
    if not lines:
        return []
    hdr = [h.strip() for h in lines[0].split(',')]
    out = []
    for l in lines[1:]:
        p = l.split(',')
        if len(p) != len(hdr):
            continue
        d = dict(zip(hdr, p))
        try:
            d['frame'] = int(d['frame'])
            d['t'] = float(d['t'])
            d['wx'] = float(d['wx'])
            d['wy'] = float(d['wy'])
            d['ww'] = float(d['ww'])
            d['wh'] = float(d['wh'])
        except Exception:
            continue
        out.append(d)
    return out


def still_runs(rows, tol=TOL):
    """按"逐帧窗口位置几乎不变"切段（与 `anim` 无关）。"""
    segs = []
    if not rows:
        return segs
    cur = [rows[0]]
    for r in rows[1:]:
        if (abs(r['wx'] - cur[-1]['wx']) <= tol
                and abs(r['wy'] - cur[-1]['wy']) <= tol):
            cur.append(r)
        else:
            segs.append(cur)
            cur = [r]
    segs.append(cur)
    return segs


def hits_of(rows):
    """返回"原地踏步"段列表（判据见文件头）。"""
    hits = []
    for seg in still_runs(rows):
        dur = seg[-1]['t'] - seg[0]['t']
        n = len(seg)
        nwalk = sum(1 for x in seg if (x.get('anim') or '').startswith(WALK_PREFIX))
        ratio = nwalk / float(n) if n else 0.0
        if dur >= MIN_SEC and ratio >= WALK_RATIO:
            hits.append(dict(f0=seg[0]['frame'], f1=seg[-1]['frame'],
                             t0=seg[0]['t'], t1=seg[-1]['t'], dur=dur, n=n,
                             ratio=ratio,
                             anims=sorted(set(x['anim'] for x in seg)),
                             mv=seg[0].get('moving'),
                             tgt=(seg[0].get('tx'), seg[0].get('ty')),
                             pos=(seg[0]['wx'], seg[0]['wy'])))
    hits.sort(key=lambda h: -h['dur'])
    return hits


def main():
    runs = sorted(os.listdir(EV))
    total = 0
    grand = []
    print('=' * 100)
    print(u'第98轮 · 原地踏步扫描 v2（静止段：逐帧位移<=%.0fpx 且 >=%.1fs 且'
          u' 走路动画占比>=%.0f%%）' % (TOL, MIN_SEC, WALK_RATIO * 100))
    print('=' * 100)
    for r in runs:
        d = os.path.join(EV, r)
        csvp = os.path.join(d, 'rec97_frames.csv')
        if not os.path.isdir(d) or not os.path.exists(csvp):
            continue
        rows = load_rows(csvp)
        hits = hits_of(rows)
        nstill = len([s for s in still_runs(rows)
                      if s[-1]['t'] - s[0]['t'] >= MIN_SEC])
        print('')
        print(u'--- %-22s 采样 %d 帧｜静止段(>=%.0fs) %d 个｜停留时长合计 %.1fs｜原地踏步 %d 段'
              % (r, len(rows), MIN_SEC, nstill,
                 sum(s[-1]['t'] - s[0]['t'] for s in still_runs(rows)
                     if s[-1]['t'] - s[0]['t'] >= MIN_SEC),
                 len(hits)))
        for h in hits:
            total += 1
            grand.append((r, h))
            print(u'    ★ frame %d-%d  t=%.2f~%.2f（%.2fs / %d 帧）  '
                  u'pos=(%.0f,%.0f)  walking 占比 %.0f%%  mv=%s  target=(%s,%s)  %s'
                  % (h['f0'], h['f1'], h['t0'], h['t1'], h['dur'], h['n'],
                     h['pos'][0], h['pos'][1], h['ratio'] * 100, h['mv'],
                     h['tgt'][0], h['tgt'][1], ','.join(h['anims'])))
    print('')
    print('=' * 100)
    print(u'合计「原地踏步」段 = %d' % total)
    for r, h in grand:
        print(u'   %-22s %.2fs  target=%s' % (r, h['dur'], h['tgt']))
    print('=' * 100)
    return 0


if __name__ == '__main__':
    sys.exit(main())
