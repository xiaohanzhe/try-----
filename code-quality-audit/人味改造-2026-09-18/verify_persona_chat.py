# -*- coding: utf-8 -*-
"""第十八轮（并行线）验证：对话 AI「人味」改造 —— 角色设定外置 + 接线修对 + 输出护栏。

背景
----
诊断见项目根 `Ralsei对话人味诊断与训练方案_2026-09-18.md`，证据见
`code-quality-audit/人味诊断-2026-09-18/_evidence/`。一句话：
**「没活人味」的主因不是 3B 模型不行，是提示词与接线没接对。**

本轮改的东西，以及每条为什么必须被锁住（都踩过坑）
----------------------------------------------------
1) **角色设定外置成单一真源** `ralsei_pet/assets/ralsei_persona.md`。
   为什么不能只写在 Modelfile 里：实测 Ollama 用 `messages` 里的 system
   **整体替换** Modelfile 的 SYSTEM（不传 system 时 prompt_eval_count=1237，
   传了之后骤降到 41）→ 写在模型里的人设，真实应用里**一次都不会生效**。

2) **persona 文件本身不能写 markdown**。它是喂给模型的提示词，不是给人看的文档；
   里面出现 `**` / 行首 `#` 会直接被 3B 学去（实测输出过
   `**听到也让我心里暖暖的**`，而对话框是逐字打字机渲染，星号会原样显示）。

3) **用户消息保持纯原话**，【此刻】/话题锚/记忆召回一律挂 system 尾部。
   拼在用户消息前面时模型会当成"用户说的话"并复述成回答（E4-V0）。

4) **车轱辘话护栏**：判退只看"和自己最近说过的话重复"，**不看"像不像 persona 示范"**。
   这是被实测推翻过一次的设计：3B 对「我好喜欢你呀」这类高频问题会**稳定地**
   吐出示范句，若示范句一律判退，真机链路上是"判退→重采样→还是照抄→交回 None
   →观众看到内置规则台词"，比照抄本身更出戏。示范句本身是好台词，第一次说出来没问题；
   真正出戏的是同一句反复出现 —— 第二次再想抄，它就落在 recent 里了。
   **所以本套件有一条"防回退"断言：回复等于 persona 示范句、但 recent 为空时必须放行。**

5) **判退后重采样**（抬温 +「换一个说法」），而不是直接沉默。

分组
----
  A persona 文件契约（存在 / 章节 / 桌宠化口径 / 世界观知识 / 无 markdown / 示范成对）
  B main.py 接线（源码级 + 行为级）
  C 输出护栏行为（合成 persona，与内容解耦；含括号动作 / 禁说清单）
  D 判退后重采样链路（FakeCli 行为级）
  E 关键词拦截收紧（软闲聊放行 / 硬指令仍子串）
  F 运行时配置与 Modelfile
  G 载体层状态管理（_build_ai_context 的状态口径）
  H 对话链路「禁说清单」兜底接线（判据与事件链路**同源**，2026-09-19 补）

本套件**不打网络、不调用 Ollama**（模型质量不进回归基线 —— 它天生不可复现）。
必须用 C:\\Python311\\python.exe 运行（PyQt5）。
"""
import io
import os
import sys
import threading
import time
import types
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
# PET 本身也要进 path：`import modules.worldview_recall` 需要能把 ralsei_pet
# 当作包的父目录来解析（K 组新增）。少了这一条 → ModuleNotFoundError: modules。
for _p in (PET, SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


# ---------------------------------------------------------------- 源码工具
MAIN_PY = os.path.join(SRC, 'main.py')
DIALOGUE_PY = os.path.join(MODS, 'dialogue_ui.py')
CFG_MGR_PY = os.path.join(MODS, 'config_manager.py')
PERSONA_MD = os.path.join(PET, 'assets', 'ralsei_persona.md')
MODELFILE = os.path.join(PET, 'assets', 'ralsei.modelfile')
CFG_JSON = os.path.join(PET, 'config.json')

MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()
DIALOGUE_TEXT = io.open(DIALOGUE_PY, encoding='utf-8').read()

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def code_only_src(src):
    """剥掉注释/字符串后的 token 串联（空白抹平）。

    铁律（MEMORY「验证脚本教训」）：`"字面量" in 源码` 会被注释/文档串误命中，
    所以源码级断言一律走这里；且 tokenize **不产空白 token**，
    拼回必须用 ' '.join（''.join 会把 `import heapq` 粘成 `importheapq`）。
    """
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in _DROP:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


def code_no_comment(src):
    """**只剥注释**（字符串字面量保留）—— 要找"字符串 needle"时必须用这个。

    为什么必须有第二个工具：`code_only_src` 把 STRING 也丢了，于是
      断言 `'assistant'` 之类的字面量 needle 永远匹配不上（B3/B4/B6/B7 首跑全挂，
      正是 MEMORY 里已记过的坑：「找字符串字面量 needle 要用 code_no_comment()」）。
    """
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


CODE_MAIN = code_only_src(MAIN_TEXT)
CODE_DIALOGUE = code_only_src(DIALOGUE_TEXT)


def func_src(src, name, cls=None):
    """取某个函数/方法的源码正文（顺序断言必须限定在目标函数体内，
    用全文件 .index() 会命中别的函数 → 判反）。"""
    lines = src.splitlines()
    start = None
    indent = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('def %s(' % name):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return ''
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= (indent or 0):
            break
        out.append(ln)
    return '\n'.join(out)


# ---------------------------------------------------------------- A
section('A. persona 文件契约（单一真源）')
ok('A1 persona 文件存在且非空', os.path.exists(PERSONA_MD) and os.path.getsize(PERSONA_MD) > 800,
   'size=%s' % (os.path.getsize(PERSONA_MD) if os.path.exists(PERSONA_MD) else None))

PERSONA = io.open(PERSONA_MD, encoding='utf-8').read() if os.path.exists(PERSONA_MD) else ''
for tag, label in (('我是谁', 'A2 有人格定义节'), ('我现在在哪', 'A3 有桌宠化定位节'),
                   ('我怎么说', 'A4 有说话方式节'), ('我的语气', 'A5 有情绪反应节'),
                   ('语气示范', 'A6 有语气示范节')):
    ok('%s（%s）' % (label, tag), tag in PERSONA)

# A7（2026-09-19 第二十轮改写）：原断言是 `'不是 Kris' in PERSONA and 'Windows' in PERSONA`。
# 用户口径：「别把我的身份变成"主人"，我和他平级，他也不是为了什么而来的，他只是来了仅此而已」。
# 于是「我现在在哪」节被整段重写：不再有"住进主人的 Windows 电脑桌面"这种措辞，
# 原锚（"不是 Kris" / "Windows"）自然落空 —— 但**它要防的东西没变**：
#   ① 对方是真实世界的人、不是 Kris（不能被当成游戏角色）
#   ② 他和 Ralsei 是**平级**关系，不能自称"主人"
# 所以断言改成断这两条**新锚**，并保留一条**负锚**：不许再出现"住进…电脑桌面"式旧叙事。
ok('A7 桌宠化口径：明确"对方不是 Kris"且**平级**（不再叫"主人"）',
   '不是 Kris' in PERSONA and '平级的' in PERSONA
   and '仅此而已' in PERSONA
   and '住进了' not in PERSONA,
   '不是Kris=%s 平级=%s 仅此而已=%s 旧叙事=%s'
   % ('不是 Kris' in PERSONA, '平级的' in PERSONA,
      '仅此而已' in PERSONA, '住进了' in PERSONA))
ok('A8 含违禁套话清单', '我理解你的感受' in PERSONA and '作为一个语言模型' in PERSONA)
ok('A9 明确"不要照抄示范句"', '不要整句搬' in PERSONA)
ok('A10 明确"复读口头禅要换着说"', '你还好吗' in PERSONA)

_bad_md = [m for m in ('**', '\n#', '\n>') if m in PERSONA]
ok('A11 persona 里没有 markdown 标记（它是 prompt，不是文档）', not _bad_md,
   '发现=%r' % (_bad_md,))

_n_owner = len([1 for ln in PERSONA.splitlines() if ln.startswith('主人：')])
_n_me = len([1 for ln in PERSONA.splitlines() if ln.startswith('我：')])
# A12 原断言是"主人：/ 我： 各 3 组"（few-shot 成对示范）。
# 2026-09-19 实测推翻了这个设计：**成对示范里的整句会被 4B 逐字背出来** ——
# 「今天吃了火锅」「我好喜欢你呀」两个高频输入，新旧 persona 都稳定输出示范原句。
# 所以把"整句示范"换成"三条接法规则 + 按场合绑定的短碎片"，并保留一条
# "不要整句搬"的显式禁令（见 A9）。
# 断言随之改成"三条接法规则齐备"—— 这才是 now 真正承载行为锚的东西，
# 而且比数对数更有判别力（少一条就说明行为锚缺了一角）。
# 2026-09-19 第二十轮：第三条规则（"不知道自己该说什么的时候"）不受影响，
# 但前两条的**主语词**从"主人"改成了"你"（平级口径），所以锚同步更新。
# 只改主语、不动规则本身 —— 这三条是"先接住对方那件事"的**行为锚**，一条都不能少。
_RULES = ('你说的是坏消息', '你说的是好消息', '不知道自己该说什么的时候')
_missing = [r for r in _RULES if r not in PERSONA]
ok('A12 三条"碰到事该怎么接"规则齐备（坏消息 / 好消息 / 不知道说什么）',
   not _missing, '缺=%r' % (_missing,))
# 反向控制：确认旧断言依赖的成对示范**确实已经不在了**，
# 否则说明改动没生效、上面那条断言是在测一份还在用旧结构的文件。
ok('A12b 反向控制：成对示范（主人：/ 我：）已移除，不再逐字可搬',
   _n_owner == 0 and _n_me == 0, '主人=%d 我=%d' % (_n_owner, _n_me))

# 世界观索引（第二十轮新增）：A 组与 K 组都要读它，**在这里统一加载一次**。
# 位置刻意放在 A 组之前 —— A13–A22 的视图是 `PERSONA + _WV_TEXT`（并集），
# 定义得晚会在构造 `_WV_VIEW` 时 NameError。
import modules.worldview_recall as WR                                   # noqa: E402

_WV_MD = os.path.join(PET, 'assets', 'ralsei_worldview.md')
_WV_TEXT = io.open(_WV_MD, encoding='utf-8').read() if os.path.exists(_WV_MD) else ''
_K_BLOCKS = WR.load_blocks()

# —— A13~A22：世界观 / 角色知识（2026-09-19 加；第二十轮改为查**索引文件**）——
# 用户口径：「一定要保证三角符文本地的世界观也存在，也就是他知道他该知道的游戏内容」。
# 依据不取我的记忆，而取**原作语料本身**：853 条 Ralsei 台词里他自己提到过
#   Susie 120 条 / Kris 116 / Lancer 9 / Queen 9 / Fountain 15 / Darkner 7 / prophecy 6 …
# 取证 `_evidence/ralsei_worldview_2026-09-19.txt`（可复算）。
#
# ⚠️ 第二十轮的位置变更（**这一组为什么改指向**）：
# 世界观正文已从 persona 搬到 `assets/ralsei_worldview.md`（按需召回，见 K 组）。
# 这一组要防的属性 ——「他知道他该知道的游戏内容」—— **没有变**，
# 变的只是**存放位置**。所以断言对象从 PERSONA 换成 PERSONA + 索引的并集。
# 并集视图而不是"只看索引"：万一有人把某段又抄回 persona，并集照样能找到，
# 而这组锁要管的是"**存不存在**"，不是"存在哪"—— 位置由 K1/K2 专门管。
_WV_VIEW = PERSONA + '\n' + _WV_TEXT
ok('A13 有世界观内容（persona 的索引节 + ralsei_worldview.md 一起算）',
   '我知道的世界' in PERSONA and len(_K_BLOCKS) >= 8)
_WORLD_ANCHORS = ('黑暗喷泉', '光之民', '暗之民', '两位光之英雄', 'Kris', 'Susie', 'Lancer')
_miss_w = [a for a in _WORLD_ANCHORS if a not in _WV_VIEW]
ok('A14 核心设定锚齐备（黑暗喷泉 / 光之民 / 暗之民 / 两位光之英雄 / Kris / Susie / Lancer）',
   not _miss_w, '缺=%r' % (_miss_w,))
ok('A15 世界观带"别主动讲、别硬拐"的使用约束（否则会退化成设定倾倒）',
   '平时它们就待在脑子里，不会平白冒出来' in _WV_VIEW
   and '只有话头碰到了那边' in _WV_VIEW
   and '别把话题硬拐' in _WV_VIEW)
ok('A16 他知道"自己瞒过同伴"这件事（原作 ch4 的核心人物动机，也是他性格的来源）',
   '瞒过' in _WV_VIEW)
# 负控制：世界观必须是**游戏里的世界**，不能把元游戏/玩家视角漏进来 ——
# 一旦出现"玩家/存档/读档/通关"这类词，他就从角色退化成旁白，世界观反而变假了。
# 视图**故意用并集**：抄回 persona 也算违规（那会把元游戏词带进常驻前缀）。
_META_WORDS = ('玩家', '存档', '读档', '通关', '第四面墙')
_hit_meta = [w for w in _META_WORDS if w in _WV_VIEW]
ok('A17 负控制：世界观里没有元游戏词（玩家 / 存档 / 读档 / 通关 / 第四面墙）',
   not _hit_meta, '命中=%r' % (_hit_meta,))

# —— A18~A22：人物群像 + 第 5 章（2026-09-19 第二轮补，用户："有些人物都没加上，尤其第 5 章"）——
# 缺口原状：世界观节只点了 Kris/Susie/Lancer/Tenna/King 5 个名字，
#   而语料里 Ralsei 自己提到过 Queen 9 / Rouxls 5 / Berdly 2 / Noelle 1（见 `_evidence/ralsei_worldview_*.txt`），
#   光明世界那一侧（Toriel / Asgore / Noelle / Berdly / Rudy / Sans / Asriel）一个都没写。
#   → 问到"Kris 的妈妈是谁""Noelle 是谁"就露怯。
_LIGHT_ANCHORS = ('托丽尔', 'Asgore', 'Noelle', 'Berdly', 'Rudy', 'Sans', 'Asriel')
_miss_l = [a for a in _LIGHT_ANCHORS if a not in _WV_VIEW]
ok('A18 光明世界人物群像齐备（托丽尔 / Asgore / Noelle / Berdly / Rudy / Sans / Asriel）',
   not _miss_l, '缺=%r' % (_miss_l,))
_DARK_ANCHORS = ('Rouxls', 'Seam', '黑桃国王')
_miss_d = [a for a in _DARK_ANCHORS if a not in _WV_VIEW]
ok('A19 黑暗世界次要人物齐备（Rouxls / Seam / 黑桃国王）',
   not _miss_d, '缺=%r' % (_miss_d,))
# 第 5 章（2026-06-24 发售；本项目语料只到 ch4，**不能**用计数取证 → 依据官方 wiki，见报告 §2.2）：
#   花之王国 / Flowery / 七色花(那束花) / 第二座喷泉 / 骑士抓走 Asgore / Dess 失踪 / 避难所密码。
_CH5_ANCHORS = ('花之王国', 'Flowery', '第二座喷泉', 'Dess', '避难所')
_miss5 = [a for a in _CH5_ANCHORS if a not in _WV_VIEW]
ok('A20 第 5 章关键设定齐备（花之王国 / Flowery / 第二座喷泉 / Dess / 避难所）',
   not _miss5, '缺=%r' % (_miss5,))
ok('A21 第 5 章按"他的记忆"口吻写（含他和 Flowery 的共情，不是关卡攻略）',
   '出发点和我是一样的' in _WV_VIEW and '我一开始很防着他' in _WV_VIEW)
# 负控制：第 5 章内容**不许**写成攻略腔（"收集 10 个粉色硬币 / 秘密 boss / 击败"这类），
#   那是玩家语言，不是 Ralsei 的语言 —— 写进去他就变成维基播报机。
_GUIDE_WORDS = ('粉色硬币', '秘密boss', '秘密BOSS', '击败', '攻略', '通关', '灵魂模式', '隐藏房间')
_hit_guide = [w for w in _GUIDE_WORDS if w in _WV_VIEW]
ok('A22 负控制：第 5 章内容不含攻略腔（粉色硬币 / 秘密 boss / 击败 / 攻略 / 灵魂模式 / 隐藏房间）',
   not _hit_guide, '命中=%r' % (_hit_guide,))

# —— A23~A25：平级关系口径（2026-09-19 第二十轮，用户原话）——
# 「别把我的身份变成"主人"，我和他平级，他也不是为了什么而来的，他只是来了仅此而已」。
# 这一组只钉**关系口径**，不钉具体措辞 —— 措辞以后可以再润，但下面三条语义是硬约束。
_OWNER_EXEMPT = '我不用管他叫'      # 唯一允许出现"主人"的地方：禁令本身
_owner_lines = [ln for ln in PERSONA.splitlines()
                if '主人' in ln and _OWNER_EXEMPT not in ln]
ok('A23 负控制：persona 里"主人"只剩禁令里那一处，没有任何地方拿它当称呼',
   not _owner_lines, '残留=%r' % (_owner_lines[:3],))

# 使命叙事的典型写法（"他把我带到…""让我在这里陪着…""这是我现在的日常"
# "住进…电脑桌面"）。用户明确要求消解掉："他不是为了什么而来的"。
_MISSION_PHRASES = ('他把我带到', '让我在这里陪', '这是我现在的日常', '住进了',
                    '陪着他——', '为了陪伴')
_hit_mission = [p for p in _MISSION_PHRASES if p in PERSONA]
ok('A24 负控制：已无"被带到电脑上/陪着他"的使命叙事',
   not _hit_mission, '命中=%r' % (_hit_mission,))

# 正向：平级关系必须**明写**出来（不是"没写主人"就算数 —— 那是缺省，不是声明）。
# "仅此而已"是用户原话里最要紧的一笔：没有理由、没有任务、没有目的。
ok('A25 正向：明写"平级 + 就是来了，仅此而已"（没有任务、没有缘由）',
   '平级' in PERSONA and '仅此而已' in PERSONA
   and '谁也没有非让我来不可的理由' in PERSONA)

# ---------------------------------------------------------------- B
section('B. main.py 接线（源码级 + 行为级）')

_f_chat = func_src(MAIN_TEXT, 'chat_with_ai')
_CHAT2 = code_no_comment(_f_chat)     # 保留字符串字面量（见 code_no_comment 注释）
ok('B1 chat_with_ai 里用户消息保持纯原话（user_msg = text）',
   'user_msg=text' in code_only_src(_f_chat))
ok('B2 chat_with_ai 的 system 来自 _build_persona_prompt()',
   'system=self._build_persona_prompt()' in _CHAT2)
ok('B3 【此刻】挂 system 尾部（不再是 user 消息前缀）',
   # S7 之后 `_build_ai_context()` 被包进 lean 分支（事件请求不发上下文，
   # 否则 system 每轮都变 → Ollama KV 前缀缓存失效 → 首字 0.63s→1.82s）。
   # 这里只要求"**非 lean** 时仍然调用它"，尾部拼接的断言不变。
   'ifleanelseself._build_ai_context()' in _CHAT2
   and 'system=system+"\\n\\n"+_ctx' in _CHAT2,
   _CHAT2[:0])
ok('B4 抽取 recent（role==assistant 的历史回复）传给护栏',
   "recent=[cfor_r,cinhistoryif_r=='assistant']" in _CHAT2)
# B5 在 S8（流式）那一轮被**加强**过：原来是数 `cli.chat(` 出现 2 次，
# 但引入流式后两次请求被收进同一个助手 `_ask()`（它负责"能流式就流式"），
# 计数法失效。改成直接断言"两次请求都存在、且都走同一个助手" ——
# 比计数更贴近意图（重采样**也**必须带上流式回调，不能绕过）。
ok('B5 判退后有重采样分支，且两次请求共用同一助手（保证重采样也走流式）',
   'reply=_ask(system,opts)' in _CHAT2
   and 'reply2=_ask(system+"\\n\\n"+RalseiPet._RETRY_NUDGE,retry_opts)' in _CHAT2
   and 'def_ask(sys_prompt,ask_opts)' in _CHAT2,
   'reply=%s reply2=%s helper=%s' % (
       'reply=_ask(system,opts)' in _CHAT2,
       'reply2=_ask(system+"\\n\\n"+RalseiPet._RETRY_NUDGE,retry_opts)' in _CHAT2,
       'def_ask(sys_prompt,ask_opts)' in _CHAT2))
ok('B6 重采样温度高于首次',
   "retry_opts['temperature']=min(1.0,float(opts.get('temperature',0.85))+0.1)" in _CHAT2)
ok('B7 _build_ai_context 返回以【此刻】开头',
   'return"【此刻】"+' in code_no_comment(func_src(MAIN_TEXT, '_build_ai_context')))

import main as M                                                    # noqa: E402
R = M.RalseiPet

# J 组用的别名（与 R 同物；单列一个名字只是为了让"读 persona 的 A 组"和
# "读代码接线的 J 组"在断言文本里一眼可分）。
RalseiPetJ = R
# 自主开口 prompt（J5 用）：它是**独立方法**，不在 chat_with_ai 里。
_f_auto = code_no_comment(func_src(MAIN_TEXT, 'start_autonomous_speech'))


def make_stub(**extra):
    s = types.SimpleNamespace()
    s.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    for name in ('_build_persona_prompt', '_clean_ai_reply', '_is_repeat_of_recent',
                 '_ai_chat_options'):
        setattr(s, name, types.MethodType(getattr(R, name), s))
    s.api_config = {}
    for k, v in extra.items():
        setattr(s, k, v)
    return s


stub = make_stub()
ok('B8 _build_persona_prompt 读到的就是 persona 文件全文',
   stub._build_persona_prompt().strip() == PERSONA.strip())

stub_cfg = make_stub(api_config={'options': {'temperature': 0.91, 'max_tokens': 128}})
_opts = stub_cfg._ai_chat_options()
ok('B9 _ai_chat_options 透传 config 的采样参数',
   _opts.get('temperature') == 0.91 and _opts.get('max_tokens') == 128, _opts)
_stub_empty = make_stub()
ok('B10 _ai_chat_options 缺省回落 0.7 / 256',
   _stub_empty._ai_chat_options() == {'temperature': 0.7, 'max_tokens': 256},
   _stub_empty._ai_chat_options())

# `_build_persona_prompt` 必须能在测试桩上跑（不依赖任何 self. 实例属性）——
# 曾经因为 except 分支引用 self.PERSONA_REL_PATH 而在桩上二次抛 AttributeError，
# 被上层宽 except 吞掉 → 表现为"AI 永远沉默"。
ok('B11 _build_persona_prompt 只用类属性（桩对象上可跑）',
   'self.PERSONA_REL_PATH' not in code_only_src(func_src(MAIN_TEXT, '_build_persona_prompt'))
   and 'RalseiPet.PERSONA_REL_PATH'
   in code_only_src(func_src(MAIN_TEXT, '_build_persona_prompt')))
ok('B12 自主开口与交互对话共用同一套护栏（_on_reply 里也过 _clean_ai_reply）',
   'text=self._clean_ai_reply(reply_text)or""'
   in code_no_comment(func_src(MAIN_TEXT, 'start_autonomous_speech')))
ok('B13 _on_reply 对护栏本身做了防御（护栏抛异常不得吞掉"已发起"）',
   'try:text=self._clean_ai_reply(reply_text)or""'
   in code_no_comment(func_src(MAIN_TEXT, 'start_autonomous_speech')))

# ---------------------------------------------------------------- C
section('C. 输出护栏行为（合成 persona，机制与内容解耦）')
SYNTH = ('## 示范\n'
         '主人：我好喜欢你呀\n'
         '我：诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。\n')
D = '诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。'   # 与合成示范逐字相同
MIRROR = '诪、诪！你突然说这个干嘛啦……我、我其实也挺喜欢你的。'        # 改两处，ratio 仅 0.74

s2 = make_stub()
s2._build_persona_prompt = lambda: SYNTH
RECENT = ['被骂了啊……是因为什么事呢？我听着都替你委屈。']

CASES = [
    ('C1 markdown 强调标记剥除', '**听到也让我心里暖暖的**。别太累了。',
     lambda g: g == '听到也让我心里暖暖的。别太累了。'),
    ('C2 行首井号/引用符剥除', '# 早点休息\n> 别熬夜', lambda g: '#' not in g and '>' not in g),
    ('C3 数字列表前缀剥除', '1. 早点休息', lambda g: g == '早点休息'),
    ('C4 小数不误伤（1.5 倍）', '今天效率是 1.5 倍呢。', lambda g: g == '今天效率是 1.5 倍呢。'),
    ('C5 自问自答续写只截前半句', '被骂了……我先陪着你。\n主人：老板说我业绩下滑了',
     lambda g: g == '被骂了……我先陪着你。'),
    ('C6 整条都是续写 → None', '主人：你怎么不说话\n你：我在想事情。', lambda g: g is None),
    ('C7 与 persona 示范逐字相同 + recent 为空 → **必须放行**（防回退）',
     D, lambda g: g == D),
    ('C8 与 persona 示范高度雷同 + recent 为空 → **必须放行**（防回退）',
     MIRROR, lambda g: g == MIRROR),
    ('C9 与 persona 示范逐字相同 + recent 已含它 → None',
     D, lambda g: g is None),
    ('C10 与 recent 高度雷同（后半段原样搬）→ None',
     '被骂了啊……是因为什么事呢？我听着都替你委屈。先坐下歇会儿吧。', lambda g: g is None),
    ('C11 纯标点（只回一个句号）→ None', '。', lambda g: g is None),
    ('C12 包裹引号剥除', '“今天辛苦了，早点休息哦。”', lambda g: g == '今天辛苦了，早点休息哦。'),
    ('C13 与示范/recent 都不重合的正常回复 → 原样通过',
     '今天风挺大的，出门记得加件外套。', lambda g: g == '今天风挺大的，出门记得加件外套。'),
    ('C14 空串 → None', '', lambda g: g is None),
    ('C15 None → None', None, lambda g: g is None),
    ('C16 非字符串 → 转字符串', 12345, lambda g: g == '12345'),
]
for name, inp, pred in CASES:
    recent = [D] if name.startswith('C9') else RECENT
    if name.startswith('C7') or name.startswith('C8'):
        recent = []
    got = s2._clean_ai_reply(inp, recent=recent)
    ok(name, bool(pred(got)), 'got=%r' % (got,))

LONG_IN = '唔……' + '这是一段很长的独白，用来测试超长截断。' * 12
LONG_OUT = stub._clean_ai_reply(LONG_IN)
ok('C17 超长截断：真实长度 ≤ 上限且以句末标点收尾',
   bool(LONG_OUT) and len(LONG_OUT) <= R.AI_REPLY_MAX_CHARS and LONG_OUT[-1] in '。！？!?',
   'in=%d out=%s last=%r' % (len(LONG_IN), len(LONG_OUT or ''), (LONG_OUT or '')[-1:]))

# —— C18/C19：句中「括号动作旁白」（2026-09-19 新增的 0b 步）——
# 样本来自探针归档的真实输出（_evidence/paren_gate_2026-09-19.txt，可复算）。
_PAREN_IN = '诶、诶？晚安啊……你也是呀。（轻轻敲了下键盘）睡吧，梦里有星星的。'
_PAREN_OUT = stub._clean_ai_reply(_PAREN_IN)
ok('C18 括号动作旁白只删那一段（不是整句作废）',
   _PAREN_OUT == '诶、诶？晚安啊……你也是呀。睡吧，梦里有星星的。',
   'got=%r' % (_PAREN_OUT,))
ok('C18b 星号版的动作旁白同样删掉（实测真出现过 `*轻轻敲了敲键盘*`）',
   stub._clean_ai_reply('诶……不说话也行啊。我在呢。*轻轻敲了敲键盘* 要不要先喝点水？')
   == '诶……不说话也行啊。我在呢。要不要先喝点水？',
   repr(stub._clean_ai_reply('诶……不说话也行啊。我在呢。*轻轻敲了敲键盘* 要不要先喝点水？')))
ok('C18c 整句只有一个括号动作 → 判无效（走重采样，与其它判退同路）',
   stub._clean_ai_reply('（歪着头）') is None, repr(stub._clean_ai_reply('（歪着头）')))
# 负控制：Ralsei 用括号讲心里话是他的正常表达手段（原作 853 条里 35 条含括号、26 条以括号开头），
# 必须原样放行 —— 否则"补一个洞"变成"砍掉他的特征"。
_INNER = '（其实我有点怕）'
ok('C19 负控制：括号讲心里话**原样放行**（对话链路不做"句首括号=旁白"的整句作废）',
   stub._clean_ai_reply(_INNER) == _INNER
   and stub._clean_ai_reply('其实……（我想想该怎么说）') == '其实……（我想想该怎么说）',
   repr((stub._clean_ai_reply(_INNER), stub._clean_ai_reply('其实……（我想想该怎么说）'))))

# —— C20/C23：设定里明令不说的两类话（2026-09-19 新增的 0c 步，补 §4.2 那个产品缺口）——
# 缺口原状：persona 写了"这些话我不说"，但**对话链路一句都不查**（事件链路才有那两道闸）。
ok('C20 客服腔 → 判无效（"有什么可以帮你的吗？"，走既有重采样路径）',
   stub._clean_ai_reply('有什么可以帮你的吗？') is None,
   repr(stub._clean_ai_reply('有什么可以帮你的吗？')))
ok('C21 出戏 → 判无效（"作为一个语言模型…"）',
   stub._clean_ai_reply('作为一个语言模型，我其实不太懂这些。') is None,
   repr(stub._clean_ai_reply('作为一个语言模型，我其实不太懂这些。')))
# 顺序锁：0c 必须排在 0b 之后 —— 先剥格式再匹配，否则 `**有什么可以帮你的吗**` 会漏网。
ok('C22 0c 排在剥 markdown 之后（加粗包裹的客服腔同样拦得住）',
   stub._clean_ai_reply('**有什么可以帮你的吗**') is None,
   repr(stub._clean_ai_reply('**有什么可以帮你的吗**')))
# 负控制：这套判据不许误伤正常台词（正/负成对 —— 否则"一律判无效"也能让上面三条变绿）。
ok('C23 负控制：正常台词原样放行（禁语表不得误伤）',
   stub._clean_ai_reply('我今天有点困了，想早点睡。') == '我今天有点困了，想早点睡。'
   and stub._clean_ai_reply('那件事我也没什么办法，但你说话我一直在听。')
   == '那件事我也没什么办法，但你说话我一直在听。',
   repr(stub._clean_ai_reply('我今天有点困了，想早点睡。')))

# ---------------------------------------------------------------- D
section('D. 判退后重采样（行为级，FakeCli）')


class FakeCli:
    enabled = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, prompt, system_prompt=None, **kw):
        self.seen.append({'temp': kw.get('temperature'),
                          'tail': (system_prompt or '')[-24:]})
        return self.replies.pop(0) if self.replies else None


