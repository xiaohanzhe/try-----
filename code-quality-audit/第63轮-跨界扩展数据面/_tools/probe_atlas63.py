# -*- coding: utf-8 -*-
u"""侦察：outertale 图集 json 的真实 schema（我先前按 Aseprite 假设是错的）。"""
import io
import json
import os

WWW = u'E:\\Download\\_extract61\\outertale\\www'
for n in (u'AYAYA-CLoY7mWt.json', u'toriel-' + u'', u'CORE-DtkqgNq-.json'):
    pass

names = sorted(f for f in os.listdir(WWW) if f.endswith(u'.json'))
for n in names[:3]:
    d = json.loads(io.open(os.path.join(WWW, n), 'rb').read().decode('utf-8'))
    print(u'== %s  top-level=%r' % (n, list(d.keys())))
    print(json.dumps(d, ensure_ascii=False)[:700])
    print()

# 找一个 toriel* 的看看角色类图集
for n in names:
    if n.lower().startswith(u'toriel'):
        d = json.loads(io.open(os.path.join(WWW, n), 'rb').read().decode('utf-8'))
        print(u'== (toriel) %s  top-level=%r' % (n, list(d.keys())))
        print(json.dumps(d, ensure_ascii=False)[:900])
        break
