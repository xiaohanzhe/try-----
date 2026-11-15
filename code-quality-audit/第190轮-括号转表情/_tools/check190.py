# -*- coding: utf-8 -*-
u"""第190轮 · 括号动作 → 表情（素材落地 + 产品接线）。

## 这条链要证明的事

用户口径（2026-11-15，三条）：

  ① `括号里的内容也就是表情和动作，用人物动画和表情头像表示`
  ② `一视同仁，不再是主体为ralsei的项目了`
  ③ `难匹配也得匹配，后期微调就好`
  ④ 头像底板：`一句话，尽量按贴近原作即可` ⇒ **纯黑**

整条链是四段，本套件逐段钉住：

```
台词「（苦笑）算了」
   │  event_speech.strip_action_parentheticals(text, sink=acts)
   ▼  acts = ['苦笑']                       ← A 段：删掉的必须**吐出来**
   │  event_speech.acts_to_emotion(acts)
   ▼  emo = 'sad'                           ← B 段：**永远有值**（难匹配兜底 neutral）
   │  main._clean_ai_reply 存 _pending_face_emotion
   │  dialogue_ui.show_dialogue / NPC 分支 pop_pending_face_emotion()
   ▼  dialogue_ui._char_face_candidates('sad') = ['sad','big_sad',...,'normal']
   │  sprite_loader.get_face_for(char_id, name) 逐级试
   ▼  贴到 face_label（黑底白边框）
```

## 为什么 E 段是核心

E 段不测"函数返回了值"，而是**拿真实素材清单验"一定拿得到图"**：
对 8 个黄魂 id × 18 个情绪键的笛卡尔积，逐个检查候选链里至少有一个名字
在该角色的 manifest 里真实存在。这一条才是用户第③条口径的**硬证据** ——
否则"难匹配也得匹配"只是嘴上说说，实际会贴出空白头像。

## 分段

A sink 通道 6 · B 情绪映射 10 · C 别名链 6 · D 接线 8 · E 素材可达 5 ·
G 旁白/三类分流 14 · F 自检 3 = **52 条**

## 第190轮续二：三类的边界（G10~G11b）

用户第二次纠正后定型（原话见 G10 段上方）：

| 括号内容 | 台词留字 | 出旁白 | 备注 |
|---|---|---|---|
| 场景交互（推开门/走到窗边） | ✘ | ✘ | 场景自己能表达 |
| **内在活动（想了想/犹豫/沉默片刻）** | ✘ | ✘ | `每一个想一想都播那就太麻烦了` |
| 外在表现（叹气/苦笑/蹲下/叉腰） | ✘ | ✔ | 就是"看得见"的那类 |

★ G4/G5/G5b 的样例在续二里**换过一次**（`推开门` → `敲键盘`）：不是放宽判据，
  而是 `推开门` 归入场景类后"不出旁白"才是正解，拿它当"映射不到"的替身属于**夹具过期**。
"""
import ast
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
ES_PY = os.path.join(MODS, 'event_speech.py')
SL_PY = os.path.join(MODS, 'sprite_loader.py')
DU_PY = os.path.join(MODS, 'dialogue_ui.py')
MAIN_PY = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')
FACES = os.path.join(REPO, 'ralsei_pet', 'assets', 'faces')
FACE_MANIFEST = os.path.join(FACES, 'manifest.json')

sys.path.insert(0, MODS)
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
import event_speech as E                       # noqa: E402
import dialogue_ui as D                        # noqa: E402

S = E.strip_action_parentheticals

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


# ================================================================ A sink 通道
print('\n=== A sink 通道（删掉的括号必须能吐出来，否则表情无从谈起）===')

_acts = []
_out = S(u'（笑）你说什么呢', sink=_acts)
check(u'A1 有 sink 时收到被删片段', _acts == [u'笑'], u'acts=%r' % (_acts,))
check(u'A2 返回值不受 sink 影响（与不传 sink 逐字相同）',
      _out == S(u'（笑）你说什么呢'), repr(_out))

_acts2 = []
_out2 = S(u'我在呢。（叹气）要不要先喝水', sink=_acts2)
check(u'A3 句中括号也能记到，且不残留空格/双标点',
      _acts2 == [u'叹气'] and _out2 == u'我在呢。要不要先喝水',
      u'acts=%r out=%r' % (_acts2, _out2))

# ★ 负控制：把 sink 去掉，这些字符串**一个都不该**出现在 acts 里 —— 证明
#   "记到了"不是靠函数副作用撞上的。
_none_ok = (S(u'（笑）你说什么呢') == u'你说什么呢'
            and S(u'（苦笑了下）算了。') == u'算了。')
check(u'A4 负控制：不传 sink 时返回值仍正确（证明 A1/A3 不靠全局副作用）', _none_ok)

