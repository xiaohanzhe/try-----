# -*- coding: utf-8 -*-
"""第142轮 · 核心文件复检（改过 `common113.py` / `check141.py` 必做）。

六项逐条打 PASS/FAIL 并落盘：
  H1 改了哪些文件（sha1 + 字节 + 行数 + EOL）
  H2 语法（`ast.parse`，**不用 `py_compile`** —— 那会产 `.pyc` 改变被测状态）
  H3 编码：无 BOM / 无 U+FFFD
  H4 恒真判据复查（`check(desc, True)` 这种"看着在守其实没守"的写法）
  H5 **逐令牌回验**：注释与报告里引用的每个数字，回证据文件核一次
  H6 工作区白名单（临时/备份/缓存没混进来）
  H7 写盘目标只有 `OUT`

★ 本轮特别加一条 H4c：本轮抓到的那个坑 —— **"防计数的判据自己把计数顶高"**。
  判据描述里一旦出现那个标记，`run_all.count_results` 就多算一次，
  套件自报 N、汇总报 N+1。这不是恒真，是"判据影响被测环境"，同族。
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
OUT = os.path.join(EV, 'recheck142.json')

TARGETS = [
    os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                 '_tools', 'common113.py'),
    os.path.join(ROOT, 'code-quality-audit', '第141轮-单句长度测量',
                 '_tools', 'check141.py'),
    os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    os.path.join(HERE, 'check142.py'),
    os.path.join(HERE, 'mutate142.py'),
]

#: 本轮的"检查脚本"：逐个确认它们自己不打印那个计数标记
SCRIPTS_NO_MARK = [
    os.path.join(HERE, 'check142.py'),
    os.path.join(ROOT, 'code-quality-audit', '第141轮-单句长度测量',
                 '_tools', 'check141.py'),
]

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


def _raw(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_raw(p))


def main():
    print(u'=' * 78)
    print(u'H1 · 改动面')
    info = {}
    for p in TARGETS:
        if not os.path.isfile(p):
            check(u'H1 文件存在：%s' % os.path.basename(p), False)
            continue
        t = _raw(p)
        crlf = t.count(u'\r\n')
        lf = t.count(u'\n') - crlf
        info[os.path.basename(p)] = {
            'sha1': hashlib.sha1(t.encode('utf-8')).hexdigest(),
            'bytes': len(t.encode('utf-8')), 'lines': t.count(u'\n'),
            'crlf': crlf, 'bare_lf': lf,
        }
        check(u'H1 %s 在盘上且非空' % os.path.basename(p),
              os.path.isfile(p) and os.path.getsize(p) > 0,
              u'%d 行 · CRLF %d · 裸 LF %d' % (t.count(u'\n'), crlf, lf))

    print(u'')
    print(u'=' * 78)
    print(u'H2 · 语法')
    for p in TARGETS:
        try:
            ast.parse(_raw(p))
            ok, err = True, ''
        except SyntaxError as e:
            ok, err = False, u'%s: %s' % (e.lineno, e.msg)
        check(u'H2 %s 可解析' % os.path.basename(p), ok, err)

    print(u'')
    print(u'=' * 78)
    print(u'H3 · 编码')
    for p in TARGETS:
        t = _raw(p)
        check(u'H3 %s 无 BOM' % os.path.basename(p), not t.startswith(u'\ufeff'))
        check(u'H3 %s 无 U+FFFD' % os.path.basename(p), u'\ufffd' not in t)

    print(u'')
    print(u'=' * 78)
    print(u'H4 · 恒真判据复查')
    for p in (os.path.join(HERE, 'check142.py'),
              os.path.join(HERE, 'mutate142.py'),
              os.path.join(ROOT, 'code-quality-audit', '第141轮-单句长度测量',
                           '_tools', 'check141.py')):
        bad, onpurpose, total = [], [], 0
        for nd in ast.walk(ast.parse(_raw(p))):
            if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
                    and nd.func.id == 'check':
                total += 1
                if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant) \
                        and isinstance(nd.args[1].value, bool):
                    (bad if nd.args[1].value is True else onpurpose).append(nd.lineno)
        check(u'H4 %s 里没有 `check(desc, True)` 字面量恒真（共 %d 处 check）'
              % (os.path.basename(p), total), not bad,
              u'恒真=%d 处 · 故意报红=%d 处' % (len(bad), len(onpurpose)))

    # H4b：产品侧函数不许有无条件 return True（只看函数体第一层）
    es = _raw(os.path.join(PET, 'modules', 'event_speech.py')).replace(u'\r\n', u'\n')
    fn = None
    for nd in ast.parse(es).body:
        if isinstance(nd, ast.FunctionDef) and nd.name == 'looks_out_of_character':
            fn = nd
    direct = []
    if fn is not None:
        for stmt in fn.body:
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) \
                    and stmt.value.value is True:
                direct.append(stmt.lineno)
    check(u'H4b `looks_out_of_character` 函数体第一层没有无条件 `return True`',
          not direct, u'%d 处' % len(direct))

    # H4c：本轮的新坑 —— 检查脚本自己不许把计数标记打印出来
    for p in SCRIPTS_NO_MARK:
        src = _raw(p)
        # 只在**判据描述**里找（`check(` 的第一个实参范围内），不扫整个文件
        hit = 0
        for nd in ast.walk(ast.parse(src)):
            if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
                    and nd.func.id == 'check' and nd.args:
                for sub in ast.walk(nd.args[0]):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                            and ('[' + 'PASS]') in sub.value:
                        hit += 1
        # 再验"运行时的输出里这个标记只出现 N 次"（N = 判据条数）
        r = subprocess.run([sys.executable, p], capture_output=True)
        out = r.stdout.decode('utf-8', 'replace')
        n_mark = out.count('[' + 'PASS]')
        n_pass = len(re.findall(u'^PASS=(\\d+)', out, re.M))
        want = int(re.findall(u'^PASS=(\\d+)', out, re.M)[0]) if n_pass else -1
        check(u'H4c %s 的输出里计数标记正好 %d 次（描述里 %d 处）'
              % (os.path.basename(p), n_mark, hit),
              hit == 0 and n_mark == want, u'want=%d got=%d' % (want, n_mark))

    print(u'')
    print(u'=' * 78)
    print(u'H5 · 逐令牌回验（注释里的数字 ← 证据文件）')
    ev = _json(os.path.join(EV, 'lead142b.json'))
    a1 = _json(os.path.join(EV, 'lead142.json'))
    rows = ev.get('rows') or []
    have = [r for r in rows if r['lead'] and not r.get('norec')]
    lack = [r for r in rows if (not r['lead']) and not r.get('norec')]
    tokens = [
        (u'76', a1.get('persona_spec_n') == 76, u'人设份数'),
        (u'38', len(have) == 38 and ev.get('have_lead') == 38, u'带 ① 的人数'),
        (u'39', len(lack) == 39, u'有语料且不带 ① 的人数'),
        (u'247', (ev.get('agg_have') or {}).get('tot200') == 247, u'带①组超长条数'),
        (u'89', (ev.get('agg_lack') or {}).get('tot200') == 89, u'对照组超长条数'),
        (u'465', (ev.get('agg_have') or {}).get('max') == 465, u'带①组最长'),
        (u'211', any(r['id'] == 'ralsei' and r['max'] == 211 for r in rows),
         u'ralsei 最长'),
        (u'8', len(ev.get('lack_but_over200') or []) == 8, u'有超长但无 ① 的人数'),
        (u'0 人', len(ev.get('have_but_clean') or []) == 0, u'无违规却有 ①'),
    ]
    miss = [u'%s(%s)' % (t, w) for t, ok, w in tokens if not ok]
    check(u'H5 证据里的 9 个数字逐个回核一致', not miss, u'不符=%r' % (miss,))

    src_common = _raw(TARGETS[0])
    need = [u'第142轮订正', u'不许批量删', u'100%', u'20.5%', u'0 人',
            u'465', u'第 7 位', u'前 3 条']
    lack_tok = [q for q in need if q not in src_common]
    check(u'H5b `common113.py` 的订正注释里确实写了这些数（不是只在我嘴里）',
          not lack_tok, u'缺=%r' % (lack_tok,))

    print(u'')
    print(u'=' * 78)
    print(u'H6 · 工作区')
    r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status',
                        '--porcelain'], cwd=ROOT, capture_output=True)
    st = r.stdout.decode('utf-8', 'replace').strip()
    lines = [l for l in st.splitlines() if l.strip()]
    for l in lines[:20]:
        print(u'    %s' % l)
    ALLOW = (
        u'code-quality-audit/第113轮-全体角色AI训练/_tools/common113.py',
        u'code-quality-audit/第141轮-单句长度测量/_tools/check141.py',
        u'code-quality-audit/regress/run_all.py',
        u'code-quality-audit/regress/baseline.json',
        u'code-quality-audit/第142轮-NPC补丁去重/',
        u'.workbuddy/memory/',
        # 已登记遗留（第138轮）：`check138` 每次运行都重写自己的证据文件
        u'code-quality-audit/第138轮-判据输出去时相/_evidence/phase138.json',
    )
    paths = [l[2:].lstrip() for l in lines]
    broken = [p for p in paths if not p or u' ' in p[:2]]
    check(u'H6a 状态行解析自证（每条都取到了像路径的东西）', not broken,
          u'解析异常=%r' % (broken,))
    outside = [p for p in paths if not any(p.startswith(a) for a in ALLOW)]
    check(u'H6 改动面全在白名单内（临时/备份/缓存没混进工作区）', not outside,
          u'越界=%r' % (outside,))
    unexpected = [p for p in paths if u'__pycache__' in p or p.endswith(u'.pyc')]
    check(u'H6b 没有把 `__pycache__` / `.pyc` 混进来', not unexpected,
          u'%r' % (unexpected,))

    print(u'')
    print(u'=' * 78)
    print(u'H7 · 写盘目标')
    writes, targets_ = [], []
    for nd in ast.walk(ast.parse(_raw(os.path.abspath(__file__)))):
        if isinstance(nd, ast.Call):
            fn2 = nd.func
            is_open = ((isinstance(fn2, ast.Name) and fn2.id == 'open')
                       or (isinstance(fn2, ast.Attribute) and fn2.attr == 'open'))
            if is_open and len(nd.args) >= 2:
                mode = nd.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                        and ('w' in mode.value or 'a' in mode.value):
                    writes.append(nd.lineno)
                    t0 = nd.args[0]
                    targets_.append(t0.id if isinstance(t0, ast.Name) else u'<expr>')
    check(u'H7 只有 1 处写盘，且目标是 `OUT`',
          writes and targets_ == [u'OUT'],
          u'写盘 %d 处 · 目标=%r' % (len(writes), targets_))

    print(u'')
    print(u'=' * 78)
    out = {'targets': info, 'pass': _n['p'], 'fail': _n['f'], 'failed': _failed}
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    print(u'已落盘：', OUT)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
