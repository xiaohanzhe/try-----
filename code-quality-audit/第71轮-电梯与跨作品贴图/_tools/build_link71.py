# -*- coding: utf-8 -*-
"""第71轮 · 电梯数据面：`ut <-> ot` 的这条跨作品连接。

用户口径（逐字）
----------------
「outertale 和 ut 联通是通过在 ut 第一个 room 里放一个电梯（具体就是素材图里的）
  然后你也知道 outertale 是设计在宇宙上的，所以**那个电梯要很高**，当然，
  **外面设计一下就好**，**内部动画你也处理**吧，就**时间长一点**就好」

⇒ 四件事必须从"我拍脑袋的数字"变成**可回归的数据**：
   ① 放在哪（落点）   ② 很高（几何）   ③ 外面设计（外景装配）   ④ 内部动画（时长）

★ 本轮**只做规格**，不做接线
----------------------------
产品侧的跨作品场景面**还没建**：`assets/scenes/_index.json` 只有 `desktop` + `ch1~ch5`
（Deltarune），寻路图 `_room_graph.json` 也只有这五章；跨作品大图 `bigmap66.json` 停在
`_evidence/` 里、且只有 `hub:ut` / `hub:uty` 两个世界枢纽（**没有 ot / os**）。
⇒ 本文件**如实写 `wiring.status = "spec_only"`**，绝不谎称"电梯已经能坐了"。
   （本项目最贵的坑 =「函数写对了 ≠ 产品用上了」。）

数字的来源（每个都写进文件，谁都能复核）
----------------------------------------
* 落点：`_source.json#site` 的 room_index=4/room_name=room_area1，与 `bigmap66.json`
  的 `ut:4` 节点**交叉验证**（工作名 + 尺寸两处都要相等）。
* 高度：用户只说"很高""时间长一点"，没有数字 ⇒ 我把它定义成**自洽三元组**
  `speed_px_per_s × duration_s == height_px`，再由 `screens = height_px / screen_px`
  给出"多少屏"。**三个数互为校验**，改一个不同步就会被 check71 的 G4/G5 抓住。
* 内外分工：15 个零件**恰好全覆盖、不重叠**（6 外景 + 6 轿厢 + 3 井道）。

用法
----
    C:\\Python311\\python.exe build_link71.py            # 只打印（dry）
    C:\\Python311\\python.exe build_link71.py --write    # 写 _link.json
"""
from __future__ import print_function

import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUD = os.path.abspath(os.path.join(HERE, '..'))                  # 第71轮-…
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))     # 仓库根
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets')
ELEV = os.path.join(ASSETS, 'elevator')
SRC = os.path.join(ELEV, '_source.json')
DST = os.path.join(ELEV, '_link.json')
BIGMAP66 = os.path.join(ROOT, 'code-quality-audit', '第66轮-大图连通与mod并入',
                        '_evidence', 'bigmap66.json')

# --- 几何（"很高"的可校验定义）---------------------------------------------
SPEED_PX_PER_S = 60.0        # 上升速度：1 秒 1/4 屏（视觉上"慢"）
ASCENT_S = 72.0              # 纯上升时长（用户："时间长一点"）
SCREEN_PX = 240.0            # UT 内部分辨率 320x240 的**屏高** ⇒ "多少屏"的换算基准
HEIGHT_PX = SPEED_PX_PER_S * ASCENT_S      # 4320.0
SCREENS = HEIGHT_PX / SCREEN_PX            # 18.0 屏

#: "很高"的下限（判据 G5 用它把"很高"变成可测的阈值，而不是形容词）
MIN_SCREENS = 12.0

