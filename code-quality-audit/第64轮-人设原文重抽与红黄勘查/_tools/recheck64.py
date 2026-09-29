# -*- coding: utf-8 -*-
"""第64轮 · 专属复检（`recheck64`）—— 只读，不改被测状态。

为什么必须有这个脚本（用户口径）
--------------------------------
「以后再调整重要核心文件时一定要记得复检」（2026-09-23）。
本轮动到的**核心文件**有四组：

  ① `ralsei_pet/assets/npc/persona/*.txt`   —— 13 份 → **50 份**（人设真源）
  ② `ralsei_pet/assets/npc/_personas.json`  —— 索引重建（schema 1 → 2）
  ③ `ralsei_pet/assets/npc/_registry.json`  —— spamton / mike 接线
  ④ `assets/sprites/ghost/*` + 两个回归套件（`check55.py` / `check57.py`）

六类判据（skill `core-file-recheck` 的形状）
-------------------------------------------
  A 人设线自洽：索引 ↔ 磁盘 ↔ 装载（含 chars/bytes/sha256 逐条**磁盘实测**比对）
  B 注册表接线：spamton/mike 翻成"已装" + `needs_setting ⇔ persona is None` 不变式
  C 幽灵素材：PNG 字节/sha256 与 `_source.json` 逐条一致 + 魔数 + 精灵名闭集
  D 回归锁改动：三个文件可 `ast.parse` + **不再残留 `== 13` 形态的份数判据**
  E 恒真判据复查：每条新判据都配**负控制**（喂坏输入必须报红）
  F 工作区：13 份旧人设**未被改动**（git 层面）+ 待提交清单如实登记

纪律
----
* ❗ 一律 `ast.parse`（**不产 `.pyc`**，复检不许改变被测状态）；
* ❗ 全部**只读**：不开文件写句柄、不建目录、不动基线；
* ❗ 判据不许恒真：E 段每条都是"喂坏输入 ⇒ False"的正/负控制。
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))          # .../第64轮-人设原文重抽与红黄勘查
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
NPC = os.path.join(PET, 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
GHOST = os.path.join(PET, 'assets', 'sprites', 'ghost')
# ⚠️ 本脚本第一版把 `_evidence` 拼到了 `HERE`（= `_tools/`）下面 ⇒ 恒不存在 ⇒
#    C5 静默拿到 0 张 PNG 而报红。真位置在**上一级**（与 `_tools/` 平级）。
EVID = os.path.join(ROUND, '_evidence')
SPR_EVID = os.path.join(EVID, 'spr64')
REG = os.path.join(NPC, '_registry.json')
IDX = os.path.join(NPC, '_personas.json')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK55 = os.path.join(ROOT, 'code-quality-audit', '第55轮-灵魂实体与NPC人设', 'check55.py')
CHECK57 = os.path.join(ROOT, 'code-quality-audit', '第57轮-模型并发实测', 'check57.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')

FAILS = []
N = [0]


def ck(name, cond, extra=''):
    N[0] += 1
    if cond:
        print(u'[PASS] %s %s' % (name, extra))
    else:
        print(u'[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def rb(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def rj(p):
    try:
        return json.loads(rb(p).decode('utf-8'))
    except Exception:
        return None


def sha(b):
    return hashlib.sha256(b).hexdigest()


REV_13 = ['susie', 'kris', 'asgore', 'toriel', 'lancer', 'king', 'queen',
          'berdly', 'noelle', 'tenna', 'rouxls', 'gerson', 'flowery']
SHORT_OPEN = u'请始终以'
TAIL_MARK = u'【本项目补充'

print(u'=' * 72)
print(u'【A】人设线自洽 —— 索引 ↔ 磁盘 ↔ 装载')
print(u'=' * 72)

idx = rj(IDX)
recs = (idx or {}).get('personas') or []
ck('A1 _personas.json 可解析，schema_version==2 且 count == len(personas)',
   isinstance(idx, dict) and idx.get('schema_version') == 2
   and idx.get('count') == len(recs) and bool(recs),
   u'schema=%r count=%r 实际 %d' % ((idx or {}).get('schema_version'),
                                   (idx or {}).get('count'), len(recs)))

_disk_txt = sorted(f for f in os.listdir(PDIR) if f.endswith('.txt')) \
    if os.path.isdir(PDIR) else []
ck('A2 索引登记的 id 集合 == 磁盘上的 .txt 集合（去扩展名）',
   sorted(r['id'] for r in recs) == [f[:-4] for f in _disk_txt],
   u'索引 %d / 磁盘 %d' % (len(recs), len(_disk_txt)))

# ★ A3 —— 本段最硬的一条：`chars/bytes/sha256/sha256_lf` 全部**回磁盘实测**
_bad_meta, _bad_missing = [], []
_ALL_TAIL = set()
for r in recs:
    fp = os.path.join(PDIR, os.path.basename(r.get('file') or ''))
    if not os.path.isfile(fp):
        _bad_missing.append(r['id'])
        continue
    raw = rb(fp)
    txt = raw.decode('utf-8')
    _ALL_TAIL.add(r.get('tail_sha256'))
    if (r.get('bytes') != len(raw)
            or r.get('chars') != len(txt)
            or r.get('sha256') != sha(raw)
            or r.get('sha256_lf') != sha(raw.replace(b'\r\n', b'\n'))):
        _bad_meta.append((r['id'], r.get('bytes'), len(raw)))
ck('A3 每条 chars/bytes/sha256/sha256_lf 与磁盘实测一致（逐条 %d 份）' % len(recs),
   not _bad_meta and not _bad_missing,
   u'元数据不符=%r 缺文件=%r' % (_bad_meta[:3], _bad_missing[:3]))

ck('A4 每份 file 的 basename == id + ".txt"（防串档）',
   all(os.path.basename(r.get('file') or '') == '%s.txt' % r['id'] for r in recs),
   str([r['id'] for r in recs
        if os.path.basename(r.get('file') or '') != '%s.txt' % r['id']][:5]))

# A5 结构体检：无 BOM / 无 U+FFFD / 短块恰 1 / 有尾部补充 / 用了 CRLF 正文
_struct = []
for r in recs:
    fp = os.path.join(PDIR, os.path.basename(r.get('file') or ''))
    raw = rb(fp)
    txt = raw.decode('utf-8')
    why = []
    if raw[:3] == b'\xef\xbb\xbf':
        why.append('BOM')
    if u'\ufffd' in txt:
        why.append('U+FFFD')
    if txt.count(SHORT_OPEN) != 1:
        why.append('短块=%d' % txt.count(SHORT_OPEN))
    if TAIL_MARK not in txt:
        why.append('无尾部补充')
    if u'**' in txt or u'##' in txt:
        why.append('markdown')
    if why:
        _struct.append((r['id'], why))
ck('A5 结构体检：无 BOM / 无 U+FFFD / 短块恰 1 / 有尾部补充 / 无 markdown',
   not _struct, str(_struct[:4]))

ck('A6 尾部"本项目补充"块全库一致（每份 tail_sha256 都等于索引顶层那份）',
   len(_ALL_TAIL) == 1 and idx.get('tail_sha256') in _ALL_TAIL,
   '不同 tail_sha256 数=%d 顶层=%r' % (len(_ALL_TAIL), idx.get('tail_sha256')))

# ⚠️ 本判据第一版写成 `by_work == {work: 计数}` ⇒ 必红。实测（先看再信）：
#    `by_work` 存的是 **work → id 列表**（不是计数）⇒ 改用列表比对。
_work = {}
for r in recs:
    _work.setdefault(r.get('work'), []).append(r['id'])
_work = {k: sorted(v) for k, v in _work.items()}
ck('A7 by_work 的分组（work → id 列表）与 personas 实测分组一致',
   {k: sorted(v) for k, v in (idx.get('by_work') or {}).items()} == _work,
   'by_work 键=%r 实测=%r' % (sorted(idx.get('by_work') or {}), sorted(_work)))

ck('A8 第55轮那 13 个 id 全在（重抽是"只增不改"）',
   set(REV_13) <= {r['id'] for r in recs},
   str(sorted(set(REV_13) - {r['id'] for r in recs})))

ck('A9 每份 sections 非空（九段标题被解析出来）',
   all(isinstance(r.get('sections'), list) and r['sections'] for r in recs),
   str([r['id'] for r in recs
        if not (isinstance(r.get('sections'), list) and r['sections'])][:5]))

print()
print(u'=' * 72)
print(u'【B】注册表接线 —— spamton / mike 翻成"已装"')
print(u'=' * 72)
reg = rj(REG)
npcs = (reg or {}).get('npcs') or []
ck('B1 _registry.json 可解析且仍是 35 条',
   isinstance(reg, dict) and len(npcs) == 35, 'n=%d' % len(npcs))
_by = {n['id']: n for n in npcs}
ck('B2 spamton / mike 已接线（persona 指向本人那份 + needs_setting=False）',
   _by.get('spamton', {}).get('persona') == 'persona/spamton.txt'
   and _by.get('spamton', {}).get('needs_setting') is False
   and _by.get('mike', {}).get('persona') == 'persona/mike.txt'
   and _by.get('mike', {}).get('needs_setting') is False,
   'spamton=%r mike=%r' % (_by.get('spamton', {}).get('persona'),
                           _by.get('mike', {}).get('persona')))
ck('B3 不变式：needs_setting == (persona is None)（35 条全成立）',
   all(bool(n.get('needs_setting')) == (n.get('persona') is None) for n in npcs),
   str([n['id'] for n in npcs
        if bool(n.get('needs_setting')) != (n.get('persona') is None)]))
_main_unset = sorted(n['id'] for n in npcs
                     if n.get('needs_setting') and n.get('persona') is None
                     and n.get('tier', 'main') == 'main')
ck('B4 主线里"还在等设定"的只剩 knight',
   _main_unset == ['knight'], str(_main_unset))
_p_refs = [n['persona'] for n in npcs if n.get('persona')]
_miss = [p for p in _p_refs
         if p != '../ralsei_persona.md'
         and not os.path.isfile(os.path.join(NPC, p))]
ck('B5 注册表里每条 persona 都在磁盘上（%d 条）' % len(_p_refs), not _miss, str(_miss))

print()
print(u'=' * 72)
print(u'【C】幽灵素材 —— 与 _source.json 逐条对账')
print(u'=' * 72)
src = rj(os.path.join(GHOST, '_source.json'))
srf = (src or {}).get('files') or {}
_gpng = sorted(f for f in os.listdir(GHOST) if f.endswith('.png')) \
    if os.path.isdir(GHOST) else []
ck('C1 ghost 目录 PNG 数 == _source.json 登记的 files 数',
   bool(srf) and sorted(srf) == _gpng,
   u'磁盘 %d / 登记 %d' % (len(_gpng), len(srf)))
_bad_g, _bad_magic = [], []
for name, meta in srf.items():
    fp = os.path.join(GHOST, name)
    if not os.path.isfile(fp):
        _bad_g.append((name, 'MISSING'))
        continue
    b = rb(fp)
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        _bad_magic.append(name)
    if meta.get('bytes') != len(b) or meta.get('sha256') != sha(b):
        _bad_g.append((name, meta.get('bytes'), len(b)))
ck('C2 每张 PNG 的 bytes / sha256 与磁盘实测一致（%d 张）' % len(srf),
   not _bad_g, str(_bad_g[:3]))
ck('C3 每张都是真 PNG（魔数 \\x89PNG\\r\\n\\x1a\\n）', not _bad_magic, str(_bad_magic[:3]))
_sprs = sorted({m.get('sprite') for m in srf.values()})
# ⚠️ 本判据第一版凭记忆写"13 个闭集" ⇒ 必红。实测 + 读 `stage_ghost64.py` 的真口径：
#    名单里**确有 13 个** sprite，但产品**只落幽灵族**（`GHOST_PREFIX` 三前缀），
#    `spr_truechara` / `spr_truechara_weird` / `spr_truechara_laugh` 这 3 个
#    **按设计只进证据、不进产品**（stage 判据 G2 原文：「只落"幽灵族"
#    （truechara 只进证据，不进产品）」）。⇒ 产品闭集 = **10 个幽灵族**。
_GHOST_PREFIX = ('spr_ghost_chara_', 'spr_ghost_clover_', 'spr_clover_ghostu')
ck('C4 产品精灵名 = 10 个幽灵族闭集，且**不含** truechara*（按设计只进证据）',
   len(_sprs) == 10
   and all(s.startswith(_GHOST_PREFIX) for s in _sprs)
   and not any(s.startswith('spr_truechara') for s in _sprs),
   '%d 个: %r' % (len(_sprs), _sprs))
_epng = sorted(f for f in os.listdir(SPR_EVID) if f.endswith('.png')) \
    if os.path.isdir(SPR_EVID) else []
# 不写死张数（那会随帧数变化失效）；守的结构是：**证据 ⊇ 产品**，且证据里**有**
# 产品不落的 truechara 帧（这正是"证据更全"的凭据）。
ck('C5 证据区 PNG 比产品更全（含 truechara 帧，那是产品按设计不落的）',
   bool(_gpng) and len(_epng) > len(_gpng)
   and any(f.startswith('spr_truechara') for f in _epng),
   '证据 %d / 产品 %d' % (len(_epng), len(_gpng)))

print()
print(u'=' * 72)
print(u'【D】回归锁改动 —— 可编译 + 不再残留"写死份数"判据')
print(u'=' * 72)
for tag, p in (('check55', CHECK55), ('check57', CHECK57), ('run_all', RUNALL)):
    ok = True
    why = ''
    try:
        ast.parse(rb(p).decode('utf-8'))
    except Exception as e:
        ok, why = False, repr(e)
    ck('D1 %s.py 可 ast.parse（不产 .pyc）' % tag, ok, why)


def _eq_consts(tree, val):
    """树里有没有 `<expr> == <常量 val>` 形态（用于抓"写死份数"）。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 \
                and isinstance(node.ops[0], ast.Eq):
            for side in (node.left,) + tuple(node.comparators):
                if isinstance(side, ast.Constant) and side.value == val:
                    hits.append(getattr(node, 'lineno', -1))
    return hits


