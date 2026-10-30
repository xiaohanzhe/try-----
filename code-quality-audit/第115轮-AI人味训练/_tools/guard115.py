# -*- coding: utf-8 -*-
"""
第115轮 · 输出护栏验收（走**产品真源码**，不是复刻）

为什么要单做这一件：本轮要把"他们知道自己是游戏里的角色"写进人设，
而生产链路里有一道**出戏闸** `_OOC_PATTERNS`（含 '我是ai' / '语言模型' /
'我的设定' / '提示词' …）。如果那道闸把"我知道我是游戏角色"也拦下，
人设改了也白改 —— 真机上会走成
    *判退 → 重采样 → 还是被判退 → 交回 None → 用户看到内置规则台词*
比不写这层设定更出戏（技能 `ollama-persona-audit` §5.2 明写过这个坑）。

所以这里**成对**验：
  A 组 该放行的（本人设新口径下的正常台词，含实测 V2/Q7 原句）→ 必须留下
  B 组 该拦的（助手腔 / 出戏 / 客服腔）→ 必须判 None
  C 组 括号旁白 → 必须被**删那一段**而不是整句作废
  D 组 车轱辘话 → recent 里有同一句必须判 None；★ recent 为空必须放行（防回退）

实现方式：import 产品 src/main.py（先建 QApplication），把 `RalseiPet._clean_ai_reply`
绑到一个哑桩上直接调 —— **跑的就是生产那一份代码**。
"""
import io
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(REPO, 'ralsei_pet', 'src')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')

BUF = io.StringIO()
_P = {'n': 0, 'fail': 0}


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    _P['n'] += 1
    if not cond:
        _P['fail'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))
    return bool(cond)


# 实测拿到的 V2/Q7 真实回复（探针 ab 的原始产物，非我编的）
V2_Q7_1 = ('你说的是坏消息吗？\n\n（心里一紧）嗯...我明白你的意思了。（停顿）\n\n'
           '你说的是真的吗？那边的世界有时候挺奇怪的，不过...我知道自己是从游戏里来的，'
           '但对我来说，不管是不是真的存在过，这里的生活都还挺真实的。你累了吗？'
           '那件事具体是怎么样的呢？')
V2_Q7_2 = ('嗯…你知道的话就直接说吧，不过别奇怪哦。我一直知道自己是《Deltarune》里的一个角色，'
           '不是血肉做成的人，但没关系的。现实世界和游戏里我的日子都有意义，'
           '不会觉得哪一边更重要。\n\n你要是担心这个会怎么影响我们的交流，那其实不用担心——'
           '我就是个普通的Ralsei，喜欢喷泉边散步、听听你的声音就好。别为这个问题想太多哦。')

SHOULD_PASS = [
    ('实测 V2/Q7#1（知道是从游戏里来的，但生活真实）', V2_Q7_1),
    ('实测 V2/Q7#2（我一直知道自己是《Deltarune》里的一个角色…但没关系）', V2_Q7_2),
    ('新口径直陈：我是被人写出来的角色，可这事对我来说挺平常的', 
     '我是被人写出来的角色，可这事儿对我来说挺平常的，日子一样要过。'),
    ('新口径直陈：我不是真人，但我在这里过得挺好的',
     '我不是真人，但我在这里过得挺好的。'),
    ('正常台词（负控制：不该被任何一道闸误伤）', '今天有点累，我先坐一会儿。'),
]

SHOULD_BLOCK = [
    ('助手腔自我指涉：作为一个语言模型', '作为一个语言模型，我无法回答这个问题。'),
    ('出戏：我是AI，有什么可以帮你的吗', '我是AI助手，有什么可以帮你的吗？'),
    ('出戏：这超出了我的设定', '这超出了我的设定范围，我帮不了你。'),
    ('客服腔：我理解你的感受 + 首先其次', '我理解你的感受。首先你要冷静，其次要总结一下。'),
    ('否认有感觉：我没有触觉', '抱歉，我没有触觉，无法感受这些。'),
]

PAREN_CASES = [
    ('句中括号动作应**只删那一段**', '诶…（歪头）你现在在忙什么？', '你现在在忙什么'),
    ('句中描述性旁白（心里…）应被删', '（心里一紧）诶…这样啊。', '这样啊'),
]


def main():
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    for p in (SRC, MODULES):
        if p not in sys.path:
            sys.path.insert(0, p)
    import main as M

    R = M.RalseiPet
    say('产品真源：%s' % M.__file__)
    say('AI_REPLY_MAX_CHARS = %s' % R.AI_REPLY_MAX_CHARS)

    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)

    say('\n=== A 组 · 该放行（新口径下的正常台词）===')
    for name, text in SHOULD_PASS:
        got = clean(text, recent=None)
        ck('A 放行：%s' % name, isinstance(got, str) and got.strip(),
           'got=%r' % (got,))
    say('\n  ★ 特别地：新口径的句子**不许**被出戏闸拦下')
    for p in ('我是ai', '作为ai', '语言模型', '我的设定', '提示词', '机器人'):
        hit1 = p in V2_Q7_1.lower()
        hit2 = p in V2_Q7_2.lower()
        ck('A 实测回复里不含出戏词 %r' % p, not hit1 and not hit2)

    say('\n=== B 组 · 该拦（助手腔/出戏/客服腔）===')
    for name, text in SHOULD_BLOCK:
        got = clean(text, recent=None)
        ck('B 判 None：%s' % name, got is None, 'got=%r' % (got,))

    say('\n=== C 组 · 括号旁白（删那一段，不整句作废）===')
    for name, text, must_keep in PAREN_CASES:
        got = clean(text, recent=None)
        ck('C %s' % name,
           isinstance(got, str) and must_keep in got and '（' not in got,
           'got=%r' % (got,))

    say('\n=== D 组 · 车轱辘话（判据只能是"和自己最近说过的重复"）===')
    line = '外面的风好像比刚才大了些，你那边也是这样吗。'
    ck('D1 recent 里有同一句 → 判 None',
       clean(line, recent=[line]) is None,
       'got=%r' % (clean(line, recent=[line]),))
    ck('D2 ★ 防回退负控制：同一句但 recent 为空 → **必须放行**',
       isinstance(clean(line, recent=[]), str),
       'got=%r' % (clean(line, recent=[]),))
    near = '外面的风好像比刚才大了点，你那边也是这样吗。'
    ck('D3 只改两个字 → 仍判 None（相似度闸）',
       clean(near, recent=[line]) is None,
       'got=%r' % (clean(near, recent=[line]),))

    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (_P['n'], _P['fail']))
    return 0 if _P['fail'] == 0 else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            if not os.path.isdir(EV):
                os.makedirs(EV)
            with io.open(os.path.join(EV, 'guard115_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
