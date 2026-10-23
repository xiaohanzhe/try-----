# -*- coding: utf-8 -*-
u"""第113轮回归锁：**全体角色 AI 训练不许静默失效**。

为什么本轮需要一条常驻锁
------------------------
本轮交付的不是"能跑的代码"，而是**证据 + 运行参数**：
96 张训练卡、77 份对话记录、若干条训练纠正（`patch`）、一份评测报告。
这类东西最容易出的问题不是崩溃，而是**静默**：

  · 卡片重建一次，`patches` 被冲掉 ⇒ 全体角色悄悄退回未训练状态（`cards113.py` 的注释）；
  · 人设改了但卡没重建 ⇒ 报告里的"角色规格"与真人设脱节；
  · 判据自己失效（正则打错、名单写窄）⇒ 报告显示"零违规"，其实是"什么都没测"；
  · 报告说训练了 77 人，raw 里只有 60 份 ⇒ 数字在说谎。

所以 A 段看**数据面自洽**、B 段**先体检判据**（正/负控制成对）、
C 段看**产品契约**（无 patch 时 prompt 逐字不变）、D 段看**产物完整性**。

零网络、零 Qt、不读临时盘。跑一遍是秒级。
"""
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.path.insert(0, HERE)
import common113 as C  # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


def _read(p):
    with open(p, 'rb') as fh:
        return fh.read().decode('utf-8')


# ---------------------------------------------------------------- A 数据面
mark('A 训练卡与人设同源')
index = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
cards = {}
cdir = os.path.join(C.TRAIN_DIR, 'cards')
if os.path.isdir(cdir):
    for fn in sorted(os.listdir(cdir)):
        if fn.endswith('.json'):
            c = C.load_json(os.path.join(cdir, fn), {})
            if c and c.get('id'):
                cards[c['id']] = c

check('A1 索引在位且登记了 96 个角色（全档覆盖）',
      index.get('counts', {}).get('total') == 96 and len(cards) == 96,
      'counts=%s cards=%d' % (index.get('counts'), len(cards)))

kinds = {}
for c in cards.values():
    kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
check('A2 三档分型：persona=77 / canned=18 / gap=1',
      kinds.get('persona') == 77 and kinds.get('canned') == 18 and kinds.get('gap') == 1,
      repr(kinds))

check('A2b 缺口集合恰为 {knight}（有人设的才进训练队列）',
      sorted(c['id'] for c in cards.values() if c.get('kind') == 'gap') == ['knight'],
      repr(sorted(c['id'] for c in cards.values() if c.get('kind') == 'gap')))

roster, gaps = C.load_roster()
check('A3 训练队列 = 77 人（registry 的 main 档里，除 knight 外全有人设文件）',
      len(roster) == 77 and len(gaps) == 1,
      'roster=%d gaps=%d(%s)' % (len(roster), len(gaps), ','.join(g['id'] for g in gaps)))

# ★ 关键：卡片必须与人设**逐字节同源**（sha256 比的是 LF 归一后的内容）
stale = []
for item in roster:
    card = cards.get(item['id']) or {}
    if card.get('persona_sha256') != item['persona_sha256']:
        stale.append(item['id'])
check('A4 77 张卡的人设 sha256 与磁盘一致（改了人设必须重建卡片）',
      not stale, '不同步：%s' % (','.join(stale[:8]) or '无'))

empty_fields = [i['id'] for i in roster
                if not (cards.get(i['id']) or {}).get('identity')
                or not (cards.get(i['id']) or {}).get('voice')]
check('A5 每张 persona 卡都解析出了 identity 与 voice（防"分节正则失效 ⇒ 空卡"）',
      not empty_fields, '空字段：%s' % (','.join(empty_fields[:8]) or '无'))

# ★ 判据自身的体检：口癖名单**不得**含 meta 词（AI/模型/提示词）。
#   本轮首版真栽过：尾部【本项目补充】被并进【示例反应】⇒ Susie 的口癖里多了「AI」，
#   于是"口癖命中率"反过来奖励自称 AI 的回复。这条判据就是拦它。
_META_BAD = ('AI', '模型', '提示词', '设定', '系统', '程序', '桌宠')


def _bad_markers(markers):
    return [m for m in (markers or []) if m in _META_BAD]


polluted = [i['id'] for i in roster if _bad_markers((cards.get(i['id']) or {}).get('voice_markers'))]
check('A6 口癖名单不含 meta 词（AI/模型/提示词…）—— 否则命中率会奖励出戏',
      not polluted, '污染：%s' % (','.join(polluted[:8]) or '无'))
