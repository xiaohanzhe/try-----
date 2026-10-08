# -*- coding: utf-8 -*-
"""reach96b.py —— 候选可达性普查：某方法/字段是否真被调用（用户视角可见性的前提）

★ 教训（第96轮b）：先判"可达性"再判"是不是缺陷"。
  本项目已多次出现"写了但零接线"（`trigger_surprise` / `reset_special_states` /
  `pet_interaction`）⇒ 静态上"逻辑闭合"但用户根本触发不到 = 不可见 ⇒ 不许报成真缺陷。
"""
import io
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

TARGETS = [
    'trigger_surprise', 'trigger_shy', 'trigger_unhappy', 'trigger_victory',
    'trigger_laugh', 'trigger_teasplash', 'reset_special_states',
    'is_shy', 'is_unhappy', 'is_wearing_suit', 'is_holding_cotton_candy',
    'speak_event', 'react_to_desktop_element', 'check_nearby_desktop_elements',
    'update_bounce', '_bounce_timer', 'play_animation_once', '_play_once_active',
]

texts = {}
for dp, dn, fn in os.walk(PKG):
    if '__pycache__' in dp:
        continue
    for f in fn:
        if f.endswith('.py'):
            p = os.path.join(dp, f)
            try:
                texts[p] = io.open(p, encoding='utf-8', newline='').read()
            except Exception:
                pass

print('=' * 78)
print('# 候选可达性普查（读写点计数）')
print('=' * 78)

for tok in TARGETS:
    w = []   # 赋值
    r = []   # 读取/调用
    d = []   # 定义
    for p, t in texts.items():
        rel = os.path.relpath(p, ROOT)
        for ln, line in enumerate(t.split('\n'), 1):
            if tok not in line:
                continue
            if re.search(r'def\s+%s\b' % re.escape(tok), line):
                d.append((rel, ln))
                continue
            if re.search(re.escape(tok) + r'\s*=', line) and not re.search(r'==|<=|>=|!=', line):
                w.append((rel, ln))
            elif re.search(re.escape(tok) + r'\s*\(', line):
                r.append((rel, ln))
            else:
                r.append((rel, ln))
    print('\n%s' % tok)
    print('  定义: %s' % (d or '无'))
    print('  赋值: %d 处 %s' % (len(w), w[:4]))
    print('  读/调: %d 处 %s' % (len(r), r[:4]))
    if not d:
        print('  ⚠️ 连定义都没有')
    elif len(r) + len(w) <= 1:
        print('  ⚠️⚠️ 除定义外几乎无引用 ⇒ 疑似零接线（用户不可达）')
