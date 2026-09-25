# -*- coding: utf-8 -*-
"""伙伴对话层 —— 「谁在跟谁说话」的协议层（L2）。

回答用户这条需求（第 46 轮）：
    「那个交互系统你仔细研究一下吧，就是到时候能做到和真人间对话一样就好」
    「要让他们能有自主互相聊天的功能，但不会导致 AI 之间分不清是谁和谁说话」

★ 本层要解决的**唯一**问题是「发言人身份不许被猜」
--------------------------------------------------
多宠物自主聊天时，"分不清谁跟谁说话"有三个**互不相同**的失败模式，必须分开治：

| 失败模式 | 具体症状 | 本层的对策 |
|---|---|---|
| **A. 无主消息** | 模型没写说话人，渲染层靠"上一条是谁"猜 | `from_id` **必填**；缺失 ⇒ 消息**不进历史**、UI 显式标 `[未知说话人]` |
| **B. 张冠李戴** | 把 A 的发言归到 B 名下 | 进 prompt 的**每一行**都写成 `[名字] 文本`；**不允许裸文本入 prompt** |
| **C. 自称混乱** | A 在文本里自称成 B | 人设里显式告知本名 + 输出护栏 `check_reply()`（说了别人的名字 ⇒ 判退重采样） |
| **D. 代他人发言** | 一条消息里出现 `Susie：滚` 这种"别人开了口"的行 | `check_reply()` 的**外资说话人检测** |

原作依据（`scr_anyface`，第 46 轮 ch5 反编译实证）::

    _speaker = string_lower(_speakerC);
    if (_speaker == "susie" || _speaker == "sus")  scr_susface(...);
    if (_speaker == "ralsei" || _speaker == "ral") scr_ralface(...);
    ── 名字（含别名、大小写不敏感）→ 说话实现 的 dispatch 表 ──

⇒ 原作的身份主键是**字符串名字**，且**带兜底**（找不到就渲染 `"* Face ~1 not found/"`）。
我们照抄"名字 + 别名"，但把兜底从"渲染一段占位文本"升级为
**"如实报错 + 不让人进历史"** —— 因为原作的兜底是给玩家看的，
而我们的兜底要给"下一轮 prompt"看，一段占位文本会被模型当成真话学走。

零依赖纪律（🔴 与 companion / scene_system 同源）
------------------------------------------------
本模块**只用标准库**（`dataclasses` / `logging` / `re`）。

⚠️ 这里与《伙伴交互系统_框架设计_2026-09-25.md》§1 写的"L2 可 import 项目内
对话/护栏模块"**有意不同**，理由两条：
  1. **初始化环**：`main.py` 在 import 期建控制器；若 L2 反向 import `main`
     或 `dialogue_ui`，环就接上了（本项目已踩 4 次）。
  2. **可测性**：现有的清洗护栏 `RalseiPet._clean_ai_reply(reply, recent=)`
     是**宿主类的方法**，把它 import 进来会让本层离不开那个宿主。
⇒ 改为**注入**：接线层把 `cleaner=...` 回调传进来即可（默认 `None` = 不清洗）。
   `check_reply()` 只做"身份类"判定，措辞类清洗仍归 `_clean_ai_reply`（职责不重叠）。
"""
import collections
import dataclasses
import logging
import re

# ★ 唯一允许的项目内依赖：L1 `companion`（本身零依赖，不构成初始化环）。
#   放在**顶层**而不是函数里 —— 见本文件头「零依赖纪律」的补充约定：
#   三个 companion* 模块一律**不许有函数内 import**，依赖必须全部写在文件顶部，
#   这样"依赖清单能否用 AST 一次看全"就不再取决于调用路径。
from companion import normalize_id as _normalize_id

_log = logging.getLogger(__name__)

# ===========================================================================
#  常量
# ===========================================================================

#: ★ 消息类别。对应原作的差异在「有没有 face 脚本」：
#:   · `speech`  —— 角色说话（`scr_ralface` 等）
#:   · `action`  —— 角色动作/神态（也归到角色名下，但 UI 可斜体）
#:   · `narrate` —— 旁白（原作 `scr_noface`：**没有**说话人）
#:   · `system`  —— 系统提示（不属于任何角色）
KIND_SPEECH = 'speech'
KIND_ACTION = 'action'
KIND_NARRATE = 'narrate'
KIND_SYSTEM = 'system'
KINDS = (KIND_SPEECH, KIND_ACTION, KIND_NARRATE, KIND_SYSTEM)

