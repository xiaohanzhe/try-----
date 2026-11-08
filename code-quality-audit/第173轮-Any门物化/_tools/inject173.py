# -*- coding: utf-8 -*-
"""第173轮 · 把 `obj_doorAny` 实例补进场景 `objects`（**幂等追加**）。

为什么要有这一轮
----------------
第172轮把 798 条 Any 门边写进了 `_routes.json`，但**一条都没被消费**：
`build_props()` 遍历 `scene['objects']`，而场景数据里 `src == 'obj_doorAny'`
的物件一个都没有 ⇒ 没有实例就没人调 `route_for_door()`。

根因不是"忘了写"，是**素材缺失导致的过滤**：
`gen_objects44.object()` 的规矩是「查不到 sprite 帧 ⇒ 返回 None」
（原意：不可见的纯逻辑锚点画出来是一堆空框）。
`obj_doorAny` 的 spr 是 `spr_doorAny`，但 `assets/scenes/objs/` 里
**没有 `spr_doorAny_0.png`**（`spr_doorA..F` 都有）⇒ 881 条实例被静默跳过。

为什么采取"追加"而不是"重跑生成器"
----------------------------------
第68轮 `gen_objects68.py` 会用 inst68 重建 `objects`，第117轮又改过门的尺寸。
重跑链上任何一环都会把后来几轮的增量冲掉（记忆 §130「派生字段必被重建冲掉」）。
⇒ 本轮只**追加**缺失项，不动任何已有条目，也不动生成器本身。
（代价：将来若重跑 gen68，这些条目会消失。已用 `check173 D 段`兜住：
 消失即报红，不会被静默吞掉。）

产物字段
--------
```json
{"pos": [x, y], "src": "obj_doorAny", "depth": <int|省略>}
```
**故意不写 `sprite`**：原作 `obj_doorAny` 是 `visible=false` 的不可见触发器，
`is_drawable_object()` 会把它滤掉（`src` 在 `_obj_visible.json` 的 hidden 里）
⇒ 永远不会被绘制，写一个指向不存在文件的 sprite 才是假话。

用法
----
    python inject173.py            # 只算不写（默认）
    python inject173.py --apply    # 真写
"""
import importlib.util
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GEN44 = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_tools',
                     'gen_objects44.py')

DRY = '--apply' not in sys.argv

#: 本轮补的对象名（**只补这一个**；ch5 的 AnyHorz/AnyVert/AnyModespecific 另行裁定）
WANT = 'obj_doorAny'

INST = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
        'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}


def load_g44():
    spec = importlib.util.spec_from_file_location('gen44_mod', GEN44)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['gen44_mod'] = mod
    spec.loader.exec_module(mod)
    return mod


def rd(p):
    return json.load(io.open(p, 'r', encoding='utf-8'))


def load_room_of():
    """`{scene_id: 原作房间下标}` —— 取自 `_index.json`（★ 补 87 个独立文件的缺口）。

    ★ 为什么需要这条回退：88 个**独立场景文件**里有 **87 个没有 `original_room_id`**
      （分片里的场景都有）。第一版本只认场景自带的字段 ⇒ 这 87 个场景被整块跳过，
      它们房间里的 Any 门（115 条）全部落到"未登记"账上。
    ★ 为什么回退到 `_index.json` 而不是往场景文件里补字段：产品运行时
      `MainWindow._scene_rooms()` 本身就是**读 `_index.json`** 取房间号的
      （`main.py` 第 4694~4698 行）⇒ 走 index 与运行时同源，行为一致；
      而改 87 个场景文件的 schema 会波及别的锁（房间反查/卡片派生），本轮不碰。
    ★ 读不到 ⇒ 空表（回退失效，那 115 条会重新算成"未登记"，`check173` 会报红）。
    """
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


