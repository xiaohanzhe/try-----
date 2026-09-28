#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 普查 B：恒真判据（"看着在守，其实没守"）。

三类目标（按危险度排序）：
  B-I   ★ 套件 pass 恒 0 —— 从不打印 [PASS]/[ OK ] 的套件，跑完 exit=0、fail=0，
        状态被判成 PASS，且基线里 pass=0 自洽 ⇒ **永远绿，什么都没守**。
        这是本框架最危险的形态：它不报红、也不留痕。
  B-II  check(常量, msg) —— 判据直接写字面量 True / 非空字符串。
  B-III assert <常量> / `x == x` 之类恒真表达式。

★★ 本脚本的**自身演进**就是本项目最贵教训的实例（"判据过宽 = 会误报"）：
   v1 假定 `arg0` 是条件位        → 1433 处"恒真"，几乎全是误报；
   v2 只按第 1 个形参名判位置    → 385 处，仍误报（三段式 check(tag,msg,cond) 被漏）；
   v3（本版）三层收窄：
       ① **只认"真判据助手"**：本文件内定义、且函数体里真的打印 `[PASS]`/`[FAIL]`
          （与 run_all.py 的计数口径同源）；属性调用只认严格名单，
          于是 `CD.check_reply(...)` 这种**业务函数**不再被误当判据。
       ② **try / 前序守卫豁免**：`check(..., True)` 若处在 try 的 body/else
          且有 except 分支，或紧跟一个"报 False 并 return"的前置守卫，
          则其效力由兜底提供 ⇒ 归入 `guarded_true`，单列不计入问题。
       ③ **自比只算纯表达式**：`X is not X` 里若 X 是**函数调用**，
          两次调用可有副作用 ⇒ 不是恒真（第46轮 D14 就是这种合法写法）。

判定口径：B7 只对 `hollow_true`（无任何兜底的真·空洞判据）报红；
其余候选必须逐条给出裁定，未裁定数 > 0 也算红（防止"扫到了但没人看"）。

只用 AST，不做 import。用法：C:\\Python311\\python.exe audit_truth60.py
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
OUT = os.path.join(ROUND, '_evidence')
BASELINE = os.path.join(AUDIT, 'regress', 'baseline.json')
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')

# 判据助手的**严格名单**：属性调用（`obj.check(...)`）只认这些名字。
STRICT_HELPER_NAMES = frozenset(('check', 'ok', 'ck', 'expect', 'verify', 'validate'))

# 「不是条件位」的形参名特征。
MSG_PARAM_WORDS = frozenset((
    'msg', 'message', 'name', 'desc', 'description', 'label', 'title', 'text',
    'info', 'reason', 'why', 'note', 'tag', 'what', 'case', 'detail', 'hint',
    'prefix', 'head', 'subject', 'about', 'explain', 'comment',
))
# 「就是条件位」的形参名特征。实测三种签名：check(cond,msg) / check(msg,cond) /
# check(tag,msg,cond)（check54a.py）—— 位置猜测必错，只能按名字认。
COND_PARAM_WORDS = frozenset((
    'cond', 'condition', 'ok', 'passed', 'pass_', 'result', 'res', 'val',
    'value', 'flag', 'truth', 'good', 'success', 'is_ok', 'yes', 'hit',
))

TAUTOLOGY_KINDS = {
    'const_true': '判据是字面量 True',
    'const_truthy': '判据是非空字面量（字符串/数）—— 永远为真',
    'self_compare': '判据自己和自己比（x == x），且两侧都是纯表达式',
    'or_true': '判据含 `or True` —— 永远为真',
    'and_false': '判据含 `and False` —— 永远为假（死判据）',
}


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


