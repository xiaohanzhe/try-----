# -*- coding: utf-8 -*-
u"""第180轮 · 临时区归档工具（D:\\_tmp → D:\\_archive）。

★ 铁律：**先打包、先验证、再删源**。验证不过就**中止**，一个字节都不删。

两包：
  ZIP_A = D:\\_archive\\第167轮-live取证_<日期>.zip
          live167 里**不在 git** 的件（诊断截图/日志/src 补丁/data），按相对路径保留。
          —— live167 的 2,624 个资产是仓库旧副本，抽查已证明，**不打包**。
  ZIP_B = D:\\_archive\\第163-179轮-临时区_<日期>.zip
          D:\\_tmp 里除 live167 之外的全部（变异备份/回归快照/一次性探针/提交信息）。

验证（三条全过才删）：
  1. `testzip()` 返回 None（无坏条目）
  2. zip 条目数 == 源文件数
  3. zip 各条目 `file_size` 之和 == 源文件 `st_size` 之和

删除：自底向上 `os.remove` + 逐层 `os.rmdir`
（第178轮踩过：`os.rmdir` 只删空目录，且本项目环境的 `rmdir` 被 shim 包过）。

用法：
    python arch180.py          # 只打印计划（dry-run）
    python arch180.py --go     # 真执行（打包 → 验证 → 删源）
"""
import datetime
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
DATE = datetime.datetime.now().strftime('%Y%m%d')

ZIP_A = os.path.join(ARCH, u'第167轮-live取证_%s.zip' % DATE)
ZIP_B = os.path.join(ARCH, u'第163-179轮-临时区_%s.zip' % DATE)


def _long(p):
    u"""Windows 长路径兜底（>240 字符时加扩展前缀）。"""
    p = os.path.abspath(p)
    if len(p) > 240 and not p.startswith('\\\\?\\'):
        return '\\\\?\\' + p
    return p


def _walk_files(root):
    u"""返回 root 下全部文件的绝对路径列表。"""
    out = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            out.append(os.path.join(dp, f))
    return out


def _git_assets():
    u"""仓库 HEAD 里 `ralsei_pet/` 下全部路径（正斜杠、相对仓库根）。"""
    r = subprocess.run(['git', 'ls-files', '-z', '--', 'ralsei_pet'],
                       cwd=REPO, stdout=subprocess.PIPE)
    raw = r.stdout.split(b'\x00')
    return set(x.decode('utf-8', 'surrogateescape') for x in raw if x)


def plan_live():
    u"""live167 里不在 git 的件 ⇒ 需要归档。返回 (归档列表, 冗余列表)。

    ★ 路径要对上两套：`live167\\` 的第一层就是 `ralsei_pet\\`，
    所以相对路径既可能是 `ralsei_pet/assets/x.png`（已经带前缀），
    也可能是 `data/config.json`（不带）。两套都试一次 —— 第一版只拼了前缀，
    结果 2,839 个全部判成"不在 git"（dry-run 当场暴露）。
    """
    tracked = _git_assets()
    keep, redundant = [], []
    for p in _walk_files(LIVE):
        rel = os.path.relpath(p, LIVE).replace(os.sep, '/')
        if rel in tracked or ('ralsei_pet/' + rel) in tracked:
            redundant.append(p)
        else:
            keep.append(p)
    return keep, redundant


def plan_rest():
    u"""D:\\_tmp 下除 live167 之外的全部文件。"""
    out = []
    for name in os.listdir(TMP):
        p = os.path.join(TMP, name)
        if os.path.abspath(p) == os.path.abspath(LIVE):
            continue
        if os.path.isdir(p):
            out.extend(_walk_files(p))
        else:
            out.append(p)
    return out


def _sum_size(paths):
    t = 0
    for p in paths:
        try:
            t += os.path.getsize(_long(p))
        except Exception:
            pass
    return t


