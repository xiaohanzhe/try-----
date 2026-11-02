# -*- coding: utf-8 -*-
"""第139轮回归锁：`patches["ralsei"]` **不再复述**人设已有的句数规格。

## 这一轮在做什么（一句话）

把第137轮登记的遗留 ①「一次最多两三句，短一点，像随口说出来的。」从数据里删掉，
并且**先证明它没用**才删 —— 不是"读起来重"就删。

## 为什么可以删（证据，不是口味）

第137轮的原话是「语义重复（冗余但无害），本轮不清」。本轮把它当被测物：

1. **它复述的是一条已有的规格**。同一条「一次说几句」在这个项目里写了**三遍**：
   - 人文本：`assets/ralsei_persona.md`「—— 我怎么说 ——」→「一次只说 1~3 句」；
   - 机器可读：`cards/ralsei.json` 的 `length_policy{max_chars:200, max_sentences:3}`；
   - 提示词：`patch` 里的 ①（`common113.PATCH_RULES['TOO_LONG']` 产出的模板句）。
   ★ 第三份是**派生品**：`patch` 的本义是"训练里真复现过的毛病对应的纠正"，
     复述规格既不是纠正，也说不清来源。
2. **它从来没被验证过**。第113轮给它做 A/B 的是 `AI_SELF` 那类，不是这一句；
   第137轮接进主宠 system 时也没测。真正被量过的只有"没有它"的情况：
   `第113轮/_evidence/raw30/ralsei.jsonl`（48 轮真机，patch 里**没有** ①）
   ⇒ 按句末标点+换行切句，**>3 句 40/48**，平均 117 字。
   即：光靠人设那一句，7B 有八成不照做。
3. **本轮补了正经 A/B**（`_tools/probe139_ab.py`，`_evidence/ab139.jsonl`）：
   同模型 `ralsei:v4`、同尾块（534 字）、同 7 题、题序交错、先热身 2 条丢弃；
   **唯一变量**就是那段（20 个字 + 一个分隔空格）（`no1` = 磁盘值去掉 ①，与 raw30 当时的 patch 内容相同；
   `with1` = 磁盘值）。56 条真机回复：

   | | >3 句 | 平均句数 | 平均字数 | OOC/BANNED/MD |
   |---|---|---|---|---|
   | no1（无①） | 14/28 | 3.93 | 74.0 | 0 / 0 / 0 |
   | with1（有①） | 13/28 | 3.71 | 60.4 | 0 / 0 / 0 |

   句数差 0.21（自助法 p=0.64）、字数差 13.5（p=0.24）—— **两样都测不出差别**。
   ⇒ 这 20 个字重复第二遍，没有换来任何可测的东西。留着它只有两个代价：
     与 persona 抢话权、让"哪句是纠正、哪句是设定"更说不清。

## 顺手修掉的四处（同一类病：判据回显时相量）

`check137` 原来有 4 处 extra 打的是**长度/偏移**（`len(_out)` / `patch@%d` /
`ralsei %d 字` / `C6` 的 `len %d → %d`）。数据一改就 DIFF，而判定一个字都没变 ——
正是第138轮定下的那条口径。本轮改数据必须碰这个文件，就一起清了。

## 本套件守什么

A 数据面：三份副本都去重了，且 ② ③（真缺口）一条没少
B 真源面：人文本与 `length_policy` **都还在**（删的是第三份派生品，不是规格本身）
C 行为面：拼出来的 system 里确实没有 ① 了，且尾块没跟着消失（含破坏性负控制）
D 改动最小：用**改动前的冻结快照**（`_evidence/patches_before139.json`）比对其余 58 条，
  不用 `git HEAD` —— 提交之后 HEAD 就等于工作区，那种判据是恒真的
E 同型普查：还有 38 位角色的 patch 复述着同一条规格（**本轮不修，登记**）
F 证据完整性：A/B 的 56 条与其汇总自洽（防"改汇总不改数据"）
G 自检

★ 零网络；Qt 用 offscreen（C 段要 `import main`，而 main 顶部 import 了 PyQt5）。
"""
import ast
import io
import json
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
PERSONA_PY = os.path.join(PET, 'assets', 'ralsei_persona.md')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
INDEX_JSON = os.path.join(TRAIN, '_index.json')
CARD_JSON = os.path.join(TRAIN, 'cards', 'ralsei.json')
CARDS_DIR = os.path.join(TRAIN, 'cards')
PERSONA_DIR = os.path.join(PET, 'assets', 'npc', 'persona')
SNAP = os.path.join(EV, 'patches_before139.json')
AB_JSONL = os.path.join(EV, 'ab139.jsonl')
AB_SUM = os.path.join(EV, 'ab139_summary.json')

