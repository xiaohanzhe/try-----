# -*- coding: utf-8 -*-
"""第48轮 · 生成 `assets/scenes/_worlds.json`（场景 → 明/暗世界）。

**为什么要这个文件**
    用户口径：「回到光世界的时候暗世界的任何道具都会变成垃圾团里包含的东西」。
    要判"是不是回到光世界"，就必须知道**每个场景属于哪个世界**。
    原作的判据是 `global.darkzone`（第46轮已实证：`0` = 光明世界，`1` = 暗世界），
    但它写在**每个房间的创建代码**里 —— 那正是第42轮 `dump_rooms.csx` 的取证缺口
    （见仓库记忆 §42.6）。所以本轮**不重跑 UTMT**，改用一条**可审计的替代判据**：

    原作房间名（`Data.Rooms` 的 resource 名）本身就是带语义的：
      · 光世界：`room_krisroom` / `room_krishallway` / `room_torroom` / `room_torhouse` /
        `room_torbathroom` / `room_town_*` / `room_beach` / `room_graveyard` /
        `room_hospital_*` / `room_diner` / `room_townhall` / `room_flowershop_*` /
        `room_library` / `room_alphysalley` / `room_torielclass` / `room_schoollobby` /
        `room_alphysclass` / `room_schooldoor` / `room_insidecloset` /
        `room_school_unusedroom` / **`room_lw_*`**（ch2+ 起，`lw` = Light World）
      · 暗世界：`room_dw_*` / `room_dark*` / `room_cc_*` / `room_castle_*` /
        `room_field_*` / `room_forest_*` / `room_board_*` / …

数据源：`code-quality-audit/第38轮-场景系统审查/_evidence/房间表_全量.json`
（第38轮从五章 `data.win` 抄录的**全量**房间表：chapter / room_index / resource / area_id）。

★ 三条纪律
-----------
1. **前缀优先**：先看 `room_dw_` —— 因为女王宅邸里有 `room_dw_mansion_krisroom`
   （假"克里斯的房间"），只看子串会把暗世界房间判成光世界。
2. **不猜**：光世界区域里发现名字带 `dark` 的房间（`room_krisroom_dark` /
   `room_town_krisyard_dark`）⇒ 标 `unknown` 并写明理由，**不硬判**。
   宁可少判几间，也不要让"回到光世界"在错误的时机触发。
3. **正反两面都要验**：既报"光区域里的可疑房间"，也报"暗区域里的可疑房间"，
   两侧都干净才认为判据可用（本项目踩过"判据过窄 ⇒ 误报"和"判据过宽 ⇒ 恒真"两种坑）。

用法（在仓库根跑）::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_tools/gen_worlds48.py"
"""
import collections
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
ROOMTABLE = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查',
                         '_evidence', '房间表_全量.json')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(SCENES, '_worlds.json')

#: ★ 光世界区域（我们自己的 area_id）。这份表由上面"房间名证据"支撑：
#: 这 5 个区域里**没有一间**房间名以 `room_dw_` / `room_dark` / `room_cc_` /
#: `room_field_` / `room_forest_` 开头（生成器会自检并打印）。
LIGHT_AREAS = ('kris_room', 'home', 'hometown', 'light_world', 'noelles_house')

#: ★ 暗世界房间名前缀 —— 命中即判暗，**优先于**区域表（纪律 1）。
DARK_PREFIXES = ('room_dw_', 'room_dark', 'room_cc_', 'room_castle_', 'room_field_',
                 'room_forest_', 'room_board_')

#: 光世界房间名白名单（区域表之外的第二重证据；命中即判光）。
LIGHT_PREFIXES = ('room_krisroom', 'room_krishallway', 'room_torroom', 'room_torhouse',
                  'room_torbathroom', 'room_town_', 'room_beach', 'room_graveyard',
                  'room_hospital_', 'room_diner', 'room_townhall', 'room_flowershop_',
                  'room_library', 'room_alphysalley', 'room_torielclass',
                  'room_schoollobby', 'room_alphysclass', 'room_schooldoor',
                  'room_insidecloset', 'room_school_unusedroom', 'room_lw_')

