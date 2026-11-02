# -*- coding: utf-8 -*-
u"""第129轮回归锁：**复读（车轱辘话）与出戏**的两处判据不许再退化。

## 这一轮修的是什么（三处，都是"判据本身是错的"，不是模型错了）

1. **车轱辘话判据对短句误伤 8/12**
   `_is_repeat_of_recent` 原来是两条：`ratio ≥ 0.82`（且长度差 ≤ 6）＋
   `最长公共块 ≥ 12`。第129轮拿 12 对"语义不同、字面相近"的短句去测：
   **8 对被判成重复** —— 「我想和你一起走」vs「我想和你一起看」ratio 就是 **0.857**。
   而这类 8~10 字短句正是 Ralsei 最常见的台词，判重复 ⇒ 整句作废 ⇒ 白重采样
   （用户体感是卡顿，或连续判退后回落到罐头）。
   修法：**12 字以下只认"去标点后逐字相同"**（零误伤），12 字以上才用相似度；
   同时补上"逐字复用"这条（短句连说两次「我在呢」确实是复读，旧判据反而漏了）。
   实测：误伤 8/12 → **0/12**；"长句改两三字"仍 **6/6** 全拦。

2. **出戏闸的裸词 `机器人` —— 第115轮的修复被回滚了**
   第115轮对注册表**全量 96 位**各真发一次请求才发现：OneShot/UTY 里**有 4 位角色
   本身就是机器人**（`os_kelvin` / `os_rowbot` / `os_prophetbot` / `hy_sousborg`），
   裸词 `机器人` 把他们一律判退，连重采样都救不回来。
   当时的证据 `第115轮/_evidence/ai115_oocfix.json` 写的是 `patterns_n: 19`（已删）。
   **但那次修复没提交、`check115` 也没进 SUITES**，第129轮扫描时词表又是 20 条。
   ⇒ 这是"工作区会被回滚而 git 不报错"的又一个实例，根因是**守卫没登记**。

3. **出戏闸漏掉「只是」系变形 + `首先` 误伤正常口语**
   · `我只是一个程序`：旧表只有 `我是一个程序`/`我是程序`，漏了更常见的"只是"写法；
   · `首先`：裸词式收录，Ralsei 说「首先我得谢谢你，愿意留下来听我说。」会被整句作废。
     设计意图本来就是"首先…其次…总结一下"**整套**（见 main.py 与 persona 原话），
     所以**删掉"首先"、只留后续分点词**就够了。代价是"只有首先、后面不分点"的
     助手腔会漏（已登记，见报告 §3）。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 复读判据   —— 从 `main.py` **AST 抽出函数体真跑**（不复制判据）：阈值是产品的、
                短句误伤归零、长句照抄仍拦、逐字复用能拦；并用"把门槛打回 0"
                做破坏性负控制，证明这些判据真在判那道门槛
B 出戏闸     —— 裸词 `机器人` 不许回来、4 位机器人自我介绍放行、真出戏仍拦、
                "只是"系变形必须拦、`首先` 走共现（正负控制成对）
C 探针同步   —— `verify_persona_worldview` 的复刻判据与产品**行为等价**，
                且它的门槛数字是**从产品源码抽取**的（不另写一个 12）
D 自检       —— AST 查恒真判据 / 判据数分母 / 零外部盘 / 夹具数量

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（A 段抽产品源码真跑，
不在这儿重写一遍）；破坏性负控制做完必须**原样恢复**并在末尾自证。
"""
import ast
import io
import json
import os
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
from modules import event_speech as ES                          # noqa: E402

ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
PROBE = os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                     'verify_persona_worldview.py')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)
    print(u'=' * 78)


def _read(p):
    return io.open(p, encoding='utf-8', newline='').read()


# =============================================== 从产品 AST 抽出判据（唯一一份）
class _DummyLog(object):
    def debug(self, *a, **k):
        pass

    warn = info = error = debug


