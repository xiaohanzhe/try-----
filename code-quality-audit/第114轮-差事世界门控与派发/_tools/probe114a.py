# -*- coding: utf-8 -*-
"""探针 A（只读）：差事目的地 → 世界，能不能判出来。

问题：`world_gate(npc, world, scene_id=...)` 需要 `world`，而差事只存
`dest_scene`（scene_id 字符串）。本探针验证「从 scene_id 反推 world」这条
路走得通、并且桌面 4 条路线与若干真实房间都能落到 light/dark。

★ 只读：不写任何文件、不改任何状态。
"""
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PROJ = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PROJ, 'modules')
sys.path.insert(0, MODS)

import scene_system as ss  # noqa: E402

OUT = []
OUT.append('ROOT   = %s' % ROOT)
OUT.append('PROJ   = %s' % PROJ)
OUT.append('scenes_dir = %s' % ss.scenes_dir())

idx = ss.load_index()
OUT.append('index.ok = %s  schema=%s  scenes=%d  default=%s  err=%s'
           % (idx.get('ok'), idx.get('schema_version'), len(idx.get('scenes') or {}),
              idx.get('default_scene'), idx.get('error')))

wd = ss.load_worlds()
OUT.append('worlds.ok = %s  rooms_chapters=%d  overrides=%s  err=%s'
           % (wd.get('ok'), len(wd.get('rooms') or {}),
              sorted((wd.get('overrides') or {}).keys()), wd.get('error')))

# ---- 桌面 4 条路线（真源 = _routes.json 里 desktop 的 4 条）----
routes_path = os.path.join(PROJ, 'assets', 'scene', '_routes.json')
if not os.path.isfile(routes_path):
    for cand in ('assets/scenes/_routes.json', 'assets/scene/_routes.json'):
        p = os.path.join(PROJ, *cand.split('/'))
        if os.path.isfile(p):
            routes_path = p
            break
OUT.append('routes_path = %s  exists=%s' % (routes_path, os.path.isfile(routes_path)))
dest_from_routes = []
if os.path.isfile(routes_path):
    with io.open(routes_path, 'r', encoding='utf-8') as fh:
        rw = json.load(fh)
    d = rw.get('desktop')
    OUT.append('routes.desktop 类型 = %s' % type(d).__name__)
    if isinstance(d, dict):
        for k, v in d.items():
            tgt = v.get('dest') if isinstance(v, dict) else v
            dest_from_routes.append(tgt)
            OUT.append('  route %r -> %r  (%s)' % (k, tgt, v))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            tgt = v.get('dest') if isinstance(v, dict) else v
            dest_from_routes.append(tgt)
            OUT.append('  route[%d] -> %r' % (i, tgt))

# ---- 待判定的 scene_id 集合 ----
dest_extra = [
    'desktop',
    None,                      # 显式试 None（"判不出"该走哪条分支）
    'ch1.hometown.town_mid',
    'oneshot.mainline.INIT',
    'ut.rooms.room_start',
    'ch1.dark_world.card_castle_entrance',
]
cands = []
for c in list(dest_from_routes) + dest_extra:
    if c not in cands:
        cands.append(c)
# 再随机取 5 个 index 里的真实 scene_id，看解析覆盖率
real = sorted((idx.get('scenes') or {}).keys())[:5]
cands.extend(real)

OUT.append('')
OUT.append('%-46s | %-12s | %-8s | %-6s' % ('scene_id', 'chapter', 'room_id', 'world'))
OUT.append('-' * 90)

def world_from_sid(sid):
    """从 scene_id 反推 world：先 overrides，再 index[chapter_id, original_room_id]。"""
    if not sid:
        return None, 'sid 为空'
    ov = wd.get('overrides') or {}
    if sid in ov:
        return ov[sid], 'override'
    entry = (idx.get('scenes') or {}).get(sid)
    if not isinstance(entry, dict):
        return None, 'index 里没有这个场景'
    ch = entry.get('chapter_id')
    rid = entry.get('original_room_id')
    if not ch or rid is None:
        return None, 'entry 缺 chapter/room（ch=%r rid=%r）' % (ch, rid)
    rec = (wd.get('rooms') or {}).get(ch)
    if not isinstance(rec, dict):
        return None, 'worlds.rooms 缺章 %r' % (ch,)
    w = rec.get(str(rid))
    if w == 'unknown':
        return None, '该房登记为 unknown'
    return (w if w in ('light', 'dark') else None), ('rooms[%s][%s]' % (ch, rid))

for sid in cands:
    if sid is None:
        OUT.append('%-46s | %-12s | %-8s | %-6s   (%s)'
                   % ('<None>', '-', '-', '-', '空场景'))
        continue
    w, how = world_from_sid(sid)
    entry = (idx.get('scenes') or {}).get(sid) or {}
    OUT.append('%-46s | %-12s | %-8s | %-6s   (%s)'
               % (sid, entry.get('chapter_id'), entry.get('original_room_id'),
                  w, how))

# ---- 顺带：world_gate 对 world=None / world='light' / 'dark' 的行为 ----
OUT.append('')
OUT.append('=== world_gate 边界（scene_id=None 时）===')
sys.path.insert(0, MODS)


class _N(object):
    def __init__(self, i, cn, hw='dark', esc=False, ch=(), scope=None):
        self.id = i
        self.name = i
        self.name_cn = cn
        self.home_world = hw
        self.escape_via_bubble = esc
        self.chapters = list(ch)
        self.roam_scope = scope


try:
    from npc_system import world_gate, RoamScope
    ral = _N('ralsei', 'Ralsei', 'dark', True, ['ch1', 'ch2'], RoamScope.HOME)
    kr = _N('kris', 'Kris', 'light', False, ['ch1'], RoamScope.HOME)
    for world in (None, 'light', 'dark', 'weird'):
        for who in (ral, kr):
            g = world_gate(who, world, scene_id=None, carried=False)
            OUT.append('  world=%-7r npc=%-7s -> ok=%-5s reason=%-22s detail=%s'
                       % (world, who.id, g.ok, g.reason, g.detail))
except Exception as e:
    OUT.append('  !! import/调用失败: %r' % (e,))

txt = '\n'.join(OUT)
print(txt)
with io.open(os.path.join(HERE, 'probe114a.txt'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(txt + '\n')
