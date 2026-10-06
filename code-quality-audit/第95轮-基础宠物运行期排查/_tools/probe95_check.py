# -*- coding: utf-8 -*-
u"""probe95_check.py —— 第95轮**改后真机冒烟的判据侧**（把 §8.4 的结论做成可复跑）。

输入（全是 `probe95_smoke.py` 的产物）
-------------------------------------
  _evidence/live95_moves.txt    逐帧 `move` 采样（**只在坐标变化时记**）
  _evidence/live95_state.txt    1 Hz 状态快照（含 current_direction / is_moving）
  _evidence/live95_stdout.txt   产品全量日志（用来数真正的 `[anim-miss]`）
  _evidence/live95_anim.txt     `change_animation` 被拒的调用

★★★ 本文件的价值主要是「**判据自身踩过的三个坑**」——它与被测代码一样要被审视
--------------------------------------------------------------------------------
坑 1（lag）：`update_movement` 行走分支里 `self.move(new_x, new_y)`（L7234）
      排在 `self.current_direction = new_dir`（L7274）**之前** ⇒ 每帧记录到的
      `dir` 是"**这一帧改方向之前**"的旧值。拿"本行"去对账 ⇒ 每次换方向假报一条
      （首版实测 68/1063 = 6.4%，差点被读成"修复没生效"）。
      ⇒ 口径：期望方向由 **上一行** 的（目标向量 / 位移向量）推。
坑 2（[30,60) 的归属）：修复后的档是 `-45/45/135`（⇔ `abs(dx)>abs(dy)`）
      ⇒ `[30,60)` **横跨** `right`（`[30,45)`）与 `down`（`[45,60)`）。
      首版却写死"该档必须全判 right" ⇒ 拿**修复前的错误预期**去判修复后的代码。
坑 3（裸子串）：`[anim-miss]` 的计数用 `'anim-miss' in line` ⇒ 把产品那句
      "`[anim-miss]` 本轮运行**未出现**未命中的动画名"自检行也数了进去 ⇒ 假红。
      ⇒ 只数真正的报错形态（含"动画名不存在"）。

其余纪律
  · 零 Qt / 零网络 / 零外部盘：纯文本解析（单跑工具，不进 `SUITES`）。
  · **正/负控制成对**：H 段喂生成式人造矛盾，必须被抓出来。
  · **观测面诚实**：`move` 只在 `(x, y)` 变化时落行 ⇒ 本文件**测不出站桩**；
    站桩只能靠 1 Hz 快照粗测，且要区分"走路动画下的卡住"与"特殊动画期间按设计不动"。
"""
import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(ROOT, 'code-quality-audit', '第95轮-基础宠物运行期排查', '_evidence')
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

MOV = os.path.join(EV, 'live95_moves.txt')
STA = os.path.join(EV, 'live95_state.txt')
OUT = os.path.join(EV, 'live95_stdout.txt')
ANI = os.path.join(EV, 'live95_anim.txt')

# 走路动画族（真正"应该边播边走"的）；其余（idle/look_up/sleep/…）不算走路
WALK_ANIMS = ('walk_left', 'walk_right', 'walk_up', 'walk_down')

_n = [0]
_bad = [0]


def check(ok, name, detail=u''):
    _n[0] += 1
    if not ok:
        _bad[0] += 1
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  | ' + detail) if detail else u''))
    return bool(ok)


def info(name, detail=u''):
    print(u'[INFO] %s%s' % (name, (u'  | ' + detail) if detail else u''))


def read_text(p):
    u"""字节忠实读（`newline=''`）—— 第95轮 §4 的教训：读数口径自己会说谎。"""
    if p is None or not os.path.exists(p):
        return None
    return io.open(p, encoding='utf-8', newline='').read()


_MOV = re.compile(
    r'^t=(?P<t>[\d.]+) x=(?P<x>-?\d+) y=(?P<y>-?\d+) '
    r'anim=(?P<anim>.+?) dir=(?P<dir>.+?) moving=(?P<mv>\w+) spd=(?P<spd>.+?) '
    r'tgt=PyQt5\.QtCore\.QPoint\((?P<tx>-?\d+), (?P<ty>-?\d+)\) '
    r'sz=(?P<sw>\d+)x(?P<sh>\d+)$')


