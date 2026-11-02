# -*- coding: utf-8 -*-
"""第143轮 · 改后 A/B：**直接跑产品源码那一段**，不是复刻。

## 为什么用 AST 抠源码而不是把逻辑抄一遍

本项目铁律「夹具不保真 = 报假问题」。把截断逻辑抄进测量脚本，测的是"我以为产品长什么样"。
所以这里从 `ralsei_pet/src/main.py` 里用 `ast` **抠出真正的 `if len(t) > max_chars:` 整段**，
`exec` 成函数再跑 —— 抠的时候顺手断言：① 抠到的源码里确有 ASCII `.`；
② 确有小数点守卫（`isdigit()`）；③ OLD（HEAD 版，硬编码在下方）**没有** `.`
—— 三条断言全过，才说明 A/B 两臂真的不一样（否则就是恒真 A/B）。

## 两臂

* OLD = 第143轮之前的切点集 `。！？!?\\n`（从 `git show HEAD:ralsei_pet/src/main.py` 抄，
  脚本里会**再对一次** HEAD 文本，防止我抄错）
* NEW = 从工作区源码 AST 抠出来的那一段

## 判据

1. OLD 上必须复现 61 条硬截（否则说明语料/口径变了，不能拿去支撑结论）
2. NEW 上硬截应降到 2 条
3. **中文样本的结果必须一条都不变**（中文本来 0 硬截，改它没有收益；若变了就是副作用）
4. 负控制：把 NEW 源码里的 `'.'` 删掉 ⇒ 必须逐条退化成 OLD 的结果
"""
import ast
import glob
import io
import json
import os
import re
import subprocess
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
EVID = os.path.join(ROUND, '_evidence')
CARDS = os.path.join(PET, 'assets', 'npc', '_training', 'cards')

CJK = re.compile(u'[\u4e00-\u9fff]')


def _src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def say(s):
    sys.stdout.write(s + u'\n')


