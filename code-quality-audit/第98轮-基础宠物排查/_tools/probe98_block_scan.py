# -*- coding: utf-8 -*-
u"""第98轮：在**分诊探针**上扫"连续不动"的段，并列出当时的拦截标志。

为什么还要这一步（`analyze98_stepinplace.py` 已经扫过一遍）：
  那份判据把"连续 `walk_*` + `is_moving=True`"当作**一个段**，中途只要夹一帧
  `idle`（滑步修复后很常见：走路↔待机切换）就会**断成两段**，于是 ≥1s 的判据
  可能整段跨不过去 ⇒ **真卡住也可能扫不出来**。
  这里换一个与动画**无关**的判据：**连续 ≥ N 帧窗口位置完全不变**，
  再看那些帧的 `anim` 与"拦截标志"（拖拽/追鼠标/特殊动画锁/施法/躲猫猫/
  缓冲减速/睡眠），就能分清"产品卡住"还是"某个分支正常接管了移动"。

用法：python probe98_block_scan.py <evidence目录名> [min_frames]
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVROOT = os.path.normpath(os.path.join(HERE, '..', '_evidence'))

_RE = re.compile(
    r"t=([\d.]+) anim=(\S+) dir=(\S+) mv=(\S+) wx=(-?\d+) wy=(-?\d+) "
    r"ww=(\d+) wh=(\d+) tgt=\(([^,]+),([^)]+)\) spd=(\S+) v=\(([^,]+),([^)]+)\) \| "
    r"drag=(\S+) dmouse=(\S+) fmouse=(\S+) ffile=(\S+) special=(\S+) spell=(\S+) "
    r"hide=(\S+) play=(\S+) brake=(\S+) sleep=(\S+) swalk=(\S+)")


def parse(path):
    rows = []
    for line in io.open(path, encoding='utf-8', newline='').read().split('\n'):
        m = _RE.search(line)
        if not m:
            continue
        g = m.groups()
        rows.append(dict(
            t=float(g[0]), anim=g[1].strip("'"), dir=g[2].strip("'"),
            mv=g[3], wx=int(g[4]), wy=int(g[5]), ww=int(g[6]), wh=int(g[7]),
            tx=g[8], ty=g[9], spd=g[10], vx=g[11], vy=g[12],
            drag=g[13], dmouse=g[14], fmouse=g[15], ffile=g[16],
            special=g[17], spell=g[18], hide=g[19], play=g[20],
            brake=g[21], sleep=g[22], swalk=g[23]))
    return rows


def main():
    run = sys.argv[1]
    nmin = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    path = os.path.join(EVROOT, run, 'rec98_block_probe.txt')
    if not os.path.exists(path):
        print('缺 %s（本轮录制需 REC98_PROBE_BLOCK=1）' % path)
        return 1
    rows = parse(path)
    print('=' * 100)
    print(u'%s：探针 %d 行，扫"连续 >=%d 帧窗口位置完全不变"的段' % (run, len(rows), nmin))
    print('=' * 100)
    segs = []
    cur = []
    for r in rows:
        if cur and (r['wx'], r['wy']) == (cur[-1]['wx'], cur[-1]['wy']):
            cur.append(r)
        else:
            if len(cur) >= nmin:
                segs.append(cur)
            cur = [r]
    if len(cur) >= nmin:
        segs.append(cur)
    if not segs:
        print(u'  没有任何 >=%d 帧的静止段' % nmin)
    for s in segs:
        anims = sorted(set(x['anim'] for x in s))
        flags = set()
        for x in s:
            if x['drag'] == 'True':
                flags.add('拖拽')
            if x['dmouse'] == 'True':
                flags.add('鼠标拖')
            if x['fmouse'] == 'True':
                flags.add('追鼠标')
            if x['ffile'] == 'True':
                flags.add('追文件')
            if x['special'] == 'True':
                flags.add('特殊动画锁')
            if x['spell'] not in ('None', '-'):
                flags.add('施法')
            if x['hide'] not in ('None', '-'):
                flags.add('躲猫猫')
            if x['play'] == 'True':
                flags.add('游戏中')
            if x['brake'] == 'True':
                flags.add('缓冲减速')
            if x['sleep'] == 'True':
                flags.add('睡眠')
            if x['swalk'] == 'True':
                flags.add('梦游')
        walkish = any(a.startswith(('walk_', 'run_')) for a in anims)
        print(u'  t=%.2f~%.2f（%.2fs / %d 帧）  pos=(%d,%d)  动画=%s  mv=%s  |v|=%s'
              % (s[0]['t'], s[-1]['t'], s[-1]['t'] - s[0]['t'], len(s),
                 s[0]['wx'], s[0]['wy'], ','.join(anims), s[0]['mv'],
                 s[0]['spd']))
        print(u'      target=(%s,%s)  拦截标志=%s  %s'
              % (s[0]['tx'], s[0]['ty'], sorted(flags),
                 u'  ← ★★★ 走路动画却在原地（疑似原地踏步）' if walkish else u''))
    print('')
    # 顺带统计：整段里"walk 家族且窗口不动"累计帧数
    n_walk_still = sum(1 for r in rows
                       if r['anim'].startswith(('walk_', 'run_'))
                       and r['vx'].strip("'") in ('0.000000', '0.0'))
    print(u'全段：anim 属 walk/run 且 vx==0 的帧数 = %d / %d' % (n_walk_still, len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
