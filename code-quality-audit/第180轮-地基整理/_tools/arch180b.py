# -*- coding: utf-8 -*-
u"""第180轮 · 归档收尾（幂等版）：先**逐文件**证明"该留的都在包里"，再删。

背景：`arch180.py --go` 被执行了**两次**（沙箱升级重跑）——
第一次建好两个 zip 并开始删源，第二次撞 `assert not exists(zip)` 崩掉。
⇒ 破坏性脚本**必须幂等**：已存在的包先当作"候选证据"来校验，而不是直接拒绝。

三条判据（全过才删）：
  V1  live167 现存文件 ⊆ （ZIP_A 条目 ∪ git 跟踪集）   —— 独有件一个不缺
  V2  D:\\_tmp 其余现存文件 ⊆ ZIP_B 条目                —— 其它件一个不缺
  V3  两个 zip 的 `testzip()` 都是 None
删除：自底向上 `os.remove` + 逐层 `os.rmdir`。

用法：
    python arch180b.py          # 只核验（dry-run）
    python arch180b.py --go     # 核验 → 删源
"""
import io
import os
import subprocess
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

TMP = r'D:\_tmp'
ARCH = r'D:\_archive'
LIVE = os.path.join(TMP, 'live167')
ZIP_A = os.path.join(ARCH, u'第167轮-live取证_20261109.zip')
ZIP_B = os.path.join(ARCH, u'第163-179轮-临时区_20261109.zip')


def _long(p):
    p = os.path.abspath(p)
    if len(p) > 240 and not p.startswith('\\\\?\\'):
        return '\\\\?\\' + p
    return p


def _walk_files(root):
    out = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            out.append(os.path.join(dp, f))
    return out


def _git_assets():
    r = subprocess.run(['git', 'ls-files', '-z', '--', 'ralsei_pet'],
                       cwd=REPO, stdout=subprocess.PIPE)
    return set(x.decode('utf-8', 'surrogateescape') for x in r.stdout.split(b'\x00') if x)


def _zip_names(p):
    with zipfile.ZipFile(p, 'r') as zf:
        return set(i.filename for i in zf.infolist()), zf.testzip()


def rm_tree(root):
    nf = nd = 0
    for dp, dn, fn in os.walk(root, topdown=False):
        for f in fn:
            os.remove(_long(os.path.join(dp, f)))
            nf += 1
        for d in dn:
            os.rmdir(_long(os.path.join(dp, d)))
            nd += 1
    os.rmdir(_long(root))
    return nf, nd + 1


def main():
    go = '--go' in sys.argv
    for p in (ZIP_A, ZIP_B):
        if not os.path.exists(p):
            print(u'缺少归档包，先跑 arch180.py：%s' % p)
            return 2

    namesA, badA = _zip_names(ZIP_A)
    namesB, badB = _zip_names(ZIP_B)
    tracked = _git_assets()

    # ---- V1：live167 现存文件必须"在 ZIP_A 里"或"在 git 里"
    live = _walk_files(LIVE) if os.path.isdir(LIVE) else []
    missA = []
    for p in live:
        rel = os.path.relpath(p, LIVE).replace(os.sep, '/')
        if rel in namesA or rel in tracked or ('ralsei_pet/' + rel) in tracked:
            continue
        missA.append(rel)

    # ---- V2：其余现存文件必须在 ZIP_B 里
    rest = []
    for name in os.listdir(TMP):
        p = os.path.join(TMP, name)
        if os.path.abspath(p) == os.path.abspath(LIVE):
            continue
        rest.extend(_walk_files(p) if os.path.isdir(p) else [p])
    missB = []
    for p in rest:
        rel = os.path.relpath(p, TMP).replace(os.sep, '/')
        if rel not in namesB:
            missB.append(rel)

    print(u'=' * 78)
    print(u'第180轮 归档核验（%s）' % (u'核验后删除' if go else u'DRY-RUN'))
    print(u'=' * 78)
    print(u'ZIP_A 条目=%-5d testzip=%-5r   live167 现存=%-5d 未覆盖=%d'
          % (len(namesA), badA, len(live), len(missA)))
    print(u'ZIP_B 条目=%-5d testzip=%-5r   其余现存  =%-5d 未覆盖=%d'
          % (len(namesB), badB, len(rest), len(missB)))
    for r in missA[:20]:
        print(u'  A 缺：%s' % r)
    for r in missB[:20]:
        print(u'  B 缺：%s' % r)

    ok = (badA is None) and (badB is None) and not missA and not missB
    print(u'\n判据：V1 独有件全覆盖=%s ｜ V2 其它件全覆盖=%s ｜ V3 testzip 干净=%s'
          % (u'✔' if not missA else u'✘', u'✔' if not missB else u'✘',
             u'✔' if (badA is None and badB is None) else u'✘'))
    if not ok:
        print(u'!! 有未覆盖的源文件，**不删任何东西**')
        return 1

    if not go:
        print(u'\n（DRY-RUN：加 --go 才删源）')
        return 0

    print(u'\n[删] 自底向上')
    if os.path.isdir(LIVE):
        nf, nd = rm_tree(LIVE)
        print(u'  live167           删：文件 %-5d 目录 %d' % (nf, nd))
    for name in list(os.listdir(TMP)):
        p = os.path.join(TMP, name)
        if os.path.isdir(p):
            nf, nd = rm_tree(p)
            print(u'  %-34s 删：文件 %-5d 目录 %d' % (name[:34], nf, nd))
        else:
            os.remove(_long(p))
            print(u'  %-34s 删：文件 1' % name[:34])

    left = []
    for name in os.listdir(TMP):
        p = os.path.join(TMP, name)
        left.extend(_walk_files(p) if os.path.isdir(p) else [p])
    print(u'\n收口：D:\\_tmp 剩余文件 = %d（应为 0）' % len(left))
    return 0 if not left else 1


if __name__ == '__main__':
    sys.exit(main())
