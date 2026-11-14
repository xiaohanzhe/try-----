# -*- coding: utf-8 -*-
u"""第189轮 · 判据：**发声直显**（`（笑声：X）` / `（NYEH HEH HEH!）` → 声音本体）。

## 用户口径

「笑声也就是角色发出来的声音直接显示就好，这也是原作的一种特色」
（2026-11-14，看完第188轮真实对白样本后给的批注，详版 §191.4）

## 实测切口（`_evidence/measure189.json`）

419 条 `ACTION_PAREN` 跑完第188轮的护栏后，仍在的括号里"发声类"是 **30 处 / 4 种**：

    （NYEH HEH HEH!）  19     （笑声：Geh ha ha ha ha）  5
    （NYEH HEH HEH！）  5     （NYEH HEH HEH!)        1

而 `（SANS! STOP BEING LAZY!）` **4 处**含实词，是"台词被塞进括号"（D 族），不是发声
⇒ **必须留着**。判据 `B1` 专门钉这条：别把"英文大写"当成"笑声"。

## 修法：己闸排最前

    t = _ANY_PAREN_RE.sub(_rescue_voice, text)    # 己（第189轮）
    t = _ANY_PAREN_RE.sub(_rescue_quoted, t)      # 丁
    t = _ACTION_PAREN_RE.sub('', t)               # 甲
    t = _ANY_PAREN_RE.sub(_kill_narration, t)     # 丙
    t = _ANY_PAREN_RE.sub(_kill_bare_label, t)    # 戊

己闸三支：① `标签：内容` ② 整段中文拟声 ③ 整段英文笑声白名单。
都不命中 ⇒ 原样返回，交给后面四道闸 —— 即**其余括号的行为逐字不变**。

## 分段

A 正控制 6 · B 负控制 7 · C 边界 4 · D 接线 3 · E 实测 4 · F 自检 3 = **27 条**
"""
import ast
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
ES_PY = os.path.join(MODS, 'event_speech.py')
RAW30 = os.path.join(REPO, 'code-quality-audit', u'第113轮-全体角色AI训练',
                     '_evidence', 'raw30')

sys.path.insert(0, MODS)
import event_speech as E                       # noqa: E402

S = E.strip_action_parentheticals

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


# ================================================================ A 正控制
print('\n=== A 正控制（语料里真出现过的 4 种形态，必须直出）===')

POS = [
    (u'（笑声：Geh ha ha ha ha）', u'Geh ha ha ha ha', u'标签冒号式 · 5 处'),
    (u'（NYEH HEH HEH!）', u'NYEH HEH HEH!', u'英文笑声 · 19 处'),
    (u'（NYEH HEH HEH！）', u'NYEH HEH HEH！', u'全角叹号 · 5 处'),
    (u'（NYEH HEH HEH!)', u'NYEH HEH HEH!', u'半角括号 · 1 处'),
    (u'姑且先表现一番嘛。（笑声：Geh ha ha ha ha）', u'姑且先表现一番嘛。Geh ha ha ha ha',
     u'句中，不能把前一句吃掉'),
    (u'别再偷懒了！（NYEH HEH HEH!）', u'别再偷懒了！NYEH HEH HEH!', u'句中'),
]
for src, want, why in POS:
    check(u'A 发声直出：%s（%s）' % (want[:16], why), S(src) == want, repr(S(src)))


# ================================================================ B 负控制
print('\n=== B 负控制（这几条**不许**变成直出，变了就是误伤）===')

NEG = [
    (u'（SANS! STOP BEING LAZY!）', u'含实词 ⇒ 是台词错位（D 族），不是发声'),
    (u'（UNDYNE TRAINS ME EVERY DAY!）', u'同上'),
    (u'（红色眼睛微微闪烁）', u'C 族角色特征'),
    (u'（你在围裙里找创可贴）', u'B 族第二人称叙述'),
    (u'（笑声渐远）', u'没有冒号、不是整段拟声 ⇒ 是叙述不是发声'),
    (u'（笑不出来）', u'`A22g` 的防线，188 轮钉过'),
    (u'（笑）随你便。', u'裸标签走戊闸删掉，不是直出'),
]
for src, why in NEG:
    want = u'随你便。' if src == u'（笑）随你便。' else src
    check(u'B 保留：%s（%s）' % (src[:14], why), S(src) == want, repr(S(src)))


# ================================================================ C 边界
print('\n=== C 边界 ===')

check(u'C1 整条只有发声 ⇒ 返回声音本体，**不是空串**（不触发判退重采样）',
      S(u'（笑声：哈）') == u'哈', repr(S(u'（笑声：哈）')))

check(u'C2 纯中文拟声（语料 0 例，预防性覆盖）⇒ 直出',
      S(u'（哈哈哈哈）') == u'哈哈哈哈', repr(S(u'（哈哈哈哈）')))

check(u'C3 单字拟声**不**命中（`（哈）` 更像标签，宁可不做）',
      S(u'（哈）') == u'（哈）', repr(S(u'（哈）')))

check(u'C4 发声与裸标签共存 `（笑）（笑声：哈）` ⇒ 标签删掉、发声直出',
      S(u'（笑）（笑声：哈）') == u'哈', repr(S(u'（笑）（笑声：哈）')))


# ================================================================ D 接线
print('\n=== D 接线（AST，钉"己闸真在里面且排最前"）===')

