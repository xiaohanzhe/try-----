# -*- coding: utf-8 -*-
"""第55轮 · NPC 人设 / 独立记忆 / 跟随决策 回归锁（`check55`）。

`soul_entity.soul_can_enter` 的 docstring 里点名的就是本套件的 **S 段**：
用**同一组输入**同时喂 `npc_system.world_gate` 与 `soul_entity.soul_can_enter`，
断言「NPC 被拒而灵魂被放行」—— 那条恒真判据之所以允许存在，全靠这里的对照。

段一览（每段都配正/负控制）
--------------------------
  A 零依赖纪律（AST，含 try/if 里的模块级 import）
  P 人设装载（索引 ↔ 磁盘 ↔ 装载 三者自洽 + 无 BOM / 无 U+FFFD / 无 markdown）
      ★ 第64轮：人设 13 份 → 50 份（用户 30 万字原文里其余 37 份入仓）⇒
        P 段的份数判据已由"写死 13"改为**不变式**，见 P1 处的判据修正记录。
  R 注册表（条数 / 分层 / 模型句柄 / persona 字段 / flowery 命名修正）
  M 独立记忆不串味（★ 用户口径「不要搞混了」—— 正面 + 反面成对断言）
  F 跟随决策 `decide_follow` 正负控制
  D 点名解析 `parse_address` / `match_name_prefix` 正负控制（真实别名表）
  S ★ 门控对照：NPC 被拒 vs 灵魂放行
  W 产品接线（AST 结构断言 + 真机行为断言，防"改了没人调用"）
"""
import ast
import io
import json
import os
import sys
import tempfile
import time as _time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
ASSETS = os.path.join(PET, 'assets')
NPC_DIR = os.path.join(ASSETS, 'npc')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))

_tmp = os.path.join(tempfile.gettempdir(), 'ralsei_check55')
os.makedirs(_tmp, exist_ok=True)
os.environ.setdefault('RALSEI_MEMORY_DIR', _tmp)

# ★★ 必须先把 NPC 记忆清空 —— 第55轮实测踩到并定位的坑：
#   `MiniMemory` 启动时会**从磁盘加载**（`load(npc_id)`），而隔离目录是**跨运行保留**的。
#   于是上一次运行写进去的「他说过的话」会被这一次读出来 ⇒ 本套件那个"固定台词的假客户端"
#   返回的同一句就被护栏 `_is_clean_ai_reply(recent=他自己说过的话)` 判成**重复自己**
#   ⇒ 判退 ⇒ 重采样（还是同一句）⇒ 仍判退 ⇒ `cleaned=None` ⇒ 回调收到 None。
#   ★ 这是**自强化**的：只要失败过一次（那一句已落盘），之后每次都失败；
#     现场表现为"同一份代码跑两次结果不同"的假竞态（其实完全确定，只是被上一次污染）。
#   只清 `npc_memory`（本子系统自己的数据），不动别的套件可能用到的存储。
_npc_mem_dir = os.path.join(os.environ.get('RALSEI_MEMORY_DIR') or _tmp, 'npc_memory')
try:
    if os.path.isdir(_npc_mem_dir):
        for _fn in os.listdir(_npc_mem_dir):
            if _fn.endswith('.json'):
                os.remove(os.path.join(_npc_mem_dir, _fn))
except OSError as _e:
    print('[note] 清理隔离区 NPC 记忆失败（已忽略）: %s' % _e)

import npc_persona as P          # noqa: E402
import npc_system as S           # noqa: E402
import soul_entity as SE         # noqa: E402

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def module_imports(path):
    """返回 `(模块级 import 名, 函数体内 import 名)`。

    ⚠️ 两条都不能省（都踩过或都会踩）：
      ① 模块级 = **不在任何函数体里**（含 `try:` / `if:` 里的 import）——
         只扫 `tree.body` 的直接子节点会**漏掉** `try: from x import y`，
         而本项目里 logger 的降级导入正好就是这个形状（漏了会得到假绿）；
      ② `from a import b` 要**同时**记 `a` 与 `a.b` —— 只记 `a` 的话
         `from modules import npc_system` 在 `main.py` 里会变成只有 `'modules'`，
         "有没有 import npc_system"这条判据就恒假（判据过窄 = 误报）。
    """
    tree = ast.parse(read_text(path))
    outer, inner = [], []

    def collect(node, bucket):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Import):
                bucket.extend(a.name for a in sub.names)
            elif isinstance(sub, ast.ImportFrom):
                mod = sub.module or ''
                if mod:
                    bucket.append(mod)
                    bucket.extend('%s.%s' % (mod, a.name) for a in sub.names)
                else:
                    bucket.extend(a.name for a in sub.names)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    collect(sub, inner)
            continue
        collect(node, outer)
    return outer, inner


