# -*- coding: utf-8 -*-
u"""第122轮侦察 B：ut 的门**到底是哪些对象**、各有多少实例、可信层覆盖到哪些。

## 为什么要单独看这一层

`probe_doors122.py` 已经证明：候选层（`conn_inferred115.json`）的 `rule` 自己写着
「摆了该对象的房间就存在这条边 **未经验证**」，且 563 条里 420 条 `via=obj_mainchara`
—— 那是"走到屏幕边缘换房"的机制，**不是门**。拿它当门的目标 = 编造。

⇒ 门的真实目标只能来自**可信层**（`conn115.json` 的 `code` 是反编译出来的函数名）。
本脚本回答三个问题：
  1. ut 里 `kind=door` 的对象有哪些、各多少**实例**（第121轮说 1,299 个实例）；
  2. 这些对象里，哪些在可信层里有边、覆盖多少实例；
  3. 剩下的门实例长什么样（是装饰门？还是另有触发方式？）。

用法：python probe_doors122b.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(RAW115, 'raw', 'ut')
ZONE = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_zone.ut.rooms.json')

sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))
import item_interact as II       # noqa: E402


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def main():
    objs = [r[1] for r in _rows(os.path.join(RAW, 'objmap_ut.txt'))
            if len(r) >= 5 and r[0] != 'GameObjects']
    objset = set(objs)

    # 实例：按"实例"计数（不是按房间去重 —— 第121轮的 1,299 是实例数）
    per_obj = collections.Counter()
    per_pair = collections.Counter()
    cur = None
    for r in _rows(os.path.join(RAW, 'inst_full.tsv')):
        if r[0] == 'R':
            cur = r[2]
        elif r[0] == 'I' and cur is not None:
            per_obj[r[1]] += 1
            per_pair[(cur, r[1])] += 1

    door_objs = sorted(o for o in objset if (II.classify(o) or {}).get('kind') == 'door')
    print(u'== ut 的 door 对象（按实例数）==')
    tot = 0
    for o in sorted(door_objs, key=lambda x: -per_obj[x]):
        print(u'  %-28s %5d' % (o, per_obj[o]))
        tot += per_obj[o]
    print(u'  ---- 合计 %d 个对象 / %d 个实例' % (len(door_objs), tot))

    # 可信层：按门对象统计
    edges = _json(os.path.join(RAW115, 'conn115.json'))['ut']['edges']

    def obj_of_code(code):
        if not isinstance(code, str) or not code.startswith('gml_Object_'):
            return None
        tail = code[len('gml_Object_'):]
        best = None
        for nm in objset:
            if (tail == nm or tail.startswith(nm + '_')) and (best is None or len(nm) > len(best)):
                best = nm
        return best

    by_obj = collections.Counter()
    for e in edges:
        o = obj_of_code(e.get('code'))
        if o:
            by_obj[o] += 1
    print(u'')
    print(u'== 可信层里出现的对象（边数）==')
    for o, n in by_obj.most_common():
        print(u'  %-28s %5d' % (o, n))

    # 每场景 door 实例数分布：装饰门的房间会长得不一样
    door_per_scene = collections.Counter()
    for (rn, o), n in per_pair.items():
        if o in door_objs:
            door_per_scene[rn] += n
    dist = collections.Counter(door_per_scene.values())
    print(u'')
    print(u'== 每场景 door 实例数分布 ==')
    print(u'  %s' % dict(sorted(dist.items())[:12]))
    print(u'  场景数 %d；实例总数 %d' % (len(door_per_scene), sum(door_per_scene.values())))
    top = door_per_scene.most_common(5)
    print(u'  实例最多的房间：%s' % (top,))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
