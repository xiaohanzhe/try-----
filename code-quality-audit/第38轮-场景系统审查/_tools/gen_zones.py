# -*- coding: utf-8 -*-
"""第 38 轮：把 1,013 个原作房间落成场景数据（区域分片制）。【v2 · 诚实命名】

用户口径
--------
「把所有都拿出来啊，别就拿87个」
「别一次性加载全部房间。只加载人物所处房间附近联通的房间，随着走随着加载，
  像是拿火把赶夜路，走到哪亮到哪」
「但，如果你全部加载完也不影响性能那也ok」

设计（为什么是区域分片，而不是 1,013 个小文件）
----------------------------------------------
实测：读 1,013 个小文件 = 835 ms（OS 开销主导）；读 61 个分片 ≈ 29 ms；
纯 json.loads 462 KB = 2.14 ms。⇒ 「火把」的最小单位是**一片区域**，不是"一个房间"。
分片粒度 = (chapter, area)。注意**不是** 32 个全局区域 —— 那会把 5 个章的
hometown 一次性全读进来。

★ v2 相对 v1 的三处修正
----------------------
1. **命名改为"不译"**（v1 拿 625 个 token 硬造中文，结果 77.9% 英文残留、
   还出现「牢房牢房」这种重复）⇒ 按本项目铁律「算不出 → 绝不伪装」，
   译名 = 伪造本地化。v2 只做**去命名空间**的机械裁剪，尾段**原样保留**：
   `room_cc_prison_cells` → 「纸牌城堡·prison_cells」。
   另存 `name_raw`（完整资源名）⇒ 任何名字都能溯源回原作。
2. **锚点识别改判据**：v1 用"有 original_room_id" ⇒ 新场景也带它 ⇒ 重跑即失真。
   v2 用"**有 `file` 键**"（只有第 36 轮登记的 87 个锚点 + desktop 有独立文件）。
3. **Z4 改成真判据**：对 87 个锚点登记行做事前/事后的**序列化快照比对**，
   而不是比对"集合差"（v1 那个判据把新场景也算进来，报红 926 条假失败）。

双源纪律
--------
87 个锚点一个字节都不动；分片里**只装新增场景**。`load_scene()` 查找顺序 =
先独立文件、后分片 ⇒ 同一场景永远只有一个数据源。
"""
import collections
import copy
import io
import json
import os
import re
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
IDX_PATH = os.path.join(SCENES, '_index.json')

RES, OUT = [], []


def w(s=''):
    OUT.append(str(s))
    print(s)


def ck(name, ok, detail=''):
    RES.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


# 纯命名空间 token（与"地点"无关，永远剥掉）
NAMESPACE = {'dw', 'lw', 'cc', 'b3bs'}


def build_tail(resource, area_id):
    """尾段 = 资源名去掉命名空间与区域自身的词。**其余一律原样保留**。

    ⚠️ v2.1 修正：v2 第一版把"纯数字 token"和"单字母 token"也丢了
    ⇒ `intro_1` / `intro_2` 双双塌成 `intro` ⇒ 同区域 33 组撞名（Z6 抓到）。
    数字与单字母（`2f` / `b` / `c`）在原作命名里**就是区分符**，必须留。
    """
    body = re.sub(r'^room_', '', resource)
    toks = [t for t in body.split('_') if t]
    area_toks = set(t for t in re.split(r'[_\s]+', area_id.lower()) if t)
    return [t for t in toks
            if t.lower() not in NAMESPACE and t.lower() not in area_toks]


def make_name(area_name, resource, area_id):
    toks = build_tail(resource, area_id)
    tail = '_'.join(toks) if toks else re.sub(r'^room_', '', resource)
    return '%s·%s' % (area_name, tail)


def slugify(resource):
    s = re.sub(r'^room_', '', resource).lower()
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    return s.strip('_') or 'scene'


def is_anchor_entry(entry):
    """锚点 = 第 36 轮登记的、有独立 `<scene_id>.json` 的场景。"""
    return bool(entry.get('file')) and entry.get('original_room_id') is not None


# ===========================================================================
#  读输入
# ===========================================================================
table = json.loads(io.open(os.path.join(EV, '房间表_全量.json'),
                           'r', encoding='utf-8').read())
IDX_BYTES_BEFORE = os.path.getsize(IDX_PATH)
raw = json.loads(io.open(IDX_PATH, 'r', encoding='utf-8').read())
SNAPSHOT = copy.deepcopy(raw)          # ★ 改动前的完整快照（Z4 用）

