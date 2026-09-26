# -*- coding: utf-8 -*-
"""第53轮 · 死代码摘要（只读）：把 A 类零引用 + 级联不可达，按模块归类，
并标出哪些属于本轮范围（除 AI 与场景系统）。输出 _evidence/deadcode_summary.txt
"""
import io
import os
import re
from collections import defaultdict

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
EV = os.path.join(ROOT, 'code-quality-audit', '第53轮-底层代码彻查', '_evidence')

# 本轮明确排除的两条线
AI = {'pet_ai', 'ai_driver', 'api_client', 'memory_system', 'memory_graph',
      'memory_store', 'worldview_recall', 'search_summarizer', 'event_speech'}
SCENE = {'scene_system', 'scene_controller', 'scene_canvas', 'scene_camera',
         'scene_render', 'scene_walk', 'scene_pathfind', 'scene_routing',
         'companion', 'companion_dialog', 'companion_roster', 'npc_system',
         'item_system', 'item_interact', 'item_menu', 'item_menu_ui'}
EXCLUDE = AI | SCENE


def mod_of(line):
    # 兼容 ralsei_pet\src\main.py:123 与 ralsei_pet\modules\foo.py:1 两种深度
    m = re.search(r'([\w_]+)\.py', line)
    return m.group(1) if m else '?'


def parse(path, tag):
    """A 类每行自带文件路径；级联清单靠 `--- <路径> (n 个) ---` 分组标题归属。"""
    rows = defaultdict(list)
    cur = '?'
    for ln in io.open(path, encoding='utf-8').read().splitlines():
        s = ln.strip()
        if not s or s.startswith(('【', '=', 'defs 总数')):
            continue
        m = re.match(r'^---\s+(.+?)\s+\(\d+\s*个\)\s+---$', s)
        if m:
            cur = mod_of(m.group(1))
            continue
        if s.startswith(('## ', '--- ')):
            continue
        key = cur if tag == '级联' else mod_of(s)
        rows[key].append('%s | %s' % (tag, s))
    return rows


A = parse(os.path.join(EV, 'baseline_deadcode.txt'), 'A零引用')
C = parse(os.path.join(EV, 'cascade_deadcode.txt'), '级联')

out = []
allmods = sorted(set(A) | set(C))
in_scope, out_scope = [], []
for m in allmods:
    n_a = len([x for x in A.get(m, []) if x.startswith('A零引用')])
    n_c = len(C.get(m, []))
    line = '%-22s A=%-3d 级联=%-3d %s' % (m, n_a, n_c,
                                          '【本轮范围】' if m not in EXCLUDE else '(AI/场景线)')
    (out_scope if m in EXCLUDE else in_scope).append(line)
    if m not in EXCLUDE:
        for x in A.get(m, []) + C.get(m, []):
            pass

out.append('=== 按模块汇总（A = 直接零引用；级联 = 从入口不可达）===')
out.append('')
out.append('---- 本轮范围（除 AI / 场景系统）----')
out.extend(in_scope)
out.append('')
out.append('---- 已排除（AI 线 / 场景线，本轮不判）----')
out.extend(out_scope)
out.append('')
out.append('=== 本轮范围内的符号明细 ===')
for m in sorted(m for m in allmods if m not in EXCLUDE):
    rows = A.get(m, []) + C.get(m, [])
    if not rows:
        continue
    out.append('')
    out.append('## %s  (%d 条)' % (m, len(rows)))
    out.extend('   ' + r for r in rows)

io.open(os.path.join(EV, 'deadcode_summary.txt'), 'w', encoding='utf-8',
        newline='\n').write('\n'.join(out) + '\n')
print('\n'.join(out[:60]))
print('...')
print('本范围内模块数 =', len(in_scope), ' 已排除模块数 =', len(out_scope))
