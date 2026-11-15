# -*- coding: utf-8 -*-
u"""第190轮（续三）· 判据：**口癖从「配额」改成「看当下场景」**。

## 用户口径（2026-11-15，逐字）

「动画又不是只有 ralsei 有，其他也做，然后，**不必要把口癖卡那么死，主要是符合当下场景**，
然后，按你的顺序施工吧」

## 为什么"卡死"要单独治（而不是把频次调低）

第189轮 §10.1 已经量清楚：靠**精确配额**（"十次里一两次"）压得住次数，
但那是拿"扣着数用"换来的 —— 模型学的是**数字**，不是**场合**：
到点就交作业，不管对方在说什么。
同轮还有一条更硬的实测：`ot_kidd` / `ut_monster_kid` 的 `Yo` 在加了频次句之后
**48/48 → 24/24 一个不差**，因为人设里同时留着「这是你的**标志**」「**不要忘记**"Yo!"」——
**强化语的压力压过频次句**。

⇒ 本轮做两件事，缺一不可：
  ① **删强化语**（`不要忘记"X"` / `最标志性` / `这是你的标志`）——这是真正让次数掉下来的那一步；
  ② **把配额换成场景判断**（"话到那儿了自然带出来，没到就一句都不带"）。

★★★ 但**不是**取消限频：每一份都仍然要有一条**行为上限**（"不是每句都带"/"多数句子直接说事"）。
      §10.1 结论 3：`welp` 那条生效的写法正是「不是每轮都要来一次，多数轮次你只是正常说完就停」——
      **没有数字，但有行为描述**。`B3` 专门钉这个：放松 ≠ 放任。

## 落点

* 全员共用规则：`npc_persona.SPEAK_RULES`（76 个 NPC 的唯一共同落点）。
  ★ 新句必须插在 `PERSONA_TONE_HUMAN` **之前**：后者要当 `SPEAK_RULES` 的**真后缀**
    （`check113h A2` 守着），这样 machine 档 `replace()` 掉四句人性话之后，
    这条口癖规则仍然在 —— 机器人同样不该"到点交作业"。
* 6 份写过配额/强化语的人设 + `asgore`（第189轮改过的那份）。

## 分段

A 规则面 5 · B 人设面 5 · C 索引面 1 · D 负控制 3 · E 自检 3 = **17 条**

★ 零 Qt、零网络、零外部盘；不 import `main`，也不构造 `RalseiPet()`。
"""
import ast
import hashlib
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
NP_PY = os.path.join(REPO, 'ralsei_pet', 'modules', 'npc_persona.py')
PERSONA_DIR = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', 'persona')
IDX_JSON = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', '_personas.json')

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))
        _failed.append(desc)


# ---------------------------------------------------------------- 判据（纯函数，便于负控制）

#: 本轮新增的两句（用户口径的落地措辞）。★ 两半必须来自**不同的句子** ——
#: 第一版两半都取自第一句，于是"删掉第二句"照样绿（M2 实测）。
NEW_RULE = (
    u'口头禅、习惯说法',
    u'话到那儿了自然带出来',
)

#: 定位「新增段」的语义关键词（不含任何整句原文 ⇒ 改措辞后仍能找到）。
NEW_KEYS = (u'口头禅', u'习惯说法', u'话到那儿')

#: 极端词表 —— 与 `check113g` 的 `EXTREME` 同源（那边管"值里不许把极端演法描述出来"）。
EXTREME = ('暴躁', '柔弱', '过分', '过度', '动不动就', '太凶', '太软',
           '撒娇', '歇斯底里', '尖叫', '哭诉', '卑微', '发火', '撒野')

#: 精确配额（本轮要清掉的东西）。★ 只列"配额"形态，不列"偶尔"这类语气词。
QUOTA_RE = re.compile(u'(?:十次里|十句里|一轮里|每句必带|每轮必念)')

#: 强化语（第189轮 §10.1 实测：它压过频次句）。★ `不要忘记` 必须紧跟引号才算 ——
#: 人设里还有「不要忘记你在第一章中的选择」（剧情提醒），那不是口癖。
BOOST_RE = re.compile(u'(?:不要忘记[\u201c\u201d"]|最标志性|标志性的口头禅|这是你的标志)')

#: 每人**必须**保留的那条行为上限（放松 ≠ 放任，见文件头 ★★★）。
BEHAVIOR_CAP = {
    'asgore': u'看场合，招呼打过了就不必再带',
    'lancer': u'不是每句都带',
    'ot_kidd': u'平常就正常说',
    'ut_monster_kid': u'平常说话不带',
    'ot_muffet': u'多数句子直接说事',
    'ot_sans': u'不是每轮都要来一次',
    'ut_sans': u'不是每轮都要来一次',
}

