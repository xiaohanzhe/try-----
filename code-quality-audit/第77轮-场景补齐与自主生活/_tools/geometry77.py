# -*- coding: utf-8 -*-
"""第77轮：把 UT / 黄魂 的真实房间尺寸登记进 `_room_geometry.json`。

★ 为什么**该登记**（而不是"不写就不写"）：
  该文件的 `note` 明写纪律是「**采不到的** (章,room) 不写进表 —— **不伪造** 640x480」。
  而 UT/黄魂 的 `w/h` **不是猜的**：它来自原作 `Data.Rooms[i].Width/Height`，
  且已与 `bigmap66.json` 的 645 个节点**逐条核验（名字+宽+高）全等**：
      ut 338/338、uty 287/287、DIFF=0。
  ⇒ 符合"采得到就写"的契约；不写反而会让 645 个场景在渲染层退化成"未知房间"
    （`rooms_round47` B7 就是这么报红的）。

★ 尺寸来源的三处一致（**同源**，不是三处各算一遍）：
  `ut_rooms.json`（UTMT 转储）→ `bigmap66.json`（第66轮）→ 本表。
  本脚本在写之前**再核验一次**，不符就不写。
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
SRC = {
    'ut': os.path.join(r'E:\Download\_extract61\_data\undertale', 'ut_rooms.json'),
    'uty': os.path.join(r'E:\Download\_extract61\_data\undertale_yellow', 'ut_rooms.json'),
}


def main():
    big = json.load(io.open(BIGMAP, encoding='utf-8'))
    gp = os.path.join(SCENES, '_room_geometry.json')
    g = json.load(io.open(gp, encoding='utf-8'))
    rooms = g['rooms']
    added = {}
    for work, ch in (('ut', 'ut'), ('uty', 'uty')):
        src = SRC[work]
        if not os.path.exists(src):
            print('[ABORT] 源不在：%s' % src)
            return 1
        raw = json.load(io.open(src, encoding='utf-8'))['rooms']
        byname = {n['index']: n for n in big['nodes'] if n.get('work') == work}
        n_ok = 0
        for r in raw:
            b = byname.get(r['index'])
            if b is None or b['name'] != r['name'] or b['w'] != r['w'] or b['h'] != r['h']:
                print('[ABORT] 核验不符：%s idx=%s' % (ch, r['index']))
                return 1
            n_ok += 1
        # 大图比原版多的（mod 增量）也一并登记（它也有真实 w/h）
        for idx, b in byname.items():
            if any(r['index'] == idx for r in raw):
                continue
            rooms['%s:%d' % (ch, idx)] = {'w': b['w'], 'h': b['h'],
                                          'name': b['name'], 'n_layers': None}
        for r in raw:
            rooms['%s:%d' % (ch, r['index'])] = {
                'w': r['w'], 'h': r['h'], 'name': r['name'],
                'n_layers': len(r.get('layers') or []) or None}
        added[ch] = len(byname)
        print('[GEOM] %s: 核验 %d/%d 全等 → 登记 %d 间' % (ch, n_ok, len(raw), len(byname)))
    g.setdefault('stats', {})
    tot = {}
    for k in rooms:
        tot[k.split(':')[0]] = tot.get(k.split(':')[0], 0) + 1
    g['stats'] = tot
    g.setdefault('note_extra', {})
    g['note_extra']['round77'] = (
        '第77轮：追加 ut / uty 两章（来自原作 Data.Rooms[i].Width/Height，'
        '经 bigmap66.json 逐条核验全等）。★ 与 ch1~ch5 同源同信度，'
        '不是"未知房间退化"填的 640x480。')
    with io.open(gp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(g, f, ensure_ascii=False, indent=1)
    print('[WRITE] _room_geometry.json  stats=', tot)
    return 0


if __name__ == '__main__':
    sys.exit(main())