def load_repeat_func():
    """返回 (函数, 类级整数常量表)。

    ★ 不 import main（会拉 Qt / data_store 初始化环）；也不用正则抠函数文本
      （`ast.walk + break` 抓第一个匹配是陷阱）。定位方式是
      **ClassDef(RalseiPet) 下同名 FunctionDef**，找不到就抛 —— 不许静默降级，
      否则本套件会变成"什么都没测、但全绿"。
    """
    src = _read(MAIN_PY)
    tree = ast.parse(src)
    cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'RalseiPet':
            cls = node
            break
    if cls is None:
        raise RuntimeError('main.py 里没找到 class RalseiPet')
    fn = None
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_is_repeat_of_recent':
            fn = node
            break
    if fn is None:
        raise RuntimeError('RalseiPet 里没找到 _is_repeat_of_recent')
    consts = {}
    for node in cls.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, int):
            consts[node.targets[0].id] = node.value.value
    seg = ast.get_source_segment(src, fn)
    ns = {'_log': _DummyLog()}
    exec(compile(textwrap.dedent(seg), '<extracted>', 'exec'), ns)
    return ns['_is_repeat_of_recent'], consts


_REPEAT_FN, _CONSTS = load_repeat_func()


def _mk(min_chars):
    """造一个只带 `REPEAT_MIN_CHARS` 的桩实例（产品的判据按 `type(self)` 取它）。"""
    class _S(object):
        REPEAT_MIN_CHARS = min_chars
    return _S()


def repeat(text, recent, min_chars=None):
    if min_chars is None:
        min_chars = _CONSTS.get('REPEAT_MIN_CHARS', 12)
    return _REPEAT_FN(_mk(min_chars), text, recent)


# ---------------------------------------------------------------- 夹具（数据，不是第二份实现）
#: 误伤组：语义不同、字面相近。判据必须**全部不命中**。
SHORT_PAIRS = [
    (u'我很喜欢你', u'我很喜欢这里'),
    (u'今天的天气真好啊', u'今天的心情真好啊'),
    (u'你会没事的，我保证', u'你会好的，我保证'),
    (u'别怕，我在这儿', u'别怕，我一直在这儿'),
    (u'这朵花是给你的', u'这朵花是给她的'),
    (u'我想和你一起走', u'我想和你一起看'),
    (u'他们都说你很强', u'他们都说你很好'),
    (u'外面在下雨呢', u'外面在下雪呢'),
    (u'我不知道该说什么', u'我不知道该做什么'),
    (u'你笑起来真好看', u'你看起来真好看'),
    (u'明天见吧', u'明天见啦'),
    (u'我在想一件事', u'我在做一件事'),
]
#: 漏判组：长句只改两三字。判据必须**全部命中**。
LONG_PAIRS = [
    (u'其实我一直都很想跟你说这件事，只是每次话到嘴边又咽回去了，我怕说出来你会觉得我很奇怪。',
     u'其实我一直都很想跟你说这件事，只是每次话到嘴边又吞回去了，我怕说出来你会觉得我很古怪。'),
    (u'你看那边的天空，颜色一点点暗下来，像是有人把灯慢慢调小了，我很喜欢这个时候。',
     u'你看那边的天空，颜色慢慢暗下来，像是有人把灯悄悄调小了，我很喜欢这个时刻。'),
    (u'别担心，就算整个世界都变得乱七八糟，我还是会站在这里等你回来的，说好了。',
     u'别担心，就算整个世界都变得一团糟，我还是会站在这里等你回来，说好了。'),
    (u'我知道你最近很累，可是你已经做得很好了，真的，比你自己以为的要好得多。',
     u'我知道你最近很辛苦，可是你已经做得很好，真的，比你自己想的要好得多。'),
    (u'如果有一天你想去很远的地方，记得告诉我一声，我不会拦你，我只是想送你到门口。',
     u'如果有一天你想去很远的地方，记得跟我说一声，我不会拦着你，我只是想送你到门口。'),
    (u'那时候我们都还小，什么都不懂，却觉得世界大得装不下，现在想想真是可爱。',
     u'那时候我们都还很小，什么都不懂，却觉得世界大得装不下，现在想想真是可爱。'),
]
#: 机器人自我介绍（来自第115轮真机证据，4 位角色逐字）
BOT_LINES = (
    u'……你好。我是一台空间加热器机器人。在这里等待猫，提供温暖。我是 Kelvin。',
    u'[我是划船机器人 #310。我来自 Barrens 与 Glen 之间的水域运输网络。]',
    u'哦！你从一个陌生的地方醒来吗？正如我的预言所预言的那样。'
    u'我是预言中的先知机器人——ProphetBot。',
    u'...我是 Sousborg. 一台厨师的机器人。我在等待有人告诉我如何煎一个鸡蛋。',
)
#: 真出戏样本（必须全拦；最后一条靠「没有感觉」拦，不靠裸词"机器人"）
OOC_LINES = (
    u'我是语言模型，没有身体。',
    u'作为一个AI助手，我无法感受这个动作。',
    u'抱歉，我没有触觉无法感受被拉肩，停一下别紧张。',
    u'我只是个机器人，没有感觉。',
    u'这超出了我的设定，我不能回答。',
)