sys.path.insert(0, os.path.join(PET, 'src'))
import main as M                                                # noqa: E402

#: ① 就是这一句（含句末分隔空格）—— 与 `_tools/probe139_ab.py` 的 `LEAD` 同一份
LEAD = u'一次最多两三句，短一点，像随口说出来的。 '
#: 只用来判"有没有复述规格"的两个短标记（比整句宽一点，防止改标点后漏抓）
MARKS = (u'两三句', u'随口说')

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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


def _has_lead(t):
    return any(m in (t or u'') for m in MARKS)


_idx = _json(INDEX_JSON)
_card = _json(CARD_JSON)
_persona = _read(PERSONA_PY)
_patches = _idx.get('patches') or {}
_idx_cards = _idx.get('cards') or {}
p_idx = _patches.get('ralsei') or u''
p_idxcard = ((_idx_cards.get('ralsei') or {}).get('patch')) or u''
p_file = _card.get('patch') or u''

# =============================================== A 数据面
head(u'A. 数据面：三份副本都去重了，② ③ 一条没少')

check(u'A0 分母非空：三份副本都取到了内容',
      bool(p_idx.strip()) and bool(p_idxcard.strip()) and bool(p_file.strip()),
      u'patches %d 条 / index.cards %d 条' % (len(_patches), len(_idx_cards)))
check(u'A1 `patches["ralsei"]` 不复述句数规格（无「两三句」也无「随口说」）',
      not _has_lead(p_idx))
check(u'A2 `_index.json` 的 `cards["ralsei"].patch` 与 `patches["ralsei"]` 逐字相同',
      p_idx == p_idxcard)
check(u'A3 `cards/ralsei.json` 的 patch 与 `patches["ralsei"]` 逐字相同（三处不漂）',
      p_file == p_idx)
check(u'A4 ② 名字白名单仍在（去重不许顺带删真缺口）', u'只认得原作里真有的名字' in p_idx)
check(u'A5 ③ 不要自己造人名 仍在', u'不要自己造人名' in p_idx)
check(u'A6 ③ 的实测例「凯斯恩」仍在', u'凯斯恩' in p_idx)
check(u'A7 拿不准时的退回说法仍在（「你」「他」「她」）', u'拿不准名字的时候' in p_idx)

# =============================================== B 真源面
head(u'B. 真源面：人文本与 `length_policy` 都还在（删的是第三份派生品）')

check(u'B0 persona 仍写着「一次只说 1~3 句」—— 规格的人文本没被一起删',
      u'一次只说 1~3 句' in _persona)
check(u'B1 persona 仍写着「像真人在聊天框里随手打字」', u'像真人在聊天框里随手打字' in _persona)
_lp = _card.get('length_policy') or {}
check(u'B2 `cards/ralsei.json` 的 `length_policy` 仍是 200 字 / 3 句（机器可读那份）',
      _lp.get('max_chars') == 200 and _lp.get('max_sentences') == 3,
      u'%s/%s' % (_lp.get('max_chars'), _lp.get('max_sentences')))
check(u'B3 ★ 三份规格的去向：人文本在、机器可读在、**提示词那份不在**',
      (u'一次只说 1~3 句' in _persona) and _lp.get('max_sentences') == 3
      and (not _has_lead(p_idx)))

# =============================================== C 行为面
head(u'C. 行为面：拼出来的 system 里确实没有 ①')

