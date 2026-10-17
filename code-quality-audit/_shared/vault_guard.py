# -*- coding: utf-8 -*-
u"""vault_guard.py —— 用户记忆库（`E:\\RalseiMemory\\`）**完整性硬尺子**。

为什么必须要有这个东西
----------------------
  第115轮发现：真机录制脚本里**只有 `rec114.py` 有沙箱**，`rec96/105/106/107/
  109~113/90/97/98/99` 全都是**裸跑** ⇒ 它们运行时直接读写用户真实的角色记忆库。
  而 `replay115.py` 头部却写着"各 rec*.py 自带沙箱（不碰用户角色记忆）"。
  ⇒ 光靠"脚本自称沙箱"是**恒真判据**（看着在守，其实没守）。
  ⇒ 必须有一把**外部的、可独立复核的**尺子：跑前拍指纹、跑后比对指纹。

用法
----
  # 1) 拍基线（写 JSON）
  python vault_guard.py snap E:\\Download\\_tmp\\vault_before.json
  # 2) 跑被测脚本
  # 3) 比对（有差异则**非零退出**，并把差异表打到 stdout）
  python vault_guard.py diff E:\\Download\\_tmp\\vault_before.json

选项
----
  --root <dir>      记忆库根（默认 E:\\RalseiMemory）
  --ignore <sub>    相对路径**前缀**，命中则该文件不参与比对（可重复）。
                    例：`--ignore logs/`（日志本来就该长）
  --quiet           只打一行结论

退出码
------
  snap : 0 成功 / 2 参数错 / 3 根不可用 **或扫描出错或扫到 0 个文件**
  diff : 0 完全一致 / 1 有差异 / 2 参数错 / 3 根不可用（含基线为空 / 扫描失败）
"""
import hashlib
import io
import json
import os
import sys
import time

DEFAULT_ROOT = r'E:\RalseiMemory'
CHUNK = 1 << 20


def _say(s):
    sys.stdout.write(s + '\n')
    sys.stdout.flush()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _scan(root, ignores):
    u"""扫描根目录 ⇒ `(files, errs)`。

    · 根目录不存在 ⇒ `(None, [...])`
    · `errs` **非空**表示扫描过程出过错（本轮新增：原来 `os.walk` 默认让
      `onerror=None` **静默吞掉**目录读取错误）。

    ★★★ 第116轮修掉的**真漏洞（假绿）**：E 盘有瞬时 `Errno 22` 的毛病，
      那一刻 `os.walk` 会**安安静静地 yield 出 0 项** ⇒ 旧版据此写出
      "0 个文件的快照"并 `rc=0`；之后 `diff` 就会说
      「一致 ✓ 0 个文件全部未变」—— **一次真实的清空会被完全掩盖**。
      本轮实测复现：同一目录 `ls` 有 79 个文件，`snap` 却报 0 个。
      ⇒ 现在把 `errs` 带出来，由调用方（`main`）升级成硬失败。
    """
    out = {}
    errs = []
    if not os.path.isdir(root):
        return None, ['根目录不可用: %s' % root]

    def _onerr(e):
        errs.append('%r' % (e,))

    for dp, dn, fn in os.walk(root, onerror=_onerr):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace('\\', '/')
            if any(rel.startswith(ig) for ig in ignores):
                continue
            try:
                st = os.stat(p)
            except Exception as e:
                out[rel] = ['ERR', repr(e), 0]
                errs.append('stat %s: %r' % (rel, e))
                continue
            try:
                h = _sha256(p)
            except Exception as e:
                h = 'ERR:%r' % (e,)
                errs.append('sha %s: %r' % (rel, e))
            out[rel] = [st.st_size, int(st.st_mtime_ns), h]
    return out, errs


def snapshot(root=DEFAULT_ROOT, ignores=()):
    u"""公开接口：拍当前指纹（rel -> [size, mtime_ns, sha256]）。

    ★ 返回 `None` 的三种情形：根目录不可用 / **扫描到 0 个文件** / 扫描出错。
      **宁可不给结论，也不给一个"看起来一切正常"的空指纹** —— 后者是本文件
      存在的意义的反面（见 `_scan` 的假绿说明）。
    """
    files, errs = _scan(root, list(ignores))
    if files is None or errs or not files:
        return None
    return files