# ------------------------------------------------------------ 套件脚本清单
def suites_from_run_all():
    """从 run_all.py 的 SUITES 里 AST 提取 (id, script绝对路径)。"""
    src = io.open(RUN_ALL, encoding='utf-8').read()
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if 'SUITES' in names and isinstance(node.value, ast.List):
                for el in node.value.elts:
                    if not isinstance(el, ast.Dict):
                        continue
                    d = {}
                    for k, v in zip(el.keys, el.values):
                        if isinstance(k, ast.Constant):
                            d[k.value] = v
                    sid = d.get('id')
                    sid = sid.value if isinstance(sid, ast.Constant) else None
                    sc = d.get('script')
                    parts = None
                    if isinstance(sc, ast.Call) and isinstance(sc.func, ast.Attribute) \
                            and sc.func.attr == 'join':
                        parts = []
                        for a in sc.args:
                            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                                parts.append(a.value)
                            elif isinstance(a, ast.Name) and a.id == 'ROOT':
                                parts.append(REPO)
                    if parts:
                        out.append((sid, os.path.join(*parts)))
    return out


# ------------------------------------------------------------ AST 辅助
def _dump(node):
    try:
        return ast.unparse(node)
    except Exception:
        return '<unparse失败>'


def build_helper_map(tree):
    """{函数名: {'params': [...], 'reports': bool}}；reports=函数体里真打印 PASS/FAIL。"""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            reports = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and (
                        '[PASS]' in sub.value or '[FAIL]' in sub.value or '[ OK ]' in sub.value):
                    reports = True
                    break
            out.setdefault(node.name, {
                'params': [a.arg for a in node.args.args],
                'reports': reports})
    return out


def build_try_guard(tree):
    """{自身或后代节点 id: True} —— 落在「带 except 的 try 的 body/orelse」里的节点。"""
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and node.handlers:
            for st in list(node.body) + list(node.orelse):
                for sub in ast.walk(st):
                    guarded.add(id(sub))
    return guarded


def build_guard_reports(tree):
    """找「前置守卫」：`if <cond>: check(..., False, ...); return` 这类语句里的
    check 名与它**紧跟其后的同一函数体**里报 True 的 check 行号。

    做法：所有「报 False 的判据调用所在行」的行号集合 —— 若某个报 True 的字面量
    判据，其**上方 30 行内**存在同名助手报 False 的调用，则视为被守卫兜底。
    这是启发式（所以单列 guarded_true），但足以把"前置哨兵"与"真·空洞"分开。
    """
    false_lines = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else '')
            if not name or name.lower() not in STRICT_HELPER_NAMES:
                continue
            for a in node.args:
                if isinstance(a, ast.Constant) and a.value is False:
                    false_lines.setdefault(name, []).append(node.lineno)
                # check(name, False, ...) 形态：False 在任意位置都算
    return false_lines


