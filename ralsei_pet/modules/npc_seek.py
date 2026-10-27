# -*- coding: utf-8 -*-
u"""「他想去找谁」—— NPC 之间互相寻找的**偏好层**（第113轮p）。

用户口径（2026-10-27 逐字）
--------------------------
「npc 之间寻找偏好也要有哦」

动手前查到的两处**真缺陷**（都是"形状齐了、没接线"）
--------------------------------------------------
1. `npc_intent.decide()` 有 `visit_friend` 这个动作，`_pick_friend()` 也确实按熟络度
   挑出了**具体某个人**，但**目的地是随机的**：
       return i, _pick_reachable(reach, rng), 'visit_friend'
   ⇒ `Intent.who` 记了名字、`why` 写了 `visit_friend`，`dest_scene` 却是随便一个
   能去的地方。**"他说去看朋友，其实走到了别处"**，而且任何报告都读不出来
   （`who` 有值、`dest` 有值、没有异常）。
   根因：`_pick_friend` 拿到的 `friends` 是 `[(id, familiar)]`，**没有"那人住哪"**；
   `main._npc_roam_decide` 里 `[(i, f) for i, f, _s in ...]` 把第三元素**丢掉了**。
2. `decide()` 的 `favorites` 在宿主里一直是 `None`（`main._npc_roam_decide`），
   所以 `visit_favorite` 永远退化成 `wander` + `no_favorite_reachable`。

本模块管第 1 件事的**偏好**部分：**他想找谁**（不是"他能找谁"、也不是"他认识谁"）。
"那人住哪"由宿主给（`_npc_roam_friends` 的第三个元素），本模块一概不碰、不 import。

度量口径：**主动提起**（先说清楚它是什么、不是什么）
--------------------------------------------------
第一版我用"关系性 cue"（想见 / 一起 / 陪着…）去数，实测**203 个关系轮只命中 28 次**
（13%）—— 中文里表达牵挂极少用这些字面词（「要是哪天我不在了你怎么办」
「你也就这样了吧」的回答里一个都不出现）。口径太窄 = 抽不出东西。

改成**行为证据**：在**问句没有点到某人名字**的轮次里，
角色自己在回答里**主动提到**那个人几次。
  · `hy_ceroba_ketsukane` 主动提 `Chujin` 18 次、`Kanako` 11 次（家人）
  · `berdly` 提 `Noelle` 14 次、`Susie` 9 次
  · `flowery` 提 `Asgore` 25 次
覆盖率 **47/49 人**。

★ 它是什么：**行为频次** —— "没人问他的时候，他也会说起谁"。
★ 它不是什么：**不是**"他明确说过想见谁"。后者只有 28 个关系轮能给出，
  所以只当**加权修正**（明说"想见/一起/陪着"抬一点；明说"躲着/受不了/闹翻"降一点），
  不当主指标。这条界限必须写在登记表里（`method` 字段），否则下一个人会拿它当宣判。

数据从哪来（★ 不许编造）
------------------------
只用**角色自己说过的话**：训练记录（`_evidence/raw30/*.jsonl`）里每个轮次的
`user`（问句）与 `final`（他的回答）。名字匹配同时认 `name` 与 `name_cn`
（否则「苏西来了啊」匹配不到 `Susie`）。

★ 刻意**不做**的三件事：
  · 不把 `relations` 列表当偏好 —— 那是"他认识谁"，不是"他想找谁"；
    而且 `relations` 里混着非人条目（`时间`、`母亲`、`萤火虫`），
    解析不到 npc_id 的一律丢弃（由生成脚本按 registry 过滤，本模块不猜）；
  · 不请模型二次判读 —— 那是让我编，不是让角色说；
  · 不收「喜欢 / 在乎」这类宽词 —— 「我喜欢电子游戏」会被误记成"喜欢某人"。

零依赖：不 import Qt / 训练脚本 / data_store。只吃 dict、只吐 dict。
"""
import collections
import io
import json

