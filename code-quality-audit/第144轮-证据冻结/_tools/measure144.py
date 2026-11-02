# -*- coding: utf-8 -*-
"""第144轮 · 量：`phase138.json` 到底被改过几次、每次都变成了什么、谁在读它。

## 为什么要量

它从第138轮起被登记了三次（141 / 142 / 143），每次的写法都是"登记未修"。
登记三次没修，说明当时没量清"它到底带来多少噪声"。本轮先量，再决定要不要动：

1. **改过几次**：`git log --oneline -- <path>` 的次数 + 每个提交里的四个数
2. **谁在读它**：全仓搜 `phase138.json`，把命中分成「写盘 / 读盘 / 只在文档里提到」
   —— 如果**零个读者**，那它就不是"证据"，是"每轮自动生成的一份快照"，
   停写的风险为零
3. **活计数该去哪**：确认 `regress/_out/` 已被 `.gitignore` 忽略

## 口径

* 只读，不改任何文件（除了把自己量到的写进 `_evidence/lead144.json`）。
* `git log` 用 `-c core.quotepath=false`，中文路径才不会变成转义串。
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')

REL = u'code-quality-audit/\u7b2c138\u8f6e-\u5224\u636e\u8f93\u51fa\u53bb\u65f6\u76f8/_evidence/phase138.json'
AUDIT = u'code-quality-audit'
OUTDIR = u'code-quality-audit/regress/_out'


def _r(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def say(s):
    sys.stdout.write(s + u'\n')


def _git(*args):
    r = subprocess.run([u'git', u'-c', u'core.quotepath=false'] + list(args),
                       cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    return r.stdout.decode('utf-8', 'replace')


def main():
    if not os.path.isdir(EV):
        os.makedirs(EV)
    out = {}

    # ---- 1. 改过几次 + 每次都变成什么
    log = _git('log', '--format=%h %s', '--', REL)
    commits = [l for l in log.split(u'\n') if l.strip()]
    say(u'=== 1. `phase138.json` 的提交史（%d 次）===' % len(commits))
    hist = []
    for l in commits:
        h = l.split(u' ')[0]
        raw = _git('show', u'%s:%s' % (h, REL))
        try:
            d = json.loads(raw)
        except Exception:
            d = {}
        rec = {'commit': h, 'subject': l[len(h) + 1:][:40],
               'files': d.get('files_scanned'), 'calls': d.get('calls_scanned')}
        hist.append(rec)
        say(u'  %s  files=%-5s calls=%-6s  %s'
            % (rec['commit'], rec['files'], rec['calls'], rec['subject']))
    out['history'] = hist
    out['n_commits'] = len(commits)

    # 相邻两次差值（证明"每加套件就变"）
    deltas = []
    for a, b in zip(hist[1:], hist[:-1]):   # log 是新的在前
        if a['files'] is None or b['files'] is None:
            continue
        deltas.append({'commit': b['commit'],
                       'd_files': b['files'] - a['files'],
                       'd_calls': (b['calls'] or 0) - (a['calls'] or 0)})
    say(u'')
    say(u'  逐次增量（旧 → 新）：')
    for d in deltas:
        say(u'    %s  +%d 文件 / +%d 调用' % (d['commit'], d['d_files'], d['d_calls']))
    out['deltas'] = deltas

    # ---- 2. 谁在读它
    say(u'')
    say(u'=== 2. 全仓谁提到 `phase138.json` ===')
    hits = {'write': [], 'read': [], 'doc': []}
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, AUDIT)):
        dirnames[:] = [d for d in dirnames if d not in ('_out', '__pycache__')]
        for fn in filenames:
            if not fn.endswith(u'.py'):
                continue
            p = os.path.join(dirpath, fn)
            try:
                src = _r(p)
            except Exception:
                continue
            if u'phase138' not in src:
                continue
            rel = os.path.relpath(p, ROOT)
            for ln in src.split(u'\n'):
                if u'phase138' not in ln:
                    continue
                if u"'w'" in ln or u'"w"' in ln:
                    hits['write'].append({'file': rel, 'line': ln.strip()[:90]})
                elif u'open(' in ln or u'json.loads' in ln:
                    hits['read'].append({'file': rel, 'line': ln.strip()[:90]})
                else:
                    hits['doc'].append({'file': rel, 'line': ln.strip()[:90]})
    for k, label in ((u'write', u'写盘'), (u'read', u'读盘'), (u'doc', u'其他提及')):
        say(u'  %s：%d 处' % (label, len(hits[k])))
        for x in hits[k][:6]:
            say(u'    %s | %s' % (x['file'], x['line']))
    out['refs'] = hits
    out['n_readers'] = len(hits['read'])

    # ---- 3. _out 是否被忽略
    gi = _r(os.path.join(ROOT, '.gitignore'))
    ignored = [l for l in gi.split(u'\n') if l.strip().endswith(u'_out/')]
    say(u'')
    say(u'=== 3. `.gitignore` 里的 `_out/` ===')
    for l in ignored:
        say(u'  %s' % l.strip())
    out['gitignore_out'] = ignored
    out['out_ignored'] = bool(ignored)

    # 冻结后的目标内容（check144 会逐字钉住这几个数）
    cur = json.loads(_r(os.path.join(ROOT, REL)))
    out['frozen'] = {'files_scanned': cur.get('files_scanned'),
                     'calls_scanned': cur.get('calls_scanned'),
                     'bad_lineno': cur.get('bad_lineno'),
                     'bad_size': cur.get('bad_size')}
    say(u'')
    say(u'=== 4. 本轮冻结成什么 ===')
    say(u'  %s' % json.dumps(out['frozen'], ensure_ascii=False))

    p = os.path.join(EV, 'lead144.json')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    say(u'')
    say(u'写盘：%s' % os.path.relpath(p, ROOT))


if __name__ == '__main__':
    main()
