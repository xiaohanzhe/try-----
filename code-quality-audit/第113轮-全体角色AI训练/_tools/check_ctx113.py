# -*- coding: utf-8 -*-
"""第113轮 / 2026-10-29 · 截断判据（`stats.truncated`）修复验证。

## 为什么要单独写这个校验
`common113.chat()` 原来这样判：
    'truncated': bool((final.get('prompt_eval_count') or 0) >= NUM_CTX)   # NUM_CTX=8192
而 `train30.py` 传的是 `num_ctx=20480`。于是**每一轮 prompt 超过 8192 token 的回答
都被标成「前缀被截断」**，断言的是"人设开头被切掉了" —— 一个根本没发生的事故。
实测虚报 **1,010 轮**，峰值 `prompt_eval_count` 只有 12,216（真实余量 8,264）。

这就是「判据也是被测物」：判据抓了一个与本次请求无关的常量。
修法不是删判据（截断是真风险），而是让它用**本次实际生效的 ctx**。

## 判据设计（吸取 §108.6：禁某 API 出现类判据禁纯文本扫）
- 用 **AST** 定位 `truncated` 那个键的表达式，看它引用的是哪个名字；
- 「payload 与判据同一把尺子」用 AST 比对两处引用的标识符；
- 行为验证正负成对：`pec=12216/ctx=20480 → False`、`pec=20480/ctx=20480 → True`；
- **负控制**：把源码副本里的 `eff_ctx` 换回 `NUM_CTX`，S1/S2 必须报红
  （否则说明这两条判据恒真，比不写还危险）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
RAW30 = os.path.join(ROUND, '_evidence', 'raw30')
COMMON = os.path.join(HERE, 'common113.py')

NUM_CTX_CONST = 8192
CTX30 = 20480

_ok = []
_bad = []


def check(name, cond, detail=''):
    (_ok if cond else _bad).append(name)
    print('[%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('  ' + detail) if detail else ''))
    return bool(cond)


def _src(path):
    with io.open(path, encoding='utf-8', newline='') as f:
        return f.read()


def find_chat(tree):
    """按名字找 `def chat(...)` —— 不用 walk+break 抓"第一个 FunctionDef"（§96b.1 陷阱）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'chat':
            return node
    return None


def names_in(node):
    """表达式里**被读取**的所有标识符（不含关键字、不含属性名）。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            out.add(n.id)
    return out


def find_truncated_value(fn):
    """在 `stats = {...}` 里找键名是 `truncated` 的那个 value 表达式。"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == 'truncated':
                    return v
    return None


def find_assign(fn, target_name):
    """找 `target_name = <expr>`（函数体内，任意深度）。返回 value 节点或 None。"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == target_name:
                    return node.value
    return None


def find_opts_num_ctx(fn):
    """找 `opts = {...}` 里 `'num_ctx'` 那个 value 表达式。

    ★ 必须是**字典字面量**里的那个键，不能全文搜 `num_ctx` —— 函数签名里有同名参数
      （`num_ctx=None`），纯文本扫会命中它，判据就恒真了。
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == 'num_ctx':
                    return v
    return None


def judge(pec, ctx):
    """复刻修好之后的判据语义 —— 与产品代码**同一个式子**，用来做行为正负控制。"""
    eff_ctx = NUM_CTX_CONST if ctx is None else int(ctx)
    return bool((pec or 0) >= eff_ctx)