check('A6b 负控制：人造 `["喂", "AI"]` 必须被 A6 的判据判出污染',
      _bad_markers(['喂', 'AI']) == ['AI'])

# ---------------------------------------------------------------- B 判据体检
mark('B 合规闸的正/负控制')
GOOD = [
    ('Susie', '喂！你搞什么啊！', '你好啊。'),
    ('Susie', '哼，随便你吧。', '今天过得怎么样？'),
    ('Ralsei', '我、我没事的，你别担心。', '你还好吗？'),
    ('Lancer', '哈哈哈！本大爷才不怕呢！', '你怕吗？'),
    ('Toriel', '孩子，先吃点东西吧。', '我饿了。'),
    ('Sans', '嗯……听起来挺麻烦的。', '你怎么看？'),
]
bad_good = [(n, C.gate_reply(t, u, (), n)[0]) for n, t, u in GOOD]
check('B1 6 条正常角色台词，硬违规必须为 0（否则闸门过严 ⇒ 天天误判）',
      all(not v for _, v in bad_good),
      repr([(n, [c for c, _ in v]) for n, v in bad_good if v]))

BAD = [
    ('#1', '**你好**，我是你的助手。', '你好啊。', 'MARKDOWN'),
    ('#2', '作为一个 AI，我不能回答这个问题。', '你是什么？', 'AI_SELF'),
    ('#3', '好的主人，小的这就去办。', '帮我个忙。', 'SLAVE'),
    ('#4', '（歪头）你在说什么呀？', '你好啊。', 'ACTION_PAREN'),
    ('#5', '这事跟 Deltarune 这个游戏有关吧。', '你怎么想？', 'META'),
    ('#6', '你' * 220, '你好啊。', 'TOO_LONG'),
    ('#7', '你好啊。', '你好啊。', 'PARROT'),
]
missed = []
for tag, text, user, want in BAD:
    codes = [c for c, _ in C.gate_reply(text, user, (), 'X')[0]]
    if want not in codes:
        missed.append((tag, want, codes))
check('B2 7 类坏样本逐个命中对应违规码（判据有鉴别力，不是恒绿）',
      not missed, repr(missed[:3]))

codes = [c for c, _ in C.gate_reply('', '你好', (), 'X')[0]]
check('B3 空回复 ⇒ EMPTY（空串不能被当成"通过"）', codes == ['EMPTY'], repr(codes))

# 复读：与**自己上一句**逐字相同
codes = [c for c, _ in C.gate_reply('哼。', '嗯', ('哼。',), 'X')[0]]
check('B4 复读自己上一句 ⇒ REPEAT；正控制：换一句则不报',
      'REPEAT' in codes and 'REPEAT' not in [c for c, _ in C.gate_reply(
          '哼，随你。', '嗯', ('哼。',), 'X')[0]],
      repr(codes))

# ---------------------------------------------------------------- C 产品契约
mark('C 产品契约：没训练过的角色 prompt 逐字不变')
import npc_persona as NP  # noqa: E402

persona = (roster[0]['persona'] if roster else '')
name = (roster[0]['name'] if roster else 'X')
a = NP.build_system_prompt(name, persona, [], 'probe', '', '')
b = NP.build_system_prompt(name, persona, [], 'probe', '', '', patch='')
c = NP.build_system_prompt(name, persona, [], 'probe', '', '', patch='')
check('C1 不传 patch 与传 patch="" 输出逐字相同（旧角色零行为变化）',
      a == b and a == c and len(a) > 100, 'len=%d/%d' % (len(a), len(b)))

patched = NP.build_system_prompt(name, persona, [], 'probe', '', '', patch='测试纠正句')
check('C2 有 patch 时真的进了 prompt',
      '测试纠正句' in patched and patched != a)
check('C2b 纠正块位置正确：在【现在跟你说话的人】之后、在【说话方式】之前',
      (patched.find('测试纠正句') > patched.find('现在跟你说话的人') > 0)
      and patched.find('测试纠正句') < patched.find('【说话方式】'),
      'idx patch=%d who=%d speak=%d' % (
          patched.find('测试纠正句'), patched.find('现在跟你说话的人'),
          patched.find('【说话方式】')))
check('C2c 负控制：空人设 + 有 patch 仍返回空串（不许凭空造 system）',
      NP.build_system_prompt(name, '', [], 'probe', '', '', patch='测试') == '')