#: ★ 必须有说话人的类别。`narrate` / `system` 允许 `from_id = None`。
KINDS_REQUIRE_SPEAKER = (KIND_SPEECH, KIND_ACTION)

#: ★ 打字机默认速度 —— 照抄 `scr_writetext` 的 `global.typer = 5;`
DEFAULT_TYPER = 5

#: ★ 表情/头像缺省值 —— 照抄 `scr_writetext` 的 `global.fc = 0;`（0 = 不换头像）。
NO_FACE = 0

#: 说话人缺省时的显示标签。**显式可见**是本层的全部意义所在。
UNKNOWN_SPEAKER = '未知说话人'

#: 单条消息长度上限。★ 必须与 `main.RalseiPet.AI_REPLY_MAX_CHARS` 同值
#: （由 `verify_companion46.B4` 从 main.py 源码解析后交叉断言，防两边漂移）。
MAX_TEXT_CHARS = 220

#: 消息正文里的"别人的发言行"模式：行首（剥掉装饰后）`名字` + 可选 `说/说道` + `：`，
#: 或者 `名字]` / `名字】` 这种"我们自己上下文格式"的收尾括号。
#: ★ 两条**故意收窄**的取舍（判据过窄会误报、过宽会恒真，两边都要防）：
#:   · **只认行首** —— 句中提到某人的名字是正常说话（"Susie 你怎么了"不是代发言）；
#:   · **只认冒号/收尾括号** —— 不认光秃秃的 `Susie说…`，因为"Susie说她不喜欢"
#:     是正当的转述，把它判成违规会导致无谓的重采样。
_LEAD_JUNK = r'[\s\u3000\*#>\-·•「『"\'（(【\[]*'
_LEAD_JUNK_RE = re.compile(r'^' + _LEAD_JUNK)
_FOREIGN_TAIL_RE = re.compile(r'^(?:(?:说道?)\s*)?[：:]')
_FOREIGN_CLOSE = (']', '】', '）', ')')

#: 「自称」模式。只认这几种**明确的自称**；不做"任何名字出现都算"的粗暴匹配
#: （那会把"Ralsei 说得好"这种转述也判成违规 ⇒ 判据过窄过宽都是错）。
_SELF_CLAIM = ('我是', '我叫', '我的名字是', '我叫作', '我是叫',
               "i'm ", 'i am ', 'my name is ')

#: 自称后面允许夹的装饰字符（引号/括号/空白）—— 之后必须**紧跟**名字才算。
_CLAIM_JUNK = ' \t\u3000"\'「『（(['


# ===========================================================================
#  消息模型
# ===========================================================================

