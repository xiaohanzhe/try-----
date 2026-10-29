# -*- coding: utf-8 -*-
"""第113轮 · 补训链路修复校验（2026-10-29）。

## 被修的是什么
`dialogue113.py --phase patch`（补训）整条链**接在旧目录 `_evidence/raw` 上**，
而 48 轮训练的产物在 `_evidence/raw30`，评测 `eval113.load_all()` 只读 raw30。
⇒ 两个后果，都不报错，只是安静地什么都不做：
  ① 筛「谁判红了」用的是 `existing_phases(x)['baseline']` —— `raw30` 里**没有**这个 phase
     键（训练写的是 `t30`）⇒ 筛出 **0 人**；
  ② 就算跑了，记录写进 `raw/`，评测读 `raw30/` ⇒ **永远看不见**。

这是第113轮s 修过「评测读错目录」之后**没修的另一半**（写盘侧）。
第113轮为此栽过三次，这里做正负成对的锁。

## 判据
- C1 `dialogue113.MAIN_RAW` 与 `eval113` 的取目录口径**同一个**
- C2 `main_record` 挑到的是 48 轮那条（不是后面追加的 12 轮试跑）
- C3 用 `main_record` 算判红人数 **> 0**（修复有效）
- C4 [负控制] 用旧的 `['baseline']` 键算判红人数 **== 0**（证明 C3 不是恒真）
- C5 AST：patch 筛选分支里**不再出现** `'baseline'` 键的取值，且调用了 `main_record`
- C6 补训转录目录**不等于** `transcripts30`（48 轮转录不可再生，不许覆盖）
- C7 三个模块语法可解析（用 ast.parse，不产 .pyc）
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import common113 as C            # noqa: E402
import dialogue113 as DG         # noqa: E402
import eval113 as EV             # noqa: E402

_ok, _bad = [], []


def check(name, cond, detail=''):
    (_ok if cond else _bad).append(name)
    print('[%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('  ' + detail) if detail else ''))
    return bool(cond)


def _src(fn):
    with io.open(os.path.join(HERE, fn), encoding='utf-8', newline='') as f:
        return f.read()


def baseline_key_sites(node, key='baseline'):
    """找出「拿 `key` 当键去取记录」的所有位置 —— 这才是那个坏模式。

    ★ 第一版只找 `ast.Subscript`（`x['baseline']`），但老代码真实写法是
      `existing_phases(x).get('baseline', {}).get('hard_violations', 0)` ——
      **键是 `.get()` 的第一个参数，不是下标**。那个检测器对老代码永远命中 0 处，
      于是「C5c 已修好」这条判据恒真（比不写还危险）。
      ⇒ 现在两种写法都抓：`.get('baseline'` 与 `['baseline']`。
    """
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript):
            if isinstance(n.slice, ast.Constant) and n.slice.value == key:
                out.append(('subscript', getattr(n, 'lineno', 0)))
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == 'get' and n.args:
                a0 = n.args[0]
                if isinstance(a0, ast.Constant) and a0.value == key:
                    out.append(('get', getattr(n, 'lineno', 0)))
    return out


def main():
    # ---- C1 同一条链 ----
    ev_raw = C.RAW30 if os.path.isdir(C.RAW30) else C.RAW
    check('C1 补训写盘目录 == 评测读盘目录', DG.MAIN_RAW == ev_raw,
          'dialogue=%s / eval=%s' % (os.path.basename(DG.MAIN_RAW), os.path.basename(ev_raw)))

    # ---- C2 main_record 挑对记录 ----
    r = DG.main_record('susie')
    check('C2 main_record 挑到 48 轮那条', bool(r) and r.get('turns_n') == 48,
          'turns_n=%s phase=%s' % (r.get('turns_n') if r else None, r.get('phase') if r else None))

    # ---- C3/C4 判红人数：新口径 vs 旧口径 ----
    ids = [x[:-6] for x in os.listdir(DG.MAIN_RAW) if x.endswith('.jsonl')]
    new_red = [i for i in ids if ((DG.main_record(i) or {}).get('hard_violations') or 0) > 0]
    old_red = [i for i in ids
               if (DG.existing_phases(i).get('baseline', {}).get('hard_violations') or 0) > 0]
    check('C3 新口径筛出判红的人 > 0', len(new_red) > 0, '%d 人' % len(new_red))
    check('C4 [负控制] 旧口径（baseline 键）筛出 0 人', len(old_red) == 0,
          '%d 人 —— 若不为 0 说明 raw30 里真有 baseline 记录，C3 的对照不成立' % len(old_red))
    check('C5a 判红人数 <= 总人数（不虚增）', len(new_red) <= len(ids),
          '%d / %d' % (len(new_red), len(ids)))

    # ---- C5 AST：筛选分支不再用 `xxx['baseline']` 取值，改用 main_record ----
    tree = ast.parse(_src('dialogue113.py'))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == 'main'), None)
    if check('C5b 找到 dialogue113.main（AST 按名字）', fn is not None):
        # ★ 判据要**精确到坏模式**：`phase = 'baseline'` 是 CLI 默认值，**合法**；
        #   坏模式是「拿 'baseline' 当**键**去取某条记录」。判据过宽=误报，同样有害。
        sits = baseline_key_sites(fn)
        calls = {n.func.id for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        check('C5c 不再拿 baseline 当键取记录（AST 下标/.get 两种写法都扫）',
              not sits, '命中 %d 处%s' % (len(sits), ('：%s' % (sits[:3],)) if sits else ''))
        check('C5d 筛选改走 main_record（AST 调用名）', 'main_record' in calls,
              '调用=%s' % sorted(calls & {'main_record', 'existing_phases'}))
        # ★ 负控制：把**修复前那一行原文**喂给同一个检测器，必须命中 —— 否则 C5c 恒真。
        old_line = ("def f(x, existing_phases):\n"
                    "    return existing_phases(x).get('baseline', {}).get('hard_violations', 0) > 0\n")
        hit = baseline_key_sites(ast.parse(old_line))
        check('C5e [负控制] 修复前那一行能被同一检测器抓到（否则 C5c 恒真）',
              bool(hit), '命中 %d 处' % len(hit))

    # ---- C6 转录目录不许覆盖 48 轮 ----
    check('C6 补训转录目录 != transcripts30', os.path.abspath(DG.TR_PATCH) !=
          os.path.abspath(os.path.join(C.EVID, 'transcripts30')),
          DG.TR_PATCH)

    # ---- D：补训必须用与 48 轮同一个 ctx，否则量到的不是同一个角色 ----
    def module_const(fname, cname):
        t = ast.parse(_src(fname))
        for n in t.body:                      # 只看**模块顶层**赋值，别扫进函数里
            if isinstance(n, ast.Assign):
                for tg in n.targets:
                    if isinstance(tg, ast.Name) and tg.id == cname:
                        if isinstance(n.value, ast.Constant):
                            return n.value.value
        return None

    t30_ctx = module_const('train30.py', 'CTX30')
    dl_ctx = module_const('dialogue113.py', 'DIALOG_CTX')
    check('D1a 两个 ctx 常量都存在（AST 取模块顶层赋值）',
          t30_ctx is not None and dl_ctx is not None,
          'train30.CTX30=%s / dialogue113.DIALOG_CTX=%s' % (t30_ctx, dl_ctx))
    check('D1b 补训 ctx == 训练 ctx（不允许各用一套尺子）',
          t30_ctx == dl_ctx and t30_ctx is not None)
    check('D1c 补训 ctx 不等于模块默认 8192（否则长人设必然截断）',
          dl_ctx != C.NUM_CTX, 'NUM_CTX=%d' % C.NUM_CTX)

    # run_conversation 里 C.chat(...) 必须显式带 num_ctx
    t2 = ast.parse(_src('dialogue113.py'))
    rc = next((n for n in ast.walk(t2)
               if isinstance(n, ast.FunctionDef) and n.name == 'run_conversation'), None)
    if check('D2a 找到 run_conversation（AST 按名字）', rc is not None):
        chat_calls = [n for n in ast.walk(rc)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and n.func.attr == 'chat']
        kw = {k.arg for n in chat_calls for k in n.keywords if k.arg}
        check('D2b C.chat 显式传了 num_ctx', 'num_ctx' in kw,
              '实参=%s' % sorted(kw))
        # 负控制：喂一段"没传 num_ctx"的代码，D2b 的判法必须报红
        demo = ast.parse("def g(m):\n    return C.chat(m, seed=1)\n")
        dkw = {k.arg for n in ast.walk(demo) if isinstance(n, ast.Call)
               for k in n.keywords if k.arg}
        check('D2c [负控制] 不传 num_ctx 的写法会被 D2b 判红（否则恒真）',
              'num_ctx' not in dkw)

    # ---- C7 语法 ----
    bad = []
    for fnm in ('common113.py', 'dialogue113.py', 'eval113.py', 'check_ctx113.py',
                'check_patch113t.py'):
        try:
            ast.parse(_src(fnm))
        except SyntaxError as e:
            bad.append('%s: %s' % (fnm, e))
    check('C7 相关模块语法全部可解析（ast.parse，不产 .pyc）', not bad, '; '.join(bad))

    # ---- D3 预热必须用正式 ctx（否则白付一次重载） ----
    for fnm, expect in (('common113.py', 'num_ctx'), ('dialogue113.py', 'num_ctx'),
                        ('train30.py', 'num_ctx')):
        t3 = ast.parse(_src(fnm))
        w = next((n for n in ast.walk(t3)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == 'warmup'), None)
        if w is None:
            check('D3 %s 无 warmup 调用（跳过）' % fnm, True)
            continue
        kw = {k.arg for k in w.keywords if k.arg}
        check('D3 %s 的 warmup 带 ctx 实参' % fnm, expect in kw, '实参=%s' % sorted(kw))

    print()
    print('===== %d PASS / %d FAIL =====' % (len(_ok), len(_bad)))
    return 0 if not _bad else 1


if __name__ == '__main__':
    sys.exit(main())
