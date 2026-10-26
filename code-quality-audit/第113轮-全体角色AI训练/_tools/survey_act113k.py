# -*- coding: utf-8 -*-
"""第113轮k · 调研 v2：活动 → 地点的**候选池**（修掉 v1 的三类误报）。

v1 的误报（实测，必须记下来）
----------------------------
1. **`rest` 命中 1438 个** —— 我把 `name_raw`（`room_castle_outskirts`）也算进了
   匹配文本，`room` 是我们的**内部前缀**不是作品里的词 ⇒ 几乎每个场景都中。
   ⇒ 先过 `npc_life.room_word()`（剥 `room_`/`rm_`、下划线转空格）再匹配。
2. **`sparks` 命中 `park`、`graveyard` 命中 `yard`** —— 子串匹配没有词边界。
   ⇒ 英文一律 `\\b...\\b`。
3. **`dw_church_poolsroom` 三活动同时命中** —— `pool` 一个词把泳池房算成"工作"。
   ⇒ 去掉 `pool` / `room` / `class` / `bar` 这类泛词。

★ 这只是**调研**，不是产品代码：它的作用是回答"哪些活动真有候选、候选长什么样"。
"""
import io
import json
import os
import re
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
IDX = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
import npc_life as L                                        # noqa: E402

ACTIVITIES = {
    'eat': {
        'zh': ('餐', '饭', '食', '厨', '咖啡', '茶', '酒馆', '小吃', '面包', '甜点', '食堂',
               '烘焙'),
        'en': ('restaurant', 'diner', 'cafe', 'coffee', 'kitchen', 'bakery',
               'tavern', 'bar', 'dinner', 'lunch', 'breakfast', 'food', 'pizza',
               'burger', 'icecream', 'soda'),
    },
    'rest': {
        'zh': ('床', '卧室', '睡', '休息', '旅店', '旅馆', '客栈', '沙发', '公寓', '宿舍'),
        'en': ('bed', 'bedroom', 'sleep', 'rest', 'inn', 'hotel', 'motel', 'home',
               'house', 'couch', 'lodge', 'cabin', 'dorm', 'apartment'),
    },
    'play': {
        'zh': ('游乐', '公园', '广场', '花园', '庭院', '操场', '游艺', '舞台', '剧场',
               '泳池', '游戏厅'),
        'en': ('park', 'plaza', 'garden', 'yard', 'playground', 'arcade', 'stage',
               'theater', 'theatre', 'amusement', 'carnival'),
    },
    'work': {
        'zh': ('商店', '市场', '工厂', '办公', '图书', '学校', '教室', '医院', '诊所',
               '实验室', '矿', '码头', '车站', '邮局', '银行'),
        'en': ('shop', 'store', 'market', 'factory', 'office', 'library', 'school',
               'hospital', 'clinic', 'lab', 'mine', 'station', 'dock',
               'postoffice', 'bank'),
    },
}


def load():
    idx = json.loads(io.open(IDX, encoding='utf-8').read())
    rows = []
    for cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for scid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                rows.append({
                    'sid': str(scid), 'chapter': cid, 'ch_name': ch_name,
                    'area': area_name,
                    'name': str(sc.get('name') or ''),
                    'raw': str(sc.get('name_raw') or ''),
                    'derived': bool(sc.get('name_derived')),
                })
    return rows


def area_id_of(sid):
    """`ch5.garden.dw_garden_video` → `garden`（sid 的第二段 ＝ 区段名）。"""
    parts = str(sid or '').split('.')
    return parts[1] if len(parts) >= 3 else ''


def core_name(r):
    """这间房**本身**叫什么 —— 必须先把「区段名」从房间名里剥掉。

    ★ 这是 v3 → v4 的关键。`ch5` 整个区 id 是 `garden`，于是该区 **106 间房**
      的 id 全是 `dw_garden_*`；`room_word()` 只剥 `dw_` ⇒ 每间都留着 `garden`
      ⇒ `play` 把整个 ch5 判成"公园"，一条都不落。
      （这就是 `希望之园` 这个区名，它**是区域**，不是"这里每间房都是公园"。）

    剥法：去掉 `dw_/lw_/rm_/room_` 后再看是否以 `<area_id>_` 开头。
      `dw_garden_video`      → `garden_video` → 剥 `garden_` → `video`      ✅ 不算公园
      `dw_castle_restaurant` → `castle_restaurant`，区 id `my_castle_town` ⇒ 不剥 ✅ 仍是餐厅
      `room_tundra_inn`      → `tundra_inn`，区 id `rooms`            ⇒ 不剥 ✅ 仍是旅店
    """
    words = L.room_word(r['raw'])
    aid = area_id_of(r['sid'])
    if aid and words.startswith(aid + ' '):
        words = words[len(aid) + 1:]
    if r['derived'] or not r['name']:
        return words
    return r['name']


