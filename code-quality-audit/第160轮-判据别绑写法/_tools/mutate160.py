# -*- coding: utf-8 -*-
u"""第160轮负控制：**破坏判据本身**，断言 `check160` 恰好变红。

## 为什么负控制要打在判据上

这一轮改的不是产品，是**判据**。所以"负控制"也必须换靶子：
把 `recheck159_core.py` 里那三个判定函数改**窄/改宽**，看 `check160` 认不认得出。

★ 纪律：
  · 一处破坏 = 一个**单一**改动；
  · 破坏**不许**把套件炸掉（保持语法完整、返回类型不变）；
  · 还原必须**字节级**（sha1 比对）；
  · 收口（Z1）必须再跑一次全绿；Z2 指纹必须与开工前一致。

用法：
    python mutate160.py            # 按 EXPECT 断言
    python mutate160.py --dry      # 只打印实际红了哪些（用于写 EXPECT）
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RECHECK = os.path.join(ROOT, 'code-quality-audit',
                       u'第159轮-空白名字不算人', '_tools', 'recheck159_core.py')
CHECK = os.path.join(HERE, 'check160.py')
PY = sys.executable


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def _sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


MUTATIONS = [
    ('M1', u'`_strip_cmp` 退化成"**只要有 `.strip()` 调用就算**"（不看是不是比较）',
     u"""    for n in ast.walk(fn):
        if isinstance(n, ast.Compare):
            sides = [n.left] + list(n.comparators)
            has_strip = any(isinstance(x, ast.Call)
                            and isinstance(x.func, ast.Attribute)
                            and x.func.attr == 'strip' for x in sides)
            has_name = any(isinstance(x, ast.Name) and x.id == name for x in sides)
            if has_strip and has_name:
                out.append(n)""",
     u"""    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \\
                and n.func.attr == 'strip':
            out.append(n)""",
     ('A4', 'A8')),

    ('M2', u'`_not_guard` 退化成"**只要提到这个名字就算**"（不看 `not` 判据）',
     u"""    for n in ast.walk(fn):
        if isinstance(n, ast.If):
            for x in ast.walk(n.test):
                if isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not) \\
                        and isinstance(x.operand, ast.Name) and x.operand.id == name:
                    out.append(n)
                    break""",
     u"""    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and n.id == name:
            out.append(n)""",
     ('A5', 'A8')),

    ('M3', u'`_what_norm` 的 test 判据退化成 `has_test = True`（死分支也认）',
     u"""            has_test = any(isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not)
                           and isinstance(x.operand, ast.Call)
                           and isinstance(x.operand.func, ast.Attribute)
                           and x.operand.func.attr == 'strip'
                           for x in ast.walk(n.test))""",
     u"""            has_test = True""",
     # 实得：退化成"见到 what 赋值就算归一"后，样本里**两个分支**都被算进来
     # ⇒ A6（在位样本数到 2）与 A7（死分支也被认）一起红。同一条判据的两个观测面。
     ('A6', 'A7')),

    ('M4', u'白名单 `_ALLOWED` 清空（真判据变"任何产品改动都不许"）',
     u"_ALLOWED = ('ralsei_pet/modules/npc_errand.py', 'ralsei_pet/src/main.py')",
     u"_ALLOWED = ()",
     ('B7',)),

    ('M5', u'`H1a` 退回**相等比较**（绑死时相：一提交就假红）',
     u"""check(u'H1a 产品侧**没有第三个文件**被改（只可能是这两个；已提交时为空也算过）',
      not _extra, u'产品改动=%r 多出来的=%r' % (_prod, _extra))""",
     u"""check(u'H1a 产品侧**没有第三个文件**被改（只可能是这两个；已提交时为空也算过）',
      _prod == list(_ALLOWED), u'产品改动=%r 多出来的=%r' % (_prod, _extra))""",
     ('B2', 'B3')),
]


def run_check():
    p = subprocess.Popen([PY, CHECK], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode('utf-8', 'replace')
    reds = []
    for line in out.splitlines():
        if line.startswith('[FAIL] '):
            reds.append(line[7:].split()[0])
    return p.returncode, sorted(set(reds)), out


def main():
    dry = '--dry' in sys.argv
    base = _read(RECHECK)
    base_sha = _sha(base)
    print(u'基线 sha1: recheck159_core=%s' % (base_sha[:12],))
    n_bad = 0
    for name, desc, old, new, expect in MUTATIONS:
        if base.count(old) != 1:
            print(u'[FAIL] %s 锚点出现 %d 次：%s' % (name, base.count(old), desc))
            n_bad += 1
            continue
        _write(RECHECK, base.replace(old, new))
        try:
            rc, reds, out = run_check()
        finally:
            _write(RECHECK, base)
            if _sha(_read(RECHECK)) != base_sha:
                print(u'[FAIL] %s 还原失败（sha1 不一致）' % (name,))
                return 1
        if dry:
            print(u'%s %s ⇒ 红：%s（rc=%d）'
                  % (name, desc, u' '.join(reds) or u'（无！）', rc))
            continue
        ok = (rc != 0) and reds == sorted(expect)
        if not ok:
            n_bad += 1
        print(u'%s %s %s ⇒ 红：%s%s'
              % (u'[PASS]' if ok else u'[FAIL]', name, desc,
                 u' '.join(reds) or u'（无！）',
                 u'' if ok else (u'    期望：%s' % (u' '.join(sorted(expect)),))))
    if dry:
        print(u'')
        print(u'mutate160（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check160 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    z2 = (_sha(_read(RECHECK)) == base_sha)
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时 `recheck159_core.py` 的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate160：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