#: 关系性**正** cue（高精度、低覆盖）：明说"想见/陪着"这类，抬权重用。
SEEK_UP = (
    '一起', '想见', '再见', '去找', '待在一块', '待在一起',
    '离不开', '依赖', '想念', '放不下', '陪着', '陪她', '陪他',
)

#: 关系性**负** cue：明说躲着/受不了/闹翻，降权重用。
SEEK_DOWN = (
    '不想见', '躲着', '躲开', '烦死', '受不了', '离远点', '闹翻', '讨厌',
)

#: 同句里出现这些词，也算"这句在说某个人"——
#: 允许「我和他一起」这种不点名的句子。
PERSON_WORDS = ('他', '她', '对方', '那家伙', '那个人')

#: 训练剧本里"问的是某个具体关系对象"的两段。
#: ★ 按 `slot` **前缀**筛，不按下标 —— 剧本加轮次时下标会整体偏移，
#:   而且偏移是静默的（第113轮为此栽过三次）。
REL_SLOT_PREFIXES = ('__REL', '__NPC')

#: 登记表文件名（放在 `assets/npc/` 下，与 `_registry.json` 同级）。
FILENAME = '_seek.json'

# ---- 权重档位（★ 简单、有界、可解释；不做"精确到小数点后两位"的假精度）----
MENTION_STEP = 0.06     # 每次主动提起 +6%
MENTION_CAP = 10        # 最多数 10 次 ⇒ 封顶 +60%
UP_STEP = 0.10          # 每句"明说想见"再 +10%
UP_CAP = 2              # 最多算 2 句
DOWN_STEP = 0.70        # 每句"明说躲着"×0.7
DOWN_CAP = 2
W_MIN = 0.45
W_MAX = 1.8


def sentences(text):
    """切开句子。只按**句末**标点与换行切，**不切逗号**。

    ★ 不切逗号是刻意的：「后来我才明白，我其实一直依赖 Susie」里，
      名字和 cue 分在逗号两侧 —— 切了就把两者拆散，这条就漏了。
    """
    out = []
    cur = []
    for ch in str(text or ''):
        if ch in u'。！？!?；;\n':
            s = u''.join(cur).strip()
            if s:
                out.append(s)
            cur = []
        else:
            cur.append(ch)
    s = u''.join(cur).strip()
    if s:
        out.append(s)
    return out


def names_of(name, aliases=None):
    """`name` + 它的别名（去重、去空）。`aliases` 可以是 `{name: [...]}` 或序列。"""
    out = [name] if name else []
    if isinstance(aliases, dict):
        extra = aliases.get(name) or ()
    else:
        extra = aliases or ()
    for a in extra:
        if a and a not in out:
            out.append(a)
    return out


def mentions(turns, relations, aliases=None):
    """**主动提起**：问句没点到名，回答里却提到了 ⇒ 计一次。→ `{名字: 次数}`。

    ★ 为什么要排除"问句已点名"的轮次：那种轮次里出现名字是**回声**，不是偏好
      （问「你觉得 Susie 怎么样」，答「Susie 嘛……」—— 这不能算他主动想起她）。
    """
    names = [str(x) for x in (relations or ()) if x]
    cnt = {}
    for t in (turns or ()):
        if not isinstance(t, dict):
            continue
        user = str(t.get('user') or u'')
        fin = str(t.get('final') or u'')
        if not fin:
            continue
        for n in names:
            al = names_of(n, aliases)
            if any(a in user for a in al):
                continue                      # 问句已点名 ⇒ 本条不计
            if any(a in fin for a in al):
                cnt[n] = cnt.get(n, 0) + 1
    return cnt


