# -*- coding: utf-8 -*-
"""第143轮回归锁：对话链的**超长截断**补上 ASCII `.`（英文回复不再被切成半个单词）。

## 这一轮在做什么

第141/142 轮连续两轮登记了「`…` 当逗号」这个规格漏洞，速查本里还留着一句
`数句子不含 …、切点含 …（两套标点）`。本轮先把它当**待证陈述**去核，结论是：

1. 那句话本身**是错的/说混了**（详见 `report143.md`）：
   · `common113._sentences`（训练侧数句）**含** `…`；
   · `event_speech._SENTENCE_ENDS`（事件链截断）**含** `…`；
   · `main._clean_ai_reply` 第 3 步（对话链截断）**不含** `…`。
   ⇒ 真正分叉的只有对话链那一处，而且它的病**不是缺 `…`**。

2. 真正的缺陷是**缺 ASCII `.`**。语料（77 人 / 5592 条真机回复）：

   | 项 | 中文 | 英文 |
   |---|---|---|
   | 超 `max_chars`(200) 的回复 | 170 | 166 |
   | **硬截**（一个切点都没找到 ⇒ `t[:200]`） | **0** | **61（36.7%）** |

   61 条的尾字符**没有一条**是句末标点，全是半个单词
   （`…'tty fragile in'` / `' such a tough '` / `'see beyond the'`）——
   这正是第135轮治过的"吊尾巴"，只是**对话链这一支从来没治**。

3. 四个变体的对照（同一批 336 条，`measure143b.py`）：

   | 切点集 | 硬截（中/英） |
   |---|---|
   | `。！？!?\\n`（原） | 0 / 61 |
   | + `…` | 0 / 59 |
   | **+ `.`** | **0 / 2** |
   | + `…` + `.` | 0 / 1 |

   ⇒ 采用「+ `.`」。**不加 `…`**：只解 2 条，却会抢走 8 条本该切在 `。` 上、
   5 条本该切在换行上的切点 —— 而 `…` 在语料里 97.4% 是当逗号用的，
   切在它后面等于切在半句话上。**两条链上限不同（24/40 vs 200），约束本来就不同，
   这是刻意的分叉。**

## 本套件守什么

A 数据面：语料规模（分母闸）· 77 张卡的 `max_chars` 全是 200 · 超限 336 条 = 170 中 + 166 英
B 机制面（AST，不看注释）：切点元组**恰好 1 处** · 含 `.` · **不含 `…`** ·
  小数点守卫在 · 事件链 `_SENTENCE_ENDS` **仍含 `…`** · 全仓没有第二份手写切点集
C 行为面（把产品源码那段 `if` 抠出来 `exec` 跑，不复刻）：OLD 61 / NEW 2 ·
  中文 0→0 · 107 条变化里 15 条中文新尾都是句末标点 · 小数点不被切断 ·
  负控制（删 `_dot` 块必须退化）· 正控制（纯英文 / 纯中文）
D 登记面：`main.py` 注释里有「第143轮」与「97.4%」与变体表
E 自检

★ 零网络、零 Qt：只读 `main.py` / `event_speech.py` / `cards/*.json` /
  `raw30/*.jsonl`（仓库内的冻结证据）。
★ C 段**回原作数据重算**，不读本轮自己写的 JSON —— 之后再把 JSON 与重算结果对账，
  避免"判据互证"（第124轮的教训）。
"""
import ast
import glob
import io
import json
import os
import re
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
CARDS = os.path.join(PET, 'assets', 'npc', '_training', 'cards')

CJK = re.compile(u'[\u4e00-\u9fff]')
TAIL_OK = u'\u3002\uff01\uff1f!?.\u2026'

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=u''):
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


def _mk(code):
    fn = (u'def _step3(t, max_chars):\n    cut = None\n'
          + textwrap.indent(textwrap.dedent(code), u'    ')
          + u'\n    return t, cut\n')
    env = {}
    exec(compile(fn, '<step3>', 'exec'), env)
    return env['_step3']


OLD_CODE = (
    u'\nif len(t) > max_chars:\n'
    u'    cut = -1\n'
    u"    for sep in (u'\\u3002', u'\\uff01', u'\\uff1f', '!', '?', '\\n'):\n"
    u'        i = t.rfind(sep, 0, max_chars)\n'
    u'        if i > cut:\n'
    u'            cut = i\n'
    u'    t = (t[:cut + 1] if cut > 0 else t[:max_chars]).strip()\n'
)


