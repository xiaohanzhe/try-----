# -*- coding: utf-8 -*-
"""H5 S3 验证：别名与 legacy 显式化之后，语义仍然等价。

S3 只做两件事：把重复的帧列表换成 `alias_of`、给静态零引用的键打 `legacy: true`。
两件事都"看起来无害"，但都可能悄悄改行为：
  - 别名方向选错 → 两个动画互换素材；
  - legacy 标错 → 把运行时才会拼出来的名字标成历史键，掩盖未来的真实缺失；
  - 顺手删组 → 直接是行为变更。

所以本脚本的断言分三类：
  A 别名：方向、清空 frames、解析后帧与目标一致、loader 真要得到帧；
  B legacy：**独立重扫一遍源码**确认这些名字在 src/modules 里确实零字面量引用；
    动态可达家族（walk_/run_/walk_tea_）与保护名单一个都不许被标；
    legacy 只打标、不删组、不影响加载；
  C 端到端：解析后的表与源码内置表深度相等；导出器 --check 通过；apply 幂等。

运行：QT_QPA_PLATFORM=offscreen python verify_s3_alias_legacy.py
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'src'))
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, HERE)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

import apply_s3_alias_legacy as a3  # noqa: E402
import extract_animations_json as ex  # noqa: E402
from sprite_loader import SpriteLoader  # noqa: E402

PASS, FAIL = [], []


def check(tid, title, cond, detail=''):
    (PASS if cond else FAIL).append(tid)
    print('  [%s] %-4s %s%s' % ('PASS' if cond else 'FAIL', tid, title,
                                ('  :: ' + detail) if detail else ''))


def note(text):
    print('  [NOTE] ' + text)


with io.open(ex.TARGET, encoding='utf-8') as fh:
    doc = json.load(fh)
groups = doc['groups']

print('=== A. 别名（alias_of）===')
aliases = {n: e['alias_of'] for n, e in groups.items() if e.get('alias_of')}
check('A1', '别名组与既定方向一致（happy→laugh / neutral→idle / sad→cry_start / splat_mad→fall_mad）',
      aliases == dict(a3.ALIAS_MAP), '%s' % sorted(aliases.items()))
check('A2', '别名组自身的 frames 已清空', all(not (groups[n].get('frames') or []) for n in aliases),
      '%s' % sorted(aliases))
check('A3', '别名目标都存在且 frames 非空',
      all(t in groups and (groups[t].get('frames') or []) for t in aliases.values()),
      '%s' % sorted(set(aliases.values())))
resolved = ex.resolve_groups(doc)
check('A4', '解析后别名组的帧 == 目标组的帧',
      all(resolved[n] == resolved[t] for n, t in aliases.items()))
check('A5', '别名组没有被同时标 legacy（标注自相矛盾）',
      not (set(aliases) & {n for n, e in groups.items() if e.get('legacy') is True}))

builtin, _node, _lines = ex.extract_literal()
loader = SpriteLoader()
check('A6', 'loader 解析后别名组拿到的也是目标的帧（运行时真有效）',
      all(loader.animation_mapping.get(n) == loader.animation_mapping.get(t)
          for n, t in aliases.items()))

print()
print('=== B. legacy（打标正确性，独立重扫）===')


def independent_literals():
    """独立实现：只扫 src/ 与 modules/ 顶层 .py 的字符串字面量，排除定义表自身的文件。

    刻意不复用 apply 脚本的代码 —— 验证要靠另一条路径得出同一个结论才有意义。
    """
    out = set()
    for d in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py') or fn == 'sprite_loader.py':
                continue
            with io.open(os.path.join(d, fn), encoding='utf-8', errors='replace') as fh:
                out |= set(re.findall(r'[\'"]([A-Za-z0-9_]+)[\'"]', fh.read()))
    return out


indep = independent_literals()
legacy = sorted(n for n, e in groups.items() if e.get('legacy') is True)
check('B1', 'JSON 里的 legacy 组非空（S3 已生效）', bool(legacy), '%d 个' % len(legacy))
check('B2', 'legacy 里的每个名字在 src/modules 里确实零字面量引用（独立重扫）',
      not (set(legacy) & indep), '被引用的=%s' % sorted(set(legacy) & indep))
check('B3', '动态可达家族（walk_/run_/walk_tea_）一个都没被标 legacy',
      not [n for n in legacy if re.match(r'^(walk|run)(_|$)', n)])
check('B4', '保护名单（idle/walk_down/walk_left/walk_right/walk_up/laugh/cry/sing/pose 与别名目标）一个都没被标',
      not (set(legacy) & (a3.PROTECTED | set(aliases.values()))))
check('B5', 'legacy 只打标不删组：组数不变',
      set(groups) == set(builtin) and len(groups) == len(builtin),
      'json=%d builtin=%d' % (len(groups), len(builtin)))
check('B6', 'legacy 不影响加载：打标组的帧列表未被改动',
      all(groups[n].get('frames') == builtin[n] for n in legacy))
check('B7', 'legacy 组仍能拿到帧（loader 里帧数 > 0，且与内置表一致）',
      all(loader.animation_mapping.get(n) == builtin[n] and builtin[n]
          for n in legacy))

print()
print('=== C. 端到端等价与自洽 ===')
check('C1', '解析后的表与源码内置表深度相等（键集合、顺序、每组帧）',
      resolved == builtin and list(resolved) == list(builtin),
      'groups=%d frames=%d' % (len(resolved), sum(len(v) for v in resolved.values())))
check('C2', 'loader 的 animation_mapping 与内置表深度相等',
      loader.animation_mapping == builtin)
check('C3', 'legacy 集合与 JSON 标注一致',
      sorted(loader.legacy_animations) == legacy, '%d 个' % len(legacy))
check('C4', 'position_offset 仍为空（S3 没有引入偏移）', loader.position_offset == {})

proc = subprocess.run([sys.executable, os.path.join(HERE, 'extract_animations_json.py'), '--check'],
                      cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                      env=dict(os.environ, PYTHONIOENCODING='utf-8'))
out = proc.stdout.decode('utf-8', 'replace')
check('C5', '导出器 --check 通过（JSON 解析后 == 代码字面量，且导出幂等）',
      proc.returncode == 0, out.strip().splitlines()[0] if out.strip() else '')

plan = a3.analyze(doc)
check('C6', 'apply 幂等：在已标注的文件上重算计划，结果与现状一致',
      sorted(plan['legacy']) == legacy and plan['aliases'] == aliases,
      'legacy=%d aliases=%d' % (len(plan['legacy']), len(plan['aliases'])))
note('别名 %d 个（%s）' % (len(aliases), ', '.join('%s→%s' % kv for kv in sorted(aliases.items()))))
note('legacy %d 个：%s' % (len(legacy), ', '.join(legacy)))
note('零引用但动态可达、故未标 legacy 的 %d 个：%s'
     % (len(plan['zero_ref'] & plan['dynamic']), sorted(plan['zero_ref'] & plan['dynamic'])))

print()
print('=' * 60)
print('S3 验证：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：%s' % FAIL)
print('=' * 60)
sys.exit(1 if FAIL else 0)
