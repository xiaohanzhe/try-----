# -*- coding: utf-8 -*-
"""第72轮 · 跨世界契约数据面 `assets/npc/_crossworld.json`。

用户口径（逐字，本轮要落成数据的那些）
--------------------------------------
* 「因为各个世界观里有重复的角色，我要求他们能够共存」
* 「niko可自由穿行所有世界，其余ut及其同人的任务只能在非暗世界穿梭」
* 「我希望他们是生活在这而不是我走到哪他们加载到哪……他们可以私下交流信息这类的，
   闲聊，移动这种行，不需要以我发起为起点」
* 「我希望他们是能对场景有反应的，比如sans来到oneshot会吐槽，这地方真黑之类的话
   （当然，不止黑，破败这类的词也需要有能力识别）」
* 「之后不同世界的人一开始也不认识，所以他们也是循序渐进的熟悉起来，当然，面对
   不同版本的自己熟悉的会更快，比如toriel，有ut的，三角符文的，黄魂里的，
   outertale里的，他们四个会熟悉的很快」
* 「怪物们之间没有身份标识说，你是哪个世界观的，所以那需要自己判断，
   而非每次都精准的知道那是哪个人」
* 「对了做好不同世界的角色在不同世界的兼容性哦」

★ 只写**数据**，不谎称接线
--------------------------
本文件里 `wiring` 逐项标注 `wired` / `spec_only`。**只有 `roam` 是真接线的**
（第72轮改的 `npc_system.RoamScope` + `world_gate`）。其余四块（同名相认 / 无身份
标识 / 熟络初值 / 场景反应 / 访客兼容）本轮**只落契约**，如实写 `spec_only`
—— 本项目最贵的坑是「函数写对了 != 产品用上了」。

用法
----
    C:\\Python311\\python.exe build_crossworld72.py [--write]
"""
from __future__ import print_function

import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NPCDIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
REG = os.path.join(NPCDIR, '_registry.json')
DST = os.path.join(NPCDIR, '_crossworld.json')

#: 跨作品前缀
XWORK = ('ut', 'hy', 'ot', 'os')

#: ★ "同一角色的不同版本（AU）"家族。
#: 依据：**Outertale 与 Undertale Yellow（黄魂）都是《Undertale》的同人衍生作品**，
#: 所以 `ut_ / hy_ / ot_` 三方的同名角色互为"另一个版本的我"。
#: `os`（OneShot）是**独立作品**，不在这条家族里 —— 它只有"同名"，没有"同人"。
AU_FAMILY = ('ut', 'hy', 'ot')

WORK_TITLE = {'ut': 'Undertale', 'hy': 'Undertale Yellow（黄魂）',
              'ot': 'Outertale', 'os': 'OneShot', 'deltarune': 'Deltarune（三角符文）'}


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def work_of(nid):
    w = nid.split('_')[0]
    return w if w in XWORK else 'deltarune'


def build_twin_groups(npcs):
    """同名组 —— **从注册表推**（真源），不手写。

    收组规则：同一 `name` 下 ≥2 位，且**至少一位来自本作之外**
    （否则 `puzzlemaster1/2` 这种 Deltarune 内部的同名会被误收进来）。
    """
    byname = collections.defaultdict(list)
    for n in npcs:
        byname[n['name']].append((n['id'], work_of(n['id'])))
    groups = []
    for name, members in sorted(byname.items()):
        if len(members) < 2:
            continue
        if not any(w in XWORK for _, w in members):
            continue
        ids = [m[0] for m in members]
        ws = dict(members)
        # 「同一角色的不同版本」= 组内**同属 UT 衍生家族**的那些两两组合
        au = sorted([m[0] for m in members if m[1] in AU_FAMILY])
        namesake = sorted([m[0] for m in members
                           if m[1] not in AU_FAMILY])
        groups.append({
            'name': name,
            'members': sorted(ids),
            'works': dict(sorted(ws.items())),
            'au_family_members': au,
            'namesake_members': namesake,
            'has_au': len(au) >= 2,
            'why': (u'组内 %s 互为"同一角色的不同版本"（Outertale / 黄魂都是 Undertale '
                    u'的同人衍生）；%s 与它们**只是同名**（另一个作品里的人）。'
                    % ('/'.join(au) or '(无)', '/'.join(namesake) or '(无)')),
        })
    return groups


