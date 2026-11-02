# -*- coding: utf-8 -*-
"""第144轮回归锁：`phase138.json` 冻结 —— 会自己变的历史证据不能拿来对账。

## 病

`check138.py` 每次运行都往 `第138轮/_evidence/phase138.json` 写一份
`{files_scanned, calls_scanned}`。这两个数**必然随套件数变化**：

| 提交 | files | calls | 增量 |
|---|---|---|---|
| 第138轮 | 137 | 6120 | —— |
| 第139轮 | 138 | 6158 | +1 / +38 |
| 第140轮 | 139 | 6198 | +1 / +40 |
| 第141轮 | 140 | 6228 | +1 / +30 |
| 第142轮 | 141 | 6246 | +1 / +18 |
| 第143轮 | 142 | 6274 | +1 / +28 |

**+N 正好是那一轮新加的判据条数** ⇒ 这个文件里没有任何"信息"，它只是
"套件清单的长度"的一个回声。后果：每轮 commit 都捎带一个语义无关的改动。

## 三条依据（都来自 `measure144.py`）

1. **改过 6 次**，且每次 `+1 文件 / +本轮判据数` ⇒ 纯机械漂移；
2. **读盘 0 处** —— 全仓没有任何脚本读它（只有 `recheck1xx` 的写盘白名单里提到路径）
   ⇒ 停写的风险为零；
3. `code-quality-audit/regress/_out/` 已在 `.gitignore` 里 ⇒ 活计数有地方放。

## 改法

`check138.py` 改成写 `regress/_out/phase138.live.json`（不入库）；
`_evidence/phase138.json` 冻在第138轮那份（137 / 6120），加 `_note` 说明来历。

⇒ **证据冻结在仓库里，活计数留在工作区外。**

## 本套件守什么

A 冻结面：四个数逐字等于常量 · `_note` 在 · `check138` 不再写它 · 写的是 live 文件
  · `.gitignore` 忽略 `_out/`
B 机制面（AST）：全仓**零处**写盘到 `phase138.json` · 扫描面没塌
  · 解码失败被跳过的文件**逐个记名 + 字节级兜底**（静默 `continue` 会让"没扫到"
    和"扫过且干净"长得一样）
  · `check138` 要写出的键集 == 冻结文件键集（**静态读源码**，不读 `_out` 的运行产物：
    否则"判据条数"会随'谁先跑过 check138'在 16/17 之间跳，基线立刻漂）
C 连带登记：`eval113.merge_patches` **保留旧键**、两边都有时走 `merge_text` 求并集
  ⇒「重跑训练会把 ① 塞回 `ralsei`」是**条件成立的**，所以 `check139 A1` 不能删
D 自检
E 证据在盘上
F 自检收口（`check(` 处数 vs 实跑条数；**必须最后一条**，否则被后面的判据顶成假红）
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
AUDIT = os.path.join(ROOT, 'code-quality-audit')
EV = os.path.join(ROUND, '_evidence')
FROZEN = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_evidence',
                      'phase138.json')
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools',
                        'check138.py')
LIVE = os.path.join(AUDIT, 'regress', '_out', 'phase138.live.json')
EVAL113 = os.path.join(AUDIT, u'第113轮-全体角色AI训练', '_tools', 'eval113.py')

#: 第138轮首次落盘时的值（`git show 46288e2b:…` 逐字）
FROZEN_VALS = {'files_scanned': 137, 'calls_scanned': 6120,
               'bad_lineno': 0, 'bad_size': 0}

_n = {'p': 0, 'f': 0, 'skip': 0}
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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write_targets(src):
    """AST 取出所有 `open(..., 'w')` 的**第一个实参源码片段**。

    ★ 为什么不用纯文本扫：注释里到处都在提 `phase138.json`（本轮加的那段说明
      自己就提了 5 次），纯文本扫会把注释算成写盘 —— 这类误报本仓踩过八次。
    """
    tree = ast.parse(src)
    out = []
    for nd in ast.walk(tree):
        if not isinstance(nd, ast.Call):
            continue
        name = getattr(nd.func, 'attr', None) or getattr(nd.func, 'id', None)
        if name != 'open' or not nd.args:
            continue
        modes = [a.value for a in nd.args[1:]
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not any(u'w' in m for m in modes):
            continue
        out.append(ast.get_source_segment(src, nd.args[0]) or u'')
    return out


def main():
    # ======================================================================
    head(u'A · 冻结面（这一份证据钉死在 138 轮）')

    fr = json.loads(_read(FROZEN))
    got = dict((k, fr.get(k)) for k in FROZEN_VALS)
    check(u'A1 `phase138.json` 四个数逐字等于 138 轮那份（137 / 6120 / 0 / 0）',
          got == FROZEN_VALS, json.dumps(got, ensure_ascii=False))
    note = fr.get(u'_note') or u''
    check(u'A2 有 `_note` 说明来历，且写明"冻结"与替代去处',
          bool(note) and u'冻结' in note and u'phase138.live.json' in note)

    c138 = _read(CHECK138)
    tg = _write_targets(c138)
    check(u'A3 `check138.py` 里**没有**写盘指向 `_evidence/phase138.json`',
          not [t for t in tg if u'phase138.json' in t],
          u'写盘点 %d 个' % len(tg))
    check(u'A4 `check138.py` 改成写 `phase138.live.json`，且落在 `regress/_out`',
          any(u'phase138.live.json' in t for t in tg)
          and u"_out" in c138,
          u'写盘点 %s' % (u' | '.join(t[:34] for t in tg) or u'无'))

    gi = _read(os.path.join(ROOT, '.gitignore'))
    check(u'A5 `.gitignore` 忽略了 `code-quality-audit/regress/_out/`',
          any(l.strip() == u'code-quality-audit/regress/_out/'
              for l in gi.split(u'\n')))

    # ======================================================================
    head(u'B · 机制面（全仓没有第二处写它）')

    offenders = []
    # ★ 跳过的文件必须**逐个记名**并打印：静默 `continue` 会让"有一个文件根本没被
    #   扫到"看起来和"扫过且干净"一模一样 —— 这正是本仓栽过多次的假绿形状。
    skipped = []
    scanned = [0]
    for dirpath, dirnames, filenames in os.walk(AUDIT):
        dirnames[:] = [d for d in dirnames if d not in ('_out', '__pycache__')]
        for fn in filenames:
            if not fn.endswith(u'.py'):
                continue
            p = os.path.join(dirpath, fn)
            if p == os.path.abspath(__file__):
                continue
            try:
                tgts = _write_targets(_read(p))
            except (SyntaxError, UnicodeDecodeError, IOError) as e:
                skipped.append(u'%s (%s)' % (os.path.relpath(p, ROOT),
                                            type(e).__name__))
                continue
            scanned[0] += 1
            for t in tgts:
                if u'phase138.json' in t:
                    offenders.append(os.path.relpath(p, ROOT))
    # ★★★ 这里**不许**打印"扫到多少个文件"：仓里每轮都会加脚本，那个数就是时相量，
    #   打进输出就变成每轮必 DIFF（第138轮那条口径）。跳过的文件是**名单**，稳定。
    for s in skipped:
        print(u'  [SKIP] %s' % s)
    check(u'B1 全仓**零处**脚本写盘到 `phase138.json`（漂移源已断）',
          not offenders, u'命中 %s' % (u', '.join(set(offenders)) or u'无'))
    # 扫描面本身也要守：若哪天 os.walk 面塌成个位数，B1 会"全绿但什么都没看"
    check(u'B1b 扫描面没塌（可解析 .py ≥ 100 个）', scanned[0] >= 100,
          u'闸门=≥100')
    # ★ 被跳过的那几个不能就这么算了：做一次**字节级**兜底。
    #   `phase138.json` 若在这些文件里**一次都没出现过**，那它绝不可能写它 ——
    #   这个方向是安全的单向证明（不区分代码/注释只会误报，不会漏报）。
    smelly = []
    for dp, dn, fns in os.walk(AUDIT):
        dn[:] = [d for d in dn if d not in ('_out', '__pycache__')]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, ROOT)
            if not any(rel in s for s in skipped):
                continue
            with io.open(p, 'rb') as f:
                if b'phase138.json' in f.read():
                    smelly.append(rel)
    check(u'B1c 被跳过的文件里字节级也**没提过** `phase138.json`', not smelly,
          u'提及 %s' % (u', '.join(smelly) or u'无'))

    # B2：**静态**读 `check138.py` 里 `_ev` 那个字典字面量的键。
    # ★ 为什么不去比对 `_out/phase138.live.json`：那个文件在**新克隆的机器上不存在**，
    #   "有没有它"取决于谁先跑过 check138 ⇒ 判据条数会在 16/17 之间跳，基线立刻漂。
    #   "判据条数随环境变"本身就是缺陷。静态读源码是确定的，而且更直接：
    #   写什么，就看源码里写了什么。
    ev_keys = []
    for nd in ast.walk(ast.parse(c138)):
        if not isinstance(nd, ast.Assign) or not isinstance(nd.value, ast.Dict):
            continue
        if any(isinstance(t, ast.Name) and t.id == '_ev' for t in nd.targets):
            ev_keys = [k.value for k in nd.value.keys
                       if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    check(u'B2 `check138.py` 要写出的键集 == 冻结文件的键集（静态对，不看运行产物）',
          set(ev_keys) == set(FROZEN_VALS),
          u'源码键=%s' % (u','.join(sorted(ev_keys)) or u'没找到'))
    # ★ live 只是参考，**连"在不在"都不打印**：B2 是静态判据，与它无关；
    #   而"在不在"取决于谁先跑过 check138 ⇒ 打出来又变成一个会变的输出行
    #   （本套件首跑就是这么自己制造了一次 DIFF：live 现值 142/6274 → 143/6291）。
    print(u'  [INFO] `_out/phase138.live.json` 只是活计数的出口：不作判据、不打印值')

    # ======================================================================
    head(u'C · 连带登记：`merge_patches` 为什么不能"反正是重建"就放心')

    ev_src = _read(EVAL113)
    fn = None
    for nd in ast.walk(ast.parse(ev_src)):
        if isinstance(nd, ast.FunctionDef) and nd.name == 'merge_patches':
            fn = nd
    check(u'C1 找到了 `eval113.merge_patches`', fn is not None)
    body_src = ast.get_source_segment(ev_src, fn) if fn else u''
    # "只有旧键 ⇒ 保留旧" 那个分支（`k not in new` 且取 `old[k]`）
    check(u'C2 它有「只有旧键 ⇒ 保留旧补丁」分支（`k not in new` → `old[k]`）',
          u'k not in new' in body_src and u'old[k]' in body_src)
    check(u'C3 两边都有时走 `merge_text` 求并集（不是覆盖）',
          u'merge_text(' in body_src)
    # 结论：重跑 evaluate ⇒ new 里又有 ① ⇒ 并集把 ① 带回来 ⇒ check139 A1 不能删
    c139 = os.path.join(AUDIT, u'第139轮-patch与人设去重', '_tools', 'check139.py')
    check(u'C4 「重建会把 ① 塞回」的兜底（`check139 A1`）仍在盘上',
          os.path.isfile(c139) and u'A1' in _read(c139))

    # ======================================================================
    head(u'D · 自检')

    tree = ast.parse(_read(os.path.abspath(__file__)))
    calls = [nd for nd in ast.walk(tree)
             if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
             and nd.func.id == 'check']
    marker = '[' + 'PASS]'
    leak = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and marker in sub.value:
                leak.append(1)
    check(u'D1 ★判据描述里没有那个计数标记的字面量（会顶高 run_all 的 PASS 计数）',
          not leak, u'命中 %d 处' % len(leak))
    trues = []
    for nd in calls:
        if len(nd.args) >= 2 and isinstance(nd.args[1], ast.Constant) \
                and nd.args[1].value is True:
            trues.append(1)
    check(u'D2 没有 `check(描述, True)` 这种恒真判据', not trues,
          u'命中 %d 处' % len(trues))

    # ======================================================================
    head(u'E · 证据')

    check(u'E1 `lead144.json`（提交史 + 读者统计）在盘上',
          os.path.isfile(os.path.join(EV, 'lead144.json')))

    # ======================================================================
    head(u'F · 自检收口（必须放在最后一条）')

    # ★ 这一条必须最后跑：它比的是"源码里写了多少处 check("与"真的跑了多少条"。
    #   -1 = 它自己还没执行；-skip = B2 那种显式 no-op 分支（打印了但没跑）。
    #   放在中间就会被后面还没执行的判据顶成假红（本套件第一次跑就是这么红的）。
    n_all = len(calls)
    n_ran = _n['p'] + _n['f']
    check(u'F1 源码里的 check( 处数 == 实跑条数 + 自己 + 显式 no-op 数',
          n_all - n_ran == 1 + _n['skip'],
          u'calls=%d ran=%d skip=%d' % (n_all, n_ran, _n['skip']))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
