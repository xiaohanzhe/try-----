# -*- coding: utf-8 -*-
u"""侦察：ut_rooms.json / uty_rooms.json 的结构。"""
import io
import json
import sys

for f in (r'E:\Download\_extract61\_data\undertale\ut_rooms.json',
          r'E:\Download\_extract61\_data\undertale_yellow\ut_rooms.json'):
    d = json.load(io.open(f, encoding='utf-8'))
    rooms = d.get('rooms')
    print(u'== %s' % f)
    print(u'   rooms: type=%s len=%d' % (type(rooms).__name__,
                                        len(rooms) if rooms is not None else -1))
    if isinstance(rooms, list) and rooms:
        print(u'   elem0 keys: %r' % (list(rooms[0].keys())
                                      if isinstance(rooms[0], dict) else rooms[0],))
        print(u'   elem0: %s' % json.dumps(rooms[0], ensure_ascii=False)[:900])
        print(u'   elem1: %s' % json.dumps(rooms[1], ensure_ascii=False)[:500])
    elif isinstance(rooms, dict):
        ks = list(rooms.keys())
        print(u'   dict keys[:10]: %r' % (ks[:10],))
        print(u'   first value: %s' % json.dumps(rooms[ks[0]],
                                                 ensure_ascii=False)[:900])
    print()
