# -*- coding: utf-8 -*-
"""第73轮 · 把 `_crossworld.json` 里已**真接线**的四块从 `spec_only` 翻成 `wired`。

★ 诚实纪律（本项目最贵的坑：「函数写对了 ≠ 产品用上了」）：
  只翻**有代码在消费它**的块，并且每块都必须写 `used_by`（谁在用）+ `wired_how`
  （接到什么程度、哪里还没接）。`visitor` **不许**跟着翻绿 —— 跨作品场景面
  还没进 `_index.json`，它确实还没接线。

用法：`python build73.py [--write]`（默认 dry-run 只打印）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
CROSS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_crossworld.json')

#: 块名 → (used_by, wired_how)
WIRED = {
    'twin_groups': (
        '`npc_system.au_twin_pairs()` 读 `au_family_members` → `RalseiPet._npc_seed_lookup()` '
        '→ `npc_life.Bonds` 的初值',
        '已接线：只取了「**谁是另一个版本的我**」这一半（喂熟络度初值 0.55）。'
        '★ 仍**未**接线的是「**相遇时该怎么开口**」（相认台词）——见 `wiring.not_yet`。'
        '⚠️ 判据上刻意只取 `au_family_members`：Toriel 组的 `toriel`（Deltarune）'
        '与另外两位**只是同名**，享受不到这条加速。',
    ),
    'identity_blind': (
        '`RalseiPet._npc_life_blocks()` 的【你认识谁】块',
        '已接线：注入的只有**显示名 + 熟络程度**；`not_injected` 列的四样（作品归属 / 版本 / '
        'npc id / 对方人设）**一处都没进 prompt**。`check73` E4 逐词反查断言。',
    ),
    'familiarity_seed': (
        '`npc_life.Bonds(seed_lookup=...)`；增长在 `_npc_life_tick`；'
        '注入在 `_npc_life_blocks`',
        '已接线：初值走契约 `seed_values`（0.55/0.30/0.0），随同场共处与互动**渐增**、'
        '封顶 1.0、**对称**（`pair_key` 排序成对，结构上不可能 A-B ≠ B-A）。',
    ),
    'scene_traits': (
        '`npc_life.scene_traits()` → `_npc_life_blocks()` 的【你周围】块 → '
        '`npc_persona.build_system_prompt(..., life=...)`',
        '已接线：traits 来源定为**场景 id / 内部名 / 资源名的文本语义**（零依赖、可复算、'
        '可解释 —— `trait_hits()` 会返回凭什么这么判）。'
        '★★ 如实说清覆盖面：现网 1,014 个真场景（另有 5 个章名 + 32 个区域名共 37 个非场景键）'
        '里只命得中 **dark（141）/ crowded（262）/ quiet（372）** 三个特质，483 个场景零特质；'
        '`ruined`（破败）/ `bright` / `cosmic`（宇宙）**零命中** —— 因为 OneShot / Outertale '
        '的场景还没进 `_index.json`。用户点名的「破败也要能识别」**当前还做不到**，'
        '已在 `npc_life.TRAIT_TOKENS_RESERVED` 里预留令牌、不假装覆盖。'
        '（数字由 `_tools/probe73_traits.py` 真跑产出，落 `_evidence/probe73_traits.json`。）',
    ),
}


def main():
    write = '--write' in sys.argv
    with io.open(CROSS, 'r', encoding='utf-8') as fh:
        d = json.load(fh)

    changed = []
    for key, (used_by, how) in WIRED.items():
        blk = d.get(key)
        if not isinstance(blk, dict):
            print('!! 缺块 %s' % key)
            continue
        if blk.get('status') != 'wired':
            changed.append('%s: %s -> wired' % (key, blk.get('status')))
        blk['status'] = 'wired'
        blk['used_by'] = used_by
        blk['wired_how'] = how

    w = d.setdefault('wiring', {})
    w['wired'] = ['roam', 'twin_groups', 'identity_blind', 'familiarity_seed', 'scene_traits']
    w['spec_only'] = ['visitor']
    w['not_yet'] = [
        '同名相认台词：`twin_groups` 的 `au_family_members` 已用于熟络度初值，'
        '但"相遇时该怎么开口"（认出对方是另一个版本的我）仍未接线',
        '主线 NPC **自主开口**：纯 NPC 已能零成本自发说内置台词；主线 NPC 要靠 7B，'
        '需把"无用户发起的生成"接进异步回调链并与用户请求排队（CPU-only 单并发）',
        '场景特质的跨作品覆盖面：`ruined`/`bright`/`cosmic` 令牌已预留，'
        '但 OneShot / Outertale 场景未进 `_index.json` ⇒ 现网零命中',
        '访客兼容：跨作品场景未接入 + 访客落点策略未做',
        '自由生活（私下闲聊、**传播信息**、不以用户发起为起点）—— 第73轮已接线'
        '（纯 NPC 自发台词 + 说完传话给同场另一位）；**更多行为**（走动中的搭话、'
        '信息二次传播的衰减）待下一轮',
    ]
    w['honesty_note'] = ('写 `spec_only` 是刻意的 —— 本项目最贵的坑就是'
                        '「函数写对了 != 产品用上了」。第73轮把四块翻成 `wired`，'
                        '因为都有代码在消费它们且 `check73` 有真跑判据；'
                        '`visitor` **不翻**，它确实还没接。')
    d['roam'] = d.get('roam', {})
    if isinstance(d.get('roam'), dict):
        d['roam'].setdefault('used_by', '`npc_system.world_gate()`')
        # ★ 第73轮补齐：`roam` 是第72轮接的线，当时没写 `wired_how`。
        #   `check73.F1b` 要求**每一项 wired** 都写清"接到什么程度" ——
        #   发现 `roam` 缺字段就该补，而不是把判据放宽（放宽带过的是真缺口）。
        d['roam'].setdefault(
            'wired_how',
            '第72轮已接线：`world_gate` 的暗世界分支按 `roam_scope` 三档放行/拒绝，'
            '`check72` C 段**真 import 真跑**逐条验过（跨作品进光世界 ✅ / 进暗世界 ❌ / '
            '回自己作品 ✅；niko 全域 ✅）。')

    d['round73'] = {
        'title': '自由生活（场景反应 / 熟络度 / 传话 / 纯 NPC 自主开口）',
        'module': 'ralsei_pet/modules/npc_life.py（零依赖纯策略）',
        'wired': ['scene_traits -> 【你周围】', 'familiarity_seed -> Bonds + 【你认识谁】',
                  'transmit -> 说完一句就告诉同场另一位（带署名）',
                  'LifeLoop -> 纯 NPC 零模型自发台词（内置对话池）'],
        'not_yet': ['主线 NPC 自主开口（需 7B，排队让路未接）',
                    '相认台词', '跨作品场景特质（ruined/cosmic 零命中）'],
        'identity_blind_enforced': '`_npc_life_blocks()` 只注入显示名与熟络度，'
                                   '作品归属/版本/id/人设**一处未进 prompt**',
    }
    d['round'] = 73

    print('plan:')
    for c in changed:
        print('  ', c)
    print('   wiring.wired =', w['wired'])
    print('   wiring.spec_only =', w['spec_only'])
    print('   not_yet 条数 =', len(w['not_yet']))
    if write:
        with io.open(CROSS, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        print('written:', CROSS, os.path.getsize(CROSS), 'bytes')
    else:
        print('(dry-run；加 --write 落盘)')


if __name__ == '__main__':
    main()
