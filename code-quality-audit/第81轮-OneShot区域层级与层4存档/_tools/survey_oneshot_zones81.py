# -*- coding: utf-8 -*-
"""第81轮 · OneShot 官方区域事实源勘查（只读）。

目的：为 `oneshot` 章节的**区域层级**取证，替代第80轮的「单区域 rooms + 待补」。
依据（全部来自原作明文，零猜测，三源互证）：
  ① gamedata/oneshot_map_colors.json  —— mapColors[]：{name, color{r,g,b,a}, maps[]}
  ② gamedata/oneshot_map_zone_names.json —— {"Blue":"The Barrens", ...}
  ③ gamedata/oneshot_minimap_nodes.json —— {zones:{Blue:{<mapid>:[{id,direction}...]}}}
  ④ gamedata/oneshot_map_names.json —— {map_names:[{id,name}...]} 263 条
  ⑤ loc/<lang>/map_zone_name_strs.po —— 官方区域名本地化（如 zh_cn: 荒野/幽谷/城市/城市（地表区））

★ 源盘缺失时**不 FAIL**：打印 SKIP 并返回空（回归套件不许依赖外部盘）。
★ 全部 JSON 均为「RPG Maker MV 风格带尾逗号」的 JS 字面量 ⇒ 必须用 _strip_trailing_commas。
  该解析器在 `_probe`/本脚本的 selfcheck() 里过 A/B 锚点（standard json 零改写 + 正负控制）。

产物：_evidence/oneshot_zones81.json
用法：C:\\Python311\\python.exe extract_oneshot_zones81.py [--src <OneShot 根>]
"""
import json
import os
import re
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.join(HERE, '..')
EVID = os.path.join(ROUND, '_evidence')

DEFAULT_SRC = r"C:\Users\23002\Desktop\项目文件夹\niko的秘密\OneShot.World.Machine.Edition.Build.16512634"

#: 官方四区（minimap_nodes 的键，与 zone_names 的键逐字一致 —— 双源互证）
ZONE_KEYS = ('Blue', 'Green', 'Red', 'RedGround')

#: 官方中文区域名（loc/zh_cn/map_zone_name_strs.po 实录，非翻译）
ZONE_ZH = {
    'Blue': '荒野',
    'Green': '幽谷',
    'Red': '城市',
    'RedGround': '城市（地表区）',
}
#: 官方英文区域名（oneshot_map_zone_names.json 实录）
ZONE_EN = {
    'Blue': 'The Barrens',
    'Green': 'The Glen',
    'Red': 'The Refuge',
    'RedGround': 'The Refuge (Surface)',
}
#: 第五区：官方**未命名**（map_colors.purple 组，与 minimap 四区零交集）
MAINLINE_KEY = 'Purple'
MAINLINE_ZH = '主线 · 家/塔/终局'
#: 兜底：既不在 minimap 四区、也不在 map_colors 的房（名字自带 IGNORE/UNUSED/demo 证据）
UNZONED_KEY = 'UNZONED'
UNZONED_ZH = '未分区（废弃/调试/演示）'


# ---------------------------------------------------------------- 容错 JSON
def _strip_trailing_commas(s):
    """剥除 true-JSON 非法的尾逗号；**仅**在字符串外部生效。

    与 E:\\Download\\_tmp 的探针同源实现；锚点见 selfcheck()。
    """
    out = []
    i, n = 0, len(s)
    instr = False
    esc = False
    while i < n:
        ch = s[i]
        if instr:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                instr = False
            i += 1
            continue
        if ch == '"':
            instr = True
            out.append(ch)
            i += 1
            continue
        if ch == ',':
            j = i + 1
            while j < n and s[j] in ' \t\r\n':
                j += 1
            if j < n and s[j] in '}]':
                i += 1
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def load_js_json(path):
    """读 RPG Maker MV 风格的 JS 字面量 JSON。"""
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.loads(_strip_trailing_commas(f.read()))


