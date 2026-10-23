# -*- coding: utf-8 -*-
"""第113轮 · 训练卡抽取（persona txt → 结构化规格）。

训练卡是什么
-----------
把一份人设从"给人看的散文"变成"给程序和模型用的表"：

  · `identity / traits / voice / taboos / relations / exemplars` —— 五段可直接引用的规格；
  · `voice_markers` —— 口头禅候选，评测时用来量化"这句像不像他"；
  · `patch` —— **训练后才写**：实测里确实出的毛病对应的纠正句（运行时可注入）。

为什么要做这一步：76 份人设的分节标题有 **10 种写法**（实测），
运行时把整份人设塞给模型没问题，但**评测**需要能被程序检索的字段。
没有卡片，就只能靠"我觉得这段挺像"——那是审稿，不是评测。

用法
----
    python cards113.py            # 只出 main 档（有人设的）
    python cards113.py --all      # 连 plain 档（内置台词）与缺口角色一起登记
    python cards113.py --verify    # 复核模式：只读，核对卡片与人设 sha256 是否同步
"""
import json
import os
import sys

import common113 as C

#: 字段 → 候选标题（按顺序试，命中即用）。
#: ★ 为什么是一组别名而不是一个字符串：76 份人设里标题有两种写法
#:   （`语言风格` / `语言与交流风格`），而 `ralsei_persona.md` 用的是
#:   `—— 我怎么说 ——` 这种完全不同的体例。只写死一个标题的后果实测过：
#:   kris 的 voice 直接是空，ralsei 整张卡全空 —— 而"空字段"不会报错，
#:   只会让评测在无输入的情况下跑出"零违规"，是最难发现的那种假绿。
SECTIONS = {
    'identity': ('角色身份', '我是谁', '身份'),
    'traits': ('核心性格', '性格'),
    'voice': ('语言风格', '语言与交流风格', '我怎么说', '说话方式'),
    'tone': ('我的语气', '语气'),
    'rules': ('行为准则',),
    'relations': ('对特定角色的态度', '与玩家的关系', '关系'),
    'inner': ('内心世界与矛盾', '内心'),
    'hobbies': ('兴趣爱好',),
    'taboos': ('禁忌',),
    'exemplars': ('示例反应', '语气示范'),
    'quirks': ('我的口癖', '口癖'),
}


def build_card(item):
    text = item['persona']
    secs = C.split_sections(text)
    fields = {k: C.find_section(secs, v) for k, v in SECTIONS.items()}
    voice_items = C.bullets(fields['voice']) + C.bullets(fields['tone'])
    ex_items = C.bullets(fields['exemplars'])
    # ★ 有显式【我的口癖】就用它（比正则在语气描述里猜准得多）；没有才走抽取
    markers = C.quirks_markers(C.bullets(fields['quirks'])) or \
        C.voice_markers(voice_items, ex_items)
    rels = C.relations(C.bullets(fields['relations']))
    ident = fields['identity'].replace('\n', ' ').strip()
    if not ident:
        # 兜底：人设开头通常就是"我是谁"，取前 400 字而不是留空
        ident = ' '.join(text.strip().split('\n')[:12])[:400]
    return {
        'schema_version': 1,
        'kind': 'persona',
        'id': item['id'],
        'name': item['name'],
        'name_cn': item['name_cn'],
        'work': item['work'],
        'tier': item['tier'],
        'persona_rel': item['persona_rel'],
        'persona_chars': len(text),
        'persona_sha256': item['persona_sha256'],
        'sections_found': sorted(secs),
        # —— 规格（原文优先，不改写）——
        'identity': ident[:400],
        'traits': [x[:120] for x in C.bullets(fields['traits'])][:14],
        'voice': [x[:120] for x in voice_items][:14],
        'rules': [x[:120] for x in C.bullets(fields['rules'])][:14],
        'taboos': [x[:120] for x in C.bullets(fields['taboos'])][:14],
        'relations': rels,
        'exemplars': C.exemplar_pairs(ex_items)[:12],
        'voice_markers': markers,
        'length_policy': {'max_chars': C.MAX_CHARS, 'max_sentences': 3},
        # 训练后回填
        'patch': '',
        'eval': {},
    }


def card_for_plain(nid, lines, name, name_cn=''):
    """纯 NPC（18 人）：按第49轮口径走内置台词，不过模型。

    仍然登记一张卡，理由是**数据面要闭合**：报告里"96 人全覆盖"必须
    真能逐个数出来，而不是"18 个人本来就不需要"这种口头豁免。
    """
    return {
        'schema_version': 1,
        'kind': 'canned',
        'id': nid,
        'name': name,
        'name_cn': name_cn,
        'tier': 'plain',
        'lines': list(lines)[:10],
        'voice_markers': [],
        'patch': '',
        'eval': {'note': 'plain 档：4~10 句内置台词，不经过模型（第49轮口径）'},
    }


