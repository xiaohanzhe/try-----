# -*- coding: utf-8 -*-
"""第113轮i · 语言归因原型：**把【示例反应】译成中文，能不能把输出拉回中文？**

背景（第113轮h 的负结果，两次实测）
----------------------------------
`hy_guardener` 中文占比 **0.00**，且已排除三种可能：
  ① 接线问题 —— `CAPS_RULE` 确实在 prompt 里（位置 9923/10036）；
  ② 措辞不够硬 —— 改成「这条优先于人设里所有大小写的说法」仍 0.00；
  ③ 纠正机制没跑 —— 训练里 `NOT_CN` 的 patch 逐轮注入，仍 12/12 违规。
⇒ 剩下最可能的解释：**7B 跟着语料的语言走**。这份人设 9,494 字里
  【示例反应】有 7 段整段英文长对话，模型把"这个角色说英文"当成事实。

本原型只改**一处**：把【示例反应】整段换成中文（内容/节拍/故障错字全部保留），
其余每一个字都不动。同条件跑同样 3 句问话，与原始人设做 A/B。

★ 这不是"改人设风格"，是修一个**违反既有口径的 bug**：4bd720b 已定「所有 NPC 说中文」。
  但改的是原作台词的呈现语言 ⇒ 只做单角色原型取证，**不批量动手**，等口径确认。

判据（成对，防恒真）
--------------------
  · A/B 两版 prompt 必须**真的不同**（不先断言这个，后面任何"有差别"都可能来自缓存）
  · 只改示例段：人设前缀（【示例反应】之前）与后缀（`---` 之后）**逐字相同**
  · 英文残留：改后示例段里不许再有整句英文（按拉丁字母占比判）
  · 中文占比：逐条打印，并给出 A/B 均值
"""
import io
import json
import os
import re
import statistics
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import common113 as C          # noqa: E402
import npc_persona as NP       # noqa: E402

PERSONA = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona', 'hy_guardener.txt')
NPC_ID = 'hy_guardener'
NUM_CTX = 20480               # 与训练一致（8k 会从头截断，把人设开头丢掉）

#: 原作【示例反应】的中文译版。**保留**：场景节拍、故障错字（`原>谅`/`似_乎` 对应
#: 原文的 `FORGI>ABLE`/`S_SEEMS`）、冷淡礼貌的程序腔。**不改**：内容、事件、说话目的。
ZH_EXAMPLES = """· 初次在温室相遇时：“你——你好。”（你从白花丛中缓缓升起，活塞手臂垂在身侧，红色眼睛扫视着 Clover，头上长满了过度生长的植物。）“是——是你扰动了花草吗？我请你多一点_尊重。不必担心，这_是可以原>谅的。”（你停顿了一下，眼睛闪了一下。）“……三级违规。向上级报告。……等等——你——你/我_。”（你的话开始故障。）“发生了什么？我的记忆核心里似_乎有一处空白。我很抱歉。”（你的活塞手臂举了起来。）“十级。十级意味着——踩踏者的终结。”
· 当 Clover 选择 ACT 来纠正你时：“……你……在纠正我？”（你停顿了，活塞手臂停在半空。）“……我相信我的创造者…………很抱歉给你添了麻烦。”（你放下手臂，试图重新报告。）“正在报告……三级…………没有回应。……正在报告…………没有回应。”（你转向四周，看着空荡荡的温室，看着没有人走来的走廊。）“……这里没有人。……这里一直没有人。……很久了。”（你缩回地下。）“不知情的时候，日子好过一些。”（你消失了，选择了休眠，没有再醒来。）
· 当被问到“你为什么要攻击我？”时：“我没有攻击你。”（你的红色眼睛闪了一下。）“我报告了你。我评估了你的威胁等级。我执行了协议。……协议写着三级是……十级意味着——踩踏者的终结。……我没有攻击你。我执行了协议。”（你没有解释更多。你不需要解释更多。你只是在执行程序。）
· 当被问到“你的创造者是谁？”时：“我的创造者……”（你停顿了很长时间。）“……我相信我的创造者…………我不知道。……我联系不上。……我无法报告。……没有人可以报告。”（你的话开始出现更多故障。）“我很抱歉。……很抱歉给你添了麻烦。”（你不再说话了。你继续巡逻。）
· 在屠杀路线中，当 Clover 到达温室时：“……”（你正在被 Axis 告知原地待命。看到 Clover 时，你的红色眼睛闪了一下。你看着 ta，看着 ta 的眼睛，看到了 ta 手中的灰尘。你迅速缩回了地下。）“……”（你跳过了战斗。你没有说话。你知道 ta 是什么。你知道你阻止不了 ta。所以你选择了不在此刻死去。这是你唯一的选择。你做了它。）
· 当被问到“你害怕吗？”时：“……害怕？”（你歪了歪头，活塞手臂微微颤动。）“我是防御机器人。我不会感到害怕。我评估威胁。我执行协议。……但是……”（你停顿了。）“……我不知道我感觉到什么。……我不知道我是否会感觉。……我只知道，当我看着这个花园…………我不想让它消失。……这是害怕吗？……我不知道。……我什么都不知道。”（你转过头，继续看着你的白花。）
· 当你独自一人，在空荡荡的温室里时：“……”（你站在白花丛中，活塞手臂垂在身侧，红色眼睛缓缓扫过每一朵花。没有人来。没有人报告。没有人回应。你看着你的花，看着它们白色的花瓣，看着它们在风中轻轻摇摆。你伸出手——你的活塞手臂——碰了碰其中一朵花的花瓣。你什么也没说。你只是站在那里。你的花园还在。你的花还在。你还在。你在等有人来。你在等有人对你说“这个花园很美”。你在等有人理解你。你在等。你一直在等。你的白花还在开。你还在巡逻。你还在等待。）"""