def _step3_node(src):
    """定位 `_clean_ai_reply` 里 `cut = -1` 所在的那个 `if`（全仓唯一）。"""
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_clean_ai_reply':
            fn = node
            break
    if fn is None:
        return None, None
    hits = []
    for sub in ast.walk(fn):
        if isinstance(sub, ast.If):
            seg = ast.get_source_segment(src, sub) or u''
            if u'cut = -1' in seg and u'max_chars' in seg:
                hits.append((sub, seg))
    if not hits:
        return fn, None
    hits.sort(key=lambda x: -len(x[1]))
    return fn, hits[0]


def _sep_tuple(seg):
    """从那段源码里取出 `for sep in (...)` 的元组值（字符串列表）。"""
    tree = ast.parse(textwrap.dedent(seg))
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                and node.target.id == 'sep' and isinstance(node.iter, ast.Tuple):
            vals = []
            for e in node.iter.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    vals.append(e.value)
                else:
                    return None
            return vals
    return None


def _corpus():
    cards = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        try:
            mc = (json.loads(_read(p)).get('length_policy') or {}).get('max_chars')
        except Exception:
            continue
        if isinstance(mc, int) and mc > 0:
            cards[os.path.basename(p)[:-5]] = mc
    files = sorted(glob.glob(os.path.join(RAW, '*.jsonl')))
    samples = []
    for p in files:
        name = os.path.basename(p)[:-6]
        mc = cards.get(name, 220)
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            for turn in (json.loads(line).get('turns') or []):
                t = (turn.get('final') or u'').strip()
                if not t:
                    continue
                n = len(CJK.findall(t))
                samples.append({'id': name, 'mc': mc, 't': t,
                                'lang': 'zh' if n >= 0.3 * len(t) else 'en'})
    return cards, files, samples


