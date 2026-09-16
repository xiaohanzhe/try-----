# -*- coding: utf-8 -*-
"""第十二轮侦察 2：运行时产物路径是否都进了"最终存储 / 本地中转站"。

不启动 GUI，只用桩对象构造各子系统，读它们的路径属性。
运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_paths.py
输出：code-quality-audit/第十二轮/_evidence/round12_paths.txt
"""
import io
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MODS)

LINES = []


def P(s=''):
    LINES.append(str(s))


P('=' * 74)
P('【运行时产物路径解析】')
P('=' * 74)

import data_store                                   # noqa: E402
P('  data_store.describe() =')
for k, v in sorted(data_store.describe().items()):
    P('      %-18s = %s' % (k, v))
P('')

stub = types.SimpleNamespace()

cases = []
try:
    from config_manager import ConfigManager
    cases.append(('config.json', ConfigManager().config_file))
except Exception as e:
    cases.append(('config.json', 'ERR %s' % e))

try:
    from customization_system import CustomizationSystem
    cases.append(('customization_config.json', CustomizationSystem(stub).config_path))
except Exception as e:
    cases.append(('customization_config.json', 'ERR %s' % e))

try:
    from entertainment_system import EntertainmentSystem
    cases.append(('entertainment_data.json', EntertainmentSystem(stub).entertainment_data_path))
except Exception as e:
    cases.append(('entertainment_data.json', 'ERR %s' % e))

try:
    from social_growth_system import SocialGrowthSystem
    cases.append(('growth_data.json', SocialGrowthSystem(stub).growth_data_path))
except Exception as e:
    cases.append(('growth_data.json', 'ERR %s' % e))

try:
    import logger_utils
    cases.append(('logs/', logger_utils.get_log_dir()))
except Exception as e:
    cases.append(('logs/', 'ERR %s' % e))

try:
    import text_segmenter
    cases.append(('jieba 缓存', text_segmenter.default_cache_path()))
    cases.append(('jieba 用户词表', text_segmenter.default_userdict_path() or '(未设置)'))
except Exception as e:
    cases.append(('jieba 缓存', 'ERR %s' % e))

root, kind = data_store.data_root(create=False)
P('  当前数据根 = %s  (%s)' % (root, kind))
P('')
P('  %-26s %s' % ('产物', '解析出的路径'))
P('  ' + '-' * 72)
for name, path in cases:
    try:
        inside = '  [在数据根内 OK]' if str(path).startswith(str(root)) else '  [!! 不在数据根内]'
    except Exception:
        inside = ''
    P('  %-26s %s%s' % (name, path, inside))

P('')
P('=' * 74)
P('【模块全量导入冒烟】')
P('=' * 74)
bad = []
for fn in sorted(os.listdir(MODS)):
    if not fn.endswith('.py') or fn.startswith('_'):
        continue
    mod = fn[:-3]
    try:
        __import__(mod)
    except Exception as e:
        bad.append('%s: %s' % (mod, e))
P('  导入失败模块数 = %d' % len(bad))
for b in bad:
    P('    !! ' + b)

OUT = os.path.join(HERE, '_evidence', 'round12_paths.txt')
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s' % OUT)