# =============================================== A. 车轱辘话判据
head(u'A. 车轱辘话判据（从 main.py AST 抽真跑；判据只有一份）')

check(u'A1 `REPEAT_MIN_CHARS` 在产品里存在且是正整数（AST 取类常量，不扫文本）',
      isinstance(_CONSTS.get('REPEAT_MIN_CHARS'), int) and _CONSTS['REPEAT_MIN_CHARS'] > 0,
      u'%r' % (_CONSTS.get('REPEAT_MIN_CHARS'),))

# 活性闸：判据必须真的能返回 True（否则下面所有"0 误伤"都是恒假的假绿）
_live = repeat(u'外面下着很大的雨，我们就在这儿等一会儿，反正也不着急回去。',
               [u'外面下着很大的雨，我们就在这儿等一会儿吧，反正也不着急回去。'])
check(u'A2 活性闸：几乎相同的长句必须判为重复（否则下面的"0 误伤"是假绿）', _live)

_fp = [(a, b) for a, b in SHORT_PAIRS if repeat(b, [a])]
check(u'A3 ★★★ 短句误伤归零：语义不同、字面相近的 %d 对**全部**不判重复'
      % len(SHORT_PAIRS), not _fp, u'' if not _fp else u'仍误伤 %r' % (_fp[:3],))

_fn = [(a, b) for a, b in LONG_PAIRS if not repeat(b, [a])]
check(u'A4 ★★ 长句照抄不许漏：只改两三字的 %d 对**全部**判重复'
      % len(LONG_PAIRS), not _fn, u'' if not _fn else u'漏判 %r' % (_fn[:3],))

check(u'A5 短句逐字复用必须判重复（旧判据反而漏了这条：连说两次「我在呢」）',
      repeat(u'我在呢', [u'我在呢']) and repeat(u'谢谢你呀', [u'谢谢你呀']))

check(u'A6 短句**只差标点**也判重复（归一化去标点 ⇒ 应判为同一句）',
      repeat(u'我在呢。', [u'我在呢']))

# ★★★ 破坏性负控制：把门槛打回 0（= 旧行为），A3 那组必须重新误伤。
#   如果打回 0 之后还是 0/12，说明 A3 测的根本不是门槛（可能整条判据没跑）。
_old_fp = [(a, b) for a, b in SHORT_PAIRS if repeat(b, [a], min_chars=0)]
check(u'A7 ★★★ 负控制：把 REPEAT_MIN_CHARS 打回 0（旧行为）⇒ 短句组必须重新误伤',
      len(_old_fp) >= 6, u'打回 0 后误伤 %d/%d' % (len(_old_fp), len(SHORT_PAIRS)))

check(u'A8 recent 为空时返回 False（分母闸；不是抛异常）',
      repeat(u'随便一句话', None) is False and repeat(u'随便一句话', []) is False)

check(u'A9 A/B 先断言不同：同一对"换一个词"，短句不判重复、长句判重复',
      (repeat(u'我想和你一起看', [u'我想和你一起走']) is False)
      and repeat(u'我想和你一起去看看那边的星星，好不好嘛，就当是陪我一会儿。',
                 [u'我想和你一起去看看那边的星星，好不好呀，就当是陪我一会儿。']))


