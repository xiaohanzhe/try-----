# -*- coding: utf-8 -*-
"""NPC「自由生活」的策略层 —— **零依赖**（顶层只 import 标准库，零函数内 import）。

用户口径（逐字）：

> 「我希望他们是**生活在这**而不是我走到哪他们加载到哪……我希望他们是**能对场景有反应**的，
>  比如 sans 来到 oneshot 会吐槽，这地方真黑之类的话……之后不同世界的人一开始也不认识，
>  所以他们也是**循序渐进的熟悉起来**，当然，**面对不同版本的自己熟悉的会更快**……
>  还有，**怪物们之间没有身份标识说，你是哪个世界观的，所以那需要自己判断**」

本模块只回答四件事，**全部是纯策略（不碰 IO、不碰 Qt、不碰模型）**：

1. `scene_traits()` —— "这地方是什么样"（给"对场景有反应"用）。★ **有出处**：
   只从场景 id / 内部名 / 资源名的**文本**里找关键词，无命中就返回空 —— **不猜**。
2. `Bonds` —— NPC 两两之间的**熟络度**（per-pair、**对称**、**渐增**）。
3. `transmit()` —— **信息传播**：把 A 记忆里的某条，**以 A 的署名**记进 B 的记忆。
4. `LifeLoop` —— 自主开口的节拍（该谁开口 / 现在该不该开口）。
5. `pick_line()` —— 纯 NPC 的**零模型**自发台词挑选（从 `_dialogue.json` 的池子里取，不重复）。
6. `presence_hint()` / `where_of()` —— **在场者感知**（第86轮）：此刻这里还有谁 + 粗方位。
   ★★ 只给"叫什么、大概在哪个方位" —— **绝不**注入作品归属 / 版本 / id / 人设。

---------------------------------------------------------------- 三条设计纪律

★ **为什么另起一个模块，而不是塞进 `npc_system`**：
  `npc_system` 回答的是"**能不能进这个世界**"（政策 / 门控），是**许可**问题；
  这里是"**进去了之后怎么过日子**"（反应 / 熟络 / 传话），是**行为**问题。
  两个问题混在一个模块里，改一个必动另一个（本项目最贵的坑）。

★ **为什么不复用 `companion_roster.ChatScheduler`**：
  后者的名册主键是 `Companion`（= 跟着主角走的那几位，带槽位 `12+slot*12` 滞后），
  这里的主键是 `NpcDef`（= 世界里的居民）。把 `NpcDef` 硬塞成 `Companion`
  会造出一批"**不是伙伴的伙伴**"，反而把两个概念搅在一起。
  ⇒ 所以这里**平行实现**同一组不变量（不并发 / 相邻两句不同人 / 失败必解锁 / 反活锁），
    并在 `check73` 里对这四条**逐条**判据 —— 判的是"**性质相同**"，不是"代码复用"。

★ **信息传播 ≠ 共享记忆**（与 `npc_persona.MiniMemory` 的"一角色一份物理分开"不冲突）：
  `MiniMemory` 在**接口层面**就不给 `all()` / `everyone()`，所以"忘了过滤导致串味"写不出来。
  但"**A 把自己说的这句话告诉 B**"是一条**合法的、显式的**动作 —— 它就是
  `dst.remember(text, who=src)`。B 记下的是"**A 说过这句话**"（带署名），
  **不是**"我知道了这件事"（无署名）。两者在存储上仍是**两份物理分开的数据**。
"""

import collections
import re

# ---------------------------------------------------------------- 场景特质

#: 与 `assets/npc/_crossworld.json#scene_traits.traits[*].id` **逐字镜像**（check73 D 段钉住）。
TRAITS = ('dark', 'ruined', 'bright', 'crowded', 'quiet', 'cosmic')

#: 特质 → 中文词（= 契约里的 `words`，逐字镜像）。给"显示 / 拼提示"用。
TRAIT_WORDS_CN = {
    'dark': ('黑', '暗', '没有光', '伸手不见五指'),
    'ruined': ('破败', '荒废', '废墟', '残破', '没人住'),
    'bright': ('亮', '明亮', '刺眼'),
    'crowded': ('人多', '热闹', '挤'),
    'quiet': ('安静', '死寂', '没声音'),
    'cosmic': ('宇宙', '星空', '失重', '太空'),
}

#: 特质 → **英文 id 令牌**（真正用来匹配的）。
#: ★ 为什么另开一张表而不是复用中文词：场景 id 是英文（`ch3_dark_cave` / `castle_town`），
#:   中文词匹配不上。两张表各司其职（中文=展示，英文=匹配），互不替代。
#: ★★ 令牌**必须真的能在现网场景 id 里命中**（`check73` D1 逐条验）：
#:   "从来不会命中"的令牌是在**虚假宣传一项不存在的能力**。
#:
#: ★★★ **第77轮：`ruined` 从预留转正**。
#:   第73轮时它与 `bright`/`cosmic` 一样是**零命中**（当时 `_index.json` 只有 Deltarune，
#:   而 Deltarune 的房间名里一个 `ruin` 都没有）。
#:   第77轮把 UT / 黄魂 迁入产品索引后，**实测命中 35 处**
#:   （`ut.rooms.room_ruins1` … `room_ruins7A` 等，UT 的「废墟」区域）⇒ 能力**真的有了**。
#:   ⇒ 用户点名的「**破败**这类的词也需要有能力识别」**现在兑现了一部分**（UT 侧）。
#:   ⚠️ **只把实测命中的 `ruin`/`ruined` 转正**；`broken`/`wreck`/`abandon`/`desolate`
#:     实测仍是 0 命中（Deltarune 与 UT/黄魂 都没有这种命名）⇒ **留在预留表**
#:     —— 这正是 D1「本位令牌逐条 ≥1 命中」那条判据在把守的：
#:     **第一版把它们一起转正了，D1 立刻报红**（`[('ruined','broken'), …]`）。
#:
#: ★★★ **第80轮：OneShot 263 场景迁入，又触发一次「预留→转正」**（同第77轮机制）。
#:   实测新增命中的预留令牌 **4 条**，但**只有 2 条语义正确、可转正**：
#:     · `sun`  → `bright`  —— `oneshot.rooms.Sunroom`（阳光房）/ `basement_after_sun`
#:               确实"有阳光 ⇒ 明亮"，语义**对** ⇒ **转正**。
#:     · `sky`  → `cosmic`  —— `oneshot.rooms.Red_sky` / `POSTGAME_RED_SKY`
#:               是"天空"，有"空旷/宇宙感"，语义**可接受** ⇒ **转正**。
#:   ⚠️ 另 2 条**语义错位，拒绝转正，反而移入 `BANNED_TOKENS`（`OMITTED` 类）**：
#:     · `square` → `crowded` —— 命中的是 `House 4 - squares`（**方块房**）、
#:                  `SQUARES BE GONE`（一个**谜题名**）⇒ 那是**几何形状**，不是"广场"。
#:     · `street` → `crowded` —— 命中的是 `Elevator Street` / `Vendor Street`（**街名**）
#:                  ⇒ 是**路名**，不代表"人多热闹"。
#:   ★ 这两条判法**和第73轮 `room` / `light` 一模一样**（"词本身能命中，但含义不是我们要的"
#:     ⇒ `OMITTED`，靠"不在任何令牌表里"挡，匹配规则挡不住）——
#:     **不许为了让判据变绿就把它们硬塞进本位表**（那才是真的"虚假宣传"）。
#:   ★ `sunny`/`bright`/`daylight`/`market`/`plaza`/`space`/`moon`/`void`/`galaxy`/`orbit`/`cosmic`
#:     当时实测**仍是 0 命中** ⇒ 继续留在预留表（第80轮口径）。
#:
#: ★★★ **第99轮：Outertale 244 场景迁入，第三次触发「预留→转正」**（同第77/80轮机制）。
#:   实测新增命中的预留令牌 **2 条**，两条**命运相反**：
#:     · `plaza` → `crowded` —— 命中 `outertale.core.a_plaza`（**Aerialis 的商场广场**）。
#:              原作实证（`index-BIKawlPs.js`）：该房 `preload` 含 **`amShop`**、
#:              `layers` 含 **`iooABurgies`**（BURGIE 的店招牌）、`score={music:"mall"}`，
#:              Papyrus 台词逐字「**THAT'S WHERE BURGIE'S SHOP IS.**」
#:              ⇒ 是"**有店有人的公共广场**"，与 `town` 同一档 ⇒ 语义**正确** ⇒ **转正**。
#:   ⚠️ · `void` → `cosmic` —— 命中 `outertale.special._void`，但**语义错位**：
#:              该房原作定义是**一间小卧室**（`region` 只有一个出生点 (160,120)、
#:              `interacts` = `trivia` 的 **bed / plushie / flowers / computer**、
#:              `score={music:"rain"}`、叙述「This room belonged to someone who spent a
#:              long time doing one specific thing.」）⇒ 是"**私密小屋**"，
#:              **不是**"很空旷的、宇宙一样的地方" ⇒ **拒绝转正，反而封禁**（`OMITTED`）。
#:   ★ 判法与第80轮 `square`/`street`、第73轮 `room`/`light` **同款**。
#:   ★ 复算产物：`code-quality-audit/第99轮-睡觉惊醒与场景系统/_evidence/`（原始 bundle 仍在盘）。
#:   ★ 迁入后仍**真零命中**的预留令牌：`sunny`/`bright`/`daylight`/`market`/`space`/
#:     `moon`/`orbit`/`cosmic`/`galaxy`/`cellar`/`underground`/`broken`/`wreck`/
#:     `abandon`/`desolate` ⇒ **继续留在预留表**（如实登记缺口，不硬塞）。
TRAIT_TOKENS = {
    'dark': ('dark', 'cave', 'basement'),
    'ruined': ('ruin', 'ruined'),
    'bright': ('sun',),
    'crowded': ('town', 'city', 'shop', 'plaza'),
    'quiet': ('home', 'house', 'forest', 'grave', 'church', 'library'),
    'cosmic': ('sky',),
}

