# -*- coding: utf-8 -*-
u"""第146轮 · 测量：`check138` 的输出里还剩几个"时相量"。

## 为什么要量

第144轮把 `_evidence/phase138.json` 冻住了（那是**落盘**那一半），
但 `check138` 的 **stdout** 里还留着两个数：

    check(u'D1 ...', len(_targets) >= 100, u'%d 个' % len(_targets))
    check(u'D2 ...', _n_calls >= 2000,      u'%d 处' % _n_calls)

`_targets` = 进 `SUITES` 的脚本数、`_n_calls` = 那些脚本里的 `check`/`ok` 调用数。
**每加一个套件，这两个数必然变** ⇒ 判定一个字没变，`check138` 却报 DIFF ⇒
每轮都得 `--only check138 --update` 一次。这就是"时相量回显"的第 9 次复发
（前 8 次见 `check138` 抬头表）。

## 怎么量（不许靠"读源码觉得它会长"）

**行为级**：临时往 `SUITES` 里塞一条探针套件 ⇒ 那两个数**必然 +1 / +5** ⇒
`check138` 的 stdout 必须**逐行不变**。带负控制：
用**旧形状**（`%d` 格式化）把改前改后的两个数各渲染一遍，那两行**必须不同** ——
否则说明"数根本没动"，那"输出没变"就不是修好了，而是夹具没生效。

## 产物（★ 按第144轮那条口径**分家**）

`_evidence/measure146.json` —— 只放**结论**（Δfiles/Δcalls、不同行数 0、负控制 2/2、布尔）。
`code-quality-audit/regress/_out/` —— 活的东西：`base146.txt`（改前 stdout）、
`probe146.txt`（塞探针后 stdout）、`measure146.live.json`（绝对计数 / 候选面名单 / 行号）。
绝对计数（144 个套件 / 6319 处调用）**每加一个套件就变**，行号也会漂 ——
会自己变的东西不进 `_evidence/`，否则它就成了下一个 `phase138.json`。
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
EV = os.path.join(ROUND, '_evidence')
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
CHECK138 = os.path.join(ROOT, 'code-quality-audit', '第138轮-判据输出去时相',
                        '_tools', 'check138.py')
PY = u'C:\\Python311\\python.exe'
PROBE = u'D:\\_tmp\\probe146.py'
TMPD = u'D:\\_tmp'


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def run138():
    u"""跑一遍 `check138`，返回 (stdout, returncode)。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK138], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return out.decode('utf-8', 'replace'), p.returncode


def recount(src, tag=u''):
    u"""**独立**重算：进 `SUITES` 且**文件真的存在**的脚本数 + 那些脚本里的 `check`/`ok` 调用数。

    ★ 与 `check138._suite_scripts()` 是两段代码（这里是"取全部 script= 常量，
      再 `os.path.join(ROOT, *parts)` + `exists` 过滤"），只为**对账**：
      同一个数两条路算出来一致，才排得掉"某一方自己数错了"。
    """
    tree = ast.parse(src)
    paths = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign)
                and any(getattr(t, 'id', '') == 'SUITES' for t in n.targets)):
            continue
        if not isinstance(n.value, ast.List):
            continue
        for el in n.value.elts:
            if not isinstance(el, ast.Dict):
                continue
            for k, v in zip(el.keys, el.values):
                if getattr(k, 'value', '') != 'script' or not isinstance(v, ast.Call):
                    continue
                parts = []
                for a in v.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        parts.append(a.value)
                    else:
                        parts = None
                        break
                if parts:
                    paths.append(os.path.join(ROOT, *parts))
    uniq = sorted(set(paths))
    exist = [p for p in uniq if os.path.exists(p)]
    ncalls = 0
    for p in exist:
        try:
            t = ast.parse(_read(p))
        except SyntaxError:
            continue
        ncalls += sum(1 for x in ast.walk(t)
                      if isinstance(x, ast.Call)
                      and (getattr(x.func, 'id', '') in ('check', 'ok')
                           or getattr(x.func, 'attr', '') in ('check', 'ok')))
    return {'entries': len(paths), 'unique': len(uniq),
            'exist': len(exist), 'calls': ncalls, 'tag': tag}


