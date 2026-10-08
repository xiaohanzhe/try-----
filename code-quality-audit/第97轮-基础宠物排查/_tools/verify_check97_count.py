# -*- coding: utf-8 -*-
"""核验 `check97.py` 的 stdout 在 **G2 口径**下计数 == 自报判据数。

为什么需要它
------------
G2（`run_all.count_results`）的判据数是
    `len(re.findall(r'\\[PASS\\]|\\[\\s*OK\\s*\\]', stdout))`
—— **纯文本出现次数**，不是脚本自报。于是：套件里任何 desc/文案**回显了成功标记
字面量**，该行就会被数成 2 次 ⇒ 统计列虚高，而 `FAIL=0` 照样成立。
"统计列必须准"是本仓库的回归铁律（§4：*全量回归须机器统计比对列，非只看 FAIL=0*）。

第 97 轮实测：`check97.py` 自报 `PASS=13`，G2 却记 **14** —— 真凶就是 C2 的 desc
里写了 `print('[PASS] %s')`。现该 desc 已去字面量，并新增静态守卫 **C5**。

用法
----
    python verify_check97_count.py

只读（除 `_tools/_tmp_mutate_97.py` 这个跑完即删的变异副本外，无任何副作用）。
退出码 0 = 正/负控制均符合预期。
"""
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or r'C:\Python311\python.exe'
G2_RE = r'\[PASS\]|\[\s*OK\s*\]'
TARGET = 'check97.py'


def run_count(script, label, mutate=None):
    """跑脚本，用 G2 的正则复算 stdout 计数，与脚本自报比对。"""
    path = os.path.join(TOOLS, script)
    src = open(path, 'r', encoding='utf-8', newline='').read()
    tmp = None
    if mutate is not None:
        new, hit = mutate(src)
        if hit == 0:
            print('[SKIP] %s：变异未命中（脚本内容已变？）' % label)
            return None
        tmp = os.path.join(TOOLS, '_tmp_mutate_97.py')
        open(tmp, 'w', encoding='utf-8', newline='').write(new)
        path = tmp
    try:
        r = subprocess.run([PY, path], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', cwd=TOOLS)
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
    out = r.stdout or ''
    n_g2 = len(re.findall(G2_RE, out))
    m = re.search(r'PASS=(\d+) FAIL=(\d+) 合计=(\d+)', out)
    self_n = int(m.group(3)) if m else None
    print('--- %s' % label)
    print('    G2 口径计数 = %d' % n_g2)
    print('    脚本自报     = %s   (rc=%d)' % (m.group(0) if m else 'N/A', r.returncode))
    print('    一致?        = %s' % ('YES' if self_n == n_g2 else 'NO  <<< 不一致'))
    for ln in out.splitlines():
        if ln.startswith('[FAIL]') or ln.startswith('[RED]'):
            print('    ' + ln)
    return n_g2, self_n, r.returncode


def main():
    print('=' * 70)
    print('正控制：现状 %s（期望：G2 计数 == 自报，且 rc=0）' % TARGET)
    pos = run_count(TARGET, '%s 现状' % TARGET)

    print()
    print('=' * 70)
    print('负控制：把一处 desc 改回"回显成功标记字面量" ⇒ C5 必须报红'
          '（且 G2 计数应比自报多 1）')

    def mutate_add_mark(src):
        # 这里**故意**用完整字面量：它只写进临时文件（跑完即删），不污染 check97.py。
        # 若用拆写规避，C5 反而抓不到 —— C5 只扫 AST 里的 Constant，
        # 防的是"疏忽回显"，不是对抗性规避。
        old = "'C3 \u88ab\u6d4b\u6587\u4ef6\u5728\u76d8'"
        new = "'C3 \u88ab\u6d4b\u6587\u4ef6\u5728\u76d8 [PASS]'"
        if old not in src:
            return src, 0
        return src.replace(old, new, 1), 1

    neg = run_count(TARGET, '负控制：desc 回显成功标记', mutate=mutate_add_mark)

    print()
    print('=' * 70)
    ok_pos = bool(pos) and pos[1] == pos[0] and pos[2] == 0
    ok_neg = bool(neg) and neg[2] == 1            # 必须非零退出（C5 报红）
    print('正控制通过 = %s ；负控制（C5 能翻面）通过 = %s' % (ok_pos, ok_neg))
    if ok_pos and ok_neg:
        print('[PASS] verify_check97_count：G2 计数口径与 C5 守卫均符合预期')
        return 0
    print('[FAIL] verify_check97_count：预期未满足')
    return 1


if __name__ == '__main__':
    sys.exit(main())
