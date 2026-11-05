# -*- coding: utf-8 -*-
"""从本地会话历史里捞"用户对桌宠基础行为"的原话。

为什么：用户说「基础桌宠还有一些问题」但没列举。历史会话（JSONL）里有他的
原话，比我猜有用。只读，不改任何东西。
"""
import os
import io
import json
import re

ROOT = r"C:\Users\23002\.workbuddy\projects\c-Users-23002-Desktop-项目文件夹-try - 副本"
KEYS = [u'桌宠', u'拉尔塞', u'ralsei']
HINTS = [u'问题', u'毛病', u'不对', u'奇怪', u'卡', u'看不见', u'动不了', u'拖',
         u'甩', u'掉', u'穿', u'挡', u'置顶', u'托盘', u'气泡', u'缩放', u'双屏',
         u'多屏', u'崩', u'没反应', u'丢了', u'找不到', u'太慢', u'占', u'糊']

files = [f for f in os.listdir(ROOT) if f.endswith('.jsonl')]
print('[INFO] 会话文件 %d 个' % len(files), flush=True)

hits = []
for fn in files:
    p = os.path.join(ROOT, fn)
    try:
        with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line or '"user"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                msg = d.get('message') or d
                role = msg.get('role') or d.get('role')
                if role != 'user':
                    continue
                c = msg.get('content')
                if isinstance(c, list):
                    txt = ' '.join(x.get('text', '') for x in c
                                   if isinstance(x, dict))
                elif isinstance(c, str):
                    txt = c
                else:
                    continue
                txt = txt.strip()
                if not txt or len(txt) > 400:
                    continue
                if txt.startswith('<') or '<user_info>' in txt:
                    continue          # 注入的系统提醒，不是用户原话
                if u'<user_query>' in txt:
                    txt = re.sub(r'</?user_query>', '', txt).strip()
                low = txt
                if any(k in low for k in KEYS) and any(h in low for h in HINTS):
                    hits.append((d.get('timestamp', ''), fn, ln, txt.replace('\n', ' / ')))
    except Exception as e:
        print('[WARN] 读 %s 失败: %s' % (fn, e), flush=True)

print('[INFO] 命中 %d 条' % len(hits), flush=True)
seen = set()
for ts, fn, ln, txt in hits:
    key = txt[:60]
    if key in seen:
        continue
    seen.add(key)
    print(u'\n--- %s  %s:%d\n%s' % (ts[:19], fn[:24], ln, txt[:300]), flush=True)
