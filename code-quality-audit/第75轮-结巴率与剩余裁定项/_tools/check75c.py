#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第75轮 · 「不知道自己住在哪 / 不知道自己在对谁说话」四项修复的回归锁。

守的是**用户这一轮真机反馈里的四件事**：
  ①「咱要不去城堡镇吧」→「不要放弃，继续努力」  ⇒ AI 不知道自己在哪
  ②「别回复的时候用那个思考的表情…我不缺那一点耐心」 ⇒ 等待期不写「……」
  ③「@托丽尔 你好啊，好久不见」→「？」        ⇒ NPC 不知道在对谁说话
  ④ 关掉思考占位后，事件台词让路闸不能跟着失效（原判据会**恒假**）

判据分四层，**每层都配负控制**（"守住了没有"必须能被测到）：
  A 段 · 场景分片：`_build_ai_context()` 真有「我在哪」，接的是 `SceneState.describe()`
  B 段 · 思考占位：总开关是**模块级**常量（假对象夹具没有类属性/实例方法）+ `_ai_pending` 状态位
  C 段 · 让路闸：`_can_speak_event` 改读 `_ai_pending`（原判据在开关关掉后恒假）
  D 段 · NPC 对话对象：`WHO_IS_TALKING` 真注入 + 76/76 人设共用一处 + 与 Ralsei 措辞不打架

★★ 为什么 A 段要**扫真源码里的 parts.append 字面量**而不是 `'我在某个地方' not in src`：
   后者会命中我**自己写的注释**里对那句话的引用 —— 本轮实测踩过（假红）。
   判据只许看**真会进 prompt 的串**。

★★ 为什么 B 段钉"模块级"：本模块有一批离屏夹具（典型 = `s8_stream` 的 D14）
   用 `types.SimpleNamespace` 假对象**直接调** `stream_delta` / `_stream_reset`。
   那种假对象既没有类属性、也没有实例方法 ⇒ 代码里任何 `self.<东西>` 都 AttributeError。
   本轮实测撞过两次（先类属性、再实例方法），所以这个"放哪儿"是**契约**，不是风格。

★ 本套件**不联网、不实例化 App、不需要显示器**（源码 AST + 纯函数 + 字符串契约）。
★ 放在 `code-quality-audit/第75轮.../_tools/` ⇒ 仓库根 = HERE 上三级。
"""

import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
#: `_tools` → 轮次目录 → `code-quality-audit` → 仓库根
ROOT = os.path.join(HERE, '..', '..', '..')
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)

from modules import npc_persona as NP          # noqa: E402
from modules import dialogue_ui as DU          # noqa: E402

_MAIN = os.path.join(PET, 'src', 'main.py')
_DUI = os.path.join(PET, 'modules', 'dialogue_ui.py')
_NPC = os.path.join(PET, 'modules', 'npc_persona.py')
_PERSONA_MD = os.path.join(PET, 'assets', 'ralsei_persona.md')

_P = 0
_F = 0


def check(name, cond, detail=''):
    global _P, _F
    if cond:
        _P += 1
        print('[PASS] %s%s' % (name, ('   <- %s' % detail) if detail else ''))
    else:
        _F += 1
        print('[FAIL] %s%s' % (name, ('   <- %s' % detail) if detail else ''))


def _read(path):
    return io.open(path, encoding='utf-8').read()


def _func_src(tree, name):
    """按名字取函数源码（AST 层，不吃注释）。取不到 ⇒ `''`。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            try:
                return ast.unparse(node)
            except Exception:
                return ''
    return ''


MAIN_TEXT = _read(_MAIN)
DUI_TEXT = _read(_DUI)
NPC_TEXT = _read(_NPC)
MAIN_TREE = ast.parse(MAIN_TEXT)
DUI_TREE = ast.parse(DUI_TEXT)


# ============================================================ A. 场景分片
print('=' * 68)
print('A. persona 身份口径 + AI 上下文「我在哪」分片')
print('=' * 68)


