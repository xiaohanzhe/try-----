# -*- coding: utf-8 -*-
"""第141轮 · 核心文件复检（改过 `event_speech.py` 必做）。

六项逐条打 PASS/FAIL 并落盘：
  H1 改了哪些文件（sha1 + 字节 + 行数 + EOL），改动面必须是最小的
  H2 语法/可编译（`ast.parse`，**不用 `py_compile`** —— 那会产 `.pyc` 改变被测状态）
  H3 编码：无 BOM / 无 U+FFFD / EOL 与改前一致
  H4 **恒真判据复查**：`check(desc, True)` 这种"看着在守其实没守"的写法
  H5 **逐令牌回验**：注释里引用的每个数字，回证据文件 `in` 一次
  H6 工作区干净（`git status --porcelain` 为空）
  H7 本脚本只许写一个目标（`_evidence/recheck141.json`）

★ 判据自己也会说谎：H4 只认**字面量** `True`/`False` 作第二实参 —— 写成
  `bool(1)` 或 `x or True` 是为了躲过扫描，这种要人看，脚本不假装能抓。
"""
import ast
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'recheck141.json')

TARGETS = [
    os.path.join(PET, 'modules', 'event_speech.py'),
    os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    os.path.join(HERE, 'check141.py'),
    os.path.join(HERE, 'mutate141.py'),
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


def _lf(p):
    return _raw(p).replace(u'\r\n', u'\n')


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
              u'%d 行 / %d 字节 / CRLF %d · 裸 LF %d'
              % (t.count(u'\n'), len(t.encode('utf-8')), crlf, lf))

    eol_ok = info.get('event_speech.py', {}).get('bare_lf') == 0
    check(u'H1b event_speech.py 是单一 EOL（裸 LF 为 0，没被工具混写）', eol_ok,
          u'bare_lf=%r' % info.get('event_speech.py', {}).get('bare_lf'))

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
        check(u'H3 %s 无 U+FFFD（没被编码事故嚼过）' % os.path.basename(p),
              u'\ufffd' not in t)

    print(u'')
    print(u'=' * 78)
    print(u'H4 · 恒真判据复查')
    for name in ('check141.py', 'mutate141.py', 'recheck141_core.py'):
        p = os.path.join(HERE, name)
        bad = []
        false_on_purpose = []
        total = 0
        for nd in ast.walk(ast.parse(_raw(p))):
            if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
                    and nd.func.id == 'check':
                total += 1
                if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant) \
                        and isinstance(nd.args[1].value, bool):
                    # ★ 只把 `True` 算恒真。`False` 是**故意的无条件报红**
                    #   （"这条不该走到这里"的锚点），是本仓自己的惯用法，不算问题。
                    if nd.args[1].value is True:
                        bad.append(nd.lineno)
                    else:
                        false_on_purpose.append(nd.lineno)
        check(u'H4 %s 里没有 `check(desc, True)` 字面量恒真（共 %d 处 check）'
              % (name, total), not bad,
              u'恒真行号=%r · 故意报红行号=%r' % (bad, false_on_purpose))

    # 产品侧的同类风险：`looks_out_of_character` 不许直接 `return True`
    es = _lf(TARGETS[0])
    tree_es = ast.parse(es)
    fn = None
    for nd in tree_es.body:
        if isinstance(nd, ast.FunctionDef) and nd.name == 'looks_out_of_character':
            fn = nd
    direct_true = []
    if fn is not None:
        # ★ 只看**函数体第一层**的 return。`for p in _OOC_PATTERNS: if ...: return True`
        #   是正常的"命中即返回"，用 `ast.walk` 会把它们全算进来（第一版就是这么误报的）。
        for stmt in fn.body:
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) \
                    and stmt.value.value is True:
                direct_true.append(stmt.lineno)
    check(u'H4b `looks_out_of_character` 函数体第一层没有无条件 `return True`',
          not direct_true, u'行号=%r' % (direct_true,))

    print(u'')
    print(u'=' * 78)
    print(u'H5 · 逐令牌回验（注释里的数字 ← 证据文件）')
    LANG = _json(os.path.join(EV, 'sentence_len141b_lang.json'))
    ELLI = _json(os.path.join(EV, 'ellipsis141.json'))
    REAL = _json(os.path.join(EV, 'real_long141.json'))
    DLTA = _json(os.path.join(EV, 'ooc_delta141.json'))

    tokens = [
        (u'5592', LANG['corpus']['total'] == 5592, u'语料条数'),
        (u'77', LANG['corpus']['npcs'] == 77, u'角色数'),
        (u'71', (LANG['A_no_ascii_dot']['zh']['max_sent']['p90']) == 71, u'zh 层 P90'),
        (u'323', (LANG['A_no_ascii_dot']['en']['max_sent']['p90']) == 323, u'en 层 P90'),
        (u'143', (LANG['B_with_ascii_dot']['en']['max_sent']['p90']) == 143, u'en 补点后 P90'),
        (u'5672', ELLI['all']['marks'] == 5672, u'省略号记号总数'),
        (u'97.4', ELLI['all']['connector']['rate_pct'] == 97.4, u'当连接符比例'),
        (u'5.57', ELLI['npc_density_top10'][0]['per100'] == 5.57, u'napstablook 密度'),
        (u'181', REAL['thresholds']['80']['no_ellipsis_chain'] == 181, u'真长句条数'),
        (u'268', REAL['thresholds']['80']['all'] == 268, u'80 字命中'),
        (u'1074', REAL['thresholds']['60']['all'] == 1074, u'60 字命中'),
        (u'4974', REAL['zh_replies'] == 4974, u'zh 层分母'),
        (u'96', DLTA['base_hits'] == 96, u'现有闸原有命中'),
        (u'7', DLTA['union_new'] == 7, u'四条正则并集净增'),
        (u'4', (DLTA['cand']['setting_play']['new']) == 4, u'`设定…扮演` 净增'),
        (u'1', DLTA['ralsei_new'] == 1, u'ralsei 本人净增'),
    ]
    miss = []
    for tok, ok, what in tokens:
        if not ok:
            miss.append(u'%s(%s)' % (tok, what))
    check(u'H5 证据里的 16 个数字逐个回核一致', not miss, u'不符=%r' % (miss,))

    # 这些数字必须**真的出现在源码注释里**（否则就是我引用了没写下来的数）
    es_txt = _raw(TARGETS[0])
    quoted = [u'5592', u'77', u'96', u'1.7%', u'1.8%', u'4 \u6761',
              u'\u2026']
    lack = [q for q in quoted if q not in es_txt]
    check(u'H5b 源码注释里确实写了这些数字（不是只在我嘴里）', not lack,
          u'缺=%r' % (lack,))

    # 正则本体逐字节回验（不是"看起来还在"）
    check(u'H5c 正则本体 `设定.{0,4}扮演` 逐字在盘',
          u"re.compile(u'\u8bbe\u5b9a.{0,4}\u626e\u6f14')" in es_txt)
    check(u'H5d 被否决的裸词没有被塞进子串表',
          not any(u"'%s'," % w in es_txt for w in (u'\u626e\u6f14', u'\u89d2\u8272\u626e\u6f14')))

    print(u'')
    print(u'=' * 78)
    print(u'H6 · 工作区')
    r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status',
                        '--porcelain'], cwd=ROOT, capture_output=True)
    st = r.stdout.decode('utf-8', 'replace').strip()
    lines = [l for l in st.splitlines() if l.strip()]
    for l in lines[:20]:
        print(u'    %s' % l)

    # ★ 白名单：改动只许落在"本轮该改的地方"。这是第109轮"临时/备份文件被
    #   `git add -A` 记成删除并提交"的守卫 —— 判"路径前缀"，不判"改动内容"。
    ALLOW = (
        u'ralsei_pet/modules/event_speech.py',
        u'code-quality-audit/regress/run_all.py',
        # `--update` 的必然产物：新套件入列后基线重建
        u'code-quality-audit/regress/baseline.json',
        u'code-quality-audit/第141轮-单句长度测量/',
        u'.workbuddy/memory/',
        # ⚠️ 遗留（第138轮，不是本轮引入）：`check138` 每次运行都会重写自己的证据文件，
        #   把 `files_scanned` / `calls_scanned` 刷成当前值（139→140 / 6198→6228，正好 +30）。
        #   ⇒ 只要新增一个套件，这个文件就永久变脏。本轮如实登记，未修。
        u'code-quality-audit/第138轮-判据输出去时相/_evidence/phase138.json',
    )
    # ★ 不许用 `l[3:]`：porcelain 的 `XY PATH` 在某些状态下空格数不一样
    #   （第一版就是固定切 3 位，把 `M  path` 切成了 `ode-…`，白报两条越界）。
    #   改成"跳过 2 位状态 + 吃掉所有前导空格"，并把解析结果自证一遍。
    paths = [l[2:].lstrip() for l in lines]
    broken = [p for p in paths if not p or u' ' in p[:2]]
    check(u'H6a 状态行解析自证（每条都取到了像路径的东西）', not broken,
          u'解析异常=%r' % (broken,))
    outside = [p for p in paths
               if not any(p.startswith(a) for a in ALLOW)]
    check(u'H6 改动面全在白名单内（临时/备份/缓存没混进工作区）', not outside,
          u'越界=%r' % (outside,))

    unexpected = [p for p in paths
                  if u'__pycache__' in p or p.endswith(u'.pyc')]
    check(u'H6b 没有把 `__pycache__` / `.pyc` 混进来', not unexpected,
          u'%r' % (unexpected,))

    print(u'')
    print(u'=' * 78)
    print(u'H7 · 写盘目标')
    writes = []
    targets = []
    for nd in ast.walk(ast.parse(_raw(os.path.abspath(__file__)))):
        if isinstance(nd, ast.Call):
            fn = nd.func
            is_open = ((isinstance(fn, ast.Name) and fn.id == 'open')
                       or (isinstance(fn, ast.Attribute) and fn.attr == 'open'))
            if is_open and len(nd.args) >= 2:
                mode = nd.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
                        and ('w' in mode.value or 'a' in mode.value):
                    writes.append(nd.lineno)
                    t0 = nd.args[0]
                    targets.append(t0.id if isinstance(t0, ast.Name) else u'<expr>')
    check(u'H7 只有 1 处写盘，且目标是 `OUT`（不写工作区别处、不造临时文件）',
          writes and targets == [u'OUT'], u'行号=%r 目标=%r' % (writes, targets))

    print(u'')
    print(u'=' * 78)
    ev = {'targets': info, 'pass': _n['p'], 'fail': _n['f'], 'failed': _failed}
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    print(u'已落盘：', OUT)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
