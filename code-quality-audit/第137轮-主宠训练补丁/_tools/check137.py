# -*- coding: utf-8 -*-
"""第137轮回归锁：`patches["ralsei"]` **真的**进主宠 system。

## 病是什么

训练卡（第113轮）为**全部 96 位**角色各产出了一条 `patch`（实测出过的毛病对应的纠正句）。
NPC 那边 `npc_persona.build_system_prompt()` 早就把它拼进 system 了；只有主宠 Ralsei
走的是 `chat_with_ai(speaker='ralsei')` 的老路径：

    system = self._build_persona_prompt()      # 只读 persona 文件

⇒ `patches["ralsei"]`（160 字）**零读取**。第134轮把这条当"真缺口"登记下来，本轮接上。

## 这条 patch 到底补了什么（人设里有没有）

三句：
  ① 一次最多两三句，短一点 —— 人设「我怎么说」已有「一次只说 1~3 句」，**语义重复**；
  ② 只认得原作里真有的名字：Kris / Susie / Lancer / Toriel / Asgore / Asriel / Noelle / Berdly；
  ③ 不要自己造人名（「凯斯恩」这种把两个名字拼起来的说法），拿不准就称「你」「他」「她」。

② ③ 在人设正文里**一个字都没有** —— `第134轮` 已核过：`造人名`/`凯斯恩`/`拿不准` 全不出现。
本条是真实观测到的出戏（模型把两个名字拼成一个新名字），不是"我觉得该加"。

## 接在哪（为什么不是并进 persona 文件）

`_build_persona_prompt()` 的契约是"读到的就是 persona 文件**全文**"
（`persona_chat B8`：`stub._build_persona_prompt().strip() == PERSONA.strip()`）。
本块是**训练产出的增量**、来源不同（`_training/_index.json`），混进去以后
就说不清"这句到底是有证据的纠正，还是原始设定"——那正是 `training_patch`
与 `relation_patch` 分家的同一条理由。

## 本套件守什么

A 数据面：`patches["ralsei"]` 在、非空、三条要求都在（分母非空）
B 人设面：② ③ 确实**不在** persona 里（否则这轮的"补缺口"就是自欺）
C 行为面：`_with_ralsei_patch()` 拼出来的串 = persona 原文 + 尾块；空/非字符串不抛
  **破坏性负控制**：把 `training_patch` 打成返回 `''` ⇒ C1 必须报红（块真没了）
D 接线（AST）：`chat_with_ai` 与 `_prewarm_ai_cache` **各一处**、都排在
  `_build_persona_prompt()` **之后**（预热必须同源，否则那 160 字每轮重 prefill）
E 契约不破：`_build_persona_prompt()` 仍返回 persona 全文（`persona_chat B8` 那条）
F 自检

★ 零网络；Qt 用 offscreen（本套件会 `import main`，而 main 顶部 import 了 PyQt5）。
"""
import ast
import io
import json
import os
import sys
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
PERSONA_PY = os.path.join(PET, 'assets', 'ralsei_persona.md')
INDEX_JSON = os.path.join(PET, 'assets', 'npc', '_training', '_index.json')

sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))
import main as M                                                # noqa: E402

# ★★ 只能取 `M.npc_persona_mod`，**不许**再 `import npc_persona`：
#   `main.py` 里是 `from modules import npc_persona as npc_persona_mod`，
#   而 `modules/` 是个包。若这里再 `import npc_persona`（把 `modules` 塞进 sys.path），
#   Python 会**再造一个模块实例**（连 `_PATCH_CACHE` 都是两份）⇒ 打桩打不到产品那份，
#   负控制就会假绿。第一版就是这么写的，C6 当场报红。
NP = M.npc_persona_mod

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


_src_main = _read(MAIN_PY)
_t_main = ast.parse(_src_main)
persona = _read(PERSONA_PY)
_idx = json.loads(_read(INDEX_JSON))
patches = _idx.get('patches') or {}
patch = (patches.get('ralsei') or '').strip()

# =============================================== A 数据面
head(u'A. 数据面：`patches["ralsei"]` 在、非空、三条要求都在')

check(u'A0 分母非空：`_index.json` 的 patches 里有 ralsei', bool(patch),
      u'共 %d 条 patch，ralsei %d 字' % (len(patches), len(patch)))
check(u'A1 ① 要求"一次最多两三句"在位', u'两三句' in patch)
check(u'A2 ② 要求"只认得原作里真有的名字"在位', u'只认得原作里真有的名字' in patch)
check(u'A3 ③ 要求"不要自己造人名"在位', u'不要自己造人名' in patch)
check(u'A4 ③ 带上了实测例「凯斯恩」（不是一句空泛的"别编"）', u'凯斯恩' in patch)

# =============================================== B 人设面
head(u'B. 人设面：② ③ 确实**不在** persona 里（否则这轮是自欺）')

_B0 = u'造人名' not in persona
_B1 = u'凯斯恩' not in persona
_B2 = u'只认得原作里真有的名字' not in persona
check(u'B0 persona 正文里没有「造人名」这条要求', _B0)
check(u'B1 persona 正文里没有实测例「凯斯恩」', _B1)
check(u'B2 persona 正文里没有名字白名单那句', _B2)
check(u'B3 ★ 三条同时成立才算"真缺口"（缺一条就说明这轮补的是重复内容）',
      _B0 and _B1 and _B2)
# ★ ①「两三句」**故意不断**：persona「我怎么说」已有"一次只说 1~3 句"，
#   这条是语义重复（冗余但无害）。判据只断"确实没有"的那两条。

