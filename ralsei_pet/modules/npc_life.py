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
#:     实测**仍是 0 命中** ⇒ **继续留在预留表**（如实登记缺口）。
TRAIT_TOKENS = {
    'dark': ('dark', 'cave', 'basement'),
    'ruined': ('ruin', 'ruined'),
    'bright': ('sun',),
    'crowded': ('town', 'city', 'shop'),
    'quiet': ('home', 'house', 'forest', 'grave', 'church', 'library'),
    'cosmic': ('sky',),
}

#: ★ **跨作品预留**令牌：现网 **0 命中**（`check73` D2 反过来验"确实 0 命中"，
#: 防有人拿它们混进本位表凑数字）。等 `hub:ot` / `hub:os` 的场景进大图后启用。
#:
#: ★★ 这张表本身就是一条**实证结论**，必须留着 —— 用户除了「这地方真黑」还点名
#:   「**破败**这类的词也需要有能力识别」。第80轮（OneShot 迁入）后实测：
#:   **`bright` 的 `sunny`/`bright`/`daylight`、`cosmic` 的 `space`/`moon`/`void`/`galaxy`/`orbit`/`cosmic`
#:   仍是 0 命中**；`crowded` 的 `market`/`plaza` 也仍 0 命中。
#:   原因不是"没做"，是 **Outertale 的场景还没进 `_index.json`**（OneShot 已进但只带来
#:   `sun`/`sky` 两条可转正 + `square`/`street` 两条语义错位）。
#:   ⇒ **如实登记缺口**，而不是把 `sun` 硬塞进本位表让判据看起来"覆盖了明亮"。
#:   （注：`sun`/`sky` **第80轮确已转正**，因为语义正确且实测有命中 —— 见上表注释。）
TRAIT_TOKENS_RESERVED = {
    'dark': ('cellar', 'underground'),
    'ruined': ('broken', 'wreck', 'abandon', 'desolate'),
    'bright': ('sunny', 'bright', 'daylight'),
    'crowded': ('market', 'plaza'),
    'cosmic': ('space', 'orbit', 'moon', 'cosmic', 'galaxy', 'void'),
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
