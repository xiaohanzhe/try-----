# -*- coding: utf-8 -*-
"""第十二轮侦察 6：`data_store → memory_store → logger_utils → data_store` 间接初始化环。

第十二轮的 `_LazyLogger` 只断开了 `logger_utils ↔ data_store` 的**直接**环。
但还有一条**间接**环：

    logger_utils._log_dir()
      -> import data_store            （若 data_store 已导入完则没问题）
      -> data_store.artifact_path('logs')
      -> data_store.vault_root()
      -> data_store._memory_store()   -> import memory_store
      -> memory_store 模块体 _log = get_logger(...)   -> logger_utils._init_logging()
      -> logger_utils._log_dir()      -> import data_store
      -> data_store.vault_root()      -> _memory_store() -> memory_store 是**半成品**
      -> ms.find_device_dir 不存在 -> AttributeError -> vault_root 返回 None
      -> data_root() 降级为 staging -> artifact_path('logs') = <staging>\\logs
      -> _log_dir() **把 staging 当成功结果缓存**（毒化）

本探针用**子进程**跑两种导入顺序，对比 logger 目录解析结果，确认上面这条链。

运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_cycle2.py
输出：code-quality-audit/第十二轮/_evidence/round12_cycle2.txt
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')

CHILD = r'''
import sys
sys.path.insert(0, r"{MODS}")
mode = sys.argv[1]
if mode == "ds_first":
    import data_store
    print("  1) import data_store                     -> ok")
    p = data_store.artifact_path("logs", ensure_dir=False)
    print("  2) data_store.artifact_path('logs')      = " + p)
import logger_utils
print("  3) logger_utils.get_log_dir()            = " + logger_utils.get_log_dir())
if mode == "lu_first":
    import data_store
    print("  4) data_store.artifact_path('logs')      = " + data_store.artifact_path("logs", ensure_dir=False))
    print("  5) data_store.describe().active_kind     = " + str(data_store.describe()["active_kind"]))
else:
    print("  4) data_store.describe().active_kind     = " + str(data_store.describe()["active_kind"]))
'''.replace('{MODS}', MODS)

LINES = []
P = LINES.append
P('=' * 78)
P('【导入顺序对照：logger 目录会不会被间接环毒化成 staging】')
P('=' * 78)


def run(mode, title):
    P('')
    P('--- %s ---' % title)
    p = subprocess.run([sys.executable, '-c', CHILD, mode],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    for line in out.rstrip('\n').split('\n'):
        P(line)
    return out


a = run('ds_first', '顺序 A：先 import data_store（第十二轮探针就是这个顺序）')
b = run('lu_first', '顺序 B：先 import logger_utils（真实 app 大概率的顺序）')

P('')
P('=' * 78)
P('【判读】')
P('  期望（E 盘在线）：两种顺序下 get_log_dir() 都应以 RalseiMemory 结尾。')


def logdir_of(out):
    """只取 get_log_dir() 那一行的值（别拿整段输出做子串判断，会误命中）。"""
    for line in out.split('\n'):
        if 'get_log_dir()' in line:
            return line.split('=', 1)[-1].strip()
    return ''


da, db = logdir_of(a), logdir_of(b)
pa = da.endswith('RalseiMemory\\logs') or da.rstrip('\\/').endswith('RalseiMemory\\logs')
pb = db.endswith('RalseiMemory\\logs') or db.rstrip('\\/').endswith('RalseiMemory\\logs')
P('    顺序 A get_log_dir() = %s   -> %s' % (da, 'vault OK' if pa else '!! 不在 vault'))
P('    顺序 B get_log_dir() = %s   -> %s' % (db, 'vault OK' if pb else '!! 不在 vault'))
P('  结论：%s' % ('两种顺序一致，间接环已断开。'
                if (pa and pb)
                else '顺序相关 —— 先碰 data_store 会把日志目录钉在非 vault 位置（真 bug）。'))
P('=' * 78)

OUT = os.path.join(HERE, '_evidence', 'round12_cycle2.txt')
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s' % OUT)
