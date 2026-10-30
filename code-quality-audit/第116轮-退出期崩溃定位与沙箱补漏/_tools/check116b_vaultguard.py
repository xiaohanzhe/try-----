# -*- coding: utf-8 -*-
u"""check116b_vaultguard.py —— `vault_guard` 的**正/负控制**（第116轮）。

为什么必须单独有这一支
----------------------
本轮实测抓到 `vault_guard.py` 自己的**假绿**：E 盘瞬时故障时 `os.walk`
**静默 yield 0 项** ⇒ 写出"0 个文件的快照"且 `rc=0` ⇒ 之后 `diff` 会报
「一致 ✓ 0 个文件全部未变」——**一次真实的清空会被完全掩盖**。
（复现证据：同一目录 `ls` 有 79 个文件，`snap` 却报 0 个，rc=0。）

⇒ 结论：**"尺子自己也会说谎"**，所以尺子本身必须有正/负控制，
   而且判据必须落在**退出码与落盘事实**上，不是落在"它说 OK"。

判据
----
  N1 空目录 ⇒ `snap` **rc=3**（不许把"扫到 0 个文件"当成功）
  N2 空目录 ⇒ `snap` **不许写出快照文件**
  N3 空目录 ⇒ `diff` rc=3
  N4 基线 `files=={}` ⇒ `diff` rc=3（"空基线"不能成为一切一致的理由）
  N5 根不存在 ⇒ `snap` rc=3 + 明确"不可用"字样
  P1 真库 ⇒ `snap` rc=0，且 JSON 里的条数 == 独立 `os.walk` 数出的条数
  P2 真库 ⇒ `diff` 自比对 rc=0（负控制：静态 ⇒ 必须"一致"）
  P3 **正控制**：在临时库里**真改一个文件** ⇒ `diff` rc=1，且差异表含该文件名
  P4 **正控制**：在临时库里**真加 / 真删** 各一个文件 ⇒ `diff` rc=1，两侧都报出
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.abspath(os.path.join(HERE, '..', '..', '_shared'))
VG = os.path.join(SHARED, 'vault_guard.py')
PY = sys.executable
REAL = r'E:\RalseiMemory'

_RES = []


def check(name, cond, detail=''):
    _RES.append((bool(cond), name))
    sys.stdout.write('[%s] %s%s\n'
                     % ('PASS' if cond else 'FAIL', name,
                        ('  -- ' + detail) if detail else ''))
    sys.stdout.flush()


def run(args):
    p = subprocess.run([PY, VG] + args, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def _mk(d, files):
    for rel, data in files.items():
        fp = os.path.join(d, rel)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, 'wb') as fh:
            fh.write(data)


def main():
    tmp = tempfile.mkdtemp(prefix='vgtest116_')
    try:
        empty = os.path.join(tmp, 'empty')
        os.makedirs(empty)
        j1 = os.path.join(tmp, 'empty_snap.json')

        # N1 / N2
        rc, out = run(['snap', j1, '--root', empty, '--quiet'])
        check('N1 空目录 ⇒ snap rc=3（0 文件判为扫描失败）', rc == 3,
              'rc=%d out=%r' % (rc, out.strip()[:90]))
        check('N2 空目录 ⇒ 不许写出快照文件', not os.path.exists(j1),
              'exists=%s' % os.path.exists(j1))
        # N3
        rc3, out3 = run(['diff', j1, '--root', empty, '--quiet'])
        check('N3 空目录 ⇒ diff rc=3', rc3 == 3, 'rc=%d' % rc3)
        # N4
        jbad = os.path.join(tmp, 'bad_base.json')
        with io.open(jbad, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps({'root': empty, 'files': {}}, ensure_ascii=False))
        rc4, out4 = run(['diff', jbad, '--root', empty, '--quiet'])
        check('N4 空基线 ⇒ diff rc=3（基线自己也要过闸）', rc4 == 3, 'rc=%d' % rc4)
        # N5
        rc5, out5 = run(['snap', os.path.join(tmp, 'x.json'),
                         '--root', os.path.join(tmp, 'nope'), '--quiet'])
        check('N5 根不存在 ⇒ snap rc=3', rc5 == 3, 'rc=%d' % rc5)

        # P1 真库
        if os.path.isdir(REAL):
            jr = os.path.join(tmp, 'real.json')
            rc6, out6 = run(['snap', jr, '--root', REAL, '--quiet'])
            n_walk = 0
            for _dp, _dn, _fn in os.walk(REAL):
                n_walk += len(_fn)
            n_json = -1
            if os.path.exists(jr):
                with io.open(jr, encoding='utf-8') as fh:
                    n_json = len(json.load(fh).get('files') or {})
            check('P1 真库 ⇒ snap rc=0 且条数 == 独立 os.walk 数',
                  rc6 == 0 and n_json == n_walk and n_walk > 0,
                  'rc=%d json=%d walk=%d' % (rc6, n_json, n_walk))
            # P2
            rc7, _ = run(['diff', jr, '--root', REAL, '--quiet'])
            check('P2 真库静态 ⇒ diff rc=0（负控制：必须"一致"）', rc7 == 0,
                  'rc=%d' % rc7)

        # P3 / P4 正控制（临时库，绝不动真库）
        lab = os.path.join(tmp, 'lab')
        _mk(lab, {'a.txt': b'AAA', 'sub/b.txt': b'BBB'})
        jl = os.path.join(tmp, 'lab.json')
        rc8, _ = run(['snap', jl, '--root', lab, '--quiet'])
        check('P3a 临时库 ⇒ snap rc=0（2 个文件）', rc8 == 0, 'rc=%d' % rc8)
        with open(os.path.join(lab, 'a.txt'), 'wb') as fh:
            fh.write(b'ZZZZ')
        rc9, out9 = run(['diff', jl, '--root', lab])
        check('P3b 真改一个文件 ⇒ diff rc=1 且报出 a.txt',
              rc9 == 1 and 'a.txt' in out9, 'rc=%d hit=%s' % (rc9, 'a.txt' in out9))
        # 加 / 删
        _mk(lab, {'c.txt': b'CCC'})
        os.remove(os.path.join(lab, 'sub', 'b.txt'))
        rc10, out10 = run(['diff', jl, '--root', lab])
        check('P4 真加+真删 ⇒ diff rc=1 且两侧都报出',
              rc10 == 1 and 'c.txt' in out10 and 'sub/b.txt' in out10,
              'rc=%d' % rc10)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [n for ok, n in _RES if not ok]
    sys.stdout.write('\n合计：PASS=%d FAIL=%d\n'
                     % (len(_RES) - len(bad), len(bad)))
    if bad:
        sys.stdout.write('FAIL 列表：%s\n' % bad)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