_h55 = _eq_consts(ast.parse(rb(CHECK55).decode('utf-8')), 13)
ck('D2 check55.py 不再有 `== 13` 形态的份数判据（判据已改为不变式）',
   not _h55, '命中行号=%r' % _h55)
# ⚠️ D3 第一版用"check57 里不许出现 `== 13`"⇒ 误报：`check57.py` 的 **C7b** 里
#    确有 `len(_r2_13) == 13`，但那是**第57轮实测产物里的档位**（"13 人档"是当时
#    真跑出来的实验条件），是**历史事实**，不是"人设份数写死"。⇒ 判据收窄到
#    **人设份数**这一具体形态（`len(_files) == 13` / `len(_persons) == 13`）。
_src57 = rb(CHECK57).decode('utf-8')
_hardcount57 = re.findall(r'len\((?:[A-Za-z_][A-Za-z0-9_]*)\)\s*==\s*13\b', _src57)
_HARDCOUNT_OK = (u'len(_files) == 13', u'len(_persons) == 13')
_h57 = [m for m in _hardcount57 if m in _HARDCOUNT_OK]
ck('D3 check57.py 不再把**人设份数**写死成 13（C7b 的实测档位不算）',
   not _h57 and u'>= 13' in _src57, '命中=%r' % _h57)
