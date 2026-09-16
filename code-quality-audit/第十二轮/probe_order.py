# -*- coding: utf-8 -*-
"""第十二轮侦察 3：两种导入顺序下，日志目录是否都会正确落到数据根。

这是"logger_utils ↔ data_store 初始化环"的回归探针：
  A) 先 import logger_utils（常规顺序）
  B) 先 import data_store（危险顺序：曾在 import 期回头向 logger 要日志器）

运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_order.py
输出：code-quality-audit/第十二轮/_evidence/round12_import_order.txt
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')

OUT = os.path.join(HERE, '_evidence', 'round12_import_order.txt')

CHILD = r'''
import io, os, sys
sys.path.insert(0, r"%s")
ORDER = %r
if ORDER == 'logger_first':
    import logger_utils
    log = logger_utils.get_logger('order_probe')
    log.info('order probe: logger first')
    import data_store
else:
    import data_store
    import logger_utils
    log = logger_utils.get_logger('order_probe')
    log.info('order probe: data_store first')
with io.open(r"%s", 'a', encoding='utf-8', newline='\n') as f:
    f.write('  %%-16s log_dir=%%s\n    %%-14s data_root=%%s\n'
            %% (ORDER, logger_utils.get_log_dir(), '', data_store.data_root(create=False)[0]))
'''

if os.path.exists(OUT):
    os.remove(OUT)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('导入顺序 → 日志目录解析（两者应一致，且都在数据根内）\n\n')

for order in ('logger_first', 'data_store_first'):
    code = CHILD % (MODS, order, OUT)
    r = subprocess.run([sys.executable, '-c', code], capture_output=True)
    if r.returncode != 0:
        with io.open(OUT, 'a', encoding='utf-8', newline='\n') as f:
            f.write('  %s FAILED: %s\n'
                    % (order, r.stderr.decode('utf-8', 'replace')[:400]))

with io.open(OUT, 'a', encoding='utf-8', newline='\n') as f:
    f.write('\n')
print('written %s' % OUT)