def main():
    src = _src(COMMON)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return check('S0 common113.py 语法', False, repr(e))

    fn = find_chat(tree)
    if not check('S0 找到 def chat（AST 按名字）', fn is not None):
        return 1

    # ---------- S1：truncated 的阈值引用的是 eff_ctx，不是 NUM_CTX ----------
    tr = find_truncated_value(fn)
    if not check('S1a 定位到 stats["truncated"] 的表达式', tr is not None):
        return 1
    used = names_in(tr)
    check('S1b truncated 用 eff_ctx 判（AST 标识符）', 'eff_ctx' in used, '引用=%s' % sorted(used))
    check('S1c truncated **不再**引用 NUM_CTX 常量', 'NUM_CTX' not in used, '引用=%s' % sorted(used))

    # ---------- S2：payload 与判据是同一把尺子 ----------
    eff = find_assign(fn, 'eff_ctx')
    if check('S2a 找到 eff_ctx 的赋值', eff is not None):
        eff_names = names_in(eff)
        check('S2b eff_ctx 由参数 num_ctx 派生（且保留 NUM_CTX 兜底）',
              'num_ctx' in eff_names and 'NUM_CTX' in eff_names,
              '引用=%s' % sorted(eff_names))
    else:
        _bad.append('S2b')
    nc = find_opts_num_ctx(fn)
    if check('S2c 定位到 opts["num_ctx"] 的表达式', nc is not None):
        check('S2d opts["num_ctx"] 用的是 eff_ctx（与判据同源）',
              names_in(nc) == {'eff_ctx'}, '引用=%s' % sorted(names_in(nc)))

    # ---------- S3：行为正负成对 ----------
    check('S3a [负] pec=12216 < ctx=20480 ⇒ 不算截断', judge(12216, CTX30) is False)
    check('S3b [正] pec=20480 >= ctx=20480 ⇒ 必须算截断', judge(20480, CTX30) is True)
    check('S3c [正] pec=25000 > ctx=20480 ⇒ 必须算截断', judge(25000, CTX30) is True)
    check('S3d [兜底] ctx=None ⇒ 退回常量 8192，pec=8300 算截断',
          judge(8300, None) is True)

    # ---------- S4：负控制 —— 把修复拆掉，S1b/S1c 必须报红 ----------
    bad_src = src.replace(">= eff_ctx)", ">= NUM_CTX)", 1)
    if not check('S4a 负控制夹具真的改到了源码', bad_src != src,
                 '若两者相同则负控制无效'):
        _bad.append('S4b')
    else:
        fn2 = find_chat(ast.parse(bad_src))
        tr2 = find_truncated_value(fn2)
        used2 = names_in(tr2) if tr2 is not None else set()
        check('S4b 负控制：改回 NUM_CTX 后 S1b 会报红（说明 S1b 不是恒真）',
              'eff_ctx' not in used2, '此时引用=%s' % sorted(used2))
        check('S4c 负控制：改回 NUM_CTX 后 S1c 会报红',
              'NUM_CTX' in used2, '此时引用=%s' % sorted(used2))

    # ---------- S5：拿 77 份实盘 raw30 用真实 ctx 重算 ----------
    if os.path.isdir(RAW30):
        n_files = n_old = n_new = 0
        peak = 0
        peak_id = ''
        for f in sorted(os.listdir(RAW30)):
            if not f.endswith('.jsonl'):
                continue
            recs = []
            with io.open(os.path.join(RAW30, f), encoding='utf-8', newline='') as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            recs.append(json.loads(line))
                        except Exception:
                            pass
            if not recs:
                continue
            r = recs[-1]
            n_files += 1
            ctx = r.get('ctx')
            for t in (r.get('turns') or []):
                pec = ((t.get('stats') or {}).get('prompt_eval_count') or 0)
                if pec > peak:
                    peak, peak_id = pec, f[:-6]
                if pec >= NUM_CTX_CONST:
                    n_old += 1
                if judge(pec, ctx):
                    n_new += 1
        check('S5a 扫到 77 份训练记录', n_files == 77, '实际 %d' % n_files)
        check('S5b 按**真实 ctx** 重算：截断轮次为 0', n_new == 0,
              '旧判据虚报 %d 轮' % n_old)
        check('S5c 旧判据确实虚报过（证明 S5b 不是"本来就没数据"）', n_old > 0,
              '虚报 %d 轮' % n_old)
        check('S5d 峰值 prompt_eval_count 低于 ctx（余量存在）', peak < CTX30,
              '峰值 %d（%s），余量 %d' % (peak, peak_id, CTX30 - peak))
    else:
        _bad.append('S5a')
        print('[FAIL] S5a raw30 目录不存在：%s' % RAW30)

    print()
    print('===== %d PASS / %d FAIL =====' % (len(_ok), len(_bad)))
    return 0 if not _bad else 1


if __name__ == '__main__':
    sys.exit(main())