#: ★ **跨作品预留**令牌：现网 **0 命中**（`check73` D2 反过来验"确实 0 命中"，
#: 防有人拿它们混进本位表凑数字）。等 `hub:ot` / `hub:os` 的场景进大图后启用。
#:
#: ★★ 这张表本身就是一条**实证结论**，必须留着 —— 用户除了「这地方真黑」还点名
#:   「**破败**这类的词也需要有能力识别」。第80轮（OneShot 迁入）后实测：
#:   **`bright` 的 `sunny`/`bright`/`daylight`、`cosmic` 的 `space`/`moon`/`galaxy`/`orbit`/`cosmic`
#:   仍是 0 命中**；`crowded` 的 `market` 也仍 0 命中。
#:   ★ 第99轮（Outertale 迁入）后复算：上列令牌**依旧全 0 命中**（`plaza` 已转正、
#:     `void` 已封禁，双双离开本表）⇒ **仍是如实登记缺口**，
#:     而不是把某个词硬塞进本位表让判据看起来"覆盖了明亮 / 宇宙"。
#:   （注：`ruin`/`ruined` 第77轮、`sun`/`sky` 第80轮、`plaza` 第99轮**确已转正**，
#:     因为语义正确且实测有命中 —— 见上表注释。）
TRAIT_TOKENS_RESERVED = {
    'dark': ('cellar', 'underground'),
    'ruined': ('broken', 'wreck', 'abandon', 'desolate'),
    'bright': ('sunny', 'bright', 'daylight'),
    'crowded': ('market',),
    'cosmic': ('space', 'orbit', 'moon', 'cosmic', 'galaxy'),
}

#: ⚠️ **永久禁用表**：令牌 → 禁用理由。★ 两种禁法的**挡法不同**，判据也分开验：
#:
#:   · `'SUBSTRING'` —— 词中假命中。靠 `_token_hits()` 的**边界规则**挡住
#:     （`check73` D4 负控制：直接证明匹配规则会拒绝它）。
#:   · `'OMITTED'`   —— 语义错位（词本身能命中，但含义不是我们要的那个）。
#:     靠"**不在任何令牌表里**"挡住（`check73` D5：证明它没被偷偷加回某张表）。
#:     ⚠️ 这类**不能**靠匹配规则挡 —— `_token_hits('room', 'ch1.kris_room')` 是 `True`，
#:       规则拦不住它，只能靠"没人往表里写"。
BANNED_TOKENS = {
    'ash': 'SUBSTRING',     # 会命中 `forest_afterthrash2`（`afterthrash` 里的 `ash`）
    'night': 'SUBSTRING',   # 会命中 `church_knightclimb`（`knight` 里的 `night`）
    'room': 'OMITTED',      # Deltarune 的**命名前缀**：所有 `room_*` 都是房间，当"安静"用会全表误判
    'light': 'OMITTED',     # `lightworld*` 是**光世界**（一个世界名），不是"光线充足"
    'square': 'OMITTED',    # ★ 第80轮：OneShot 里 `squares` 是**几何方形**（`House 4 - squares`
                            #   / 谜题 `SQUARES BE GONE`），不是"广场" ⇒ 不能当 `crowded` 用
    'street': 'OMITTED',    # ★ 第80轮：OneShot 里 `Elevator Street`/`Vendor Street` 是**街名**，
                            #   不代表"人多热闹" ⇒ 不能当 `crowded` 用
    'void': 'OMITTED',      # ★ 第99轮：Outertale 的 `_void` 是**一间小卧室**
                            #   （床/玩偶/花/电脑 + `music:"rain"`），不是"空旷宇宙"
                            #   ⇒ 不能当 `cosmic` 用。该词曾被列在 `cosmic` 预留表里
                            #   （第73/80轮），第99轮实测 1 命中后**拒绝转正并封禁**
                            #   —— 与 `square`/`street` 同款判法。
}


def banned_tokens(kind=None):
    """被禁的令牌（`kind` 给了就只取那一类）。→ 稳定序的 tuple。"""
    items = BANNED_TOKENS.items()
    if kind is not None:
        items = [(k, v) for k, v in items if v == kind]
    return tuple(sorted(k for k, _ in items))


def _components(text):
    """把场景文本切成**分量**（非字母数字都是分隔符）。`''` ⇒ `[]`。

    ★ 为什么要切分量而不是直接 `token in text`：直接子串匹配会造出
      `'ash' in 'afterthrash2'`、`'night' in 'knightclimb'` 这类**假命中**（实测踩到）。
    """
    if not isinstance(text, str) or not text:
        return []
    out = []
    cur = []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append(''.join(cur))
            cur = []
    if cur:
        out.append(''.join(cur))
    return out


def _token_hits(token, text):
    """**英语复合词边界**规则：令牌必须等于某个分量，或落在某个分量的**词首 / 词尾**。

    · `shicave` endswith `cave` ✅（真洞窟）
    · `darkworld` startswith `dark` ✅（暗世界）
    · `afterthrash2` —— `ash` 在词中 ⇒ ❌（不误判）
    · `knightclimb`  —— `night` 在词中 ⇒ ❌（不误判）
    """
    if not token:
        return False
    for c in _components(text):
        if c == token or c.startswith(token) or c.endswith(token):
            return True
    return False

#: 特质 → 一句**中性**中文描述（给模型"这地方是什么样"，**不含台词示范**：
#: 用户口径「可逐字搬走的固定例句」是失真头号来源，所以这里只给"环境事实"，
#: 怎么吐槽由模型按着人设自己说）。
TRAIT_DESC = {
    'dark': '很暗，几乎没什么光',
    'ruined': '破败荒废，看得出很久没人打理',
    'bright': '很亮，光线充足',
    'crowded': '人多、热闹',
    'quiet': '安静，没什么人',
    'cosmic': '在外面看，是很空旷的、宇宙一样的地方',
}

#: 一个场景最多报几个特质（多了提示词会变成流水账）。
MAX_TRAITS = 3


def _scene_text(scene_id, extra_text=None):
    """把"用来推断特质的文本"合成一条串。非法输入 ⇒ `''`（**不抛**）。"""
    bits = []
    if isinstance(scene_id, str) and scene_id.strip():
        bits.append(scene_id)
    if isinstance(extra_text, str) and extra_text.strip():
        bits.append(extra_text)
    return ' '.join(bits)


def _match_terms(trait, use_reserved=False):
    """某个特质的全部**匹配词**：本位英文令牌 (+ 预留英文令牌) + 中文词。

    ★ 中文词（`TRAIT_WORDS_CN`）也参与匹配：场景 id 是英文，但**场景显示名 / 内部名
      可能是中文**，宿主通过 `extra_text` 传进来时应该能命中。
      它们**不**参与"本位令牌必须命中"的那条判据（那是英文令牌的责任）。
    ★★ 第80轮起：**`OMITTED` 类禁词（`BANNED_TOKENS`）在此处被硬过滤掉** ——
      它们是"能命中但语义错位"的词（`room`/`light`/`square`/`street` …），
      之前只靠"没人往表里写"挡；现在加一道**运行期闸**，即使有人误写进表也进不了匹配。
      （`check73` D5 仍验"没被偷偷加回表里"；本条只是多一层不依赖人自觉的保护。）
    """
    banned = set(banned_tokens('OMITTED'))
    terms = [w for w in TRAIT_TOKENS.get(trait, ()) if w not in banned]
    if use_reserved:
        terms += [w for w in TRAIT_TOKENS_RESERVED.get(trait, ()) if w not in banned]
    terms += [w for w in TRAIT_WORDS_CN.get(trait, ()) if w not in banned]
    return terms