@dataclasses.dataclass
class Message(object):
    """一条消息。四元组照抄 `scr_writetext(msc, msg, fc, typer)` + 我们的 to_id。

    · `from_id` —— ★ **必填**（`narrate` / `system` 除外）。说话人的 `speaker_id`。
    · `to_id`   —— 可选。**仅"点名"时使用**（`ralsei → susie`）；
                   `None` = 对所有人说。渲染成 `[a→b]` 而不是 `[a]`，
                   这就是"谁跟谁说话"的**可见答案**。
    · `text`    —— 正文。
    · `expr`    —— 表情变体（对应原作的 `emotion` 参数 / `global.fc`）。
    · `typer`   —— 打字机速度（0 = 用默认 5，同原作 `if (typer != 0)`）。
    · `kind`    —— 见上面的 `KIND_*`。
    · `seq`     —— 序号（由 `DialogueLog` 填，便于排序/去重）。
    """

    text: str = ''
    from_id: object = None
    to_id: object = None
    expr: object = NO_FACE
    typer: int = DEFAULT_TYPER
    kind: str = KIND_SPEECH
    seq: int = 0

    # ---------------------------------------------------------------- 属性
    @property
    def effective_typer(self):
        """真正生效的打字速度（0 ⇒ 默认 5，照抄原作 `if (typer != 0) global.typer = typer;`）。"""
        try:
            t = int(self.typer)
        except Exception:
            return DEFAULT_TYPER
        return t if t > 0 else DEFAULT_TYPER

    @property
    def is_self_speaking(self):
        """是不是"角色在说话"（而非旁白/系统）。"""
        return self.kind in KINDS_REQUIRE_SPEAKER

    # ---------------------------------------------------------------- 校验
    def validate(self, known_ids=None, alias_map=None):
        """→ `(ok, reason)`。`reason` 是**机器可读**的短标签 + 细节，便于统计。

        ★ §4.2 铁律 1：**不猜、不默认**。任何一条不满足就如实拒绝。
        `known_ids` 为 `None` 表示"不校验身份是否存在"（只校验形状）。
        """
        if self.kind not in KINDS:
            return False, 'bad_kind:%r' % (self.kind,)

        if not isinstance(self.text, str) or not self.text.strip():
            return False, 'empty_text'
        if len(self.text) > MAX_TEXT_CHARS:
            return False, 'too_long:%d>%d' % (len(self.text), MAX_TEXT_CHARS)

        try:
            t = int(self.typer)
        except Exception:
            return False, 'bad_typer:%r' % (self.typer,)
        if t < 0:
            return False, 'bad_typer:%d' % t

        frm = _resolve(self.from_id, alias_map)
        if self.is_self_speaking:
            if not frm:
                return False, 'missing_from'
            if known_ids is not None and frm not in known_ids:
                return False, 'unknown_from:%r' % (self.from_id,)
        else:
            # 旁白/系统：允许 None；给了名字则必须是已知的人（不然就是"编了个说话人"）。
            if frm and known_ids is not None and frm not in known_ids:
                return False, 'unknown_from:%r' % (self.from_id,)

        to = _resolve(self.to_id, alias_map)
        if to:
            if known_ids is not None and to not in known_ids:
                return False, 'unknown_to:%r' % (self.to_id,)
            if frm and to == frm:
                return False, 'self_talk'
        return True, ''

    def norm_from(self, alias_map=None):
        """归一后的说话人 id（解析不出来 ⇒ `None`）。"""
        return _resolve(self.from_id, alias_map)

    def norm_to(self, alias_map=None):
        return _resolve(self.to_id, alias_map)

    def __repr__(self):
        return '<Message %s→%s %r kind=%s>' % (
            self.from_id, self.to_id, (self.text or '')[:20], self.kind)


def _resolve(name, alias_map):
    """名字 → `speaker_id`。`alias_map` 为 `None` 时只做形状归一。"""
    n = _normalize_id(name)
    if not n:
        return None
    if alias_map:
        return alias_map.get(n, n)
    return n


# ===========================================================================
#  上下文格式化（★ §4.2 铁律 2：每一行都带名字前缀）
# ===========================================================================

def format_line(msg, display=None, known_ids=None, alias_map=None):
    """单行上下文：`[a] 文本` / `[a→b] 文本`。

    ★ **绝不允许裸文本**：`from_id` 缺失或解析不出来时，
    前缀是 `[未知说话人]` / `[未知说话人:原始值]`，而不是把文本裸着塞进去。
    这条是"张冠李戴"唯一的根治手段 —— 只要进了 prompt 的每行都有主，
    模型就没有"上面那句是谁说的"的可猜空间。

    ★ `alias_map` **必须传**（`DialogueLog.context_lines()` 已经传了）：
    不传的话，伙伴用别名说话时（`from_id='ral'`）会命中 `unknown_from`
    分支、被打成 `[未知说话人:ral]` —— 身份明明认识，却显示成不认识。
    这是首版实测踩到的一个真 bug。
    """
    display = display or {}
    frm_raw = msg.from_id
    frm = _resolve(frm_raw, alias_map)
    if not frm:
        label = UNKNOWN_SPEAKER
    else:
        label = display.get(frm, frm)
        if known_ids is not None and frm not in known_ids:
            label = '%s:%s' % (UNKNOWN_SPEAKER, frm_raw)
    to_raw = msg.to_id
    to = _resolve(to_raw, alias_map)
    if to:
        to_label = display.get(to, to)
        if known_ids is not None and to not in known_ids:
            to_label = '%s:%s' % (UNKNOWN_SPEAKER, to_raw)
        return '[%s→%s] %s' % (label, to_label, msg.text)
    return '[%s] %s' % (label, msg.text)


def format_context(msgs, display=None, known_ids=None, alias_map=None):
    """把消息列表拼成 prompt 用的多行文本。空列表 → 空串（不是 None）。"""
    return '\n'.join(format_line(m, display, known_ids, alias_map)
                     for m in (msgs or ()))


# ===========================================================================
#  输出护栏（★ §4.2 铁律 3 + 4）
# ===========================================================================

