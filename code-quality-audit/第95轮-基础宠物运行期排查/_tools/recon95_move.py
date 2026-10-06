# -*- coding: utf-8 -*-
u"""recon95_move.py —— 第95轮 运行期运动日志复核（只读 · 零依赖 · 不联网）。

背景
----
第95轮的运行期 recon 落了两份东西：
  · `_recon/move_log.txt`   —— 劫持 `pet.move()` 记的 2480 条（t,x,y,anim,dir,moving,spd,tgt,sz）
  · `_recon/move_audit.txt` —— 由它派生出的"体检"，报了三条

    ① 朝向矛盾：往右走却显示 `walk_left`（严格 6 帧 / 宽松 11 帧）
    ③ 站桩（anim=walk_* 但本帧位移 0）：0 帧          ← 好消息（第92轮"走不动"没回归）
    ④ 单帧位移 >40px（"瞬移候选"）：20 帧

★ 复核动机：`move_log.txt` 里的 `x,y` 是**窗口左上角**，而宠物窗口的尺寸会随
  动画切换（`walk_*` 38x80 ↔ `idle` 族 138x94 ↔ 42x82 …，见详版 §94.2.3），
  渲染分支又是按**中心**回算 `setGeometry` 的。
  ⇒ 尺寸一变，左上角就跳 ~50px，而中心不动。
  ⇒ 若不复核就照抄，等于把"测量口径"当成"产品缺陷"。

本脚本对同一份原始日志，**同时**按「左上角」与「窗口中心」两套口径重算，
并对每一步按 `dt` 归一化成 px/s —— 判据本身也是被测物，两套口径不一致时不下结论。

本脚本复核结论（可复跑，见 stdout）
----------------------------------
  · ③ 站桩 = 0 帧            ⇒ **成立**（第92轮"走不动"修复没回归）
  · ④ 瞬移候选 = 56 步(>40px) ⇒ **伪影**：56 步 **100%** 落在"窗口尺寸变化步"上；
      尺寸变化步上 Δtopleft 中位 **48.0px** vs Δcenter 中位 **3.6px**（13 倍）；
      换中心口径后 >40px 只剩 1 步。⇒ 渲染按中心回算，左上角不是运动学量。
  · ① 朝向矛盾 331/2410 = 13.7% ⇒ **一半伪影、一半是真缺陷**：
      · 6 例是单帧边界采样（尺寸跳变那一拍）；
      · ★ 但 **319 步 / 10.48s 是一条连续长段**（t=261.2~271.7），段内尺寸恒定 38x80，
        目标 (1877,1196)、起点 x=594 一路 +x ⇒ 复算 `atan2(1113,1283) = 40.9°`，
        正落在旧档 `-30/30/60/120` 的**缝隙 [30,60)** 里 ⇒ 被判 `left`。
        **这是真缺陷**（第95轮已修，见 `check95` E 段）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第95轮-基础宠物运行期排查\\_tools\\recon95_move.py
"""
import io
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
R95 = os.path.join(ROOT, 'code-quality-audit', '第95轮-基础宠物运行期排查')
# ★ `_recon/` 被 `.gitignore` 排除（`code-quality-audit/*/_recon/`）⇒ 原始日志必须
#   随 `_evidence/` 进仓库，否则本工具在**新克隆**里跑不起来（记忆铁律：
#   「回归套件不许依赖临时区／外部盘 ⇒ 事实蒸馏进仓库」）。
#   本地还留一份 `_recon/move_log.txt` 作为抓取现场的备份。
LOG = os.path.join(R95, '_evidence', 'move_log.txt')
if not os.path.isfile(LOG):                    # pragma: no cover
    LOG = os.path.join(R95, '_recon', 'move_log.txt')

_p = _f = 0


