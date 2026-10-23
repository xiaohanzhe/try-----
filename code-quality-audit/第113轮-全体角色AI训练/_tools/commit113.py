# -*- coding: utf-8 -*-
"""第113轮提交 + 推送（**只提交本轮路径，且一个字节都不动用户的暂存区**）

## 为什么不用 `gitpush.py`
它内部是 `git add -A`，会把工作区那 **1017 个"已暂存的删除"**（用户此前的操作，
第101/102轮等历史产物）一起带上。提交那批删除**不可逆**，也不该由一个跑训练的
会话替他决定。

## 为什么也不用 `git reset` + `git add`
`reset` 虽然只动 index、不动工作区，但仍会把用户辛苦攒下的 1017 个暂存删除
**降级成未暂存**。信息不丢，可这属于"没经允许改变用户状态"。
（我自己在上一版就是这么写的 —— 想清楚之后退掉了。）

## 这里走 pathspec 提交
`git commit --only -- <paths>`：只把这些路径的**工作区**内容提交，
index 里其它内容（= 用户的 1017 个删除）原封不动。
唯一需要碰 index 的地方：全新目录（未跟踪）pathspec 匹配不到任何已知文件，
会报 `did not match any file(s)` ⇒ 先 `git add -N`（intent-to-add，只登记路径，
不暂存内容）把新目录"报户口"。

## 零副作用的证据
步骤 [1] 与步骤 [6] 各打印一次暂存区摘要（按状态码分组计数）；
两者**逐字相同**才算"没动过用户的暂存区"。

用法：python commit113.py <msgfile>
"""
import os
import subprocess
import sys
import time

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'

#: 本轮改动（相对仓库根）。
#:
#: ★★★ **刻意不含** `ralsei_pet/src/main.py` / `regress/run_all.py` /
#: `regress/baseline.json` —— 这三个文件的**工作区版本**里夹着用户自己的回退：
#:   · 1017 个已暂存删除（第101~112 轮产物 + `ralsei_pet/assets` 812 个场景素材）；
#:   · main.py 少掉第107/109/112 轮的场景特性（宠物缩放 / 场景过渡 / 门渐显）；
#:   · baseline 从 102 个套件掉到 93 个（check101~112 一并消失）。
#: 方向与用户口径「场景系统有大 bug ⇒ 拿出去做独立兼容项目」一致 ⇒ 那是**他的决定**，
#: 不该由一个跑训练的会话替他提交（删了虽然 git 历史里还能取回，但推送是公开且不可逆的）。
#: 代价（已登记）：远端 main.py 暂不接 `relation=`，远端 SUITES 暂不注册 `check113`。
#: 两者都不影响远端自洽：`build_system_prompt` 的 `relation` 有默认值 `''`，
#: 不传就是第112轮的逐字行为；而 check113 不注册 ⇒ 远端 G2 不会因缺接线报红。
PATHS = [
    '.workbuddy/memory/2026-10-24.md',
    'ralsei_pet/modules/npc_persona.py',
    'ralsei_pet/assets/npc/_relations',
    'ralsei_pet/assets/npc/_training',
    'ralsei_pet/assets/npc/persona',
    'code-quality-audit/第113轮-全体角色AI训练',
    'code-quality-audit/第六轮/verify_round6_fixes.py',
]

DEL_LIMIT = 2000        # 删除行数硬上限（本轮没有任何删除，超了就是路径写错）
BASE = ['-c', 'core.quotepath=false', '-c', 'http.sslBackend=schannel',
        '-c', 'http.schannelCheckRevoke=false', '-c', 'http.version=HTTP/1.1']


def w(msg):
    print(msg, flush=True)


