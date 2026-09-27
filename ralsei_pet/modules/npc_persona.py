# -*- coding: utf-8 -*-
"""NPC 人设 / 独立记忆 / 跟随决策（第55轮）。

用户口径（第55轮原话，逐字要点）
--------------------------------
* 「我会给你每个人的设定（deepseek生成的），**你给装上就好**」
  「其余我没提到的人物就先不做，主要我觉得那些貌似不算很重要」
* 「具体会不会主动跟随我觉得**可以给 AI 决策**」
* 「4B 貌似没办法支撑起来这些角色的灵魂，所以，给他们也升级成 7B 吧，
  但如果这非常吃性能那就慎重，但**又不是同时运行所有**，应该不至于」
* ★★ 「那这样的话，**每个人都需要分每个人的记忆，不要搞混了**，
  整的和有葫芦娃那个千里眼顺风耳似的那就离谱了」

⇒ 本模块五件事，**互相独立、各自可单测**：
  1. `load_personas()` / `persona_text()` —— 把 `assets/npc/persona/<id>.txt` 读进来；
  2. `MiniMemory` —— ★ **每个 NPC 一份记忆，物理上分开**（不是"约定好别串"）；
  3. `decide_follow()` / `parse_follow_choice()` —— 「要不要主动跟着走」交给 AI 决定，
     模型没表态时**保守地不跟**（而不是替它决定）；
  4. `parse_address()` / `address_aliases()` —— 把「@名字 内容」解析成 `(npc_id, 内容)`，
     **中文名与英文名都认**（两层都扫，见下）；
  5. `build_system_prompt()` / `build_follow_system()` —— 把"人设 + 说话方式 + 他自己
     的记忆 + 此刻"组装成 system prompt 的**唯一出口**（`history_block` 只吃
     `MiniMemory.history(npc_id)` 的返回，所以拼错人的历史在调用层面就写不出来）。

★★ 为什么记忆要"物理分开"而不是"记得别串"
-------------------------------------------
用户用的比喻是「葫芦娃的千里眼顺风耳」—— 那种串味的典型症状是：
甲知道乙说过的话，或者甲把玩家对乙说的话当成对自己说的。
只要数据还是"一个大历史 + 一个 speaker 字段"，就永远存在某一处忘记过滤的可能
（本项目在对话历史、事件台词两条线上都踩过同类坑）。
所以 `MiniMemory` 的内部结构就是 `{npc_id: deque}`，**取历史必须带 npc_id**，
不存在"不带 id 也能拿到全部"的入口 —— 从接口形状上让串味不可表达。
落盘也一样：一个 NPC 一个文件（`<记忆目录>/<id>.json`，记忆目录默认 = `<数据根>/npc_memory`），
不是一个大文件。

零依赖纪律（与 `scene_camera` / `npc_system` / `soul_entity` 同源）
------------------------------------------------------------------
只允许模块顶部 `import collections / json / logging / os`。
**禁 import Qt、禁 import 任何项目内模块**（含 `npc_system`；跟随策略由调用方注入）。
内部函数**不许**再 import（回归锁 `check55` 用 AST 强制）。
"""
import collections
import json
import logging
import os

try:  # 项目内统一 logger；模块外独立导入时降级
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: 人设文件目录（相对 `assets/npc/`）—— 与 `_personas.json` 里的 `file` 前缀一致。
PERSONA_SUBDIR = 'persona'

#: 每个 NPC 记住多少轮（"你好/我说过什么"这种程度够用，不做长篇档案）。
#: ⚠️ 与 Ralsei 自己的拟人记忆（`memory_system`）**不是一回事**，也不共用存储。
MAX_HISTORY = 24

#: 单条记忆的最大字数（超了截断；防一条模型输出把整个记忆撑爆）。
MAX_LINE_CHARS = 240

# ---------------------------------------------------------------- 跟随决策