PROBE_SRC = u'''# -*- coding: utf-8 -*-
u"""第146轮探针套件（**临时**，跑完即删）。

只为证明一件事：往 `SUITES` 里加一条套件（文件数 +1、check 调用数 +5）之后，
`check138` 的 stdout **必须逐行不变**。它不是产品、不是回归、不进 `baseline.json`。
"""


def check(desc, cond, extra=u''):
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc, extra))


check(u'probe-1', 1 == 1, u'')
check(u'probe-2', 2 == 2, u'')
check(u'probe-3', 3 == 3, u'')
check(u'probe-4', 4 == 4, u'')
check(u'probe-5', 5 == 5, u'')
'''

PROBE_ENTRY = (
    u"\n    {\n"
    u"        'id': 'check146-probe',\n"
    u"        'script': os.path.join(ROOT, u'" + PROBE.replace('\\', '\\\\') + u"'),\n"
    u"        'offscreen': False,\n"
    u"        'desc': u'第146轮探针（临时，跑完即删）',\n"
    u"    },\n"
)


def _insert_probe(src):
    u"""把探针条目塞进 `SUITES` 列表的**第一个位置**（末尾有 `,` ⇒ 语法合法）。"""
    mark = u'SUITES = ['
    if src.count(mark) != 1:
        raise RuntimeError(u'`SUITES = [` 出现 %d 次，定位不唯一' % src.count(mark))
    i = src.index(mark) + len(mark)
    return src[:i] + PROBE_ENTRY + src[i:]


def suite_scripts():
    u"""`SUITES` 里登记的全部脚本路径（不去重、不滤存在）。"""
    tree = ast.parse(_read(RUN_ALL))
    paths = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign)
                and any(getattr(t, 'id', '') == 'SUITES' for t in n.targets)):
            continue
        for el in getattr(n.value, 'elts', []):
            if not isinstance(el, ast.Dict):
                continue
            for k, v in zip(el.keys, el.values):
                if getattr(k, 'value', '') != 'script' or not isinstance(v, ast.Call):
                    continue
                parts = [a.value for a in v.args[1:]
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if parts:
                    paths.append(os.path.join(ROOT, *parts))
    return sorted(set(paths))


def tainted(tree):
    u"""这个脚本里，哪些变量装着"**扫了多大范围**"（而不是"抓到几个"）。

    ★★★ 第一版按**名字**匹配（`_targets`/`_n_calls`/`SUITES`…），当场抓出 15 处，
       **13 处是误报** —— `check90/91/92/99` 的 `_n_calls` 是**它们自己的记账计数器**
       （判据是 `CALLS == PASS + FAIL` 守恒，跟套件数一点关系都没有）。
       这正是"判据只判提到某名字＝恒真"的反面：**提到名字 ≠ 会变**。
       ⇒ 改成数据流：只有从 `_suite_scripts()` / `SUITES` 派生出来的量才算。
       `check138` 的链路实测是 `_targets = [p for p in _suite_scripts() …]` →
       `for _p in _targets` → `_tree = ast.parse(_read(_p))` → `_n_calls += sum(…_tree…)`
       —— 四跳，所以要跑到不动点。

    ★ 刻意**不追** `_bad_ln.append(...)` 这类"命中列表"：它记的是"抓到几个坏件"，
      健康态恒 0，只有真出问题时才变 —— 那时判据本来就该红。本轮清的是
      **规模量**（扫了多少文件 / 多少处调用），那个数**语义不变也会变**。

    ⇒ 返回 `(names, anomaly)`：
       `names`   = 规模量（`_targets` / `_n_calls`）—— 回显它就是要清的病；
       `anomaly` = **命中列表**（`[p for p in _suite_scripts() if not exists(p)]`，
                   即 `_missing`）—— 健康态恒 0，豁免但**登记**，不默默放过。
       判据：这种列表的推导式里带**否定**过滤（`if not …`）＝"只装异常项"。

    ★★ 补过一刀：第一版只追"值里出现脏名字"的累加（`_n_calls += sum(… _tree …)`），
       漏了最常见的 `for p in _targets: _n += 1` —— 值是个常数 `1`，一辈子追不到。
       实测（`check146 C5` 正控制只抓到 1/2 处）。⇒ 补"**在扫描集上遍历的循环体里，
       任何 `+=` 的计数目标都是规模量**"。
    """
    names = set(['SUITES', '_suites'])
    anomaly = set()
    for _ in range(10):
        before = (set(names), set(anomaly))
        for n in ast.walk(tree):
            if isinstance(n, ast.For) and isinstance(n.target, ast.Name):
                hit_iter = any(isinstance(s, ast.Name) and s.id in names
                               for s in ast.walk(n.iter))
                if hit_iter:
                    names.add(n.target.id)
                    # ★ 循环体里的计数器全部算规模量：`_n += 1`
                    for sub in ast.walk(n):
                        if isinstance(sub, ast.AugAssign) \
                                and isinstance(sub.target, ast.Name):
                            names.add(sub.target.id)
            elif isinstance(n, ast.Assign):
                val = n.value
                ref = any(isinstance(s, ast.Name) and s.id in names
                          for s in ast.walk(val))
                ref = ref or any(isinstance(f, ast.Call)
                                 and getattr(f.func, 'id', '') == '_suite_scripts'
                                 for f in ast.walk(val))
                if not ref:
                    continue
                neg = any(isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not)
                          for gen in getattr(val, 'generators', [])
                          for x in gen.ifs)
                for t in n.targets:
                    if not isinstance(t, ast.Name):
                        continue
                    (anomaly if neg else names).add(t.id)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                if any(isinstance(s, ast.Name) and s.id in names
                       for s in ast.walk(n.value)):
                    names.add(n.target.id)
        if (names, anomaly) == before:
            break
    return names, anomaly


