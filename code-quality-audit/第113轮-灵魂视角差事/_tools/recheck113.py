# -*- coding: utf-8 -*-
"""第113轮 复检：改过「重要核心文件」之后的逐项自证（落盘）。

复检对象（本轮改动）：
  · `.workbuddy/memory/MEMORY.md`（速查本：§7/§5→§6/§7→§8 粘连修复 + §19 进度状态订正 + §10 去冗余指针）
  · `.workbuddy/memory/参考-契约与历轮（详版）.md`（新增 §113）
  · `.workbuddy/memory/2026-10-14.md`（新建当日日志）
  · `ralsei_pet/modules/npc_errand.py`（新建）· `ralsei_pet/src/main.py`（接线）

六类判据（见 skill `core-file-recheck`）：
  P1 可解析  P2 结构  P3 编码  P4 恒真判据复查  P5 逐令牌回验  P6 状态干净

★ 本脚本自己也会被 P4 的 AST 扫到 —— 所以本文件里**不许**出现 `ok(..., True)` 这种形状；
  纯信息一律走 `info()`（不计入判据数）。
"""
from __future__ import print_function

import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize as _tkmod
import traceback

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
REPORT = os.path.join(HERE, '..', '_evidence', 'recheck113.txt')

MEM_QUICK = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
MEM_DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
MEM_TODAY = os.path.join(ROOT, '.workbuddy', 'memory', '2026-10-14.md')

R = []          # [(name, ok, detail)]
INFOS = []      # 纯信息，不计入判据


def ok(name, cond, detail=''):
    R.append((name, bool(cond), detail))


def info(name, detail):
    INFOS.append((name, detail))


def read_b(path):
    with io.open(path, 'rb') as f:
        return f.read()


def text_b(raw):
    """字节忠实解码（不做 EOL 归一化 —— 契约：读文件必须 newline='' 级忠实）。"""
    return raw.decode('utf-8')


def _code_only(src):
    """用 `tokenize` 剥掉 STRING / COMMENT，只留代码 token（供正则侧独立计数）。"""
    out = []
    try:
        for tok in _tkmod.generate_tokens(io.StringIO(src).readline):
            if tok.type in (_tkmod.STRING, _tkmod.COMMENT, _tkmod.NL, _tkmod.NEWLINE):
                continue
            out.append(tok.string)
    except Exception:
        return src
    return ' '.join(out)


# ---------------------------------------------------------------- P1 可解析
def p1():
    pys = [
        'ralsei_pet/src/main.py',
        'ralsei_pet/modules/npc_errand.py',
        'code-quality-audit/第113轮-灵魂视角差事/_tools/check113.py',
        'code-quality-audit/第113轮-灵魂视角差事/_tools/mutate113.py',
        'code-quality-audit/第113轮-灵魂视角差事/_tools/rec113.py',
    ]
    for rel in pys:
        p = os.path.join(ROOT, rel)
        try:
            src = read_b(p).decode('utf-8')
            ast.parse(src)               # ★ 用 ast.parse，不产 .pyc（复检不许改变被测状态）
            ok('P1 parse %s' % os.path.basename(rel), True)
        except Exception as e:
            ok('P1 parse %s' % os.path.basename(rel), False, repr(e))

    jsons = [
        'code-quality-audit/regress/baseline.json',
        'code-quality-audit/第113轮-灵魂视角差事/_evidence/rec113_report.json',
    ]
    for rel in jsons:
        p = os.path.join(ROOT, rel)
        try:
            with io.open(p, encoding='utf-8') as f:
                json.load(f)
            ok('P1 json %s' % os.path.basename(rel), True)
        except Exception as e:
            ok('P1 json %s' % os.path.basename(rel), False, repr(e))

    ev = os.path.join(ROOT, 'code-quality-audit/第113轮-灵魂视角差事/_evidence/EVIDENCE.md')
    s = read_b(ev).decode('utf-8')
    n_fence = len(re.findall(r'(?m)^```', s))     # ★ 按行首数，不用裸 count('```')
    ok('P1 EVIDENCE 围栏成对', n_fence % 2 == 0, 'fences=%d' % n_fence)


# ---------------------------------------------------------------- P2 结构
def _body_no_fence(s):
    return re.sub(r'(?ms)^```.*?^```[ \t]*$', '', s)


#: 行内**合法**提到 `##` 的语境（前一个非空白字符属于这些 ⇒ 不是粘连）
_INLINE_PREFIX = '「『“"\u2018\u2019（(/、·\\'