def trait_hits(scene_id, extra_text=None, use_reserved=False):
    """→ `{trait: [命中词, ...]}`（**只含真命中的**）。可解释：能说清凭什么这么判。

    `use_reserved=True` 时把**跨作品预留**令牌一起算进去（现网用不到，留给 OT/OS 场景面）。
    """
    text = _scene_text(scene_id, extra_text)
    if not text:
        return {}
    out = {}
    for t in TRAITS:
        hit = [w for w in _match_terms(t, use_reserved) if _token_hits(w, text)]
        if hit:
            out[t] = hit
    return out


def scene_traits(scene_id, extra_text=None, max_traits=MAX_TRAITS, use_reserved=False):
    """一个场景的特质列表（按 `TRAITS` 顺序，**稳定**）。无命中 ⇒ `()`（**不猜**）。

    `max_traits=None` / 非法 ⇒ 用 `MAX_TRAITS`；`<= 0` ⇒ 返回 `()`。
    """
    hits = trait_hits(scene_id, extra_text, use_reserved=use_reserved)
    if not hits:
        return ()
    ordered = [t for t in TRAITS if t in hits]
    if max_traits is None:
        cap = MAX_TRAITS
    else:
        try:
            cap = int(max_traits)
        except (TypeError, ValueError):
            cap = MAX_TRAITS
    if cap <= 0:
        return ()
    return tuple(ordered[:cap])


def trait_hint(traits):
    """把特质列表变成**一行**环境提示。空/非法 ⇒ `''`（**不产空块**）。"""
    if not traits:
        return ''
    descs = [TRAIT_DESC[t] for t in traits if t in TRAIT_DESC]
    if not descs:
        return ''
    return ('【你周围】这里' + '，'.join(descs)
            + '。（这是环境事实，不是台词 —— 按你自己的性子决定要不要理它，别逐条念。）')


# ---------------------------------------------------------------- 空间认知（第113轮j）

#: 场景标签的层级分隔符：`区 · 场景名`。
PLACE_SEP = ' · '

#: 区名**自己就带** `PLACE_SEP` 时用的替代连接符（第113轮j）。
#: ★ 为什么需要它：OneShot 的区名是 `主线 · 家/塔/终局`，已经占用了中点。
#:   再拼场景名就有两种坏结果 —— 要么三段（`主线 · 家/塔/终局 · FINALE`，
#:   读者分不清哪层是哪层），要么干脆不拼、把末级地名丢掉（`FINALE` 没了，
#:   模型就不知道这是终局场景）。换一个分隔符两头都能保住。
PLACE_JOIN_ALT = ' — '

#: 这些**区名**对模型没有信息量（它们是我们的容器，不是作品里的地方）⇒ 不显示。
#: ★ 为什么用白名单式的"已知填充名"而不是"短于 2 字就不要"：
#:   「桌面」只有 2 个字但是真地名，按长度判会把它误删。
PLACE_FILLER = frozenset(('全部房间', 'unzoned', '未分区', 'unknown', '未知'))


#: 这些**区 id** 是我们自己的系统 / 演出 / 调试区，不是作品里的地方 ⇒
#:   **不给"去处"候选**（位置标签照旧显示，人在里面也要知道自己在哪）。
#: ★ 与 `PLACE_FILLER` 分工：那个按**区名**过滤（容器叫「全部房间」），
#:   这个按 **id** 过滤 —— `系统与演出` 读起来像真地名，按名字判会漏；
#:   而 id 是索引结构的一部分、不是文案，按 id 判不会误伤真地名。
#: ★ 实测：`ch5.system` = `plat_lab` / `rhythmgame_editor` / `shop_ch5` 三个**调试房**，
#:   不拦的话 NPC 会建议「那要不去系统与演出那家商店」—— 把人送进测试关。
PLACE_SKIP_AREA_IDS = frozenset(('system', 'unzoned', 'test', 'debug', 'tmp'))


def place_container(area_name):
    """这个**区名**是不是我们自己的容器？⇒ True 表示「不是作品里的地方」。

    ★ 为什么不能只做 `area_name in PLACE_FILLER`：索引里同一类容器有两种写法，
      带括注的那种（`未分区（废弃/调试/演示）`）精确匹配不上。第113轮j 全量普查
      因此漏判 **26 条**，模型会在 prompt 里读到「未分区（废弃/调试/演示） · Bedroom」
      —— 它看到的是我们的目录结构，不是作品里的地名。
    ★ 只剥**一层**括注取主干：多剥会把 `城堡镇（废墟）` 也误判成容器。
    """
    s = str(area_name or '').strip()
    if not s:
        return False
    if s in PLACE_FILLER:
        return True
    core = s.split('（', 1)[0].split('(', 1)[0].strip()
    return bool(core) and core in PLACE_FILLER

def room_word(raw):
    """把**原作房间 id** 变成能读的词：`rm_steamworks_29` → `steamworks 29`。

    ★ 为什么不直接给模型看 `rm_steamworks_29`：全小写 + `rm_` 前缀，模型读到多半会
      照抄成"我住在 rm_steamworks_29" —— 比不给还糟。
    ★ 为什么这样改不算编造：只做**去前缀 + 下划线转空格**，`steamworks`、`29` 都是原作写的，
      一个词都没换。中文名拿不到时才走这条（黄魂 1251 间 / UT 没有中文名，
      OneShot 是英文原题，Deltarune 有中文名）。
    ★ 只取末段：`uty.rooms.rm_steamworks_29` 的前两段是**我们的登记结构**，不是作品里的名字。
    """
    s = str(raw or '').strip()
    if not s:
        return ''
    s = s.rsplit('.', 1)[-1]
    # ★★ 前缀必须**循环剥**，而且已知前缀是这几个：
    #   `rm_`   = 黄魂 / UT 的房间
    #   `room_` = Deltarune 的房间（但它常常**套着**下一层：`room_dw_…`）
    #   `dw_`   = 暗世界（dark world）· `lw_` = 光世界（light world）
    # 第113轮j 只剥一层、漏了 dw_/lw_ ⇒ 模型会读到 `dw garden video`。
    # 这些**全是我们的命名**，不是作品里的词，露出来等于把内部结构塞给模型。
    # 循环最多剥 4 层（前缀表长度），防止某个畸形名字把循环拖成死循环。
    _PREFIXES = ('rm_', 'room_', 'dw_', 'lw_')
    for _ in range(len(_PREFIXES)):
        for _p in _PREFIXES:
            if s.startswith(_p):
                s = s[len(_p):]
                break
        else:
            break
    return ' '.join(part for part in s.replace('_', ' ').split() if part)


def place_hint(here='', home='', near=(), at_home=False):
    """【你现在在哪】/【你的归属地】/【你还记得这些地方】—— 三个都空 ⇒ `''`（不产空块）。

    ★ 为什么不塞进 `trait_hint`：`trait_hint` 说的是"这地方**什么样**"（安静 / 拥挤），
      这里说的是"你**在地图的哪儿**"。前者描述气氛、后者是坐标事实；混进一句里，
      模型会把"你在城堡镇"当成形容气氛的词去发挥。
    ★ `at_home` 由调用方**判好再传**，不让模型自己比：`here == home` 时若还说
      "你平常在那儿待着，累了会想回去"，模型会以为家在**别处**，说出"我该回家了"
      —— 而它就在家。这是"同一份事实两处算"的典型坑，所以只算一次。
    """
    blocks = []
    if here:
        blocks.append('【你现在在哪】%s。' % here)
    if home:
        if at_home:
            blocks.append('【你的归属地】%s —— 就是这儿，你现在就在自己待惯了的地方。' % home)
        else:
            blocks.append('【你的归属地】%s —— 你平常在那儿待着，累了会想回去。' % home)
    near = [n for n in (near or ()) if n]
    if near:
        blocks.append('【你还记得这些地方】' + '、'.join(near) + '。')
    if not blocks:
        return ''
    blocks.append('（这些是位置事实，不是台词 —— 顺着说自己要去哪、想回哪就行，别照着念。）')
    return '\n'.join(blocks)


# ---------------------------------------------------------------- 活动与去处（第113轮k）

#: 用户口径（2026-10-26 逐字）：
#: 「我说的**特定事件**就是指，**吃饭，活动，休息，做任务**等，他能识别出来要去哪，
#:   并**给出建议**这样的，就像是人类之间问，咱吃饭去吧，别人会回答，
#:   **那要不去 XXX 家餐厅**？这样的话一样」
#:
#: ⇒ 两件事必须分开：① 从**话里**听出"要去干什么"（`detect_activity`，只认意图词）；
#:   ② 知道**哪儿真能干这事**（`place_matches` / `activity_hint`，只认地点词）。
#:   ★ 混成一张表会**因果倒置**（"因为人在餐厅所以他在吃饭"）——
#:     而人说话是"我想吃饭，所以去餐厅"。

#: 活动类型。顺序 = `detect_activity` 的并列兜底顺序，不承载语义。
ACTIVITY_KINDS = ('eat', 'rest', 'play', 'work')

#: 活动 → 一句人话。**不是台词模板** —— 台词由模型自己组织（见 `activity_hint`）。
ACTIVITY_SAY = {
    'eat': '吃点东西',
    'rest': '歇一会儿',
    # ★ 不能写 `出去转转`：模板是「要去%s」，拼起来成「要去出去转转」（叠了"去"）。
    'play': '转一圈',
    'work': '办点事',
}