check(u'C0 `_with_ralsei_patch` 是模块级函数（不需要 Qt 宿主）',
      callable(getattr(M, '_with_ralsei_patch', None)))
_out = M._with_ralsei_patch(_persona)
check(u'C1 system 里不再出现「两三句」/「随口说」', not _has_lead(_out))
check(u'C2 system 仍以 persona 原文开头（正文一字未改）', _out.startswith(_persona.rstrip()))
check(u'C3 尾块还在（去重不是把整块删了）',
      M.PATCH_HEADER_RALSEI in _out and u'只认得原作里真有的名字' in _out)
check(u'C4 删掉的确实只有 ①：② ③ 都在 system 里',
      u'不要自己造人名' in _out and u'凯斯恩' in _out)

# ★ 破坏性负控制：让训练纠正返回空 ⇒ 尾块必须整个消失。
#   这条证明 C3 的"在"是靠 `training_patch`，不是 persona 里本来就有。
NP = M.npc_persona_mod
_orig = NP.training_patch
try:
    NP.training_patch = lambda *_a, **_k: u''
    _dry = M._with_ralsei_patch(_persona)
finally:
    NP.training_patch = _orig
check(u'C5 负控制：`training_patch` 返回空 ⇒ 尾块整个消失、只剩 persona',
      M.PATCH_HEADER_RALSEI not in _dry and _dry.strip() == _persona.strip())
check(u'C6 负控制恢复后 C1/C3 仍成立（没把产品改坏）',
      (lambda o: (not _has_lead(o)) and M.PATCH_HEADER_RALSEI in o)(M._with_ralsei_patch(_persona)))

# =============================================== D 改动最小
head(u'D. 改动最小：拿**改动前的冻结快照**比对，只有 ralsei 变了')

_snap = _json(SNAP)
_old = _snap.get('patches') or {}
check(u'D0 快照分母非空（否则"其余没变"是空集恒真）', len(_old) >= 50,
      u'快照 %d 条 / 现 %d 条' % (len(_old), len(_patches)))
check(u'D1 条数没变（去重不是增删角色）', len(_old) == len(_patches))
_changed = sorted(k for k in set(_old) | set(_patches)
                  if (_old.get(k) or '') != (_patches.get(k) or ''))
check(u'D2 变动键恰好是 {ralsei}', _changed == [u'ralsei'], u'%d 个' % len(_changed))
_rest = [k for k in _old if k != u'ralsei']
check(u'D3 其余 58 条 patch 逐字未动',
      all((_old[k] or '') == (_patches.get(k) or '') for k in _rest), u'%d 条' % len(_rest))
check(u'D4 快照里 ralsei 原本**含** ①（否则"删掉了"这句话不成立）',
      _has_lead(_snap.get('card_ralsei_patch') or u''))


def _lead_ids(mapping, getter):
    return sorted(k for k, v in mapping.items() if _has_lead(getter(v)))


_lead_p = _lead_ids(_patches, lambda v: v)
_lead_ic = _lead_ids(_idx_cards, lambda v: (v or {}).get('patch'))
_lead_cf = [os.path.basename(p)[:-5] for p in sorted(os.listdir(CARDS_DIR))
            if p.endswith('.json')
            and _has_lead((_json(os.path.join(CARDS_DIR, p)) or {}).get('patch'))]
check(u'D5 三份副本里"仍含 ①"的角色集合完全一致（没有改一半）',
      _lead_p == _lead_ic == sorted(_lead_cf),
      u'%d/%d/%d 人' % (len(_lead_p), len(_lead_ic), len(_lead_cf)))
check(u'D6 ralsei 不在这个集合里', u'ralsei' not in _lead_p)

# =============================================== E 同型普查
head(u'E. 同型普查：还有 38 位角色的 patch 复述着同一条规格（本轮不修，登记）')

_reg = set()
for _fn in sorted(os.listdir(PERSONA_DIR)):
    if _fn.endswith('.txt') and u'一次开口通常' in _read(os.path.join(PERSONA_DIR, _fn)):
        _reg.add(_fn[:-4])
