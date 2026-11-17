# -*- coding: utf-8 -*-
u"""第194轮 · 内在活动「只存关键词」（四要素：时间 / 地点 / 人物 / 干啥）。

## 这一轮要证明的事

用户口径（§201.4，第193/194轮）：

  `这些想法当成记忆也就是后面要是问能说出来，但当时不用用旁白`
  `心里想的东西存在记忆力，后期问起来能说出来就足够了`
  `只需要关键词`
  `时间，地点，人物，干啥`
  `这些记忆可以有一定偏差，但不能太离谱，就像真人一样`

⇒ 读法：`（盘算了一下）要不要开口` 里的**内在活动**不进片段正文，
只记四要素；`要不要开口`（台词）照旧入库。

## 三个最容易做错的地方（各写成判据）

1. **只存动词的条目永远召不回来。** `recall()` 里 keys 的匹配面是
   `text` 做**子串**比较，而没有人会在聊天时说出"盘算"两个字。
   ⇒ 地点必须并进匹配面（只对 `kind == 'inner'`）。
   **C3 是这条的负控制**：另造一条 `where` 为空的内在活动，`recall('教室')`
   不许命中它 —— 否则"命中"可能来自别处，不是地点。
2. **不能拿显示层护栏来拆记忆。** `strip_action_parentheticals()` 会删掉
   **所有**括号旁白；§201.4 明写「动作/动画＝外在表现（→旁白）」，旁白该说出口。
   ⇒ E3 钉住 `_note_memory` 里**不许**出现它。
3. **内在活动不能说成"说过"。** 它不是「角色发出的声音」，而是没说出口的。
   ⇒ D1 钉渲染；D3 是负控制：普通片段必须**仍然**是"说过"，证明分支没把老逻辑吞掉。

## 分段

A 纯函数 7 · B 写入与限额 6 · C 召回（含负控制）4 ·
D 渲染 3 · E 接线（AST）5 · F 自检 3 = **28 条**

零网络、零 Ollama；不 import `main`、不构造 `RalseiPet()`；
记忆库用 `tempfile` 隔离，退出即删（不碰真实 D 盘记忆）。
"""
import ast
import hashlib
import io
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
ES_PY = os.path.join(MODS, 'event_speech.py')
MS_PY = os.path.join(MODS, 'memory_system.py')
DU_PY = os.path.join(MODS, 'dialogue_ui.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# ★ 记忆库隔离：必须在 import memory_system 之前设，否则会读到真实 D 盘记忆
_VAULT = tempfile.mkdtemp(prefix='ms194_')
os.environ['RALSEI_MEMORY_DIR'] = _VAULT
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _calls(node):
    """函数体里被**调用**的名字集合（Name 与 Attribute 都收）。"""
    out = set()
    if node is None:
        return out
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


ES_SRC = _read(ES_PY)
MS_SRC = _read(MS_PY)
DU_SRC = _read(DU_PY)
MS_TREE = ast.parse(MS_SRC)
DU_TREE = ast.parse(DU_SRC)

import event_speech as ES                                        # noqa: E402

# ================================================================ A 纯函数
check(u'A1 `盘算了一下` 取出动词 `盘算`',
      ES.inner_verb(u'盘算了一下') == u'盘算', repr(ES.inner_verb(u'盘算了一下')))
check(u'A2 长词优先：`想了想` 不被截成 `想`',
      ES.inner_verb(u'想了想') == u'想了想'
      and ES.inner_verb(u'想了想') != u'想', repr(ES.inner_verb(u'想了想')))
check(u'A3 `我` 开头的心里话不算内在活动（C19/A22c 契约）',
      ES.inner_verb(u'我想想该怎么说') == u'', repr(ES.inner_verb(u'我想想该怎么说')))
check(u'A4 摘得到内在活动括号',
      list(ES.iter_inner_acts(u'（盘算了一下）要不要开口')) == [u'盘算了一下'],
      repr(list(ES.iter_inner_acts(u'（盘算了一下）要不要开口'))))
check(u'A5 放过外在表现（动作要变旁白，不许吞）',
      list(ES.iter_inner_acts(u'（手忙脚乱地翻口袋）好的')) == [],
      repr(list(ES.iter_inner_acts(u'（手忙脚乱地翻口袋）好的'))))
check(u'A6 放过发声类（`（笑声：X）` 是台词不是心思）',
      list(ES.iter_inner_acts(u'（笑声：Geh ha ha ha ha）')) == [],
      repr(list(ES.iter_inner_acts(u'（笑声：Geh ha ha ha ha）'))))

_SAMPLES = [u'想了想', u'盘算了一下', u'犹豫', u'沉默片刻', u'我想想该怎么说',
            u'手忙脚乱地翻口袋', u'笑声：NYEH HEH HEH!', u'微微一笑']
_split = [s for s in _SAMPLES if (ES.inner_verb(s) != u'') != ES.is_inner_act(s)]
check(u'A7 `inner_verb` 与 `is_inner_act` 同源（不许一个说是一不是说）',
      not _split, u'分裂样本=%r' % (_split,))

# ================================================================ B 写入与限额
import memory_system as MSYS                                     # noqa: E402


class _P(object):
    api_enabled = False


ms = MSYS.MemorySystem(_P())

_n_frag0 = len(ms.fragments)
_rec = ms.note_inner(u'盘算', who='ralsei', where=u'教室')
check(u'B1 写入成功且 kind=inner',
      isinstance(_rec, dict) and _rec.get('kind') == 'inner',
      repr(_rec.get('kind') if isinstance(_rec, dict) else None))

_meta = (_rec or {}).get('meta') or {}
check(u'B2 四要素齐全（时间/地点/人物/干啥）',
      bool(_rec) and _rec.get('text') == u'盘算'
      and bool(_rec.get('day')) and bool(_rec.get('tod'))
      and _meta.get('where') == u'教室' and _meta.get('who') == 'ralsei',
      # ★ 回显**只给"有没有"、不给具体值**：`day`/`tod` 来自真实墙钟，
      #   回显出来就等于把基线钉在"今天这个时段"——换个时段跑必 DIFF。
      u'text=%r 有day=%r 有tod=%r meta=%r'
      % ((_rec or {}).get('text'), bool((_rec or {}).get('day')),
         bool((_rec or {}).get('tod')), _meta))

check(u'B3 原句不落盘：fragments 条数不变',
      len(ms.fragments) == _n_frag0, u'%d -> %d' % (_n_frag0, len(ms.fragments)))

ms.note_inner(u'盘算', who='ralsei', where=u'教室')
_in1 = [k for k in ms.keys if k.get('kind') == 'inner']
check(u'B4 同（动词,地点）2h 内去重，count 累加',
      len(_in1) == 1 and int(_in1[0].get('count', 0)) == 2,
      u'inner=%d count=%r' % (len(_in1),
                              _in1[0].get('count') if _in1 else None))

ms.note_inner(u'盘算', who='ralsei', where=u'走廊')
_in2 = [k for k in ms.keys if k.get('kind') == 'inner']
check(u'B5 负控制：换个地点就是另一条（去重键含地点）',
      len(_in2) == 2, u'inner=%d' % len(_in2))

# 限额：只丢 inner，关键记忆一条不许少
ms.remember_key('level', u'升级到五级')
for _i in range(85):
    ms.note_inner(u'想', who='ralsei', where=u'地点%d' % _i)
_inners = [k for k in ms.keys if k.get('kind') == 'inner']
_keeps = [k for k in ms.keys if k.get('kind') == 'level']
# ★ 这里**只钉"只裁 inner、关键记忆一条不少"**，故意**不钉**「教室」那条还活着 ——
#   它死不死取决于 `(last_at, count)` 排序下 85 条是否落在同一时间刻度（见 C 段开头的
#   长注释）。把它钉进来就等于把判据绑在机器快慢上。
check(u'B6 超限只裁 inner（上限 %d），关键记忆仍在'
      % ms.INNER_KEYS_MAX,
      len(_inners) <= ms.INNER_KEYS_MAX and len(_keeps) == 1,
      u'inner=%d key=%d' % (len(_inners), len(_keeps)))

# ================================================================ C 召回
# ★★★ 必须**另起一个干净的库**，不许复用上面那个被 B6 冲爆的 `ms`。
#   第194轮收口时踩到的真坑（单跑 28/28、全量跑 25/28，同一份代码）：
#   B6 灌了 85 条 `note_inner`，`_trim_inner()` 按 `(last_at, count)` **升序**删最老的
#   那几条，而「教室」是**最先写入**的一条 —— 于是它到底死不死取决于机器负载：
#     · 机器快：85 条挤进同一个 `time.time()` 刻度 ⇒ `last_at` 全等 ⇒ 退化成按
#       `count` 排 ⇒ 「教室」`count=2` 排最后、侥幸活着；
#     · 机器慢（刚跑完 190 个套件、每条 `note_inner` 还都要 `autosave()` 写盘）：
#       `last_at` 被拉开成严格递增 ⇒ 真 LRU ⇒ 「教室」排第一被裁。
#   ⇒ **判据绿不绿由机器快慢决定**，这是假红。产品侧没错（删"最久没想起的"本就该删它），
#   错的是夹具：**每条判据必须自带状态，不许继承上一条判据的副作用**。
_ms_c = MSYS.MemorySystem(_P())
_ms_c.keys = []
_ms_c.note_inner(u'盘算', who='ralsei', where=u'教室')

_hit = [h for h in _ms_c.recall(u'教室', limit=6, reinforce=False)
        if h.get('kind') == 'inner']
check(u'C1 按地点召回到内在活动', bool(_hit), u'hits=%d' % len(_hit))

_miss = [h for h in _ms_c.recall(u'完全无关的词zzz', limit=6, reinforce=False)
         if h.get('kind') == 'inner']
check(u'C2 负控制：无关词不命中', not _miss, u'hits=%d' % len(_miss))

# ★ C3：另起一个库，造一条 **where 为空** 的内在活动 ⇒ 它不该被 "教室" 召回。
#   少了这条，"C1 命中"可能只是碰巧（比如动词本身被匹配上了）。
#   ★★ 必须**先清空 keys**：同一个 `RALSEI_MEMORY_DIR` 下新构造的 MemorySystem
#      会从盘上**继承** ms 刚写进去的"教室"那条（实测踩到：命中数=1，但命中
#      的是继承来的记录，不是它自己那条 —— 夹具不隔离 ⇒ 假红）。
_ms3 = MSYS.MemorySystem(_P())
_ms3.keys = []
_ms3.note_inner(u'盘算', who='ralsei', where=u'')
_hit3 = [h for h in _ms3.recall(u'教室', limit=6, reinforce=False)
         if h.get('kind') == 'inner']
check(u'C3 负控制：无地点的那条不被「教室」召回（证明确实是地点在起作用）',
      not _hit3 and len([k for k in _ms3.keys if k.get('kind') == 'inner']) == 1,
      u'hits=%d inner_keys=%d' % (
          len(_hit3), len([k for k in _ms3.keys if k.get('kind') == 'inner'])))

_hit4 = [h for h in ms.recall(u'升级', limit=6, reinforce=False)
         if h.get('is_key') and h.get('kind') == 'level']
check(u'C4 老的关键记忆匹配行为不变', bool(_hit4), u'hits=%d' % len(_hit4))

# ================================================================ D 渲染
# ★ 同样用 `_ms_c`（干净库），不复用被 B6 冲过的 `ms` —— 理由见 C 段开头。
_txt = _ms_c.recall_text(u'教室', limit=6)
check(u'D1 内在活动不说「说过」', bool(_txt) and u'说过' not in _txt, repr(_txt[:120]))
check(u'D2 内在活动渲染带地点', u'教室' in _txt, repr(_txt[:120]))

_ms5 = MSYS.MemorySystem(_P())
_ms5.keys = []
_ms5.add_fragment(u'今天天气不错，我们去院子里坐了一会儿', who='user', kind='dialogue')
_txt5 = _ms5.recall_text(u'天气', limit=6)
check(u'D3 负控制：普通片段仍然渲染成「说过」',
      bool(_txt5) and u'说过' in _txt5,
      # ★ 不回显原文：这行渲染带 `tod`（"刚刚的**深夜**，你说过…"），回显就把基线
      #   钉死在跑的那一时段（第194轮收口实测：22:55 是"晚上"、23:0x 变成"深夜"）。
      u'含说过=%r' % (u'说过' in _txt5,))

# ================================================================ E 接线（AST）
_nm = _func(DU_TREE, '_note_memory')
_c = _calls(_nm)
check(u'E1 `_note_memory` 调了 `_iter_inner_acts`',
      '_iter_inner_acts' in _c, repr(sorted(_c)))
check(u'E2 `_note_memory` 调了 `note_inner`',
      'note_inner' in _c, repr(sorted(_c)))
check(u'E3 `_note_memory` 里**不许**出现 `strip_action_parentheticals`'
      u'（那是显示层护栏，会连外在表现一起删）',
      'strip_action_parentheticals' not in _c, repr(sorted(_c)))

_pl = _func(DU_TREE, '_current_place_label')
_pl_names = _calls(_pl)
_pl_strs = set()
if _pl is not None:
    for _n in ast.walk(_pl):
        if isinstance(_n, ast.Constant) and isinstance(_n.value, str):
            _pl_strs.add(_n.value)
        elif isinstance(_n, ast.Name):
            _pl_names.add(_n.id)
check(u'E4 `_current_place_label` 走 `current_scene` + `_scene_place_label`'
      u'（两者都是 `getattr(..., \'名字\')` 里的**字符串字面量** ⇒ 必须扫常量；'
      u'只扫 `Call` 的名字会恒空）',
      _pl is not None and u'_scene_place_label' in _pl_strs
      and u'current_scene' in _pl_strs,
      u'strs=%r names=%r' % (sorted(_pl_strs), sorted(_pl_names)))

_rc = _func(MS_TREE, 'recall')
_has_inner = bool(_rc) and any(
    isinstance(n, ast.Constant) and n.value == 'inner' for n in ast.walk(_rc))
check(u'E5 `recall` 里有 `inner` 的专门匹配分支', _has_inner)

# ================================================================ F 自检
check(u'F2 分母闸：确有判据被执行', len(RESULTS) > 0, u'%d' % len(RESULTS))

_sha = hashlib.sha1((MS_SRC + DU_SRC + ES_SRC).encode('utf-8')).hexdigest()
check(u'F3 记下被测源码 sha1（换轮次后可比对到底改没改）', len(_sha) == 40,
      u'sha1=%s' % _sha[:16])

# ★ F1 必须放**最后**：它数的是"含它自己"的总条数。第一版写 `len+1` 却放在
#   F2/F3 之前 ⇒ 实测 26≠28（后面还有两条没跑）。这类"基数随位置漂移"的判据
#   与第160轮"别绑时相"同型。
check(u'F1 判据条数固定为 28（不随环境变）', len(RESULTS) + 1 == 28,
      u'当前=%d' % (len(RESULTS) + 1))

# ---------------------------------------------------------------- 汇总
_FAIL = [r for r in RESULTS if not r[0]]
print(u'')
print(u'合计：PASS=%d FAIL=%d  共 %d 条' % (len(RESULTS) - len(_FAIL), len(_FAIL),
                                          len(RESULTS)))
if _FAIL:
    print(u'【失败明细】')
    for _ok, _n, _d in _FAIL:
        print(u'  - %s  <- %s' % (_n, _d))

try:
    shutil.rmtree(_VAULT, ignore_errors=True)
except Exception:                                                 # noqa: BLE001
    pass

sys.exit(0 if not _FAIL else 1)
