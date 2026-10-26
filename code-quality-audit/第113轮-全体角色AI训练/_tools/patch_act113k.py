# -*- coding: utf-8 -*-
"""第113轮k · 补丁 8：`npc_life` 加「活动 → 去处」的纯策略层。

用户口径（2026-10-26 逐字）
--------------------------
「我说的**特定事件**就是指，**吃饭，活动，休息，做任务**等，他能识别出来要去哪，
  并**给出建议**这样的，就像是人类之间问，咱吃饭去吧，别人会回答，
  **那要不去 XXX 家餐厅**？这样的话一样」

⇒ 两件事，必须分开：
  ① **听懂**别人在张罗什么（`detect_activity`）—— 只认意图词；
  ② **知道哪儿真能干这事**（`place_matches` 筛、`activity_hint` 产块）—— 只认地点词。

★ 为什么两张表必须分开：混成一张就会出现**因果倒置**
  （"因为人在餐厅，所以他在吃饭"）。而人说话是"我想吃饭，所以去餐厅"。

★ 为什么 `activity_hint` 要强调「用你自己的说法，别照着念」：
  本项目失真头号来源就是**可逐字搬走的固定例句**（113i 的 A12d）。
  台词一旦写死成模板，7B 会原样复述 —— 那就不是"他给建议"，是"他念模板"。

守门：全 CRLF / 锚唯一 / 回读比对 / CRLF 增量。幂等：见到 `ACTIVITY_KINDS` 即跳过。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LIFE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_life.py')


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)
    assert rd(p) == t, '写回与内存不一致：%s' % p


def eol_guard(t, tag):
    gap = len(t.splitlines()) - t.count('\r\n')
    assert gap in (0, 1), '%s 不是全 CRLF：gap=%d' % (tag, gap)


def swap(t, old, new, tag, must=None):
    assert t.count(old) == 1, '%s 锚命中 %d 次（需 1）' % (tag, t.count(old))
    c0 = t.count('\r\n')
    t2 = t.replace(old, new, 1)
    assert t2 != t, '%s 替换无变化' % tag
    if must:
        assert must in t2, '%s 没写进 %r' % (tag, must)
    need = new.count('\r\n') - old.count('\r\n')
    got = t2.count('\r\n') - c0
    assert got == need, '%s CRLF 增量 %d（应 %d）' % (tag, got, need)
    eol_guard(t2, tag + '(post)')
    return t2


# ---------------------------------------------------------------- 1) import re
IMP_OLD = "import collections\r\n"
IMP_NEW = "import collections\r\nimport re\r\n"

# ---------------------------------------------------------------- 2) 活动段
ANCHOR = "# ---------------------------------------------------------------- 在场者感知（第86轮）\r\n"

BLOCK = '''# ---------------------------------------------------------------- 活动与去处（第113轮k）

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
    'play': '出去转转',
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


def detect_activity(text):
    """一句话里认「他要去干什么」⇒ `(kind, 命中的词)`；认不出 `(None, '')`。

    ★ 多个活动同时命中时取**句子里最先出现**的那个：
      "吃完饭去逛逛" 的第一件事是吃饭。按表顺序取会得到与语序无关的答案，那是错的。
    ★ 空串 / None ⇒ `(None, '')`，不猜。
    """
    s = str(text or '').strip().lower()
    if not s:
        return (None, '')
    best_kind, best_word, best_at = None, '', len(s) + 1
    for kind in ACTIVITY_KINDS:
        for w in INTENT_WORDS.get(kind, ()):
            i = s.find(w.lower())
            if 0 <= i < best_at:
                best_kind, best_word, best_at = kind, w, i
    return (best_kind, best_word)


def place_matches(text, kind):
    """这段文本像不像「能干 kind 这件事的地方」⇒ 命中的词列表（空 = 不像）。

    ★★ 调用方传进来的文本**必须已经剥掉区段名**。`ch5` 整个区叫 `garden`，
      房间 id 全是 `dw_garden_*` —— 不剥的话 106 间房会全部命中 `play`，
      「这个区叫希望之园」就被读成「每间房都是公园」。第113轮k 实测踩过。

    ★ 英文一律 `\\b` 词边界：`sparks` 不含词 `park`，`graveyard` 不含词 `yard`。
    """
    s = str(text or '').lower()
    if not s or kind not in PLACE_WORDS:
        return []
    table = PLACE_WORDS[kind]
    out = []
    for w in table.get('zh', ()):
        if w in s:
            out.append(w)
    for w in table.get('en', ()):
        if re.search(r'\\b%s\\b' % re.escape(w), s):
            out.append(w)
    return out


def activity_hint(kind, places, note='', limit=4):
    """【这会儿能张罗的事】—— 有人提到要去干什么，他手边**真有哪些地方**可提。

    参数
    ----
    kind   : `ACTIVITY_KINDS` 之一；不认识 ⇒ `''`（不产块）
    places : `[(scene_id, 可读名), ...]`。★ **调用方按"能去"筛好**再传 ——
             能不能去是门控的事（`world_gate` / 章归属），策略层不碰。
    note   : 可选的一句上下文（比如"他刚才问要不要一起"）。
    limit  : 最多列几个。太多模型会挑花眼，反而说不出一个具体的。

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
    lines = [
        head + '要去%s，你们这儿真有的地方：%s。' % (ACTIVITY_SAY[kind], '、'.join(names)),
        '（想接这个话就提一个，用你自己平常的说法 —— 别照着念，也别硬拉人家去。）',
    ]
    return '\\n'.join(lines)


'''

def main():
    t = rd(LIFE)
    eol_guard(t, 'npc_life.py(pre)')

    if 'ACTIVITY_KINDS' in t:
        print('npc_life.py 已有活动段，跳过')
        return 0

    # 1) import re
    t2 = swap(t, IMP_OLD, IMP_NEW, 'import re', must='import re')
    # 2) 插活动段（CONNECT 分隔线之前）
    block = BLOCK.replace('\n', '\r\n')
    assert ANCHOR in t2, '找不到「在场者感知」分节锚'
    t3 = swap(t2, ANCHOR, block + ANCHOR, '活动段', must='def activity_hint')
    # 3) 顶层 docstring 的"本模块只回答四件事"要跟着改（不然文档说谎）
    wr(LIFE, t3)
    print('npc_life.py OK 行数=%d' % len(t3.splitlines()))
    print('EXIT=0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
