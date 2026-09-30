# -*- coding: utf-8 -*-
"""第69轮 · 注册 26 位新增角色（黄魂 15 + Outertale 11）—— **当前被素材阻塞，故意拒写**。

★★★ 为什么本轮**不注册**（这是结论，不是漏做）
------------------------------------------------
`npc_system.load_registry()` 是"这个 NPC 在不在世上"的唯一登记处 —— 所以第69轮
确实**应该**登记这 26 位。但注册表有一条**硬契约**：

    code-quality-audit/第49轮-NPC与球容器/verify_npc49.py:110
        check('B4', all(n.objects for n in REG.all()), '每条 NPC 都有原作物件名')

即：**注册表里不许有无素材锚点的 NPC**。而 `objects` 的合法来源是"该作品里标识角色的
资源名"（第66轮 N4 的原文口径：OneShot 用官方 `contacts_metadata.json` 的 `walkspriteId`、
Undertale 用原文 sprite 名）。**黄魂与 Outertale 的素材还压在 apk 里没解包**
（`黄魂.apk` / `outertale.apk` / `红与黄.apk`）⇒ 现在填 `objects` 只能靠编。

后果不是"先记着、以后再补"，而是两条**实打实的坏结果**：
  1. `verify_npc49` **B4 立刻报红** ⇒ 要么改坏一条真判据，要么留着红；
  2. 26 个 `objects` 为空的 NPC **没有贴图、没法定点位** ⇒ 会变成 26 个"登记了但画不出来"
     的隐形 NPC —— 正是本项目最贵的坑「**看起来记了、其实没接线**」。

⇒ 按第66轮 N4 的**既有次序**（先有素材证据、再注册），注册挪到"素材提取"那一轮。
   本工具留在仓库里，并被做成**缺证据就拒写** —— 不给后面留一颗"跑一下就撞 B4"的地雷。

口径（严格沿用第66轮 N4，不另立一套）
------------------------------------
* `tier = 'main'`（有完整人设 ⇒ 走模型，与既有 50 条人设记录一致）；
* `home_world` **显式写 `dark`**（本项目世界模型只有 光/暗 两分；
  写别的值会被 `NpcDef.__init__` **静默改判**成 `dark`）；
* `chapters = [作品 slug]`（与第66轮 `oneshot` / `undertale` 同款小写单词；
  黄魂 → `undertale_yellow`、Outertale → `outertale`）；
* `model = None`（第55轮口径：所有 NPC 都不单独指定模型，跟随 App 配置）；
* `needs_setting = False` **且** `persona = 'persona/<id>.txt'`
  （`NpcDef` 注释：`needs_setting = (persona is None)` 是唯一关系）；
* `escape_via_bubble = False`。

★ 另有一条用户新口径**不在本表**（故意不写进来）
------------------------------------------------
用户第69轮：「**niko 可自由穿行所有世界，其余 ut 及其同人只能在非暗世界穿梭**」。
这是**穿行域**，不是 `home_world`。而 `NpcDef.__slots__` 是固定的 ⇒ 往 JSON 里塞一个
它不认识的键会被 `npc_from_dict` **静默忽略**（"看起来记了、其实没接线"）。
⇒ 留给「跨世界机制」轮：先把字段加进 `NpcDef.__slots__` + `npc_from_dict` + `to_dict`，
再落数据，并配回归锁位。

用法
----
    python _tools/register_npcs69.py            # dry：只打印（本轮预期就是"报告被阻塞"）
    python _tools/register_npcs69.py --write    # 素材证据齐备后才会真的写
"""
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
N = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
EV = os.path.join(ROOT, 'code-quality-audit', '第69轮-人设数据面重建', '_evidence')

DO_WRITE = '--write' in sys.argv
FAIL = 0
LINES = []


def w(s=''):
    print(s)
    LINES.append(str(s))