class FakeSig:
    def __init__(self):
        self.vals = []
        self.ev = threading.Event()

    def emit(self, val, cb):
        self.vals.append(val)
        self.ev.set()


FRESH = '诶？！你、你别突然说这个啦……我耳朵都要热起来了。'
s3 = make_stub(api_config={'options': {'temperature': 0.85, 'max_tokens': 256}})
s3.api_enabled = True
s3.api_client = FakeCli([D, FRESH])
s3._api_result = FakeSig()
# 触发条件必须是"和 recent 重合"（本轮的定案）——所以历史里得先有一句几乎一样的台词。
# 曾经这里挂的是 get_ai_history=lambda: []，配旧版"照抄 persona 也算判退"的实现能过；
# 改成 recent-only 之后为空历史 = 不判退 = 不重试，D1~D4 全挂（首跑实测）。
s3.dialogue_ui = types.SimpleNamespace(
    get_ai_history=lambda limit=0: [('assistant', D)],
    get_focus_brief=lambda: '')
s3._build_ai_context = lambda: ''
s3.memory_system = None
s3._build_persona_prompt = lambda: SYNTH
R.chat_with_ai(s3, '我好喜欢你呀', lambda r: None)
s3._api_result.ev.wait(10)
ok('D1 首次判退后确实重采样（cli.chat 调用 2 次）',
   len(s3.api_client.seen) == 2, 'calls=%d' % len(s3.api_client.seen))
