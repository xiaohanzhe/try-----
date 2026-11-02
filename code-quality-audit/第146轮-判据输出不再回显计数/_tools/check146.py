# -*- coding: utf-8 -*-
u"""第146轮回归锁：`check138` 的输出里**不再回显"规模量"**（扫了多少文件 / 多少处调用）。

## 病是什么（第 9 次复发，前 8 次见 `check138` 抬头表）

`check138` 的 D 段原来长这样：

    check(u'D1 扫到的判据文件 ≥ 100 个', len(_targets) >= 100, u'%d 个' % len(_targets))
    check(u'D2 扫到的调用 ≥ 2000 处',   _n_calls >= 2000,     u'%d 处' % _n_calls)

`_targets` = 进 `SUITES` 的脚本数、`_n_calls` = 那些脚本里的 `check`/`ok` 调用数。
**每加一个套件，这两个数必然变** ⇒ 判定一个字没改，`check138` 却报 DIFF ⇒
每轮都得 `--only check138 --update` 一次。

第144轮只冻了**落盘**那一半（`_evidence/phase138.json` 不再重写），
**stdout** 这一半没动 —— 于是那条口径还得再走一次。

## 本套件守什么

A 改到位（静态）：D1/D2 的 extra 里那两个数**只参与比较算布尔**，不作为 `%` 元素印出来
B **行为级**（核心）：临时往 `SUITES` 塞一条探针套件 ⇒ Δfiles=+1、Δcalls=+N ⇒
  `check138` 的 stdout **必须逐行不变**。带负控制：用旧形状渲染，那两行**必须不同**
  （否则"输出没变"就不是修好了，而是夹具没生效）
C 族清空：全仓再没有第二个套件把"规模量"印进输出（含**反控制**：`check90/91/92/99`
  也印 `_n_calls`，但那是自身记账计数，**不许**被判红）
D 鉴别力：内存里 `eval` D1/D2 的 extra，喂 144 个 / 0 个 target 必须给不同结论
E 自检

## ★★★ 为什么 B 段是"行为级"而不是"读源码觉得它不会变"

第 124 轮的教训：**判据互证 ≠ 独立验证**。静态扫描只能看"这个名字有没有被印出来"，
它抓不到"跨函数洗过的量"（`d = recount(SUITES)` 这种，本套件自己就有 —— 见 E4 登记的盲区）。
所以静态扫描是**便宜的前置筛**，真判据是 B 段：**输入数真的动了，输出真的没动**。

## ★★ 依赖
`measure146.py`（同目录）：复用 `tainted` / `printed_tainted` / `fam_scan` / 探针夹具。
两条 `recount` 实现互相对账（B0），不一致就红 —— 不是"互相印证所以对"，是"不一致就查"。
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
AUDIT = os.path.join(ROOT, 'code-quality-audit')
EV = os.path.join(ROUND, '_evidence')
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools', 'check138.py')
PHASE138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_evidence', 'phase138.json')
PY = u'C:\\Python311\\python.exe'

sys.path.insert(0, HERE)
import measure146 as M                                     # noqa: E402

_n_ok = 0
_n_bad = 0
_failed = []


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _calls_of(name):
    u"""`check138` 里 desc 以 `name` 开头的那个 `check(...)` 调用的 AST 节点。"""
    tree = ast.parse(_read(CHECK138))
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        if (getattr(n.func, 'id', '') or getattr(n.func, 'attr', '')) not in ('check', 'ok'):
            continue
        if not n.args:
            continue
        d = n.args[0]
        if isinstance(d, ast.Constant) and isinstance(d.value, str) \
                and d.value.startswith(name):
            return n
    return None


# =============================================== A 改到位（静态）
head(u'A 改到位：D1/D2 的 extra 不再把"规模量"印出来')

_names, _anom = M.tainted(ast.parse(_read(CHECK138)))
check(u'A1 `check138` 里能被识别出"规模量"变量（分母非空，否则下面两条是空跑）',
      len(_names - set(['SUITES', '_suites'])) >= 2,
      u'%d 个' % len(_names - set(['SUITES', '_suites'])))
check(u'A2 `check138 A4` 的 `_missing` 被正确归到**命中列表**桶，不混进规模量',
      u'_missing' in _anom and u'_missing' not in _names)

_bad_print = []
for _d in (u'D1', u'D2'):
    _c = _calls_of(_d)
    if _c is None or len(_c.args) < 3:
        _bad_print.append(_d + u':missing')
        continue
    if M.printed_tainted(_c.args[2], _names):
        _bad_print.append(_d)
check(u'A3 D1/D2 的输出位不再用 `%` 印出 `_targets` / `_n_calls`',
      not _bad_print, u'%s' % (_bad_print or u'0 处'))

_mentions = 0
for _d in (u'D1', u'D2'):
    _c = _calls_of(_d)
    if _c is None or len(_c.args) < 3:
        continue
    if any(isinstance(s, ast.Name) and s.id in _names for s in ast.walk(_c.args[2])):
        _mentions += 1
check(u'A4 D1/D2 的 extra 里那两个名字**还在**（只是改成算布尔，不是删掉了完事）',
      _mentions == 2, u'%d/2' % _mentions)

# ★★★ 这里原来是静态判据 `u"'regress'" in _src138` —— **半个恒真**：
#   `check138` 抬头就有 `RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', …)`，
#   光"文件里出现 regress 这个词"永远成立。⇒ 删掉，改成 B7 的**行为级**判据
#   （跑完之后：冻结件字节没变 + 活计数真落到 `regress/_out/`）。

# =============================================== B 行为级
head(u'B 行为级：塞一条探针套件 ⇒ 输入数 +1/+N，输出必须逐行不变')


def _run138():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK138], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return out.decode('utf-8', 'replace'), p.returncode


def _recount():
    u"""本套件**自己**数一遍：SUITES 里存在的脚本数 + 那些脚本里的 check/ok 调用数。"""
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
    exist = [p for p in sorted(set(paths)) if os.path.exists(p)]
    nc = 0
    for p in exist:
        try:
            t = ast.parse(_read(p))
        except SyntaxError:
            continue
        nc += sum(1 for x in ast.walk(t) if isinstance(x, ast.Call)
                  and (getattr(x.func, 'id', '') in ('check', 'ok')
                       or getattr(x.func, 'attr', '') in ('check', 'ok')))
    return len(exist), nc


_n_files, _n_calls = _recount()
_m_r = M.recount(_read(RUN_ALL))
check(u'B0 两条独立实现算出同一个数（不一致就查，不是"互相印证所以对"）',
      (_n_files, _n_calls) == (_m_r['exist'], _m_r['calls']))

if not os.path.isdir(u'D:\\_tmp'):
    os.makedirs(u'D:\\_tmp')
_write(M.PROBE, M.PROBE_SRC)
_probe_calls = sum(1 for x in ast.walk(ast.parse(M.PROBE_SRC)) if isinstance(x, ast.Call)
                   and getattr(x.func, 'id', '') in ('check', 'ok'))

_orig = _read(RUN_ALL)
_orig_sha = _sha1(RUN_ALL)
_p138_sha0 = _sha1(PHASE138)
_base, _rc0 = _run138()
_diff = -1
_d_files = 0
_d_calls = 0
_restored = False
_probe_gone = False
_old_pair = (False, False)
try:
    _new = M._insert_probe(_orig)
    ast.parse(_new)                                    # 塞完必须还能解析
    _write(RUN_ALL, _new)
    _f2, _c2 = _recount()
    _d_files, _d_calls = _f2 - _n_files, _c2 - _n_calls
    _probe, _rc1 = _run138()
    _a = _base.splitlines()
    _b = _probe.splitlines()
    _diff = abs(len(_a) - len(_b))
    _diff += sum(1 for i in range(min(len(_a), len(_b))) if _a[i] != _b[i])
    # 负控制：**旧形状**渲染。两个数必须真的不同，否则下面那条"输出没变"是假的
    _o1 = u'%d 个' % _n_files
    _o1p = u'%d 个' % _f2
    _o2 = u'%d 处' % _n_calls
    _o2p = u'%d 处' % _c2
    _old_pair = (_o1 != _o1p, _o2 != _o2p)
finally:
    _write(RUN_ALL, _orig)
    _restored = (_sha1(RUN_ALL) == _orig_sha)
    if os.path.exists(M.PROBE):
        os.remove(M.PROBE)
    _probe_gone = not os.path.exists(M.PROBE)

check(u'B1 探针真的进了 `SUITES`（文件数 +1；否则后面全是空跑）',
      _d_files == 1, u'Δfiles==1 ? %s' % (_d_files == 1))
check(u'B2 探针里的 `check` 调用真的被数进去（Δcalls == 探针里的调用数）',
      _d_calls == _probe_calls, u'Δcalls==%d ? %s' % (_probe_calls, _d_calls == _probe_calls))
check(u'B3 ★ 塞了探针之后 `check138` 的 stdout **逐行不变**',
      _diff == 0, u'不同行数==0 ? %s' % (_diff == 0))
check(u'B4 负控制：用**旧形状**渲染，D1/D2 那两行**必然不同**（证明数真的动了）',
      _old_pair == (True, True), u'两行都变 ? %s' % (_old_pair == (True, True),))
check(u'B5 `run_all.py` 已按字节还原（sha1 一致）',
      _restored, u'还原 ? %s' % _restored)
check(u'B6 探针文件已删除（不留临时件）', _probe_gone)
# ★ B7（替代 A5 那条半恒真）：跑两遍 `check138` 之后，**冻结件字节没变**，
#   而活计数真落到了 `regress/_out/`。这是行为，不是"源码里有没有那个词"。
_p138_sha1 = _sha1(PHASE138)
_live_json = os.path.join(AUDIT, 'regress', '_out', 'phase138.live.json')
check(u'B7 冻结的 `phase138.json` 一个字节没动（跑 check138 不再改写历史证据）',
      _p138_sha1 == _p138_sha0, u'字节未变 ? %s' % (_p138_sha1 == _p138_sha0))
check(u'B8 活计数落到了 `regress/_out/phase138.live.json`（不在 `_evidence/`）',
      os.path.exists(_live_json))

# =============================================== C 族清空
head(u'C 这一族清空（含反控制：自身记账计数不许被误伤）')
_cands, _hits, _exempts = M.fam_scan()
check(u'C1 候选面够大（提到 run_all/SUITES 的套件 ≥ 40，否则这条闸是空跑）',
      len(_cands) >= 40, u'≥40 ? %s' % (len(_cands) >= 40))
check(u'C2 ★ 全仓 0 处把"规模量"印进输出',
      not _hits, u'0 处 ? %s' % (not _hits))
check(u'C3 豁免恰好 1 处（`check138 A4` 的 `_missing`：健康态恒 0 的命中列表）',
      len(_exempts) == 1, u'==1 ? %s' % (len(_exempts) == 1))
_ctl = M.selfcount_control()
_bad_ctl = [c for c in _ctl if c['prints_tainted']]
check(u'C4 反控制：`check90/91/92/99` 的自身记账计数 0 处误伤',
      len(_ctl) == 4 and not _bad_ctl,
      u'4 个文件 / 误伤 %d 个' % len(_bad_ctl))

# 正控制：**旧写法**必须被抓到 —— 否则 C2 的"0 处"可能只是闸坏了
_OLD = ast.parse(
    u"def f():\n"
    u"    _targets = [p for p in _suite_scripts() if os.path.exists(p)]\n"
    u"    _n = 0\n"
    u"    for _p in _targets:\n"
    u"        _n += 1\n"
    u"    check(u'd', len(_targets) > 0, u'%d 个' % len(_targets))\n"
    u"    check(u'd', _n > 0, u'%d 处' % _n)\n")
_old_names, _ = M.tainted(_OLD)
_old_hit = sum(len(M.printed_tainted(c.args[2], _old_names))
               for c in ast.walk(_OLD)
               if isinstance(c, ast.Call) and getattr(c.func, 'id', '') == 'check'
               and len(c.args) >= 3)
check(u'C5 正控制：合成一段**旧写法**，必须抓到 2 处（否则 C2 是空跑）',
      _old_hit == 2, u'抓到 %d 处' % _old_hit)
# 反控制：同一段把它改成"算布尔"，必须 0 处 —— 钉住"只改判定形态不算病"
_NEWLIKE = ast.parse(
    u"def f():\n"
    u"    _targets = [p for p in _suite_scripts() if os.path.exists(p)]\n"
    u"    check(u'd', len(_targets) > 0, u'\u8fc7\u9608=%s' % (len(_targets) > 0))\n")
_nl_names, _ = M.tainted(_NEWLIKE)
_nl_hit = sum(len(M.printed_tainted(c.args[2], _nl_names))
              for c in ast.walk(_NEWLIKE)
              if isinstance(c, ast.Call) and getattr(c.func, 'id', '') == 'check'
              and len(c.args) >= 3)
check(u'C6 反控制：同一段改成"算布尔"必须 0 处（新形状不算病）', _nl_hit == 0)

# =============================================== D 鉴别力
head(u'D 鉴别力：extra 是**跟着判定走**的，不是死字串')
_tree138 = ast.parse(_read(CHECK138))
_src138_txt = _read(CHECK138)
_eval_ok, _eval_differ = 0, 0
for _d in (u'D1', u'D2'):
    _c = _calls_of(_d)
    if _c is None or len(_c.args) < 3:
        continue
    _seg = ast.get_source_segment(_src138_txt, _c.args[2])
    if not _seg:
        continue
    try:
        _t = eval(_seg, {'_targets': list(range(1000)), '_n_calls': 10 ** 6})   # noqa: S307
        _f = eval(_seg, {'_targets': [], '_n_calls': 0})                        # noqa: S307
    except Exception:
        continue
    if u'True' in _t and u'False' in _f:
        _eval_ok += 1
    if _t != _f:
        _eval_differ += 1
check(u'D1 D1/D2 的 extra 在"过阈 / 不过阈"下分别给出 True / False',
      _eval_ok == 2, u'%d/2' % _eval_ok)
check(u'D2 两种输入的输出**确实不同**（extra 是 thunk，不是写死的字符串）',
      _eval_differ == 2, u'%d/2' % _eval_differ)

# =============================================== E 自检
head(u'E 自检')
_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'E1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'0 处 ? %s' % (not _bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'E2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'E3 零外部盘（扫的都在仓库内；`D:\\_tmp` 只放已删的探针）',
      os.path.abspath(AUDIT).startswith(ROOT + os.sep))
_self_names, _ = M.tainted(_self)
_self_print = 0
for _c in ast.walk(_self):
    if isinstance(_c, ast.Call) and len(_c.args) >= 3 \
            and (getattr(_c.func, 'id', '') or getattr(_c.func, 'attr', '')) in ('check', 'ok'):
        _self_print += len(M.printed_tainted(_c.args[2], _self_names))
check(u'E4 本文件自己也不把"规模量"印进输出（守别人的人自己得守）',
      _self_print == 0, u'0 处 ? %s' % (_self_print == 0))
# ★ 已知盲区如实登记：跨函数的量（`d = recount(SUITES)`）静态追不到 ——
#   本文件 B1 的 `Δfiles` 就是这种形状，它能过 E4 不是因为它干净，是因为它洗过函数。
#   ★ 第一版这里写成 `check(..., u'Δfiles' in src or True)` —— 那是**恒真判据**
#     （被本文件自己的 E1 抓出来）。恒真比不写还危险，改成"确认盲区真的存在"。
_LAUNDER = ast.parse(
    u"def f():\n"
    u"    _n = recount()\n"
    u"    check(u'd', _n > 0, u'%d \u4e2a' % _n)\n")
_ln_names, _ = M.tainted(_LAUNDER)
_n_launder = sum(len(M.printed_tainted(c.args[2], _ln_names))
                 for c in ast.walk(_LAUNDER)
                 if isinstance(c, ast.Call) and getattr(c.func, 'id', '') == 'check'
                 and len(c.args) >= 3)
check(u'E5 盲区如实登记：跨函数洗过的量本闸**抓不到**（预期 0 处）',
      _n_launder == 0, u'0 处 ? %s' % (_n_launder == 0))

# =============================================== 落盘 + 收口
_live = os.path.join(AUDIT, 'regress', '_out')
if not os.path.isdir(_live):
    os.makedirs(_live)
with io.open(os.path.join(_live, 'check146.live.json'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(json.dumps({'d_files': _d_files, 'd_calls': _d_calls,
                        'probe_calls': _probe_calls, 'diff_lines': _diff,
                        'candidates': len(_cands), 'hits': len(_hits),
                        'exempts': len(_exempts)},
                       ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check146：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