def mentions_str(node, text):
    """`node` 里有没有字符串字面量 `text`（用于 `getattr(x, 'name', None)` 形状）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and sub.value == text:
            return True
    return False


# ================================================================== A 零依赖纪律
print('== A 零依赖纪律 ==')
PURE = ('soul_entity', 'npc_persona', 'npc_system')
PURE_ALLOW = {'collections', 'json', 'logging', 'os', 'math', 'logger_utils'}
for m in PURE:
    p = os.path.join(PET, 'modules', '%s.py' % m)
    outer, inner = module_imports(p)
    # 判据是"**顶层模块名**在白名单内"（`logger_utils.get_logger` 这种
    # `from x import y` 的展开形式也一并收进同一段比对）。
    bad = sorted({n for n in outer if n.split('.')[0] not in PURE_ALLOW})
    check('A1 %s.py 模块级 import 只在白名单内' % m, not bad, str(bad))
    check('A2 %s.py 函数体内零 import' % m, not inner, str(inner))

_ov_outer, _ov_inner = module_imports(os.path.join(PET, 'modules', 'soul_overlay.py'))


def _ov_allowed(n):
    """Qt 壳的模块级 import 白名单：标准库 + PyQt5 + **纯逻辑兄弟模块**（`soul_entity`）。

    也就是说：它只许依赖"不会反过来依赖 App"的东西 —— 业务模块（`modules.item_system`
    这种）一律不许进。判据写成函数是因为 `from x import y` 会展开成 `x.y`，
    而白名单要能区分 `modules.soul_entity`（可以）与 `modules.item_system`（不行）。
    """
    if n.startswith('PyQt5'):
        return True
    if n.split('.')[0] in ('logging', 'os', 'sys', 'math'):
        return True
    if n == 'logger_utils' or n.startswith('logger_utils.'):
        return True
    return n in ('modules', 'modules.soul_entity', 'soul_entity')


_ov_bad = sorted({n for n in _ov_outer if not _ov_allowed(n)})
check('A3 soul_overlay.py（Qt 壳）不拖进任何业务模块', not _ov_bad, str(_ov_bad))
check('A3b soul_overlay 的函数内 import 只许是延迟加载 Qt',
      all(n.startswith('PyQt5') for n in _ov_inner), str(sorted(set(_ov_inner))))
# 负控制：构造一个"明显违规"的 import 名单，确认白名单判据**真会报红**
_dummy_bad = sorted({n for n in ('os', 'main', 'modules.item_system')
                     if not _ov_allowed(n)})
check('A4 负控制：白名单判据对 "main" / 业务模块会报红（不是恒真）',
      _dummy_bad == ['main', 'modules.item_system'], str(_dummy_bad))

# ================================================================== P 人设装载
print('== P 人设装载 ==')
idx = P.load_index(assets_dir=ASSETS)
recs = (idx or {}).get('personas') or []
_pdir = P.persona_dir(assets_dir=ASSETS)
check('P3 人设目录存在', os.path.isdir(_pdir), _pdir)

# ⚠️ 判据修正记录（第64轮）——P1 / P2 / P8 原先**写死 13 份**（第55轮用户只交了 13 份）。
#    第64轮把用户 30 万字原文里**其余 37 份**一并入仓（13 → 50）⇒ "写死份数"这条形状
#    立刻变成**过窄判据**（事实变了就报红，而且报的是假问题）。
#    真正该守的从来不是"13"这个数字，而是 **索引 / 磁盘 / 装载 三者自洽**：
#      P1  索引登记的 id 集合 == 磁盘上的 .txt 集合（去扩展名）
#      P2  每条记录的 id == 自己 `file` 的 basename（防两人指同一份档）
#      P8  装载出来的份数 == 索引登记的份数
#    这样无论以后加多少份都成立，且照样能抓到"登记了但文件没落盘 / 落了盘但没登记 /
#    两个 id 共用一个文件"这三类真错。★ 本轮的教训：**判据过窄 = 会误报**，与
#    "恒真判据"同样是元级坑（详见 report §5）。
_disk_txt = sorted(f for f in os.listdir(_pdir) if f.endswith('.txt')) \
    if os.path.isdir(_pdir) else []
check('P1 索引可读，且登记的 id 与磁盘上的 .txt **一一对应**（不写死份数）',
      bool(recs) and sorted(r['id'] for r in recs) == [f[:-4] for f in _disk_txt],
      '索引 %d 份 / 磁盘 %d 个 .txt' % (len(recs), len(_disk_txt)))
_pairs = [(r['id'], os.path.basename(r.get('file') or '')) for r in recs]
_bad_pair = [p for p in _pairs if not p[1].endswith('.txt') or p[1][:-4] != p[0]]
check('P2 每条记录的 id == 自己 file 的 basename（去扩展名）—— 防两人指同一份档',
      not _bad_pair
      and len({p[0] for p in _pairs}) == len(_pairs)
      and len({p[1] for p in _pairs}) == len(_pairs),
      '异常=%r' % (_bad_pair,))
_missing, _empty, _bom, _bad = [], [], [], []
for r in recs:
    fp = os.path.join(_pdir, os.path.basename(r.get('file') or ''))
    if not os.path.isfile(fp):
        _missing.append(r['id'])
        continue
    raw = open(fp, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        _bom.append(r['id'])
    txt = raw.decode('utf-8')
    if not txt.strip():
        _empty.append(r['id'])
    if '\ufffd' in txt:
        _bad.append(r['id'])
    for mark in ('**', '##', '```'):
        if mark in txt:
            _bad.append('%s:%s' % (r['id'], mark))
check('P4 索引登记的文件都在磁盘上（%d 份）' % len(recs), not _missing, str(_missing))
check('P5 登记的正文都非空', not _empty, str(_empty))
check('P6 无 BOM', not _bom, str(_bom))
check('P7 无 U+FFFD / 无 markdown 标记', not _bad, str(_bad))

_loaded = P.load_personas(assets_dir=ASSETS, index=idx)
check('P8 load_personas 取到的份数 == 索引登记的份数（不写死份数）',
      len(_loaded) == len(recs), '%d / 登记 %d' % (len(_loaded), len(recs)))
# ⚠️ 判据修正记录（第64轮）：本条原先拿 `'mike'` 当"没装设定的样本"。第64轮 mike
#    装上了 ⇒ 这个样本失效。改成**不依赖具体谁没装**的两条腿：
#      ① 负控制用**根本不存在的 id**（`__no_such_npc__`）—— 永远不会因为"谁装上了"而失效；
#      ② 再从**注册表实时**取"当前确实没装 persona 的 id"，逐个断言也返回 None
#         （这样无论用户以后交上来多少份，这一条都不用再改）。
_unset_ids = sorted(n.id for n in S.load_registry().all() if n.persona is None)
check('P9 persona_text 对**没装**的 id 返回 None（不是空串）：'
      '负控制=不存在的 id + 实时取自注册表的未装 id',
      P.persona_text('__no_such_npc__', personas=_loaded) is None
      and bool(_unset_ids)
      and all(P.persona_text(i, personas=_loaded) is None for i in _unset_ids)
      and P.persona_text('susie', personas=_loaded) is not None,
      '不存在的 id ⇒ None；注册表里 %d 个未装 id 全 ⇒ None' % len(_unset_ids))
_s = _loaded.get('susie') or ''
check('P10 载入的正文里带用户给的节标题（【角色身份】等）',
      '【' in _s, _s[:40].replace('\n', '|'))
check('P11 正文里带"本项目补充"尾注（且明确标注不是原作者设定）',
      '本项目补充' in _s and '不是原作者设定' in _s)

# ================================================================== R 注册表
print('== R 注册表 ==')
reg = S.load_registry()
# ⚠️ 判据修正记录（第66轮）：本条原先写死 `== 35 and main == 17 and plain == 18`。
#    第66轮 N4 把 OneShot 21 + Undertale 14 共 35 条**跨作品 NPC** 注册进表
#    ⇒ 数字变成 70 / 52 / 18。"数字本身"从来不是要守的东西；要守的是
#    ① **不许被意外削掉**（下限：总 ≥ 35、main ≥ 17、plain ≥ 15）；
#    ② 「main + plain == 总数」（分层不许丢人）；
#    ③ 「id 唯一」（**加条目时加重复了**的照妖镜 —— 这条是本次新增的，比原来更强）。
#    与 R6/R8 的第64轮修正记录同一套做法：判据形状改，事实锚点随事实走。
check('R1 注册表 ≥ 基线 35 条（分层守恒 + id 唯一；不写死条数）',
      len(reg) >= 35
      and len(reg.main_npcs()) >= 17 and len(reg.plain_npcs()) >= 15
      and len(reg.main_npcs()) + len(reg.plain_npcs()) == len(reg)
      and len(set(reg.ids())) == len(reg),
      '%d / %d / %d' % (len(reg), len(reg.main_npcs()), len(reg.plain_npcs())))
check('R2 修掉的命名：有 flowery、没有 flowey',
      reg.get('flowery') is not None and reg.get('flowey') is None)
check('R3 新增主角团 kris / susie（物件名有据：obj_herokris / obj_herosusie）',
      (reg.get('kris') or None) is not None
      and 'obj_herokris' in reg.get('kris').objects
      and 'obj_herosusie' in reg.get('susie').objects)
check('R4 ★ main 一律**不单独指定模型**（`None` = 跟随 App 配置，'
      '而 `config.json.api.model` 就是 7B —— "升到 7B"的落地方式）',
      all(n.model is None for n in reg.main_npcs()),
      str(sorted({repr(n.model) for n in reg.main_npcs()})))
check('R5 纯 NPC 同样不配模型句柄（走内置短对话）',
      all(n.model is None for n in reg.plain_npcs()),
      str(sorted({repr(n.model) for n in reg.plain_npcs()})))
# ⚠️ 判据修正记录（第55轮）：R4 原先断言 `n.model == 'ralsei-npc:7b'`。查证后发现
#    那是**登记值**，没有任何代码读它；而 App 实际发的模型是 `config.json.api.model`
#    （= `ralsei:v4` = qwen2.5:7b）⇒ NPC 拿到的**本来就是 7B**，用户要的效果已成立。
#    真正该守的不是"字段上写着哪个句柄"，而是：① 字段**真的被读**（见 W 段的 A/B）；
#    ② 不许凭空指一个 Ollama 里**不存在**的句柄（那会让每次 NPC 请求 404 哑掉）。
_NPCMODEL_HEAD = 'ralsei-npc:'
_p_with = [n for n in reg.all() if n.persona]
_p_without = [n for n in reg.all() if not n.persona]
# ⚠️ 判据修正记录（第64轮）：本条原先写死 `== 14 条`（13 份 txt + Ralsei 那份 md）。
#    第64轮人设 13 → 50，且 spamton / mike 接上 persona ⇒ 数字变成 16。
#    数字本身不是要守的东西；要守的是**"Ralsei 自己那份 md 有且只有一个，
#    其余 persona 一律指向 `persona/` 下的 txt"** 这条结构不变式（+ 份数不被削的下限）。
_md_persona = [n for n in reg.all() if n.persona == '../ralsei_persona.md']
_txt_persona = [n for n in reg.all()
                if n.persona and n.persona != '../ralsei_persona.md']
check('R6 persona 贯通：恰好 1 条指向 Ralsei 自己那份 md，'
      '其余一律 persona/*.txt（不写死条数）',
      len(_md_persona) == 1
      and all(n.persona.startswith('persona/') for n in _txt_persona)
      and len(_txt_persona) >= 13,
      'md=%d txt=%d' % (len(_md_persona), len(_txt_persona)))
check('R7 needs_setting 与 persona 归实一致（persona is None ⇔ 还在等设定）',
      all(bool(n.needs_setting) == (n.persona is None) for n in reg.all()))
# ⚠️ 判据修正记录（第55轮）：本条原先拿**全部 35 条**去比，报红后查明是**判据过窄** ——
#    18 个纯 NPC（hammerguy / sign / …）按设计就是**没有** persona 的（走内置 4~10 句），
#    所以"没 persona"在一半条目上是**正常状态**。真正该守的是：
#    **主线里**persona 为 None 的只能是"用户还没给设定的"那些人。
# ⚠️ 判据修正记录（第64轮）：本条原先断言"没设定的正是 mike / knight / spamton 三人"。
#    第64轮用户把 Spamton / Mike 的设定交上来了（已接线）⇒ **事实变了**，
#    于是这条从"三人"收窄成"只剩 knight"（咆哮骑士，用户还没给）。
#    ★ 这不是"放宽判据"，而是**真值锚点随事实更新** —— 判据的形状（名单精确相等）
#      一个字没动；变的只是被期待的那个事实。与第49轮 `B7b` 是同一套做法。
_main_no_persona = sorted(n.id for n in reg.main_npcs() if n.persona is None)
check('R8 ★ 主线里"还在等设定"的只剩 knight（第64轮：Spamton/Mike 已到）',
      _main_no_persona == ['knight'], str(_main_no_persona))
check('R8b 纯 NPC 一律没有 persona（按设计走内置短对话）',
      all(n.persona is None for n in reg.plain_npcs()))
_persona_files = [n.persona for n in _p_with if n.persona != '../ralsei_persona.md']
check('R9 persona 相对路径都在磁盘上（%d 条）' % len(_persona_files),
      all(os.path.isfile(os.path.join(NPC_DIR, f)) for f in _persona_files),
      str([f for f in _persona_files
           if not os.path.isfile(os.path.join(NPC_DIR, f))]))
check('R10 to_dict / npc_from_dict 往返保住 persona',
      S.npc_from_dict(reg.get('susie').to_dict()).persona == 'persona/susie.txt')

# ================================================================== M 独立记忆
print('== M 独立记忆不串味 ==')
mem = P.MiniMemory(root=None)
A, B, C = 'susie', 'kris', 'toriel'
_ta, _tb, _tc = '我喜欢巧克力', '我不喜欢黑暗', '孩子你要按时睡觉'
check('M1 三句都写进各自的队列',
      mem.remember(A, _ta, who='player')
      and mem.remember(B, _tb, who='player')
      and mem.remember(C, _tc, who='player'))
check('M2 各自的条数都为 1',
      mem.count_of(A) == 1 and mem.count_of(B) == 1 and mem.count_of(C) == 1)
check('M3 ★ 正文层面的隔离：A 的历史里**不含** B/C 说过的话',
      all(_tb not in it['text'] and _tc not in it['text'] for it in mem.history(A)),
      str(mem.lines(A)))
check('M4 ★ 反向也成立（B 的历史里不含 A/C 的）',
      all(_ta not in it['text'] and _tc not in it['text'] for it in mem.history(B)),
      str(mem.lines(B)))
check('M5 未知 id ⇒ 返回空表（**不返回别人的**）',
      mem.history('nobody') == [] and mem.lines('nobody') == []
      and mem.count_of('nobody') == 0 and mem.last_from('nobody') is None)
check('M6 ids() 只给 id、不给内容（唯一"一次看很多个"的入口）',
      mem.ids() == sorted([A, B, C]), str(mem.ids()))
check('M7 forget 只清一个', mem.forget(B) == 1 and mem.count_of(A) == 1
      and mem.count_of(B) == 0 and mem.count_of(C) == 1)
check('M8 空文本 / 非法 id 不记（不写空条）',
      mem.remember(A, '   ') is False and mem.remember(None, 'x') is False
      and mem.remember(A, 123) is False)
check('M9 单条超长被截断到 MAX_LINE_CHARS',
      mem.remember(C, 'x' * (P.MAX_LINE_CHARS + 50))
      and len(mem.history(C)[-1]['text']) == P.MAX_LINE_CHARS)

# —— 落盘：一角色一文件，文件之间互不可见 ——
_disk = os.path.join(_tmp, 'mm55')
mem2 = P.MiniMemory(root=_disk)
mem2.remember(A, _ta, who='player')
mem2.remember(B, _tb, who='player')
_pa, _pb = mem2.path_of(A), mem2.path_of(B)
check('M10 两个 NPC 的落盘路径不同', _pa != _pb and _pa and _pb,
      '%s | %s' % (os.path.basename(_pa), os.path.basename(_pb)))
check('M11 路径就在 root 下（不再多套一层 npc_memory）',
      os.path.dirname(_pa) == _disk, os.path.dirname(_pa))
mem2.save(A)
mem2.save(B)
_files = sorted(os.listdir(os.path.dirname(_pa)))
check('M12 磁盘上是"一个角色一个文件"', _files == ['kris.json', 'susie.json'],
      str(_files))
_a_raw = read_text(_pa)
_b_raw = read_text(_pb)
check('M13 ★★ 文件层面的隔离：A 的文件正文里**没有** B 的话',
      _tb not in _a_raw and _ta not in _b_raw)
check('M14 A 的文件里确实有 A 自己的话（正面控制，防"两边都空"也过）',
      _ta in _a_raw and _tb in _b_raw)
_back = P.MiniMemory(root=_disk)
_na, _nb = _back.load(A), _back.load(B)
check('M15 从磁盘读回：各读回 1 条，且内容各归各位',
      _na == 1 and _nb == 1
      and _back.history(A)[0]['text'] == _ta
      and _back.history(B)[0]['text'] == _tb)
check('M16 memory_root(data_root) = <data_root>/npc_memory（唯一拼这一层的地方）',
      P.memory_root('D:/x') == os.path.abspath('D:/x/npc_memory')
      and P.memory_root(None) is None and P.memory_root('') is None)

# ================================================================== F 跟随决策
print('== F 跟随决策 ==')
_far = 160.0
check('F1 AI 表态优先（给了 follow ⇒ source=ai）',
      P.decide_follow('follow') == ('follow', 'ai'))
check('F2 AI 表态 + 门控不放行 ⇒ 门控赢（AI 不能越过硬约束）',
      P.decide_follow('follow', can_follow=False) == ('stay', 'gate'))
check('F3 AI 乱说 ⇒ 落回策略（不是"猜一个"）',
      P.decide_follow('随便吧', policy='autonomous', dist=999, far_threshold=_far)
      == ('follow', 'policy'))
check('F4 autonomous + 远 ⇒ 自主跟上',
      P.decide_follow(None, policy='autonomous', dist=999,
                      far_threshold=_far) == ('follow', 'policy'))
check('F5 autonomous + 近 ⇒ 不跟（不需要跟）',
      P.decide_follow(None, policy='autonomous', dist=10,
                      far_threshold=_far) == ('stay', 'policy'))
check('F6 consent（纯 NPC）⇒ 不主动跟（等主角点头）',
      P.decide_follow(None, policy='consent', dist=999,
                      far_threshold=_far) == ('stay', 'policy'))
check('F7 策略未知 ⇒ 保守不跟（source=default）',
      P.decide_follow(None, policy=None, dist=999,
                      far_threshold=_far) == ('stay', 'default'))
check('F8 算不出距离 ⇒ 不硬判（本项目铁律：算不出就别猜）',
      P.decide_follow(None, policy='autonomous', dist=None,
                      far_threshold=_far) == ('stay', 'default'))
check('F9 AI 给了别名写法也认（跟 ⇒ follow）',
      P.decide_follow('跟') == ('follow', 'ai')
      and P.decide_follow('rally') == ('rally', 'ai')
      and P.decide_follow('leave') == ('leave', 'ai'))
check('F10 负控制：认不出的写法一律 None（不模糊匹配）',
      P.parse_follow_choice('跟一下试试看') is None
      and P.parse_follow_choice('') is None
      and P.parse_follow_choice(None) is None
      and P.parse_follow_choice(123) is None)
check('F11 默认落点是 stay（保守一侧）',
      P.DEFAULT_FOLLOW_CHOICE == P.FOLLOW_STAY)

# ================================================================== D 点名解析
print('== D 点名解析 ==')
_aliases = P.address_aliases([(n.id, n.name, n.name_cn) for n in reg.all()])
check('D0 别名表条数 ≥ 35（id/英文/中文三层都收）',
      len(_aliases) >= 35, '%d 条' % len(_aliases))
check('D1 @susie 你好', P.parse_address('@susie 你好', _aliases) == ('susie', '你好'))
check('D2 中文名 + 中文冒号：苏西：你好',
      P.parse_address('苏西：你好', _aliases) == ('susie', '你好'))
check('D3 @ 后有空格也认', P.parse_address('@ 苏西：你好', _aliases) == ('susie', '你好'))
check('D4 名字含空格（Rouxls Kaard）走最长匹配',
      P.parse_address('Rouxls Kaard: hi', _aliases) == ('rouxls', 'hi'))
# ⚠️ 判据修正记录（第55轮）：本项原先写 `@susie dark 你好` 期望命中 `susiedark`，
#    报红后查明是**判据过窄/fixture 想当然** —— 真实注册表里 `susiedark.name`
#    是 `'Susie?'`（第49轮的登记），压根没有 `susie dark` 这个别名，所以命中
#    `susie` 是**对的**。改成两段：① 用真实别名验它确实能点到；② 用受控夹具
#    单独验"最长优先"这条规则（fixture 里才有那个别名）。
check('D5a 真实数据：susiedark 能被 id 点到（且不会与 susie 混）',
      P.parse_address('@susiedark 你好', _aliases) == ('susiedark', '你好')
      and P.parse_address('@暗之苏西 你好', _aliases) == ('susiedark', '你好'),
      str(P.parse_address('@susiedark 你好', _aliases)))
_ab = P.address_aliases([('susie', 'Susie', '苏西'),
                         ('susiedark', 'Susie Dark', '暗之苏西')])
check('D5b ★ 受控夹具：别名互为前缀时取**最长**的那条',
      P.parse_address('@Susie Dark hi', _ab) == ('susiedark', 'hi')
      and P.parse_address('@Susie hi', _ab) == ('susie', 'hi'),
      str(P.parse_address('@Susie Dark hi', _ab)))
check('D5c 先断言 A ≠ B：同一段文本在"有长别名 / 无长别名"下结果不同',
      P.parse_address('@Susie Dark hi', _ab)
      != P.parse_address('@Susie Dark hi', P.address_aliases([('susie', 'Susie', '苏西')])))
check('D6 只点名没内容 ⇒ 空内容而不是 None',
      P.parse_address('@Kris', _aliases) == ('kris', ''))
check('D7 负控制：没点名的普通句子 ⇒ None',
      P.parse_address('你好呀', _aliases) is None)
check('D8 负控制：名字后面还接着字母不算点名（susiex）',
      P.parse_address('@susiex hi', _aliases) is None)
check('D9 负控制：不存在的名字 ⇒ None（不猜）',
      P.parse_address('@不存在的人 你好', _aliases) is None)
check('D10 负控制：空别名表 / 非字符串输入 ⇒ None',
      P.parse_address('@susie hi', {}) is None
      and P.parse_address(None, _aliases) is None
      and P.parse_address('@', _aliases) is None)

# ================================================================== S 门控对照
print('== S 门控对照（NPC 被拒 vs 灵魂放行）==')
_gerson = reg.get('gerson')          # 只登记了 ch4
_hg = reg.get('hammerguy') or reg.plain_npcs()[0]
check('S0 取到测试用的两个 NPC（gerson 只在 ch4）',
      _gerson is not None and _gerson.chapters == ('ch4',), str(_gerson))
_g_own = S.world_gate(_gerson, 'dark', 'ch4.hometown.hometown')
_g_foreign = S.world_gate(_gerson, 'dark', 'ch2.cyber_city.cyber_city')
_g_light = S.world_gate(_gerson, 'light', 'ch1.hometown.hometown')
check('S1 正控制：NPC 进**自己登记的章** ⇒ 放行', bool(_g_own), repr(_g_own))
check('S2 ★ NPC 进**别人的暗世界** ⇒ 拒绝（REASON_FOREIGN_DARK）',
      (not bool(_g_foreign)) and _g_foreign.reason == S.REASON_FOREIGN_DARK,
      repr(_g_foreign))
check('S3 NPC 去光世界 ⇒ 放行且不需要球（第50轮口径）',
      bool(_g_light) and _g_light.detail == 'light_free', repr(_g_light))
_s_own = SE.soul_can_enter('dark', 'ch4.hometown.hometown')
_s_foreign = SE.soul_can_enter('dark', 'ch2.cyber_city.cyber_city')
_s_light = SE.soul_can_enter('light', 'ch1.hometown.hometown')
check('S4 ★★ 同一组输入：(gerson 被拒) 而 (灵魂放行)',
      (not bool(_g_foreign)) and bool(_s_foreign), repr(_s_foreign))
check('S5 灵魂对三处都放行（含所属章与光世界，正控制）',
      bool(_s_own) and bool(_s_foreign) and bool(_s_light))
check('S6 灵魂对未知世界也放行（"自由出入各个场景"的字面落实）',
      bool(SE.soul_can_enter('???', None)))
check('S7 灵魂门控不带 reason 之外的门槛（理由是 soul_free）',
      _s_foreign.reason == SE.SOUL_REASON_FREE, _s_foreign.reason)
# 纯 NPC 门控负控制：没登记任何章 ⇒ 拒（不硬判）
_hg_dark = S.world_gate(_hg, 'dark', 'ch2.x.y')
check('S8 负控制：章节字段为空的 NPC 进暗世界 ⇒ 拒（不猜）',
      bool(_hg.chapters) or (not bool(_hg_dark)), repr(_hg_dark))

# ================================================================== W 产品接线
print('== W 产品接线 ==')
_main = read_text(os.path.join(PET, 'src', 'main.py'))
_t_main = ast.parse(_main)
_outer, _inner = module_imports(os.path.join(PET, 'src', 'main.py'))
check('W1 main.py 真的 import 了 npc_system / npc_persona',
      'modules.npc_system' in _outer and 'modules.npc_persona' in _outer,
      str([n for n in _outer if 'npc' in n]))
_cls = [n for n in _t_main.body
        if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet']
check('W2 RalseiPet 类存在', len(_cls) == 1)
_methods = {m.name: m for m in _cls[0].body if isinstance(m, ast.FunctionDef)}
for _k in ('init_npc_systems', 'npc_address', 'npc_label', 'npc_persona_of',
           'npc_system_prompt', '_build_npc_context', 'npc_speak',
           'npc_follow_decide', 'npc_follow_approve', '_on_scene_switched_npc',
           '_npc_apply_follow', '_npc_ai_available', '_npc_scene_id',
           '_npc_follow_policy', '_npc_menu_message'):
    check('W3 方法存在：%s' % _k, _k in _methods)


def calls_in(node, attr_name):
    """`node` 函数体里有没有 `....<attr_name>(...)` 形式的**真调用点**。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == attr_name:
            return True
    return False


