# -*- coding: utf-8 -*-
u"""第92轮变异测试：把本轮每一处修复**逐个打回原形**，`check92` 必须报红。

为什么必须有它（记忆铁律）
--------------------------
「**夹具不保真 = 报假问题**」（比报红更危险）与「**恒真判据比不写还危险**」：
一条判据只有在"破坏它就会红"时才叫守卫。本脚本对每一处修复做一次**定向变异**，
断言**指定的那条判据**（而不是"随便红一条"）变成 FAIL。

负控制
------
`M0 注释改写`：不改变任何语义的变异**必须** FAIL=0 —— 证明本夹具不是"一改就红"。

做法
----
把 `main.py` 复制成 `_mut/main_<id>.py`，用文本替换做定点变异，然后以
`CHECK92_MUTATION_HARNESS=1 CHECK92_MAIN=<副本>` 跑 `check92.py`，解析它的输出。
产品代码与仓库文件**全程只读**（副本写在临时区，跑完即删）。
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check92.py')
PY = sys.executable or r'C:\Python311\python.exe'

TMP = os.environ.get('MUT92_TMP') or os.path.join(
    os.environ.get('TEMP', r'C:\Users\23002\AppData\Local\Temp'), '_mut92')
if os.path.isdir(TMP):
    shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

with open(MAIN, encoding='utf-8') as _fh:
    SRC = _fh.read()

# ------------------------------------------------------------------ 变异清单
# (id, 说明, 期望变成 FAIL 的判据子串, old, new)
MUTS = [
    ('M0', '负控制：只改注释（无语义变化）⇒ 必须 FAIL=0', None,
     '# ★★ 第92轮：**位移小数余量**', '# ★★ 第92轮：**位移小数余量（改写）**'),
    ('M1', '取整前不再加回余量', 'A2',
     'direction_x * move_distance + self._subpixel_x',
     'direction_x * move_distance'),
    ('M2', '结转赋值改成恒 0（等于不结转）', 'A4',
     '_carry_x = _raw_x - new_x', '_carry_x = 0.0'),
    ('M3', '近距减速去掉下限', 'B1',
     'target_move_speed = max(self.speed * (distance / 50.0), 1.0)',
     'target_move_speed = self.speed * (distance / 50.0)'),
    ('M4', '情绪因子之后去掉第二道下限', 'B7',
     'target_final_speed = max(target_move_speed * self._cached_mood_factor, 1.0)',
     'target_final_speed = target_move_speed * self._cached_mood_factor'),
    ('M5', '速度恢复成旧的系数形态（被压出配置区间）', 'C1',
     '_pos_lo, _pos_hi = _speed_pos.get(dominant_emotion, (0.25, 0.65))',
     '_pos_lo, _pos_hi = 0.2, 0.4\n        self.speed = random.uniform(self.min_speed * _pos_lo, '
     'self.max_speed * _pos_hi)\n        _pos_lo, _pos_hi = _speed_pos.get(dominant_emotion, (0.25, 0.65))'),
    # ⚠️ 锚点用"8 空格缩进"的声明行（`init_movement` / `generate_new_move_target`
    #    都是 8 空格；到达分支是 16 空格，不会误伤）。`replace(..., 1)` 打第一条 = init。
    ('M6', '`init_movement` 不再预声明余量字段', 'A1',
     '        self._subpixel_x = 0.0\n        self._subpixel_y = 0.0\n',
     ''),
    ('M7', '第二道下限被换成 min（形状变了）', 'B7',
     'target_final_speed = max(target_move_speed * self._cached_mood_factor, 1.0)',
     'target_final_speed = min(target_move_speed * self._cached_mood_factor, 1.0)'),
    ('M8', '把 round 去掉（回到 int 截断）', 'A2',
     'new_x = int(round(_raw_x))', 'new_x = int(_raw_x)'),
    ('M9', '到达处不再清零余量', 'D1',
     '                self.current_speed_x = 0\n                self.current_speed_y = 0\n'
     '                # ★ 第92轮：到达即清位移余量（下一段从干净状态起步）\n'
     '                self._subpixel_x = 0.0\n                self._subpixel_y = 0.0',
     '                self.current_speed_x = 0\n                self.current_speed_y = 0\n'
     '                # ★ 第92轮：到达即清位移余量（下一段从干净状态起步）'),
    ('M10', '另起一处"取整不结转"的旧写法', 'D3',
     '                # 计算实际移动向量\n',
     '                new_x = int(round(current_pos.x() + direction_x * move_distance))\n'
     '                # 计算实际移动向量\n'),
]

_passed = 0
_failed = []


def run_check(main_path):
    env = dict(os.environ)
    env['CHECK92_MUTATION_HARNESS'] = '1'
    env['CHECK92_MAIN'] = main_path
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([PY, CHECK], capture_output=True, cwd=HERE, env=env, timeout=300)
    out = r.stdout.decode('utf-8', 'replace')
    return out, r.returncode


print('=' * 70)
print('第92轮变异测试：%d 个变异' % len(MUTS))
print('=' * 70)

for mid, desc, expect, old, new in MUTS:
    if old not in SRC:
        print('[SETUP-FAIL] %s %s —— 变异锚点找不到（产品代码已变？）' % (mid, desc))
        _failed.append(mid)
        continue
    mutated = SRC.replace(old, new, 1)
    path = os.path.join(TMP, 'main_%s.py' % mid)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(mutated)

    out, rc = run_check(path)
    m = re.search(r'第92轮：PASS=(\d+) FAIL=(\d+)', out)
    n_fail = int(m.group(2)) if m else -1
    fail_lines = [l for l in out.splitlines() if l.startswith('[FAIL]')]

    if expect is None:
        ok = (n_fail == 0 and rc == 0)
        detail = 'FAIL=%d rc=%d' % (n_fail, rc)
    else:
        hit = [l for l in fail_lines if expect in l]
        ok = bool(hit)
        detail = 'expect=%s hit=%s FAIL=%d' % (
            expect, (hit[0][:80] if hit else 'NONE'), n_fail)

    if ok:
        _passed += 1
        print('[OK]   %s %s    %s' % (mid, desc, detail))
    else:
        _failed.append(mid)
        print('[MISS] %s %s    %s' % (mid, desc, detail))
        for l in fail_lines[:6]:
            print('         %s' % l[:110])

shutil.rmtree(TMP, ignore_errors=True)

print('=' * 70)
print('变异测试：OK=%d MISS=%d' % (_passed, len(_failed)))
if _failed:
    print('未达成：%s' % _failed)
print('=' * 70)
sys.exit(0 if not _failed else 1)
