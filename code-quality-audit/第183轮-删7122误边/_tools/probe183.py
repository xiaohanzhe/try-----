# -*- coding: utf-8 -*-
u"""第183轮 · 只读探针：把 traffic_3 那扇 W 门的全部同源边摊开看。

只读，不改任何东西。
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    raw = rd(ROUTES)
    data = json.loads(raw)
    routes = data.get('routes') or []
    print('总条数 = %d' % len(routes))

    keys = ('from_scene', 'from_door', 'from_letter', 'when_scene', 'when_door',
            'when_letter', 'to', 'priority')

    # 1) 精确找 traffic_3 的所有出边
    src = [r for r in routes if isinstance(r, dict) and r.get('from_scene') == 'traffic_3']
    print('\n[1] from_scene == traffic_3 的边：%d 条' % len(src))
    for r in sorted(src, key=lambda x: x.get('priority') or 0):
        print('    ' + ' | '.join('%s=%s' % (k, r.get(k)) for k in keys if k in r))

    # 2) 7000 段附近全部
    near = [r for r in routes
            if isinstance(r, dict) and isinstance(r.get('priority'), int)
            and 7100 <= r['priority'] <= 7140]
    print('\n[2] priority 在 7100~7140 的边：%d 条' % len(near))
    for r in sorted(near, key=lambda x: x['priority']):
        print('    ' + ' | '.join('%s=%s' % (k, r.get(k)) for k in keys if k in r))

    # 3) 7122 究竟几条
    hit = [r for r in routes if isinstance(r, dict) and r.get('priority') == 7122]
    print('\n[3] priority == 7122 命中 %d 条' % len(hit))

    # 4) 设计稿：7121 与 7122 的 when_* 是否完全一致
    if hit:
        a = [r for r in routes if isinstance(r, dict) and r.get('priority') == 7121]
        if a:
            wa = {k: v for k, v in a[0].items() if k.startswith('when_')}
            wb = {k: v for k, v in hit[0].items() if k.startswith('when_')}
            print('[4] 7121.when_* = %s' % json.dumps(wa, sort_keys=True, ensure_ascii=False))
            print('    7122.when_* = %s' % json.dumps(wb, sort_keys=True, ensure_ascii=False))
            print('    完全一致 = %s' % (wa == wb))

    # 5) 谁指向 dw_city_moss / dw_city_man
    for tgt in ('dw_city_moss', 'dw_city_man'):
        t = [r for r in routes if isinstance(r, dict) and r.get('to') == tgt]
        print('\n[5] to == %s 的边：%d 条 -> %s'
              % (tgt, len(t), sorted(x.get('priority') for x in t
                                     if isinstance(x.get('priority'), int))))

    # 6) 隐藏房登记现状
    h = data.get('_hidden_rooms') or []
    print('\n[6] _hidden_rooms：%d 条' % len(h))
    for e in h:
        print('    ' + json.dumps(e, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
