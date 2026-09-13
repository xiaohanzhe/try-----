# -*- coding: utf-8 -*-
"""带固定随机种子的套件启动器（G2 回归基线的一部分）。

为什么需要它：`verify_round5_fixes.py` 的 V2b 用的是 `random.choice([...])` 选承接语，
两次运行会给出不同文案 → 归一化文本哈希必然漂移，回归基线就失去意义。
（实测差异：`你想查看系统的哪个具体指标？` vs `需要我再次检查系统状态吗？`）

所以所有套件统一由本启动器执行：
  1. 先 `random.seed(SEED)`，把 random 序列钉死；
  2. 再用 runpy 以 `__name__ == '__main__'` 执行目标脚本（保留 `if __name__` 语义与 `__file__`）；
  3. SystemExit 原样向上抛，套件自身的退出码不受影响。

配合环境变量 `PYTHONHASHSEED=0`（由 run_all.py 注入），
把 `set` 的字符串迭代顺序也一并钉死——项目里多处按 set 顺序打印来源列表。

用法：python _seed_runner.py <seed> <script.py>
"""
import random
import runpy
import sys

if len(sys.argv) < 3:
    sys.stderr.write('usage: _seed_runner.py <seed> <script.py>\n')
    raise SystemExit(2)

_seed = int(sys.argv[1])
_script = sys.argv[2]

random.seed(_seed)
sys.argv = [_script]

runpy.run_path(_script, run_name='__main__')
