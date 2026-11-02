# -*- coding: utf-8 -*-
"""第142轮回归锁：38 位 NPC 的 ① 不是"人设的重复"，是**38 份实测诊断** —— 不许批量删。

## 这一轮在做什么

第139轮处理主宠 `ralsei` 时，把 patch 开头那句
    「一次最多两三句，短一点，像随口说出来的。」（简称 ①）
判成「人设句数规格的第三份复述」并删掉了，同时登记遗留：
「38 位 NPC 的 patch 同型重复未修（`check139 E1` 守着 `38/76`）」。

本轮去修那 38 条之前先量了一步，结果**推翻了那个前提**。

### ① 是怎么来的（代码侧）

`code-quality-audit/第113轮/_tools/common113.py`：

  · `evaluate()` 里 `if len(t) > MAX_CHARS: bad.append(('TOO_LONG', ...))`
    —— 触发条件是**回复超过 200 字**，跟"句数"不是一回事；
  · `build_patch()` 按优先级取**前 3 条**：
    `MARKDOWN, AI_SELF, SLAVE, NOT_CN, ACTION_PAREN, META, TOO_LONG,
     TOO_MANY_SENTENCES, PARROT, REPEAT, ENGLISH, EMPTY`
    ⇒ patch 里出现 ①，说明这个角色**真的踩过 TOO_LONG**，
    而且前面几项没把 3 个槽位占满。

### ① 与数据的关系（语料侧，77 份 raw30 / 5592 条真机回复）

| 组 | n | 实测有 >200 字的回复 | 实测有 >3 句的回复 |
|---|---|---|---|
| **带 ①** | 38 | **38 人（100%）**·共 247 条 | 38 人（100%） |
| 不带 ① | 39 | 8 人（20.5%）·共 89 条 | 38 人（97.4%） |

「既没超长也没超句」却带 ① 的：**0 人**。

⇒ 38/76 不是"模板没清干净"，是 **38 份诊断**。删掉 ① ＝ 把这 38 个角色
「你实测超过 200 字」这条信息抹掉。

### 为什么"删 ①"不等于"去重"

人设（`assets/npc/persona/*.txt`，76 份**同一种写法**）写的是：

    一次开口通常 1~2 句，最长不超过 200 字；像真人那样说话，不要写成说明书。

而 ① 写的是「最多两三句」—— **更宽**。所以删 ① 不是删重复，
是**把规格从 ≤3 收紧到 1~2**，那是行为改变。第139轮 `ralsei` 那里之所以
A/B 无差别，是因为 `ralsei` 的人设自己也写「一次只说 1~3 句」，两边语义相同；
这 38 位**不具备这个前提**。

### 连带订正

`ralsei` 实测最长 **211 字**、有 1 条 >200 ⇒ 它当初**确实踩过 TOO_LONG**。
第139轮说它"只是重复"的归因不成立。删掉后 56 条真机 A/B 无差别**仍是实测结论**，
可以保留现状；但**不能当先例**去删另外 38 条。

## 本套件守什么

A 数据面：人设规格只有 1 种写法且是 1~2 句 · ① 只有 1 种写法且逐字等于
  `PATCH_RULES['TOO_LONG']` · 三份副本（`_index.patches` / `_index.cards` /
  `cards/*.json`）集合一致
B 因果：`TOO_LONG` 的触发是 `> MAX_CHARS`（AST 读比较）· `build_patch` 里它在
  第 7 位、只取前 3 条（AST 读元组顺序）· 语料面 100% / <25% / 0 人三连
C 结论登记：**38 条仍在**（批量删会当场红）· `ralsei` 仍不含 ①（第139轮的现状不动）·
  `ralsei` 实测最长 > 200（订正归因的证据）· `common113` 里有那段订正注释
D 自检

★ 零网络、零 Qt：只读 `_index.json`、`cards/*.json`、`persona/*.txt`、
  `common113.py` 源码，以及本轮已落盘的 `lead142b.json`。
★ 语料侧不重跑（重跑要读 77 份真机记录），直接吃上一步的测量结果。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
CARDS_DIR = os.path.join(TRAIN, 'cards')
INDEX_JSON = os.path.join(TRAIN, '_index.json')
PERSONA_DIR = os.path.join(PET, 'assets', 'npc', 'persona')
COMMON_PY = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                         '_tools', 'common113.py')
EV = os.path.join(ROUND, '_evidence')

MARKS = (u'两三句', u'随口说')
LEAD = u'一次最多两三句，短一点，像随口说出来的。'
SPEC_1 = u'一次开口通常 1~2 句'

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


def _has_lead(t):
    return any(m in (t or u'') for m in MARKS)


def main():
    idx = _json(INDEX_JSON)
    cards = idx.get('cards') or {}
    patches = idx.get('patches') or {}
    ev = _json(os.path.join(EV, 'lead142b.json'))

    # ======================================================================
    head(u'A · 数据面：规格冲突是真的，"重复"这个说法不成立')

    # 人设侧：句数规格的写法种类
    specs = {}
    for fn in sorted(os.listdir(PERSONA_DIR)):
        if not fn.endswith('.txt'):
            continue
        for line in _read(os.path.join(PERSONA_DIR, fn)).split(u'\n'):
            if u'一次开口通常' in line:
                specs.setdefault(line.strip(), []).append(fn[:-4])
                break
    check(u'A1 人设里写「一次开口通常」的 76 份，只有 **1 种写法**',
          len(specs) == 1 and sum(len(v) for v in specs.values()) == 76,
          u'%d 种写法 / %d 份' % (len(specs), len(specs) and
                                  sum(len(v) for v in specs.values())))
    spec_line = list(specs)[0] if specs else u''
    # ★ 判**所有**写法都含 1~2 句，而不是只看 `list(specs)[0]` ——
    #   后者在有多种写法时取哪个取决于 set 的迭代顺序，判据会时红时绿。
    check(u'A2 那句写的是 **1~2 句**（与 ① 的"两三句"不同 —— 冲突成立的证据）',
          bool(specs) and all(SPEC_1 in s and u'200 字' in s for s in specs),
          u'%r' % (spec_line[:40],))

    # 卡片侧：① 的写法种类
    lead_ids = sorted(k for k, v in cards.items() if _has_lead((v or {}).get('patch')))
    frags = set()
    for k in lead_ids:
        p = (cards[k] or {}).get('patch') or u''
        for s in p.replace(u'。', u'。\n').split(u'\n'):
            if any(m in s for m in MARKS):
                frags.add(s.strip())
    check(u'A3 ① 只有 1 种写法、逐字等于 `PATCH_RULES[\'TOO_LONG\']`',
          frags == set([LEAD]), u'%r' % (sorted(frags),))

    # 三份副本一致
    p_idx = sorted(k for k, v in patches.items() if _has_lead(v))
    cf = []
    for fn in sorted(os.listdir(CARDS_DIR)):
        if fn.endswith('.json'):
            if _has_lead((_json(os.path.join(CARDS_DIR, fn)) or {}).get('patch')):
                cf.append(fn[:-5])
    check(u'A4 三份副本的"带 ①"集合完全一致（改一处不够，要改三处）',
          lead_ids == p_idx == sorted(cf),
          u'%d/%d/%d' % (len(p_idx), len(lead_ids), len(cf)))

    # ======================================================================
    head(u'B · 因果：① 是 `TOO_LONG` 实测触发的，不是模板')

    tree = ast.parse(_read(COMMON_PY).replace(u'\r\n', u'\n'))

    # B1：TOO_LONG 的触发是不是 `len(t) > MAX_CHARS`
    trig = None
    for nd in ast.walk(tree):
        if isinstance(nd, ast.If):
            has_tl = False
            for sub in ast.walk(nd):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == 'append' and sub.args:
                    a0 = sub.args[0]
                    if isinstance(a0, ast.Tuple) and a0.elts \
                            and isinstance(a0.elts[0], ast.Constant) \
                            and a0.elts[0].value == 'TOO_LONG':
                        has_tl = True
            if has_tl:
                t0 = nd.test
                if isinstance(t0, ast.Compare) and len(t0.ops) == 1 \
                        and isinstance(t0.ops[0], ast.Gt) and t0.comparators:
                    rhs = t0.comparators[0]
                    if isinstance(rhs, ast.Name) and rhs.id == 'MAX_CHARS':
                        left = t0.left
                        if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) \
                                and left.func.id == 'len':
                            trig = 'len(..) > MAX_CHARS'
    check(u'B1 `TOO_LONG` 的触发是 `len(t) > MAX_CHARS`（**字数**，不是句数）',
          trig == 'len(..) > MAX_CHARS', u'%r' % (trig,))

    # B2：build_patch 的优先级表里 TOO_LONG 的位置 + 只取前 3
    order = None
    take3 = False
    for nd in ast.walk(tree):
        if isinstance(nd, ast.FunctionDef) and nd.name == 'build_patch':
            for sub in ast.walk(nd):
                if isinstance(sub, ast.For) and isinstance(sub.iter, ast.Tuple):
                    vals = [e.value for e in sub.iter.elts
                            if isinstance(e, ast.Constant)]
                    if 'TOO_LONG' in vals:
                        order = vals
                if isinstance(sub, ast.If) and isinstance(sub.test, ast.Compare):
                    try:
                        if isinstance(sub.test.left, ast.Call) \
                                and getattr(sub.test.left.func, 'id', '') == 'len' \
                                and isinstance(sub.test.comparators[0], ast.Constant) \
                                and sub.test.comparators[0].value == 3:
                            take3 = True
                    except Exception:
                        pass
    pos = (order.index('TOO_LONG') + 1) if order else 0
    check(u'B2 `build_patch` 里 `TOO_LONG` 排第 7 位（前 6 项会先占槽）',
          pos == 7, u'第 %d 位' % pos)
    check(u'B3 只取**前 3 条**（`len(want) >= 3` ⇒ break）', take3)

    # B4~B6：语料侧三连（数据来自 lead142b.json，上一步已落盘）
    rows = ev.get('rows') or []
    have = [r for r in rows if r['lead'] and not r.get('norec')]
    lack = [r for r in rows if (not r['lead']) and not r.get('norec')]
    h_over = [r for r in have if r['over200'] > 0]
    l_over = [r for r in lack if r['over200'] > 0]
    clean = [r for r in have if r['over200'] == 0 and r['over3s'] == 0]
    check(u'B4 ★带 ① 的 38 人，**100%** 实测有 >200 字的回复',
          len(have) == 38 and len(h_over) == 38,
          u'%d/%d 人' % (len(h_over), len(have)))
    pct = 100.0 * len(l_over) / max(1, len(lack))
    check(u'B5 ★对照组：不带 ① 的 39 人里，超长过的不超过 25%',
          len(lack) == 39 and pct <= 25.0,
          u'%d/%d = %.1f%%' % (len(l_over), len(lack), pct))
    check(u'B6 ★★「既没超长也没超句」却带 ① 的 = **0 人**（若 >0 才叫"模板塞的"）',
          len(clean) == 0, u'%d 人' % len(clean))
    check(u'B7 存在"有超长但没拿到 ①"的人（被前 3 槽挤掉）⇒ 没 ① **不等于**没违规',
          len(l_over) >= 4, u'%d 人' % len(l_over))

    # ======================================================================
    head(u'C · 结论登记：38 条不许批量删')

    # ★ 三处副本都要守：`_index.json` 的 `patches` / `_index.json` 的 `cards` /
    #   `cards/*.json` 各一份，是**故意保持同步**的（第139轮 A2/A3 就是钉这个）。
    #   第一版只查 `cards`（索引里那份）⇒ 删 `cards/asgore.json` 里的一条时
    #   C1 照样绿，等于没守住真正会发出去的那份文件。
    check(u'C1 ★三处副本都仍是 **38 条**（批量删任何一处都会当场红）',
          len(lead_ids) == len(p_idx) == len(cf) == 38,
          u'索引cards=%d 索引patches=%d 文件=%d'
          % (len(lead_ids), len(p_idx), len(cf)))

    ral_file = _json(os.path.join(CARDS_DIR, 'ralsei.json'))
    check(u'C2 ★三处副本里 `ralsei` 都**不含** ①（第139轮的删除保持现状，本轮不回滚）',
          (u'ralsei' not in lead_ids) and (u'ralsei' not in p_idx)
          and (not _has_lead(ral_file.get('patch'))))

    ral = [r for r in rows if r['id'] == 'ralsei']
    ral_max = ral[0]['max'] if ral else 0
    check(u'C3 ★订正依据：`ralsei` 实测最长 > 200 字（它确实踩过 TOO_LONG）',
          ral_max > 200, u'最长 %d 字' % ral_max)

    src = _read(COMMON_PY)
    check(u'C4 `common113.py` 的 `TOO_LONG` 旁有订正注释（不许当"人设复述"批量删）',
          u'第142轮订正' in src and u'不许批量删' in src)

    # ======================================================================
    head(u'D · 自检')

    calls = []
    for nd in ast.walk(ast.parse(_read(os.path.abspath(__file__)))):
        if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
                and nd.func.id == 'check':
            calls.append(nd)
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and ('[' + 'PASS]') in sub.value:
                leak.append(sub.value[:36])
    # ★★ 措辞刻意**不写那个标记本身**：它一旦被打印出来，`run_all.count_results`
    #   （正则数 `[PASS]` 的**出现次数**）就会把这行多算一次 —— 防计数的判据
    #   自己把计数顶高 1，套件自报 N、汇总报 N+1。第141轮 `check141 D2` 就是这么
    #   带着这个坑发出去的（那次 `check141 0 31 0` vs 套件自报 30），本轮一并修掉。
    check(u'D1 ★判据描述里没有那个计数标记的字面量（会顶高 run_all 的 PASS 计数）',
          not leak, u'命中 %d 处' % len(leak))

    check(u'D2 本轮两份测量证据在盘上（语料侧直接吃上一步的结果，不重跑）',
          os.path.isfile(os.path.join(EV, 'lead142.json'))
          and os.path.isfile(os.path.join(EV, 'lead142b.json')))

    n_check = len(calls)
    n_ran = _n['p'] + _n['f']
    check(u'D3 写了多少处 check( 与实际跑了几条，只差本判据自己这一处',
          n_check - n_ran == 1, u'calls=%d ran=%d' % (n_check, n_ran))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