ok('D2 重采样温度抬高（0.85 → 0.95）',
   len(s3.api_client.seen) == 2
   and abs(s3.api_client.seen[0]['temp'] - 0.85) < 1e-6
   and abs(s3.api_client.seen[1]['temp'] - 0.95) < 1e-6,
   [c['temp'] for c in s3.api_client.seen])
ok('D3 重采样带「换一个说法」提示',
   len(s3.api_client.seen) == 2
   and '不要沿用你想到的第一句' in s3.api_client.seen[1]['tail'],
   [c['tail'] for c in s3.api_client.seen])
ok('D4 最终交给 UI 的是重采样结果，不是被丢弃的那句',
   s3._api_result.vals == [FRESH], s3._api_result.vals)

s4 = make_stub(api_config={'options': {'temperature': 0.85, 'max_tokens': 256}})
s4.api_enabled = True
s4.api_client = FakeCli(['   '])
s4._api_result = FakeSig()
s4.dialogue_ui = types.SimpleNamespace(get_ai_history=lambda limit=0: [],
                                       get_focus_brief=lambda: '')
s4._build_ai_context = lambda: ''
s4.memory_system = None
R.chat_with_ai(s4, '在吗', lambda r: None)
s4._api_result.ev.wait(10)
ok('D5 模型主动沉默（空回复）不触发重试',
   len(s4.api_client.seen) == 1, 'calls=%d' % len(s4.api_client.seen))