def ok(m):
    w('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    w('[FAIL] %s' % m)


#: 作品 slug：与第66轮的 `oneshot` / `undertale` 同款
WORK_SLUG = {'Undertale Yellow': 'undertale_yellow', 'Outertale': 'outertale'}
#: ★★ 素材证据文件（`{id: [资源名, ...]}`）：**没有它就不许注册**
OBJ_EVIDENCE = {
    'undertale_yellow': os.path.join(EV, 'objects_undertale_yellow.json'),
    'outertale': os.path.join(EV, 'objects_outertale.json'),
}
EXPECT_NEW = 26
EXPECT_TOTAL = 96


def _dump():
    out = os.path.join(EV, 'register_npcs69.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(LINES) + '\n')
    w('')
    w('落盘 %s' % out)
    w('RESULT: FAIL=%d' % FAIL)


def _load_objs():
    """→ {id: [objects]}；文件缺失 = 该作品素材未就位。"""
    out, missing = {}, []
    for slug, p in OBJ_EVIDENCE.items():
        if not os.path.isfile(p):
            missing.append('%s（缺 %s）' % (slug, os.path.basename(p)))
            continue
        try:
            d = json.loads(io.open(p, 'rb').read().decode('utf-8'))
        except Exception as e:
            missing.append('%s（%s 解析失败 %r）' % (slug, os.path.basename(p), e))
            continue
        for k, v in (d or {}).items():
            if isinstance(v, list) and v:
                out[k] = v
    return out, missing


def main():
    reg_p = os.path.join(N, '_registry.json')
    old = json.loads(io.open(reg_p, 'rb').read().decode('utf-8'))
    recs = old.get('npcs') or []
    have = {r['id'] for r in recs}
    w('_registry.json 现有 = %d 条' % len(recs))

    pj = json.loads(io.open(os.path.join(N, '_personas.json'), 'rb').read().decode('utf-8'))
    per = {r['id']: r for r in (pj.get('personas') or [])}
    w('_personas.json = %d 条' % len(per))

    todo = sorted(i for i in per if i not in have)
    w('待登记 = %d 条' % len(todo))
    if len(todo) != EXPECT_NEW:
        bad('待登记 %d ≠ 期望 %d' % (len(todo), EXPECT_NEW))

    # ---- ★★ 闸门：素材证据 ----
    w('')
    w('=== 素材证据闸（`objects` 必须有据；否则会撞 `verify_npc49` B4）===')
    objs, missing = _load_objs()
    if missing:
        for m in missing:
            bad('素材未就位：%s' % m)
        w('')
        w('⇒ **拒绝注册**。理由：`verify_npc49.py:110` 的 B4 = '
          '「每条 NPC 都有原作物件名」，26 位新人 `objects` 为空会立刻报红；'
          '而 `objects` 只能来自解包产物（第66轮 N4 的既有次序：先有素材证据、再注册）。')
        w('⇒ 另外：`objects` 为空的 NPC 没有贴图、没法定点位 ⇒ 会变成'
          '"登记了但画不出来"的隐形 NPC（本项目最贵的坑）。')
        w('⇒ 落地动作留在「素材提取」轮：先解 `黄魂.apk`/`outertale.apk`/`红与黄.apk`，')
        w('   产出 `_evidence/objects_undertale_yellow.json` 与 `objects_outertale.json`，再跑本工具。')
        _dump()
        return 1
    ok('★ 两个作品的素材证据都在盘上（%d 个 id 有 objects）' % len(objs))

    # ---- 组装 ----
    new_recs, blocked = [], []
    for i in todo:
        r = per[i]
        slug = WORK_SLUG.get(r['work'])
        if slug is None:
            bad('%s 的作品 %r 未在 WORK_SLUG 里' % (i, r['work']))
            continue
        if not objs.get(i):
            blocked.append(i)
            continue
        new_recs.append(collections.OrderedDict((
            ('id', i), ('name', r['name']), ('name_cn', r['name']),
            ('tier', 'main'), ('chapters', [slug]), ('home_world', 'dark'),
            ('objects', list(objs[i])), ('model', None), ('needs_setting', False),
            ('escape_via_bubble', False),
            ('notes', '《%s》角色。本次由 `_tools/register_npcs69.py` 登记（第69轮）；'
                      '`objects` 出自解包产出 `_evidence/objects_%s.json`。' % (r['work'], slug)),
            ('persona', 'persona/%s.txt' % i),
        )))
    if blocked:
        bad('以下 id 缺素材证据，拒写：%s' % blocked)
        _dump()
        return 1

    old_keys = {k for x in recs for k in x}
    new_keys = {k for x in new_recs for k in x}
    if new_keys - old_keys:
        bad('新记录引入了既有记录没有的键 %s' % sorted(new_keys - old_keys))
    else:
        ok('★ 新记录的键集 ⊆ 既有记录的键集（同构）')

    merged = recs + new_recs
    counts = collections.OrderedDict()
    for x in merged:
        counts[x.get('tier', 'plain')] = counts.get(x.get('tier', 'plain'), 0) + 1
    w('')
    w('合并后 = %d 条，counts = %s' % (len(merged), dict(counts)))
    if len(merged) != EXPECT_TOTAL:
        bad('合并后 %d ≠ 期望 %d' % (len(merged), EXPECT_TOTAL))
    if len({x['id'] for x in merged}) != len(merged):
        bad('合并后有重复 id')

    nxt = collections.OrderedDict()
    for k, v in old.items():
        if k == 'npcs':
            nxt['npcs'] = merged
        elif k == 'counts':
            nxt['counts'] = counts
        else:
            nxt[k] = v
    nxt.setdefault('npcs', merged)
    nxt.setdefault('counts', counts)
    nxt['round69'] = {
        'what': '注册 26 位新增角色（黄魂 15 hy_* + Outertale 11 ot_*）⇒ 70 → %d 条' % EXPECT_TOTAL,
        'why': 'load_registry() 是"这个 NPC 在不在世上"的唯一登记处；只加 persona 文件不登记 ⇒ 场景里不出现。',
        'objects': '来自解包产出（第66轮 N4 的既有次序：先素材证据、再注册）。',
        '★ 未落表的用户口径': ('「niko 可自由穿行所有世界，其余 ut 及其同人只能在非暗世界穿梭」'
                        '= **穿行域**，不是 home_world；`NpcDef.__slots__` 固定，塞未知键会被静默忽略 ⇒ '
                        '留给"跨世界机制"轮（先改 NpcDef 再落数据 + 配回归锁位）。'),
        'tool': 'code-quality-audit/第69轮-人设数据面重建/_tools/register_npcs69.py',
    }

    if DO_WRITE:
        text = json.dumps(nxt, ensure_ascii=False, indent=1)
        with io.open(reg_p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        w('')
        w('★ 已写盘 _registry.json（%d 字节）' % len(text.encode('utf-8')))
        w('')
        w('=== 回读自检 ===')
        back = json.loads(io.open(reg_p, 'rb').read().decode('utf-8'))
        nb = back['npcs']
        if len(nb) == EXPECT_TOTAL:
            ok('回读 count=%d' % len(nb))
        else:
            bad('回读 count=%d ≠ %d' % (len(nb), EXPECT_TOTAL))
        if back['counts'] == counts:
            ok('counts 与实际分层一致：%s' % dict(counts))
        else:
            bad('counts 不符')
        miss = [x['id'] for x in nb if x.get('persona')
                and not os.path.isfile(os.path.join(N, x['persona']))]
        if not miss:
            ok('★ 所有 persona 引用都指向真实文件')
        else:
            bad('persona 引用指向不存在的文件：%s' % miss)
        # ★ B4 预检：不许有无 objects 的 NPC
        empty_obj = [x['id'] for x in nb if not x.get('objects')]
        if not empty_obj:
            ok('★ B4 预检通过：全部 %d 条都有原作物件名' % len(nb))
        else:
            bad('B4 会报红：无 objects 的 = %s' % empty_obj)
        try:
            sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
            from modules import npc_system
            reg = npc_system.load_registry(os.path.join(ROOT, 'ralsei_pet'))
            if len(reg) == EXPECT_TOTAL:
                ok('★ `load_registry()` 实测载入 %d 条（含 26 位新人）' % len(reg))
            else:
                bad('产品代码只载入 %d 条 ≠ %d' % (len(reg), EXPECT_TOTAL))
            absent = [i for i in todo if i not in reg]
            ok('★ 26 位新人全部可被产品代码查到') if not absent else \
                bad('产品代码查不到：%s' % absent)
            w('  产品侧分层：main=%d plain=%d' % (len(reg.main_npcs()), len(reg.plain_npcs())))
        except Exception as e:
            bad('用产品代码加载失败：%r' % (e,))

    _dump()
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