def build(zip_path, files, arc_base):
    u"""打包 + 三条验证。返回 (ok, 说明)。"""
    n_src = len(files)
    b_src = _sum_size(files)
    if n_src == 0:
        return True, u'源为空，跳过'
    assert not os.path.exists(zip_path), u'目标 zip 已存在，拒绝覆盖: %s' % zip_path
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in files:
            rel = os.path.relpath(p, arc_base).replace(os.sep, '/')
            zf.write(_long(p), rel)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        bad = zf.testzip()
        n_zip = len(zf.infolist())
        b_zip = sum(i.file_size for i in zf.infolist())
    ok = (bad is None) and (n_zip == n_src) and (b_zip == b_src)
    msg = (u'条目 源=%d zip=%d ｜ 字节 源=%d zip=%d ｜ testzip=%r ｜ zip 体积=%.2f MB'
           % (n_src, n_zip, b_src, b_zip, bad, os.path.getsize(zip_path) / 1048576.0))
    return ok, msg


def rm_tree(root):
    u"""自底向上删除（先 os.remove 每个文件，再逐层 os.rmdir）。返回 (删文件数, 删目录数)。"""
    nf = nd = 0
    for dp, dn, fn in os.walk(root, topdown=False):
        for f in fn:
            os.remove(_long(os.path.join(dp, f)))
            nf += 1
        for d in dn:
            os.rmdir(_long(os.path.join(dp, d)))
            nd += 1
    os.rmdir(_long(root))
    nd += 1
    return nf, nd


def main():
    go = '--go' in sys.argv
    if not os.path.isdir(TMP):
        print(u'源目录不存在：%s' % TMP)
        return 2
    os.makedirs(ARCH, exist_ok=True)

    keep, redundant = plan_live()
    rest = plan_rest()

    print(u'=' * 78)
    print(u'第180轮 临时区归档计划（%s）' % ('执行' if go else 'DRY-RUN，只看不动'))
    print(u'=' * 78)
    print(u'live167  文件总数 = %d' % (len(keep) + len(redundant)))
    print(u'  ├ 不在 git（归档） = %-5d %8.2f MB' % (len(keep), _sum_size(keep) / 1048576.0))
    print(u'  └ 仓库有（删）     = %-5d %8.2f MB' % (len(redundant), _sum_size(redundant) / 1048576.0))
    print(u'其余临时区 文件     = %-5d %8.2f MB' % (len(rest), _sum_size(rest) / 1048576.0))
    print(u'')
    print(u'ZIP_A → %s' % ZIP_A)
    print(u'ZIP_B → %s' % ZIP_B)

    if not go:
        print(u'\n（DRY-RUN：加 --go 才动真格）')
        return 0

    # ---- 包 A（live167 独有件）
    print(u'\n[1] 打包 ZIP_A ...')
    okA, msgA = build(ZIP_A, keep, LIVE)
    print(u'    %s  %s' % (u'OK  ' if okA else u'FAIL', msgA))
    if not okA:
        print(u'!! ZIP_A 验证不过，中止（未删任何东西）')
        return 1

    # ---- 包 B（其余）
    print(u'[2] 打包 ZIP_B ...')
    okB, msgB = build(ZIP_B, rest, TMP)
    print(u'    %s  %s' % (u'OK  ' if okB else u'FAIL', msgB))
    if not okB:
        print(u'!! ZIP_B 验证不过，中止（未删任何东西）')
        return 1

    # ---- 删源
    print(u'[3] 删源（自底向上）')
    nf1, nd1 = rm_tree(LIVE)
    print(u'    live167 删：文件 %d / 目录 %d' % (nf1, nd1))
    left = []
    for name in os.listdir(TMP):
        p = os.path.join(TMP, name)
        n = len(_walk_files(p)) if os.path.isdir(p) else 1
        left.append((name, n))
    for name, n in left:
        p = os.path.join(TMP, name)
        if os.path.isdir(p):
            nf, nd = rm_tree(p)
            print(u'    %-40s 删：文件 %d / 目录 %d' % (name[:40], nf, nd))
        else:
            os.remove(_long(p))
            print(u'    %-40s 删：文件 1' % name[:40])

    rest_after = plan_rest()
    print(u'\n[4] 收口核验')
    print(u'    D:\\_tmp 剩余文件 = %d（应为 0）' % len(rest_after))
    print(u'    ZIP_A=%.2f MB  ZIP_B=%.2f MB'
          % (os.path.getsize(ZIP_A) / 1048576.0, os.path.getsize(ZIP_B) / 1048576.0))
    return 0 if len(rest_after) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
