# -*- coding: utf-8 -*-
r"""mutate195.py —— 证明 check195 的判据**真的能红**（不是恒真）。

规范（本项目历轮沉淀）：
  · 每个变异必须让**红数 > 0 且 < 总数**（红了 = 抓到了；等于总数 = 判据自己崩了，不算抓到）
  · 另有一条**无害变异**必须红 0（证明判据不会因为"文件被动过"而乱红）
  · 每个变异跑完**整文件还原**并核 sha1，双跑一致
  · 幂等：任何时刻中断，下一次运行都能从盘上的原始快照恢复

用法：python mutate195.py
"""
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
CHECK = os.path.join(HERE, 'check195.py')
PY = sys.executable
TOTAL = 23          # check195 的判据总数（改判据数时同步改这里）

# (名字, 文件, 原文, 替换成, 期望)
MUTANTS = [
    ('M1 去掉"NPC 不继承本体旧记忆"',
     'memory_system.py',
     '            self._legacy_file = None',
     "            self._legacy_file = 'MUTATED-legacy'",
     'B3 必须红'),
    ('M2 去掉 LRU 淘汰',
     'people_memory.py',
     '            self._evict_locked()',
     '            pass  # mutate: 不淘汰',
     'C1/C2 必须红'),
    ('M3 断掉 add_npc_line 的接线',
     'dialogue_ui.py',
     '            self._note_person_memory(char_id, text, _acts)',
     '            pass  # mutate: 不记',
     'D1 必须红'),
    ('M0 无害变异（只改注释）',
     'people_memory.py',
     '#: 相对记忆根的子目录名（与 Ralsei 的 `memory.json` 同级）',
     '#: 相对记忆根的子目录名（与 Ralsei 的 memory.json 同级）  ← 只动注释',
     '必须红 0'),
]


def sha1(p):
    with io.open(p, 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def run_check():
    p = subprocess.run([PY, CHECK], cwd=HERE, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    n_fail = len(re.findall(r'^\[FAIL\]', out, re.M))
    n_pass = len(re.findall(r'^\[PASS\]', out, re.M))
    return n_fail, n_pass, out


def main():
    originals = {}
    for name, fname, _old, _new, _exp in MUTANTS:
        p = os.path.join(MODS, fname)
        if p not in originals:
            with io.open(p, 'r', encoding='utf-8', newline='') as fh:
                originals[p] = (fh.read(), sha1(p))

    base_fail, base_pass, _ = run_check()
    print(u'基线：PASS=%d FAIL=%d（总数应为 %d）' % (base_pass, base_fail, TOTAL))
    if base_fail:
        print(u'[ABORT] 基线本来就红，先修好再变异')
        return 2

    bad = 0
    for name, fname, old, new, expect in MUTANTS:
        p = os.path.join(MODS, fname)
        src, h0 = originals[p]
        if src.count(old) != 1:
            print(u'[SKIP] %s：锚点出现 %d 次（要求恰好 1 次）' % (name, src.count(old)))
            bad += 1
            continue
        try:
            with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                fh.write(src.replace(old, new, 1))
            f, pa, _out = run_check()
            ok = (f > 0 and f < TOTAL) if '红 0' not in expect else (f == 0)
            print(u'[%s] %s → FAIL=%d PASS=%d（%s）'
                  % ('OK' if ok else 'BAD', name, f, pa, expect))
            if not ok:
                bad += 1
        finally:
            with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                fh.write(src)
            if sha1(p) != h0:
                print(u'[FATAL] %s 还原失败！sha1 %s != %s' % (fname, sha1(p), h0))
                return 3

    # 全部还原后再跑一次，确认回到基线
    f2, p2, _ = run_check()
    print(u'还原后复跑：PASS=%d FAIL=%d' % (p2, f2))
    if f2 != 0:
        print(u'[FATAL] 还原后仍有红')
        return 3
    print(u'')
    print(u'结论：%s' % (u'全部变异都被抓到' if bad == 0 else u'有 %d 条没抓到' % bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