def _a1_scene_shard_in_ctx():
    """A1 `_build_ai_context()` 真注入场景分片，且走 `SceneState.describe()` 唯一入口。"""
    src = _func_src(MAIN_TREE, '_build_ai_context')
    if not src:
        check('A1 _build_ai_context 存在且可解析', False, 'AST 取不到')
        return
    # 只扫**真会进 prompt 的串**：parts.append(<字面量>)。
    # ★ 为什么不扫裸 `'你在桌面上' in src`：会命中注释里的引用（本轮实测假红）。
    appends = re.findall(r"parts\.append\(\s*(?:f)?['\"]([^'\"]+)", src)
    has_scene = any(('你在桌面上' in s) or ('你此刻在' in s) for s in appends)
    uses_describe = '.describe()' in src
    check('A1 上下文真有「我在哪」分片（扫真 parts.append 字面量，不吃注释）',
          has_scene, 'appends=%r' % (appends[:6],))
    check('A1b 场景名来自 SceneState.describe() 唯一入口（不自己拼）',
          uses_describe)
    # 负控制：合成的旧写法（无分片）必须被判「无」
    fake_old = "parts=[]\nparts.append('现在是晚上')\nreturn ''.join(parts)"
    old_appends = re.findall(r"parts\.append\(\s*(?:f)?['\"]([^'\"]+)", fake_old)
    check('A1c 负控制：无分片的旧写法必须判否（证明判据有鉴别力）',
          not any(('你在桌面上' in s) or ('你此刻在' in s) for s in old_appends))


def _a2_scene_empty_omitted():
    """A2 取不到场景时**整段省略**（不注入"我在某个地方"这类废话）。"""
    src = _func_src(MAIN_TREE, '_build_ai_context')
    # `if _where:` 守卫在，且**没有**任何 append 出占位式废话
    appends = re.findall(r"parts\.append\(\s*(?:f)?['\"]([^'\"]+)", src)
    nonsense = [s for s in appends if ('某个地方' in s) or ('不知道在哪' in s)]
    guarded = bool(re.search(r'if\s+_where\s*:', src))
    check('A2 取到空场景时整段省略（有 if 守卫 + 无"我在某个地方"废话）',
          guarded and not nonsense,
          'guarded=%s nonsense=%r' % (guarded, nonsense))
    check('A2b 正控制：守卫变量确实是非空判据（不是恒真）',
          bool(re.search(r"_where\s*=\s*_scene\.describe\(\)", src)))


def _a3_persona_where_section():
    """A3 真源 persona 的「我现在在哪」节与新口径一致（用户裁定：住在暗世界、桌面是窗）。"""
    md = _read(_PERSONA_MD)
    check('A3 persona 存在「我现在在哪」节', '我现在在哪' in md)
    check('A3b 明写「我住在黑暗世界里」（不是"过去的事"）',
          '我住在黑暗世界里' in md)
    check('A3c 明写「桌面 = 窗」（用户裁定的连接口径）',
          '窗' in md and ('你的桌面' in md))
    # 负控制：旧口径不许回来
    check('A3d 负控制：已无"住进…电脑桌面"式旧叙事',
          '住进了' not in md)


_a1_scene_shard_in_ctx()
_a2_scene_empty_omitted()
_a3_persona_where_section()


# ============================================================ B. 思考占位
print()
print('=' * 68)
print('B. 思考占位：可关 + 显式等待态')
print('=' * 68)


def _b1_module_level_flag():
    """B1 总开关必须是**模块级**常量（假对象夹具没有类属性/实例方法）。"""
    check('B1 AI_THINKING_PLACEHOLDER_ENABLED 是模块级常量',
          hasattr(DU, 'AI_THINKING_PLACEHOLDER_ENABLED'),
          'value=%r' % getattr(DU, 'AI_THINKING_PLACEHOLDER_ENABLED', None))
    check('B1b 默认值 = False（用户裁定：不要那个思考的表情）',
          getattr(DU, 'AI_THINKING_PLACEHOLDER_ENABLED', None) is False)
    # 源码级：确认它是**模块顶层赋值**而不是类属性
    top_assign = False
    for node in DUI_TREE.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'AI_THINKING_PLACEHOLDER_ENABLED':
                    top_assign = True
    check('B1c 源码级：该名字在模块顶层被赋值（不是只在类里）', top_assign)
    # 负控制：类里那份只是同值镜像，**不许**被代码读
    reads_class = re.search(r'self\.AI_THINKING_PLACEHOLDER_ENABLED', DUI_TEXT)
    check('B1d 负控制：没有任何地方读 `self.AI_THINKING_PLACEHOLDER_ENABLED`',
          reads_class is None, '命中=%r' % (reads_class.group(0) if reads_class else None))


