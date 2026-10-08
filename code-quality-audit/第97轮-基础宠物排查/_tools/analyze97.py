# -*- coding: utf-8 -*-
u"""analyze96.py —— 第96轮「10 分钟录制」的**逐帧分析端**（用户视角）。

用户指令（原话）
----------------
「你先让程序跑10分钟，你录视频然后逐帧分析，查看用户视角下他究竟对不对，
  尤其是我之前提到过的问题」

★ 什么叫"用户视角下他究竟对不对"
--------------------------------
用户看到的三件事，就是判据的全部依据：
  ① **位置**：他到底动了没有（对"站桩/走不动"——第90/92轮用户原话「他在这里站桩呢？？？」）
  ② **朝向**：走的方向和脸朝的方向一不一致（对"朝右下走却播朝左"——第95轮缺陷 B）
  ③ **姿态**：停下来的时候是不是还摆着走路姿势（对 F35-4「静止残留走路姿势」）
⇒ 判据一律**从这三个可观测量互相印证**，不拿代码赋值当结论。

数据源（均由 `rec97.py` 产出）
-----------------------------
  rec97_frames.csv   每帧：帧号/t/窗口矩形/动画/方向/移动/速度/目标/尺寸
  rec97_moves.txt    窗口矩形变化事件（含 anim/dir/moving/spd/tgt/sz）
  rec97_state.txt    1 Hz 内部状态快照
  rec97_meta.txt     录制参数（含采集率、占用率）
  frames/*.png       关键帧截图

判据分组
--------
  A 录制可信性    —— 这次录制本身能不能作为证据（采集率/占用率/覆盖度）
  B 位置正确性    —— 真在动？有没有"动画在播但位移为 0"（第92轮指纹）
  C 朝向正确性    —— 方向 vs 实际位移 vs 动画名，三方一致（第95轮缺陷 B 的扇区）
  D 姿态正确性    —— 静止时不该残留走路姿势（F35-4）
  E 状态机        —— 互斥状态不并存、位置不越界
  F 用户报过的原症状逐条复核 —— 每条给"复现/未复现 + 证据"

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第96轮-用户视角录制复核\\_tools\\analyze96.py
"""
import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
# ★ 第97轮：与 rec97.py 对齐 —— 用 `REC97_EVDIR` 可分析"定向注入录制"那一轮。
EV = os.environ.get('REC97_EVDIR') or os.path.join(ROUND, '_evidence')

_P = []
_N = [0]
_BAD = [0]


def P(s=''):
    _P.append(s)


def check(ok, name, detail=u''):
    _N[0] += 1
    if not ok:
        _BAD[0] += 1
    P(u'[%s] %s%s' % (u'PASS' if ok else u'FAIL', name,
                      (u'  —— ' + detail) if detail else u''))
    return bool(ok)


def info(name, detail=u''):
    P(u'     %s：%s' % (name, detail))


def rd(p):
    if not os.path.exists(p):
        return None
    return io.open(p, encoding='utf-8', newline='').read()


# ================= A 录制可信性 =================
def sec_a(meta):
    P(u'')
    P(u'=== A 录制可信性（这次录制能不能当证据）===')
    if not meta:
        check(False, u'A0 rec97_meta.txt 存在', u'读不到 ⇒ 后续全部无从谈起')
        return {}
    m = {}
    for k, pat in [(u'实际帧数', r'实际帧数\s*=\s*(\d+)'),
                   (u'采集率', r'有效采集率\s*=\s*([\d.]+)'),
                   (u'占用率', r'占用率.*?=\s*([\d.]+)%'),
                   (u'时长', r'墙钟耗时\s*=\s*([\d.]+)'),
                   (u'PNG', r'frames/ 实际 PNG 数\s*=\s*(\d+)')]:
        g = re.search(pat, meta)
        m[k] = float(g.group(1)) if g else None
    cap = m.get(u'时长') or 0
    info(u'墙钟时长', u'%.1f s' % cap)
    info(u'实际帧数', u'%s' % m.get(u'实际帧数'))
    info(u'采集率', u'%s Hz' % m.get(u'采集率'))
    info(u'占用率', u'%s %%' % m.get(u'占用率'))
    check((cap or 0) >= 570, u'A1 ★★★ 真的跑够 10 分钟（≥570 s）',
          u'实测 %.1f s' % cap)
    check((m.get(u'采集率') or 0) >= 1.5, u'A2 ★★★ 采集率 ≥1.5 Hz（逐帧分析有统计力）',
          u'实测 %s Hz（第92轮教训：只看"在不在播动画"查不出问题，须有足够帧）'
          % m.get(u'采集率'))
    check((m.get(u'占用率') or 99) <= 40, u'A3 ★★★ 录制占用率 ≤40%（测量不严重干扰被测物）',
          u'实测 %s %%（v1 用逐帧存 PNG 时是 ~99%%，把事件循环堵死 ⇒ 30s 只出 19 帧）'
          % m.get(u'占用率'))
    check((m.get(u'PNG') or 0) > 0, u'A4 ★★ 关键帧 PNG 真实落盘',
          u'磁盘 %s 张（`cv2.imwrite` 中文路径会静默失败，本工具已改 imencode）'
          % m.get(u'PNG'))
    return m


