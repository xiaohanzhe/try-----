# -*- coding: utf-8 -*-
"""第91轮：把 G2 的 13 个 DIFF 逐个**看差异行**，判定「我的合法改动」还是「环境抖动」。

判据（必须能区分两类）：
  · 我的合法改动 ⇒ 差异行里出现 animations.json 的组数/帧数（114→115 / +3 帧）
    或我改过的 check52c.py 的计数（82→83）。
  · 环境抖动   ⇒ 差异行里出现 E 盘相关的「memory 继承/搬入」「可交互物 N→0」
    或 App 实例化相关的日志噪声。
只读，不改任何东西。
"""
import difflib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REGRESS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'code-quality-audit', 'regress'))
OUT = os.path.join(REGRESS, '_out')

DIFFS = ['s1_anim_miss', 's2_anim_json', 's3_alias_legacy', 'round8_anim',
         'dialog_lounge52', 'sit_round54', 'soul_round55', 'npc_persona55',
         'npc_place56', 'check67', 'check73', 'check77', 'check81']

# 关键词：出现即强烈暗示该差异属于哪一类
KEY_MINE = ['115', '497', 'walk_down_sleep', 'sleep']
KEY_ENV = ['memory 继承', '搬入', '可交互物', 'Errno', 'E:\\', 'E盘', 'RalseiMemory',
           'ut/uty', '转储', 'SKIP']


def show(sid):
    cur_p = os.path.join(OUT, sid + '.txt')
    old_p = os.path.join(OUT, sid + '.baseline.txt')
    cur = open(cur_p, encoding='utf-8', errors='replace').read().splitlines()
    if not os.path.exists(old_p):
        print('  (无 baseline.txt 副本，跳过逐行对比)')
        return
    old = open(old_p, encoding='utf-8', errors='replace').read().splitlines()
    d = [l for l in difflib.unified_diff(old, cur, lineterm='', n=0)
         if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    print('  差异行 %d 条，前 14 条：' % len(d))
    for l in d[:14]:
        print('    ' + l[:150])
    body = '\n'.join(cur)
    mine = sorted({k for k in KEY_MINE if k in body})
    env = sorted({k for k in KEY_ENV if k in body})
    print('  当前文本里命中我的关键词: %s' % (mine or '无'))
    print('  当前文本里命中环境关键词: %s' % (env or '无'))


for sid in DIFFS:
    print('=' * 76)
    print(sid)
    show(sid)