# ---------------------------------------------------------------- E
section('E. 关键词拦截收紧（软闲聊放行 / 硬指令仍子串）')
from modules.dialogue_ui import DialogueUI as DUI                    # noqa: E402

KW_CASES = [
    ('天气', '天气', True), ('天气', '查看天气', True),
    ('天气', '今天天气真好', False), ('天气', '我这边天气怎么样', False),
    ('哭', '我快哭了', False), ('哭', '别哭', True),
    ('游戏', '我做的游戏上线了', False), ('游戏', '游戏', True),
    ('状态', '我状态不太好', False), ('精力', '没什么精力', False),
    ('饿了吗', '你饿了吗', True), ('唱歌', '你唱歌真好听', False),
    ('石头剪刀布', '陪我玩石头剪刀布吧', True), ('睡觉', '你去睡觉吧', True),
]
kw_bad = []
for kw, raw, want in KW_CASES:
    got = (kw in raw) if kw in DUI._HARD_CMDS else DUI._is_command_phrase(raw, kw)
    if got != want:
        kw_bad.append((kw, raw, got, want))
ok('E1 14 条关键词用例全部符合预期', not kw_bad, kw_bad)
ok('E2 硬指令集合非空且与"动作控制流"同名',
   isinstance(DUI._HARD_CMDS, frozenset) and '睡觉' in DUI._HARD_CMDS
   and '石头剪刀布' in DUI._HARD_CMDS)
ok('E3 软关键词的命中判定要求"去掉关键词后剩字 ≤ allowance"',
   'CMD_EXTRA_ALLOWANCE' in DIALOGUE_TEXT and '_is_command_phrase' in DIALOGUE_TEXT)

# ---------------------------------------------------------------- F
section('F. 运行时配置与 Modelfile')
import json                                                          # noqa: E402

_cfg = json.load(io.open(CFG_JSON, encoding='utf-8'))
_api = _cfg.get('api') or {}
# 断言写成"ralsei 系列 + 带版本号"而不是钉死某个版本：
# 底座会随换代而换（2026-09-19 :v2(3B) → :v3(4B)），钉死版本号等于每换一次就要改测试
# —— 与 s1_anim_miss / round5_smoke 的教训同源：**别在断言里写会随项目演进而变的常量**。
ok('F1 仓库默认配置指向 ralsei 系列模型（:vN，版本随底座换代而变）',
   str(_api.get('model', '')).startswith('ralsei:'), _api.get('model'))