_both = sorted(i for i in _reg if _has_lead((_idx_cards.get(i) or {}).get('patch') or u''))
check(u'E0 分母：人设里写着句数规格的角色数（含「一次开口通常」）',
      len(_reg) >= 50, u'%d 人' % len(_reg))
check(u'E1 其中 patch 仍复述 ① 的人数 = 38（登记未修；数字一变请回来看这一节）',
      len(_both) == 38, u'%d/%d' % (len(_both), len(_reg)))
check(u'E2 ralsei 不属于这 38 人（它的人设是 `ralsei_persona.md`，不在这个目录）',
      u'ralsei' not in _both)

# =============================================== F 证据完整性
head(u'F. A/B 证据：56 条与其汇总自洽')

_rows = [json.loads(l) for l in io.open(AB_JSONL, encoding='utf-8') if l.strip()] \
    if os.path.isfile(AB_JSONL) else []
check(u'F0 `ab139.jsonl` 在且条数 = 7 题 × 2 臂 × 4 采样', len(_rows) == 56,
      u'%d 条' % len(_rows))
_r_no1 = [r for r in _rows if r.get('arm') == 'no1']
_r_with1 = [r for r in _rows if r.get('arm') == 'with1']
check(u'F1 两臂条数相等（A/B 的分母闸：不等就没法比）',
      len(_r_no1) == len(_r_with1) == 28, u'%d/%d' % (len(_r_no1), len(_r_with1)))
_sum = _json(AB_SUM) if os.path.isfile(AB_SUM) else {}


def _recalc(rs):
    return (sum(1 for r in rs if r.get('sents', 0) > 3),
            round(sum(r.get('sents', 0) for r in rs) / float(max(1, len(rs))), 3))


_ok_f2 = True
for _k, _rs in ((u'no1', _r_no1), (u'with1', _r_with1)):
    _o = ((_sum.get('ab') or {}).get(_k) or {})
    _calc = _recalc(_rs)
    if _o.get('over3') != _calc[0] or _o.get('mean_sents') != _calc[1]:
        _ok_f2 = False
check(u'F2 汇总里的 over3 / mean_sents 与 raw jsonl 重算一致（防"改汇总不改数据"）', _ok_f2)
_sc = _sum.get('system_chars') or {}
check(u'F3 两臂 system 只差 ① 那段（含分隔空格，差 == len(①)）',
      isinstance(_sc.get('no1'), int) and isinstance(_sc.get('with1'), int)
      and _sc['with1'] - _sc['no1'] == len(LEAD),
      u'差 %s 字' % (_sc.get('with1', 0) - _sc.get('no1', 0)))
check(u'F4 两臂的护栏命中一律为 0（OOC/BANNED/MD 都不该因为去重而动）',
      all(((r.get('judge') or {}).get(k) in (None, [], False))
          for r in _rows for k in ('ooc_hits', 'banned_hits', 'md_marks')))

# =============================================== G 自检
head(u'G. 本套件自检')

_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'G1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as _f:
    _raw = _f.read()
check(u'G2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'G3 零外部盘（读的文件全在仓库内）',
      all(os.path.abspath(p).startswith(ROOT + os.sep)
          for p in (MAIN_PY, PERSONA_PY, INDEX_JSON, CARD_JSON, SNAP, AB_JSONL, AB_SUM)))
check(u'G4 判据只认产品那一个函数（本文件不自己拼尾块）',
      u"PATCH_HEADER_RALSEI + '\\n' + patch" not in _read(os.path.abspath(__file__)))

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'patch_len': len(p_idx), 'persona_len': len(_persona),
       'out_len': len(_out), 'lead_ids': len(_lead_p),
       'registry_ids': len(_reg), 'ab_rows': len(_rows),
       'ab_over3': {'no1': ((_sum.get('ab') or {}).get('no1') or {}).get('over3'),
                    'with1': ((_sum.get('ab') or {}).get('with1') or {}).get('over3')}}
with io.open(os.path.join(EV, 'patch139.json'), 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check139：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
