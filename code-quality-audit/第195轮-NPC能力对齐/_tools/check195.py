# -*- coding: utf-8 -*-
r"""check195 —— NPC 一人一库（第195轮）。

用户口径：
  「ralsei 和其他人一样，是同级的那种，也就是现有 ralsei 的功能需要在所有人身上
   都能看到，但，也要根据具体情况来看」
  「表情动画也不能关啊，给每个npc都复制一套模版过去然后针对性的替换内容呗，
   但，记得兼顾性能要么来个5090都跑不动这程序的算力」

本套件只钉**记忆这一层**（第 1 批）。三个必须钉住的性质：

  ① **不串味** —— 每个 NPC 一个目录、一个 `memory.json`。
     为什么不能用"一个大库 + owner 字段"：`recall()` 的关键记忆匹配面是
     `text + ' ' + meta.where`，**不含 `who`** ⇒ Lancer 在教室盘算的事，
     问"教室"时 Ralsei 也会想起来。B1 是行为级判据（真的跑 recall）。
  ② **不继承本体旧记忆** —— `MemorySystem` 有个 `_legacy_file`，指向仓库里的
     `ralsei_pet/memory.json`（升级不失忆用）。NPC 的空库要是继承了它，
     每个人一开口就自带 Ralsei 的记忆 ⇒ 串味。B2 钉 `_legacy_file is None`。
  ③ **性能** —— 96 个人不能一人一个常驻实例。懒加载 + LRU 上限。
     C1~C4 钉"超上限就淘汰""淘汰最久没用的""淘汰后数据不丢（从盘上回来）"，
     外加 C4 负控制（上限调大就不淘汰，证明 C1 不是恒真）。

★ 零 Qt、零网络、零外部盘（库根用 `tempfile`）。
★ 判据之间**不共享可变夹具**（第194轮那个教训）：每个 B/C 判据各自新建 bank。
"""
import ast
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
PM_PY = os.path.join(MODS, 'people_memory.py')
MS_PY = os.path.join(MODS, 'memory_system.py')
DU_PY = os.path.join(MODS, 'dialogue_ui.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# ★ 记忆库隔离：必须在 import memory_system 之前设
_VAULT = tempfile.mkdtemp(prefix='pm195_')
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


def _str_consts(node):
    """函数体里出现的**字符串常量**（`getattr(x, '名字')` 那种扫 Call 扫不到）。"""
    out = set()
    if node is None:
        return out
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _has_guard(node, name):
    """函数体里有没有 `if <name>: ...` 这种守卫（**不是**"参数里有这个名字"）。"""
    if node is None:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.If):
            for t in ast.walk(n.test):
                if isinstance(t, ast.Name) and t.id == name:
                    return True
                if isinstance(t, ast.Attribute) and t.attr == name:
                    return True
    return False


def _attr_assigns(tree):
    """`self.X = ...` 里被赋值的 X 集合。"""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute):
                    out.add(t.attr)
    return out


PM_SRC = _read(PM_PY)
MS_SRC = _read(MS_PY)
DU_SRC = _read(DU_PY)
MAIN_SRC = _read(MAIN_PY)
PM_TREE = ast.parse(PM_SRC)
MS_TREE = ast.parse(MS_SRC)
DU_TREE = ast.parse(DU_SRC)
MAIN_TREE = ast.parse(MAIN_SRC)

import people_memory as PM                                      # noqa: E402

_roots = []


def _bank(max_loaded=PM.MAX_LOADED):
    d = tempfile.mkdtemp(prefix='pmbank_')
    _roots.append(d)
    return PM.PeopleMemoryBank(root=d, max_loaded=max_loaded)

# ================================================================ A 路径与 id
check(u'A1 合法 id 原样返回（不改名）',
      PM.PeopleMemoryBank.safe_id('lancer') == 'lancer'
      and PM.PeopleMemoryBank.safe_id('hy_ceroba_ketsukane') == 'hy_ceroba_ketsukane',
      repr(PM.PeopleMemoryBank.safe_id('lancer')))

_bad = [PM.PeopleMemoryBank.safe_id(x) for x in
        ('', None, '   ', '../etc', 'a/b', 'x\\y', '..')]