# 己闸（发声直显）：内容**不删**，但也要记一笔 —— asgore 的招牌笑声就是这条
_acts3 = []
_out3 = S(u'（笑声：NYEH HEH HEH!）你说得对', sink=_acts3)
check(u'A5 发声直显（己闸）也记一笔，且声音本体仍保留在台词里',
      bool(_acts3) and u'NYEH HEH HEH' in _out3,
      u'acts=%r out=%r' % (_acts3, _out3))

# 负控制：没有实义字符的括号不该被记（否则 acts 里全是垃圾）
_acts4 = []
S(u'（）', sink=_acts4)
S(u'（  ）', sink=_acts4)
check(u'A6 负控制：空括号/纯空白**不记**', _acts4 == [], u'acts=%r' % (_acts4,))


# ================================================================ B 情绪映射
print('\n=== B 情绪映射（永远有值；具体规则优先于笼统规则）===')

check(u'B1 「笑」→ smile', E.act_to_emotion(u'笑') == u'smile',
      E.act_to_emotion(u'笑'))
check(u'B2 「苦笑了下」→ sad（**必须压过** 笑→smile，顺序即优先级）',
      E.act_to_emotion(u'苦笑了下') == u'sad', E.act_to_emotion(u'苦笑了下'))
check(u'B3 「尴尬地笑了笑」→ shy（同理压过 笑）',
      E.act_to_emotion(u'尴尬地笑了笑') == u'shy',
      E.act_to_emotion(u'尴尬地笑了笑'))
check(u'B4 「大笑」→ laugh（压过 笑）',
      E.act_to_emotion(u'大笑') == u'laugh', E.act_to_emotion(u'大笑'))
check(u'B5 「想了想」→ thinking',
      E.act_to_emotion(u'想了想') == u'thinking', E.act_to_emotion(u'想了想'))
check(u'B6 ★ 无情绪词的动作落到兜底 neutral（**不许是 None/空串**）',
      E.act_to_emotion(u'轻轻敲了敲键盘') == u'neutral',
      repr(E.act_to_emotion(u'轻轻敲了敲键盘')))
check(u'B7 ★ 空输入也返回 non-empty（用户：难匹配也得匹配）',
      isinstance(E.act_to_emotion(u''), str) and E.act_to_emotion(u'') != u'',
      repr(E.act_to_emotion(u'')))
check(u'B8 acts_to_emotion 取**第一个**能匹配具体情绪的（不是最后一个）',
      E.acts_to_emotion([u'轻轻敲了敲键盘', u'笑']) == u'smile',
      E.acts_to_emotion([u'轻轻敲了敲键盘', u'笑']))
check(u'B8b 第一个本身就是具体情绪时就用它（叹气→tired，不被后面的笑盖掉）',
      E.acts_to_emotion([u'叹气', u'笑']) == u'tired',
      E.acts_to_emotion([u'叹气', u'笑']))
check(u'B9 acts_to_emotion([]) → neutral', E.acts_to_emotion([]) == u'neutral')


# ================================================================ C 别名链
print('\n=== C 别名链（情绪键 → 该角色真实存在的表情名）===')

check(u'C1 「smile」首选就是 smile 本身',
      D._char_face_candidates(u'smile')[0] == u'smile',
      u'%r' % (D._char_face_candidates(u'smile'),))
_BASES = [u'normal', u'neutral', u'default', u'plain']
check(u'C2 ★ 任意键的候选链**末尾一定是四个底图名**（少一个就可能贴不出图）',
      D._char_face_candidates(u'sad')[-4:] == _BASES
      and D._char_face_candidates(u'zzz')[-4:] == _BASES
      and D._char_face_candidates(u'') == _BASES,
      u'空键→%r' % (D._char_face_candidates(u''),))
check(u'C3 未知键 ⇒ 原键 + 四个底图名（不吞掉原键，以免原键恰好是原作名）',
      D._char_face_candidates(u'zzz') == [u'zzz'] + _BASES,
      u'%r' % (D._char_face_candidates(u'zzz'),))
_bad_alias = [k for k, v in D._EMO_ALIASES.items() if not v]
check(u'C4 负控制：别名表里没有空候选列表（有就是配置写漏了）',
      not _bad_alias, u'空项 %r' % (_bad_alias,))
_no_norm = [k for k, v in D._EMO_ALIASES.items() if u'normal' not in v]
check(u'C5 负控制：别名表每一项都自带 normal（不靠函数末尾补）',
      not _no_norm, u'缺 normal 的键 %r' % (_no_norm,))

