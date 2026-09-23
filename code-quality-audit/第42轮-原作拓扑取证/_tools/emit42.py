# -*- coding: utf-8 -*-
"""第42轮 · 生成可交付数据：_room_order.json（五章房间全序）+ _room_graph.json（五章连接图）
并做自检：边数一致 / src·dst 都在表内 / 无自环
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
DRW = r'E:\Download\_tmp\drw'
OUTD = r'E:\Download\_tmp'
CH = [('chapter1_windows', 'ch1', '第一章', 'The Beginning'),
      ('chapter2_windows', 'ch2', '第二章', "A Cyber's World"),
      ('chapter3_windows', 'ch3', '第三章', 'Late Night TV'),
      ('chapter4_windows', 'ch4', '第四章', 'Prophecy'),
      ('chapter5_windows', 'ch5', '第五章', 'Garden of Hopes and Dreams')]

KIND_RULES = [
    (re.compile(r'PLACE_|INITIALIZE|legend|gameover|splash|continue|^room_ed$|^room_man$|'
                r'room_empty|DARKempty|battletest|^PROCESS_|^DEVICE_|^room_credits', re.I), 'system'),
    (re.compile(r'debug|tester|_test|demo|failsafe|gif_|sound_|sprite_|teacup|shaun|'
                r'placeholder|bullettest|^room_gms_', re.I), 'debug'),
    (re.compile(r'dark|_dw\b|^room_dw_|cyber|board|mansion|sanctuary|prison|cliff|'
                r'garden|castle|mike|tenna', re.I), 'dark'),
    (re.compile(r'^room_(krisroom|krishallway|torroom|torhouse|torbathroom)$'), 'home'),
    (re.compile(r'^room_town'), 'town'),
    (re.compile(r'^room_(beach|graveyard|diner|hospital_|flowershop_|library|alphysalley|'
                r'torielclass|schoollobby|alphysclass|schooldoor|insidecloset|'
                r'school_unusedroom|lw_|gms_debug)'), 'town_life'),
    (re.compile(r'^room_(field|forest)'), 'field_forest'),
    (re.compile(r'^room_cc_'), 'card_castle'),
]


def kind_of(name):
    for rx, k in KIND_RULES:
        if rx.search(name):
            return k
    return 'other'


order = {'schema_version': 1,
         'meta': {
             'note': '原作五章「房间全序表」——直接取自 data.win 的 Data.Rooms 列表下标。'
                     '原作的房间顺序就是这份列表的顺序；门对象的 ±1/±2/±3 位移全部基于本表下标。',
             'source': 'UTMT CLI v0.9.2.0 读 Data.Rooms（五章 data.win 副本，只读不落盘）',
             'why': '用户口径：「所有 room 排序和连接都按照原作，相当于场景复现」。'
                    '本表 = 排序真相；_room_graph.json = 连接真相。',
             'field_kind': 'home 克里斯家 / town 街道 / town_life 邻接生活区+店铺 / dark 暗世界 / '
                           'field_forest 田野森林 / card_castle 扑克城堡 / system 系统房间 / '
                           'debug 调试房间 / other 未归类',
         },
         'chapters': {}}
graph = {'schema_version': 1,
         'meta': {
             'note': '原作五章「房间连接图」——由门对象实例 + 门对象 Alarm 事件反汇编共同还原。'
                     '相邻关系全部来自原作，非我们发明。',
             'rules': {
                 'obj_doorA[_musfade]': 'room_goto_next()  => index + 1',
                 'obj_doorB[_musfade]': 'room_goto_previous() => index - 1',
                 'obj_doorC[_musfade]': 'room_goto(room_next(room_next(room))) => index + 2',
                 'obj_doorD[_musfade]': 'room_goto(room_previous(room_previous(room))) => index - 2',
                 'obj_doorE': 'room_next x3 => index + 3',
                 'obj_doorF': 'room_previous x3 => index - 3',
                 'obj_doorX[_musfade]': '表驱动双向跳转（建筑入口）',
                 'obj_doorW[ obj_doorw_musfade]': '表驱动双向跳转（建筑入口）',
                 'obj_doorAny': '无任何代码 —— 纯占位标记，不参与换房间',
                 'obj_markerA..X': '落点：从对应 door 进入本房间时玩家的落点坐标',
             },
             'caveat': '边只覆盖「门对象驱动」的换房间。过场对象（obj_carcutscene / '
                       'obj_krisroom / obj_insidEclosetcutscene / DEVICE_CONTACT 等）的 room_goto '
                       '属剧情转场，未计入连接图。',
         },
         'chapters': {}}

GALL = json.loads(open(os.path.join(OUTD, 'graph42.json'), 'rb').read().decode('utf-8'))
tot_e = 0
for folder, key, cname, alias in CH:
    conn = json.loads(open(os.path.join(DRW, folder, 'conn42b.json'), 'rb').read().decode('utf-8'))
    g = GALL
    rn = conn['room_names']
    rooms = [{'index': i, 'name': n, 'kind': kind_of(n)} for i, n in enumerate(rn)]
    order['chapters'][key] = {'folder': folder, 'name': cname, 'display_alias': alias,
                              'n_rooms': len(rn), 'rooms': rooms}
    edges = []
    for e in g[key]['edges']:
        edges.append({'src': e['src'], 'src_name': rn[e['src']],
                      'dst': e['dst'], 'dst_name': rn[e['dst']],
                      'door': e['door'], 'kind': e['kind']})
    graph['chapters'][key] = {'folder': folder, 'n_edges': len(edges),
                              'edges': edges}
    tot_e += len(edges)

fo = os.path.join(OUTD, '_room_order.json')
fg = os.path.join(OUTD, '_room_graph.json')
json.dump(order, open(fo, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(graph, open(fg, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------------- 自检 ----------------
print('=' * 78)
print('生成产物')
print('=' * 78)
print('  %-24s %d B' % ('_room_order.json', os.path.getsize(fo)))
print('  %-24s %d B' % ('_room_graph.json', os.path.getsize(fg)))
print('  边总数 = %d' % tot_e)

print()
print('=' * 78)
print('自检')
print('=' * 78)
ok = True
tot_rooms = 0
for folder, key, cname, alias in CH:
    o = order['chapters'][key]
    gr = graph['chapters'][key]
    rn = [r['name'] for r in o['rooms']]
    tot_rooms += len(rn)
    # ① 边数一致
    c1 = (gr['n_edges'] == len(gr['edges']))
    # ② src/dst 在表内
    c2 = all(0 <= e['src'] < len(rn) and 0 <= e['dst'] < len(rn) for e in gr['edges'])
    # ③ 无自环
    selfloop = [e for e in gr['edges'] if e['src'] == e['dst']]
    # ④ 名字一致（edge 里冗余的名字 vs 表里的名字）
    c4 = all(rn[e['src']] == e['src_name'] and rn[e['dst']] == e['dst_name'] for e in gr['edges'])
    # ⑤ kind 覆盖
    kinds = {}
    for r in o['rooms']:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    flag = 'OK' if (c1 and c2 and not selfloop and c4) else 'FAIL'
    if flag == 'FAIL':
        ok = False
    print('  %-4s rooms=%-4d edges=%-4d  边数一致=%s 下标合法=%s 无自环=%s 名字一致=%s  %s'
          % (key, len(rn), gr['n_edges'], c1, c2, not selfloop, c4, flag))
    print('       kind: %s' % kinds)
print('  五章房间合计 = %d' % tot_rooms)
print('  总判定 = %s' % ('PASS' if ok else 'FAIL'))
