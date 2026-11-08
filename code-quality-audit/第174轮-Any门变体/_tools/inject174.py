# -*- coding: utf-8 -*-
u"""第174轮 · 把 `obj_doorAnyHorz` / `obj_doorAnyVert` 实例补进场景 `objects`（**幂等追加**）。

与第173轮 `inject173.py` 同一套做法（只追加、不重跑生成器），差别只有两点：
  ① 对象名从单值 `obj_doorAny` 变成**集合**（两个变体）；
  ② 实例来源从第42轮普查换成 `第174轮/_evidence/analyze174.json` —— 因为它
     已经把「实例 → 源场景」解析好了（含 `_index.json` 回退），省掉重复推导。

产物字段与 173 完全一致：

    {"pos": [x, y], "src": "obj_doorAnyHorz"}     # 或 obj_doorAnyVert

**故意不写 `sprite`**：两个变体都是 `visible=false` 的触发器（`_obj_visible.json`
的 hidden 名单里有），`is_drawable_object()` 会滤掉 ⇒ 永不绘制；写一个指向不存在
文件的 sprite 才是假话（`assets/scenes/objs/` 里只有 `spr_doorA..F`，没有 `spr_doorAny`）。

★ 为什么 51 扇全物化、连没有路由的 9 扇也物化：
  原作里它们**确实存在**。没路由时 `build_props` 查不到目标就**不建门**
  （`查不到 ⇒ 不建，而不是建一扇推不开的门`）⇒ 多这 9 个物件零行为变化，
  但数据不说谎；将来若补上边就直接生效。

用法
----
    python inject174.py            # 只算不写（默认）
    python inject174.py --apply    # 真写
"""
import importlib.util
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROUND, '_evidence')
GEN44 = os.path.join(REPO, 'code-quality-audit', u'第44轮-原作对话框复刻', '_tools',
                     'gen_objects44.py')

DRY = '--apply' not in sys.argv

#: 本轮补的对象名（**集合**；第173轮的 `obj_doorAny` 不在这里，不许重复补）
WANT = ('obj_doorAnyHorz', 'obj_doorAnyVert')


def load_g44():
    spec = importlib.util.spec_from_file_location('gen44_mod', GEN44)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['gen44_mod'] = mod
    spec.loader.exec_module(mod)
    return mod


def rd(p):
    return json.load(io.open(p, 'r', encoding='utf-8'))


def load_room_of():
    """`{scene_id: 原作房间下标}` —— 取自 `_index.json`（★ 87 个独立文件缺该字段）。"""
    p = os.path.join(SCENES, '_index.json')
    out = {}
    if not os.path.exists(p):
        return out
    for _ch, blk in ((rd(p).get('chapters') or {}) or {}).items():
        if not isinstance(blk, dict):
            continue
        for _ar, ablk in ((blk.get('areas') or {}) or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, e in ((ablk.get('scenes') or {}) or {}).items():
                if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
                    out[str(sid)] = e['original_room_id']
    return out


def collect():
    """`{'章:房间id': [(x, y, obj), ...]}` —— 取自已解析的取证，坐标去重。"""
    an = rd(os.path.join(EV, 'analyze174.json'))
    out, total = {}, 0
    for r in an.get('rows') or []:
        if r.get('obj') not in WANT:
            continue
        x, y, rid = r.get('x'), r.get('y'), r.get('room_index')
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(rid, int):
            continue
        total += 1
        lst = out.setdefault('%s:%d' % (r['ch'], rid), [])
        if not any(a == x and b == y and o == r['obj'] for a, b, o in lst):
            lst.append((x, y, r['obj']))
    return out, total


def fill(sc, key, want):
    items = want.get(key)
    if not items:
        return 0
    objs = sc.setdefault('objects', [])
    added = 0
    for x, y, obj in items:
        if any(isinstance(o, dict) and o.get('src') == obj
               and (o.get('pos') or [None, None]) == [x, y] for o in objs):
            continue
        objs.append({'pos': [x, y], 'src': obj})
        added += 1
    return added


def main():
    g44 = load_g44()
    g44.DRY_RUN = DRY

    want, total = collect()
    print(u'取证里变体实例 %d 条（去重后落 %d 个「章:房间id」键）' % (total, len(want)))
    room_of = load_room_of()
    print(u'房间号回退表（_index.json）%d 条' % len(room_of))

    files = n_add = n_have = n_fallback = 0
    per_file, hit = {}, set()
    for name in sorted(os.listdir(SCENES)):
        if not name.endswith('.json'):
            continue
        if name.startswith('_') and not name.startswith('_zone.'):
            continue
        p = os.path.join(SCENES, name)
        data = rd(p)
        if not isinstance(data, dict):
            continue
        inner = data.get('scenes')
        if isinstance(inner, dict):
            ch = data.get('chapter_id')
            pool = [sc for sc in inner.values() if isinstance(sc, dict)]
        elif 'objects' in data or 'scene_id' in data:
            ch = data.get('chapter_id')
            pool = [data]
        else:
            continue
        files += 1
        add_here = 0
        for sc in pool:
            rid = sc.get('original_room_id')
            if not isinstance(rid, int):
                rid = room_of.get(str(sc.get('scene_id') or ''))
                if isinstance(rid, int):
                    n_fallback += 1
            if not (ch and isinstance(rid, int)):
                continue
            key = '%s:%d' % (ch, rid)
            if key not in want:
                continue
            hit.add(key)
            for x, y, obj in want[key]:
                if any(isinstance(o, dict) and o.get('src') == obj
                       and (o.get('pos') or [None, None]) == [x, y]
                       for o in (sc.get('objects') or [])):
                    n_have += 1
            add_here += fill(sc, key, want)
        if add_here:
            per_file[name] = add_here
            n_add += add_here
            if not DRY:
                g44.dump(p, data)

    print('')
    print(u'★ 需新增 %d 条 | 已存在 %d 条 | 落在未登记房间 %d 条'
          % (n_add, n_have, sum(len(v) for k, v in want.items() if k not in hit)))
    print(u'★ 涉及文件 %d 个 / 已扫文件 %d 个 / 经 index 回退补房间号 %d 个场景'
          % (len(per_file), files, n_fallback))
    for name, c in sorted(per_file.items(), key=lambda kv: -kv[1]):
        print('   %-52s +%d' % (name, c))
    if DRY:
        print('')
        print(u'（DRY RUN：未写盘。加 --apply 生效）')
        return 0
    print('')
    print(u'已写回 %d 个文件' % len(per_file))
    return 0


if __name__ == '__main__':
    sys.exit(main())