#: 光世界 = 名字里带这些词的房间**要当心**（`_dark` / `dark_` 后缀是"光世界的夜间变体"
#: 还是"真的暗世界"需要 `global.darkzone` 实证；本轮不猜）。
SUSPECT_IN_LIGHT = ('dark',)

LIGHT, DARK, UNKNOWN = 'light', 'dark', 'unknown'

#: ★ 场景级覆盖（**产品口径**）—— 键 = `scene_id`，值 = 世界。
#: 为什么需要：`desktop`（桌面）是我们自建的前置场景，**不对应任何原作房间**，
#: 房间表里查不到 ⇒ 只能显式指定。口径：桌面 = 现实这一侧（光世界），
#: 桌面上的暗之泉通向暗世界（`ch1.castle_town.castle_town`，原作房间 45 = 暗）。
#: 于是「桌面 ↔ 暗世界」就构成一个用户能亲手走完的循环：
#: 暗世界拿到的道具，回到桌面（光世界）时全部变成垃圾团里的东西。
OVERRIDES = {'desktop': LIGHT}


def classify_room(resource, area_id):
    """`(world, why)` —— 判据顺序：暗前缀 → 光前缀 → 区域表 → unknown。"""
    n = resource or ''
    if not n or n == '---':
        return UNKNOWN, '无房间名'
    for p in DARK_PREFIXES:
        if n.startswith(p):
            return DARK, '房间名以 %s 开头' % p
    for p in LIGHT_PREFIXES:
        if n.startswith(p):
            # ★ 纪律 2：光世界前缀 + 名字里另有 dark ⇒ **不猜**。
            if any(s in n[len(p):] for s in SUSPECT_IN_LIGHT):
                return UNKNOWN, '光世界前缀 %s 但名字含 dark（疑为夜间变体），需 darkzone 实证' % p
            return LIGHT, '房间名以 %s 开头' % p
    if area_id in LIGHT_AREAS:
        if any(s in n for s in SUSPECT_IN_LIGHT):
            return UNKNOWN, '光世界区域 %s 但房名含 dark，需 darkzone 实证' % area_id
        return LIGHT, '属于光世界区域 %s' % area_id
    if area_id:
        return DARK, '属于暗世界区域 %s' % area_id
    return UNKNOWN, '无区域、无可辨房间名'