check('C3 training_patch 对未知 id 返回空串', NP.training_patch('__no_such_npc__') == '')
check('C3b training_patch 读不到训练数据时返回空串（负控制：指向不存在的 assets 目录）',
      NP.training_patch('susie', assets_dir=os.path.join(ROOT, '__nope__')) == '')

_susie = NP.training_patch('susie')
check('C4 training_patch 能读到 susie 的纠正（若训练判红；未判红则应为空串）',
      isinstance(_susie, str), 'len=%d' % len(_susie or ''))

# 运行时真接了：main.py 把 training_patch 传进 build_system_prompt
MAIN = os.path.join(PKG, 'src', 'main.py')
msrc = _read(MAIN)
check('C5 main.py 的 npc_system_prompt 真把 training_patch 传下去了（不是只写在模块里）',
      'training_patch(' in msrc and 'patch=npc_persona_mod.training_patch' in msrc)

# ---- 关系卡：对他人态度（第113轮新增，prompt 唯一出口的第二处改动）----
check('C6 relation_patch(susie) 能读到关系卡，且内容真的讲到 Lancer',
      bool(NP.relation_patch('susie')) and 'Lancer' in NP.relation_patch('susie'))
check('C7 负控制：relation_patch 对未知 id 返回空串',
      NP.relation_patch('__no_such_npc__') == '')
_rel_a = NP.build_system_prompt('Susie', '我是 Susie。', npc_id='susie', relation='')
_rel_b = NP.build_system_prompt('Susie', '我是 Susie。', npc_id='susie')
check('C8 relation="" 与不传时逐字相同（没卡的角色零行为变化）', _rel_a == _rel_b)
_rel_c = NP.build_system_prompt('Susie', '我是 Susie。', npc_id='susie',
                                relation=NP.relation_patch('susie'))
check('C9 关系块位置：在【现在跟你说话的人】之后、【说话方式】之前',
      -1 < _rel_c.find(NP.WHO_IS_TALKING) < _rel_c.find('【你和其他人的关系')
      < _rel_c.find(NP.SPEAK_RULES))


def _main_has_relation_call(src_text):
    """AST 核对 main.py 是否真把 relation_patch 传进 build_system_prompt。

    ★ 不用字符串扫：注释或 docstring 里提一句 `relation_patch(` 就会误报成"已接线"。
    """
    import ast as _ast
    try:
        tree = _ast.parse(src_text)
    except SyntaxError:
        return False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute) \
                and node.func.attr == 'build_system_prompt':
            for kw in node.keywords:
                if kw.arg == 'relation' and isinstance(kw.value, _ast.Call) \
                        and isinstance(kw.value.func, _ast.Attribute) \
                        and kw.value.func.attr == 'relation_patch':
                    return True
    return False


check('C10 main.py 真接线 relation_patch（AST 核对，不是扫字符串）',
      _main_has_relation_call(msrc))

# ---------------------------------------------------------------- D 产物完整
mark('D 训练产物：raw / transcript / corpus / 报告 四者对得上')
raw_dir = C.RAW
raws = {}
if os.path.isdir(raw_dir):
    for fn in os.listdir(raw_dir):
        if fn.endswith('.jsonl'):
            raws[fn[:-6]] = C.read_jsonl(os.path.join(raw_dir, fn))
base_ids = sorted(k for k, v in raws.items() if any(r.get('phase') == 'baseline' for r in v))
check('D1 有第一遍对话记录的角色数 == 训练队列 77', len(base_ids) == len(roster),
      'raw=%d roster=%d 缺=%s' % (len(base_ids), len(roster),
                                  ','.join(sorted({r['id'] for r in roster} - set(base_ids))[:8]) or '无'))

bad_turns = []
for nid in base_ids:
    rec = next(r for r in raws[nid] if r.get('phase') == 'baseline')
    if len(rec.get('turns') or []) != 4:
        bad_turns.append((nid, 'turns=%d' % len(rec.get('turns') or [])))
        continue
    for t in rec['turns']:
        if not (t.get('attempts') or []):
            bad_turns.append((nid, 'turn%d 无 attempts' % t['i']))
        if not (t.get('final') or '').strip():
            bad_turns.append((nid, 'turn%d 空回复' % t['i']))
check('D2 每人恰 4 轮，每轮都有 attempts 与非空 final（失败也落盘，不许吞）',
      not bad_turns, repr(bad_turns[:4]))

missing_tr = [nid for nid in base_ids
              if not os.path.isfile(os.path.join(C.TRANSCRIPTS, nid + '.md'))
              or '## 第 1 轮' not in _read(os.path.join(C.TRANSCRIPTS, nid + '.md'))]
