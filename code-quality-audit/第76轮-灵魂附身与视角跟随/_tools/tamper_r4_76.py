# -*- coding: utf-8 -*-
"""check_r4_76 的**鉴别力体检**：把 `soul.state.size` 改回 `size()`，判据必须报红。

背景（第76轮真事）：产品里误写 `soul.state.size()`（`size` 其实是 property），
套件第一版因为**夹具也把 size 造成了方法**而全绿 —— 离线假绿、真机才暴露。
所以这里做一次定点篡改自证：改回坏写法 ⇒ 必须至少 2 条报红；还原 ⇒ 全绿。

★ 纪律：篡改只在**内存副本**里做（不写盘、不动工作区）。
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check_r4_76.py')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_failed = 0


def note(msg=''):
    print(msg)


def run_check():
    r = subprocess.run([sys.executable, CHECK], capture_output=True, cwd=ROOT)
    out = r.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'\[FAIL\] (.*)', out)
    passes = re.findall(r'\[PASS\] (.*)', out)
    return len(passes), fails


with io.open(MAIN, 'r', encoding='utf-8') as f:
    _orig = f.read()

note('=== check_r4_76 鉴别力体检 ===')
note('main.py 字节数 = %d' % len(_orig.encode('utf-8')))
note()

# ---- ① 基线：现在必须全绿 ----
p0, f0 = run_check()
note('① 未篡改：PASS=%d FAIL=%d' % (p0, len(f0)))
if f0:
    note('   !! 基线就报红，体检无意义：')
    for x in f0:
        note('      - %s' % x)
    _failed += 1
note()

# ---- ② 定点篡改：把裸属性改回方法调用 ----
_bad = _orig.replace('soul.state.size)', 'soul.state.size())')
if _bad == _orig:
    note('!! 篡改没命中（源码里没有 `soul.state.size)`）⇒ 判据过时')
    _failed += 1
else:
    note('② 篡改：`soul.state.size)` → `soul.state.size())`（1 处）')
    # 用临时文件跑：把 main.py 换成坏版本 → 跑 → 立刻还原
    _backup = _orig
    try:
        with io.open(MAIN, 'w', encoding='utf-8', newline='') as f:
            f.write(_bad)
        p1, f1 = run_check()
        note('   篡改后：PASS=%d FAIL=%d' % (p1, len(f1)))
        for x in f1:
            note('      [FAIL] %s' % x)
        need = [x for x in f1 if 'size()' in x or 'size' in x]
        if len(need) >= 2:
            note('   ✅ 命中 ≥2 条（含 size property 判据）⇒ 判据有鉴别力')
        else:
            note('   ❌ 报红条数不足（需要 ≥2 条与 size 相关）⇒ 判据鉴别力不够')
            _failed += 1
    finally:
        with io.open(MAIN, 'w', encoding='utf-8', newline='') as f:
            f.write(_backup)
    note()

# ---- ③ 还原自证：逐字节一致 + 再跑一次全绿 ----
with io.open(MAIN, 'r', encoding='utf-8') as f:
    _now = f.read()
if _now == _orig:
    note('③ 还原：逐字节一致 ✅')
else:
    note('③ 还原：!! 不一致（差 %d 字符）' % (len(_now) - len(_orig)))
    _failed += 1

p2, f2 = run_check()
note('③ 还原后：PASS=%d FAIL=%d' % (p2, len(f2)))
if f2:
    note('   !! 还原后仍报红：')
    for x in f2:
        note('      - %s' % x)
    _failed += 1
note()

note('=== 体检结论：%s ===' % ('PASS' if _failed == 0 else 'FAIL(%d)' % _failed))
sys.exit(1 if _failed else 0)