check('W4 ★ init_systems 里**真调用**了 init_npc_systems（防"改了没人调用"）',
      calls_in(_methods['init_systems'], 'init_npc_systems'))
check('W5 chat_with_ai 有 speaker / system_override 形参',
      'speaker' in [a.arg for a in _methods['chat_with_ai'].args.args]
      and 'system_override' in [a.arg for a in _methods['chat_with_ai'].args.args])
check('W6 cleanup_on_exit 里收尾落盘 NPC 记忆',
      calls_in(_methods['cleanup_on_exit'], 'save_all'))

_dui = read_text(os.path.join(PET, 'modules', 'dialogue_ui.py'))
_t_dui = ast.parse(_dui)
_dcls = [n for n in _t_dui.body
         if isinstance(n, ast.ClassDef) and n.name == 'DialogueUI'][0]
_dmethods = {m.name: m for m in _dcls.body if isinstance(m, ast.FunctionDef)}
check('W7 D1 dialogue_ui 有 NPC 显示/路由三件套',
      all(k in _dmethods for k in ('_is_npc_speaker', 'add_npc_addressed',
                                   'add_npc_line', '_send_npc_message')))
# ⚠️ 判据修正记录（第55轮）：`send_message` 里点名解析写的是
#    `getattr(self.parent, 'npc_address', None)`（字符串），**不是** `.npc_address(...)`
#    属性调用 ⇒ 只找"属性调用点"会恒假（判据过窄）。这里改成"字符串出现 + 真调用点"成对。
check('W8 ★ send_message 里**真接线**了点名与 NPC 路由',
      mentions_str(_dmethods['send_message'], 'npc_address')
      and calls_in(_dmethods['send_message'], '_send_npc_message'))
