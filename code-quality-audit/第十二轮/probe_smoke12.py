# -*- coding: utf-8 -*-
"""第十二轮侦察 1：data_store 解析 + jieba 接入前后抽词对比。

运行：C:\\Python311\\python.exe code-quality-audit/第十二轮/probe_smoke12.py
输出：code-quality-audit/第十二轮/_evidence/round12_smoke.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
EV = os.path.join(HERE, '_evidence')
sys.path.insert(0, MODS)
OUT = os.path.join(EV, 'round12_smoke.txt')
os.makedirs(EV, exist_ok=True)

import data_store                       # noqa: E402
import text_segmenter                   # noqa: E402
import conversation_focus as CF         # noqa: E402

LINES = []


def P(s=''):
    LINES.append(str(s))


SENTS = [
    '我明天想写点代码',
    '今天想聊聊塞尔达这游戏的剧情',
    '学习编程需要花不少时间',
    '要不要休息一下啊',
    '写代码写累了就喝咖啡',
    '今天下雨会有点冷吧',
    '刚喝了杯咖啡感觉还行',
    '明天开会吗',
    '这件事很重要',
]

P('=' * 74)
P('【一】data_store 解析结果')
P('=' * 74)
for k, v in sorted(data_store.describe().items()):
    P('  %-18s = %s' % (k, v))
P('')
P('  注：E 盘离线时应落到 staging（%%LOCALAPPDATA%%\\RalseiPet）')
P('')

P('=' * 74)
P('【二】抽词：内置滑窗词法（jieba 未接入）')
P('=' * 74)
builtin = {}
for s in SENTS:
    kw = CF.extract_keywords(s)
    builtin[s] = kw
    P('  %-16s -> %s' % (s, ' '.join(kw)))

P('')
P('=' * 74)
P('【三】抽词：jieba 接入后')
P('=' * 74)
st = text_segmenter.install(preload=False)
P('  install status = %s' % st)
P('')
seg = {}
for s in SENTS:
    kw = CF.extract_keywords(s)
    seg[s] = kw
    P('  %-16s -> %s' % (s, ' '.join(kw)))

P('')
P('=' * 74)
P('【四】逐句差异（内置 → jieba）')
P('=' * 74)
n_before = n_after = 0
for s in SENTS:
    b, a = builtin[s], seg[s]
    n_before += len(b)
    n_after += len(a)
    tag = '  ' if b == a else '→ '
    P('  %s%-16s %s' % (tag, s, ' '.join(b)))
    if b != a:
        P('    %-16s %s' % ('', ' '.join(a)))
P('')
P('  词条总数：内置 %d → jieba %d' % (n_before, n_after))
P('')
P('  describe(): ' + text_segmenter.describe())

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(LINES) + '\n')
print('written ' + OUT)