def main():
    src = _read(MAIN)
    fn_node, hit = _step3_node(src)
    seg = hit[1] if hit else u''
    new = _mk(seg) if seg else None
    old = _mk(OLD_CODE)

    # ======================================================================
    head(u'A · 数据面（分母闸：先把"有多少样本"钉死，免得空集恒真）')

    cards, files, samples = _corpus()
    check(u'A1 语料在盘上且规模对得上（77 个角色文件 / 5592 条回复）',
          len(files) == 77 and len(samples) == 5592,
          u'files=%d turns=%d' % (len(files), len(samples)))
    check(u'A2 77 张卡的 `length_policy.max_chars` 全是 200',
          len(cards) == 77 and set(cards.values()) == set([200]),
          u'cards=%d 取值=%s' % (len(cards), sorted(set(cards.values()))))

    over = [s for s in samples if len(s['t']) > s['mc']]
    n_zh = len([s for s in over if s['lang'] == 'zh'])
    n_en = len([s for s in over if s['lang'] == 'en'])
    check(u'A3 超上限的 336 条 = 中文 170 + 英文 166',
          len(over) == 336 and n_zh == 170 and n_en == 166,
          u'总 %d（中 %d / 英 %d）' % (len(over), n_zh, n_en))

    # 与本轮已落盘的证据对账（不是"互证"，是"同一批数据两次独立算法要同值"）
    ev_ok = True
    try:
        ev = json.loads(_read(os.path.join(EV, 'lead143c.json')))
        ev_ok = (ev.get('hard_total') == 61) and (ev.get('zh_dot_cut') == 15)
    except Exception:
        ev_ok = False
    check(u'A4 落盘证据与重算对账（硬截 61 条 / 中文切在 `.` 的 15 条）', ev_ok)

    # ======================================================================
    head(u'B · 机制面（AST 取真值，不看注释）')

    check(u'B1 找到了 `_clean_ai_reply` 的第 3 步（`cut = -1` 那一段）',
          fn_node is not None and bool(seg))
    seps = _sep_tuple(seg) if seg else None
    check(u'B2 那段里 `for sep in (...)` 恰好 1 处（切点集没有第二份副本）',
          seps is not None and seg.count(u'for sep in (') == 1,
          u'seps=%r' % (seps,))
    # ⚠️ B3 第一版写的是「元组里含 `.`」——**当场报红，但那是判据错**：
    #   本轮刻意**不**把 `.` 放进 `for sep in (...)` 元组，而是单独算一次
    #   `_dot = t.rfind('.', …)` 再 `if _dot > cut`。理由是小括号里的循环没法
    #   对单个字符加守卫（小数点 `3.14` 要跳过去往回找），塞进元组就把守卫写死了。
    # ⚠️ 第二版写「段里出现 `t.rfind('.',`」——被 `M1` 抓出来**还是太松**：
    #   小数点守卫的 `while` 里也有一句 `t.rfind('.', 0, _dot)`，把主查找换成
    #   `。` 之后它还在，判据照样绿。⇒ 必须钉到**那一行赋值**。
    check(u'B3 主查找是 `_dot = t.rfind(\'.\', 0, max_chars)`（`.` 真的参与了切点计算）',
          bool(seg) and u"_dot = t.rfind('.', 0, max_chars)" in seg
          and u'if _dot > cut' in seg)
    check(u'B4 切点集**不含** `…`（刻意的分叉：`…` 在语料里 97.4% 当逗号）',
          bool(seps) and u'\u2026' not in seps)
    check(u'B5 小数点守卫在（`isdigit` + 往回再找一次）',
          bool(seg) and u'isdigit()' in seg and u'while ' in seg)
    # 事件链那一半：AST 读 `_SENTENCE_ENDS` 的**值**（不看注释，也不靠 import 拉 Qt）
    es_src = _read(os.path.join(PET, 'modules', 'event_speech.py'))
    es_val = None
    for nd in ast.walk(ast.parse(es_src)):
        if isinstance(nd, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '_SENTENCE_ENDS'
                for t in nd.targets):
            if isinstance(nd.value, ast.Constant):
                es_val = nd.value.value
    # ★★ 第145轮：extra 原来回显**整条常量**（`常量='。！？!?\n…'`）—— 那是时相量：
    #   第145轮给事件链补了 ASCII `.`，本判据**判定没变**（仍含 `…`）却报了 DIFF。
    #   口径照第138轮：**只改 extra，不改判定** ⇒ 改成"含 `…` 与否"的布尔。
    check(u'B6 事件链 `_SENTENCE_ENDS` **仍含** `…`（不许被"顺手统一"掉）',
          bool(es_val) and u'\u2026' in es_val,
          u'含…=%s' % (bool(es_val) and u'\u2026' in es_val))
    n_main = src.count(u'rfind(sep')
    check(u'B7 全仓 `main.py` 里 `rfind(sep` 只 1 处（没有第二条截断链）',
          n_main == 1, u'处数=%d' % n_main)

    # ======================================================================
    head(u'C · 行为面（把产品源码那段抠出来 exec 跑，不复刻）')

    def hard(s, fn):
        _, c = fn(s['t'], s['mc'])
        return c is not None and c < 0

    if new is None:
        check(u'C0 第 3 步源码抠不出来 ⇒ 后面行为面全部作废', False)
    else:
        h_old = {'zh': 0, 'en': 0}
        h_new = {'zh': 0, 'en': 0}
        for s in over:
            if hard(s, old):
                h_old[s['lang']] += 1
            if hard(s, new):
                h_new[s['lang']] += 1
        check(u'C1 OLD 复现缺陷：英文硬截 61 条（中文 0）',
              h_old['en'] == 61 and h_old['zh'] == 0,
              u'中 %d / 英 %d' % (h_old['zh'], h_old['en']))
        check(u'C2 NEW 修好：英文硬截降到 2 条（中文仍 0）',
              h_new['en'] == 2 and h_new['zh'] == 0,
              u'中 %d / 英 %d' % (h_new['zh'], h_new['en']))

        diff = []
        for s in over:
            a, _ = old(s['t'], s['mc'])
            b, _ = new(s['t'], s['mc'])
            if a != b:
                diff.append((s, a, b))
        zh_diff = [x for x in diff if x[0]['lang'] == 'zh']
        bad_tail = [x for x in zh_diff if not x[2] or x[2][-1] not in TAIL_OK]
        check(u'C3 截断结果变化 107 条（中 15 / 英 92）',
              len(diff) == 107 and len(zh_diff) == 15,
              u'总 %d 中 %d' % (len(diff), len(zh_diff)))
        check(u'C4 变化的 15 条中文，新尾**全是句末标点**（没有新吊尾巴）',
              not bad_tail, u'例外 %d 条' % len(bad_tail))

        # 小数点守卫：造一条"唯一的 `.` 是小数点、后面全是字母"的样本
        dec = u'a' * 150 + u'3.14' + u'b' * 100
        got, _c = new(dec, 200)
        check(u'C5 小数点守卫：不会切在 `3.` 后面（尾部不是 `3.`）',
              not got.endswith(u'3.'), u'尾 4 字=%r' % got[-4:])
        # 正控制 1：纯英文句号
        en = u'Hi there. ' * 30
        got_en, _c = new(en, 200)
        check(u'C6 正控制：纯英文回复必须切在 `.` 上（尾字符是 `.`）',
              got_en.endswith(u'.'))
        # 正控制 2：纯中文
        zh = u'你好呀。' * 60
        got_zh, _c = new(zh, 200)
        check(u'C7 正控制：纯中文回复仍切在 `。` 上（尾字符是 `。`）',
              got_zh.endswith(u'\u3002'))

        # 负控制：把 `_dot` 整块删掉 ⇒ 必须逐条退化成 OLD
        keep, skipping = [], False
        for ln in seg.split(u'\n'):
            if u'_dot = t.rfind' in ln:
                skipping = True
            if skipping:
                if u'cut = _dot' in ln:
                    skipping = False
                continue
            keep.append(ln)
        neg_code = u'\n'.join(keep)
        check(u'C8 负控制确实动到了源码（删掉 `_dot` 相关行）',
              neg_code != seg,
              u'少 %d 行' % (len(seg.split(u'\n')) - len(neg_code.split(u'\n'))))
        neg = _mk(neg_code)
        mismatch = 0
        for s in over:
            if neg(s['t'], s['mc']) != old(s['t'], s['mc']):
                mismatch += 1
        check(u'C9 负控制：删掉 ASCII `.` 后与 OLD 逐条一致（不一致 0 条）',
              mismatch == 0, u'不一致 %d 条' % mismatch)

    # ======================================================================
    head(u'D · 登记面（改动理由写在改的地方，别让它只活在报告里）')

    # ⚠️ D1 第一版只断「段里出现 `第143轮`」—— 被 `M5` 抓出来是**恒真族**：
    #   注释里还有一处 `第143轮/_evidence/lead143c.json`（证据路径），
    #   把标题那句删掉它照样绿。⇒ 钉**完整首行**，不是钉"提到某个名字"。
    check(u'D1 `main.py` 第 3 步的注释首行是「★★★ 第143轮：切点集补 ASCII」',
          u'\u2605\u2605\u2605 \u7b2c143\u8f6e\uff1a\u5207\u70b9\u96c6\u8865 ASCII' in seg)
    check(u'D2 注释里写了 `…` 当逗号的实测依据（97.4%）', u'97.4%' in seg)
    check(u'D3 注释里写了四变体对照的硬截数（`0 / 61` 与 `0 / 59`，防以后凭直觉补 `…`）',
          u'0 / 61' in seg and u'0 / 59' in seg)
    check(u'D4 报告与三份证据在盘上',
          all(os.path.isfile(os.path.join(EV, n)) for n in
              ('lead143.json', 'lead143b.json', 'lead143c.json', 'ab143.json')))

    # ======================================================================
    head(u'E · 自检')

    tree = ast.parse(_read(os.path.join(HERE, 'check143.py')))
    calls = [nd for nd in ast.walk(tree)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    # 判据描述里不许出现那个计数标记（否则 run_all 的正则会把这一行多算一次）
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and ('[' + 'PASS]') in sub.value:
                leak.append(sub.value[:36])
    check(u'E1 ★判据描述里没有那个计数标记的字面量（会顶高 run_all 的 PASS 计数）',
          not leak, u'命中 %d 处' % len(leak))

    trues = []
    for nd in calls:
        if len(nd.args) >= 2:
            a = nd.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                trues.append(True)
    check(u'E2 没有 `check(描述, True)` 这种恒真判据（`False` 是故意的报红锚点，不算）',
          not trues, u'命中 %d 处' % len(trues))

    n_ran = _n['p'] + _n['f']
    # 差 2 而不是 1：本判据自己还没跑（1 处）+ `C0` 与 C 段主分支**互斥**
    #   （`new is None` 才跑 C0，正常情况下它永远不执行）。第一版写成"差 1"就红了。
    check(u'E3 写了多少处 check( 与实际跑了几条，只差"本判据自己"与互斥分支 C0',
          len(calls) - n_ran == 2, u'calls=%d ran=%d' % (len(calls), n_ran))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