def _elem_prints(e, names):
    u"""`e` 作为 `%` 的一个替换元素时，会把这个数**印出来**吗？

    ★ 与 `check138._prints_lineno` 同一条口径：**拿它算布尔不算印**。
      `u'过阈=%s' % (len(_targets) >= 100)` → 元素是 `Compare` ⇒ 印的是 True/False ⇒ 放行。
      `u'%d 个' % len(_targets)`            → 元素是 `len(...)` ⇒ 印的是 144 ⇒ 抓。
    """
    if isinstance(e, ast.Compare):
        return False
    if isinstance(e, ast.Call) and getattr(e.func, 'id', '') == 'bool':
        return False
    return any(isinstance(s, ast.Name) and s.id in names for s in ast.walk(e))


def printed_tainted(slot, names):
    u"""输出位里被 `%` 真印出来的"规模量"表达式（空 = 合规）。"""
    out = []
    for n in ast.walk(slot):
        if not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod)):
            continue
        right = n.right
        elems = right.elts if isinstance(right, ast.Tuple) else [right]
        for e in elems:
            if _elem_prints(e, names):
                out.append(ast.dump(e)[:60])
    return out


def fam_scan():
    u"""扫全仓：还有哪些判据的输出位**回显"随套件数变化"的规模量**。

    候选面 = 所有进了 `SUITES`、且**提到过** `run_all` / `SUITES` / `_suite_scripts`
    的脚本（不提就不可能依赖它）。候选面为空 ⇒ 这条闸自己就是空跑，所以单独报出来。
    """
    cands, hits, exempts = [], [], []
    for p in suite_scripts():
        if not os.path.exists(p):
            continue
        try:
            t = ast.parse(_read(p))
        except SyntaxError:
            continue
        mentions = any(
            (isinstance(s, ast.Name) and s.id in ('SUITES', '_suites'))
            or (isinstance(s, ast.Call) and getattr(s.func, 'id', '') == '_suite_scripts')
            or (isinstance(s, ast.Constant) and isinstance(s.value, str)
                and 'run_all' in s.value)
            for s in ast.walk(t))
        if not mentions:
            continue
        cands.append(os.path.relpath(p, ROOT))
        names, anomaly = tainted(t)
        for c in ast.walk(t):
            if not isinstance(c, ast.Call):
                continue
            if (getattr(c.func, 'id', '') or getattr(c.func, 'attr', '')) not in ('check', 'ok'):
                continue
            for sl in list(c.args[2:4]):
                pr = printed_tainted(sl, names)
                if pr:
                    hits.append({'file': os.path.relpath(p, ROOT),
                                 'line': c.lineno, 'printed': pr})
                ex = printed_tainted(sl, anomaly)
                if ex:
                    exempts.append({'file': os.path.relpath(p, ROOT),
                                    'line': c.lineno, 'printed': ex,
                                    'why': u'命中列表（健康态恒 0；只有真登记了坏件才变）'})
    return cands, hits, exempts


