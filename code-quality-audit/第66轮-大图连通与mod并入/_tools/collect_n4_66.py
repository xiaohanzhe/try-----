# -*- coding: utf-8 -*-
u"""第66轮 · N4 取证：把"注册 35 条跨作品 NPC"所需的权威依据**蒸馏进仓**。

用户口径（第66轮逐字）
----------------------
* 「N4 素材这类的不是在我给你发过的那个文件里吗」
* （澄清）「就是之前那个 onnshot.world.machine 的那个文件」

⇒ OneShot 侧的权威来源 =
  `<桌面>/niko的秘密/OneShot.World.Machine.Edition.Build.16512634/gamedata/twm/contacts_metadata.json`
  （26 profile / 21 唯一角色；字段 `unlockId` / `title` / `subtitle`("Met: 区域") /
    `walkspriteId` / `facespics` / `uxColorTheme`）
  ⚠️ 该文件是 Newtonsoft 风格序列化产物，**带尾逗号**（`,}` / `,]`）⇒ 标准 json 会解析失败，
     先用 `re.sub(r',(\s*[}\]])', r'\1', raw)` 清洗。

Undertale 侧用户**没有**给对应文件 ⇒ 本脚本用磁盘上已有的用户素材
  `<桌面>/UT素材/`（5818 张 PNG）的**文件名**取证，取每个角色的原作 sprite 名（`spr_*`）。
  ★ 这是"该作品里的真实资源名"，不是猜的；逐条记 `evidence`（哪个目录下有哪些文件）。

铁律：**回归/后续施工不许依赖外部盘与临时区** ⇒ 本脚本把两份取证结果落进
      `_evidence/`（`oneshot_contacts66.json` / `ut_sprites66.json`）。

用法：python collect_n4_66.py
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, '_evidence')

DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
PROJ = os.path.join(DESKTOP, u'项目文件夹')

OS_CONTACTS = os.path.join(
    PROJ, u'niko的秘密', u'OneShot.World.Machine.Edition.Build.16512634',
    u'gamedata', u'twm', u'contacts_metadata.json')
UT_MATERIAL = os.path.join(PROJ, u'UT素材')

#: Undertale 14 份人设（第64轮入 `_personas.json`）→ 取 sprite 时用的**角色关键词**。
#: ★ `monster_kid` 在 UT 原作里的 sprite 前缀是 `spr_mkid_`（**不是** `spr_monster_kid_`）；
#:   `frisk` 用的是 `spr_f_mainchara*` —— 两条都由本脚本在磁盘上实证，不靠记忆。
UT_ROLES = [
    (u'ut_toriel', u'toriel'),
    (u'ut_sans', u'sans'),
    (u'ut_papyrus', u'papyrus'),
    (u'ut_undyne', u'undyne'),
    (u'ut_alphys', u'alphys'),
    (u'ut_mettaton', u'mettaton'),
    (u'ut_muffet', u'muffet'),
    (u'ut_napstablook', u'napstablook'),
    (u'ut_monster_kid', u'mkid'),
    (u'ut_asgore', u'asgore'),
    (u'ut_flowey', u'flowey'),
    (u'ut_frisk', u'f_mainchara'),
    (u'ut_chara', u'chara'),
    (u'ut_gaster', u'gaster'),
]

#: UT 的 overworld 四向后缀。★ 原作里**两种写法都有**，都要认：
#:   ① `spr_<name>_d`（sans / papyrus / toriel / asgore / alphys / undyne /
#:      napstablook / mkid —— 带下划线分隔）
#:   ② `spr_<name>d`（`spr_charad` / `spr_f_maincharad` —— 直接贴在名字后面）
UT_DIRS = (u'_d', u'_u', u'_l', u'_r')
UT_DIRS_BARE = (u'd', u'u', u'l', u'r')


def load_oneshot():
    raw = io.open(OS_CONTACTS, 'r', encoding='utf-8', errors='replace').read()
    clean = re.sub(r',(\s*[}\]])', r'\1', raw)
    data = json.loads(clean)
    profs = data.get('profiles') or []
    out = []
    for p in profs:
        out.append({
            'unlockId': p.get('unlockId'),
            'title': p.get('title'),
            'subtitle': p.get('subtitle'),
            'region': (p.get('subtitle') or '').replace('Met:', '').strip(),
            'walkspriteId': p.get('walkspriteId'),
            'uxColorTheme': p.get('uxColorTheme'),
            'facepics': list(p.get('facepics') or []),
            'singleSprite': p.get('singleSprite'),
            'walkAnimation': p.get('walkAnimation'),
        })
    return {
        'source': OS_CONTACTS.replace('\\', '/'),
        'source_bytes': len(raw.encode('utf-8')),
        'n_profiles': len(out),
        'n_unique_unlock': len(set(x['unlockId'] for x in out)),
        'region_counts': _counts(x['region'] for x in out),
        'profiles': out,
        'note': (u'权威来源 = 用户给定的 OneShot: World Machine Edition 官方 contacts 数据；'
                 u'`george1..6` 是同一角色 George 的 6 个变体 ⇒ 唯一角色 21 个。'
                 u'`walkspriteId` 即 OneShot 原作里这个角色的 sprite 标识。'),
    }


def _counts(seq):
    d = {}
    for k in seq:
        d[k] = d.get(k, 0) + 1
    return d


def _sprite_bases(root):
    """`{sprite_base: [相对路径, ...]}`（去掉 `_<帧号>` 与 `.png`）。"""
    idx = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.lower().endswith('.png'):
                continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace('\\', '/')
            b = re.sub(r'\.png$', '', f)
            b = re.sub(r'_\d+$', '', b)
            idx.setdefault(b, []).append(rel)
    return idx


def load_ut():
    idx = _sprite_bases(UT_MATERIAL)
    bases = sorted(idx)
    out = {}
    for npc_id, key in UT_ROLES:
        hits = [b for b in bases if key in b.lower()]
        lk = key.lower()
        ow = {}
        for d in UT_DIRS + UT_DIRS_BARE:
            cand = [b for b in hits if b.lower().endswith(lk + d)
                    and not b.lower().endswith(lk + d + '_fall')]
            if cand:
                # 归一化键：`_d` 与 `d` 收进同一个槽（优先带下划线的写法）
                ow.setdefault(d.lstrip('_'), []).extend(sorted(cand))
        ow = {k: sorted(set(v)) for k, v in sorted(ow.items())}
        pick = None
        how = None
        # ① 优先**精确**的 overworld 四向（down 帧）
        if ow.get('d'):
            pick = ow['d'][0]
            how = 'overworld_4dir'
        else:
            # ② 次优：名字里带 `overworld` 的（原作用它标"地图上的那一版"）
            ovw = [b for b in hits if 'overworld' in b.lower()]
            if ovw:
                pick = sorted(ovw, key=lambda s: (len(s), s))[0]
                how = 'overworld_tagged'
            elif hits:
                # ③ 退而取"最短的那个 base"（越短越接近角色本体名，
                #    不是 `X_behind` / `X_flame_mask` 这类派生）
                pick = sorted(hits, key=lambda s: (len(s), s))[0]
                how = 'nearest_base'
        out[npc_id] = {
            'key': key,
            'objects': [pick] if pick else [],
            'how': how,
            'overworld_dirs': ow,
            'n_hits': len(hits),
            'top_hits': sorted(hits, key=lambda s: (len(s), s))[:8],
            'evidence': [idx[b][0] for b in sorted(hits, key=lambda s: (len(s), s))[:3]],
        }
    return {
        'source': UT_MATERIAL.replace('\\', '/'),
        'n_png_bases': len(bases),
        'roles': out,
        'note': (u'Undertale 侧**没有** contacts 那样的官方归属文件 ⇒ 这里的 `objects` 取'
                 u'用户素材目录里的**原作 sprite 名**（`spr_*`），逐条记 evidence（哪个文件）。'
                 u'无 overworld 四向的角色（mettaton / flowey / gaster）取最接近本体的 base，'
                 u'已在 `how` 里标出（`nearest_base`）—— 如实登记，不假装是行走图。'),
    }


def main():
    if not os.path.isfile(OS_CONTACTS):
        print(u'!! OneShot contacts 文件不存在：%s' % OS_CONTACTS)
        return 2
    if not os.path.isdir(UT_MATERIAL):
        print(u'!! UT 素材目录不存在：%s' % UT_MATERIAL)
        return 2
    if not os.path.isdir(EVID):
        os.makedirs(EVID)

    os_data = load_oneshot()
    ut_data = load_ut()

    p1 = os.path.join(EVID, 'oneshot_contacts66.json')
    p2 = os.path.join(EVID, 'ut_sprites66.json')
    for path, obj in ((p1, os_data), (p2, ut_data)):
        with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False))
            fh.write(u'\n')

    print(u'[ONEShot] profiles=%d unique=%d regions=%s'
          % (os_data['n_profiles'], os_data['n_unique_unlock'],
             json.dumps(os_data['region_counts'], ensure_ascii=False)))
    for p in os_data['profiles']:
        print(u'   %-14s %-22s %-26s %s'
              % (p['unlockId'], p['title'], p['walkspriteId'], p['region']))
    print()
    print(u'[Undertale] sprite bases=%d' % ut_data['n_png_bases'])
    for npc_id, rec in sorted(ut_data['roles'].items()):
        print(u'   %-16s key=%-12s how=%-15s objects=%s  ow=%s'
              % (npc_id, rec['key'], rec['how'], rec['objects'],
                 ','.join(rec['overworld_dirs'])))
    print()
    print(u'落盘：\n  %s\n  %s' % (p1, p2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
