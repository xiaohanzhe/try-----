# -*- coding: utf-8 -*-
u"""第113轮k回归锁：**特定事件 → 去哪儿**（NPC 听懂"咱吃饭去吧"并给出具体去处）。

用户口径（2026-10-26 逐字）
--------------------------
「我说的**特定事件**就是指，**吃饭，活动，休息，做任务**等，他能识别出来要去哪，
  并**给出建议**这样的，就像是人类之间问，咱吃饭去吧，别人会回答，
  **那要不去 XXX 家餐厅**？这样的话一样」

两件事必须分开（混成一张表会**因果倒置**）
------------------------------------------
  ① 从**话里**听出"要去干什么"  ⇒ `detect_activity`，**只认意图词**；
  ② 知道**哪儿真能干这事**      ⇒ `place_matches` / `activity_hint`，**只认地点词**。
混成一张表就会变成"因为人在餐厅，所以他在吃饭"，而人说话是"我想吃饭，所以去餐厅"。

本套件守什么
------------
A 抽取：产品那几个方法真的抽到了（抽不到后面全是假绿）。
B 听懂：四种活动的**意图词**；多个同时命中取**语序最先**的那个。
C `place_matches` **正负成对**：`town_school` 要命中 `school`（`_` 在正则里不是词首，
  必须先转空格）；而 `sparks` 不含 `park`、`graveyard` 不含 `yard`（子串误报）。
D 候选必须**能说出是哪一家**：`Hometown · Diner`，不是光秃秃的 `Hometown`。
  ★ 这条是第113轮k 端到端实测抓到的真错误 —— 第一版输出「真有的地方：家乡」，
    用户要的那个「XXX 家餐厅」没了。
  ★★ 第113轮l 起**全英文**（用户口径「名字用英文」「人名也要改成英文」）：
    中文类型名（`（餐厅）`）只在内部当**去重键**，不进 prompt。
E 负控制：无关的话不产块 · **调试区不算去处**（`ch5.system` 的三个测试房）·
  ★ 第113轮l 起「判不出章」**不再阻塞**（用户口径「可以跨区域哦」）——
    它只影响"同章优先"和引导语（`activity_hint(cross=)`）。
F 翻译表**不越权**：`station`/`dock` 猜不准就**不翻**（`Research Station` 不是火车站）。
  ★ 翻译表现在**不进 prompt**，只供去重键用 —— 但规则本身照旧要守。
G 名字整形：去房号、去行首单字母、截到类型词为止 —— 三条都**正负成对**。
H **全量普查**：所有章 × 四种活动，标签非空、零内部标记、零章括注、零中文。
K 英文地名 / 口语化 / 跨区域（第113轮l）：`speakable_en` 四条规则、所有格
  **正负成对**、容器区 `rooms`（`Rooms · Shop` 是内部结构泄漏）、中文人名换英文。
I AST 接线：`heard` 真的从 `chat_with_ai` 一路传到 `_npc_life_blocks`，且**有闸**
  （`if heard:` 才产块）—— 这条错了就是给所有 NPC 无条件加行、等于改人设。
J 方法级端到端（抽产品 `_npc_life_blocks` 整段挂桩跑）。

稳定性（G2 要逐字节比对）
------------------------
★ **不打印随数据规模变化的绝对数**（场景数 / NPC 数 / 候选数会随素材新增而变
  ⇒ 假 DIFF），只打布尔、失败条数和**写死的样本 sid**；判据用**不变量**
  （"同一个区里不许有两家同类型的店"），不冻结数据（"ch1 必须有 3 条"）。

零网络、零 Qt、零 E 盘依赖。
"""
import ast
import io
import json
import logging
import os
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
IDX = os.path.join(PET, 'assets', 'scenes', '_index.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                        # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


# ================================================================ 抽取工具
_SRC = io.open(MAIN, encoding='utf-8', newline='').read()
_TREE = ast.parse(_SRC)


def _method_src(src, tree, name):
    """从 `main.py` 取出类方法源码（dedent 后可直接 exec）。找不到返 None。"""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn))
    return None