check(u'A2 ★ 负控制：非法 id 一律返回空串（**不许洗成另一个名字照用**）',
      all(b == '' for b in _bad), repr(_bad))

# 分母闸：上面这组里"合法样本"必须真能过，否则 A1/A2 一起恒真
check(u'A2b 分母闸：合法样本 3 个必须全过',
      sum(1 for x in ('lancer', 'susie', 'hy_ace')
          if PM.PeopleMemoryBank.safe_id(x) == x) == 3)

_bk = _bank()
check(u'A3 一人一目录（两个 id 不撞同一个目录）',
      _bk.dir_of('lancer') != _bk.dir_of('susie')
      and os.path.basename(_bk.dir_of('lancer')) == 'lancer',
      u'%s / %s' % (os.path.basename(_bk.dir_of('lancer')),
                    os.path.basename(_bk.dir_of('susie'))))

check(u'A4 `root=None` ⇒ 不伪造路径（返回 None）',
      PM.PeopleMemoryBank(root=None).dir_of('lancer') is None)

# ================================================================ B 隔离（行为级）
_b1 = _bank()
_a = _b1.of('lancer')
_b = _b1.of('susie')
_a.note_inner(u'盘算', who='lancer', where=u'教室')
_a.add_fragment(u'今天天气不错', who='lancer', kind='dialogue')
_b.note_inner(u'犹豫', who='susie', where=u'走廊')

_hit_a = [h for h in _a.recall(u'教室', limit=6, reinforce=False)
          if h.get('kind') == 'inner']
_hit_b = [h for h in _b.recall(u'教室', limit=6, reinforce=False)
          if h.get('kind') == 'inner']
check(u'B1 ★★★ 不串味：lancer 在教室记的事，susie 问"教室"想不起来',
      len(_hit_a) == 1 and len(_hit_b) == 0,
      u'lancer=%d susie=%d' % (len(_hit_a), len(_hit_b)))

# ★ B1 的负控制：同一个库自己写自己问必须命中，否则 B1 可能只是"根本不命中"
_self = [h for h in _a.recall(u'教室', limit=6, reinforce=False)
         if h.get('kind') == 'inner']
check(u'B2 ★ B1 的负控制：同库自写自问必须命中（证明不是"根本不命中"）',
      len(_self) == 1, u'hits=%d' % len(_self))

check(u'B3 ★★★ NPC 的库**不继承**本体旧记忆（`_legacy_file is None`）',
      getattr(_a, '_legacy_file', 'from-elsewhere') is None,
      repr(getattr(_a, '_legacy_file', 'from-elsewhere')))

import memory_system as _MSmod                                  # noqa: E402

# ★ B3b 是 B3 的负控制：**本体**那条路（不指定 memory_dir）必须仍然有 `_legacy_file`。
#   少了它，B3 的 `is None` 可能只是因为"这个属性根本不存在"而恒真。
_bare = _MSmod.MemorySystem(PM._NullParent())
check(u'B3b ★ B3 的负控制：本体那条路必须**仍有** `_legacy_file`（证明 B3 不是恒真）',
      getattr(_bare, '_legacy_file', None) is not None,
      u'legacy=%r' % (getattr(_bare, '_legacy_file', None),))

# ================================================================ C 性能（LRU）
_c1 = _bank(max_loaded=2)
_c1.of('a1').note_inner(u'盘算', who='a1', where=u'教室')   # 先留一条可验证的数据
_c1.of('a2')
_c1.of('a3')                                                 # 建第三个 ⇒ 淘汰 a1
_loaded = _c1.loaded_ids()
check(u'C1 ★ 超过上限就淘汰（同时驻留 ≤ max_loaded）',
      len(_loaded) <= 2 and _c1.stats['evicted'] >= 1,
      u'驻留=%r 淘汰=%d' % (_loaded, _c1.stats['evicted']))

check(u'C2 淘汰的是**最久没用**的（LRU，不是随便丢）',
      'a1' not in _loaded and 'a3' in _loaded, repr(_loaded))