#: 听懂别人在张罗什么。★ 只认**意图**，不认地名（地名在 `PLACE_WORDS`）。
INTENT_WORDS = {
    'eat': ('吃', '饭', '饿', '餐', '喝', '咖啡', '茶', '酒', '点心', '夜宵',
            '早餐', '午饭', '晚饭', '下馆子', 'eat', 'food', 'hungry', 'dinner',
            'lunch', 'breakfast'),
    'rest': ('累', '困', '睡', '歇', '休息', '躺', '打个盹', '回去', '回家',
             'tired', 'sleep', 'rest', 'nap'),
    'play': ('玩', '逛', '出去', '转转', '溜达', '散步', '活动', '热闹',
             'walk', 'play', 'stroll', 'hang out'),
    'work': ('办事', '上班', '上课', '看病', '任务', '工作', '买东西', '买点',
             'work', 'task', 'errand', 'buy'),
}

#: 哪儿能干什么。★ 中英两份：Deltarune 有中文名（`西姆的店`），
#: UT / 黄魂 / OneShot 只有英文原题（`diner` / `inn` / `pizza`）。
#: ★★ 刻意**不收**这些泛词（都是实测踩出来的误报）：
#:   `room`（我们的内部前缀，会命中一切）· `park`（`sparks` 含它）·
#:   `yard`（`graveyard` 是墓地）· `pool`（`poolsroom` 是泳池房）·
#:   `church`（ch4 有 114 间 `dw_church_*`，会把整池淹没）。
PLACE_WORDS = {
    'eat': {
        'zh': ('餐', '饭', '食', '厨', '咖啡', '茶', '酒馆', '小吃', '面包',
               '甜点', '食堂', '烘焙'),
        'en': ('restaurant', 'diner', 'cafe', 'coffee', 'kitchen', 'bakery',
               'tavern', 'bar', 'dinner', 'lunch', 'breakfast', 'food', 'pizza',
               'burger', 'soda'),
    },
    'rest': {
        'zh': ('床', '卧室', '睡', '休息', '旅店', '旅馆', '客栈', '沙发', '公寓',
               '宿舍'),
        'en': ('bed', 'bedroom', 'sleep', 'rest', 'inn', 'hotel', 'motel', 'home',
               'house', 'couch', 'lodge', 'cabin', 'dorm', 'apartment'),
    },
    'play': {
        'zh': ('游乐', '公园', '广场', '花园', '庭院', '操场', '游艺', '舞台',
               '剧场', '泳池', '游戏厅'),
        'en': ('park', 'plaza', 'garden', 'yard', 'playground', 'arcade', 'stage',
               'theater', 'theatre', 'amusement', 'carnival'),
    },
    'work': {
        'zh': ('商店', '市场', '工厂', '办公', '图书', '学校', '教室', '医院',
               '诊所', '实验室', '矿', '码头', '车站', '邮局', '银行'),
        'en': ('shop', 'store', 'market', 'factory', 'office', 'library', 'school',
               'hospital', 'clinic', 'lab', 'mine', 'station', 'dock', 'bank'),
    },
}


#: 意图词前面的**否定词**：出现就说明"他不是要去"。
#: ★ 为什么需要：`我不饿` 里那个 `饿` 会让 NPC 立刻推荐餐厅 —— 用户刚说吃饱，
#:   桌宠还劝他吃饭，这是"不像人"的典型（第113轮k 自查）。
_NEG_HEADS = '不没别甭勿莫'
#: 往前看几个字。取 3：`我不太饿` 的 `不` 与 `饿` 隔两个字。
_NEG_WINDOW = 3
#: **断句符**：否定不跨句。
#: ★ 踩过：「我不累，出去逛逛」里 `出去` 距 `不` 是 3 个字、中间还有个逗号，
#:   不切断的话 `出去` 被误否 ⇒ 退回命中更靠后的 `逛`（意思对了，但命中的词错了）；
#:   更坏的情形是后半句真正想说的那个词也被否掉。
_NEG_BREAK = '，。！？；：、,.!?;: \t\r\n…—~（）()「」'


def _negated(s, i):
    """`s[i:]` 开头的那个词，**同一口气里**前面有否定词吗？

    ★ 窗口 `_NEG_WINDOW` 个字内、且中间不许夹断句符。
    """
    if i <= 0:
        return False
    seg = s[max(0, i - _NEG_WINDOW):i]
    if any(ch in _NEG_BREAK for ch in seg):
        return False
    return any(ch in _NEG_HEADS for ch in seg)


def detect_activity(text):
    """一句话里认「他要去干什么」⇒ `(kind, 命中的词)`；认不出 `(None, '')`。

    ★ 多个活动同时命中时取**句子里最先出现**的那个：
      "吃完饭去逛逛" 的第一件事是吃饭。按表顺序取会得到与语序无关的答案，那是错的。
    ★ 空串 / None ⇒ `(None, '')`，不猜。
    ★★ **否定**要认（`我不饿` / `没吃饭` / `别玩了`）⇒ 那个词不算 —— 否则
      用户刚说吃饱，桌宠就开始推荐餐厅。只否**被否的那一处**，不整句丢弃：
      `我不累，出去逛逛` 里的 `出去` 仍然该命中 `play`。
    """
    s = str(text or '').strip().lower()
    if not s:
        return (None, '')
    best_kind, best_word, best_at = None, '', len(s) + 1
    for kind in ACTIVITY_KINDS:
        for w in INTENT_WORDS.get(kind, ()):
            wl = w.lower()
            i = s.find(wl)
            # ★ 同一词可能在一句里出现多次（`我不饿，你想吃点什么`）：被否掉的那次
            #   跳过、继续找下一次，**不能**因为第一处是否定就当整句没提。
            while i >= 0 and _negated(s, i):
                i = s.find(wl, i + 1)
            if 0 <= i < best_at:
                best_kind, best_word, best_at = kind, w, i
    return (best_kind, best_word)


def place_matches(text, kind):
    """这段文本像不像「能干 kind 这件事的地方」⇒ 命中的词列表（空 = 不像）。

    ★★ 调用方传进来的文本**必须已经剥掉区段名**。`ch5` 整个区叫 `garden`，
      房间 id 全是 `dw_garden_*` —— 不剥的话 106 间房会全部命中 `play`，
      「这个区叫希望之园」就被读成「每间房都是公园」。第113轮k 实测踩过。

    ★ 英文一律 `\b` 词边界：`sparks` 不含词 `park`，`graveyard` 不含词 `yard`。
    """
    # ★ `_` 转空格：`town_school` 里的 `school` 在正则里**不是**词首
    #   （`\w` 含 `_`）⇒ `\bschool\b` 匹配不上。调用方一般已过 `room_word`，
    #   但这里再容一次 —— 任何一边漏了都不会静默失效。
    s = str(text or '').replace('_', ' ').lower()
    if not s or kind not in PLACE_WORDS:
        return []
    table = PLACE_WORDS[kind]
    out = []
    for w in table.get('zh', ()):
        if w in s:
            out.append(w)
    for w in table.get('en', ()):
        if re.search(r'\b%s\b' % re.escape(w), s):
            out.append(w)
    return out


#: 地点类型词 → 中文类型名。
#: ★★ 这是**翻译**，不是给地方起名：`diner` 就是餐厅、`cafe` 就是咖啡店。
#:   原作没给中文名（Deltarune 全是 `room_diner` 这种 id、UT 是 `room_fire_restaurant`），
#:   我们就**照字面翻**；**绝不编**「XX 家餐厅」这种店名 —— 编出来的名字模型会当真，
#:   而那家店在原作里根本不存在。
#: ★ 只收**第113轮k 全量普查里实际出现过**的词：`eat` diner/restaurant/cafe/kitchen/
#:   pizza · `rest` house/couch/bed/bedroom/cabin/inn · `play` carnival/garden/plaza ·
#:   `work` school/hospital/library/lab/shop/store/office/dock/factory/station。
#:   查不到的英文词**原样留着**（宁可给英文，也不给它编个中文名）。
PLACE_GLOSS = {
    # -- 吃
    'diner': '餐厅', 'restaurant': '餐馆', 'cafe': '咖啡店', 'coffee': '咖啡馆',
    'kitchen': '厨房', 'bakery': '面包店', 'pizza': '披萨店', 'burger': '汉堡店',
    'tavern': '酒馆', 'bar': '酒吧', 'food': '餐馆',
    # -- 歇
    'inn': '旅店', 'hotel': '旅馆', 'motel': '汽车旅馆', 'bedroom': '卧室',
    'bed': '床', 'couch': '沙发', 'cabin': '小屋', 'house': '房子', 'home': '家',
    'lodge': '小屋', 'dorm': '宿舍', 'apartment': '公寓',
    # -- 玩
    'park': '公园', 'garden': '花园', 'plaza': '广场', 'yard': '院子',
    'playground': '操场', 'carnival': '游乐场', 'arcade': '游戏厅', 'stage': '舞台',
    'theater': '剧院', 'theatre': '剧院',
    # -- 办事
    'shop': '商店', 'store': '商店', 'market': '市场', 'factory': '工厂',
    'office': '办公室', 'library': '图书馆', 'school': '学校', 'hospital': '医院',
    'clinic': '诊所', 'lab': '实验室', 'mine': '矿', 'bank': '银行',
    # ★★ `station` / `dock` **故意不在这里**（第113轮k 全量人读）：
    #   OneShot 的 `Research Station` 是**研究站**不是火车站、UT 的
    #   `room_fire_dock` 到底是码头还是停靠点我判不准 —— 猜错就是**编造地名**，
    #   比留着英文更糟（模型自己看得懂 `Research Station`）。表格里**只放
    #   我确定**的翻译，宁缺毋滥。
}


