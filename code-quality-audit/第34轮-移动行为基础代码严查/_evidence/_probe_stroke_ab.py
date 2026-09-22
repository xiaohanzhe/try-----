# -*- coding: utf-8 -*-
"""探针 23 号：抚摸判据修复 A/B 对照（旧判据 vs 新判据）。

判据来源
--------
  A（旧）：从 git 父版本 commit 里取 main.py 的那段（`has_ball` 式硬取证）
  B（新）：从当前工作区 main.py 取同一段

两个版本都**逐字抽取**、exec 成函数，喂同一批轨迹 —— 避免"重写不一致"。
参照系：A 的源码必须与 `git show <父提交>:ralsei_pet/src/main.py` 逐字一致。
"""
import io
import math
import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN_REL = 'ralsei_pet/src/main.py'
MAIN = os.path.join(ROOT, MAIN_REL)

GIT = shutil.which('git')
print('=' * 72)
print('探针 23：抚摸判据 A/B 对照')
print('=' * 72)
print('git =', GIT)
print()

# ---------- 取 A（父版本，即旧判据） ----------
def git_out(args):
    r = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), \
        r.stderr.decode('utf-8', 'replace')


rc, out, err = git_out([GIT, 'rev-parse', 'HEAD'])
print('HEAD =', out.strip(), '(rc=%d)' % rc)
rc2, out2, _ = git_out([GIT, 'rev-parse', 'HEAD~1'])
print('HEAD~1 =', out2.strip(), '(rc=%d)' % rc2)
rev = out2.strip()
rc3, old_src, err3 = git_out([GIT, 'cat-file', 'blob',
                              '%s:%s' % (rev, MAIN_REL)])
if rc3 != 0 or not old_src:
    print('[FAIL] 取父版本 main.py 失败 rc=%d %s' % (rc3, err3[:300]))
    sys.exit(1)
print('父版本 main.py 取到 %d 字符' % len(old_src))
print()

NEW_SRC = io.open(MAIN, 'r', encoding='utf-8', errors='replace').read()
print('工作区 main.py 取到 %d 字符' % len(NEW_SRC))
print()


def extract_func(src, marker_old):
    """按内容标记定位循环体并抽成函数。

    marker_old=True  -> 旧版（含 'current_dir' 主轴判据）
    marker_old=False -> 新版（含 'abs(move_dx) >= 1' 独立计数）
    """
    lines = src.splitlines()
    # 找 direction_changes = 0 且其后紧跟 prev_dx = None 的那一处
    start = None
    for i, l in enumerate(lines):
        if 'direction_changes = 0' in l and i + 1 < len(lines) \
                and 'prev_dx = None' in lines[i + 1]:
            # 必须确认这是那段抚摸判据（附近有 movement_history 或 prev_dy）
            near = '\n'.join(lines[max(0, i - 40):i + 40])
            if 'prev_dy' in near and ('movement_history' in near or '_last' in near):
                start = i
                break
    if start is None:
        return None, '未找到 direction_changes=0 段落'
    end = None
    for j in range(start, min(start + 60, len(lines))):
        if 'prev_dy = move_dy' in lines[j]:
            end = j
            break
    if end is None:
        return None, '未找到结尾 prev_dy = move_dy'
    chunk = lines[start:end + 1]
    indents = [len(l) - len(l.lstrip()) for l in chunk if l.strip()]
    base = min(indents)
    body = '\n'.join(l[base:] if len(l) >= base else l for l in chunk)
    # 去掉赋值首行，改成函数签名
    body_lines = body.splitlines()[1:]
    func = ('def dc_of(history):\n'
            '    class _S:\n'
            '        pass\n'
            '    self = _S()\n'
            "    self._pet_detection_state = {'movement_history': history}\n"
            '    direction_changes = 0\n'
            + '\n'.join('    ' + l for l in body_lines) + '\n'
            '    return direction_changes\n')
    return func, None


f_old, e_old = extract_func(old_src, True)
f_new, e_new = extract_func(NEW_SRC, False)
if e_old or e_new:
    print('[FAIL] 抽取失败: old=%s new=%s' % (e_old, e_new))
    sys.exit(1)

# 判别力自证：两版源码必须**不同**（否则 A/B 无意义）
if f_old.strip() == f_new.strip():
    print('[FAIL] 新旧源码逐字相同 ⇒ A/B 无鉴别力')
    sys.exit(1)
print('[PASS] 新旧源码不同，A/B 有鉴别力')
print()
print('--- 旧判据关键行 ---')
for l in f_old.splitlines():
    if 'current_dir' in l or 'prev_dir' in l:
        print('   ', l.strip())
print('--- 新判据关键行 ---')
for l in f_new.splitlines():
    if 'abs(move_dx) >= 1' in l or 'abs(move_dy) >= 1' in l:
        print('   ', l.strip())
print()

ns_o, ns_n = {}, {}
exec(compile(f_old, '<old-from-git>', 'exec'), ns_o)
exec(compile(f_new, '<new-worktree>', 'exec'), ns_n)
dc_old, dc_new = ns_o['dc_of'], ns_n['dc_of']


def seq(pairs):
    return [(dx, dy, math.hypot(dx, dy)) for dx, dy in pairs]


random.seed(20260922)