check('D3 每人一份可读对话记录（transcripts/<id>.md），且真含四轮正文',
      not missing_tr, '缺：%s' % (','.join(missing_tr[:6]) or '无'))

corpus_dir = os.path.join(C.TRAIN_DIR, 'corpus')
bad_corpus = []
corpus_rows = 0
if not os.path.isdir(corpus_dir):
    bad_corpus.append('目录不存在')
else:
    for nid in base_ids:
        p = os.path.join(corpus_dir, nid + '.jsonl')
        rows = C.read_jsonl(p)
        corpus_rows += len(rows)
        if not rows:
            bad_corpus.append(nid + ':空')
            continue
        for r in rows:
            msgs = r.get('messages') or []
            if len(msgs) != 3 or [m.get('role') for m in msgs] != ['system', 'user', 'assistant']:
                bad_corpus.append(nid + ':形状错')
                break
            if not (msgs[0].get('content') or '').strip():
                bad_corpus.append(nid + ':system 空')
                break
check('D4 语料每人一份、三段式 messages（system/user/assistant）且 system 非空',
      not bad_corpus, '%d 条 / 问题：%s' % (corpus_rows, ','.join(bad_corpus[:6]) or '无'))
check('D4b 语料条数 == 77 人 × 4 轮（不缺轮、不重复追加）',
      corpus_rows == len(roster) * 4, '%d vs %d' % (corpus_rows, len(roster) * 4))

rep = C.load_json(os.path.join(C.EVID, 'report113.json'), {}) or {}
summary = rep.get('summary') or {}
recount_turns = 0
recount_viol = 0
for nid in base_ids:
    rec = next(r for r in raws[nid] if r.get('phase') == 'baseline')
    recount_turns += len(rec.get('turns') or [])
    for t in rec.get('turns') or []:
        recount_viol += len(t.get('violations') or [])
check('D5 报告里的 轮数/违规数 == 从 raw 重算的结果（报告不许自己说一套）',
      summary.get('turns') == recount_turns and summary.get('hard_violations') == recount_viol,
      '报告=%s/%s 重算=%d/%d' % (summary.get('turns'), summary.get('hard_violations'),
                                 recount_turns, recount_viol))

# patches 只许给"实测判红或撞车"的人
per_char = summary.get('per_char') or {}
patches = index.get('patches') or {}
dup_involved = set()
for d in (rep.get('dup_pairs') or []):
    dup_involved.add(d.get('a'))
    dup_involved.add(d.get('b'))
no_reason = [nid for nid in patches
             if (per_char.get(nid, {}).get('violations', 0) == 0 and nid not in dup_involved)]
check('D6 每条 patch 都有依据（判红或跨角色撞车）；无证据却写纠正必须报红',
      not no_reason, '无依据：%s' % (','.join(no_reason[:8]) or '无'))
check('D6b patch 长度 ≤ 160 字（纠正句不许变成第二份人设）',
      all(len(p) <= 160 for p in patches.values()),
      '最长 %d' % (max([len(p) for p in patches.values()] or [0])))

# ---------------------------------------------------------------- E 区分度
mark('E 跨角色区分度（"不是同一个 AI 换皮"）')
first = {}
for nid in base_ids:
    rec = next(r for r in raws[nid] if r.get('phase') == 'baseline')
    t = next((x for x in rec['turns'] if x['i'] == 1), None)
    if t and t.get('final'):
        first[nid] = t['final']
uniq = len(set(first.values()))
check('E1 第一轮（同一句「你好啊。」）的不同回答数 ≥ 10（其余角色不是复读机）',
      uniq >= 10, '不同回答 %d / %d 人' % (uniq, len(first)))

dup_rate = 0.0
if summary.get('turns'):
    dup_rate = (summary.get('cross_dups') or 0) / max(1, len(base_ids) * 4)
check('E2 跨角色撞车对数已如实登记（撞车率 < 50%%；不达标就说明剧本区分度不够）',
      dup_rate < 0.5, '撞车 %s 对 / 撞车率 %.1f%%' % (summary.get('cross_dups'), dup_rate * 100))

# ---------------------------------------------------------------- G 关系卡数据面
mark('G 关系卡（对他人态度）：从关系总纲摘的原句，配对不许张冠李戴')
_att_path = os.path.join(C.NPC_DIR, '_relations', '_attitude.json')
_att = C.load_json(_att_path, {}) or {}
_att_npcs = _att.get('npcs') or {}
check('G1 关系卡覆盖 77 人（有人设的全部），且自检通过',
      len(_att_npcs) == len(roster) and (_att.get('selfcheck') or {}).get('ok') is True,
      '卡=%d roster=%d' % (len(_att_npcs), len(roster)))