def place_type_name(word):
    """地点类型词 → 中文类型名。中文词原样返回；英文查 `PLACE_GLOSS`；查不到原样返回。

    ★ 中文词原样返回是有意的：`餐` / `咖啡` / `舞台` 本身就是原作给的中文名的一部分，
      再翻一次（`餐`→`餐厅`）反而会把 `理想餐厅` 变成 `理想餐厅（餐厅）`。
    """
    w = str(word or '').strip()
    if not w:
        return ''
    return PLACE_GLOSS.get(w.lower(), w)


#: 英文地名里**不首字母大写**的虚词（不在首词时）。
_EN_MINOR = frozenset(('of', 'the', 'a', 'an', 'and', 'in', 'at', 'on', 'to',
                       'for', 'by', 'with'))

#: 楼层缩写 → 口语说法。
#: ★ `2f` 不是地名的一部分，是"二层"的缩写；照抄进 prompt 模型会读成 "two f"。
#:   只收实测出现过的几个（黄魂 `tundra inn 2f`、`steamworks 3f`）。
_FLOOR_EN = {
    '1f': 'First Floor', '2f': 'Second Floor', '3f': 'Third Floor',
    '4f': 'Fourth Floor', 'b1f': 'Basement',
    '1st': 'First Floor', '2nd': 'Second Floor', '3rd': 'Third Floor',
}

#: 已知缩写 → 正确写法。★ 只收**确定**的：`tv` 是 Deltarune 的 `TV World`，
#: `ut`/`uty` 是作品缩写（`Undertale` / `Undertale Yellow`）。
#: 不收 `dw`/`lw`（那是我们的区名前缀，`room_word` 已经剥掉了）。
_ABBR_EN = {'tv': 'TV', 'ut': 'UT', 'uty': 'UTY',
            # `truelab` 是 id 粘连词（`room_truelab_bedroom`），原作写作 True Lab。
            'truelab': 'True Lab'}

#: CJK **文字**码位段 —— 只用于"这个真名是不是中文"。
#: ★ 刻意**不收**标点段：`0x3000-0x303F`（`、`「」）与 `0xFF00`（全角括号）
#:   是排版符号，不是文字。把它们算成中文会让「零中文地名」的判据**恒假** ——
#:   `Hometown · Diner、Light World · Icee Pizza` 明明全英文，却因为列表用的
#:   `、` 被判成中文。第113轮l 实测踩过（4 条 J 判据假红）。
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))


#: **id 形态**的容器区：`ut.rooms.*` / `uty.rooms.*`。
#: ★ 与 `PLACE_FILLER`（中文区名）分工：那个挡「全部房间」这种叫法，这个挡
#:   `rooms` 这个 id。两者都是我们的目录结构，不是作品里的地方 —— 不挡的话
#:   1251 间房的标签全变成 `Rooms · X`，模型会把 `Rooms` 当成真地名，
#:   而它其实相当于"磁盘上的文件夹"。
PLACE_CONTAINER_IDS = frozenset(('rooms',))


def has_cjk(text):
    """这段文本里有中日韩字符吗？⇒ True 表示"是中文名，不是英文地名"。

    ★ 用途只有一个：`place_label` 决定**能不能**用真名。Deltarune 的真名是中文
      （`理想餐厅`），和英文区名（`Hometown`）拼在一起会变成半中半英；
      这种情形退回原作 id 末段（`diner` ⇒ `Diner`），整条标签才是同一种语言。
    """
    for ch in str(text or ''):
        o = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= o <= hi:
                return True
    return False


def speakable_en(text, proper=()):
    """原作 id 末段 → **能说出口的英文地名**：`castle cafe` → `Castle Cafe`。

    ★★ 为什么必须整形（用户口径「有些 room 名称并不口语化」）：
      原作 id 是给程序看的 —— `c asgore kitchen` / `couch overworld 01` /
      `tundra inn 2f`。直接塞进 prompt，模型会照抄成"去 c asgore kitchen"，
      比不给还糟（与 `room_word` 里 `rm_steamworks_29` 是同一条道理）。
    ★ 只做**四件**事，一件都不多：
      ① 下划线转空格 ② 楼层缩写说成人话 ③ 每个词首字母大写（虚词除外）
      ④ 人名 + 地点词 ⇒ 所有格 `Asgore's Kitchen`。
      **不替换任何实词、不补冠词、不猜同义词** —— 名字必须还是原作那个名字。
    ★ `proper` 是**人名集合**（小写）。只用于判首词要不要加 `'s`：
      `asgore kitchen` 在集合里 ⇒ `Asgore's Kitchen`；`castle cafe` 不在 ⇒
      `Castle Cafe`（给 `castle` 也加 `'s` 就成了不存在的"城堡的咖啡店"）。
    """
    toks = str(text or '').replace('_', ' ').split()
    if not toks:
        return ''
    props = {str(p).strip().lower() for p in (proper or ()) if str(p).strip()}
    words = []
    for i, tok in enumerate(toks):
        low = tok.lower()
        if low in _FLOOR_EN:
            words.append(_FLOOR_EN[low])
            continue
        if low in _ABBR_EN:
            words.append(_ABBR_EN[low])
            continue
        # ★ id 里的 `_s_` 是**所有格分隔**：`noelle_s_house` = `Noelle's House`。
        #   `_`→空格后 `s` 变成一个独立词，不合并就会拼成
        #   `Noelle's S House`（还因为前词是人名多吃了个 `'s`）。第113轮l 实测。
        if low == 's' and i > 0 and words:
            # ★ 前词可能已经按人名加过 `'s`（`noelle s house` 的 `noelle`）——
            #   再拼一次就成 `Noelle's's House`。第113轮l 实测。
            if not words[-1].endswith("'s"):
                words[-1] += "'s"
            continue
        if low in _EN_MINOR and i > 0:
            words.append(low)
            continue
        w = tok[:1].upper() + tok[1:]
        if i == 0 and len(toks) > 1 and low in props:
            w += "'s"
        words.append(w)
    return ' '.join(words)


def de_cjk_names(text, names_en=None):
    """把地名里夹着的**中文人名**换成英文名：`托丽尔的房子` ⇒ `Toriel的房子`。

    ★ 为什么只换人名、不换别的：地名里只有"人名"有**确定的**英文对应
      （`npc_registry` 里就有 `name`），其余中文（`的房子` / `餐厅`）没有可靠译法，
      瞎翻就是**编造地名**。换完仍含中文的，由 `place_label` 整条退回原作 id 末段。
    ★ 长名优先：同时存在 `Ketsukane 家` 与 `Ketsukane` 时，先换长的才不会留半截。
    """
    s = str(text or '')
    if not s or not names_en:
        return s
    for cn in sorted(names_en, key=lambda k: -len(k)):
        en = names_en.get(cn)
        if cn and en and cn in s:
            s = s.replace(cn, en)
    return s


def trim_core_at_type(core, hits):
    """把 `core` 截到**类型词为止**：`hospital hallway` → `hospital`。

    ★★ 为什么必须截（正反两面都是实测）：
      · 类型词**之后**的是**同一栋楼里的具体房间**（`hospital lobby` / `hospital
        hallway` / `library upstairs` / `shop interior` / `couch overworld`）——
        留着会把"去哪儿"说成"去那栋楼的某间房"，而走廊/楼上在原作里不是去处。
      · 类型词**之前**的是**店名的前半截**（`icee pizza` / `castle cafe` /
        `fire restaurant` / `b3bs shop` / `city spamton shop`）—— 截掉就只剩
        「披萨店」「咖啡店」，同城几家店全糊成一个，模型说不出是哪一家。
    ★ 只按**空白分词**比：中文词（`餐` / `咖啡` / `舞台`）出现在**真名**里，
      走的是 `detail` 那一支，根本不进这里。
    ★ 命中不到类型词（`plat lab` 之类分词怪例）⇒ **原样返回**，不猜。
    """
    toks = str(core or '').split()
    if len(toks) < 2:
        return ' '.join(toks)
    lows = [t.lower() for t in toks]
    cut = -1
    for h in (hits or ()):
        h = str(h or '').strip().lower()
        if not h or ' ' in h:
            continue
        if h in lows:
            cut = max(cut, lows.index(h))
    if cut < 0 or cut >= len(toks) - 1:
        return ' '.join(toks)
    return ' '.join(toks[:cut + 1])


