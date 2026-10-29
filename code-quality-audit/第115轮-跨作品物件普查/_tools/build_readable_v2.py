# -*- coding: utf-8 -*-
u"""第119轮 · 重建 `assets/scenes/_readable_text.json`（v2：带**守卫等级**）

## 为什么换数据源

v1（第117轮）的键来自**指令流**：`PushBltn room` 后面紧跟的 `PushI` 当作房间守卫。
这个做法有个静默缺陷 —— `pending` 只被**下一个字符串 push** 消费一次，同一个
`if (room == X)` 块里的第 2、3… 个键拿不到房间，被记成 `-1` 后跳过。
`audit119.py` 实测：**ut 少 105 组、outertale 少 78 组**候选键（污染 0 组）。

v2 改用第118轮的 **GML 原文解析**（`conds118.py`，与指令流交叉校验过：交集 203、
仅在指令流侧 0），并把每条候选标上守卫等级：

    base   除 `room == X` 外没有别的条件  ⇒ 进这间房就会显示（**默认值就该取它**）
    pos    只多出 x / y 比较              ⇒ 可按实例坐标静态判
    state  还有剧情/全局变量/函数调用      ⇒ 只能运行时判

## 三条纪律

1. **一条都不许丢**：写盘前断言 v1 的每条 `(scene, obj, key)` 都在 v2 里。
2. **顺序即语义**：`order` 保留 GML 里的赋值顺序（后面的覆盖前面的）。
3. **不改字、不解码**：正文原样搬运（`markers_raw` 仍为 true），解码在
   `item_interact.decode_readable` 里做，数据层不许偷偷替换。

用法：
    python build_readable_v2.py            # 只看统计
    python build_readable_v2.py --write    # 真写盘
"""
import argparse
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(SCENES, '_readable_text.json')

