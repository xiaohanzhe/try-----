# -*- coding: utf-8 -*-
u"""第189轮 · 测量脚本：**先量再改**（第161/187轮的教训：不量就改＝靠印象）。

三件事一起量，全部只读，产物 `_evidence/measure189.json`。

## A. 发声类括号的真实形态

用户口径：「笑声也就是角色发出来的声音直接显示就好」。
要落地就得知道语料里到底长什么样，而不是我拍脑袋想 `笑声：X` 这一种。
做法：把 419 条 `ACTION_PAREN` 里**通过产品护栏后仍在的**括号全捞出来，
按「像不像发声」粗分（标签前缀 / 拟声词 / 其它），列出全部去重形态与次数。

## B. 口癖频率：谁在"每轮必念"

用户口径：「像是 asgore 的这个 Howdy 不用每次都有，就偶尔」。
`voice_markers` 是**评测口径**（回复里出现任一 marker 就算命中），训练时每轮记 `marker_hits`。
⇒ 一个人 48 轮里有多少轮命中，就能量出"是不是每轮都念"。
输出按命中率降序，并区分「命中率 ≥90%（疑似每轮必念）」/「40~90%」/「<40%」。

## C. 书面语形态

用户口径：「你觉得正常人说中文会那么书面语吗，口语化些，所有角色都是」。
"书面语"必须先变成**可判定的形态**，否则改哪里都是猜。本脚本量：

  · 平均句长、长句（≥40 字）占比
  · 书面连接词命中率（然而/因此/此外/总之/事实上/不仅/而且/尽管/即便/倘若…）
  · 四字格密度（用"连续 4 个 CJK 且命中成语式构件"太玄，改用**固定成语/书面短语表**）
  · 句末语气：`。` 收尾 vs `！`/`？` 收尾
  · 第二人称敬语「您」
  · 口语特征词命中率（啊/呢/吧/嘛/呀/哦/啦 + 语气词结尾）

★ 全部只统计 `final`（模型直出），不统计 prompt。

用法（幂等，直接覆盖）：
    C:/Python311/python.exe measure189.py
"""
import io
import json
import os
import re
import sys
from collections import Counter, OrderedDict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
RAW30 = os.path.join(REPO, 'code-quality-audit', u'第113轮-全体角色AI训练',
                     '_evidence', 'raw30')
OUT = os.path.join(ROUND, '_evidence', 'measure189.json')

sys.path.insert(0, MODS)
import event_speech as E                       # noqa: E402

PAREN = re.compile(u'[（(][^（（））]{1,200}[)）]')
CJK = re.compile(u'[\u4e00-\u9fff]')

# ---- 发声类：标签前缀（形如 `笑声：…` / `笑：…`） ----
_VOICE_LABEL = re.compile(
    u'^(?:笑\\s*声|笑|声音|音效|配音|语气声|笑声效果)\\s*[:：]\\s*(.+)$', re.S)
_VOICE_LABEL2 = re.compile(
    u'^(?:笑\\s*声|声音|音效)\\s*[（(]\\s*(.+?)\\s*[)）]$', re.S)
# ---- 拟声/发声：整段就是拟声词 ----
_ONO = re.compile(
    u'^(?:[哈嘿嘻呵哇呜啊嗯哼哦呀唉]{2,}|'
    u'[哈嘿嘻呵]{1,}(?:[哈嘿嘻呵]{1,})?[哈嘿嘻呵]{1,})$')
# ---- 英文笑声（`NYEH HEH HEH!` 这种）：全部词都在笑声表里才算 ----
_EN_TOK = re.compile(u"[A-Za-z']+")
LAUGH_EN = set(['ha', u'haa', u'haha', u'hahaha', u'hahahaha', u'heh', u'hehe',
                u'heheh', u'hehehe', u'heheheh', u'nyeh', u'nyehh', u'mweh',
                u'mwehehe', u'mweheheh', u'geh', u'geheh', u'huh', u'ho',
                u'hoho', u'hohoho', u'hah', u'hee', u'heehee', u'teehee',
                u'nyah', u'nya', u'lah', u'haa', u'lol', u'mwah', u'psst'])