def label_key(text):
    """地名归一：只留字母数字（`Noelle's House` 与 `Noelles House` ⇒ 同一个键）。

    ★ 为什么需要：id 里带不带所有格分隔符是**命名习惯**，不是两个地方。
      不归一就会出现 `Noelles House · Noelle's House` 这种自我复读。
    """
    return ''.join(ch for ch in str(text or '').casefold() if ch.isalnum())


def place_label(area, detail, core, hits, sep=PLACE_SEP, proper=(),
                names_en=None):
    """拼一个**能说出口的英文地名**：`Hometown · Diner`。

    参数
    ----
    area   : 区名 / 区 id（**英文**）。容器名会被滤掉。
    detail : **已经能读的原作名**。★ 只有它**不含中文**时才用 —— 中文真名
             （`理想餐厅`）和英文区名拼在一起是半中半英，宁可退回 id 末段。
    core   : 原作 id 末段（**剥过区段名**，如 `diner` / `castle cafe`）。
    hits   : `place_matches` 命中的类型词，用于把 `core` 截到类型词为止。
    sep    : 层级分隔符。
    proper : 人名集合（小写），用于 `Asgore's Kitchen` 这类所有格。
    names_en : 中文人名 → 英文名的映射（`托丽尔` ⇒ `Toriel`）。★ 用户口径
             「人名也要改成英文」—— 只换人名，不换地名里的其他中文。

    ★★ 为什么全是英文（第113轮l 用户口径「名字用英文」）：
      原先输出 `家乡 · diner（餐厅）` —— 中文区名 + 英文 id + 中文翻译括注，
      三种东西挤在一行，模型念出来是"去家乡 diner 括号餐厅"。改成
      `Hometown · Diner` 后它只有一件事要念。
    ★ 中文类型名（`place_type_name`）**仍然有用**，但只在内部当**去重键**
      （同一家医院的走廊/大厅/病房合成一条），不进 prompt。
    ★ 纯拼接：不查索引、不猜名字。数据从哪来是调用方的事。
    """
    # ★ 先换人名再判"是不是中文"：`托丽尔的房子` 换完是 `Toriel的房子`，
    #   仍含中文 ⇒ 走 core 那一支（`toriel house` ⇒ `Toriel's House`）。
    area = de_cjk_names(area, names_en)
    detail = de_cjk_names(detail, names_en)
    core = de_cjk_names(core, names_en)
    area = str(area or '').strip()
    if place_container(area) or area.lower() in PLACE_CONTAINER_IDS:
        area = ''
    core = trim_core_at_type(
        strip_room_index(' '.join(str(core or '').split())), hits)

    area_en = speakable_en(area)
    body = ''
    if detail and not has_cjk(detail):
        # ★ 真名也要去尾号：`Steamworks Factory 01` / `Dunes 30 House 1`
        #   是索引里的英文真名，不 strip 就原样进 prompt（B 判据抓不到，
        #   因为它们不是"中文"也不是"id 形态"）。第113轮l 人眼通读抓到。
        body = speakable_en(strip_room_index(detail), proper)
    # ★ `detail` 只是**区名的复读** ⇒ 它没有"哪一家"的信息，必须用 core 补。
    #   实测：`ch5.garden.garden_ideal_diner` 的 base = `Garden`（场景名被判无名、
    #   只剩区名），照用会让整条候选变成 `Garden` —— 用户要的那个 XXX 家餐厅没了。
    if body and area_en and label_key(body) == label_key(area_en):
        body = ''
    if not body:
        body = speakable_en(core, proper)
    # ★ 区名与店名同名（`diner` 区里的 `diner`）⇒ 只留一个，否则 `Diner · Diner`
    if area_en and body and label_key(area_en) == label_key(body):
        return body
    if area_en and body:
        return area_en + sep + body
    return body or area_en


def strip_room_index(core):
    """去掉**纯数字的房号**：`couch overworld 01` → `couch overworld`。

    ★ 为什么要去：ch3 有 8 间 `dw_couch_overworld_01..05`，留着房号会输出
      「黑暗世界 · couch overworld 01（沙发）」等 4 条几乎一样的东西 ——
      模型只会挑花眼，说不出一个具体的。
    ★ 只去**纯数字**：`tundra inn 2f` 的 `2f` 有意义（二层），不动它。
    ★ 另去**行首单字母**（`c asgore kitchen` → `asgore kitchen`）：那是 Outertale
      把区名缩写进 id 的产物，不是店名的一部分。第113轮k 全量人读抓到。
    """
    toks = [t for t in str(core or '').split() if t]
    # ★ 行首的**单字母**是区名缩写（Outertale 的 `c_asgore_kitchen` → `c`）：
    #   留在 prompt 里像打错字。只认行首、只认单个 ASCII 字母 ——
    #   `House 1 - stew` 的 `1`、`tundra inn 2f` 的 `2f` 都不受影响。
    while len(toks) > 1 and len(toks[0]) == 1 and toks[0].isalpha() \
            and toks[0].isascii():
        toks.pop(0)
    # ★ 行首**纯数字**同理：`dark_sanctuary_1_library` 剥掉区名前缀后剩
    #   `1 library`，那个 `1` 是场景序号，不是地名（输出成 `· 1 Library` 很怪）。
    #   只去**行首**：`dunes 30 house` 的 `30` 在中间（是门牌），不动。
    while len(toks) > 1 and toks[0].isdigit():
        toks.pop(0)
    while toks and toks[-1].isdigit():
        toks.pop()
    return ' '.join(toks)


def activity_hint(kind, places, note='', limit=4, cross=False):
    """【这会儿能张罗的事】—— 有人提到要去干什么，他手边**真有哪些地方**可提。

    参数
    ----
    kind   : `ACTIVITY_KINDS` 之一；不认识 ⇒ `''`（不产块）
    places : `[(scene_id, 可读名), ...]`。★ **调用方按"能去"筛好**再传 ——
             能不能去是门控的事（`world_gate` / 章归属），策略层不碰。
    note   : 可选的一句上下文（比如"他刚才问要不要一起"）。
    limit  : 最多列几个。太多模型会挑花眼，反而说不出一个具体的。
    cross  : 候选里**混进了别处/别章**的地方 ⇒ 换一句更诚实的引导。
             ★ 跨区域后还说"你们这儿真有的地方"就是**撒谎** —— 模型会当真，
               把别处的餐厅说成"走两步就到"。第113轮l。

    返回 `''` 表示**没有可说的** —— 不产块，而不是写"附近没什么地方"这种废话。
    """
    if kind not in ACTIVITY_SAY:
        return ''
    names = []
    for pair in (places or ()):
        try:
            _sid, lbl = pair
        except (TypeError, ValueError):
            continue
        lbl = str(lbl or '').strip()
        if lbl and lbl not in names:
            names.append(lbl)
        if len(names) >= max(1, int(limit or 4)):
            break
    if not names:
        return ''

    head = '【这会儿能张罗的事】'
    if note:
        head += str(note).strip() + ' '
    if cross:
        lines = [
            head + '要去%s，能想到的地方：%s。' % (ACTIVITY_SAY[kind], '、'.join(names)),
            '（有的不在你这一带 —— 提的时候把"在哪儿"也说出来；还用你自己平常的说法，别照着念，别让人以为走两步就到。）',
        ]
    else:
        lines = [
            head + '要去%s，你们这儿真有的地方：%s。' % (ACTIVITY_SAY[kind], '、'.join(names)),
            '（想接这个话就提一个，用你自己平常的说法 —— 别照着念，也别硬拉人家去。）',
        ]
    return '\n'.join(lines)


# ---------------------------------------------------------------- 在场者感知（第86轮）

#: 相对方位词（按"你看的方向"分档）—— **粗档**，不给精确坐标。
_WHERE_CN = {
    'left': '左边', 'right': '右边', 'near': '近处', 'far': '远处',
    'same': '就在旁边',
}

#: 判"横向够不够格说左右"的比例：`|dx| < |dy| * HORIZ_RATIO` ⇒ 视为**纯竖直**，
#:  返回 `None`（不编左右）。★ 一处算 —— `where_of` 里只读这一个名字。
HORIZ_RATIO = 0.5


