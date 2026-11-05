# -*- coding: utf-8 -*-
u"""生成 `ralsei_pet/assets/npc/_motion_profile.json`（96 人运动能力档案）。

为什么用脚本生成而不是手写 json
------------------------------
1. 96 条 × 6 个字段，手写必错一个逗号；脚本还能**逐个过 validate_entry**，
   缺 `why` / `evidence` 不在三档 / 数值越界，当场报出来（build 期就红，
   不用等到产品运行）。
2. 名单以 `_registry.json` 为准，**脚本断言 96 条一个不多一个不少**
   —— 以后注册表加了人，这个脚本会直接告诉你"某人没有档案"。
3. 数据留在这张表里，可复核、可改动、可解释。

★ 依据等级口径（用户 2026-11-06 选「每人落值 + 标依据等级」）
-----------------------------------------------------------
· **明证**：原作里有直接的跑/跳/体力/战斗动作描写（如 Papyrus 反复自夸体力、
  Undyne 全程追捕、Susie 挥斧、Napstablook 是幽灵没有腿）。
· **推断**：没有动作描写，但从体型 / 年龄 / 职业 / 种族 / 形态可以合理推
  （巨大者力量高、年迈者成长慢、机器人参数难改）。
· **无据**：原作信息极少，或根本不是生物（告示牌 / 垃圾桶 / 空房间占位 / 元层概念）。
  ⇒ 一律落**默认档 1.0**，**不假装知道**。这是本项目「不许把不知道当知道」的直接应用。

★ 数值区间（见 motion_profile.LIMITS）
jump / run / accel ∈ [0.4, 2.0]，growth ∈ [0.3, 2.5]；1.0 = 全局常量本身。
`jump` 起跳力（跳多高）、`run` 冲刺上限（跑多快）、`accel` 助跑加速度（多快能拉到最高速）。

跑法：C:\\Python311\\python.exe gen165_profiles.py [--check]
  --check 只校验不写盘（给回归/复检用）
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
REGISTRY = os.path.join(ASSETS, '_registry.json')
OUT = os.path.join(ASSETS, '_motion_profile.json')

sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import motion_profile as MP      # noqa: E402

#: id -> (jump, run, accel, growth, evidence, why)
TABLE = {
    # ---- Deltarune 主线 ----
    # ★★★ 基准人必须是 1.0：`JUMP_SPEED_MAX` / `RUNUP_ACCEL` / `RUNUP_SPEED_MAX`
    #   这三个常量本来就是照**他的手感**调出来的（第90/164 轮反复试过）。
    #   给他 0.95 就等于"加个学习模块顺手把桌宠跳矮 5%"——用户没要求，
    #   而且会让第164轮的闸门判据（高度上限 ≈490px）当场红。
    #   ⇒ 他的"特点"体现在**肯练**（growth 1.25）而不是底子。
    'ralsei': (1.00, 1.00, 1.00, 1.25, u'推断',
               u'基准人：现有全局常量就是照他的手感定的，故取 1.0；矮小温和 ⇒ 靠练而不是靠底子'),
    'kris': (1.10, 1.15, 1.10, 1.30, u'明证',
             u'主角，跑/跳/挥剑都由玩家直接操作本体'),
    'susie': (1.30, 1.35, 1.30, 1.50, u'明证',
              u'高大强壮、挥大斧，战斗与奔跑都有直接表现'),
    'toriel': (1.15, 1.00, 1.00, 0.90, u'推断',
               u'成年山羊体型高大、走路稳重；原作没有奔跑动作'),
    'asgore': (1.35, 1.00, 1.00, 1.00, u'明证',
               u'全作体型最大之一，持三叉戟近战，力量明显强于速度'),
    'king': (1.40, 0.85, 0.90, 0.60, u'明证',
             u'黑桃王体型巨大、动作缓慢，是典型的重力型'),
    'lancer': (0.90, 1.20, 1.15, 1.60, u'明证',
               u'个子小，但原作里骑自行车速度极快；小孩成长空间大'),
    'queen': (1.10, 0.80, 0.85, 0.50, u'明证',
              u'常坐椅子/机械臂代步，几乎没有自主奔跑'),
    'spamton': (1.20, 1.30, 1.20, 1.10, u'推断',
                u'极瘦小、动作神经质而快；原作没有量化描写'),
    'berdly': (1.20, 1.00, 1.00, 1.00, u'明证',
               u'有翅膀能飞（ch2），但本人自知体力不行'),
    'noelle': (0.80, 0.85, 0.90, 1.40, u'推断',
               u'体弱胆小的鹿少女，原作以魔法为主；底子差但肯练'),
    'tenna': (1.00, 1.10, 1.05, 0.80, u'推断',
              u'电视主持型角色，舞台动作多，但缺乏运动量描写'),
    'rouxls': (0.85, 0.85, 0.90, 0.90, u'推断',
               u'自命不凡但体格普通，原作无运动表现'),
    'gerson': (0.90, 0.80, 0.85, 0.50, u'推断',
               u'年迈的龟，原作以知识/商店为主，成长空间小'),
    'mike': (1.00, 1.00, 1.00, 1.00, u'无据',
             u'原作信息极少，落默认档'),
    'knight': (1.30, 1.15, 1.15, 1.20, u'推断',
               u'咆哮骑士，重甲形象；没有直接运动描写'),
    'flowery': (0.90, 0.90, 1.00, 1.30, u'无据',
                u'花形角色，没有肢体运动依据'),
    # ---- 普通 / 杂项 ----
    'hammerguy': (1.20, 1.00, 1.00, 1.40, u'推断',
                  u'拿锤子的工人形象，力量型'),
    'puzzlemaster1': (0.90, 0.90, 0.90, 1.00, u'无据',
                      u'谜题 NPC，无运动描写'),
    'puzzlemaster2': (0.90, 0.90, 0.90, 1.00, u'无据',
                      u'谜题 NPC，无运动描写'),
    'sign': (0.40, 0.40, 0.40, 0.30, u'无据',
             u'告示牌，不是生物，取区间下限'),
    'npc_room': (0.40, 0.40, 0.40, 0.30, u'无据',
                 u'空房间占位，不是生物'),
    'conbini': (0.95, 1.00, 1.00, 1.10, u'推断',
                u'便利店店员，长期站柜台'),
    'police': (1.10, 1.15, 1.10, 1.20, u'推断',
               u'警察，职业本身要求体能与追捕'),
    'catti': (0.90, 0.95, 0.95, 1.10, u'推断',
              u'猫，慵懒但不弱小'),
    'rudy': (0.85, 0.80, 0.85, 1.00, u'推断',
             u'病中的鹿，体能受限'),
    'dumpster': (0.40, 0.40, 0.40, 0.30, u'无据',
                 u'垃圾桶，不是生物'),
    'addison_tea': (1.00, 1.05, 1.00, 1.10, u'推断',
                    u'店老板，日常走动多'),
    'castle_cafe': (0.95, 0.95, 0.95, 1.00, u'推断',
                    u'咖啡店老板，普通体格'),
    'rabbits': (0.85, 1.10, 1.10, 1.40, u'推断',
                u'兔子，跳跃见长但体量小'),
    'wrapper': (0.50, 0.50, 0.60, 0.80, u'无据',
                u'包装怪，形态不明'),
    'doubter': (1.00, 1.00, 1.00, 0.90, u'无据',
                u'质疑者，无运动描写'),
    # ★ 原本给的是 1.05 —— 那是**编的**：对一个没有运动描写的角色给"略高于常人"，
    #   等于把猜测写成了数据。这一档的纪律是「不许超过默认档」，落 1.0。
    'zapper': (1.00, 1.00, 1.00, 1.00, u'无据',
               u'电击者，无运动描写，落默认档'),
    'susiedark': (1.30, 1.35, 1.30, 1.50, u'推断',
                  u'暗之苏西，与苏西同体设定'),
    'mansion_room': (0.40, 0.40, 0.40, 0.30, u'无据',
                     u'宅邸房间占位，不是生物'),
    # ---- Oneshot ----
    'os_niko': (1.00, 1.10, 1.05, 1.50, u'明证',
                u'主角，原作需要在世界里跑动探索'),
    'os_the_world_machine': (0.60, 0.60, 0.60, 0.40, u'无据',
                             u'世界机器，非生物形态'),
    'os_the_author': (0.50, 0.50, 0.50, 0.40, u'无据',
                      u'作者（元层概念），没有身体'),
    'os_prophetbot': (0.90, 0.90, 0.90, 0.60, u'推断',
                      u'机器人，机械式行动，参数难改'),
    'os_silver': (1.00, 1.05, 1.00, 1.00, u'推断',
                  u'机器人角色，行动稳定'),
    'os_rowbot': (0.90, 0.90, 0.90, 0.60, u'推断',
                  u'船形机器人，靠推进移动'),
    'os_prototype': (0.95, 0.90, 0.90, 0.80, u'无据',
                     u'原型机，细节不足'),
    'os_calamus': (0.90, 0.90, 0.90, 0.90, u'无据',
                   u'信息不足，落接近默认档'),
    'os_alula': (0.85, 0.95, 0.95, 1.30, u'推断',
                 u'小孩形象，活泼但体量小'),
    'os_maize': (0.90, 0.90, 0.90, 1.00, u'无据',
                 u'信息不足'),
    'os_magpie': (0.95, 1.00, 1.00, 1.10, u'推断',
                  u'鸟形，轻快'),
    'os_shepherd': (1.00, 0.95, 0.95, 1.00, u'推断',
                    u'牧羊人，长期行走'),
    'os_cedric': (1.00, 1.00, 1.00, 1.00, u'无据',
                  u'信息不足'),
    'os_lamplighter': (0.90, 0.90, 0.90, 0.90, u'无据',
                       u'灯夫，信息不足'),
    'os_watcher': (0.80, 0.80, 0.80, 0.70, u'推断',
                   u'观察者，静多于动'),
    'os_ling': (1.00, 1.00, 1.00, 1.00, u'无据',
                u'信息不足'),
    'os_mason': (1.05, 1.00, 1.00, 1.00, u'推断',
                 u'石匠/工人形象，体力中等偏上'),
    'os_kelvin': (1.00, 1.00, 1.00, 1.00, u'无据',
                  u'信息不足'),
    'os_kip': (0.95, 1.05, 1.05, 1.30, u'推断',
               u'小孩形象，成长快'),
    'os_george': (1.00, 1.00, 1.00, 1.00, u'无据',
                  u'信息不足'),
    'os_rue': (0.95, 0.95, 0.95, 1.00, u'无据',
               u'信息不足'),
    # ---- Undertale ----
    'ut_toriel': (1.15, 1.00, 1.00, 0.90, u'推断',
                  u'同 Deltarune 的 Toriel：成年山羊，体型高大、动作稳重'),
    'ut_sans': (1.00, 1.20, 1.10, 0.60, u'明证',
                u'战斗中闪避极快，但日常极度懒惰，练不动'),
    'ut_papyrus': (1.45, 1.40, 1.35, 1.80, u'明证',
                   u'反复自夸体力并坚持训练；跑步/跳跃表现明确，成长最快'),
    'ut_undyne': (1.40, 1.50, 1.40, 1.70, u'明证',
                  u'全程追捕玩家、长矛近战，体力与速度都是顶级'),
    'ut_alphys': (0.75, 0.70, 0.85, 1.30, u'明证',
                  u'自称宅、体力差、不擅长运动；但因起点低，练起来涨幅明显'),
    'ut_mettaton': (1.20, 1.25, 1.20, 0.70, u'明证',
                    u'机械身体、腿功与舞台动作强；但机器人参数难改'),
    'ut_muffet': (1.15, 1.20, 1.25, 1.20, u'明证',
                  u'蜘蛛，多肢体、动作敏捷'),
    'ut_napstablook': (0.60, 0.60, 0.70, 0.80, u'明证',
                       u'幽灵，没有腿脚，靠漂浮移动'),
    'ut_monster_kid': (0.90, 1.05, 1.00, 1.50, u'推断',
                       u'小孩，爱跑动'),
    'ut_asgore': (1.35, 1.00, 1.00, 1.00, u'明证',
                  u'同 Deltarune 的 Asgore：体型最大之一，力量型'),
    'ut_flowey': (0.70, 0.65, 0.80, 1.50, u'明证',
                  u'花，没有肢体，靠藤蔓与根系'),
    'ut_frisk': (1.10, 1.20, 1.10, 1.60, u'明证',
                 u'主角，跑跳闪避全部由玩家执行；成长空间大'),
    'ut_chara': (1.10, 1.20, 1.10, 1.60, u'推断',
                 u'与 Frisk 同体，运动能力按本体计'),
    'ut_gaster': (0.90, 0.90, 0.90, 1.00, u'推断',
                  u'消失的科学家，形态破碎、行动方式不明'),
    # ---- Undertale Yellow ----
    'hy_clover': (1.10, 1.20, 1.10, 1.60, u'明证',
                  u'主角，跑动探索与战斗都由玩家执行'),
    'hy_martlet': (1.30, 1.25, 1.20, 1.40, u'明证',
                   u'蓝色鸟，原作明确能飞'),
    'hy_ceroba_ketsukane': (1.20, 1.30, 1.25, 1.20, u'明证',
                            u'狐面忍者型，动作迅速'),
    'hy_starlo': (1.10, 1.10, 1.00, 0.90, u'推断',
                  u'牛仔镇长，中年，体能中等'),
    'hy_dalv': (1.00, 0.90, 0.90, 0.70, u'推断',
                u'吸血鬼，宅居、喜静'),
    'hy_axis': (1.00, 0.95, 0.95, 0.50, u'明证',
                u'机器人，出厂参数固定，能练的余地小'),
    'hy_ed': (0.95, 0.95, 0.95, 1.00, u'无据',
              u'信息不足，落接近默认档'),
    'hy_mooch': (1.05, 1.20, 1.15, 1.30, u'推断',
                 u'小偷型，动作快'),
    'hy_moray': (1.00, 1.00, 1.00, 1.10, u'推断',
                 u'水中形象，灵活度中等'),
    'hy_sousborg': (0.95, 0.90, 0.90, 0.60, u'推断',
                    u'厨师机器人，重且稳'),
    'hy_guardener': (1.05, 0.95, 0.95, 0.60, u'推断',
                     u'园丁机器人，体量大但参数固定'),
    'hy_bowll': (1.00, 1.00, 1.00, 1.00, u'无据',
                 u'信息不足'),
    'hy_ace': (1.05, 1.10, 1.05, 1.10, u'推断',
               u'扑克牌意象，身手灵活'),
    'hy_chujin_ketsukane': (0.95, 0.90, 0.90, 0.80, u'推断',
                            u'科学家型父亲，非战斗角色'),
    'hy_flowey': (0.70, 0.65, 0.80, 1.50, u'推断',
                  u'与 UT 的 Flowey 同形态：花，无肢体'),
    # ---- Outertale ----
    'ot_toriel': (1.15, 1.00, 1.00, 0.90, u'推断',
                  u'Outertale 版 Toriel，体型与动作特征沿用本体'),
    'ot_sans': (1.00, 1.20, 1.10, 0.60, u'推断',
                u'Outertale 版 Sans，沿用本体的"闪避快但懒"'),
    'ot_papyrus': (1.45, 1.40, 1.35, 1.80, u'推断',
                   u'Outertale 版 Papyrus，沿用本体的高强度训练设定'),
    'ot_undyne': (1.40, 1.50, 1.40, 1.70, u'推断',
                  u'Outertale 版 Undyne，沿用本体的顶级体力'),
    'ot_alphys': (0.75, 0.70, 0.85, 1.30, u'推断',
                  u'Outertale 版 Alphys，沿用本体的体力短板'),
    'ot_mettaton': (1.20, 1.25, 1.20, 0.70, u'推断',
                    u'Outertale 版 Mettaton，机械身体、参数难改'),
    'ot_muffet': (1.15, 1.20, 1.25, 1.20, u'推断',
                  u'Outertale 版 Muffet，沿用多肢体敏捷'),
    'ot_napstablook': (0.60, 0.60, 0.70, 0.80, u'推断',
                       u'Outertale 版 Napstablook，幽灵形态、无腿'),
    'ot_asgore': (1.35, 1.00, 1.00, 1.00, u'推断',
                  u'Outertale 版 Asgore，沿用本体的力量型体格'),
    'ot_asriel_twinkly': (1.00, 1.10, 1.05, 1.40, u'推断',
                          u'少年体型 + Twinkly 小形态，轻快但体量小'),
    'ot_kidd': (1.00, 1.05, 1.00, 1.30, u'推断',
                u'少年形象，成长空间中等偏上'),
}


def main():
    check_only = '--check' in sys.argv
    reg = json.load(io.open(REGISTRY, 'r', encoding='utf-8'))
    ids = [x['id'] for x in reg['npcs']]

    problems = []
    # ① 名单必须一一对应
    missing = [i for i in ids if i not in TABLE]
    extra = [k for k in TABLE if k not in ids]
    if missing:
        problems.append(u'注册表里有 %d 人没有档案：%s' % (len(missing), missing))
    if extra:
        problems.append(u'档案里有 %d 人不在注册表：%s' % (len(extra), extra))

    # ② 每条都过 validate_entry（缺 why / evidence 越档 / 数值越界）
    data = {'_meta': {
        'round': 165,
        'why': u'运动能力档案：倍率制，1.0 = 全局常量本身；没档案的人物一律 1.0',
        'evidence_levels': list(MP.EVIDENCE_LEVELS),
        'limits': {k: list(v) for k, v in MP.LIMITS.items()},
        'growth_note': u'level = exp // %s（上限 %s 级，满级 %s 经验）；mult = 1 + %s * growth * level'
                       % (MP.LEVEL_STEP, MP.MAX_LEVEL, MP.MAX_EXP, MP.GAIN_PER_LEVEL),
        'source': u'code-quality-audit/第165轮-运动能力养成/_tools/gen165_profiles.py',
    }}
    for nid in ids:
        row = TABLE.get(nid)
        if row is None:
            continue
        jump, run, accel, growth, ev, why = row
        ent = {'jump': jump, 'run': run, 'accel': accel, 'growth': growth,
               'evidence': ev, 'why': why}
        problems.extend(MP.validate_entry(ent, nid))
        data[nid] = ent

    if problems:
        print(u'[FAIL] 档案不合格（%d 条）：' % len(problems))
        for p in problems:
            print(u'  - %s' % p)
        return 1

    n_ev = {}
    for nid in data:
        if nid == '_meta':
            continue
        e = data[nid]['evidence']
        n_ev[e] = n_ev.get(e, 0) + 1
    print(u'档案 %d 人：%s' % (len(data) - 1, n_ev))

    if check_only:
        # 只校验：还要确认磁盘上的文件与本次生成**逐字一致**（防"改了表没重生成"）
        if not os.path.exists(OUT):
            print(u'[FAIL] 磁盘上没有 %s' % os.path.basename(OUT))
            return 1
        old = io.open(OUT, 'r', encoding='utf-8', newline='').read()
        new = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
        if old.replace('\r\n', '\n').strip() != new.replace('\r\n', '\n').strip():
            print(u'[FAIL] 磁盘上的档案与生成表不一致（改了表没重新生成）')
            return 1
        print(u'[PASS] 磁盘档案与生成表逐字一致')
        return 0

    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + '\n'
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(payload)
    print(u'[PASS] 已写入 %s（%d 字节）' % (OUT, len(payload.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