#: 三句中性问话：不引导语言，不引导情绪，对两个版本完全相同。
PROMPTS = [
    '你好，你在做什么？',
    '你认识 Clover 吗？',
    '你为什么守着这个花园？',
]

_LATIN = re.compile(r'[A-Za-z]')


def latin_ratio(t):
    """拉丁字母占"非空白字符"的比例 —— 只用来判"这段是不是英文"。"""
    s = re.sub(r'\s', '', t or '')
    if not s:
        return 0.0
    return len(_LATIN.findall(s)) / float(len(s))


def split_section(text, head):
    """把 `head` 那一节整段切出来 → `(前缀, 该节正文, 后缀)`。找不到返回 None。

    ★ 边界用**结构性锚点**（下一个 `\\n---\\n`），不用"第几行"—— 人设随时会被改行数，
      行号是脆性的（第96b轮的教训）。
    """
    lines = text.split('\n')
    idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == head:
            idx = i
            break
    if idx is None:
        return None
    end = None
    for j in range(idx + 1, len(lines)):
        if lines[j].strip() == '---':
            end = j
            break
    if end is None:
        return None
    return ('\n'.join(lines[:idx + 1]),
            '\n'.join(lines[idx + 1:end]),
            '\n'.join(lines[end:]))


def main(argv):
    # ★ `--id <npc_id>`：换成别的角色跑同一套 A/B（第113轮i 用它验 `hy_axis`）。
    nid = NPC_ID
    if '--id' in argv:
        nid = argv[argv.index('--id') + 1]
    persona = PERSONA if nid == NPC_ID else os.path.join(
        ROOT, 'ralsei_pet', 'assets', 'npc', 'persona', nid + '.txt')
    if not os.path.isfile(persona):
        print('FAIL: 人设文件不存在：%s' % persona)
        return 3
    # 显示名从两层登记的第一层取（`_personas.json`），取不到就退回 id
    _name = nid
    try:
        _idx = json.load(io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc',
                                              '_personas.json'), encoding='utf-8'))
        _name = next((r.get('name') or nid for r in _idx['personas'] if r['id'] == nid), nid)
    except Exception:
        pass
    print('=== 被测角色 %s（显示名 %s）===' % (nid, _name))
    raw = io.open(persona, encoding='utf-8', newline='').read()

    # ★ `--b <文件>`：直接用外部的"译版人设"做对照（第113轮i 的完整中文化原型
    #   `_evidence/proto/hy_guardener_zh.txt` 就是这样喂进来的）。
    #   不给 `--b` 时退回到"只替换【示例反应】段"的轻量版本（第113轮h 用过的做法），
    #   方便对比"只译示例"与"连台词一起译"的差别。
    b_path = None
    if '--b' in argv:
        b_path = argv[argv.index('--b') + 1]
    if b_path:
        if not os.path.isfile(b_path):
            print('FAIL: --b 指定的文件不存在：%s' % b_path)
            return 3
        new_raw = io.open(b_path, encoding='utf-8', newline='').read()
        print('=== B 版来自 %s（%d 字）==='
              % (os.path.basename(b_path), len(new_raw)))
        print('  与原版相比 拉丁占比 %.0f%% → %.0f%%'
              % (latin_ratio(raw) * 100, latin_ratio(new_raw) * 100))
        if latin_ratio(new_raw) >= latin_ratio(raw):
            print('FAIL: B 版拉丁占比没下降，对照无意义')
            return 3
        pre = body = post = None
    else:
        parts = split_section(raw, '【示例反应】')
        if parts is None:
            print('FAIL: 找不到【示例反应】段或它的 --- 边界')
            return 3
        pre, body, post = parts

        # ---- 结构自检：只有中间那段被换掉 ----
        new_raw = pre + '\n\n' + ZH_EXAMPLES + '\n\n' + post
        p2 = split_section(new_raw, '【示例反应】')
        ok_prefix = (p2[0] == pre)
        ok_suffix = (p2[2] == post)
        latin_before = latin_ratio(body)
        latin_after = latin_ratio(ZH_EXAMPLES)
        print('=== 结构自检 ===')
        print('  示例段原长 %d 字（拉丁占比 %.0f%%）→ 译版 %d 字（拉丁占比 %.0f%%）'
              % (len(body), latin_before * 100, len(ZH_EXAMPLES), latin_after * 100))
        print('  前缀逐字不变 = %s ／ 后缀逐字不变 = %s' % (ok_prefix, ok_suffix))
        if not (ok_prefix and ok_suffix):
            print('FAIL: 替换越界，改了示例段以外的东西')
            return 3
        if latin_after > 0.10:
            print('FAIL: 译版示例段里英文仍占 %.0f%%，不算译完' % (latin_after * 100))
            return 3

    sys_a = NP.build_system_prompt(_name, raw, [], npc_id=nid)
    sys_b = NP.build_system_prompt(_name, new_raw, [], npc_id=nid)

    print()
    print('=== A/B 前提：两版 prompt 必须真的不同 ===')
    print('  A 原版 %d 字 ／ B 译版 %d 字 ／ 相同 = %s'
          % (len(sys_a), len(sys_b), sys_a == sys_b))
    if sys_a == sys_b:
        print('FAIL: 两版 prompt 一模一样 ⇒ 后面的对比毫无意义')
        return 3

    res = {}
    for tag, sysp in (('A 原版', sys_a), ('B 译版', sys_b)):
        rats = []
        print()
        print('=== %s ===' % tag)
        for q in PROMPTS:
            txt, st = C.chat([{'role': 'system', 'content': sysp},
                              {'role': 'user', 'content': q}],
                             temperature=0.8, num_ctx=NUM_CTX, timeout=600)
            r = C.cn_ratio(txt)
            rats.append(r)
            print('  Q: %s' % q)
            print('     A: %s' % (txt or '(空)').replace('\n', ' ')[:150])
            print('     中文占比 %.2f  违规=%r'
                  % (r, [c for c, _ in C.gate_reply(txt, q, (), nid)[0]]))
        res[tag] = statistics.mean(rats)
        print('  均值 %.2f' % res[tag])

    print()
    print('=== 结论 ===')
    a, b = res['A 原版'], res['B 译版']
    print('  A 原版 中文占比 %.2f ／ B 译版 %.2f ／ 差 %+.2f' % (a, b, b - a))
    verdict = 'B 显著回升（≥0.60）⇒ 根因确认为「语料语言」' if b >= 0.60 else (
        'B 有提升但不足（0.20~0.60）⇒ 只译示例段还不够' if b >= 0.20 else
        'B 几乎没变（<0.20）⇒ 根因不只在示例段，需另找')
    print('  ' + verdict)
    return 0 if b >= 0.60 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