# ---------------------------------------------------------------- 锚点
def selfcheck(src):
    """A/B 锚点：这步不过 ⇒ 后续所有结论作废。返回 (ok, notes)。"""
    notes = []
    ok = True
    g = os.path.join(src, 'gamedata')

    # A1 标准 JSON 经容错器后必须与原解析**完全一致**（不许改坏好数据）
    std_files = ['oneshot_map_names.json', 'oneshot_minimap_info.json',
                 'oneshot_tilesets.json', 'oneshot_items.json',
                 'oneshot_flag_names.json', 'oneshot_var_names.json',
                 'oneshot_common_events.json']
    for fn in std_files:
        p = os.path.join(g, fn)
        if not os.path.exists(p):
            notes.append('A1 %s : MISSING' % fn)
            ok = False
            continue
        with open(p, 'r', encoding='utf-8-sig') as fh:
            strict = json.load(fh)
        tolerant = load_js_json(p)
        same = (strict == tolerant)
        ok &= same
        notes.append('A1 %-32s strict==tolerant : %s' % (fn, same))

    # A2 已知真值：map_names 恰 263 条且 id == 1..263
    mn = load_js_json(os.path.join(g, 'oneshot_map_names.json'))['map_names']
    ids = sorted(int(x['id']) for x in mn)
    a2 = (len(mn) == 263 and ids == list(range(1, 264)))
    ok &= a2
    notes.append('A2 map_names 恰 263 条且 id==1..263 : %s' % a2)

    # A3 负控制：串内逗号 + 串内括号不许被动
    neg_src = '{"a":[1,2,3],"b":"x,y}","c":{}}'
    neg_exp = {"a": [1, 2, 3], "b": "x,y}", "c": {}}
    a3 = (json.loads(_strip_trailing_commas(neg_src)) == neg_exp)
    ok &= a3
    notes.append('A3 负控制（串内逗号/括号不许动）: %s' % a3)

    # A4 正控制：尾逗号必须被剥
    pos_src = '{"a":[1,2,3,],"b":1,}'
    a4 = (json.loads(_strip_trailing_commas(pos_src)) == {"a": [1, 2, 3], "b": 1})
    ok &= a4
    notes.append('A4 正控制（尾逗号必被剥）: %s' % a4)

    # A5 三源互证的关键锚点：minimap_nodes 的 zone 键 == zone_names 的键
    zn = set(load_js_json(os.path.join(g, 'oneshot_map_zone_names.json')).keys())
    nd = set(load_js_json(os.path.join(g, 'oneshot_minimap_nodes.json'))['zones'].keys())
    a5 = (zn == nd) and (nd == set(ZONE_KEYS))
    ok &= a5
    notes.append('A5 minimap zone 键 == zone_names 键 == %s : %s' % (list(ZONE_KEYS), a5))

    return ok, notes


