# -*- coding: utf-8 -*-
"""第十轮真机取证：用**真实的记忆文件**跑一次多跳召回（只读源文件，写落在临时目录）。

为什么必须做这一步：自检脚本用的是构造出来的小图，只能证明"逻辑对"，
不能证明"真机上那份 memory.json（第九轮格式、只带 1 跳 int 联想）能平滑升级"。
这里把 RALSEI_LEGACY_MEMORY 指向真机文件、RALSEI_MEMORY_DIR 指向临时目录：
  · 读：走真机数据（旧格式 assoc → 分层图）；
  · 写：落临时目录（**绝不改动真机记忆**）。
输出几个真实线索的召回结果，人工看一眼"像不像人想起来的东西"。

用法：C:\\Python311\\python.exe probe_real_recall.py [记忆文件路径]
"""
import io
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')

DEFAULT_REAL = r'E:\RalseiMemory\memory.json'
ROOT_LEGACY = os.path.join(ROOT, 'ralsei_pet', 'memory.json')
real = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REAL
if not os.path.exists(real) and os.path.exists(ROOT_LEGACY):
    real = ROOT_LEGACY          # E 盘那份被"清空测试"清掉后，退回项目内真机文件

TMP = tempfile.mkdtemp(prefix='ralsei_real10_')
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(TMP, 'scratch')
os.environ['RALSEI_LEGACY_MEMORY'] = real
sys.path.insert(0, MODS)

import memory_graph as MG                                # noqa: E402
from memory_system import MemorySystem                   # noqa: E402


class P(object):
    api_enabled = False


def line(s=''):
    print(s)


line('=' * 72)
line('真机记忆召回取证（源文件只读）')
line('=' * 72)
line('记忆文件 = %s' % real)
line('文件存在 = %s' % os.path.exists(real))


def _stat(path):
    try:
        st = os.stat(path)
        return {'size': st.st_size, 'mtime': st.st_mtime}
    except Exception:
        return None


_src_before = _stat(real)
if _src_before:
    line('源文件取证前 = size %d  mtime %s'
         % (_src_before['size'],
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_src_before['mtime']))))
if os.path.exists(real):
    with io.open(real, encoding='utf-8') as fh:
        raw = json.load(fh)
    line('文件 schema = %s  字节 = %d' % (raw.get('schema'),
                                          os.path.getsize(real)))
    _a = raw.get('assoc') or {}
    _vals = []
    for _slot in _a.values():
        _vals.extend(list(_slot.values())[:3])
    _kinds = set(type(v).__name__ for v in _vals)
    line('文件里 assoc 值类型 = %s（int=第九轮旧格式）' % (sorted(_kinds) or ['空']))
    line('文件里 fragments = %d  keys = %d  digests = %d  assoc 词条 = %d'
         % (len(raw.get('fragments') or []), len(raw.get('keys') or []),
            len(raw.get('digests') or {}), len(_a)))

t0 = time.time()
ms = MemorySystem(P())
t_load = (time.time() - t0) * 1000.0

g = ms._graph
line('')
line('--- 升级结果 ---')
line('加载耗时 = %.1f ms' % t_load)
line('落点 = %s（on_device=%s）' % (ms.memory_dir, ms._on_device))
line('图自检 = %s' % (g.stats() if g is not None else None))
line('索引关键词数 = %d' % len(ms._index))

# 旧格式是否真的被升级（而不是被丢）
_legacy_upgraded = 0
for _slot in (ms.assoc or {}).values():
    for _e in _slot.values():
        if isinstance(_e, dict) and 'tier' in _e:
            _legacy_upgraded += 1
line('边记录（带 tier）总数 = %d' % _legacy_upgraded)

cues = []
# 线索取自真实数据：用出现频率最高的几个关键词当线索
from collections import Counter
_cnt = Counter()
for f in ms.fragments:
    for k in (f.get('kw') or []):
        _cnt[k] += 1
cues = [k for k, _c in _cnt.most_common(5)]
if not cues:
    cues = ['游戏', '今天']

line('')
line('--- 真实召回（线索取自真实高频词：%s）---' % '、'.join(cues))
_worst = 0.0
for cue in cues:
    t1 = time.time()
    items = ms.recall(cue, limit=3)
    dt = (time.time() - t1) * 1000.0
    _worst = max(_worst, dt)
    line('')
    line('· 线索「%s」  -> %d 条  耗时 %.1f ms' % (cue, len(items), dt))
    for it in items:
        via = ('   [由%s联想到]' % '、'.join(it.get('via') or [])) if it.get('via') else ''
        line('    - (%s|%s|hop=%s, score=%s) %s%s' % (
            it.get('who'), it.get('tier') or 'direct', it.get('hop'),
            it.get('score'), str(it.get('text'))[:34], via))

line('')
line('--- 出口文案（真机数据）---')
_rt = ms.recall_text(cues[0], limit=3)
line(_rt or '(该线索没有想起任何东西)')

line('')
line('--- 场景重构（真机数据）---')
line(ms.reconstruct_scene(cues[0]) or '(没聚到同一天的片段)')

line('')
line('--- 巩固与指标（不写盘）---')
line('consolidate = %s' % ms.consolidate())
line('metrics = %s' % ms.recall_report())

line('')
line('单次召回最慢 = %.1f ms（预算上限 %s ms）'
     % (_worst, ms.RECALL_BUDGET.get('max_ms')))
_src_after = _stat(real)
_untouched = (_src_before == _src_after)
line('源文件取证后 = %s' % (_src_after or '(不存在)'))
line('源文件未被改动 = %s（size+mtime 前后一致；本轮写盘全部落在临时目录 %s）'
     % (_untouched, TMP))
line('=' * 72)
sys.exit(0 if _untouched else 1)
