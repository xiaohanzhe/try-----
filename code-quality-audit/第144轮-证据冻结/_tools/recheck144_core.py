# -*- coding: utf-8 -*-
"""第144轮 · 核心文件复检（改过 `check138.py` —— 它是 `SUITES` 里的一个回归套件，必做）。

用户口径：「以后再调整重要核心文件时一定要记得复检」。

  H1 改动面：`check138.py` 只动了"落盘段"，**判据一条没动**（AST 对 HEAD 版核 ID 集）
  H2 语法（`ast.parse`，**不用 `py_compile`** —— 那会产 `.pyc` 改变被测状态）
  H3 编码：无 BOM / 无 U+FFFD
  H4 恒真判据复查（`check(desc, True)` / 函数体第一层 `return True` / 计数标记字面量）
     ＋ 运行时标记次数 == 自报 PASS
  H5 **逐令牌回验**：提交史表里的 6 组数、5 个增量、"读盘 0 处"，逐条回 `lead144.json`
  H6 工作区白名单（按路径列 + 每条写理由）
  H7 写盘目标（不许写死盘符；`mutate144` 的备份必须落外部盘）

★ 为什么改一个"落盘路径"也要复检：
  这一轮删掉的是**每轮都会被改的文件**。如果改法错了（比如 `_LIVE` 指错、`makedirs`
  少一层），症状是 `check138` 仍然 22 条全绿 —— 因为它只是"少写了一个文件"，
  没有任何判据会红。⇒ 必须靠外部对照（HEAD 版 ID 集 / 字节级 diff / 工作区白名单）看出来。
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
AUDIT = os.path.join(ROOT, 'code-quality-audit')
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'recheck144.json')

R138 = u'code-quality-audit/\u7b2c138\u8f6e-\u5224\u636e\u8f93\u51fa\u53bb\u65f6\u76f8'
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools', 'check138.py')
FROZEN = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_evidence',
                      'phase138.json')
CHECK = os.path.join(HERE, 'check144.py')
MUTATE = os.path.join(HERE, 'mutate144.py')
MEASURE = os.path.join(HERE, 'measure144.py')
GITIGNORE = os.path.join(ROOT, '.gitignore')
LIVE = os.path.join(AUDIT, 'regress', '_out', 'phase138.live.json')

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


def _ids(src):
    """取源码里每个 `check(` 的判据 ID（`A1` / `B1b` / `H4c2` …）。"""
    return set(re.findall(r"check\(\s*u?'([A-Z]\d+[a-z0-9]*)", src))


def main():
    out = {}

    # ======================================================================
    head(u'H1 · 改动面（只动落盘段；判据一条没动）')

    for tag, p in ((u'check138.py', CHECK138), (u'check144.py', CHECK),
                   (u'mutate144.py', MUTATE), (u'measure144.py', MEASURE),
                   (u'phase138.json', FROZEN), (u'.gitignore', GITIGNORE)):
        b = _raw(p)
        s = _txt(p)
        crlf = s.count(u'\r\n')
        print(u'  %-16s sha1=%s  字节=%d  行=%d  CRLF=%d 裸LF=%d'
              % (tag, _sha1(p)[:12], len(b), s.count(u'\n'), crlf,
                 s.count(u'\n') - crlf))

    diff = _git('diff', '-U0', '--', R138 + '/_tools/check138.py')
    n_hunk = len([l for l in diff.split(u'\n') if l.startswith(u'@@')])
    # 2 处 = 注释块 / 落盘那 5 行。第一版若又写成"必须 1 处"就是"判据假设实现形状"。
    check(u'H1a `check138.py` 的改动只有 2 处 hunk（注释块 / 落盘段）',
          n_hunk == 2, u'hunk=%d' % n_hunk)
    minus = [l for l in diff.split(u'\n')
             if l.startswith(u'-') and not l.startswith(u'---')]
    plus = [l for l in diff.split(u'\n')
            if l.startswith(u'+') and not l.startswith(u'+++')]
    print(u'  删 %d 行 / 增 %d 行' % (len(minus), len(plus)))
    # ★ 真正要守的是"判据条数没被我改少"：用 AST 把 HEAD 版与现版的判据 ID 集对一遍。
    old = subprocess.run(['git', 'show', 'HEAD:' + R138 + '/_tools/check138.py'],
                         cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    old_src = old.stdout.decode('utf-8', 'replace')
    check(u'H1b 能取到 HEAD 版 `check138.py`', bool(old_src.strip()))
    check(u'H1c 判据 ID 集与 HEAD 版**逐字相同**（没有被我删掉/改名一条判据）',
          _ids(old_src) == _ids(_txt(CHECK138)),
          u'HEAD=%d 现=%d 差=%s'
          % (len(_ids(old_src)), len(_ids(_txt(CHECK138))),
             u','.join(sorted(_ids(old_src) ^ _ids(_txt(CHECK138)))) or u'无'))
    check(u'H1d 删掉的那 1 行里没有 `check(`（没有顺手删判据）',
          len(minus) == 1 and u'check(' not in minus[0],
          u'删 %d 行' % len(minus))
    check(u'H1e 新增行里没有 `check(`（没有顺手加判据、也没把判据搬走）',
          not [l for l in plus if u'check(' in l])

    # ======================================================================
    head(u'H2 · 语法（ast.parse；不用 py_compile，免得产 .pyc 改变被测状态）')

    bad = []
    for p in (CHECK138, CHECK, MUTATE, MEASURE):
        try:
            ast.parse(_txt(p))
        except SyntaxError as e:
            bad.append(u'%s: %s' % (os.path.basename(p), e))
    check(u'H2 四个脚本都能解析（check138 / check144 / mutate144 / measure144）',
          not bad, u' | '.join(bad))

    # ======================================================================
    head(u'H3 · 编码（无 BOM / 无 U+FFFD）')

    for tag, p in ((u'check138.py', CHECK138), (u'check144.py', CHECK),
                   (u'mutate144.py', MUTATE), (u'measure144.py', MEASURE),
                   (u'phase138.json', FROZEN)):
        b = _raw(p)
        s = _txt(p)
        check(u'H3 %s 无 BOM' % tag, not b.startswith(b'\xef\xbb\xbf'))
        check(u'H3 %s 无 U+FFFD（没有被错误转码的字符）' % tag,
              u'\ufffd' not in s)

    # ======================================================================
    head(u'H4 · 恒真判据复查（"看着在守其实没守"）')

    src = _txt(CHECK)
    tree = ast.parse(src)
    calls = [nd for nd in ast.walk(tree)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    trues = [nd for nd in calls
             if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant)
             and nd.args[1].value is True]
    check(u'H4a `check144.py` 里没有 `check(描述, True)`', not trues,
          u'命中 %d 处' % len(trues))

    ret_true = []
    for fn in [nd for nd in ast.walk(tree) if isinstance(nd, ast.FunctionDef)]:
        for st in fn.body:          # ★ 只看函数体第一层（walk 会把嵌套的 return 也算）
            if isinstance(st, ast.Return) and isinstance(st.value, ast.Constant) \
                    and st.value.value is True:
                ret_true.append(fn.name)
    check(u'H4b 没有"函数体第一层直接 return True"的桩函数', not ret_true,
          u'命中 %d 个' % len(ret_true))

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
          self_pass == txt.count(marker),
          u'自报=%d 标记=%d' % (self_pass, txt.count(marker)))
    # ★ 判据条数不许随环境变：把 live 挪走再跑一次，条数必须一模一样
    #   （B2 第一版读运行产物，就是这么在 16/17 之间跳的）
    moved = LIVE + '.h4d'
    had = os.path.isfile(LIVE)
    if had:
        os.replace(LIVE, moved)
    try:
        r2 = subprocess.run([sys.executable, CHECK], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        txt2 = r2.stdout.decode('utf-8', 'replace')
        m2 = re.search(r'PASS=(\d+) FAIL=(\d+)', txt2)
        p2 = int(m2.group(1)) if m2 else -1
    finally:
        if had:
            os.replace(moved, LIVE)
    check(u'H4d 判据条数与"live 文件在不在"无关（无运行产物时也一个不少）',
          p2 == self_pass, u'有 live=%d / 无 live=%d' % (self_pass, p2))

    # ======================================================================
    head(u'H5 · 逐令牌回验（提交史表里的每个数，回 lead144.json 核一次）')

    lead = json.loads(_txt(os.path.join(EV, 'lead144.json')))
    hist = lead.get('history') or []
    by_c = dict((h['commit'], h) for h in hist)
    # 表里 6 行（从新到旧）
    rows = [(u'0e4544b3', 142, 6274), (u'5562ac09', 141, 6246),
            (u'c3600942', 140, 6228), (u'ea67b36f', 139, 6198),
            (u'43216d24', 138, 6158), (u'46288e2b', 137, 6120)]
    check(u'H5a 提交史恰好 6 条', len(hist) == 6, u'实见 %d' % len(hist))
    for c, f, k in rows:
        h = by_c.get(c) or {}
        check(u'H5 `%s` = %d 文件 / %d 调用' % (c, f, k),
              h.get('files') == f and h.get('calls') == k,
              u'实见 %s/%s' % (h.get('files'), h.get('calls')))
    deltas = lead.get('deltas') or []
    d_file = set(d.get('d_files') for d in deltas)
    check(u'H5b 5 个增量**每次都是 +1 个文件**（纯机械漂移的核心证据）',
          d_file == set([1]), u'实见 %s' % sorted(d_file))
    want = [28, 18, 30, 40, 38]
    got = [d.get('d_calls') for d in deltas]
    check(u'H5c `d_calls` = 28/18/30/40/38（与表里的 +N 逐条对上）',
          got == want, u'实见 %s' % got)
    check(u'H5d 全仓**读盘 0 处**（停写的风险为零）',
          (lead.get('refs') or {}).get('read') == [],
          u'实见 %s' % ((lead.get('refs') or {}).get('read'),))
    check(u'H5e 冻结文件里写的四个数 = 最早那条（137 / 6120 / 0 / 0）',
          all(json.loads(_txt(FROZEN)).get(k) == v
              for k, v in (('files_scanned', 137), ('calls_scanned', 6120),
                           ('bad_lineno', 0), ('bad_size', 0))))
    note = json.loads(_txt(FROZEN)).get('_note') or u''
    for lit in (u'137', u'6 个提交', u'138~143', u'check144',
                u'phase138.live.json'):
        check(u'H5 _note 里的 `%s` 在盘上找得到' % lit, lit in note)
    check(u'H5f 6 个提交的 subject 都在 `_note` 的说法下（138~143 连续）',
          all((h.get('subject') or u'').startswith(u'\u7b2c%d\u8f6e' % n)
              for h, n in zip(sorted(hist, key=lambda x: x['calls']),
                              range(138, 144))),
          u'%s' % [h.get('subject', u'')[:6] for h in
                   sorted(hist, key=lambda x: x['calls'])])

    # ======================================================================
    head(u'H6 · 工作区白名单（按路径列 + 每条写理由）')

    por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
    lines = [l for l in por.split(u'\n') if l.strip()]
    print(u'  工作区状态 %d 行' % len(lines))
    allow_paths = (
        (u'code-quality-audit/第138轮-判据输出去时相/_tools/check138.py',
         u'本轮改落盘段（核心文件，已复检）'),
        (u'code-quality-audit/第138轮-判据输出去时相/_evidence/phase138.json',
         u'本轮冻结（+_note，两个数回到 138 轮那份）'),
        (u'code-quality-audit/第144轮-证据冻结/', u'本轮产物'),
        (u'code-quality-audit/regress/', u'登记 + 基线'),
        (u'.workbuddy/memory/', u'记忆'),
    )
    bad_paths = []
    for l in lines:
        path = l[2:].lstrip().strip(u'"')
        if not any(path.startswith(p) for p, _ in allow_paths):
            bad_paths.append(l)
    check(u'H6a 工作区只有预期改动（%d 条允许路径，逐条写了理由）'
          % len(allow_paths), not bad_paths, u'越界 %d 行' % len(bad_paths))
    for l in bad_paths[:8]:
        print(u'     越界：%s' % l)
    check(u'H6b 没有残留 `.bak144` / `_out` 之外的临时物',
          not [l for l in lines if u'.bak144' in l or u'.h4d' in l])
    check(u'H6c `regress/_out/` 没混进工作区（被 `.gitignore` 吃掉了）',
          not [l for l in lines if u'regress/_out/' in l])

    # ======================================================================
    head(u'H7 · 写盘目标')

    for p in (CHECK, MUTATE, MEASURE):
        src = _txt(p)
        hits = []
        for ln in src.split(u'\n'):
            if u"'w'" in ln and re.search(u"['\"][A-Za-z]:[\\\\/]", ln):
                hits.append(ln.strip()[:60])
        check(u'H7 %s 的写盘行里没有写死的绝对盘符'
              % os.path.basename(p), not hits, u' | '.join(hits))
    msrc = _txt(MUTATE)
    check(u'H7b `mutate144` 的备份固定在 `D:\\_tmp`（**绝不放工作区**：`git add -A` 会当成删除）',
          u"'D:\\\\_tmp'" in msrc or u'D:\\_tmp' in msrc)
    check(u'H7c `mutate144` 强制还原（`finally` 里 `copy2` 回来）',
          u'finally:' in msrc and msrc.count(u'shutil.copy2(bak, path)') >= 2)

    # ======================================================================
    out['summary'] = {'pass': _n['p'], 'fail': _n['f']}
    out['sha1'] = dict((k, _sha1(v)) for k, v in (
        (u'check138.py', CHECK138), (u'check144.py', CHECK),
        (u'mutate144.py', MUTATE), (u'measure144.py', MEASURE),
        (u'phase138.json', FROZEN)))
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
