# -*- coding: utf-8 -*-
u"""打印指定 jsonl 的指定行（完整 JSON，只读）。用法：dump_lines.py <jsonl> <a> <b> [kw]"""
import io
import json
import sys

p = sys.argv[1]
a = int(sys.argv[2])
b = int(sys.argv[3])
kw = sys.argv[4] if len(sys.argv) > 4 else None

with io.open(p, encoding='utf-8', errors='replace') as fh:
    for ln, line in enumerate(fh, 1):
        if ln < a:
            continue
        if ln > b:
            break
        line = line.strip()
        if not line:
            continue
        if kw and kw not in line:
            print('%d  <不含关键字>' % ln)
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        print('#' * 78)
        print('# line %d  type=%s role=%s' % (ln, o.get('type'), o.get('role')))
        for k in ('content', 'rawContent', 'providerData', '__codebuddyLocal', 'meta'):
            if k in o:
                s = json.dumps(o[k], ensure_ascii=False)
                print('  [%s] %s' % (k, s[:4000]))
