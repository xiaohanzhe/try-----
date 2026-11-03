# -*- coding: utf-8 -*-
u"""第147轮回归锁：硬截兜底**切在半个单词**上时，退到最后一个空格。

## 病（第145轮的遗留①）

第145轮给 `_SENTENCE_ENDS` 加了 ASCII `.`，治掉了"英文有句号却被硬截"。
剩下的那批**24/40 字里一个句末标点都没有**（全大写自造拼写、`hehe that tickles` 连写）
只能走兜底 `t[:max_chars].rstrip(...)` ⇒ `hehe that tickles so mu` —— 切在词中间。

## 改法

抽出 `_hard_cut(t, max_chars)`（原来**三处**各抄一遍，同一份规则三处算），
切点落在 **ASCII 词**中间时退到最后一个空格。两条底线：
① 留下 ≥ `MIN_FIRST_CHARS`；② 留下 ≥ 半个预算。

## ★★★ 本轮最贵的一课：`isalnum()` 对 CJK 也是 True

第一版用 `t[len(cut)].isalnum()` 判"切在词中"。因为中文**每个字都是 alnum**，
于是**每一次中文硬截**都被判成切在词中 ⇒ 退到空格（那空格往往在英文人名前）
⇒ 中文输出被改了 **151 / 57 条**（全量语料 A/B，`_evidence/ab147.json`）。
⇒ 必须限定 **ASCII** 词字符：只有空格分词的文字才有"词边界"。

## 本套件守什么

A 结构：`_hard_cut` 在位、三处调用都走它、代码行里没有旧写法、`_WORDY` **无 CJK**
B 行为：英文整词收尾 / **纯中文与旧规则逐字相同** / 混合文本退到人名前 /
  **两道底线各有一个样本**（空格在第 0 位〔单元级〕/ 退过去不到半个预算）/
  **无空格**不许退 / 长度与前缀性质
C 负控制（成对）：把 `_WORDY` 塞进 CJK，中文样本**必须**被改 —— 否则 B 是恒真
D 自检
"""
import ast
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'modules', 'event_speech.py')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

_n_ok = 0
_n_bad = 0
_failed = []


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _old_hard(t, m):
    u"""**旧规则复刻**（第147轮之前）：只切 + 去尾巴。

    ★ 这是负控制/对账用的独立实现，不是从产品里抄的 —— 若产品退让了，
      两者就会不同，差异正是"本轮改动"。
    """
    return t[:m].rstrip(ES._HARD_CUT_TAIL)