def _name_tokens(name_index):
    """`{归一名字: speaker_id}` → 按名字长度**降序**（长名优先，避免"sus"吃掉"susie"）。"""
    items = [(n, sid) for n, sid in (name_index or {}).items() if n]
    items.sort(key=lambda kv: (-len(kv[0]), kv[0]))
    return items


def detect_foreign_speaker_lines(text, speaker_id, name_index):
    """★ 失败模式 D：一条消息里出现了**别人开的头**。

    返回 `[(名字, 原始行), ...]`（空列表 = 干净）。判定规则：
    把行首的装饰字符（`*` `#` `>` `「` `[` `(` 引号…）剥掉后，
    若**紧跟**另一个伙伴的名字，且名字后面是 `]` / `】` / `）` 这类收尾符，
    或者是 `：` / `:` / `说：` / `说道:` ⇒ 这一行是"别人在说话"。

    只认行首 + 只认冒号/收尾括号（见常量注释里的两条收窄取舍）。
    """
    if not isinstance(text, str) or not text:
        return []
    me = _normalize_id(speaker_id)
    tokens = _name_tokens(name_index)
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        core = stripped[_LEAD_JUNK_RE.match(stripped).end():]
        if not core:
            continue
        low = core.lower()
        for name, sid in tokens:
            if sid == me:
                continue                      # ★ 自己开的头不算"外资"
            if not low.startswith(name):
                continue
            rest = low[len(name):].lstrip()
            if not rest:
                continue                      # 整行只有别人的名字 ⇒ 无从判断，放过
            if rest[0] in _FOREIGN_CLOSE or _FOREIGN_TAIL_RE.match(rest):
                out.append((name, stripped))
                break
    return out


def detect_wrong_self_claim(text, speaker_id, name_index):
    """★ 失败模式 C：A 在正文里**自称成 B**。

    返回 `[(被冒充的名字, 片段), ...]`（空列表 = 干净）。
    只认 `我是X` / `我叫X` / `my name is X` 这类**明确自称**，
    且要求名字**紧跟**在自称词之后（中间只许有引号/空白）——
    这样"我是说，Susie…"不会被误判。
    """
    if not isinstance(text, str) or not text:
        return []
    me = _normalize_id(speaker_id)
    low = text.lower()
    out = []
    for claim in _SELF_CLAIM:
        start = 0
        while True:
            i = low.find(claim, start)
            if i < 0:
                break
            start = i + len(claim)
            j = i + len(claim)
            while j < len(low) and low[j] in _CLAIM_JUNK:
                j += 1
            rest = low[j:]
            for name, sid in _name_tokens(name_index):
                if sid == me:
                    continue
                if rest.startswith(name):
                    frag = text[max(0, i - 4):j + len(name) + 6]
                    out.append((name, frag))
                    break
    return out


def check_reply(text, speaker_id, name_index=None, max_chars=None):
    """身份类输出护栏 —— 返回 `(ok, reason)`。reason 空串 = 通过。

    只查**身份**两件事（自称 / 代他人发言）+ 长度。
    括号、markdown、禁说"主人"、自问自答、车轱辘话**仍归** `_clean_ai_reply`
    ——职责不重叠，避免两套规则漂移（本项目已在多处吃过"两份规则打架"的亏）。
    """
    if not isinstance(text, str) or not text.strip():
        return False, 'empty_text'
    limit = MAX_TEXT_CHARS if max_chars is None else int(max_chars)
    if len(text) > limit:
        return False, 'too_long:%d>%d' % (len(text), limit)
    foreign = detect_foreign_speaker_lines(text, speaker_id, name_index)
    if foreign:
        return False, 'foreign_speaker:%s' % ','.join(sorted({n for n, _ in foreign}))
    wrong = detect_wrong_self_claim(text, speaker_id, name_index)
    if wrong:
        return False, 'wrong_self_claim:%s' % ','.join(sorted({n for n, _ in wrong}))
    return True, ''


# ===========================================================================
#  系统提示尾巴（★ §4.2-C 的对策；★ 性能铁律：必须放在 system **最末尾**）
# ===========================================================================