#: `Yo` 那两人必须有**不含口癖的中性正例**（第189轮 §9.1：例句才是杠杆）。
NEUTRAL_SAMPLE = {'ot_kidd': u'嗯，好啊', 'ut_monster_kid': u'嗯，好啊'}

#: 改前的**真实原文**（逐字从 git 取，不是编的）—— 负控制靶子。
OLD_QUOTA = (
    u'你偶尔会用“Howdy”打招呼——十次里一两次，不是每次开口都带。',
    u'只有在吹牛、自称坏蛋、或者给自己壮胆的时候才换成“本大爷”——十句里一两句，不是每句都带。',
    u'你有时会用“Yo!”开头——十次里三四次，不是每句都带。',
    u'你偶尔会用“亲爱的”“小可爱”称呼客人——十次里一两次；',
    u'这些词你挑着用，一轮里一两个就够，别每句都塞。',
)

OLD_BOOST = (
    u'· 不要忘记“Yo!”。这是 Kidd 最标志性的口头禅，但一轮里出现一两次就够。',
    u'· 不要忘记“Ahuhuhuhu~”。这是你最标志性的笑声，应该在对话中自然地出现。',
    u'· 不要忘记你的笑话。即使在严肃的时刻，你也会在最后用一个笑话收尾。这是你的标志。',
    u'这是你的标志，也是你的保护色；但不是每轮都要来一次。',
)


def new_block(val):
    """从 `SPEAK_RULES` 的值里**按语义关键词**捞出本轮新增的那几句。

    ★★★ 为什么不能直接判 `NEW_RULE` 这两个常量：那样 A3/A4 判的是**常量自己**，
    改文件（往新句里塞"过度"、塞一条引号例句）根本不影响它们 ⇒ 恒真判据
    （`mutate190b` 的 M4/M5 实测全绿才暴露）。所以必须从**被测文件**里取。
    """
    return u''.join(s for s in re.split(u'(?<=。)', val or '') if any(k in s for k in NEW_KEYS))