def where_of(dx, dy=0.0, near_px=120.0):
    """把位移归一成**一个粗方位词**。`None` = 算不出来（不猜）。

    ★ 为什么不给"左 37 像素"这种精确值：模型不需要像素，给了反而会
      开始念坐标（"你在我左手边三十七像素处"）—— 那是把人话说成日志。
      ⇒ 只给**够做社交判断**的粗档。判"够不够近"用 `near_px`（默认 120）；
      判"横向够不够格说左右"用 `HORIZ_RATIO`（纯竖直位移**不编左右**）。
    """
    try:
        dx = float(dx)
        dy = float(dy)
        near = float(near_px)
    except (TypeError, ValueError):
        return None
    if near <= 0:
        near = 120.0
    ax, ay = abs(dx), abs(dy)
    if ax < 1e-6 and ay < 1e-6:
        return 'same'
    if max(ax, ay) <= near:
        return 'near'
    # ★ 纯竖直位移（横向几乎没差）⇒ **不编左右**（`None`）。
    #   踩过的坑：早先 `dx < 0 else right` 会把"正上方 500 像素"说成"右边"
    #   —— 那不是粗档，那是**错档**。宁可不说，也不说反。
    if ax < (ay * HORIZ_RATIO):
        return None
    return 'left' if dx < 0 else 'right'


def presence_hint(speaker_id, others, positions=None, near_px=120.0,
                  label_of=None):
    """【此刻这里还有谁】—— **只给"有谁 + 粗方位"，不给作品归属/版本/id**。

    :param speaker_id: 说话的这个人（会从 `others` 里剔除）
    :param others: 在场其他人的 id 序列
    :param positions: 可选 `{id: (dx, dy)}` —— **相对说话人**的偏移（宿主算）
    :param label_of: 可选 `(id) -> 显示名`；不给 ⇒ 用 id 本身（退化但**不崩**）
    :return: 一行提示；没有别人 / 非法输入 ⇒ `''`（**不产空块**）

    ★★★ 与 `_crossworld.json#identity_blind.not_injected` 严格一致：
      **绝不**注入对方的作品 / 版本 / npc id / 人设 —— 只给"他叫什么、在哪个方位"。
      怎么判断来人是谁，是 NPC 自己的事（用户口径：怪物之间没有身份标识）。
    ★ 顺序：说话人自己永远不出现；重复 id 去重；无位置信息时**不编方位**
      （只说"这里还有 X"，不硬塞"在你左边"）。
    """
    if not isinstance(speaker_id, str) or not speaker_id.strip():
        return ''
    sid = speaker_id.strip()
    seen = []
    for o in (others or ()):
        if not isinstance(o, str):
            continue
        o = o.strip()
        if not o or o == sid or o in seen:
            continue
        seen.append(o)
    if not seen:
        return ''
    pos = positions if isinstance(positions, dict) else {}
    rows = []
    for oid in seen[:6]:
        nm = oid
        if callable(label_of):
            try:
                nm = label_of(oid) or oid
            except Exception:
                nm = oid
        w = None
        if oid in pos:
            p = pos.get(oid)
            if isinstance(p, (tuple, list)) and len(p) >= 2:
                w = where_of(p[0], p[1], near_px=near_px)
        rows.append(nm + ('（在%s）' % _WHERE_CN[w]) if w in _WHERE_CN else nm)
    return ('【此刻这里还有谁】' + '、'.join(rows)
            + '。（只知道他叫什么、大概在哪个方位 —— 他是哪里来的、是哪个版本，'
              '你并不知道，也别去猜。）')


# ---------------------------------------------------------------- 熟络度

#: 初值（★ 与 `_crossworld.json#familiarity_seed.seed_values` **逐字同源**，check73 D 段钉住）。
SEED_SAME_AU_TWIN = 0.55     # 「另一个版本的我」——起手最高（"我认得你，但你不是他"）
SEED_SAME_PRODUCTION = 0.30  # 同一作品内的人
SEED_STRANGER = 0.0          # 跨作品陌生人

#: 每"同处一室"一个节拍涨多少（**渐增**，不是一次到位）。
GAIN_PER_TICK = 0.004
#: 单次互动（说了一句话）额外涨多少。
GAIN_PER_MEETING = 0.03
#: 封顶 / 地板。
FAMILIAR_MAX = 1.0
FAMILIAR_MIN = 0.0

#: 「算熟人」的下限（给"你认识谁"那块用）。
KNOWN_THRESHOLD = 0.20


def pair_key(a, b):
    """**无向**键：`A-B` 与 `B-A` 必须落到同一把钥匙。非法/自反 ⇒ `None`。

    ★ 为什么不是 `(a, b)` 直存：那样 `meet(a,b)` 与 `meet(b,a)` 会写成两条，
      "熟络度"就有了两个真相。排序后成对 ⇒ 结构上不可能分叉。
    """
    if not isinstance(a, str) or not isinstance(b, str):
        return None
    a, b = a.strip(), b.strip()
    if not a or not b or a == b:
        return None
    return (a, b) if a < b else (b, a)


