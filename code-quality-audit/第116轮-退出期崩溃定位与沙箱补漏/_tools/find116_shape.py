# -*- coding: utf-8 -*-
u"""看清会话 jsonl 的**真实结构**（只读）。"""
import io
import json
import os
import sys

p = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
with io.open(p, encoding='utf-8', errors='replace') as fh:
    for ln, line in enumerate(fh, 1):
        if ln > n:
            break
        line = line.strip()
        if not line:
            print('%d: <blank>' % ln)
            continue
        try:
            o = json.loads(line)
        except Exception as e:
            print('%d: <json err %r>' % (ln, e))
            continue
        print('--- line %d  type=%r  keys=%s' % (ln, o.get('type'), list(o.keys())))
        m = o.get('message')
        if isinstance(m, dict):
            print('    message.keys=%s role=%r' % (list(m.keys()), m.get('role')))
            c = m.get('content')
            if isinstance(c, list):
                for it in c:
                    if isinstance(it, dict):
                        print('      item.type=%r keys=%s' % (it.get('type'),
                                                              list(it.keys())))
            else:
                print('    content=%r' % (str(c)[:200],))
        else:
            print('    (no message dict)')