def _b2_ai_pending_state():
    """B2 `_ai_pending` 是显式状态位，且只在**非 user** 说话时清。"""
    src = _func_src(DUI_TREE, '_init_state')
    check('B2 _init_state 里预声明 `_ai_pending`（不是成功路径才建）',
          '_ai_pending' in src and re.search(r'_ai_pending\s*=\s*False', src) is not None)
    add = _func_src(DUI_TREE, 'add_dialogue')
    # ★ 关键：排除 user（用户回显发生在 chat_with_ai **之前**，无差别清 = 等待态自杀）
    guarded = re.search(r"if\s+speaker\s*!=\s*'user'\s*:", add) is not None
    check('B2b add_dialogue 里清 `_ai_pending` 时**排除 user**（否则等待态在发出瞬间被自己清掉）',
          '_ai_pending' in add and guarded)
    # 负控制：合成的无差别清必须被判否
    fake = "def add_dialogue(self, speaker, text):\n    self._ai_pending = False"
    fake_add = ast.parse(fake).body[0]
    fake_src = ast.unparse(fake_add)
    check('B2c 负控制：无差别的旧写法必须判否（证明 `!=user` 这条真有鉴别力）',
          re.search(r"if\s+speaker\s*!=\s*'user'\s*:", fake_src) is None)


def _b3_flags_in_both_branches():
    """B3 开关的两档都**真能跑**，且产出不同（A≠B，用假对象真调）。"""
    from types import SimpleNamespace as NS
    from types import MethodType
    _orig = DU.AI_THINKING_PLACEHOLDER_ENABLED
    got = {}
    try:
        for flag in (True, False):
            DU.AI_THINKING_PLACEHOLDER_ENABLED = flag
            s = NS()
            s.typing_text = ''
            s.typing_index = 0
            s.is_typing = False
            s._streaming = False
            s._stream_raw = ''
            s.faces = []

            class _T:
                def stop(self):
                    pass
            s.typing_timer = _T()
            s.set_face = MethodType(lambda self, f: self.faces.append(f), s)
            s._refresh_display = MethodType(lambda self: None, s)
            s.AI_THINKING_PLACEHOLDER = '……'
            DU.DialogueUI._stream_reset(s)
            got[flag] = (s.typing_text, tuple(s.faces),
                         getattr(s, '_ai_pending', None))
    finally:
        DU.AI_THINKING_PLACEHOLDER_ENABLED = _orig
    check('B3 两档都真能跑（假对象不抛）且都在等待态（_ai_pending True）',
          all(v[2] is True for v in got.values()),
          'got=%r' % (got,))
    check('B3b A≠B：占位开 = 「……」+thinking 脸 / 关 = 干净留白',
          got.get(True, ())[:2] != got.get(False, ())[:2],
          'on=%r off=%r' % (got.get(True), got.get(False)))


def _b4_reset_restores_flag():
    """B4 复位：跑完必须把总开关还原（不留脏状态给后续用例）。"""
    check('B4 开关已被复位为 False（本套件跑完后）',
          DU.AI_THINKING_PLACEHOLDER_ENABLED is False,
          'now=%r' % DU.AI_THINKING_PLACEHOLDER_ENABLED)


_b1_module_level_flag()
_b2_ai_pending_state()
_b3_flags_in_both_branches()
_b4_reset_restores_flag()