_tree = ast.parse(rd(ES_PY))


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


_fn = _find_func(_tree, 'strip_action_parentheticals')
_has_fn = _fn is not None
check(u'D1 `strip_action_parentheticals` 还在', _has_fn)

_subs = []
if _has_fn:
    for node in ast.walk(_fn):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'sub'
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == '_ANY_PAREN_RE'
                and node.args
                and isinstance(node.args[0], ast.Name)):
            _subs.append((node.args[0].id, node.lineno))
_ln = dict((nm, l) for nm, l in _subs)

check(u'D2 己闸 `_rescue_voice` 排在**第一个** `_ANY_PAREN_RE.sub`'
      u'（后面四道闸对其它括号的行为才能逐字不变）',
      '_rescue_voice' in _ln and _ln['_rescue_voice'] == min(_ln.values()),
      u'%r' % (_subs,))

check(u'D3 `_rescue_voice` 是模块级函数（不是函数内闭包 —— 判据与打桩都靠它）',
      _find_func(_tree, '_rescue_voice') is not None)


# ================================================================ E 实测
print('\n=== E 实测（拿训练产物复算，不采信注释里的数）===')

PAREN = re.compile(u'[（(][^（（））]{1,200}[)）]')
_EN_TOK = re.compile(u"[A-Za-z']+")


def _latest(path, target=48):
    best = None
    for line in io.open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and r.get('turns_n') == target:
            best = r
    return best


_n_all = 0
_n_left = 0
_voice_left = 0            # 跑完护栏后**仍会被己闸认出**的括号（必须 0）
_d_left = 0                # 含实词的英文括号（必须还在）


def _is_voice(inner):
    u"""★ 用**产品自己的常量**判，不在这里重写一遍。

    第一版判据写成 `inner.startswith('笑声')` ⇒ 把 `（笑声渐远）`（叙述）也算成发声，
    报了一个假红。这正是"观察量须由产品代码判"。
    """
    if (E._VOICE_LABEL_RE.match(inner) or E._VOICE_WRAP_RE.match(inner)
            or E._ONO_RE.match(inner)):
        return True
    toks = _EN_TOK.findall(inner)
    return bool(toks) and all(x.lower() in E._LAUGH_EN for x in toks)


if os.path.isdir(RAW30):
    for f in sorted(os.listdir(RAW30)):
        if not f.endswith('.jsonl'):
            continue
        rec = _latest(os.path.join(RAW30, f))
        if not rec:
            continue
        for t in (rec.get('turns') or []):
            if not any(v[0] == 'ACTION_PAREN' for v in (t.get('violations') or [])):
                continue
            _n_all += 1
            out = E.strip_action_parentheticals(t.get('final') or u'')
            left = PAREN.findall(out)
            if left:
                _n_left += 1
            for h in left:
                inner = h[1:-1].strip()
                if _is_voice(inner):
                    _voice_left += 1
                if inner.upper().startswith(u'SANS'):
                    _d_left += 1

check(u'E1 训练产物里 `ACTION_PAREN` 仍是 419 条（分母没变，比的才是同一批）',
      _n_all == 419, u'实测 %d' % _n_all)

check(u'E2 跑完护栏后**一个发声形括号都不剩**（30 处全部直出）',
      _voice_left == 0, u'残留发声形 %d 处' % _voice_left)

# ★ 用固定阈值而不是"随轮次增长的绝对数"：230 是第189轮实测值，
#   阈值 240 = "至少消掉 72 轮"，语料不变它就不会过期。
check(u'E3 残留括号轮数 ≤ 240（187 轮实测 312；188 轮 243；189 轮实测见右）',
      0 < _n_left <= 240, u'实测 %d / %d 轮' % (_n_left, _n_all))
check(u'E4 D 族台词（`SANS…`）**仍原样留在括号里**（没被"英文大写=笑声"误伤）',
      _d_left >= 1, u'仍在 %d 处' % _d_left)


# ================================================================ F 自检
print('\n=== F 自检 ===')

EXPECT = 27
check(u'F1 判据条数 == 声明的 %d 条' % EXPECT, (_n['p'] + _n['f']) + 3 == EXPECT,
      u'实跑 %d 条（F1 之前，未计 F1/F2/F3）' % ((_n['p'] + _n['f']),))

_writes = []
for node in ast.walk(ast.parse(rd(os.path.abspath(__file__)))):
    if isinstance(node, ast.Call):
        fn = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
        if fn == 'open':
            modes = [a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if any(('w' in m or 'a' in m or '+' in m) for m in modes[1:]):
                _writes.append(getattr(node, 'lineno', -1))
        elif fn in ('write_text', 'dump', 'write'):
            _writes.append(getattr(node, 'lineno', -1))
check(u'F2 本套件只读：AST 里没有写模式的 open / dump / write',
      not _writes, u'可疑行 %r' % (_writes,))

_s = rd(os.path.abspath(__file__))
check(u'F3 PASS / FAIL 标记是字面量（`run_all` 才数得到；此处不回显字面量）',
      u"'[PASS] %s%s'" in _s and u"'[FAIL] %s%s'" in _s,
      u'源码两处都在')

print()
print(u'%d PASS / %d FAIL' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
sys.exit(0 if _n['f'] == 0 else 1)