def run(args, timeout=300):
    p = subprocess.run(['git'] + BASE + args, cwd=REPO,
                       capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def index_digest():
    """暂存区摘要：按 porcelain 两位状态码分组计数。"""
    rc, o, e = run(['status', '--porcelain'])
    if rc != 0:
        return None, (o + e).strip()[:200]
    cnt = {}
    for ln in o.splitlines():
        if len(ln) < 3:
            continue
        code = ln[:2]
        cnt[code] = cnt.get(code, 0) + 1
    return cnt, ''


def staged_deletes():
    """**已暂存的删除**（`D `）路径集合 —— 用户那 1017 个就靠这个守。

    ★ 为什么不能拿整个 status 摘要前后比对：我自己提交成功的路径
      会自然从 status 里消失（`M `→`''`、`??`→`''`），那是**提交的应有结果**，
      不是"动了用户的暂存区"。上一版就是这么误报的 —— 判据得盯着
      **唯一该守住的东西**，而不是所有会变的东西。
    """
    rc, o, e = run(['status', '--porcelain'])
    if rc != 0:
        return None
    return {ln[3:] for ln in o.splitlines() if ln[:2] == 'D '}


def fmt_digest(cnt):
    if cnt is None:
        return '(读不到)'
    return ' · '.join('%s=%d' % (k, cnt[k]) for k in sorted(cnt))


def main(argv):
    if not argv:
        w('用法：python commit113.py <msgfile>')
        return 2
    args = [a for a in argv if not a.startswith('--')]
    dry = '--dry' in argv
    if not args:
        w('用法：python commit113.py <msgfile> [--dry]')
        return 2
    msg_file = args[0]
    if not os.path.isfile(msg_file):
        w('!! 提交信息文件不存在：%s' % msg_file)
        return 2

    w('[1] 提交前：已暂存的删除（用户那 1017 条应当原样在这里）')
    before_c, err = index_digest()
    before = staged_deletes()
    w('    status 摘要：' + fmt_digest(before_c) + ('  ' + err if err else ''))
    w('    已暂存删除 %d 条' % (len(before) if before is not None else -1))

    w('[2] 统计本轮改动（工作区 vs HEAD，限定路径）')
    rc, o, e = run(['diff', 'HEAD', '--numstat', '--'] + PATHS)
    adds = dels = files = 0
    pure_del = []
    for ln in o.splitlines():
        parts = ln.split('\t')
        if len(parts) < 3:
            continue
        files += 1
        a, d, path = parts[0], parts[1], parts[2]
        if a.isdigit():
            adds += int(a)
        if d.isdigit():
            dels += int(d)
        if a == '0' and d.isdigit() and int(d) > 0:
            pure_del.append(path)
    rc2, o2, _ = run(['ls-files', '--others', '--exclude-standard', '--'] + PATHS)
    new_files = [x for x in o2.splitlines() if x.strip()]
    w('    已跟踪改动 %d 文件 / +%d / -%d' % (files, adds, dels))
    w('    新增未跟踪 %d 文件' % len(new_files))
    if pure_del:
        w('    !! 有 %d 个纯删除文件（不该出现）：%s' % (len(pure_del), pure_del[:5]))
    if dels > DEL_LIMIT:
        w('!! 删除 %d 行 > %d ⇒ 中止（路径大概率写错）' % (dels, DEL_LIMIT))
        return 3
    if pure_del:
        w('!! 指定路径里有纯删除文件 ⇒ 中止（会误删历史产物）')
        return 3
    if not files and not new_files:
        w('!! 这些路径没有任何改动 ⇒ 没有可提交的内容')
        return 3

    # ★ `git commit --only` 只认**已跟踪**路径：路径下的未跟踪文件必须先用
    #   `git add -N`（intent-to-add：只登记路径，**不暂存内容**）"报户口"。
    #   上一版只对"整条新目录"做 -N，漏掉了落在**已跟踪目录**里的新文件
    #   （`_tools/push113.py` 就这么被漏掉的）⇒ 现在对全部 PATHS 幂等地做一遍。
    if dry:
        w('[DRY] 只做检查，不 add / 不 commit / 不 push')
        return 0
    for p in PATHS:
        rc, o, e = run(['add', '-N', '--', p])
        if rc != 0:
            w('    add -N %-52s rc=%d %s' % (p, rc, e.strip()[:70]))

    w('[3] commit --only（不动 index 里其它内容）')
    rc, o, e = run(['commit', '--only', '-F', msg_file, '--'] + PATHS)
    w('    rc=%d' % rc)
    for ln in (o + e).splitlines()[:14]:
        if ln.strip():
            w('    ' + ln[:170])
    if rc != 0:
        return 4

    rc, local, _ = run(['rev-parse', 'HEAD'])
    local = local.strip()
    w('    HEAD=%s' % local[:12])

    w('[3b] 提交后核验：这条 commit 里到底动了哪些文件（防 --only 夹带用户的删除）')
    rc, o, e = run(['show', '--numstat', '--format=', 'HEAD'])
    c_files = c_del = 0
    c_pure = []
    for ln in o.splitlines():
        parts = ln.split('\t')
        if len(parts) < 3:
            continue
        c_files += 1
        a, d, path = parts[0], parts[1], parts[2]
        if d.isdigit():
            c_del += int(d)
        if a == '0' and d.isdigit() and int(d) > 0:
            c_pure.append(path)
    w('    commit 内 %d 文件 / -%d 行 / 纯删除 %d 个' % (c_files, c_del, len(c_pure)))
    want = files + len(new_files)
    if c_files < want:
        w('    !! 只提交了 %d 个文件，但预期 %d（%d 改动 + %d 新增未跟踪）'
          % (c_files, want, files, len(new_files)))
        w('    !! ⇒ 有未跟踪文件没进 commit（--only 不认未跟踪路径，需 add -N）')
    if c_pure or c_files > 600:
        w('    !! 夹带了不该有的改动：%s' % (c_pure[:5] or '文件数异常'))
        rc2, o2, _ = run(['reset', '--soft', 'HEAD~1'])
        w('    !! 已本地撤销该 commit（reset --soft，工作区与 index 未动）rc=%d' % rc2)
        return 6

    w('[3c] ★ 分叉闸：远端是另一条线就**不推**（推了会覆盖主线）')
    rc, o, e = run(['ls-remote', 'origin', 'refs/heads/main'], timeout=120)
    remote = ''
    for ln in o.splitlines():
        if ln.endswith('refs/heads/main'):
            remote = ln.split()[0]
    if not remote:
        w('    远端读不到（网络/代理） ⇒ 不推，等人工')
        w('=== 结论 = COMMITTED_LOCAL_ONLY（远端不可达）===')
        return 0
    rc, _, _ = run(['merge-base', '--is-ancestor', remote, local])
    if rc != 0:
        rc2, o2, _ = run(['log', '--oneline', '%s..%s' % (local, remote)])
        n = len([x for x in o2.splitlines() if x.strip()])
        w('    远端 main=%s，比本地多 %d 个提交 ⇒ **分叉**' % (remote[:12], n))
        w('    ⇒ 不推送（直接 push 会被 git 拒；强推会覆盖主线成果）')
        w('=== 结论 = COMMITTED_LOCAL_ONLY（分叉，未推送）===')
        return 0
    w('    远端是本地祖先（可快进） ⇒ 继续推送')

    w('[4] push（openssl + HTTP/1.1）')
    rc, o, e = run(['push', 'origin', 'main'], timeout=300)
    w('    rc=%d' % rc)
    for ln in (o + e).splitlines():
        if ln.strip():
            w('    ' + ln[:170])

    w('[5] 独立核验（ls-remote，重试 3 次）')
    remote = ''
    for i in range(3):
        rc, o, e = run(['ls-remote', 'origin', 'refs/heads/main'], timeout=90)
        for ln in o.splitlines():
            if ln.endswith('refs/heads/main'):
                remote = ln.split()[0]
        if remote:
            break
        time.sleep(2)
    w('    remote=%s' % (remote[:12] if remote else '(空)'))
    ok = bool(remote) and remote == local
    w('    远端 == 本地：%s' % ok)

    w('[6] 提交后：已暂存的删除必须**逐条**与 [1] 相同')
    after_c, err = index_digest()
    after = staged_deletes()
    w('    status 摘要：' + fmt_digest(after_c) + ('  ' + err if err else ''))
    w('    已暂存删除 %d 条' % (len(after) if after is not None else -1))
    same = (before == after)
    w('    删除集合与 [1] 相同：%s' % same)
    if not same:
        miss = sorted((before or set()) - (after or set()))[:5]
        extra = sorted((after or set()) - (before or set()))[:5]
        w('    !! 变化：少了 %s / 多了 %s' % (miss, extra))
        w('    !! 请人工核对（git status）')

    w('=== 结论 = %s ===' % ('PUSHED' if (ok and same) else
                             ('PUSHED_BUT_INDEX_CHANGED' if ok else 'NOT_VERIFIED')))
    return 0 if (ok and same) else 5


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
