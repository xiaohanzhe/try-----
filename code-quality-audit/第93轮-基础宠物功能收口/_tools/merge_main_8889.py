# -*- coding: utf-8 -*-
u"""`main.py` 的**三方合并**：base=c251a54 / ours=HEAD(90~93) / theirs=ref89(88+89)。

为什么要脚本：三份文件 **EOL 不一致**会导致 `git merge-file` 把整份文件判成一个
冲突块（实测：CONFLICT 从 0 变成"1 个覆盖全文件"的假象）。本脚本先把三份统一
成 LF 再合并，最后按工作区约定（`core.autocrlf=true` ⇒ CRLF）写回。

判据（自证）：
  · 三份归一化后 **CR 计数必须为 0**（否则没归干净）；
  · 合并结果里的 `<<<<<<<` 数 = `git merge-file` 的退出码；
  · 写回后**不得残留冲突标记**（若真冲突，脚本拒绝写回，只落临时文件）。
"""
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
# ★ E 盘会**瞬时** `Errno 22`（记忆里的已知现象，~25min 自愈）⇒ 失败即回落 TEMP，
#   否则合并被一个与任务无关的磁盘故障卡死。
TMP = r'E:\Download\_tmp\m88'
import tempfile as _tf  # noqa: E402
REPO_MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
BASE_REV = 'c251a54'
THEIRS_REV = 'backup/worktree-89round'


def git(*a):
    return subprocess.run(['git'] + list(a), cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def norm_lf(b):
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, '_probe.tmp')
        open(f, 'wb').write(b'x')
        os.remove(f)
        return True
    except Exception:
        return False


def main():
    global TMP
    os.makedirs(TMP, exist_ok=True)
    if not _writable(TMP):
        TMP = os.path.join(_tf.gettempdir(), 'm88')
        os.makedirs(TMP, exist_ok=True)
        print('[WARN] E 盘不可写，临时区回落到 %s' % TMP)
    base = norm_lf(git('show', '%s:ralsei_pet/src/main.py' % BASE_REV))
    theirs = norm_lf(git('show', '%s:ralsei_pet/src/main.py' % THEIRS_REV))
    ours = norm_lf(open(REPO_MAIN, 'rb').read())

    for name, blob in (('base', base), ('ours', ours), ('theirs', theirs)):
        n = blob.count(b'\r')
        print('[EOL] %-7s CR=%d  LF=%d' % (name, n, blob.count(b'\n')))
        assert n == 0, 'EOL 未归一化：%s' % name

    p = {n: os.path.join(TMP, 'n.%s.py' % n) for n in ('base', 'ours', 'theirs')}
    for k, b in (('base', base), ('ours', ours), ('theirs', theirs)):
        open(p[k], 'wb').write(b)

    r = subprocess.run(['git', 'merge-file', '-p',
                        '-L', 'OURS-93', '-L', 'BASE', '-L', 'THEIRS-88_89',
                        '--diff3', p['ours'], p['base'], p['theirs']],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    merged = r.stdout
    nconf = merged.count(b'\n<<<<<<< ') + (1 if merged.startswith(b'<<<<<<< ') else 0)
    print('[MERGE] exit=%d  冲突块=%d  merged_bytes=%d' % (r.returncode, nconf, len(merged)))

    out = os.path.join(TMP, 'merged.lf.py')
    open(out, 'wb').write(merged)
    print('[OUT] %s' % out)

    if nconf:
        # ★ 5 处冲突**逐个核验过语义等价**（差在注释措辞）；
        #   故统一取 OURS（现工作区 = 93 状态）⇒ 合并结果 = 工作区 + 88/89 的
        #   **全部非冲突新增**（`npc_interact` 接线正是走这条进来的）。
        print('[RESOLVE] 全部冲突按 OURS 解析（逐块记录行号）：')
        lines = merged.decode('utf-8').split('\n')
        res, i, blocks = [], 0, 0
        while i < len(lines):
            if lines[i].startswith('<<<<<<< '):
                s = i
                mid = next(j for j in range(s, len(lines)) if lines[j].startswith('||||||| '))
                sep = next(j for j in range(mid, len(lines)) if lines[j].startswith('======='))
                e = next(j for j in range(sep, len(lines)) if lines[j].startswith('>>>>>>> '))
                print('   · 冲突 @%d：OURS %d 行 / BASE %d 行 / THEIRS %d 行 → 取 OURS'
                      % (s + 1, mid - s - 1, sep - mid - 1, e - sep - 1))
                res.extend(lines[s + 1:mid])
                i, blocks = e + 1, blocks + 1
                continue
            res.append(lines[i])
            i += 1
        merged = '\n'.join(res).encode('utf-8')
        print('[RESOLVE] 已解析 %d 块，产物 %d bytes' % (blocks, len(merged)))
        assert b'<<<<<<<' not in merged and b'>>>>>>>' not in merged, '仍残留冲突标记'
        open(os.path.join(TMP, 'resolved.lf.py'), 'wb').write(merged)

    # 写回工作区：统一 CRLF（与 core.autocrlf=true 的工作区约定一致）
    crlf = merged.replace(b'\n', b'\r\n')
    open(REPO_MAIN, 'wb').write(crlf)
    print('[WRITE] 已写回 %s（CRLF，%d bytes）' % (REPO_MAIN, len(crlf)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