GAMES = ('ut', 'outertale')
GUARDS = ('base', 'pos', 'state')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='真写盘（默认只统计）')
    a = ap.parse_args(argv)

    texts = json.load(io.open(os.path.join(EV, 'readables115.json'), encoding='utf-8'))
    # ★ 对账基准 = **第117轮交付的键集合快照**（`readable_v1_keys.txt`，从 git HEAD 提的 355 条），
    #   不能拿"当前磁盘上的资产"当基准：脚本会被重跑，第二次跑时基准就变成了自己的产物，
    #   "一条都不许丢"当场退化成恒真。
    v1p = os.path.join(EV, 'readable_v1_keys.txt')
    old_keys = set()
    if os.path.isfile(v1p):
        for ln in io.open(v1p, encoding='utf-8'):
            if ln.startswith('#') or not ln.strip():
                continue
            q = ln.rstrip('\n').split('\t')
            if len(q) == 3:
                old_keys.add((q[0], q[1], q[2]))
    if not old_keys:
        print(u'[FAIL] 缺 %s —— 没有对账基准，"一条都不许丢"无从谈起' % v1p)
        return 1

    # ★ 实例数由 `readable_plan119.*.tsv` 带过来（见 plan119.py），这里不再重复枚举

    by_scene = collections.defaultdict(list)
    games_info = {}
    total = 0
    dead_all = []
    for game in GAMES:
        keys = (texts.get(game) or {}).get('keys') or {}
        c = collections.Counter()
        dead = []
        for ln in io.open(os.path.join(EV, 'readable_plan119.%s.tsv' % game),
                          encoding='utf-8'):
            q = ln.rstrip('\n').split('\t')
            if len(q) != 6 or q[0] == 'scene':
                continue
            sid, obj, key, guard, gtxt, n_inst = q
            n_inst = int(n_inst)
            if n_inst == 0:
                # ★ 第117轮的纪律：只收"这间房真的摆了该可读物"的组合。
                #   实例 0 = 这间房里根本没有这个对象 ⇒ 这段 `if (room == X)` 是死代码。
                dead.append((sid, obj, key))
                c['dead'] += 1
                continue
            t = keys.get(key) or {}
            raw = (t.get('cn_tight') or t.get('cn') or t.get('en') or t.get('ja'))
            if not raw:
                c['no_text_%s' % guard] += 1
                continue
            if guard not in GUARDS:
                c['bad_guard'] += 1
                continue
            by_scene[sid].append({
                'obj': obj,
                'key': key,
                'guard': guard,
                'guard_text': gtxt or None,
                'order': c['seen'],
                'cn': t.get('cn'),
                'cn_tight': t.get('cn_tight'),
                'en': t.get('en'),
                'ja': t.get('ja'),
                'instances': n_inst,
            })
            c['seen'] += 1
            c['entries'] += 1
            c['guard_' + guard] += 1
            total += 1
        dead_all.extend([(game,) + d for d in dead])
        unresolved = []
        up = os.path.join(EV, 'readable_plan119.%s.unresolved.tsv' % game)
        if os.path.isfile(up):
            for i, ln in enumerate(io.open(up, encoding='utf-8')):
                if i == 0:
                    continue
                q = ln.rstrip('\n').split('\t')
                if len(q) == 4:
                    unresolved.append({'room': q[0], 'obj': q[1],
                                       'key': q[2], 'why': q[3]})
        games_info[game] = {
            'status': 'OK',
            'scenes_out': len([s for s in by_scene if s.startswith(game + '.')]),
            'entries': c['entries'],
            'by_guard': {g: c['guard_' + g] for g in GUARDS},
            'keys_without_text': {g: c['no_text_' + g] for g in GUARDS},
            'dead_blocks': c['dead'],
            'unresolved': len(unresolved),
            'unresolved_list': unresolved,
            'source': 'GML 原文（第118轮 conds118.py），与指令流交叉校验过',
        }
        print(u'[%s] 场景 %d / 条目 %d（base %d / pos %d / state %d）；死代码 %d；未解 %d'
              u'（无房间条件）；缺正文 %d'
              % (game, games_info[game]['scenes_out'], c['entries'],
                 c['guard_base'], c['guard_pos'], c['guard_state'], c['dead'],
                 len(unresolved),
                 c['no_text_base'] + c['no_text_pos'] + c['no_text_state']))

    # ★ uty：原作**没有**可读物正文表（第117轮实测 0 条）⇒ 显式记 EMPTY，不当"通过"
    games_info['uty'] = {
        'status': 'EMPTY',
        'scenes_out': 0,
        'entries': 0,
        'by_guard': {g: 0 for g in GUARDS},
        'dead_blocks': 0,
        'unresolved': 0,
        'unresolved_list': [],
        'source': '原作没有可读物正文表（gml_Script_textdata_* 里 0 条可读物键）⇒ 如实记 EMPTY',
    }

    if not total:
        print(u'[FAIL] 一条都没生成 —— 分母为空')
        return 1

    # ---- 排序：同一对象内按 GML 顺序（后面的覆盖前面的）----
    for sid in by_scene:
        by_scene[sid].sort(key=lambda e: (e['obj'], e['order']))

    new_keys = {(sid, e['obj'], e['key'])
                for sid, es in by_scene.items() for e in es}
    lost = sorted(old_keys - new_keys)
    added = len(new_keys - old_keys)
    print(u'对账：v1 %d 条 → v2 %d 条；**丢失 %d 条**；新增 %d 条'
          % (len(old_keys), len(new_keys), len(lost), added))
    if lost:
        print(u'[FAIL] v1 有 %d 条在 v2 里找不到（不许悄悄丢数据）：' % len(lost))
        for t in lost[:10]:
            print(u'   %s' % (t,))
        return 1

    per_obj = collections.Counter()
    for sid, es in by_scene.items():
        for e in es:
            per_obj[(sid, e['obj'])] += 1
    n_multi = sum(1 for v in per_obj.values() if v > 1)
    n_no_base = 0
    for sid, es in by_scene.items():
        g = collections.defaultdict(set)
        for e in es:
            g[e['obj']].add(e['guard'])
        n_no_base += sum(1 for v in g.values() if 'base' not in v)
    print(u'组合 %d（多条候选 %d）；**没有任何 base 的组合 %d**（只能靠 pos/state 选）'
          % (len(per_obj), n_multi, n_no_base))

    doc = {
        'schema_version': 2,
        'note': (u'可读物的正文：键由「房间 + 该对象的守卫条件」共同决定'
                 u'（原作 obj_readable_*_Alarm_0 是一串平行 if，逐条覆盖 global.msg[0]）。'
                 u'v2 换用 GML 原文解析生成，并给每条候选标 guard 等级。'),
        'selection': (u'取正文的顺序：① 该 (场景,对象) 里**最后一条 base**（除房间外无条件，'
                      u'执行到最后就是它）；② 没有 base 时取第一条（pos/state 需要运行时信息，'
                      u'产品侧暂不可判，如实按原文顺序取）。'),
        'guard_note': (u'base=除 room 外无条件；pos=只多出 x/y 比较（可按实例坐标静态判）；'
                       u'state=还有剧情/全局变量/函数调用（产品侧无法判）。'),
        'markers_raw': True,
        'markers_note': (u'正文里的 % & / ^1 ^2 是原作控制符（换页/换行/按键停顿），'
                         u'**未解码**，原样保留；解码在 item_interact.decode_readable 里做。'),
        'games': games_info,
    }
    doc['by_scene'] = {sid: by_scene[sid] for sid in sorted(by_scene)}

    if not a.write:
        print(u'\n[DRY] 未写盘。加 --write 才落盘。')
        return 0

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1))
    print(u'\n[PASS] 写出 %s（%d 条 / %d 场景 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT), total, len(by_scene),
             os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