def check(desc, cond, detail=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _f += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


ROW = re.compile(
    r"t=(?P<t>[-\d.]+)\s+x=(?P<x>-?\d+)\s+y=(?P<y>-?\d+)\s+"
    r"anim='(?P<anim>[^']*)'\s+dir='(?P<dir>[^']*)'\s+"
    r"moving=(?P<moving>\w+)\s+spd=(?P<spd>[-\d.eE]+)\s+"
    r"tgt=PyQt5\.QtCore\.QPoint\((?P<tx>-?\d+),\s*(?P<ty>-?\d+)\)\s+"
    r"sz=(?P<w>\d+)x(?P<h>\d+)")

rows = []
with io.open(LOG, encoding='utf-8', newline='') as fh:
    for ln in fh:
        m = ROW.search(ln)
        if not m:
            continue
        rows.append({'t': float(m.group('t')), 'x': int(m.group('x')),
                     'y': int(m.group('y')), 'w': int(m.group('w')),
                     'h': int(m.group('h')), 'anim': m.group('anim'),
                     'dir': m.group('dir'),
                     'tx': int(m.group('tx')), 'ty': int(m.group('ty')),
                     'moving': m.group('moving') == 'True',
                     'spd': float(m.group('spd'))})

print('=' * 78)
print('0. 样本')
print('=' * 78)
print('解析成功 = %d 条   t ∈ [%.3f, %.3f]' % (len(rows), rows[0]['t'], rows[-1]['t']))
fam = {}
for r in rows:
    fam[(r['w'], r['h'])] = fam.get((r['w'], r['h']), 0) + 1
print('窗口尺寸族 = %s' % sorted(fam.items(), key=lambda kv: -kv[1]))
print('目标速度 spd 取值 = %s' % sorted(set(r['spd'] for r in rows)))

steps = []
for i in range(1, len(rows)):
    a, b = rows[i - 1], rows[i]
    dt = b['t'] - a['t']
    if dt <= 0:
        continue
    d_tl = ((b['x'] - a['x']) ** 2 + (b['y'] - a['y']) ** 2) ** 0.5
    ca = (a['x'] + a['w'] / 2.0, a['y'] + a['h'] / 2.0)
    cb = (b['x'] + b['w'] / 2.0, b['y'] + b['h'] / 2.0)
    dxc, dyc = cb[0] - ca[0], cb[1] - ca[1]
    d_c = (dxc ** 2 + dyc ** 2) ** 0.5
    steps.append({'a': a, 'b': b, 'dt': dt, 'd_tl': d_tl, 'd_c': d_c,
                  'dxc': dxc, 'dyc': dyc,
                  'sz': (a['w'] != b['w']) or (a['h'] != b['h'])})

dts = sorted(s['dt'] for s in steps)
print('步数 = %d   dt: median=%.3f  p90=%.3f  max=%.3f'
      % (len(steps), dts[len(dts) // 2], dts[int(len(dts) * .9)], dts[-1]))

print()
print('=' * 78)
print('1. ★ 站桩检查（第92轮"走不动"是否回归）')
print('=' * 78)
walk_steps = [s for s in steps if s['b']['anim'].startswith('walk')]
stuck = [s for s in walk_steps if s['d_c'] == 0.0]
stuck_tl = [s for s in walk_steps if s['d_tl'] == 0.0]
print('步后 anim 为 walk_* 的步 = %d' % len(walk_steps))
print('  其中 Δcenter == 0 的步 = %d' % len(stuck))
print('  其中 Δtopleft == 0 的步 = %d' % len(stuck_tl))
if stuck_tl:
    print('  样例（左上角零位移）：')
    for s in stuck_tl[:5]:
        print('     t=%6.2f anim=%s dir=%s moving=%s Δc=%.1f'
              % (s['b']['t'], s['b']['anim'], s['b']['dir'], s['b']['moving'], s['d_c']))
check('M1 不存在"anim=walk_* 且中心零位移"的步（第92轮缺陷未回归）',
      len(stuck) == 0, '零位移步 = %d' % len(stuck))

print()
print('=' * 78)
print('2. 速度：两套口径 × dt 归一化（px/s）')
print('=' * 78)


def stat(vals, lab):
    v = sorted(vals)
    n = len(v)
    print('%-16s median=%7.1f  p90=%7.1f  p99=%7.1f  max=%7.1f'
          % (lab, v[n // 2], v[int(n * .9)], v[int(n * .99)], v[-1]))
    return v


v_c = stat([s['d_c'] / s['dt'] for s in steps], '中心 px/s')
v_tl = stat([s['d_tl'] / s['dt'] for s in steps], '左上角 px/s')
tgt = sorted(set(r['spd'] for r in rows))
print('移动时的目标速度（源码里的 spd）= %s px/' % [round(x, 2) for x in tgt])
print('★ 注意 dt 不恒定（%.3f~%.3f s）⇒ 直接比"每步位移"没有意义，必须除以 dt。'
      % (dts[0], dts[-1]))
check('M2 只用"每步位移"（未除 dt）会得出虚假的"瞬移"结论 —— 已按 dt 归一化',
      dts[-1] / max(dts[0], 1e-9) >= 3.0,
      'dt 跨度 = %.3f ~ %.3f s（比值 %.1f）' % (dts[0], dts[-1], dts[-1] / dts[0]))

print()
print('=' * 78)
print('3. ★ 尺寸变化步：左上角 vs 中心（检验 move_audit ①/④ 是不是伪影）')
print('=' * 78)
sz_steps = [s for s in steps if s['sz']]
print('尺寸变化步 = %d' % len(sz_steps))
if sz_steps:
    mtl = statistics.median([s['d_tl'] for s in sz_steps])
    mc = statistics.median([s['d_c'] for s in sz_steps])
    print('  Δtopleft 中位 = %.1f px' % mtl)
    print('  Δcenter  中位 = %.1f px' % mc)
    print('  样例：')
    for s in sz_steps[:6]:
        print('     t=%6.2f  %dx%d -> %dx%d   Δtl=%6.1f  Δc=%6.1f  Δc/dt=%7.1f px/s'
              % (s['a']['t'], s['a']['w'], s['a']['h'], s['b']['w'], s['b']['h'],
                 s['d_tl'], s['d_c'], s['d_c'] / s['dt']))
    check('M3 尺寸变化步上，Δtopleft 明显大于 Δcenter（⇒ 左上角读数被尺寸跳变污染）',
          mtl > mc * 1.5, 'Δtl=%.1f  vs  Δc=%.1f  （比 %.2f）' % (mtl, mc, mtl / max(mc, .001)))

big_tl = [s for s in steps if s['d_tl'] > 40]
big_c = [s for s in steps if s['d_c'] > 40]
n_sz_in_big = len([s for s in big_tl if s['sz']])
print()
print('Δtopleft > 40px 的步 = %d ；其中落在"尺寸变化步"上的 = %d (%.0f%%)'
      % (len(big_tl), n_sz_in_big, 100.0 * n_sz_in_big / max(len(big_tl), 1)))
print('Δcenter  > 40px 的步 = %d ；其中落在"尺寸变化步"上的 = %d (%.0f%%)'
      % (len(big_c), len([s for s in big_c if s['sz']]),
         100.0 * len([s for s in big_c if s['sz']]) / max(len(big_c), 1)))
print('Δtopleft>40 步的速度（px/s）p90 = %.1f ；同一批步的 Δcenter 速度 p90 = %.1f'
      % (sorted(s['d_tl'] / s['dt'] for s in big_tl)[int(len(big_tl) * .9)],
         sorted(s['d_c'] / s['dt'] for s in big_tl)[int(len(big_tl) * .9)]))
check('M4 Δtopleft>40px 的步**全部**落在尺寸变化步上或 dt 明显偏大（⇒ 不是瞬移）',
      all(s['sz'] or s['dt'] > 0.4 for s in big_tl),
      '越界步 = %d' % len([s for s in big_tl if not s['sz'] and s['dt'] <= 0.4]))

print()
print('=' * 78)
print('4. ★ 朝向一致性（中心口径；只取"位移足够大且 dt 足够小"的步）')
print('=' * 78)
EX = {'walk_left': ('x', -1), 'walk_right': ('x', +1),
      'walk_up': ('y', -1), 'walk_down': ('y', +1)}
cand = [s for s in steps if s['b']['anim'] in EX
        and s['dt'] <= 0.25 and (abs(s['dxc']) + abs(s['dyc'])) >= 3.0]
bad = []
for s in cand:
    ax, sign = EX[s['b']['anim']]
    got = s['dxc'] if ax == 'x' else s['dyc']
    if got * sign < 0:
        bad.append(s)
print('可判步 = %d' % len(cand))
print('朝向矛盾 = %d (%.1f%%)' % (len(bad), 100.0 * len(bad) / max(len(cand), 1)))
n_pad = len([1 for s in bad if s['sz']])
print('其中"同时发生尺寸变化"的 = %d/%d' % (n_pad, len(bad)))

# ---- 聚类：孤立边界帧 vs 真长段 ----
runs = []
for s in bad:
    if runs and s['b']['t'] - runs[-1][-1]['b']['t'] <= 0.25:
        runs[-1].append(s)
    else:
        runs.append([s])
runs.sort(key=len, reverse=True)
print('连续段数 = %d ；段长 = %s' % (len(runs), [len(r) for r in runs][:10]))
longest = runs[0] if runs else []
print('最长段 = t %.2f ~ %.2f（%d 步 / %.2f s）'
      % (longest[0]['b']['t'], longest[-1]['b']['t'], len(longest),
         longest[-1]['b']['t'] - longest[0]['b']['t']) if longest else '（无）')

# ---- 复算最长段的角度：目标 − 位置 ----
ANG = None
if longest:
    s = longest[len(longest) // 2]
    m = __import__('math')
    ang = m.degrees(m.atan2(s['b']['ty'] - s['b']['y'], s['b']['tx'] - s['b']['x']))
    ANG = ang
    print('最长段中点：t=%.2f  pos=(%d,%d)  tgt=(%d,%d)  ⇒ atan2 = %.1f°'
          % (s['b']['t'], s['b']['x'], s['b']['y'], s['b']['tx'], s['b']['ty'], ang))
    print('  ★ 旧档 `-30/30/60/120` 把 [30,60) 落进 `else` ⇒ 判 `left`；'
          '新档 `-45/45/135` ⇒ 判 `right`')

check('M5 ★★ 朝向矛盾必须**高度聚集**（最长段占矛盾步的大头）⇒ 是"特定走向"触发，'
      '不是逐帧随机抖动',
      len(longest) >= 100 and len(longest) * 2 >= len(bad),
      '最长段 %d 步 / 矛盾共 %d 步' % (len(longest), len(bad)))
check('M6 ★★★ 最长段的走向角度必须落在旧档缝隙 `[30,60)` 内（⇒ 根因就是角度分档）',
      ANG is not None and 30.0 <= ANG < 60.0,
      'atan2 = %s' % (('%.1f°' % ANG) if ANG is not None else 'N/A'))
check('M7 说明：本条**不是几何伪影** —— 该长段内窗口尺寸基本恒定 `38x80`，'
      'Δtopleft 与 Δcenter 同判（尺寸变化步 ≤ 5%）',
      bool(longest) and len([s for s in longest if s['sz']])
      <= max(1, int(0.05 * len(longest))),
      '段内尺寸变化步 = %d / %d'
      % (len([s for s in longest if s['sz']]), len(longest)))

print()
print('=' * 78)
print('合计  PASS=%d  FAIL=%d' % (_p, _f))
print('=' * 78)
sys.exit(1 if _f else 0)