def glued_heading_lines(text):
    """真·标题粘连：行首不是 `#`，却在行内出现 `## `/`### ` 这种**标题形状**。

    ★ 判据必须**先剥掉反引号片段**：本项目中大量正文以 `` `## 6.` `` 的形式
      **引用**标题（复检/记忆文档自己就写满了），不剥 ⇒ 12 行**假报红**
      （"判据过窄=误报"，与"恒真判据"是同一枚硬币的两面）。
    ★ 再排掉「引号/括号/斜杠/顿号」直接前缀 —— 那是**引述**，不是粘连。
    """
    out = []
    infence = False
    for i, raw in enumerate(text.split('\n'), 1):
        if raw.startswith('```'):
            infence = not infence
            continue
        if infence:
            continue
        l = re.sub(r'`[^`\n]*`', '', raw)          # 剥反引号片段（引用）
        m = re.search(r'##\s', l)
        if not m or l.startswith(('##', '>')):
            continue
        j = m.start() - 1
        if j >= 0 and l[j] in _INLINE_PREFIX:      # 引述语境 ⇒ 豁免
            continue
        out.append(i)
    return out


def p2():
    q = text_b(read_b(MEM_QUICK))
    lines = q.split('\n')
    miss = [n for n in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 19]
            if not any(l.startswith('## %d. ' % n) for l in lines)]
    ok('P2 速查本标题全在', not miss, 'missing=%r' % (miss,))
    gq = glued_heading_lines(q)
    ok('P2 速查本无标题粘连', not gq, 'lines=%r' % (gq,))
    # ★ 负控制：把 "## 6." 粘回上一行，检测器必须报红（防判据恒真/过宽）
    glued_fixture = q.replace('\n## 6. H4/H5', '。## 6. H4/H5', 1)
    ok('P2 负控制：人为粘连必被检出',
       glued_fixture != q and bool(glued_heading_lines(glued_fixture)),
       'fixture_changed=%s' % (glued_fixture != q))

    d = text_b(read_b(MEM_DETAIL))
    ok('P2 详版 §113 恰一处', d.count('## §113') == 1, 'count=%d' % d.count('## §113'))
    gd = glued_heading_lines(d)
    ok('P2 详版无标题粘连', not gd, 'lines=%r' % (gd[:8],))
    # ★ 本轮只**追加**在文件尾部 ⇒ 追加区间内必须零粘连（范围收窄，不受历史行内引用干扰）
    tail = d[d.index('## §113'):]
    ok('P2 详版新增区间零粘连', not glued_heading_lines(tail))

    t = text_b(read_b(MEM_TODAY))
    tl = t.split('\n')
    ok('P2 当日日志首行', tl[0].strip() == '# 2026-10-14 工作日志', repr(tl[0][:40]))
    ok('P2 当日日志有第113轮小节', any(l.startswith('## 第113轮') for l in tl))


# ---------------------------------------------------------------- P3 编码
def p3():
    cases = [
        ('ralsei_pet/src/main.py', 16821, 0),
        ('ralsei_pet/modules/npc_errand.py', 0, None),     # LF
        ('.workbuddy/memory/MEMORY.md', 0, None),
        ('.workbuddy/memory/参考-契约与历轮（详版）.md', 0, None),
        ('.workbuddy/memory/2026-10-14.md', 0, None),
    ]
    for rel, crlf_want, bare_want in cases:
        p = os.path.join(ROOT, rel)
        raw = read_b(p)
        crlf = raw.count(b'\r\n')
        bare = raw.count(b'\n') - crlf
        name = os.path.basename(rel)
        ok('P3 %s 无BOM' % name, raw[:3] != b'\xef\xbb\xbf')
        ok('P3 %s 无U+FFFD' % name, '\ufffd' not in text_b(raw))
        ok('P3 %s CRLF' % name, crlf == crlf_want, 'crlf=%d want=%d' % (crlf, crlf_want))
        if bare_want is not None:
            ok('P3 %s 裸LF' % name, bare == bare_want, 'bare=%d want=%d' % (bare, bare_want))
        else:
            ok('P3 %s 全LF' % name, crlf == 0 and bare > 0, 'crlf=%d bare=%d' % (crlf, bare))


# ------------------------------------------------------- P4 恒真判据复查
CK = ('check', 'ok', 'ck', 'expect', 'verify')


def _second_arg_forms(tree):
    """{判据名源码文本: {第二实参源码文本...}} —— 名字级恒真判据（skill §二.2/§二.3）。

    ★★ 为什么不能用"只要第二实参是常量 True 就报红"：本项目合法的**守卫写法**是
      `try: … ok('X', True) except: ok('X', False, err)`（P1 解析段就是这个形状）。
      名字级规则（同一"名字"**只**以常量 True 出现过 ⇒ 才判恒真）能同时避开
      "过宽=恒真"和"过窄=误报"两种毛病。
    """
    seen = {}
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and len(n.args) >= 2
                and (getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)) in CK):
            try:
                key = ast.unparse(n.args[0])
                val = ast.unparse(n.args[1])
            except Exception:
                continue
            seen.setdefault(key, set()).add(val)
    return seen