def _method_node(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return fn
    return None


def _calls(fn, attr):
    """方法体里**真的调用**了 `xxx.attr(...)` 的 Call 节点（AST，不扫字符串）。"""
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == attr:
            out.append(n)
    return out


def _kw_calls(tree, funcname, kw):
    """全文件里 `funcname(..., kw=...)` 的调用（用来判 heard 有没有真传下去）。"""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = getattr(f, 'attr', None) or getattr(f, 'id', None)
        if name != funcname:
            continue
        if any(k.arg == kw for k in n.keywords):
            out.append(n)
    return out


METHODS = ('_scene_place_label', '_activity_label', '_activity_chapter',
           '_activity_places', '_npc_life_blocks',
           '_place_proper', '_place_names_en')
_NS = {'npc_life_mod': L, '_log': logging.getLogger('check113k')}
_MISSING = []
for _n in METHODS:
    _code = _method_src(_SRC, _TREE, _n)
    if not _code:
        _MISSING.append(_n)
        continue
    exec(compile(_code, '<%s>' % _n, 'exec'), _NS)

# 索引表（与产品 `_scene_label_map` 同构：5 元组）
_IDXMAP = {}
try:
    _idx = json.loads(io.open(IDX, encoding='utf-8').read())
    for _cid, _ch in (_idx.get('chapters') or {}).items():
        for _aid, _ar in ((_ch or {}).get('areas') or {}).items():
            for _sid, _sc in ((_ar or {}).get('scenes') or {}).items():
                _sc = _sc or {}
                _IDXMAP[str(_sid)] = (
                    str(_ch.get('name') or ''), str(_ar.get('name') or ''),
                    str(_sc.get('name') or ''), bool(_sc.get('name_derived')),
                    str(_sc.get('name_raw') or ''))
except Exception as e:                                      # pragma: no cover
    print('[FAIL] 场景索引读不到：%s' % e)
    sys.exit(1)


class _Place(object):
    def __init__(self, home):
        self._home = home

    def home_of(self, npc_id):
        return self._home


#: 桩用的人名集合 / 中文→英文映射。
#: ★ 只放**判定需要**的几个，不抄全表 —— 这里测的是"有没有按人名加 `'s`"和
#:   "中文人名有没有被换掉"，不是测 registry 内容。
_PROPER = frozenset(('asgore', 'toriel', 'susie', 'kris', 'ralsei', 'clover',
                     'martlet', 'ceroba'))
_NAMES_EN = {'托丽尔': 'Toriel', '艾斯戈尔': 'Asgore', '苏西': 'Susie'}


class _Stub(object):
    """桩：只提供产品代码真正用到的那几个出口。

    ★ 凡是被测方法会回调的，一律**转发到产品方法**：
      自己实现 = 测的是复刻版；不实现 = AttributeError 被 `except` 吞掉 ⇒ 静默不产块（假红）。
    """
    npc_life_mod = L
    npc_bonds = None

    def __init__(self, sid=None, home=None):
        self._sid = sid
        self.npc_placement = _Place(home)

    def _scene_label_map(self):
        return _IDXMAP

    def _place_proper(self):
        return _PROPER

    def _place_names_en(self):
        return _NAMES_EN

    def _scene_place_label(self, sid, with_chapter=True):
        return _NS['_scene_place_label'](self, sid, with_chapter=with_chapter)

    def _activity_label(self, sid, core, hits):
        return _NS['_activity_label'](self, sid, core, hits)

    def _activity_chapter(self, npc_id):
        return _NS['_activity_chapter'](self, npc_id)

    def _activity_places(self, kind, chapter):
        return _NS['_activity_places'](self, kind, chapter)

    def _npc_scene_id(self):
        return self._sid

    def _npc_scene_text(self):
        return ''

    def _npc_life_ids(self):
        return []

    def _npc_relative_positions(self, *a, **k):
        return {}

    def _npc_display_label(self, nid):
        return ''


def _blocks(stub, heard=None):
    return _NS['_npc_life_blocks'](stub, 'ralsei', heard=heard)


def _places(stub, kind, chap):
    return stub._activity_places(kind, chap)


# ================================================================ A 抽取
print('--- A 抽取与结构 ---')
_STDLIB = ('collections', 're', 'math', 'random', 'time', 'json', 'os',
           'itertools', 'functools', 'typing', 'dataclasses')
_LIFE_SRC = io.open(os.path.join(PET, 'modules', 'npc_life.py'),
                    encoding='utf-8').read()
_LIFE_IMPORTS = []
for _n in ast.parse(_LIFE_SRC).body:
    if isinstance(_n, ast.Import):
        _LIFE_IMPORTS.extend(a.name for a in _n.names)
    elif isinstance(_n, ast.ImportFrom) and _n.level == 0:
        _LIFE_IMPORTS.append(_n.module or '')
check('A0 五个产品方法都抽到了（缺一个后面全是假绿）', not _MISSING,
      '缺=%r' % (_MISSING,))
if _MISSING:
    print()
    print('=' * 74)
    print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
    print('=' * 74)
    sys.exit(1)

check('A1 策略层是零依赖的：`npc_life` 顶层只 import 标准库',
      all(m.split('.')[0] in _STDLIB for m in _LIFE_IMPORTS),
      repr(sorted(set(m for m in _LIFE_IMPORTS if m.split('.')[0] not in _STDLIB))))

# ================================================================ B 听懂
print()
print('--- B 听懂「要去干什么」（只认意图词）---')
_CASES = (('咱吃饭去吧', 'eat'), ('我有点累了，歇会儿吧', 'rest'),
          ('出去逛逛？', 'play'), ('去买点东西', 'work'))
for _line, _want in _CASES:
    _got = L.detect_activity(_line)
    check('B `%s` ⇒ %s' % (_line, _want), _got[0] == _want, '实测 %r' % (_got,))

check('B5 多个活动同时命中 ⇒ 取**语序最先**的（`吃完饭去逛逛` 先吃饭）',
      L.detect_activity('吃完饭去逛逛')[0] == 'eat',
      repr(L.detect_activity('吃完饭去逛逛')))
check('B6 负控制：空串 / None ⇒ (None, \'\')，**不猜**',
      L.detect_activity('') == (None, '') and L.detect_activity(None) == (None, ''))
check('B7 负控制：`今天天气不错` ⇒ 认不出（不许硬塞一个活动）',
      L.detect_activity('今天天气不错')[0] is None,
      repr(L.detect_activity('今天天气不错')))
# ★★ 否定：`我不饿` 里那个 `饿` 会让 NPC 立刻推荐餐厅 —— 用户刚说吃饱，
#    桌宠还劝他吃饭，这是"不像人"的典型（第113轮k 自查发现）。
check('B8 ★★ 否定要认：`我不饿` ⇒ 认不出', L.detect_activity('我不饿')[0] is None,
      repr(L.detect_activity('我不饿')))
check('B8b 正控制：`我饿了` ⇒ eat（证明 B8 不是恒真）',
      L.detect_activity('我饿了')[0] == 'eat')
check('B8c 否定两型：`没吃饭呢` / `别玩了` ⇒ 都认不出',
      L.detect_activity('没吃饭呢')[0] is None
      and L.detect_activity('别玩了')[0] is None)
# ★ 断句符：否定不跨句。命中的**词**也要对 —— 光判 kind 会漏（`逛` 也是 play）。
check('B9 否定**不跨句**：`我不累，出去逛逛` ⇒ play 且命中的是 `出去`',
      L.detect_activity('我不累，出去逛逛') == ('play', '出去'),
      repr(L.detect_activity('我不累，出去逛逛')))

# ================================================================ C 地点匹配
print()
print('--- C `place_matches` 正负成对 ---')
check('C1 正控制：`town_school` 命中 `school`（`_` 在正则里不是词首，必须先转空格）',
      L.place_matches('town school', 'work') == ['school'],
      repr(L.place_matches('town school', 'work')))
check('C2 正控制：`diner` 命中 `eat`',
      'diner' in L.place_matches('diner', 'eat'))
for _bad, _kind, _tok in (('sparks', 'play', 'park'),
                          ('graveyard', 'play', 'yard'),
                          ('poolsroom', 'play', 'pool')):
    check('C3 负控制：`%s` **不许**命中 `%s`（子串误报）' % (_bad, _tok),
          _tok not in L.place_matches(_bad, _kind),
          repr(L.place_matches(_bad, _kind)))
check('C4 正控制：函数**照字面判**（`garden` 命中 play）—— 剥区段名是调用方的责任',
      L.place_matches('garden', 'play') == ['garden'],
      repr(L.place_matches('garden', 'play')))
check('C5 负控制：空文本 / None ⇒ `[]`（不猜、不抛）',
      L.place_matches('', 'play') == [] and L.place_matches(None, 'eat') == [])
check('C6 负控制：不认识的活动类型 ⇒ `[]`（不是异常）',
      L.place_matches('diner', 'sleep') == [])

# ================================================================ D 候选质量
print()
print('--- D 候选要能说出**是哪一家** ---')
_st = _Stub('ch1.hometown.town_square')
_eat = _places(_st, 'eat', 'ch1')
_eat_lbl = [lbl for _s, lbl in _eat]
check('D1 ch1 吃饭候选**点名到店**（不是一个光秃秃的区名）',
      bool(_eat_lbl) and all(lbl != 'Hometown' for lbl in _eat_lbl),
      '%r' % (_eat_lbl[:3],))
check('D2 候选**零中文**（口径「名字用英文」「人名也要改成英文」）',
      bool(_eat_lbl) and not any(L.has_cjk(lbl) for lbl in _eat_lbl),
      '%r' % ([l for l in _eat_lbl if L.has_cjk(l)][:2],))
check('D2b 候选是**首字母大写**的地名（不是全小写 id 形态 `diner`）',
      bool(_eat_lbl)
      and all(lbl.split(L.PLACE_SEP)[-1][:1].isupper() for lbl in _eat_lbl),
      '%r' % (_eat_lbl[:3],))
check('D3 候选**不带章括注**（四项各带一遍「（第一章…）」纯属噪音）',
      all('（第' not in lbl for lbl in _eat_lbl), '%r' % (_eat_lbl[:3],))
_work = _places(_st, 'work', 'ch1')
_work_lbl = [lbl for _s, lbl in _work]
# ★ 断行为：`activity_hint` 拿到**重复的名字**时只能列一次。
#   （不直接数 `_work`，因为跨区域后 `ch1` 与 `ch2` 的 `Hometown · Hospital`
#   是两家店、两个去重键 —— 候选里两条都在，是 hint 那一层合并的。）
_dup = [('ch1.hometown.hospital_lobby', 'Hometown · Hospital'),
        ('ch1.hometown.hospital_hallway', 'Hometown · Hospital'),
        ('ch1.hometown.library', 'Hometown · Library')]
_dup_out = L.activity_hint('work', _dup)
check('D4 去重不变量：同一个名字**只列一次**（走廊/大厅合成一条）',
      _dup_out.count('Hometown · Hospital') == 1, repr(_dup_out))
check('D5 去重**不许过度**：不同类别必须都留着（医院 ≠ 图书馆）',
      'Hometown · Library' in _dup_out and 'Hometown · Hospital' in _dup_out,
      repr(_dup_out))
# 正/负成对：`with_chapter` 开关必须真的有效，且默认值不许动 113j 的位置块
_lbl_def = _st._scene_place_label('ch1.hometown.diner')
_lbl_no = _st._scene_place_label('ch1.hometown.diner', with_chapter=False)
check('D6 `with_chapter` 默认 True ⇒ 位置块**逐字不变**（113j 契约）',
      ('（第一章' in _lbl_def) and ('（第一章' not in _lbl_no),
      '默认=%r / 关掉=%r' % (_lbl_def, _lbl_no))

# ================================================================ E 负控制
print()
print('--- E 负控制：不该说话时**闭嘴** ---')
check('E1 `heard=None` ⇒ 不产活动块（这条 prompt 每个 NPC 每次都用！）',
      '【这会儿能张罗的事】' not in _blocks(_st))
check('E2 无关的话（`今天天气不错`）⇒ 不产块',
      '【这会儿能张罗的事】' not in _blocks(_st, heard='今天天气不错'))
_st_noch = _Stub(None, None)
check('E3 判不出章 ⇒ `_activity_chapter` 返空串', _st_noch._activity_chapter('ralsei') == '')
_e4 = _blocks(_st_noch, heard='咱吃饭去吧')
check('E4 判不出章**不再阻塞**（跨区域）：照样能张罗，但要说清"有的在别处"',
      ('【这会儿能张罗的事】' in _e4) and ('有的不在你这一带' in _e4),
      repr([x for x in _e4.split('\n') if '这会儿能张罗' in x][:1]))
_dbg = []
for _k in L.ACTIVITY_KINDS:
    for _sid, _lbl in _places(_st, _k, 'ch5'):
        if _sid.split('.')[1] in L.PLACE_SKIP_AREA_IDS or '系统与演出' in _lbl:
            _dbg.append((_k, _sid))
check('E5 调试区（`ch5.system` 三个测试房）**不算去处**', not _dbg, '%r' % (_dbg[:3],))
check('E5b 负控制：ch5 **自己的地方**还在（证明 E5 不是把整章砍了）',
      any(_s.startswith('ch5.') for _k in L.ACTIVITY_KINDS
          for _s, _lbl in _places(_st, _k, 'ch5')))

# ================================================================ F 翻译表
print()
print('--- F 翻译表**不越权**（猜不准就不翻）---')
check('F1 `station` / `dock` 退出翻译表（`Research Station` 不是火车站）',
      L.place_type_name('station') == 'station'
      and L.place_type_name('dock') == 'dock',
      'station=%r dock=%r' % (L.place_type_name('station'),
                              L.place_type_name('dock')))
check('F1b 负控制：`diner`/`cafe` 仍翻（证明翻译函数没整体坏掉，F1 不是恒真）',
      L.place_type_name('diner') == '餐厅' and L.place_type_name('cafe') == '咖啡店')
check('F2 中文词**原样返回**（`理想餐厅` 不许被再翻成 `理想餐厅（餐厅）`）',
      L.place_type_name('餐') == '餐',
      repr(L.place_type_name('餐')))

# ================================================================ G 名字整形
print()
print('--- G 名字整形：三条都正负成对 ---')
check('G1 去房号：`couch overworld 01` ⇒ `couch overworld`',
      L.strip_room_index('couch overworld 01') == 'couch overworld',
      repr(L.strip_room_index('couch overworld 01')))
check('G1b 负控制：`tundra inn 2f` 的 `2f` 有意义，**不许**剥',
      L.strip_room_index('tundra inn 2f') == 'tundra inn 2f',
      repr(L.strip_room_index('tundra inn 2f')))
check('G2 去行首单字母（Outertale 的区名缩写）：`c asgore kitchen` ⇒ `asgore kitchen`',
      L.strip_room_index('c asgore kitchen') == 'asgore kitchen',
      repr(L.strip_room_index('c asgore kitchen')))
check('G2b 负控制：`House 1 - stew` **不许**被拆（`1` 不在行首）',
      L.strip_room_index('House 1 - stew') == 'House 1 - stew',
      repr(L.strip_room_index('House 1 - stew')))
check('G3 截到类型词为止：`hospital hallway` ⇒ `hospital`（走廊不是"去处"）',
      L.trim_core_at_type('hospital hallway', ['hospital']) == 'hospital',
      repr(L.trim_core_at_type('hospital hallway', ['hospital'])))
check('G3b 正控制：`icee pizza` 的 `icee` 是**店名前半截**，必须留着',
      L.trim_core_at_type('icee pizza', ['pizza']) == 'icee pizza',
      repr(L.trim_core_at_type('icee pizza', ['pizza'])))
check('G3c 负控制：命中不到类型词 ⇒ **原样返回**，不猜',
      L.trim_core_at_type('plat lab', ['diner']) == 'plat lab',
      repr(L.trim_core_at_type('plat lab', ['diner'])))

# ================================================================ H 全量
print()
print('--- H 全量普查（所有章 × 四种活动）---')
_chaps = sorted({s.split('.')[0] for s in _IDXMAP})
#: 裸的**通用类型词**：只有"这是一家餐厅"、看不出在哪儿的标签。
#: ★ 为什么不是"所有不带 ` · ` 的都算裸"：`Flower Castle` / `Green Room` / `Core`
#:   本身就是完整地名（区名 == 场景名时 `_scene_place_label` 只留一个），
#:   不带分隔符也说得出在哪儿。第113轮l 实测：按"必须含分隔符"判会误伤它们。
_BARE_TYPES = {v.lower() for v in L.PLACE_GLOSS.values()} | set(L.PLACE_GLOSS)
_bad = []
_empt = []
_noloc = []
for _c in _chaps:
    for _k in L.ACTIVITY_KINDS:
        for _sid, _lbl in _places(_st, _k, _c):
            if not _lbl:
                _empt.append((_c, _k, _sid))
                continue
            # ★ 跨区域是**要的**（用户口径「可以跨区域哦」）⇒ 不再判"跨章=错"，
            #   改判"跨章不许只给一个通用类型词"：`Diner` 在 10 个世界里都有。
            if not _sid.startswith(_c + '.') and _lbl.strip().lower() in _BARE_TYPES:
                _noloc.append((_c, _k, _sid, _lbl))
            for _tok in ('（第', 'rm ', 'dw ', 'lw ', 'room_', 'Rooms',
                         '全部房间', '未分区', 'None', '（餐厅', '（商店'):
                if _tok in _lbl:
                    _bad.append((_c, _k, _sid, _tok))
check('H1 零空标签', not _empt, '%r' % (_empt[:3],))
check('H2 跨区域**不许出现裸的通用类型词**（`Diner` / `Shop` 看不出在哪个世界）',
      not _noloc, '%r' % (_noloc[:3],))
check('H2b 正控制：无区名时 `place_label` **确实**只给裸名（证明 H2 有牙）',
      L.place_label('', '', 'diner', ['diner']).strip().lower() in _BARE_TYPES,
      repr(L.place_label('', '', 'diner', ['diner'])))
check('H3 零内部标记 / 零容器名 / 零章括注 / 零中文类型括注', not _bad,
      '%r' % (_bad[:3],))
check('H4 四种活动在 ch1 **都**有候选（跨区域后不该再出现"一种都没有"）',
      all(_places(_st, _k, 'ch1') for _k in L.ACTIVITY_KINDS))
# ★ 断行为：候选里**不许有同名项**。跨章同名店（`ch1`/`ch2`/`ch3` 的
#   `hometown.diner`）是同一家店的不同章节版本，留着会占满 `limit=4` 的名额，
#   模型看到两个 `Hometown · Diner` 只会犹豫。
_duplbl = []
for _k in L.ACTIVITY_KINDS:
    _ls = [_l for _s, _l in _places(_st, _k, 'ch1')]
    if len(set(_ls)) != len(_ls):
        _duplbl.append(_k)
check('H5 同一种活动里**同一个名字只出现一次**（跨章同名店合成一条）',
      not _duplbl, '%r' % (_duplbl,))

# ================================================================ I AST 接线
print()
print('--- I AST 接线（`heard` 必须真传下来，且**有闸**）---')
_fn_blocks = _method_node(_TREE, '_npc_life_blocks')
_fn_sys = _method_node(_TREE, 'npc_system_prompt')
check('I1 `_npc_life_blocks` 里**真的调用** `detect_activity`',
      bool(_calls(_fn_blocks, 'detect_activity')))
check('I2 `_npc_life_blocks` 里**真的调用** `_activity_places` / `activity_hint`',
      bool(_calls(_fn_blocks, '_activity_places'))
      and bool(_calls(_fn_blocks, 'activity_hint')))
_guarded = False
for _n in ast.walk(_fn_blocks):
    if isinstance(_n, ast.If) and isinstance(_n.test, ast.Name) \
            and _n.test.id == 'heard':
        _guarded = True
        break
check('I3 活动段**有闸**（`if heard:` 才产块）—— 没闸就是给所有 NPC 无条件加行',
      _guarded)
check('I4 `npc_system_prompt` 把 `heard` 传给 `_npc_life_blocks`',
      any(k.arg == 'heard' for c in _calls(_fn_sys, '_npc_life_blocks')
          for k in c.keywords))
check('I5 `chat_with_ai` 真把**对方那句话**传进去（全文件至少一处 `... heard=text`）',
      bool(_kw_calls(_TREE, 'npc_system_prompt', 'heard')))
_fn_lbl = _method_node(_TREE, '_activity_label')
check('I6 `_activity_label` 真的走 `place_label`（不是自己拼字符串）',
      bool(_calls(_fn_lbl, 'place_label')))
_fn_pl = _method_node(_TREE, '_activity_places')
# ★ 用 AST 判"真的拿 PLACE_SKIP_AREA_IDS 做了成员判断"，不扫字符串 ——
#   文本扫会被一句解释它为什么存在的注释打绿（本项目已连踩多次的坑）。
_skip_gate = False
for _n in ast.walk(_fn_pl):
    if isinstance(_n, ast.Compare) and any(isinstance(op, ast.In) for op in _n.ops):
        if any(getattr(_c, 'attr', None) == 'PLACE_SKIP_AREA_IDS'
               for _c in ast.walk(_n)):
            _skip_gate = True
            break
check('I7 `_activity_places` 真的调 `_activity_label`，且**真拿** `PLACE_SKIP_AREA_IDS` 做成员判断',
      bool(_calls(_fn_pl, '_activity_label')) and _skip_gate)

# ================================================================ J 端到端
print()
print('--- J 方法级端到端（抽产品整段挂桩跑）---')
for _line, _want in _CASES:
    _out = _blocks(_st, heard=_line)
    _has = '【这会儿能张罗的事】' in _out
    check('J `%s` ⇒ 产块' % _line, _has,
          repr([x for x in _out.split('\n') if '这会儿能张罗' in x][:1]))
    if _has:
        _names_txt = _out.split('：')[-1].split('。')[0]
        check('J `%s` ⇒ 点名到具体地方（含 ` · `）且**零中文**' % _line,
              (' · ' in _names_txt) and not L.has_cjk(_names_txt),
              repr(_names_txt))
# ★ 断**机制**不绑数据：同一批地方，`cross` 开关必须真的换引导语。
#   （不判"ch1 的块里一定有某句话" —— 那会随素材增减而红，是绑数据。）
_same = [('ch1.hometown.a', 'Hometown · Diner'),
         ('ch1.hometown.b', 'Hometown · Cafe')]
_mixed = _same + [('ch2.cyber_city.c', 'Cyber City · Pizza')]
check('J5 `cross` 开关**真的**改文案（同章说"真有的地方"，混章说"有的在别处"）',
      ('真有的地方' in L.activity_hint('eat', _same, cross=False))
      and ('有的不在你这一带' in L.activity_hint('eat', _mixed, cross=True))
      and L.activity_hint('eat', _same, cross=False)
      != L.activity_hint('eat', _mixed, cross=True))
check('J5b 负控制：不传 `cross` 时**不许**冒出"有的不在你这一带"（默认仍是同章口径）',
      '有的不在你这一带' not in L.activity_hint('eat', _same))
check('J6 两种文案都明确"别照着念"（固定例句被逐字搬走 = 人设失真头号来源）',
      ('别照着念' in L.activity_hint('eat', _same))
      and ('别照着念' in L.activity_hint('eat', _mixed, cross=True)))

# ================================================================ K 英文 / 口语化 / 跨区域
print()
print('--- K 英文地名 · 口语化 · 跨区域（第113轮l 用户口径）---')
check('K1 口语化：`castle cafe` ⇒ `Castle Cafe`（逐词 Title Case）',
      L.speakable_en('castle cafe') == 'Castle Cafe',
      repr(L.speakable_en('castle cafe')))
check('K2 所有格：**人名词** + 地点词 ⇒ `Asgore\'s Kitchen`',
      L.speakable_en('asgore kitchen', _PROPER) == "Asgore's Kitchen",
      repr(L.speakable_en('asgore kitchen', _PROPER)))
check('K2b 负控制：`castle` 不在人名表 ⇒ **不许**加 `\'s`（会编出不存在的店）',
      L.speakable_en('castle cafe', _PROPER) == 'Castle Cafe',
      repr(L.speakable_en('castle cafe', _PROPER)))
check('K3 楼层缩写说成人话：`tundra inn 2f` ⇒ `Tundra Inn Second Floor`',
      L.speakable_en('tundra inn 2f') == 'Tundra Inn Second Floor',
      repr(L.speakable_en('tundra inn 2f')))
check('K4 虚词不大写：`hall of fame` ⇒ `Hall of Fame`',
      L.speakable_en('hall of fame') == 'Hall of Fame',
      repr(L.speakable_en('hall of fame')))
check('K5 中文人名换英文：`托丽尔的房子` ⇒ `Toriel的房子`',
      L.de_cjk_names('托丽尔的房子', _NAMES_EN) == 'Toriel的房子',
      repr(L.de_cjk_names('托丽尔的房子', _NAMES_EN)))
check('K5b 负控制：没有映射 ⇒ **原样返回**（不许瞎翻任何中文）',
      L.de_cjk_names('托丽尔的房子') == '托丽尔的房子')
check('K6 容器区 `rooms` 不许当地名（`ut.rooms.*` ⇒ 作品缩写，不是 `Rooms · X`）',
      not [1 for _k in L.ACTIVITY_KINDS for _s, _l in _places(_st, _k, 'ut')
           if _l.startswith('Rooms')])
check('K6b 负控制：`ut.rooms.*` 的候选**还在**（缩写替换不是把整区砍了）',
      any(_s.startswith('ut.rooms.') for _k in L.ACTIVITY_KINDS
          for _s, _l in _places(_st, _k, 'ut')))
check('K7 真跨区域了（ch1 的 play 候选里**必须有**非 ch1 的）',
      any(not _s.startswith('ch1.') for _s, _l in _places(_st, 'play', 'ch1')))
check('K8 跨区域**同章排前面**（有同章的就必须排第一）',
      all(_places(_st, _k, 'ch1')[0][0].startswith('ch1.')
          for _k in L.ACTIVITY_KINDS
          if any(_s.startswith('ch1.') for _s, _l in _places(_st, _k, 'ch1'))))
_all_lbl = [_l for _c in _chaps for _k in L.ACTIVITY_KINDS
            for _s, _l in _places(_st, _k, _c)]
check('K9 全量普查里**零中文地名**（含人名）',
      bool(_all_lbl) and not any(L.has_cjk(_l) for _l in _all_lbl),
      '%r' % ([_l for _l in _all_lbl if L.has_cjk(_l)][:3],))

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
