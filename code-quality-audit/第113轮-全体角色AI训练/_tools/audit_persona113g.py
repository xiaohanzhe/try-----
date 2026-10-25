# -*- coding: utf-8 -*-
"""第113轮g · 人设污染源普查：① 逐字台词 ② 非中文语言要求

## 为什么要查
`mike` 在验证批里整段复读了「喂，你来这里做什么？！你没看见门上写着什么吗？！」，
一查人设，原文写着「你的经典反应是：『……』」—— **逐字台词被模型当成了"我该说的话"**。
这正是记忆里第 A12d 条锁的东西（失真头号来源＝可逐字搬走的固定例句），
只是这次污染在**人设侧**，不是 prompt 侧。

同时 `hy_guardener` / `hy_axis` 全英文大写输出，一查人设：明文要求
「你的说话方式全部大写」+ 元音替换（`FORGI>ABLE`）—— 是**原作特征**，
但和 10-24 22:38 定的「所有 NPC 说中文」口径直接冲突。
⇒ 这类冲突得先数清有多少角色，再决定是改人设还是给人设开豁免。

## 判据
- **逐字台词**：`「…」`/`“…”`/`『…』` 里长度 ≥ 8 的对白式引用。≥3 处 ⇒ 高风险。
  ★ 不收 `"..."`：人设里 ASCII 双引号多用于强调词，噪声太大。
- **非中文语言要求**：出现「全部大写」「全大写」「以大写字母输出」「全部用英文」等。

只读，不修改任何人设。
"""

import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PERSONA_DIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')

RE_QUOTE = re.compile(r'[「『“]([^」』”\n]{10,200})[」』”]')
#: ★ 第二版判据（仍不准）：要求引用里含句末标点 ⇒ 1734 处、72 个角色"高风险"。
#:   还是错 —— 人设里放原作台词是**既定结构**（给模型语料，"一切根据原作"），
#:   叙述性引用（"他在 X 场景说过 Y"）不会让模型把它当成自己的台词。
RE_SENT = re.compile(r'[。！？!?…]')
#: ★★★ 第三版（本版）：真正的污染源是**祈使框架** —— 人设直说
#:   「你的经典反应是『…』」「你的口头禅是『…』」＝ 明确指令"你就该这么说"。
#:   `mike` 就是栽在这句上：整段复读「喂，你来这里做什么？！…」。
#:   而 `papyrus` 的「NYEH HEH HEH」虽然是口癖，但它短、是音效，复读无害。
RE_FRAME = re.compile(
    r'(经典反应|标志性台词|口头禅|开场白|习惯性地说|总会说|常说|你会说|必说'
    r'|招牌台词|的口头语)[^\n]{0,30}?[「『“]')
RE_UPPER = re.compile(r'(全部?大写|全大写|大写字母输出|全部用英文|以英文|用英语说话)')

HIGH = 1      #: 出现 1 处「祈使框架 + 台词」就已经是模型复读的足够理由


def scan(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        t = f.read()
    all_quotes = RE_QUOTE.findall(t)
    quotes = [q for q in all_quotes if RE_SENT.search(q)]
    # 祈使框架命中的台词：取框架后紧跟的那句引用
    framed = []
    for m in RE_FRAME.finditer(t):
        seg = t[m.start():m.start() + 120]
        q = re.search(r'[「『“]([^」』”\n]{4,200})[」』”]', seg)
        if q:
            framed.append((m.group(1), q.group(1)))
    return {
        'n_quote': len(framed),
        'framed': framed,
        'n_all': len(all_quotes),
        'n_sent': len(quotes),
        'upper': RE_UPPER.findall(t),
        'len': len(t),
    }


def main(argv):
    files = sorted(fn for fn in os.listdir(PERSONA_DIR) if fn.endswith('.txt'))
    print('人设目录：%s' % PERSONA_DIR)
    print('共 %d 份人设\n' % len(files))

    rows = []
    for fn in files:
        r = scan(os.path.join(PERSONA_DIR, fn))
        r['id'] = fn[:-4]
        rows.append(r)

    # ---- ① 祈使框架 + 台词（真正的污染源）----
    print('=' * 78)
    print('① 祈使框架 + 台词（「你的经典反应是『…』」这类**指令性**写法）')
    rows.sort(key=lambda r: -r['n_quote'])
    tot = sum(r['n_quote'] for r in rows)
    tot_all = sum(r['n_all'] for r in rows)
    tot_sent = sum(r['n_sent'] for r in rows)
    hi = [r for r in rows if r['n_quote'] >= HIGH]
    print('  全库：引用 %d 处 / 其中完整句子 %d 处 / 其中被祈使框架指定 %d 处'
          % (tot_all, tot_sent, tot))
    print('  ★ 前两个数字是**人设的既定结构**（放原作台词当语料），不是问题；')
    print('    问题只在第三个：明文告诉模型"你就该这么说"。')
    print('  命中 %d 个角色：' % len(hi))
    print('  %-18s %-4s %s' % ('角色', '处', '框架 → 被指定的台词'))
    for r in hi:
        seg = '；'.join('%s→「%s」' % (f, q[:30]) for f, q in r['framed'][:2])
        print('  %-18s %-4d %s' % (r['id'], r['n_quote'], seg))

    # ---- ② 非中文语言要求 ----
    print('\n' + '=' * 78)
    print('② 「全部大写 / 全英文」类要求（与「所有 NPC 说中文」口径冲突）')
    up = [r for r in rows if r['upper']]
    print('  命中 %d 个角色' % len(up))
    for r in up:
        print('  %-18s %s' % (r['id'], '／'.join(sorted(set(r['upper'])))))

    # ---- 结论 ----
    print('\n' + '=' * 78)
    print('结论')
    if hi:
        print('  · %d 个角色被祈使框架指定台词 ⇒ 复读高风险：%s'
              % (len(hi), ', '.join(r['id'] for r in hi)))
    else:
        print('  · 没有角色达到 %d 处逐字台词' % HIGH)
    if up:
        print('  · %d 个角色被要求全大写/全英文 ⇒ 与中文口径冲突：%s'
              % (len(up), ', '.join(r['id'] for r in up)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