# =====================================================================
# ★ 关键：按**真实像素量级**构造轨迹（探针 22 的教训）
#   产品入历史门槛是 3 < distance < 50（像素）。所以每一步的位移
#   必须落在 3~50px 区间，才是"真实的鼠标事件差分量"。
#   单步 10px 差分量 = 采样频率与手速的正常组合（8ms × 1250px/s 也算）。
#   这里统一用"单步 8~15px"，并在横纵两轴都给出同量级的抖动。
# =====================================================================


def sim(builder, n_cycle=3):
    """统一过产品门槛筛步。"""
    h = seq(builder(n_cycle))
    return [(dx, dy, d) for (dx, dy, d) in h if 3 < d < 50]


# 6 条典型轨迹（真实像素量级）
def T1(n):
    """纯水平往返：单步 ±12px"""
    p = []
    for _ in range(n):
        for t in range(20):
            p.append((12.0 * math.cos(t / 20 * math.pi * 2), 0.0))
        for t in range(20):
            p.append((-12.0 * math.cos(t / 20 * math.pi * 2), 0.0))
    return p


def T2(n):
    """水平往返 + 纵向抖动 ±4px（约单步 1/3，尚不足以夺走主轴）"""
    p = []
    for _ in range(n):
        for t in range(20):
            p.append((12.0 * math.cos(t / 20 * math.pi * 2),
                      random.uniform(-4.0, 4.0)))
        for t in range(20):
            p.append((-12.0 * math.cos(t / 20 * math.pi * 2),
                      random.uniform(-4.0, 4.0)))
    return p


def T3(n):
    """垂直往返 + 横向抖动 ±4px"""
    p = []
    for _ in range(n):
        for t in range(20):
            p.append((random.uniform(-4.0, 4.0),
                      12.0 * math.cos(t / 20 * math.pi * 2)))
        for t in range(20):
            p.append((random.uniform(-4.0, 4.0),
                      -12.0 * math.cos(t / 20 * math.pi * 2)))
    return p


def T4(n):
    """自然弧线：横向 15px + 纵向 12px（两轴同量级 → 主轴频繁翻转）"""
    p = []
    for _ in range(n):
        for t in range(40):
            ang = t / 40 * math.pi * 2
            p.append((15.0 * math.sin(ang), 12.0 * (1 - math.cos(ang))))
    return p


def T5(n):
    """自然弧线 + 抖动（最像真人）"""
    p = []
    for _ in range(n):
        for t in range(40):
            ang = t / 40 * math.pi * 2
            p.append((15.0 * math.sin(ang) + random.uniform(-3.0, 3.0),
                      12.0 * (1 - math.cos(ang)) + random.uniform(-3.0, 3.0)))
    return p


def T6(n):
    """人真撸猫：斜向 45° 来回（两轴几乎等量 → 主轴摇摆）"""
    p = []
    for _ in range(n):
        for t in range(30):
            v = 10.0 * math.cos(t / 30 * math.pi * 2)
            p.append((v + random.uniform(-2.0, 2.0),
                      v + random.uniform(-2.0, 2.0)))
    return p


def T7(n):
    """原地噪声：每步 <3px（应被产品门槛滤掉）"""
    return [(random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0))
            for _ in range(60)]


def T8(n):
    """单向横扫（不往返），不该触发"""
    return [(12.0, 0.0) for _ in range(30)]


CASES = [
    ('T1 纯水平往返', T1, True),
    ('T2 水平往返+纵抖±4', T2, True),
    ('T3 垂直往返+横抖±4', T3, True),
    ('T4 自然弧线(15,12)', T4, True),
    ('T5 自然弧线+抖动', T5, True),
    ('T6 斜向45°来回', T6, True),
    ('T7 原地噪声（不该触发）', T7, False),
    ('T8 单向横扫（不该触发）', T8, False),
]

print('%-32s %-8s %-8s %-10s %s' % ('用例', '旧dc', '新dc', '阈值2', '判定'))
print('-' * 78)
old_ok = new_ok = total = 0
fixed = []
broke = []
for name, builder, should_fire in CASES:
    total += 1
    h = sim(builder)
    o = dc_old(h) if len(h) >= 5 else 0
    nw = dc_new(h) if len(h) >= 5 else 0
    o_fire = o >= 2
    n_fire = nw >= 2
    if o_fire == should_fire:
        old_ok += 1
    if n_fire == should_fire:
        new_ok += 1
    if (not o_fire) and n_fire and should_fire:
        fixed.append(name)
    if o_fire and (not n_fire):
        broke.append(name)
    mark = ''
    if o_fire != n_fire:
        mark = '  ← ★判据结果不同（旧%s→新%s）' % ('✓' if o_fire else '✗',
                                                  '✓' if n_fire else '✗')
    print('%-32s %-8d %-8d %-10s %s%s'
          % (name, o, nw, '期望触发' if should_fire else '期望不触发',
             '旧%s/新%s' % ('✓' if o_fire else '✗', '✓' if n_fire else '✗'), mark))

print()
print('-' * 78)
print('  旧判据符合预期: %d/%d' % (old_ok, total))
print('  新判据符合预期: %d/%d' % (new_ok, total))
print('  修复生效（旧不触发→新触发）: %s' % (fixed if fixed else '（无）'))
print('  修复引入退化           : %s' % (broke if broke else '（无）'))
print()
if fixed and not broke:
    print('[PASS] 修复生效且无退化')
elif not fixed:
    print('[FAIL] 修复未生效 —— 新判据与旧判据行为一致，C 缺陷不成立或被误诊')
sys.exit(0 if (fixed and not broke) else 1)