_src55 = rb(CHECK55).decode('utf-8')
ck('D4 check55.py 真含新不变式（索引↔磁盘一一对应 / 实时未装 id）',
   u'一一对应' in _src55 and u'__no_such_npc__' in _src55
   and u'_unset_ids' in _src55)
_src57 = rb(CHECK57).decode('utf-8')
ck('D5 check57.py 真含放宽后的量级区间与份数下限',
   u'2000~12000' in _src57 and u'>= 13' in _src57)
_bl = rj(BASELINE)
ck('D6 baseline.json 可解析', isinstance(_bl, dict) and bool(_bl),
   'keys=%d' % (len(_bl or {})))

print()
print(u'=' * 72)
print(u'【E】恒真判据复查 —— 每条新判据的负控制（喂坏输入必须报红）')
print(u'=' * 72)
# E1 索引↔磁盘集合判据：故意不等 ⇒ 必须 False
_good = sorted(r['id'] for r in recs) == [f[:-4] for f in _disk_txt]
_fake_idx = sorted(r['id'] for r in recs)[:-1]          # 少一个
_bad_input = _fake_idx == [f[:-4] for f in _disk_txt]
ck('E1 负控制：索引↔磁盘判据喂"少一条"的输入 ⇒ False（不是恒真）',
   _good is True and _bad_input is False,
   '真输入=%s 坏输入=%s' % (_good, _bad_input))
