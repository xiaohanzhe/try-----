# -*- coding: utf-8 -*-
u"""probe104p.py —— 临时取证：多页事件里"换页会改变 opacity/blend_type"的那 7 条。"""
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
_spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
_o = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_o)
MAPS = os.path.join(_o.OSD, 'gamedata', 'maps')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def _has_cond(pg):
    u"""这一页是否**真的**被条件门控。

    ★★ RMXP 的 `condition` 是
      `{switch1_valid, switch1_id, switch2_valid, switch2_id, variable_valid,
        variable_id, variable_value, self_switch_valid, self_switch_ch}` ——
      **id 字段恒为真值**（默认 1）、**`self_switch_ch` 恒为 `"A"`**，
      真正的门控只有那四个 `*_valid`。用 `any(values())` 会得出
      "7804 条全带条件"的荒唐结果（本工具首版就栽在这，第二版漏了
      `self_switch_valid` **再栽一次**）。
    """
    c = pg.get('condition') or {}
    return bool(c.get('switch1_valid') or c.get('switch2_valid')
                or c.get('variable_valid')) or (bool(c.get('self_switch_valid'))
                                                and bool(c.get('self_switch_ch')))


hits = []
n_cond0 = 0
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for ei, e in enumerate(rj(p).get('events', [])):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g0 = pgs[0].get('graphic') or {}
        if int(g0.get('tile_id') or 0) > 0:
            continue
        cn0 = (g0.get('character_name') or '').strip()
        if not cn0 or cn0 not in HAVE:
            continue
        if _has_cond(pgs[0]):
            n_cond0 += 1
        if len(pgs) < 2:
            continue
        op0, bl0 = int(g0.get('opacity', 255)), int(g0.get('blend_type', 0))
        for k, pg in enumerate(pgs[1:], 1):
            g2 = pg.get('graphic') or {}
            if int(g2.get('tile_id') or 0) > 0:
                continue
            op2, bl2 = int(g2.get('opacity', 255)), int(g2.get('blend_type', 0))
            if (op2, bl2) != (op0, bl0):
                hits.append(dict(
                    room=n, event_index=ei, name=(e.get('name') or '').strip(),
                    tile=[int(e.get('x') or 0), int(e.get('y') or 0)],
                    sheet0=cn0, page0=[op0, bl0],
                    page=k, sheet=((g2.get('character_name') or '')).strip(),
                    pageN=[op2, bl2],
                    gated=_has_cond(pg),
                    cond=dict(pg.get('condition') or {}),
                    n_pages=len(pgs),
                ))
                break
print(u'命中 %d 条；其中"差异页**没有**条件门控"的 %d 条'
      % (len(hits), sum(1 for h in hits if not h['gated'])))
print(u'另：page0 自带条件的可见物件 %d 条' % n_cond0)
for h in hits:
    print(json.dumps(h, ensure_ascii=False))