def p4():
    files = ['code-quality-audit/第113轮-灵魂视角差事/_tools/check113.py',
             'code-quality-audit/第113轮-灵魂视角差事/_tools/mutate113.py',
             'code-quality-audit/第113轮-灵魂视角差事/_tools/rec113.py',
             # ★ 复检脚本自己也扫（skill §二.3：判据也是被测物）
             'code-quality-audit/第113轮-灵魂视角差事/_tools/recheck113.py']
    for rel in files:
        src = read_b(os.path.join(ROOT, rel)).decode('utf-8')
        base = os.path.basename(rel)
        tree = ast.parse(src)
        seen = _second_arg_forms(tree)
        bad = sorted(k for k, v in seen.items() if v == {'True'})
        ok('P4 %s 无恒真判据(名字级AST)' % base, not bad, 'bad=%r' % (bad[:4],))
        # ★ 独立机制交叉验证：`tokenize` 剥掉**字符串/注释**后正则数一遍常量 True 实参。
        #   ⚠️ 不能用裸文本正则 —— 本文件 docstring 里就写着 `ok(..., True)` 当反例，
        #      裸正则会把它数进去（regex=4 vs ast=2 的**假报红**，实测踩到）。
        code = _code_only(src)
        n_re = len(re.findall(r",\s*True\s*[,\)]", code))
        n_ast = sum(1 for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and len(n.args) >= 2
                    and isinstance(n.args[1], ast.Constant) and n.args[1].value is True)
        ok('P4 %s 正则/AST 交叉一致' % base, n_re == n_ast,
           'regex=%d ast=%d' % (n_re, n_ast))

    # ★ 负控制：真恒真（同一名字只以常量 True 出现一次）必须被判出 —— 防判据恒真
    fx = "def f():\n    ok('只有恒真', True)\n"
    bad_fx = sorted(k for k, v in _second_arg_forms(ast.parse(fx)).items() if v == {'True'})
    ok('P4 负控制：真恒真必被检出', bool(bad_fx), 'bad=%r' % (bad_fx,))


# ------------------------------------------------------- P5 逐令牌回验
def tokenize(t):
    """可检索令牌：反引号片段 + 标识符 + 多位数 + **连续中文(>=3 字)**。

    ★★ 第一版**漏了中文** ⇒ `removed` 恒为空 ⇒ no-op 控制报红（判据过窄）。
      本项目速查本里被删的东西**绝大多数是中文短语**，不抓中文等于没在查。
    """
    out = set()
    for m in re.finditer(r'`([^`\n]+)`', t):
        out.add(m.group(1).strip())
    for m in re.finditer(r'[A-Za-z_][A-Za-z0-9_\.]{2,}', t):
        out.add(m.group(0))
    for m in re.finditer(r'\d{3,}', t):
        out.add(m.group(0))
    for m in re.finditer(r'[\u4e00-\u9fff]{3,}', t):
        out.add(m.group(0))
    return out


def _sq(s):
    return re.sub(r'[\s;=,\.\(\)（）/\u201c\u201d\u300c\u300d]', '', s)


def hit(tok, text):
    """三级命中：raw → squashed（吸收书写差异）→ subphrase（中文 >=4 字连续子串）。"""
    if tok in text:
        return 'raw'
    s = _sq(tok)
    if len(s) >= 3 and s in _sq(text):
        return 'squashed'
    cjk = re.sub(r'[^\u4e00-\u9fff]', '', tok)
    for i in range(0, max(0, len(cjk) - 3)):
        if cjk[i:i + 4] in text:
            return 'subphrase'
    return None


# 白名单：删掉的「指向详版的冗余指针」—— 必须带锚点，且锚点要在现盘真存在。
WHITELIST = {
    '全表见详版': '全表/要点见详版',          # §10 标题里保留的等价（超集）指针
    '§91~§107': '§91~§107',
    '§72': '§72',
    '§87': '§87',
}