def main():
    with io.open(ROOMTABLE, 'r', encoding='utf-8') as fh:
        table = json.load(fh)

    worlds = {}          # chapter -> {str(room_id): world}
    reasons = {}         # chapter -> {str(room_id): why}
    area_world = {}      # chapter -> {area: world}
    unknown = []         # [(chapter, room_id, resource, area, why)]
    suspect_dark_side = []   # 暗区域里像光世界的房间（反例检查）
    suspects = []

    for ch in sorted(table.keys()):
        rooms = {}
        why = {}
        for r in table[ch]:
            if r.get('cls') not in ('scene', 'maybe'):
                continue
            rid = r.get('room_index')
            res = r.get('resource') or ''
            area = r.get('area_id')
            w, reason = classify_room(res, area)
            rooms[str(rid)] = w
            why[str(rid)] = reason
            if w == UNKNOWN:
                unknown.append((ch, rid, res, area, reason))
            # 反例检查：判成暗、却在光世界区域 / 或判成光的房间进了 `room_dw_`
            if area in LIGHT_AREAS and w == DARK:
                suspect_dark_side.append((ch, rid, res, area))
            if w == LIGHT and res.startswith('room_dw_'):
                suspects.append((ch, rid, res, area))
        worlds[ch] = rooms
        reasons[ch] = why
        cnt = collections.Counter(rooms.values())
        area_world[ch] = {}
        for r in table[ch]:
            if r.get('cls') not in ('scene', 'maybe'):
                continue
            a = r.get('area_id')
            if not a:
                continue
            area_world[ch].setdefault(a, set()).add(rooms[str(r['room_index'])])
        print('%s: 光=%d 暗=%d 未知=%d' % (ch, cnt[LIGHT], cnt[DARK], cnt[UNKNOWN]))

    # 区域 → 世界（一个区域若混了 world，如实标 mixed）
    area_out = {}
    for ch, m in area_world.items():
        area_out[ch] = {}
        for a, ws in sorted(m.items()):
            known = sorted(w for w in ws if w != UNKNOWN)
            if len(known) == 1 and len(ws) == 1:
                area_out[ch][a] = known[0]
            elif len(known) == 1:
                area_out[ch][a] = known[0]
                print('  ⚠ %s/%s 区域混有未知房间（按 %s 记）' % (ch, a, known[0]))
            else:
                area_out[ch][a] = 'mixed'
                print('  ⚠ %s/%s 区域同时含 %s ⇒ 标 mixed' % (ch, a, known))

    print()
    print('--- 反例检查（两侧都必须为空）')
    print('  光世界区域里判成暗的房间：%d %s' % (len(suspect_dark_side), suspect_dark_side[:5]))
    print('  判成光但房名 room_dw_ ：%d %s' % (len(suspects), suspects[:5]))
    print('--- 未判定（如实登记，接线层不会据此切世界）')
    for u in unknown:
        print('   %s #%-4s %-32s area=%-16s %s' % u)

    sidx = None
    with io.open(os.path.join(SCENES, '_index.json'), 'r', encoding='utf-8') as fh:
        sidx = json.load(fh)
    cover = collections.Counter()
    miss = []
    for ch, crec in (sidx.get('chapters') or {}).items():
        for ak, av in (crec.get('areas') or {}).items():
            for sid, sr in (av.get('scenes') or {}).items():
                if sid in OVERRIDES:
                    cover[OVERRIDES[sid]] += 1
                    continue
                rid = sr.get('original_room_id')
                w = (worlds.get(ch) or {}).get(str(rid))
                if w is None:
                    miss.append((ch, sid, rid))
                else:
                    cover[w] += 1
    print()
    print('--- 覆盖率（%d 个场景）' % sum(cover.values()))
    print('  light=%d dark=%d' % (cover[LIGHT], cover[DARK]))
    print('  未覆盖：%d %s' % (len(miss), miss[:8]))

    out = {
        'schema_version': 1,
        'meta': {
            'why': '场景 → 明/暗世界。用户口径「回到光世界时暗世界道具变垃圾团」需要它。',
            'original_judgement': 'global.darkzone：0=光明世界 / 1=暗世界（第46轮实证）',
            'why_not_darkzone': 'global.darkzone 写在每间房的创建代码里，属第42轮 dump_rooms 的取证缺口；'
                                '本轮改用「原作房间 resource 名」这条可审计替代判据，不猜。',
            'source': 'code-quality-audit/第38轮-场景系统审查/_evidence/房间表_全量.json（五章全量房间表）',
            'rule': '房间名暗前缀优先（防 room_dw_mansion_krisroom 误判）→ 光前缀 → 光区域表 → 否则暗前缀→暗',
            'light_areas': list(LIGHT_AREAS),
            'generator': 'code-quality-audit/第48轮-道具与背包系统/_tools/gen_worlds48.py',
            'overrides_why': 'desktop 是我们自建场景，不对应原作房间；口径见产品记忆 §43.6。',
            'unknown_rooms': [
                {'chapter': c, 'room_id': r, 'resource': n, 'area': a, 'why': wy}
                for (c, r, n, a, wy) in unknown
            ],
        },
        'overrides': dict(OVERRIDES),
        'areas': area_out,
        'rooms': worlds,
    }
    blob = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(blob)
    print()
    print('已写 %s（%d 字节，sha1=%s）' % (
        OUT, len(blob.encode('utf-8')),
        hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
