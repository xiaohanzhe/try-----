# -*- coding: utf-8 -*-
r"""inventory194.py —— 盘「现有 Ralsei 的能力 × 每个 NPC 有没有」。

用户口径（第194轮）：
  「ralsei 和其他人一样，是同级的那种，也就是现有 ralsei 的功能需要在所有人身上
   都能看到，但，也要根据具体情况来看」

所以先出**事实表**，再谈改什么。本脚本只读，不改任何东西：
  1. 读 `assets/npc/_registry.json`（96 条：78 main + 18 plain）
  2. 逐个查：人设文件 / 立绘帧 / 表情张数（都从磁盘真实算，不猜）
  3. 系统级能力（长期记忆 / 内在活动 / 情绪 / 关系 / 动画）目前**没有角色维度**，
     属于"全员统一缺口"，逐人表里不重复列，单独一节说明

用法：python inventory194.py [--md <out.md>]
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
ASSETS = os.path.join(REPO, 'ralsei_pet', 'assets')
NPC_DIR = os.path.join(ASSETS, 'npc')
FACES = os.path.join(ASSETS, 'faces')
FRAMES = os.path.join(ASSETS, 'sprites', 'dr', '_npc_frames.json')

WORLD_CN = {
    'dark': '暗世界', 'light': '光世界', 'ut': 'UT', 'outertale': 'Outertale',
    'oneshot': 'Oneshot', 'hollowknight': '黄魂', 'uty': 'UTY', 'deltarune': 'Deltarune',
    'foreign': '外来',
}

# 外来作品的 id 前缀（按登记表实际取值，不猜）：hy_=黄魂 / os_=Oneshot /
# ot_=Outertale / ut_=UT / uty_=UTY，其余归 Deltarune 本家
PREFIX_CN = [
    ('hy_', '黄魂'), ('os_', 'Oneshot'), ('ot_', 'Outertale'),
    ('uty_', 'UTY'), ('ut_', 'UT'),
]


def _json(p):
    try:
        with io.open(p, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def _faces_count(npc_id):
    d = os.path.join(FACES, npc_id)
    if not os.path.isdir(d):
        return 0
    try:
        return len([f for f in os.listdir(d)
                    if f.lower().endswith(('.png', '.webp', '.jpg'))])
    except Exception:
        return 0


def _size(p):
    try:
        return os.path.getsize(p)
    except Exception:
        return 0


def _art_kind(npc_id, chars, no_art, not_person):
    """这个 id 的立绘状态：有帧 / 原作无图 / 不是人 / 未登记。"""
    if npc_id in not_person:
        return u'非人物', 0
    ent = chars.get(npc_id) if isinstance(chars, dict) else None
    if isinstance(ent, dict):
        fr = ent.get('frames') or {}
        n = 0
        if isinstance(fr, dict):
            for v in fr.values():
                n += len(v) if isinstance(v, list) else 1
        elif isinstance(fr, list):
            n = len(fr)
        return u'有', n
    if npc_id in no_art:
        return u'原作无图', 0
    return u'未做', 0


def main(argv):
    reg = _json(os.path.join(NPC_DIR, '_registry.json')) or {}
    npcs = reg.get('npcs') or []
    man = _json(FRAMES) or {}
    chars = (man.get('characters') or {}) if isinstance(man, dict) else {}
    no_art = set((man.get('no_art') or [])) if isinstance(man, dict) else set()
    not_person = set((man.get('not_a_person') or [])) if isinstance(man, dict) else set()

    rows = []
    for n in npcs:
        nid = str(n.get('id') or '')
        if not nid:
            continue
        per = n.get('persona') or ''
        ppath = ''
        if per:
            ppath = os.path.normpath(os.path.join(NPC_DIR, per))
        has_per = bool(ppath) and os.path.isfile(ppath)
        art, nfr = _art_kind(nid, chars, no_art, not_person)
        world = WORLD_CN.get(str(n.get('home_world') or ''), str(n.get('home_world') or ''))
        for pre, cn in PREFIX_CN:
            if nid.startswith(pre):
                world = cn
                break
        rows.append({
            'id': nid,
            'cn': n.get('name_cn') or n.get('name') or '',
            'tier': n.get('tier') or '',
            'world': world,
            'persona': has_per,
            'per_kb': round(_size(ppath) / 1024.0, 1) if has_per else 0.0,
            'art': art,
            'frames': nfr,
            'faces': _faces_count(nid),
            'roam': n.get('roam_scope') or '',
        })

    # ---------------- 汇总
    total = len(rows)
    s_per = sum(1 for r in rows if r['persona'])
    s_fr = sum(1 for r in rows if r['art'] == u'有')
    s_noart = sum(1 for r in rows if r['art'] == u'原作无图')
    s_np = sum(1 for r in rows if r['art'] == u'非人物')
    s_todo = sum(1 for r in rows if r['art'] == u'未做')
    s_fc = sum(1 for r in rows if r['faces'])
    by_world = {}
    for r in rows:
        by_world.setdefault(r['world'], []).append(r)

    out = []
    out.append(u'# NPC 能力盘点（第194轮）')
    out.append(u'')
    out.append(u'数据来源：`assets/npc/_registry.json`（%d 条）、`assets/sprites/dr/_npc_frames.json`、'
               u'`assets/faces/<id>/`、`assets/npc/persona/*.txt`。**全部从磁盘真实算，无一处手填。**'
               % total)
    out.append(u'')
    out.append(u'## 一、素材齐备度（逐人差异只在这里）')
    out.append(u'')
    out.append(u'| 项 | 有 | 缺 | 覆盖率 |')
    out.append(u'|---|---|---|---|')
    out.append(u'| 人设文件 | %d | %d | %.0f%% |' % (s_per, total - s_per, 100.0 * s_per / max(1, total)))
    out.append(u'| 立绘：有帧 | %d | %d | %.0f%% |' % (s_fr, total - s_fr, 100.0 * s_fr / max(1, total)))
    out.append(u'| 立绘：原作就没图（`no_art`） | %d | — | — |' % s_noart)
    out.append(u'| 立绘：不是人（`not_a_person`） | %d | — | — |' % s_np)
    out.append(u'| 立绘：未做（外来作品，manifest 里没登记） | %d | — | — |' % s_todo)
    out.append(u'| 表情套（faces/<id>） | %d | %d | %.0f%% |' % (s_fc, total - s_fc, 100.0 * s_fc / max(1, total)))
    out.append(u'')
    out.append(u'## 二、按作品分布')
    out.append(u'')
    out.append(u'| 作品 | 人数 | 有人设 | 有立绘 | 原作无图 | 未做 | 有表情 |')
    out.append(u'|---|---|---|---|---|---|---|')
    for w in sorted(by_world, key=lambda x: -len(by_world[x])):
        g = by_world[w]
        out.append(u'| %s | %d | %d | %d | %d | %d | %d |'
                   % (w or '(空)', len(g),
                      sum(1 for r in g if r['persona']),
                      sum(1 for r in g if r['art'] == u'有'),
                      sum(1 for r in g if r['art'] == u'原作无图'),
                      sum(1 for r in g if r['art'] == u'未做'),
                      sum(1 for r in g if r['faces'])))
    out.append(u'')
    out.append(u'## 三、逐人明细')
    out.append(u'')
    out.append(u'| # | id | 中文名 | tier | 作品 | 人设(KB) | 立绘 | 表情 | 活动范围 |')
    out.append(u'|---|---|---|---|---|---|---|---|---|')
    for i, r in enumerate(sorted(rows, key=lambda x: (x['tier'] != 'main', x['world'], x['id'])), 1):
        out.append(u'| %d | `%s` | %s | %s | %s | %s | %s | %s | %s |'
                   % (i, r['id'], r['cn'], r['tier'], r['world'],
                      (u'%.1f' % r['per_kb']) if r['persona'] else u'**缺**',
                      (u'%d 帧' % r['frames']) if r['art'] == u'有' else r['art'],
                      r['faces'] if r['faces'] else u'**缺**',
                      r['roam'] or u'-'))
    out.append(u'')

    txt = u'\n'.join(out)
    if '--md' in argv:
        p = argv[argv.index('--md') + 1]
        with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt)
        print(u'已写入 %s（%d 行）' % (p, txt.count(u'\n') + 1))
    else:
        print(txt)

    print(u'')
    print(u'合计 %d 人 · 人设 %d · 立绘 %d · 表情 %d' % (total, s_per, s_fr, s_fc))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
