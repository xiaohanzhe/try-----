# -*- coding: utf-8 -*-
"""第143轮 · 量：「句末标点」在这个仓库里到底有几套尺子，对话链的超长截断会不会硬截。

## 起因（第142轮遗留 ①）

速查本里那句 `数句子不含 …、切点含 …（两套标点）` 一直没被证实过。本轮直接读源码取真值。
第142轮顺手还留了个疑点：`measure142b.py` 的 `END` 常量注释写
「与 `common113._sentences` 同口径（不含 `…`）」，但 `_sentences` 的源码里**有** `…`
—— 注释与实现相反。先证实这个，再谈要不要治。

## 本脚本问四件事（全部只读，不改产品）

Q1 五处「句末标点」定义逐字取出来，做集合对照（谁含 `…`、谁不含、谁多出 `；`/`\n`）
Q2 语料里真正会触发对话链截断（>200 字）的回复有多少条，其中**一条句末标点都没有**
   ⇒ `cut = -1` ⇒ **硬截**（截在半句话上，即第135轮治过的"吊尾巴"，但对话链这一支没治）
   的有几条
Q3 若把 `…` 并进对话链的切点集，切点会往后移多少字、还有多少条硬截
Q4 事件链 / 自主开口链会不会被牵连（口径确认，不测）

## 口径（先声明，免得被数字骗）

* 语料 = `第113轮/_evidence/raw30/*.jsonl` 的 `turns[].final`（77 文件）。
  它是**判退重采样后的模型输出原文**，也就是 `_clean_ai_reply` 第 3 步的**输入** ——
  正是我们要测的那一段逻辑的入口，所以口径合适。
* 「>200 字」= `len(t) > max_chars`，`max_chars` 取该角色卡 `length_policy.max_chars`，
  缺卡回落 220（与 `main._clean_ai_reply` 第 3 步同一条规则）。
* 硬截判据 = 复刻第 3 步：
  ```python
  cut = -1
  for sep in ('。', '！', '？', '!', '?', '\\n'):
      i = t.rfind(sep, 0, max_chars)
      if i > cut: cut = i
  t = t[:cut+1] if cut > 0 else t[:max_chars]
  ```
  `cut == -1` ⇒ 走 `t[:max_chars]` ⇒ 尾字符不是任何句末标点 ⇒ **吊尾巴**。
"""
import ast
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
EVID = os.path.join(ROUND, '_evidence')
CARDS = os.path.join(PET, 'assets', 'npc', '_training', 'cards')

sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, os.path.join(PET, 'src'))

SEPS_MAIN = (u'\u3002', u'\uff01', u'\uff1f', u'!', u'?', u'\n')  # 对话链第 3 步（真值来自 AST）


def _src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_src(p))


def say(s):
    sys.stdout.write(s + u'\n')


# ---------------------------------------------------------------------------
# Q1 五处定义
# ---------------------------------------------------------------------------
def q1():
    say(u'=== Q1 「句末标点」的每一处定义（源码取值）===')
    rows = {}

    # 1) 事件链：直接 import（纯逻辑，无 Qt）
    import event_speech as ES
    rows['event_speech._SENTENCE_ENDS'] = ES._SENTENCE_ENDS

    # 2) 对话链第 3 步：AST 取 `for sep in (...)` 的元组字面量
    tree = ast.parse(_src(os.path.join(PET, 'src', 'main.py')))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                and node.target.id == 'sep' and isinstance(node.iter, ast.Tuple):
            vals = []
            ok = True
            for e in node.iter.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    vals.append(e.value)
                else:
                    ok = False
            if ok:
                found.append(u''.join(vals))
    rows['main._clean_ai_reply 第3步 for sep'] = found[0] if found else u'<未找到>'

    # 3) 训练侧数句子：AST 取 `re.split(r'[...]+', text)` 的第一个实参
    tree113 = ast.parse(_src(os.path.join(
        ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools',
        'common113.py')))
    pat = None
    for node in ast.walk(tree113):
        if isinstance(node, ast.FunctionDef) and node.name == '_sentences':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == 'split' and sub.args \
                        and isinstance(sub.args[0], ast.Constant):
                    pat = sub.args[0].value
    rows['common113._sentences 正则'] = pat or u'<未找到>'

    # 4) extreme113 的密度分母
    tree_ex = ast.parse(_src(os.path.join(
        ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools',
        'extreme113.py')))
    pat_ex = None
    for node in ast.walk(tree_ex):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'RE_SENT' for t in node.targets):
            if isinstance(node.value, ast.Call) and node.value.args \
                    and isinstance(node.value.args[0], ast.Constant):
                pat_ex = node.value.args[0].value
    rows['extreme113.RE_SENT'] = pat_ex or u'<未找到>'

    # 5) 第142轮自己那份（不是为了比对产品，是为了确认注释是否说谎）
    m142b = os.path.join(ROOT, 'code-quality-audit', '第142轮-NPC补丁去重',
                         '_tools', 'measure142b.py')
    pat142 = None
    if os.path.exists(m142b):
        t142 = ast.parse(_src(m142b))
        for node in t142.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(x, ast.Name) and x.id == 'END' for x in node.targets):
                if isinstance(node.value, ast.Constant):
                    pat142 = node.value.value
    rows['measure142b.END'] = pat142 or u'<未找到>'

    # 统一成"字符集"再比
    def charset(s):
        # 正则形如 [。！？!?…]+ ⇒ 取方括号内
        if s.startswith(u'['):
            inner = s[1:s.index(u']')]
            return set(inner)
        return set(s)

    base = None
    out = []
    for k in ('event_speech._SENTENCE_ENDS',
              u'main._clean_ai_reply 第3步 for sep',
              u'common113._sentences 正则',
              'extreme113.RE_SENT',
              'measure142b.END'):
        v = rows[k]
        cs = charset(v)
        if base is None:
            base = cs
        out.append({
            'where': k,
            'literal': v,
            'repr': repr(v),
            'has_ellipsis': u'\u2026' in cs,
            'only_here': sorted(cs - base),
            'missing': sorted(base - cs),
        })
        say(u'  %-34s %-22s `…`=%-5s 比事件链多=%s 少=%s' % (
            k, repr(v), u'\u2026' in cs,
            u''.join(sorted(cs - base)) or u'-',
            u''.join(sorted(base - cs)) or u'-'))
    say(u'')
    return out