def speak_rules_value():
    """AST 取 `SPEAK_RULES` 的**值**（相邻字面量拼接后）。不吃注释（注释里写了教训本身）。"""
    with io.open(NP_PY, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == 'SPEAK_RULES':
                return ''.join(x.value for x in ast.walk(node.value)
                               if isinstance(x, ast.Constant) and isinstance(x.value, str))
    return None


def tone_human_value():
    with io.open(NP_PY, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == 'PERSONA_TONE_HUMAN':
                return ''.join(x.value for x in ast.walk(node.value)
                               if isinstance(x, ast.Constant) and isinstance(x.value, str))
    return None


def read_persona(tid):
    p = os.path.join(PERSONA_DIR, tid + '.txt')
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


print('=' * 72)
print('A 规则面：全员共用的那一条（插在 PERSONA_TONE_HUMAN 之前）')
print('=' * 72)

VAL = speak_rules_value()
HUMAN = tone_human_value()
check('A0 SPEAK_RULES / PERSONA_TONE_HUMAN 都能解析到', VAL is not None and HUMAN is not None,
      'rules %s 字 / human %s 字' % (len(VAL or ''), len(HUMAN or '')))
VAL = VAL or ''
HUMAN = HUMAN or ''

missing = [s for s in NEW_RULE if s not in VAL]
check('A1 新口径两句都在 SPEAK_RULES 的值里', not missing, '缺：%s' % (missing or '无'))

in_suffix = [s for s in NEW_RULE if s in HUMAN]
check('A2 ★ 新句在 PERSONA_TONE_HUMAN **之外**（后缀仍是真后缀 ⇒ machine 档也带上）',
      VAL.endswith(HUMAN) and not in_suffix,
      'endswith=%s 漏进后缀=%s' % (VAL.endswith(HUMAN), in_suffix or '无'))

hit = [w for w in EXTREME if w in new_block(VAL)]
check('A3 ★ 新句里没有把极端演法描述出来（113g 的写法红线）',
      bool(new_block(VAL)) and not hit,
      '新段 %d 字 / 命中：%s' % (len(new_block(VAL)), hit or '无'))

#: A12d：不许出现"可逐字搬走的固定例句"。判据＝新句里一个引号都没有。
check('A4 ★ 新句里没有逐字可搬的例句（不带任何引号）',
      bool(new_block(VAL)) and not re.search(u'[\u201c\u201d"]', new_block(VAL)),
      '新段 %d 字' % len(new_block(VAL)))

print()
print('=' * 72)
print('B 人设面：7 份里的配额与强化语清干净，但**上限没跟着一起丢**')
print('=' * 72)

empty = [t for t in BEHAVIOR_CAP if len(read_persona(t)) < 3000]
check('B0 分母闸：7 份人设都真读到了（每份 > 3000 字）', not empty, '异常：%s' % (empty or '无'))

q_hits = {t: QUOTA_RE.findall(read_persona(t)) for t in BEHAVIOR_CAP}
q_left = {t: v for t, v in q_hits.items() if v}
check('B1 ★ 7 份里精确配额表述为 0（十次里 / 十句里 / 一轮里）', not q_left,
      '残留：%s' % (q_left or '无'))

b_hits = {t: BOOST_RE.findall(read_persona(t)) for t in BEHAVIOR_CAP}
b_left = {t: v for t, v in b_hits.items() if v}
check('B2 ★ 7 份里强化语为 0（不要忘记"X" / 最标志性 / 这是你的标志）', not b_left,
      '残留：%s' % (b_left or '无'))

cap_missing = {t: s for t, s in BEHAVIOR_CAP.items() if s not in read_persona(t)}
check('B3 ★★★ 放松 ≠ 放任：每份都还留着一条**行为上限**（不是数字，是行为描述）',
      not cap_missing, '缺：%s' % (cap_missing or '无'))

ns_missing = {t: s for t, s in NEUTRAL_SAMPLE.items() if s not in read_persona(t)}
check('B4 `Yo` 那两人保留了一条**不含口癖**的中性正例（189 §9.1 的杠杆）',
      not ns_missing, '缺：%s' % (ns_missing or '无'))

print()
print('=' * 72)
print('C 索引面：派生字段与磁盘同源（改了人设不重算索引＝两层登记打架）')
print('=' * 72)

idx = json.load(io.open(IDX_JSON, 'r', encoding='utf-8'))
recs = {r['id']: r for r in idx['personas']}
drift = {}
for tid in BEHAVIOR_CAP:
    path = os.path.join(PERSONA_DIR, tid + '.txt')
    raw = open(path, 'rb').read()
    rec = recs.get(tid) or {}
    want = {'chars': len(raw.decode('utf-8')),
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'sha256_lf': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()}
    bad = [k for k, v in want.items() if rec.get(k) != v]
    if bad:
        drift[tid] = bad
check('C1 7 份的 chars / bytes / sha256 / sha256_lf 都与磁盘一致', not drift,
      '不同步：%s' % (drift or '无'))

print()
print('=' * 72)
print('D 负控制：证明 B1/B2 抓得住（否则"清干净了"可能只是判据看不见）')
print('=' * 72)

q_old = [s for s in OLD_QUOTA if QUOTA_RE.search(s)]
check('D1 ★ 改前的 5 条真实原文，QUOTA 判据**逐条**都要命中',
      len(q_old) == len(OLD_QUOTA), '命中 %d/%d' % (len(q_old), len(OLD_QUOTA)))

b_old = [s for s in OLD_BOOST if BOOST_RE.search(s)]
check('D2 ★ 改前的 4 条真实原文，BOOST 判据**逐条**都要命中',
      len(b_old) == len(OLD_BOOST), '命中 %d/%d' % (len(b_old), len(OLD_BOOST)))

#: 变体措辞（同义换一种写法）也必须命中 —— 防判据只认那 9 条字面量。
VARIANT = (
    (u'你每隔十句里一两句会喊一次“Yo!”。', QUOTA_RE),
    (u'你的标志性口头禅是“本大爷”，每句必带。', QUOTA_RE),
    (u'· 不要忘记“嚯嚯嚯”。', BOOST_RE),
    (u'这是你的标志。', BOOST_RE),
)
v_miss = [s for s, rx in VARIANT if not rx.search(s)]
check('D3 ★ 变体措辞也命中（判据不是只认那 9 条字面量）', not v_miss,
      '漏：%s' % (v_miss or '无'))

print()
print('=' * 72)
print('E 自检')
print('=' * 72)

raw_src = open(os.path.abspath(__file__), 'rb').read()
check('E1 本文件无 BOM、且 `ast` 可解析', not raw_src.startswith(b'\xef\xbb\xbf'))
_tree = ast.parse(raw_src.decode('utf-8'))
_imports = set()
for _n in ast.walk(_tree):
    if isinstance(_n, ast.Import):
        _imports.update(a.name.split('.')[0] for a in _n.names)
    elif isinstance(_n, ast.ImportFrom) and _n.module:
        _imports.add(_n.module.split('.')[0])
check('E2 不 import `main` / 不碰 Qt（零真机、零显示器）',
      'main' not in _imports and not any(m.startswith('PyQt') for m in _imports),
      '导入 %s' % sorted(_imports))

check('E3 判据条数固定为 17（含本条；`+1` 是因为本条还没算进去）',
      _n_pass + _n_fail + 1 == 17, '实得 %d' % (_n_pass + _n_fail + 1))

print()
print('=' * 72)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _n_fail:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 72)
sys.exit(0 if _n_fail == 0 else 1)
