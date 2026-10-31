# -*- coding: utf-8 -*-
u"""第127轮回归锁：NPC「他想去找谁」的**名字消歧**不许再漏。

## 这一轮修的是什么（用户口径：「训练这类的也要抓一下」）

训练线（第113轮）的接线我逐环实测过，没有断的：96 个角色覆盖齐（77 人设有
AI、18 个 `tier=plain` 走内置台词、`knight` 武装成"沉默"）、`patches` 59 条
进 system prompt（`main.py` → `training_patch`）、`_seek.json` 72 人进决策
（`npc_seek.load` → `weights_of` → `_pick_friend`）。

真缺口在**数据被白白丢掉的那一段**：`_seek.json` 的 `unresolved_names` 里有
4 条 `Asgore（ambiguous）` —— 而它们**解得开**。

根因（`gen_seek113p.pick_id`）：第 148 行的「登记名以该名字开头」第三档，被
写在 `if not cand:` 里 ⇒ 只有"精确档**零命中**"才会启用。而 UT 那个 Asgore 的
登记名是 **`Asgore Dreemurr`**：

    'Asgore' 精确档 → ['asgore'(Deltarune), 'ot_asgore'(outertale)]   # 两条
    源 ut_toriel 的作品前缀 = 'ut_' → 同作品候选 = 空 → ambiguous（丢弃）
    别名档里明明有 ut_asgore，却因为"精确档不为空"永远读不到。

⇒ 修法：同作品候选为空时，**再兜一次别名档、且只收同作品那一条**。
跨作品同名（`Sans` 在 ut_/ot_ 各一条、源无前缀）仍然丢弃 —— 猜错等于把 A 的
偏好挂到 B 头上（第113轮p 的原始教训）。

结果：`_seek.json` 条目 189 → **193**（+4：ut_toriel / ut_undyne / ut_frisk /
ut_flowey → ut_asgore），既有 189 条**逐字段一字未改**，`formula` 未动。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 现场        —— 8 个 `ut_*` 源提 `Asgore` 必须解析成 `ut_asgore`（真跑生成器函数）
B 拒猜纪律    —— 跨作品同名 / 名册外的人**仍然** discarded（成对：A 绿的同时 B 必须绿）
C 数据面      —— `_seek.json` 里那 4 条真的在、`why` 原句真的提到 Asgore、自指为零
D 破坏性负控制 —— 把别名兜底**拆掉**再算 ⇒ 4 条必须消失（证明 A 的绿是修复带来的，
                 不是判据恒真）；另加"换一部作品（`ot_toriel`）也成立"，排除硬编码 ut
E 自检        —— AST 查恒真判据（有分母）/ 无 BOM / 生成器里别名档**只有一份实现**

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；断行为不断赋值；
负控制必须真的落进被测分支（D 段直接改内存里的候选再比对，不是另写一份判据）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
SEEK_P = os.path.join(PET, 'assets', 'npc', '_seek.json')
REG_P = os.path.join(PET, 'assets', 'npc', '_registry.json')
GEN_P = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                     '_tools', 'gen_seek113p.py')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)
    print(u'=' * 78)


def load(p):
    with io.open(p, 'rb') as fh:
        return json.loads(fh.read().decode('utf-8'))


# ---- 把生成器当被测物加载（它 import 时只读 products 内的 modules）----
sys.path.insert(0, os.path.dirname(GEN_P))
import gen_seek113p as G                     # noqa: E402

BY_NAME, BY_LOWER, BY_CN, CN_OF, IDS = G.registry_maps()


def pick(nm, src):
    return G.pick_id(nm, src, BY_NAME, BY_LOWER, BY_CN, IDS)


def pick_old(nm, src, by_name, by_lower, by_cn, ids):
    u"""**修复前**的逻辑（复制一份，只为做 D 段负控制）。

    ★ 与产品唯一的差别：同作品候选为空时**不兜别名档**。
      其余（精确档 / 前缀档 / 剥括号 / 同前缀筛）逐行相同。
    """
    cand = G._dedup((by_name.get(nm) or []) + (by_lower.get(str(nm).lower()) or [])
                    + (by_cn.get(str(nm)) or []))
    cand = [c for c in cand if c in ids]
    if not cand:
        if len(str(nm)) >= 5:
            low = str(nm).lower()
            for nm2, lst in by_name.items():
                if str(nm2).lower() == low:
                    continue
                if str(nm2).lower().startswith(low):
                    cand.extend(lst)
            cand = G._dedup([c for c in cand if c in ids])
    if not cand:
        core = G._strip_note(nm)
        if core != str(nm):
            got, why = pick_old(core, src, by_name, by_lower, by_cn, ids)
            if got:
                return got, why
    if not cand:
        return None, 'unknown'
    if len(cand) == 1:
        return cand[0], 'ok'
    p, _ = G.split_prefix(src)
    same = [c for c in cand if G.split_prefix(c)[0] == p]
    if len(same) == 1:
        return same[0], 'ok'
    return None, 'ambiguous'          # ← 修复前：这里直接放弃


# ============================================================ A 现场
head(u'A. 现场：8 个 ut_* 源提 `Asgore` 必须落到 `ut_asgore`')

UT_SRCS = ['ut_alphys', 'ut_chara', 'ut_flowey', 'ut_frisk', 'ut_gaster',
           'ut_mettaton', 'ut_toriel', 'ut_undyne']
_bad = []
for _s in UT_SRCS:
    _got, _why = pick(u'Asgore', _s)
    if _got != 'ut_asgore':
        _bad.append((_s, _got, _why))
check(u'A1 8 个 ut_* 源全部解析为 `ut_asgore`（真跑 `pick_id`）',
      len(_bad) == 0, u'不合格=%s' % (_bad,))

check(u'A2 分母非空：这 8 个源都在名册里',
      all(s in IDS for s in UT_SRCS), u'缺=%s' % [s for s in UT_SRCS if s not in IDS])

_reg = {r['id']: r for r in load(REG_P)['npcs']}
check(u'A3 根因可复述：`ut_asgore` 的登记名是 `Asgore Dreemurr`（与提及用的 `Asgore` 不同）',
      _reg.get('ut_asgore', {}).get('name') == u'Asgore Dreemurr',
      u'name=%r' % _reg.get('ut_asgore', {}).get('name'))

check(u'A4 精确档确实只拿到两条（Deltarune + outertale）—— 这是歧义的来源',
      sorted(BY_NAME.get(u'Asgore') or []) == ['asgore', 'ot_asgore'],
      u'%s' % (BY_NAME.get(u'Asgore'),))

# ============================================================ B 拒猜纪律
head(u'B. 拒猜纪律：跨作品同名 / 名册外的人，一条都不许"猜出来"')

_b1 = pick(u'Asgore', u'toriel')
_b2 = pick(u'Asgore', u'asgore')
# ★ 第127轮修判据（首跑就是这条报红，报的是**我的断言**不是产品）：
#   无前缀源（Deltarune）提 `Asgore` 时，候选里**无前缀**那条恰好一个 ⇒ 本来就该
#   解析成 `asgore`（修复前也一样）。真正该守的是「**不许**跨到 ot_/ut_ 那两条」,
#   因为别名兜底一旦写成"不看前缀"，这里就会跳到 `ot_asgore`/`ut_asgore`。
check(u'B1 Deltarune 源提 `Asgore` 仍落 `asgore`（**不许**被别名兜底带到 ot_/ut_）',
      _b1 == (u'asgore', 'ok') and _b2 == (u'asgore', 'ok'),
      u'toriel=%s asgore=%s' % (_b1, _b2))

check(u'B2 `Sans` 在 ut_/ot_ 各一条、源 `toriel` 无前缀 ⇒ 仍 ambiguous',
      pick(u'Sans', u'toriel') == (None, 'ambiguous'), u'%s' % (pick(u'Sans', u'toriel'),))

check(u'B3 `Undyne` 跨作品（源 `asgore`）⇒ 仍 ambiguous',
      pick(u'Undyne', u'asgore') == (None, 'ambiguous'), u'%s' % (pick(u'Undyne', u'asgore'),))

check(u'B4 名册外的人 `Grillby` ⇒ unknown（不是 ambiguous）',
      pick(u'Grillby', u'ut_sans') == (None, 'unknown'), u'%s' % (pick(u'Grillby', u'ut_sans'),))

check(u'B5 名册外的人 `Kanako` ⇒ unknown',
      pick(u'Kanako', u'hy_dalv') == (None, 'unknown'), u'%s' % (pick(u'Kanako', u'hy_dalv'),))

check(u'B6 非人条目 `人类` / `厨房` 仍丢弃（不硬塞给任何角色）',
      pick(u'人类', u'ut_chara') == (None, 'unknown')
      and pick(u'厨房', u'hy_sousborg') == (None, 'unknown'),
      u'%s / %s' % (pick(u'人类', u'ut_chara'), pick(u'厨房', u'hy_sousborg')))

# ============================================================ C 数据面
head(u'C. 数据面：`_seek.json` 里那 4 条真的在，且证据自洽')

doc = load(SEEK_P)
SEEK = doc.get('seek') or {}
UNRES = doc.get('unresolved_names') or {}

NEW4 = ['ut_toriel', 'ut_undyne', 'ut_frisk', 'ut_flowey']
_miss = [w for w in NEW4 if 'ut_asgore' not in (SEEK.get(w) or {})]
check(u'C1 4 个源都真的有 `ut_asgore` 条目', not _miss, u'缺=%s' % (_miss,))

_noev = []
for _w in NEW4:
    _it = (SEEK.get(_w) or {}).get('ut_asgore') or {}
    _why = str(_it.get('why') or '')
    if u'Asgore' not in _why or not isinstance(_it.get('w'), (int, float)):
        _noev.append((_w, _why[:40]))
check(u'C2 每条 `why` 原句里都真的出现 `Asgore`（可复核，不是我编的）',
      not _noev, u'不合格=%s' % (_noev,))

_left = [(k, nm) for k, v in UNRES.items() for nm in (v or [])
         if nm == u'Asgore（ambiguous）']
check(u'C3 `unresolved_names` 里**不再**有 `Asgore（ambiguous）`', not _left, u'残留=%s' % (_left,))

_keep = [(k, nm) for k, v in UNRES.items() for nm in (v or []) if 'ambiguous' in str(nm)]
check(u'C4 仍被拒的歧义条目还在（`Sans` / `Undyne`，证明拒猜那道门没被一起拆掉）',
      len(_keep) >= 3, u'剩 %d 条：%s' % (len(_keep), _keep[:4]))

_nitem = sum(len(v) for v in SEEK.values())
check(u'C5 条目总数只增不减（下界 193，不钉死绝对数）', _nitem >= 193, u'now=%d' % _nitem)

_self = [(a, b) for a, v in SEEK.items() for b in v if a == b]
check(u'C6 无自指（没人"想去找自己"）', not _self, u'%s' % (_self[:3],))

# ============================================================ D 破坏性负控制
head(u'D. 破坏性负控制：把别名兜底拆掉 ⇒ 这 4 条必须消失')

_old_bad = []
for _s in NEW4:
    _got, _why = pick_old(u'Asgore', _s, BY_NAME, BY_LOWER, BY_CN, IDS)
    if _got is not None:
        _old_bad.append((_s, _got))
check(u'D1 修复前的逻辑对同 4 个源**全部**解不出（证明 A 的绿来自这次修复）',
      len(_old_bad) == 0, u'旧逻辑竟然解出了=%s' % (_old_bad,))

check(u'D2 差异是"唯一的那一处"：新旧只在 ut_* 上分叉，Deltarune 源两者一致',
      pick(u'Asgore', u'toriel') == pick_old(u'Asgore', u'toriel', BY_NAME, BY_LOWER, BY_CN, IDS),
      u'new=%s old=%s' % (pick(u'Asgore', u'toriel'),
                          pick_old(u'Asgore', u'toriel', BY_NAME, BY_LOWER, BY_CN, IDS)))

_ot = pick(u'Asgore', u'ot_toriel')
check(u'D3 换一部作品也成立（`ot_toriel` 提 `Asgore` ⇒ `ot_asgore`）—— 排除"只硬编码 ut"',
      _ot[0] == 'ot_asgore', u'%s' % (_ot,))

_src = io.open(GEN_P, 'rb').read().decode('utf-8')
check(u'D4 生成器里别名档**只有一份实现**（`def _alias_startswith` 恰好 1 处，`pick_id` 真的调它）',
      _src.count(u'def _alias_startswith') == 1
      and _src.count(u'_alias_startswith(nm, by_name, ids)') >= 2,
      u'def=%d call=%d' % (_src.count(u'def _alias_startswith'),
                           _src.count(u'_alias_startswith(nm, by_name, ids)')))

# ============================================================ E 自检
head(u'E. 自检：判据本身不自欺')

_ast = ast.parse(_src)
_trues = []
_nfun = 0
for _node in ast.walk(_ast):
    if isinstance(_node, ast.FunctionDef):
        _nfun += 1
    if isinstance(_node, ast.Assert) and isinstance(_node.test, ast.Constant):
        _trues.append(getattr(_node.test, 'value', None))
check(u'E1 生成器里没有 `assert True` 这类恒真写法（有分母：函数 ≥5 个）',
      not _trues and _nfun >= 5, u'恒定断言=%s 函数数=%d' % (_trues, _nfun))

_self_src = io.open(os.path.abspath(__file__), 'rb').read()
check(u'E2 本脚本无 BOM / 无 U+FFFD',
      not _self_src.startswith(b'\xef\xbb\xbf')
      and _self_src.decode('utf-8').count(u'\ufffd') == 0)

_sb = io.open(SEEK_P, 'rb').read()
check(u'E3 `_seek.json` 无 BOM / 无 U+FFFD',
      not _sb.startswith(b'\xef\xbb\xbf')
      and _sb.decode('utf-8').count(u'\ufffd') == 0, u'bytes=%d' % len(_sb))

check(u'E4 全部被测文件在盘',
      all(os.path.isfile(p) for p in (SEEK_P, REG_P, GEN_P)))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    for _d in _failed:
        print(u'   [失败] %s' % _d)
    sys.exit(1)
