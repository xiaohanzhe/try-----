# -*- coding: utf-8 -*-
u"""第170轮：**`_original.marker` 的选取规则 —— 反推 + 用 102 条已知样本验证**。

背景
----
`branch_letter == chr(entrance + 64)` 在 batch169 的 102 条里 **102/102 成立**
（已单独验证），所以落点字母可以按这个约定推。
但 `marker` **推不出来**：它记的是**目标房间里实际存在哪个 `obj_marker*`**，
取值里有 `obj_markerX`(23) / `obj_markerAny`(15) / 4 条 `None` —— 与落点字母无关。

做法
----
候选规则（先猜，再用样本证伪）：
  R1 目标房里存在 `obj_marker<落点字母小写>` ⇒ 取它
  R2 否则若目标房只有 **1 种** marker 对象 ⇒ 取它
  R3 否则若存在 `obj_markerX` ⇒ 取它
  R4 否则 `None`（不猜）
若 R1~R4 能**逐条复现** 102 条已知样本 ⇒ 规则可信，可用于 9 条新规则；
否则打印反例、**不许用**。
"""
import collections
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(ROUND, '_evidence', 'marker170.json')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def norm(src):
    if not isinstance(src, str):
        return ''
    s = src.strip()
    return s.split('_', 1)[0] if '_' in s[len('obj_marker'):] else s


def pick_marker(markers, letter):
    u"""R1~R4。`markers` = 目标房里归一后的 marker 对象名集合（保序去重）。"""
    if letter:
        want = 'obj_marker' + letter.lower()
        if want in markers:
            return want
    if len(markers) == 1:
        return markers[0]
    if 'obj_markerX' in markers:
        return 'obj_markerX'
    return None


def main():
    route_d = jl(os.path.join(SCENES, '_routes.json'))
    routes = route_d['routes']

    #: scene_id -> 归一 marker 对象集合（保序）
    mk = {}
    #: original_room_id -> scene_id （按章）
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if not isinstance(v, dict):
                continue
            sid = v.get('scene_id') or k
            seen = []
            for o in v.get('objects') or []:
                if not isinstance(o, dict):
                    continue
                n = norm(o.get('src'))
                if n.startswith('obj_marker') and n not in seen:
                    seen.append(n)
            mk[sid] = seen

    #: 用 (ch, dst_room_id) -> sid 反查目标场景
    by_rid = {}
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        ch = z.get('chapter_id') or ''
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if isinstance(v, dict) and v.get('original_room_id') is not None:
                by_rid[(ch, v['original_room_id'])] = v.get('scene_id') or k

    # ---------- 验证 R1~R4 能否复现 102 条已知样本 ----------
    known = [r for r in routes if (r.get('_original') or {}).get('batch') == 169]
    bad = []
    for r in known:
        o = r['_original']
        sid_d = by_rid.get((o.get('chapter'), o.get('dst_room_id'))) or r.get('to')
        ms = mk.get(sid_d, [])
        got = pick_marker(ms, o.get('branch_letter'))
        if got != o.get('marker'):
            bad.append({'src': o.get('src_room_name'), 'dst': o.get('dst_room_name'),
                        'sid_d': sid_d, 'letter': o.get('branch_letter'),
                        'expected': o.get('marker'), 'got': got, 'markers': ms})
    print(u'== 用 R1~R4 复现 102 条已知 marker ==')
    print(u'   一致 %d / 不符 %d' % (len(known) - len(bad), len(bad)))
    for b in bad[:12]:
        print(u'   ✗ %-32s -> %-34s letter=%s 表=%r 推=%r 房内markers=%r'
              % (b['src'], b['dst'], b['letter'], b['expected'], b['got'], b['markers']))

    ok = not bad
    print()
    print(u'   结论：%s' % (u'R1~R4 可信，可用于新规则' if ok else u'★ 规则不成立，新规则一律不写 marker'))
    io.open(OUT, 'wb').write(json.dumps({'ok': ok, 'bad': bad}, ensure_ascii=False, indent=1)
                             .replace('\n', '\r\n').encode('utf-8'))


if __name__ == '__main__':
    main()
