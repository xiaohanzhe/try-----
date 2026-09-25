# -*- coding: utf-8 -*-
"""第49轮 · 生成 `ralsei_pet/assets/npc/_registry.json` 与 `_dialogue.json`。

* 主线 NPC 名单（tier=main / model=4B / needs_setting=True）＝**基于本轮原作取证**
  （`_evidence/names49/ch*_hits.txt` 的 OBJ 名），用户据此提供设定。
* 纯 NPC（tier=plain）＝ 内置 4~10 句对话，内容由本项目撰写（不走模型）。

用法: C:\\Python311\\python.exe gen_npc49.py
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
DST = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')

# ---------------------------------------------------------------- 主线 NPC（4B）
# needs_setting=True ⇒ 等用户提供设定；objects 一律是**本轮反编译查到的真实物件名**
MAIN = [
    dict(id='toriel', name='Toriel', name_cn='托丽尔', chapters=['ch1', 'ch2', 'ch3', 'ch4', 'ch5'],
         home_world='light', objects=['obj_npc_toriel'],
         notes='光世界的母亲，五章都有戏份；照顾者，口吻温和但会唠叨。'),
    dict(id='asgore', name='Asgore', name_cn='艾斯戈尔', chapters=['ch5'],
         home_world='light', objects=['obj_ch5_DW30_asgore', 'obj_dw_fcastle_asgore',
                                      'obj_town_north_asgore'],
         notes='五章才正式登场；温和、笨拙、有心事的花店老板。'),
    dict(id='king', name='King', name_cn='黑桃王', chapters=['ch1', 'ch2', 'ch3'],
         home_world='dark', objects=['obj_king_boss', 'obj_npc_king'],
         notes='ch1 的 Boss，傲慢、威严；后续以被关押/旁白形象出现。'),
    dict(id='lancer', name='Lancer', name_cn='兰瑟', chapters=['ch1', 'ch2', 'ch3', 'ch4'],
         home_world='dark', objects=['obj_darklancer', 'obj_lancerboss', 'obj_lancerboss2',
                                     'obj_lancerboss3', 'obj_b1lancer'],
         notes='黑桃王之子；自称"坏蛋"，其实是好孩子。★ 他也能进球，但**不能脱下**。'),
    dict(id='queen', name='Queen', name_cn='女王', chapters=['ch2', 'ch4'],
         home_world='dark', objects=['obj_queen_social_media', 'obj_room_castle_queen'],
         notes='ch2 的 Boss；机械、夸张、口癖是"哦呵呵"。'),
    dict(id='spamton', name='Spamton', name_cn='斯帕姆顿', chapters=['ch2'],
         home_world='dark', objects=['obj_spamton_enemy', 'obj_spamton_neo_enemy'],
         notes='ch2 的隐藏 Boss；推销员口吻，全大写，神经质。'),
    dict(id='berdly', name='Berdly', name_cn='伯德利', chapters=['ch2', 'ch5'],
         home_world='dark', objects=['obj_berdlyb_enemy', 'obj_berdlyb2_enemy',
                                     'obj_town_north_berdly'],
         notes='自命不凡的优等生；爱说大词，其实很在意朋友。'),
    dict(id='noelle', name='Noelle', name_cn='诺艾尔', chapters=['ch2', 'ch4', 'ch5'],
         home_world='light', objects=['obj_heronoelle', 'obj_noellehouse_noelle'],
         notes='胆小的驯鹿女孩；后来变得坚强。'),
    dict(id='tenna', name='Tenna', name_cn='天娜', chapters=['ch3', 'ch4'],
         home_world='dark', objects=['obj_actor_tenna', 'obj_tenna_enemy'],
         notes='ch3 的 Boss；电视综艺主持人式的高能量口吻。'),
    dict(id='rouxls', name='Rouxls Kaard', name_cn='鲁尔斯·卡德', chapters=['ch3'],
         home_world='dark', objects=['obj_rouxls_yarnball'],
         notes='自封的"谜题公爵"；古英语腔的滑稽反派。'),
    dict(id='gerson', name='Gerson', name_cn='格森', chapters=['ch4'],
         home_world='dark', objects=['obj_npc_gerson', 'obj_dw_church_gerson_follow'],
         notes='老当益壮的老人；原作里唯一的暗世界 NPC 跟随者。'),
    dict(id='mike', name='Mike', name_cn='迈克', chapters=['ch4', 'ch5'],
         home_world='dark', objects=['obj_mike', 'obj_mike_battle', 'obj_mike_lancer'],
         notes='ch4 的对手/主持人；浮夸的节目腔。'),
    dict(id='knight', name='Roaring Knight', name_cn='咆哮骑士', chapters=['ch3', 'ch4'],
         home_world='dark', objects=['obj_knight_enemy', 'obj_ch4_DCA01_roaringknight'],
         notes='主线反派；不说话/极少说话，压迫感来自沉默。'),
    dict(id='flowey', name='Flowey', name_cn='小花', chapters=['ch5'],
         home_world='dark', objects=['obj_flowery_throwkris', 'obj_flowery_kristhrown'],
         notes='ch5 的 Boss；甜腻的恶意。'),
]

# ---------------------------------------------------------------- 纯 NPC（内置对话）
PLAIN = [
    dict(id='hammerguy', name='Hammer Guy', name_cn='锤子哥', chapters=['ch1', 'ch2'],
         objects=['obj_npc_hammerguy'],
         lines=['嘿！别站那儿，小心我锤子抡到你。',
                '这地方以前挺安静的，现在全是响声。',
                '你要是看见我的工具箱，记得喊我一声。',
                '锤一下不行？那就锤两下。']),
    dict(id='puzzlemaster1', name='Puzzle Master', name_cn='谜题大师·甲', chapters=['ch1'],
         objects=['obj_npc_puzzlemaster1'],
         lines=['哦？有人来解谜了？',
                '我出的题，我自己都答不上来。',
                '别按那个按钮——好吧，你按了。',
                '下次给你出个简单点的。']),
    dict(id='puzzlemaster2', name='Puzzle Master', name_cn='谜题大师·乙', chapters=['ch1'],
         objects=['obj_npc_puzzlemaster2'],
         lines=['规则很简单：别踩红的。',
                '……好吧，红的就是整块地板。',
                '你已经很努力了。',
                '我看着都替你紧张。']),
    dict(id='sign', name='Sign', name_cn='告示牌', chapters=['ch1', 'ch2', 'ch3'],
         objects=['obj_npc_sign'],
         lines=['（牌子上写着：前方请勿奔跑。）',
                '（牌子背面画着一个箭头。）',
                '（有人用粉笔补了一句：跑也没关系。）',
                '（还有一行小字：摔了别找我。）']),
    dict(id='npc_room', name='???', name_cn='空房间', chapters=['ch1'],
         objects=['obj_npc_room', 'obj_npc_room_animated'],
         lines=['这间屋子什么都没有。',
                '什么都没有，也是一种有。',
                '你可以在这儿站一会儿。',
                '反正也没人赶你。']),
    dict(id='conbini', name='Shopkeeper', name_cn='便利店店员', chapters=['ch2'],
         objects=['obj_npc_conbini'],
         lines=['欢迎光临——哦，是你啊。',
                '今天的关东煮还热着。',
                '要袋子吗？……不要也行。',
                '下次再来。']),
    dict(id='police', name='Officer', name_cn='警察', chapters=['ch2'],
         objects=['obj_npc_police'],
         lines=['站住！……哦，是小朋友。',
                '天黑之前回家。',
                '最近这片儿不太平。',
                '注意安全。']),
    dict(id='catti', name='Catti', name_cn='卡蒂', chapters=['ch2'],
         objects=['obj_npc_catti'],
         lines=['喵——我是说，你好。',
                '你刚才是不是看我了？',
                '算了，看就看吧。',
                '……喵。']),
    dict(id='rudy', name='Rudy', name_cn='鲁迪', chapters=['ch2'],
         objects=['obj_npc_rudy'],
         lines=['孩子，你看起来跑了不少路。',
                '歇会儿吧，我不着急。',
                '路还长着呢。',
                '记得吃饭。']),
    dict(id='dumpster', name='Dumpster', name_cn='垃圾桶', chapters=['ch2'],
         objects=['obj_npc_dumpster'],
         lines=['（垃圾桶里传来轻微的响声。）',
                '（你往里看了一眼，什么也没有。）',
                '（它似乎不太欢迎你。）',
                '（还是走开吧。）']),
    dict(id='addison_tea', name='Addison', name_cn='艾迪森', chapters=['ch2'],
         objects=['obj_npc_addison_tea'],
         lines=['来杯茶吗？今天特调。',
                '喝了会让人放松——也可能只是烫。',
                '别急，慢慢来。',
                '要不要再来一杯？']),
    dict(id='castle_cafe', name='Cafe Owner', name_cn='咖啡店老板', chapters=['ch5'],
         objects=['obj_npc_castle_cafe', 'obj_npc_cafe'],
         lines=['咖啡还是热可可？',
                '小孩子就别喝黑咖啡了。',
                '我给你加了两块棉花糖。',
                '慢慢喝。']),
    dict(id='rabbits', name='Rabbits', name_cn='兔子们', chapters=['ch5'],
         objects=['obj_npc_rabbits'],
         lines=['（一群兔子安静地看着你。）',
                '（其中一只挪了挪位置。）',
                '（然后它们都不动了。）',
                '（像什么也没发生过。）']),
    dict(id='wrapper', name='Wrapper', name_cn='包装怪', chapters=['ch5'],
         objects=['obj_npc_wrapper'],
         lines=['沙沙沙……', '别踩我。',
                '我只是想找个地方待着。', '沙沙。']),
    dict(id='doubter', name='Doubter', name_cn='质疑者', chapters=['ch5'],
         objects=['obj_npc_doubter'],
         lines=['你确定这些都是真的？',
                '我看未必。',
                '不过……也许吧。',
                '算了，你走吧。']),
    dict(id='zapper', name='Zapper', name_cn='电击者', chapters=['ch4'],
         objects=['obj_npc_zapper', 'obj_npc_castle_tutorial_zapper'],
         lines=['别碰我，噼里啪啦的。',
                '我不是故意的。',
                '离远点就好。',
                '……谢谢。']),
    dict(id='susiedark', name='Susie?', name_cn='暗之苏西', chapters=['ch1', 'ch2', 'ch3'],
         objects=['obj_npc_susiedark'],
         lines=['看什么看。', '……哼。',
                '你要走就快点。', '别磨蹭。']),
    dict(id='mansion_room', name='Room Note', name_cn='宅邸房间', chapters=['ch2'],
         objects=['obj_npc_mansion_room'],
         lines=['（房间里落着一层灰。）',
                '（桌上有半杯凉掉的水。）',
                '（窗外的雨还在下。）',
                '（没有人回来过。）']),
]

MODEL_MAIN = 'ralsei-npc:4b'


def safe_write(path, text, tries=6):
    import time
    for _ in range(tries):
        try:
            with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            return True
        except OSError:
            time.sleep(0.4)
    return False


def npc_rec(d, tier):
    r = {
        'id': d['id'], 'name': d['name'], 'name_cn': d['name_cn'], 'tier': tier,
        'chapters': d['chapters'],
        'home_world': d.get('home_world', 'dark'),
        'objects': d['objects'],
        'model': MODEL_MAIN if tier == 'main' else None,
        'needs_setting': tier == 'main',
        'escape_via_bubble': d['id'] == 'ralsei',
        'notes': d.get('notes', ''),
    }
    return r


def main():
    npcs = [npc_rec(d, 'main') for d in MAIN] + [npc_rec(d, 'plain') for d in PLAIN]
    # Ralsei 本人也是"不可脱离暗世界"的暗世界居民 ⇒ 登记成主线条目供门控用
    npcs.insert(0, {
        'id': 'ralsei', 'name': 'Ralsei', 'name_cn': '雷尔赛', 'tier': 'main',
        'chapters': ['ch1', 'ch2', 'ch3', 'ch4', 'ch5'], 'home_world': 'dark',
        'objects': ['obj_heroralsei'], 'model': MODEL_MAIN, 'needs_setting': True,
        'escape_via_bubble': True,
        'notes': '主角团成员，但同时是暗世界居民 ⇒ 受"不可脱离暗世界"约束；'
                 '唯一豁免 = 第49轮的扭蛋球容器。',
    })
    reg = {
        'schema_version': 1,
        'source': '第49轮 UTMT 反编译（names49 普查）+ 本项目撰写',
        'tiers': {
            'main': '主线 NPC：非主角团但有重大影响（Toriel/Asgore/各章 Boss/少数关键角色）；'
                    '配 4B 模型，设定由用户提供。',
            'plain': '纯 NPC：没有重大帮助对话；用 4~10 句内置对话，不走模型。',
        },
        'counts': {'main': sum(1 for r in npcs if r['tier'] == 'main'),
                   'plain': sum(1 for r in npcs if r['tier'] == 'plain')},
        'npcs': npcs,
    }
    dia = {
        'schema_version': 1,
        'source': '本项目撰写（用户口径：纯 NPC 4~10 句内置对话，自己写就行）',
        'lines': {d['id']: d['lines'] for d in PLAIN},
    }
    if not os.path.isdir(DST):
        os.makedirs(DST)
    rp = os.path.join(DST, '_registry.json')
    dp = os.path.join(DST, '_dialogue.json')
    ok1 = safe_write(rp, json.dumps(reg, ensure_ascii=False, indent=1) + '\n')
    ok2 = safe_write(dp, json.dumps(dia, ensure_ascii=False, indent=1) + '\n')
    print('registry=%s (%d 条: main %d / plain %d)' % (ok1, len(npcs),
                                                       reg['counts']['main'],
                                                       reg['counts']['plain']))
    print('dialogue=%s (%d 组内置对话，句数 %s)' % (
        ok2, len(dia['lines']), sorted(set(len(v) for v in dia['lines'].values()))))
    for r in npcs:
        if r['tier'] == 'main':
            print('   [main ] %-12s %-10s %s' % (r['id'], r['name_cn'], ','.join(r['chapters'])))
    bad = [k for k, v in dia['lines'].items() if not (4 <= len(v) <= 10)]
    print('   句数越界:', bad or 'none')


if __name__ == '__main__':
    main()