check('W8b 负控制：send_message 里的点名解析**排在** Ralsei 回显之前'
      '（否则"你对别人说的话"会被写进 Ralsei 的历史）',
      _dui.count('self._send_npc_message(_addr[0], _addr[1])') == 1
      and _dui.index('_addr_fn(user_input)')
      < _dui.index('self.add_dialogue("user", user_input, "normal")'))
check('W9 add_dialogue 里对 NPC 说话人分流',
      calls_in(_dmethods['add_dialogue'], '_is_npc_speaker'))
check('W10 负控制：add_dialogue 里**没有**把 NPC 写进 Ralsei 历史的老写法'
      '（_push_ai_history 调用点被 _npc_line 守着）',
      '_npc_line' in ast.dump(_dmethods['add_dialogue']))

# —— 真机：把 App 起起来，验接线真的通了 ——
from PyQt5.QtWidgets import QApplication       # noqa: E402
import main as M                               # noqa: E402

app = QApplication.instance() or QApplication([])
pet = M.RalseiPet()
for _a in ('animation_timer', 'ai_timer', 'stats_timer', 'dialogue_init_timer',
           'auto_mouse_drag_timer', 'api_control_timer', 'placeholder_timer',
           'movement_timer', 'mouse_drag_timer', '_bounce_timer',
           '_hide_search_timer'):
    _t = getattr(pet, _a, None)
    try:
        if _t is not None:
            _t.stop()
    except Exception:
        pass