def compare(base_files, cur_files):
    u"""公开接口：比对两份指纹。

    返回 `(added, removed, changed)`；三者都空 = 完全一致。
    """
    added = sorted(set(cur_files) - set(base_files))
    removed = sorted(set(base_files) - set(cur_files))
    changed = []
    for k in sorted(set(base_files) & set(cur_files)):
        if base_files[k] != cur_files[k]:
            changed.append((k, base_files[k], cur_files[k]))
    return added, removed, changed


def _parse(argv):
    root = DEFAULT_ROOT
    ignores = []
    pos = []
    quiet = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--root':
            i += 1
            root = argv[i]
        elif a == '--ignore':
            i += 1
            ignores.append(argv[i].replace('\\', '/'))
        elif a == '--quiet':
            quiet = True
        else:
            pos.append(a)
        i += 1
    return root, ignores, pos, quiet


def main(argv):
    if not argv:
        _say(__doc__)
        return 2
    cmd = argv[0]
    root, ignores, pos, quiet = _parse(argv[1:])
    if not pos:
        _say('缺 JSON 路径')
        return 2
    jp = pos[0]

    cur, errs = _scan(root, ignores)
    if cur is None:
        _say('[vault_guard] 根目录不可用: %s' % root)
        return 3
    # ★★★ 第116轮两道硬闸（都是"把假绿变成响亮的红"）：
    if errs:
        _say('[vault_guard] ★ 扫描出错 %d 条，**拒绝给出任何结论**：' % len(errs))
        for e in errs[:10]:
            _say('    %s' % e)
        if len(errs) > 10:
            _say('    ...（其余 %d 条略）' % (len(errs) - 10))
        return 3
    if not cur:
        _say('[vault_guard] ★ 扫描到 **0 个文件** ⇒ 判为**扫描失败**'
             u'（本库恒有文件；0 个更可能是 E 盘瞬时故障，不当成"空库"）')
        return 3

    if cmd == 'snap':
        payload = {
            'root': root,
            'ignores': ignores,
            'taken_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'files': cur,
        }
        with io.open(jp, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, indent=1,
                                sort_keys=True))
        _say('[vault_guard] 快照已写 %s（%d 个文件，root=%s）'
             % (jp, len(cur), root))
        return 0

    if cmd == 'diff':
        with io.open(jp, encoding='utf-8') as fh:
            base = json.load(fh)
        b = base['files']
        # ★ 基线自己也得过闸：一条 0 文件的基线是一切"一致"的温床
        if not b:
            _say('[vault_guard] ★ 基线 %s 里**没有文件** ⇒ 基线不可用，'
                 u'不能据此判"一致"' % jp)
            return 3
        added, removed, changed = compare(b, cur)
        total = len(added) + len(removed) + len(changed)
        if total == 0:
            _say('[vault_guard] 一致 ✓  %d 个文件全部未变（root=%s）'
                 % (len(cur), root))
            return 0
        if not quiet:
            _say('[vault_guard] ★ 有差异 %d 处（基线 %s，root=%s）'
                 % (total, base.get('taken_at'), root))
            for k in added[:60]:
                _say('  + 新增  %s  (%d B)' % (k, cur[k][0]))
            for k in removed[:60]:
                _say('  - 消失  %s  (%d B)' % (k, b[k][0]))
            for k, o, n in changed[:60]:
                tag = []
                if o[0] != n[0]:
                    tag.append('size %s->%s' % (o[0], n[0]))
                if o[2] != n[2]:
                    tag.append('hash %s..->%s..' % (o[2][:8], n[2][:8]))
                if o[1] != n[1]:
                    tag.append('mtime')
                _say('  ~ 变化  %s  [%s]' % (k, ', '.join(tag)))
            if total > 60:
                _say('  ...（其余 %d 处略）' % (total - 60))
        else:
            _say('[vault_guard] ★ 有差异 %d 处' % total)
        return 1

    _say('未知命令: %s（只认 snap / diff）' % cmd)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
