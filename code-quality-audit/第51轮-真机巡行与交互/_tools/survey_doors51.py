# -*- coding: utf-8 -*-
"""第51轮探针：全量普查「场景里有没有门 / 落点坐标」。

为什么要普查
------------
用户要的是「实际上的操控 ralsei 去各个场景（**我也能看到的那种**）」。
要实现"走到门 → 换场景"，段内行走的 goal 必须是**门在房间里的坐标**。
`scene_pathfind.plan_from_text()` 只给门**名字**（`obj_doorA`），不给坐标 ——
坐标只能从场景的 `objects` 里按 `src` 反查（`src` 形如 `obj_doorA` /
`obj_markerA`，`pos` 就是房间局部像素坐标）。

所以本脚本回答一个问题：**这份数据齐不齐？**
  齐 → 可以直接实现"逐门执行"；
  不齐 → 先补采（重跑 UTMT），否则"走到门口"只能是猜一个边缘点。

判据纪律（项目记忆 §4）
----------------------
· 先把 **A/B 锚点**打出来（已知真值：`ch1.castle_town.castle_town` 应有
  doorA/B/X + markerA/B/X），锚点不全命中 → 整份统计**作废**，不许用；
· 统计"有"的时候，同时统计"没有"（正/负对照），否则分不清"全都有"和"没扫到"。
"""
import io
import json
import os
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
# ★ scene_system 住在 ralsei_pet/modules/ 且是**扁平导入**（`from scene_system import`），
#   main.py 同样把这两个目录都挂上 sys.path ⇒ 这里必须一致，否则 ModuleNotFoundError。
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))

import scene_system  # noqa: E402  (扁平导入，与 main.py 同源)

OUT_JSON = os.path.join(REPO, 'code-quality-audit', '第51轮-真机巡行与交互',
                        '_evidence', 'doors_survey51.json')
OUT_TXT = os.path.join(REPO, 'code-quality-audit', '第51轮-真机巡行与交互',
                       '_evidence', 'doors_survey51.txt')

lines = []


def w(s=''):
    lines.append(str(s))


def letters_of(src, prefix):
    """`obj_doorA` → 'A'；不是该前缀 → None。"""
    if not isinstance(src, str) or not src.startswith(prefix):
        return None
    tail = src[len(prefix):]
    if not tail:
        return None
    # 门/落点名可能是 doorA / doorA_left / doorAny …
    ch = tail[0]
    return ch if ('A' <= ch <= 'Z' or 'a' <= ch <= 'z') else None


def nodes_of(scene):
    """一个场景里的 door / marker 字母 → 坐标。"""
    doors, markers = {}, {}
    for ob in (getattr(scene, 'objects', None) or ()):
        if not isinstance(ob, dict):
            continue
        src = ob.get('src') or ob.get('id') or ''
        pos = ob.get('pos')
        if not (isinstance(pos, (list, tuple)) and len(pos) >= 2):
            continue
        k = letters_of(src, 'obj_door')
        if k:
            doors.setdefault(k.upper(), (int(pos[0]), int(pos[1])))
            continue
        k = letters_of(src, 'obj_marker')
        if k:
            markers.setdefault(k.upper(), (int(pos[0]), int(pos[1])))
    return doors, markers