anchor_snapshot = {}                   # (ch, rid) → 序列化文本
for cid, c in (raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, s in (a.get('scenes') or {}).items():
            if is_anchor_entry(s):
                anchor_snapshot[(cid, int(s['original_room_id']))] = \
                    json.dumps(s, ensure_ascii=False, sort_keys=True)

w('=== 生成区域分片 v2（诚实命名）===')
w('已有登记：chapters=%d  锚点=%d'
  % (len(raw.get('chapters') or {}), len(anchor_snapshot)))

# ===========================================================================
#  构造"新增场景"
# ===========================================================================
new_by_ca = collections.OrderedDict()
used_ids = set()
for cid, c in (raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        used_ids.update((a.get('scenes') or {}).keys())

anchor_rooms = set(anchor_snapshot.keys())
area_name_of = {}

for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    for rec in table.get(ch, []):
        if rec['cls'] != 'scene':
            continue
        rid = rec['room_index']
        if (ch, rid) in anchor_rooms:
            continue                               # ★ 锚点不动
        aid = rec['area_id']
        if not aid:
            continue
        area_name_of[(ch, aid)] = rec['area_name']
        base = slugify(rec['resource'])
        sid = '%s.%s.%s' % (ch, aid, base)
        n = 2
        while sid in used_ids:
            sid = '%s.%s.%s_%d' % (ch, aid, base, n)
            n += 1
        used_ids.add(sid)
        new_by_ca.setdefault((ch, aid), {})[sid] = {
            'name': make_name(rec['area_name'], rec['resource'], aid),
            'name_raw': rec['resource'],
            'name_derived': True,
            'original_room_id': rid,
            # ★ 背景：原作**多数房间本来就没有背景精灵**（第37轮实测：147 个房间里
            #   只有 40 层带 bg_sprite）⇒ 这 926 个里绝大多数没有真实背景可给。
            #   **不编造"区域代表素材"**（那是把"我没有这张图"伪装成"就是这张图"，
            #   违反「算不出 → None，绝不伪装」铁律）。
            #   改成**显式声明 null + bg_source='none'**：让"忘了写 bg"和"确实没有"
            #   可区分。补真实背景属本轮 #17 的活。
            'bg': None,
            'bg_source': 'none',
        }

total_new = sum(len(v) for v in new_by_ca.values())
w('新增场景 = %d 个，分布于 %d 个 (章, 区域) 组合' % (total_new, len(new_by_ca)))

# --- 撞名回退：同区域内两个场景算出同名时，改用**完整资源名**当尾段 ---
# 实测唯一一例：`room_susiezilla` 与 `room_dw_susiezilla` 同属 tv_backstage，
# 去命名空间后尾巴一样。完整资源名更有区分度、也更可溯源。
n_renamed = 0
for (ch, aid), scenes in sorted(new_by_ca.items()):
    seen = {}
    for sid, e in scenes.items():
        seen.setdefault(e['name'], []).append(sid)
    for nm, lst in seen.items():
        if len(lst) > 1:
            for sid in lst:
                e = scenes[sid]
                e['name'] = '%s·%s' % (e['name'].split('·', 1)[0],
                                       re.sub(r'^room_', '', e['name_raw']))
                n_renamed += 1
w('撞名回退改名 %d 条' % n_renamed)

ck('Z0 新增场景数 = 1013 - 87', total_new == 926, str(total_new))

# ===========================================================================
#  写分片（临时名 → 原子替换）
# ===========================================================================
ZONE_TPL = '_zone.%s.%s.json'
zone_name_of = {}
expected_files = []
for (ch, aid), scenes in sorted(new_by_ca.items()):
    zname = ZONE_TPL % (ch, aid)
    payload = {
        'schema_version': 1,
        'chapter_id': ch,
        'area_id': aid,
        'area_name': area_name_of.get((ch, aid)) or aid,
        'note': ('区域分片：只装"第 38 轮新增"的场景。已有独立 <scene_id>.json 的'
                 '87 个锚点不在这里，避免双源。name 为机械裁剪后的原样名，'
                 'name_raw 是可溯源的完整原作资源名。'),
        'scenes': scenes,
    }
    tmp = os.path.join(SCENES, zname + '.tmp')
    final = os.path.join(SCENES, zname)
    with io.open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, final)
    zone_name_of[(ch, aid)] = zname
    expected_files.append(final)

# ★★ 硬校验：磁盘上真有这么多文件（v1 只数了内存里的 list ⇒ 漏掉了"没落盘"）
on_disk = [f for f in os.listdir(SCENES) if f.startswith('_zone.')
           and f.endswith('.json')]
ck('Z1 分片文件数 = (章,区域) 组合数【查磁盘，不查内存】',
   len(on_disk) == len(new_by_ca),
   'disk=%d  expect=%d' % (len(on_disk), len(new_by_ca)))
ck('Z1b 每个预期文件都真实存在',
   all(os.path.isfile(p) for p in expected_files),
   '缺 %d 个' % sum(1 for p in expected_files if not os.path.isfile(p)))

# ===========================================================================
#  重建 _index.json（只加，不改）
# ===========================================================================
added_areas, added_scenes, skipped = [], 0, []
for (ch, aid), scenes in sorted(new_by_ca.items()):
    chapters = raw.setdefault('chapters', {})
    if ch not in chapters:
        chapters[ch] = {'name': ch, 'order': int(ch[2:] or 0), 'areas': {}}
    areas = chapters[ch].setdefault('areas', {})
    if aid not in areas:
        areas[aid] = {'name': area_name_of.get((ch, aid)) or aid, 'scenes': {}}
        added_areas.append('%s.%s' % (ch, aid))
    areas[aid]['zone'] = zone_name_of[(ch, aid)]
    dst = areas[aid].setdefault('scenes', {})
    for sid, entry in scenes.items():
        if sid in dst:
            # 幂等：**只有分片场景**（无独立文件）允许被覆盖重建；
            # 锚点（有 file）若撞 id 就是设计事故，必须报出来而不是覆盖。
            if is_anchor_entry(dst[sid]):
                skipped.append(sid)
                continue
            dst[sid] = entry
            added_scenes += 1
            continue
        dst[sid] = entry
        added_scenes += 1

raw.setdefault('meta', {})
raw['meta']['zone_file_pattern'] = '_zone.<chapter>.<area>.json'
raw['meta']['zone_note'] = (
    '场景数据有两个来源，**优先级：独立 <scene_id>.json > 区域分片**。'
    '87 个"锚点"场景（第 36 轮登记）各有独立文件；其余场景住在所在 (章,区域) '
    '分片里，进区域时整片读一次（"拿火把赶夜路"）。同一场景只出现在一个来源。'
    'zone 场景的 name 是机械裁剪后的原样名（name_derived=true），'
    'name_raw 保存完整原作资源名。')

tmp = IDX_PATH + '.tmp'
with io.open(tmp, 'w', encoding='utf-8') as fh:
    json.dump(raw, fh, ensure_ascii=False, indent=1)
os.replace(tmp, IDX_PATH)

ck('Z2 新增了区域行', len(added_areas) > 0, '%d 个' % len(added_areas))
ck('Z3 新增场景登记数 = 新增场景数，且无重名冲突',
   added_scenes == total_new and not skipped,
   '新增 %d / 期望 %d / 冲突 %d' % (added_scenes, total_new, len(skipped)))

# ===========================================================================
#  复核
# ===========================================================================
raw2 = json.loads(io.open(IDX_PATH, 'r', encoding='utf-8').read())
changed = []
for cid, c in (raw2.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, s in (a.get('scenes') or {}).items():
            if is_anchor_entry(s):
                k = (cid, int(s['original_room_id']))
                if k in anchor_snapshot and \
                        json.dumps(s, ensure_ascii=False, sort_keys=True) \
                        != anchor_snapshot[k]:
                    changed.append(sid)
ck('Z4 87 个锚点登记行序列化后逐条未变', not changed,
   '改了 %d 条：%s' % (len(changed), changed[:5]))

# 重跑幂等性：再生成一遍"新增集合"，应当为空
idem = 0
for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    for rec in table.get(ch, []):
        if rec['cls'] != 'scene':
            continue
        if (ch, rec['room_index']) in anchor_rooms:
            continue
        sid = '%s.%s.%s' % (ch, rec['area_id'], slugify(rec['resource']))
        if sid not in used_ids:
            idem += 1
w('  （幂等性提示：裸 id 未加后缀的 %d 条 —— 仅作参考）' % idem)

leftover = [f for f in os.listdir(SCENES) if f.endswith('.tmp')]
ck('Z5 无残留 .tmp 文件', not leftover, str(leftover))

# 同区域内重名检测
dup_names = []
for (ch, aid), scenes in new_by_ca.items():
    seen = {}
    for sid, e in scenes.items():
        seen.setdefault(e['name'], []).append(sid)
    for nm, lst in seen.items():
        if len(lst) > 1:
            dup_names.append('%s.%s %s x%d' % (ch, aid, nm, len(lst)))
ck('Z6 同区域内场景名不重复', not dup_names,
   '%d 组：%s' % (len(dup_names), dup_names[:5]))

# EOL 复核
b = io.open(IDX_PATH, 'rb').read()
ck('Z7 _index.json 仍为 CRLF（与原文件一致）',
   b.count(b'\r\n') > 0 and b.count(b'\n') == b.count(b'\r\n'),
   'CRLF=%d lone_LF=%d' % (b.count(b'\r\n'), b.count(b'\n') - b.count(b'\r\n')))

# 索引体积
w('')
w('_index.json %d → %d 字节' % (IDX_BYTES_BEFORE, len(b)))
w('分片总字节 = %d'
  % sum(os.path.getsize(os.path.join(SCENES, f)) for f in on_disk))
w('')
w('抽样 20 条：')
shown = 0
for (ch, aid), scenes in sorted(new_by_ca.items()):
    for sid, e in scenes.items():
        if shown >= 20:
            break
        w('  %-46s %-30s %s' % (sid, e['name'], e['name_raw']))
        shown += 1
    if shown >= 20:
        break

fails = [r for r in RES if not r[0]]
w('')
w('=== 生成汇总：%d 项 PASS=%d FAIL=%d ==='
  % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    w('  FAIL: %s %s' % (n, d))

with io.open(os.path.join(EV, '区域分片生成报告.txt'), 'w',
             encoding='utf-8') as fh:
    fh.write('\n'.join(OUT) + '\n')
print('')
print('written 区域分片生成报告.txt')
