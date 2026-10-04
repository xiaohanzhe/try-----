# -*- coding: utf-8 -*-
"""第87轮：把 50 条「家」合并进 `ralsei_pet/assets/npc/_placement.json`。

纪律
----
* **只增不改**：既有 34 条站位的所有字段逐字保留（含顺序 / 缩进风格）；
* 家作为**新增的独立字段**（`home` / `home_source` / `home_evidence` / `home_why`）
  挂在对应 NPC 的站位记录上；**`scene` 语义一个字都不动**；
* 跨作品 NPC（UT / 黄魂 / OneShot）**原本不在** `placement` 里 ⇒ 为它们**新增条目**，
  `scene=None / pos=[0,0] / mode='stand' / source='authored'`（不是站位、不参与桌面生活，
  只有 `home` 有值）；`why` 里写清"这条不是为了站位，只是为了登记家"；
* 数据源 = `E:/_tmp87/build/homes87.json`（50 条，逐条带 `why` 证据）。

★ 为什么不做成两个文件（`_placement.json` + `_homes.json`）：
  两个文件 ⇒ 两个 loader ⇒ "同一份规则两处算"的温床（谁先谁后 / 谁是权威）。
  家与站位本来就是**同一个 NPC 的两列属性**，放同一条记录里、由同一个 loader 读出来，
  才没有"两处口径"的可能。
"""
import collections
import io
import json
import os
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PLACEMENT = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', '_placement.json')
HOMES = r'E:\_tmp87\build\homes87.json'

# 跨作品前缀 → 世界的可读名（只用于生成 why 文案）
WORLD_CN = {
    'ut': '《Undertale》',
    'uty': '《Undertale Yellow》',
    'oneshot': '《OneShot》',
}


def load_json(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh, object_pairs_hook=collections.OrderedDict)


def world_of(nid, chapter):
    if chapter in WORLD_CN:
        return WORLD_CN[chapter]
    return '《Deltarune》'


def build_why(nid, chapter, home_entry):
    """给跨作品 NPC 新增条目时用的 `why`（说明"这条不是站位"）。"""
    w = world_of(nid, chapter)
    return ('★ 这条条目**不是站位**：%s 角色不属于 Deltarune 的任何房间，'
            '桌面上也不露面（见 `desktop.allowed`）。登记它只为携带 `home` 一列，'
            '让"回家 / 就寝"能识别它的归属地。' % w)


def main():
    src = load_json(PLACEMENT)
    homes = load_json(HOMES)
    home_list = homes.get('homes') or []
    print('输入：站位 %d 条，家 %d 条' % (len(src.get('placement') or []), len(home_list)))

    by_id = collections.OrderedDict()
    for rec in (src.get('placement') or []):
        by_id[rec.get('id')] = rec

    added = []      # 新增条目（跨作品）
    patched = []    # 既有条目上补 home
    already = []    # 已经带 home 的（防重复跑）

    for h in home_list:
        nid = h['id']
        rec = by_id.get(nid)
        block = collections.OrderedDict((
            ('home', h['scene']),
            ('home_source', h['source']),
            ('home_evidence', h.get('why') or ''),
            ('home_why', ''),
        ))
        if rec is None:
            # 跨作品 NPC：新增条目
            ch = h.get('chapter')
            new = collections.OrderedDict((
                ('id', nid),
                ('scene', None),
                ('pos', [0, 0]),
                ('facing', 'down'),
                ('mode', 'stand'),
                ('patrol', None),
                ('pace', None),
                ('room_id', None),
                ('room_raw', h.get('room')),
                ('source', 'authored'),
                ('evidence', ''),
                ('why', build_why(nid, ch, h)),
            ))
            new.update(block)
            by_id[nid] = new
            added.append(nid)
        else:
            if rec.get('home'):
                already.append(nid)
                continue
            rec.update(block)
            patched.append(nid)

    src['placement'] = list(by_id.values())

    # -- 更新 note / counts（诚实反映新增的两类信息）
    note_add = ('★ 第87轮补：`home` = **静态归属地**（与 `scene` = 当前站位**语义不同**，'
                '见 `npc_placement.HOME_KEY` 的注释）。跨作品角色（ut_* / hy_* / os_*）'
                '只登记 `home`，`scene` 为 null（他们不在 Deltarune 房间里、也不在桌面露面）。')
    src['note'] = (src.get('note') or '') + ' ' + note_add
    src['homes'] = collections.OrderedDict((
        ('note', '家的三级来源：original = 有原作房间名/实例硬证据；'
                 'derived = 有原作依据但"家"是本项目推定的（如"无家者归其常驻区"）；'
                 'authored = 原作依据不足，按原作分布规律安置（**必须**在 home_evidence 里说清）。'),
        ('rule', '★ 证据分级判据与站位表**完全一致**（同一个 SOURCE_KINDS），不另造一套标签。'),
        ('source_file', 'code-quality-audit/第87轮-每人一个家/_evidence/homes87.json'),
        ('by_source', collections.OrderedDict((
            ('original', sum(1 for h in home_list if h['source'] == 'original')),
            ('derived', sum(1 for h in home_list if h['source'] == 'derived')),
            ('authored', sum(1 for h in home_list if h['source'] == 'authored')),
        ))),
        ('homes', sum(1 for r in by_id.values() if r.get('home'))),
        ('nohome_deltarune', homes.get('nohome') or []),
        ('outertale_pending', homes.get('outertale_pending') or []),
    ))

    c = src.get('counts') or collections.OrderedDict()
    c['homes'] = sum(1 for r in by_id.values() if r.get('home'))
    c['home_by_source'] = src['homes']['by_source']
    c['outertale_pending'] = len(homes.get('outertale_pending') or [])
    src['counts'] = c

    # -- 落盘（4 空格缩进 / 保留中文 / 末尾换行，与既有风格一致）
    out = json.dumps(src, ensure_ascii=False, indent=1)
    with io.open(PLACEMENT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(out + '\n')

    print('新增条目 %d：%s' % (len(added), added))
    print('补 home 的既有条目 %d：%s' % (len(patched), patched))
    print('已带 home 跳过 %d：%s' % (len(already), already))
    print('总条目 %d，其中带 home %d' % (len(by_id), src['counts']['homes']))


if __name__ == '__main__':
    main()
