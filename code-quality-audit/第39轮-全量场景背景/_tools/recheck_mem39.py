# -*- coding: utf-8 -*-
"""
第 39 轮 · 记忆文件**逐令牌回验**（改过重要核心文件的必做项）。

判据：把 HEAD（上一次提交）里的速查本抽成"可检索令牌"集合，
逐个在当前速查本 **或** 详版里找一次。找不到的列出来人工判定：
是真丢了（要补回），还是"本轮有意更新了数值/表述"。
"""
import io, os, re, subprocess, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
QUICK = '.workbuddy/memory/MEMORY.md'
DETAIL = '.workbuddy/memory/参考-契约与历轮（详版）.md'
REL = '.workbuddy/memory/MEMORY.md'


def git_show(rev, path):
    p = subprocess.run(['git', 'show', '%s:%s' % (rev, path)], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode('utf-8')


old = git_show('HEAD', REL)
new = io.open(os.path.join(REPO, QUICK), encoding='utf-8').read()
det = io.open(os.path.join(REPO, DETAIL), encoding='utf-8').read()
print('HEAD 速查本 %d 字符 ｜ 现速查本 %d 字符 ｜ 详版 %d 字符'
      % (len(old), len(new), len(det)))

# 令牌 = 反引号里的片段 + 十六进制短串 + 形如 1,013 / 25,000 / 320×240 的数字
TOK = re.compile(r'`([^`\n]{2,60})`|\b([0-9a-f]{7})\b')
tokens = {}
for m in TOK.finditer(old):
    t = (m.group(1) or m.group(2) or '').strip()
    if not t or len(t) < 3:
        continue
    tokens[t] = tokens.get(t, 0) + 1
print('从 HEAD 抽出令牌 %d 个' % len(tokens))

missing_quick, missing_both = [], []
for t in sorted(tokens):
    in_new = t in new
    in_det = t in det
    if not in_new and not in_det:
        missing_both.append(t)
    elif not in_new:
        missing_quick.append(t)

print('')
print('=' * 74)
print('A. 速查本与详版**都没有**的令牌（最需要人工判定）')
print('=' * 74)
for t in missing_both:
    print('   %s' % t)
print('   共 %d 个' % len(missing_both))

print('')
print('=' * 74)
print('B. 速查本没了、但详版还有（下沉，可接受）')
print('=' * 74)
for t in missing_quick:
    print('   %s' % t)
print('   共 %d 个' % len(missing_quick))

print('')
print('=' * 74)
print('C. 本轮**新增**的关键令牌是否都在（正向核验）')
print('=' * 74)
NEW = ['1547', 'bg_round39', '原件', 'bg_source', 'bg_asset', 'room.bg_layer',
       'bg_common', 'classify', '原作房间背景溯源', '689', '320×240',
       'dump_rooms.csx', 'xscale', 'tiled', 'Q1', '瓦片还原', '选层',
       '真背景', '逼近', '逐行替换']
bad = []
for t in NEW:
    if t == '原件' or t == '逼近':
        continue
    ok = (t in new) or (t in det)
    if not ok:
        bad.append(t)
    print('   %-24s 速查=%s 详版=%s %s' % (t, t in new, t in det, '' if ok else '❗'))
print('   缺 %d 个' % len(bad))