# C6 ★★ **Ralsei 侧**也要全覆盖 —— 只接 NPC 不接 Ralsei 等于接了一半。
#    `ACT_EMOTION_RULES` 吐的是短键（smile/laugh/cry…），而 `_FACE_MAP` 原来是
#    `happy_very` 这类长键；缺映射时 `_resolve_face_name` 会拼出 `face_smile`
#    这种不存在的名字 ⇒ 回退 face_normal ⇒ **括号里的笑被吃掉**。
_GEN_KEYS = ['neutral', 'smile', 'happy', 'laugh', 'sad', 'cry', 'angry',
             'surprised', 'shy', 'worried', 'thinking', 'confused', 'serious',
             'tired', 'excited', 'love', 'smug', 'hurt']
_rface = os.path.join(REPO, 'ralsei_face')
if not os.path.isdir(_rface):
    check(u'C6 Ralsei 表情目录存在', False, _rface)
else:
    _rhave = {f[:-4].lower() for f in os.listdir(_rface)
              if f.lower().endswith('.png')}
    _rmiss = [k for k in _GEN_KEYS
              if D._resolve_face_name(k).lower() not in _rhave]
    check(u'C6 ★ Ralsei 侧：%d 个通用情绪键全部映射到**真实存在的** face_*.png'
          % len(_GEN_KEYS), not _rmiss,
          u'落空的 %r（素材 %d 个）' % (_rmiss, len(_rhave)))


# ================================================================ D 接线
print('\n=== D 接线（改的是不是**产品代码**，不是只在旁边放了个新函数）===')

_es_src = rd(ES_PY)
_sl_src = rd(SL_PY)
_du_src = rd(DU_PY)
_main_src = rd(MAIN_PY)