def is_pure(node):
    """子树里没有函数调用 ⇒ 两次求值结果相同，自比才有意义。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            return False
    return True


def tautology_kind(node):
    """返回 (kind, 证据) 或 (None, None)。只判"纯语法恒真"。"""
    if isinstance(node, ast.Constant):
        v = node.value
        if v is True:
            return 'const_true', 'True'
        if isinstance(v, (str, int, float)) and v:
            return 'const_truthy', repr(v)
        return None, None
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1 and len(node.comparators) == 1:
            left, right = node.left, node.comparators[0]
            try:
                if ast.dump(left) == ast.dump(right) and is_pure(left) and is_pure(right):
                    return 'self_compare', _dump(node)
            except Exception:
                pass
    if isinstance(node, ast.BoolOp):
        for v in node.values:
            if isinstance(v, ast.Constant) and v.value is True and isinstance(node.op, ast.Or):
                return 'or_true', _dump(node)
            if isinstance(v, ast.Constant) and v.value is False and isinstance(node.op, ast.And):
                return 'and_false', _dump(node)
    return None, None


def cond_index(fn_name, args, helpers):
    """判定「第几个实参是条件」。判不出返回 0。"""
    h = helpers.get(fn_name)
    params = h['params'] if h else None
    if params:
        low = [p.lower().lstrip('_') for p in params]
        for i, p in enumerate(low):
            if p in COND_PARAM_WORDS:
                return i
        non_msg = [i for i, p in enumerate(low) if p not in MSG_PARAM_WORDS]
        if len(non_msg) == 1:
            return non_msg[0]
        return 0
    if len(args) >= 2 and isinstance(args[0], ast.Constant) \
            and isinstance(args[0].value, str) and not isinstance(args[1], ast.Constant):
        return 1
    return 0


def scan_script(path):
    try:
        src = io.open(path, encoding='utf-8').read()
        tree = ast.parse(src)
    except Exception as e:
        return {'path': path, 'error': '%s: %s' % (type(e).__name__, e),
                'sites': [], 'n_sites': 0, 'sig': {}, 'helpers': []}
    lines = src.split('\n')
    helpers = build_helper_map(tree)
    guarded = build_try_guard(tree)
    false_lines = build_guard_reports(tree)
    sites = []
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Assert):
            name = 'assert'
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute):
                nm = fn.attr
                # 属性调用：只认严格名单，且要求同名的本地定义真的报 PASS/FAIL
                if nm.lower() in STRICT_HELPER_NAMES and helpers.get(nm, {}).get('reports'):
                    name = nm
            elif isinstance(fn, ast.Name):
                nm = fn.id
                if helpers.get(nm, {}).get('reports') or nm.lower() in STRICT_HELPER_NAMES:
                    name = nm
        if name is None:
            continue

        if name == 'assert':
            kind, why = tautology_kind(node.test)
            ci, cond = None, node.test
        else:
            if not node.args:
                continue
            ci = cond_index(name, node.args, helpers)
            if ci >= len(node.args):
                continue
            cond = node.args[ci]
            kind, why = tautology_kind(cond)

        if not kind:
            # ★ 非恒真的判据点也要**记下来**：它们既是 B4「≥500」的分子
            #   （防止"路径全错 ⇒ 0 恒真"的假绿），也是自检里核对条件位下标的样本。
            sites.append({
                'line': node.lineno, 'fn': name, 'cond': _dump(cond), 'ci': ci,
                'kind': None, 'why': None, 'exempt': None, 'verdict': None,
                'code': lines[node.lineno - 1].strip()[:200]})
            continue
        # 分类：有兜底 ⇒ guarded_true
        exempt = None
        if id(node) in guarded:
            exempt = 'try/except 兜底（异常分支会报 False）'
        else:
            fl = false_lines.get(name) or []
            if any(0 < node.lineno - x <= 30 for x in fl):
                exempt = '前置守卫兜底（上方 30 行内同名助手报过 False）'
        sites.append({
            'line': node.lineno, 'fn': name, 'cond': _dump(cond), 'ci': ci,
            'kind': kind, 'why': why, 'exempt': exempt,
            'verdict': 'guarded_true' if exempt else 'hollow_true',
            'code': lines[node.lineno - 1].strip()[:200]})
    return {'path': path, 'error': None, 'sites': sites, 'n_sites': None,
            'sig': {k: v['params'] for k, v in helpers.items()
                    if k.lower() in STRICT_HELPER_NAMES or v['reports']}}


# ------------------------------------------------------------ 自检
def self_test():
    """扫描器必须能证伪。正控制：恒真必须报；负控制：合法写法必须不报。

    ★ 负控制里那三种签名，正是本扫描器 v1/v2 的**误报来源**，必须常驻。
    """
    d = OUT
    os.makedirs(d, exist_ok=True)
    pos = os.path.join(d, '_truth_pos.py')
    neg = os.path.join(d, '_truth_neg.py')
    with io.open(pos, 'w', encoding='utf-8', newline='') as f:
        f.write('def check(cond, msg):\n'
                '    print("[PASS]" if cond else "[FAIL]")\n'
                'check(True, "恒真")\n'
                'check("yes", "非空串")\n'
                'check(x == x, "自比-纯表达式")\n'
                'check(False or True, "or True")\n'
                'assert True\n')
    with io.open(neg, 'w', encoding='utf-8', newline='') as f:
        f.write('def check(cond, msg):\n'
                '    print("[PASS]" if cond else "[FAIL]")\n'
                'check(x > 0, "正常")\n'
                'check(x == y, "正常")\n'
                'check(False, "恒假不是恒真")\n'
                'assert x > 0\n'
                '\n'
                '# ① 消息在前\n'
                'def ok(msg, cond, detail=""):\n'
                '    print("[PASS]" if cond else "[FAIL]")\n'
                'ok("V1a 文案", x > 0)\n'
                '\n'
                '# ② 三段式：tag, msg, cond\n'
                'def ck(tag, msg, cond):\n'
                '    print("[PASS]" if cond else "[FAIL]")\n'
                "ck('C1', '文案', x > 0)\n"
                '\n'
                '# ③ 业务函数：名字里带 check 但不是判据\n'
                'def check_reply(text, who):\n'
                '    return (True, "")\n'
                "check_reply('我想去城北看看。', 'ralsei')\n"
                '\n'
                '# ④ 带副作用的"自比"：两次调用可以不同 ⇒ 不是恒真\n'
                'def reset():\n'
                '    return object()\n'
                'check(reset() is not reset(), "重置后拿到不同对象")\n'
                '\n'
                '# ⑤ try 兜底的成功分支：允许\n'
                'def boom():\n'
                '    raise ValueError("x")\n'
                'try:\n'
                '    boom()\n'
                'except Exception:\n'
                '    check(False, "失败")\n'
                'else:\n'
                '    check(True, "成功")\n')
    rp, rn = scan_script(pos), scan_script(neg)
    pos_kinds = sorted(s['kind'] for s in rp['sites'])
    hollow = [s for s in rn['sites'] if s['verdict'] == 'hollow_true']
    guarded = [s for s in rn['sites'] if s['verdict'] == 'guarded_true']
    ok = True
    print('      正控制：%d 处命中 %s' % (len(rp['sites']), pos_kinds))
    ok &= check(len(rp['sites']) == 5, '自检-正控制：5 处恒真全抓到（实际 %d）' % len(rp['sites']))
    ok &= check(len(hollow) == 0,
                '自检-负控制：真·空洞判据必须 0（实际 %d）%s'
                % (len(hollow), [(s['fn'], s['line']) for s in hollow]))
    ok &= check(len(guarded) == 1, '自检-负控制：try 兜底的成功分支必须被识别为 guarded（实际 %d）'
                % len(guarded))
    print('      负控制：扫到 %d 个判据点（含 4 种合法签名 + 1 个 try 兜底）' % len(rn['sites']))
    dbg = {s['fn']: (s['ci'], s['verdict']) for s in rn['sites'] if s['fn'] != 'assert'}
    print('      条件位/裁定：%s' % dbg)
    ok &= check(dbg.get('ok', (None,))[0] == 1, '自检-条件位：消息在前的 ok 必须解析成下标 1')
    ok &= check(dbg.get('ck', (None,))[0] == 2, '自检-条件位：三段式 ck 必须解析成下标 2')
    ok &= check('check_reply' not in dbg, '自检-负控制：业务函数 check_reply 必须不被当判据')
    for p in (pos, neg):
        try:
            os.remove(p)
        except OSError:
            pass
    return ok


def main():
    print('=' * 72)
    print('普查 B —— 恒真判据')
    print('=' * 72)

    # ---------- B-I 套件 pass 恒 0 ----------
    print('--- B-I 套件级：pass 恒 0（永远绿，什么都没守） ---')
    zero, counts = [], {}
    if os.path.exists(BASELINE):
        with io.open(BASELINE, encoding='utf-8') as f:
            base = json.load(f)
        for sid, rec in sorted(base.get('suites', {}).items()):
            counts[sid] = rec.get('pass', 0)
            if not rec.get('pass'):
                zero.append(sid)
    print('      共 %d 个套件；最小 PASS=%s；最大 PASS=%s'
          % (len(counts), min(counts.values()) if counts else '-',
             max(counts.values()) if counts else '-'))
    ok = True
    ok &= check(len(counts) > 0, 'B0 基线里有套件记录（实际 %d 个）' % len(counts))
    ok &= check(not zero, 'B1 没有 pass 恒 0 的套件（实际 %d 个：%s）' % (len(zero), zero))

    # ---------- B-II / B-III 脚本级恒真 ----------
    print()
    print('--- B-II/III 脚本级：判据调用点的恒真表达式 ---')
    suites = suites_from_run_all()
    ok &= check(len(suites) >= 50,
                'B2 SUITES 提取成功（实际 %d，≥50 说明 AST 解析没退化成空）' % len(suites))

    all_sites, findings, missing, scanned = 0, [], [], 0
    sigs = {}
    for sid, path in suites:
        if not os.path.exists(path):
            missing.append((sid, path))
            continue
        scanned += 1
        r = scan_script(path)
        if r['error']:
            findings.append({'suite': sid, 'error': r['error'], 'verdict': 'error'})
            continue
        sigs[sid] = r['sig']
        for s in r['sites']:
            all_sites += 1
            if not s['kind']:
                continue                       # 非恒真：只计入总数，不进候选清单
            s = dict(s)
            s['suite'] = sid
            s['path'] = os.path.relpath(path, REPO).replace('\\', '/')
            findings.append(s)

    print('      扫描 %d 个脚本；判据调用点合计 %d 处' % (scanned, all_sites))
    ok &= check(scanned >= 50, 'B3 实际扫描脚本数 ≥50（实际 %d）—— 防"路径全错所以 0 恒真"的假绿' % scanned)
    ok &= check(all_sites >= 500, 'B4 判据调用点 ≥500（实际 %d）—— 同上' % all_sites)
    ok &= check(not missing, 'B5 SUITES 里的脚本全部存在（缺失 %d 个）' % len(missing))
    ok &= check(not [f for f in findings if f.get('error')],
                'B6 全部脚本可解析（失败 %d 个）' % len([f for f in findings if f.get('error')]))

    hollow = [f for f in findings if f.get('verdict') == 'hollow_true']
    guarded = [f for f in findings if f.get('verdict') == 'guarded_true']
    print()
    if guarded:
        print('      ○ 已解释（%d 处，由 try/前置守卫兜底 —— 不是缺陷，登记备查）：' % len(guarded))
        for f in guarded:
            print('        %s:%s  [%s] %s' % (f['path'], f['line'], f['kind'], f['code']))
    if hollow:
        print('      ⚠ 真·空洞判据（%d 处，无任何兜底 ⇒ 永远为真）：' % len(hollow))
        for f in hollow:
            print('        %s:%s  [%s] %s' % (f['path'], f['line'], f['kind'], f['code']))
    ok &= check(not hollow, 'B7 没有真·空洞判据（实际 %d 处）' % len(hollow))

    print()
    print('--- 自检：扫描器自己必须能证伪 ---')
    ok &= self_test()

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, 'truth62.json')
    with io.open(dst, 'w', encoding='utf-8') as f:
        json.dump({'suite_pass_counts': counts, 'zero_pass': zero,
                   'n_suites': len(suites), 'n_scanned': scanned,
                   'n_sites': all_sites,
                   'hollow': hollow, 'guarded': guarded,
                   'signatures': sigs}, f, ensure_ascii=False, indent=1)
    print()
    print('证据：%s' % dst.replace('\\', '/'))
    print('=' * 72)
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
