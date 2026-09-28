# -*- coding: utf-8 -*-
u"""侦察：ut_objects.json / uty_objects.json 里的对象名（找门/传送类）。"""
import io
import json
import re
import sys

PAT = re.compile(u'door|warp|transition|marker|teleport|portal|gate|exit|room|save',
                 re.I)
for f in (r'E:\Download\_extract61\_data\undertale\ut_objects.json',
          r'E:\Download\_extract61\_data\undertale_yellow\ut_objects.json'):
    d = json.load(io.open(f, encoding='utf-8'))
    objs = d.get('objects')
    print(u'== %s' % f)
    print(u'   objects=%d' % (len(objs) if objs is not None else -1))
    if not objs:
        continue
    o0 = objs[0]
    print(u'   elem0 keys: %r' % (list(o0.keys()) if isinstance(o0, dict) else o0,))
    print(u'   elem0: %s' % json.dumps(o0, ensure_ascii=False)[:400])
    names = [o.get('name') for o in objs if isinstance(o, dict)]
    hits = [n for n in names if n and PAT.search(n)]
    print(u'   名字含门/传送语义的对象 %d 个：' % len(hits))
    for h in sorted(set(hits))[:60]:
        print(u'      %s' % h)
    print()
