# -*- coding: utf-8 -*-
"""第44轮 · `_room_geometry.json` 锚点校验（三个已知真值 + 覆盖度 + 负控制）。

铁律（记忆 §4）：**解析器/生成器的输出必须先过"已知真值"锚点，
全命中才允许用它的输出。**

三个已知真值（互相独立，来源不同）：
  A1 `ch1:2` = room_krisroom，**320×240** —— 第 43 轮相机结论独立给出
     "现实世界 320×240"；第 44 轮 rooms44 也采到 320×240。两处必须一致。
  A2 `ch1:35` = room_unknown（？？？？？？），见 `_index.json` 里
     `ch1.unknown.unknown` 的 `original_room_id: 35`。
  A3 全表 1,251 条 —— 与第 41/42/44 轮"原作 1,251 间"口径一致。

覆盖度：产品的 1,013 个 `original_room_id` 有多少能在几何表里找到？
  （找不到的 = 该场景背景/相机退化，必须量化，不能"应该没问题"）

负控制：故意查一个不存在的键、一个越界 id，确保校验**区分得出来**。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
GEO = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_room_geometry.json')
IDX = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')

FAIL = []
OK = []


def chk(cond, msg):
    (OK if cond else FAIL).append(msg)
    print(('  [OK]   ' if cond else '  [FAIL] ') + msg)


def main():
    with open(GEO, 'r', encoding='utf-8') as fh:
        geo = json.load(fh)
    rooms = geo['rooms']

    print('== A 已知真值锚点 ==')
    # A1
    r = rooms.get('ch1:2')
    chk(r is not None, 'A1 ch1:2 存在')
    chk(r and r.get('w') == 320 and r.get('h') == 240,
        'A1 ch1:2 = 320x240（第43轮相机结论一致）实际=%s' % (r,))
    chk(r and r.get('name') == 'room_krisroom',
        'A1 ch1:2 name = room_krisroom 实际=%s' % (r.get('name') if r else None,))
    # A2
    r2 = rooms.get('ch1:35')
    chk(r2 is not None, 'A2 ch1:35 存在')
    with open(IDX, 'r', encoding='utf-8') as fh:
        idx = json.load(fh)
    ent = (((idx.get('chapters') or {}).get('ch1') or {}).get('areas') or {}) \
        .get('unknown', {}).get('scenes', {}).get('ch1.unknown.unknown')
    chk(ent and ent.get('original_room_id') == 35,
        'A2 索引 ch1.unknown.unknown original_room_id == 35 实际=%s'
        % (ent.get('original_room_id') if ent else None,))
    # A3
    chk(len(rooms) == 1251, 'A3 全表 1,251 条 实际=%d' % len(rooms))

    print()
    print('== B 覆盖度（产品 1,013 场景 vs 几何表）==')
    scenes = {}
    for cid, chobj in (idx.get('chapters') or {}).items():
        if not isinstance(chobj, dict):
            continue
        for aid, aobj in (chobj.get('areas') or {}).items():
            if not isinstance(aobj, dict):
                continue
            for sid, sent in (aobj.get('scenes') or {}).items():
                if isinstance(sent, dict):
                    scenes[sid] = (cid, sent.get('original_room_id'))
    with_oid = [(s, c, o) for s, (c, o) in scenes.items() if isinstance(o, int)]
    miss = []
    for sid, c, o in with_oid:
        if '%s:%d' % (c, o) not in rooms:
            miss.append((sid, c, o))
    print('  产品场景 = %d，带 original_room_id = %d' % (len(scenes), len(with_oid)))
    print('  几何表命中 = %d / %d (%.1f%%)'
          % (len(with_oid) - len(miss), len(with_oid),
             100.0 * (len(with_oid) - len(miss)) / max(1, len(with_oid))))
    chk(len(miss) == 0 or len(miss) < 30,
        'B 未命中数 < 30（实际 %d）%s' % (len(miss), miss[:6]))
    for m in miss[:10]:
        print('     [MISS] %s (%s:%s)' % m)

    print()
    print('== C 负控制（校验必须区分得出来）==')
    chk(rooms.get('ch1:99999') is None, 'C1 越界 id 返回 None')
    chk(rooms.get('ch9:2') is None, 'C2 不存在的章返回 None')
    chk(rooms.get('ch1:2') != rooms.get('ch1:35'), 'C3 两个不同键给出不同记录')
    # C4：确定性 —— 重新加载结果一致
    with open(GEO, 'r', encoding='utf-8') as fh:
        geo2 = json.load(fh)
    chk(geo2['rooms'] == rooms, 'C4 重复加载结果一致（无随机/无顺序依赖）')

    print()
    if FAIL:
        print('结论：FAIL = %d' % len(FAIL))
        for f in FAIL:
            print('  - ' + f)
        return 1
    print('结论：FAIL = 0（%d 条断言全绿）' % len(OK))
    return 0


if __name__ == '__main__':
    sys.exit(main())
