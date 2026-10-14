# -*- coding: utf-8 -*-
"""探针 C（只读）：注册表的 chapters / roam_scope 取值 + 桌面 4 门真实目的地。

要回答：
  ① `os_niko` / `ut_*` 的 `chapters` 填的是什么（作品名？'ut'？'undertale'？）
     —— 它决定 `world_gate` 暗世界分支能不能正确放行"回自己作品那侧"。
  ② `RoamScope` 各档各有多少人。
  ③ 桌面 4 门（`when_scene == 'desktop'`）的 `to` 到底是谁。
★ 只读。
"""
import collections
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PROJ = os.path.join(ROOT, 'ralsei_pet')
ASSETS = os.path.join(PROJ, 'assets')

OUT = []


def _load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


# ---------------- 注册表 ----------------
reg = _load(os.path.join(ASSETS, 'npc', '_registry.json'))
OUT.append('=== _registry.json 顶层键: %s' % sorted(reg.keys()))
npcs = reg.get('npcs')
OUT.append('npcs 类型 = %s  n=%d' % (type(npcs).__name__, len(npcs)))

items = npcs if isinstance(npcs, list) else list((npcs or {}).values())

OUT.append('')
OUT.append('--- 字段名（第一条的键）---')
OUT.append('  %s' % sorted(items[0].keys()))

OUT.append('')
OUT.append('--- chapters 取值分布 ---')
c_ch = collections.Counter()
for it in items:
    ch = it.get('chapters')
    c_ch[json.dumps(ch, ensure_ascii=False)] += 1
for k, v in c_ch.most_common():
    OUT.append('  %-40s %d' % (k, v))

OUT.append('')
OUT.append('--- roam_scope 取值分布 ---')
c_rs = collections.Counter(str(it.get('roam_scope')) for it in items)
for k, v in c_rs.most_common():
    OUT.append('  %-20s %d' % (k, v))

OUT.append('')
OUT.append('--- home_world 取值分布 ---')
c_hw = collections.Counter(str(it.get('home_world')) for it in items)
for k, v in c_hw.most_common():
    OUT.append('  %-20s %d' % (k, v))

OUT.append('')
OUT.append('--- 重点角色明细 ---')
want = ('ralsei', 'kris', 'susie', 'lancer', 'os_niko')
for it in items:
    if it.get('id') in want or str(it.get('id', '')).startswith(('ut_', 'os_', 'oty_', 'hy_')):
        OUT.append('  %-22s chapters=%-24s scope=%-10s home=%-6s esc=%s'
                   % (it.get('id'), json.dumps(it.get('chapters'), ensure_ascii=False),
                      it.get('roam_scope'), it.get('home_world'),
                      it.get('escape_via_bubble')))

OUT.append('')
OUT.append('--- 前缀分布（id 前 3 字符）---')
c_p = collections.Counter(str(it.get('id', ''))[:3] for it in items)
OUT.append('  %s' % dict(c_p))

# ---------------- 桌面 4 门 ----------------
OUT.append('')
OUT.append('=== _routes.json 里 when_scene == "desktop" 的路线 ===')
rw = _load(os.path.join(ASSETS, 'scenes', '_routes.json'))
routes = rw.get('routes') or []
hit = [r for r in routes if r.get('when_scene') == 'desktop']
OUT.append('  命中 %d 条' % len(hit))
for r in hit:
    OUT.append('  door=%-3s to=%-32s priority=%s' % (r.get('when_door'), r.get('to'), r.get('priority')))
    OUT.append('        reason=%s' % r.get('reason'))
OUT.append('  _fallback = %s' % json.dumps(rw.get('_fallback'), ensure_ascii=False))
OUT.append('  meta.coverage_policy = %s' % json.dumps((rw.get('meta') or {}).get('coverage_policy'), ensure_ascii=False))
OUT.append('  meta.oneshot_note = %s' % json.dumps((rw.get('meta') or {}).get('oneshot_note'), ensure_ascii=False))

# ---------------- scene_chapter 对这几个 id 的输出 ----------------
OUT.append('')
OUT.append('=== scene_chapter() 对迁入章 scene_id 的输出 ===')
import sys
sys.path.insert(0, os.path.join(PROJ, 'modules'))
import npc_system as ns  # noqa: E402
for sid in ('desktop', 'oneshot.mainline.INIT', 'ut.rooms.room_start',
            'ch1.hometown.town_mid', 'outertale.rooms.x', None):
    OUT.append('  %-30r -> %r' % (sid, ns.scene_chapter(sid)))

txt = '\n'.join(OUT)
print(txt)
with io.open(os.path.join(HERE, 'probe114c.txt'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(txt + '\n')