_back_ms = _c1.of('a1')          # 重新取回（应从盘上重新加载）
_back = [k for k in _back_ms.keys if k.get('kind') == 'inner']
check(u'C3 ★ 淘汰后重新取，那条数据**还在**（淘汰 ≠ 丢数据）',
      len(_back) == 1, u'回读 inner=%d' % len(_back))

_c4 = _bank(max_loaded=10)
for _i in range(3):
    _c4.of('b%d' % _i)
check(u'C4 ★ 负控制：上限够大时**一个都不淘汰**（证明 C1 不是恒真）',
      len(_c4.loaded_ids()) == 3 and _c4.stats['evicted'] == 0,
      u'驻留=%d 淘汰=%d' % (len(_c4.loaded_ids()), _c4.stats['evicted']))

check(u'C5 懒加载：只 `of()` 过的人才有库，没碰过的不占内存',
      len(_c4.loaded_ids()) == 3 and 'never_touched' not in _c4.loaded_ids(),
      repr(_c4.loaded_ids()))

# ================================================================ D 接线（AST）
_npcline = _func(DU_TREE, 'add_npc_line')
check(u'D1 `add_npc_line` 真的调了 `_note_person_memory`（接线没断）',
      '_note_person_memory' in _calls(_npcline))

_npm = _func(DU_TREE, '_note_person_memory')
_c = _calls(_npm)
check(u'D2 ★ 取的是 `people_memory` 的库，**不是**本体那个 `memory_system`',
      'of' in _c and 'add_fragment' in _c and 'note_inner' in _c,
      repr(sorted(_c)))

check(u'D3 ★ 内在活动从 `acts`（sink 收集的括号）里也摘了一次'
      u'（NPC 主路径的括号已被护栏删出正文）',
      '_inner_verb' in _c and 'note_inner' in _c,
      u'调用=%r' % sorted(x for x in _c if 'inner' in x.lower()))

check(u'D4 ★ 只记有 `char_id` 的（有 `if char_id:` 守卫；没 id 就宁可记不住）',
      _has_guard(_npcline, 'char_id'),
      u'守卫=%r' % _has_guard(_npcline, 'char_id'))

check(u'D5 `main` 里真的**赋值**了 `self.people_memory`（不是只在注释里提一句）',
      'people_memory' in _attr_assigns(MAIN_TREE),
      u'赋值的属性数=%d' % len(_attr_assigns(MAIN_TREE)))

# ================================================================ E 兼容与自检
_init = _func(MS_TREE, '__init__')
_args = [a.arg for a in (_init.args.args if _init else [])]
_defaults = [d for d in (_init.args.defaults if _init else [])]
check(u'E1 ★ `MemorySystem.__init__` 新增 `memory_dir` 是**可选参数**'
      u'（默认 None ⇒ 老调用方行为一字不变）',
      'memory_dir' in _args and len(_defaults) >= 1
      and isinstance(_defaults[0], ast.Constant) and _defaults[0].value is None,
      u'args=%r 默认=%r' % (_args, [getattr(d, 'value', '?') for d in _defaults]))

check(u'E2 分母闸：确有判据被执行',
      len(RESULTS) > 0, u'%d' % len(RESULTS))
check(u'E3 判据名无重复（防复制粘贴漏改名）',
      len(set(n for _o, n, _d in RESULTS)) == len(RESULTS),
      u'共 %d 条' % len(RESULTS))
check(u'E4 记下被测源码 sha1（换轮次后可比对"到底改没改"）',
      bool(MS_SRC), u'memory_system.py sha1=%s' % __import__('hashlib').sha1(
          MS_SRC.encode('utf-8')).hexdigest()[:16])

for _d in _roots:
    shutil.rmtree(_d, ignore_errors=True)
shutil.rmtree(_VAULT, ignore_errors=True)

_n_fail = sum(1 for ok, _n, _d in RESULTS if not ok)
print("")
print(u"合计：PASS=%d FAIL=%d  共 %d 条"
      % (len(RESULTS) - _n_fail, _n_fail, len(RESULTS)))
if _n_fail:
    print(u"【失败明细】")
    for ok, n, d in RESULTS:
        if not ok:
            print(u"  - %s  <- %s" % (n, d))
raise SystemExit(1 if _n_fail else 0)