def main():
    index = scene_system.load_index()
    scenes = index.get('scenes') or {}
    w('=== 门坐标全量普查（第51轮）===')
    w('索引 ok=%s  场景数=%d  default=%r' % (index.get('ok'), len(scenes),
                                            index.get('default_scene')))

    # ---------- A. 锚点自检（已知真值） ----------
    anchor_id = 'ch1.castle_town.castle_town'
    sc = scene_system.load_scene(anchor_id, entry=scenes.get(anchor_id))
    a_doors, a_markers = nodes_of(sc) if sc is not None else ({}, {})
    w('')
    w('[A] 锚点自检 scene=%s' % anchor_id)
    w('    doors   = %s' % a_doors)
    w('    markers = %s' % a_markers)
    want_doors = {'A', 'B', 'X'}
    want_markers = {'A', 'B', 'X'}
    ok_a = want_doors <= set(a_doors) and want_markers <= set(a_markers)
    w('    期望 doors ⊇ %s / markers ⊇ %s  => %s'
      % (sorted(want_doors), sorted(want_markers), 'PASS' if ok_a else 'FAIL'))
    if not ok_a:
        w('!! 锚点未全命中 => 提取逻辑有问题，整份统计作废（不许用）')
        write_all()
        return 2

    # ---------- B. 负对照（必然没有门的场景） ----------
    neg_id = 'desktop'
    scn = scene_system.load_scene(neg_id, entry=scenes.get(neg_id))
    n_doors, n_markers = nodes_of(scn) if scn is not None else ({}, {})
    w('')
    w('[B] 负对照 scene=%s  doors=%s markers=%s => 期望都为空 => %s'
      % (neg_id, n_doors, n_markers,
         'PASS' if (not n_doors and not n_markers) else 'FAIL'))

    # ---------- C. 全量扫描 ----------
    total = 0
    load_fail = 0
    with_doors = 0
    with_markers = 0
    both = 0
    door_sum = marker_sum = 0
    by_chapter = {}
    rows = {}
    mismatch = []          # 有门无落点 / 有落点无门（字母不配对）
    for sid, entry in sorted(scenes.items()):
        total += 1
        scene = scene_system.load_scene(sid, entry=entry)
        if scene is None:
            load_fail += 1
            continue
        d, m = nodes_of(scene)
        ch = (entry or {}).get('chapter_id') or getattr(scene, 'chapter_id', '?')
        rec = by_chapter.setdefault(ch, {'n': 0, 'doors': 0, 'markers': 0, 'both': 0})
        rec['n'] += 1
        door_sum += len(d)
        marker_sum += len(m)
        if d:
            with_doors += 1
            rec['doors'] += 1
        if m:
            with_markers += 1
            rec['markers'] += 1
        if d and m:
            both += 1
            rec['both'] += 1
        if d or m:
            rows[sid] = {'chapter': ch,
                         'doors': {k: list(v) for k, v in sorted(d.items())},
                         'markers': {k: list(v) for k, v in sorted(m.items())}}
            only_d = sorted(set(d) - set(m))
            only_m = sorted(set(m) - set(d))
            if only_d or only_m:
                mismatch.append({'scene': sid, 'door_only': only_d,
                                 'marker_only': only_m})

    w('')
    w('[C] 全量扫描（场景 %d）' % total)
    w('    加载失败            = %d' % load_fail)
    w('    含 obj_door*        = %d' % with_doors)
    w('    含 obj_marker*      = %d' % with_markers)
    w('    两者都有            = %d  <== "逐门执行"可用的场景数' % both)
    w('    door 实例总数       = %d' % door_sum)
    w('    marker 实例总数     = %d' % marker_sum)
    w('    字母不配对的场景    = %d' % len(mismatch))
    w('')
    w('    分章：')
    for ch in sorted(by_chapter):
        r = by_chapter[ch]
        w('      %-4s 场景 %4d  有门 %4d  有落点 %4d  两者都有 %4d'
          % (ch, r['n'], r['doors'], r['markers'], r['both']))
    if mismatch:
        w('')
        w('    字母不配对样本（前 10）：')
        for m in mismatch[:10]:
            w('      %s  door_only=%s marker_only=%s'
              % (m['scene'], m['door_only'], m['marker_only']))

    payload = {
        'anchor_check': {'scene': anchor_id, 'doors': a_doors, 'markers': a_markers,
                         'pass': ok_a},
        'negative_check': {'scene': neg_id, 'doors': n_doors, 'markers': n_markers},
        'totals': {'scenes': total, 'load_fail': load_fail,
                   'with_doors': with_doors, 'with_markers': with_markers,
                   'both': both, 'door_instances': door_sum,
                   'marker_instances': marker_sum,
                   'letter_mismatch_scenes': len(mismatch)},
        'by_chapter': by_chapter,
        'scenes': rows,
        'mismatch': mismatch[:200],
    }
    with io.open(OUT_JSON, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    write_all()
    return 0


def write_all():
    text = '\n'.join(lines) + '\n'
    with io.open(OUT_TXT, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(text)


if __name__ == '__main__':
    sys.exit(main())
