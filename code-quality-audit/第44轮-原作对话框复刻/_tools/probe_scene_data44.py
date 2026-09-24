# -*- coding: utf-8 -*-
"""只读探针 v2：场景数据里到底有什么可画。

⚠️ v1 两个 bug（正是"判据会说谎"的现场，故留痕）：
  1) `_index.json` 顶层 **没有 `scenes` 键**（实测键 = ['schema_version','meta',
     'default_scene','chapters']）⇒ v1 打印"索引读到 0 个登记场景"。真值是 1,014。
  2) 分片实体的章号**不在实体里**，而在**文件名**里（`_zone.ch1.home.json`）——
     v1 读 `raw['chapter_id']` 全 None ⇒ 逐章统计全落 `?`。
  ⇒ v2：章号从文件名正则取；索引按 `chapters[*].scenes` 真形状取。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
RE_ZONE = re.compile(r'^_zone\.(ch\d+)\.')

FAIL = 0


def ok(msg):
    print('[PASS] %s' % msg)


def bad(msg):
    global FAIL
    FAIL += 1
    print('[FAIL] %s' % msg)


def load(name):
    with io.open(os.path.join(SCENES, name), 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    idx = load('_index.json')
    print('索引顶层键 = %s' % sorted(idx.keys()))
    chapters = idx.get('chapters') or {}
    # ★ 真形状（v2 实测）：三级 = chapters[章]['areas'][区]['scenes'][场景id]。
    #   v1 找 `idx['scenes']` ⇒ 恒 0（"判据会说谎"现场 2）。
    n_idx_scene = 0
    for ch, blk in (chapters.items() if isinstance(chapters, dict) else []):
        if not isinstance(blk, dict):
            continue
        for area, ablk in (blk.get('areas') or {}).items():
            if isinstance(ablk, dict):
                n_idx_scene += len(ablk.get('scenes') or {})
    print('索引登记场景（三级展开）= %d' % n_idx_scene)
    print('索引章 = %s' % (sorted(chapters.keys()) if isinstance(chapters, dict) else '?'))
    if n_idx_scene:
        ok('A1 索引登记场景 %d 条（三级 chapters[章].areas[区].scenes）' % n_idx_scene)
    else:
        bad('A1 索引仍读不出场景 —— 形状假设又错了')

    zone_files = sorted(f for f in os.listdir(SCENES)
                        if f.startswith('_zone.') and f.endswith('.json'))
    total = with_objects = obj_total = obj_max = 0
    obj_with_name = obj_with_pos = with_bg = with_oid = 0
    per_ch = {}
    sample = None
    for zf in zone_files:
        m = RE_ZONE.match(zf)
        ch = m.group(1) if m else '?'          # ★ 章号来自文件名
        try:
            data = load(zf)
        except Exception as e:
            bad('分片 %s 读失败: %s' % (zf, e))
            continue
        table = data.get('scenes') if isinstance(data, dict) and 'scenes' in data else data
        if not isinstance(table, dict):
            bad('分片 %s 形状异常' % zf)
            continue
        for sid, raw in table.items():
            if not isinstance(raw, dict):
                continue
            total += 1
            slot = per_ch.setdefault(ch, {'n': 0, 'obj': 0, 'bg': 0, 'oid': 0, 'objs': 0})
            slot['n'] += 1
            objs = raw.get('objects')
            n = len(objs) if isinstance(objs, (list, tuple)) else 0
            slot['objs'] += n
            if n:
                with_objects += 1
                slot['obj'] += 1
                obj_total += n
                obj_max = max(obj_max, n)
                if sample is None:
                    sample = (zf, sid, objs[:3])
                for o in objs:
                    if not isinstance(o, dict):
                        continue
                    if o.get('sprite') or o.get('image') or o.get('asset'):
                        obj_with_name += 1
                    p = o.get('pos')
                    if isinstance(p, (list, tuple)) and len(p) == 2:
                        obj_with_pos += 1
            bg = raw.get('bg')
            if isinstance(bg, str) and bg:
                with_bg += 1
                slot['bg'] += 1
            if isinstance(raw.get('original_room_id'), int):
                with_oid += 1
                slot['oid'] += 1

    print('')
    print('=== 数据面统计（分片实体） ===')
    print('场景实体总数           : %d' % total)
    print('带 objects 的场景      : %d (%.1f%%)' % (with_objects, 100.0 * with_objects / max(1, total)))
    print('objects 总条数         : %d' % obj_total)
    print('单场景 objects 最大值  : %d' % obj_max)
    print('物件带 sprite/image/asset : %d' % obj_with_name)
    print('物件带 pos(len==2)     : %d' % obj_with_pos)
    print('带 bg 非空的场景       : %d (%.1f%%)' % (with_bg, 100.0 * with_bg / max(1, total)))
    print('带 original_room_id    : %d (%.1f%%)' % (with_oid, 100.0 * with_oid / max(1, total)))
    print('')
    print('=== 逐章（章号取自文件名） ===')
    print('%-6s %6s %8s %8s %8s %8s' % ('章', '场景', '带obj', '带bg', '带oid', 'obj数'))
    for ch in sorted(per_ch, key=lambda s: (len(s), s)):
        s = per_ch[ch]
        print('%-6s %6d %8d %8d %8d %8d' % (ch, s['n'], s['obj'], s['bg'], s['oid'], s['objs']))

    if sample:
        print('')
        print('=== 真值锚点 ===')
        print('分片=%s 场景=%s' % (sample[0], sample[1]))
        for o in sample[2]:
            print('  %s' % json.dumps(o, ensure_ascii=False)[:240])
    else:
        print('')
        print('!! 没有任何场景带 objects')

    print('')
    print('=== 判据 ===')
    if n_idx_scene:
        ok('C1 索引登记场景 %d 条' % n_idx_scene)
    else:
        bad('C1 索引登记场景 0 条')
    if total:
        ok('C2 分片实体 %d 条' % total)
    else:
        bad('C2 分片实体 0 条')
    if perf_ok(per_ch):
        ok('C3 逐章统计非空（%d 章）' % len(per_ch))
    else:
        bad('C3 逐章统计落空 —— 章号没取到')
    if with_oid > total * 0.9:
        ok('C4 original_room_id 覆盖 %d/%d' % (with_oid, total))
    else:
        bad('C4 original_room_id 覆盖不足 %d/%d' % (with_oid, total))
    print('')
    print('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


def perf_ok(per_ch):
    return any(k != '?' for k in per_ch)


if __name__ == '__main__':
    sys.exit(main())