class Bonds(object):
    """NPC 两两之间的**熟络度**。per-pair、**对称**、**渐增**、可存盘。

    `seed_lookup` 是一个可插拔函数 `(a, b) -> float`（由宿主从注册表 + 同名组推初值）；
    不给 ⇒ 一律从 `SEED_STRANGER` 起。**本类自己不读文件**（零依赖）。
    """

    def __init__(self, seed_lookup=None, threshold=KNOWN_THRESHOLD):
        self._d = {}
        self.seed_lookup = seed_lookup if callable(seed_lookup) else None
        try:
            self.threshold = float(threshold)
        except (TypeError, ValueError):
            self.threshold = KNOWN_THRESHOLD

    # -- 内部
    def _clamp(self, v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return FAMILIAR_MIN
        if f != f:                       # NaN
            return FAMILIAR_MIN
        return max(FAMILIAR_MIN, min(FAMILIAR_MAX, f))

    # -- 读
    def get(self, a, b):
        """当前熟络度。**没存过** ⇒ 现场问 `seed_lookup`（问不到就 `SEED_STRANGER`）。

        ★ 注意这里**不写回** `self._d`：查一次就落一条，会把"没相处过"变成"相处过"。
        """
        k = pair_key(a, b)
        if k is None:
            return FAMILIAR_MIN
        if k in self._d:
            return self._d[k]
        if self.seed_lookup is not None:
            try:
                return self._clamp(self.seed_lookup(k[0], k[1]))
            except Exception:
                return FAMILIAR_MIN
        return FAMILIAR_MIN

    def known(self, npc_id, threshold=None):
        """对 `npc_id` 而言"够熟"的人（按熟络度降序、同分按 id 升序 —— **稳定**）。"""
        if not isinstance(npc_id, str) or not npc_id:
            return []
        try:
            th = float(threshold) if threshold is not None else self.threshold
        except (TypeError, ValueError):
            th = self.threshold
        out = []
        for (x, y), v in self._d.items():
            if x == npc_id:
                out.append((y, v))
            elif y == npc_id:
                out.append((x, v))
        out = [(n, v) for n, v in out if v >= th]
        out.sort(key=lambda t: (-t[1], t[0]))
        return [n for n, _ in out]

    def pairs(self):
        """全部已存的键（只读副本，稳定序）。"""
        return sorted(self._d.keys())

    # -- 写
    def seed(self, a, b, value):
        """显式设一个初值（**只在没有记录时**生效，不覆盖已经相处出来的值）。→ 是否写入。"""
        k = pair_key(a, b)
        if k is None or k in self._d:
            return False
        self._d[k] = self._clamp(value)
        return True

    def meet(self, a, b, amount=GAIN_PER_MEETING):
        """相处一次（说了一句话）。→ 新的熟络度；非法入参 ⇒ 现值（不改）。"""
        k = pair_key(a, b)
        if k is None:
            return FAMILIAR_MIN
        cur = self.get(a, b)            # 允许从 seed 初值开始累加
        return self._set(k, cur + amount)

    def tick(self, a, b, amount=GAIN_PER_TICK):
        """同处一室的一个节拍（**很慢**）。→ 新值。"""
        return self.meet(a, b, amount)

    def _set(self, k, v):
        self._d[k] = self._clamp(v)
        return self._d[k]

    # -- 存盘（纯字典，宿主决定往哪写）
    def to_dict(self):
        return {'%s|%s' % k: v for k, v in self._d.items()}

    @classmethod
    def from_dict(cls, data, seed_lookup=None, threshold=KNOWN_THRESHOLD):
        b = cls(seed_lookup=seed_lookup, threshold=threshold)
        if isinstance(data, dict):
            for key, v in data.items():
                if not isinstance(key, str) or '|' not in key:
                    continue
                a, _, c = key.partition('|')
                k = pair_key(a, c)
                if k is None:
                    continue
                b._d[k] = b._clamp(v)
        return b

    def __len__(self):
        return len(self._d)

    def __repr__(self):
        return '<Bonds pairs=%d threshold=%.2f>' % (len(self._d), self.threshold)


# ---------------------------------------------------------------- 信息传播

#: 一次最多传几条（**传播不等于搬家**：把整份记忆倒过去既没意义又会让对方"看穿一切"）。
DEFAULT_TRANSMIT_LIMIT = 3


def transmit(mem, src_id, dst_id, limit=DEFAULT_TRANSMIT_LIMIT):
    """★ **信息传播**：把 `src_id` 记忆里最近 `limit` 条，**以 src 的署名**记进 `dst_id`。

    → 实际传过去的条数（`0` = 什么都没传，**不是错误**）。

    三条硬约束（`check73` E 段逐条判）：

    1. **不共享容器**：只从 `src` 的历史（浅拷贝）取文本，再调 `dst` 自己的
       `remember()` —— 两边在存储上仍是**两份物理分开**的数据。本函数**拿不到**
       `MiniMemory` 的内部字典，所以"把 A 的记忆对象塞给 B"这件事在接口层面写不出来。
    2. **必须署名**：`who=src_id`。B 记下的是"**A 说过这句话**"，不是"我知道这件事"。
       ⇒ 这正是用户那句「怪物之间**没有身份标识**，所以**那需要自己判断**」的落地方式：
         **信息带着来源走，但不带"他是哪个世界的"**（见 `_crossworld.json#identity_blind`）。
    3. **不许自说自话**：`src_id == dst_id` / 任一非法 / mem 不可用 ⇒ 返回 `0`。

    另外**跳过**对方自己说过的那几条（`who == dst_id`）—— 把人家自己的话"转告"给他，
    只在坏掉的时候有意义。
    """
    if not isinstance(src_id, str) or not isinstance(dst_id, str):
        return 0
    src_id, dst_id = src_id.strip(), dst_id.strip()
    if not src_id or not dst_id or src_id == dst_id:
        return 0
    if mem is None:
        return 0
    try:
        history = mem.history(src_id)
    except Exception:
        return 0
    if not history:
        return 0
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = DEFAULT_TRANSMIT_LIMIT
    if n <= 0:
        return 0
    cand = [e for e in history if isinstance(e, dict) and e.get('who') != dst_id]
    if not cand:
        return 0
    sent = 0
    for e in cand[-n:]:
        text = e.get('text')
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            ok = mem.remember(dst_id, text, who=src_id, scene=e.get('scene'))
        except Exception:
            continue
        if ok:
            sent += 1
    return sent


# ---------------------------------------------------------------- 自发台词（纯 NPC，零模型）

def pick_line(lines, used=None):
    """从**内置池**里挑一句还没说过的。→ `(line, 新 used 集合)`；池空 ⇒ `('', used)`。

    ★ 为什么纯 NPC 的自发台词走内置池而不是模型：
      用户口径「纯 npc ……就用 4~10 句内置对话就好」（第49轮 C 段），
      并且 7B 是**纯 CPU 单并发**（第57轮）：让几十位纯 NPC 自发闲聊去排队抢模型，
      会把用户自己的对话挤到几十秒之外。内置池让"生活"**零成本**地跑起来。
      ★ 反过来，**主线 NPC 不走这里**（`lines_of` 对他们返回空表）—— 他们说人话靠模型，
        自发开口必须有让路闸（见 `LifeLoop.gate`）。

    `used` 是"已经说过的下标集合"；说不满一圈就**不重复**；满了自动重置（允许第二轮）。
    """
    if not lines:
        return '', used if used is not None else set()
    u = {i for i in (used or ()) if isinstance(i, int) and 0 <= i < len(lines)}
    left = [i for i in range(len(lines)) if i not in u]
    if not left:
        u = set()
        left = list(range(len(lines)))
    idx = left[0]                 # 确定性：取第一个还没说过的（不引入随机源，便于回归）
    u.add(idx)
    return lines[idx], u


# ---------------------------------------------------------------- 自主开口节拍

#: 两句自发对话之间至少隔多久（秒）。★ 定得比"用户对话"松得多：自发闲聊是背景音，
#: 不该跟用户抢注意力。
DEFAULT_MIN_GAP = 25.0
#: 一轮最多说几句（说完就停，等下一轮 reset）。
DEFAULT_MAX_TURNS = 3
#: 至少要有几个人在场才可能自发开口（1 = 允许自言自语，默认关）。
MIN_TALKERS = 2
#: 连续失败到这个数 ⇒ 停手（**反活锁**）。
MAX_CONSECUTIVE_FAILURES = 3


class LifeLoop(object):
    """自主开口的节拍。四条不变量（与 `companion_roster.ChatScheduler` **性质相同**）：

      1. `busy` 时 `tick()` **恒**返回 `None`（不并发 —— 一次只让一个人开口）；
      2. 下一个 speaker **绝不等于**上一个（不出现"自己跟自己聊"）；
      3. 任何失败路径（`abort` / `speaker_mismatch`）都**必须解锁**（不许永久卡死）；
      4. 连续失败 >= `MAX_CONSECUTIVE_FAILURES` ⇒ 停手（**反活锁**，不空转烧 CPU）。

    `gate` 是可插拔的"现在允不允许开口"闸（宿主用来让路给用户）：
    返回假值 ⇒ 本拍不开口，**且不推进轮转**（下次还是同一位 —— 不是他的错）。
    """

    def __init__(self, min_gap=DEFAULT_MIN_GAP, max_turns=DEFAULT_MAX_TURNS,
                 allow_solo=False, gate=None):
        self.min_gap = float(min_gap)
        self.max_turns = int(max_turns)
        self.allow_solo = bool(allow_solo)
        self.gate = gate if callable(gate) else None
        self._busy = False
        self._pending = None
        self._last_from = None
        self._last_time = None
        self._turns = 0
        self._fail_count = 0
        self.mismatch_count = 0

    # -- 状态
    @property
    def busy(self):
        return self._busy

    @property
    def pending_id(self):
        return self._pending

    @property
    def turns(self):
        return self._turns

    @property
    def fail_count(self):
        return self._fail_count

    # -- 节拍
    def tick(self, now, ids):
        """该谁开口？→ `npc_id` 或 `None`。**调一次若返回非 None 就会置 busy。**"""
        if self._busy:
            return None
        if self._fail_count >= MAX_CONSECUTIVE_FAILURES:
            return None
        members = sorted({i for i in (ids or ()) if isinstance(i, str) and i.strip()})
        if len(members) < (1 if self.allow_solo else MIN_TALKERS):
            return None
        if self._turns >= self.max_turns:
            return None
        if self._last_time is not None and (float(now) - self._last_time) < self.min_gap:
            return None
        if self.gate is not None:
            try:
                if not self.gate():
                    return None
            except Exception:
                return None
        cand = self._next_speaker(members)
        if cand is None:
            return None
        self._busy = True
        self._pending = cand
        return cand

    def _next_speaker(self, members):
        """轮转：从上一位的**下一位**开始找第一个 `!= 上一位` 的人。"""
        start = 0
        if self._last_from is not None:
            for i, m in enumerate(members):
                if m == self._last_from:
                    start = i + 1
                    break
        n = len(members)
        for k in range(n):
            m = members[(start + k) % n]
            if m != self._last_from:
                return m
        return None

    # -- 收束
    def finish(self, now, from_id=None):
        """生成结束（**成功或失败都要调**）。→ `(ok, reason)`。

        `from_id` 与 `tick()` 返回的人不一致 ⇒ 记 `speaker_mismatch`（**张冠李戴的兜底报警**），
        但**仍然解锁并推进轮转** —— 卡死比错一次更严重。
        """
        if not self._busy:
            return False, 'not_busy'
        pending = self._pending
        self._busy = False
        self._pending = None
        reason = ''
        if from_id is not None:
            got = from_id.strip() if isinstance(from_id, str) else from_id
            if got != pending:
                self.mismatch_count += 1
                reason = 'speaker_mismatch:%s!=%s' % (got, pending)
        self._last_from = pending
        self._last_time = float(now)
        self._turns += 1
        self._fail_count = 0
        return (reason == ''), reason

    def abort(self, now, advance=False):
        """失败 / 被打断：**解锁**。→ `True` = 确实解锁了。

        `advance=False`（默认）⇒ **不推进轮转**，下次还是同一位开口
        （失败是环境的事，不是他的事）。
        """
        if not self._busy:
            return False
        self._busy = False
        self._pending = None
        self._fail_count += 1
        if advance and self._last_from is not None:
            self._last_time = float(now)
        return True

    def reset(self, keep_turns=True):
        """清空轮转状态。`keep_turns=False` ⇒ 连计数一起归零（下一轮重新开始）。"""
        self._busy = False
        self._pending = None
        self._last_from = None
        self._last_time = None
        self._fail_count = 0
        if not keep_turns:
            self._turns = 0
        return self

    def __repr__(self):
        return ('<LifeLoop busy=%s pending=%s last=%s turns=%d/%d fails=%d>'
                % (self._busy, self._pending, self._last_from,
                   self._turns, self.max_turns, self._fail_count))


# ---------------------------------------------------------------- 交互动作表（给"做点什么"用）

#: 自发行为的最小集合（**只登记，不各自实现**）：id → 中文名。
#: 第73轮只接线 `speak` / `transmit`；`move` 复用 `npc_placement` 的游荡（不在这里重造）。
ACTIONS = collections.OrderedDict((
    ('speak', '说一句'),
    ('transmit', '把知道的说给别人'),
))