def score_text(text, name, aliases=(), question=u''):
    """在一段回答里判「明说想见 / 明说躲着」。→ `(pos, neg, quote)`。

    ★★ 守卫一：cue 必须与**名字或人称代词**同句。
      否则「我们一起走吧」这种没指向任何人的句子会被算到碰巧出现的那个人头上
      —— 这是本条最容易犯的误报，所以守卫写死在函数里，调用方绕不过去。

    ★★ 守卫二：**问句里出现过的 cue 不算回声**。
      实测踩过：剧本有一条是「如果有一天你和 X 彻底闹翻了，你会先低头吗？」，
      回答里几乎每句都带「闹翻」——那是**在复述题目**，不是在表达厌恶。
      第一版没这道闸，`berdly → kris` 被扣到 0.70，理由竟是
      「但如果 Kris 真的要和我彻底闹翻的话」这种假设句。
    """
    pos = neg = 0
    quote = u''
    al = names_of(name, aliases)
    q = str(question or u'')
    ups = [c for c in SEEK_UP if c not in q]
    downs = [c for c in SEEK_DOWN if c not in q]
    for s in sentences(text):
        if not any(a in s for a in al) and not any(w in s for w in PERSON_WORDS):
            continue
        if [c for c in ups if c in s]:
            pos += 1
            if not quote:
                quote = s[:60]
        if [c for c in downs if c in s]:
            neg += 1
            if not quote:
                quote = s[:60]
    return pos, neg, quote


def weigh(mention, pos=0, neg=0):
    """提及次数 + 明说正负 → 权重（乘在熟络度上）。→ `float`，钳在 `[W_MIN, W_MAX]`。"""
    try:
        m = max(0, int(mention))
        p = max(0, int(pos))
        d = max(0, int(neg))
    except (TypeError, ValueError):
        return 1.0
    w = 1.0 + MENTION_STEP * min(m, MENTION_CAP)
    w *= 1.0 + UP_STEP * min(p, UP_CAP)
    w *= DOWN_STEP ** min(d, DOWN_CAP)
    return round(max(W_MIN, min(W_MAX, w)), 3)


def extract(turns, relations, aliases=None, prefixes=REL_SLOT_PREFIXES):
    """一份训练记录的 `turns` → `{对方名字: {'mention','pos','neg','quote'}}`。

    ★ 正负 cue 只从**关系段/角色间段**取：那两段的问句点了名，回答里的
      "想见/躲着"才有明确指向。跨全篇取会把"我们一起去散步"算到无关的人头上。
    """
    cnt = mentions(turns, relations, aliases)
    out = {}
    for n, c in cnt.items():
        out[n] = {'mention': c, 'pos': 0, 'neg': 0, 'quotes': []}
    names = [str(x) for x in (relations or ()) if x]
    for t in (turns or ()):
        if not isinstance(t, dict):
            continue
        slot = str(t.get('slot') or u'')
        if not any(slot.startswith(p) for p in prefixes):
            continue
        user = str(t.get('user') or u'')
        hit = [n for n in names if any(a in user for a in names_of(n, aliases))]
        if len(hit) != 1:
            continue                      # 没点名 / 点了多个 ⇒ 不猜
        who = hit[0]
        pos, neg, quote = score_text(t.get('final') or u'', who,
                                     names_of(who, aliases), question=user)
        row = out.setdefault(who, {'mention': 0, 'pos': 0, 'neg': 0, 'quotes': []})
        row['pos'] += pos
        row['neg'] += neg
        if quote and quote not in row['quotes'] and len(row['quotes']) < 3:
            row['quotes'].append(quote)
    return out


def _first_sentence_with(text, name, aliases=None):
    for s in sentences(text):
        if any(a in s for a in names_of(name, aliases)):
            return s[:60]
    return u''