def collect_inst():
    """普查 → {'ch:roomid': [(x, y, depth), ...]}（同坐标去重）。"""
    out = {}
    total = 0
    for ch, fn in INST.items():
        p = os.path.join(E42, fn)
        if not os.path.exists(p):
            print('缺普查 %s' % p)
            continue
        d = rd(p)
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            if not isinstance(rid, int):
                continue
            for it in (rec.get('insts') or []):
                if it.get('obj') != WANT:
                    continue
                x, y = it.get('x'), it.get('y')
                if not isinstance(x, int) or not isinstance(y, int):
                    continue
                total += 1
                lst = out.setdefault('%s:%d' % (ch, rid), [])
                if not any(a == x and b == y for a, b, _ in lst):
                    lst.append((x, y, it.get('depth')))
    return out, total


def fill(sc, ch, want, rid):
    """给一个场景补齐缺的 Any 条目；返回新增条数。

    ★ `rid` 由调用方传入（**不再从 `sc` 里取**）：87 个独立场景文件没有
      `original_room_id`，要靠 `_index.json` 回退（见 `load_room_of`）。
    """
    if ch is None or not isinstance(rid, int):
        return 0
    items = want.get('%s:%d' % (ch, rid))
    if not items:
        return 0
    objs = sc.setdefault('objects', [])
    added = 0
    for x, y, dpt in items:
        if any(isinstance(o, dict) and o.get('src') == WANT
               and (o.get('pos') or [None, None]) == [x, y] for o in objs):
            continue
        rec = {'pos': [x, y], 'src': WANT}
        if isinstance(dpt, int):
            rec['depth'] = dpt
        objs.append(rec)
        added += 1
    return added


def main():
    g44 = load_g44()
    g44.DRY_RUN = DRY

    want, total_inst = collect_inst()
    print('普查里 %s 实例 %d 条（去重后落 %d 个「章:房间id」键）'
          % (WANT, total_inst, len(want)))

    room_of = load_room_of()
    print('房间号回退表（_index.json）%d 条' % len(room_of))

    # ---- 逐文件处理：先算，再（可选）写 ----
    files = 0
    n_add = n_have = n_noroom = 0
    n_rid_fallback = 0
    per_file = {}
    hit_keys = set()
    for name in sorted(os.listdir(SCENES)):
        if not name.endswith('.json'):
            continue
        # ★ 只跳过「登记表/配置」类下划线文件；`_zone.*.json` 是场景载体，必须处理
        #   （第一版一刀切跳过 `_` 开头 ⇒ 2,078 个场景全漏，只剩 88 个独立文件）。
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
                # ★ 回退：87 个独立场景文件没有这个字段，用 `_index.json` 补
                #   （与运行时 `_scene_rooms()` 同源）。取不到才是真的没登记。
                rid = room_of.get(str(sc.get('scene_id') or ''))
                if isinstance(rid, int):
                    n_rid_fallback += 1
            key = '%s:%d' % (ch, rid) if (ch and isinstance(rid, int)) else None
            if key is None:
                continue
            if key in want:
                hit_keys.add(key)
                # 统计"已存在"用于口算
                for x, y, _d in want[key]:
                    if any(isinstance(o, dict) and o.get('src') == WANT
                           and (o.get('pos') or [None, None]) == [x, y]
                           for o in (sc.get('objects') or [])):
                        n_have += 1
            add_here += fill(sc, ch, want, rid)

        if add_here:
            per_file[name] = add_here
            n_add += add_here
            if not DRY:
                g44.dump(p, data)

    n_noroom = sum(len(v) for k, v in want.items() if k not in hit_keys)

    print('')
    print('★ 需新增 %d 条 | 已存在 %d 条 | 落在未登记房间 %d 条'
          % (n_add, n_have, n_noroom))
    print('★ 涉及文件 %d 个 / 已扫文件 %d 个 / 经 index 回退补房间号 %d 个场景'
          % (len(per_file), files, n_rid_fallback))
    for name, c in sorted(per_file.items(), key=lambda kv: -kv[1])[:10]:
        print('   %-56s +%d' % (name, c))

    if DRY:
        print('')
        print('（DRY RUN：未写盘。加 --apply 生效）')
        return 0

    print('')
    print('已写回 %d 个文件' % len(per_file))
    return 0


if __name__ == '__main__':
    sys.exit(main())