def hay_of(r):
    """拆成 **三份独立的匹配文本**，这是 v2 → v3 的修正。

    v2 把「区名 + 场景名 + 房间名」拼成一串去匹配，于是 `ch5` 的区名
    `希望之园` 里那个 `garden` 命中了该区**全部 106 间房**。

    ⇒ 分开：
      · `core` ＝ **强信号**（"这间房本身是什么"）
      · `area` ＝ **弱信号**（"它在哪个区里"，不能单独判定）
    """
    return {
        'area': r['area'].lower(),
        'core': (core_name(r) or '').lower(),
        'raw': L.room_word(r['raw']).lower(),
    }


def hit_words(hay, table):
    """返回 (强命中词, 弱命中词)。强 = 场景名/房间名；弱 = 只有区名。"""
    def scan(text):
        out = []
        for w in table['zh']:
            if w in text:
                out.append(w)
        for w in table['en']:
            if re.search(r'\b%s\b' % re.escape(w), text):
                out.append(w)
        return out

    strong = scan(hay['core'])
    weak = [] if strong else scan(hay['area'])
    return strong, weak


def main():
    rows = load()
    for r in rows:
        r['hay'] = hay_of(r)
    print('场景总数 = %d' % len(rows))

    ok_all = True
    pools = {}
    for act, table in ACTIVITIES.items():
        strong, weak = [], []
        for r in rows:
            s, w = hit_words(r['hay'], table)
            if s:
                strong.append((r, s))
            elif w:
                weak.append((r, w))
        pools[act] = strong
        by_ch = collections.Counter(r['chapter'] for r, _w in strong)
        weak_ch = collections.Counter(r['chapter'] for r, _w in weak)
        print()
        print('===== %-5s 强命中 %d   弱命中(仅区名) %d' % (act, len(strong), len(weak)))
        print('      强分布=%r' % dict(by_ch))
        print('      弱分布=%r' % dict(weak_ch))
        for r, ws in strong[:12]:
            print('    [强][%-9s] %-44s 区=%-10s 名=%-22s 词=%r'
                  % (r['chapter'], r['sid'], r['area'][:10], r['name'][:22], ws))
        for r, ws in weak[:3]:
            print('    [弱][%-9s] %-44s 区=%-10s 名=%-22s 词=%r'
                  % (r['chapter'], r['sid'], r['area'][:10], r['name'][:22], ws))
        if not strong:
            ok_all = False

    print()
    print('===== 交叉：同一场景强命中多个活动 =====')
    multi = []
    for r in rows:
        n = 0
        for act in ACTIVITIES:
            s, _w = hit_words(r['hay'], ACTIVITIES[act])
            if s:
                n += 1
        if n >= 2:
            multi.append((r['sid'], n))
    print('  多命中 %d 个，前 12：' % len(multi))
    for sid, n in multi[:12]:
        print('    %-46s %d' % (sid, n))

    print()
    print('===== 词频：每个活动是被哪些词命中的（看有没有泛词撑数）=====')
    for act, table in ACTIVITIES.items():
        cnt = collections.Counter()
        for r in rows:
            s, _w = hit_words(r['hay'], table)
            for w in s:
                cnt[w] += 1
        print('  %-5s %r' % (act, dict(cnt.most_common())))

    print()
    print('===== 人工验货：每个活动头 5 条，读起来像不像那个地方 =====')
    for act in ACTIVITIES:
        print('  --%s--' % act)
        for r, ws in pools[act][:5]:
            print('     %r  ← %r' % ('%s · %s' % (r['area'], r['name']), ws))

    print()
    print('结论：', '四个活动都有强候选' if ok_all else '**有活动零强候选**')
    return 0 if ok_all else 3


if __name__ == '__main__':
    sys.exit(main())