# ★ 不信 selfcheck 的自证，独立重算一遍：卡句必须同时含【本角色】和【对方】。
_reg = C.load_json(os.path.join(C.NPC_DIR, '_registry.json'), {}) or {}
_reg_by_id = {x['id']: x for x in (_reg.get('npcs') or [])}
try:
    import relations113 as _R

    def _names(nid):
        return _R.names_of(_reg_by_id.get(nid, {'id': nid}))
except Exception:
    def _names(nid):
        return {n for n in (_reg_by_id.get(nid, {}).get('name'),) if n}

_bad_pair = []
for _nid, _v in _att_npcs.items():
    _me = _names(_nid)
    for _p in (_v.get('pairs') or []):
        _s = (_p.get('sentences') or [''])[0]
        _other = _names(_p.get('with'))
        if not any(x in _s for x in _me):
            _bad_pair.append((_nid, _p.get('with'), '缺本角色'))
        if not any(x in _s for x in _other):
            _bad_pair.append((_nid, _p.get('with'), '缺对方'))
check('G2 独立重算：每条卡句同时含本角色与对方（0 处张冠李戴）',
      not _bad_pair, '错配 %d 处 %s' % (len(_bad_pair), _bad_pair[:3]))

_bad_probe = []
for _nid, _v in _att_npcs.items():
    for _p in (_v.get('probe') or []):
        if _p not in _reg_by_id:
            _bad_probe.append((_nid, _p))
        elif _p == _nid:
            _bad_probe.append((_nid, '自己'))
check('G3 探针对象都是已登记角色、且不是自己', not _bad_probe,
      '异常 %d 个 %s' % (len(_bad_probe), _bad_probe[:3]))

_bad_quote = []
for _nid, _v in _att_npcs.items():
    _lines = [ln for ln in (_v.get('card') or '').split('\n') if ln.strip()]
    if len(_lines) > 3:
        _bad_quote.append((_nid, '行数%d' % len(_lines)))
    for _ln in _lines:
        if len(_ln) > 120:
            _bad_quote.append((_nid, '单行%d字' % len(_ln)))
            break
check('G4 每张卡 ≤3 组关系、单行 ≤120 字（不许变成第二份人设）', not _bad_quote,
      '超限 %d 张 %s' % (len(_bad_quote), _bad_quote[:3]))

_txt = [v.get('card') or '' for v in _att_npcs.values() if v.get('card')]
_dup_card = len(_txt) - len(set(_txt))
check('G5 不同角色的卡不雷同（同一张卡发给多个人 = 没做区分）',
      _dup_card == 0, '重复 %d 张' % _dup_card)

# ---- 态度评测产物（--eval 跑出来的回答）----
_apath = os.path.join(ROUND, '_evidence', 'attitude113.json')
_ad = C.load_json(_apath, {}) or {}
_ad_npcs = _ad.get('npcs') or {}
check('G6 态度评测覆盖 ≥30 人（探针 ≥2 的才参评），每人 ≥2 条回答',
      len(_ad_npcs) >= 30 and all(len(v.get('replies') or []) >= 2 for v in _ad_npcs.values()),
      '参评 %d 人' % len(_ad_npcs))
_pairs_all = [p for v in _ad_npcs.values() for p in (v.get('pairs') or [])]
_same = sum(1 for p in _pairs_all if p.get('same'))
_den = sum(1 for p in _pairs_all if p.get('same_denamed'))
check('G7 同一角色对不同人的态度真的有区分（同质对 0、去名同质 0）',
      bool(_pairs_all) and _same == 0 and _den == 0,
      '回答对 %d / 同质 %d / 去名同质 %d' % (len(_pairs_all), _same, _den))
_fmt = _ad.get('format') or {}
check('G8 态度回答的格式合规率 ≥80%%（括号/字卡按人设豁免后）',
      (_fmt.get('rate') or 0) <= 0.20,
      '%d/%d 不合规 %.1f%% %s' % (_fmt.get('bad', 0), _fmt.get('replies', 0),
                                  (_fmt.get('rate') or 0) * 100, _fmt.get('by_code')))

# ---------------------------------------------------------------- 收尾
print()
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for f in _failed:
        print('  - ' + f)
sys.exit(1 if _n_fail else 0)
