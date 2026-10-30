# -*- coding: utf-8 -*-
u"""只列 user 文本 + AskUserQuestion 标记（窄输出，只读）。"""
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
        ts = o.get('timestamp')
        if t == 'message' and o.get('role') == 'user':
            c = o.get('content')
            s = ''
            if isinstance(c, list):
                for it in c:
                    if isinstance(it, dict):
                        s += it.get('text') or ''
            elif isinstance(c, str):
                s = c
            s = s.strip()
            if s and not s.lstrip().startswith('<'):
                print('[%s] L%d USER: %s' % (ts, ln, s[:900].replace('\n', ' | ')))
        elif t == 'function_call':
            s = json.dumps(o.get('providerData'), ensure_ascii=False)
            if 'AskUserQuestion' in s:
                print('[%s] L%d >>> AskUserQuestion 调用' % (ts, ln))
        elif t == 'function_call_result':
            s = json.dumps(o.get('providerData'), ensure_ascii=False)
            if 'toolResult' in s and ('请问 UT' in s or '→' in s and 'spr_' in s):
                i = s.find('toolResult')
                print('[%s] L%d <<< 选项结果: %s' % (ts, ln, s[i:i + 1100]))