def selfcount_control():
    u"""反控制：`check90/91/92/99` 也印 `_n_calls`，但那是**自身记账计数**，不许被判红。

    没有这条，`fam_scan` 的"0 处"可能只是因为我把范围缩到"提过 run_all 的文件" ——
    那等于把闸门调到"看不见"。
    """
    out = []
    for rel in (u'第90轮-基础宠物审查', u'第91轮-基础宠物状态机',
                u'第92轮-宠物移动结算', u'第99轮-睡觉惊醒与场景系统'):
        p = os.path.join(ROOT, 'code-quality-audit', rel, '_tools')
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            if not fn.startswith('check') or not fn.endswith('.py'):
                continue
            fp = os.path.join(p, fn)
            t = ast.parse(_read(fp))
            names, anomaly = tainted(t)
            pr = 0
            for c in ast.walk(t):
                if not isinstance(c, ast.Call):
                    continue
                if (getattr(c.func, 'id', '') or getattr(c.func, 'attr', '')) not in ('check', 'ok'):
                    continue
                for sl in list(c.args[2:4]):
                    pr += len(printed_tainted(sl, names))
            out.append({'file': rel + '/' + fn, 'tainted': sorted(names),
                        'prints_tainted': pr})
    return out


def main():
    if not os.path.isdir(EV):
        os.makedirs(EV)
    if not os.path.isdir(TMPD):
        os.makedirs(TMPD)

    res = {}

    # ---------------------------------------------------------- 0 改前
    print(u'[1/6] 跑一遍 check138（改前）…')
    base, rc0 = run138()
    n0 = recount(_read(RUN_ALL), u'base')
    print(u'      exit=%d  files=%d calls=%d' % (rc0, n0['exist'], n0['calls']))
    res['base'] = {'exit': rc0, 'lines': len(base.splitlines()),
                   'files': n0['exist'], 'calls': n0['calls']}

    # ---------------------------------------------------------- 1 塞探针
    print(u'[2/6] 往 SUITES 塞探针（临时）…')
    _write(PROBE, PROBE_SRC)
    orig = _read(RUN_ALL)
    orig_sha = _sha1(RUN_ALL)
    new_src = _insert_probe(orig)
    ast.parse(new_src)                      # 塞完必须还能解析，否则后面全是噪声
    _write(RUN_ALL, new_src)
    try:
        n1 = recount(_read(RUN_ALL), u'probe')
        print(u'      塞完：files=%d calls=%d（Δfiles=%+d Δcalls=%+d）'
              % (n1['exist'], n1['calls'],
                 n1['exist'] - n0['exist'], n1['calls'] - n0['calls']))
        res['probe'] = {'files': n1['exist'], 'calls': n1['calls'],
                        'd_files': n1['exist'] - n0['exist'],
                        'd_calls': n1['calls'] - n0['calls']}
        print(u'[3/6] 再跑一遍 check138（塞了探针）…')
        probe, rc1 = run138()
        res['probe']['exit'] = rc1
    finally:
        _write(RUN_ALL, orig)
        back = _sha1(RUN_ALL)
        res['restored_sha1_ok'] = (back == orig_sha)
        print(u'      还原 run_all.py：sha1 %s' % (u'一致' if back == orig_sha else u'**不一致**'))
        if os.path.exists(PROBE):
            os.remove(PROBE)

    # ---------------------------------------------------------- 2 逐行比
    print(u'[4/6] 逐行比 base vs probe …')
    b = base.splitlines()
    q = probe.splitlines()
    changed = []
    if len(b) != len(q):
        changed.append(('__len__', len(b), len(q)))
    for i in range(min(len(b), len(q))):
        if b[i] != q[i]:
            changed.append((i + 1, b[i], q[i]))
    res['diff_lines'] = len(changed)
    res['diff_sample'] = [[str(x[0]), str(x[1])[:120], str(x[2])[:120]]
                          for x in changed[:6]]
    print(u'      不同行数 = %d' % len(changed))

    # ---------------------------------------------------------- 3 负控制
    print(u'[5/6] 负控制：**旧形状**（`%d`）渲染，两行必须不同 …')
    old_d1 = u'[PASS] D1 扫到的判据文件 \u2265 100 个  %d \u4e2a' % n0['exist']
    old_d1p = u'[PASS] D1 扫到的判据文件 \u2265 100 个  %d \u4e2a' % n1['exist']
    old_d2 = u'[PASS] D2 \u626b\u5230\u7684 `check`/`ok` \u8c03\u7528 \u2265 2000 \u5904  %d \u5904' % n0['calls']
    old_d2p = u'[PASS] D2 \u626b\u5230\u7684 `check`/`ok` \u8c03\u7528 \u2265 2000 \u5904  %d \u5904' % n1['calls']
    res['negctl_changed'] = int(old_d1 != old_d1p) + int(old_d2 != old_d2p)
    print(u'      旧形状下会变的行数 = %d / 2' % res['negctl_changed'])
    res['negctl_lines'] = [[old_d1, old_d1p], [old_d2, old_d2p]]

    # ---------------------------------------------------------- 4 族扫描
    print(u'[6/6] 扫全仓：还有哪些判据的输出位回显"随套件数变化"的规模量 …')
    cands, hits, exempts = fam_scan()
    print(u'      候选面（提到 run_all/SUITES/_suite_scripts 的套件）= %d：%s'
          % (len(cands), u', '.join(os.path.basename(c) for c in cands)))
    res['candidates'] = cands
    res['family_hits'] = hits
    res['family_exempts'] = exempts
    for h in hits:
        print(u'      \u2605 %s:%d  \u5370\u4e86 %s' % (h['file'], h['line'], u' + '.join(h['printed'])))
    if not hits:
        print(u'      （0 处：这一族清空了）')
    for h in exempts:
        print(u'      豁免 %s:%d  印了 %s —— %s'
              % (h['file'], h['line'], u' + '.join(h['printed']), h['why']))

    ctl = selfcount_control()
    res['selfcount_control'] = ctl
    bad_ctl = [c for c in ctl if c['prints_tainted']]
    print(u'      反控制（自身记账计数，印了也不许判红）：%d 个文件，误判 %d 个'
          % (len(ctl), len(bad_ctl)))
    for c in ctl:
        print(u'        %-42s tainted=%-28s 印了规模量=%d'
              % (c['file'].split(u'/')[-1], c['tainted'] or u'[]', c['prints_tainted']))

    # ---------------------------------------------------------- 落盘（分家）
    # ★★★ 第144轮那条口径：**会自己变的东西不进 `_evidence/`**。
    #   绝对计数（144 个文件 / 6319 处调用）、候选面名单、行号（`:236`）都是时相量，
    #   每加一个套件就变 —— 它们进 `regress/_out/`（`.gitignore` 已忽略整个目录）。
    #   `_evidence/measure146.json` 只放**结论**：Δ、0/2、布尔。
    live = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')
    if not os.path.isdir(live):
        os.makedirs(live)
    _write(os.path.join(live, 'base146.txt'), base)
    _write(os.path.join(live, 'probe146.txt'), probe)
    _write(os.path.join(live, 'measure146.live.json'),
           json.dumps(res, ensure_ascii=False, indent=1))

    stable = {
        'd_files': res['probe']['d_files'],
        'd_calls': res['probe']['d_calls'],
        'diff_lines': res['diff_lines'],
        'negctl_changed': res['negctl_changed'],
        'restored_sha1_ok': res['restored_sha1_ok'],
        'family_hits': len(hits),
        'family_exempts': len(exempts),
        'candidates_ge_40': len(cands) >= 40,
        'selfcount_false_positive': len(bad_ctl),
    }
    _write(os.path.join(EV, 'measure146.json'),
           json.dumps(stable, ensure_ascii=False, indent=1))
    print(u'      稳定结论 → _evidence/measure146.json；活计数 → regress/_out/')

    print(u'')
    print(u'=' * 70)
    ok = (res['diff_lines'] == 0 and res['negctl_changed'] == 2
          and res['probe']['d_files'] == 1 and res['probe']['d_calls'] > 0
          and res['restored_sha1_ok'] and not hits and not bad_ctl and len(cands) >= 40)
    print(u'measure146：%s' % (u'成立（数确实动了 +5，输出一行没动，族已清空）' if ok
                               else u'不成立 —— 看上面哪一步'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