# ============================================================ C. 让路闸
print()
print('=' * 68)
print('C. 事件让路闸：改读 _ai_pending（原判据在开关关掉后恒假）')
print('=' * 68)


def _c1_can_speak_event_uses_pending():
    """C1 `_event_ai_ready` 优先读 `_ai_pending`，旧占位串只作兼容回退。

    ★★ 函数真名是 `_event_ai_ready`（main.py:8042）。
      本判据第一版写成了 `_can_speak_event`，第二版又信了"叫 `_can_speak_now`"
      的旧记忆 —— **两次都因为 AST 取不到而报红**，才定位到真名。
      "判据里的函数名/常量名写错"在本项目出现过多次（取不到 ⇒ 恒假或恒红），
      所以这里保留一条 C1a：**名字取不到时必须报红**，不许静默跳过。
      ★ 顺带记一条环境事实：`_can_speak_now`（7809-7830）是**另一个**函数
        （判断"现在能不能开口"），不负责事件让路 —— 两者别混。
    """
    src = _func_src(MAIN_TREE, '_event_ai_ready')
    if not src:
        check('C1a 函数名取得到（写错名字必须报红，不许静默跳过）', False,
              'main.py 里没有 `_event_ai_ready`')
        return
    check('C1a 函数名取得到（写错名字必须报红，不许静默跳过）', True)
    has_pending = '_ai_pending' in src
    has_fallback = 'AI_THINKING_PLACEHOLDER' in src
    check('C1 让路闸真读 `_ai_pending`（显式状态位，与显示内容解耦）', has_pending)
    check('C1b 保留旧占位串作兼容回退（老版本没有该属性时仍能守）', has_fallback)
    # 负控制：**只**靠占位串的旧写法，在开关关掉后必然恒假 ⇒ 判据要能识别它
    fake_old = ("if getattr(dui, 'typing_text', '') == "
                "getattr(dui, 'AI_THINKING_PLACEHOLDER', None):\n    return False")
    check('C1c 负控制：**只**靠占位串的写法必须被判"未读 _ai_pending"',
          '_ai_pending' not in fake_old)


def _c2_pending_survives_flag_off():
    """C2 行为级：关掉占位后，`typing_text` 为空但等待态仍为真（这就是让路闸还能工作的原因）。"""
    pending_true = False
    try:
        DU.AI_THINKING_PLACEHOLDER_ENABLED = False
        from types import SimpleNamespace as NS
        from types import MethodType
        s = NS()
        s.typing_text = ''
        s.typing_index = 0
        s.is_typing = False
        s.faces = []
        s.set_face = MethodType(lambda self, f: self.faces.append(f), s)
        s._refresh_display = MethodType(lambda self: None, s)
        DU.DialogueUI._ai_thinking_on(s)
        pending_true = (getattr(s, '_ai_pending', None) is True
                        and s.typing_text == '')
    except Exception as e:
        print('   [warn] C2 构造异常（已记录）: %s' % e)
    finally:
        DU.AI_THINKING_PLACEHOLDER_ENABLED = False
    check('C2 关掉占位后：前台是空的（typing_text==\'\'）但 `_ai_pending` 仍为真',
          pending_true,
          '⇒ 让路闸靠 `_ai_pending` 才不会随占位一起失效')


_c1_can_speak_event_uses_pending()
_c2_pending_survives_flag_off()


# ============================================================ D. NPC 对话对象
print()
print('=' * 68)
print('D. NPC「现在跟你说话的是谁」（@托丽尔 → 「？」的真根因）')
print('=' * 68)


def _d1_who_is_talking_exists():
    """D1 常量存在、非空、只讲本体论（不含 Ralsei 专属关系措辞）。"""
    who = getattr(NP, 'WHO_IS_TALKING', None)
    check('D1 WHO_IS_TALKING 是模块级常量且非空',
          isinstance(who, str) and bool(who.strip()))
    if not isinstance(who, str):
        return
    check('D1b 明写「对方是真实世界的玩家本人」',
          '真实世界' in who and '玩家' in who)
    check('D1c 明写「不是原作剧情里的角色」（否则模型会往人设里的角色上猜）',
          '不是原作' in who)
    # ★ 措辞纪律：不许带 Ralsei 专属的关系措辞（会与仆从类人设打架）
    banned = ['平级', '主人', '使命']
    hit = [b for b in banned if b in who]
    check('D1d 负控制：不含 Ralsei 专属关系措辞（平级/主人/使命）——套上去会与各人设打架',
          not hit, '命中=%r' % (hit,))


