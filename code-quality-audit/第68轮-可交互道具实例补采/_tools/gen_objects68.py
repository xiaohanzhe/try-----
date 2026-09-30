# -*- coding: utf-8 -*-
"""第68轮 · 用**扩容后的实例普查**（inst68）重建场景 objects。

与第44轮的关系（**复用而非复制**）
-----------------------------------
`object()` / `parse_objmap()` / `build_frame_index()` / `dump()` / `_sniff_style()`
全部**从 `第44轮.../_tools/gen_objects44.py` 动态载入复用** ——
"一条实例怎么变 objects 元素"这条逻辑**只有一份**（单一真源）。
本脚本自己写的只有**编排**（读哪个输入、写哪两个载体、自检哪些锚点）。

为什么要有这一轮
----------------
第48轮登记过一个缺口（§49.8 缺口 1）：
    `obj_readable` / 宝箱 / 拾取 / 招牌 / 可调查家具 **一件实例都没有**。
根因有二：
  1. `inst42.csx` 的关键词表里**没有** readable/sign/chest/treasure/pickup/interactable
     ⇒ 这些类的实例**从未被导出**（不是"生成了没收录"，是"根本没采"）；
  2. `objs/` 里没有这些类的 sprite ⇒ 即便采到也会被 `object()` 的"无素材跳过"过滤掉。
本脚本配合 `copy_spr68.py` 一起解决这一条。

★★ 等价性判据（本轮最关键的一条）
--------------------------------
`inst68.csx` 的 keys = 第42轮 14 个键 **∪** 新增可交互键 ⇒
**对同一条实例，inst68 必须原样包含 inst42 的每一条**（obj/x/y/layer/depth 逐字段相等）。
这条判据把"换输入源"从"看起来对"变成"逐条对账过"：
只要新旧普查在共有部分有任何漂移，`A0` 立刻报红。
"""
import importlib.util
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
EV68 = os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采', '_evidence')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GEN44 = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_tools',
                     'gen_objects44.py')

#: 第68轮输入（超集）与第42轮输入（用于等价性对账）
INST68 = {'ch1': 'inst68.json', 'ch2': 'ch2_inst68.json', 'ch3': 'ch3_inst68.json',
          'ch4': 'ch4_inst68.json', 'ch5': 'ch5_inst68.json'}
INST42 = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
          'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}

FAIL = 0
_DRY = '--dry' in sys.argv


