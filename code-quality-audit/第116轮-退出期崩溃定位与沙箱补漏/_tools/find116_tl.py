# -*- coding: utf-8 -*-
u"""按时间序列出某 jsonl 区间内的 user/assistant 文本（只读）。"""
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
            if s:
                print('[%s] L%d USER: %s' % (ts, ln, s[:700].replace('\n', ' | ')))
        elif t == 'message' and o.get('role') == 'assistant':
            c = o.get('content')
            s = ''
            if isinstance(c, list):
                for it in c:
                    if isinstance(it, dict) and it.get('type') == 'output_text':
                        s += it.get('text') or ''
            elif isinstance(c, str):
                s = c
            s = s.strip()
            if s:
                print('[%s] L%d AI  : %s' % (ts, ln, s[:400].replace('\n', ' | ')))
        elif t == 'function_call':
            s = json.dumps(o.get('providerData'), ensure_ascii=False)
            if 'AskUserQuestion' in s:
                print('[%s] L%d >>> AskUserQuestion' % (ts, ln))
        elif t == 'function_call_result':
            s = json.dumps(o.get('providerData'), ensure_ascii=False)
            if 'toolResult' in s and ('spr_' in s or '请问' in s or '推荐' in s):
                i = s.find('toolResult')
                print('[%s] L%d <<< RESULT: %s' % (ts, ln, s[i:i + 1200]))
