"""第76轮 R0 现场取证探针（离线读源码 + 真机端口检查）。

不做任何修改，只**读**。输出落盘 UTF-8。
"""
import io
import json
import os
import re
import sys

# 本文件在 <ROOT>/code-quality-audit/<轮次>/_tools/ 下 ⇒ 上三级才是仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   '_evidence', 'r0_probe76.txt')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

buf = []


def w(s=''):
    buf.append(s)


MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
src = io.open(MAIN, encoding='utf-8').read()
lines = src.splitlines()

w('=== 第76轮 R0 现场取证 ===')
w('main.py 行数 = %d' % len(lines))
w()

# --- 1. 灵魂相关方法接线计数 ---
w('## 1. 灵魂（SOUL）接线现状')
for pat in ['_soul_visible', '_soul_press', '_soul_release', '_soul_pick_prop',
            '_soul_tick', '_on_scene_switched_soul', 'toggle_soul', 'show_soul',
            'hide_soul', 'init_soul', '_soul_respawn']:
    defs = len(re.findall(r'^\s*def\s+%s\b' % re.escape(pat), src, re.M))
    calls = len(re.findall(r'\b%s\b' % re.escape(pat), src))
    w('  %-24s 定义=%d 全文出现=%d 真实调用≈%d' % (pat, defs, calls, calls - defs))
w()

# --- 2. 方向键 / E / Z 键接线 ---
w('## 2. 按键接线')
for pat, label in [(r'_Qt\.Key_S', 'S键(菜单)'),
                   (r'_Qt\.Key_E', 'E键(交互)'),
                   (r'_Qt\.Key_Z', '★Z键(附身)'),
                   (r'direction_of_qt_key', '方向键识别')]:
    hits = [(i + 1, lines[i].strip()) for i, l in enumerate(lines) if re.search(pat, l)]
    w('  %-16s %d 处' % (label, len(hits)))
    for ln, t in hits[:6]:
        w('      :%d  %s' % (ln, t[:100]))
w()

# --- 3. 视角跟随：相机锚点 ---
w('## 3. ★ 视角跟随（R4）锚点')
for pat in ['camera_follow', '_pet_target_rect', 'screen_to_room']:
    hits = [(i + 1, lines[i].strip()) for i, l in enumerate(lines) if re.search(re.escape(pat), l)]
    w('  %-20s %d 处' % (pat, len(hits)))
    for ln, t in hits[:8]:
        w('      :%d  %s' % (ln, t[:110]))
w()

# --- 4. R0-1 一句话入口：三个函数调用数 ---
w('## 4. ★ R0-1 一句话入口接线')
for pat in ['follow_route', 'plan_route_to', 'resolve_destination',
            'plan_route_text', 'destinations_text', 'pick_route']:
    hits = []
    for root, dirs, files in os.walk(os.path.join(ROOT, 'ralsei_pet')):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for fn in files:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(root, fn)
            s2 = io.open(p, encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'\b%s\b' % re.escape(pat), s2):
                ln = s2[:m.start()].count('\n') + 1
                ln_txt = s2.splitlines()[ln - 1].strip()
                is_def = bool(re.match(r'\s*def\s+%s\b' % re.escape(pat), ln_txt))
                is_comment = ln_txt.startswith('#')
                hits.append((os.path.relpath(p, ROOT), ln, is_def, is_comment, ln_txt))
    real = [h for h in hits if not h[2] and not h[3]]
    w('  %-22s 总=%d 定义=%d 注释=%d ★真实调用=%d' % (
        pat, len(hits), sum(1 for h in hits if h[2]),
        sum(1 for h in hits if h[3]), len(real)))
    for h in real[:6]:
        w('      %s:%d  %s' % (h[0], h[1], h[4][:100]))
w()

# --- 5. R0-2 门可交互 ---
w('## 5. ★ R0-2 门可交互')
II = os.path.join(ROOT, 'ralsei_pet', 'modules', 'item_interact.py')
ii = io.open(II, encoding='utf-8').read()
ii_lines = ii.splitlines()
for i, l in enumerate(ii_lines):
    if 'door' in l.lower() and ('handled_by' in l or 'kind' in l or 'skip' in l or 'continue' in l):
        w('  item_interact:%d  %s' % (i + 1, l.strip()[:110]))
w()
# build_props 的 else 分支
m = re.search(r'def build_props\(', ii)
if m:
    start = ii[:m.start()].count('\n')
    w('  --- build_props 全文（%d 行起）---' % (start + 1))
    for j in range(start, min(start + 110, len(ii_lines))):
        w('  %d| %s' % (j + 1, ii_lines[j]))
w()

# --- 6. 世界门控 ---
w('## 6. R0-3 世界门控')
for pat in ['soul_can_enter', 'world_gate', '_worlds.json']:
    hits = []
    for root, dirs, files in os.walk(os.path.join(ROOT, 'ralsei_pet')):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for fn in files:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(root, fn)
            s2 = io.open(p, encoding='utf-8', errors='replace').read()
            c = len(re.findall(re.escape(pat), s2))
            if c:
                hits.append((os.path.relpath(p, ROOT), c))
    w('  %-18s %s' % (pat, hits if hits else '无'))
w()

# --- 7. 数据文件 ---
w('## 7. 数据文件')
for rel in ['ralsei_pet/assets/scenes/_aliases.json',
            'ralsei_pet/assets/scenes/_routes.json',
            'ralsei_pet/assets/scenes/_worlds.json',
            'ralsei_pet/assets/scenes/_index.json',
            'ralsei_pet/assets/scenes/_geometry.json']:
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        w('  %-46s %d B' % (rel, os.path.getsize(p)))
    else:
        w('  %-46s ❌ 不存在' % rel)
# 找 scenes 目录
sd = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
if os.path.isdir(sd):
    w('  scenes 目录下非场景文件: %s' % [f for f in sorted(os.listdir(sd))
                                        if f.startswith('_') or f.endswith('.json')][:20])
w()

io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(buf))
print('written:', OUT, len('\n'.join(buf)), 'chars')
