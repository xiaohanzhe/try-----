# -*- coding: utf-8 -*-
"""第140轮回归锁：`length_policy` 从**死数据**变成**真执行的规格**（只执行字数那一半）。

## 这一轮在做什么

第139轮把「一次说几句」这条规格的三份写法数清了：人文本 / 机器可读的
`length_policy` / 提示词里的 ①。当时删掉了第三份（派生品），留下两个问题：
`length_policy` 仍然是**全仓零读取**的死数据，真正生效的是 `_clean_ai_reply`
里硬写的 `AI_REPLY_MAX_CHARS = 220`。

本轮把执行点接到卡片上，并且**只接字数那一半**。

## 为什么句数那一半不执行（这是本轮的结论，不是没做完）

先把"到底有多少条不遵守"量清楚。★★ 第139轮那个 83.3% 是**切句口径的产物**：
它把 `…` 当句号，而人设第 57 行写着「用省略号让声音软下来：**很少用，别拿它当句号**」
—— 拿省略号当句号去判人设的遵守率，尺子本身就是错的。

同一批 48 轮，换切法：

| 切句口径 | >3 句 |
|---|---|
| 含 `…`（第139轮） | 40/48 = 83.3% |
| 不含 `…`（人设口径） | 31/48 = 64.6% |
| 不含 `…` 且引号内不切 | 24/48 = 50.0% |

再放大到**全体角色**（`第113轮/_evidence/raw30/` 77 份语料，5592 条真机回复）：

| 句数 | 条数 | 占比 | 累计 ≥N |
|---|---|---|---|
| 1 | 618 | 11.1% | 98.7% |
| 2 | 777 | 13.9% | 87.6% |
| **3** | **996** | **17.8%** | **73.7%** |
| 4 | 980 | 17.5% | 55.9% |
| 5 | 767 | 13.7% | 38.4% |
| 6 | 538 | 9.6% | 24.7% |
| 8 | 230 | 4.1% | 8.7% |

**中位数是 4 句**、**44.1% 的回复在 3 句以内**。
⚠️ "≥3 句 73.7%" 与 "按 3 句砍会动 73.7%" **不是一回事**：后者只动 `>3` 句的，
实际是 **55.9%**（`>6` 句是 **15.1%**）。这两个数我第一次写错过一次 ——
靠把证据落成 `_evidence/length140.json` 再回头核才发现，别凭印象引用。
而那批 6 句的回复平均才 **150 字**、**还在字数预算内**。

⇒ 句子数多 ≠ 话太多。它是**目标倾向**，不是"超了就砍"的闸；硬执行等于把结尾那半句
（人设要求的「先补一句我自己的感受」正好在结尾）系统性地削掉。
所以本轮只执行 `max_chars`，`max_sentences` **读进来、不用去截断** ——
并且用 E 段把它钉成"显式不执行"，防止以后有人凭直觉悄悄接上。

## 本套件守什么

A 数据面：96 张卡里 77 张带规格，且**全部是 (200, 3)**（统一，才谈得上"取一份"）
B 读取层：`npc_persona.training_length_policy` 的真值 / 缺卡 / 坏卡 / bool 冒充 int
C 结算层：`reply_length_limits` 只许**收紧**全局兜底，不许放宽
D 行为面：真 `_clean_ai_reply` —— 210 字被截到 ≤200、195 字不动（成对）、
  卡不可用时回落到 220（破坏性负控制）、且**其余护栏没被我改哑**（D6 是最贵的一条）
E 不执行的显式登记：`max_sentences` 在 `_clean_ai_reply` 里**没有**参与任何比较/调用
F 常量面：220 / 24 / 40 一个没被偷改
G 自检

★ 零网络；Qt 用 offscreen（D 段要 `import main`，而 main 顶部 import 了 PyQt5）。
★ 临时卡片写在系统 temp（`tempfile.mkdtemp`），**不碰工作区**、不依赖 E 盘。
"""
import ast
import builtins
import io
import json
import os
import shutil
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
NP_PY = os.path.join(PET, 'modules', 'npc_persona.py')
CD_PY = os.path.join(PET, 'modules', 'companion_dialog.py')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
CARDS_DIR = os.path.join(PET, 'assets', 'npc', '_training', 'cards')
CARD_JSON = os.path.join(CARDS_DIR, 'ralsei.json')

sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, PET)

import main as M                                                # noqa: E402
from modules import npc_persona as NP                            # noqa: E402
from modules import companion_dialog as CD                       # noqa: E402
from modules import event_speech as ES                           # noqa: E402

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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


class Stub(object):
    """与回归里那二十几个桩**同形**：只绑 `_clean_ai_reply` 一个方法。

    ★ D 段用它、不直接用 `RalseiPet` 实例：第140轮第一版把长度结算写成
      `self._reply_length_policy()`，桩上没有这个属性 ⇒ `AttributeError` ⇒
      被本方法自己的 `except` 静默吞掉 ⇒ 整条护栏返回原文不洗（13 条判据一起红）。
      这个桩就是那条坑的复现装置。
    """
    AI_REPLY_MAX_CHARS = M.RalseiPet.AI_REPLY_MAX_CHARS

    def _clean_ai_reply(self, reply, recent=None, speaker=None):
        return M.RalseiPet._clean_ai_reply(self, reply, recent, speaker)


def body(n, tail=u'\u3002'):
    """造一条 n 个字的回复：整句重复，保证截断点落在句末标点上。"""
    unit = u'\u6211\u5728\u8fd9\u91cc\u966a\u7740\u4f60\u5462\uff0c\u4f60\u6162\u6162\u8bf4\u3002'
    s = unit * (n // len(unit))
    rest = n - len(s)
    if rest:
        s += (u'\u597d' * (rest - 1) + tail) if rest > 1 else tail
    return s


def _tmp_card(dirname, name, payload):
    """在临时 assets 树里造一张卡，返回 assets 根目录（供 assets_dir 参数用）。"""
    d = os.path.join(dirname, 'assets', 'npc', '_training', 'cards')
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(os.path.join(d, name + '.json'), 'w', encoding='utf-8', newline='') as f:
        f.write(payload if isinstance(payload, str) else json.dumps(payload))
    return os.path.join(dirname, 'assets')


_CARDS = sorted([p for p in os.listdir(CARDS_DIR) if p.endswith('.json')])
_POLICIES = {}
for _f in _CARDS:
    _d = _json(os.path.join(CARDS_DIR, _f))
    _lp = _d.get('length_policy') if isinstance(_d, dict) else None
    if isinstance(_lp, dict):
        _POLICIES[_f[:-5]] = (_lp.get('max_chars'), _lp.get('max_sentences'))

# =============================================== A 数据面
head(u'A. 数据面：96 张卡里 77 张带规格，且全部同值（统一才谈得上"取一份"）')

check(u'A0 分母非空：卡片目录读得到，且带 `length_policy` 的卡不是 0 张',
      len(_CARDS) > 0 and len(_POLICIES) > 0,
      u'卡 %d 张 / 带规格 %d 张' % (len(_CARDS), len(_POLICIES)))
check(u'A1 带规格的卡**分布唯一** == {(200, 3)}（一旦分角色不同，"按一张取"就不成立）',
      set(_POLICIES.values()) == {(200, 3)},
      u'分布=%r' % (sorted(set(_POLICIES.values())),))
check(u'A2 每张卡的 `max_chars`/`max_sentences` 都是**真 int**（不是 "200" / true）',
      all(type(v[0]) is int and type(v[1]) is int for v in _POLICIES.values()))
check(u'A3 主宠 ralsei 在带规格的卡里且是 (200, 3)',
      _POLICIES.get('ralsei') == (200, 3))
check(u'A4 另有卡**不带**规格（说明"缺卡回落"不是假想分支，盘上真有这种卡）',
      len(_POLICIES) < len(_CARDS),
      u'不带规格 %d 张' % (len(_CARDS) - len(_POLICIES)))

# =============================================== B 读取层
head(u'B. 读取层：`training_length_policy` 的取真值 / 缺卡 / 坏卡 / bool 冒充 int')

NP._POLICY_CACHE.clear()
check(u'B1 ralsei → (200, 3)', NP.training_length_policy('ralsei') == (200, 3),
      u'实测=%r' % (NP.training_length_policy('ralsei'),))
check(u'B2 未登记的角色 → None（不猜默认值）',
      NP.training_length_policy('who_is_this') is None)
check(u'B3 非法入参（空串 / None / 数字）→ None 且不抛',
      NP.training_length_policy('') is None
      and NP.training_length_policy(None) is None
      and NP.training_length_policy(123) is None)

_TMP = tempfile.mkdtemp(prefix='check140_')
try:
    # 负控制 1：`max_chars` 写成字符串 —— 校验必须拒收（否则 int("200") 会悄悄通过）
    _a1 = _tmp_card(os.path.join(_TMP, 's1'), 'x_str', {
        'length_policy': {'max_chars': '200', 'max_sentences': 3}})
    NP._POLICY_CACHE.clear()
    check(u'B4 坏卡（`max_chars` 是字符串）→ None（负控制：校验真在跑）',
          NP.training_length_policy('x_str', _a1) is None)

    # 负控制 2：`max_chars: true` —— `isinstance(True, int)` 为 True，
    #   用 isinstance 写会把 true 当成 1，静默变成"每条都截到 1 个字"。这是专治写法的那条。
    _a2 = _tmp_card(os.path.join(_TMP, 's2'), 'x_bool', {
        'length_policy': {'max_chars': True, 'max_sentences': 3}})
    NP._POLICY_CACHE.clear()
    check(u'B5 坏卡（`max_chars: true`）→ None（`isinstance(True, int)` 是陷阱）',
          NP.training_length_policy('x_bool', _a2) is None)

    # 负控制 3：缺字段 / 0 / 负数 一律拒收
    _a3 = _tmp_card(os.path.join(_TMP, 's3'), 'x_zero', {
        'length_policy': {'max_chars': 0, 'max_sentences': 3}})
    NP._POLICY_CACHE.clear()
    check(u'B6 坏卡（`max_chars: 0`）→ None（0 字上限等于把话全吃掉）',
          NP.training_length_policy('x_zero', _a3) is None)
finally:
    shutil.rmtree(_TMP, ignore_errors=True)

NP._POLICY_CACHE.clear()
_first = NP.training_length_policy('ralsei')
_calls = {'n': 0}
_orig_open = builtins.open


def _count_open(*a, **k):
    _calls['n'] += 1
    return _orig_open(*a, **k)


builtins.open = _count_open
try:
    _second = NP.training_length_policy('ralsei')
finally:
    builtins.open = _orig_open
check(u'B7 进程内缓存真生效（第二次调用不再读盘）',
      _first == _second and _calls['n'] == 0,
      u'第二次调用读盘 %d 次' % _calls['n'])

# =============================================== C 结算层
head(u'C. 结算层：`reply_length_limits` 只许收紧全局兜底，不许放宽')

check(u'C1 (ralsei, 220) → (200, 3)：卡片比兜底更严 ⇒ 用卡片',
      NP.reply_length_limits('ralsei', 220) == (200, 3),
      u'实测=%r' % (NP.reply_length_limits('ralsei', 220),))
check(u'C2 (未登记, 220) → (220, 0)：回落兜底，且句数标记为"不限"',
      NP.reply_length_limits('who_is_this', 220) == (220, 0),
      u'实测=%r' % (NP.reply_length_limits('who_is_this', 220),))
check(u'C3 (ralsei, 100) → (100, 3)：**更严的兜底仍然赢**（卡片不许放宽）',
      NP.reply_length_limits('ralsei', 100) == (100, 3),
      u'实测=%r' % (NP.reply_length_limits('ralsei', 100),))
check(u'C4 (ralsei, 500) → (200, 3)：宽松的兜底不会把卡片顶掉',
      NP.reply_length_limits('ralsei', 500) == (200, 3),
      u'实测=%r' % (NP.reply_length_limits('ralsei', 500),))
check(u'C5 `hard` 非法（None / 0 / 非数字）→ 220（兜底不许变成 0 或崩溃）',
      NP.reply_length_limits('who_is_this', None)[0] == 220
      and NP.reply_length_limits('who_is_this', 0)[0] == 220
      and NP.reply_length_limits('who_is_this', 'x')[0] == 220)

# =============================================== D 行为面
head(u'D. 行为面：真 `_clean_ai_reply` —— 卡片压过 220，且其余护栏没被改哑')

_st = Stub()
_d210 = _st._clean_ai_reply(body(210))
_d195 = _st._clean_ai_reply(body(195))
_d225 = _st._clean_ai_reply(body(225))

check(u'D0 分母非空：三条样本都真取到了输出',
      bool(_d210) and bool(_d195) and bool(_d225))
check(u'D1 210 字 → 截到 **≤200**（改造前是 220，会整条放过）',
      _d210 is not None and len(_d210) <= 200,
      u'原 210 → 出 %d' % (len(_d210) if _d210 else 0))
check(u'D2 成对：195 字**原样不动**（证明 D1 不是"见长就砍"）',
      _d195 == body(195),
      u'原 195 → 出 %d' % (len(_d195) if _d195 else 0))
check(u'D3 截断落在**句末标点**上（不吊尾巴）',
      bool(_d210) and _d210[-1] in u'。！？!?…',
      u'末字=%r' % ((_d210 or u'')[-1:],))

# ★ 破坏性负控制：把读卡这件事整个掐掉 ⇒ 必须回落到 220 —— 210 字**不再被截**
_orig_tlp = NP.training_length_policy
NP._POLICY_CACHE.clear()
NP.training_length_policy = lambda *_a, **_k: None
try:
    _no_card_210 = Stub()._clean_ai_reply(body(210))
    _no_card_225 = Stub()._clean_ai_reply(body(225))
finally:
    NP.training_length_policy = _orig_tlp
    NP._POLICY_CACHE.clear()
check(u'D4 负控制（读不到卡）⇒ 210 字**原样**（证明 D1 真的依赖卡片，不是恒真）',
      _no_card_210 == body(210),
      u'原 210 → 出 %d' % (len(_no_card_210) if _no_card_210 else 0))
check(u'D5 负控制同一支：读不到卡时 225 字仍被兜底 220 截（兜底没跟着失效）',
      _no_card_225 is not None and len(_no_card_225) <= 220 < 225,
      u'原 225 → 出 %d' % (len(_no_card_225) if _no_card_225 else 0))

check(u'D6 换 speaker 拿到同一套限额（77 张卡同规格 ⇒ 按谁取都一样）',
      Stub()._clean_ai_reply(body(210), speaker='ut_sans')
      == Stub()._clean_ai_reply(body(210), speaker=None))

# ★★ 最贵的一条：护栏**其余各步**不许被我改哑。
#    第140轮第一版就是这样翻车的 —— 一个 AttributeError 被 except 吞掉，
#    整条护栏原样返回，13 条老判据一起红。这里用三条老能力做哨兵。
_sent = {
    u'md': u'**\u542c\u5230\u4e5f\u8ba9\u6211\u5fc3\u91cc\u6696\u6696\u7684**\u3002\u522b\u592a\u7d2f\u4e86\u3002',
    u'role': u'\u88ab\u9a82\u4e86\u2026\u2026\u6211\u5148\u966a\u7740\u4f60\u3002\n\u4e3b\u4eba\uff1a\u8001\u677f\u8bf4\u6211\u4e1a\u7ee9\u4e0b\u6ed1\u4e86',
    u'quote': u'\u201c\u4eca\u5929\u8f9b\u82e6\u4e86\uff0c\u65e9\u70b9\u4f11\u606f\u54e6\u3002\u201d',
}
_out = {k: Stub()._clean_ai_reply(v) for k, v in _sent.items()}
check(u'D6b 0b markdown 剥除**仍生效**（护栏没整体哑掉）',
      u'**' not in (_out[u'md'] or u''), u'出=%r' % (_out[u'md'],))
check(u'D6c 第 1 步自问自答截断**仍生效**',
      u'主人' not in (_out[u'role'] or u''), u'出=%r' % (_out[u'role'],))
check(u'D6d 包裹引号剥除**仍生效**',
      bool(_out[u'quote']) and _out[u'quote'][0] not in u'"\'“”「」『』《》',
      u'出=%r' % (_out[u'quote'],))

# =============================================== E 不执行的显式登记
head(u'E. `max_sentences` **不参与截断** —— 把"不做"钉成判据，防以后凭直觉接上')

_tree = ast.parse(_read(MAIN_PY))
_fn = None
for _node in ast.walk(_tree):
    if isinstance(_node, ast.FunctionDef) and _node.name == '_clean_ai_reply':
        _fn = _node
        break
check(u'E0 定位到 `_clean_ai_reply` 函数体（否则下面几条恒真）', _fn is not None)

_sent_names = []
if _fn is not None:
    for _node in ast.walk(_fn):
        if isinstance(_node, ast.Name) and 'sent' in _node.id.lower():
            _sent_names.append((_node.id, type(_node.ctx).__name__))
_stores = [n for n, c in _sent_names if c == 'Store']
_loads = [n for n, c in _sent_names if c == 'Load']
check(u'E1 句数额度只被**赋值**、从没被**读取**（`_max_sent` 有 Store 无 Load）',
      bool(_stores) and not _loads,
      u'Store=%r Load=%r' % (sorted(set(_stores)), sorted(set(_loads))))

_calls_with_sent = 0
if _fn is not None:
    for _node in ast.walk(_fn):
        if not isinstance(_node, ast.Call):
            continue
        _args = list(_node.args) + [k.value for k in _node.keywords]
        for _a in _args:
            if isinstance(_a, ast.Name) and 'sent' in _a.id.lower():
                _calls_with_sent += 1
check(u'E2 句数额度**没有**被当实参传给任何函数（不存在"偷偷接上一道句数截断"）',
      _calls_with_sent == 0, u'实参处数=%d' % _calls_with_sent)

# ★ E3 也走 AST。第一版写成 `"max_sentences" in 源码`，被**自己的文档串**喂饱了：
#   变异 M5 把 `lp.get('max_sentences')` 换成 `3`（字段彻底不碰），E3 照样绿
#   —— 文档串里还写着 `max_sentences` 呢。这是"禁某名字出现"类判据的老坑，
#   只是这次反过来（要求出现）：**名字在注释里 ≠ 代码在读它**。
_np_tree = ast.parse(_read(NP_PY))
_tlp = None
for _nd in ast.walk(_np_tree):
    if isinstance(_nd, ast.FunctionDef) and _nd.name == 'training_length_policy':
        _tlp = _nd
        break
_sent_read = 0
if _tlp is not None:
    for _nd in ast.walk(_tlp):
        if (isinstance(_nd, ast.Call) and isinstance(_nd.func, ast.Attribute)
                and _nd.func.attr == 'get' and _nd.args
                and isinstance(_nd.args[0], ast.Constant)
                and _nd.args[0].value == 'max_sentences'):
            _sent_read += 1
        if (isinstance(_nd, ast.Subscript) and isinstance(_nd.slice, ast.Constant)
                and _nd.slice.value == 'max_sentences'):
            _sent_read += 1
check(u'E3 但字段本身**真的被读了**（`training_length_policy` 里真取 `max_sentences`，'
      u'不是只在文档里提一嘴）',
      _sent_read >= 1, u'取值处数=%d' % _sent_read)

# ★ E4 走 AST 而不是文本扫：`"def xxx" in 源码` 会被注释/文档串误伤
#   —— 本项目栽过六次（第108轮起每次都记一笔），这里不再重复。
_forbid = {'trim_to_sentences', 'keep_sentences', 'cap_sentences', 'clip_sentences'}
_found_defs = set()
for _p in (MAIN_PY, NP_PY):
    # ★ 循环变量别用 `_n` —— 它是本文件的记账字典，覆盖了就是
    #   `TypeError: 'Load' object is not subscriptable`（本轮实测踩到一次）。
    for _nd in ast.walk(ast.parse(_read(_p))):
        if isinstance(_nd, ast.FunctionDef) and _nd.name in _forbid:
            _found_defs.add(_nd.name)
check(u'E4 本轮没有造"句数截断"这个能力（main / npc_persona 里零定义）',
      not _found_defs, u'找到=%r' % (sorted(_found_defs),))

# =============================================== F 常量面
head(u'F. 常量面：兜底 220 / 事件 24 / 主动开口 40，一个都没被偷改')

check(u'F1 `AI_REPLY_MAX_CHARS` 仍是 220（本轮只让卡片收紧，不改兜底）',
      M.RalseiPet.AI_REPLY_MAX_CHARS == 220,
      u'实测=%d' % M.RalseiPet.AI_REPLY_MAX_CHARS)
check(u'F2 `companion_dialog.MAX_TEXT_CHARS` 仍与兜底同值（那条同值约定没破）',
      CD.MAX_TEXT_CHARS == M.RalseiPet.AI_REPLY_MAX_CHARS,
      u'%d vs %d' % (CD.MAX_TEXT_CHARS, M.RalseiPet.AI_REPLY_MAX_CHARS))
check(u'F3 事件台词 24 / 主动开口 40 未动',
      ES.EVENT_MAX_CHARS == 24 and ES.AUTO_SPEAK_MAX_CHARS == 40,
      u'%d / %d' % (ES.EVENT_MAX_CHARS, ES.AUTO_SPEAK_MAX_CHARS))
_sig = M.RalseiPet._clean_ai_reply.__code__
check(u'F4 `_clean_ai_reply` 的 `speaker` 是**带默认值**的第三参（老调用点不用改）',
      'speaker' in _sig.co_varnames[:4]
      and _sig.co_varnames.count('speaker') == 1,
      u'形参=%r' % (_sig.co_varnames[:4],))

# =============================================== G 自检
head(u'G. 自检：恒真判据 / 标记字面量 / 编码 / 记账守恒')

_SELF = _read(os.path.abspath(__file__))
_self_tree = ast.parse(_SELF)
_trivial = 0
for _node in ast.walk(_self_tree):
    if (isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name)
            and _node.func.id == 'check' and len(_node.args) >= 2):
        _c = _node.args[1]
        if isinstance(_c, ast.Constant) and _c.value is True:
            _trivial += 1
