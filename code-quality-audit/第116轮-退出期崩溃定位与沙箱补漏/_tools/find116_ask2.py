# -*- coding: utf-8 -*-
u"""从 jsonl 里挖含「门贴图选项」的 AskUserQuestion / tool_result（只读）。"""
import io
import json
import os
import re

R = r'C:\Users\23002\.workbuddy\projects'
PAT = re.compile(u'spr_shortcut_door|spr_giantdarkdoor|bg_castle_realdoor|'
                 u'任意门|门框|王座')
rows = []


def walk(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for q in walk(p):
                yield q
        elif name.endswith('.jsonl'):
            yield p


def blobs(o):
    """把一条记录里所有可能的文本抖出来。"""
    out = []
    for k in ('content', 'rawContent', 'providerData', '__codebuddyLocal'):
        v = o.get(k)
        if v is None:
            continue
        out.append(json.dumps(v, ensure_ascii=False))
    return out


for p in walk(R):
    with io.open(p, encoding='utf-8', errors='replace') as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line or 'AskUserQuestion' not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            s = u'\n'.join(blobs(o))
            if PAT.search(s):
                rows.append((os.path.basename(p), ln, o.get('role'),
                             o.get('type'), o.get('timestamp'), s))

print('命中 %d 条' % len(rows))
for base, ln, role, typ, ts, s in rows:
    print('=' * 78)
    print('%s :%d role=%s type=%s ts=%s' % (base, ln, role, typ, ts))
    # 只挑跟门贴图有关的片段
    for m in PAT.finditer(s):
        a = max(0, m.start() - 700)
        b = min(len(s), m.end() + 700)
        print('   ...%s...' % s[a:b].replace('\\n', ' ')[:1600])
        break