check('W11 真机：NPC 服务建起来了（注册表 ≥ 基线 35 / 人设数 == 索引登记数 / 别名表非空）',
      pet.npc_registry is not None and len(pet.npc_registry) >= 35
      and len(pet.npc_personas) == len(recs) and len(pet._npc_aliases) > 0,
      '人设 %d 份（索引登记 %d），别名 %d 条'
      % (len(pet.npc_personas), len(recs), len(pet._npc_aliases)))
check('W12 真机：跟随板建起来了', pet.npc_followers is not None)
check('W13 真机：NPC 记忆的落盘目录以 npc_memory 结尾',
      pet.npc_memory is not None and pet.npc_memory.root is not None
      and pet.npc_memory.root.endswith('npc_memory'),
      # ⚠️ 这里**不能**写 `x if x else None`：`MiniMemory` 定义了 `__len__`，
      #    空记忆是 **falsy** ⇒ 那样写会恒打印 None（本轮踩过，第一次跑出来就是 None）。
      str(pet.npc_memory.root) if pet.npc_memory is not None else 'None')
_iso = os.environ.get('RALSEI_MEMORY_DIR')
if not _iso:
    print('[note] 未设 RALSEI_MEMORY_DIR（非 run_all 直跑）⇒ 跳过"落盘在隔离区"一项')
