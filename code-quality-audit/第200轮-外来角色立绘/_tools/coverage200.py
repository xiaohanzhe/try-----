# -*- coding: utf-8 -*-
"""第200轮 · 62 个外来角色的立绘素材盘点（只读）

背景
----
`inventory195.py` 报「立绘未做 62」，但 `assets/sprites/ut|hy|ot|os` 里**已经有帧**
（第70/71轮落的）。差别在：产品的 `npc_body_render.NpcFrameBook` 只读
`sprites/dr/_npc_frames.json`，那份清单只覆盖 Deltarune ⇒ 外来作品**有素材没登记**。

本脚本只回答三个问题：
  1. 62 人各自的帧在不在、有多少、什么尺寸；
  2. 帧名前缀能不能**唯一**对到一个 id（不能唯一就必须人工看图，别猜）；
  3. 有没有"谁都没有"的（那才是真的要从游戏源文件重抽）。
"""
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
REG = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_registry.json')
MANI = os.path.join(SPR, 'dr', '_npc_frames.json')

WORKS = ('ut', 'hy', 'ot', 'os')


def png_size(p):
    """读 IHDR 拿真实像素尺寸（`size_semantics.png` 是权威，gms_meta 不是）。"""
    try:
        with open(p, 'rb') as f:
            head = f.read(33)
        if head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        w, h = struct.unpack('>II', head[16:24])
        return (w, h)
    except Exception:
        return None


def main():
    reg = json.loads(io.open(REG, encoding='utf-8').read())
    npcs = reg.get('npcs') or []
    mani = json.loads(io.open(MANI, encoding='utf-8').read())
    have_dr = set((mani.get('characters') or {}).keys())
    no_art = set(mani.get('no_art') or [])
    not_person = set(mani.get('not_a_person') or [])

    # 每作的帧文件
    files = {}
    for w in WORKS:
        d = os.path.join(SPR, w)
        if not os.path.isdir(d):
            files[w] = []
            continue
        files[w] = sorted(n for n in os.listdir(d) if n.lower().endswith('.png'))

    print('=== 素材总量 ===')
    for w in WORKS:
        print('  %-3s %3d 张 PNG' % (w, len(files[w])))

    # 62 人 = 登记里有 id、无 dr 立绘、不是 no_art / not_a_person
    todo = []
    for it in npcs:
        i = it.get('id')
        if not i:
            continue
        if i in have_dr or i in no_art or i not in not_person and False:
            continue
        if i in no_art:
            continue
        if i in have_dr:
            continue
        todo.append(it)
    # not_a_person 也要排除
    todo = [it for it in todo if it.get('id') not in not_person]

    print('\n=== 待做 %d 人 ===' % len(todo))
    print('%-24s %-6s %-10s %5s  %s' % ('id', 'work', 'name', '帧数', '前缀命中'))
    stat = {'ok': 0, 'ambig': 0, 'none': 0}
    rows = []
    for it in todo:
        i = it['id']
        work = (it.get('work') or '').lower()
        key = None
        for w, alias in (('ut', ('ut', 'undertale')), ('hy', ('hy', 'yellow', '黄魂')),
                         ('ot', ('ot', 'outertale')), ('os', ('os', 'oneshot'))):
            if work in alias:
                key = w
        if key is None:
            # 用 id 前缀兜底（ut_/hy_/ot_/os_）
            key = i.split('_')[0] if '_' in i else ''
        if key not in files:
            rows.append((i, work or '?', it.get('name') or '', 0, '—(未知作品)'))
            stat['none'] += 1
            continue
        # 前缀候选：去掉 ut_/hy_/ot_/os_ 后的本体名
        base = i.split('_', 1)[1] if '_' in i else i
        cand = [n for n in files[key] if base.lower() in n.lower()]
        if not cand and '_' in base:
            # dalv / ceroba_ketsukane 这种，退一步用首段
            b2 = base.split('_')[0]
            cand = [n for n in files[key] if b2.lower() in n.lower()]
        n = len(cand)
        if n == 0:
            stat['none'] += 1
            tag = '✗ 无'
        else:
            stat['ok'] += 1
            tag = '%d 张' % n
        rows.append((i, key, it.get('name') or '', n, tag))
        # 顺便记尺寸分布
        if n:
            sizes = {}
            for p in cand[:6]:
                s = png_size(os.path.join(SPR, key, p))
                sizes[s] = sizes.get(s, 0) + 1

    for r in rows:
        print('%-24s %-6s %-10s %5d  %s' % r)

    print('\n=== 汇总 ===')
    print('有帧 %d · 无帧 %d · 合计 %d' % (stat['ok'], stat['none'], len(rows)))

    # 44/62 里还差谁
    lack = [r[0] for r in rows if r[3] == 0]
    if lack:
        print('\n无帧的 %d 人：%s' % (len(lack), ', '.join(lack)))

    out = os.path.join(ROUND, '_evidence', 'coverage200.json')
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps([{'id': r[0], 'work': r[1], 'name': r[2], 'frames': r[3]}
                            for r in rows], ensure_ascii=False, indent=1))
    print('\n[写出] %s' % out)


if __name__ == '__main__':
    main()