ok('F2 仓库默认配置带 options（temperature/max_tokens）',
   isinstance(_api.get('options'), dict) and 'temperature' in _api['options']
   and 'max_tokens' in _api['options'], _api.get('options'))

_cm = io.open(CFG_MGR_PY, encoding='utf-8').read()
ok('F3 config_manager 默认值同步带 options（新装用户也是这套采样参数）',
   '"options"' in _cm and '"temperature": 0.85' in _cm and '"max_tokens": 256' in _cm)

_mf = io.open(MODELFILE, encoding='utf-8').read() if os.path.exists(MODELFILE) else ''
ok('F4 ralsei.modelfile 存在', bool(_mf))
ok('F5 Modelfile 写死 num_ctx 8192（/v1 端点会忽略该参数，只能靠 Modelfile）',
   'num_ctx 8192' in _mf, repr(_mf[:80]))
ok('F6 Modelfile 写死 repeat_penalty（同上）', 'repeat_penalty' in _mf)
# 原断言是 'FROM qwen2.5:3b'（钉死底座）。2026-09-19 底座换到 4B 后它会假红 ——
# 而 Modelfile 真正要守的不变量不是"用哪个底座"，而是 **FROM 指向 ralsei 系列底座**
# 且**采样参数烘在里面**（不然 App 只发 temperature/max_tokens，其余会被静默换掉）。
_mf_from = [ln.strip() for ln in _mf.splitlines() if ln.strip().startswith('FROM ')]
ok('F7 Modelfile 有且只有一条 FROM（底座换代只会改这一行，断言不钉死具体版本）',
   len(_mf_from) == 1 and len(_mf_from[0]) > len('FROM '), _mf_from)
ok('F8 保存配置时不会清空 options（api_config 字典带 options）',
   "'options':_cur_cfg.get('options'," in code_no_comment(MAIN_TEXT))

# ---------------------------------------------------------------- G
section('G. 载体层状态管理（_build_ai_context 的状态口径）')
# 「载体层状态」= 由 App（载体）持有、每轮拼进 system 尾部的"Ralsei 此刻状态"。
# 性格不只在人设文件里，也在状态里：累了会抱怨、被冷落会委屈、
# 站在窗口上和在桌面上说话不该一模一样。
# 这里锁两件事：① 状态确实进了提示词；② 缺子系统时必须静默降级（不能拖垮对话）。
#
# 视图选择：本组 needle 大多含**字符串字面量**（`getattr(self,'is_falling',...)`），
# 而 code_only_src 会把 STRING 也剥掉 → 一律走 code_no_comment（MEMORY 已记 5 次踩坑）。
# G0 就是这条工具语义的自检，免得视图一变形、下面所有断言一起失真。
_CTX_SRC = code_no_comment(func_src(MAIN_TEXT, '_build_ai_context'))
_CTX_CODE = code_only_src(func_src(MAIN_TEXT, '_build_ai_context'))

ok('G0 X0 自检：含引号的 needle 在 code_only_src 上必然落空、在 code_no_comment 上才搜得到',
   ('你站在桌面上' not in _CTX_CODE) and ('你站在桌面上' in _CTX_SRC))
ok('G1 仍以【此刻】开头（S7 时代订下的格式，不许改）',
   'return"【此刻】"+' in _CTX_SRC)
ok('G2 精力/饥饿分档（不再只有"低"一档）',
   '_energy<20' in _CTX_CODE and '_energy<45' in _CTX_CODE
   and '_energy>85' in _CTX_CODE and '_hunger<20' in _CTX_CODE
   and '_hunger<45' in _CTX_CODE)
ok('G3 载体状态：在窗口上 / 在桌面上 / 走动 / 掉落 都会说出来',
   all(k in _CTX_SRC for k in ('你站在一个打开的窗口上', '你站在桌面上',
                               '你正在走动', '你正从高处往下掉')))
ok('G4 被冷落时长由载体时间戳派生（>30 分钟才提，不让模型猜）',
   '你有很久没跟对方说话了' in _CTX_SRC and '_idle>1800' in _CTX_CODE
   and '主人已经很久没跟你说' not in _CTX_SRC)
ok('G5 尾部带"别逐条念"的用法约束（否则模型会把状态当清单念出来）',
   '别逐条念' in _CTX_SRC)
_F_CHAT_CODE = code_only_src(_f_chat)
ok('G6 chat_with_ai 是"主人开口时间戳"的唯一写点，且写在 api_enabled 判断之前（关 AI 也要记）',
   '_last_user_chat_ts=time.time()' in _F_CHAT_CODE
   and _F_CHAT_CODE.index('_last_user_chat_ts=time.time()')
   < _F_CHAT_CODE.index('ifnotself.api_enabled:'))


class _Sub:
    """只提供 _build_ai_context 需要的两个读口的极简桩。"""

    def __init__(self, e, h):
        self._e, self._h = e, h

    def get_energy(self):
        return self._e

    def get_hunger(self):
        return self._h


def make_ctx_stub(energy=50, hunger=50, window=None, fall=False, moving=False,
                  idle=None):
    """**故意不挂** weather_system / emotion_system / memory_system ——
    那三块本来就该走 except 静默降级，顺便当"缺子系统不崩"的常驻负控制。"""
    s = types.SimpleNamespace()
    s.energy_hunger = _Sub(energy, hunger)
    s.current_window = window
    s.window_level = 0
    s.is_falling = fall
    s.is_moving = moving
    if idle is not None:
        s._last_user_chat_ts = time.time() - idle
    return s


_c1 = R._build_ai_context(make_ctx_stub(energy=10, hunger=10))
ok('G7 行为级：低精力 + 低饥饿真的进了上下文',
   '累得快撑不住' in _c1 and '饿得厉害' in _c1, _c1[:90])
_c2 = R._build_ai_context(make_ctx_stub(energy=95, window={'hwnd': 1}, idle=3600))
ok('G8 行为级：精神好 + 站在窗口上 + 久未互动，三条都在',
   '精神很好' in _c2 and '窗口上' in _c2 and '很久没跟对方说话' in _c2, _c2[:130])
_c3 = R._build_ai_context(make_ctx_stub(idle=5))
ok('G9 行为级："刚聊过"与"久未互动"互斥（不会同时出现）',
   '刚跟对方说过话' in _c3 and '很久没跟对方说话' not in _c3, _c3[:130])
_c4 = R._build_ai_context(make_ctx_stub(fall=True))
ok('G10 行为级：掉落时不再报"在走动"（同一份状态的优先级）',
   '往下掉' in _c4 and '正在走动' not in _c4, _c4[:130])
_c5 = R._build_ai_context(types.SimpleNamespace())
ok('G11 行为级：子系统与状态属性全缺也不抛（静默降级），仍是【此刻】串',
   isinstance(_c5, str) and _c5.startswith('【此刻】'), repr(_c5)[:90])

# ---------------------------------------------------------------- H
section('H. 对话链路「禁说清单」兜底接线（§4.2）')
# 缺口原状：persona 第 57~63 行写着"这些话我不说"，事件链路也补了两道代码闸，
# 但**对话链路的 `_clean_ai_reply` 一个字都不查**（用户天天用的正是这条链路）。
# 2026-09-19 补 0c 步，判据**与事件链路共用同一份**（不另抄一张表，免得两处漂移）。
_CLN = code_only_src(func_src(MAIN_TEXT, '_clean_ai_reply'))
ok('H1 _clean_ai_reply 里真的调用了出戏闸（写对了）',
   'looks_out_of_character(t)' in _CLN)
ok('H2 _clean_ai_reply 里真的调用了客服腔闸（写对了）',
   'looks_like_assistant_speak(t)' in _CLN)
# "写对了" ≠ "产品用上了"（本项目最贵的坑，踩过 4 次）：这里再钉一次它**来自 event_speech**。
ok('H3 判据与事件链路共用同一份（从 modules.event_speech 导入）',
   'looks_out_of_character,looks_like_assistant_speak' in CODE_MAIN, CODE_MAIN[:0])
# 反向控制：main.py 里不许出现第二份表 —— 抄一份就一定会漂移。
# （视图走 code_only_src：本文件的注释里提到了这两个名字，用字面量 in 源码会假红。）
ok('H4 反向控制：main.py 里没有第二份禁语表（判据只有 event_speech 一处）',
   '_BANNED_PATTERNS' not in CODE_MAIN and '_OOC_PATTERNS' not in CODE_MAIN)

# ---------------------------------------------------------------- J
# J 组：平级口径的**接线锁**（2026-09-19 第二十轮）
# 为什么单开一组而不并进 A 组：A 组看的是 persona **文件**写没写对，
# 而这里要防的是本项目最贵的那个坑 —— **"文件写对了，产品没用上"**。
# "主人"这个词在代码里还有 5 处会**真的发进模型请求**：
#   ① _build_ai_context 的两条冷落提示  ② 名字提示  ③ _PERSONA_FALLBACK
#   ④ memory_system.recall_text 的 who 标签  ⑤ 自主开口的两条 prompt
# 只改 persona 不改这 5 处，等于白改 —— 而单看 persona 文件是**看不出来**的。
section('J. 平级口径的接线（改 persona 不够，代码里那几处也会发给模型）')

