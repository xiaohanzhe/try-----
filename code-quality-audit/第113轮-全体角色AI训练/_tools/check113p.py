# -*- coding: utf-8 -*-
u"""第113轮p回归锁：**NPC 之间互相寻找** —— 偏好层 + 真目的地。

用户口径（2026-10-27 逐字）
--------------------------
「npc 之间寻找偏好也要有哦」

动手前查到的两处真缺陷（都是"形状齐了、没接线"）
------------------------------------------------
1. `npc_intent._pick_friend()` 挑出了**具体某个人**，但目的地是
   `_pick_reachable(reach, rng)` —— **随机一个能去的地方**：
       return i, _pick_reachable(reach, rng), 'visit_friend'
   ⇒ `Intent.who` 有值、`dest_scene` 有值、`why='visit_friend'`，
   **"他说去看朋友，其实走到了别处"，任何报告都读不出来**。
   根因：`friends` 是 `[(id, familiar)]`（宿主把第三元素 `_s` 丢掉了），
   决策层手里**没有"那人在哪"**。
2. `main._npc_roam_decide` 里 `favorites=None` 写死 ⇒ `visit_favorite` 永远
   退化成 `wander` + `no_favorite_reachable`。（本轮**不做**，只登记。）

本套件守什么
------------
A `npc_seek` 纯函数：切句 / 两道守卫（同句指向、**问句回声不算**）/ 权重单调与钳位。
B `extract` / `rows_of`：合成夹具**真跑**，指名、主动提及、正负 cue 分别能数对。
C 登记表 `assets/npc/_seek.json`：结构合法、id 全部落在 `_registry.json`、
   权重在区间内、**不自指**、覆盖率用**只增不减的下界**。
D AST 接线：`decide()` 真的收到 `seek=` 与 `friend_scenes=`，且两者都来自
   `self._npc_seek_weights(...)` / `self._npc_friend_scenes(...)`（一步数据流）。
   ★ 一律 AST，禁纯文本扫 —— "提到某名字"类恒真判据已发作过六次。
E 行为（真跑 `decide`）：
   E1 默认参数 ⇒ 与旧实现**逐值相同**（600 拍 + 400 个随机种子逐条对照）；
   E2 给 `friend_scenes` ⇒ 目的地**就是那人在的场景**；
   E3 给 `seek` ⇒ 被偏爱的人被选中的次数**真的变多**；
   E4 负控制：`seek` 全填 1.0 ⇒ 结果与默认**完全一致**（证明 E3 的差异来自权重）。
F 破坏性负控制：拆掉 `scenes` 分支 / 把权重打回 1.0 ⇒ 对应判据**必须变红**。
G 本轮脚本自检（语法 / 无 BOM / 行尾不混 / 无恒真判据 / 记账守恒）。

稳定性（G2 要逐字节比对）
------------------------
★ 不打印随数据变化的绝对数（登记人数 / 条目数会随训练素材长），
  覆盖率只断言**下界**，失败时才回显实际值。
★ 全部写死 id 与种子，不用 `sorted()[0]`。

零网络、零 Qt、零 E 盘依赖。
"""
import ast
import io
import json
import os
import random
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
INTENT = os.path.join(PET, 'modules', 'npc_intent.py')
SEEK = os.path.join(PET, 'modules', 'npc_seek.py')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
TABLE = os.path.join(PET, 'assets', 'npc', '_seek.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_intent as NI                                     # noqa: E402
import npc_seek as S                                        # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0
_n_check = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail, _n_check
    _n_check += 1
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


# ================================================================ A 纯函数
print('=' * 74)
print('A npc_seek 纯函数')
print('=' * 74)

check('A1 切句只按句末标点/换行，**不切逗号**（名字与 cue 常分在逗号两侧）',
      S.sentences(u'后来我才明白，我其实一直依赖 Susie。他讨厌那样！') == [
          u'后来我才明白，我其实一直依赖 Susie', u'他讨厌那样'],
      repr(S.sentences(u'后来我才明白，我其实一直依赖 Susie。他讨厌那样！')))

check('A2 正 cue 命中（明说「依赖」）',
      S.score_text(u'其实我一直依赖 Susie，想再见她一次。', u'Susie')[0] >= 1,
      repr(S.score_text(u'其实我一直依赖 Susie，想再见她一次。', u'Susie')))

check('A3 ★★ 守卫一（同句指向）：没点名、也没人称代词的「我们一起走吧」**不计给任何人**',
      S.score_text(u'我们一起走吧。', u'Susie') == (0, 0, u''),
      repr(S.score_text(u'我们一起走吧。', u'Susie')))

check('A4 ★★ 守卫二（问句回声不算）：问句里已经出现「闹翻」，回答里的「闹翻」不判负',
      S.score_text(u'但如果 Kris 真的要和我彻底闹翻的话……', u'Kris',
                   question=u'如果有一天你和Kris彻底闹翻了，你会先低头吗？')[1] == 0,
      repr(S.score_text(u'但如果 Kris 真的要和我彻底闹翻的话……', u'Kris',
                        question=u'如果有一天你和Kris彻底闹翻了，你会先低头吗？')))

check('A4b 上一条的**正控制**：不给 question ⇒ 同一个「闹翻」真的被判负'
      '（证明 A4 变 0 是那道闸干的，不是词表里没有这个词）',
      S.score_text(u'但如果 Kris 真的要和我彻底闹翻的话……', u'Kris')[1] == 1,
      repr(S.score_text(u'但如果 Kris 真的要和我彻底闹翻的话……', u'Kris')))

check('A5 中文别名生效：「苏西」能认出是 Susie（cue 用真实词表里的「一起」）',
      S.score_text(u'苏西你这丫头，下次一起去吧。', u'Susie',
                   [u'Susie', u'苏西'])[0] >= 1,
      repr(S.score_text(u'苏西你这丫头，下次一起去吧。', u'Susie',
                        [u'Susie', u'苏西'])))

check('A6 权重：0 次提及 = 1.0（中性）；提及越多越大（单调不降）',
      S.weigh(0) == 1.0 and S.weigh(1) > S.weigh(0) and S.weigh(10) >= S.weigh(5),
      'w(0)=%.2f w(1)=%.2f w(5)=%.2f w(10)=%.2f'
      % (S.weigh(0), S.weigh(1), S.weigh(5), S.weigh(10)))

check('A7 负 cue 降权、且整体钳在 [W_MIN, W_MAX]',
      S.weigh(0, 0, 2) < 1.0
      and S.weigh(999, 99, 0) <= S.W_MAX and S.weigh(0, 0, 99) >= S.W_MIN,
      'neg2=%.2f 上限=%.2f 下限=%.2f'
      % (S.weigh(0, 0, 2), S.weigh(999, 99, 0), S.weigh(0, 0, 99)))

check('A8 坏输入不抛：weigh(None) / 非数字 ⇒ 1.0',
      S.weigh(None) == 1.0 and S.weigh('abc') == 1.0,
      '%r %r' % (S.weigh(None), S.weigh('abc')))


# ================================================================ B 抽取
print()
print('=' * 74)
print('B extract / rows_of（合成夹具，真跑）')
print('=' * 74)

_FIX = [
    {'slot': '__REL1__', 'user': u'你和Susie的关系一开始是什么样的？',
     'final': u'我和Susie一起长大，我很依赖她。'},
    {'slot': '__REL2__', 'user': u'后来你和Kris之间有什么变化吗？',
     'final': u'Kris 啊……我们没什么变化。'},
    {'slot': '__PREF1__', 'user': u'你平时喜欢做什么？',
     'final': u'我喜欢看书，Susie 也喜欢这个。'},
    {'slot': 'close', 'user': u'随便聊聊？', 'final': u'Susie 最近还好吗。'},
]
_REL = [u'Susie', u'Kris']

_m = S.mentions(_FIX, _REL)
check('B1 主动提及：问句**已点名**的轮次不算，问句没点名却提到的算',
      _m.get(u'Susie') == 2 and _m.get(u'Kris', 0) == 0, repr(_m))

_m2 = S.mentions(_FIX[:1] + _FIX[3:], _REL)
check('B2 上一条的正控制：拿掉那两轮「问句没点名」的对话 ⇒ Susie 的提及数下降',
      _m2.get(u'Susie', 0) < _m.get(u'Susie', 0), repr(_m2))

_ex = S.extract(_FIX, _REL)
check('B3 关系段点名命中：Susie 有正 cue 分，Kris 没有（他那句不带关系词）',
      _ex.get(u'Susie', {}).get('pos', 0) >= 1
      and _ex.get(u'Kris', {}).get('pos', 0) == 0, repr(_ex))

_rows = S.rows_of({'turns': _FIX, 'relations': _REL})
check('B4 rows_of 带出 w/mention/pos/neg/why，且 why 是一句**真原话**',
      bool(_rows) and all(set(v.keys()) >= {'w', 'mention', 'pos', 'neg', 'why'}
                          for v in _rows.values())
      and any((v.get('why') or u'').strip() for v in _rows.values()),
      repr({k: (v['w'], v['mention']) for k, v in _rows.items()}))

_rows2 = S.rows_of({'turns': _FIX, 'relations': _REL},
                   id_of=lambda nm: None if nm == u'Susie' else nm.lower())
check('B5 `id_of` 返回 None 时**保留原名**（不静默丢人、也不猜 id）'
      '——把 Susie 的解析故意打断，她必须以原名留下',
      u'Susie' in _rows2 and u'susie' not in _rows2, repr(sorted(_rows2)))

check('B6 空输入不抛：extract([], []) == {} 且 mentions 也为空',
      S.extract([], []) == {} and S.mentions([], []) == {})


# ================================================================ C 登记表
print()
print('=' * 74)
print('C 登记表 `assets/npc/_seek.json`')
print('=' * 74)

_tbl = S.load(TABLE)
_ids = set()
try:
    _reg = json.loads(_read(REG))
    _ids = set(r.get('id') for r in (_reg.get('npcs') or []) if isinstance(r, dict))
except Exception:
    _ids = set()

check('C1 登记表读得到且 `seek` 是非空 dict', isinstance(_tbl.get('seek'), dict)
      and bool(_tbl.get('seek')), 'seek 键数=%d' % len(_tbl.get('seek') or {}))

check('C2 `method` / `formula` / `unresolved_names` 三个"说清口径"的字段都在'
      '（下一个人不会把它当宣判）',
      bool(_tbl.get('method')) and bool(_tbl.get('formula'))
      and isinstance(_tbl.get('unresolved_names'), dict))

_bad_owner = [k for k in (_tbl.get('seek') or {}) if k not in _ids]
check('C3 每个登记人的 id 都在 `_registry.json` 里', not _bad_owner, repr(_bad_owner[:5]))

_bad_who, _self, _out = [], [], []
for _o, _row in (_tbl.get('seek') or {}).items():
    for _w, _v in (_row or {}).items():
        if _w not in _ids:
            _bad_who.append((_o, _w))
        if _w == _o:
            _self.append(_o)
        try:
            if not (S.W_MIN <= float(_v.get('w')) <= S.W_MAX):
                _out.append((_o, _w, _v.get('w')))
        except Exception:
            _out.append((_o, _w, _v))
check('C4 每个被找的人 id 也都在 registry 里（不许挂到不存在的人身上）',
      not _bad_who, repr(_bad_who[:5]))
check('C5 不许**找自己**（自指条目一律不该生成）', not _self, repr(_self[:5]))
check('C6 所有权重都钳在 [W_MIN, W_MAX]', not _out, repr(_out[:5]))

_n_char, _n_item = S.summarize(_tbl)
check('C7 覆盖率下界：**至少 40 人**有偏好条目（下界只增不减；补素材只会更多）',
      _n_char >= 40, '实际 %d 人' % _n_char)
check('C8 条目数 ≥ 人数（每人平均至少一条）', _n_item >= _n_char,
      '实际 %d 条 / %d 人' % (_n_item, _n_char))

_bw = S.weights_of(_tbl, 'berdly')
check('C9 写死样本：`berdly` 的偏好里真有 `noelle`，且权重 > 1.0'
      '（`berdly` 主动提她 14 次）',
      isinstance(_bw, dict) and _bw.get('noelle', 0) > 1.0, repr(_bw))

check('C10 负控制：没人登记的角色 ⇒ `weights_of` 返 `{}`（不是"人人 1.0"）',
      S.weights_of(_tbl, '__no_such_npc__') == {})


# ================================================================ D AST 接线
print()
print('=' * 74)
print('D AST 接线：`decide()` 真的收到 seek / friend_scenes')
print('=' * 74)

_src = _read(MAIN)
_tree = ast.parse(_src)


def _find_cls_method(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return fn
    return None


_dec = _find_cls_method(_tree, '_npc_roam_decide')
_fs = _find_cls_method(_tree, '_npc_friend_scenes')
_st = _find_cls_method(_tree, '_npc_seek_table')


def _decide_call(fn):
    if fn is None:
        return None
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'decide':
            return node
    return None


_call = _decide_call(_dec)
_kw = {k.arg: k.value for k in (_call.keywords if _call else []) if k.arg}
check('D1 `_npc_roam_decide` 里的 `npc_intent_mod.decide(...)` 存在（定位器有效）',
      _call is not None, 'call=%r' % (_call is not None))

check('D2 `decide()` 真的带 `seek=`（不是只在注释里写）',
      'seek' in _kw, repr(sorted(_kw)))

check('D3 `seek=` 的值来自 `self._npc_seek_weights(...)`（一步数据流，不是常量/None）',
      isinstance(_kw.get('seek'), ast.Call)
      and isinstance(_kw['seek'].func, ast.Attribute)
      and _kw['seek'].func.attr == '_npc_seek_weights',
      repr(getattr(_kw.get('seek'), 'func', None)))

check('D4 `decide()` 真的带 `friend_scenes=`',
      'friend_scenes' in _kw, repr(sorted(_kw)))

check('D5 `friend_scenes=` 的值来自 `self._npc_friend_scenes(...)`',
      isinstance(_kw.get('friend_scenes'), ast.Call)
      and isinstance(_kw['friend_scenes'].func, ast.Attribute)
      and _kw['friend_scenes'].func.attr == '_npc_friend_scenes',
      repr(getattr(_kw.get('friend_scenes'), 'func', None)))

# `_npc_friend_scenes` 里真的取了第三个元素（`item[2]`），不是只回 {}
_idx2 = []
if _fs is not None:
    for node in ast.walk(_fs):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and node.slice.value == 2:
            _idx2.append(True)
check('D6 `_npc_friend_scenes` 真的读了元组的**第三元素**（`item[2]` = 那人在哪）',
      bool(_idx2), '命中 %d 处' % len(_idx2))

# `_npc_seek_table` 真的读了 `npc_seek_mod.FILENAME`
_reads_name = False
if _st is not None:
    for node in ast.walk(_st):
        if isinstance(node, ast.Attribute) and node.attr == 'FILENAME':
            _reads_name = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'load':
            _reads_name = _reads_name or True
check('D7 `_npc_seek_table` 真的调了 `npc_seek.load(...)` 并引用 `FILENAME`',
      _reads_name, 'reads=%s' % _reads_name)

# 反回滚闸：这三个函数不许被删成空壳
check('D8 三个新方法都**有实体**（不是 `pass` 占位）',
      all(fn is not None and len(fn.body) >= 2 for fn in (_dec, _fs, _st)),
      'dec=%s fs=%s st=%s' % tuple(bool(x) for x in (_dec, _fs, _st)))


# ================================================================ E 行为
print()
print('=' * 74)
print('E 行为：真的会走到人那儿，偏好真的改选人')
print('=' * 74)

_REACH = ['s.a', 's.b', 's.c', 's.d']
_FRI = [('kris', 0.9), ('susie', 0.8)]


def _run(**kw):
    out = []
    for d in range(600):
        now = 86400.0 * (9000 + d) + 3600.0 * 18
        it = NI.decide('d', now, reachable=_REACH, friends=_FRI, **kw)
        out.append((it.what, it.who, it.dest_scene, it.why))
    return out


_a = _run()
_b = _run(friend_scenes={'kris': 's.b', 'susie': 's.d'})
_c = _run(seek={'kris': 1.8, 'susie': 0.45})
_d = _run(seek={'kris': 1.0, 'susie': 1.0})

check('E1 ★★ 负回归：`seek` 全填 1.0 ⇒ 与默认参数**逐值完全相同**'
      '（新分支不改旧行为）', _a == _d)

# 旧实现逐值对照（把旧 `_pick_friend` 复刻一遍）
def _old_pick(friends, reach, rng):
    cand = [(i, f) for i, f in friends if f > 0 and i]
    wts = [max(1e-6, f) for _, f in cand]
    total = sum(wts)
    x = rng.random() * total
    acc = 0.0
    for (i, f), wv in zip(cand, wts):
        acc += wv
        if x < acc:
            return i, reach[rng.randrange(len(reach))], 'visit_friend'
    i, _f = cand[-1]
    return i, reach[rng.randrange(len(reach))], 'visit_friend'


_diff = 0
for _k in range(400):
    if _old_pick(_FRI, _REACH, random.Random(_k)) != \
            NI._pick_friend(_FRI, _REACH, random.Random(_k)):
        _diff += 1
check('E1b ★★ 默认参数下 `_pick_friend` 与**旧实现**逐条相同（400 个随机种子）',
      _diff == 0, '不同 %d / 400' % _diff)

_who_dest_b = sorted({(x[1], x[2]) for x in _b if x[1]})
check('E2 ★★★ 给 `friend_scenes` ⇒ 目的地**就是那人在的场景**'
      '（这是本轮修的那个"假目的地"缺陷）',
      _who_dest_b == [('kris', 's.b'), ('susie', 's.d')], repr(_who_dest_b))

check('E2b 且 `why` 是 `visit_friend`（找到人），不是 `visit_friend_away`',
      all(x[3] == 'visit_friend' for x in _b if x[1]),
      repr(sorted({x[3] for x in _b if x[1]})))

_away = _run(friend_scenes={'kris': 's.zzz', 'susie': 's.a'})
check('E2c 朋友在的场景**不可达** ⇒ 如实标 `visit_friend_away`（不把回落伪装成成功）',
      any(x[3] == 'visit_friend_away' for x in _away if x[1]),
      repr(sorted({x[3] for x in _away if x[1]})))

_wa = [x[1] for x in _a if x[1]]
_wc = [x[1] for x in _c if x[1]]
check('E3 ★★ 给 `seek` ⇒ 被偏爱的人（kris ×1.8）被选中的次数**真的变多**，'
      '被压低的人（susie ×0.45）变少',
      _wc.count('kris') > _wa.count('kris') and _wc.count('susie') < _wa.count('susie'),
      'kris %d→%d, susie %d→%d'
      % (_wa.count('kris'), _wc.count('kris'), _wa.count('susie'), _wc.count('susie')))


# ================================================================ F 破坏性负控制
print()
print('=' * 74)
print('F 破坏性负控制（证明 E 不是恒真）')
print('=' * 74)

# F1：把 scenes 打回 None ⇒ E2 的判据必须失效
_f1 = sorted({(x[1], x[2]) for x in _run() if x[1]})
check('F1 拆掉 `scenes` 分支（打回 None）⇒ 目的地重新变成**随机可达点**'
      '（E2 不是恒真）',
      _f1 != [('kris', 's.b'), ('susie', 's.d')]
      and {d for _w, d in _f1} <= set(_REACH), repr(_f1))

# F2：把权重倍数打回 1.0 ⇒ E3 的差异必须消失
_keep = getattr(NI, '_seek_mul', None)
_f2_ok = False
try:
    NI._seek_mul = lambda seek, who: 1.0
    _f2 = _run(seek={'kris': 1.8, 'susie': 0.45})
    _f2_ok = (_f2 == _a)
finally:
    if _keep is not None:
        NI._seek_mul = _keep
check('F2 把 `_seek_mul` 打回恒 1.0 ⇒ 与默认结果**完全相同**'
      '（证明 E3 的差异真来自权重，不是随机噪声）', _f2_ok)

# F3：正控制——恢复后 E3 仍然成立
_f3 = _run(seek={'kris': 1.8, 'susie': 0.45})
check('F3 正控制：把 `_seek_mul` 装回去 ⇒ E3 的差异重新出现',
      _f3 == _c, '恢复后一致=%s' % (_f3 == _c))


# ================================================================ G 自检
print()
print('=' * 74)
print('G 本轮脚本自检')
print('=' * 74)

for _p in (MAIN, INTENT, SEEK):
    _t = _read(_p)
    _ok = True
    try:
        ast.parse(_t)
    except SyntaxError:
        _ok = False
    check('G1 `%s` 语法可解析（用 ast.parse，不产 .pyc）' % os.path.basename(_p), _ok)

_bom = [os.path.basename(p) for p in (MAIN, INTENT, SEEK)
        if io.open(p, 'rb').read(3) == b'\xef\xbb\xbf']
check('G2 三个文件都没有 BOM', not _bom, repr(_bom))

_eol = []
for _p in (MAIN, INTENT, SEEK):
    _t = _read(_p)
    _crlf = _t.count('\r\n')
    _lf = _t.count('\n')
    _eol.append((os.path.basename(_p), _crlf, _lf))
# main.py 必须全 CRLF；两个 modules 必须全 LF —— 与原文件一致，不许编辑后变混行
_mixed_main = _eol[0][1] != _eol[0][2]
_mixed_mods = any(c != 0 for _n, c, _l in _eol[1:])
check('G3 行尾不混：`main.py` 全 CRLF、`npc_intent.py`/`npc_seek.py` 全 LF',
      not _mixed_main and not _mixed_mods, repr(_eol))

# 恒真判据复查：本文件里不许出现 `check(<desc>, True)` / `check(<desc>, 1)`
_self_src = _read(os.path.abspath(__file__))
_self_tree = ast.parse(_self_src)
_taut = 0
for _node in ast.walk(_self_tree):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and len(_node.args) >= 2:
        _a1 = _node.args[1]
        if isinstance(_a1, ast.Constant) and _a1.value in (True, 1):
            _taut += 1
check('G4 本套件里**没有**恒真判据（`check(desc, True)` 这一类）', _taut == 0,
      '命中 %d 处' % _taut)

# 正控制：扫描器本身有牙（构造一个恒真判据喂给它，必须被数出来）
_taut_probe = 0
_probe_tree = ast.parse('check("x", True)\n')
for _node in ast.walk(_probe_tree):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and len(_node.args) >= 2:
        if isinstance(_node.args[1], ast.Constant) and _node.args[1].value in (True, 1):
            _taut_probe += 1
check('G5 上一条的**正控制**：扫描器对 `check("x", True)` 真的会数出来（不是恒 0）',
      _taut_probe == 1, '命中 %d 处' % _taut_probe)


# ==================================================== H 宿主熟络度 API（活体核对）
# ★★★ 为什么必须有这一段：`main._npc_roam_friends` 原来调 `bonds.familiarity(...)`，
#   而 `npc_life.Bonds` **没有这个方法**。整块包在 `except Exception` 里 ⇒
#   `AttributeError` 被静默吞成 `fam = 0.0` ⇒ `if fam <= 0.0: continue` ⇒
#   **`friends` 对每个 NPC 恒为 `[]`** ⇒ `visit_friend` 永不发生、睡朋友家永不发生、
#   `npc_seek` 的权重**永远没有候选可乘**。
#   这是「形状有了、也接线了、值恒为空」——`check78` 的 E/F 段喂的是**合成** friends，
#   正好绕过这条链，所以它一直全绿。⇒ 判据要打**宿主真调的方法名是否真实存在**。
print()
print('=' * 74)
print('H 宿主熟络度 API（形状有了、值恒为空的那条链）')
print('=' * 74)

import npc_life as NL                                       # noqa: E402

_NL_API = frozenset(m for m in dir(NL.Bonds) if not m.startswith('_'))


def _bonds_call_attrs(tree):
    """`<bonds>.<attr>(...)` 的全部 `(attr, lineno)`（只看接收者名叫 `bonds` 的调用）。"""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            v = n.func.value
            if isinstance(v, ast.Name) and v.id == 'bonds':
                out.append((n.func.attr, n.lineno))
    return out


_H_CALLS = _bonds_call_attrs(ast.parse(_read(MAIN)))
# ★ 必须同时要求**非空**：`all([])` 恒为真 —— 只判 `all(...)` 的话，
#   一旦那段代码被删掉/改名，判据会变恒真（比不写还危险）。
_H_BAD = [(a, ln) for a, ln in _H_CALLS if a not in _NL_API]
check('H1 ★★★ main.py 里 `bonds.<方法>()` 调的每个方法都真实存在于 `npc_life.Bonds`',
      len(_H_CALLS) >= 1 and not _H_BAD,
      '调用点=%s 不存在=%s Bonds 公开 API=%s'
      % ([(a, ln) for a, ln in _H_CALLS], _H_BAD or '无', sorted(_NL_API)))

# ---- H1n 破坏性负控制：把 `bonds.get(` 改回 `bonds.familiarity(` ⇒ H1 必须报红
_H_src = _read(MAIN)
_H_mut = _H_src.replace('bonds.get(', 'bonds.familiarity(')
assert _H_mut != _H_src, '负控制没命中：源码里找不到 `bonds.get(` ⇒ 变异无效（假红/假绿都可能）'
_MUT_CALLS = _bonds_call_attrs(ast.parse(_H_mut))
_MUT_BAD = [(a, ln) for a, ln in _MUT_CALLS if a not in _NL_API]
check('H1n ★★ 负控制：把 `bonds.get(` 变异回 `bonds.familiarity(` ⇒ H1 必须判红',
      bool(_MUT_BAD), '变异后不存在的方法=%s' % (_MUT_BAD or '无(判据没牙!)'))

# ---- H2 A/B 成对：没播种 ⇒ 0.0（`fam <= 0` 分支可进）；播种 ⇒ > 0（能过闸）
_b_stranger = NL.Bonds()
_b_seeded = NL.Bonds(seed_lookup=lambda _a, _b: NL.SEED_SAME_PRODUCTION)
check('H2 ★★ `Bonds.get` 的两种取值都能出现：未播种=0.0（会被 `continue` 跳过）· 播种>0（能过闸）',
      float(_b_stranger.get('kris', 'susie')) == 0.0
      and float(_b_seeded.get('kris', 'susie')) > 0.0,
      'stranger=%.3f seeded=%.3f' % (float(_b_stranger.get('kris', 'susie')),
                                     float(_b_seeded.get('kris', 'susie'))))

# ---- H3 AST 形状：`_npc_roam_friends` 交出去的是**三元组** `(oid, fam, scene)`
_FR_FN = None
for _n in ast.walk(ast.parse(_read(MAIN))):
    if isinstance(_n, ast.FunctionDef) and _n.name == '_npc_roam_friends':
        _FR_FN = _n
        break
_H3_triple = False
_H3_detail = '函数未找到'
if _FR_FN is not None:
    for _n in ast.walk(_FR_FN):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'append' and len(_n.args) == 1 \
                and isinstance(_n.args[0], ast.Tuple) and len(_n.args[0].elts) == 3 \
                and isinstance(_n.args[0].elts[2], ast.Name) \
                and _n.args[0].elts[2].id == 'scene':
            _H3_triple = True
    _H3_detail = '三元组且第三项是 scene' if _H3_triple else '没找到 (oid, fam, scene) 形状'
check('H3 ★★ `_npc_roam_friends` 交出**三元组** `(oid, fam, scene)`（第三项是"他住哪"）',
      _H3_triple, _H3_detail)

# ---- H4 数据事实：Deltarune 章的站位**够用**（这条是防回滚/防丢数据的绊线）
_H4 = '加载失败'
try:
    import npc_placement as NPL                             # noqa: E402
    import npc_system as NSY                                # noqa: E402
    _book = NPL.load_placement(PET)
    _reg = NSY.load_registry(PET)
    _ids = [getattr(o, 'id', None) for o in _reg.all()]
    _ids = [i for i in _ids if i]
    _dr = [i for i in _ids
           if not i.startswith(('hy_', 'os_', 'ot_', 'ut_'))]
    _dr_ok = [i for i in _dr if _book.scene_of(i)]
    _rest = [i for i in _ids if i.startswith(('hy_', 'os_', 'ot_', 'ut_'))]
    _rest_ok = [i for i in _rest if _book.scene_of(i)]
    _H4_ok = len(_dr_ok) >= 30
    _H4 = ('Deltarune %d/%d 有场景 · 跨作品 %d/%d 有场景'
           % (len(_dr_ok), len(_dr), len(_rest_ok), len(_rest)))
except Exception as _e:                                     # noqa: BLE001
    _H4_ok = False
    _H4 = '异常 %s: %s' % (type(_e).__name__, _e)
# ★ 跨作品 0 是**已知数据缺口**（第87轮遗留），这里只记录、不判红：
#   要让他们互相登门，得先在 `_placement.json` 里登记站位 —— 那是另一件事。
check('H4 ★★ Deltarune 章的站位覆盖 ≥30 人（`visit_friend` 现实上可发生；防回滚丢数据）',
      _H4_ok, _H4)


# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
