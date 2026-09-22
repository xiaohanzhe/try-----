# -*- coding: utf-8 -*-
"""鉴别力体检（§5 铁律：回归锁必须有鉴别力，两侧同值 = 没测）。

做法：把 floor_manager.py 的修复**暂时回退**成 `return i - 1`，跑套件，
      必须报红（rc=1）；再还原，必须全绿（rc=0）。
绝不留下改动：用原文/备份文本在内存里替换后写临时副本，跑完立即还原并核验。
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
TARGET = os.path.join(ROOT, 'ralsei_pet', 'modules', 'floor_manager.py')
SUITE = os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                     'verify_round34_floor_manager.py')
PY = r'C:\Python311\python.exe'

FIXED = "                return 0 if i == 0 else i - 1"
BROKEN = "                return i - 1"

with open(TARGET, 'r', encoding='utf-8') as f:
    original = f.read()

if FIXED not in original:
    print('!! 找不到修复行，无法体检。实际内容片段：')
    for ln in original.split('\n'):
        if 'i - 1' in ln or 'i == 0' in ln:
            print(repr(ln))
    sys.exit(2)

print('=' * 70)
print('鉴别力体检：把修复回退成 `return i - 1`，套件必须报红')
print('=' * 70)

try:
    # ── 破坏版 ──────────────────────────────────────────────
    broken = original.replace(FIXED, BROKEN)
    assert broken != original, '替换未生效'
    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write(broken)

    r1 = subprocess.run([PY, SUITE], capture_output=True, cwd=ROOT)
    out1 = r1.stdout.decode('utf-8', 'replace')
    fails = out1.count('[FAIL]')
    passes = out1.count('[PASS]')
    print()
    print('[破坏版] rc=%s  PASS=%d FAIL=%d' % (r1.returncode, passes, fails))
    for ln in out1.split('\n'):
        if '[FAIL]' in ln:
            print('   ', ln.strip())
    caught = (r1.returncode != 0 and fails > 0)
    print('   → 是否抓住破坏:', '是 ✅' if caught else '否 ❌（套件无鉴别力！）')

finally:
    # ── 无条件还原 ─────────────────────────────────────────
    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write(original)

# ── 还原核验 ────────────────────────────────────────────────
with open(TARGET, 'r', encoding='utf-8') as f:
    restored = f.read()
print()
print('[还原核验] 文件与原文逐字节一致:', restored == original)

r2 = subprocess.run([PY, SUITE], capture_output=True, cwd=ROOT)
out2 = r2.stdout.decode('utf-8', 'replace')
print('[修复版] rc=%s  PASS=%d FAIL=%d'
      % (r2.returncode, out2.count('[PASS]'), out2.count('[FAIL]')))
green = (r2.returncode == 0 and out2.count('[FAIL]') == 0)
print('   → 修复版全绿:', '是 ✅' if green else '否 ❌')

print()
print('=' * 70)
print('体检结论:', '通过（有鉴别力：破坏被抓、修复全绿）' if (caught and green)
      else '不通过 —— 需重做断言')
print('=' * 70)
sys.exit(0 if (caught and green) else 1)
