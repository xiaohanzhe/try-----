# -*- coding: utf-8 -*-
"""第113轮i · 训练产物的备份/恢复（为了跑一次「12 轮重训验证」而不污染主产物）。

为什么需要
----------
`train30.py` 的两条写盘路径对**重跑单角色**都不友好：
  · `append_jsonl(RAW30/<id>.jsonl)` —— **追加**，同一个人会留两条记录（旧 48 轮 + 新 12 轮）；
  · `write_text(TR30/<id>.md)` —— **覆盖**，transcript 只剩最后一次。
⇒ 直接用 `--only --turns 12 --force` 会污染 `check113 D 段`（raw/transcript/corpus/报告
四者要对得上），而且这两个目录**都已入库**（291 个文件）。

所以验证流程固定成三步：备份 → 跑 → 恢复。本脚本只做 1 和 3，且**用 sha256 自证**：
恢复后逐个比对备份时的哈希，不一致直接报红 —— 不许"看起来恢复了"。

用法
----
    python bkp_train113i.py backup hy_guardener hy_axis
    python bkp_train113i.py restore
    python bkp_train113i.py status
"""
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EVID = os.path.join(ROUND, '_evidence')

#: 备份落点**绝不能在工作区**（`git add -A` 会把它当新增文件提交）。
#: 用户口径：下载/临时默认 E 盘，`E:\\Download\\_tmp\\` 用后即删。
#: ★ E 盘会**瞬时失效**（`OSError [WinError 1] 函数不正确`，实测十几分钟后自愈；
#:   2026-10-25 本轮又撞了一次）。所以按 **E > D > 系统 temp** 逐个试写，不许一撞就终止。
_BKP_CANDIDATES = (
    r'E:\Download\_tmp\train30_bkp_113i',
    r'D:\_tmp\train30_bkp_113i',
    os.path.join(os.environ.get('TEMP') or os.environ.get('TMP') or '.',
                 'train30_bkp_113i'),
)
BKP = None
MANIFEST = None


def pick_root():
    """按候选顺序找一个**真能写**的目录（建目录 + 落探针文件再删）。"""
    for d in _BKP_CANDIDATES:
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, '.w')
            with io.open(probe, 'w', encoding='utf-8') as fh:
                fh.write('x')
            os.remove(probe)
            return d
        except OSError as e:
            print('  [跳过] %s —— %s' % (d, e))
    raise SystemExit('FAIL: 三个候选落点都写不了，先修盘再跑')

REL_DIRS = ('raw30', 'transcripts30')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def do_backup(ids):
    if not ids:
        print('用法：bkp_train113i.py backup <id> [<id> ...]')
        return 2
    if os.path.isdir(BKP):
        print('注意：备份目录已存在，先清掉旧备份再备（避免把上一轮当基准）')
        shutil.rmtree(BKP)
    os.makedirs(BKP)
    items = []
    for nid in ids:
        for rel in (os.path.join('raw30', nid + '.jsonl'),
                    os.path.join('transcripts30', nid + '.md')):
            src = os.path.join(EVID, rel)
            if not os.path.isfile(src):
                print('  [缺] %s（首次训练？跳过）' % rel)
                items.append({'rel': rel, 'exists': False})
                continue
            dst = os.path.join(BKP, rel.replace(os.sep, '__'))
            shutil.copy2(src, dst)
            rec = {'rel': rel, 'exists': True, 'bytes': os.path.getsize(src),
                   'sha256': sha(src), 'name': os.path.basename(dst)}
            items.append(rec)
            print('  [备] %-34s %8d B  %s' % (rel, rec['bytes'], rec['sha256'][:12]))
    with io.open(MANIFEST, 'w', encoding='utf-8') as fh:
        json.dump({'ids': ids, 'items': items}, fh, ensure_ascii=False, indent=1)
    print('清单 → %s（%d 项）' % (MANIFEST, len(items)))
    return 0


def do_restore():
    if not os.path.isfile(MANIFEST):
        print('FAIL: 没有清单，无法恢复 —— %s' % MANIFEST)
        return 3
    man = json.load(io.open(MANIFEST, encoding='utf-8'))
    bad = []
    for it in man['items']:
        dst = os.path.join(EVID, it['rel'])
        if not it.get('exists'):
            # 原本不存在 ⇒ 恢复 = 删掉这次新生成的（只删我们自己造的，别的文件不碰）
            if os.path.isfile(dst):
                os.remove(dst)
                print('  [清] %s（原本不存在）' % it['rel'])
            continue
        src = os.path.join(BKP, it['name'])
        if not os.path.isfile(src):
            bad.append('%s（备份文件丢了）' % it['rel'])
            continue
        shutil.copy2(src, dst)
        got = sha(dst)
        ok = (got == it['sha256'])
        print('  [复] %-34s %s' % (it['rel'], 'OK' if ok else 'HASH-MISMATCH %s' % got[:12]))
        if not ok:
            bad.append(it['rel'])
    print()
    print('恢复后逐文件回验：%s' % ('全部一致' if not bad else '不一致 %r' % (bad,)))
    return 0 if not bad else 3


def do_status():
    if not os.path.isfile(MANIFEST):
        print('没有备份清单')
        return 0
    man = json.load(io.open(MANIFEST, encoding='utf-8'))
    for it in man['items']:
        dst = os.path.join(EVID, it['rel'])
        cur = sha(dst) if os.path.isfile(dst) else None
        print('  %-34s 备份=%s 现值=%s %s'
              % (it['rel'], (it.get('sha256') or '-')[:12], (cur or '-')[:12],
                 '一致' if cur == it.get('sha256') else '**已被改动**'))
    return 0


def main(argv):
    global BKP, MANIFEST
    BKP = pick_root()
    MANIFEST = os.path.join(BKP, '_manifest.json')
    print('备份落点 = %s' % BKP)
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == 'backup':
        return do_backup(argv[1:])
    if cmd == 'restore':
        return do_restore()
    if cmd == 'status':
        return do_status()
    print('未知命令 %r' % cmd)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