#: AI 可以表的四个态。值就是给模型看/收回来的字面量。
FOLLOW_FOLLOW = 'follow'    # 跟上去
FOLLOW_STAY = 'stay'        # 待在原地
FOLLOW_RALLY = 'rally'      # 紧跟（比 follow 更贴）
FOLLOW_LEAVE = 'leave'      # 主动离开（回自己的场景去）

FOLLOW_CHOICES = (FOLLOW_FOLLOW, FOLLOW_STAY, FOLLOW_RALLY, FOLLOW_LEAVE)

#: ★ 模型没表态 / 表了看不懂的态时的落点 = **不跟**。
#: 为什么是不跟而不是跟：跟上去是"会改变用户桌面画面"的动作，
#: 而在信息不足时少动一步永远是更安全的一侧（与 `_current_world()` 判不出就取
#: 更保守的一侧同一条道理）。
DEFAULT_FOLLOW_CHOICE = FOLLOW_STAY

#: 模型输出的常见同义写法 → 四态。**只收窄，不发散**（认不出就是 None，由调用方走默认）。
_FOLLOW_ALIASES = {
    'follow': FOLLOW_FOLLOW, '跟': FOLLOW_FOLLOW, '跟随': FOLLOW_FOLLOW,
    '跟着': FOLLOW_FOLLOW, '跟上去': FOLLOW_FOLLOW, 'yes': FOLLOW_FOLLOW,
    'stay': FOLLOW_STAY, '留': FOLLOW_STAY, '留下': FOLLOW_STAY,
    '原地': FOLLOW_STAY, '不动': FOLLOW_STAY, '等待': FOLLOW_STAY,
    'no': FOLLOW_STAY, '等': FOLLOW_STAY,
    'rally': FOLLOW_RALLY, '紧跟': FOLLOW_RALLY, '贴紧': FOLLOW_RALLY,
    'close': FOLLOW_RALLY,
    'leave': FOLLOW_LEAVE, '离开': FOLLOW_LEAVE, '走开': FOLLOW_LEAVE,
    '回去': FOLLOW_LEAVE, 'bye': FOLLOW_LEAVE,
}


def parse_follow_choice(text):
    """模型输出 → 四态之一；认不出返回 `None`（**不猜**）。

    只做"清洗 + 查表"：去空白、去常见标点、转小写、剥掉可能的 JSON 引号与句号。
    不做模糊匹配（"跟一下试试看"这种整句要靠 prompt 约束，不靠这里救）。
    """
    if not isinstance(text, str):
        return None
    s = text.strip().strip('`\'".,。！!？?*【】[]()（）').strip()
    if not s:
        return None
    low = s.lower()
    if low in _FOLLOW_ALIASES:
        return _FOLLOW_ALIASES[low]
    if low in FOLLOW_CHOICES:
        return low
    return None


def decision_reason(choice, source):
    """一行中文摘要（日志 / 自省用）。"""
    return '跟随决策=%s（来源=%s）' % (choice, source)