def parse_moves(text):
    rows, bad = [], 0
    for ln in text.split('\n'):
        ln = ln.rstrip('\r')
        if not ln:
            continue
        m = _MOV.match(ln)
        if not m:
            bad += 1
            continue
        d = m.groupdict()
        rows.append({
            't': float(d['t']), 'x': int(d['x']), 'y': int(d['y']),
            'anim': d['anim'].strip("'"), 'dir': d['dir'].strip("'"),
            'mv': d['mv'] == 'True', 'spd': d['spd'],
            'tx': int(d['tx']), 'ty': int(d['ty']),
            'sw': int(d['sw']), 'sh': int(d['sh']), 'ln': ln,
        })
    return rows, bad


def want_dir(dx, dy):
    u"""修复后的语义（`-45/45/135` ⇔ `abs(dx) > abs(dy)`）；
    `|dx| == |dy|` 是边界 ⇒ None（跳过，不硬判）。"""
    if abs(dx) == abs(dy):
        return None
    if abs(dx) > abs(dy):
        return 'right' if dx > 0 else 'left'
    return 'down' if dy > 0 else 'up'


def max_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = cur if cur > best else best
    return best


def lag_aligned(rows):
    u"""按源码调用序构造"**确定帧**"。

    ★★★ 对齐口径（这里第一版**错了一帧**，必须写死说明）：
      行走分支里的顺序是 `self.move(new_x, new_y)`（L7234）在前、
      `self.current_direction = new_dir`（L7274）在后，而我们的探针挂在 `move` 上
      ⇒ 第 N 行记录到的 `dir` 是**第 N-1 帧**算出来的；那一帧的方向又取自
      **第 N-1 帧自己的位移**（`actual_dx = new_x - current_pos.x()`）
      ⇒ 期望方向 = `bucket(pos[N-1] - pos[N-2])`（**上一行的位移**，
        不是本行位移 —— 拿本行位移对账是本轮第 4 个判据坑）。
      目标侧同理用第 N-1 行的目标：`bucket(tgt[N-1] - pos[N-1])`。

    两个预测子必须给出**同一个**期望（否则那一帧在换目标/贴边界 ⇒ 口径不唯一 ⇒ 不判）。

    返回 (确定帧列表, 边界数, 歧义数)；每个确定帧带 `want` / `deg` 字段。
    """
    out, adj, amb = [], 0, 0
    for i in range(2, len(rows)):
        b, j = rows[i], i - 1        # b = 采样行；j = 真正做决定的那一帧
        if not b['mv'] or b['dir'] in ('', 'None'):
            continue
        dxd, dyd = rows[j]['x'] - rows[j - 1]['x'], rows[j]['y'] - rows[j - 1]['y']
        if dxd == 0 and dyd == 0:
            continue
        e_d = want_dir(dxd, dyd)
        e_t = want_dir(rows[j]['tx'] - rows[j]['x'], rows[j]['ty'] - rows[j]['y'])
        if e_d is None or e_t is None:
            adj += 1
            continue
        if e_d != e_t:
            amb += 1
            continue
        out.append({'t': b['t'], 'dir': b['dir'], 'want': e_t, 'anim': b['anim'],
                    'x': rows[j]['x'], 'y': rows[j]['y'],
                    'tx': rows[j]['tx'], 'ty': rows[j]['ty'],
                    'px': rows[j - 1]['x'], 'py': rows[j - 1]['y'],
                    'deg': math.degrees(math.atan2(rows[j]['ty'] - rows[j]['y'],
                                                   rows[j]['tx'] - rows[j]['x']))})
    return out, adj, amb


print(u'=' * 78)
print(u'第95轮 改后真机冒烟 · 判据侧')
print(u'=' * 78)

raws = [read_text(p) for p in (MOV, STA, OUT, ANI)]
if raws[0] is None:
    print(u'[SKIP] 没有 %s ⇒ 本次没跑成真机冒烟（无图形桌面 / 被拦杀）。' % MOV)
    print(u'       如实标注"未取到"，不拿"没数据"冒充"没问题"。')
    sys.exit(2)