def main():
    write = '--write' in sys.argv
    reg = read_json(REG)
    npcs = reg['npcs']
    twins = build_twin_groups(npcs)
    scopes = collections.Counter(n.get('roam_scope') for n in npcs)

    out = {
        'schema_version': 1,
        'round': 72,
        'kind': 'cross_world_contract',
        'why': u'各个世界观里有重复的角色，要求他们能够共存；niko 可自由穿行所有世界，'
               u'其余 UT 及其同人只能在非暗世界穿梭；不同世界的人一开始不认识、'
               u'循序渐熟（同版本更快）；互相没有身份标识、要自己判断；要对场景有反应。',
        'user_words': u'（逐字）「niko可自由穿行所有世界，其余ut及其同人的任务只能在'
                      u'非暗世界穿梭」「怪物们之间没有身份标识说，你是哪个世界观的，'
                      u'所以那需要自己判断」「面对不同版本的自己熟悉的会更快，'
                      u'比如toriel，有ut的，三角符文的，黄魂里的，outertale里的，'
                      u'他们四个会熟悉的很快」「做好不同世界的角色在不同世界的兼容性哦」',

        # ---------------- ① 穿行域（★ 本文件唯一真接线的一块）----------------
        'roam': {
            'status': 'wired',
            'gate_impl': 'ralsei_pet/modules/npc_system.py 的 RoamScope + world_gate 暗世界分支',
            'data_impl': 'ralsei_pet/assets/npc/_registry.json 的 roam_scope 字段（全 96 条显式）',
            'scope_values': {
                'home': u'只在自己登记的世界/章节（Deltarune 侧 35 位；= 第49/50轮原口径）',
                'non_dark': u'可穿行所有非暗世界（跨作品 60 位的默认档）',
                'all': u'所有世界（含 Deltarune 暗世界）—— 仅 Niko',
            },
            'counts': {'home': scopes.get('home', 0),
                       'non_dark': scopes.get('non_dark', 0),
                       'all': scopes.get('all', 0)},
            'all_ids': sorted(n['id'] for n in npcs
                              if n.get('roam_scope') == 'all'),
            'why_foreign': u'跨作品 61 位的 `home_world` 由 `dark` 改为 `foreign`：'
                           u'`light/dark` 是 Deltarune 语汇（暗之泉那一侧），UT 的地下'
                           u'世界与 OneShot 的城市都不是"暗世界"；第66轮写 `dark` 是借用'
                           u'（当时世界模型只有两分）。★ 这不改变运行时行为 —— 拦人的是 '
                           u'`escape_via_bubble`，不是 `home_world`（第71轮实证）。',
            'light_side_note': u'光世界一侧**不用改**：`light_needs_bubble` 只认 '
                               u'`is_dark_only`，跨作品角色从来不在其中 ⇒ 他们本来就能进光世界。',
        },

        # ---------------- ② 同名角色（共存 / 相认）----------------
        'twin_groups': {
            'status': 'spec_only',
            'why': u'「各个世界观里有重复的角色，我要求他们能够共存」+「面对不同版本的'
                   u'自己熟悉的会更快……他们四个会熟悉的很快」',
            'rule': u'同名 ≠ 同一人。组内**同属 UT 衍生家族**（ut/hy/ot）的才是'
                    u'"另一个版本的我"；Deltarune 与 OneShot 的人只能算同名。',
            'au_family': list(AU_FAMILY),
            'au_family_why': u'Outertale 与黄魂（Undertale Yellow）都是《Undertale》的'
                             u'同人衍生作品；OneShot 是独立作品，不在家族内。',
            'count': len(twins),
            'groups': twins,
        },

        # ---------------- ③ 无身份标识 ----------------
        'identity_blind': {
            'status': 'spec_only',
            'why': u'「怪物们之间没有身份标识说，你是哪个世界观的，所以那需要自己判断，'
                   u'而非每次都精准的知道那是哪个人」',
            'rule': u'相遇时**不注入**对方的作品归属与版本；只知道"他长这样、他这么说话"。',
            'injected': [u'对方的显示名（他自己说的 / 别人叫的）', u'对方此刻的样子（贴图）'],
            'not_injected': [u'对方来自哪个作品', u'对方是哪个版本', u'对方的 npc id',
                             u'对方人设文件里的任何内容'],
            'how_to_judge': u'从对话里推断：口癖、称呼、提到的人与地。这正是 AI 该干的活，'
                            u'也是"像人"的地方 —— 精准知道反而假。',
        },

        # ---------------- ④ 熟络初值（循序渐熟）----------------
        'familiarity_seed': {
            'status': 'spec_only',
            'why': u'「不同世界的人一开始也不认识……循序渐进的熟悉起来，当然，面对不同'
                   u'版本的自己熟悉的会更快」',
            'seed_values': {
                'same_au_twin': 0.55,
                'same_production': 0.30,
                'stranger': 0.0,
            },
            'rule': u'初见一律低；同 AU 版本的"另一个我"起手最高（"我认得你，但你不是他"）；'
                    u'同一作品内的人次之；跨作品陌生人从 0 开始。',
            'growth': u'靠相处累加（同处一室 / 互动），**不是一次到位**；'
                      u'与 `_placement.json` 的 `rules.bond_scope`（结对只在同场景生效）同源。',
        },

        # ---------------- ⑤ 对场景有反应 ----------------
        'scene_traits': {
            'status': 'spec_only',
            'why': u'「他们是能对场景有反应的，比如sans来到oneshot会吐槽，这地方真黑之类的话'
                   u'（当然，不止黑，破败这类的词也需要有能力识别）」',
            'traits': [
                {'id': 'dark', 'words': [u'黑', u'暗', u'没有光', u'伸手不见五指'],
                 'sample': u'这地方真黑'},
                {'id': 'ruined', 'words': [u'破败', u'荒废', u'废墟', u'残破', u'没人住'],
                 'sample': u'这里像是很久没人来过了'},
                {'id': 'bright', 'words': [u'亮', u'明亮', u'刺眼'], 'sample': None},
                {'id': 'crowded', 'words': [u'人多', u'热闹', u'挤'], 'sample': None},
                {'id': 'quiet', 'words': [u'安静', u'死寂', u'没声音'], 'sample': None},
                {'id': 'cosmic', 'words': [u'宇宙', u'星空', u'失重', u'太空'],
                 'sample': u'……这比我想的还要高'},
            ],
            'how': u'场景侧给 traits，NPC 侧据 traits + 自己的人设生成反应。'
                   u'★ traits 的**来源**本轮未定（候选：背景图亮度 / 房间资源名语义），'
                   u'不猜、不先写死一个会撒谎的推断器。',
        },

        # ---------------- ⑥ 访客兼容（用户本轮强调）----------------
        'visitor': {
            'status': 'spec_only',
            'why': u'「对了做好不同世界的角色在不同世界的兼容性哦」',
            'rule': u'跨作品角色在**非自己作品**的场景里以「访客」身份出现：'
                    u'没有原作站位 ⇒ 不硬编坐标；台词不假设自己熟悉此地。',
            'unplaced_policy': u'61 位跨作品 + knight 共 62 位保持 `_placement.json` 的 '
                               u'`unplaced`，**不编坐标**（沿用第44轮口径：缺依据就如实缺着）。',
            'works_today': [
                u'门控：能进哪些世界（本轮，wired）',
                u'人设：76 份 persona 文件在位（第64/69轮）',
                u'贴图：四作 529 张已落地（第71轮）',
            ],
            'not_yet': [
                u'跨作品作品的**场景**还没进 `assets/scenes/_index.json`'
                u'（目前只有 desktop + ch1~ch5）⇒ 他们眼下只能出现在 Deltarune 的场景里',
                u'没有站位 ⇒ 需要一个"访客落点"策略（跟随落点 / 场景入口落点）',
                u'访客台词模板（"我不太熟这里"）尚未接入对话层',
            ],
        },

        # ---------------- ⑦ 接线台账（★ 诚实判据的真源）----------------
        'wiring': {
            'wired': ['roam'],
            'spec_only': ['twin_groups', 'identity_blind', 'familiarity_seed',
                          'scene_traits', 'visitor'],
            'not_yet': [
                u'同名相认：`twin_groups` 只有数据，没有接进对话层（相遇时该怎么开口）',
                u'无身份标识：需要改 `npc_persona` 的 system 拼装（**不注入**对方作品归属）',
                u'熟络初值：需要一个 per-pair 的 familiarity 存储（现在只有 per-npc 记忆）',
                u'场景反应：traits 的来源（亮度 / 资源名语义）未定',
                u'访客兼容：跨作品场景未接入 + 访客落点策略未做',
                u'自由生活（私下闲聊、传播信息、不以用户发起为起点）= 轮次 73',
            ],
            'honesty_note': u'写 `spec_only` 是刻意的 —— 本项目最贵的坑就是'
                            u'「函数写对了 != 产品用上了」。',
        },
    }

    print('== 跨世界契约 ==')
    print('  roam        : %s  scope=%s  all=%s'
          % (out['roam']['status'], json.dumps(out['roam']['counts'], ensure_ascii=False),
             out['roam']['all_ids']))
    print('  twin_groups : %d 组（%s）'
          % (len(twins), ', '.join(g['name'] for g in twins)))
    print('  含 AU 关系的组 = %d' % sum(1 for g in twins if g['has_au']))
    print('  spec_only   : %s' % ', '.join(out['wiring']['spec_only']))
    if not write:
        print('  (dry run —— 加 --write 才落盘)')
        return 0
    with io.open(DST, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
        fh.write(u'\n')
    print('-> %s (%d bytes)' % (DST, os.path.getsize(DST)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