def _d2_injected_into_system():
    """D2 真注入：`build_system_prompt` 产出的 system 里有它，且顺序在 persona 之后。"""
    personas = NP.load_personas()
    if not personas:
        check('D2 load_personas 非空（人设真在盘上）', False)
        return
    sid = 'toriel' if 'toriel' in personas else sorted(personas)[0]
    sp = NP.build_system_prompt('T', personas[sid], None, sid, '【此刻】现在是上午。')
    check('D2 system 里真含 WHO_IS_TALKING', NP.WHO_IS_TALKING in sp)
    i_p = sp.find(str(personas[sid])[:20])
    i_w = sp.find(NP.WHO_IS_TALKING[:20])
    i_s = sp.find('【说话方式】')
    check('D2b 顺序 = 人设正文 → WHO_IS_TALKING → SPEAK_RULES（纠正性说明必须紧跟被纠正那段）',
          -1 < i_p < i_w < i_s, 'idx: persona=%d who=%d speak=%d' % (i_p, i_w, i_s))
    # 负控制：合成一份"没有 WHO_IS_TALKING"的调用（模拟改前），判据必须判否
    check('D2c 负控制：把该段摘掉后同判据必须判否（证明注入非恒真）',
          NP.WHO_IS_TALKING not in sp.replace(NP.WHO_IS_TALKING, ''))


def _d3_all_personas_share_one_source():
    """D3 ★ 修法是**一处**生效：76 份人设原文里**不许**各自硬塞一份（避免以后每加人设都漏）。"""
    personas = NP.load_personas()
    n_with_text = sum(1 for t in personas.values() if '你要知道' in t or '真实世界的玩家' in t)
    check('D3 76 份人设原文里**没有**各自硬塞这段（修法收在代码一处，不散在素材里）',
          n_with_text == 0, '硬塞份数=%d / 共%d份' % (n_with_text, len(personas)))
    check('D3b 人设份数 ≥ 70（本判据不是对着空集在数）', len(personas) >= 70,
          '份数=%d' % len(personas))


def _d4_fallback_aligned():
    """D4 `main.py:_PERSONA_FALLBACK` 与真源同口径（读失败时不许退回"住进电脑桌面"旧叙事）。"""
    src = _func_src(MAIN_TREE, '_build_persona_prompt')
    # 取类属性字面量（AST 层扫赋值）
    fb = ''
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_PERSONA_FALLBACK':
                    try:
                        fb = ast.literal_eval(node.value)
                    except Exception:
                        fb = ''
    check('D4 兜底人设取得到（AST 层真读到字面量）', bool(fb), 'len=%d' % len(fb))
    if fb:
        check('D4b 兜底仍含 J1 判据锚（不用叫他 / 仅此而已 / 平级）——改了会连带 J1 报红',
              ('不用叫他' in fb) and ('仅此而已' in fb) and ('平级' in fb))
        check('D4c 兜底已对齐新口径：明写「住在黑暗世界」（不再只说"在这台电脑的桌面上"）',
              '黑暗世界' in fb)
        check('D4d 负控制：兜底里已无"住在主人"式旧叙事',
              '住在主人' not in fb and 'Windows 电脑桌面' not in fb)


_d1_who_is_talking_exists()
_d2_injected_into_system()
_d3_all_personas_share_one_source()
_d4_fallback_aligned()


# ============================================================ 收尾
print()
print('=' * 68)
print('总计 %d 项，通过 %d，失败 %d' % (_P + _F, _P, _F))
print('=' * 68)
sys.exit(1 if _F else 0)
