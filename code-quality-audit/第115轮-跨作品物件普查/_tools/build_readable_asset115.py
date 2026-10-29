# -*- coding: utf-8 -*-
u"""第117轮：把「(房间, 对象) → 文本键 → 正文」做成产品侧数据资产。

数据来源全部在仓库内：
  code-quality-audit/第115轮-跨作品物件普查/_evidence/raw/<game>/readable_bind.tsv
      —— `Alarm_0` 里 `if (room == N)` 抽出来的 (房间下标, 对象) → 键
  code-quality-audit/第115轮-跨作品物件普查/_evidence/raw/<game>/inst_full.tsv
      —— 房间下标 → 房间名，以及"这间房真的摆了哪些可读物"
  code-quality-audit/第115轮-跨作品物件普查/_evidence/readables115.json
      —— 键 → 正文（cn / cn_tight / en / ja），来源是 gml_Script_textdata_*
  ralsei_pet/assets/scenes/_zone.<game>*.json
      —— original_room_id → 产品的 scene_id

产出：ralsei_pet/assets/scenes/_readable_text.json

★ 三条纪律：
  1. **只写"这间房真的摆了该可读物"的组合**（拿 inst_full 当分母），不把 411 条
     没被任何房间用到的预置槽也塞进来 —— 那会让资产看着很大、实际一半没处用。
  2. **解不出来的如实列在 `unresolved` 里**，不猜、不用空串顶。
  3. 标记（`%` `&` `/` `^1` `^2`）**原样保留**，`markers_raw: true` 写清楚；
     渲染规则没定之前，谁都不许在数据层偷偷替换。
"""
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
AUDIT = os.path.join(ROOT, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(AUDIT, 'raw')
PET = os.path.join(ROOT, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
OUT = os.path.join(SCENES, '_readable_text.json')

GAMES = ('ut', 'outertale', 'uty')


def read_lines(p):
    with io.open(p, encoding='utf-8', errors='replace', newline='') as f:
        return f.read().splitlines()


def load_zone_ids(game):
    """original_room_id → scene_id（按 original_room_id，不按房间名：outertale 名字被改过）"""
    by_oid = {}
    dup = 0
    for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % game))):
        try:
            d = json.loads(io.open(p, encoding='utf-8').read())
        except Exception as e:
            print('  !! %s 读不了: %s' % (os.path.basename(p), e))
            continue
        for sid, s in (d.get('scenes') or {}).items():
            oid = s.get('original_room_id')
            if not isinstance(oid, int):
                continue
            if oid in by_oid:
                dup += 1
                continue
            by_oid[oid] = sid
    return by_oid, dup


def load_inst_pairs(game):
    """(房间下标, 对象名) → 实例数（只统计可读物）"""
    p = os.path.join(RAW, game, 'inst_full.tsv')
    if not os.path.isfile(p):
        return None
    cnt = collections.Counter()
    cur = None
    for ln in read_lines(p):
        c = ln.split('\t')
        if not c:
            continue
        if c[0] == 'R' and len(c) >= 2:
            try:
                cur = int(c[1])
            except ValueError:
                cur = None
        elif c[0] == 'I' and len(c) >= 2 and cur is not None and 'readable' in c[1]:
            cnt[(cur, c[1])] += 1
    return cnt


def load_bind(game):
    p = os.path.join(RAW, game, 'readable_bind.tsv')
    if not os.path.isfile(p):
        return None
    out = collections.defaultdict(list)
    for i, ln in enumerate(read_lines(p)):
        if i == 0 or not ln.strip():
            continue
        c = ln.split('\t')
        if len(c) != 4:
            continue
        ri = int(c[2])
        if ri < 0:
            continue
        out[(ri, c[1])].append(c[3])
    return out


def main():
    texts = json.loads(io.open(os.path.join(AUDIT, 'readables115.json'),
                                encoding='utf-8').read())

    doc = {
        'schema_version': 1,
        'note': (u'可读物的正文：键由「房间」决定（原作 obj_readable_*_Alarm_0 里 '
                 u'if (room == N) 选键），不是按实例坐标。'
                 u'本文件只收录"该房间真的摆了该可读物"的组合。'),
        'markers_raw': True,
        'markers_note': (u'正文里的 % & / ^1 ^2 是原作控制符（换页/换行/按键停顿），'
                         u'**未解码**，原样保留；渲染规则定下来之前不许在数据层替换。'),
        'games': {},
    }

    total_entries = 0
    for g in GAMES:
        by_oid, dup = load_zone_ids(g)
        inst = load_inst_pairs(g)
        bind = load_bind(g)
        info = {'scenes_with_oid': len(by_oid), 'dup_oid': dup}
        if inst is None or bind is None:
            info.update({'status': 'NO_DATA', 'entries': 0})
            doc['games'][g] = info
            print('[%s] 无原始数据（跳过，不写空对象）' % g)
            continue

        keys = texts.get(g, {}).get('keys') or {}
        by_scene = collections.defaultdict(list)
        unresolved = []
        no_scene = 0
        no_text = 0

        for (ri, obj), n in sorted(inst.items()):
            ks = bind.get((ri, obj))
            sid = by_oid.get(ri)
            if not ks:
                # 解不出来：如实登记（带房间名，方便以后补）
                unresolved.append({'room_idx': ri, 'scene': sid, 'obj': obj,
                                   'n': n, 'why': 'no_room_guard'})
                continue
            if not sid:
                no_scene += 1
                continue
            for k in ks:
                t = keys.get(k)
                if not t:
                    no_text += 1
                    continue
                if not (t.get('cn') or t.get('cn_tight') or t.get('en')):
                    no_text += 1
                    continue
                by_scene[sid].append({
                    'obj': obj,
                    'key': k,
                    'cn': t.get('cn'),
                    'cn_tight': t.get('cn_tight'),
                    'en': t.get('en'),
                    'ja': t.get('ja'),
                    'instances': n,
                })

        for sid in by_scene:
            by_scene[sid].sort(key=lambda e: (e['obj'], e['key']))

        n_slots = sum(len(v) for v in by_scene.values())
        total_entries += n_slots
        info.update({
            'status': 'OK',
            'scenes_with_oid': len(by_oid),
            'scenes_out': len(by_scene),
            'entries': n_slots,
            'unresolved': len(unresolved),
            'rooms_without_scene': no_scene,
            'keys_without_text': no_text,
            'unresolved_list': unresolved,
        })
        doc['games'][g] = info
        doc.setdefault('by_scene', {}).update(by_scene)
        print('[%s] 场景 %d / 可读物组合 %d → 输出 %d 条（%d 个场景）；未解 %d，缺场景 %d，缺正文 %d'
              % (g, len(by_oid), len(inst), n_slots, len(by_scene),
                 len(unresolved), no_scene, no_text))
        if dup:
            print('     注意：有 %d 个 original_room_id 撞了多个场景（只取第一个）' % dup)

    if not total_entries:
        print('')
        print('[FAIL] 一条都没生成 —— 分母为空，本脚本什么也没证明')
        return 1

    os.makedirs(SCENES, exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True))
    print('')
    print('[PASS] 写出 %s（%d 条 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT), total_entries,
             os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
