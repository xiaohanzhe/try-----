# -*- coding: utf-8 -*-
"""第164轮 · `motion2d` 的破坏性检验（证明 `verify_motion2d` 的判据**会红**）。

为什么要做
----------
"验绿了"不等于"验对了"。一个恒真判据也会绿。所以每一条关键判据都必须
**举得出反例**：把被守的行为破坏掉，跑一遍，必须报红；再恢复，必须转绿。

做法
----
不碰产品文件：读 `motion2d.py` 源码 → 在内存里替换成"变异体" → 写到临时目录 →
用环境变量 `MOTION2D_DIR` 指过去 → 跑 `verify_motion2d.py` → 看退出码与 FAIL 数。

每个变异都要求：`returncode != 0` 且输出里出现 `[FAIL]`。
若某个变异**跑绿了**，说明对应判据是恒真的，必须重写那条判据。
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
SRC = os.path.join(ROOT, 'ralsei_pet', 'modules', 'motion2d.py')
VERIFY = os.path.join(HERE, 'verify_motion2d.py')
PY = sys.executable


# (代号, 说明, 原文片段, 替换片段, 期望被哪一节抓到)
MUTANTS = [
    ('M1', '速度上限失效（= 产品的旧行为：只看目标位移）',
     'if v_req > v_max + _EPS:',
     'if False:',
     '3b 同一位移不同速度上限'),
    ('M2', '高度上限写死成常数（不再是起跳力的函数）',
     'return (jump_speed * jump_speed) / (2.0 * gravity)',
     'return 62.5',
     '1 负控制：不同重力必须得到不同 h_max'),
    ('M3', '规划输出的水平初速恒为 0（原地跳照样绿，横跳必须红）',
     "out['vx'] = dx * scale",
     "out['vx'] = 0.0",
     '3 横跳 vx 必须 != 原地跳'),
    ('M4', '够不着高度也硬给一个时间（负控制失效）',
     '    if disc < -_EPS:\n        return None',
     '    if disc < -_EPS:\n        disc = 0.0',
     '2b 够不着的高度必须返回 None'),
    ('M5', '助跑距离算成线性（v/a 而不是 v^2/2a）',
     'return (v_target * v_target - v_now * v_now) / (2.0 * accel)',
     'return (v_target - v_now) / accel',
     '6 0→320 需 85.333px'),
]


def run_verify(mod_dir):
    env = dict(os.environ)
    env['MOTION2D_DIR'] = mod_dir
    p = subprocess.run([PY, VERIFY], capture_output=True, env=env)
    out = (p.stdout or b'').decode('utf-8', 'replace')
    return p.returncode, out


def main():
    src = open(SRC, 'r', encoding='utf-8').read()

    # ---- 基线：未变异必须绿 ----
    rc, out = run_verify(os.path.join(ROOT, 'ralsei_pet', 'modules'))
    n_fail = len(re.findall(r'\[FAIL\]', out))
    print('=' * 68)
    print('基线（未变异）：exit=%d FAIL=%d' % (rc, n_fail))
    print('=' * 68)
    if rc != 0 or n_fail:
        print('!! 基线就是红的，后面的变异测试没意义，先修基线')
        return 2

    tmp_root = tempfile.mkdtemp(prefix='m2mut_')
    results = []
    try:
        for code, desc, old, new, expect in MUTANTS:
            if old not in src:
                results.append((code, desc, 'ANCHOR_MISS', expect, ''))
                print('[%s] 锚点未命中 —— 源码变了，请更新 MUTANTS' % code)
                continue
            mutated = src.replace(old, new, 1)
            assert mutated != src, '%s 替换没生效' % code
            d = os.path.join(tmp_root, code)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'motion2d.py'), 'w',
                      encoding='utf-8', newline='\n') as f:
                f.write(mutated)
            rc2, out2 = run_verify(d)
            fails = re.findall(r'\[FAIL\] (.+)', out2)
            caught = (rc2 != 0) and bool(fails)
            results.append((code, desc, 'CAUGHT' if caught else 'MISSED',
                            expect, fails[0] if fails else '(无 FAIL)'))
            print('[%s] %-6s %s' % (code, 'CAUGHT' if caught else '!!MISSED',
                                    desc))
            if fails:
                print('        首条红：%s' % fails[0])
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print('\n' + '=' * 68)
    missed = [r for r in results if r[2] != 'CAUGHT']
    print('变异 %d 个，抓住 %d 个，漏 %d 个'
          % (len(results), len(results) - len(missed), len(missed)))
    if missed:
        for code, desc, st, expect, got in missed:
            print('  ✗ %s %s（期望被抓：%s）' % (code, st, expect))
        return 1
    print('[PASS] 全部变异都被判据抓住（判据不是恒真）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