# 判据要和 A23 用**同一条豁免规则**：兜底里允许出现"主人"，
# 但只允许在"不用叫他主人"这个**禁令本身**里出现（那是在否证它）。
# 用整句锚而不是裸词，是为了让这条断言对"兜底被写回旧叙事"仍然敏感。
ok('J1 兜底人设与真源同口径（persona 读失败时不会退回"主人"旧叙事）',
   '不用叫他' in RalseiPetJ._PERSONA_FALLBACK
   and '仅此而已' in RalseiPetJ._PERSONA_FALLBACK
   and '平级' in RalseiPetJ._PERSONA_FALLBACK
   # 负锚：旧兜底那两句"住在主人的 Windows 电脑桌面上"必须不在
   and '住在主人' not in RalseiPetJ._PERSONA_FALLBACK
   and 'Windows 电脑桌面' not in RalseiPetJ._PERSONA_FALLBACK)

# 行为级：真跑一次上下文拼装，确认发给模型的那串里没有"主人"。
# 用 idle 触发"久未互动"分支、并挂一个带名字的 memory_system 桩 ——
# 这两条正是旧代码里唯二会拼出"主人"的路径，必须都覆盖到。
class _MemStub:
    def get_user_preference(self, k, d=''):
        return '小哲' if k == 'user_name' else d

    def get_user_preferences_summary(self):
        return []


_j_stub = make_ctx_stub(energy=95, window={'hwnd': 1}, idle=3600)
_j_stub.memory_system = _MemStub()      # make_ctx_stub 故意不挂它，这里按需补上
_cj = RalseiPetJ._build_ai_context(_j_stub)
ok('J2 行为级：冷落 + 名字两条路径拼出的上下文里没有"主人"',
   '主人' not in _cj and '很久没跟对方说话' in _cj and '小哲' in _cj, _cj[:130])
# 反向控制：这两条断言**不是恒真** —— 换成旧措辞必须变红（否则等于没测）。

_j_old = _cj.replace('对方', '主人')
ok('J3 反向控制：把措辞换回"主人"后，J2 的判据确实会变红（证明 J2 有鉴别力）',
   '主人' in _j_old and '主人' not in _cj)

# 回忆块的 who 标签：直接发给模型，属于"会真正生效"的一处。
_MEM_SRC = code_no_comment(
    func_src(io.open(os.path.join(ROOT, 'ralsei_pet', 'modules', 'memory_system.py'),
                     encoding='utf-8').read(), 'recall_text'))
ok('J4 回忆块的 who 标签是"你"（不是"主人"），且不再拿"主人"当称呼',
   "who='你'if" in _MEM_SRC.replace(' ', '')
   and "who='主人'" not in _MEM_SRC.replace(' ', ''))

# 自主开口的两条 prompt 里有"主人主动来找你聊天了"，也是真发给模型的。
ok('J5 自主开口的 prompt 用"对方"（不再说"主人主动来找你"）',
   '主人主动来找你' not in _f_auto and '对方主动来找你' in _f_auto)

# 自问自答截断正则：**「主人：」必须仍然被认得**（历史记忆/旧模型可能残留），
# 所以这里断的是"它在正则候选里"而不是"它被删了" —— 与 A23 不矛盾：
# A23 管的是**不能拿它当称呼**，这里管的是**要认得这个残留标记**。
ok('J6 截断闸仍认得「主人：」这类残留角色标记（防漏截一整条自问自答）',
   '主人|对方|用户' in RalseiPetJ._role_marker_re().pattern)

# ---------------------------------------------------------------- K
# K 组：世界观**按需召回**（2026-09-19 第二十轮，C1）
# 用户口径：「没必要每次让他说话的时候都读取完整的世界观啊，可以按照语言的关联性
#   去单个读取或是一定范围内读取，就和咱那个记忆系统一样，或是说这个世界观本就是
#   他自己自带的初始记忆」。
# 这一组要同时钉住三件事：**省下来了**、**该想起的想得起来**、**不该倒的不倒**。
section('K. 世界观按需召回（不再每轮全读；碰话题才想起）')

# K1 —— 结构性：世界观**已不在 persona 常驻文本里**。
# 这是"省下来了"的直接证据。注意断的是**正文**而不是标题：
# persona 里现在还有一个"（初始记忆）"的**说明节**，说明节必须留（它告诉模型
# "你现在只有个索引，取到的会附在后面"），但正文不许再躺在里面。
_K_MOVED = ('世界有两面。光明世界是你住的这种普通世界',
            '光明世界来的人叫光之民',
            'Kris 是人类少年，话很少',
            '花的首领叫 Flowery')
_hit_in_persona = [p for p in _K_MOVED if p in PERSONA]
ok('K1 世界观正文已从 persona 常驻前缀移出（不再每轮全读）',
   not _hit_in_persona, '仍留在 persona=%r' % (_hit_in_persona,))
# 反向控制：同一批正文**必须还在**索引文件里 —— 否则上面那条只是因为内容被删了。
_hit_in_wv = [p for p in _K_MOVED if p in _WV_TEXT]
ok('K2 反向控制：同一批正文确实搬到了 ralsei_worldview.md（不是被删掉）',
   len(_hit_in_wv) == len(_K_MOVED), '索引里找到 %r' % (_hit_in_wv,))

# K3 —— persona 变短了（这是"省 token"的量化证据）。
# 阈值取 10000：改前 13140 B。**故意不等号取宽**，让文案增删几行不会假红，
# 但"世界观又被塞回来"（+4768 B）必然越界。
ok('K3 persona 常驻体积已下降（世界观移出后 < 10KB）',
   os.path.getsize(PERSONA_MD) < 10000,
   'size=%s' % os.path.getsize(PERSONA_MD))

# K4 —— 索引可解析：块数够用、每块都有标签和触发词。
ok('K4 世界观索引可解析出 ≥8 个块（每块都有标签与触发词）',
   len(_K_BLOCKS) >= 8
   and all(b.label and b.triggers and b.body for b in _K_BLOCKS),
   'blocks=%d' % len(_K_BLOCKS))

# K5 —— 行为级：**该想起的想得起来**。这几条是"召回有没有接线"的实证。
# 期望值写**中文标签**（人读得懂，改 key 不会假红），因此比对的是 `b.label`。
_K_WANT = (('黑暗喷泉是啥', '世界怎么运作'),
           ('庆典那天发生了什么', '庆典那天'),
           ('你还记得 Dess 吗', '那件事的结局'),
           ('你们去过哪些地方', '走过的地方'))
_k_bad = []
for _q, _want_label in _K_WANT:
    _got = [b.label for b in WR.recall(_q, limit=2)]
    if _want_label not in _got:
        _k_bad.append((_q, _want_label, _got))
ok('K5 行为级：问到世界/庆典/Dess/地点，都召回到对应那块',
   not _k_bad, '未命中=%r' % (_k_bad,))

# K6 —— **负控制：闲聊不召回**。这条最要紧：用户要的是"按关联性读取"，
# 不是"什么都想起来"。回归锁若只测"能召回"，把 MIN_SCORE 调成 0（全命中）
# 也能通过 —— 那就成了"每轮还是在倒设定"，等于没改。
_k_chat = [('我最近好累啊',), ('今天吃什么',)]
_k_leak = []
for (_q,) in _k_chat:
    if WR.recall(_q, limit=2):
        _k_leak.append((_q, [b.key for b in WR.recall(_q, limit=2)]))
ok('K6 负控制：闲聊（累/吃什么）不召回任何世界观块（不硬拐话题）',
   not _k_leak, '误召回=%r' % (_k_leak,))

# K7 —— 上限硬约束：一次最多两块。persona 里"一次别倒太多"是写死的口径，
# 召回必须同源，否则它会把那句话顶掉（设定倾倒）。
ok('K7 一次最多召回 2 块（与 persona"一次别倒太多"同源）',
   len(WR.recall('Kris Susie 喷泉 庆典 Asgore Dess 骑士 避难所', limit=99)) <= 2
   and WR.MAX_BLOCKS == 2)

# K8 —— 无命中返回**空串**（而不是某块兜底）。
# 空串意味着"这轮不追加任何东西"，正是"他没想起来"的正确表现。
ok('K8 无命中时 recall_text 返回空串（不拿某块硬兜底）',
   WR.recall_text('今天天气不错') == '')

# K9 —— 接线：chat_with_ai 里真的调了它，且 **lean 分支跳过**（事件台词不吃召回）。
_CHAT_K = code_no_comment(func_src(MAIN_TEXT, 'chat_with_ai'))
ok('K9 chat_with_ai 真的调用了世界观召回，且 lean 时跳过',
   'worldview_recall' in _CHAT_K and 'ifnotlean' in _CHAT_K.replace(' ', '')
   and 'system=system+"\\n\\n"+_wv' in _CHAT_K)

# K10 —— 初始化环：召回模块**不许** import 项目内模块（QA 启动早期要用它）。
_WR_SRC = io.open(os.path.join(PET, 'modules', 'worldview_recall.py'),
                  encoding='utf-8').read()
_WR_IMPORTS = [ln for ln in _WR_SRC.split('\n')
               if ln.startswith(('import ', 'from '))]