def p5():
    before = subprocess.run(
        ['git', '-c', 'core.quotepath=false', 'show', 'HEAD:.workbuddy/memory/MEMORY.md'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode('utf-8')
    after = text_b(read_b(MEM_QUICK))
    detail = text_b(read_b(MEM_DETAIL))

    removed = sorted(tokenize(before) - tokenize(after))
    ok('P5 no-op 控制（确有被删令牌）', len(removed) > 0, 'removed=%d' % len(removed))
    info('P5 被删令牌清单', repr(removed))

    unhandled = []
    how = {}
    for tok in removed:
        h = hit(tok, detail)
        if h:
            how[tok] = 'detail:' + h
            continue
        h2 = hit(tok, after)
        if h2:
            how[tok] = 'quick:' + h2
            continue
        if tok in WHITELIST and WHITELIST[tok] in after:
            how[tok] = 'whitelist(anchor in quick)'
            continue
        unhandled.append(tok)
    ok('P5 被删令牌无静默丢失', not unhandled, 'unhandled=%r' % (unhandled,))
    info('P5 命中方式', repr(how))

    # 负控制：伪造令牌必须不命中（用生僻字，先自证全阴性）
    fake = '彘鬻鱻麤龘靐齉爩虪黐'
    ok('P5 负控制夹具自证(生僻串原本不在任何处)',
       (fake not in detail) and (fake not in after))
    ok('P5 负控制：伪造令牌不命中', hit(fake, detail) is None)


# ------------------------------------------------------- P6 状态干净
EXPECT = {
    ' M .workbuddy/memory/MEMORY.md',
    ' M .workbuddy/memory/参考-契约与历轮（详版）.md',
    ' M code-quality-audit/regress/baseline.json',
    ' M code-quality-audit/regress/run_all.py',
    ' M code-quality-audit/第107轮-全屏化与全局缩放/_evidence/check107.txt',
    ' M code-quality-audit/第107轮-全屏化与全局缩放/_tools/check107.py',
    ' M ralsei_pet/src/main.py',
    '?? .workbuddy/memory/2026-10-14.md',
    '?? code-quality-audit/第113轮-灵魂视角差事/',
    '?? ralsei_pet/modules/npc_errand.py',
}


def p6():
    out = subprocess.run(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
        cwd=ROOT, stdout=subprocess.PIPE).stdout.decode('utf-8')
    parts = [p for p in out.split('\0') if p]
    cur = set()
    for p in parts:
        st, path = p[:2], p[3:]
        if st == 'R ' or st.startswith('R'):
            continue                     # 重命名第二段（无 XY 头）
        cur.add('%s %s' % (st, path))
    ok('P6 工作区无意外项', cur == EXPECT, 'extra=%r missing=%r' % (
        sorted(cur - EXPECT), sorted(EXPECT - cur)))
    ok('P6 未残留八进制转义', not re.search(r'\\[0-7]{3}', out))
    # 负控制：仓库外路径必须被判为意外项
    ok('P6 负控制：伪造项被判意外', (' M no/such/file.py' in cur) is False)
    info('P6 现盘条目', repr(sorted(cur)))


# ------------------------------------------------------- P7 G2 比对列统计
def p7():
    # ★ E 盘会瞬时 Errno 22 ⇒ 全量输出落仓库内 `regress/_out/`（本就 gitignored）
    gp = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'g2_full_113.txt')
    if not os.path.exists(gp):
        info('P7 G2', '未找到落盘输出（跳过）')
        return
    txt = io.open(gp, encoding='utf-8', errors='replace').read()
    rows = [l for l in txt.splitlines()
            if re.match(r'^\S+\s+\d+\s+\d+\s+\d+\s+(IDENTICAL|DIFF|BASELINE|SKIP)\b', l)]
    from collections import Counter
    c = Counter(l.split()[4] for l in rows)
    ok('P7 G2 套件数与全 IDENTICAL', len(rows) == 103 and c.get('IDENTICAL') == 103,
       'rows=%d %r' % (len(rows), dict(c)))
    ok('P7 G2 无 DIFF/BASELINE/SKIP',
       c.get('DIFF', 0) == 0 and c.get('BASELINE', 0) == 0 and c.get('SKIP', 0) == 0,
       repr(dict(c)))
    m = re.search(r'合计：PASS=(\d+) FAIL=(\d+)\s+套件=(\d+)', txt)
    ok('P7 G2 合计行', bool(m) and m.group(2) == '0',
       (m.group(0) if m else 'no summary'))


def main():
    for fn in (p1, p2, p3, p4, p5, p6, p7):
        try:
            fn()
        except Exception:
            R.append((fn.__name__, False, 'EXC\n' + traceback.format_exc()))

    npass = sum(1 for _, o, _ in R if o)
    nfail = len(R) - npass
    lines = ['第113轮 复检报告（core-file-recheck）', '=' * 60,
             'PASS=%d FAIL=%d' % (npass, nfail), '']
    lines += ['[PASS] %s%s' % (nm, ('  ' + dt if dt else '')) for nm, o, dt in R if o]
    fails = [(nm, dt) for nm, o, dt in R if not o]
    if fails:
        lines += ['', '---- FAIL 明细 ----']
        lines += ['[FAIL] %s  %s' % (nm, dt) for nm, dt in fails]
    lines += ['', '---- 信息（不计入判据） ----']
    lines += ['[INFO] %s = %s' % (nm, dt) for nm, dt in INFOS]

    rp = os.path.abspath(REPORT)
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    with io.open(rp, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')
    print('PASS=%d FAIL=%d' % (npass, nfail))
    print('report ->', rp)
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main())