def build_speaker_header(companion, others=(), extra_rules=()):
    """生成 system 提示的**末尾片段**，明确告知「你是谁 / 还有谁 / 不许替谁说话」。

    ★ 为什么必须放在 system **最末尾**：决定首字（TTF）的是 KV 前缀缓存是否命中，
    而缓存命中的前提是前缀不变。把"每轮都可能变"的部分（在场名单）压到最末尾，
    前面的人设/世界观就能稳定命中（第 31 轮实测：首字 4.601s，验收 ≤5s）。

    纯文本、无 markdown —— 与 `assets/ralsei_persona.md` 的口径一致。
    """
    me = _normalize_id(companion.speaker_id)
    alias_txt = ''
    if companion.aliases:
        alias_txt = '（也可以被叫做 %s）' % '、'.join(companion.aliases)
    lines = [
        '【你现在的身份】',
        '你是「%s」，身份编号 %s%s。' % (companion.display_name, companion.speaker_id, alias_txt),
    ]
    other_names = []
    for o in (others or ()):
        if _normalize_id(getattr(o, 'speaker_id', o)) == me:
            continue
        other_names.append(getattr(o, 'display_name', None) or str(o))
    if other_names:
        lines.append('在场还有：%s。' % '、'.join(other_names))
        lines.append('你只代表「%s」一个人说话。不要替他们说话，'
                     '不要写出「%s：……」这样的行，也不要自称成他们的名字。'
                     % (companion.display_name, other_names[0]))
    else:
        lines.append('现在没有别的伙伴在场，你只代表自己说话。')
    lines.extend(str(r) for r in (extra_rules or ()))
    return '\n'.join(lines)


# ===========================================================================
#  历史（★ §4.2 铁律 1：无效消息不进历史）
# ===========================================================================

class DialogueLog(object):
    """有界的对话历史 + **准入闸门**。

    ★ 三条不变量（都有正/负控制断言）：
      1. 只有 `validate()` 通过的消息才会进入历史；被拒的进 `rejected()`；
      2. `context_lines()` 产出的**每一行**都带名字前缀（铁律 2）；
      3. `last_from_id()` 是"下一条不许是同一个人"的判据来源（铁律 4）。
    """

    def __init__(self, known_ids=None, alias_map=None, maxlen=60,
                 cleaner=None, display=None):
        try:
            self._log = collections.deque(maxlen=int(maxlen))
        except Exception:
            self._log = collections.deque()          # 非法 maxlen ⇒ 不限长（不抛）
        self._rejected = []
        self._seq = 0
        self.known_ids = set(known_ids) if known_ids is not None else None
        self.alias_map = dict(alias_map or {})
        self.display = dict(display or {})
        #: 注入的措辞清洗回调（`None` = 不接）。签名 `(text, recent) -> str|None`。
        self.cleaner = cleaner

    # ---------------------------------------------------------------- 写入
    def append(self, msg, clean=False):
        """校验后入库。返回 `(ok, reason)`。

        `clean=True` 时先过注入的 `cleaner`（措辞类清洗）；清洗后为空 ⇒ 拒绝。
        """
        if clean and self.cleaner is not None:
            try:
                text = self.cleaner(msg.text, [m.text for m in self._log])
            except Exception:
                _log.exception('注入的 cleaner 抛异常 ⇒ 按"清洗失败"处理，拒绝本条')
                text = None
            if not text:
                return self._reject(msg, 'cleaner_dropped')
            msg.text = text
        ok, reason = msg.validate(self.known_ids, self.alias_map)
        if not ok:
            return self._reject(msg, reason)
        self._seq += 1
        msg.seq = self._seq
        self._log.append(msg)
        return True, ''

    def _reject(self, msg, reason):
        self._rejected.append((msg, reason))
        # ★ 铁律 1 的后半句：**如实记日志**（静默丢弃才是事故）。
        _log.warning('消息被拒（%s）：from=%r text=%r', reason, msg.from_id,
                     (msg.text or '')[:40])
        return False, reason

    # ---------------------------------------------------------------- 读取
    def recent(self, n=None):
        items = list(self._log)
        return items if n is None else items[-int(n):]

    def __len__(self):
        return len(self._log)

    def last_from_id(self):
        """最近一条**入库**消息的说话人（归一后）。空历史 ⇒ `None`。"""
        if not self._log:
            return None
        return self._log[-1].norm_from(self.alias_map)

    def context_lines(self, n=10):
        """给 prompt 用的最近 `n` 行（每行都带名字前缀）。"""
        return [format_line(m, self.display, self.known_ids, self.alias_map)
                for m in self.recent(n)]

    def context_text(self, n=10):
        return '\n'.join(self.context_lines(n))

    def rejected(self):
        """被拒的消息（诊断用）—— 返回 `[(Message, reason), ...]` 的副本。"""
        return list(self._rejected)

    def clear(self):
        self._log.clear()
        self._rejected.clear()
        self._seq = 0