_WR_BAD_IMP = [ln for ln in _WR_IMPORTS
               if 'modules' in ln or 'PyQt' in ln or ln.strip().endswith('main')]
ok('K10 召回模块不 import 任何项目内模块 / Qt（初始化环）',
   not _WR_BAD_IMP, '违规=%r' % (_WR_BAD_IMP,))

# —— K11~K18：世界观**网图**（2026-09-19 第二十一轮，用户口径）——
# 用户口径：「那既然改成更好的读取方式了，那相对应的，世界观可以详细点，然后，
#   你直接做探针吧，测试这类的留到后面，然后，我觉得你可以把他的世界观拆分成网图，
#   这应该会更高效」。
# 这一组钉的是**图本身有没有连对、扩图有没有按规矩开火**。
# 为什么必须单独一组：K5 只管"命中种子对不对"，把边全删掉它照样全绿 ——
# 那就等于"图白写了"（本项目最贵的坑："函数写对了 ≠ 产品用上了"的同型）。
# 所以这里每一条都要求**扩图行为**可见，而不只是结构存在。

_K_BLOCKS, _K_ADJ, _K_DANGLING = WR.load_graph()

# K11 —— 结构：边解析出来了（不是空图）。
# 双侧判据：块数 ≥8 且**至少一半的块有出边** —— 只断"有边"会被一条边糊弄过去。
_k_with_edge = [b.key for b in _K_BLOCKS if b.edges]
ok('K11 世界观已连成网（块间有向边可解析，且多数块真的带边）',
   len(_K_BLOCKS) >= 8 and len(_k_with_edge) >= len(_K_BLOCKS) // 2,
   '带边块=%d/%d' % (len(_k_with_edge), len(_K_BLOCKS)))

# K12 —— **负控制：悬空边为 0**。指向不存在的键 = 那条边永远不会开火，
# 是"看起来连了、其实接不上"的静默失效（本项目已有 4 次"改了没人调用"记录）。
ok('K12 负控制：没有悬空边（每条 @@> 都指向真实存在的块）',
   not _K_DANGLING, '悬空=%r' % (_K_DANGLING,))

# K13 —— 反向可达：边的两端必须**互相**声明（有向图，但世界观是双向联想）。
# 单向边会让"从 A 想起 B"成立、"从 B 想起 A"不成立 —— 用户没理由接受这种不对称。
#
# ⚠️ 这里踩过一次**恒真判据**（第二十一轮鉴别力体检抓到，很值得记）：
#   最初写成 `b.key not in _k_rev.get(t, [])`，其中 `_k_rev[t]` = "指向 t 的所有块"。
#   但对边 A→B 而言，A 指向 B **本就应该**出现在 `_k_rev[B]` 里 ——
#   于是这条对**任何**图都返回空，是一条永远绿的死断言。
#   **更坑的是**：它当时掩盖了真实存在的 4 条单向边（world_main_cast→world_minor 等），
#   给了"图是双向的"这份虚假安全感。判据一旦写反，比不写还危险。
#   正确判据：对边 A→B，要求 **B 也出现在 A 的邻块里**（即 `b.key in adj[t]`，互为邻块）。
_k_oneway = [(b.key, t) for b in _K_BLOCKS for t in b.edges
             if b.key not in _K_ADJ.get(t, [])]
ok('K13 每条边都有反向边（双向联想，不许单向）',
   not _k_oneway, '单向=%r' % (_k_oneway,))

# K14 —— 无自环。**注意断言位置**：不能断"解析结果里没有自环"——
# `_parse` 内部有 `if t == b.key: continue` 主动滤掉自环，那条断言于是**永远为真**
# （死断言，本项目铁律："别写在死代码上"；这条是鉴别力体检实测发现的）。
# 所以这里断的是**解析器对自环的处理**：喂一个**带自环的样本**进去，
# 输出的图里不许有自环、且同一行的其它边必须保留 —— 若哪天有人删了那行过滤，
# 这条才红。
_K_SELF_SAMPLE = ('@@ a|x|aa\n'
                  '@@> a -> a, b\n'
                  '甲\n'
                  '@@ b|y|bb\n'
                  '@@> b -> a\n'
                  '乙\n')
try:
    _k_sb, _k_sadj, _k_sdang = WR._parse(_K_SELF_SAMPLE)
    _k_self = [(b.key, t) for b in _k_sb for t in b.edges if t == b.key]
    _k_self_ok = (not _k_self) and _k_sadj.get('a', []) == ['b']
except Exception as _e:
    _k_self = [('<ERR>', repr(_e))]
    _k_self_ok = False
ok('K14 解析器会滤掉自环（喂自环样本 → 无自环且同行的其它边保留）',
   _k_self_ok, '自环=%r' % (_k_self,))


# K15 —— **扩图真的开火**：种子只占 1 个名额时，必须能沿边补上第 2 块。
# 这是整组最要紧的一条：把 `recall` 里的扩图循环删掉，K11–K14 全绿而这条必红。
# 期望值写成"命中块的邻块之一"（从图里算，不写死 key）—— 改图不会假红，
# 但"不扩图"必然红。
_k_seed_key = None
for _b in _K_BLOCKS:
    # 找一个"只命中它自己、但它带边"的种子场景：用它的第一个触发词当 cue
    if not _b.triggers or not _b.edges:
        continue
    _cue = _b.triggers[0]
    _got = WR.recall(_cue, limit=2)
    if len(_got) == 2 and _got[0].key == _b.key and _got[1].key in _b.edges:
        _k_seed_key = (_cue, _b.key, _got[1].key)
        break
ok('K15 扩图真的开火：命中一块时能沿边补出邻块（删掉扩图必红）',
   _k_seed_key is not None,
   '找不到"命中即扩"的样例（扩图可能没接线）')

# K16 —— 扩图**不越上限**：即使 cue 命中很多、图很密，也绝不超 2 块。
# 与 K7 的区别：K7 断"关键词命中"时的上限，这里断"命中 + 扩图"合计的上限。
ok('K16 扩图后仍不超过 MAX_BLOCKS（命中+邻块合计 ≤2）',
   len(WR.recall('Kris Susie 喷泉 庆典 Asgore Dess 骑士 避难所 花 传说 Seam', limit=99)) <= 2)

# K17 —— **负控制：闲聊不扩图**。这条防的是"只要有边就无条件带一块"那种写法：
# 没有种子 → 没有起点 → 自然不扩。若有人把扩图改成"无条件从图里挑一块补满"，
# 这条必红（而 K6 断的是 recall() 非空，会一起红 —— 两条互为交叉验证）。
_k_chat_expand = [q for q in ('我最近好累啊', '今天吃什么', '在吗')
                  if WR.recall(q, limit=2)]
ok('K17 负控制：闲聊不扩图（没有种子就没有起点）',
   not _k_chat_expand, '误扩=%r' % (_k_chat_expand,))

# K18 —— 确定性：同一 cue 连跑 5 次结果必须逐字相同（图遍历不许依赖 dict 顺序）。
_k_det = set(tuple(b.key for b in WR.recall('喷泉 Kris 庆典', limit=2))
             for _ in range(5))
ok('K18 同 cue 连跑 5 次结果一致（扩图顺序确定、不抖动）',
   len(_k_det) == 1, '出现 %r' % (_k_det,))

# K19 —— **内容量**：用户口径「世界观可以详细点」。这是可量化的诉求，所以给它一条锁。
# 量的是**块体总量**（真正会发给模型的那部分，不含文件头说明与 @@> 边行）。
# 旧版（第二十轮）块体约 1.7K 字符；本轮加厚到约 2.7K。
# 阈值取 2200：改几条不影响，但"又缩回大纲式两句话"（回到 1.7K 档）必然红 ——
# 那正是退步方向。**上限一起断**：任何一块都不许超过 MAX_BLOCK_CHARS，
# 否则一块就能撑爆一次召回（截断是静默的，会悄悄吃掉后半段内容）。
_k_wv_body = sum(len(b.body) for b in _K_BLOCKS)
_k_overlong = [b.key for b in _K_BLOCKS if len(b.body) >= WR.MAX_BLOCK_CHARS]
ok('K19 世界观正文已加厚（按需读取后篇幅不再是常驻成本）且无单块超限',
   _k_wv_body >= 2200 and not _k_overlong,
   'body_chars=%d 超限块=%r' % (_k_wv_body, _k_overlong))

# K20 —— **每块都必须有自己的边**（不许有孤儿块）。
# 孤儿块 = 只在被直接命中时出现、永远不会被"顺带想起"，
# 那它就是"半个图"——用户要的"拆成网图"没落到位。
_k_orphan = [b.key for b in _K_BLOCKS if not b.edges]
ok('K20 没有孤儿块（每个块都至少有一条出边，图是连通的）',
   not _k_orphan, '孤儿=%r' % (_k_orphan,))

# ---------------------------------------------------------------- L
# L 组：关系演进（2026-09-19 第二十轮，D）
# 用户口径：「朋友关系是**逐渐**的，**开始并不是朋友**……他只是一个**意外**来到我桌面上
#   的人，后期和我们相处的关系是**一步一步搭起来**的。加入一个**信任度**，这个信任度
#   **不可见**，只作为关系好坏的评估标准。开始他是**害怕**我们对他的举动，到**不愿意
#   继续和我们说什么**，再**逐渐成为朋友**。」
# 三条要害各有锁：① 起始是戒备 ② 数值不可见 ③ 演进路径有序。
section('L. 关系演进（起始是戒备、信任度不可见、路径有序）')

