# -*- coding: utf-8 -*-
"""第90轮：把 G2 的每一个 DIFF 做**字段级**归因（sha256 / pass 哪一项不一致）。

为什么必须做：
  `run_all.py` 的 DIFF 判据是三项合取 ——
      old['sha256'] == now['sha256'] and old['exit'] == now['exit'] and old['pass'] == now['pass']
  所以「DIFF」这一个词背后可能是三种完全不同的事：
    ① 输出文本真的变了（sha 变）→ 可能是真回归；
    ② 只有 PASS 计数变了（sha 不变）→ 说明基线里**记账字段**与文本自相矛盾；
    ③ 只有 exit 变了。
  另外 `write_diff()` 是用来**给人看**的，它把当前文本与
  `_out/<id>.baseline.txt` 比（那是 `--update` 时留下的副本），
  **不是**与 `baseline.json` 里那条记录所对应的文本比 ——
  两个文件一旦不同步，`write_diff` 就会写出"(归一化文本相同，仅计数/退出码不同)"
  这种**误导性**提示（第90轮 check81 实测踩到）。

  本脚本绕开 `write_diff`，直接用 `baseline.json` 的 sha256 重算，逐一归因。
  只读，不改任何东西。
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REGRESS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'code-quality-audit', 'regress'))
OUT_DIR = os.path.join(REGRESS, '_out')
BASELINE = os.path.join(REGRESS, 'baseline.json')

sys.path.insert(0, REGRESS)
import run_all as R  # noqa: E402

assert R.OUT_DIR == OUT_DIR, (R.OUT_DIR, OUT_DIR)
assert R.BASELINE == BASELINE, (R.BASELINE, BASELINE)


def sha(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def main():
    base = json.load(open(BASELINE, encoding='utf-8'))
    suites = base.get('suites', {})
    ids = [s['id'] for s in R.SUITES]
    missing_txt = [i for i in ids if not os.path.exists(os.path.join(OUT_DIR, i + '.txt'))]
    only_sha, only_pass, both, ok, nobase = [], [], [], [], []
    rows = []
    for sid in ids:
        p = os.path.join(OUT_DIR, sid + '.txt')
        if not os.path.exists(p):
            continue
        raw = open(p, encoding='utf-8', errors='replace').read()
        norm = R.normalize(raw)
        n_pass, n_fail = R.count_results(raw)
        cur_sha = sha(norm)
        old = suites.get(sid)
        if old is None:
            nobase.append(sid)
            rows.append((sid, '-', '-', '-', 'NO-BASELINE', n_pass, n_fail))
            continue
        d_sha = old.get('sha256') != cur_sha
        d_pass = old.get('pass') != n_pass
        d_fail = old.get('fail') != n_fail
        if not (d_sha or d_pass or d_fail):
            ok.append(sid)
            verdict = 'IDENTICAL'
        else:
            parts = []
            if d_sha:
                parts.append('sha')
            if d_pass:
                parts.append('pass')
            if d_fail:
                parts.append('fail')
            verdict = 'DIFF:' + '+'.join(parts)
            if d_sha and not d_pass and not d_fail:
                only_sha.append(sid)
            elif d_pass and not d_sha:
                only_pass.append(sid)
            elif d_sha and (d_pass or d_fail):
                both.append(sid)
            else:
                only_pass.append(sid)
        rows.append((sid, str(old.get('pass')), str(n_pass), str(n_fail), verdict,
                     old.get('sha256', '')[:12], cur_sha[:12]))

    print('=' * 78)
    print('G2 字段级归因  （共 %d 个套件；磁盘无输出 %d 个）' % (len(ids), len(missing_txt)))
    print('=' * 78)
    print('%-16s %-6s %-6s %-5s %-18s %-13s %s' % ('suite', 'base', 'now', 'fail', 'verdict', 'sha_old', 'sha_new'))
    print('-' * 78)
    for r in rows:
        sid, bp, np_, nf, v, so, sn = r
        if v == 'IDENTICAL':
            continue
        print('%-16s %-6s %-6s %-5s %-18s %-13s %s' % (sid, bp, np_, nf, v, so, sn))
    print('-' * 78)
    print('IDENTICAL : %d' % len(ok))
    print('DIFF 总数 : %d' % (len(only_sha) + len(only_pass) + len(both)))
    print('  ├ 只 sha 变（文本真变了）           : %d  %s' % (len(only_sha), only_sha))
    print('  ├ 只 pass 变（记账与文本自相矛盾）  : %d  %s' % (len(only_pass), only_pass))
    print('  └ sha+pass 都变                     : %d  %s' % (len(both), both))
    if nobase:
        print('基线里没有的套件: %s' % nobase)
    if missing_txt:
        print('★ 磁盘上没有输出（会被 run_all 判 SKIP/无基线）: %s' % missing_txt)

    # —— 附：所有 DIFF 套件里，哪一行的差异是「归一化后仍然不同」的 —— #
    print()
    print('=' * 78)
    print('逐个 DIFF 套件：直接拿 baseline.json 对应的旧文本行做对比')
    print('  ※ 旧文本只有 `_out/<id>.baseline.txt` 这一份副本；')
    print('    它若与 baseline.json 的 sha 对不上，说明**这份副本是陈旧的**。')
    print('=' * 78)
    for sid in only_sha + only_pass + both:
        old = suites.get(sid)
        bp = os.path.join(OUT_DIR, sid + '.baseline.txt')
        line = '%-16s' % sid
        if os.path.exists(bp):
            on = R.normalize(open(bp, encoding='utf-8', errors='replace').read())
            same = (sha(on) == old.get('sha256'))
            line += ' baseline.txt 与 baseline.json %s' % ('一致' if same else '★ 不一致（副本陈旧）')
        else:
            line += ' 无 baseline.txt 副本'
        print(line)


if __name__ == '__main__':
    main()
