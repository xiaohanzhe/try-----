# -*- coding: utf-8 -*-
"""探针：为什么时钟平移下日志全没了？（B11 用，落 E 盘临时区，用后即删）

只做一件事：把 logger_utils 的格式化/发射路径逐步跑一遍，把**异常原文**打出来。
"""
import io
import os
import sys
import traceback

sys.path.insert(0, os.path.join(r'C:\Users\23002\Desktop\项目文件夹\try - 副本',
                                'ralsei_pet', 'modules'))

print('CLOCK_SHIFT_SEC =', os.environ.get('CLOCK_SHIFT_SEC'))

import logging
import time

print('logging.Formatter.converter =', logging.Formatter.converter)
print('time.localtime           =', time.localtime)
print('converter is localtime   =', logging.Formatter.converter is time.localtime)

fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
rec = logging.LogRecord('ralsei_pet.probe', logging.INFO, 'p', 1, 'hello %s', ('x',), None)
print('record.created =', rec.created)

try:
    print('[1] format() OK ->', repr(fmt.format(rec)))
except Exception:
    print('[1] format() RAISED:')
    traceback.print_exc()

# 真正的路径：装 logger_utils 自己的 handler
try:
    import logger_utils as LU
except Exception:
    print('[2] import logger_utils RAISED:')
    traceback.print_exc()
    raise SystemExit(0)

print('[2] _initialized =', LU._initialized, ' root =', LU._root_logger)
lg = LU.get_logger('probe')
print('[3] root handlers =', LU._root_logger.handlers if LU._root_logger else None)
for h in (LU._root_logger.handlers if LU._root_logger else []):
    print('    handler=%r level=%s emit_failures=%s' % (
        type(h).__name__, h.level, getattr(h, 'emit_failures', 'n/a')))
    if h.formatter is not None:
        try:
            print('    试格式化 ->', repr(h.formatter.format(rec)))
        except Exception:
            print('    试格式化 RAISED:')
            traceback.print_exc()

print('[4] 真发一条 INFO：')
lg.info('这是一条探针日志')
for h in (LU._root_logger.handlers if LU._root_logger else []):
    print('    handler=%s emit_failures=%s' % (type(h).__name__, getattr(h, 'emit_failures', 'n/a')))

print('[5] 直接调 handler.emit 看原始异常：')
if LU._root_logger and LU._root_logger.handlers:
    h = LU._root_logger.handlers[0]
    try:
        h.emit(rec)
        print('    emit 返回（可能内部已吞）')
    except Exception:
        print('    emit RAISED:')
        traceback.print_exc()
    # 再手动走一遍 StreamHandler.emit 的裸路径
    try:
        msg = h.format(rec)
        stream = h.stream
        stream.write(msg + h.terminator)
        print('    裸写成功')
    except Exception:
        print('    裸写 RAISED:')
        traceback.print_exc()
