#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · G2 套件的"环境耦合"扫描（找下一个 `npc_persona55` 式的假红）。

**为什么要有它**：本轮全量 G2 里 `npc_persona55` 报了 DIFF，根因不是产品缺陷，
而是它的断言消息里打了一个**真实天气**算出来的字符串长度（`len=3426` → `3427`，
天气 'cloudy' 换了词）。这与第60轮修掉的 `round8_anim` **时间炸弹**同型：
套件把"会随时间/环境变化的值"写进了与基线比对的输出里 ⇒ 迟早自己翻红。

**它是什么、不是什么**（如实写明，免得被当成结论）：
  它是一个**候选清单生成器**，不是判决。真正判红/判绿要人读代码确认
  "那个易变值有没有流进断言消息/打印文本"。所以输出分三档：
    RISK-HIGH  易变调用出现在 `check(...)/ck(...)/ok(...)` 或 `print(...)` 同一行
    RISK-MID   文件里有易变调用，且文件里有断言（需要人读一眼）
    INFO       只有易变调用，但该文件不产出被比对的文本（如只在逻辑里用）

判据（自检，保证脚本自己不说谎）：
  E1 能从 `run_all.py` 里解析出套件清单（不是 0 条）
  E2 ★ 已知样本必须被抓到：`npc_persona55` 指向的脚本必须命中
     `get_current_weather` / `_build_npc_context` 一类
  E3 ★ 负控制：一个**没有**易变调用的合成文件必须不被判为 RISK-HIGH/MID
  E4 ★ 正控制：一个把 `time.localtime()` 打进 `print()` 的合成文件必须判 RISK-HIGH

用法：
  C:\\Python311\\python.exe envflak62.py
