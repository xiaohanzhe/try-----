# -*- coding: utf-8 -*-
"""第145轮 · 核心文件复检（改过 `event_speech.py` —— 事件链 + 主动开口链，必做）。

`event_speech.py` 是**产品主链路**：`first_sentence` 决定用户点一下看到的那句话，
`fit_sentences` 决定 Ralsei 主动开口说什么。改错一个字，回归**不会报错**，
只会让台词变短/变怪 —— 所以必须逐项复核（用户口径：「以后再调整重要核心文件时
一定要记得复检」）。

  H1 改动面：4 处 hunk / +46 −13，删掉的 13 行**全部**是那两段重复循环 + 常量行
  H2 语法（`ast.parse`，**不用 `py_compile`** —— 那会产 `.pyc` 改变被测状态）
  H3 编码：无 BOM / 无 U+FFFD / **EOL 保持 CRLF**（本文件原本就是 CRLF）
  H4 恒真判据复查 + 运行时标记数 == 自报 PASS
  H5 **逐令牌回验**：注释里写的每个数都回证据核一次
  H6 工作区白名单（按路径列 + 每条写理由）
  H7 写盘目标（只在本轮 `_evidence/`；不许写死盘符）
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'recheck145.json')

ES_PATH = os.path.join(PET, 'modules', 'event_speech.py')
MAIN = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check145.py')
MUTATE = os.path.join(HERE, 'mutate145.py')
MEASURE = os.path.join(HERE, 'measure145.py')
MEASURE_B = os.path.join(HERE, 'measure145b.py')

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


def _raw(p):
    with open(p, 'rb') as f:
        return f.read()


def _txt(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _sha1(p):
    return hashlib.sha1(_raw(p)).hexdigest()


def _git(*args):
    r = subprocess.run(['git'] + list(args), cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    return r.stdout.decode('utf-8', 'replace')


def main():
    out = {}

    # ======================================================================
    head(u'H1 · 改动面（删掉的每一行都要能说清是哪一行）')

    for tag, p in ((u'event_speech.py', ES_PATH), (u'check145.py', CHECK),
                   (u'mutate145.py', MUTATE), (u'measure145.py', MEASURE),
                   (u'measure145b.py', MEASURE_B)):
        s = _txt(p)
        crlf = s.count(u'\r\n')
        print(u'  %-18s sha1=%s  字节=%d  行=%d  CRLF=%d 裸LF=%d'
              % (tag, _sha1(p)[:12], len(_raw(p)), s.count(u'\n'),
                 crlf, s.count(u'\n') - crlf))

    diff = _git('diff', '-U0', '--', 'ralsei_pet/modules/event_speech.py')
    n_hunk = len([l for l in diff.split(u'\n') if l.startswith(u'@@')])
    plus = [l for l in diff.split(u'\n')
            if l.startswith(u'+') and not l.startswith(u'+++')]
    minus = [l for l in diff.split(u'\n')
             if l.startswith(u'-') and not l.startswith(u'---')]
    check(u'H1a 4 处 hunk（常量 / 新函数 / 两条链各一处）', n_hunk == 4,
          u'hunk=%d' % n_hunk)
    check(u'H1b +46 / −13', len(plus) == 46 and len(minus) == 13,
          u'+%d / -%d' % (len(plus), len(minus)))
    # 删掉的 13 行必须是：1 行常量 + 两段各 6 行的重复循环。逐行验，不靠"看着像"。
    body = [l[1:].strip() for l in minus]
    check(u'H1c 删掉的 1 行是常量赋值',
          len([l for l in body if l.startswith('_SENTENCE_ENDS =')]) == 1)
    check(u'H1d 删掉的 12 行**恰好**是两段重复循环（`_raw = sorted(...)` 出现 2 次、'
          u'`ends.append(_j)` 出现 2 次）',
          len([l for l in body if l.startswith('_raw = sorted(')]) == 2
          and len([l for l in body if l == 'ends.append(_j)']) == 2,
          u'raw=%d append=%d'
          % (len([l for l in body if l.startswith('_raw = sorted(')]),
             len([l for l in body if l == 'ends.append(_j)'])))
    check(u'H1e 删掉的行里没有 `check(`（没有顺手删判据）',
          not [l for l in body if u'check(' in l])
    check(u'H1f `main.py` 本轮**一字未动**（两条链的接线没碰）',
          not _git('diff', '--', 'ralsei_pet/src/main.py').strip())

    # ======================================================================
    head(u'H2 · 语法（ast.parse；不用 py_compile，免得产 .pyc 改变被测状态）')

    bad = []
    for p in (ES_PATH, CHECK, MUTATE, MEASURE, MEASURE_B):
        try:
            ast.parse(_txt(p))
        except SyntaxError as e:
            bad.append(u'%s: %s' % (os.path.basename(p), e))
    check(u'H2 五个脚本都能解析', not bad, u' | '.join(bad))

    # ======================================================================
    head(u'H3 · 编码（无 BOM / 无 U+FFFD / EOL 保持 CRLF）')

    for tag, p in ((u'event_speech.py', ES_PATH), (u'check145.py', CHECK),
                   (u'mutate145.py', MUTATE), (u'measure145.py', MEASURE),
                   (u'measure145b.py', MEASURE_B)):
        b = _raw(p)
        s = _txt(p)
        check(u'H3 %s 无 BOM' % tag, not b.startswith(b'\xef\xbb\xbf'))
        check(u'H3 %s 无 U+FFFD' % tag, u'\ufffd' not in s)

    s_es = _txt(ES_PATH)
    crlf = s_es.count(u'\r\n')
    lf = s_es.count(u'\n') - crlf
    # ★ 本文件原本就是纯 CRLF（`git` 属性 `text=auto`，工作区按 CRLF 检出）。
    #   第一版若只判"有 CRLF"就恒真了 —— 要判"**没有裸 LF**"。
    check(u'H3b `event_speech.py` 的 EOL 没被写混（裸 LF == 0）', lf == 0,
          u'CRLF=%d 裸LF=%d' % (crlf, lf))

    # ======================================================================
    head(u'H4 · 恒真判据复查（"看着在守其实没守"）')

    tree = ast.parse(_txt(CHECK))
    calls = [nd for nd in ast.walk(tree)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    trues = [nd for nd in calls
             if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant)
             and nd.args[1].value is True]
    check(u'H4a `check145.py` 里没有 `check(描述, True)`', not trues,
          u'命中 %d 处' % len(trues))
    ret_true = []
    for fn in [nd for nd in ast.walk(tree) if isinstance(nd, ast.FunctionDef)]:
        for st in fn.body:
            if isinstance(st, ast.Return) and isinstance(st.value, ast.Constant) \
                    and st.value.value is True:
                ret_true.append(fn.name)
    check(u'H4b 没有"函数体第一层直接 return True"的桩函数', not ret_true)
    marker = '[' + 'PASS]'
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and marker in sub.value:
                leak.append(1)
    check(u'H4c 判据描述里没有那个计数标记的字面量', not leak)

    r = subprocess.run([sys.executable, CHECK], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = r.stdout.decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+) FAIL=(\d+)', txt)
    self_pass = int(m.group(1)) if m else -1
    check(u'H4c2 运行时标记次数 == 套件自报 PASS', self_pass == txt.count(marker),
          u'自报=%d 标记=%d' % (self_pass, txt.count(marker)))

    # ======================================================================
    head(u'H5 · 逐令牌回验（注释里的每个数，回证据核一次）')

    lead = json.loads(_txt(os.path.join(EV, 'lead145.json')))
    ab = json.loads(_txt(os.path.join(EV, 'ab145.json')))
    en, zh, all_ = ab['en'], ab['zh'], ab['all']

    tokens = [
        (u'77 个文件', lead.get('files') == 77),
        (u'5592 条', lead.get('turns') == 5592),
        (u'英文 448 条', en['turns'] == 448),
        (u'事件链 203 → 135', en['mid24'] == [203, 135]),
        (u'开口链 184 → 100', en['mid40'] == [184, 100]),
        (u'中文 1031 / 5144', zh['mid24'][0] == 1031 and zh['turns'] == 5144),
        (u'全量 1234 → 1094', all_['mid24'] == [1234, 1094]),
        (u'40 字 423 → 300', all_['mid40'] == [423, 300]),
        (u'24 字内含 `.` 的英文 194 条', lead.get('en_dot_in_24') == 194),
    ]
    for name, ok in tokens:
        check(u'H5 回验：%s' % name, bool(ok))

    # 注释里写的两个百分数必须由这两个数算出来（不是手写的近似）
    p24 = round(203 * 100.0 / 448, 1)
    p40 = round(184 * 100.0 / 448, 1)
    check(u'H5 注释里的 `45.3%%` == 203/448', p24 == 45.3, u'算出 %.1f' % p24)
    check(u'H5 注释里的 `41.1%%` == 184/448', p40 == 41.1, u'算出 %.1f' % p40)
    body = _txt(ES_PATH)
    for lit in (u'203/448', u'184/448', u'1031/5144', u'45.3%', u'41.1%'):
        check(u'H5 注释里写了 `%s`' % lit, lit in body)

    # ======================================================================
    head(u'H6 · 工作区白名单（按路径列 + 每条写理由）')

    por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
    lines = [l for l in por.split(u'\n') if l.strip()]
    print(u'  工作区状态 %d 行' % len(lines))
    allow_paths = (
        (u'ralsei_pet/modules/event_speech.py', u'本轮唯一产品改动'),
        (u'code-quality-audit/第145轮-事件链英文切点/', u'本轮产物'),
        (u'code-quality-audit/regress/', u'登记 + 基线'),
        (u'.workbuddy/memory/', u'记忆'),
    )
    bad_paths = [l for l in lines
                 if not any(l[2:].lstrip().strip(u'"').startswith(p)
                            for p, _ in allow_paths)]
    check(u'H6a 工作区只有预期改动（%d 条允许路径，逐条写了理由）'
          % len(allow_paths), not bad_paths, u'越界 %d 行' % len(bad_paths))
    for l in bad_paths[:8]:
        print(u'     越界：%s' % l)
    check(u'H6b 没有残留 `.bak145` 备份',
          not [l for l in lines if u'.bak145' in l])

    # ======================================================================
    head(u'H7 · 写盘目标')

    for p in (CHECK, MUTATE, MEASURE, MEASURE_B):
        src = _txt(p)
        hits = [ln.strip()[:60] for ln in src.split(u'\n')
                if u"'w'" in ln and re.search(u"['\"][A-Za-z]:[\\\\/]", ln)]
        check(u'H7 %s 的写盘行里没有写死的盘符'
              % os.path.basename(p), not hits, u' | '.join(hits))
    check(u'H7b `measure145b` 把 HEAD 版落到 `D:\\_tmp`（临时件绝不放工作区）',
          u'D:\\\\_tmp' in _txt(MEASURE_B) or r'D:\_tmp' in _txt(MEASURE_B))

    # ======================================================================
    out['summary'] = {'pass': _n['p'], 'fail': _n['f']}
    out['sha1'] = dict((k, _sha1(v)) for k, v in (
        (u'event_speech.py', ES_PATH), (u'check145.py', CHECK),
        (u'mutate145.py', MUTATE)))
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