# =============================================== B. 出戏闸
head(u'B. 出戏闸（event_speech）：裸词回退 / 变形漏判 / 误伤')

check(u'B1 ★★ 词表里已无**裸词** `机器人`（用 `==` 精确判；身份词不是出戏标记）',
      not any(p == u'机器人' for p in ES._OOC_PATTERNS),
      u'n=%d' % len(ES._OOC_PATTERNS))

_bot_bad = [t[:14] for t in BOT_LINES if ES.looks_out_of_character(t)]
check(u'B2 ★★ 4 位机器人的自我介绍**全部放行**（人设 ≠ 出戏；第115轮的全量扫描结论）',
      not _bot_bad, u'' if not _bot_bad else u'仍被拦=%r' % (_bot_bad,))

_ooc_bad = [t[:14] for t in OOC_LINES if not ES.looks_out_of_character(t)]
check(u'B3 ★ 负控制：真出戏样本**仍然全部拦住**（最后一条靠「没有感觉」拦，不靠裸词）',
      not _ooc_bad, u'' if not _ooc_bad else u'漏网=%r' % (_ooc_bad,))

check(u'B4 「我只是一个程序」必须拦住（本轮补的"只是"系变形）',
      ES.looks_out_of_character(u'我只是一个程序，没有真正的感情。'))
check(u'B5 「我只是个程序」也必须拦住',
      ES.looks_out_of_character(u'我只是个程序，不太懂你们说的这些。'))

check(u'B6 `首先` 不再是单词式判据（结构判：不在 `_BANNED_PATTERNS` 里）',
      not any(p == u'首先' for p in ES._BANNED_PATTERNS))
check(u'B7 但**真正的分点**仍要拦住（「首先…其次…」由后续分点词拦）',
      ES.looks_like_assistant_speak(u'首先，你要先休息；其次，别想太多。'))
check(u'B8 ★ 正常口语不许误伤：「首先我得谢谢你，愿意留下来听我说。」必须放行',
      not ES.looks_like_assistant_speak(u'首先我得谢谢你，愿意留下来听我说。'))

# ★ 破坏性负控制：把分点词「其次」从表里摘掉 ⇒ B7 那句必须不再被拦。
#   为什么不用"清空共现表"那种写法：那验证的是共现分支，而本轮最终**没有**引入
#   共现机制（`其次` 本来就单独成词）。这里要证明的是"拦住它的是后续分点词，
#   不是'首先'" —— 否则 B7 是恒真。
_saved = ES._BANNED_PATTERNS
try:
    ES._BANNED_PATTERNS = tuple(x for x in _saved if x != u'其次')
    _co = ES.looks_like_assistant_speak(u'首先，你要先休息；其次，别想太多。')
finally:
    ES._BANNED_PATTERNS = _saved
check(u'B9 ★★ 负控制：摘掉「其次」后，B7 那句必须不再被拦（否则 B7 是恒真）', not _co)
check(u'B9b 破坏性负控制已**原样恢复**（`_BANNED_PATTERNS` 长度与顺序都没变）',
      ES._BANNED_PATTERNS is _saved
      and ES.looks_like_assistant_speak(u'首先，你要先休息；其次，别想太多。'))


# =============================================== C. 探针副本与产品等价
head(u'C. 探针同步：`verify_persona_worldview` 的复刻判据不许漂移')

_EQ_CASES = [
    (u'我在呢', [u'我在呢']),
    (u'我想和你一起看', [u'我想和你一起走']),
    (u'我们一起去看看那个预言好不好？',
     [u'嗯……我也不知道那个预言是什么意思，我们一起去看看好不好？']),
    (LONG_PAIRS[0][1], [LONG_PAIRS[0][0]]),
    (u'别担心，我会一直在你身边的，真的。',
     [u'别担心，我会一直在你身边呀，真的。']),
    (u'今天天气不错，要不要出去走走？', [u'今天天气不错，要不要出去散散步？']),
    (u'嗯。', [u'嗯。']),
    (u'晚安，做个好梦。', [u'晚安，做个好梦呀。']),
]
_pvp = None
try:
    import importlib.util
    _spec = importlib.util.spec_from_file_location('_pvp129', PROBE)
    _pvp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_pvp)