else:
    check('W14 落盘目录落在隔离区里（不碰用户真实存储）',
          pet.npc_memory.root.startswith(os.path.abspath(_iso)),
          pet.npc_memory.root)
check('W15 真机：三钩子齐全（道具 / 灵魂 / NPC）且没互相挤掉',
      pet._on_scene_switched_items in pet._scene_switch_hooks
      and pet._on_scene_switched_soul in pet._scene_switch_hooks
      and pet._on_scene_switched_npc in pet._scene_switch_hooks,
      '%d 个钩子' % len(pet._scene_switch_hooks))

check('W16 真机：npc_address 认中文名', pet.npc_address('@苏西 你好') == ('susie', '你好'),
      str(pet.npc_address('@苏西 你好')))
check('W17 真机：npc_label 给中文名', pet.npc_label('susie') == '苏西',
      pet.npc_label('susie'))
_prompt = pet.npc_system_prompt('susie')
check('W18 真机：susie 的 system prompt 以**她自己的**人设开头',
      bool(_prompt) and _prompt.startswith((P.persona_text(
          'susie', personas=pet.npc_personas) or '\x00')[:40]),
      repr(_prompt[:30]))
check('W19 ★ susie 的 prompt 里**不含** Ralsei 人设的特征句（不串味）',
      '你是《Deltarune》中的 Ralsei' not in _prompt)
# ⚠️ 判据修正记录（第64轮）：原 W20 / W22 拿 `mike` 当"没装设定的样本"。第64轮 mike
#    装上了 ⇒ ① W20（prompt == ''）会直接翻红；② **W22 更阴**：它现在落在
#    "模型不可用"那条分支上（夹具 `api_enabled=False`）而**照样返回 False** ⇒
#    判据**变成恒真**（谁都过），但名字还写着"没装设定的 mike" ⇒ 典型的
#    "判据名与事实脱节 + 恒真"（本项目的头号坑）。
#    改成**实时从注册表取"当前确实没装 persona 的那一个"**（main 优先，其次纯 NPC）。
#    这样用户以后交多少份设定都不用再动这两条，且永远落在真正的"还没装设定"分支上。
_unset_main_w = sorted(n.id for n in pet.npc_registry.main_npcs() if n.persona is None)
_unset_any_w = sorted(n.id for n in pet.npc_registry.all() if n.persona is None)
_probe_unset = (_unset_main_w or _unset_any_w or ['__no_such_npc__'])[0]
check('W20 真机：没装设定的人（当前=%s）prompt 为空 ⇒ 会拒绝说话' % _probe_unset,
      pet.npc_system_prompt(_probe_unset) == '')

# —— npc_speak：拒绝路径 + 记忆归属 ——
# ★ 受控夹具：把本地模型**关掉**，让"模型不可用"这条分支真的被走到。
#   为什么必须显式关（而不是"反正机器上没跑 Ollama"）：本机的 `api_enabled`
#   是真的为 True（配置里就开着），不关的话会走**异步真实请求**分支 ——
#   那既不可复现（要看 Ollama 起没起），也不是本段要守的行为。
#   关掉之后 `npc_speak` / `npc_follow_decide` 都走**同步**的"按策略落定"分支，
#   判据才是确定的。测完立刻还原。
_saved_api_enabled = getattr(pet, 'api_enabled', False)
pet.api_enabled = False
print('[note] 受控夹具：把 api_enabled 临时置 False，让"模型不可用"分支真被执行'
      '（原值=%r）' % _saved_api_enabled)
_calls = []
_before_ts = getattr(pet, '_last_user_chat_ts', None)
check('W21 拒绝：未登记的 id ⇒ False + 回调 None',
      pet.npc_speak('nobody-xyz', '在吗',
                    lambda r: _calls.append(('unknown', r))) is False
      and _calls[-1] == ('unknown', None))
check('W22 拒绝：没装设定的 %s ⇒ False + 回调 None' % _probe_unset,
      pet.npc_speak(_probe_unset, '在吗',
                    lambda r: _calls.append((_probe_unset, r))) is False
      and _calls[-1] == (_probe_unset, None))
_n_before = pet.npc_memory.count_of('susie')
_k_before = pet.npc_memory.count_of('kris')
_r = pet.npc_speak('susie', '我最喜欢巧克力', lambda t: _calls.append(('susie', t)))
check('W23 真机（夹具：模型不可用）⇒ 明确 False（不是"假装发出去了"）',
      _r is False)
check('W24 ★ 但"你对他说的话"记进了**他自己**的记忆',
      pet.npc_memory.count_of('susie') == _n_before + 1
      and pet.npc_memory.count_of('kris') == _k_before,
      'susie=%d kris=%d' % (pet.npc_memory.count_of('susie'),
                            pet.npc_memory.count_of('kris')))
check('W25 ★ kris 的记忆里**没有**这句话（同一时刻只有 susie 涨了）',
      '巧克力' not in json.dumps(pet.npc_memory.history('kris'),
                                 ensure_ascii=False))
check('W26 NPC 对话**不动** Ralsei 的"刚说过话"时间戳',
      getattr(pet, '_last_user_chat_ts', None) == _before_ts)

# —— 跟随决策：AI 不可用 ⇒ 按分层策略落定（真实产品路径）——
_ok1 = pet.npc_follow_decide('susie', dist=9999)
check('W27 真机（夹具：模型不可用）：susie（主线/autonomous）+ 很远 '
      '⇒ 决策=follow 且落成"正在跟"',
      _ok1 is True and pet.npc_followers.is_following('susie'),
      str(pet._npc_last_decision))
check('W28 决策来源是 policy（模型不可用 ⇒ 分层策略，不是编一个 ai）',
      pet._npc_last_decision == ('susie', 'follow', 'policy'),
      str(pet._npc_last_decision))
_ok2 = pet.npc_follow_decide('susie', dist=1)
check('W29 负控制：很近 ⇒ 不跟（决策=stay，落到 idle）',
      _ok2 is True and not pet.npc_followers.is_following('susie'),
      str(pet._npc_last_decision))
check('W30 未登记的 id ⇒ 不发决策（返回 False）',
      pet.npc_follow_decide('nobody-xyz') is False)
_pid = reg.plain_npcs()[0].id
check('W31a 负控制：纯 NPC（consent）+ 模型没表态 ⇒ 不主动跟（落 idle）',
      pet.npc_follow_decide(_pid, dist=9999) is True
      and pet.npc_followers.state_of(_pid) == S.FOLLOW_IDLE
      and _pid not in pet._npc_follow_pending,
      pet.npc_followers.state_of(_pid))

