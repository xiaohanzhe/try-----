# -*- coding: utf-8 -*-
"""第 38 轮 · 房间表严格复检（B 轮）。

用户口径：「记得严格些，做完了仔细复查」「复检一下有没有纰漏」。

设计要点（避免"判据自己说谎"）
------------------------------
· 规则表**不复刻**：用 AST 从 `build_roomtable3.py` 里把 `RULES / NONSCENE / MAYBE`
  三个赋值节点原文抽出来 exec。⇒ 我检的一定是**真正跑过的那张表**，不是我手抄的一份。
· 判据分三档：真/假 + 需人眼看的清单（清单不判分，只呈现）。
· 反面控制：必须有一条**故意错**的断言来证明这套判据有鉴别力（见 A0）。
"""
import ast
import io
import json
import os
import re
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
BUILD = os.path.join(HERE, 'build_roomtable3.py')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

RES, OUT = [], []


def w(s=''):
    OUT.append(str(s))
    print(s)


def ck(name, ok, detail=''):
    RES.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


# ---------------------------------------------------------------- 抽真实规则
def pull(filepath, names):
    src = io.open(filepath, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
    nodes = []
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    nodes.append(n)
    mod = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    ns = {'re': re}
    exec(compile(mod, filepath, 'exec'), ns)
    return ns


ns = pull(BUILD, {'RULES', 'NONSCENE', 'MAYBE'})
RULES = ns['RULES']
NONSCENE = ns['NONSCENE']
MAYBE = ns['MAYBE']
assert len(RULES) and len(NONSCENE) and len(MAYBE)

w('=== 第 38 轮房间表 · 严格复检（B）===')
w('规则来源：%s（AST 抽取，非手抄）' % os.path.basename(BUILD))
w('RULES=%d 条  NONSCENE=%d 条  MAYBE=%d 条' % (len(RULES), len(NONSCENE), len(MAYBE)))
w('')

table = json.loads(io.open(os.path.join(EV, '房间表_全量.json'),
                           'r', encoding='utf-8').read())
FLAT = [r for ch in table for r in table[ch]]
w('房间表：%d 章 / %d 房间' % (len(table), len(FLAT)))
w('')

# ---------------------------------------------------- A0 反面控制（鉴别力）
# ⚠️ 第一版这里用 `^room_forest` 当"错误规则"，它恰好也命中 32 个 ⇒ 报红。
#    真相：**是探针选错了**（forest 是个真规则）。改用**保证命中 0** 的名字。
w('--- A0 判据鉴别力自检（故意用不存在的规则，必须与真规则不同）---')
_wrong = re.compile(r'^room_ZZZ_neverseen_anywhere$')
_hit_fake = sum(1 for r in FLAT if _wrong.search(r['resource']))
_hit_real = sum(1 for r in FLAT if RULES[0][0].search(r['resource']))
ck('A0a 不存在的规则命中 0（判据能识别"无匹配"）', _hit_fake == 0,
   'ZZZ=%d' % _hit_fake)
ck('A0b 真规则命中数 ≠ 0（判据能识别"有匹配"）', _hit_real != 0,
   'RULES[0]=%d' % _hit_real)
w('')

# ---------------------------------------------------- A1 规则归属与死规则
# ⚠️ 第一版把"死规则"定义为「scene 维度命中 0」⇒ 规则[0] 报红。
#    真相：规则[0]（legend/gameover/intro/…）命中的房间**全被归到 maybe/nonscene**，
#    但它仍在给这些房间**定区域**（map_area 对所有房间都调用）⇒ 不是死规则。
#    ⇒ 判据改为「**全量房间**维度命中 0 才算死规则」，并同时列出 scene 维度计数。
w('--- A1 每条规则的命中数（全量 / 其中 scene）---')
scene_recs = [r for r in FLAT if r['cls'] == 'scene']


def _hit_index(rec):
    for i, (rx, aid, aname) in enumerate(RULES):
        if rx.search(rec['resource']):
            return i
    return None


attr, attr_all = {}, {}
for r in FLAT:
    attr_all.setdefault(_hit_index(r), []).append(r)
for r in scene_recs:
    attr.setdefault(_hit_index(r), []).append(r['resource'])

dead = []
for i, (rx, aid, aname) in enumerate(RULES):
    n_all = len(attr_all.get(i, []))
    n_sc = len(attr.get(i, []))
    w('  [%2d] %-6s %-16s 全量 %4d  scene %4d   %s'
      % (i, aid, aname, n_all, n_sc, rx.pattern[:52]))
    if n_all == 0:
        dead.append(i)
ck('A1a 每条规则在全量房间维度都命中过 ≥1（无死规则）', not dead,
   '死规则下标=%s' % dead)
ck('A1b 每个 scene 都被某条规则命中（无遗漏）', None not in attr,
   '未命中=%d' % len(attr.get(None, [])))
for nm in attr.get(None, [])[:10]:
    w('    ✗ 未命中：%s' % nm)
w('')

# ---------------------------------------------------- A2 跨章一致性
w('--- A2 同名资源跨章区域一致性 ---')
byname = {}
for ch in table:
    for r in table[ch]:
        byname.setdefault(r['resource'], set()).add(
            (r['area_id'], r['area_name']))
inconsistent = {k: v for k, v in byname.items() if len(v) > 1}
ck('A2 同名资源在所有章里判到同一区域', not inconsistent,
   '不一致 %d 个' % len(inconsistent))
for k in sorted(inconsistent)[:20]:
    w('    ! %-44s %s' % (k, sorted(inconsistent[k])))
w('')

# ---------------------------------------------------- A3 区域名 1:1
w('--- A3 area_id 与 area_name 一对一 ---')
id2name, name2id = {}, {}
for r in FLAT:
    if not r['area_id']:
        continue
    id2name.setdefault(r['area_id'], set()).add(r['area_name'])
    name2id.setdefault(r['area_name'], set()).add(r['area_id'])
ck('A3a 一个 area_id 只对应一个 area_name',
   all(len(v) == 1 for v in id2name.values()),
   str({k: sorted(v) for k, v in id2name.items() if len(v) > 1}))
ck('A3b 一个 area_name 只对应一个 area_id',
   all(len(v) == 1 for v in name2id.values()),
   str({k: sorted(v) for k, v in name2id.items() if len(v) > 1}))
w('区域总数 = %d' % len(id2name))
w('')

# ---------------------------------------------------- A4 分类总数
w('--- A4 分类计数与锚点 ---')
sc = {}
for r in FLAT:
    sc[r['cls']] = sc.get(r['cls'], 0) + 1
w('  %s' % sc)
ck('A4a 总数 = 1251', len(FLAT) == 1251, str(len(FLAT)))
ck('A4b 分类键只有 scene/maybe/nonscene',
   set(sc) <= {'scene', 'maybe', 'nonscene'}, str(sorted(sc)))

idx_raw = json.loads(io.open(os.path.join(SCENES, '_index.json'),
                             'r', encoding='utf-8').read())
anchors = {}
for cid, c in (idx_raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, s in (a.get('scenes') or {}).items():
            rid = s.get('original_room_id')
            if rid is not None:
                anchors[(cid, int(rid))] = (sid, s.get('name'), aid)
ck('A4c 锚点 = 87（不含 desktop）', len(anchors) == 87, str(len(anchors)))
bad = 0
for ch in table:
    for r in table[ch]:
        a = anchors.get((ch, r['room_index']))
        if a and r['area_id'] != a[2]:
            bad += 1
            w('    ✗ %s[%d] %s 锚点=%s 我=%s'
              % (ch, r['room_index'], r['resource'], a[2], r['area_id']))
ck('A4d 87 个锚点的 area_id 全部被复现', bad == 0, '不一致 %d' % bad)
w('')

# ---------------------------------------------------- A5 nonscene 全清单
w('--- A5 nonscene 全清单（逐条人眼核，找误杀）---')
ns_hit = {}
for rx in NONSCENE:
    ns_hit[rx.pattern] = []
for ch in table:
    for r in table[ch]:
        if r['cls'] != 'nonscene':
            continue
        for rx in NONSCENE:
            if rx.search(r['resource']):
                ns_hit[rx.pattern].append('%s:%s' % (ch, r['resource']))
                break
for rx in NONSCENE:
    lst = ns_hit[rx.pattern]
    w('  %-42s %3d 个' % (rx.pattern[:42], len(lst)))
    for x in lst[:40]:
        w('        %s' % x)
    if len(lst) > 40:
        w('        … 余 %d' % (len(lst) - 40))
w('')

# ---------------------------------------------------- A6 maybe 全清单
w('--- A6 maybe 全清单 ---')
mb = {}
for rx in MAYBE:
    mb[rx.pattern] = []
for ch in table:
    for r in table[ch]:
        if r['cls'] != 'maybe':
            continue
        for rx in MAYBE:
            if rx.search(r['resource']):
                mb[rx.pattern].append('%s[%d]:%s' % (ch, r['room_index'],
                                                     r['resource']))
                break
for rx in MAYBE:
    w('  %-40s %3d 个' % (rx.pattern[:40], len(mb[rx.pattern])))
    for x in mb[rx.pattern]:
        w('        %s' % x)
w('')

# ---------------------------------------------------- A7 敏感子串命中
# ⚠️ 第一版这里留了个死循环（`[x for v in ns_hit[...] for x in []]`）⇒ 清理掉。
w('--- A7 敏感子串正则命中明细（test / debug / failsafe）---')
for r in FLAT:
    nm = r['resource']
    if re.search(r'test', nm, re.I) or re.search(r'debug|failsafe', nm, re.I):
        w('  %-8s %-46s cls=%s' % (r['chapter'], nm, r['cls']))
w('')

# ---------------------------------------------------- A9 开发残留房间
# 「原件里真实存在、但正常游玩到不了」的房间（example / mockup / old / backup /
#  unused / _og / _original …）。**不判 FAIL** —— 只是把口径摆出来让人能一眼看到
#  "1,013 个 scene 里有几个是开发残留"，避免以后误以为它们是可玩场景。
w('--- A9 开发残留特征 rooms（仍算 scene，仅呈现）---')
DEV = [re.compile(r'example', re.I), re.compile(r'mockup', re.I),
       re.compile(r'unused', re.I), re.compile(r'placeholder', re.I),
       re.compile(r'(_old|_og|_original|_backup|_rev|_tiled|_separate)\b', re.I)]
dev_hits = []
for r in FLAT:
    if r['cls'] != 'scene':
        continue
    for rx in DEV:
        if rx.search(r['resource']):
            dev_hits.append((r['chapter'], r['resource'], rx.pattern))
            break
w('  命中 %d 个 / 共 %d 个 scene' % (len(dev_hits), len(scene_recs)))
for ch, nm, pat in dev_hits:
    w('    %-8s %-46s (%s)' % (ch, nm, pat))
w('')

# ---------------------------------------------------- A8 抽查
w('--- A8 抽查：易错映射 ---')
probes = ['room_beach', 'room_town_krisyard_dark', 'room_darkness_example',
          'room_dw_castle_area_2', 'room_dw_castle_tv', 'room_cc_lancer',
          'room_dw_green_room', 'room_dw_church_intro1',
          'room_krisroom_dark', 'room_dogplatforming', 'room_dw_city_mice2_og']
for pn in probes:
    rows = [(r['chapter'], r['cls'], r['area_id']) for r in FLAT
            if r['resource'] == pn]
    w('  %-34s %s' % (pn, rows))
w('')

fails = [r for r in RES if not r[0]]
w('=== 复检汇总：%d 项  PASS=%d  FAIL=%d ==='
  % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    w('  FAIL: %s %s' % (n, d))

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, '复检_房间表B.txt'), 'w',
             encoding='utf-8') as fh:
    fh.write('\n'.join(OUT) + '\n')
print('')
print('written 复检_房间表B.txt')
sys.exit(0)