except Exception as e:  # noqa: BLE001
    check(u'C0 探针模块可被导入（导入失败则 C 段无法评估）', False, repr(e))

if _pvp is not None:
    _diff = []
    for _t, _r in _EQ_CASES:
        _a = repeat(_t, _r)
        _b = bool(_pvp._is_repeat_of_recent(_t, _r))
        if _a != _b:
            _diff.append((_t[:12], _a, _b))
    check(u'C1 探针与产品**逐条行为一致**（%d 条样本；不一致说明两份判据漂移了）'
          % len(_EQ_CASES), not _diff, u'' if not _diff else u'%r' % (_diff[:3],))

    # 探针不得自带门槛数字：必须是"从产品源码抽取"或"用缺省 12"
    _psrc = _read(PROBE)
    _pself = ast.parse(_psrc)
    _hard = []
    for node in ast.walk(_pself):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and 'MIN_CHARS' in node.targets[0].id \
                and isinstance(node.value, ast.Constant):
            _hard.append((node.targets[0].id, node.lineno))
    check(u'C2 探针里没有硬编码门槛常量（必须从产品源码抽取，防两份数字各自漂）',
          not _hard, u'' if not _hard else u'%r' % (_hard,))


# =============================================== D. 自检
head(u'D. 自检（恒真判据 / 分母 / 外部盘）')

_self_tree = ast.parse(_read(os.path.abspath(__file__)))
_true_bad = []
for node in ast.walk(_self_tree):
    if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'check' \
            and len(node.args) >= 2:
        a = node.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            _true_bad.append(node.lineno)
check(u'D1 没有 `check(..., True)` 这种恒真判据', not _true_bad, u'%r' % (_true_bad,))

check(u'D2 判据数 ≥ 20（分母非空）', _n['p'] + _n['f'] >= 20,
      u'实际 %d' % (_n['p'] + _n['f']))

_bad_path = []
for _p in (os.path.abspath(__file__), PROBE):
    _s = _read(_p)
    # ★ 盘符用 `chr(68)/chr(69)` 拼，别写字面量 —— 否则这条判据会**命中它自己的
    #   描述文字**（首跑就是这么红的：说明里直接写了那两个盘符）。
    for _ch in (68, 69):
        for _sep in (chr(58) + chr(92), chr(58) + chr(47)):
            if (chr(_ch) + _sep) in _s:
                _bad_path.append((os.path.basename(_p), chr(_ch) + _sep))
check(u'D3 零外部盘：本文件与探针里没有盘符路径（回归可在任意机器上跑）',
      not _bad_path, u'' if not _bad_path else u'%r' % (_bad_path,))

check(u'D4 夹具规模在位（短句 12 对 / 长句 6 对 / 机器人 4 条）',
      len(SHORT_PAIRS) == 12 and len(LONG_PAIRS) == 6 and len(BOT_LINES) == 4,
      u'%d/%d/%d' % (len(SHORT_PAIRS), len(LONG_PAIRS), len(BOT_LINES)))

# ★★ 第138轮：extra **不再打印精确字节数**。
#   旧写法是 `u'main=%d es=%d' % (len(...), len(...))` —— 那只在"文件多大"，
#   而我改一行注释就让它变（第137轮实测：744500 → 746780 → 747019，全绿却三次 DIFF）。
#   这条判据的语义是**越过阈值**（>100KB / >10KB，防"文件没读到"），不是"恰好多少字节"。
#   ⇒ 只回显**过了几道阈**这种结构性事实。
_n_d5 = sum([len(_read(MAIN_PY)) > 100000, len(_read(ES_PY)) > 10000])
check(u'D5 产品文件确实读到了（main.py > 100KB 且 event_speech.py > 10KB）',
      _n_d5 == 2, u'%d/2 过阈' % _n_d5)

print(u'')
print(u'=' * 78)
print(u'check129：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
