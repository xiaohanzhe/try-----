# -*- coding: utf-8 -*-
"""等价性验证：探针的 _apply_gates 复刻品  vs  产品的 _clean_ai_reply（真身）。

为什么必须做这一步（本项目最贵的坑之一："函数写对了 ≠ 产品用上了"，
这里反过来：**探针复刻对了 ≠ 复刻出了产品真身的行为**）：
    探针第 2 步的 `_is_repeat_of_recent` 是**唯一一处不得不重写**的判据
    （产品那份写在实例方法里、依赖 self，取不出来）。重写就有漂移风险。
    所以拿同一批样本同时喂两侧、逐条比对输出，**必须逐条一致**。

跑法（必须用 C:\\Python311 —— 只有它有 PyQt5，能 import main）：
    C:\\Python311\\python.exe check_probe_fidelity.py
"""
import io
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')

if PET not in sys.path:
    sys.path.append(PET)
if os.path.join(PET, 'src') not in sys.path:
    sys.path.append(os.path.join(PET, 'src'))

# 探针模块（同目录）——导入它的 _apply_gates
sys.path.insert(0, HERE)
import verify_persona_worldview as PVP            # noqa: E402

import main as M                                  # noqa: E402
R = M.RalseiPet


def make_stub(**extra):
    s = types.SimpleNamespace()
    s.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    for name in ('_clean_ai_reply', '_is_repeat_of_recent', '_build_persona_prompt',
                 '_ai_chat_options'):
        setattr(s, name, types.MethodType(getattr(R, name), s))
    for k, v in extra.items():
        setattr(s, k, v)
    return s


stub = make_stub()

# ---- 样本：(输入, recent) ----
RECENT = [
    '被骂了啊……是因为什么事呢？我听着都替你委屈。',
    '诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢你的就是了。',
    '嗯……我也不知道那个预言是什么意思，我们一起去看看好不好？',
]
CASES = [
    # --- 第 0a 步：括号动作 ---
    ('诶、诶？晚安啊……你也是呀。（轻轻敲了下键盘）睡吧，梦里有星星的。', None),
    ('（歪着头）', None),
    ('（其实我有点怕）', None),                       # 负控制：心里话必须放行
    ('其实……（我想想该怎么说）', None),
    # --- 第 0c 步：出戏 / 客服腔 ---
    ('有什么可以帮你的吗？', None),
    ('作为一个语言模型，我其实不太懂这些。', None),
    ('**有什么可以帮你的吗**', None),
    ('我今天有点困了，想早点睡。', None),             # 负控制
    # --- 第 1 步：自问自答截断 ---
    ('嗯……我想想。\n主人：你今天怎么这么安静', None),
    ('主人：我在呢', None),                          # 行首 → 截完为空 → 判退
    ('好呀。\n你：嗯嗯，我也是', None),
    ('Kris:hello there', None),                     # 不在候选 → 放行
    # --- 第 2 步：车轱辘话（与 recent 比）---
    ('被骂了啊……是因为什么事呢？我听着都替你委屈。', RECENT),        # 逐字复读
    ('被骂了啊…是因为什么事呢？我听着都替你委屈。', RECENT),          # 只改标点 → 归一化后同
    ('诶、诶？！你突然说这个干嘛啦……我其实也挺喜欢你的就是了。', RECENT),
    ('我们一起去看看那个预言好不好？', RECENT),                      # 负控制：不重合
    # --- 第 3 步：超长 ---
    ('唔……' + '这是一段很长的独白，用来测试超长截断。' * 12, None),
    ('这是一段很长的话用来测试跑飞上限' * 75, None),
    # --- 第 0b 步：markdown 剥除 / 包裹引号（2026-09-20 第三处补的闸）---
    ('**听到也让我心里暖暖的**。别太累了。', None),
    ('# 早点休息\n> 别熬夜', None),
    ('1. 早点休息', None),
    ('"今天风挺大的。"', None),
    ('——那个结尾是说：**世界才会真正开始重置。**', None),   # 真机 Q3 的形态
    ('我在呢。`代码块` 别熬夜。', None),
    # --- 组合 ---
    ('（停顿了一下）\n主人：喂', None),
    ('嗯……我在听。（轻轻点头）\n你：那就好', None),
]

fails = 0
print('样本数: %d' % len(CASES))
print('=' * 78)
for i, (inp, recent) in enumerate(CASES, 1):
    got_prod = stub._clean_ai_reply(inp, recent=recent)
    got_probe, _n, _cut = PVP._apply_gates(inp, R.AI_REPLY_MAX_CHARS, recent=recent)
    same = (got_prod == got_probe)
    if not same:
        fails += 1
    print('[%s] #%-2d in=%r recent=%s' % ('OK ' if same else 'DIF', i,
                                          inp[:34] + ('…' if len(inp) > 34 else ''),
                                          'y' if recent else '-'))
    print('        产品: %r' % (got_prod,))
    if not same:
        print('        探针: %r' % (got_probe,))
print('=' * 78)
print('%d/%d 一致' % (len(CASES) - fails, len(CASES)))
sys.exit(1 if fails else 0)