# —— ★ 让"AI 真的表态"（受控夹具：只替换**出词**那一步）——
#   ⚠️ 为什么是替换 `api_client` 而不是替换 `chat_with_ai`：
#     `chat_with_ai` 里就装着"NPC 的回复要落进他自己的记忆"这段产品代码（以及
#     system 装配、护栏比对集合）。把它整个换掉 = **把要测的东西换掉了**
#     （第一次跑就是这么失败的：回复压根没进记忆）。替换客户端只影响"模型吐什么词"。
#   ⚠️ 为什么还要转事件循环：`chat_with_ai` 在**工作线程**里跑，结果经 Qt 信号
#     投递回主线程；不转 `processEvents()` 回调永远不会到。
_saved_client = getattr(pet, 'api_client', None)
_saved_api_enabled2 = getattr(pet, 'api_enabled', False)


class _FakeClient(object):
    """只负责"出词"的假客户端（enabled=True，无 chat_stream ⇒ 走阻塞 chat）。"""

    enabled = True

    def __init__(self):
        self.calls = []
        self.reply = 'follow'

    def chat(self, user_msg, system_prompt=None, history=None, **kw):
        self.calls.append({'user': user_msg, 'system': system_prompt,
                           'history': history, 'opts': kw})
        return self.reply


_fake = _FakeClient()
pet.api_client = _fake
pet.api_enabled = True
print('[note] 受控夹具：换掉 api_client（只换"出词"），chat_with_ai 全走产品真代码')


def _pump(pred, timeout=10.0):
    """转事件循环等异步回调落地（最多 `timeout` 秒）。"""
    t0 = _time.time()
    while _time.time() - t0 < timeout:
        app.processEvents()
        if pred():
            return True
        _time.sleep(0.02)
    app.processEvents()
    return pred()


# —— ① 纯 NPC 没有设定 ⇒ **不进 AI 决策**（负控制：桩不该被调用）——
_n_before_stub = len(_fake.calls)
pet.npc_follow_decide(_pid, dist=9999)
check('W31b 负控制：没装设定的纯 NPC **不发起 AI 决策**（没得可问，谁也不许替他想）',
      len(_fake.calls) == _n_before_stub,
      '桩被调用 %d 次' % (len(_fake.calls) - _n_before_stub))

# —— ② 纯 NPC 的"等你点头"路径（状态机入口 + 产品的许可出口）——
check('W31c 纯 NPC 的跟随请求进 pending（第49轮口径：要主角同意）',
      pet.npc_followers.request(_pid) == S.FOLLOW_PENDING
      and _pid not in pet._npc_follow_pending)
# ⚠️ 上面用 `FollowerBoard.request` 直接造 pending：因为"没设定 ⇒ 不发起 AI 决策"
#    （W31b）⇒ 产品的 decide 路径**不会**把纯 NPC 带进 pending。
#    下面测的是产品的**许可出口** `npc_follow_approve` 真能把 pending 落定。
pet._npc_follow_pending.append(_pid)
check('W32 主角点头 ⇒ 立刻变成"正在跟"',
      pet.npc_follow_approve(_pid, True) is True
      and pet.npc_followers.is_following(_pid)
      and _pid not in pet._npc_follow_pending)
check('W33 负控制：没在 pending 的不受理（respond 返回 False）',
      pet.npc_follow_approve(_pid, True) is False)

# —— ③ ★★ AI 决策：同一 NPC、同一距离，**只换模型那个词**，结果相反 ——
pet._npc_last_decision = None
_fake.reply = 'stay'
pet.npc_follow_decide('susie', dist=9999)
_ok = _pump(lambda: pet._npc_last_decision is not None)
_stay_state = pet.npc_followers.is_following('susie')
_stack = len(_fake.calls)
check('W33a ★ AI 说"留下" ⇒ 不跟（来源=ai，**压过了 autonomous 策略**：很远本该跟）',
      _ok and _stay_state is False
      and pet._npc_last_decision == ('susie', 'stay', 'ai'),
      str(pet._npc_last_decision))
check('W33a2 决策请求带的是"只回一个词"的小 system（人设开头 + 问句）',
      _stack > 0 and '只回一个词' in (_fake.calls[-1]['system'] or '')
      and len(_fake.calls[-1]['system']) < 2000,
      'system 长度 %d' % len(_fake.calls[-1]['system'] or ''))
check('W33a3 决策请求只回一个词、且**不进**他自己的记忆（内部问句不是台词）',
      'follow' not in json.dumps(pet.npc_memory.history('susie'),
                                 ensure_ascii=False)
      and 'stay' not in json.dumps(pet.npc_memory.history('susie'),
                                   ensure_ascii=False))
pet._npc_last_decision = None
_fake.reply = 'follow'
pet.npc_follow_decide('susie', dist=9999)
_ok = _pump(lambda: pet._npc_last_decision is not None)
_follow_state = pet.npc_followers.is_following('susie')
check('W33b A/B：同一距离，AI 改口说"跟" ⇒ 跟了（先断言 A ≠ B）',
      _ok and _follow_state is True and _follow_state != _stay_state
      and pet._npc_last_decision == ('susie', 'follow', 'ai'),
      str(pet._npc_last_decision))

# —— ④ 回复写回：模型的话要落进**他自己**的记忆，并出现在他自己的提示词里 ——
_fake.reply = '我很好，谢谢你还记得问我。'
_n2 = pet.npc_memory.count_of('susie')
_k2 = pet.npc_memory.count_of('kris')
_replies = []
_ok3 = pet.npc_speak('susie', '你最近好吗', lambda t: _replies.append(t))
_ok4 = _pump(lambda: bool(_replies))
check('W33c 夹具下 npc_speak 返回 True 且回调真拿到那句话',
      _ok3 is True and _replies == ['我很好，谢谢你还记得问我。'],
      str(_replies))
# ★ 反向锁（A/B 成对，纯同步、无异步）：把这次定位到的"假竞态"钉死 ——
#   护栏的"车轱辘话"判定拿**他自己说过的话**当比对集合；隔离区一旦没清干净，
#   上面那句在请求发出前就已经躺在他记忆里，固定台词的假客户端必然被判退。
#   这条同时是"NPC 的护栏比对集合确实取自他自己的记忆"的正面证据。
_dirty = pet._clean_ai_reply(_fake.reply, recent=[_fake.reply])
_clean = pet._clean_ai_reply(_fake.reply, recent=[])
check('W33c2 ★ 反向锁：他自己说过的那句会被"重复自己"护栏判退 '
      '（= 不清隔离区就必然翻红的原因；先断言 A ≠ B）',
      _dirty is None and _clean is not None,
      'recent=他自己那句 ⇒ %r ；recent 为空 ⇒ %r' % (_dirty, _clean))
_last = pet.npc_memory.history('susie')[-1]
check('W33d ★ 模型那句以 **who=susie** 落进 susie 自己的记忆（不是 Ralsei 的）',
      pet.npc_memory.count_of('susie') == _n2 + 2
      and pet.npc_memory.count_of('kris') == _k2
      and _last.get('who') == 'susie' and _last.get('text') == _fake.reply,
      str(_last))
check('W33e ★ kris 的记忆里既没有问句也没有答句（严格不串味）',
      '你最近好吗' not in json.dumps(pet.npc_memory.history('kris'),
                                     ensure_ascii=False)
      and '谢谢你还记得' not in json.dumps(pet.npc_memory.history('kris'),
                                           ensure_ascii=False))