# =============================================== C 行为面
head(u'C. 行为面：`_with_ralsei_patch()` 拼出来的串')

_HEADER = M.PATCH_HEADER_RALSEI
_out = M._with_ralsei_patch(persona)

check(u'C0 `_with_ralsei_patch` 是模块级函数（桩上可直调，不需要 Qt 宿主）',
      callable(getattr(M, '_with_ralsei_patch', None)))
check(u'C1 输出以 persona 原文开头（正文一字未改）', _out.startswith(persona.rstrip()),
      u'len=%d' % len(_out))
check(u'C2 patch 逐字在输出里', patch in _out)
check(u'C3 尾块标题是第一人称「我」（不是 NPC 那句"这个角色"）',
      _HEADER in _out and u'这个角色' not in _out, u'%r' % _HEADER)
check(u'C4 patch 排在 persona **之后**（不许压在人设前面）',
      _out.find(patch) > len(persona.rstrip()) - 1,
      u'patch@%d persona_len=%d' % (_out.find(patch), len(persona.rstrip())))
check(u'C5 空串 / None 不抛（防御面）',
      isinstance(M._with_ralsei_patch(u''), str)
      and isinstance(M._with_ralsei_patch(None), str))

# ★ 破坏性负控制：让训练纠正返回空 ⇒ 尾块必须**整个消失**
check(u'C8 打桩打的正是产品用的那个模块实例（不是第二份 `npc_persona`）',
      NP is M.npc_persona_mod)
_orig_tp = NP.training_patch
try:
    NP.training_patch = lambda *_a, **_k: u''
    _dry = M._with_ralsei_patch(persona)
finally:
    NP.training_patch = _orig_tp
check(u'C6 负控制：`training_patch` 返回空时，尾块必须整个消失（不是拼个空标题）',
      patch not in _dry and _HEADER not in _dry,
      u'len %d → %d' % (len(_out), len(_dry)))
check(u'C7 恢复后 C1/C2 仍成立（负控制没把产品改坏）',
      (lambda o: o.startswith(persona.rstrip()) and patch in o)(M._with_ralsei_patch(persona)))

# =============================================== D 接线
head(u'D. 接线（AST）：对话与预热**各一处**，且都排在 `_build_persona_prompt()` 之后')


def _func(name):
    for n in ast.walk(_t_main):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _calls(fn, name):
    out = []
    for n in ast.walk(fn) if fn else []:
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == name:
                out.append(n.lineno)
            elif isinstance(f, ast.Attribute) and f.attr == name:
                out.append(n.lineno)
    return sorted(out)


_chat = _func(u'chat_with_ai')
_pre = _func(u'_prewarm_ai_cache')
check(u'D0 两个宿主函数都在（`chat_with_ai` / `_prewarm_ai_cache`）',
      _chat is not None and _pre is not None)

_chat_p = _calls(_chat, u'_with_ralsei_patch')
_pre_p = _calls(_pre, u'_with_ralsei_patch')
_chat_b = _calls(_chat, u'_build_persona_prompt')
_pre_b = _calls(_pre, u'_build_persona_prompt')

check(u'D1 `chat_with_ai` 里恰好 1 处调用', len(_chat_p) == 1, u'%r' % (_chat_p,))
check(u'D2 `_prewarm_ai_cache` 里也恰好 1 处（预热与对话同源，否则预热白做一半）',
      len(_pre_p) == 1, u'%r' % (_pre_p,))
check(u'D3 两处的调用都排在 `_build_persona_prompt()` **之后**（先读人设、再拼补丁）',
      _chat_b and _chat_p and _chat_p[0] > _chat_b[0]
      and _pre_b and _pre_p and _pre_p[0] > _pre_b[0],
      u'chat %r vs %r ｜ prewarm %r vs %r' % (_chat_b, _chat_p, _pre_b, _pre_p))

_bpp = _func(u'_build_persona_prompt')
check(u'D4 `_build_persona_prompt` 自己**不碰**训练纠正（B8 契约"读到的就是全文"不许破）',
      not _calls(_bpp, u'training_patch') and u'training_patch' not in (_bpp and
                                                                       ast.dump(_bpp) or ''))

# =============================================== E 契约不破
head(u'E. `_build_persona_prompt()` 仍返回 persona 全文（`persona_chat B8` 那条）')

_stub = types.SimpleNamespace()
_stub._persona_cache = None
_got = types.MethodType(M.RalseiPet._build_persona_prompt, _stub)()
check(u'E1 桩上真跑，返回值逐字等于 persona 文件', _got.strip() == persona.strip(),
      u'%d vs %d' % (len(_got.strip()), len(persona.strip())))
check(u'E2 它**不含**训练纠正（所以 C1 里"以 persona 开头"不可能靠它蒙过去）',
      patch not in _got)

# =============================================== F 自检
head(u'F. 本套件自检')

_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'F2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'F3 零外部盘（读的文件全在仓库内）',
      all(os.path.abspath(p).startswith(ROOT + os.sep)
          for p in (MAIN_PY, PERSONA_PY, INDEX_JSON)))
check(u'F4 判据只认产品那一个函数（本文件不自己拼尾块）',
      u"PATCH_HEADER_RALSEI + '\\n' + patch" not in _read(os.path.abspath(__file__)))

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'patch_len': len(patch), 'persona_len': len(persona),
       'out_len': len(_out), 'header': _HEADER,
       'chat_call': _chat_p, 'prewarm_call': _pre_p}
with io.open(os.path.join(EV, 'patch137.json'), 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check137：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