def rows_of(record, aliases=None, id_of=None):
    """一份 raw 记录 → `{名字或id: {'w','mention','pos','neg','why'}}`（供生成登记表）。

    `id_of` : 可选 `名字 -> npc_id`；给了就换键，返回 `None` 的键**保留原名**
    （由生成脚本决定丢弃还是留 —— 本函数不替它拿主意）。
    `why`   : 有"明说"的引文就用它；没有就取**第一次主动提起那人的那句**
              —— 让每条登记项都指得回原话，人能复核。
    """
    rec = record or {}
    turns = rec.get('turns') or ()
    raw = extract(turns, rec.get('relations') or (), aliases)
    out = {}
    for who, r in raw.items():
        if not (r['mention'] or r['pos'] or r['neg']):
            continue
        quote = (r['quotes'][0] if r['quotes']
                 else _first_sentence_with(_all_finals(turns), who, names_of(who, aliases)))
        key = who
        if id_of is not None:
            try:
                key = id_of(who) or who
            except Exception:
                key = who
        out[key] = {
            'w': weigh(r['mention'], r['pos'], r['neg']),
            'mention': r['mention'],
            'pos': r['pos'],
            'neg': r['neg'],
            'why': quote,
        }
    return out


def _all_finals(turns):
    return u'\n'.join(str(t.get('final') or u'') for t in (turns or ())
                      if isinstance(t, dict))


def empty_table():
    return {'version': 1, 'seek': {}}


def load(path):
    """读登记表。**读不到 / 坏掉 ⇒ 空表**（不抛）。"""
    try:
        with io.open(path, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return empty_table()
    if not isinstance(d, dict):
        return empty_table()
    s = d.get('seek')
    if not isinstance(s, dict):
        return empty_table()
    d['seek'] = s
    return d


def weights_of(table, npc_id):
    """`npc_id` 的 `{对方id: 权重}`。没登记 ⇒ `{}`。

    ★ 空字典与"权重全是 1.0"是**两件事**：前者等于"没有偏好数据"，
      调用方据此**完全不改**原有行为；后者会悄悄把随机序列改掉。
    """
    if not isinstance(table, dict):
        return {}
    s = table.get('seek')
    if not isinstance(s, dict):
        return {}
    row = s.get(npc_id)
    if not isinstance(row, dict):
        return {}
    out = {}
    for who, v in row.items():
        if isinstance(v, dict):
            try:
                w = float(v.get('w'))
            except (TypeError, ValueError):
                continue
        else:
            try:
                w = float(v)
            except (TypeError, ValueError):
                continue
        if w > 0 and who:
            out[str(who)] = max(W_MIN, min(W_MAX, w))
    return out


def bonus(seek, who):
    """`seek` 里 `who` 的权重倍数；没有 ⇒ **1.0**（中性，不改原有行为）。"""
    if not isinstance(seek, dict) or not who:
        return 1.0
    try:
        return float(seek.get(who) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def summarize(table):
    """→ `(登记人数, 登记条目数)`。给判据用（只报规模，不报"谁"）。"""
    s = (table or {}).get('seek') or {}
    if not isinstance(s, dict):
        return 0, 0
    n = 0
    for _k, v in s.items():
        if isinstance(v, dict):
            n += len(v)
    return len(s), n


WIRING = collections.OrderedDict((
    ('wired', True),
    ('used_by', ['main._npc_roam_decide（把 `_seek.json` 的权重传给 decide(seek=...)）',
                 'npc_intent._pick_friend（乘在熟络度上，并取朋友**真实所在场景**）']),
    ('wired_how', u'`main._npc_roam_decide` 每次决策调 `npc_seek.weights_of(table, npc_id)`'
                  u' ⇒ 交给 `npc_intent.decide(seek=...)`；`_pick_friend` 用 '
                  u'`familiar × npc_seek.bonus(seek, who)` 加权，并在 `friend_scenes` '
                  u'里查得到时把目的地设成**那人在的地方**（查不到才回落随机可达点）。'),
    ('not_yet', [u'「地方偏好」`favorites` 仍是 None（本轮只做"找谁"，不做"爱去哪"）',
                 u'登记表依赖训练素材：本轮先用已跑完的记录，训练收口后重跑生成脚本',
                 u'「主动提起」是**行为频次**代理，不是"他明确说过想见谁"']),
))