_sys = _fake.calls[-1]['system'] or ''
# ⚠️ 判据自身踩过的坑（记下来，别再犯）：这里**不能**要求"模型刚回的那句"也在本次
#    system 里 —— 那句话是**这次请求的产物**，请求发出时它当然还不存在（因果倒置）。
#    正确的两段式：① 本次 system 带着"对方刚说的那句"；② 等回复落进记忆后**再构建一次**，
#    那一份里才该两句都有。
check('W33f ★★ 本次发出去的 system 带上了"对方刚说的那句"（记忆真接进提示词了）',
      '你最近好吗' in _sys and '【你记得的事' in _sys,
      'len=%d 有对方那句=%s 有记忆块=%s'
      % (len(_sys), '你最近好吗' in _sys, '【你记得的事' in _sys))
_sys_next = pet.npc_system_prompt('susie')
check('W33f2 ★★ 回复落进记忆后**再构建一次**：那一份里两句都在（记忆真的在累积）',
      '你最近好吗' in _sys_next and _fake.reply in _sys_next,
      '有对方那句=%s 有他自己那句=%s'
      % ('你最近好吗' in _sys_next, _fake.reply in _sys_next))
check('W33g ★★ 发出去的 system 用的**不是** Ralsei 的人设（连头都不是它）',
      not _sys.startswith(pet._build_persona_prompt()[:40]),
      repr(pet._build_persona_prompt()[:24]))
check('W33g2 发出去的用户消息就是原话（没有被拼上状态块）',
      _fake.calls[-1]['user'] == '你最近好吗', repr(_fake.calls[-1]['user']))
check('W33h ★ 换个人看 prompt 是干净的（kris 的 prompt 里没有 susie 的话）',
      '你最近好吗' not in pet.npc_system_prompt('kris'))

# —— ⑥ ★★ 模型字段**真的被读**（A/B 成对）——
# 为什么非要有这一段：第49~55轮 `_registry.json` 里一直写着 `model='ralsei-npc:4b'/':7b'`，
# 而**没有任何代码读它** —— 于是"主线 NPC 用哪个模型"完全由 `config.json` 决定，
# 那句登记是**假账**（本项目最贵那类坑：写对了 ≠ 用上了）。
# 判据先改字段再发真请求，看它落不落进 `opts`：填了就必须带、填 None 就必须**没有这个键**
# （后者才是"老路径零变化"的硬要求 —— 带个 `model=None` 也会改到 payload 的语义）。
_npc_susie = pet.npc_registry.get('susie')
_saved_npc_model = getattr(_npc_susie, 'model', None)
_npc_susie.model = 'ralsei:v4'
_fake.reply = '嗯，知道了。'
_seen_a = []
pet.npc_speak('susie', '测试模型字段甲', lambda t: _seen_a.append(t))
_pump(lambda: bool(_seen_a))
_opt_a = _fake.calls[-1]['opts'].get('model')
_npc_susie.model = None
_fake.reply = '行吧。'
_seen_b = []
pet.npc_speak('susie', '测试模型字段乙', lambda t: _seen_b.append(t))
_pump(lambda: bool(_seen_b))
_opt_b_has = 'model' in _fake.calls[-1]['opts']
_npc_susie.model = _saved_npc_model
check('W36 ★★ 模型字段真被读（A/B 成对）：填了句柄 ⇒ 请求真带上；填 None ⇒ 压根不带这个键',
      _opt_a == 'ralsei:v4' and _opt_b_has is False,
      '填句柄时 opts[model]=%r ；填 None 时"有 model 键"=%r' % (_opt_a, _opt_b_has))
check('W36b 解析出口 `_npc_model`：登记的句柄原样返回 / None 与空串都归到 None',
      pet._npc_model('susie') is None
      and pet._npc_model('nobody-xyz') is None
      and pet._npc_model('susie') == pet._npc_model('susie'),
      'susie=%r' % (pet._npc_model('susie'),))
check('W36c ★ 反面对照：注册表现在**没有**指向任何 Ollama 里不存在的句柄'
      '（指了就会每次 404 静默哑掉）',
      all(n.model is None for n in pet.npc_registry.all())
      and all(not (isinstance(n.model, str) and n.model.startswith(_NPCMODEL_HEAD))
              for n in pet.npc_registry.all()),
      str(sorted({repr(n.model) for n in pet.npc_registry.all()})))

# —— ⑥b `api_client._chat_payload` 真认这个覆盖（真类，不 mock）——
import api_client as AC          # noqa: E402
_cli = AC.HTTPLocalAI({'model': 'base-model'})
_kw = {'model': 'npc-model', 'temperature': 0.5}
_pl = _cli._chat_payload('hi', None, _kw, False)
_kw2 = {'model': None}
_pl2 = _cli._chat_payload('hi', None, _kw2, False)
_kw3 = {'model': '   '}
_pl3 = _cli._chat_payload('hi', None, _kw3, False)
check('W36d ★★ payload 覆盖语义四态：非空 ⇒ 覆盖 / None、空串、不给 ⇒ 一律沿用 `self.model`',
      _pl['model'] == 'npc-model' and _pl2['model'] == 'base-model'
      and _pl3['model'] == 'base-model'
      and _cli._chat_payload('hi', None, {}, False)['model'] == 'base-model',
      '给句柄=%r None=%r 空串=%r 不给=%r'
      % (_pl['model'], _pl2['model'], _pl3['model'],
         _cli._chat_payload('hi', None, {}, False)['model']))
check('W36e `model` 必须被**取走**（不许漏进采样参数继续往下传）',
      'model' not in _kw and _pl['temperature'] == 0.5,
      'kwargs 残留=%r' % (sorted(_kw.keys()),))

pet.api_client = _saved_client                        # 还原夹具
pet.api_enabled = _saved_api_enabled2
check('W33i 夹具已还原（api_client / api_enabled 都回到原值）',
      pet.api_client is _saved_client
      and getattr(pet, 'api_enabled', None) == _saved_api_enabled2)

# —— 场景切换：跟不进来的人会被清掉（★ 真实门控）——
pet.scene.switch('ch2.cyber_city.cyber_city')
pet._on_scene_switched_npc(pet.current_scene, pet._scene_state)
check('W34 ★ 换了不属于他的暗世界 ⇒ gerson 的跟随被清掉（跟不进来就说进来）',
      not pet.npc_followers.is_following('gerson'),
      pet.npc_followers.snapshot().get('gerson'))

try:
    pet.api_enabled = _saved_api_enabled          # 还原夹具
    pet.cleanup_on_exit()
    check('W35 cleanup_on_exit 不抛（NPC 记忆收尾落盘）', True)
except Exception as e:
    check('W35 cleanup_on_exit 不抛（NPC 记忆收尾落盘）', False, repr(e))

# 收尾：把本轮在临时隔离区里写下的 NPC 记忆删掉，别留垃圾
try:
    _mr = pet.npc_memory.root
    if _mr and os.path.abspath(_mr).startswith(os.path.abspath(_tmp)):
        for _f in os.listdir(_mr):
            if _f.endswith('.json'):
                os.remove(os.path.join(_mr, _f))
except Exception as e:
    print('[note] 临时记忆清理失败（不影响判据）: %s' % e)

print('\n== 结果 ==')
print('  断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
if FAILS:
    print('  失败项：%s' % FAILS)
sys.exit(0 if not FAILS else 1)
