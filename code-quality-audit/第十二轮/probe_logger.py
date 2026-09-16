# -*- coding: utf-8 -*-
"""第十二轮侦察 4：logger_utils 重入护栏 + 日志目录路由。

`logger_utils` 被几乎所有模块导入，且初始化时要解析日志目录（会 import data_store）
—— 这里验证"护栏 + 惰性日志器"之后不会递归、目录也正确。

运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_logger.py
输出：code-quality-audit/第十二轮/_evidence/round12_logger.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MODS)

L = []
try:
    import logger_utils
    L.append('import logger_utils OK')
    L.append('get_log_dir() = %s' % logger_utils.get_log_dir())
    log = logger_utils.get_logger('probe')
    log.info('probe: 日志系统工作正常')
    L.append('二次 get_logger OK（未递归）')
    L.append('_initialized = %s / _initializing = %s'
             % (logger_utils._initialized, logger_utils._initializing))
    L.append('日志目录存在 = %s' % os.path.isdir(logger_utils.get_log_dir()))
except Exception as e:
    import traceback
    L.append('FAIL: %s' % e)
    L.append(traceback.format_exc())

OUT = os.path.join(HERE, '_evidence', 'round12_logger.txt')
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(L) + '\n')
print('written %s' % OUT)