# ---------------------------------------------------------------- 样本
# 故意都不用句末标点（这样才会走到硬截那条兜底）
EN1 = u'hehe that tickles so much i cant even'                    # 24 字处切在 `mu|ch`
EN2 = u'AXIS MODEL 014 READY TO GUARD AND PROTECT THE CORE'       # 40 字处切在 `PROTEC|T`
ZH1 = u'那件事之后我开始试着去理解别人的感受因为我也曾经这样被误解过所以他'
ZH2 = u'今天的风很舒服我想一直坐在这里看着院子里的树叶慢慢飘下来一直看到天黑'
# ★ ZH3 是 C1 的夹具，**必须带空格**：ZH1 一个空格都没有 ⇒ `rfind(' ')` 返回 −1
#   ⇒ 退让分支根本进不去 ⇒ 往 `_WORDY` 里塞汉字毫无反应，C1 会变成"永远绿的空判据"。
#   （第147轮第一次写 C1 就是这么废掉的：负控制输入没落进被测分支。）
#   24 字处切在 `曾|经` 之间，两侧都是汉字 —— 只要白名单含它们就必须退到那个空格。
ZH3 = u'那件事之后我开始试着去理解 别人的感受因为我也曾经被这样误解过'
# 中文句尾接英文人名，24 字处切在 `Noell|e` 中间 ⇒ 退到人名**之前**
# ★ 样本长度必须 > 24：上一版 24 字整 ⇒ 根本不进截断，B4 等于没判。
MIX = u'那件事之后我开始试着去理解别人的感受 Noelle 的'
SHORT = u'well'
# 全文**一个空格都没有**（`'a' + 'bcdef…'` 拼起来就是连续字母，别被名字骗了）⇒
# `rfind(' ')` 返回 −1 ⇒ 没有"最后一个空格"可退 ⇒ 必须原样硬截。中文绝大多数是这种。
NOSPACE = u'a' + u'bcdefghijklmnopqrstuvwxyz'
# 空格在**第 0 位**：退过去只剩空串 ⇒ 底线① 必须挡住。
# ★★ 只能直接喂 `_hard_cut`：两个公开入口（`first_sentence` / `fit_sentences`）
#   开头都有 `t = text.strip()`，前置空格在进函数前就没了 ⇒ 从公开 API **走不到**这条分支。
#   所以这是**单元级**探针，不是"用户能看到的行为"—— 写清楚，免得下一个人以为它管端到端。
SPACE0 = u' ' + u'bcdefghijklmnopqrstuvwxyz'
# ★ 底线②（留下 ≥ 半个预算）的**唯一**覆盖样本：24 字处切在 `v|w` 中间，
#   但最后一个空格在第 8 位 ⇒ 退过去只剩 8 字（< 24/2）⇒ 必须**不退**、照旧硬截。
#   没有这条样本，"半个预算"那条底线在整套判据里是死的（实测过：删掉它全绿）。
HALF = u'abcdefgh ijklmnopqrstuvwxyz'

# =============================================== A 结构
head(u'A 结构：一处实现、三处调用、白名单不许含 CJK')
_src = _read(SRC)
_tree = ast.parse(_src)


