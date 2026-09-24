# -*- coding: utf-8 -*-
"""第44轮 · 从原作房间图重建产品路由表（P1 主体）—— v2 正式版。

背景（用户裁定）
----------------
「路由重建我也不懂，你自己判断」
「所有 room 排序/连接都按照原作，相当于场景复现」

⇒ 把「26 条人工按区域写死的规则」升级为
  「按**原作门的下标位移机制**生成的、覆盖尽可能多可游玩场景的规则表」。

★★★ 门 → 目标房 的真实机制（本轮实证，见 _evidence/连接顺序分析.txt §E）
------------------------------------------------------------------------
原作 `obj_doorA/B/C` 不读空间坐标，而是 **`Data.Rooms` 数组下标位移**：

    门对象    位移      五章命中率（"目标房含同字母落点"）
    obj_doorA  +1       ch1 69/69(100%) ch2 79/99(80%) ch3 13/13(100%) ch4 13/13(100%) ch5 10/10(100%)
    obj_doorB  -1       ch1 69/69(100%) ch2 85/104(82%) ch3 13/13(100%) ch4 11/13(85%) ch5 11/11(100%)
    obj_doorC  +2       ch1 18/18(100%) ch2 10/11(91%) ch3 8/9(89%) ch4 8/8(100%) ch5 8/8(100%)

★ 判据：**目标房必须含 `obj_marker<同字母>`**。位移是先验假设，
  落点是它的**独立验证** —— 两者同时成立才编边，否则丢弃。

⚠️ 被**本条证伪**的旧启发式（不要退回去）
---------------------------------------
初版用「两房中心距离最近 + 同字母落点」编边，锚点校验当场报红：
  · krisroom 的 doorA 被判到 `torbathroom`（错），正解是 `krishallway`；
  · 99.3% 的边被标 `ambiguous`（等于没判）。
根因：**落点坐标是"房间自己坐标系里的局部坐标"**（实测都是 10~300 的
小数值），不是全地图共享的世界坐标 ⇒ 用坐标做跨房匹配**在原理上就不成立**。
（教训落地：记忆 §4「解析器输出必须先过已知真值锚点」——
  这次正是锚点校验把一条"看起来跑通了"的错路拦下来的。）

不编边的情况（如实报告，不伪造连通性）
--------------------------------------
  · `obj_doorAny`(830) / `obj_doorAnyHorz`(42) / `obj_doorAnyVert`(9) —— 无字母；
  · `obj_doorW`(213) / `obj_markerw`(91) —— 表驱动双向，需读对象代码；
  · `obj_doorX`(106+23) —— 表驱动双向，需读对象代码；
  · `obj_door_solid`(9) —— 实心装饰；
  · `obj_doorD`(66) —— 位移未定（实测 +2 只有 33%，证据不足，**不猜**）；
  · `obj_doorE/F`(各 1) —— 样本量 1，不足以定位移。
  ⇒ 以上都**不编边**，由 `_fallback` 兜底。

输出
----
覆盖写入  ralsei_pet/assets/scenes/_routes.json  （schema_version 保持 1）
落盘统计  _evidence/routes44/新路由统计.txt
"""
import io
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
R44 = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻')
EV = os.path.join(R44, '_evidence')
ROOMS = os.path.join(EV, 'rooms44')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

#: ★ 已实证的门 → 下标位移表。只在**落点验证通过**时使用。
DOOR_DELTA = {
    'A': 1,
    'B': -1,
    'C': 2,
}

#: 不编边的门型（如实报告，不做猜测）。
UNSUPPORTED = ('W', 'X', 'D', 'E', 'F', 'Any')


def door_letter(objname):
    """`obj_doorA` → 'A'；`obj_doorA_musfade` → 'A'；`obj_doorAny` → None。"""
    if not objname or not objname.startswith('obj_door'):
        return None
    tail = objname[len('obj_door'):]
    for suf in ('_musfade', '_solid'):
        if tail.endswith(suf):
            tail = tail[:-len(suf)]
    if len(tail) == 1 and tail.isalpha() and tail.upper() in DOOR_DELTA:
        return tail.upper()
    return None


def marker_letter(objname):
    """`obj_markerA` → 'A'；`obj_markerAny` / `obj_markerw` → None（大小写敏感）。"""
    if not objname or not objname.startswith('obj_marker'):
        return None
    tail = objname[len('obj_marker'):]
    if len(tail) == 1 and tail.isalpha() and tail.isupper():
        return tail
    return None


def parse_pts(lst):
    out = []
    for s in lst or []:
        parts = str(s).split(',')
        if len(parts) >= 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


