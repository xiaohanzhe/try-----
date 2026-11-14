# -*- coding: utf-8 -*-
u"""第188轮 · 护栏补一道「裸情绪标签」闸（`（笑）` / `（微笑）` / `（苦笑）`）。

## 为什么做这个（实证链，不是感觉）

第187轮把 77 个 NPC × 48 轮训练产物里那 **419 条 `ACTION_PAREN`** 拿去跑
**产品自己的护栏**（`event_speech.strip_action_parentheticals`），量出来：

    已删干净        107 条（25.5%）
    删完判无效        0 条
    仍有括号残留   **312 条（74.5%）**   ← 洞在这儿

残留高频项全是**裸情绪标签**：`（笑）42` / `（微笑）39` / `（苦笑）6` / `（思考片刻）3`。
甲闸抓不到它们，而且**是故意的** —— `_ACTION_VERBS` 上方第 589 行明写
「裸 `笑` 会命中 `（笑不出来）`」，锁 `A22g` 实测过。

## 修法：整段形态匹配，不是往动词表里加词

戊闸 `_BARE_LABEL_RE` 要求括号内容**整段**是「（可选修饰语）+ 情绪词 +（可选后缀）」：
  · `（笑）` `（微笑）` `（苦笑）` `（思考片刻）` `（微微一笑）` → 删
  · `（笑不出来）` —— `不出来` 不在后缀集 ⇒ **天然不命中**（A22g 继续绿）
  · `（微笑切面条）` / `（红色眼睛微微闪烁）` ⇒ 不命中（动作+宾语 / 角色特征，属另一族）

★ 为什么不用"等值词表"：`微微一笑` / `苦笑了一下` / `思考片刻` 这类组合会无穷增生，
  项目里「动词表要穷举」是踩过的老坑。形态表达一次覆盖。

## 实测效果（本套件 E 段复算）

    仍有括号残留 312 → **243 轮**（74.5% → 58.0%），419 条里消掉 69 轮

## 本轮**不做**的（如实记录）

  · **B 族**「第二人称叙述」：`（你在围裙口袋里找创可贴）` `（你轻声说）`
  · **C 族**「角色自身动作」：`（红色眼睛微微闪烁）` `（眨了下眼睛）`
  · **D 族**「台词错位」：`（NYEH HEH HEH!）` `（SANS! STOP BEING LAZY!）`
    —— 删了丢内容、提出来等于替模型改写台词，需单独拍口径。

## 分段

A 正控制 7 · B 负控制 7 · C 边界 3 · D 接线 4 · E 实测 2 · F 自检 3 = **26 条**
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
MAIN_PY = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')
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
print('\n=== A 正控制（戊闸该删的，删不掉就是没接上）===')

POS = [
    (u'（笑）', u''),
    (u'（微笑）', u''),
    (u'（苦笑）', u''),
    (u'（思考片刻）', u''),
    (u'（微微一笑）', u''),
    (u'嗯。（笑）我在呢。', u'嗯。我在呢。'),
]
for src, want in POS:
    check(u'A 删掉裸标签：%r → %r' % (src, want), S(src) == want, repr(S(src)))

check(u'A7 句中标签删完不留空标点（「我在呢（笑）」不得变「我在呢，」）',
      S(u'我在呢（笑）') == u'我在呢', repr(S(u'我在呢（笑）')))


# ================================================================ B 负控制
print('\n=== B 负控制（这几条必须**原样保留**，删了就是误杀）===')

NEG = [
    (u'（笑不出来）', u'`不出来` 不在后缀集'),
    (u'（微笑切面条）', u'`微笑` 后面跟宾语'),
    (u'（红色眼睛微微闪烁）', u'角色特征，属 C 族'),
    (u'（其实我有点怕）', u'第一人称心里话'),
    (u'（我想想该怎么说）', u'第一人称心里话'),
    (u'（你在围裙口袋里找创可贴）', u'第二人称叙述，属 B 族'),
    (u'（看着你）', u'动作+宾语，不是裸标签'),
]
for src, why in NEG:
    check(u'B 保留：%s（%s）' % (src, why), S(src) == src, repr(S(src)))


# ================================================================ C 边界
print('\n=== C 边界 ===')

check(u'C1 整条只有一个裸标签 ⇒ 返回空串（走既有判退重采样，不是显示空对话框）',
      S(u'（笑）') == u'', repr(S(u'（笑）')))

check(u'C2 连排多个标签全删，且不留下空标点',
      S(u'（笑）（微笑）今天挺好。') == u'今天挺好。',
      repr(S(u'（笑）（微笑）今天挺好。')))

check(u'C3 括号里是「标签 + 引号台词」⇒ 台词必须救回来（丁闸优先于戊闸）',
      S(u'（笑“我真的没事”）') == u'我真的没事',
      repr(S(u'（笑“我真的没事”）')))


# ================================================================ D 接线
print('\n=== D 接线（AST，钉的是"戊闸真的在里面、且排在丁闸之后"）===')

_src = rd(ES_PY)
_tree = ast.parse(_src)


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


_fn = _find_func(_tree, 'strip_action_parentheticals')
_has_fn = _fn is not None
check(u'D1 `strip_action_parentheticals` 还在（老函数没被改名/删掉）', _has_fn)

# 找函数体内所有 `_ANY_PAREN_RE.sub(<回调>, ...)` 的 (回调名, 行号)
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
_names = [n for n, _ in _subs]
check(u'D2 函数体里 `_ANY_PAREN_RE.sub` 恰好 4 处'
      u'（己发声 / 丁救台词 / 丙叙述 / 戊裸标签）',
      len(_subs) == 4, u'%r' % (_subs,))

_ln = dict((n, l) for n, l in _subs)
# ★ 回调名**带前导下划线**（模块级函数 `_rescue_quoted` / `_kill_narration` /
#   `_kill_bare_label`）。第一版判据写成不带下划线的名字，`_ln.get` 全 None ⇒ 报红。
#   报红三步里第二步「再疑判据本身」命中：产品行号 777 < 781 < 787，顺序本来就是对的。
# ★★ 第189轮引账：新增己闸 `_rescue_voice`（发声直出），排在**最前**。
#   本判据从"3 处"改成"4 处"，并把「己在最前」并进同一条（条数不变，仍是 26 条）。
check(u'D3 闸序：己发声 → 丁救台词 → 戊裸标签（先直出、再救台词、最后删标签）',
      '_rescue_voice' in _ln and '_rescue_quoted' in _ln
      and '_kill_bare_label' in _ln
      and _ln['_rescue_voice'] < _ln['_rescue_quoted'] < _ln['_kill_bare_label'],
      u'voice=%s rescue=%s bare=%s'
      % (_ln.get('_rescue_voice'), _ln.get('_rescue_quoted'),
         _ln.get('_kill_bare_label')))

check(u'D4 `main._clean_ai_reply` 仍在调 `strip_action_parentheticals`（接线没断）',
      'strip_action_parentheticals' in rd(MAIN_PY))


# ================================================================ E 实测
print('\n=== E 实测（拿训练产物复算，不采信注释里的数）===')

PAREN = re.compile(u'[（(][^（（））]{1,200}[)）]')


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
            if PAREN.search(E.strip_action_parentheticals(t.get('final') or u'')):
                _n_left += 1

check(u'E1 训练产物里 `ACTION_PAREN` 仍是 419 条（分母没变，比的才是同一批）',
      _n_all == 419, u'实测 %d' % _n_all)

# ★ 改前实测 312 轮（第187轮留档）。判据用**固定阈值**而不是"随轮次增长的绝对数"：
#   阈值 250 是"至少消掉 62 轮"的另一种写法，语料不变它就不会过期。
check(u'E2 护栏跑完仍残留括号的轮数 ≤ 250（改前实测 312；本轮消掉约 69 轮）',
      0 < _n_left <= 250, u'实测 %d / %d 轮（%.1f%%）'
      % (_n_left, _n_all, 100.0 * _n_left / max(1, _n_all)))


# ================================================================ F 自检
print('\n=== F 自检 ===')

EXPECT = 26
# F1 跑的时候后面还剩 F1/F2/F3 三条（含自己）⇒ 补 +3，不是 +2。
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