# E2 sha256 判据：改一字节 ⇒ 必须不等
_r0 = recs[0]
_fp0 = os.path.join(PDIR, os.path.basename(_r0['file']))
_b0 = rb(_fp0)
_tampered = _b0[:-1] + (b'X' if _b0[-1:] != b'X' else b'Y')
ck('E2 负控制：sha256 判据对"改一字节"的输入 ⇒ 不等（不是恒真）',
   sha(_b0) == _r0['sha256'] and sha(_tampered) != _r0['sha256'],
   '%s 原=%s 改=%s' % (_r0['id'], sha(_b0)[:12], sha(_tampered)[:12]))
# E3 needs_setting 不变式：构造一个反例 ⇒ 必须报红
_inv_ok = all(bool(n.get('needs_setting')) == (n.get('persona') is None) for n in npcs)
_fake = dict(_by['susie'])
_fake['needs_setting'] = True                            # 装了设定却说"还在等"
_inv_bad = bool(_fake.get('needs_setting')) == (_fake.get('persona') is None)
ck('E3 负控制：needs_setting 不变式对"装了却说还没装"的反例 ⇒ False',
   _inv_ok is True and _inv_bad is False, '反例判定=%s' % _inv_bad)
# E4 "没装的 id ⇒ persona_text 返回 None"不能是"恒 None"
sys.path.insert(0, os.path.join(PET, 'modules'))
try:
    import npc_persona as P
    _loaded = P.load_personas(assets_dir=os.path.join(PET, 'assets'), index=idx)
    ck('E4 负控制：persona_text 对**装了的** id 返回非 None（防"恒 None"假绿）',
       P.persona_text('susie', personas=_loaded) is not None
       and P.persona_text('__no_such_npc__', personas=_loaded) is None
       and len(_loaded) == len(recs),
       '装=%d 份；susie 非 None；不存在的 id ⇒ None' % len(_loaded))