def main():
    # ---------------------------------------------------------- 1. 读原作房
    rooms = {}            # (ch, room_id) -> room dict
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        p = os.path.join(ROOMS, ch + '.json')
        d = json.load(io.open(p, encoding='utf-8'))
        for r in d['rooms']:
            r['_ch'] = ch
            rooms[(ch, r['id'])] = r

    # ---------------------------------------------------------- 2. 读产品索引
    idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    scenes = {}
    by_room_id = {}
    for ch_id, chapter in (idx.get('chapters') or {}).items():
        for area_id, area in (chapter.get('areas') or {}).items():
            for sid, entry in (area.get('scenes') or {}).items():
                e = dict(entry)
                e['scene_id'] = sid
                e['chapter_id'] = ch_id
                e['area_id'] = area_id
                scenes[sid] = e
                orid = e.get('original_room_id')
                if isinstance(orid, int):
                    by_room_id[(ch_id, orid)] = sid

    # ---------------------------------------------------------- 3. 建边
    # 键 = (src_sid, dst_sid) ；值 = 证据 dict
    edges = {}
    stats = {'total_door_letters': 0, 'verified': 0,
             'no_target_room': 0, 'no_marker': 0, 'target_not_indexed': 0,
             'unsupported': 0}

    for (ch, rid), r in sorted(rooms.items()):
        sid = by_room_id.get((ch, rid))
        # 无论出发房是否登记，都要统计门型（口径完整）
        for (_x, _y, dname) in parse_pts(r.get('doors')):
            letter = door_letter(dname)
            if letter is None:
                if any(dname.endswith(u) or ('door' + u) in dname
                       for u in UNSUPPORTED):
                    stats['unsupported'] += 1
                continue
            stats['total_door_letters'] += 1
            if not sid:
                stats['target_not_indexed'] += 1
                continue
            delta = DOOR_DELTA[letter]
            tr = rooms.get((ch, rid + delta))
            if tr is None:
                stats['no_target_room'] += 1
                continue
            # ★ 独立验证：目标房必须含同字母落点
            if not any(marker_letter(n) == letter
                       for (_a, _b, n) in parse_pts(tr.get('markers'))):
                stats['no_marker'] += 1
                continue
            dst = by_room_id.get((ch, tr['id']))
            if not dst:
                stats['target_not_indexed'] += 1
                continue
            stats['verified'] += 1
            edges[(sid, dst)] = {
                'letter': letter,
                'delta': delta,
                'src_room': r['name'],
                'dst_room': tr['name'],
            }

    # ---------------------------------------------------------- 4. 出规则
    # ★ 多出口场景的「共同卡口」处理（用户点名要我解决）：
    #   297 个起点里 125 个有多于 1 条出边（最多 3 条），when_scene 单条件
    #   无法区分"从哪个门出去"。故每条规则都带 `when_door`（= 门的字母），
    #   由 scene_routing._match_one 的**反向语义**处理：
    #     · context 没给 door        → 所有门规则都放行，靠 priority 决胜；
    #     · context 给了 door        → 只有字母相等的规则命中。
    #   priority 里同一 when_scene 的多条按**字母序**铺开（A<B<C），
    #   于是"没指定门"时的默认出口是稳定的、可复现的（取字母最靠前的门）。
    #
    # ★★ 第44轮续 · 修复「priority 回绕」缺陷（原 `110 + order % 240`）
    # ------------------------------------------------------------------
    # 旧写法 `priority = 110 + (order % 240)` 用的是**全局** order 计数器，
    # 当 order 跨过 240 时取模回绕 ⇒ 同一场景的出边 priority 不再随字母
    # 单调。实测 443 条里有 1 个多出口场景（ch2.cyber_field.
    # dw_cyber_maze_virokun）中招：B=110 / C=111 在回绕前，A=349 在回绕后
    # ⇒ "没指定门时走字母最靠前的门（A）"这条设计约定**失效**，默认走了 B。
    #
    # 新写法：**每个场景独占一个 priority 段**（段长 8，足够容纳 A/B/C 三条），
    # 段内按字母序递增。这样：
    #   · 同一场景的出边 priority 一定连续且随字母递增（不再回绕）；
    #   · 不同场景的段互不重叠（段间隔 8 > 单场景最大出边数 3）；
    #   · 全程 ≤ 110 + 297*8 = 2486，仍远离未来手写规则可能占用的低区间。
    # 为什么不是"全局单调"：匹配是**按场景分流**的（`when_scene` 相同时才比
    # priority），跨场景 priority 谁大谁小**无关结果**；真正必须守住的不变量
    # 是"**同一场景内**，字母序 = priority 序"。
    BAND = 8
    routes = []
    order = 0
    per_scene = {}
    for (sa, sb) in sorted(edges):
        per_scene.setdefault(sa, []).append(sb)

    scene_ord = {sa: i for i, sa in enumerate(sorted(per_scene))}
    for sa in sorted(per_scene):
        exits = sorted(per_scene[sa],
                       key=lambda s: (edges[(sa, s)]['letter'], s))
        for k, sb in enumerate(exits):
            info = edges[(sa, sb)]
            ea, eb = scenes[sa], scenes[sb]
            reason = ('原作连接：从 %s 的 %s 门离开，落到 %s 的 %s 落点'
                      '（房间数组下标 %+d）。'
                      % (ea.get('name') or sa, info['letter'],
                         eb.get('name') or sb, info['letter'], info['delta']))
            routes.append({
                'to': sb,
                'priority': 110 + scene_ord[sa] * BAND + k,
                'reason': reason,
                'when_scene': sa,
                'when_door': info['letter'],
                '_original': {
                    'chapter': ea['chapter_id'],
                    'door_letter': info['letter'],
                    'room_delta': info['delta'],
                    'src_room_name': info['src_room'],
                    'dst_room_name': info['dst_room'],
                },
            })
            order += 1

    # ---------------------------------------------------------- 5. 落盘
    out = {
        'schema_version': 1,
        'meta': {
            'note': ('场景路由表 v2 —— 由原作**门的下标位移机制**生成'
                     '（见 code-quality-audit/第44轮-原作对话框复刻/_tools/gen_routes44.py）。'),
            'how_it_works': [
                '1. 控制器把当前语境打包成 context（scene_id / mood / event / keywords）。',
                '2. scene_routing.match() 按 priority 升序挑第一条匹配规则。',
                '3. 拿 to 去 switch()。匹配不到 = 没有理由换场景 → 原地不动。',
            ],
            'rule_fields': {
                'to': '目标 scene_id',
                'priority': '越小越先匹配',
                'when_scene': '出发场景 id（v2 的唯一条件）',
                'when_door': ('出口门字母（A/B/C）—— 解决「多出口共同卡口」：'
                              'context 没给 door 时全部放行（按 priority 决胜，'
                              '同一场景内按字母序，故默认出口稳定）；'
                              '给了 door 就精确分流。见 scene_routing._match_one。'),
                'reason': '自然语言解释，注入给 AI',
                '_original': '本条规则的原作依据（章 / 门的字母 / 下标位移 / 两端房名）',
            },
            'source_of_truth': ('原作房间与门/落点实例：'
                                '_evidence/rooms44/ch{1..5}.json（UTMT 读真实 data.win）'),
            'mechanism': ('obj_doorA/B/C = Data.Rooms 数组下标位移（A +1 / B -1 / C +2），'
                          '且**必须有同字母落点作为独立验证**才编边。'
                          '五章交叉验证命中率 80~100%。'),
            'coverage_policy': ('只覆盖 obj_doorA / obj_doorB / obj_doorC。'
                                'obj_doorAny / W / X / D / E / F / solid 不编边 —— '
                                '它们要么无字母、要么表驱动双向（需读对象代码）、'
                                '要么样本不足以定位移。未覆盖场景由 _fallback 兜底，'
                                '**不伪造连通性**。'),
            'critical_warning_priority_beats_score': ('priority 是第一排序键，压过 score；'
                                                      '兜底一律走 _fallback。'),
        },
        'routes': routes,
        '_fallback': {'to': 'desktop',
                      'reason': '没有匹配到任何规则时的落脚点：回桌面'},
    }
    dst = os.path.join(SCENES, '_routes.json')
    with io.open(dst, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    # ---------------------------------------------------------- 6. 统计落盘
    reached = set(r['to'] for r in routes)
    srcset = set(r['when_scene'] for r in routes)
    lines = []
    lines.append('第44轮 · 路由重建（v2 · 由原作门的下标位移机制生成）')
    lines.append('=' * 72)
    lines.append('原作房（五章）              : %d' % len(rooms))
    lines.append('产品登记场景                : %d' % len(scenes))
    lines.append('可参与配对（有 room_id）    : %d' % len(by_room_id))
    lines.append('')
    lines.append('【门型普查（全 1840 个门实例）】')
    lines.append('  A/B/C 字母门（可用）      : %d' % stats['total_door_letters'])
    lines.append('  其它门型（无字母/表驱动） : %d' % stats['unsupported'])
    lines.append('')
    lines.append('【A/B/C 字母门的去向判定】')
    lines.append('  ★ 验证通过（编边）        : %d' % stats['verified'])
    lines.append('    目标房不存在            : %d' % stats['no_target_room'])
    lines.append('    目标房无同字母落点      : %d' % stats['no_marker'])
    lines.append('    目标房未登记为场景      : %d' % stats['target_not_indexed'])
    lines.append('')
    lines.append('【成品路由表】')
    lines.append('  规则数                    : %d' % len(routes))
    lines.append('  起点场景                  : %d' % len(srcset))
    lines.append('  可达场景                  : %d' % len(reached))
    lines.append('  可达率（对 1013 个有 original_room_id 的场景）: %.1f%%'
                 % (100.0 * len(reached) / 1013.0))
    lines.append('')
    lines.append('【逐章可达】')
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        tot = sum(1 for e in scenes.values() if e['chapter_id'] == ch)
        got = sum(1 for sid in reached
                  if scenes.get(sid, {}).get('chapter_id') == ch)
        lines.append('  %s : %d/%d (%.0f%%)' % (ch, got, tot, 100.0 * got / max(1, tot)))
    outp = os.path.join(EV, 'routes44', '新路由统计.txt')
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with io.open(outp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')

    print('\n'.join(lines))
    print()
    print('[done] -> %s' % dst)


if __name__ == '__main__':
    main()