# ---- 书面连接词（选的是"口语里基本不说"的那批） ----
BOOKISH = [u'然而', u'因此', u'此外', u'总之', u'事实上', u'不仅', u'而且',
           u'尽管', u'即便', u'倘若', u'除此之外', u'与之相比', u'总而言之',
           u'由此可见', u'与此同时', u'换言之', u'基于', u'鉴于', u'进而',
           u'从而', u'无非', u'尚未', u'颇为', u'亦', u'乃', u'其所']
# ---- 口语特征 ----
SPOKEN = [u'啊', u'呢', u'吧', u'嘛', u'呀', u'哦', u'啦', u'哎', u'诶',
          u'哈', u'唔', u'唉', u'嘿', u'咋', u'咱']


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def latest(path, target=48):
    best = None
    for line in io.open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and r.get('turns_n') == target:
            best = r
    return best


def split_sent(t):
    u"""按中英文句末标点切句，保留 `…`（人设明写"别拿省略号当句号"）。"""
    parts = re.split(u'[。！？!?]+', t)
    return [p.strip() for p in parts if p.strip()]


def main():
    if not os.path.isdir(RAW30):
        print(u'语料目录不在：%s' % RAW30)
        return 2

    recs = []
    for f in sorted(os.listdir(RAW30)):
        if not f.endswith('.jsonl'):
            continue
        r = latest(os.path.join(RAW30, f))
        if r:
            recs.append(r)

    # ---------------- A. 发声形态 ----------------
    voice = Counter()          # 去重形态 → 次数
    voice_kind = Counter()     # 分类计数
    others = Counter()
    en_inners = Counter()      # 含 ASCII 字母的括号内容（看 D 族到底长什么样）
    n_paren_turn = 0
    for r in recs:
        for t in (r.get('turns') or []):
            if not any(v[0] == 'ACTION_PAREN' for v in (t.get('violations') or [])):
                continue
            n_paren_turn += 1
            out = E.strip_action_parentheticals(t.get('final') or u'')
            for h in PAREN.findall(out):
                inner = h[1:-1].strip()
                toks = _EN_TOK.findall(inner)
                if _VOICE_LABEL.match(inner) or _VOICE_LABEL2.match(inner):
                    voice[h] += 1
                    voice_kind[u'标签冒号式'] += 1
                elif _ONO.match(inner):
                    voice[h] += 1
                    voice_kind[u'拟声词'] += 1
                elif toks and all(x.lower() in LAUGH_EN for x in toks):
                    voice[h] += 1
                    voice_kind[u'英文笑声'] += 1
                else:
                    others[h] += 1
                    if toks:
                        en_inners[h] += 1

    # ---------------- B. 口癖命中率 ----------------
    # ★ 第一版只按"有没有任一 marker"算 ⇒ 哦/嗯/啊 这种通用语气词让 16 人全是 100%，
    #   完全看不出"口癖病"。必须**逐 marker** 统计，并标出哪些 marker 是"通用语气词"。
    GENERIC = set([u'哦', u'嗯', u'啊', u'呃', u'唉', u'诶', u'呀', u'唔', u'哈',
                   u'嘛', u'呢', u'吧', u'嗯……', u'啊……', u'哦……'])
    per_char = []
    marker_rows = []
    for r in recs:
        turns = r.get('turns') or []
        if not turns:
            continue
        n = len(turns)
        hit = sum(1 for t in turns if (t.get('marker_hits') or []))
        per_char.append({
            'id': r.get('id'),
            'name_cn': r.get('name_cn'),
            'turns': n,
            'hit_turns': hit,
            'rate': round(100.0 * hit / n, 1),
            'markers': (r.get('voice_markers') or [])[:6],
        })
        for mk in (r.get('voice_markers') or []):
            if not mk or len(mk) < 2:
                continue
            k = sum(1 for t in turns if mk in (t.get('final') or u''))
            # ★ 纯标点（`……`）不是口癖 —— 它出现频率天然高，算进来只会淹没真信号。
            is_generic = (mk in GENERIC) or (not re.search(
                u'[0-9A-Za-z\u4e00-\u9fff]', mk))
            marker_rows.append({
                'id': r.get('id'), 'marker': mk, 'turns': n, 'hits': k,
                'rate': round(100.0 * k / n, 1),
                'generic': is_generic,
            })
    per_char.sort(key=lambda x: -x['rate'])
    # ★ 只看**非通用**且 ≥80% 的：这才是"每轮必念口癖"
    marker_rows.sort(key=lambda x: (-x['rate'], x['id']))
    chronic = [m for m in marker_rows if (not m['generic']) and m['rate'] >= 80.0]

    # ---------------- C. 书面语 ----------------
    n_turn = 0
    n_sent = 0
    n_long = 0
    n_book = 0
    n_spoken = 0
    n_nin = 0
    n_end_excl = 0
    n_end_period = 0
    n_cjk = 0
    book_hit = Counter()
    char_book = OrderedDict()      # id → [书面轮, 总轮]
    for r in recs:
        cid = r.get('id')
        for t in (r.get('turns') or []):
            txt = t.get('final') or u''
            if not txt.strip():
                continue
            n_turn += 1
            sents = split_sent(txt)
            n_sent += len(sents)
            n_long += sum(1 for s in sents if len(CJK.findall(s)) >= 40)
            n_cjk += len(CJK.findall(txt))
            hit = [w for w in BOOKISH if w in txt]
            stat = char_book.setdefault(cid, [0, 0])
            stat[1] += 1
            if hit:
                n_book += 1
                stat[0] += 1
                for w in hit:
                    book_hit[w] += 1
            if any(w in txt for w in SPOKEN):
                n_spoken += 1
            if u'您' in txt:
                n_nin += 1
            tail = txt.rstrip()
            if tail.endswith((u'。', u'.')):
                n_end_period += 1
            elif tail.endswith((u'！', u'!', u'？', u'?')):
                n_end_excl += 1

    char_rank = sorted(
        [{'id': k, 'bookish_turns': v[0], 'turns': v[1],
          'rate': round(100.0 * v[0] / max(1, v[1]), 1)} for k, v in char_book.items()],
        key=lambda x: -x['rate'])

    d = OrderedDict()
    d['schema'] = 1
    d['corpus'] = {'chars': len(recs), 'paren_turns': n_paren_turn, 'turns': n_turn}
    d['voice'] = {
        'tags_colon': voice_kind.get(u'标签冒号式', 0),
        'onomatopoeia': voice_kind.get(u'拟声词', 0),
        'laugh_en': voice_kind.get(u'英文笑声', 0),
        'distinct': len(voice),
        'total': sum(voice.values()),
        'top': [[k, v] for k, v in voice.most_common(40)],
        'other_top': [[k, v] for k, v in others.most_common(25)],
        'en_other_top': [[k, v] for k, v in en_inners.most_common(20)],
    }
    d['markers'] = {
        'per_char': per_char,
        'chronic': chronic,
        'rows': [m for m in marker_rows if m['hits'] > 0][:80],
        'ge90': [x['id'] for x in per_char if x['rate'] >= 90],
        'mid': [x['id'] for x in per_char if 40 <= x['rate'] < 90],
        'lt40': [x['id'] for x in per_char if x['rate'] < 40],
    }
    d['bookish'] = {
        'turns': n_turn,
        'sents': n_sent,
        'avg_sent_cjk': round(float(n_cjk) / max(1, n_sent), 2),
        'long_sent_ratio': round(100.0 * n_long / max(1, n_sent), 2),
        'bookish_turn_ratio': round(100.0 * n_book / max(1, n_turn), 2),
        'spoken_turn_ratio': round(100.0 * n_spoken / max(1, n_turn), 2),
        'nin_ratio': round(100.0 * n_nin / max(1, n_turn), 2),
        'end_period_ratio': round(100.0 * n_end_period / max(1, n_turn), 2),
        'end_excl_ratio': round(100.0 * n_end_excl / max(1, n_turn), 2),
        'word_hits': [[k, v] for k, v in book_hit.most_common()],
        'per_char': char_rank,
    }

    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))

    # ================= 打印摘要 =================
    print(u'语料：%d 人 / %d 轮（其中带 ACTION_PAREN 的 %d 轮）'
          % (len(recs), n_turn, n_paren_turn))
    print()
    print(u'=== A 发声类（护栏跑完后仍在的括号）===')
    print(u'  标签冒号式 %d · 拟声词 %d · 英文笑声 %d · 合计 %d 处 / %d 种'
          % (voice_kind.get(u'标签冒号式', 0), voice_kind.get(u'拟声词', 0),
             voice_kind.get(u'英文笑声', 0), sum(voice.values()), len(voice)))
    for k, v in voice.most_common(15):
        print(u'    %-34s %d' % (k, v))
    print(u'  —— 其余（非发声）top10，用来看边界 ——')
    for k, v in others.most_common(10):
        print(u'    %-34s %d' % (k, v))
    print(u'  —— 其余里含英文的（D 族到底长什么样）——')
    for k, v in en_inners.most_common(10):
        print(u'    %-40s %d' % (k, v))
    print()
    print(u'=== B 口癖：**逐 marker**（排除通用语气词，≥80% 才算每轮必念）===')
    if chronic:
        for m in chronic[:15]:
            print(u'    %-20s %-10s %2d/%d = %5.1f%%'
                  % (m['id'], m['marker'], m['hits'], m['turns'], m['rate']))
    else:
        print(u'    （无）')
    print(u'  全部有命中的 marker（前 12，含通用词，用来看"100% 是怎么来的"）：')
    for m in d['markers']['rows'][:12]:
        print(u'    %-20s %-10s %2d/%d = %5.1f%% %s'
              % (m['id'], m['marker'], m['hits'], m['turns'], m['rate'],
                 u'[通用]' if m['generic'] else u''))
    print(u'  按角色命中率分档：≥90%% %d 人 · 40~90%% %d 人 · <40%% %d 人'
          % (len(d['markers']['ge90']), len(d['markers']['mid']),
             len(d['markers']['lt40'])))
    print()
    print(u'=== C 书面语 ===')
    b = d['bookish']
    print(u'  平均句长 %.2f 字 · 长句(≥40字)占比 %.2f%%'
          % (b['avg_sent_cjk'], b['long_sent_ratio']))
    print(u'  含书面连接词的轮 %.2f%% · 含口语词 %.2f%% · 用「您」%.2f%%'
          % (b['bookish_turn_ratio'], b['spoken_turn_ratio'], b['nin_ratio']))
    print(u'  句末：。%.2f%% · ！/？ %.2f%%'
          % (b['end_period_ratio'], b['end_excl_ratio']))
    print(u'  书面词 top10：')
    for k, v in book_hit.most_common(10):
        print(u'    %-8s %d' % (k, v))
    print(u'  最"书面"的角色 top10（含书面连接词的轮占比）：')
    for x in char_rank[:10]:
        print(u'    %-22s %2d/%d = %5.1f%%'
              % (x['id'], x['bookish_turns'], x['turns'], x['rate']))
    print()
    print(u'→ %s' % OUT)

    # ★ 分母闸：任何一项条数不能超过语料规模（防"数错分母还很自信"）
    assert n_paren_turn <= n_turn <= 4000, (n_paren_turn, n_turn)
    assert b['bookish_turn_ratio'] <= 100.0 and b['spoken_turn_ratio'] <= 100.0
    return 0


if __name__ == '__main__':
    sys.exit(main())