def card_for_gap(nid, name, name_cn='', why=''):
    return {
        'schema_version': 1,
        'kind': 'gap',
        'id': nid,
        'name': name,
        'name_cn': name_cn,
        'tier': 'main',
        'patch': '',
        'eval': {'note': why},
    }


def main(argv):
    all_tier = '--all' in argv
    verify = '--verify' in argv
    roster, gaps = C.load_roster()
    reg = C.load_json(os.path.join(C.NPC_DIR, '_registry.json'), {}) or {}
    dial = (C.load_json(os.path.join(C.NPC_DIR, '_dialogue.json'), {}) or {}).get('lines') or {}
    cards_dir = os.path.join(C.TRAIN_DIR, 'cards')

    if verify:
        bad = []
        for item in roster:
            p = os.path.join(cards_dir, item['id'] + '.json')
            card = C.load_json(p)
            if not card:
                bad.append((item['id'], '卡片缺失'))
                continue
            if card.get('persona_sha256') != item['persona_sha256']:
                bad.append((item['id'], '人设已改但卡片未重建'))
            if not card.get('identity'):
                bad.append((item['id'], 'identity 为空'))
            if not card.get('voice'):
                bad.append((item['id'], 'voice 为空'))
        print('核对 %d 张卡：%d 处不同步' % (len(roster), len(bad)))
        for b in bad[:20]:
            print('  ', b)
        return 0 if not bad else 1

    written = []
    for item in roster:
        card = build_card(item)
        C.write_text(os.path.join(cards_dir, item['id'] + '.json'),
                     json.dumps(card, ensure_ascii=False, indent=1) + '\n')
        written.append(card)

    if all_tier:
        for rec in (reg.get('npcs') or []):
            nid = rec.get('id')
            if not nid or any(c['id'] == nid for c in written):
                continue
            if nid in dial:
                card = card_for_plain(nid, dial[nid], rec.get('name') or nid,
                                      rec.get('name_cn') or '')
            else:
                card = card_for_gap(nid, rec.get('name') or nid, rec.get('name_cn') or '',
                                    '既无人设也无内置台词 —— 缺口，等用户给设定')
            C.write_text(os.path.join(cards_dir, nid + '.json'),
                         json.dumps(card, ensure_ascii=False, indent=1) + '\n')
            written.append(card)
        for item in gaps:
            if any(c['id'] == item['id'] for c in written):
                continue
            card = card_for_gap(item['id'], item['name'], item['name_cn'],
                                'registry 标为 main，但没有人设文件（第55轮口径：主线设定由用户提供）')
            C.write_text(os.path.join(cards_dir, item['id'] + '.json'),
                         json.dumps(card, ensure_ascii=False, indent=1) + '\n')
            written.append(card)

    index = {
        'schema_version': 1,
        'model': C.MODEL,
        'built_from': {
            'registry': 'assets/npc/_registry.json',
            'personas': 'assets/npc/_personas.json',
        },
        'counts': {
            'total': len(written),
            'persona': sum(1 for c in written if c['kind'] == 'persona'),
            'canned': sum(1 for c in written if c['kind'] == 'canned'),
            'gap': sum(1 for c in written if c['kind'] == 'gap'),
        },
        'gaps': [c['id'] for c in written if c['kind'] == 'gap'],
        'cards': {c['id']: {'kind': c['kind'], 'name': c['name'],
                            'name_cn': c.get('name_cn', ''),
                            'persona_chars': c.get('persona_chars', 0),
                            'markers': len(c.get('voice_markers') or []),
                            'patch': ''} for c in written},
    }
    # ★ 重建索引**不许冲掉训练结果**：`patches` / `trained` 是 eval113 写的，
    #   而卡片重建是随时可能发生的（改了人设就得重建）。冲掉就等于
    #   "重建一次卡片，全体角色的纠正全丢，而且运行时静默退回未训练状态"。
    old = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
    if isinstance(old.get('patches'), dict):
        index['patches'] = old['patches']
        for nid, p in old['patches'].items():
            if nid in index['cards']:
                index['cards'][nid]['patch'] = p
    if isinstance(old.get('trained'), dict):
        index['trained'] = old['trained']
    C.write_text(os.path.join(C.TRAIN_DIR, '_index.json'),
                 json.dumps(index, ensure_ascii=False, indent=1) + '\n')

    print('已写 %d 张卡 → %s' % (len(written), cards_dir))
    print('  分类：%s' % index['counts'])
    if index['gaps']:
        print('  缺口（无人设）：%s' % '、'.join(index['gaps']))
    no_marker = [c['id'] for c in written if c['kind'] == 'persona' and not c['voice_markers']]
    print('  抽不出口癖的：%d 人 %s' % (len(no_marker), '、'.join(no_marker[:12])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
