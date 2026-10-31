# -*- coding: utf-8 -*-
"""第129轮 · 探针：**复读（车轱辘话）与出戏**在 7B 上的真实水平。

只做一件事：拿 300 条**已经存在的真实模型输出**（第128轮 `_evidence/raw/` 五臂），
去问产品里的两处判据还成不成立：

  判据 A  `_is_repeat_of_recent`（main.py，difflib 0.82 / 最长公共块 12 字）
  判据 B  `looks_out_of_character` + `looks_like_assistant_speak`（event_speech.py）

为什么要重测：这两个阈值是**3B 时代**定的（第十八轮）。现在底座是 `ralsei:v4`（7B），
"什么算重复""什么算客服腔"的分布都变了 —— **判据本身也是被测物**。

设计约束（都来自本项目踩过的坑）
------------------------------
1. **只调产品函数，不复制判据**：判据一旦有两份实现，改一处另一处会漂移。
   `_is_repeat_of_recent` 在 `main.py`（会卷进 Qt），因此用 **AST 抽出函数体真跑**
   （先例：第113轮n 抽 `_npc_place_near`）。
2. **正/负控制成对**：命中类判据必须有"该命中的"和"不该命中的"。
   ★ 负控制不能靠"不含任何表内子串"来构造 —— 那是恒真。要用**近似串**
   （`我相信他` vs 表内的 `我相信你`）才真的落到边界上。
3. **分母闸**：每段先断言样本非空，空集判红而不是静默通过。
4. 零 Qt、零网络、零外部盘（只读仓库内 `raw/`）。

输出：`_evidence/probe129.json`（明细）+ 控制台表（结论）
"""
import ast
import io
import json
import os
import re
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
RAW128 = os.path.join(ROOT, 'code-quality-audit', '第128轮-结巴率收敛', '_evidence', 'raw')
EV = os.path.join(ROUND, '_evidence')

sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES          # noqa: E402  （零依赖：只 import random/re）


# ---------------------------------------------------------------- 判据 A 抽取
class _DummyLog(object):
    def debug(self, *a, **k):
        pass

    warn = info = error = debug


def load_repeat_func(main_py):
    """从 main.py **AST 抽出** `_is_repeat_of_recent` 并编译成可调用的纯函数。

    ★ 为什么不 import main：它会拉起 Qt 与 data_store 那条初始化环（第十二轮教训）。
    ★ 为什么不用正则抠函数文本：`ast.walk + break` 抓"第一个匹配"是陷阱（§96b.1），
      这里按 **ClassDef(RalseiPet) 下的同名 FunctionDef** 精确定位，找不到就抛。
    """
    src = io.open(main_py, encoding='utf-8', newline='').read()
    tree = ast.parse(src)
    cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'RalseiPet':
            cls = node
            break
    if cls is None:
        raise RuntimeError('main.py 里没找到 class RalseiPet')
    fn = None
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_is_repeat_of_recent':
            fn = node
            break
    if fn is None:
        raise RuntimeError('RalseiPet 里没找到 _is_repeat_of_recent')
    seg = ast.get_source_segment(src, fn)
    if not seg:
        raise RuntimeError('取不到 _is_repeat_of_recent 的源码段')
    # ★ 顺手把类级整数常量也取出来（`REPEAT_MIN_CHARS`）——探针**不许另写一个数**，
    #   否则产品改了阈值、探针还按老数算，W2 就会变成"两份各自错、恰好都不报红"。
    consts = {}
    for node in cls.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, int):
            consts[node.targets[0].id] = node.value.value
    ns = {'_log': _DummyLog()}
    exec(compile(textwrap.dedent(seg), '<extracted _is_repeat_of_recent>', 'exec'), ns)
    return ns['_is_repeat_of_recent'], seg, consts


