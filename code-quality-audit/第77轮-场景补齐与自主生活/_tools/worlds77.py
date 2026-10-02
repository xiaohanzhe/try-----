# -*- coding: utf-8 -*-
"""第77轮：把 UT / 黄魂 登记进 `_worlds.json`（**如实标 unknown，不猜**）。

★ 为什么标 `unknown` 而不是 `dark`：
  `world_of_scene` 的契约（`scene_system.py:377`）明写
  「`'unknown'` 是一个**显式状态**，不是"暗世界"」⇒ 返回 `None`（不猜）。
  猜错的后果是把"回到光世界"在不该触发时触发，**把玩家的道具变成垃圾**。
  UT / 黄魂 的 `global.darkzone` 我们**没有取证**（那是每间房创建代码里的变量），
  所以**只能**标 unknown —— 这正是"如实登记缺口"。

★ 为什么还要写进表：让 `_index.json`（有 ut/uty 章）与 `_worlds.json`
  （无 ut/uty）**不再互相矛盾**；两处不一致正是"同一份规则两处算"的温床。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BIGMAP = os.path.join(ROOT, 'code-quality-audit', '第66轮-大图连通与mod并入',
                      '_evidence', 'bigmap66.json')


def main():
    big = json.load(io.open(BIGMAP, encoding='utf-8'))
    wp = os.path.join(SCENES, '_worlds.json')
    w = json.load(io.open(wp, encoding='utf-8'))
    added = {}
    for work, ch in (('ut', 'ut'), ('uty', 'uty')):
        nodes = [n for n in big['nodes'] if n.get('work') == work]
        rec = {str(n['index']): 'unknown' for n in nodes}
        w.setdefault('rooms', {})[ch] = rec
        w.setdefault('areas', {})[ch] = {'rooms': 'unknown'}
        added[ch] = len(rec)
        print('[WORLDS] %s: %d 间 → unknown' % (ch, len(rec)))
    unk = w.setdefault('meta', {}).setdefault('unknown_rooms', [])
    have = {(u.get('chapter'), u.get('room_id')) for u in unk}
    for work, ch in (('ut', 'ut'), ('uty', 'uty')):
        for n in [x for x in big['nodes'] if x.get('work') == work]:
            if (ch, n['index']) in have:
                continue
            unk.append({'area': 'rooms', 'chapter': ch, 'resource': n['name'],
                        'room_id': n['index'],
                        'why': '第77轮迁入：UT/黄魂 无 darkzone 取证，不猜世界'})
    w['meta']['work_chapters'] = {
        'why': '第77轮：跨作品大图 bigmap66.json 的房间已迁入 _index.json，'
               '此处为其世界登记（全部 unknown）。',
        'works': ['ut', 'uty'],
    }
    with io.open(wp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(w, f, ensure_ascii=False, indent=2)
    print('[WRITE] _worlds.json  新增 rooms/areas:', added)
    return 0


if __name__ == '__main__':
    sys.exit(main())
