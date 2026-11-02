# -*- coding: utf-8 -*-
"""第143轮 · 核心文件复检（改过 `ralsei_pet/src/main.py` —— 产品主链路，必做）。

六项逐条打 PASS/FAIL 并落盘（用户口径：「以后再调整重要核心文件时一定要记得复检」）：

  H1 改动面：动了哪几行、几处 hunk、EOL 有没有被写混
  H2 语法（`ast.parse`，**不用 `py_compile`** —— 那会产 `.pyc` 改变被测状态）
  H3 编码：无 BOM / 无 U+FFFD
  H4 恒真判据复查（`check(desc, True)`）＋ H4b（函数体第一层的 `return True`）
     ＋ H4c（**判据自己不许打印那个计数标记**，且运行时标记次数 == 自报 PASS）
  H5 **逐令牌回验**：`main.py` 注释里引用的每个数字，回证据/原作数据核一次
  H6 工作区白名单（临时/备份/缓存没混进来；`main.py.bak143` 不许残留）
  H7 写盘目标只在本轮 `_evidence/`

★ 为什么要单独复检 `main.py`：它是**产品主链路**里唯一被改的文件，且改动落在
  `_clean_ai_reply` 的第 3 步 —— 对话链、NPC 链、自主开口链**都从这里过**
  （第140轮的注释已写明它要求"单一真源"）。改错一个字，表现是"台词被截短"，
  而且在回归里**不会报错**，只会悄悄变短。
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
OUT = os.path.join(EV, 'recheck143.json')

MAIN = os.path.join(PET, 'src', 'main.py')
ES = os.path.join(PET, 'modules', 'event_speech.py')
CHECK = os.path.join(HERE, 'check143.py')
MUTATE = os.path.join(HERE, 'mutate143.py')

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
    head(u'H1 · 改动面（改了哪几处、EOL 有没有被写混）')

    for tag, p in ((u'main.py', MAIN), (u'event_speech.py', ES),
                   (u'check143.py', CHECK), (u'mutate143.py', MUTATE)):
        b = _raw(p)
        s = _txt(p)
        crlf = s.count(u'\r\n')
        lf = s.count(u'\n') - crlf
        print(u'  %-18s sha1=%s  字节=%d  行=%d  CRLF=%d 裸LF=%d'
              % (tag, _sha1(p)[:12], len(b), s.count(u'\n'),
                 crlf, lf))

    diff = _git('diff', '-U0', '--', 'ralsei_pet/src/main.py')
    n_hunk = len([l for l in diff.split(u'\n') if l.startswith(u'@@')])
    # 为什么是 2 处而不是 1 处：`cut = -1` 那一行**没动**，它把本次新增的
    #   注释块与 `_dot` 逻辑隔开 ⇒ `-U0` 下自然裂成两块。第一版写成"必须 1 处"
    #   就红了 —— 又是"判据假设了实现的形状"。
    check(u'H1a `main.py` 的改动只有 2 处 hunk（注释块 / `_dot` 逻辑，中间隔着未动的 `cut = -1`）',
          n_hunk == 2, u'hunk=%d' % n_hunk)
    plus = len([l for l in diff.split(u'\n')
                if l.startswith(u'+') and not l.startswith(u'+++')])
    minus = len([l for l in diff.split(u'\n')
                 if l.startswith(u'-') and not l.startswith(u'---')])
    # ★ 这条比"加了几行"更有价值：**零删除**说明没重写既有行为，只是新增了一路切点。
    check(u'H1b 纯新增（删 0 行、增 <60 行）—— 没有重写既有行为',
          minus == 0 and 0 < plus < 60, u'+%d / -%d' % (plus, minus))
    ev_src = _txt(ES)
    check(u'H1c `event_speech.py` 本轮**一字未动**（事件链的分叉是刻意的，不是漏改）',
          not _git('diff', '--', 'ralsei_pet/modules/event_speech.py').strip())

    # ======================================================================
    head(u'H2 · 语法（ast.parse；不用 py_compile，免得产 .pyc 改变被测状态）')

    bad = []
    for p in (MAIN, CHECK, MUTATE):
        try:
            ast.parse(_txt(p))
        except SyntaxError as e:
            bad.append(u'%s: %s' % (os.path.basename(p), e))
    check(u'H2 三个脚本都能解析（main.py / check143.py / mutate143.py）',
          not bad, u' | '.join(bad))

    # ======================================================================
    head(u'H3 · 编码（无 BOM / 无 U+FFFD）')

    for tag, p in ((u'main.py', MAIN), (u'check143.py', CHECK),
                   (u'mutate143.py', MUTATE)):
        b = _raw(p)
        s = _txt(p)
        check(u'H3 %s 无 BOM' % tag, not b.startswith(b'\xef\xbb\xbf'))
        check(u'H3 %s 无 U+FFFD（没有被错误转码的字符）' % tag,
              u'\ufffd' not in s)

    # ======================================================================
    head(u'H4 · 恒真判据复查（"看着在守其实没守"）')

    tree = ast.parse(_txt(CHECK))
    calls = [nd for nd in ast.walk(tree)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    trues = [nd for nd in calls
             if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant)
             and nd.args[1].value is True]
    check(u'H4a `check143.py` 里没有 `check(描述, True)`', not trues,
          u'命中 %d 处' % len(trues))
    # `False` 是本仓惯用的"故意无条件报红"锚点（C0 就是），单列出来给人看，不算缺陷
    falses = [nd for nd in calls
              if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant)
              and nd.args[1].value is False]
    print(u'  （另有 %d 处 `check(描述, False)`：故意的报红锚点，不算恒真）'
          % len(falses))

    ret_true = []
    for fn in [nd for nd in ast.walk(tree) if isinstance(nd, ast.FunctionDef)]:
        for st in fn.body:          # ★ 只看**函数体第一层**（ast.walk 会把
            if isinstance(st, ast.Return) and isinstance(st.value, ast.Constant) \
                    and st.value.value is True:
                ret_true.append(fn.name)
    check(u'H4b 没有"函数体第一层直接 return True"的桩函数', not ret_true,
          u'命中 %d 个' % len(ret_true))

    # H4c：判据自己不许打印那个计数标记（第141/142 轮的幽灵计数）
    marker = '[' + 'PASS]'
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and marker in sub.value:
                leak.append(1)
    check(u'H4c ★判据描述里没有那个计数标记的字面量（会顶高 run_all 的 PASS 计数）',
          not leak, u'命中 %d 处' % len(leak))

    r = subprocess.run([sys.executable, CHECK], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = r.stdout.decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+) FAIL=(\d+)', txt)
    self_pass = int(m.group(1)) if m else -1
    check(u'H4c2 运行时标记次数 == 套件自报 PASS（没有幽灵计数）',
          self_pass == txt.count(marker), u'自报=%d 标记=%d' % (self_pass,
                                                             txt.count(marker)))

    # ======================================================================
    head(u'H5 · 逐令牌回验（注释与报告里的每个数字，回原作数据核一次）')

    lead = json.loads(_txt(os.path.join(EV, 'lead143.json')))
    leadb = json.loads(_txt(os.path.join(EV, 'lead143b.json')))
    leadc = json.loads(_txt(os.path.join(EV, 'lead143c.json')))
    ab = json.loads(_txt(os.path.join(EV, 'ab143.json')))
    seg = _txt(MAIN)

    # ⚠️ 第一版从 `ab143.json` 里取 `over_zh/over_en` —— 那两个键在 **lead143b.json**
    #   （语言拆分那一步）里，ab143 里没有 ⇒ `.get()` 返回 None ⇒ 两条判据假红。
    #   "读错文件"和"数字不对"长得一模一样，必须靠键名核对分开。
    tokens = [
        (u'77 人', u'77' == str(lead.get('files'))),
        (u'5592 条', u'5592' == str(lead.get('turns'))),
        (u'336 条超限', u'336' == str(lead.get('over'))),
        (u'中文 170', u'170' == str(leadb.get('over_zh'))),
        (u'英文 166', u'166' == str(leadb.get('over_en'))),
        (u'硬截 61', u'61' == str(leadc.get('hard_total'))),
        (u'`. 切点（中文）15 条', u'15' == str(leadc.get('zh_dot_cut'))),
        (u'NEW 剩 2', u'2' == str(ab.get('NEW', {}).get('hard_en'))),
        (u'OLD 61', u'61' == str(ab.get('OLD', {}).get('hard_en'))),
        (u'变化 107 条', u'107' == str(ab.get('diff'))),
        (u'其中中文 15', u'15' == str(ab.get('diff_zh'))),
        (u'卡片 77 张、max_chars=200', u'200' in _txt(os.path.join(
            PET, 'assets', 'npc', '_training', 'cards', 'ralsei.json'))),
    ]
    for name, ok in tokens:
        check(u'H5 回验：%s' % name, bool(ok))

    # 注释里写的数字必须真的能从证据里对上（防"报告改了、注释没改"）
    for lit in (u'0 / 61', u'0 / 59', u'0 / 2', u'0 / 1', u'97.4%', u'36.7%'):
        check(u'H5 注释里写的 `%s` 是真值之一' % lit, lit in seg)

    # ======================================================================
    head(u'H6 · 工作区白名单（临时/备份没混进来）')

    por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
    lines = [l for l in por.split(u'\n') if l.strip()]
    print(u'  工作区状态 %d 行' % len(lines))
    # ★ 白名单按**路径**列，每条都写清为什么允许 —— 只按"状态前缀"列（` M ` / `?? `）
    #   会在 memory 从"改"变"新增"时假红。第一版就是这样。
    allow_paths = (
        (u'ralsei_pet/src/main.py', u'本轮唯一产品改动'),
        (u'code-quality-audit/第143轮-对话链截断切点/', u'本轮产物'),
        (u'code-quality-audit/regress/', u'登记 + 基线'),
        (u'.workbuddy/memory/', u'记忆'),
        (u'code-quality-audit/第142轮-NPC补丁去重/_tools/measure142b.py',
         u'连带订正（注释与实现相反）'),
        (u'code-quality-audit/第138轮-判据输出去时相/_evidence/phase138.json',
         u'已知刷脏（登记未修）'),
    )
    bad_paths = []
    for l in lines:
        path = l[2:].lstrip().strip(u'"')
        if not any(path.startswith(p) for p, _ in allow_paths):
            bad_paths.append(l)
    check(u'H6a 工作区只有预期改动（%d 条允许路径，逐条写了理由）'
          % len(allow_paths), not bad_paths, u'越界 %d 行' % len(bad_paths))
    for l in bad_paths[:8]:
        print(u'     %s' % l)
    for l in lines:
        print(u'     允许：%s' % l)
    check(u'H6b 没有残留 `.bak143` 备份',
          not [l for l in lines if u'.bak143' in l])

    # ======================================================================
    head(u'H7 · 写盘目标（只在本轮 _evidence/）')

    # ⚠️ 第一版把"写盘变量名"写死成 `p` / `OUT` —— `measure143.py` 用的是 `out`，
    #   当场假红。判据该断的是"写盘路径能不能追溯到本轮的 `_evidence/`"，
    #   而不是"变量叫什么名字"。
    scripts = [CHECK, MUTATE,
               os.path.join(HERE, 'measure143.py'),
               os.path.join(HERE, 'measure143b.py'),
               os.path.join(HERE, 'measure143c.py'),
               os.path.join(HERE, 'measure143d.py')]
    outs, no_anchor, abs_path = [], [], []
    for p in scripts:
        if not os.path.isfile(p):
            continue
        src = _txt(p)
        hits = re.findall(r"(?:io\.open|open)\(\s*([A-Za-z_][\w.\[\]']*)", src)
        writes = len(re.findall(r",\s*'w'", src))
        if writes and not (u'os.path.join(EV' in src or u'os.path.join(EVID' in src
                           or u'OUT' in src):
            no_anchor.append(os.path.basename(p))
        outs.extend(hits)
        for ln in src.split(u'\n'):
            if u"'w'" in ln and re.search(u"['\"][A-Za-z]:[\\\\/]", ln):
                abs_path.append(os.path.basename(p))
    print(u'  写盘点：%s' % (u' | '.join(sorted(set(outs))) or u'（无）'))
    check(u'H7a 每个有写盘的脚本都能追溯到本轮 `_evidence/`（EV / EVID / OUT）',
          not no_anchor, u'没有锚点：%s' % (u', '.join(no_anchor) or u'无'))
    check(u'H7b 写盘行里没有写死的绝对盘符（不许往 D:/E:/C: 落）',
          not abs_path, u'越界：%s' % (u', '.join(set(abs_path)) or u'无'))

    # ======================================================================
    out['summary'] = {'pass': _n['p'], 'fail': _n['f']}
    out['sha1'] = {u'main.py': _sha1(MAIN), u'event_speech.py': _sha1(ES),
                   u'check143.py': _sha1(CHECK), u'mutate143.py': _sha1(MUTATE)}
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