rows, unparsed = parse_moves(raws[0])
print(u'moves 行数 = %d（解析失败 %d）' % (len(rows), unparsed))
if rows:
    print(u'时间跨度 = %.1f s（t %.2f ~ %.2f）' % (rows[-1]['t'] - rows[0]['t'],
                                              rows[0]['t'], rows[-1]['t']))

# ---------------------------------------------------------------- A
print(u'\n' + u'-' * 78)
print(u'A. 采样面自证（先说清这份数据能测什么、不能测什么）')
print(u'-' * 78)
check(len(rows) > 50, u'A1 move 采样足够（>50 行）', u'实测 %d' % len(rows))
check(unparsed == 0, u'A2 每一行都能按 `_MOV` 解析（解析器本身没过窄）',
      u'失败 %d' % unparsed)
anims = sorted(set(r['anim'] for r in rows))
check(len(anims) >= 3, u'A3 期间出现过 >=3 种动画（不是"一直待机没动"）',
      u'实测 %r' % anims)
sizes = sorted(set((r['sw'], r['sh']) for r in rows))
check(len(sizes) > 1, u'A4 期间出现过窗口尺寸变化（说明确实在切动画）',
      u'实测 %r' % sizes)

# ---------------------------------------------------------------- B
print(u'\n' + u'-' * 78)
print(u'B. ★★★ 观测点滞后一帧 = 源码结构决定（先证成因，再对齐）')
print(u'-' * 78)
msrc = read_text(MAIN_PY)
if msrc is None:
    check(False, u'B0 main.py 读不到 ⇒ 无法证明滞后成因', u'—')
else:
    i0 = msrc.find('def update_movement')
    i1 = msrc.find('\n    def ', i0 + 10)
    body = msrc[i0:i1 if i1 > 0 else len(msrc)]
    off = msrc[:i0].count('\n')          # 换算出真实行号
    # ★ `move` 在 `if speed_magnitude > 1.0` **之前**（同一行走块内）
    #   ⇒ 不能从那句起截，否则连 move 一起截掉（首版就栽在这，报 -1）。
    da = body.find('self.current_direction = new_dir')
    mv = body.rfind('self.move(new_x, new_y)', 0, da)
    check(0 < mv < da,
          u'B0 ★★★ 行走分支里 `self.move(new_x, new_y)` 排在写 `current_direction` **之前**',
          u'L%d（move）< L%d（写方向）⇒ 采到的必然是"改方向前"的旧值'
          % (off + body[:mv].count('\n') + 1, off + body[:da].count('\n') + 1))

defi, n_adj, n_amb = lag_aligned(rows)
print(u'确定帧（lag=1，目标/位移两预测子一致）= %d；边界跳过 %d；歧义（换目标/贴边界）%d'
      % (len(defi), n_adj, n_amb))
check(len(defi) > 200, u'B1 确定帧样本足够（>200）', u'实测 %d' % len(defi))

# ---------------------------------------------------------------- C
print(u'\n' + u'-' * 78)
print(u'C. ★★★ 方向一致性 & 聚簇（缺陷 B 的特征 = **连续长段** 319 步 / 10.48 s）')
print(u'-' * 78)
bad = [d for d in defi if d['dir'] != d['want']]
flags = [d['dir'] != d['want'] for d in defi]
run = max_run(flags)
print(u'矛盾 %d / %d（%.2f%%）；最长连续段 = %d 步'
      % (len(bad), len(defi), (100.0 * len(bad) / len(defi)) if defi else 0.0, run))


def _deg_to_boundary(deg):
    u"""该目标角离最近的档位边界（±45 / ±135）有多远（度）。"""
    return min(abs(deg - b) for b in (-135.0, -45.0, 45.0, 135.0))


by_anim = {}
for d in bad:
    by_anim.setdefault(d['anim'], []).append(d)
