# -*- coding: utf-8 -*-
"""第113轮j · 逐令牌回验：文档/判据里引用的每个事实，逐个回原文件 `in` 一次。

为什么必须做
------------
记忆与文档里的数字/路径/名字会**随压缩与手改悄悄失真**。2026-09-23 就靠这一步
抓到一个被压丢的 hash。本脚本只做一件事：把令牌分成「必须出现在哪」的清单，
逐个 `in` / 精确取值，报 PASS/FAIL。

★ 判据形状：`need_in[(file, token)] = True` ⇒ 该文件必须含该 token。
  数字类用**精确取值**（读源码/数据算出，不与文档比字面），因为"改文档去迎合
  脚本"是本末倒置 —— 脚本要能发现"文档写了但产品里没有"。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
DOC = os.path.join(ROUND, '_evidence', 'Validation_113j.md')

LIFE = os.path.join(PET, 'modules', 'npc_life.py')
MAIN = os.path.join(PET, 'src', 'main.py')
CHK = os.path.join(HERE, 'check113j.py')

_n_pass = 0
_n_fail = 0


def ok(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


li = rd(LIFE)
mn = rd(MAIN)
ck = rd(CHK)
doc = rd(DOC)

print('=== 1 产品侧令牌：文档说有的，源码里必须真有 ===')
for tok in ('room_word', 'place_hint', 'place_container',
            'PLACE_SEP', 'PLACE_JOIN_ALT', 'PLACE_FILLER'):
    ok('npc_life.py 含 `%s`' % tok, tok in li)

for tok in ('_scene_label_map', '_scene_place_label', '_npc_scene_id',
            'npc_life_mod.place_hint', 'npc_placement.home_of',
            'npc_life_mod.place_container', 'PLACE_JOIN_ALT'):
    ok('main.py 含 `%s`' % tok, tok in mn)

print()
print('=== 2 判据侧：check113j 里真有这些段 ===')
for tok in ('_scene_place_label', '_npc_life_blocks', 'place_hint',
            'place_container', 'home_of', 'FINALE'):
    ok('check113j.py 含 `%s`' % tok, tok in ck)

print()
print('=== 3 数据侧：真实数据里真有这些值 ===')
idx = json.loads(rd(os.path.join(PET, 'assets', 'scenes', '_index.json')))
n_scene = sum(len((ar or {}).get('scenes') or {})
              for ch in (idx.get('chapters') or {}).values()
              for ar in ((ch or {}).get('areas') or {}).values())
ok('场景总数 == 2166（文档 §3 的「2166 个场景」）', n_scene == 2166, '实测 %d' % n_scene)

# `rm_dalvExit` 必须真的在索引里（否则 §3 第 5 条是编的）
has_dalv = False
for ch in (idx.get('chapters') or {}).values():
    for ar in ((ch or {}).get('areas') or {}).values():
        if 'uty.rooms.rm_dalvExit' in ((ar or {}).get('scenes') or {}):
            has_dalv = True
ok('索引里真有 `uty.rooms.rm_dalvExit`（§3 第 5 条的实证）', has_dalv)

# 「未分区（废弃/调试/演示）」必须真的带括注（否则 §3 第 2 条是编的）
filler_bare = 0
filler_suffix = 0
for ch in (idx.get('chapters') or {}).values():
    for ar in ((ch or {}).get('areas') or {}).values():
        nm = str((ar or {}).get('name') or '')
        if nm == '未分区':
            filler_bare += 1
        if nm.startswith('未分区（'):
            filler_suffix += 1
ok('区名里真有带括注的 `未分区（…）`（§3 第 2 条的实证）', filler_suffix > 0,
   '裸=%d 带括注=%d' % (filler_bare, filler_suffix))

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_placement as P                                    # noqa: E402
book = P.load_placement(PET)
ids = list(book.ids())
ok('`_placement.json` 里 NPC 数 == 84（文档 §4 的「84 条」）', len(ids) == 84,
   '实测 %d' % len(ids))

print()
print('=== 4 行数：文档 §2 的两张表必须与磁盘一致 ===')
n_li = len(li.splitlines())
n_mn = len(mn.splitlines())
ok('`npc_life.py` 行数 == 873（文档写 789 → 873）', n_li == 873, '实测 %d' % n_li)
ok('`main.py` 行数 == 16654（文档写 16532 → 16654）', n_mn == 16654, '实测 %d' % n_mn)

print()
print('=== 5 回归数字：文档 §5 引用的必须真实 ===')
base_path = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
bl = json.loads(rd(base_path))
suites = (bl.get('suites') or {})
ok('基线里已有 `check113j` 条目', 'check113j' in suites)
if 'check113j' in suites:
    ok('`check113j` 基线 PASS == 30（文档 §4 的「30 条」）',
       suites['check113j'].get('pass') == 30, '%r' % suites['check113j'].get('pass'))
tot = sum(int(v.get('pass') or 0) for v in suites.values())
ok('基线 PASS 合计 == 5517（文档 §5 全量读数）', tot == 5517, '实测 %d' % tot)
ok('基线套件数 == 107', len(suites) == 107, '实测 %d' % len(suites))

print()
print('=== 6 EOL 纪律：两文件必须全 CRLF（末行有无换行都放行）===')
for tag, t in (('npc_life.py', li), ('main.py', mn)):
    gap = len(t.splitlines()) - t.count('\r\n')
    ok('%s 全 CRLF（gap ∈ {0,1}）' % tag, gap in (0, 1), 'gap=%d' % gap)

print()
print('=== 7 无 BOM / 无 U+FFFD ===')
for tag, t in (('npc_life.py', li), ('main.py', mn), ('check113j.py', ck),
               ('Validation_113j.md', doc)):
    ok('%s 无 BOM、无替换字符' % tag,
       (not t.startswith('\ufeff')) and ('\ufffd' not in t))

print()
print('=== 8 文档自身：关键结论不能只说"改了" ===')
for tok in ('不是让模型做路径搜索', '修一条丢一条', '在家不许说想回去',
            'trait_hint', 'home_of', 'place_container'):
    ok('文档含关键令牌 `%s`' % tok, tok in doc)

print()
print('=' * 70)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
print('=' * 70)
sys.exit(0 if _n_fail == 0 else 1)