def decide_follow(ai_choice, policy=None, dist=None, far_threshold=None,
                  world=None, can_follow=True):
    """「这个 NPC 要不要主动跟着走」—— **AI 说了算**，没表态才落回策略。

    用户口径：「具体会不会主动跟随我觉得可以给 AI 决策」。
    所以判定顺序是：

      1. **AI 表态了且是合法态** ⇒ 用它（`source='ai'`）。这是常态路径。
      2. AI 没表态（`None`）或表了一个看不懂的态 ⇒ 落回 `policy`：
         · `policy == 'autonomous'`（主线）⇒ 距离超过 `far_threshold` 时跟（`source='policy'`）
         · `policy == 'consent'`（纯 NPC）⇒ 不主动跟，等主角点（`source='policy'`）
         · `policy` 未知 / `None` ⇒ 不跟（`source='default'`，**保守一侧**）。
      3. `can_follow=False`（世界门控不让跟）⇒ 恒 `stay`（`source='gate'`）。
         门控是**硬约束**，AI 不能靠"想跟"越过去。

    ⚠️ `policy` 由**调用方注入**（`npc_system.FollowPolicy` 的字面量），
       本模块不 import `npc_system` —— 零依赖纪律，与 `event_speech` 同源。

    :param ai_choice: AI 给的态（`FOLLOW_CHOICES` 之一 / 同义写法 / `None`）。
    :return: `(choice, source)`；`source ∈ {'ai', 'policy', 'default', 'gate'}`。
    """
    if not can_follow:
        return (FOLLOW_STAY, 'gate')
    ch = parse_follow_choice(ai_choice) if isinstance(ai_choice, str) else ai_choice
    if ch in FOLLOW_CHOICES:
        return (ch, 'ai')
    policy = policy if isinstance(policy, str) else ''
    if policy == 'autonomous':
        if far_threshold is None or dist is None:
            # 判据不全 ⇒ 不硬判（本项目铁律：算不出就别猜）
            return (FOLLOW_STAY, 'default')
        try:
            far = float(dist) > float(far_threshold)
        except (TypeError, ValueError):
            return (FOLLOW_STAY, 'default')
        return (FOLLOW_FOLLOW if far else FOLLOW_STAY, 'policy')
    if policy == 'consent':
        return (FOLLOW_STAY, 'policy')
    return (DEFAULT_FOLLOW_CHOICE, 'default')


def build_follow_prompt(npc_name, dist=None, current=None, world=None):
    """给 AI 的「要不要跟着走」的问句（纯文本，不含任何状态副作用）。

    与 `event_speech.build_prompt` 同一形状：**只造 prompt，不发请求**。
    要求模型**只回一个词**（`follow` / `stay` / `rally` / `leave`），
    这样 `parse_follow_choice` 就能确定性地解析 —— 让模型自由发挥再靠正则猜，
    是"看着在工作、其实在猜"的那类写法，本项目不采用。
    """
    parts = ['你现在在决定要不要跟用户走。']
    if isinstance(npc_name, str) and npc_name.strip():
        parts.append('你扮演的是 %s。' % npc_name.strip())
    if world in ('light', 'dark'):
        parts.append('当前在%s世界。' % ('光' if world == 'light' else '暗'))
    if dist is not None:
        try:
            parts.append('用户离你大约 %.0f 像素。' % float(dist))
        except (TypeError, ValueError):
            pass
    if isinstance(current, str) and current in FOLLOW_CHOICES:
        parts.append('你现在是「%s」。' % current)
    parts.append('只回一个词，必须是这四个之一：follow（跟上去）、stay（待着不动）、'
                 'rally（紧跟）、leave（离开回自己那边）。不要解释，不要标点，不要换行。')
    return ''.join(parts)


# ---------------------------------------------------------------- 人设装载

def persona_dir(root=None, assets_dir=None):
    """人设目录绝对路径。`root` = 项目根（含 `assets/`）；`assets_dir` 优先。"""
    base = assets_dir
    if base is None:
        if root is None:
            here = os.path.dirname(os.path.abspath(__file__))
            base = os.path.join(here, '..', 'assets')
        else:
            base = os.path.join(root, 'assets')
    return os.path.abspath(os.path.join(base, 'npc', PERSONA_SUBDIR))


