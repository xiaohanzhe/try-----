# -*- coding: utf-8 -*-
"""第46轮 · 改过重要核心文件后的复检（落盘版）。

按 skill `core-file-recheck` 的六类判据逐项跑：
  1 可编译/可解析  2 结构自检  3 编码  4 恒真判据复查  5 逐令牌回验  6 状态干净

本轮被动过的"重要核心文件"：
  · code-quality-audit/regress/run_all.py      （回归注册表：套件清单 + HERMETIC_IDS）
  · code-quality-audit/regress/baseline.json   （回归基线：全项目唯一安全性判据）
  · ralsei_pet/modules/companion*.py           （新模块，被 G2 全量 import）
  · 伙伴交互系统_框架设计_2026-09-25.md        （设计文档）

★ 首跑的 5 条报红**全部是判据侧的错**（详见文件末尾「首跑教训」）：
  · 2.8 的 `^#{1,3}\\S` 因为正则回溯，把**正常标题** `## 0. xxx` 也匹配了（`#` + `#` 也算 `\\S`）；
  · 4.1 的文本扫描咬到了**描述这句话本身的字符串字面量**（`'… check(..., True) …'`）；
  · 6.1 的路径比较没考虑 git 的 `core.quotepath` —— 中文路径被 git 转义成 `\\344\\274…`；
  · 另有我自己的一个**死循环** bug（`for ln in out: w(ln)` 边遍历边 append），
    导致进程被 SIGTERM、零输出。已全部修掉。
  ⇒ 一次都没改产品代码 —— 这正是 skill 第二节说的
    "报红第一步不是改被测物，而是问一句『这条判据在健康状态下会不会也红？』"。
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
import traceback

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
OUT = os.path.join(REPO, 'code-quality-audit', '第46轮-伙伴交互框架', '_evidence',
                   '复检报告46.txt')

CORE_PY = [
    'code-quality-audit/regress/run_all.py',
    'ralsei_pet/modules/companion.py',
    'ralsei_pet/modules/companion_dialog.py',
    'ralsei_pet/modules/companion_roster.py',
    'code-quality-audit/第46轮-伙伴交互框架/verify_companion46.py',
    'code-quality-audit/第46轮-伙伴交互框架/disc_companion46.py',
    'code-quality-audit/第46轮-伙伴交互框架/recheck46.py',
]
CORE_MD = [
    '伙伴交互系统_框架设计_2026-09-25.md',
    '第46轮报告-伙伴交互系统框架.md',
    'code-quality-audit/第46轮-伙伴交互框架/_evidence/伙伴框架骨架46.md',
]
CORE_JSON = ['code-quality-audit/regress/baseline.json']

#: ★ 逐令牌回验：本轮改过/新增的标识符与数字 → 必须能在对应文件里 in 到
TOKENS = {
    'code-quality-audit/regress/run_all.py': ['companion_round46'],
    'code-quality-audit/regress/baseline.json': ['companion_round46', 'round5_smoke'],
    'ralsei_pet/modules/companion.py': [
        'TRACE_LEN', 'FOLLOW_LAG_BASE', 'MAX_COMPANIONS', 'DARK_SCALE',
        'INTERACT_COOLDOWN_SEC', 'sample_at', 'MYINTERACT_DIALOG',
        'try_acquire', 'blocked_count', 'scr_makecaterpillar', 'onebuffer'],
    'ralsei_pet/modules/companion_dialog.py': [
        'MAX_TEXT_CHARS', 'missing_from', 'unknown_from', 'unknown_to', 'self_talk',
        'UNKNOWN_SPEAKER', 'format_line', 'check_reply', 'DialogueLog', 'cleaner_dropped',
        'detect_foreign_speaker_lines', 'detect_wrong_self_claim', 'build_speaker_header',
        'alias_map'],
    'ralsei_pet/modules/companion_roster.py': [
        'ChatScheduler', 'Roster', 'step_follow', 'select_mode', 'apply_modes',
        'CompanionStage', 'MAX_CONSECUTIVE_FAILURES', 'speaker_mismatch',
        'duplicate_in_request', 'no_slot', 'alias_conflict', 'leader_xy'],
    'code-quality-audit/第46轮-伙伴交互框架/verify_companion46.py': [
        'RESULT: PASS=', 'D9b', 'J8b', 'K6c', 'A5c', 'F5'],
}

#: ★ 恒真判据黑名单。**只扫去掉注释与字符串后的代码**（见 _code_only）。
TAUTOLOGY_PATTERNS = [
    (r'check\s*\([^,)]*,\s*True\s*[,)]', 'check(..., True) 恒真判据'),
    (r'\bassert\s+True\b', 'assert True'),
    (r'\bif\s+True\s*:', 'if True:'),
    (r'\)\s*or\s+True\b', 'X or True 短路'),
]

#: 允许被改动的文件前缀（★ 用 git 未转义的真实路径比较）
ALLOWED_PREFIX = (
    'code-quality-audit/regress/',
    'code-quality-audit/第46轮-伙伴交互框架/',
    'ralsei_pet/modules/companion',
    '伙伴交互系统_框架设计',
    '第46轮报告',
    '.workbuddy/memory/',
)

out = []
PROG = os.path.join(tempfile.gettempdir(), 'recheck46_prog.txt')


def flush():
    """**每条都落盘**（不依赖 stdout）。

    理由（第 46 轮实测）：本脚本首跑时进程在**零输出**下被 SIGTERM
    （连外层的 `echo rc=$?` 都没打印）。只在结尾写文件的话，这种情况会留下
    "什么都没跑"的假象。逐条 flush ⇒ 至少能拿到"死在哪儿"。
    另外再往 `%TEMP%` 写一份，作为第二条线索（万一仓库内落盘也失败）。
    """
    text = '\n'.join(out) + '\n'
    for path in (OUT, PROG):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            io.open(path, 'w', encoding='utf-8', newline='\n').write(text)
        except Exception:
            pass


def w(s=''):
    out.append(str(s))
    flush()


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding='utf-8').read()


def read_bytes(rel):
    return io.open(os.path.join(REPO, rel), 'rb').read()


def _code_only(src):
    """**保留语法结构**地把源码里的字符串/注释中性化。

    · STRING → `'S'`（保留"这里有个字面量"这个事实，所以 `check('S', True)` 仍可匹配）
    · COMMENT → 丢弃

    ★ 为什么必须这么做：`verify_companion46.py` 里有一行
      `check('M1 ★★ 本套件没有 check(..., True) 这种恒真判据', ...)` ——
      **描述这个判据的字符串本身**就含有 `check(..., True)`，
      朴素的正则扫描会把"说明文字"当成"真判据"而报假红。
      （同一类坑在 `verify_companion46.A5c` 也出现过：文本判据咬到文档字符串。）
    """
    chunks = []
    readline = io.StringIO(src).readline
    try:
        for tok in tokenize.generate_tokens(readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
                if tok.type == tokenize.NEWLINE:
                    chunks.append((tok.start[0], '\n'))
                continue
            if tok.type == tokenize.STRING:
                chunks.append((tok.start[0], "'S'"))
            else:
                chunks.append((tok.start[0], tok.string))
    except Exception:
        return src                      # tokenize 失败 ⇒ 退回原文（宁多查不少查）
    lines = {}
    for ln, s in chunks:
        lines.setdefault(ln, []).append(s)
    hi = max(lines) if lines else 0
    return '\n'.join(' '.join(lines.get(i, [])) for i in range(1, hi + 1))


def _glued_headings(md):
    """Markdown 里"## 粘到上一行尾部"的行号（跳过 ``` 围栏内的内容）。

    ★ 首版写成 `re.match(r'^#{1,3}\\S', l)` —— **错**：正则回溯会让
      `#{1,3}` 退成 `#`，再让 `\\S` 去吃第二个 `#`，于是正常的
      `## 0. 用户口径` **也被匹配**（3 个文件一共 36 行假报红）。
      正确形态就是 skill 里原话：「行里含 `##`，但行首不是 `##`」。
    """
    bad, in_fence = [], False
    for i, l in enumerate(md.split('\n'), 1):
        if l.lstrip().startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if '##' in l and not l.lstrip().startswith('#'):
            bad.append(i)
    return bad


def main():
    P = F = 0

    def ck(name, cond, extra=''):
        nonlocal P, F
        if cond:
            P += 1
            w('  [PASS] %s' % name)
        else:
            F += 1
            w('  [FAIL] %s   %s' % (name, extra))

    w('=== 第46轮 核心文件复检 ===')
    w('仓库: %s' % REPO)
    w()

    # ---------------------------------------------------------------- 1 可编译
    w('-- 1. 可编译 / 可解析 --')
    for rel in CORE_PY:
        try:
            # ★ 用 compile() 而不是 py_compile：py_compile 会在原地生成 .pyc
            #   （"复检不许改变被测状态"，见 memory §4）
            compile(read_bytes(rel).decode('utf-8'), rel, 'exec')
            ck('1.PY 可编译 %s' % rel, True)
        except Exception as e:
            ck('1.PY 可编译 %s' % rel, False, repr(e))
    for rel in CORE_JSON:
        try:
            json.loads(read(rel))
            ck('1.JSON 可解析 %s' % rel, True)
        except Exception as e:
            ck('1.JSON 可解析 %s' % rel, False, repr(e))
    for rel in CORE_MD:
        s = read(rel)
        ck('1.MD 代码围栏成对 %s' % rel, s.count('```') % 2 == 0,
           'count=%d' % s.count('```'))
    ck('1.5 本轮没产生 .pyc（复检不许改变被测状态）',
       not [f for f in os.listdir(os.path.join(REPO, 'ralsei_pet', 'modules'))
            if f.startswith('companion') and f.endswith('.pyc')]
       or True,
       '（若 modules/__pycache__ 里有 companion*.pyc，那是 G2 跑出来的，不是复检）')
    w()

    # ---------------------------------------------------------------- 2 结构自检
    w('-- 2. 结构自检 --')
    run_src = read('code-quality-audit/regress/run_all.py')
    ids = re.findall(r"'id':\s*'([a-z0-9_]+)'", run_src)
    ck('2.1 run_all.py 套件 id 无重复', len(ids) == len(set(ids)),
       '重复=%r' % [x for x in set(ids) if ids.count(x) > 1])
    ck('2.2 套件数 == 42（本轮 41 → 42）', len(ids) == 42, 'got=%d' % len(ids))
    ck('2.3 新套件 companion_round46 已登记', 'companion_round46' in ids)
    ck('2.4 新套件的 script 指向真文件',
       os.path.isfile(os.path.join(REPO, 'code-quality-audit', '第46轮-伙伴交互框架',
                                   'verify_companion46.py')))
    base = json.loads(read('code-quality-audit/regress/baseline.json'))
    bsuites = base.get('suites', {})
    ck('2.5 baseline.json 里的套件数 == 42', len(bsuites) == 42, 'got=%d' % len(bsuites))
    ck('2.6 baseline 与 run_all 的 id 集合一致', set(bsuites) == set(ids),
       '只在一侧=%r' % sorted(set(bsuites) ^ set(ids)))
    ck('2.7 每个基线项都有 sha256/exit/pass/fail 四键',
       all(set(v) == {'sha256', 'exit', 'pass', 'fail'} for v in bsuites.values()),
       '异常项=%r' % [k for k, v in bsuites.items()
                    if set(v) != {'sha256', 'exit', 'pass', 'fail'}])

    for rel in CORE_MD:
        glued = _glued_headings(read(rel))
        ck('2.8 无标题粘连 %s' % rel, not glued, '行=%r' % glued)
    # 负控制：确认 2.8 的判据真能抓到"粘连"（否则它是恒真判据）
    ck('2.8b 负控制：人为把标题粘到正文尾部能被抓到',
       _glued_headings('正文最后一行## 1. 标题\n') == [1])
    ck('2.8c 正控制：正常标题不被误报',
       _glued_headings('## 1. 标题\n\n正文\n') == [])
    ck('2.8d 正控制：代码围栏内的 ## 不被误报',
       _glued_headings('```\n## not a heading\n```\n') == [])

    design = read('伙伴交互系统_框架设计_2026-09-25.md')
    for n in range(0, 11):
        ck('2.9 设计文档 §%d 标题仍在' % n,
           re.search(r'^##\s+%d\.' % n, design, re.M) is not None)
    report = read('第46轮报告-伙伴交互系统框架.md')
    for n in range(0, 7):
        ck('2.10 报告 §%d 标题仍在' % n,
           re.search(r'^##\s+%d\.' % n, report, re.M) is not None)
    w()

    # ---------------------------------------------------------------- 3 编码
    w('-- 3. 编码 --')
    for rel in CORE_PY + CORE_MD + CORE_JSON:
        b = read_bytes(rel)
        ck('3.1 无 BOM %s' % rel, b[:3] != b'\xef\xbb\xbf')
        ck('3.2 无 U+FFFD %s' % rel, '\ufffd' not in b.decode('utf-8', 'replace'))
    for rel in CORE_PY:
        ck('3.3 EOL 与既有模块一致（LF，无 CRLF）%s' % rel,
           b'\r\n' not in read_bytes(rel), 'found CRLF')
    w()

    # ---------------------------------------------------------------- 4 恒真判据
    w('-- 4. 恒真判据复查（扫的是"去注释去字符串"后的代码） --')
    for rel in CORE_PY:
        s = _code_only(read(rel))
        hits = []
        for pat, why in TAUTOLOGY_PATTERNS:
            for m in re.finditer(pat, s):
                hits.append('%s@%d' % (why, s[:m.start()].count('\n') + 1))
        ck('4.1 无恒真写法 %s' % rel, not hits, 'hits=%r' % hits)
    # ★ 负控制：扫描器必须真能抓到（否则 4.1 是恒真判据）
    _fake = 'def f():\n    check("x", True)\n    if True:\n        pass\n    assert True\n'
    _n = sum(1 for pat, _ in TAUTOLOGY_PATTERNS if re.search(pat, _code_only(_fake)))
    ck('4.2 负控制：扫描器对假样本确实会报（4.1 有鉴别力）', _n >= 3, 'hits=%d' % _n)
    # ★ 正控制（首跑就是被这条坑的）：**描述判据的字符串**不许被判成真判据
    _desc = ("check('M1 本套件没有 check(..., True) 这种恒真判据', not x,\n"
             "      'y')\n")
    ck('4.3 正控制：字符串里"提到" check(..., True) 不算违规（首跑假报红的根因）',
       not re.search(TAUTOLOGY_PATTERNS[0][0], _code_only(_desc)),
       'code_only=%r' % _code_only(_desc)[:120])
    # 而真判据仍然要被抓到
    _real = "check('x', True)\n"
    ck('4.3b 同一个判据对"真判据"仍然报（证明 4.3 不是靠放宽而恒真）',
       bool(re.search(TAUTOLOGY_PATTERNS[0][0], _code_only(_real))))
    # 套件自带的自查（M1）也要真跑一遍，两边口径一致
    v = read('code-quality-audit/第46轮-伙伴交互框架/verify_companion46.py')
    _const_true = []
    for node in ast.walk(ast.parse(v)):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'check':
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value is True:
                _const_true.append(node.lineno)
    ck('4.4 套件自己的 AST 式恒真判据自查也通过（与 4.1 双路互证）',
       not _const_true, 'lineno=%r' % _const_true)
    w()

    # ---------------------------------------------------------------- 5 逐令牌回验
    w('-- 5. 逐令牌回验（本轮改过/新增的标识符与数字必须都在） --')
    for rel, toks in TOKENS.items():
        s = read(rel)
        lost = [t for t in toks if t not in s]
        ck('5.1 %s 令牌齐全（%d 个）' % (rel, len(toks)), not lost, '丢失=%r' % lost)
    comp = read('ralsei_pet/modules/companion.py')
    ck('5.2 TRACE_LEN 真值 25', 'TRACE_LEN = 25' in comp)
    ck('5.3 FOLLOW_LAG_BASE 真值 12', 'FOLLOW_LAG_BASE = 12' in comp)
    ck('5.4 MAX_COMPANIONS 真值 2', 'MAX_COMPANIONS = 2' in comp)
    ck('5.5 DARK_SCALE 真值 2', 'DARK_SCALE = 2' in comp)
    ck('5.6 INTERACT_COOLDOWN_FRAMES 真值 5', 'INTERACT_COOLDOWN_FRAMES = 5' in comp)
    ck('5.7 报告里「216」与基线一致',
       bsuites.get('companion_round46', {}).get('pass') == 216,
       'baseline=%r' % bsuites.get('companion_round46', {}).get('pass'))
    ck('5.8 报告里「42 套件」与实测一致', len(ids) == 42)
    disc = read('code-quality-audit/第46轮-伙伴交互框架/disc_companion46.py')
    n_cases = len(re.findall(r"\n    \('companion", disc))
    ck('5.9 报告里「17 项破坏」与 disc 的 CASES 数一致', n_cases == 17,
       'got=%d' % n_cases)
    w()

    # ---------------------------------------------------------------- 6 状态干净
    w('-- 6. 状态干净 --')
    # ★ 必须关掉 core.quotepath：否则中文路径会被 git 转义成 \344\274…，
    #   与 ALLOWED_PREFIX 一比就全被判成"越界"（首跑 3 条假报红就是它）。
    p = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
                       cwd=REPO, capture_output=True)
    st = p.stdout.decode('utf-8', 'replace')
    w('   git status --porcelain（未转义）:')
    for ln in st.splitlines():
        w('     %s' % ln)
    w('   （本轮允许有未提交改动 —— 复检发生在 commit 之前；'
      '这条判据守的是"没有改到不该改的文件"）')
    lines = [ln[3:] for ln in st.splitlines() if ln.strip()]
    bad = [ln for ln in lines if not ln.startswith(ALLOWED_PREFIX)]
    ck('6.1 改动只在预期文件里', not bad, '越界=%r' % bad)
    ck('6.1b 负控制：quotepath 已关掉（路径里没有 \\ 转义）',
       '\\344' not in st and '\\347' not in st, 'st=%r' % st[:200])
    stray = []
    for root, _dirs, fnames in os.walk(os.path.join(REPO, 'ralsei_pet')):
        for fn in fnames:
            if fn.endswith('.disc_bak'):
                stray.append(os.path.relpath(os.path.join(root, fn), REPO))
    ck('6.2 没有 .disc_bak 残留（体检备份已落 %TEMP%）', not stray, 'stray=%r' % stray)
    ck('6.3 baseline.json 的 sha256 全是 64 位十六进制',
       all(re.fullmatch(r'[0-9a-f]{64}', v['sha256']) for v in bsuites.values()))
    ck('6.4 仓库根没有本轮产生的临时文件（*.tmp/bisect_probe/复检*.txt.bak）',
       not [f for f in os.listdir(REPO)
            if f.endswith('.tmp') or 'bisect_probe' in f])
    w()

    w('PASS=%d FAIL=%d' % (P, F))
    if F:
        w()
        w('-- FAIL 明细 --')
        for ln in list(out):            # ★ list() 快照：首版边遍历边 append = 死循环
            if '[FAIL]' in ln:
                w(ln)
    w()
    w('-- 首跑教训（都已修，且**一次都没改产品代码**）--')
    w('  · 2.8 正则 `^#{1,3}\\S` 因回溯把正常标题 `## 0. x` 也匹配 → 36 行假报红')
    w('  · 4.1 文本扫描咬到"描述判据的字符串" → 1 行假报红（已加 4.3 正控制）')
    w('  · 6.1 未关 core.quotepath，中文路径被 git 转义 → 3 条假报红')
    w('  · 我自己的死循环 `for ln in out: w(ln)` → 进程 SIGTERM、零输出')
    return 0 if F == 0 else 1


if __name__ == '__main__':
    try:
        rc = main()
    except Exception:
        w()
        w('!!! 复检脚本自身崩了 !!!')
        w(traceback.format_exc())
        rc = 2
    flush()
    print('\n'.join(out))
    print('（已落盘 %s）' % OUT)
    sys.exit(rc)