except Exception as e:
    ck('E4 负控制：persona_text 对装了的 id 返回非 None', False, repr(e))

print()
print(u'=' * 72)
print(u'【F】工作区 —— 13 份旧人设未被改动 + 待提交清单')
print(u'=' * 72)


def _git(*a):
    try:
        r = subprocess.run(['git'] + list(a), cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        return r.returncode, r.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return -1, repr(e)


_rc, _mod = _git('diff', '--name-only', 'HEAD', '--',
                 'ralsei_pet/assets/npc/persona/')
ck('F1 13 份旧人设文件在 git 层面未被改动（`git diff HEAD` 对 persona/ 为空）',
   _rc == 0 and not _mod.strip(), 'rc=%r 改动=%r' % (_rc, _mod.strip()[:200]))
_rc2, _st = _git('status', '--porcelain')
_new_persona = [l for l in _st.splitlines() if 'assets/npc/persona/' in l]
ck('F2 新增人设确以"未跟踪/新增"形态出现（不是改动）',
   all(l.startswith('??') or l.startswith('A ') or l.startswith('A\t')
       for l in _new_persona) or not _new_persona,
   '前 3 条=%r' % (_new_persona[:3],))

print()
print(u'=' * 72)
print(u'== 复检结果 ==')
print(u'  断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
if FAILS:
    print(u'  失败项：')
    for f in FAILS:
        print(u'    - %s' % f)
else:
    print(u'  全部通过。')
print(u'=' * 72)
sys.exit(0 if not FAILS else 1)