# ---------------------------------------------------------------------------
# Q2/Q3 语料
# ---------------------------------------------------------------------------
def _cut(t, max_chars, seps):
    cut = -1
    for sep in seps:
        i = t.rfind(sep, 0, max_chars)
        if i > cut:
            cut = i
    return cut


def q23(seps_main, seps_with_ellipsis):
    cards = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        try:
            d = _json(p)
        except Exception:
            continue
        lp = d.get('length_policy') or {}
        mc = lp.get('max_chars')
        if isinstance(mc, int) and mc > 0:
            cards[os.path.basename(p)[:-5]] = mc

    files = sorted(glob.glob(os.path.join(RAW, '*.jsonl')))
    tot = 0
    over = []
    for p in files:
        name = os.path.basename(p)[:-6]
        mc = cards.get(name, 220)
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if not t:
                    continue
                tot += 1
                if len(t) > mc:
                    over.append((name, mc, t))

    say(u'=== Q2 语料：%d 个角色 / %d 条回复 ===' % (len(files), tot))
    say(u'  超过 max_chars 的（会进第 3 步截断）：%d 条' % len(over))

    hard = []
    early = []
    by_sep = {}
    for name, mc, t in over:
        c = _cut(t, mc, seps_main)
        if c < 0:
            hard.append((name, mc, t))
        else:
            by_sep[t[c]] = by_sep.get(t[c], 0) + 1
            if c + 1 < mc * 0.75:
                early.append((name, mc, c + 1, t))
    say(u'  ★ cut == -1（**硬截**，尾字符不是句末标点）:%d 条  ← 这就是"吊尾巴"'
        % len(hard))
    say(u'  切在哪个字符上：%s' % json.dumps(
        dict((k, v) for k, v in sorted(by_sep.items())), ensure_ascii=False))
    say(u'  切点 < 75%% 上限（宁可早切很多也要落在句末）：%d 条' % len(early))
    say(u'')

    if hard:
        say(u'  —— 硬截样例（最多 5 条，前 60 字）——')
        for name, mc, t in hard[:5]:
            say(u'   [%s] mc=%d len=%d 开头=%s' % (name, mc, len(t), t[:60]))
        say(u'')

    # Q3 加 `…` 之后
    gain = []
    hard2 = 0
    for name, mc, t in over:
        c1 = _cut(t, mc, seps_main)
        c2 = _cut(t, mc, seps_with_ellipsis)
        if c2 < 0:
            hard2 += 1
        if c2 > c1:
            gain.append(c2 - c1)
    gain.sort()

    def pct(xs, q):
        if not xs:
            return 0
        i = min(len(xs) - 1, int(round((len(xs) - 1) * q)))
        return xs[i]

    moved = len([g for g in gain if g > 0])
    say(u'=== Q3 把 `…` 并进切点集之后 ===')
    say(u'  切点后移的条数：%d / %d（%.1f%%）'
        % (moved, len(over), 100.0 * moved / max(1, len(over))))
    say(u'  后移字数：P50=%d P90=%d max=%d' % (pct(gain, 0.5), pct(gain, 0.9),
                                              gain[-1] if gain else 0))
    say(u'  仍然硬截：%d 条（原 %d 条）' % (hard2, len(hard)))
    say(u'')
    return {
        'files': len(files), 'turns': tot, 'over': len(over),
        'hard_cut': len(hard),
        'cut_char': dict((k, v) for k, v in sorted(by_sep.items())),
        'early_cut': len(early),
        'hard_samples': [{'id': n, 'max_chars': m, 'len': len(t), 'head': t[:60]}
                         for n, m, t in hard[:10]],
        'with_ellipsis': {'moved': moved, 'p50': pct(gain, 0.5),
                          'p90': pct(gain, 0.9),
                          'max': gain[-1] if gain else 0,
                          'still_hard': hard2},
    }


def main():
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    q1rows = q1()
    import event_speech as ES
    seps_main = SEPS_MAIN
    seps_with = seps_main + (u'\u2026',)
    stats = q23(seps_main, seps_with)
    stats['definitions'] = q1rows
    stats['seps_main'] = list(seps_main)
    stats['seps_event_chain'] = ES._SENTENCE_ENDS
    out = os.path.join(EVID, 'lead143.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=1))
    say(u'写盘：%s' % os.path.relpath(out, ROOT))


if __name__ == '__main__':
    main()
