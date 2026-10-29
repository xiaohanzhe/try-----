# -*- coding: utf-8 -*-
u"""第115轮 · UT / UTY / Outertale 物件分级 + 待填清单

口径**沿用 Deltarune**（`_tools/props115.py`），三分类不变，这样两边以后能并到同一套块级结构：
    logic   ：没有 sprite，或 vis=False        —— 纯逻辑
    trigger ：sprite 是「占位/判定/事件」图     —— 剧情事件/判定区，不是布景
    prop    ：其余可见对象                     —— 真正要摆到桌面上的东西

输入（全部在仓库里，不碰游戏目录、不碰 E:）：
    _evidence/raw/<key>/objmap_ut.txt     对象索引：id / name / spr= / vis= / pers=
    _evidence/raw/<key>/inst_full.tsv     实例坐标（第115轮已落库）

输出：
    _evidence/cross_props115.json         三款合并的分级明细
    _evidence/cross_objects_todo.csv      ★ 给用户填的清单（带「作品」列，一个文件搞定）
    _evidence/cross_triggers115.txt       触发器名单（只作参考，不用填）

★★ 占位图判据为什么长这样（每条都有实测依据，不许凭感觉加）：
   · UTY 的 `shadow` 类精灵（`spr_martlet_head_shadow` 等）是**角色部件**，是真物件，
     所以 `shadow` **不进**占位规则 —— 第一版探针把它算进去过，是误报。
   · `spr_solid*` 是**不可见碰撞块**（UT 的墙），不是布景 ⇒ 算 trigger（判定区）。
   · `spr_event*` 覆盖 `spr_event` / `spr_event_small` / `spr_event_collider` 三种写法。
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')

WORKS = ['ut', 'uty', 'outertale']
WORK_CN = {'ut': u'Undertale', 'uty': u'Undertale Yellow', 'outertale': u'Outertale'}

# ---- 占位/判定/事件图：正则 -> 理由（理由会写进 JSON，便于复核）--------------
TRIGGER_RULES = [
    (re.compile(r'^spr_event', re.I), u'事件占位图（spr_event / _small / _collider）'),
    (re.compile(r'^spr_marker', re.I), u'标记点（spr_markerX）'),
    (re.compile(r'^spr_collisionbox$', re.I), u'碰撞盒'),
    (re.compile(r'_hitbox$', re.I), u'碰撞盒（*_hitbox）'),
    (re.compile(r'^spr_invisible$', re.I), u'显式不可见图'),
    (re.compile(r'^spr_debug_', re.I), u'调试图'),
    (re.compile(r'^spr_crosshair', re.I), u'准星'),
    (re.compile(r'^spr_solid', re.I), u'不可见碰撞块（墙）'),
    (re.compile(r'^spr_border$', re.I), u'边界框'),
    (re.compile(r'^spr_whitefader$', re.I), u'全屏淡出遮罩'),
]

#: 名字不表意：obj_prop_1 / obj_thing / obj_x2 / 单字母 / 纯数字结尾
_VAGUE = re.compile(r'(^obj_(prop|thing|stuff|misc|obj|deco)\b|_?\d+$|^obj_[a-z]$)', re.I)


def triggered_by(spr):
    """返回命中的理由；没命中返回 None"""
    if not spr:
        return None
    for rx, why in TRIGGER_RULES:
        if rx.search(spr):
            return why
    return None


def load_objmap(key):
    p = os.path.join(RAW, key, 'objmap_ut.txt')
    out = {}
    if not os.path.isfile(p):
        return out
    in_rooms = False
    for ln in io.open(p, encoding='utf-8', errors='replace'):
        ln = ln.rstrip('\n')
        if ln.startswith('== Rooms = '):
            in_rooms = True
            continue
        if in_rooms or not ln or ln.startswith('GameObjects') or ln.startswith('!!'):
            continue
        parts = ln.split('\t')
        if not parts[0].strip().isdigit():
            continue
        d = {'id': int(parts[0]), 'name': parts[1].strip()}
        for extra in parts[2:]:
            k, _, v = extra.partition('=')
            d[k.strip()] = v.strip()
        out[d['name']] = d
    return out


def load_inst(key):
    """按实例表汇总：obj -> {inst, rooms[], depths Counter}"""
    p = os.path.join(RAW, key, 'inst_full.tsv')
    per = collections.defaultdict(lambda: {'inst': 0, 'rooms': [], 'seen': set(),
                                           'depths': collections.Counter()})
    cur = None
    if not os.path.isfile(p):
        return per
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                cur = ln.split('\t')[2]
            elif ln.startswith('I\t'):
                q = ln.split('\t')
                name = q[1]
                e = per[name]
                e['inst'] += 1
                e['depths'][int(q[9])] += 1
                if cur not in e['seen']:
                    e['seen'].add(cur)
                    e['rooms'].append(cur)
    return per


def main():
    rows = []
    per_work = {}
    missing_sprite = collections.Counter()
    not_in_objmap = collections.Counter()

    for key in WORKS:
        om = load_objmap(key)
        inst = load_inst(key)
        per_work[key] = {'objects_total': len(om), 'used': len(inst)}
        for name, e in inst.items():
            o = om.get(name)
            if o is None:
                not_in_objmap[key] += 1
                o = {'spr': '', 'vis': '?'}
            spr = o.get('spr') or ''
            vis = o.get('vis') or ''
            if not spr or vis != 'True':
                cls = 'logic'
                why = u'无精灵' if not spr else u'vis=False'
            else:
                hit = triggered_by(spr)
                if hit:
                    cls = 'trigger'
                    why = hit
                else:
                    cls = 'prop'
                    why = u'可见且非占位图'
            if not spr:
                missing_sprite[key] += 1
            depths = sorted(e['depths'].items(), key=lambda kv: (-kv[1], kv[0]))
            dvals = [d for d, _ in depths]
            rows.append({
                'work': key,
                'name': name,
                'sprite': spr,
                'vis': vis,
                'class': cls,
                'why': why,
                'inst': e['inst'],
                'rooms': len(e['rooms']),
                'depth_mode': dvals[0] if dvals else None,
                'n_depths': len(depths),
                'room_samples': e['rooms'][:3],
                'vague': bool(_VAGUE.search(name)),
            })

    cnt = collections.Counter((r['work'], r['class']) for r in rows)
    inst_by = collections.Counter()
    for r in rows:
        inst_by[(r['work'], r['class'])] += r['inst']

    totals = {}
    for key in WORKS:
        totals[key] = {
            'objects_in_objmap': per_work[key]['objects_total'],
            'objects_used': per_work[key]['used'],
            'inst_total': sum(r['inst'] for r in rows if r['work'] == key),
            'by_class': {c: {'objects': cnt[(key, c)], 'inst': inst_by[(key, c)]}
                         for c in ('prop', 'trigger', 'logic')},
            'not_in_objmap': not_in_objmap[key],
            'no_sprite': missing_sprite[key],
        }

    out = {
        'note': u'第115轮 · UT/UTY/Outertale 物件分级；口径同 props115.py（logic/trigger/prop）',
        'totals': totals,
        'trigger_rules': [(rx.pattern, why) for rx, why in TRIGGER_RULES],
        'objects': rows,
    }

    # ---- 待填清单：★★ 按对象名分组，同名跨作品合并成一行 ----
    # 理由：UT 的 454 个实体物件里有 453 个在 Outertale 中原样重现（96% 重合），
    # 不合并就是让用户把同一个物件填两遍（1,516 行 → 1,056 行，省掉 460 行）。
    props = [r for r in rows if r['class'] == 'prop']
    groups = collections.OrderedDict()
    for r in sorted(props, key=lambda x: (-x['inst'], x['name'], WORKS.index(x['work']))):
        groups.setdefault(r['name'], []).append(r)

    merged = []
    for name, rs in groups.items():
        works = sorted({x['work'] for x in rs}, key=WORKS.index)
        sprites = []
        for w in works:
            sp = next(x['sprite'] for x in rs if x['work'] == w)
            if sp not in sprites:
                sprites.append(sp)
        dm = []
        for w in works:
            d = next(x['depth_mode'] for x in rs if x['work'] == w)
            tag = u'%s:%s' % (w, d)
            if d not in [x[1] for x in dm]:
                dm.append((w, d))
        depth_txt = (u'%s' % dm[0][1]) if len(dm) == 1 else u' / '.join(u'%s=%s' % (w, d) for w, d in dm)
        samples = []
        for x in rs:
            for s in x['room_samples']:
                if s not in samples:
                    samples.append(s)
        merged.append({
            'name': name,
            'works': works,
            'sprite': sprites[0] if len(sprites) == 1 else u' | '.join(sprites),
            'n_works': len(works),
            'inst': sum(x['inst'] for x in rs),
            'rooms': sum(x['rooms'] for x in rs),
            'depth_txt': depth_txt,
            'room_samples': samples[:3],
            'vague': any(x['vague'] for x in rs),
            'per_work': {x['work']: x['inst'] for x in rs},
        })
    merged.sort(key=lambda x: (-x['inst'], x['name']))

    out['csv'] = {
        'rows': len(merged),
        'rows_unmerged': len(props),
        'distinct_prop_names': len(groups),
        'saved_rows': len(props) - len(merged),
    }
    with io.open(os.path.join(EV, 'cross_props115.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    with io.open(os.path.join(EV, 'cross_objects_todo.csv'), 'w',
                 encoding='utf-8-sig', newline='') as f:
        f.write(u'编号,作品,对象名,精灵,作品数,房间数(合计),实例数(合计),'
                u'最常见层深,示例房间,名字含糊,功能简介（请填写）\n')
        for i, r in enumerate(merged, 1):
            f.write(u'%03d,%s,%s,%s,%d,%d,%d,%s,%s,%s,\n' % (
                i,
                u' / '.join(WORK_CN[w] for w in r['works']),
                r['name'], r['sprite'], r['n_works'],
                r['rooms'], r['inst'], r['depth_txt'],
                u' | '.join(r['room_samples']),
                u'是' if r['vague'] else u''))

    # ---- 触发器名单 ----
    trig = [r for r in rows if r['class'] == 'trigger']
    trig.sort(key=lambda r: (-r['inst'], r['work'], r['name']))
    with io.open(os.path.join(EV, 'cross_triggers115.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(u'第115轮 · 事件触发器 / 判定区（占位精灵，不是布景，不用填功能简介）\n')
        f.write(u'共 %d 个对象 / %d 次实例\n\n' % (len(trig), sum(r['inst'] for r in trig)))
        for r in trig:
            f.write(u'%-11s %-40s %-40s inst=%-5d rooms=%-4d %s\n' % (
                r['work'], r['name'], r['sprite'], r['inst'], r['rooms'], r['why']))

    # ---- 控制台汇总 ----
    print(u'对象 %d（实例 %d）' % (len(rows), sum(r['inst'] for r in rows)))
    for key in WORKS:
        t = totals[key]
        print(u'[%s] %s：对象 %d / 实例 %d' % (key, WORK_CN[key],
                                              t['objects_used'], t['inst_total']))
        for c, lab in (('prop', u'实体物件'), ('trigger', u'事件触发器'), ('logic', u'纯逻辑')):
            print(u'    %-8s %4d 个 / %6d 次' % (lab, t['by_class'][c]['objects'],
                                                 t['by_class'][c]['inst']))
        print(u'    其中名字含糊的实体物件 %d 个；objmap 里查不到的 %d 个'
              % (sum(1 for r in rows if r['work'] == key and r['class'] == 'prop' and r['vague']),
                 t['not_in_objmap']))
    print(u'待填清单：合并后 %d 行（未合并 %d 行，同名跨作品省掉 %d 行）'
          % (len(merged), len(props), len(props) - len(merged)))
    print(u'落盘：cross_props115.json / cross_objects_todo.csv / cross_triggers115.txt')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