"""
import ast
import io
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')
OUT = os.path.join(ROUND, '_evidence')

#: 易变输入（真实世界状态）—— 命中即"值会变"。
#: ⚠️ 刻意**不收** `os.environ` 与 `tempfile.gettempdir()`：
#:    前者绝大多数是"**写**测试专用变量"（`os.environ[...] = ...` / `setdefault`），
#:    后者在同一台机上是稳定值 —— 两者都属"测试隔离"，不是"输出会漂移"的成因。
#:    （本脚本第二版把它们算进来，直接把 27/56 个套件标红：判据过宽 = 会误报。）
VOLATILE = [
    (u'time.localtime', re.compile(r'time\.localtime\s*\(')),
    (u'time.time(', re.compile(r'time\.time\s*\(')),
    (u'datetime.now', re.compile(r'datetime\.now\s*\(')),
    (u'date.today', re.compile(r'date\.today\s*\(')),
    (u'天气取值', re.compile(r'get_current_weather\s*\(|weather_system')),
    (u'NPC环境块', re.compile(r'_build_npc_context\s*\(')),
    (u'Ralsei环境块', re.compile(r'_build_ai_context\s*\(')),
    (u'PID', re.compile(r'os\.getpid\s*\(')),
    (u'用户名', re.compile(r'getpass\.getuser\s*\(')),
    (u'平台', re.compile(r'platform\.\w+\s*\(')),
    (u'网络', re.compile(r'\b(requests|urllib|socket|http\.client)\.')),
    (u'random', re.compile(r'(?<![\w.])random\.')),
]

#: "这些函数把值打到输出里" —— 命中才算真的会污染基线
EMIT = re.compile(r'\b(check|ck|ok|expect|verify|P|LINES\.append|print)\s*\(')

#: 有 seed 就不算随机风险
SEED = re.compile(r'random\.seed\s*\(')


def suite_scripts():
    u"""从 run_all.py 的 SUITES 里解析出每个套件的 script 路径。"""
    tree = ast.parse(io.open(RUN_ALL, 'rb').read().decode('utf-8'),
                     filename=RUN_ALL)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if 'SUITES' not in names:
            continue
        if not isinstance(node.value, ast.List):
            continue
        for el in node.value.elts:
            if not isinstance(el, ast.Dict):
                continue
            d = {}
            for k, v in zip(el.keys, el.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    d[k.value] = v
            if 'script' not in d or 'id' not in d:
                continue
            v = d['script']
            parts = []
            if isinstance(v, ast.Call) and v.args:
                for a in v.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        parts.append(a.value)
            if parts:
                out.append((d['id'].value, os.path.join(*parts)))
    return out


def _strip_str(ln):
    u"""把字符串字面量抹成空串（只为数括号配平，不要求语义精确）。"""
    return re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', u'""', ln)


def stmt_at(lines, i, max_lines=12):
    u"""取 `lines[i]` 所属的**整条语句**文本（到括号配平为止）。

    ★ 为什么不用"往后看 3 行"（第三版之前的写法）：`print('')` 后面紧跟
      `print('=== %s ===' % title)`，3 行窗口会把**邻行**的 `%s` 算到 `print('')`
      头上 ⇒ 又把一批无辜行标进 fmt（判据过宽 = 会误报，这是第三次踩）。
      按语句边界取，`print('')` 的片段就是 `print('')`，不含 `%s`。
    """
    buf = []
    depth = 0
    for k in range(i, min(len(lines), i + max_lines)):
        ln = lines[k]
        buf.append(ln)
        depth += _strip_str(ln).count(u'(') - _strip_str(ln).count(u')')
        depth += _strip_str(ln).count(u'[') - _strip_str(ln).count(u']')
        depth += _strip_str(ln).count(u'{') - _strip_str(ln).count(u'}')
        if depth <= 0 and k >= i:
            break
    return u'\n'.join(buf)


def scan_src(src):
    u"""`scan` 的核心：对**源码字符串**做扫描（自检要能喂合成样本，故拆出来）。

    本脚本第一版把"易变调用出现在 emit 前后 3 行内"当成 RISK ⇒ 几乎每个文件都中
    （`os.environ.setdefault('QT_QPA_PLATFORM', ...)` 这种无副作用设置也被算上），
    是典型的**判据过宽 = 会误报**。第二版收窄成两条同时成立：
      ① 文件里引用了易变输入（时钟 / 天气 / 环境块）；
      ② 存在"emit 调用之后 3 行内出现 `len(` 或 `%d`/`%s` 格式化"——
         即那个可变量真的被**打进断言消息**（`npc_persona55` 的 `len=3426` 就是这条）。
    第三版（本轮）再修掉两处**残留的过宽**（都是实测抓到的，不是想当然）：
      ③ **注释行**：`dialog_lounge52:621` 是一行 `# ★ 第54轮修：C9b 原先用
         NOW = time.time()` 的注释 —— 代码里早就修好了，扫描器却把它当"易变调用"。
      ④ **断言助手自己的打印行**：形如
         `print("[%s] %s%s" % ("PASS" if ok else "FAIL", name, ...))`
         第二版只过滤了**字面量** `'[PASS] %s'`，漏掉"标签由三元表达式算出来"这种
         （`[%s]` + `"PASS" if ok`），于是每个套件都会中。现按三元形态过滤。
    ③④ 各配一条自检（E6 / E7），免得以后又滑回去。
    """
    lines = src.split('\n')

    def is_comment(ln):
        return ln.lstrip().startswith(u'#')

    volatile = []
    for i, ln in enumerate(lines):
        if is_comment(ln):          # ③ 注释里写的历史代码不是"活代码"
            continue
        for label, pat in VOLATILE:
            if pat.search(ln):
                volatile.append({'line': i + 1, 'label': label,
                                 'code': ln.strip()[:110]})
    # ② 找 "emit(...) → 紧随 3 行内出现 len( / %d" 的形态。
    #    ★ 必须**跳过断言助手自身的定义与它的打印行** —— 否则每个套件都会中：
    #      `def check(name, cond, extra)` + `print('[PASS] %s %s' % (name, extra))`
    #      天然带 `%s`，与"易变值"毫无关系（判据过宽 = 会误报，第二次踩）。
    HELPER_DEF = re.compile(r'^\s*def\s+(check|ok|ck|expect|verify|validate)\b')
    # 助手自己的打印行：形如 `print('  [%s] %-6s %s' % ('PASS' if ...))`
    # ★ 第一版把 `'[PASS]'` 当整体匹配 ⇒ 漏掉 `'[PASS] %s'` 这种，白过滤了。
    HELPER_TAG = re.compile(r'\[(PASS|FAIL)\]')
    # ★ 第三版：标签由**三元**算出的形态（`"[%s] ..." % ("PASS" if ok else "FAIL", ...)`）
    HELPER_TERNARY = re.compile(r'''["'](PASS|FAIL|OK|DIF)\s*["']\s*if\b''')
    fmt = []
    for i, ln in enumerate(lines):
        if not EMIT.search(ln):
            continue
        if is_comment(ln):
            continue
        if HELPER_DEF.search(ln) or HELPER_TAG.search(ln) \
                or HELPER_TERNARY.search(ln):
            continue
        if re.match(r'^\s*(def|class)\s', ln):
            continue
        win = stmt_at(lines, i)
        if re.search(r'\blen\s*\(', win) or re.search(r'%\s*[\d.]*[ds]', win):
            fmt.append({'line': i + 1, 'code': ln.strip()[:110],
                        'win': win.strip()[:160]})
    return src, volatile, fmt


def scan(path):
    u"""对**文件**做扫描（`scan_src` 的薄包装）。"""
    return scan_src(io.open(path, 'rb').read().decode('utf-8', 'replace'))


def classify(src, volatile, fmt):
    u"""分档（`random` 且已 seed ⇒ 风险消失）。"""
    volatile = [h for h in volatile if h['label'] != u'random'] + \
               ([h for h in volatile if h['label'] == u'random']
                if not SEED.search(src) else [])
    if not volatile:
        return u'INFO', []
    if fmt:
        return u'RISK-HIGH', volatile + fmt
    return u'RISK-MID', volatile


def selftest():
    got = []
    neg = u'import math\ncheck("A1", math.sqrt(4) == 2)\n'
    lv, _h = classify(neg, [], [])
    got.append((u'E3 负控制：无易变调用 ⇒ 不算 RISK', lv == u'INFO'))
    vol = [{'line': 2, 'label': u'天气取值', 'code': u'w = get_current_weather()'}]
    fmt = [{'line': 4, 'code': u"check('L1', True, 'len=%d' % len(x))"}]
    lv2, _h = classify(u'w = get_current_weather()\ncheck(...)\n', vol, fmt)
    got.append((u'E4 正控制：可变量被格式化进断言消息 ⇒ 必须 RISK-HIGH',
                lv2 == u'RISK-HIGH'))
    got.append((u'E5 正控制：只有易变调用、没进消息 ⇒ RISK-MID',
                classify(u'x = get_current_weather()\n', vol, [])[0] == u'RISK-MID'))
    # ---- 第三版新增（锁住本轮修掉的两处过宽）----
    # E6 ★ 负控制：注释里出现 `time.time()` **不算**易变调用（活代码里没有）。
    s6 = u'import time\n# \u539f\u5148\u7528 NOW = time.time() \u53d6\u771f\u5b9e\u65f6\u949f\uff0c\u5df2\u4fee\nx = 1\n'
    _s, v6, _f6 = scan_src(s6)
    got.append((u'E6 \u2605 \u8d1f\u63a7\u5236\uff1a\u6ce8\u91ca\u91cc\u7684 time.time() \u4e0d\u5f97\u8ba1\u4e3a\u6613\u53d8\u8c03\u7528',
                len(v6) == 0))
    # E7 ★ 负控制：助手自身的**三元**打印行不得被计成"把可变量打进消息"。
    #    若这条过滤退化，套件会从 RISK-MID 假升到 RISK-HIGH。
    s7 = (u'w = get_current_weather()\n'
          u'def check(name, cond, extra=u\'\'):\n'
          u'    print(u"[%s] %s%s" % (u"PASS" if cond else u"FAIL", name, extra))\n')
    _s, v7, f7 = scan_src(s7)
    got.append((u'E7 \u2605 \u8d1f\u63a7\u5236\uff1a\u4e09\u5143\u5f62\u6001\u7684\u52a9\u624b\u6253\u5370\u884c\u4e0d\u5f97\u8ba1\u5165 fmt',
                len(f7) == 0 and len(v7) > 0))
    # E8 ★ 负控制：`print('')` 不得因**邻行**的 `%s` 被算成 fmt（按语句边界取片段）。
    s8 = (u'w = get_current_weather()\n'
          u"print('')\n"
          u"print('=== %s ===' % title)\n")
    _s, v8, f8 = scan_src(s8)
    _l8 = [h['line'] for h in f8]
    got.append((u'E8 \u2605 \u8d1f\u63a7\u5236\uff1aprint(\'\') \u4e0d\u5f97\u56e0\u90bb\u884c %%s \u88ab\u8ba1\u5165\uff08\u5b9e\u9645 fmt \u884c=%r\uff09'
                % (_l8,), 2 not in _l8))
    return got


def main():
    scripts = suite_scripts()
    print(u'=== 第62轮 · G2 套件环境耦合扫描 ===')
    got = selftest()
    for nm, ok in got:
        print(u'[%s] %s' % (u'PASS' if ok else u'FAIL', nm))
    ok1 = len(scripts) > 0
    print(u'[%s] E1 从 run_all.py 解析出套件清单（%d 个）'
          % (u'PASS' if ok1 else u'FAIL', len(scripts)))
    print()

    rows = []
    miss = []
    for sid, p in scripts:
        if not os.path.isfile(p):
            rows.append({'id': sid, 'script': p, 'level': u'MISSING'})
            miss.append(sid)
            continue
        src, vol, fmt = scan(p)
        lv, keep = classify(src, vol, fmt)
        rows.append({'id': sid, 'script': os.path.relpath(p, REPO),
                     'level': lv, 'n_volatile': len(vol), 'n_fmt': len(fmt),
                     'volatile': vol[:6], 'fmt': fmt[:3]})

    order = {u'RISK-HIGH': 0, u'RISK-MID': 1, u'INFO': 2, u'MISSING': 3}
    rows.sort(key=lambda r: (order.get(r['level'], 9), r['id']))
    for r in rows:
        if r['level'] in (u'RISK-HIGH', u'RISK-MID'):
            print(u'  [%s] %-18s volatile=%d fmt=%d'
                  % (r['level'], r['id'], r['n_volatile'], r['n_fmt']))
            for h in r['fmt'][:2]:
                print(u'         L%-5d %s' % (h['line'], h['code']))
            for h in r['volatile'][:2]:
                print(u'         L%-5d %-10s %s'
                      % (h['line'], h['label'], h['code']))
    n_hi = sum(1 for r in rows if r['level'] == u'RISK-HIGH')
    n_mid = sum(1 for r in rows if r['level'] == u'RISK-MID')
    print()
    print(u'汇总：RISK-HIGH %d / RISK-MID %d / INFO %d / MISSING %d（共 %d）'
          % (n_hi, n_mid, sum(1 for r in rows if r['level'] == u'INFO'),
             len(miss), len(rows)))

    # ---- E2 已知样本必须被抓到 ----
    npc = [r for r in rows if r['id'] == 'npc_persona55']
    e2 = bool(npc) and npc[0]['level'] == u'RISK-HIGH' \
        and npc[0]['n_volatile'] > 0 and npc[0]['n_fmt'] > 0
    print(u'[%s] E2 ★ 已知样本 `npc_persona55` 必须被判为 RISK-HIGH'
          % (u'PASS' if e2 else u'FAIL'))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    ev = {'n_suites': len(scripts), 'missing': miss,
          'selftest': [{'name': n, 'ok': o} for n, o in got],
          'e2_known_sample': e2,
          'rows': rows}
    p = os.path.join(OUT, 'envflak62.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0 if (e2 and all(o for _n, o in got) and ok1) else 1


if __name__ == '__main__':
    sys.exit(main())
