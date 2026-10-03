# -*- coding: utf-8 -*-
u"""第80轮：把 OneShot 章**同步**进 `_worlds.json`（明暗世界表）。

为什么必须同步（★「同一份规则两处算」的反面用法）
--------------------------------------------------
第77轮 `build77.py` 抬头写死了一条纪律：
> `_worlds.json` 与 `_index.json` 必须一致，故由**同一份中间产物**派生，不手写两遍。

`_index.json` 已加 `oneshot` 章（263 场景），若 `_worlds.json` 不跟：
* `ch48` 系的「明暗世界覆盖」判据会漏掉 263 个新场景；
* `scene_world()` 对这 263 间会返回 `None`（"不知道"），
  而 UT/黄魂的同类是 `'unknown'` —— **两处口径就不一致了**。

口径（**照抄 UT/黄魂，不许猜**）
-------------------------------
UT(358) / 黄魂(287) 在 `_worlds.json` 里**逐间**都是 `'unknown'`
（原作出处：第48轮 F 段 —— 这两作的明暗判定表未建，**如实标 unknown**）。
OneShot 同理：本轮的勘查**只取了地图尺寸与门**，**没有**取明暗，
⇒ 263 间**全部** `'unknown'`，与两作同规。★ 一个 `light`/`dark` 都不许编。

零改 main.py；只动数据。
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
WORLDS = os.path.join(SCENES, '_worlds.json')
INDEX = os.path.join(SCENES, '_index.json')

CH = 'oneshot'
AREA = 'rooms'


def load_json(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def one_shot_room_ids():
    """→ 从**已迁入的产品索引**里取 OneShot 的 original_room_id 集合。

    ★ 真源 = `_index.json`（不是勘查产物）—— 这样"两处"派生于**同一份事实**，
      不会出现"索引多一间、worlds 少一间"的漂移。
    """
    idx = load_json(INDEX)
    ch = (idx.get('chapters') or {}).get(CH)
    if not ch:
        return None
    ids = set()
    for a in (ch.get('areas') or {}).values():
        for sc in (a.get('scenes') or {}).values():
            rid = sc.get('original_room_id')
            if isinstance(rid, int):
                ids.add(rid)
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    w = load_json(WORLDS)
    ids = one_shot_room_ids()
    if ids is None:
        print('[ABORT] `_index.json` 里没有 `oneshot` 章 ⇒ 先跑 build80.py')
        return 1
    print('[SRC] 索引里 OneShot 房间 %d 间 -> id %d..%d'
          % (len(ids), min(ids), max(ids)))

    # ---- 前置自检：UT/黄魂的既有口径（必须是 unknown，否则本脚本照抄的基准就错了）----
    ut = (w['rooms'].get('ut') or {})
    uty = (w['rooms'].get('uty') or {})
    all_unknown = all(v == 'unknown' for v in ut.values()) \
        and all(v == 'unknown' for v in uty.values())
    if not all_unknown:
        print('[ABORT] UT/黄魂 的 rooms 不是全 unknown ⇒ 口径变了，别照抄')
        return 1
    print('[OK] UT/%d 黄魂/%d 全 unknown（照抄基准成立）' % (len(ut), len(uty)))

    # ---- 幂等：已存在的 oneshot rooms 必须与重算结果一致 ----
    before = w['rooms'].get(CH)
    want = dict((str(i), 'unknown') for i in sorted(ids))
    if before is not None and before != want:
        print('[WARN] 既有 oneshot rooms 与重算不一致（%d vs %d）'
              % (len(before), len(want)))

    if not args.write:
        print('[CHECK-ONLY] 将写入 areas.oneshot=%s 与 rooms.oneshot(%d 间)，未写盘'
              % ({AREA: 'unknown'}, len(want)))
        return 0

    w['areas'][CH] = {AREA: 'unknown'}
    w['rooms'][CH] = want

    # ★★ 第80轮补（首版**漏了**这一步，被 ch48 F4 判据抓到）：
    #   `meta.unknown_rooms` 也必须同步 —— 它由 `rooms` **派生**（单一真源），
    #   凡值 not in ('light','dark') 的 (章, room_id) 一律登记。
    #   Deltarune 的既有登记**逐条保留原文**（含 why），迁入章按既有形状补。
    _sync_meta_unknown(w, INDEX, CH)
    with io.open(WORLDS, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(w, f, ensure_ascii=False, indent=1)
    print('[WRITE] _worlds.json（areas+rooms+meta.unknown_rooms 同步）')

    # ---- 写后回验：真落盘了 ----
    w2 = load_json(WORLDS)
    ok = (w2['areas'].get(CH) == {AREA: 'unknown'}
          and len(w2['rooms'].get(CH) or {}) == len(want)
          and len((w2.get('meta') or {}).get('unknown_rooms') or []) == 649 + 263)
    print('[VERIFY] 回读: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


_DR_CH = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')


def _sync_meta_unknown(w, index_path, ch):
    """把 `meta.unknown_rooms` 重算成 `rooms` 的派生物（Deltarune 原文保留）。"""
    idx = load_json(index_path)
    name_of = {}
    for c, crec in (idx.get('chapters') or {}).items():
        for a in (crec.get('areas') or {}).values():
            for _, ent in (a.get('scenes') or {}).items():
                rid = ent.get('original_room_id')
                if isinstance(rid, int):
                    name_of.setdefault((c, rid),
                                       ent.get('name_raw') or ent.get('name') or '')
    keep = {}
    for r in ((w.get('meta') or {}).get('unknown_rooms') or []):
        if r.get('chapter') in _DR_CH:
            keep[(r['chapter'], int(r['room_id']))] = r
    want = []
    for c in sorted(w.get('rooms') or {}):
        for rid_s, v in sorted((w['rooms'][c] or {}).items(), key=lambda kv: int(kv[0])):
            if v in ('light', 'dark'):
                continue
            key = (c, int(rid_s))
            if key in keep:
                want.append(keep[key])
            else:
                want.append({'chapter': c, 'room_id': int(rid_s), 'area': None,
                             'resource': name_of.get(key, ''),
                             'why': '迁入章，明暗判定表未建（如实标 unknown，见第77/80轮）'})
    w.setdefault('meta', {})['unknown_rooms'] = want
    return want


if __name__ == '__main__':
    sys.exit(main())