#: 内部动画四拍（ms）。总和必须 == total。
PHASES = [
    {'id': 'door_close', 'ms': 800,
     'what': '轿厢门合上', 'parts': ['spr_elevatordoorframe']},
    {'id': 'ascend', 'ms': int(ASCENT_S * 1000),
     'what': '匀速上升 —— 井道背景循环滚动（bg_elevbelow 平铺），两侧指示灯跑帧',
     'parts': ['bg_elevbelow', 'spr_elevatorgem_l', 'spr_elevatorgem_r',
               'spr_darkelevator_l', 'spr_darkelevator_r']},
    {'id': 'arrive', 'ms': 1200,
     'what': '到顶：外景（宇宙）淡入', 'parts': ['bg_elevtop']},
    {'id': 'door_open', 'ms': 800,
     'what': '轿厢门打开', 'parts': ['spr_elevatordoorframe']},
]
TOTAL_MS = sum(p['ms'] for p in PHASES)


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    write = '--write' in sys.argv
    src = read_json(SRC)
    parts = src['parts']
    site = src['site']

    # ---- 落点：两侧都要对得上（产物 vs 数据面契约 vs 大图节点）------------
    bm = read_json(BIGMAP66)
    n4 = None
    for n in bm['nodes']:
        if n['id'] == 'ut:4':
            n4 = n
            break
    assert n4 is not None, 'bigmap66 里找不到 ut:4'
    assert n4['name'] == site['room_name'], (
        '落点对不上：bigmap66 ut:4 = %r，_source.json site = %r'
        % (n4['name'], site['room_name']))
    assert [n4['w'], n4['h']] == list(site['size']), (
        '落点尺寸对不上：bigmap66 %sx%s，_source.json %s'
        % (n4['w'], n4['h'], site['size']))

    # ---- 15 个零件：内外分工必须**恰好全覆盖且不重叠** --------------------
    exterior = ['bg_elevbottom', 'bg_elevleg', 'bg_elevarmL', 'bg_elevarmR',
                'bg_elevunit', 'bg_elevtop']
    cabin = ['spr_elevatordoor', 'spr_elevatordoorframe',
             'spr_elevatordoor_vines', 'spr_elevatorpanel',
             'spr_elevatorgem_l', 'spr_elevatorgem_r']
    shaft = ['bg_elevbelow', 'spr_darkelevator_l', 'spr_darkelevator_r']
    cover = exterior + cabin + shaft
    assert len(cover) == len(set(cover)) == len(parts) == 15, (
        '零件覆盖不完整/重复：分工 %d 件（去重 %d）vs 真源 %d 件'
        % (len(cover), len(set(cover)), len(parts)))
    unknown = [p for p in cover if p not in parts]
    assert not unknown, '分工里出现真源没有的零件：%s' % unknown

    out = {
        'schema_version': 1,
        'round': 71,
        'kind': 'cross_work_link',
        'id': 'ut-ot-elevator',
        'user_words': (
            'outertale 和 ut 联通是通过在 ut 第一个 room 里放一个电梯（具体就是素材图里的）'
            '然后你也知道 outertale 是设计在宇宙上的，所以那个电梯要很高，当然，外面设计'
            '一下就好，内部动画你也知道如何处理吧，就时间长一点就好'),
        'why': 'Outertale 与 UT 的**唯一通道**：在 UT 的第一间房立一部电梯，升到宇宙。'
               '本文件 = 这条通道的规格（落点/几何/外景/内部动画），零件见 _source.json。',
        'endpoints': {
            'lower': {
                'work': 'ut', 'title': 'Undertale',
                'room_index': site['room_index'],
                'room_resource': site['room_name'],
                'room_size': list(site['size']),
                'role': '电梯井底部（地面侧，玩家站在这里按面板）',
                'status': 'evidenced',
                'evidence': ['assets/elevator/_source.json#site',
                             'code-quality-audit/第66轮-大图连通与mod并入/_evidence/'
                             'bigmap66.json#/nodes/ut:4'],
                'cross_check': {'bigmap66_node': n4['id'], 'name': n4['name'],
                                'size': [n4['w'], n4['h']]},
            },
            'upper': {
                'work': 'ot', 'title': 'Outertale',
                'room_index': None, 'room_resource': None,
                'role': '电梯顶端 = 宇宙（Outertale 设定在宇宙上）',
                'status': 'pending_room_table',
                'pending_why': (
                    'Outertale 的房间表还没并进跨作品大图 —— bigmap66 的世界枢纽只有 '
                    'hub:ut / hub:uty（外加 hub:desktop），**没有 hub:ot**。所以上端本轮'
                    '只能先记到"世界级"落点，等房间表并入后再细到具体房间。'),
                'provisional_node': 'hub:ot',
                'why_provisional_is_ok': (
                    '电梯的"上面"本来就还没建（宇宙侧的场景面是后续轮次的活）；'
                    '写 hub:ot 是**如实标注缺口**，不是拿假房间号充数。'),
            },
        },
        'shaft': {
            'why_high': 'Outertale 设在宇宙上 ⇒ 电梯要跨"地表 → 宇宙"，不是楼内两层高。',
            'unit': 'px',
            'screen_px': SCREEN_PX,
            'screen_note': '换算基准 = UT 内部分辨率 320x240 的**屏高**；'
                           'Deltarune 用的是 640x480，跨作品比高度一律以 UT 这侧为准。',
            'speed_px_per_s': SPEED_PX_PER_S,
            'ascend_s': ASCENT_S,
            'height_px': HEIGHT_PX,
            'screens': SCREENS,
            'min_screens_for_high': MIN_SCREENS,
            'self_consistency': ('speed_px_per_s * ascend_s == height_px；'
                                 'screens == height_px / screen_px —— 三个数互为校验，'
                                 '改一个不同步会被 check71 的 G4/G5 抓住。'),
            'why_this_speed': '用户只说"很高""时间长一点"，没给数字 ⇒ 我把它定义成'
                              '「匀速上升 60 px/s 跑 72 s」，时长与井道高同时满足。',
        },
        'exterior': {
            'why': '用户口径：「外面设计一下就好」⇒ 外面**只做到"看得出是部电梯"**即可，'
                   '不做精细建筑。',
            'parts': exterior,
            'assembly': 'vertical_stack',       # 底座 → 腿 → 机箱 → 两臂 → 顶盖
            'assembly_order': ['bg_elevbottom', 'bg_elevleg', 'bg_elevunit',
                               'bg_elevarmL', 'bg_elevarmR', 'bg_elevtop'],
            'align': 'center_bottom',           # 各件按**底边中点**对齐，水平居中
            'derived_by': '本项目设计（用户授权「外面设计一下就好」）；'
                          '**不是**原作装配 —— 原作只给了这 6 张零件图，没给坐标。',
        },
        'interior': {
            'why': '用户口径：「内部动画你也知道如何处理吧，就时间长一点就好」',
            'cabin_parts': cabin,
            'shaft_parts': shaft,
            'animation': {
                'loop': False,
                'total_ms': TOTAL_MS,
                'phases': PHASES,
                'frame_source': 'spr_elevatorgem_l/r 各 6 帧（指示灯跑动）；'
                                'spr_elevatordoorframe 2 帧（开/合）；'
                                'bg_elevbelow 平铺滚动表示"上升中"。',
                'why_long': '电梯要爬 %g 屏（%g px），按 %g px/s 得 %g s —— 「时间长一点」'
                            '是**几何的结果**，不是随意拉长的过场。'
                            % (SCREENS, HEIGHT_PX, SPEED_PX_PER_S, ASCENT_S),
            },
        },
        'parts_ref': 'assets/elevator/_source.json',
        'parts_cover': {'exterior': exterior, 'cabin': cabin, 'shaft': shaft,
                        'count': len(cover)},
        'wiring': {
            'status': 'spec_only',
            'not_yet': [
                'ut 侧房间还没作为场景登记进 assets/scenes/_index.json'
                '（该索引目前只有 desktop + ch1~ch5）',
                'Outertale 房间表未并入 ⇒ 上端只能停在 hub:ot',
                '跨作品大图仍在 code-quality-audit/第66轮…/_evidence/bigmap66.json，'
                '产品侧寻路图 _room_graph.json 只有 Deltarune 五章',
                '跨世界穿行规则（谁能走暗世界）属轮次 72，本轮不碰',
            ],
            'how_to_consume': '后续轮次把本条 link 作为「跨作品边」的证据源：'
                              'lower 端 = ut:4，upper 端 = hub:ot，载体 = 电梯动画。',
            'honesty_note': '写 spec_only 是刻意的 —— 本项目最贵的坑就是'
                            '「函数写对了 ≠ 产品用上了」。',
        },
        'evidence': [
            'code-quality-audit/第71轮-电梯与跨作品贴图/_evidence/fetch71_ut.json',
            'code-quality-audit/第71轮-电梯与跨作品贴图/_evidence/fetch71_plan.json',
        ],
    }

    print('== 电梯 data face 自检 ==')
    print('  落点  : %s:%d %s %s  (bigmap66 交叉验证 OK)'
          % ('ut', site['room_index'], site['room_name'], site['size']))
    print('  上端  : ot / hub:ot（pending：房间表未并入）')
    print('  几何  : %.1f px/s × %.1f s = %.1f px = %.1f 屏（下限 %.1f）'
          % (SPEED_PX_PER_S, ASCENT_S, HEIGHT_PX, SCREENS, MIN_SCREENS))
    print('  自洽  : speed*ascend == height  ->  %s'
          % (abs(SPEED_PX_PER_S * ASCENT_S - HEIGHT_PX) < 1e-9))
    print('  零件  : 外景 %d + 轿厢 %d + 井道 %d = %d / 真源 %d'
          % (len(exterior), len(cabin), len(shaft), len(cover), len(parts)))
    print('  动画  : %d 拍，合计 %d ms' % (len(PHASES), TOTAL_MS))
    if not write:
        print('  (dry run —— 加 --write 才落盘)')
        return 0
    with io.open(DST, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    print('-> %s (%d bytes)' % (DST, os.path.getsize(DST)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
