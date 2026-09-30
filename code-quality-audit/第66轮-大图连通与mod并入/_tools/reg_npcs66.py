# -*- coding: utf-8 -*-
u"""第66轮 · N4：把 OneShot 21 + Undertale 14 条跨作品 NPC 注册进
`ralsei_pet/assets/npc/_registry.json`，并把它们如实挂进 `_placement.json` 的 `unplaced`。

为什么要注册（现状勘误）
------------------------
第64轮把用户 30 万字原文里的 37 份人设抽进 `_personas.json`（13 → 50），
但**只到了人设层**：`_registry.json` 仍是 35 条（全是 Deltarune）。
而 `npc_persona.load_personas()` 的真源 = `_personas.json` 的 `personas[].file`，
`_registry.json` 的 `persona` 字段**没有任何运行时消费者** ⇒ 那 35 份人设
"有设无人"：不会被 `main._npc_aliases`（@点名）收录，也不会被 `MiniMemory` 建档。

字段取值口径（逐条有据，零臆造）
--------------------------------
| 字段 | OneShot（21） | Undertale（14） |
|---|---|---|
| `id` | `_personas.json` 的 id（`os_*`） | `_personas.json` 的 id（`ut_*`） |
| `name` | contacts 的 `title` | persona 首行英文名 |
| `name_cn` | persona 首行中文括号（有才给） | 同左（UT 无括号 ⇒ = name） |
| `objects` | contacts 的 `walkspriteId`（**官方**） | 用户 `UT素材/` 文件名里的原作 sprite 名 |
| `chapters` | `['oneshot']` | `['undertale']` |
| `home_world` | `'dark'`（★见下） | `'dark'` |

★ `home_world` 为什么写 `'dark'` 而不是 `'oneshot'`：
  `NpcDef.__init__` 里 `home_world if home_world in ('light','dark') else 'dark'`
  ⇒ 写 `'oneshot'` 会被**静默改判**成 `'dark'`。本项目世界模型只有两分，
  OneShot / Undertale 都归入 `'dark'`。**显式写 `'dark'`** 让读的人一眼看到真值，
  不靠"被静默改判"来发现（本项目最讨厌的那类惊喜）。

★ `chapters` 为什么非空：
  ① `npc_system.can_follow()` = `bool(chapters)` ⇒ 空 = 不能跟随；
  ② `world_gate()` 的暗世界分支遇到空 chapters 直接 `REASON_NO_CHAPTERS` 拒绝；
  ③ 第49轮回归 `verify_npc49.B5` 硬断言 `all(n.chapters for n in REG.all())`。
  当前**没有** `oneshot.*` / `undertale.*` 场景（`scene_system` 里只有 ch1~ch5 + desktop）
  ⇒ 这两个值现在是**未来场景前缀锚**（`scene_chapter()` 取 `split('.')[0]`），
  实际效果：它们进不了任何 Deltarune 暗世界场景（跨作品天然隔离），也不在桌面白名单里。

安全闸：写回前先做**等价性锚点** —— `json.loads` 后原样 `dumps` 必须与磁盘字节**逐字节相同**。
不同就停下（说明这个文件的排版不是 `indent=1` 的产物，得改别的写法），绝不盲写。

用法：python reg_npcs66.py [--apply]     # 不给 --apply = 只做 dry-run
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
NPC_DIR = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
REG_PATH = os.path.join(NPC_DIR, '_registry.json')
PLACE_PATH = os.path.join(NPC_DIR, '_placement.json')
EVID = os.path.join(ROUND, '_evidence')

WORK_ONESHOT = 'oneshot'
WORK_UNDERTALE = 'undertale'

#: NPCDef 的字段顺序 = 磁盘上的既有排版（注意 `notes` 在 `persona` **前**面）。
ENTRY_KEYS = ('id', 'name', 'name_cn', 'tier', 'chapters', 'home_world', 'objects',
              'model', 'needs_setting', 'escape_via_bubble', 'notes', 'persona')

#: OneShot：`_personas.json` 的 id → contacts 的 `unlockId`。
#: 21 条里只有 3 个不规则，逐个说明（其余一律 `os_<unlockId>`）：
OS_UNLOCK_OVERRIDE = {
    'os_the_world_machine': 'world_machine',   # 官方 unlockId 没有 `the_`
    'os_the_author': 'author',                 # 官方 unlockId 没有 `the_`
    'os_george': 'george1',                    # 官方是 george1..george6 六个变体 ⇒ 取 1 号
}

#: ★ 首行模板（实测两种写法都有，空格数不同，一律宽容匹配）：
#:   `…《OneShot》中的 Niko 的身份进行对话`      （无括号名 ⇒ 名后有空格）
#:   `…《OneShot》中的 The World Machine（又称 The Entity / 本体）的身份进行对话`
#:                                            （带括号名 ⇒ 全角 `）` 直接接 `的`，**没有空格**）
_PERSONA_HEAD = re.compile(
    u'你是一个角色扮演 AI，你将完全以《(.+?)》中的\\s*(.+?)\\s*的身份进行对话')


def read_bytes(path):
    with io.open(path, 'rb') as fh:
        return fh.read()


def read_text(path):
    return read_bytes(path).decode('utf-8')


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + u'\n'


def parse_head(text):
    """persona 首行 → `(work, name, name_cn)`。认不出 ⇒ `(None, None, None)`。"""
    line = text.split('\n')[0]
    m = _PERSONA_HEAD.search(line)
    if not m:
        return None, None, None
    work, raw = m.group(1), m.group(2).strip()
    mm = re.match(u'^(.+?)（(.+?)）$', raw)
    if mm:
        name, cn = mm.group(1).strip(), mm.group(2).strip()
        cn = re.sub(u'^又称\\s*', u'', cn)
        return work, name, cn
    return work, raw, raw


def load_evidence():
    with io.open(os.path.join(EVID, 'oneshot_contacts66.json'), 'r',
                 encoding='utf-8') as fh:
        os_ev = json.load(fh)
    with io.open(os.path.join(EVID, 'ut_sprites66.json'), 'r',
                 encoding='utf-8') as fh:
        ut_ev = json.load(fh)
    return os_ev, ut_ev


def build_entries(os_ev, ut_ev, personas_idx):
    """按 `_personas.json` 的 `by_work` 分组构造 35 条注册记录。"""
    by_work = personas_idx.get('by_work') or {}
    os_ids = list(by_work.get('OneShot') or [])
    ut_ids = list(by_work.get('Undertale') or [])
    if len(os_ids) != 21 or len(ut_ids) != 14:
        raise SystemExit(u'!! `_personas.json.by_work` 的 OneShot/Undertale 份数不是 21/14：%d/%d'
                         % (len(os_ids), len(ut_ids)))

    # ---- OneShot：按 unlockId 建索引（george1..6 归并取 1 号） ----
    prof_by_unlock = {}
    for p in os_ev['profiles']:
        prof_by_unlock.setdefault(p['unlockId'], p)
    region_counts = os_ev['region_counts']

    out = []
    for nid in os_ids:
        unlock = OS_UNLOCK_OVERRIDE.get(nid)
        if unlock is None:
            unlock = nid[3:] if nid.startswith('os_') else nid
        prof = prof_by_unlock.get(unlock)
        if prof is None:
            raise SystemExit(u'!! OneShot 角色 %s 在 contacts 里找不到 unlockId=%r'
                             % (nid, unlock))
        raw = read_text(os.path.join(NPC_DIR, 'persona', nid + '.txt'))
        work, _pname, cn = parse_head(raw)
        if work != 'OneShot':
            raise SystemExit(u'!! %s 的 persona 首行作品名不是 OneShot：%r' % (nid, work))
        n_george = 6 if unlock == 'george1' else 1
        george_tail = (u'；官方 26 条 profile 里 George 有 george1..george6 六个变体，'
                       u'本条第 1 号' if n_george == 6 else u'')
        out.append({
            'id': nid,
            'name': prof['title'],
            'name_cn': cn or prof['title'],
            'tier': 'main',
            'chapters': [WORK_ONESHOT],
            'home_world': 'dark',
            'objects': [prof['walkspriteId']],
            'model': None,
            'needs_setting': False,
            'escape_via_bubble': False,
            'notes': (u'《OneShot》角色（第66轮注册）。原作区域 = %s'
                      u'（出处：用户提供的 contacts_metadata.json 的 subtitle）。'
                      u'`objects` = 官方 `walkspriteId`。'
                      u'★ `home_world` 显式写 `dark`（本项目的世界模型只有 光/暗 两分；'
                      u'写 `oneshot` 会被 `NpcDef` 静默改判成 `dark`）；'
                      u'`chapters=[oneshot]` 是**未来场景前缀锚**（当前无 oneshot.* 场景）%s。'
                      % (prof['region'], george_tail)),
            'persona': 'persona/%s.txt' % nid,
        })

    # ---- Undertale：sprite 取证 ----
    ut_roles = ut_ev['roles']
    for nid in ut_ids:
        rec = ut_roles.get(nid)
        if rec is None or not rec.get('objects'):
            raise SystemExit(u'!! Undertale 角色 %s 没取到 sprite 证据' % nid)
        raw = read_text(os.path.join(NPC_DIR, 'persona', nid + '.txt'))
        work, pname, cn = parse_head(raw)
        if work != 'Undertale':
            raise SystemExit(u'!! %s 的 persona 首行作品名不是 Undertale：%r' % (nid, work))
        how = rec['how']
        if how == 'overworld_4dir':
            how_cn = u'有四向行走图（取 down 帧）'
        elif how == 'overworld_tagged':
            how_cn = u'原作用 `overworld` 标的那一版'
        else:
            how_cn = u'★ 该角色在本素材集里**没有** overworld 行走图 ⇒ 取最接近本体的原作 sprite'
        out.append({
            'id': nid,
            'name': pname,
            'name_cn': cn or pname,
            'tier': 'main',
            'chapters': [WORK_UNDERTALE],
            'home_world': 'dark',
            'objects': list(rec['objects']),
            'model': None,
            'needs_setting': False,
            'escape_via_bubble': False,
            'notes': (u'《Undertale》角色（第66轮注册）。`objects` = 原作 sprite 名（%s，'
                      u'证据 `_evidence/ut_sprites66.json`）。'
                      u'★ 用户**没有**给 Undertale 侧的 contacts 式归属文件 ⇒ 这里登记的是'
                      u'**sprite 名**（`spr_*`），不是 GameMaker 对象名（`obj_*`）；'
                      u'与 OneShot 侧（官方 walkspriteId）同口径，都是"该作品里标识角色的资源名"。'
                      u'`chapters=[undertale]` 是未来场景前缀锚（当前无 undertale.* 场景）。'
                      % how_cn),
            'persona': 'persona/%s.txt' % nid,
        })
    return out


def patch_registry(entries, apply):
    raw = read_bytes(REG_PATH)
    data = json.loads(raw.decode('utf-8'))
    # —— 锚点：原样 dumps 必须与磁盘逐字节相同 ——
    if dump_json(data).encode('utf-8') != raw:
        raise SystemExit(u'!! 等价性锚点失败：本文件不是 `json.dumps(indent=1, ensure_ascii=False)` '
                         u'的产物 ⇒ 停下，不要盲写。')
    print(u'[anchor] 等价性锚点通过：dumps 能逐字节重现 %s' % os.path.basename(REG_PATH))

    old_n = len(data['npcs'])
    have = set(n['id'] for n in data['npcs'])
    dup = [e['id'] for e in entries if e['id'] in have]
    if dup:
        raise SystemExit(u'!! 这些 id 已经在注册表里了：%s' % dup)

    for e in entries:
        data['npcs'].append(_ordered(e))

    main_n = sum(1 for n in data['npcs'] if n.get('tier') == 'main')
    plain_n = sum(1 for n in data['npcs'] if n.get('tier') == 'plain')
    data['counts'] = {'main': main_n, 'plain': plain_n}
    data['source'] = (
        u'第49轮 UTMT 反编译（names49 普查）+ 本项目撰写；'
        u'第55轮：用户提供 13 份人设（assets/npc/persona/）+ 模型口径修正（见 model_policy）；'
        u'第64轮：用户重新提供《其余人物设定.txt》⇒ 人设 13 → 50（含 OneShot 21 / Undertale 14）；'
        u'第66轮（N4）：把 OneShot 21 + Undertale 14 共 35 条**跨作品 NPC 注册进本表**'
        u'（此前只到人设层、无人注册）。取值口径 —— OneShot 用官方 contacts_metadata.json 的'
        u' `title` / `subtitle`(区域) / `walkspriteId`；Undertale 用用户 UT素材/ 文件名里的'
        u'原作 sprite 名；两作品 `home_world` 一律显式 `dark`（本项目世界模型只有两分），'
        u'`chapters` 用作品 id 作未来场景前缀锚。证据见 '
        u'code-quality-audit/第66轮-大图连通与mod并入/_evidence/。')

    txt = dump_json(data)
    print(u'[registry] %d → %d 条（main %d / plain %d）' % (old_n, len(data['npcs']),
                                                          main_n, plain_n))
    if apply:
        with io.open(REG_PATH, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt)
        print(u'[registry] 已写入 %s' % REG_PATH)
    else:
        print(u'[registry] dry-run：未写盘')
    return data


def _ordered(e):
    return dict((k, e[k]) for k in ENTRY_KEYS)


def patch_placement(entries, apply):
    raw = read_bytes(PLACE_PATH)
    data = json.loads(raw.decode('utf-8'))
    if dump_json(data).encode('utf-8') != raw:
        raise SystemExit(u'!! 等价性锚点失败：%s 不是 `json.dumps(indent=1, ensure_ascii=False)` '
                         u'的产物 ⇒ 停下。' % os.path.basename(PLACE_PATH))
    print(u'[anchor] 等价性锚点通过：%s' % os.path.basename(PLACE_PATH))

    unpl = data['unplaced']
    added = 0
    for e in entries:
        if e['id'] in unpl:
            continue
        unpl[e['id']] = (
            u'%s 角色（第66轮注册）：**不属于 Deltarune 的任何房间** ⇒ 没有 `obj_npc_*` '
            u'站位脚本，也没有原作坐标可抄 ⇒ 如实挂在"未安置"，不给他编一个安身之所。'
            % (u'《OneShot》' if e['id'].startswith('os_') else u'《Undertale》'))
        added += 1
    data['counts']['unplaced'] = len(unpl)
    txt = dump_json(data)
    print(u'[placement] unplaced +%d → 共 %d 条；counts.unplaced=%d'
          % (added, len(unpl), data['counts']['unplaced']))
    if apply:
        with io.open(PLACE_PATH, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt)
        print(u'[placement] 已写入 %s' % PLACE_PATH)
    else:
        print(u'[placement] dry-run：未写盘')
    return data


def main(argv):
    apply = '--apply' in argv
    os_ev, ut_ev = load_evidence()
    with io.open(os.path.join(NPC_DIR, '_personas.json'), 'r', encoding='utf-8') as fh:
        personas_idx = json.load(fh)
    entries = build_entries(os_ev, ut_ev, personas_idx)
    print(u'[build] 构造出 %d 条（OneShot %d / Undertale %d）'
          % (len(entries),
             sum(1 for e in entries if e['id'].startswith('os_')),
             sum(1 for e in entries if e['id'].startswith('ut_'))))
    for e in entries:
        print(u'   %-22s %-26s %-24s ch=%s notes_len=%d'
              % (e['id'], e['name'], ','.join(e['objects']), e['chapters'][0],
                 len(e['notes'])))
    print()
    patch_registry(entries, apply)
    print()
    patch_placement(entries, apply)
    if not apply:
        print(u'\n(dry-run 完成；加 --apply 才真写盘)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
