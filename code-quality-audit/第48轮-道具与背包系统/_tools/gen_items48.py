# -*- coding: utf-8 -*-
"""第48轮 · 生成产品侧道具数据表（#56 数据层）。

★ 数据来源与真实性纪律
----------------------
- **效果（kind/target/amount/per_char）全部由 `_evidence/items_effects48.json` 机器抽取**，
  该文件由 `scr_itemuse` / `scr_litemuseb` 的真反编译文本正则切块得到，**不是我手写的**。
- **名字（name）只在"有据可依"时才填**：
  · `verified` —— 效果与权威中文资料（Deltarune Wiki 中文 / 萌娘百科译名对照表）**逐项吻合**，
    例如 `case 12` 的 `{Kris:20, Susie:80, Ralsei:50}` 与「红心甜甜圈 非战斗 +20/+80/+50」完全一致。
  · `role`     —— 由代码里唯一的证据锚定，例如光世界 `case 8` 播 `snd_egg` ⇒ 蛋。
  · `null`     —— 查不到就**留空**（UI 显示 `？？？`，这也是原作对未知道具的表示法）。
  绝不为了"填满"而编名字 —— 编出来的名字会让"照抄原作"这句声明变成假话。
- 语言包（`lang/lang_zh_names.json`）**不随 data.win 分发**，本项目拿不到原作中文文本
  （见 `_evidence/道具与菜单取证48.md` §2.3），这是 name 留空的**唯一原因**。

输出
----
`ralsei_pet/assets/items/_index.json`、`ch1.json` .. `ch5.json`
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
OUT_DIR = os.path.join(REPO, 'ralsei_pet', 'assets', 'items')
EFFECTS = os.path.join(ROUND, '_evidence', 'items_effects48.json')

#: 袋子容量 —— 照抄 `scr_itemget`（暗 12）/ `scr_litemget`（光 8），五章一致（已实证）。
BAG_CAPACITY = {'dark': 12, 'light': 8}

#: 暗世界道具 id → (中文名, 名字可信度)
#: verified 的判据写在 gen 的 docstring 里；null 表示"查不到，留空"。
DARK_NAMES = {
    1: ('黑暗糖果', 'verified', ' +40HP。一颗红黑相间的星星，口感像棉花糖。'),
    2: ('复活薄荷', 'verified', '让倒下的同伴站起来，回满其全部 HP。'),
    5: ('损坏的蛋糕', 'verified', '尽管残缺不全，却翻腾着力量。+20HP。'),
    6: ('顶尖蛋糕', 'verified', '能让你舌头打结的蛋糕。治愈全员 160HP。'),
    7: ('旋转蛋糕', 'verified', '陀螺形状的糕点。治愈全员 80HP。'),
    8: ('黑暗汉堡', 'verified', '神秘的黑色汉堡……材料是？等等，这只是烤焦了而已！+70HP。'),
    9: ('Lancer饼干', 'verified', '一块形状像 Lancer 脸的饼干。也许它根本不是饼干。+4HP。'),
    11: ('梅花三明治', 'verified', '能够一分为三的三明治。治愈全员 30HP。'),
    12: ('红心甜甜圈', 'verified', '这可是心哦？！填满了一坨坨粘乎乎的红色果酱。'),
    13: ('方钻巧克力', 'verified', '它很小，但有些人非常喜欢它。'),
    14: ('赞赞三明治', 'verified', '你觉得这味道完美无瑕。治愈 500HP。'),
    15: ('Rouxls油面酱', 'verified', '散发着美妙味道的黑色油面酱。……里面有蠕虫。+50HP。'),
}

#: 光世界道具 id → (中文名, 可信度, 描述)
LIGHT_NAMES = {
    8: ('蛋', 'role', '光世界的蛋。用途不明。'),
}

OWN = '产品自定'   # 名字来源标记


def _kind_of(eff):
    """把抽取出来的效果列表归成一个 (kind, target, amount, per_char)。"""
    kinds = [e[0] for e in eff]
    per = None
    for e in eff:
        if e[0] == 'per_char':
            per = e[1]
    if 'per_char' in kinds:
        return 'per_char', 'one', None, per
    if 'heal_all' in kinds:
        amt = [e[1] for e in eff if e[0] == 'heal_all']
        return 'heal_all', 'all', max(amt), None
    if 'revive' in kinds:
        return 'revive', 'one', None, None
    if 'heal' in kinds:
        amt = [e[1] for e in eff if e[0] == 'heal']
        return 'heal', 'one', max(amt), None
    if 'equip' in kinds:
        return 'equip', 'one', None, None
    if 'recover' in kinds:
        return 'recover', 'one', None, None
    if 'phone' in kinds:
        return 'phone', 'none', None, None
    if 'egg' in kinds:
        return 'egg', 'none', None, None
    if 'consume' in kinds:
        return 'consume', 'none', None, None
    if 'dialog' in kinds:
        return 'dialog', 'none', None, None
    if 'text' in kinds:
        return 'text', 'none', None, None
    if 'room_gate' in kinds:
        return 'room_gate', 'none', None, None
    return 'none', 'none', None, None


def _entry(world, iid, eff):
    kind, target, amount, per = _kind_of(eff)
    names = DARK_NAMES if world == 'dark' else LIGHT_NAMES
    nm, conf, desc = (None, None, None)
    if iid in names:
        nm, conf, desc = names[iid]
    e = {
        'id': iid,
        'world': world,
        'name': nm,
        'name_source': conf,
        'desc': desc,
        'kind': kind,
        'target': target,
        'amount': amount,
        'per_char': per,
        # ★ 可消耗：只有"用掉就走"的才消耗。原作 `usable == 1` 的语义在
        #   `scr_itemconsumeb` 里被用来决定是否 `scr_itemshift_temp`（移出背包）。
        'consumable': kind in ('heal', 'heal_all', 'revive', 'per_char', 'consume', 'recover'),
        # ★ 可丢弃：照抄 `obj_overworldc_Step_0` 的 `dontthrow` 名单（id 5 / id 11 丢不掉）。
        'droppable': not (world == 'light' and iid in (5, 11)),
        'src': 'scr_%suse%s' % ('litem' if world == 'light' else 'item',
                                'b' if world == 'light' else ''),
    }
    # 限定场景使用（照抄 `scr_litemuseb` 里 `room == ...` 的门控；无门控 = None）
    gates = [e0 for e0 in eff if e0[0] == 'room_gate']
    e['scene_gate'] = True if gates else None
    return e


def main():
    with io.open(EFFECTS, encoding='utf-8') as fh:
        raw = json.load(fh)

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    idx = {
        'schema_version': 1,
        'note': '道具数据表索引。效果由原作 GML 机器抽取；名字只在有据可依时填写，'
                '查不到留空（UI 显示 ？？？）。生成器见 code-quality-audit/第48轮-道具与背包系统/_tools/gen_items48.py。',
        'bag_capacity': BAG_CAPACITY,
        'worlds': ['dark', 'light'],
        'chapters': {},
    }

    total = 0
    named = 0
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        if ch not in raw:
            continue
        rec = {'schema_version': 1, 'chapter': ch,
               'bags': dict(BAG_CAPACITY),
               'items': {'dark': {}, 'light': {}}}
        for world in ('dark', 'light'):
            src = raw[ch].get(world) or {}
            for k in sorted(src, key=lambda x: int(x)):
                e = _entry(world, int(k), src[k])
                rec['items'][world][k] = e
                total += 1
                if e['name']:
                    named += 1
        p = os.path.join(OUT_DIR, ch + '.json')
        if os.path.isfile(p):
            os.remove(p)
        with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, indent=1))
        idx['chapters'][ch] = {
            'file': ch + '.json',
            'dark_items': len(rec['items']['dark']),
            'light_items': len(rec['items']['light']),
        }

    p = os.path.join(OUT_DIR, '_index.json')
    if os.path.isfile(p):
        os.remove(p)
    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(idx, ensure_ascii=False, indent=1))

    print('道具条目 %d 条；其中有名字 %d 条（%.0f%%）' % (total, named, 100.0 * named / max(1, total)))
    for ch, v in idx['chapters'].items():
        print('  %s 暗 %d / 光 %d' % (ch, v['dark_items'], v['light_items']))
    print('输出目录：%s' % OUT_DIR)


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