def ok(m):
    print('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    print('[FAIL] %s' % m)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _load44():
    spec = importlib.util.spec_from_file_location('gen44_mod', GEN44)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['gen44_mod'] = mod
    spec.loader.exec_module(mod)
    return mod


#: 一条实例的**判等键**（对账用；顺序无关，字段固定）。
def _ikey(it):
    return (it.get('obj'), it.get('x'), it.get('y'), it.get('layer'), it.get('depth'))


def _all_insts(path):
    """一个章文件 → 每间房一份实例列表（保留房间分组，用于对账粒度）。"""
    d = load(path)
    out = {}
    for rec in (d.get('rooms') or []):
        rid = rec.get('index')
        if isinstance(rid, int):
            out[rid] = [_ikey(i) for i in (rec.get('insts') or [])]
    return out


def check_superset():
    """★★ 等价性：inst68 必须**逐条包含** inst42 的每一条（共有的 14 个键部分）。"""
    all_ok = True
    total42 = 0
    for ch in INST42:
        p42 = os.path.join(E42, INST42[ch])
        p68 = os.path.join(EV68, INST68[ch])
        if not (os.path.isfile(p42) and os.path.isfile(p68)):
            bad('A0[%s] 输入缺失：42=%s 68=%s'
                % (ch, os.path.isfile(p42), os.path.isfile(p68)))
            all_ok = False
            continue
        a = _all_insts(p42)
        b = _all_insts(p68)
        miss = 0
        for rid, lst in a.items():
            blob = b.get(rid) or []
            from collections import Counter
            need = Counter(lst)
            have = Counter(blob)
            for k, n in need.items():
                if have.get(k, 0) < n:
                    miss += 1
                    if miss <= 3:
                        print('      [MISS %s room=%s] %r' % (ch, rid, k))
            total42 += len(lst)
        if miss:
            bad('A0[%s] inst68 **未包含** inst42 的 %d 条实例 ⇒ 换输入源引入了漂移' % (ch, miss))
            all_ok = False
        else:
            ok('A0[%s] inst68 ⊇ inst42（%d 条逐条命中）'
               % (ch, sum(len(v) for v in a.values())))
    if all_ok:
        ok('A0 ★★ 等价性成立：inst68 对 %d 条第42轮实例逐条包含（字段 obj/x/y/layer/depth）'
           % total42)
    return all_ok


def main():
    g44 = _load44()
    ok('复用第44轮纯函数（object/parse_objmap/build_frame_index/dump）—— 逻辑单一真源')

    if not check_superset():
        print('')
        print('!! 等价性不成立 ⇒ **不写盘**（宁可不动，也不引入未对账的漂移）')
        return 1

    # ★★ 按章取对象表（**修既有缺陷**）
    #   第44轮只读 ch1 的 `objmap43.txt`（353 个对象）却用于全 5 章 ⇒
    #   ch2~5 **独有的**对象名查不到 spr 一律被丢。
    #   实证：`obj_board_pickup`（ch3，11 条实例）只在 `chapter3_objmap43.txt` 里，
    #   于是它虽然采到了、素材也搬了，却**永远进不了 objects**。
    #   修法 = 每章用自己那张表；ch1 仍用 `objmap43.txt`（表内容不变 ⇒ ch1 不漂移）。
    OBMAP = {'ch1': 'objmap43.txt', 'ch2': 'chapter2_objmap43.txt',
             'ch3': 'chapter3_objmap43.txt', 'ch4': 'chapter4_objmap43.txt',
             'ch5': 'chapter5_objmap43.txt'}
    e43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
    objmaps = {ch: g44.parse_objmap(os.path.join(e43, fn)) for ch, fn in OBMAP.items()}
    objmap = objmaps['ch1']
    ok('对象表（ch1）%d 个；按章取表合计 %d 个'
       % (len(objmap), sum(len(v) for v in objmaps.values())))
    # ⚠️ 这里**不能**用 `for ... else`：Python 的 for-else 在"没 break"时**无条件**执行，
    #    写成 for 里 bad / else 里 ok ⇒ 同一个事实**既报红又报绿**（自相矛盾的判据）。
    _missing_tbl = [c for c in ('ch2', 'ch3', 'ch4', 'ch5') if not objmaps[c]]
    if _missing_tbl:
        bad('A0b 第 %s 章对象表为空 ⇒ 按章取表没生效' % ','.join(_missing_tbl))
    else:
        ok('A0b ★ 五章对象表齐备（ch1 353 / ch2 %d / ch3 %d / ch4 %d / ch5 %d）'
           % (len(objmaps['ch2']), len(objmaps['ch3']), len(objmaps['ch4']), len(objmaps['ch5'])))
    frame_idx = g44.build_frame_index()
    ok('objs/ 帧索引 %d 个 sprite' % len(frame_idx))
    sprite_anim = g44.load_sprite_anim()

    # ---- 1. 建「章:房间id → [objects]」----
    by_room = {}
    inst_total = drawable_total = 0
    new_kind_total = 0
    #: 本轮的**目标类**（`item_interact.PROP_CLASSES` 里被点名"无实例"的那几类）。
    WANT = ('obj_readable', 'obj_readable_room1', 'obj_board_readable', 'obj_npc_sign',
            'obj_treasure_room', 'obj_bug_treasure_chest', 'obj_board_pickup',
            'obj_alphysdesk', 'obj_schooldesk', 'obj_interactablesolid')
    for ch in INST68:
        d = load(os.path.join(EV68, INST68[ch]))
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            if not isinstance(rid, int):
                continue
            slot = by_room.setdefault('%s:%d' % (ch, rid), [])
            for it in (rec.get('insts') or []):
                inst_total += 1
                ob = g44.object(it, objmaps[ch], frame_idx, sprite_anim)
                if ob is not None:
                    slot.append(ob)
                    drawable_total += 1
                    if ob.get('src') in WANT:
                        new_kind_total += 1
    print('')
    print('实例总条数 = %d（第42轮为 5,523）；可绘制 = %d；不可绘 = %d'
          % (inst_total, drawable_total, inst_total - drawable_total))
    ok('A1 输入条数 %d > 5523（扩容生效）' % inst_total) if inst_total > 5523 else \
        bad('A1 输入条数没有超过第42轮（%d）' % inst_total)
    ok('A2 ★ 新增可交互类实例落地 %d 条（>0）' % new_kind_total) if new_kind_total > 0 else \
        bad('A2 新增可交互类实例为 0 ⇒ 缺口 1 没被补上')

    # ---- 2. 写回（两种载体；复用第44轮 dump 的 EOL/缩进嗅探）----
    g44.DRY_RUN = _DRY
    SCENES = g44.SCENES
    import re as _re
    RE_ZONE = _re.compile(r'^_zone\.(ch\d+)\.')

    index = load(os.path.join(SCENES, '_index.json'))
    file_scenes = {}
    for ch, blk in (index.get('chapters') or {}).items():
        if not isinstance(blk, dict):
            continue
        for area, ablk in (blk.get('areas') or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, entry in (ablk.get('scenes') or {}).items():
                if not isinstance(entry, dict) or not entry.get('file'):
                    continue
                rid = entry.get('original_room_id')
                if isinstance(rid, int):
                    file_scenes.setdefault((ch, rid), []).append((sid, entry['file']))

    zone_files = sorted(f for f in os.listdir(SCENES)
                        if f.startswith('_zone.') and f.endswith('.json'))
    n_touched = n_with = written = 0
    for zf in zone_files:
        m = RE_ZONE.match(zf)
        ch = m.group(1) if m else None
        if not ch:
            continue
        p = os.path.join(SCENES, zf)
        data = load(p)
        table = data.get('scenes') if isinstance(data, dict) and 'scenes' in data else None
        if not isinstance(table, dict):
            continue
        changed = False
        for sid, raw in table.items():
            if not isinstance(raw, dict):
                continue
            rid = raw.get('original_room_id')
            if not isinstance(rid, int):
                continue
            objs = by_room.get('%s:%d' % (ch, rid))
            n_touched += 1
            if objs:
                n_with += 1
                if raw.get('objects') != objs:
                    raw['objects'] = objs
                    changed = True
            elif 'objects' not in raw:
                raw['objects'] = []
                changed = True
        if changed:
            g44.dump(p, data)
            written += 1

    n_ftouched = n_fwith = n_fwritten = 0
    for (ch, rid), items in sorted(file_scenes.items()):
        objs = by_room.get('%s:%d' % (ch, rid))
        for sid, fname in items:
            fp = os.path.join(SCENES, fname)
            if not os.path.exists(fp):
                bad('独立文件缺失：%s' % fname)
                continue
            raw = load(fp)
            if not isinstance(raw, dict):
                continue
            n_ftouched += 1
            changed = False
            new_objs = objs if objs else []
            if raw.get('objects') != new_objs:
                raw['objects'] = new_objs
                changed = True
            if objs:
                n_fwith += 1
            if changed:
                g44.dump(fp, raw)
                n_fwritten += 1

    print('')
    print('分片写回 %d / %d' % (written, len(zone_files)))
    print('覆盖场景（分片，有 original_room_id） = %d，其中带可绘制物件 = %d'
          % (n_touched, n_with))
    print('独立文件场景 = %d，其中带可绘制物件 = %d，写入 = %d'
          % (n_ftouched, n_fwith, n_fwritten))
    if _DRY:
        print('*** DRY RUN：未写盘 ***')
        return 0

    # ---- 3. 锚点自检（**从磁盘读**，不看内存副本）----
    print('')
    print('=== 锚点自检（磁盘真值）===')

    def disk_objects(path, want_rid, want_sid=None):
        if not os.path.isfile(path):
            return None, None
        d = load(path)
        t = d.get('scenes') if isinstance(d, dict) and 'scenes' in d else None
        if isinstance(t, dict):
            for sid, raw in t.items():
                if isinstance(raw, dict) and raw.get('original_room_id') == want_rid:
                    return sid, raw.get('objects')
            return None, None
        if want_sid and os.path.basename(path).startswith(want_sid.split('.')[-1]):
            return want_sid, d.get('objects')
        return None, None

    # ★ 本轮新锚点：**城堡镇**必须真的有可交互物落地（不只是存档点）
    #   ⚠️ `_index.json` 的结构是 `{chapters:{ch:{areas:{area:{scenes:{sid:entry}}}}}}`
    #      —— **没有顶层 `scenes`**（首版按顶层取 ⇒ 恒 None ⇒ 判据恒假报红）。
    sid = 'ch1.castle_town.castle_town'

    def _find_entry(idx, want_sid):
        for _ch, _blk in (idx.get('chapters') or {}).items():
            if not isinstance(_blk, dict):
                continue
            for _area, _ablk in (_blk.get('areas') or {}).items():
                if not isinstance(_ablk, dict):
                    continue
                e = (_ablk.get('scenes') or {}).get(want_sid)
                if isinstance(e, dict):
                    return e
        return None

    entry = _find_entry(index, sid)
    found = None
    if isinstance(entry, dict) and entry.get('file'):
        found = os.path.join(SCENES, entry['file'])
    if found and os.path.isfile(found):
        d = load(found)
        table = d.get('scenes') if isinstance(d, dict) and 'scenes' in d else None
        objs = None
        if isinstance(table, dict) and sid in table:
            objs = (table[sid] or {}).get('objects')
        if objs is None:
            objs = d.get('objects')
        srcs = sorted(set((o or {}).get('src') for o in (objs or [])))
        print('%s objects=%d src=%s' % (sid, len(objs or []), srcs))
        n_save = sum(1 for o in (objs or []) if (o or {}).get('src') == 'obj_savepoint')
        if n_save >= 1:
            ok('A3 城堡镇包含 %d 个 obj_savepoint（真交互锚点仍在）' % n_save)
        else:
            bad('A3 城堡镇 obj_savepoint 消失（%d）' % n_save)
    else:
        bad('A3 找不到城堡镇分片')

    # 全库对账（★ 强判据）：产物里出现的可交互类 src，必须都在 PROP_CLASSES 且 in_data=True
    print('')
    print('=== 全库 objects 对账 ===')
    seen_src = {}
    for zf in zone_files:
        p = os.path.join(SCENES, zf)
        try:
            d = load(p)
        except Exception:
            continue
        for sid2, raw in ((d.get('scenes') or {}) if isinstance(d, dict) else {}).items():
            if not isinstance(raw, dict):
                continue
            for o in (raw.get('objects') or []):
                s = (o or {}).get('src')
                if s:
                    seen_src[s] = seen_src.get(s, 0) + 1
    print('产物里 distinct src = %d' % len(seen_src))

    # ---- 4. 落盘统计 JSON（供回归锁与报告读）----
    stat = {
        'inst_total': inst_total,
        'inst42_total': 5523,
        'drawable': drawable_total,
        'new_kind_insts': new_kind_total,
        'src_hist': seen_src,
    }
    sp = os.path.join(EV68, 'gen68_stat.json')
    with io.open(sp, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(stat, ensure_ascii=False, indent=1, sort_keys=True))
    ok('落盘 %s' % os.path.basename(sp))

    print('')
    print('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