# D1 sink 形参真的在函数签名里（AST 取，不扫文本 —— 注释里也提到 sink）
_es_tree = ast.parse(_es_src)
_sink_param = False
for node in ast.walk(_es_tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'strip_action_parentheticals':
        _sink_param = any(a.arg == 'sink' for a in node.args.args)
check(u'D1 `strip_action_parentheticals` 形参里有 sink', _sink_param)

# D2 main 的 0a 步真的把 sink 传下去了（AST 找 keyword，防"只写了变量名没用"）
_main_tree = ast.parse(_main_src)
_passed = []
for node in ast.walk(_main_tree):
    if isinstance(node, ast.Call):
        fn = node.func
        nm = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
        if nm == 'strip_action_parentheticals':
            for kw in node.keywords:
                if kw.arg == 'sink':
                    _passed.append(getattr(node, 'lineno', -1))
check(u'D2 main 里真的以 `sink=` 关键字调用（不是只定义不用）',
      len(_passed) >= 1, u'行号 %r' % (_passed,))

check(u'D3 main 有 `pop_pending_face_emotion`（取出即清的出口）',
      'def pop_pending_face_emotion' in _main_src)

# D4 NPC 分支真的按 speaker 贴脸（用户第②条口径的落点）
_du_tree = ast.parse(_du_src)
_npc_face = (u'set_face(_nface, char_id=speaker)' in _du_src)
check(u'D4 NPC 分支按 speaker 贴脸（一视同仁）', _npc_face)

# D4b ★★ NPC 台词的**主路径**是 `add_npc_line`（`npc_speak` 回调走它），
#     不是 `add_dialogue` 的 NPC 分支（那条只有 `_is_npc_speaker` 为真才走）。
#     只改后者等于没改 —— 这条钉住"主路径也贴脸了"。
_anl_cid = False
for node in ast.walk(_du_tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'add_npc_line':
        _anl_cid = any(a.arg == 'char_id' for a in node.args.args)
_passes_npc = (u'add_npc_line(label, reply_text, char_id=npc_id)' in _du_src)
check(u'D4b `add_npc_line` 带 char_id，且调用处真的传了 npc_id（主路径）',
      _anl_cid and _passes_npc,
      u'签名有 char_id=%s 传了 npc_id=%s' % (_anl_cid, _passes_npc))

# D5 set_face 签名带 char_id
_has_cid = False
for node in ast.walk(_du_tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'set_face':
        _has_cid = any(a.arg == 'char_id' for a in node.args.args)
check(u'D5 `set_face` 形参里有 char_id', _has_cid)

# D6 sprite_loader 真的提供按角色取图（两个方法都在，缺一个就取不到）
_sl_tree = ast.parse(_sl_src)
_sl_methods = set()
for node in ast.walk(_sl_tree):
    if isinstance(node, ast.FunctionDef):
        _sl_methods.add(node.name)
check(u'D6 sprite_loader 有 get_face_for + has_face_for',
      {'get_face_for', 'has_face_for'} <= _sl_methods,
      u'缺 %r' % (sorted({'get_face_for', 'has_face_for'} - _sl_methods),))

# D7 头像框底色是纯黑（用户第④条裁定），不是 transparent
#    ★ 判据范围要**收窄到 face_label 自己的 stylesheet**：整个文件里别的控件
#       （输入框/按钮）本来就有 `background-color: transparent`，全文扫会永远红
#       —— 那是"判据过宽→误报"（第159轮的教训）。
_fl_ss = u''
_m = re.search(r'self\.face_label\.setStyleSheet\(\s*"""(.*?)"""',
               _du_src, re.S)
if _m:
    _fl_ss = _m.group(1)
_black = (u'background-color: #000000' in _fl_ss)
_trans = (u'background-color: transparent' in _fl_ss)
check(u'D7 头像框底色=#000000 且不再有 transparent（纯黑底板）',
      bool(_fl_ss) and _black and not _trans,
      u'块内 black=%s transparent=%s' % (_black, _trans))


# ================================================================ E 素材可达
print('\n=== E 素材可达（拿**真实素材清单**验"一定贴得出图"）===')

if not os.path.isfile(FACE_MANIFEST):
    check(u'E0 素材清单存在', False, FACE_MANIFEST)
else:
    _man = json.load(io.open(FACE_MANIFEST, encoding='utf-8'))
    _by_id = {}
    for m in _man:
        if m.get('kind') == 'expression':
            _by_id.setdefault(m['id'], set()).add(m['emotion'])

    # E1 每个 expression id 都必须有"正常脸"那张
    #    ★ 名字不统一（实测：chujin 只有 neutral，ceroba 是 default，
    #      ace/ed 是 normal）⇒ 判据要认这四种，不能只写 normal。
    _BASE_NAMES = {u'normal', u'neutral', u'default', u'plain'}
    _no_base = [cid for cid, emos in _by_id.items()
                if not (_BASE_NAMES & emos)]
    check(u'E1 每个黄魂 id 都有正常脸（normal/neutral/default/plain 之一）',
          bool(_by_id) and not _no_base,
          u'%d 个 id，缺底图的 %r' % (len(_by_id), _no_base))

    # E2 兜底可达：任意情绪键的候选链，至少有一个名字在该角色素材里真实存在
    #    ★ 这一条与 E1 **不蕴含**：E1 只说"素材里有底图"，E2 还要证明
    #      `_char_face_candidates` 的输出里**真的包含那个名字**（补错了就红）。
    _emo_keys = list(D._EMO_ALIASES)
    _dead = []
    for cid, emos in _by_id.items():
        for key in _emo_keys:
            cands = D._char_face_candidates(key)
            if not any(c.lower() in emos for c in cands):
                _dead.append((cid, key))
    check(u'E2 ★ 8 个 id × %d 个情绪键，**全部**能落到真实存在的图（难匹配也得匹配）'
          % len(_emo_keys), not _dead, u'落空的 %r' % (_dead[:5],))

    # E3 每个 id 都能被至少一个**具体**（非 normal）候选命中 —— 否则等于"永远只换正常脸"
    _only_norm = []
    for cid, emos in _by_id.items():
        hit = False
        for key in _emo_keys:
            for c in D._char_face_candidates(key):
                if c != u'normal' and c.lower() in emos:
                    hit = True
                    break
            if hit:
                break
        if not hit:
            _only_norm.append(cid)
    check(u'E3 每个 id 都至少能命中一张**非 normal** 的表情（不然等于没接）',
          not _only_norm, u'只能换 normal 的 %r' % (_only_norm,))

    # E4 反向：别名表里点到的名字，有多少是**真实存在**的（覆盖率，不是判据过/不过）
    _allnames = set()
    for v in D._EMO_ALIASES.values():
        _allnames |= set(v)
    _allreal = set()
    for emos in _by_id.values():
        _allreal |= emos
    _cover = len(_allnames & _allreal)
    check(u'E4 别名表覆盖度报告：引用 %d 个名字，其中 %d 个在素材里真实存在'
          % (len(_allnames), _cover), _cover >= 20,
          u'%.0f%%' % (100.0 * _cover / max(1, len(_allnames))))

    # E5 ★ 端到端：从**真实台词**一路跑到「磁盘上真的存在那个文件」
    #    ★ 前面 E1~E3 验的是"映射表配得对"，这条验的是"整条链串起来了"：
    #      台词 → sink → 情绪键 → 候选名 → 真实 png 路径。中间任何一环断了都会红。
    _E2E = [
        (u'（苦笑）算了。', u'hy_ceroba_ketsukane'),
        (u'（大笑）哈哈，你说得对！', u'hy_starlo'),
        (u'（想了想）那倒也是。', u'hy_chujin_ketsukane'),
        (u'（叹气）今天真是累。', u'hy_mooch'),
        (u'嗯（笑）我在呢。', u'hy_ace'),
    ]
    _e2e_bad = []
    for line, cid in _E2E:
        acts = []
        S(line, sink=acts)
        emo = E.acts_to_emotion(acts)
        hit = None
        for nm in D._char_face_candidates(emo):
            if nm.lower() in _by_id.get(cid, set()):
                hit = nm
                break
        p = os.path.join(FACES, cid, (hit or '') + '.png')
        if not (hit and os.path.isfile(p)):
            _e2e_bad.append((line, cid, acts, emo, hit))
    check(u'E5 端到端：%d 句真实台词 → 情绪键 → 候选名 → **磁盘上真实存在的 png**'
          % len(_E2E), not _e2e_bad, u'断链的 %r' % (_e2e_bad[:3],))


# ================================================================ G 旁白分流
print('\n=== G 旁白分流（没表情可用的括号 ⇒ 交给旁白说出来）===')

# ★★★ 用户 2026-11-15：
#   `括号里的东西有些没有表情的那就用旁白，你还记得旁白是啥，对吧，
#    到时候就单独把那些括号交给旁白说就好`
#   （我追问"没有表情"按哪个口径判）`就是没表情素材可以用来当做那个括号里的
#    东西用的时候`
#
# ⇒ 判据的核心是**素材层**"有没有真对应这张图"，不是"语义上对不对"：
#   语义对上了、但只能退到正常脸，也**算没表情** ⇒ 走旁白。


class _FakeUI(object):
    """假 self：只提供 `split_acts` 需要的 `face_has_real`。

    ★ 为什么不建真 `DialogueUI`：那要 QApplication + 整套控件，而本套件
      从头到尾"零 Qt 构造"。`split_acts` 里除了 `self.face_has_real(...)`
      全是模块级函数 ⇒ 假 self 就够，而且能**精确指定**哪些 (角色, 情绪)
      有真图 —— 测的是分流逻辑本身，不是素材。
    """

    def __init__(self, real):
        self._real = set(real)

    def face_has_real(self, char_id, face_type):
        return (str(char_id), str(face_type)) in self._real


def _split(real, cid, acts):
    return D.DialogueUI.split_acts(_FakeUI(real), cid, acts)


# G1 映射的双出口：真匹配 hit=True / 兜底 hit=False；
#    老接口 `act_to_emotion` 的"永远非空"**一个字没变**
_ex_real = E.act_to_emotion_ex(u'苦笑')
_ex_fall = E.act_to_emotion_ex(u'轻轻敲了敲键盘')
check(u'G1 映射双出口：真匹配 hit=True / 兜底 hit=False，且老接口仍永远非空',
      _ex_real == ('sad', True) and _ex_fall == ('neutral', False)
      and E.act_to_emotion(u'轻轻敲了敲键盘') == 'neutral',
      u'苦笑=%r 敲键盘=%r' % (_ex_real, _ex_fall))

# G2 ★ 负控制：该角色**真有**这张情绪图 ⇒ 换表情、**不许**出旁白
_fk, _nr = _split([('hy_x', 'smile')], 'hy_x', [u'笑'])
check(u'G2 负控制：真有对应图 ⇒ 换表情且**不出**旁白（旁白不能乱冒）',
      _fk == 'smile' and _nr == [], u'face=%r narr=%r' % (_fk, _nr))

# G3 ★★★ 用户口径的落点：只能退到正常脸 ⇒ 算"没表情" ⇒ 走旁白
_fk, _nr = _split([], 'hy_x', [u'笑'])
check(u'G3 ★★★ 只有底图可用 ⇒ 该括号进旁白、头像位不占（用户口径）',
      _fk is None and _nr == [u'笑'], u'face=%r narr=%r' % (_fk, _nr))

# G4 语义上就没匹配到任何情绪 ⇒ 同样走旁白
#    ★★ 第190轮续二换样例（引账，不是调数）：原来拿 `推开门` 当"映射不到"的替身，
#      可这个词现在归**场景类**（用户：`像是和场景互动比如推开门这类的也不用`），
#      它"不出旁白"才是对的 —— 用它当替身会和新口径打架，属于**夹具过期**。
#      改用 `敲键盘`：`G1` 已实测 `hit=False`，且场景/内在/外在三张表都不认它。
_fk, _nr = _split([('hy_x', 'neutral')], 'hy_x', [u'敲键盘'])
check(u'G4 语义没匹配到任何情绪 ⇒ 走旁白（即使该角色有正常脸）',
      _fk is None and _nr == [u'敲键盘'], u'face=%r narr=%r' % (_fk, _nr))

# G5 混合：一句两条括号，一条能换、一条不能 ⇒ 头像位取能换的那条，
#    另一条照样**一条不丢**地进旁白
_fk, _nr = _split([('hy_x', 'smile')], 'hy_x', [u'笑', u'敲键盘'])
check(u'G5 混合括号：能换表情的占头像位，另一条**不丢**、进旁白',
      _fk == 'smile' and _nr == [u'敲键盘'], u'face=%r narr=%r' % (_fk, _nr))

# G5b 反过来（能换的在后）：头像位仍归它 ⇒ 顺序不影响"谁占位"
_fk, _nr = _split([('hy_x', 'cry')], 'hy_x', [u'敲键盘', u'哭'])
check(u'G5b 能换表情的那条在后 ⇒ 仍占头像位，旁白只留换不出的那条',
      _fk == 'cry' and _nr == [u'敲键盘'], u'face=%r narr=%r' % (_fk, _nr))

# G6 边界：规则**显式**命中中性（点头/摇头/温柔…）⇒ 正常脸就是它的正解，
#    **不该**为它单出一行旁白（否则每句"（点头）"都多一行，很吵）
_fk, _nr = _split([], 'hy_x', [u'点头'])
check(u'G6 边界：显式中性动作（点头）⇒ 贴正常脸、**不**出旁白',
      _fk == 'neutral' and _nr == [], u'face=%r narr=%r' % (_fk, _nr))

# ---------------------------------------------------------------------------
# G10~G11b（第190轮续二）：用户 2026-11-15 的第二轮口径
#
#   `不不不，想一想这类的不留，旁白也只是负责，动作类，
#    像是每一个想一想都播那就太麻烦了`
#   `但一定要留时间如果有，那就用动画表示哦`
#
# ⇒ 三类定型：场景交互**删不说** / 内在活动**删不说** / 外在表现**删+说**。
#   旁白的职责被收窄成"只负责看得见的东西"。
# ---------------------------------------------------------------------------

# G10 ★★★ 场景交互类：即使它一条情绪规则都映射不上，也**不许**变成旁白。
#     这条是 G4 的反面 —— 两条合起来才说明"进旁白"是有门槛的，不是兜底垃圾桶。
_fk, _nr = _split([('hy_x', 'smile')], 'hy_x', [u'推开门', u'笑'])
check(u'G10 场景交互类：映射不上也**不许**进旁白（场景自己能表达）',
      _fk == 'smile' and _nr == [], u'face=%r narr=%r' % (_fk, _nr))

# G11 ★★★ 内在活动：台词里**一个字都不留**，而且**一声旁白都不出**
_i_acts = []
_i_clean = E.strip_action_parentheticals(u'（想了想）也许吧。', sink=_i_acts)
_fk, _nr = _split([('hy_x', 'neutral')], 'hy_x', _i_acts)
check(u'G11 内在活动：台词里删干净、且不冒旁白（`太麻烦了`）',
      (u'想了想' not in _i_clean) and (_nr == []) and (_fk is None),
      u'clean=%r acts=%r narr=%r' % (_i_clean, _i_acts, _nr))

# G11b 早期闸（`_BARE_MOOD`/`_NARRATION_INNER`）删掉的内在词**会进 sink**，
#      所以分流层必须自己再挡一道 —— 少这一道，`（犹豫）`照样会变成一行旁白。
_fk, _nr = _split([('hy_x', 'neutral')], 'hy_x', [u'犹豫', u'沉默片刻'])
check(u'G11b 早期闸删掉的内在词：进得了 sink，分流层也必须**挡住不播**',
      _nr == [], u'face=%r narr=%r' % (_fk, _nr))


# G7 旁白渲染：**没有说话人**（无 `▸`、无名字）且斜体 ——
#    否则读起来像"有个人名字叫旁白"
class _FakeHtml(object):
    def _html_pt(self, n):
        return int(n)


_blank = D.DialogueUI._narration_html(_FakeHtml(), u'推开门')
check(u'G7 旁白渲染**无说话人**（没有 `▸`、没有名字、斜体）',
      bool(_blank) and (u'\u25b8' not in _blank) and (u'italic' in _blank)
      and u'推开门' in _blank, _blank[:64])
check(u'G7b 空/纯空白不进历史（负控制：别凭空多一行空旁白）',
      D.DialogueUI._narration_html(_FakeHtml(), u'   ') == u''
      and D.DialogueUI._narration_html(_FakeHtml(), None) == u'')

# G8 取出即清：两个出口共用一份状态，取任一个都要把另一个清掉，
#    否则"先取了片段、情绪还挂着"⇒ 下一句凭空多一个表情。
#    ★ main 构造太重（QApplication + 整套真机），这里只能 AST 判**赋值** ——
#      能证明的是"两个方法各自真的清了对方那一半"，**不是端到端行为**，如实标注。
#    ★ 第一版用 `ast.dump` 取函数体去搜字符串，撞上 F2 的"禁止 dump"（那是防写盘
#      的闸）⇒ 判据误报。改成**结构化判 `self.<attr> = ...`**，既更严也不撞闸。
_main_tree_g = ast.parse(rd(MAIN_PY))


def _self_assigns(fn_name):
    """该函数体里所有 `self.<attr> = ...` 的 attr 名集合（不看字符串）。"""
    out = set()
    for node in ast.walk(_main_tree_g):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if (isinstance(t, ast.Attribute)
                                and isinstance(t.value, ast.Name)
                                and t.value.id == 'self'):
                            out.add(t.attr)
    return out


_a_acts = _self_assigns('pop_pending_paren_acts')
_a_face = _self_assigns('pop_pending_face_emotion')
check(u'G8 两个 pop 互相清状态（取一个就把另一个也清掉，防串句）',
      bool(_a_acts) and bool(_a_face)
      and '_pending_face_emotion' in _a_acts
      and '_pending_paren_acts' in _a_face,
      u'paren_acts 清 %r · face_emotion 清 %r' % (sorted(_a_acts), sorted(_a_face)))

# G9 接线：两条**显示路径**都真的调了"取片段 + 拼旁白"
#    ★ 用 AST 找**调用**，不扫文本 —— 注释里也有这两个名字，纯文本扫会假绿。
_du_tree_g = ast.parse(rd(DU_PY))
_acts_calls = []
_narr_calls = []
for node in ast.walk(_du_tree_g):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == '_acts_of_this_line':
            _acts_calls.append(getattr(node, 'lineno', -1))
        elif node.func.attr in ('_narration_html', 'add_narration'):
            _narr_calls.append(getattr(node, 'lineno', -1))
check(u'G9 接线：`add_npc_line` / Ralsei / NPC 三条路径都取了片段，且都拼了旁白',
      len(_acts_calls) >= 3 and len(_narr_calls) >= 3,
      u'取片段 %r · 拼旁白 %r' % (_acts_calls, _narr_calls))

# ===========================================================================
# H 表演层（第190轮续二）：留时间 / 用动画 / 表情配动画
#
# 用户 2026-11-15 两条原话：
#   `但一定要留时间如果有，那就用动画表示哦`
#   `角色做出表情的时候原作有些时候也会配合一些外部动画来加强表示`
#
# ★ 这一段所有判据都要能看见"演不出来"的失败形态：动画名写错时
#   `play_animation_once` 只 `note_animation_miss` 然后静默返回 False ——
#   行为上完全看不出来。所以 H2 直接核 `animations.json` 里的组名。
# ===========================================================================

# H1 双通道：内在活动**只**进 `pause_sink`，一个都不许漏进 `sink`
#    （漏进去就会被说成旁白 —— 用户：`每一个想一想都播那就太麻烦了`）
_p1, _i1 = [], []
_c1 = E.strip_action_parentheticals(u'（想了想）也许吧。', sink=_p1, pause_sink=_i1)
_p2, _i2 = [], []
_c2 = E.strip_action_parentheticals(u'（叹了口气）好吧。', sink=_p2, pause_sink=_i2)
check(u'H1 双通道分离：内在活动只进 pause（不播），外在表现只进 sink（要播）',
      (_i1 == [u'想了想'] and _p1 == []) and (_p2 == [u'叹了口气'] and _i2 == []),
      u'内在→sink=%r pause=%r · 外在→sink=%r pause=%r'
      % (_p1, _i1, _p2, _i2))

# H2 ★★★ 动画名必须是 `animations.json` 里**真实存在**的组。
#    否则 `play_animation_once` 静默返回 False ⇒ "说了要演、其实永远不演"，
#    而且从任何行为断言上都看不出来（这是本项目最怕的失败形态）。
_anim_path = os.path.join(REPO, 'ralsei_pet', 'assets', 'animations.json')
try:
    _anim_groups = set(json.loads(rd(_anim_path)).get('groups') or {})
except Exception:
    _anim_groups = set()
_need_anims = {u'look_up'}
try:
    _need_anims |= set(D.DialogueUI.EXPRESSION_ANIM.values())
except Exception:
    _need_anims |= {u'laugh', u'surprised', u'cry', u'sad'}
_miss_anim = sorted(_need_anims - _anim_groups)
check(u'H2 ★ 每个用到的动画名都在 animations.json 里（写错不报错，只会永不播）',
      bool(_anim_groups) and not _miss_anim,
      u'用到 %r · 缺失 %r · 清单 %d 组'
      % (sorted(_need_anims), _miss_anim, len(_anim_groups)))

# H3 "先想再说"用的是**定时器**，不是动画完成回调
#    ★ 理由：动画可能被 `change_animation` 的状态锁拦下（返回 False），
#      回调就永远不来 ⇒ 台词永远不显示。"沉默"是这里最坏的失败方式。
_h3 = None
for node in ast.walk(_main_tree_g):
    if isinstance(node, ast.FunctionDef) and node.name == '_event_say_after_thinking':
        _h3 = node
_timers = 0
_anim_cb = 0
_speak_def = False
if _h3 is not None:
    for sub in ast.walk(_h3):
        if isinstance(sub, ast.FunctionDef) and sub.name == '_speak':
            _speak_def = True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr == 'singleShot':
                _timers += 1
            if sub.func.attr == 'play_animation_once':
                for kw in sub.keywords:
                    if kw.arg == 'callback':
                        _anim_cb += 1
check(u'H3 「想一想」用定时器驱动说话，且**不**把说话挂在动画回调上',
      (_h3 is not None) and _timers >= 1 and _speak_def and _anim_cb == 0,
      u'找到函数=%s · singleShot=%d · _speak=%s · 动画回调=%d'
      % (_h3 is not None, _timers, _speak_def, _anim_cb))

# H4 `set_face` 必须是**外层壳**（先 `_set_face_apply` 再配动画）
#    ★ 为什么不把动画直接塞进 `_set_face_apply`：那个函数里有**两条贴图分支**
#      （角色素材命中 → 立刻 return；否则走 Ralsei 老路径），逐个加调用迟早漏一条。
#      这里不数 `return`（它只有 1 条显式 return + 末尾落空），改判"两条分支都在"——
#      即内层同时调了 `_char_face_pixmap` 与 `get_face`。少任何一条，说明有人把
#      回落路径删了，那时"外壳"这个结构也就不再必要了，判据应该叫起来。
_du_tree_h = ast.parse(rd(DU_PY))
_shell = None
_apply = None
for node in ast.walk(_du_tree_h):
    if isinstance(node, ast.FunctionDef) and node.name == 'set_face':
        _shell = node
    if isinstance(node, ast.FunctionDef) and node.name == '_set_face_apply':
        _apply = node
_shell_calls = set()
if _shell is not None:
    for sub in ast.walk(_shell):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            _shell_calls.add(sub.func.attr)
_apply_calls = set()
if _apply is not None:
    for sub in ast.walk(_apply):
        if isinstance(sub, ast.Call):
            _f = sub.func
            if isinstance(_f, ast.Attribute):
                _apply_calls.add(_f.attr)
            elif isinstance(_f, ast.Name):
                _apply_calls.add(_f.id)
check(u'H4 `set_face` 是外层壳：先贴图再配动画（内层两条贴图分支都还在）',
      (u'_set_face_apply' in _shell_calls)
      and (u'_maybe_expression_anim' in _shell_calls)
      and (u'_char_face_pixmap' in _apply_calls)
      and (u'get_face' in _apply_calls),
      u'外壳调用 %r · 内层分支 %r'
      % (sorted(_shell_calls), sorted(_apply_calls)))

# H5 接线：显示层真的把表情交给了宿主；宿主那边确实在写节流状态
#    ★ 不能找 `xxx.play_expression_anim(...)` 这种属性调用 —— 实现是
#      `fn = getattr(self.parent, 'play_expression_anim')` 再 `fn(...)`，
#      AST 里看到的是个局部名字。所以按 `getattr` 的**字符串常量**判。
_du_hook_literal = False
for node in ast.walk(_du_tree_h):
    if isinstance(node, ast.FunctionDef) and node.name == '_maybe_expression_anim':
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == 'getattr'):
                for a in sub.args:
                    if isinstance(a, ast.Constant) and a.value == 'play_expression_anim':
                        _du_hook_literal = True
_main_anim_attrs = _self_assigns('play_expression_anim')
check(u'H5 接线：表情→动画的钩子两边都接上了（宿主会写节流状态）',
      _du_hook_literal and '_expr_anim_at' in _main_anim_attrs,
      u'显示层取钩子=%s · 宿主写 %r'
      % (_du_hook_literal, sorted(_main_anim_attrs)))


# ================================================================ F 自检
print('\n=== F 自检 ===')

EXPECT = 57
# F1 跑的时候后面还剩 F1/F2/F3 三条（含自己）⇒ 补 +3
check(u'F1 判据条数 == 声明的 %d 条' % EXPECT, (_n['p'] + _n['f']) + 3 == EXPECT,
      u'实跑 %d 条（F1 之前，未计 F1/F2/F3）' % (_n['p'] + _n['f'],))

_writes = []
for node in ast.walk(ast.parse(rd(os.path.abspath(__file__)))):
    if isinstance(node, ast.Call):
        fn = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
        if fn == 'open':
            modes = [a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if any(('w' in m or 'a' in m or '+' in m) for m in modes[1:]):
                _writes.append(getattr(node, 'lineno', -1))
        elif fn in ('write_text', 'dump', 'write'):
            _writes.append(getattr(node, 'lineno', -1))
check(u'F2 本套件只读：AST 里没有写模式的 open / dump / write',
      not _writes, u'可疑行 %r' % (_writes,))

_s = rd(os.path.abspath(__file__))
check(u'F3 PASS / FAIL 标记是字面量（`run_all` 才数得到；此处不回显字面量）',
      u"'[PASS] %s%s'" in _s and u"'[FAIL] %s%s'" in _s,
      u'源码两处都在')

print()
print(u'%d PASS / %d FAIL' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
sys.exit(0 if _n['f'] == 0 else 1)