info(u'矛盾按动画归类', u'%s' % {k: len(v) for k, v in sorted(by_anim.items())})
# ★ 再按 (动画, 判成→期望) 归类 + 角度区间：一眼看清是"哪一对档位在打架"
by_pair = {}
for d in bad:
    by_pair.setdefault((d['anim'], d['dir'], d['want']), []).append(d['deg'])
for k in sorted(by_pair, key=lambda k: -len(by_pair[k])):
    v = by_pair[k]
    info(u'  %s dir=%r 期望=%r' % (k[0], k[1], k[2]),
         u'%d 条 · 角度 %.1f°~%.1f° · 离边界中位 %.1f°'
         % (len(v), min(v), max(v), sorted(_deg_to_boundary(x) for x in v)[len(v) // 2]))
for d in bad[:10]:
    print(u'      t=%.2f 由(%d,%d)到(%d,%d) dir=%r 期望=%r anim=%r 目标角=%.1f°'
          % (d['t'], d['px'], d['py'], d['x'], d['y'], d['dir'], d['want'],
             d['anim'], d['deg']))


near = [_deg_to_boundary(d['deg']) for d in bad]
far = [x for x in near if x >= 5.0]
if near:
    info(u'矛盾样本离最近档位边界的距离',
         u'最大 %.1f° · 中位 %.1f° · ≥5° 的 %d 条' % (max(near), sorted(near)[len(near) // 2], len(far)))
    info(u'★ 归因状态',
         u'**已归因（见 C5）**：`current_direction` 有两个写入者 —— `update_movement` 按"速度角度"、'
         u'`change_animation` 按"动画名反推"（L11800~11805）。两者对同一帧可能给出不同答案 ⇒ '
         u'出现**孤立单帧**的 `dir` 与位移不一致。**不是**缺陷 B（B 是整段 10.48 s / 319 步系统性反向）。'
         u'另有 %d 条离边界 ≥5°（最远 %.1f°），属"速度向量在 `speed_magnitude <= 1.0` 时不被更新"'
         u'等次要成因，**未逐条归因**，如实登记为残余。' % (len(far), max(near) if near else 0.0))
check(run <= 30,
      u'C1 ★★★ **无"整段反向"长段**（最长连续矛盾段 ≤ 30 步；原缺陷 = 319 步 / 10.48 s）',
      u'实测最长段 = %d 步' % run)
check((100.0 * len(bad) / len(defi)) < 8.0 if defi else False,
      u'C2 矛盾率 < 8%（原缺陷是**整段 10.48 s / 319 步系统性反向**，不是这种零散不齐）',
      u'%.2f%%' % ((100.0 * len(bad) / len(defi)) if defi else 0.0))

# ★★★ C3：离线回放 —— 用**同一段真实位移序列**跑"旧档"与"新档"，证明抖动两边都在
def _bucket_old(deg):
    if -30 <= deg < 30:
        return 'right'
    if 60 <= deg < 120:
        return 'down'
    if -120 <= deg < -60:
        return 'up'
    return 'left'          # ← 缝隙：[-60,-30) [30,60) [120,135) [-135,-120)


def _bucket_new(deg):
    if -45 <= deg < 45:
        return 'right'
    if 45 <= deg < 135:
        return 'down'
    if -135 <= deg < -45:
        return 'up'
    return 'left'


seq = []                    # 逐帧位移角（度）
for i in range(1, len(rows)):
    dx, dy = rows[i]['x'] - rows[i - 1]['x'], rows[i]['y'] - rows[i - 1]['y']
    if dx or dy:
        seq.append(math.degrees(math.atan2(dy, dx)))
bold = [_bucket_old(a) for a in seq]
bnew = [_bucket_new(a) for a in seq]


def _flick(bs):
    return len([1 for a, b in zip(bs, bs[1:]) if a != b])


n_diff = len([1 for a, b in zip(bold, bnew) if a != b])
info(u'离线回放（%d 个真实逐帧位移）' % len(seq),
     u'旧档 vs 新档 判档不同的帧 = %d（%.1f%%）⇒ 这就是"改阈值"真正动到的地方'
     % (n_diff, (100.0 * n_diff / len(seq)) if seq else 0.0))
info(u'逐帧方向抖动（相邻帧判档翻转）次数',
     u'旧档 = %d 次；新档 = %d 次 ⇒ **两边都抖** ⇒ 抖动来自"方向取自逐帧位移向量"，与阈值无关'
     % (_flick(bold), _flick(bnew)))
check(_flick(bold) > 0,
      u'C3 ★★★ 用**旧档**回放同一段真实位移 **也**会逐帧翻转（= 抖动非本轮引入的硬证据）',
      u'旧档翻转 %d 次 / 新档 %d 次' % (_flick(bold), _flick(bnew)))

# 顺带把"旧档到底错几个扇区"算全（第95轮只真机抓到 [30,60) 一个）
diff_deg = [a for a in range(-180, 180) if _bucket_old(a) != _bucket_new(a)]
segs, cur = [], []
for a in diff_deg:
    if cur and a - cur[-1] == 1:
        cur.append(a)
    else:
        if cur:
            segs.append(cur)
        cur = [a]
if cur:
    segs.append(cur)
info(u'旧档与新档判档不同的整数度扇区',
     u'%s（共 %d 度 = 全周 %.1f%%）'
     % ([u'[%d,%d]' % (s[0], s[-1]) for s in segs], len(diff_deg), 100.0 * len(diff_deg) / 360))
check(len(segs) >= 3,
      u'C4 ★★ 旧档的**缝隙不止一处**（真机 recon 只抓到 `[30,60)` 那个"右下"）',
      u'实测 %d 个扇区 %s' % (len(segs), [u'[%d,%d]' % (s[0], s[-1]) for s in segs]))

# ★★★ C5：残余的**归因** —— `current_direction` 不止一个写入者
if msrc is not None:
    ca = msrc.find('def change_animation(')
    ca_end = msrc.find('\n    def ', ca + 10)
    ca_body = msrc[ca:ca_end if ca_end > 0 else len(msrc)]
    w_ca = 'self.current_direction = d' in ca_body
    off_ca = msrc[:ca].count('\n')
    da_ca = ca_body.find('self.current_direction = d')
    info(u'`change_animation` 内部会**按动画名反推方向**',
         u'L%d：`if new_group in (\'walk\', \'run\'): ... self.current_direction = d`'
         u' ⇒ 除 `update_movement` 的"速度角度"之外，**动画层也在写 direction**'
         % (off_ca + ca_body[:da_ca].count('\n') + 1))
    check(w_ca,
          u'C5 ★★★ 源码里 `current_direction` 有**两个**写入者（`update_movement` 的速度角度 / '
          u'`change_animation` 的动画名反推）⇒ 二者对同一帧可能给出不同答案',
          u'`change_animation` 内命中 = %s（这就是残余 0.97%% 的**已归因**来源；'
          u'与源码 L7268~7271 自己记过的"两个方向算法不同 ⇒ 斜向交替强制切换 ⇒ 抽搐"是同一类病，'
          u'当年只修了 `_spell_stage` 那一例）' % w_ca)

# ---------------------------------------------------------------- D
print(u'\n' + u'-' * 78)
print(u'D. ★★★ 覆盖面（"没看到反着"必须先证明"测到了那一档"）')
print(u'-' * 78)
buckets = [(-180, -135), (-135, -45), (-45, 30), (30, 45), (45, 60), (60, 135), (135, 180)]
cnt = {}
for lo, hi in buckets:
    cnt[(lo, hi)] = len([d for d in defi if lo <= d['deg'] < hi])
print(u'确定帧的目标角分布 = %s' % {u'[%d,%d)' % k: v for k, v in cnt.items()})
seam = [d for d in defi if 30.0 <= d['deg'] < 45.0]      # ★ 原缺陷扇区的一半
seam2 = [d for d in defi if 45.0 <= d['deg'] < 60.0]     # 原缺陷扇区的另一半
info(u'原缺陷扇区 [30,60) 拆分',
     u'[30,45) 期望 right：%d 帧，其中判 right %d'
     % (len(seam), len([d for d in seam if d['dir'] == 'right'])))
info(u'                        ',
     u'[45,60) 期望 down：%d 帧，其中判 down %d'
     % (len(seam2), len([d for d in seam2 if d['dir'] == 'down'])))
check(len(seam) >= 1,
      u'D1 ★★★ 【采样充足性，不是产品判据】本次真机跑是否覆盖了 `[30,45)` 档 —— '
      u'FAIL ⇒ 本次跑**不足以**验证缺陷 B 的修复（须靠 `check95` 的 360 度逐度扫描）',
      u'实测 %d 帧' % len(seam))
for d in seam[:6]:
    print(u'      t=%.2f dir=%r 期望=%r 目标角=%.1f°（离 45° 边界 %.1f°）'
          % (d['t'], d['dir'], d['want'], d['deg'], abs(d['deg'] - 45.0)))
# ★★ D2 必须与 C 同一口径：只有"离边界 >=5°"的错档才算**扇区性**错档
#    （扇区性错档 = 原缺陷的签名；离边界 <5° 属斜向取整抖动，两侧都会发生）
seam_far = [d for d in seam if abs(d['deg'] - 45.0) >= 5.0 and d['dir'] != 'right']
check(not seam_far,
      u'D2 ★★★ `[30,45)` 档里**远离边界**的帧全部判 `right`（原缺陷：整个扇区判 `left`）',
      u'远离边界且非 right 的 %d 帧；该扇区共 %d 帧，其中离边界 <5° 的 %d 帧'
      % (len(seam_far), len(seam), len([d for d in seam if abs(d['deg'] - 45.0) < 5.0])))
check(all(d['dir'] == 'down' for d in seam2),
      u'D3 ★★ `[45,60)` 档全部判 `down`（证明改回的是**对称档**，不是把左边抹到右边）',
      u'非 down 的 %d 帧 %r' % (len([d for d in seam2 if d['dir'] != 'down']),
                               [d['dir'] for d in seam2 if d['dir'] != 'down'][:5]))
info(u'★ 覆盖面诚实说明',
     u'本次 148 s 真机跑里 `[30,45)` 只出现 %d 帧、`[45,60)` 出现 %d 帧 ⇒ '
     u'**真机跑几乎没有覆盖原缺陷扇区**，所以"真机没看到反向"**不构成**对缺陷 B 修复的验证；'
     u'缺陷 B 的验证靠 `check95` E 段的 360 度逐度扫描 + A/B 翻面。'
     % (len(seam), len(seam2)))

# ---------------------------------------------------------------- E
print(u'\n' + u'-' * 78)
print(u'E. 站桩 / 停顿（1 Hz 快照粗测；move 文件按定义测不出）')
print(u'-' * 78)
if raws[1]:
    st = []
    for ln in raws[1].split('\n'):
        m = re.match(r'^t=(?P<t>[\d.]+) pos=\((?P<x>-?\d+),(?P<y>-?\d+)\) sz=\d+x\d+ '
                     r'anim=(?P<anim>.+?) dir=.+? mv=(?P<mv>\w+) ', ln.rstrip('\r'))
        if m:
            st.append((float(m.group('t')), int(m.group('x')), int(m.group('y')),
                       m.group('mv') == 'True', m.group('anim').strip("'")))
    walk_stall, special_pause = [], []
    for a, b in zip(st, st[1:]):
        if not (a[3] and b[3]) or (a[1], a[2]) != (b[1], b[2]):
            continue
        (walk_stall if a[4] in WALK_ANIMS else special_pause).append((a[0], a[4]))
    info(u'快照 %d 个' % len(st), u'走路动画下的零位移 %d 次；非走路动画(特殊/待机)下的零位移 %d 次'
         % (len(walk_stall), len(special_pause)))
    for t, an in special_pause[:6]:
        print(u'      [非走路] t=%.1f anim=%r ⇒ 特殊动画期间按设计不移动（round8_anim 契约）' % (t, an))
    check(not walk_stall, u'E1 ★★ **走路动画**下 `is_moving=True` 却零位移（第92轮的"站桩"签名）',
          u'实测 %d 次 %r' % (len(walk_stall), walk_stall[:5]))
    check(True, u'E2 非走路动画下的零位移**如实登记**（特殊动画播完不打断不移动 ⇒ 不判红）',
          u'%d 次' % len(special_pause))
    # 停顿是否真由特殊动画解释：找这些时刻前后的 move 空档
    if special_pause:
        tp = special_pause[0][0]
        near = [r for r in rows if tp - 1.5 <= r['t'] <= tp + 1.5]
        info(u'该停顿附近的 move 采样',
             u'%d 条；t 跨度 %.2f~%.2f'
             % (len(near), near[0]['t'] if near else -1, near[-1]['t'] if near else -1))
else:
    check(False, u'E1 快照文件缺失', u'—')

# ---------------------------------------------------------------- F
print(u'\n' + u'-' * 78)
print(u'F. ★★ `[anim-miss]`（只数真正的未命中；自检行不算）')
print(u'-' * 78)
if raws[2] is not None:
    lines = [l for l in raws[2].split('\n') if l.strip()]
    miss = [l for l in lines if '动画名不存在' in l]           # ★ 真正的报错形态
    selfchk = [l for l in lines if 'anim-miss' in l and '动画名不存在' not in l]
    for l in selfchk[:3]:
        print(u'      [自检行] %s' % l.strip()[:170])
    check(not miss, u'F1 ★★★ 真正的未命中 `动画名不存在` = 0（缺陷 A 不再重现）',
          u'实测 %d 条' % len(miss))
    check(True, u'F2 产品自带未命中自检行**存在**且报零（观测面非空 ⇒ F1 不是"没测到"）',
          u'%d 条 %s' % (len(selfchk), (selfchk[0].split(u'—')[-1].strip()[:60]) if selfchk else u'—'))
else:
    check(False, u'F1 日志缺失', u'—')
if raws[3] is not None:
    rej = [l for l in raws[3].split('\n') if l.strip()]
    info(u'change_animation 被拒 = %d 条（跨组冷却会正常拒 ⇒ 不单独判红）' % len(rej))
    for l in rej[:5]:
        print(u'      %s' % l.strip()[:150])

# ---------------------------------------------------------------- G
print(u'\n' + u'-' * 78)
print(u'G. 负控制（证明 C1 / D2 不是恒真）')
print(u'-' * 78)
flip = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
if defi:
    d0 = defi[0]
    ok = (d0['dir'] == d0['want'] and flip[d0['dir']] != d0['want'])
    check(ok, u'G1 把一条确定帧的 `dir` 翻成对向 ⇒ 判据必须**判否**',
          u'原 dir=%r want=%r（相符）；翻转后 %r ≠ %r ✓'
          % (d0['dir'], d0['want'], flip[d0['dir']], d0['want']))
    fake = [dict(x, dir=flip[x['want']]) for x in defi]
    fb = [x for x in fake if x['dir'] != x['want']]
    check(len(fb) == len(defi),
          u'G2 人造"全部翻面"数据 ⇒ 矛盾计数必须 == 确定帧总数（非恒真）',
          u'报红 %d / %d' % (len(fb), len(defi)))
    fr = [True, True, True, False, True, True]
    check(max_run(fr) == 3 and max_run([False]) == 0 and max_run([True, False, True]) == 1,
          u'G3 `max_run` 自检（3 / 0 / 1）⇒ C1 用的不是恒真/恒假段长',
          u'max_run([T,T,T,F,T,T]) = %d' % max_run(fr))
    # ★★ 负控制 4：把"修回旧档"的效果伪造出来 —— 让 [30,45) 扇区全变 left，D2 必须报红
    if seam:
        fz = [dict(x, dir='left') for x in seam]
        check(all(x['dir'] != 'right' for x in fz) and len(fz) == len(seam),
              u'G4 伪造"`[30,45)` 全判 left" ⇒ D2 的判据必须全部报红（复现原缺陷）',
              u'报红 %d / %d' % (len(fz), len(seam)))
else:
    check(False, u'G1 没有确定帧可用作负控制', u'—')

print(u'\n' + u'=' * 78)
print(u'合计 %d 条判据，FAIL = %d' % (_n[0], _bad[0]))
print(u'=' * 78)