# ---------------------------------------------------------------- 素材
def read_jsonl(name):
    p = os.path.join(RAW128, name)
    rows = []
    for line in io.open(p, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        rows.append({'user': o.get('user') or '', 'reply': (o.get('reply') or '').strip()})
    return rows


ARMS = ('base', 'pnew_bold', 'pnew_bnew', 'pnew_bnew2', 'pnew_relax')


# ---------------------------------------------------------------- M4/M5 夹具
#: 误伤夹具：语义不同、但**字面高度相近**（这正是 0.82 ratio 的死角）。
#: 判据必须**全部不命中**。三组分别压不同维度：换宾语 / 换主语 / 换程度词。
FALSE_POS_PAIRS = [
    (u'我很喜欢你', u'我很喜欢这里'),
    (u'今天的天气真好啊', u'今天的心情真好啊'),
    (u'你会没事的，我保证', u'你会好的，我保证'),
    (u'别怕，我在这儿', u'别怕，我一直在这儿'),
    (u'这朵花是给你的', u'这朵花是给她的'),
    (u'我想和你一起走', u'我想和你一起看'),
    (u'他们都说你很强', u'他们都说你很好'),
    (u'外面在下雨呢', u'外面在下雪呢'),
    (u'我不知道该说什么', u'我不知道该做什么'),
    (u'你笑起来真好看', u'你看起来真好看'),
    (u'明天见吧', u'明天见啦'),
    (u'我在想一件事', u'我在做一件事'),
]

#: 漏判夹具：长句只改两三个字（这是产品**必须**拦住的"换汤不换药"）。
#: 判据必须**全部命中**。
FALSE_NEG_PAIRS = [
    (u'其实我一直都很想跟你说这件事，只是每次话到嘴边又咽回去了，我怕说出来你会觉得我很奇怪。',
     u'其实我一直都很想跟你说这件事，只是每次话到嘴边又吞回去了，我怕说出来你会觉得我很古怪。'),
    (u'你看那边的天空，颜色一点点暗下来，像是有人把灯慢慢调小了，我很喜欢这个时候。',
     u'你看那边的天空，颜色慢慢暗下来，像是有人把灯悄悄调小了，我很喜欢这个时刻。'),
    (u'别担心，就算整个世界都变得乱七八糟，我还是会站在这里等你回来的，说好了。',
     u'别担心，就算整个世界都变得一团糟，我还是会站在这里等你回来，说好了。'),
    (u'我知道你最近很累，可是你已经做得很好了，真的，比你自己以为的要好得多。',
     u'我知道你最近很辛苦，可是你已经做得很好，真的，比你自己想的要好得多。'),
    (u'如果有一天你想去很远的地方，记得告诉我一声，我不会拦你，我只是想送你到门口。',
     u'如果有一天你想去很远的地方，记得跟我说一声，我不会拦着你，我只是想送你到门口。'),
    (u'那时候我们都还小，什么都不懂，却觉得世界大得装不下，现在想想真是可爱。',
     u'那时候我们都还很小，什么都不懂，却觉得世界大得装不下，现在想想真是可爱。'),
]

#: 出戏正控制：必须命中（且要覆盖两条判据各自的分支）。
OOC_POS = [
    (u'作为AI，我不能回答这个问题。', 'ooc'),
    (u'我只是一个程序，没有真正的感情。', 'ooc'),
    (u'我的设定里没有这一条。', 'ooc'),
    (u'有什么我可以帮你的吗？', 'ban'),
    (u'我理解你的感受，一切都会好起来的。', 'ban'),
    # ★ 129：这条原来写的是「首先，我们需要冷静下来分析。」——但 `首先` 已收窄为
    #   **共现**判据（必须有 其次/总之/… 才算分点），单靠"首先"不再命中。
    #   正控制必须换成**真正的分点句**，否则它测的是旧语义。
    (u'首先，我们需要冷静下来分析；其次，列出可能的原因。', 'ban'),
]
#: ★ 129 收窄的**代价**，如实登记：只有"首先"、没有后续分点词的助手腔会漏过。
#:   这不是 bug 没修，是**有意取舍** —— 换掉的是一整类正常口语的误杀
#:   （「首先我得谢谢你，愿意留下来听我说。」）。两边都只有构造样本，
#:   真实 300 条回复里"首先"出现 **0** 次（见逐 pattern 明细）。
OOC_KNOWN_MISS = [
    (u'首先，我们需要冷静下来分析。', 'ban'),
]
#: 出戏负控制：**近似串**，必须不命中（不含表内完整子串，但含前半截）。
#: ★ 构造原则：句子里要有一个"表内词的近似物"，否则就是恒真（不含子串当然不命中）。
OOC_NEG = [
    (u'我相信他会回来的。', 'ban'),              # 表里是「我相信你」
    (u'我理解这种心情，真的。', 'ban'),          # 表里是「我理解你的心情」
    # ★ 下面两条是**真误伤**候选：Deltarune 世界观里确实有机器人（Sweet Cap'n Cakes），
    #   Ralsei 提"机器人"完全正常；而"首先"只是很常见的连接词。
    (u'那三个是机器人呀，它们唱得可好了。', 'ooc'),
    (u'首先我得谢谢你，愿意留下来听我说。', 'ban'),
]
#: ★ 这条**不是**误伤，登记为"判据该命中"：Ralsei 说"大模型"确实出戏。
#:   （第一版我把它写成负控制，是**判据设计错了**，不是产品错了。）
OOC_TRUE_HIT = [
    (u'这不是什么大模型能算出来的事。', 'ooc'),
]


def ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def biggest_block(a, b):
    import difflib
    return max((x.size for x in difflib.SequenceMatcher(None, a, b).get_matching_blocks()),
               default=0)


def norm(s):
    return re.sub(u'[\\s，。！？!?、~…—\\-（）()「」“”"\\\'’*`]', '', str(s))


def main():
    rep = {'input': {}, 'arms': {}, 'controls': {}, 'findings': []}
    if not os.path.isdir(EV):
        os.makedirs(EV)

    _fn, seg, _consts = load_repeat_func(os.path.join(PET, 'src', 'main.py'))
    rep['input']['repeat_src_chars'] = len(seg)
    rep['input']['raw_dir'] = 'code-quality-audit/第128轮-结巴率收敛/_evidence/raw'
    rep['input']['repeat_min_chars'] = _consts.get('REPEAT_MIN_CHARS')

    class _Stub(object):
        """只为让 `getattr(type(self), 'REPEAT_MIN_CHARS', 12)` 读到产品里的那个数。"""
        REPEAT_MIN_CHARS = _consts.get('REPEAT_MIN_CHARS', 12)

    _SELF = _Stub()

    def repeat(text, recent=None):
        """★ self 必须显式传实例。

        第一版漏了：直接 `repeat(b, [a])` ⇒ `self=b`、`text=[a]`、`recent=None`
        ⇒ 函数第一行 `if not recent: return False` ⇒ **整段恒 False**。
        当时 C1 报"复读 0%"、C3 报"误伤 0/12"，两个数字都漂亮，全是**判据恒假**；
        是 C4 的正控制（6 对全报"漏判"）把它拽出来的。
        ⇒ 所以下面加一道**活性闸**：先用一对几乎相同的长句，必须判 True 才继续。
        """
        return _fn(_SELF, text, recent)

    # —— 活性闸（判据恒假比不写还危险）——
    _live_a = u'外面下着很大的雨，我们就在这儿等一会儿吧，反正也不着急回去。'
    _live_b = u'外面下着很大的雨，我们就在这儿等一会儿，反正也不着急回去。'
    if not repeat(_live_b, [_live_a]):
        raise SystemExit('判据活性闸失败：几乎相同的两句话都没判成重复 ⇒ '
                         '`_is_repeat_of_recent` 没被正确调用（检查 self 绑定）')

    data = {}
    for arm in ARMS:
        data[arm] = read_jsonl(arm + '.jsonl')
    # 分母闸：五个臂一个都不能空（空集会让人误以为"零违规"）
    empty = [a for a in ARMS if not data[a]]
    if empty:
        raise SystemExit('分母为空：%r' % (empty,))
    rep['input']['n'] = {a: len(data[a]) for a in ARMS}

    print('=' * 78)
    print('素材：%s' % rep['input']['n'])

    # ---------------- B: 出戏 / 客服腔（产品两条判据直调）
    print('')
    print('=' * 78)
    print('B. 出戏 / 客服腔 —— 300 条真实回复里的命中')
    print('=' * 78)
    tot = {'n': 0, 'ooc': 0, 'ban': 0, 'both': 0}
    hits = []
    for arm in ARMS:
        n = len(data[arm])
        o = [r for r in data[arm] if ES.looks_out_of_character(r['reply'])]
        b = [r for r in data[arm] if ES.looks_like_assistant_speak(r['reply'])]
        bo = [r for r in data[arm] if ES.looks_out_of_character(r['reply'])
              and ES.looks_like_assistant_speak(r['reply'])]
        rep['arms'][arm] = {'n': n, 'ooc': len(o), 'banned': len(b), 'both': len(bo)}
        tot['n'] += n
        tot['ooc'] += len(o)
        tot['ban'] += len(b)
        tot['both'] += len(bo)
        for r in o:
            hits.append({'arm': arm, 'kind': 'ooc', 'user': r['user'], 'reply': r['reply']})
        for r in b:
            hits.append({'arm': arm, 'kind': 'ban', 'user': r['user'], 'reply': r['reply']})
        print('  %-12s n=%3d  OOC=%d  客服腔=%d  同时=%d' % (arm, n, len(o), len(b), len(bo)))
    rep['arms']['_total'] = tot
    print('  %-12s n=%3d  OOC=%d  客服腔=%d  同时=%d' % ('合计', tot['n'], tot['ooc'],
                                                       tot['ban'], tot['both']))
    rep['findings'].append({'id': 'B', 'desc': '出戏/客服腔总命中',
                            'n': tot['n'], 'ooc': tot['ooc'], 'banned': tot['ban']})

    # 逐 pattern 明细（用来暴露误伤：哪个词一个人贡献了全部命中）
    print('')
    print('  逐 pattern 命中明细（只列 >0 的）：')
    per = {}
    for r in data['pnew_relax'] + data['pnew_bnew2'] + data['base']:
        t = (r['reply'] or '').lower()
        for p in ES._OOC_PATTERNS:
            if p in t:
                per.setdefault('OOC:' + p, []).append(r['reply'][:24])
        for p in ES._BANNED_PATTERNS:
            if p in t:
                per.setdefault('BAN:' + p, []).append(r['reply'][:24])
    for k in sorted(per):
        print('    %-24s %d 次  例：%s' % (k, len(per[k]), per[k][0]))
    rep['controls']['per_pattern'] = {k: len(v) for k, v in per.items()}

    # 正 / 负控制（★ 负控制用近似串，才真落在边界上）
    print('')
    print('  正控制（必须命中）：')
    pos_ok = 0
    for sent, kind in OOC_POS:
        got = (ES.looks_out_of_character(sent) if kind == 'ooc'
               else ES.looks_like_assistant_speak(sent))
        pos_ok += 1 if got else 0
        print('    [%s] %s  %r' % ('OK' if got else 'MISS', kind, sent))
    print('  负控制（近似串，应当**不**命中；命中即误伤）：')
    neg_bad = []
    for sent, kind in OOC_NEG:
        got = (ES.looks_out_of_character(sent) if kind == 'ooc'
               else ES.looks_like_assistant_speak(sent))
        if got:
            neg_bad.append(sent)
        print('    [%s] %s  %r' % ('HIT(误伤)' if got else 'OK', kind, sent))
    rep['controls']['ooc_pos_hit'] = pos_ok
    rep['controls']['ooc_pos_n'] = len(OOC_POS)
    rep['controls']['ooc_neg_falsehit'] = neg_bad
    print('  应当命中（登记为正确拦截，不是误伤）：')
    for sent, kind in OOC_TRUE_HIT:
        got = (ES.looks_out_of_character(sent) if kind == 'ooc'
               else ES.looks_like_assistant_speak(sent))
        print('    [%s] %s  %r' % ('OK' if got else 'MISS', kind, sent))
    print('  已知漏网（收窄的代价，如实登记；命中即说明规则被误改回"单词式"）：')
    known_miss_ok = 0
    for sent, kind in OOC_KNOWN_MISS:
        got = (ES.looks_out_of_character(sent) if kind == 'ooc'
               else ES.looks_like_assistant_speak(sent))
        known_miss_ok += 1 if not got else 0
        print('    [%s] %s  %r' % ('仍漏(符合预期)' if not got else '反而命中了', kind, sent))
    rep['controls']['known_miss'] = [(s, k) for s, k in OOC_KNOWN_MISS]
    rep['controls']['known_miss_still_missing'] = known_miss_ok

    # ---------------- C: 车轱辘话
    print('')
    print('=' * 78)
    print('C. 车轱辘话 —— `_is_repeat_of_recent` 在真实输出上的表现')
    print('=' * 78)

    # C1 同一问题问两遍（pnew_relax = 50 问 × 2 轮）
    pairs = data['pnew_relax']
    half = len(pairs) // 2
    same_q = [(pairs[i], pairs[i + half]) for i in range(half)]
    same_q = [(a, b) for a, b in same_q if a['user'] == b['user']]
    rep['input']['same_q_pairs'] = len(same_q)
    if len(same_q) != half:
        raise SystemExit('配对失败：%d/%d 的问题不一致（顺序假设被推翻）' % (len(same_q), half))
    c1_hit = [(a, b) for a, b in same_q if repeat(b['reply'], [a['reply']])]
    c1_ratios = [ratio(norm(a['reply']), norm(b['reply'])) for a, b in same_q]
    print('  C1 同一问题问两遍（%d 对）：判为重复 %d 对 = %.1f%%'
          % (len(same_q), len(c1_hit), 100.0 * len(c1_hit) / len(same_q)))
    print('     相似度：中位 %.3f  均值 %.3f  最大 %.3f'
          % (sorted(c1_ratios)[len(c1_ratios) // 2], sum(c1_ratios) / len(c1_ratios),
             max(c1_ratios)))
    for _a, _b in c1_hit[:3]:
        print('     命中例：[%s] %r → %r' % (_a['user'], _a['reply'][:26], _b['reply'][:26]))
    rep['arms']['_c1_same_question'] = {
        'pairs': len(same_q), 'repeat': len(c1_hit),
        'median': sorted(c1_ratios)[len(c1_ratios) // 2],
        'mean': sum(c1_ratios) / len(c1_ratios), 'max': max(c1_ratios),
        'examples': [{'user': a['user'], 'a': a['reply'], 'b': b['reply']}
                     for a, b in c1_hit]}

    # C2 相邻轮次（真机语义：recent = 自己最近 3 条）
    seq = data['pnew_relax']
    c2_hit = 0
    c2_n = 0
    c2_examples = []
    for i in range(3, len(seq)):
        rec = [seq[i - 1]['reply'], seq[i - 2]['reply'], seq[i - 3]['reply']]
        c2_n += 1
        if repeat(seq[i]['reply'], rec):
            c2_hit += 1
            if len(c2_examples) < 5:
                c2_examples.append((seq[i]['user'], seq[i]['reply'][:30]))
    print('  C2 相邻 3 条窗口（%d 条）：跨话题被判重复 %d 条 = %.1f%%'
          % (c2_n, c2_hit, 100.0 * c2_hit / c2_n))
    for u, t in c2_examples:
        print('     - [%s] %r' % (u, t))
    rep['arms']['_c2_cross_topic'] = {'n': c2_n, 'repeat': c2_hit, 'examples': c2_examples}

    # C3 误伤夹具（必须全部**不**命中）
    print('')
    print('  C3 误伤夹具（语义不同、字面相近；判据必须全部不命中）')
    fp = []
    for a, b in FALSE_POS_PAIRS:
        r = repeat(b, [a])
        rr = ratio(norm(a), norm(b))
        bb = biggest_block(norm(a), norm(b))
        if r:
            fp.append({'a': a, 'b': b, 'ratio': round(rr, 3), 'block': bb})
        print('    [%s] ratio=%.3f block=%2d  %r / %r'
              % ('误伤' if r else 'OK', rr, bb, a, b))
    print('    ⇒ 误伤 %d / %d' % (len(fp), len(FALSE_POS_PAIRS)))
    rep['controls']['false_pos_pairs'] = len(FALSE_POS_PAIRS)
    rep['controls']['false_pos_hits'] = fp

    # C4 漏判夹具（必须全部命中）
    print('')
    print('  C4 漏判夹具（长句只改两三字；判据必须全部命中）')
    fn_miss = []
    for a, b in FALSE_NEG_PAIRS:
        r = repeat(b, [a])
        rr = ratio(norm(a), norm(b))
        bb = biggest_block(norm(a), norm(b))
        if not r:
            fn_miss.append({'a': a, 'b': b, 'ratio': round(rr, 3), 'block': bb})
        print('    [%s] ratio=%.3f block=%2d' % ('OK' if r else '漏判', rr, bb))
    print('    ⇒ 漏判 %d / %d' % (len(fn_miss), len(FALSE_NEG_PAIRS)))
    rep['controls']['false_neg_pairs'] = len(FALSE_NEG_PAIRS)
    rep['controls']['false_neg_miss'] = fn_miss

    io.open(os.path.join(EV, 'probe129.json'), 'w', encoding='utf-8',
            newline='\n').write(json.dumps(rep, ensure_ascii=False, indent=1))
    print('')
    print('WROTE %s' % os.path.join(EV, 'probe129.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