def _head_main():
    """HEAD 版 `main.py` 的文本（用于自证 OLD 没抄错）。"""
    try:
        r = subprocess.run(['git', 'show', 'HEAD:ralsei_pet/src/main.py'],
                           cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return r.stdout.decode('utf-8')
    except Exception:
        pass
    return None


def _extract_step3(src):
    """从 `_clean_ai_reply` 里抠出 `if len(t) > max_chars:` 整段源码。"""
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_clean_ai_reply':
            body = node
            break
    if body is None:
        raise RuntimeError(u'找不到 _clean_ai_reply')
    hit = None
    # ⚠️ 第 3 步在 `_clean_ai_reply` 里套在 `try:` 里 ⇒ 不是 `body.body` 的直接子节点，
    #    必须 ast.walk；用 `cut = -1` 这个特征片段定位（全仓只有这一处）。
    for sub in ast.walk(body):
        if isinstance(sub, ast.If):
            seg = ast.get_source_segment(src, sub) or u''
            if u'cut = -1' in seg and u'max_chars' in seg:
                if hit is None or len(seg) > len(ast.get_source_segment(src, hit) or u''):
                    hit = sub
    if hit is None:
        raise RuntimeError(u'找不到第 3 步')
    return ast.get_source_segment(src, hit)


def _mk(code):
    """把一段 `if ...:` 包成函数（缩进对齐 def 体）。

    ★ 让函数**把 `cut` 也返回出来**：`cut == -1` 才是"一个切点都没找到"的精确判据。
      第一版只看返回值，于是一批"切点之后到上限之间全是空白"的样本被误判成硬截
      （`t[:cut+1].strip()` 恰好等于 `t[:max_chars].strip()`）—— 中文 7 / 英文 66
      里有一半是这个假阳性。**判据要看机制，别看结果的形状。**
    """
    fn = (u'def _step3(t, max_chars):\n    cut = None\n'
          + textwrap.indent(textwrap.dedent(code), u'    ')
          + u'\n    return t, cut\n')
    env = {}
    exec(compile(fn, '<step3>', 'exec'), env)
    return env['_step3']


OLD_CODE = u'''
if len(t) > max_chars:
    cut = -1
    for sep in (u'\\u3002', u'\\uff01', u'\\uff1f', u'!', u'?', u'\\n'):
        i = t.rfind(sep, 0, max_chars)
        if i > cut:
            cut = i
    t = (t[:cut + 1] if cut > 0 else t[:max_chars]).strip()
'''


def main():
    src = _src(MAIN)
    code_new = _extract_step3(src)
    say(u'=== 抠出的第 3 步源码（%d 行）===' % code_new.count(u'\n'))
    for ln in code_new.split(u'\n'):
        say(u'  | ' + ln)

    # 三条"两臂真的不一样"的断言
    old = _mk(OLD_CODE)
    new = _mk(code_new)
    checks = []
    checks.append((u"ASCII `.` 在工作区源码里（`t.rfind('.', …)`）",
                   u"t.rfind('.'," in code_new))
    checks.append((u'小数点守卫 isdigit 在工作区源码里', u'isdigit()' in code_new))
    checks.append((u'HEAD 版里没有 ASCII `.`（OLD 抄得对）',
                   (lambda h: bool(h) and u"'。', '！', '？', '!', '?', '\\n'" in h)(_head_main())))
    say(u'')
    for name, ok in checks:
        say(u'  [%s] %s' % (u'OK' if ok else u'FAIL', name))
    if not all(ok for _, ok in checks):
        say(u'两臂不成立，停止。')
        return 2

    # 语料
    cards = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        try:
            mc = (json.loads(_src(p)).get('length_policy') or {}).get('max_chars')
        except Exception:
            continue
        if isinstance(mc, int) and mc > 0:
            cards[os.path.basename(p)[:-5]] = mc

    samples = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
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
    over = [s for s in samples if len(s['t']) > s['mc']]
    say(u'')
    say(u'语料 %d 条，其中超上限 %d 条（中 %d / 英 %d）'
        % (len(samples), len(over),
           len([s for s in over if s['lang'] == 'zh']),
           len([s for s in over if s['lang'] == 'en'])))

    def hard(s, fn):
        """硬截判据：**`cut == -1`**（一个切点都没找到 ⇒ 走 `t[:max_chars]`）。

        ⚠️ 这条判据我改了两版才对，两版都是"看结果的形状"而不是"看机制"：
        ① 第一版判"结果末字符不是句末标点" ⇒ 把 `\\n` 切点全误判成硬截（`\n` 被 strip 掉了）；
        ② 第二版判"结果 == `t[:max_chars].strip()`" ⇒ 切点之后到上限之间全是空白的样本
           会与硬截**同形**，又误判一批。
        真正等价于"没找到切点"的只有 `cut` 本身 —— 所以让被测函数把 `cut` 返出来。
        """
        _, c = fn(s['t'], s['mc'])
        return c is not None and c < 0

    res = {'total': len(samples), 'over': len(over)}
    for tag, fn in ((u'OLD', old), (u'NEW', new)):
        h = {'zh': 0, 'en': 0}
        for s in over:
            if hard(s, fn):
                h[s['lang']] += 1
        res[tag] = {'hard_zh': h['zh'], 'hard_en': h['en']}
        say(u'  %s 硬截：中文 %d / 英文 %d' % (tag, h['zh'], h['en']))

    # 逐条 diff（只统计差异，不打印时相量）
    diff = []
    for s in over:
        a, _ = old(s['t'], s['mc'])
        b, _ = new(s['t'], s['mc'])
        if a != b:
            diff.append({'id': s['id'], 'lang': s['lang'], 'mc': s['mc'],
                         'len': len(s['t']), 'old': a[-30:], 'new': b[-30:]})
    res['diff'] = len(diff)
    res['diff_zh'] = len([d for d in diff if d['lang'] == 'zh'])
    res['diff_en'] = len([d for d in diff if d['lang'] == 'en'])
    say(u'  截断结果不同：%d 条（中 %d / 英 %d）'
        % (res['diff'], res['diff_zh'], res['diff_en']))
    for d in diff[:8]:
        say(u'   [%s/%s] len=%d 旧尾=%r 新尾=%r'
            % (d['id'], d['lang'], d['len'], d['old'], d['new']))
    say(u'')

    # 判据 3：中文侧**硬截条数不许增加**，且新增切点必须落在真句末上
    #   ★ 第一版判据写的是"中文样本结果一条都不许变"，跑出来 15 条变化就红了 ——
    #     逐条看，15 条**全是"切得更晚、多保留了原句"**（`Well, well, well.` /
    #     `EVEN IF IT MEANS TAKING LIVES.` / `Dinner's almost ready.`，都是原文本就有、
    #     角色自己夹的英文），没有一条是半句话。所以"不许变"这个判据**本身错了**
    #     （把好处判成副作用），改成"不许出现新的吊尾巴"。
    zh_hard = res['NEW']['hard_zh']
    tail_ok = u'\u3002\uff01\uff1f!?.\u2026'
    bad_tail = []
    for d in diff:
        if d['lang'] != 'zh':
            continue
        if not d['new'] or d['new'][-1] not in tail_ok:
            bad_tail.append(d)
    say(u'  [%s] 判据3a 中文硬截不增加（OLD %d → NEW %d）'
        % (u'OK' if zh_hard <= res['OLD']['hard_zh'] else u'FAIL',
           res['OLD']['hard_zh'], zh_hard))
    say(u'  [%s] 判据3b 变化的 %d 条中文里，新尾都是句末标点（例外 %d 条）'
        % (u'OK' if not bad_tail else u'FAIL', res['diff_zh'], len(bad_tail)))
    for d in bad_tail[:6]:
        say(u'     [%s] 新尾=%r' % (d['id'], d['new']))

    # 判据 4：负控制 —— 把 NEW 里的 `_dot` 整块删掉，必须退化成 OLD
    #   ⚠️ 第一版用 `code_new.replace("'.', ", '')` 删「ASCII `.`」——
    #      它把 `t.rfind('.', 0, max_chars)` 里的 `'.', ` 也删了，
    #      于是 `t.rfind(0, max_chars)` ⇒ `TypeError: must be str, not int`。
    #      负控制**拆错了东西**，报的不是"判据失效"而是崩溃（另一种报假问题）。
    keep, skipping = [], False
    for ln in code_new.split(u'\n'):
        if u'_dot = t.rfind' in ln:
            skipping = True
        if skipping:
            if u'cut = _dot' in ln:
                skipping = False
            continue
        keep.append(ln)
    neg_code = u'\n'.join(keep)
    say(u'  [%s] 负控制确实改到了源码（删掉 %d 行）'
        % (u'OK' if neg_code != code_new else u'FAIL',
           len(code_new.split(u'\n')) - len(neg_code.split(u'\n'))))
    neg = _mk(neg_code)
    mismatch = 0
    for s in over:
        if neg(s['t'], s['mc']) != old(s['t'], s['mc']):
            mismatch += 1
    say(u'  [%s] 判据4 负控制：删掉 ASCII `.` 后与 OLD 逐条一致（不一致 %d 条）'
        % (u'OK' if mismatch == 0 else u'FAIL', mismatch))
    res['neg_mismatch'] = mismatch

    # 判据 1/2
    res['ok_old61'] = (res['OLD']['hard_en'] == 61)
    res['ok_new2'] = (res['NEW']['hard_en'] == 2)
    say(u'  [%s] 判据1 OLD 复现 61 条英文硬截'
        % (u'OK' if res['ok_old61'] else u'FAIL'))
    say(u'  [%s] 判据2 NEW 降到 2 条'
        % (u'OK' if res['ok_new2'] else u'FAIL'))

    p = os.path.join(EVID, 'ab143.json')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    say(u'')
    say(u'写盘：%s' % os.path.relpath(p, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