import modules.relationship as REL                                      # noqa: E402

# L1 —— 起始态：**不是朋友**。这是整组的地基：
# 若 TRUST_INITIAL 落在 warming/friend，其余断言全都是摆设。
_L0 = REL.Relationship(path=None)
ok('L1 起始档位是"害怕戒备"（不是朋友、不是"我来陪你"）',
   _L0.stage == 'distrust' and REL.TRUST_INITIAL < REL.STAGES[1][1],
   'stage=%s trust=%.3f' % (_L0.stage, REL.TRUST_INITIAL))

# L2 —— 路径顺序**逐字**对齐用户原话，不许调换/删档。
_L_ORDER = [k for k, _f, _l in REL.STAGES]
ok('L2 演进路径与用户原话同序（害怕戒备 → 不愿多说 → 慢慢熟 → 朋友）',
   _L_ORDER == ['distrust', 'guarded', 'warming', 'friend'], _L_ORDER)

# L3 —— **信任度不可见**（本组最要紧的一条）。
# 只测"数值没进提示词"不够 —— 还要防止他把"信任/关系/阶段"当话题说出来。
_L_BRIEF = REL.build_brief(0.6)
_has_num = any(ch.isdigit() for ch in _L_BRIEF)
ok('L3 给模型的关系段里**没有数字**（信任度是内部量，不许进提示词）',
   not _has_num, _L_BRIEF[:100])
# 档位名（distrust/guarded/…）也不许出现 —— 出现就等于给了模型一个可以念的词
_L_KEY_LEAK = [k for k, _f, _l in REL.STAGES if k in _L_BRIEF]
ok('L4 关系段里没有档位标识（distrust/guarded/warming/friend 都不出现）',
   not _L_KEY_LEAK, '泄漏=%r' % (_L_KEY_LEAK,))
# 但**必须有禁令**：光有正面指令，4B 一定会把"我现在信任你 X%"说出来。
ok('L5 关系段带"别把它当话题说"的禁令（否则模型会念出信任度）',
   '绝对不要' in _L_BRIEF and '信任' in _L_BRIEF and '打分数' in _L_BRIEF)

# L6 —— 行为级：**好的互动会涨、坏的会跌**。正负成对，避免只测一边。
_L_a = REL.Relationship(path=None)
_L_b = REL.Relationship(path=None)
for _i in range(6):
    _L_a.note('comfort')
    _L_b.note('harsh')
ok('L6 行为级：安慰让信任上升、命令/贬低让它下降（正负成对）',
   _L_a.trust > REL.TRUST_INITIAL and _L_b.trust < REL.TRUST_INITIAL,
   'comfort=%.3f harsh=%.3f' % (_L_a.trust, _L_b.trust))

# L7 —— **"一步一步"**：单轮涨幅有硬上限，不能几句话就称兄道弟。
_L_c = REL.Relationship(path=None)
for _i in range(50):
    _L_c.note('comfort', now=1000.0 + _i)      # 同一时刻连打，排除时间回落干扰
ok('L7 存在单轮涨幅上限（一次互动不可能把关系拉满）',
   _L_c.trust < REL.TRUST_MAX and REL.GAIN_CAP_PER_TURN <= 0.1,
   'trust=%.3f（50 轮 comfort 后）' % _L_c.trust)

# L8 —— 边界：值域是 [0, TRUST_MAX]，两端都不许穿。
# 这条断的是**硬边界**，不是"harsh 后仍不低于起点" —— 后者是错的设计：
# 若下界设成 TRUST_INITIAL，`harsh` 在开局就完全无效，信任度只剩好的一端，
# 退化成进度条（本轮实测抓到的）。0 = 戒备到极点，仍归"害怕戒备"档。
_L_d = REL.Relationship(path=None)
for _i in range(400):
    _L_d.note('comfort', now=1000.0 + _i)
_L_e = REL.Relationship(path=None)
for _i in range(400):
    _L_e.note('harsh', now=1000.0 + _i)
ok('L8 边界：涨到顶不超 TRUST_MAX，跌到底不低于 0（clamp 两端都生效）',
   _L_d.trust <= REL.TRUST_MAX and _L_e.trust >= 0.0
   and _L_d.trust > _L_e.trust,
   'hi=%.3f lo=%.3f' % (_L_d.trust, _L_e.trust))
# 反向控制：`harsh` 必须**真的**能推动关系往下走 —— 否则它是个死事件。
ok('L8b 反向控制：harsh 真的能把信任度压到起点之下（不是死事件）',
   _L_e.trust < REL.TRUST_INITIAL,
   'lo=%.3f init=%.3f' % (_L_e.trust, REL.TRUST_INITIAL))

# L9 —— 久不说话关系会**回落**（信任度是"好坏评估"，必须能往回走）。
_L_f = REL.Relationship(path=None)
for _i in range(40):
    _L_f.note('comfort', now=1000.0 + _i)
_L_peak = _L_f.trust
_L_f.note('chat', now=1000.0 + 40 + REL.IDLE_DECAY_AFTER + 10 * 86400)
ok('L9 久未互动后信任回落（冷落会让关系变凉）',
   _L_f.trust < _L_peak, 'peak=%.3f now=%.3f' % (_L_peak, _L_f.trust))

# L10 —— 分类器：把"安慰/命令/好奇/自我暴露"分对。确定性规则，可回归。
_L_cls = (('别怕，我在呢', 'comfort'),
          ('你给我闭嘴', 'harsh'),
          ('你为什么喜欢这个', 'curious'),
          ('嗯', 'chat'))
_L_bad_cls = [(t, want, REL.classify(t)) for t, want in _L_cls
              if REL.classify(t) != want]
ok('L10 输入分类：安慰/命令/好奇/普通闲聊都分得对',
   not _L_bad_cls, '分错=%r' % (_L_bad_cls,))

# L11 —— **接线**：chat_with_ai 里真的记了账、真的拼了关系段。
# 只写模块不接线 = 本项目最贵的坑（"函数写对了 ≠ 产品用上了"，踩过 4 次）。
_CHAT_L = code_no_comment(func_src(MAIN_TEXT, 'chat_with_ai'))
ok('L11 chat_with_ai 真的调了关系记账与关系段拼接，且 lean 时跳过',
   '_relmod.classify(text)' in _CHAT_L.replace(' ', '')
   and '_rel.note(' in _CHAT_L.replace(' ', '')
   and '_rel.brief()' in _CHAT_L.replace(' ', '')
   and 'system=system+"\\n\\n"+_rel_brief' in _CHAT_L)
ok('L12 关系实例由 App 持有（初始化里挂上 self.relationship）',
   'self.relationship=_make_relationship()' in CODE_MAIN.replace(' ', ''))

# L13 —— persona 的静态关系句必须让位：不许写死"已经是朋友"。
# 这条防的是**本轮真踩过的坑** —— C2 先写了"我们是一起待着的关系"（太热），
# 后来 D 要求起始是戒备。若 persona 里留着一句静态热关系，动态关系段会被它顶掉。
_L_HOT = ('我们是一起待着的关系', '我们是朋友', '我最好的朋友是你')
_L_hot_hit = [h for h in _L_HOT if h in PERSONA]
ok('L13 负控制：persona 里没有写死"已经是朋友/一起待着"的静态关系句',
   not _L_hot_hit, '命中=%r' % (_L_hot_hit,))
# 正向：persona 必须**显式声明关系不固定、以 App 那句为准**（否则模型不知道
# 该听谁的 —— 两份关系描述并存时它会挑更热的那句说）。
ok('L14 persona 声明"关系不是定死的、以另给的那句为准"',
   '我们俩是什么关系，不是定死的' in PERSONA
   and '我另有一句话告诉你，以那句为准' in PERSONA)

# L15 —— 初始化环 + 可选导入：关系模块不许 import 项目内模块。
_REL_SRC = io.open(os.path.join(PET, 'modules', 'relationship.py'),
                   encoding='utf-8').read()
_REL_IMPORTS = [ln for ln in _REL_SRC.split('\n')
                if ln.startswith(('import ', 'from '))]
_REL_BAD_IMP = [ln for ln in _REL_IMPORTS
                if 'modules' in ln or 'PyQt' in ln]
ok('L15 关系模块不 import 任何项目内模块 / Qt（初始化环）',
   not _REL_BAD_IMP, '违规=%r' % (_REL_BAD_IMP,))
# 反向控制：模块是**可选导入**的 —— 挂了也不能让程序起不来。
ok('L16 main.py 对关系模块走可选导入（失败降级，不炸启动）',
   'frommodules.relationshipimportRelationshipas_Relationship' in CODE_MAIN.replace(' ', '')
   and '_Relationship=None' in CODE_MAIN.replace(' ', ''))

# ---------------------------------------------------------------- 汇总
print('')
print('=' * 60)
print('总计 %d 项，通过 %d，失败 %d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - ' + f)
sys.exit(1 if FAIL else 0)