def load_index(root=None, assets_dir=None):
    """读 `assets/npc/_personas.json`。读不到 / 坏 JSON ⇒ 返回 `{}`（**不抛**）。"""
    base = assets_dir
    if base is None:
        if root is None:
            here = os.path.dirname(os.path.abspath(__file__))
            base = os.path.join(here, '..', 'assets')
        else:
            base = os.path.join(root, 'assets')
    path = os.path.join(base, 'npc', '_personas.json')
    try:
        with open(path, 'rb') as fh:
            data = json.loads(fh.read().decode('utf-8'))
    except Exception as e:
        _log.warning('人设索引读不到（%s）：%s', path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_personas(root=None, assets_dir=None, index=None):
    """`{npc_id: 人设全文}`。

    ★ 判据是**磁盘**而不是索引：索引说"有"，文件不在也算没有（并记 warning）。
      反过来，索引里没登记但目录下有 `<id>.txt` 的，也**不**自动收录 ——
      那会让"我明明删了这条"变成"它又自己回来了"（本项目最烦的那类惊喜）。
    """
    idx = load_index(root, assets_dir) if index is None else index
    recs = idx.get('personas') if isinstance(idx, dict) else None
    out = {}
    d = persona_dir(root, assets_dir)
    for rec in (recs or ()):
        if not isinstance(rec, dict):
            continue
        nid = rec.get('id')
        rel = rec.get('file')
        if not isinstance(nid, str) or not nid or not isinstance(rel, str):
            continue
        path = os.path.join(d, os.path.basename(rel))
        try:
            with open(path, 'rb') as fh:
                raw = fh.read()
        except Exception as e:
            _log.warning('NPC %s 的人设文件读不到（%s）：%s', nid, path, e)
            continue
        text = raw.decode('utf-8')
        if raw[:3] == b'\xef\xbb\xbf':
            _log.warning('NPC %s 的人设文件带 BOM（已按 UTF-8 读，内容可能多一个字符）', nid)
        if '\ufffd' in text:
            _log.warning('NPC %s 的人设文件含 U+FFFD（编码可疑）', nid)
        out[nid] = text
    return out


def persona_text(npc_id, personas=None, root=None, assets_dir=None):
    """单个 NPC 的人设全文；没有 ⇒ `None`（**不返回空串**，空串会被当成"有人设但空的"）。"""
    if personas is None:
        personas = load_personas(root, assets_dir)
    if not isinstance(npc_id, str):
        return None
    t = personas.get(npc_id)
    return t if isinstance(t, str) and t.strip() else None


def has_persona(npc_id, personas=None, root=None, assets_dir=None):
    return persona_text(npc_id, personas, root, assets_dir) is not None


# ---------------------------------------------------------------- 独立记忆

class MiniMemory(object):
    """★ **每个 NPC 一份、物理分开的记忆**。

    结构就是 `{npc_id: deque(maxlen=MAX_HISTORY)}`。三条设计约束：

    1. **取历史必须带 `npc_id`** —— 没有 `all()` / `everyone()` 这种入口，
       所以"忘了过滤导致串味"在接口层面就写不出来（用户最担心的那个问题）。
    2. **一条记忆 = 一个 dict**（`who` / `text` / `scene`），不拼成一整段字符串 ——
       拼字符串之后就没法再问"这句是谁说的"了。
    3. **落盘一角色一文件**（`<dir>/<id>.json`）。不是"一个大文件按 id 分桶"：
       分桶写法只要有一处忘了带过滤就会串，而分成文件之后，
       读一个 NPC 的记忆**在文件系统层面**就只碰得到它自己的数据。

    `root=None` ⇒ 纯内存态（可离线单测，也用于"不想落盘"的场景）。
    """

    def __init__(self, root=None, maxlen=MAX_HISTORY):
        self.root = root
        try:
            self.maxlen = max(1, int(maxlen))
        except (TypeError, ValueError):
            self.maxlen = MAX_HISTORY
        self._by_npc = collections.OrderedDict()

    # -- 内部
    def _deque(self, npc_id):
        """取（必要时建）某个 NPC 的队列。**唯一的取队列入口**，因此无法绕过 id。"""
        if not isinstance(npc_id, str) or not npc_id:
            return None
        dq = self._by_npc.get(npc_id)
        if dq is None:
            dq = collections.deque(maxlen=self.maxlen)
            self._by_npc[npc_id] = dq
        return dq

    def path_of(self, npc_id):
        """该 NPC 的记忆文件路径；`root=None` 或无 id ⇒ `None`（**不伪造路径**）。

        ⚠️ `root` 就是**放这些文件的目录本身**（不是"数据根"）—— 目录由调用方给，
        默认由 `memory_root(数据根)` 算出 `<数据根>/npc_memory`。
        这里**不再**自己拼一层 `npc_memory`：那会让调用方给的目录白白多套一层
        （曾经写成 `<root>/npc_memory/<id>.json`，与 `memory_root` 叠加成双层路径）。
        """
        if not self.root or not isinstance(npc_id, str) or not npc_id:
            return None
        safe = ''.join(c for c in npc_id if c.isalnum() or c in '_-')
        if not safe:
            return None
        return os.path.join(self.root, '%s.json' % safe)

    # -- 写
    def remember(self, npc_id, text, who='player', scene=None):
        """记一句。`who` = 谁说的（`'player'` / 该 NPC 自己的 id / 别的 id）。

        空文本 / 非法 id ⇒ 返回 `False`（**不记空条**：空条会让"上一条是谁说的"失准）。
        """
        dq = self._deque(npc_id)
        if dq is None:
            return False
        if not isinstance(text, str):
            return False
        t = text.strip()
        if not t:
            return False
        if len(t) > MAX_LINE_CHARS:
            t = t[:MAX_LINE_CHARS]
        dq.append({'who': who if isinstance(who, str) and who else 'unknown',
                   'text': t, 'scene': scene if isinstance(scene, str) else None})
        return True

    def forget(self, npc_id):
        """清掉某个 NPC 的记忆（**只清他一个**）。返回清掉的条数；未知 id ⇒ 0。"""
        dq = self._by_npc.get(npc_id)
        if dq is None:
            return 0
        n = len(dq)
        dq.clear()
        return n

    def clear(self):
        """清光（测试/隐私重置用）。返回清掉的 NPC 数。"""
        n = len(self._by_npc)
        self._by_npc = collections.OrderedDict()
        return n

    # -- 读
    def history(self, npc_id, limit=None):
        """★ 取某个 NPC 的历史（**必须给 id**）。返回 `list[dict]` 的浅拷贝。

        未知 id ⇒ `[]`（**不返回别人的** —— 这就是"不串味"的正面表达）。
        """
        dq = self._by_npc.get(npc_id)
        if not dq:
            return []
        items = list(dq)
        if limit is not None:
            try:
                k = int(limit)
                if k >= 0:
                    items = items[-k:] if k else []
            except (TypeError, ValueError):
                pass
        return items

    def last_from(self, npc_id):
        """该 NPC 记忆里最后一条是谁说的；没有 ⇒ `None`。"""
        dq = self._by_npc.get(npc_id)
        if not dq:
            return None
        return dq[-1].get('who')

    def lines(self, npc_id, limit=None):
        """该 NPC 的历史文本（`['甲：…', ...]` 形状，供拼 prompt 用）。"""
        return ['%s：%s' % (it.get('who'), it.get('text'))
                for it in self.history(npc_id, limit)]

    def ids(self):
        """有记忆的 NPC id（**这是唯一"一次看很多个"的入口，且只给 id，不给内容**）。"""
        return sorted(self._by_npc)

    def __len__(self):
        return len(self._by_npc)

    def count_of(self, npc_id):
        dq = self._by_npc.get(npc_id)
        return len(dq) if dq else 0

    def describe(self):
        return '独立记忆 %d 个角色：%s' % (len(self._by_npc),
                                        '、'.join('%s(%d)' % (k, len(v))
                                                  for k, v in self._by_npc.items()))

    # -- 落盘
    def save(self, npc_id):
        """把某个 NPC 的记忆写进他自己的文件。成功返回路径，否则 `None`。"""
        path = self.path_of(npc_id)
        if path is None:
            return None
        dq = self._by_npc.get(npc_id)
        if dq is None:
            return None
        payload = {'schema_version': SCHEMA_VERSION, 'npc_id': npc_id,
                   'items': list(dq)}
        try:
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            tmp = path + '.tmp'
            with open(tmp, 'wb') as fh:
                fh.write(json.dumps(payload, ensure_ascii=False,
                                    indent=1).encode('utf-8') + b'\n')
            os.replace(tmp, path)
            return path
        except Exception as e:
            _log.warning('NPC %s 记忆落盘失败（%s）：%s', npc_id, path, e)
            return None

    def load(self, npc_id):
        """从该 NPC 自己的文件读回。文件不在 / 坏 ⇒ 返回 `0`（**不抛、不猜**）。"""
        path = self.path_of(npc_id)
        if path is None or not os.path.isfile(path):
            return 0
        try:
            with open(path, 'rb') as fh:
                data = json.loads(fh.read().decode('utf-8'))
        except Exception as e:
            _log.warning('NPC %s 记忆读回失败（%s）：%s', npc_id, path, e)
            return 0
        items = data.get('items') if isinstance(data, dict) else None
        if not isinstance(items, list):
            return 0
        dq = self._deque(npc_id)
        dq.clear()
        n = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            txt = it.get('text')
            if not isinstance(txt, str) or not txt.strip():
                continue
            dq.append({'who': it.get('who') or 'unknown',
                       'text': txt[:MAX_LINE_CHARS],
                       'scene': it.get('scene') if isinstance(it.get('scene'), str) else None})
            n += 1
        return n

    def save_all(self):
        """把所有有记忆的角色各自落盘。返回成功写出的文件数。"""
        if not self.root:
            return 0
        n = 0
        for nid in list(self._by_npc):
            if self.save(nid):
                n += 1
        return n


def memory_root(data_root):
    """`MiniMemory` 的落盘目录：`<data_root>/npc_memory`（**直接传给 `MiniMemory(root=)`**）。

    ⚠️ 为什么由调用方传入 `data_root`（= `data_store` 的数据根）而不是本模块自己找：
       那是**初始化环**的老坑（`memory_system` / `relationship` 都栽过 4 次），
       而本模块是零依赖的，找不到就退内存态 —— 不抛、不静默写错地方。
    ⚠️ 与 `MiniMemory.path_of` 的分工：**只有这里**拼 `npc_memory` 这一层，
       `MiniMemory.root` 就是"放文件的那个目录"，不再自己拼 —— 两边都拼会变成双层路径。
    """
    if not isinstance(data_root, str) or not data_root.strip():
        return None
    return os.path.abspath(os.path.join(data_root, 'npc_memory'))


# ---------------------------------------------------------------- 定向称呼（@名字）

#: 名字候选的长度上限（"@超级无敌长的名字"这种不该被当成一次点名）。
#: ★ 取 24 而不是 12：英文全名带空格（`Asgore Dreemurr` 15 / `Noelle Holiday` 14 /
#:   `Rouxls Kaard` 12）**必须放得下** —— 本项目已经因为"判据太窄"误报过好几次。
ADDRESS_MAX_NAME = 24


def address_aliases(items):
    """`[(id, name, name_cn), ...]` → `{别名(小写): npc_id}`。

    ★ 三个别名都收（`id` / 英文名 / 中文名）：本项目已经踩过一次
      「命名 = 不译 ⇒ 『教堂』不在场景名里」的坑（第46轮别名表），
      所以点名一律**两层都认**，而不是只认 id。
    ★ 先到先得（`setdefault`）：调用方按 `id → name → name_cn` 顺序传，
      于是"某个别名同时属于两个人"时，**胜出的是排在前面的那个**，
      而不是后写覆盖（覆盖会让结果依赖遍历顺序，不可复现）。
    """
    out = {}
    for rec in (items or ()):
        try:
            nid, name, cn = rec[0], rec[1], rec[2]
        except (TypeError, IndexError):
            continue
        if not isinstance(nid, str) or not nid.strip():
            continue
        for alias in (nid, name, cn):
            if isinstance(alias, str) and alias.strip():
                out.setdefault(alias.strip().lower(), nid.strip())
    return out


def match_name_prefix(text, aliases):
    """在 `text` **开头**用**最长**别名匹配。返回 `(npc_id, 消耗字符数)` 或 `None`。

    ★ 三条判据（缺一条都会出假结果）：
      1. **边界**：别名后面必须是 空白 / 冒号 / 结尾 —— 否则 `susiex` 会被当成 `susie`
         （"名字后面还能接着字母"就不叫点名了）；
      2. **最长优先**：别名互为前缀时取长的那条（`susie` vs `susie dark`），
         否则短名会把长名吃掉一半；
      3. 长度 ≤ `ADDRESS_MAX_NAME`。
    """
    if not isinstance(text, str) or not text or not isinstance(aliases, dict):
        return None
    low = text.lower()
    best = None
    for alias, nid in aliases.items():
        n = len(alias)
        if n == 0 or n > ADDRESS_MAX_NAME:
            continue
        if not low.startswith(alias):
            continue
        nxt = text[n:n + 1]
        if nxt and (not nxt.isspace()) and nxt not in '：:':
            continue
        if best is None or n > best[1]:
            best = (nid, n)
    return best


def parse_address(text, aliases):
    """`'@susie 你好'` / `'@ 苏西：你好'` / `'苏西：你好'` → `('susie', '你好')`。

    认不出 ⇒ `None`（**不猜**）。只认两种**明确点名**的写法：

      * `@名字`（前缀 `@` 或全角 `＠`）—— `@` 后面可有空白，名字由
        `match_name_prefix` 按最长别名匹配（所以 `@Rouxls Kaard hi` 也成立）；
      * `名字：` / `名字:` —— 冒号前的**整段**必须正好是一个别名
        （中文冒号与英文冒号都认；这一条故意从严：冒号前面常常是半句话，
        "整段就是名字"才说明是在点名）。

    点名了但没内容 ⇒ 返回 `(npc_id, '')`（**不是 `None`**）：
    "叫了一声但没说话"和"压根没点名"是两件事，调用方要能分开处理。
    """
    if not isinstance(text, str) or not isinstance(aliases, dict) or not aliases:
        return None
    s = text.strip()
    if not s:
        return None
    if s[0] in ('@', '＠'):
        body = s[1:].lstrip()
        m = match_name_prefix(body, aliases)
        if m is None:
            return None
        nid, n = m
        return (nid, body[n:].lstrip().lstrip('：:').strip())
    picks = [k for k in (s.find('：'), s.find(':')) if k > 0]
    if not picks:
        return None
    i = min(picks)
    head = s[:i].strip()
    m = match_name_prefix(head, aliases)
    if m is None or m[1] != len(head):
        return None
    return (m[0], s[i + 1:].strip())


# ---------------------------------------------------------------- system prompt 组装

#: 说话方式约束（**所有 NPC 共用一份**，与 Ralsei 的 `ralsei_persona.md` 同口径）。
#: 为什么必须显式写"别自称 AI / 别用 markdown / 一次 1~3 句"：
#:   人设原文是"角色扮演提示词"，它假设的是**聊天框里只有这个角色**；
#:   而这里是桌宠场景，模型很容易顺手加小标题、分点、或者自称"作为 AI"。
#: 为什么**不**把 Ralsei 那段整块复制过来：那段里有"平级、不叫主人"等**针对 Ralsei**
#:   的措辞，NPC 人设各有各的关系设定（比如仆从类角色），套上去会互相打架。
SPEAK_RULES = (
    "【说话方式】你就是这个角色本人，不要自称 AI、不要提模型或提示词。"
    "一次只说 1~3 句，像真人在聊天框里随手打字：不要分点、不要小标题、不要加粗、"
    "不要写 markdown 标记，也不要用括号描写动作。只回应对方这句话本身，"
    "不要复述对方的话，不要替别的角色说话。"
)


def history_block(entries, npc_id=None, max_lines=12):
    """把**某一个 NPC 自己**的记忆折成提示词段落。没有任何记忆 ⇒ `''`。

    `entries` 只能是 `MiniMemory.history(npc_id)` 的返回值 —— 本函数**不接受**
    "全部记忆"，所以"拼错人的历史"在调用层面就写不出来（与 `MiniMemory` 同一条思路）。
    """
    rows = []
    for it in (entries or ())[-max_lines:]:
        if not isinstance(it, dict):
            continue
        txt = it.get('text')
        if not isinstance(txt, str) or not txt.strip():
            continue
        who = it.get('who') or ''
        if npc_id and who == npc_id:
            rows.append('你说过：%s' % txt.strip())
        elif who == 'player':
            rows.append('对方说过：%s' % txt.strip())
        else:
            rows.append('%s 说过：%s' % (who or '别人', txt.strip()))
    if not rows:
        return ''
    return ('【你记得的事（只有你自己的记忆，别人经历的事你并不知道）】\n'
            + '\n'.join(rows))


def build_system_prompt(npc_name, persona, entries=None, npc_id=None, context=''):
    """某个 NPC 的 system prompt —— **唯一出口**。

    结构（顺序即含义）：
      ① 人设正文（用户给的原文，**不再改写**）；
      ② `SPEAK_RULES`（说话方式硬约束）；
      ③ 他自己的记忆（`history_block`）；
      ④ 此刻状态（`context`，由宿主提供）。

    `persona` 为空 ⇒ 返回 `''`（调用方据此**拒绝**这次对话，而不是发一份空人设
    过去让模型自由发挥 —— 那正是"人设没装上但看起来在工作"的假象）。
    """
    if not isinstance(persona, str) or not persona.strip():
        return ''
    parts = [persona.rstrip(), SPEAK_RULES]
    hb = history_block(entries, npc_id=npc_id)
    if hb:
        parts.append(hb)
    if isinstance(context, str) and context.strip():
        parts.append(context.strip())
    return '\n\n'.join(parts)


def speaker_label(npc_name, name_cn=None):
    """对话里显示的名字（有中文名取中文名，否则取英文名）。空 ⇒ `''`。"""
    for cand in (name_cn, npc_name):
        if isinstance(cand, str) and cand.strip():
            return cand.strip()
    return ''


#: 「要不要跟着走」是个**只回一个词**的问答 —— 为此把整份人设（上万字）送去 prefill
#: 太亏（7B 纯 CPU，prefill 远慢于 decode，本项目"首字铁律"）。但一个字不给，决策
#: 又会丢掉性格。折中：取人设**开头**一段（身份/性格通常在最前），并保证**不切在半句里**。
FOLLOW_PERSONA_BRIEF = 600


def persona_brief(persona, max_chars=FOLLOW_PERSONA_BRIEF):
    """人设开头一段（按行边界截，**不切在半句中间**）。空/非法 ⇒ `''`。

    ★ 宁可短也不要断句：截断点只认换行，所以取出来的永远是**整句**。
      如果第一行本身就超长（没人设分段），退回"整段照给"而不是硬切 ——
      硬切出来的半句话喂给模型比不给更糟。
    """
    if not isinstance(persona, str) or not persona.strip():
        return ''
    try:
        cap = int(max_chars)
    except (TypeError, ValueError):
        cap = FOLLOW_PERSONA_BRIEF
    if cap <= 0:
        return ''
    s = persona.strip()
    if len(s) <= cap:
        return s
    head = s[:cap]
    cut = head.rfind('\n')
    if cut <= 0:
        # 第一段就超长 ⇒ 不硬切（切了就是半句），整段照给
        nxt = s.find('\n')
        return s if nxt < 0 else s[:nxt]
    return head[:cut].strip()


def build_follow_system(npc_name, persona, dist=None, current=None, world=None):
    """「要不要跟着走」这一次请求的 system（人设开头 + 只回一个词的问句）。"""
    parts = []
    b = persona_brief(persona)
    if b:
        parts.append(b)
    parts.append(build_follow_prompt(npc_name, dist=dist, current=current, world=world))
    return '\n\n'.join(parts)