def _fn(name):
    for n in ast.walk(_tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


_hc = _fn('_hard_cut')
check(u'A1 `_hard_cut()` 存在', _hc is not None)
check(u'A2 `first_sentence` / `fit_sentences` 里各有调用',
      _hc is not None and (
          sum(1 for n in ast.walk(_fn('first_sentence'))
              if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == '_hard_cut') == 1
          and sum(1 for n in ast.walk(_fn('fit_sentences'))
                  if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == '_hard_cut') == 2),
      u'1 + 2')
# ★ 代码行里不许再有"带字面尾巴"的旧写法（注释里当反例引用不算 —— 判据只看非注释行）
_old_shape = u"t[:max_chars]." + u"rstrip('" + ES._HARD_CUT_TAIL + u"')"
_code_hits = [ln for ln in _src.replace(u'\r\n', u'\n').split(u'\n')
              if _old_shape in ln and not ln.lstrip().startswith(u'#')]
check(u'A3 代码行里没有旧写法（三处已统一走 `_hard_cut`）',
      not _code_hits, u'%d 处' % len(_code_hits))
# ★★ A4 第一版判"全 ASCII"，但白名单里那个 `’`(U+2019) 和 `-` 是**故意**的
#   （`don't` / `well-known` 是词内，ASCII 撇号与连字符都得收）⇒ 判据过窄会永久报红。
#   真正要守的是"**不许有 CJK 汉字**"，因为汉字才让"切在词中"这个判断对中文成立。
_cjk_in = [c for c in ES._WORDY if u'\u4e00' <= c <= u'\u9fff']
check(u'A4 ★ `_WORDY` 里**一个 CJK 汉字都没有**（含一个就会改坏中文，见 C1）',
      not _cjk_in and len(ES._WORDY) >= 36,
      u'%d 个字符，CJK %d 个（`’` `-` 非 ASCII 但故意）'
      % (len(ES._WORDY), len(_cjk_in)))
_has_digit = any(c.isdigit() for c in ES._WORDY) and any('a' <= c <= 'z' for c in ES._WORDY)
check(u'A5 白名单含字母与数字（不是空集/半集）', _has_digit)

# =============================================== B 行为
head(u'B 行为：英文整词收尾、中文逐字不变、底线真的挡')
check(u'B1 英文 24 字链：`hehe that tickles so much…` ⇒ `hehe that tickles so`',
      ES.first_sentence(EN1) == u'hehe that tickles so',
      repr(ES.first_sentence(EN1)))
# ★★ 中文负控制：**纯中文**（无 ASCII 词）必须与旧规则**逐字相同**
#   含 ZH3 这条**带空格**的样本，否则这一组只是"根本进不了分支"的绿，判不出东西。
_zh_same = [t for t in (ZH1, ZH2, ZH3) if ES.first_sentence(t) == _old_hard(t, 24)]
check(u'B2 ★★ 纯中文 3 条与旧规则**逐字相同**（退让不许碰中文）',
      len(_zh_same) == 3, u'%d/3' % len(_zh_same))
_zh_same40 = [t for t in (ZH1, ZH2, ZH3) if ES.fit_sentences(t) == _old_hard(t, 40)]
check(u'B3 同上，40 字链', len(_zh_same40) == 3, u'%d/3' % len(_zh_same40))
# 混合：中文句尾接英文人名 ⇒ 退到人名前（不把人名劈开）
_m = ES.first_sentence(MIX)
check(u'B4 中文+英文人名：退到人名**之前**，不劈开 `Noelle`',
      _m == u'那件事之后我开始试着去理解别人的感受', repr(_m))
check(u'B5 40 字链：`…GUARD AND PROTECT` ⇒ 收在整词 `AND`',
      ES.fit_sentences(EN2) == u'AXIS MODEL 014 READY TO GUARD AND',
      repr(ES.fit_sentences(EN2)))
check(u'B6 不超限的短句原样返回（不许"为了退让而退让"）',
      ES.first_sentence(SHORT) == SHORT and ES.fit_sentences(SHORT) == SHORT)
# 底线①：空格在第 0 位 ⇒ 退过去是空串 ⇒ **不许退**（单元级，见 SPACE0 注释）
_b = ES._hard_cut(SPACE0, 24)
check(u'B7 ★ 底线①：空格在第 0 位就**不退**（单元级探针，公开 API 走不到）',
      _b == _old_hard(SPACE0, 24), repr(_b))
# 全文没有空格（中文常态）：没有切点 ⇒ 同样不许退
_ns = ES.first_sentence(NOSPACE)
check(u'B12 全文无空格 ⇒ 没有切点可退，原样硬截',
      _ns == _old_hard(NOSPACE, 24), repr(_ns))
# 底线②：退过去只剩 8 字（< 12）⇒ 同样**不许退**（否则一句话就剩个零头）
_hf = ES.first_sentence(HALF)
check(u'B11 ★ 底线②：退过去不到半个预算就**不退**（照旧硬截）',
      _hf == _old_hard(HALF, 24), repr(_hf))
# 性质：长度 ≤ 上限；结果是原文前缀（对本文件的样本集）
_samples = (EN1, EN2, ZH1, ZH2, ZH3, MIX, NOSPACE, HALF, SPACE0)
_ok_len = all(len(ES.first_sentence(t)) <= 24 for t in _samples)
_ok_len40 = all(len(ES.fit_sentences(t)) <= 40 for t in _samples)
check(u'B8 上限守住（24 / 40）', _ok_len and _ok_len40)
_prefix = 0
# ★ 前缀性质只对有公开入口的样本成立：`first_sentence` 入口 `strip()` 会吃掉前置空格，
#   所以 `SPACE0` 的返回天然不是原文前缀 —— 那是入口的既定行为，不是退让的 bug。
_pub = tuple(t for t in _samples if t is not SPACE0)
for t in _pub:
    r = ES.first_sentence(t)
    if (not r) or t.startswith(r):
        _prefix += 1
check(u'B9 结果都是原文前缀（不拼不补）', _prefix == len(_pub),
      u'%d/%d' % (_prefix, len(_pub)))
# 性质：退让之后，末字符不许是 ASCII 词字符**且**下一位也是（即"不再切在词中"）
_still = 0
for t in (EN1, EN2):
    m = 24 if t is EN1 else 40
    r = ES.first_sentence(t) if t is EN1 else ES.fit_sentences(t)
    if r and len(r) < len(t) and r[-1] in ES._WORDY and t[len(r)] in ES._WORDY:
        _still += 1
check(u'B10 退让后不再切在词中（两条英文样本）', _still == 0, u'仍切词中 %d' % _still)

# =============================================== C 负控制（成对）
head(u'C 负控制：把 `_WORDY` 塞进 CJK ⇒ 中文样本**必须**被改')
# ★ 这条是 B2 的配对，而且**必须在同一个样本上**（ZH3，带空格）：
#   如果 B2 绿只是因为"这个中文根本走不到退让分支"，那 C1 也会绿、两绿一片和谐。
#   只有 C1 红 + B2 绿，才证明"是 ASCII 白名单在挡"。
# ★★ 实测：只塞 `曾` 或只塞 `经` **都不够** —— 判据要切点**两侧**都在白名单里
#   （`cut[-1] == '曾'` 且 `t[24] == '经'`）⇒ 必须把样本里的汉字全塞进去。
_keep = ES._WORDY
try:
    ES._WORDY = _keep + ZH3
    _after = ES.first_sentence(ZH3)
finally:
    ES._WORDY = _keep
check(u'C1 白名单一旦含 CJK，中文样本（ZH3，带空格）立刻被改（B2 不是恒真）',
      _after != _old_hard(ZH3, 24), repr(_after))
check(u'C2 还原之后中文又逐字相同（patch 真的撤了）',
      ES.first_sentence(ZH3) == _old_hard(ZH3, 24))
# 反面：**只**塞切点一侧 ⇒ 不许变。锁住"两侧都判"这个实现细节（易被改成 `or`）。
_keep_a = ES._WORDY
try:
    ES._WORDY = _keep_a + u'曾'
    _one_side = ES.first_sentence(ZH3)
finally:
    ES._WORDY = _keep_a
check(u'C3 只塞切点**左**侧一个字 ⇒ 不许退让（证明判的是两侧、不是一侧）',
      _one_side == _old_hard(ZH3, 24), repr(_one_side))

# =============================================== D 鉴别力
head(u'D 鉴别力：把退让关掉，B1 必须退回半个单词')
_keep2 = ES.MIN_FIRST_CHARS
try:
    ES.MIN_FIRST_CHARS = 10 ** 6        # 退让永远不达标 ⇒ 退回硬截
    _off = ES.first_sentence(EN1)
finally:
    ES.MIN_FIRST_CHARS = _keep2
check(u'D1 关掉退让 ⇒ 立刻退回 `hehe that tickles so muc`（B1 不是恒真）',
      _off == _old_hard(EN1, 24), repr(_off))
_keep3 = ES._HARD_CUT_TAIL
try:
    ES._HARD_CUT_TAIL = u''             # 尾巴集合清空，行为不该变
    _no_tail = ES.first_sentence(EN1)
finally:
    ES._HARD_CUT_TAIL = _keep3
check(u'D2 清空尾巴集合后英文结果不变（说明 B1 靠的是退让，不是 rstrip 的巧合）',
      _no_tail == u'hehe that tickles so', repr(_no_tail))

# =============================================== E 自检
head(u'E 自检')
_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'E1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'E2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'E3 零外部盘（只读仓库内文件）',
      os.path.abspath(SRC).startswith(ROOT + os.sep))
# ★ E4 第一版写成 `not re.search(u'条以上', u''.join(_failed))` —— `_failed` 空时恒真，
#   等于没判。换成一条真性质：**幂等**（结果再压一次不许再变）。
_idem = all(ES._hard_cut(ES._hard_cut(t, 24), 24) == ES._hard_cut(t, 24)
            for t in _samples)
check(u'E4 `_hard_cut` 幂等（对结果再压一次不变）', _idem)

print(u'')
print(u'=' * 78)
print(u'check147：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