# ---------------------------------------------------------------- 主勘查
def survey(src):
    g = os.path.join(src, 'gamedata')
    do = os.path.join(g, 'loc', 'zh_cn', 'map_zone_name_strs.po')

    mn = {int(x['id']): x['name']
          for x in load_js_json(os.path.join(g, 'oneshot_map_names.json'))['map_names']}
    colors = {x['name']: set(int(v) for v in (x.get('maps') or []))
              for x in load_js_json(os.path.join(g, 'oneshot_map_colors.json'))['mapColors']}
    zone_en = load_js_json(os.path.join(g, 'oneshot_map_zone_names.json'))
    nodes = load_js_json(os.path.join(g, 'oneshot_minimap_nodes.json'))['zones']
    node_ids = {z: set(int(k) for k in d.keys()) for z, d in nodes.items()}

    # 官方中文（po 实录）
    zone_zh = dict(ZONE_ZH)
    if os.path.exists(do):
        txt = open(do, 'r', encoding='utf-8-sig', errors='replace').read()
        got = dict(re.findall(r'msgid\s+"([^"]+)"\s*\nmsgstr\s+"([^"]*)"', txt))
        for k, v in ZONE_EN.items():
            hit = got.get('%s=%s' % (k, v))
            if hit:
                zone_zh[k] = hit

    # 分区：minimap 四区（最权威，官方邻接图）> map_colors > unzoned
    def assign(mid):
        for z in ('RedGround', 'Blue', 'Green', 'Red'):
            if mid in node_ids[z]:
                return z
        for z, key in (('Red', 'red'), ('Green', 'green'), ('Blue', 'blue'),
                       (MAINLINE_KEY, 'purple')):
            if mid in colors.get(key, set()):
                return z
        return UNZONED_KEY

    buckets = collections.OrderedDict()
    for z in list(ZONE_KEYS) + [MAINLINE_KEY, UNZONED_KEY]:
        buckets[z] = []
    for mid in sorted(mn):
        buckets[assign(mid)].append(mid)

    # 无歧义校验：两两零交集 + 全覆盖
    zones = list(buckets.keys())
    overlaps = []
    for i in range(len(zones)):
        for j in range(i + 1, len(zones)):
            s = set(buckets[zones[i]]) & set(buckets[zones[j]])
            if s:
                overlaps.append([zones[i], zones[j], sorted(s)])
    covered = sum(len(v) for v in buckets.values())

    return {
        'schema': 1,
        'source': src,
        'authority': [
            'gamedata/oneshot_map_colors.json (mapColors[] -> maps[])',
            'gamedata/oneshot_map_zone_names.json',
            'gamedata/oneshot_minimap_nodes.json (zones -> 邻接图)',
            'gamedata/oneshot_map_names.json (263)',
            'gamedata/loc/zh_cn/map_zone_name_strs.po',
        ],
        'zone_names_en': zone_en,
        'zone_names_zh': zone_zh,
        'mainline_key': MAINLINE_KEY,
        'mainline_zh': MAINLINE_ZH,
        'unzoned_key': UNZONED_KEY,
        'unzoned_zh': UNZONED_ZH,
        'counts': {k: len(v) for k, v in buckets.items()},
        'covered_total': covered,
        'expected_total': len(mn),
        'overlaps': overlaps,
        'members': {k: v for k, v in buckets.items()},
        # RedGround 是 Red 的**子集**（地表区特化），如实登记
        'redground_subset_of_red': sorted(set(buckets['RedGround']) - set(buckets['Red'])),
        'note': ('★ 官方只有 4 个**命名**区域（Blue/Green/Red/RedGround）；'
                 'map_colors.purple 组（69 间：家/塔/终局/调试）官方**未命名**，'
                 '本勘查如实登记为第五区「主线」。'
                 '★ OneShot 房数据中**没有** light/dark 维度 ⇒ 明暗表**不可从房数据推断**。'),
    }


def main():
    src = DEFAULT_SRC
    if '--src' in sys.argv:
        src = sys.argv[sys.argv.index('--src') + 1]
    if not os.path.isdir(src):
        print('[SKIP] OneShot 源盘不在：%s' % src)
        print('[SKIP] 现场不动，仓库内已蒸馏的事实见 _evidence/oneshot_zones81.json')
        return 0

    ok, notes = selfcheck(src)
    for n in notes:
        print('      ' + n)
    if not ok:
        print('[FAIL] 锚点未全命中 ⇒ 拒绝产出结论')
        return 1

    data = survey(src)
    print('[OK] 分区计数：%s' % data['counts'])
    print('[OK] 覆盖 %d / %d，交集 %s'
          % (data['covered_total'], data['expected_total'],
             data['overlaps'] if data['overlaps'] else '无 ✔'))

    os.makedirs(EVID, exist_ok=True)
    out = os.path.join(EVID, 'oneshot_zones81.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('[OK] 已写 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
