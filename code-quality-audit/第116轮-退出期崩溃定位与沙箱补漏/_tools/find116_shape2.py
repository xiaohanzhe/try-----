# -*- coding: utf-8 -*-
u"""看清 assistant 消息里的**工具调用**长什么样（只读）。"""
import io
import json
import sys

p = sys.argv[1]
a = int(sys.argv[2])
b = int(sys.argv[3])
with io.open(p, encoding='utf-8', errors='replace') as fh:
    for ln, line in enumerate(fh, 1):
        if ln < a:
            continue
        if ln > b:
            break
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = o.get('type')
        if t not in ('message', 'reasoning'):
            continue
        role = o.get('role')
        c = o.get('content')
        kinds = []
        if isinstance(c, list):
            for it in c:
                if isinstance(it, dict):
                    kinds.append(it.get('type'))
        print('%d type=%s role=%s content_kinds=%r' % (ln, t, role, kinds))
        if role == 'assistant' and isinstance(c, list):
            for it in c:
                if isinstance(it, dict) and it.get('type') == 'tool_use':
                    print('    TOOL %s  input=%s' % (
                        it.get('name'),
                        json.dumps(it.get('input'), ensure_ascii=False)[:1800]))