check(u'G1 没有 `check(desc, True)` 这种恒真判据', _trivial == 0,
      u'恒真 %d 处' % _trivial)
# ★ 描述里**不许**出现完整的 `[PASS]` 字样：`run_all.count_results` 是
#   `re.findall(r'\[PASS\]|\[\s*OK\s*\]', text)` —— 数**出现次数**，不是行首。
#   第一版把 `[PASS]` 写进这条判据的描述里，run_all 数出 41、套件自己数出 40，
#   两边差 1 且没人会去查（差点当成"多了一条判据"提交）。
_MARK_P = u'[' + u'PASS]'
_MARK_F = u'[' + u'FAIL]'
check(u'G2 输出标记仍是行首的 `[`+`PASS]` / `[`+`FAIL]` 形式'
      u'（run_all 靠它数 PASS/FAIL，且它是按出现次数数的）',
      _MARK_P in _SELF and _MARK_F in _SELF)
check(u'G3 本文件无 BOM、无 U+FFFD',
      not _SELF.startswith(u'\ufeff') and u'\ufffd' not in _SELF)
# ★ G4 的独立计数器：从**源码 AST 数**本该执行多少条，而不是自己数自己。
#   写 `_n['f'] == len(_failed)` 是恒真的（两者在 check() 里一起加），等于没判。
_src_checks = 0
for _node in ast.walk(_self_tree):
    if (isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name)
            and _node.func.id == 'check'):
        _src_checks += 1
check(u'G4 记账守恒：源码里 %d 处 check() 都真执行了（没有分支把判据跳过去）'
      % _src_checks,
      # `+1` 是 G4 **自己这一处**：源码里数得到它，但执行到这行时它还没记账。
      # 少执行任何一条（被 if 跳过）这个等式就破 —— 这正是要抓的。
      _src_checks == _n['p'] + _n['f'] + 1 and _n['p'] > 0,
      u'源码 %d / 实跑 %d（G4 自身未计入）' % (_src_checks, _n['p'] + _n['f']))

print(u'')
print(u'=' * 78)
print(u'check140：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - ' + _d)
sys.exit(1 if _n['f'] else 0)
