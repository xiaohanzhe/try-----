# -*- coding: utf-8 -*-
u"""第115轮补：可读物「房间 → 文本键」绑定，做交叉验证与异常清单。

机理（三次 UTMT 探针逐步排除后剩下的唯一解释）
------------------------------------------------
`obj_readable_<kind>_Alarm_0` 里是一串

    PushBltn{room} ; PushI <N> ; Cmp ; Bf <skip> ; Push 'obj_readable_<kind>_<M>' ; …

⇒ **键由房间下标决定，与实例坐标无关**。
证据两条：① `probe_dump_ins` 反射出 `ValueVariable = {room}`；
② `probe_key_users` 显示每个键只被**自己对象的 Alarm** 引用一次（别的代码不碰）。

本脚本做三件事
--------------
1. 在**分母非空**的前提下，量出「有实例的 (房间, 对象) 组合」里有多少能被绑定表对上。
2. 把对不上的组合**逐条列出来**（不猜、不补、不静默算进分母）。
3. 产出 `_evidence/readable_bind115.json` 与同名 `.txt`。

★ 只读仓库内文件，不碰 D:/E:（回归纪律）。
"""
import io
import json
import os
import collections
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
RAW = os.path.join(ROUND, '_evidence', 'raw')
EVI = os.path.join(ROUND, '_evidence')

GAMES = ('ut', 'outertale', 'uty')


def read_lines(p):
    with io.open(p, encoding='utf-8', errors='replace', newline='') as f:
        return f.read().splitlines()


def load_bind(game):
    """readable_bind.tsv ⇒ [(alarm, obj, room_idx, key)]；room_idx=-1 表示无 room 守卫。"""
    p = os.path.join(RAW, game, 'readable_bind.tsv')
    if not os.path.isfile(p):
        return None
    out = []
    for i, ln in enumerate(read_lines(p)):
        if i == 0 or not ln.strip():
            continue
        c = ln.split('\t')
        if len(c) != 4:
            continue
        out.append((c[0], c[1], int(c[2]), c[3]))
    return out


def load_inst(game):
    """inst_full.tsv ⇒ rooms{idx:name}, inst[(room_idx, obj)] = [(x, y)]"""
    p = os.path.join(RAW, game, 'inst_full.tsv')
    if not os.path.isfile(p):
        return None, None
    rooms = {}
    inst = collections.defaultdict(list)
    cur = None
    for ln in read_lines(p):
        c = ln.split('\t')
        if not c:
            continue
        if c[0] == 'R' and len(c) >= 3:
            cur = (int(c[1]), c[2])
            rooms[cur[0]] = cur[1]
        elif c[0] == 'I' and len(c) >= 4 and 'readable' in c[1] and cur:
            inst[(cur[0], c[1])].append((int(c[2]), int(c[3])))
    return rooms, inst


def main():
    report = {'method': u'Alarm_0 内 if (room == N) 绑定文本键', 'games': {}}
    lines = []

    for g in GAMES:
        bind = load_bind(g)
        rooms, inst = load_inst(g)
        if bind is None or inst is None:
            report['games'][g] = {'status': 'NO_DATA'}
            lines.append('[%s] 无数据（未导出）' % g)
            continue

        keys = set(b[3] for b in bind)
        guarded = [b for b in bind if b[2] >= 0]
        by_room_obj = collections.defaultdict(list)
        for _a, obj, ri, k in guarded:
            by_room_obj[(ri, obj)].append(k)

        combos = sorted(inst.keys())
        hit = [c for c in combos if c in by_room_obj]
        miss = [c for c in combos if c not in by_room_obj]
        total_inst = sum(len(v) for v in inst.values())

        report['games'][g] = {
            'bind_rows': len(bind),
            'guarded': len(guarded),
            'unique_keys': len(keys),
            'rooms_with_readable': len(set(c[0] for c in combos)),
            'instances': total_inst,
            'combos': len(combos),
            'combo_hit': len(hit),
            'combo_miss': len(miss),
            'miss_list': [{'room_idx': c[0], 'room': rooms.get(c[0]),
                           'obj': c[1], 'n': len(inst[c])} for c in miss],
            'multi_instance_combos': sum(1 for c in combos if len(inst[c]) > 1),
        }

        lines.append('=' * 66)
        lines.append('[%s] 绑定行 %d（有 room 守卫 %d）· 唯一键 %d'
                     % (g, len(bind), len(guarded), len(keys)))
        lines.append('     可读物实例 %d 个 · (房间,对象) 组合 %d 个 · 涉及 %d 间房'
                     % (total_inst, len(combos), len(set(c[0] for c in combos))))
        if combos:
            lines.append('     ★ 能绑定 %d / %d = %.1f%%'
                         % (len(hit), len(combos), 100.0 * len(hit) / len(combos)))
        else:
            lines.append(u'     EMPTY：没有可读物实例，覆盖率无从计算（不当 100%）')
        if miss:
            lines.append('     对不上 %d 个（全部列出，不猜）：' % len(miss))
            for c in miss:
                lines.append('       - %-18s %-28s 实例%d'
                             % (rooms.get(c[0]) or ('#%d' % c[0]), c[1], len(inst[c])))
        lines.append('     同一房间摆多个同类可读物的组合：%d 个'
                     % report['games'][g]['multi_instance_combos'])
        if report['games'][g]['multi_instance_combos']:
            lines.append('     ⚠ 这些组合会**共享同一条正文**（本规则只到 (房间,对象) 粒度，'
                         '不能当成"每实例一文本"）')

    os.makedirs(EVI, exist_ok=True)
    with io.open(os.path.join(EVI, 'readable_bind115.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1))
    with io.open(os.path.join(EVI, 'readable_bind115.txt'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(u'\n'.join(lines) + u'\n')
    print('\n'.join(lines))

    # ---- 分母闸：至少有一款真的算出了覆盖率，否则这脚本什么也没证明 ----
    computed = [g for g in report['games'] if report['games'][g].get('combos')]
    if not computed:
        print('')
        print('[FAIL] 分母为空：没有任何一款算出覆盖率 —— 本脚本没有证明任何东西')
        return 1
    print('')
    print('[PASS] 至少一款算出覆盖率：%s' % ', '.join(computed))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