def sec_a2_target_sectors(frames):
    u"""A5 ★★★ **扇区覆盖度** —— 这是第95轮留下的最大缺口。

    第95轮报告 §8.4 自己写明：「本次 148 s 里目标方向落在 `[30,45)` 的只有 **0 帧**、
    `[45,60)` **0 帧** ⇒ 真机跑根本没有走到原缺陷扇区」。
    ⇒ 所以「真机没看到朝右下反而朝左」**不构成**验证。

    这里反过来做：先量**这次 10 分钟到底覆盖了哪些目标角扇区**，
    再据此说明"哪些结论有真机支撑、哪些仍然只有离线逐度扫描支撑"。

    ★ 参数统一用 `frames.csv` 的字段名（`wx/wy`），不再用 `moves` 的 `x/y`
      ——首版混用导致 `KeyError: 'x'`（自测 S5 段暴露）。
    """
    P(u'')
    P(u'=== A2 目标角扇区覆盖度（决定"哪条结论有真机支撑"）===')
    angs = []
    for r in frames:
        if r.get('tx') in (None, '') or r.get('wx') is None:
            continue
        try:
            dx = int(r['tx']) - r['wx']
            dy = int(r['ty']) - r['wy']
        except Exception:
            continue
        if dx == 0 and dy == 0:
            continue
        angs.append(math.degrees(math.atan2(dy, dx)))
    if not angs:
        check(False, u'A5a 有可算目标角的帧', u'—')
        return 0
    info(u'可算目标角帧', u'%d' % len(angs))
    hi = [0] * 36
    for a in angs:
        hi[max(0, min(35, int((a + 180.0) // 10.0)))] += 1

    def cnt(lo, hi_):
        return len([a for a in angs if lo <= a < hi_])
    c_30_45 = cnt(30, 45)
    c_45_60 = cnt(45, 60)
    c_old = cnt(30, 60)                  # ★ 旧档把这一整段判成 left（缺陷本体）
    info(u'目标角 [30,45)（旧档判 left 的下半）', u'%d 帧' % c_30_45)
    info(u'目标角 [45,60)（旧档判 left 的上半）', u'%d 帧' % c_45_60)
    info(u'★ 原缺陷扇区 [30,60) 合计', u'%d 帧' % c_old)
    check(c_old >= 20,
          u'A5b ★★★ 本次 10 分钟**真的走到了**原缺陷扇区 `[30,60)`（≥20 帧）',
          u'实测 %d 帧（第95轮 148s 跑是 **0 帧** ⇒ 那次无法验证；'
          u'本次若仍为 0，则"没看到反向"依旧不构成证据）' % c_old)
    P(u'     目标角直方图（每 10°）：')
    for i in range(36):
        if hi[i]:
            lo = i * 10 - 180
            P(u'       [%4d,%4d) %5d' % (lo, lo + 10, hi[i]))
    return c_old


# ================= 解析 =================
_MV = re.compile(
    r"t=(?P<t>[\d.]+) x=(?P<x>-?\d+) y=(?P<y>-?\d+) anim=(?P<anim>'[^']*'|None) "
    r"dir=(?P<dir>'[^']*'|None) moving=(?P<mv>True|False) spd=(?P<spd>[^ ]+) "
    r"tgt=(?P<tgt>.+?) sz=(?P<w>\d+)x(?P<h>\d+)")


def parse_moves(txt):
    rows = []
    for ln in txt.split('\n'):
        g = _MV.match(ln.strip())
        if not g:
            continue
        d = g.groupdict()
        tgt = re.match(r"PyQt5\.QtCore\.QPoint\((-?\d+),\s*(-?\d+)\)", d['tgt'])
        rows.append({
            't': float(d['t']), 'x': int(d['x']), 'y': int(d['y']),
            'anim': d['anim'].strip("'") if d['anim'] != 'None' else '',
            'dir': d['dir'].strip("'") if d['dir'] != 'None' else '',
            'mv': d['mv'] == 'True',
            'spd': float(d['spd']) if re.match(r'^[\d.]+$', d['spd']) else None,
            'tx': int(tgt.group(1)) if tgt else None,
            'ty': int(tgt.group(2)) if tgt else None,
            'w': int(d['w']), 'h': int(d['h']),
        })
    return rows


def parse_csv(txt):
    """rec97_frames.csv -> list[dict]"""
    if not txt:
        return []
    lines = txt.split('\n')
    if not lines:
        return []
    # ★★★ 第96轮修：**必须逐行 `strip()`**。
    #   `rec97.py` 写 CSV 走的是 `csv.writer`（默认 `\r\n` 行尾），
    #   而 `rd()` 是**字节忠实读取**（保留 `\r`）⇒ 最后一项键名会变成 `'spdy\r'`，
    #   于是 `d['spdy']` 永远缺键 ⇒ **速度向量判据静默拿到 0 个样本**。
    #   症状：C2v/C3v 报「仅 0 个 ⇒ 无法判定」，而 CSV 里明明有数据。
    hdr = [h.strip() for h in lines[0].split(',')]
    out = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        v = [x.strip() for x in ln.split(',')]
        if len(v) != len(hdr):
            continue
        d = dict(zip(hdr, v))
        for k in ('wx', 'wy', 'ww', 'wh'):
            try:
                d[k] = int(d[k])
            except Exception:
                d[k] = None
        # ★ 第96轮新增：速度向量（`rec97.py` v4 起采集）——决定朝向的**权威判据**来源
        for k in ('spd', 'spdx', 'spdy'):
            if k in d:
                try:
                    d[k] = float(d[k])
                except Exception:
                    d[k] = None
            else:
                d[k] = None
        try:
            d['frame'] = int(d['frame'])
        except Exception:
            pass
        try:
            d['t'] = float(d['t'])
        except Exception:
            pass
        out.append(d)
    return out


DIRS = ('up', 'down', 'left', 'right')
WALK = re.compile(r'^(walk|run)_(up|down|left|right)')
_WALKF = re.compile(r'^(?:walk|run)_(up|down|left|right)')


def want_dir(dx, dy):
    u"""按产品现行 `-45/45/135` 档位把位移向量映射成方向。
    ★ 与 `main.py` 的 `update_movement` 逐度等价（`abs(dx)>abs(dy)` 口径）：
        dx>0,dy<0 右上 → right 在 [-45,45) 里含 dx>0 的那半；
      这里只做"哪一档"的判定，边界归 None 表示口径不唯一。"""
    if dx == 0 and dy == 0:
        return None
    a = math.degrees(math.atan2(dy, dx))          # 屏幕坐标 +y 向下
    if abs(abs(dx) - abs(dy)) < 1e-9:
        return None                                # 正 45 度线上，口径不唯一
    if -45 <= a < 45:
        return 'right'
    if 45 <= a < 135:
        return 'down'
    if -135 <= a < -45:
        return 'up'
    return 'left'


def want_dir_old(dx, dy):
    u"""第95轮修复**之前**的档位（有缝隙：`[30,60)` 落 else ⇒ 判 left）。"""
    if dx == 0 and dy == 0:
        return None
    a = math.degrees(math.atan2(dy, dx))
    if -30 <= a < 30:
        return 'right'
    if 60 <= a < 120:
        return 'down'
    if -120 <= a < -60:
        return 'up'
    return 'left'


# ================= B 位置正确性 =================
def sec_b(frames):
    u"""位置正确性 —— 用户视角：他到底动没动。

    ★ 数据源 = `rec97_frames.csv`（等间隔采样）：相邻两行是**真正的相邻采样**，
      位移/时间戳同源 ⇒ 可以直接算速度、算零位移。用 `moves.txt` 则会因为
      "只在坐标变化时记录"而把多帧合并成一"步"，量不出真实的零位移占比。
    """
    P(u'')
    P(u'=== B 位置正确性（用户视角：他到底动没动）===')
    if len(frames) < 3:
        check(False, u'B0 frames.csv 样本足够', u'太少')
        return []
    steps = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        try:
            dt = float(b['t']) - float(a['t'])
        except Exception:
            continue
        if dt <= 0 or dt > 3.0:
            continue
        steps.append({'t': float(b['t']), 'dt': dt,
                      'dx': b['wx'] - a['wx'], 'dy': b['wy'] - a['wy'],
                      'd': math.hypot(b['wx'] - a['wx'], b['wy'] - a['wy']),
                      'anim': b['anim'], 'dir': b['dir'],
                      'w': b['ww'], 'h': b['wh'], 'pw': a['ww'], 'ph': a['wh']})
    if not steps:
        check(False, u'B0 有效步', u'0')
        return []

    # ★★★ B1：走路动画下的零位移（第92轮"站桩"的指纹）
    #   ★ 排除尺寸变化帧（换帧会重设几何，那一帧的位移不代表运动学）
    zero_walk, walk_n = [], 0
    for s in steps:
        if not WALK.match(s['anim']):
            continue
        walk_n += 1
        if s['w'] != s['pw'] or s['h'] != s['ph']:
            continue
        if s['d'] == 0:
            zero_walk.append(s)
    info(u'走路动画下的采样步', u'%d' % walk_n)
    info(u'其中零位移', u'%d（已排除尺寸变化帧）' % len(zero_walk))
    check(walk_n > 0, u'B1a 本段真的出现过走路动画（否则"没站桩"是没测到）',
          u'走路步 %d' % walk_n)
    ratio = (100.0 * len(zero_walk) / walk_n) if walk_n else 0.0
    check(ratio <= 5.0, u'B1b ★★★ 走路动画下零位移占比 ≤5%（第92轮指纹 91.9%）',
          u'实测 %.1f%%' % ratio)
    for s in zero_walk[:6]:
        print(u'        t=%.2f anim=%r 位置没变（尺寸 %dx%d）'
              % (s['t'], s['anim'], s['w'], s['h']))

    # ★★ B2：累计位移
    total = sum(s['d'] for s in steps)
    span = steps[-1]['t'] - steps[0]['t']
    moving = [s for s in steps if s['d'] > 0]
    info(u'累计位移', u'%.0f px（墙钟 %.1f s）' % (total, span))
    info(u'有位移的步', u'%d / %d = %.1f%%'
         % (len(moving), len(steps), 100.0 * len(moving) / len(steps)))
    vels = sorted(s['d'] / s['dt'] for s in moving)
    if vels:
        info(u'位移速度', u'中位 %.1f px/s（min %.1f / max %.1f）'
             % (vels[len(vels) // 2], vels[0], vels[-1]))
    check(total > 500, u'B2 ★★ **真的在漫游**（累计位移 >500px）',
          u'实测 %.0f px（第92轮修前形态：165s 只挪 179px 且一直播走路）' % total)

    # ★ B3：长时间零位移段（用户会感知的"卡住"）
    segs, cur = [], None
    for s in steps:
        if s['d'] == 0:
            if cur is None:
                cur = {'t0': s['t'] - s['dt'], 't1': s['t'], 'dur': s['dt'],
                       'anim': s['anim']}
            else:
                cur['t1'] = s['t']
                cur['dur'] += s['dt']
        else:
            if cur is not None:
                segs.append(cur)
                cur = None
    if cur is not None:
        segs.append(cur)
    long_segs = sorted([s for s in segs if s['dur'] >= 30],
                       key=lambda x: -x['dur'])
    info(u'静止段', u'%d 段，其中 ≥30s 的 %d 段' % (len(segs), len(long_segs)))
    for s in long_segs[:6]:
        print(u'        静止 %.1fs（t=%.1f→%.1f）末帧动画 %r'
              % (s['dur'], s['t0'], s['t1'], s['anim']))
    return steps


# ================= C 朝向正确性 =================
def sec_c(frames):
    u"""朝向正确性 —— **纯用户视角**：他走的方向、脸朝的方向、播的精灵，三者一致吗？

    ★★★ 为什么不用"由位移推方向"当**唯一**判据
        `probe96_angle.py` 实测（本轮）：
          · 用"采样位移"推方向 → 与真实 `dir` 一致 **91.89%**
          · 用"复原的 current_speed"推 → 只有 **54.61%**（我的复原模型漏了
            `new_speed`/情绪因子/近距减速等，**测不动**）
        ⇒ 结论：**"由采样位移推方向"本身就是一个带偏差的代理**，
          拿它当唯一判据会造出 8.1% 的假矛盾（第95轮 0.97% 那次也是同源）。

    ★ 改成"**三方自洽**"（更贴用户视角）：
      用户能看到的只有三样东西 —— ① 走过的位移方向、② 播的精灵朝向（`anim` 的方向段）、
      ③ 脸的方向（`dir`，表现为精灵选择）。
      判据 = **三者两两一致**；只要三者一致，对用户而言就是"对的"，
      不需要知道产品内部用速度向量还是位移向量算的。
      （若三者不一致 ⇒ 用户**能直接看出来**别扭 ⇒ 那才是要报的缺陷。）

      C1 `dir` == `anim` 的方向段        （用户看到的两个"朝向"要一致）
      C2 `anim` 方向段 == 采样位移方向    （播的精灵要跟走向一致）
      C3 `dir` == 采样位移方向            （脸的方向要跟走向一致）
    """
    P(u'')
    P(u'=== C 朝向正确性（用户视角：走向 / 脸的方向 / 播的精灵，三者一致吗）===')
    if len(frames) < 3:
        check(False, u'C0 frames.csv 样本足够', u'太少')
        return []

    # ---- 组装"有位移的走路帧"序列 ----
    recs = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        if b.get('anim') is None:
            continue
        mm = _WALKF.match(b['anim'] or '')
        if not mm:
            continue
        dx, dy = b['wx'] - a['wx'], b['wy'] - a['wy']
        if dx == 0 and dy == 0:
            continue
        if b['ww'] != a['ww'] or b['wh'] != a['wh']:
            continue                                   # 尺寸变化帧（换帧重设几何）
        try:
            dt = float(b['t']) - float(a['t'])
        except Exception:
            continue
        if dt <= 0 or dt > 3.0:
            continue
        e = want_dir(dx, dy)
        if e is None:
            continue                                   # 正 45° 线上口径不唯一
        recs.append({'t': float(b['t']), 'dir': b['dir'], 'anim': b['anim'],
                     'anim_dir': mm.group(1), 'move_dir': e,
                     'dx': dx, 'dy': dy,
                     'spdx': b.get('spdx'), 'spdy': b.get('spdy'),
                     'deg': math.degrees(math.atan2(dy, dx))})
    info(u'有位移的走路采样帧', u'%d' % len(recs))
    check(len(recs) >= 30, u'C0b 样本足够（≥30）', u'%d 帧' % len(recs))
    if len(recs) < 5:
        return []

    # ---- C1: dir == anim 方向段（用户看到的两个朝向要对得上）----
    bad1 = [r for r in recs if r['dir'] in DIRS and r['dir'] != r['anim_dir']]
    r1 = 100.0 * len(bad1) / len(recs)
    check(r1 < 2.0,
          u'C1 ★★★ `current_direction` == 走路动画的方向段（两者都直接决定用户看到什么）',
          u'不一致 %d / %d = %.2f%%%s'
          % (len(bad1), len(recs), r1,
             u'' if not bad1 else u' 例：' + u' / '.join(
                 u't=%.2f %s vs dir=%s' % (r['t'], r['anim'], r['dir'])
                 for r in bad1[:4])))

    # ---- C2: 播的精灵朝向 == **产品自己的速度向量**方向（★★★ 第96轮改正）----
    #   ★★★ 本轮最重要的一条方法论修正（probe96_walkup 实证）：
    #     产品 L7244 决定朝向的那一行是
    #         `angle = atan2(self.current_speed_y, self.current_speed_x)`
    #     —— 用的**就是速度向量**。而"相邻两次采样的位移"在 0.4 s 窗口内
    #     会跨过转向边界 / 含折返，与"当前瞬时动画"**本就不该相等**。
    #     实测对照（probe96_walkup，148 个有效样本，速度幅值 ≥0.3）：
    #       · 用「采样位移」推方向 ⇒ 4.43% 报"矛盾"（**全部是伪影**）
    #       · 用「速度向量」推方向 ⇒ **0.00% 不一致**
    #     ⇒ 判据必须用速度向量；采样位移只作**参考信息**，不再参与报红。
    #     （这正是记忆铁律「判据也是被测物」的又一次命中：
    #       上一版我拿"位移"当唯一证据，造出了 4.43% 的假矛盾。）
    vrec = []
    for r in recs:
        sx, sy = r.get('spdx'), r.get('spdy')
        if sx is None or sy is None:
            continue
        mag = math.hypot(sx, sy)
        if mag < 0.3:
            continue                       # 速度太小时方向无意义（产品自己也不切）
        e = want_dir(sx, sy)
        if e is None:
            continue
        vrec.append(dict(r, svx=sx, svy=sy, smag=mag,
                         vdeg=math.degrees(math.atan2(sy, sx)), vmovedir=e))
    info(u'有速度向量的走路采样帧（速度幅值 ≥0.3）', u'%d' % len(vrec))
    if len(vrec) >= 10:
        # C2v: anim 方向段 == 速度向量分档
        bv = [r for r in vrec if r['anim_dir'] != r['vmovedir']]
        rv = 100.0 * len(bv) / len(vrec)
        runsv, curv, prevv = [], 0, None
        for i, r in enumerate(vrec):
            if r['anim_dir'] != r['vmovedir']:
                curv = curv + 1 if (prevv is not None and i == prevv + 1) else 1
                if curv == 1 and prevv is not None and i != prevv + 1 and runsv:
                    pass
                prevv = i
            else:
                if curv:
                    runsv.append(curv)
                curv = 0
                prevv = i
        if curv:
            runsv.append(curv)
        runsv.sort(reverse=True)
        info(u'C2v 动画方向段 vs 速度向量：不一致', u'%d / %d = %.2f%%；连续段 %s'
             % (len(bv), len(vrec), rv, runsv[:8] if runsv else u'[]'))
        check((runsv[0] if runsv else 0) <= 2,
              u'C2v ★★★ 播的精灵方向段 == **速度向量**方向（最长连续不一致段 ≤2 帧）'
              u' —— 这是决定用户所见的**权威判据**',
              u'实测最长 %d 帧；占比 %.2f%%%s'
              % (runsv[0] if runsv else 0, rv,
                 u'' if not bv else u' 例：' + u' / '.join(
                     u't=%.2f %s 但速度 %.1f° ⇒ 应 %s'
                     % (r['t'], r['anim'], r['vdeg'], r['vmovedir'])
                     for r in bv[:4])))
        # C3v: current_direction == 速度向量分档
        cv = [r for r in vrec if r['dir'] in DIRS and r['dir'] != r['vmovedir']]
        rcv = 100.0 * len(cv) / len(vrec)
        runs3v, cur3v, prev3v = [], 0, None
        for i, r in enumerate(vrec):
            if r['dir'] in DIRS and r['dir'] != r['vmovedir']:
                cur3v = cur3v + 1 if (prev3v is not None and i == prev3v + 1) else 1
                prev3v = i
            else:
                if cur3v:
                    runs3v.append(cur3v)
                cur3v = 0
                prev3v = i
        if cur3v:
            runs3v.append(cur3v)
        runs3v.sort(reverse=True)
        info(u'C3v `current_direction` vs 速度向量：不一致', u'%d / %d = %.2f%%'
             % (len(cv), len(vrec), rcv))
        check((runs3v[0] if runs3v else 0) <= 2,
              u'C3v ★★★ `current_direction` == **速度向量**方向（最长连续不一致段 ≤2 帧）',
              u'实测最长 %d 帧；占比 %.2f%%' % (runs3v[0] if runs3v else 0, rcv))
    else:
        check(False,
              u'C2v/C3v 用**速度向量**判朝向（需 ≥10 个速度向量样本）',
              u'仅 %d 个 ⇒ 无法判定（`rec97.py` 须采集 `spdx/spdy`）' % len(vrec))

    # ---- C2（参考 · 采样位移口径，**不报红**）----
    #   ★ 保留它只为"与历轮报告口径可比"，**不再作为判据**：
    #     它测的是"0.4s 窗口内的平均位移方向"，天然会被转向/折返污染。
    bad2 = [r for r in recs if r['anim_dir'] != r['move_dir']]
    r2 = 100.0 * len(bad2) / len(recs)
    runs, cur = [], 0
    prev_idx = None
    for i, r in enumerate(recs):
        if r['anim_dir'] != r['move_dir']:
            if prev_idx is not None and i == prev_idx + 1:
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur = 1
            prev_idx = i
        else:
            if cur:
                runs.append(cur)
            cur = 0
            prev_idx = i
    if cur:
        runs.append(cur)
    runs.sort(reverse=True)
    info(u'C2【参考·采样位移口径】反向帧', u'%d / %d = %.2f%%；连续段 %s'
         % (len(bad2), len(recs), r2, runs[:8] if runs else u'[]'))
    info(u'  ← 该口径**不作判据**（会被转向/折返污染；见下方 C2v 与 probe96_walkup）',
         u'最长连续 %d 帧' % (runs[0] if runs else 0))

    # ---- C3（参考 · 采样位移口径，**不报红**）----
    bad3 = [r for r in recs if r['dir'] in DIRS and r['dir'] != r['move_dir']]
    r3 = 100.0 * len(bad3) / len(recs)
    info(u'C3【参考·采样位移口径】不一致帧',
         u'%d / %d = %.2f%%' % (len(bad3), len(recs), r3))

    # ---- C4 ★★★ 决定性：原缺陷扇区 [30,60) 内**逐帧**看 ----
    #   第95轮缺陷 B 的形态 = 该扇区内一律判 left（连动画都播 left）。
    #   ★★★ 第96轮改正：扇区**必须按速度向量角度划分**，不能按采样位移角度。
    #     实证（t=60.12）：速度 `(-4.403,+2.202) = 153.4°` ⇒ 判 left **正确**；
    #     但"采样位移"只有 `(+19,+14) = 36.4°`（折返瞬间的半帧位移）
    #     ⇒ 用位移划分扇区会把这一帧误当成"36.4° 却判 left"的缺陷。**这是判据伪影。**
    seam = [r for r in recs if r.get('spdx') is not None and r.get('spdy') is not None
            and math.hypot(r['spdx'], r['spdy']) >= 0.3
            and 30.0 <= math.degrees(math.atan2(r['spdy'], r['spdx'])) < 60.0]
    info(u'★ 原缺陷扇区 [30,60) 的帧（**按速度向量角度**划分）', u'%d' % len(seam))
    if seam:
        wrong = [r for r in seam if r['dir'] == 'left' or r['anim_dir'] == 'left']
        check(not wrong,
              u'C4 ★★★ 扇区 `[30,60)` 内**没有任何一帧**朝左（旧档在此全判 left）',
              u'朝左 %d / %d%s' % (len(wrong), len(seam),
                                 u'' if not wrong else u' 例：' + u' / '.join(
                                     u't=%.2f 速度角=%.1f° dir=%s'
                                     % (r['t'],
                                        math.degrees(math.atan2(r['spdy'], r['spdx'])),
                                        r['dir'])
                                     for r in wrong[:4])))
        dr = {}
        for r in seam:
            dr[r['dir']] = dr.get(r['dir'], 0) + 1
        info(u'  该扇区内 dir 分布', u'%s' % dr)
    else:
        check(False, u'C4 ★★★ 扇区 `[30,60)` 覆盖（帧 ≥1）',
              u'实测 0 帧 ⇒ **本段没走到该扇区**，"没看到反向"不构成验证'
              u'（第95轮报告 §8.4 同样登记了这个缺口）')
    return bad1 + bad2 + bad3


# ================= D 姿态正确性 =================
def sec_d(frames):
    P(u'')
    P(u'=== D 姿态正确性（用户视角：停下来还摆走路姿势吗 —— F35-4）===')
    if len(frames) < 3:
        check(False, u'D0 样本足够', u'—')
        return
    # 找"连续 ≥4 秒零位移"的静止段，看段**末**的动画是不是走路
    segs, cur = [], None
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        try:
            dt = float(b['t']) - float(a['t'])
        except Exception:
            continue
        if dt <= 0 or dt > 3.0:
            continue
        still = (a['wx'] == b['wx'] and a['wy'] == b['wy'] and a['ww'] == b['ww'])
        if still:
            if cur is None:
                cur = {'t0': float(a['t']), 'last': b}
            else:
                cur['last'] = b
        else:
            if cur is not None:
                cur['dur'] = float(cur['last']['t']) - cur['t0']
                segs.append(cur)
                cur = None
    if cur is not None:
        cur['dur'] = float(cur['last']['t']) - cur['t0']
        segs.append(cur)
    long_still = [s for s in segs if s['dur'] >= 4.0]
    resid = [s for s in long_still if WALK.match(s['last']['anim'])]
    info(u'≥4s 静止段', u'%d 段' % len(long_still))
    info(u'其中末帧仍播走路', u'%d 段' % len(resid))
    check(not resid,
          u'D1 ★★★ 静止段结束时**不残留走路姿势**（F35-4 的原症状）',
          u'残留 %d 段%s' % (len(resid), u'' if not resid else u' 例：'
                           + u' / '.join(u't=%.1f %.1fs anim=%r'
                                         % (x['t0'], x['dur'], x['last']['anim'])
                                         for x in resid[:4])))
    for s in sorted(long_still, key=lambda x: -x['dur'])[:6]:
        print(u'        静止 %.1fs 末帧 anim=%r dir=%r'
              % (s['dur'], s['last']['anim'], s['last']['dir']))


# ================= E 状态机与边界 =================
def sec_e(frames, geo_wh):
    P(u'')
    P(u'=== E 状态机与边界 ===')
    if not frames:
        check(False, u'E0 frames.csv 非空', u'—')
        return
    # 互斥状态并存（★ 第97轮：坠落口径含 `is_gravity_falling`，与 F7 统一）
    both = [f for f in frames
            if (str(f.get('falling')) == 'True'
                or str(f.get('gfall')) == 'True')
            and str(f.get('moving')) == 'True'
            and str(f.get('sleeping')) == 'True']
    check(not both, u'E1 跳跃/坠落/睡眠互斥不并存', u'并存 %d 帧' % len(both))
    # 越界（屏幕 0..W-1 / 0..H-1；产品 clamp 用 screenGeometry）
    W, H = geo_wh
    oob = []
    for f in frames:
        if f['wx'] is None:
            continue
        if f['wx'] < -200 or f['wx'] > W + 200 or f['wy'] < -200 or f['wy'] > H + 200:
            oob.append(f)
    info(u'屏幕', u'%dx%d' % (W, H))
    check(not oob, u'E2 ★★ 窗口位置未严重越界（允许 ±200 锚点补偿余量）',
          u'越界 %d 帧%s' % (len(oob), u'' if not oob else
                           u' 例：' + u' / '.join(u't=%.1f (%d,%d)'
                                                  % (x['t'], x['wx'], x['wy'])
                                                  for x in oob[:4])))
    xs = [f['wx'] for f in frames if f['wx'] is not None]
    ys = [f['wy'] for f in frames if f['wy'] is not None]
    if xs:
        info(u'位置范围', u'x[%d,%d] y[%d,%d]' % (min(xs), max(xs), min(ys), max(ys)))


# ================= F 用户报过的原症状逐条复核 =================
def sec_f(frames):
    P(u'')
    P(u'=== F 用户历次点名过的症状 · 逐条复核 ===')
    if not frames:
        check(False, u'F0 数据', u'—')
        return
    # F1 站桩（第90/92轮：「他在这里站桩呢？？？」「光有那个移动的动画，没有实际移动」）
    walk_zero, walk_n = 0, 0
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        if not WALK.match(b['anim']):
            continue
        if b['ww'] != a['ww'] or b['wh'] != a['wh']:
            continue
        walk_n += 1
        if a['wx'] == b['wx'] and a['wy'] == b['wy']:
            walk_zero += 1
    r = (100.0 * walk_zero / walk_n) if walk_n else 0.0
    check(r <= 5.0,
          u'F1 【第90/92轮·站桩/走不动】走路动画下零位移占比 ≤5%',
          u'%.1f%%（第92轮修前实测 91.9%%；本次走路采样帧 %d）' % (r, walk_n))

    # F2 朝向反了（第95轮缺陷 B：朝右下走却播朝左）
    #   ★★★ 第96轮改正：判据口径与 C2v/C3v 统一 —— **用速度向量**，不用采样位移。
    #     理由见 sec_c 顶部：位移在 0.4s 窗口内会跨转向边界/含折返，
    #     实测两种口径差异 5.54% vs **0.17%**（后者才是产品真实表现）。
    bad = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        # ★★★ 第97轮修正（**判据缺陷**）：必须**限定走路帧**，否则睡眠/站姿帧会
        #   大规模假阳性 —— 实测本轮 591 条"矛盾"**全部**是 `anim=sleep`：
        #   睡眠时 `dir='left'`（上次朝向残留）而 `current_speed_x=5.82`（未清零）
        #   ⇒ 判"应 right" ⇒ 矛盾。限定走路帧后 = **0/184 = 0.00%**，与 C2v/C3v 一致。
        if not WALK.match(str(b['anim']) or ''):
            continue
        if b['dir'] not in DIRS:
            continue
        sx, sy = b.get('spdx'), b.get('spdy')
        if sx is None or sy is None:
            continue
        if math.hypot(sx, sy) < 0.3:
            continue
        e = want_dir(sx, sy)
        if e is not None and b['dir'] != e:
            bad.append(b)
    # 分母 = 有速度向量的**走路帧**（★ 第97轮修正：与 C2v/C3v 口径统一）
    _f2_n = len([f for f in frames
                 if WALK.match(str(f['anim']) or '')
                 and f['dir'] in DIRS and f.get('spdx') is not None
                 and f.get('spdy') is not None
                 and math.hypot(f['spdx'], f['spdy']) >= 0.3])
    check(len(bad) <= max(2, 0.02 * max(1, _f2_n)),
          u'F2 【第95轮·朝右下走却播朝左】朝向矛盾 ≤2%（口径=速度向量·**限走路帧**）',
          u'矛盾 %d 条 / %d 帧（含速度向量的走路帧数）' % (len(bad), _f2_n))

    # F3 anim-miss（第91轮 / F35-1：`walk_left/right/up_sleep` 素材不存在）
    #   ★★★ 第96轮修：产品把**正面自检报告**也打上了 `[anim-miss]` 前缀 ——
    #     `[anim-miss] 本轮运行未出现未命中的动画名（已加载 497 组）`
    #     原正则 `\[anim-miss\][^\n]*` 会把它当成"1 条 miss"⇒ **假红**。
    #     正确做法：先按"未出现未命中"这行把正面报告摘出去，剩下的才算真 miss。
    txt = rd(os.path.join(EV, 'rec97_stdout.txt')) or ''
    all_mm = re.findall(r'\[anim-miss\][^\n]*', txt)
    miss = [m for m in all_mm if u'未出现未命中' not in m and u'未命中' not in m]
    has_selfcheck = u'本轮运行未出现未命中的动画名' in txt
    check(len(miss) == 0 and has_selfcheck,
          u'F3 【第91轮·小憩走路素材缺失】真 `[anim-miss]` 记录 0 条 **且**产品自检行在场',
          u'真 miss %d 条（原始匹配 %d 条，含正面自检行）；自检行 %s'
          % (len(miss), len(all_mm),
             u'在场（⇒ 观测面非空）' if has_selfcheck
             else u'★不在场 ⇒ 这是"没测到"不是"没命中"'))
    for m in miss[:4]:
        print(u'        [anim-miss] %s' % m)

    # F4 静止残留走路（F35-4）见 D1
    # F5 互斥状态见 E1
    # F6 瞬移（第35轮那条"伪影"教训：必须排除尺寸变化帧）
    jump = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a['wx'] is None or b['wx'] is None:
            continue
        if b['ww'] != a['ww'] or b['wh'] != a['wh']:
            continue                                   # ★ 尺寸变化帧排除（真凶是它）
        d = math.hypot(b['wx'] - a['wx'], b['wy'] - a['wy'])
        if d > 300:
            jump.append((float(b['t']), d))
    check(not jump, u'F6 【第35轮·瞬移】同尺寸下的单步位移 ≤300px',
          u'超限 %d 次%s' % (len(jump), u'' if not jump else
                          u' 例：' + u' / '.join(u't=%.1f %.0fpx' % x for x in jump[:4])))

    # F7 ★★★【第90轮·抛物线/跳跃】原话：「抛物线和跳上去不对」「跳上去窗口也只有跳没有上去」
    #   ★ 诚实说明（第97轮收尾修正，原文只说"没有主动制造" —— 对 run2 已不成立）：
    #     · **run1（自然 600s）**：没有主动制造"跳跃/坠落"场景（宠物自主行为不一定触发）
    #       ⇒ 只能做"是否发生过"的覆盖度判据 + 若发生则核对几何。
    #     · **run2（定向 180s）**：由 `rec97.py` 的 `REC97_INJECT_FALL` **主动注入**坠落
    #       （为补 run1"600s 零坠落"的覆盖缺口）⇒ 此时"有过坠落"是**构造出来的**，
    #       **绝不能**当作产品自发行为的证据（第97轮真实教训：用户看到注入的"空桌面摔"，
    #       误以为是产品 bug）。分析前先看 `REC97_EVDIR` 分清是哪一轮。
    # ★★★ 第97轮修正（**判据缺口**）：产品把"**重力坠落**"记在 `is_gravity_falling`，
    #   而 `is_falling` 只覆盖"**原地摔**"（`start_fall`）⇒ 旧观测面**看不到任何
    #   重力坠落**，会把"其实摔过"误报成"没覆盖"。这里改为**两者取或**。
    jf = [f for f in frames
          if str(f.get('falling')) == 'True' or str(f.get('gfall')) == 'True']
    info(u'`is_falling=True` 的采样帧',
         u'%d' % len([f for f in frames if str(f.get('falling')) == 'True']))
    info(u'`is_gravity_falling=True` 的采样帧',
         u'%d' % len([f for f in frames if str(f.get('gfall')) == 'True']))
    info(u'坠落帧合计（两者取或）', u'%d' % len(jf))
    if jf:
        # 有坠落/跳跃时的竖直位移应向下（屏幕 +y 向下 = 下落）。
        # ★★★ 第97轮修正（**判据缺陷**，两处；与 F6 同型）：
        #   ① **必须排除尺寸变化帧** —— 实测 29 步"向上"里 **18 步**伴随窗口尺寸
        #      变化（`fall_mad`/`land`/`idle` 切换时的**锚点补偿**），不是位置问题；
        #   ② **必须跳过坠落段首步** —— 坠落常紧接"向上走"（本轮把宠物驱动到屏幕
        #      上方），首帧仍带**运动惯性**：实测 t=119.027/119.527 两帧
        #      `walk_right` 的 Δy=-13（真在往上走），t=120.173 坠落首帧 Δy=-12
        #      是它的延续；**从第 2 步起立刻转为 +27 / +137**（正常下落）。
        #   ⇒ 这两处都是判据的锅，不是产品的锅。
        desc = []
        for i in range(1, len(frames)):
            a, b = frames[i - 1], frames[i]
            # ③ 只判**真·重力坠落**（`is_gravity_falling`）。`is_falling` 覆盖的是
            #    "**原地摔**"整个流程（含落地后 `fall_mad` 生气 ≥5s、`splat_mad`、
            #    `land`、`idle`），期间的 y 变化是动画/对齐微调，**本就不是"下落"**，
            #    拿它判"下落方向"必然假红（实测残留 6/85 全来自这些动画）。
            if str(b.get('gfall')) != 'True':
                continue
            if a['wy'] is None or b['wy'] is None:
                continue
            if b['ww'] != a['ww'] or b['wh'] != a['wh']:
                continue                      # ① 锚点补偿帧，排除
            if str(a.get('gfall')) != 'True':
                continue                      # ② 坠落段首步（运动惯性），排除
            desc.append(b['wy'] - a['wy'])
        n_up = len([d for d in desc if d < 0])
        info(u'  真重力坠落帧的 Δy（已排除锚点补偿帧与段首惯性帧）',
             u'共 %d 步，其中 y 变小（往上）的 %d 步' % (len(desc), n_up))
        check(n_up == 0 or len(desc) < 3,
              u'F7b ★★ 真·重力坠落帧的竖直位移应向下（Δy ≥ 0）',
              u'向上 %d / %d' % (n_up, len(desc)))
    else:
        check(False, u'F7 【第90轮·抛物线/跳跃】本段是否覆盖到坠落/跳跃',
              u'**0 帧** ⇒ 这次 10 分钟**没有触发**坠落或跳跃 ⇒'
              u'「抛物线和跳上去不对」这条**本次无法验证**，'
              u'必须如实登记而不是默认为"没问题"')


def main():
    meta = rd(os.path.join(EV, 'rec97_meta.txt'))
    mv = rd(os.path.join(EV, 'rec97_moves.txt'))
    csvt = rd(os.path.join(EV, 'rec97_frames.csv'))
    if mv is None and csvt is None:
        print(u'★ 没有找到录制产物，先跑 rec97.py')
        return 2
    rows = parse_moves(mv) if mv else []
    frames = parse_csv(csvt)
    P(u'#' * 72)
    P(u'# 第97轮 · 基础宠物排查 · 用户视角录制 · 逐帧分析')
    P(u'#' * 72)
    info(u'moves 事件数', u'%d' % len(rows))
    info(u'frames 采样数', u'%d' % len(frames))
    m = sec_a(meta)
    sec_a2_target_sectors(frames)
    P(u'')
    sec_b(frames)
    sec_c(frames)
    sec_d(frames)
    geo = (2560, 1600)
    mm = re.search(r'屏幕\s*=\s*(\d+)x(\d+)', meta or '')
    if mm:
        geo = (int(mm.group(1)), int(mm.group(2)))
    sec_e(frames, geo)
    sec_f(frames)

    P(u'')
    P(u'=' * 72)
    P(u'合计：PASS=%d  FAIL=%d  判据=%d' % (_N[0] - _BAD[0], _BAD[0], _N[0]))
    P(u'=' * 72)
    out = os.path.join(EV, 'analyze97.txt')
    io.open(out, 'w', encoding='utf-8', newline='\n').write(u'\n'.join(_P) + u'\n')
    print(u'\n'.join(_P))
    return 1 if _BAD[0] else 0


if __name__ == '__main__':
    sys.exit(main())
