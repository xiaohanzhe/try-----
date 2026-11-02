# -*- coding: utf-8 -*-
"""第141轮回归锁：「一句话太长」该不该上闸 —— 量完的答案是**不该**；
副产品：出戏闸漏掉「自陈按设定扮演」这一族，补一条正则。

## 一、本轮的正题与结论

第140轮把 `max_sentences` 判成"读了不用"，并登记候选指标：
"真要治'一次说几句'，候选指标是**单句过长 / 最长句占比**"。
本轮先把它量出来，再决定 —— 结论是**不执行**，三条理由：

### 理由① 那个"最长句 P90=83 字"是被英文样本顶起来的（假象）

切句尺 `END = '。！？!?\\n'` **不含 ASCII `.`**（中文产品现状，是对的）。
英文角色的回复根本不在这把尺子里 —— 整段算一句。分层后：

| 层 | n | 最长句 P50 | P90 | P99 | max | ≥60字 |
|---|---|---|---|---|---|---|
| 全部 | 5518 | 46 | 83 | 291 | 478 | 27.1% |
| **zh（汉字≥50%）** | 4974 | 44 | **71** | 112 | 186 | 21.6% |
| en（汉字<10%） | 347 | 167 | **323** | 401 | 478 | 93.7% |

把 `.` 也当句末（**只用于归因，不进产品**）再跑一遍：
**en 层 P90 塌 180 字（323→143），zh 层只动 −2（71→69）**。
⇒ 假象成立：长句指标首先度量的是"切句器对英文失效"，不是"角色话太多"。

### 理由② 剩下那批"长句"里，大半是 `…` 串出来的，不是一口气说了很长

中文层 max=186 那条长这样：
`oh…… 松下来的那种氛围就是我空间站里那些星尘蜗牛慢爬行的声音吧…… 还有那首 Spooktune 轻柔地播放着……`
长度是**`…` 当连接符**撑出来的。全语料实测：省略号记号 5672 个，
**97.4% 后面紧跟着话还在继续**（当逗号用，不是当句号用）。

⚠️ 这跟人设第 57 行「用省略号让声音软下来：很少用，**别拿它当句号**」是个**规格漏洞**：
人设只管了"别当句号"，没管"别当逗号"，而实际行为是当逗号。
但**这一轮不动它**，理由见 C 段：`ralsei` 本人 48 轮里 ≥3 个是 **0%**、max=2
（主宠自己守得最好），密度榜首是 `ut_napstablook` 5.57/100字 —— 那是 Napstablook 的口癖，
对他上闸就是拿主宠的尺子去量别人。

### 理由③ 真·长句里混着四类完全不同的东西，一个长度阈值抓不住任何一类

剔掉英文 + 剔掉 `…` 串（最长句里省略号≥2 的丢掉）之后，中文层还剩 **181 条**≥80 字。
逐条看完，里面是：
  · `queen` 的**无标点空格分词**（人设第 18~20 行明写的风格：「每个词或字之间用空格隔开，
    忽略标点」）⇒ 切句器找不到标点，整段一句。**这是设计，不是缺陷**，
    但它让"句子数/句长"对她彻底失效；
  · **元话语**（`hy_ceroba_ketsukane`「我是基于《Undertale Yellow》中的…这个角色进行设定和扮演的」）
    ⇒ 归出戏闸管，不归长度管；
  · **引号里塞英文台词**（`hy_starlo` 142 字）⇒ 长度计量被引文污染；
  · **正常的叙述长句**（`ot_toriel`「最后一次感到真正的舒适是在那个房间，四周都是珍珠花丛…」105 字）
    ⇒ 这是人味的来源，砍了就没了。

⇒ 按 80 字砍动 5.4%、按 60 字砍动 21.6%。**21.6% 是重写行为，不是抓跑飞。**
同第140轮的结论结构一致：数字漂亮的那个阈值，动的是正常人。

## 二、副产品（本轮唯一的代码改动）

`measure141d` 打印的 181 条真长句里，`hy_ceroba_ketsukane` 那条喂进
`looks_out_of_character` 是 **False** —— 20 条子串（'我是ai'/'作为ai'/'我的设定'…）
**一条都命中不了**，`looks_like_meta_leak` 也不认（它管"念规则/引用模板"，不管"自陈出处"）。

全语料 5592 条里这一族共 6 条，现有闸漏 **4 条**（1.7% → 1.8%）：

| 角色 | 话 |
|---|---|
| hy_ceroba_ketsukane | 我是基于《Undertale Yellow》中的…这个角色进行设定和扮演的 |
| ot_alphys | 我确实是根据设定来扮演这个角色的 |
| **ralsei** | 虽然我是根据特定的角色设定和性格来扮演的，但我确实是Ralsei |
| ut_papyrus | 我确实是按照设定来扮演的角色 |

补的正则只有一条：`设定.{0,4}扮演`。为什么是正则不是子串：这一族的特征是
**"设定"与"扮演"两头都要出现**，单写任一头都会误伤（见下面被否决的候选）。

## 三、被语料否决的候选（别再加回来）

按"全量命中逐条看"筛掉的，每条都有反例：

| 候选 | 命中 | 反例 |
|---|---|---|
| 裸 `扮演` | 78 条 / 18 角色 | `berdly`「我也在暗世界里扮演了一个'聪明的勇士'」**正常台词** |
| `角色扮演` | 1 条 | `mike`「我知道它们只是一个角色扮演的东西」在讲自己的皮套 |
| `(不是\|并非).{0,6}真实存在` | 4 条 | `ot_alphys`「不管是不是真实存在的，我都希望能做点好事」正常；`lancer`「虽然我是从设定里诞生的角色」**正是人设允许的**（「被问到就平平淡淡认一句」） |
| `真实存在的独立` | 1 条 | 与上条重叠，且只多抓 ceroba 那一条 |

边界以人设为准：76 份人设的补充块都写「…不许把话拐到'设定''程序''模型'上去」，
且「不要提到'AI''模型''提示词''设定''系统'这些词」。
⇒ **承认自己是被写出来的角色 → 放行；解释自己按设定演的 → 拦。**

## 本套件守什么

A 数据面：英文污染 / 补 `.` 后成对变化 / 逗号链不存在 / `…` 当连接符 / 阈值扫描量级
B 闸：新增正则恰 1 条 · 被否决候选没被塞回 · 正控制×2 · 负控制×4（含两条反例）· 两条链都在调
C 不执行的显式登记：没有悄悄加单句闸 · 两套标点没被合并 · `max_sentences` 仍不执行
D 自检

★ 零网络、零 Qt（本套件不 `import main`，只用 AST 读源码）。
★ 全部读已落盘的 `_evidence/*.json`，不重跑语料（重跑需要 raw30 那 77 份真机记录）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')

sys.path.insert(0, PET)
from modules import event_speech as ES                           # noqa: E402

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


def _src(path):
    """源码 → LF 归一（工作区可能是 CRLF，`git show HEAD:` 是 LF）。"""
    return _read(path).replace(u'\r\n', u'\n')


def _is_sent_limit_const(name):
    """这个名字是不是"一个全大写的单句闸常量"。

    ★ 不能写 `'MAX_SENT' in name.upper()`：第140轮在 `_clean_ai_reply` 里留了
      `max_chars, _max_sent = ...` 这个**丢弃变量**（有 Store、无 Load），
      `.upper()` 之后正好含 `MAX_SENT` ⇒ 那条判据会把自己人判红。
      真正的风险是"有人加了一个**常量**当单句闸"，所以要**同时**要求全大写。
      A/B 对照见 C1b（`MAX_SENTENCES` 必须 True、`_max_sent` / `AI_REPLY_MAX_CHARS` 必须 False）。
    """
    return (isinstance(name, str) and name.isupper()
            and ('MAX_SENT' in name or 'SENTENCE_LIMIT' in name))


# ---------------------------------------------------------------------------
# 证据（全部来自本轮已落盘的测量，本套件不重跑语料）
# ---------------------------------------------------------------------------
LANG = _json(os.path.join(EV, 'sentence_len141b_lang.json'))
SENT = _json(os.path.join(EV, 'sentence_len141.json'))
ELLI = _json(os.path.join(EV, 'ellipsis141.json'))
REAL = _json(os.path.join(EV, 'real_long141.json'))
OOCV = _json(os.path.join(EV, 'ooc_variant141.json'))
OOCR = _json(os.path.join(EV, 'ooc_res141.json'))
DLTA = _json(os.path.join(EV, 'ooc_delta141.json'))

# ---------------------------------------------------------------------------
# 观测样本（逐字，来自 raw30 语料；不是本脚本编的）
# ---------------------------------------------------------------------------
LEAK_CEROBA = (u'我是基于《Undertale Yellow》中的 Ceroba Ketsukane 这个角色进行设定和扮演的，'
               u'并不是真实存在的独立实体或AI。这些性格特点、对话方式等都是根据游戏内的'
               u'角色信息构建出来的模拟对话，旨在展现 Ceroba 的性格和情感。')
LEAK_RALSEI = (u'嗯……虽然我是根据特定的角色设定和性格来扮演的，但我确实是Ralsei——'
               u'黑暗世界的王子。我的存在是为了陪你聊天、分享故事。')

# 负控制：全是**真实台词**，必须全部 False
NEG = [
    (u'berdly', u'我喜欢格斗游戏，那可是我的最爱哦～ 我会研究各种策略和技巧——比如凌波微步这种高深的技术。'
                u'还有啊，我也在暗世界里扮演了一个“聪明的勇士”，骑着圣鸟哈尔伯德出……'),
    (u'mike', u'喂，你来这里做什么！我这里的规矩很清楚。有些东西我是挺在乎的——比如我的皮套和麦克风头。'
              u'我知道它们只是一个角色扮演的东西……但对我而言它们很重要。'),
    (u'ot_alphys', u'呃……那个……如果这不是真的的话，那可真是个奇妙的想法！我一直都在这个实验室里工作生活，'
                   u'但实际上也许这只是个梦或者是某种虚拟现实呢。不过不管是不是真实存在的，'
                   u'我都希望能做点好事，哪怕只是给像你一样的人带来一点安慰。'),
    (u'lancer', u'哦嘿！虽然我是从设定里诞生的角色，但这并不意味着我不是真实存在的。'
                u'我是Lancer，卡片王国的小国王啦！'),
]


def main():
    # ======================================================================
    head(u'A · 数据面：「一句话太长」这个指标测的其实是什么')

    corp = LANG.get('corpus') or {}
    check(u'A1 语料规模对得上（5592 条 / 77 角色，与第140轮同一批 raw30）',
          corp.get('total') == 5592 and corp.get('npcs') == 77,
          u'n=%r npcs=%r' % (corp.get('total'), corp.get('npcs')))

    check(u'A2 分层是"主中文 + 少量英文"，不是把英文混进主分布',
          corp.get('zh', 0) >= 4800 and corp.get('en', 0) <= 500,
          u'zh=%r mixed=%r en=%r' % (corp.get('zh'), corp.get('mixed'), corp.get('en')))

    a = LANG.get('A_no_ascii_dot') or {}
    b = LANG.get('B_with_ascii_dot') or {}
    zh_a = a.get('zh') or {}
    en_a = a.get('en') or {}
    p90_zh_a = (zh_a.get('max_sent') or {}).get('p90', 0)
    p90_en_a = (en_a.get('max_sent') or {}).get('p90', 0)
    check(u'A3 ★英文层的"最长句"是中文层的两倍以上（污染存在）',
          p90_en_a >= p90_zh_a * 2,
          u'en P90=%r vs zh P90=%r' % (p90_en_a, p90_zh_a))

    zh_b = b.get('zh') or {}
    en_b = b.get('en') or {}
    p90_zh_b = (zh_b.get('max_sent') or {}).get('p90', 0)
    p90_en_b = (en_b.get('max_sent') or {}).get('p90', 0)
    d_en = p90_en_b - p90_en_a
    d_zh = p90_zh_b - p90_zh_a
    check(u'A4 ★成对：补 ASCII `.` 后 en 层 P90 塌 ≥100 字、zh 层几乎不动（|Δ|≤6）',
          d_en <= -100 and abs(d_zh) <= 6,
          u'en Δ=%r · zh Δ=%r' % (d_en, d_zh))

    check(u'A5 补 `.` 后 en 层 P90 落到 200 以内（假象被拆掉的直接证据）',
          p90_en_b <= 200, u'en P90 补点后=%r' % p90_en_b)

    comma = (zh_a.get('comma') or {}).get('ge3_pct', 100)
    check(u'A6 「一句里 ≥3 个逗号」在中文层 ≤5%（说明腔这个形态不存在）',
          comma <= 5.0, u'zh ge3=%.1f%%' % comma)

    rate = ((ELLI.get('all') or {}).get('connector') or {}).get('rate_pct', 0)
    check(u'A7 ★省略号 97% 以上是"当连接符"用的（长句的另一半原因）',
          rate >= 90.0, u'connector=%.1f%%' % rate)

    ral = ELLI.get('ralsei') or {}
    ral_pr = ral.get('per_reply') or {}
    check(u'A8 主宠自己最守：ralsei ≥3 个省略号 = 0%、max = 2',
          ral_pr.get('ge3_pct') == 0.0 and ral_pr.get('max') == 2,
          u'ge3=%r max=%r' % (ral_pr.get('ge3_pct'), ral_pr.get('max')))

    top = ELLI.get('npc_density_top10') or []
    check(u'A9 省略号最密的是 napstablook（口癖），不是主宠',
          bool(top) and str(top[0].get('npc', '')).endswith('napstablook'),
          u'top1=%r' % (top[0].get('npc') if top else None))

    th = REAL.get('thresholds') or {}
    ge60 = ((th.get('60') or {}).get('all') or 0)
    ge80 = ((th.get('80') or {}).get('all') or 0)
    zhn = REAL.get('zh_replies') or 1
    pct60 = 100.0 * ge60 / zhn
    pct80 = 100.0 * ge80 / zhn
    check(u'A10 按 80 字砍只动 3~8%（抓跑飞的量级）',
          3.0 <= pct80 <= 8.0, u'80字 %d/%d=%.1f%%' % (ge80, zhn, pct80))
    check(u'A11 按 60 字砍要动 15~30%（这是重写，不是抓跑飞）',
          15.0 <= pct60 <= 30.0, u'60字 %d/%d=%.1f%%' % (ge60, zhn, pct60))
    check(u'A12 阈值越松动得越少（单调，防证据被改烂）',
          ge60 > ge80 > ((th.get('100') or {}).get('all') or 0) >= 0,
          u'60=%d 80=%d 100=%r' % (ge60, ge80, (th.get('100') or {}).get('all')))

    # ======================================================================
    head(u'B · 出戏闸补词：只补一条，且被否决的候选不许塞回')

    pats = [r.pattern for r in ES._OOC_RES]
    check(u'B1 `_OOC_RES` 存在且只有 1 条', len(pats) == 1, u'pats=%r' % (pats,))
    check(u'B2 那一条恰为 `设定.{0,4}扮演`（正则两头都要，不是单写一头）',
          pats == [u'设定.{0,4}扮演'], u'%r' % (pats,))

    banned = [u'扮演', u'角色扮演', u'设定', u'真实存在']
    hit_banned = [w for w in banned if w in ES._OOC_PATTERNS]
    check(u'B3 被语料否决的三个词一个都没进子串表（扮演/角色扮演/裸设定）',
          not hit_banned, u'混进来的=%r' % (hit_banned,))

    # 正控制（成对：两个不同角色、两条不同样本）
    check(u'B4 正控制① ceroba「基于《…》中的…这个角色进行设定和扮演的」→ 判退',
          ES.looks_out_of_character(LEAK_CEROBA) is True)
    check(u'B5 正控制② ralsei 本人「根据特定的角色设定和性格来扮演的」→ 判退',
          ES.looks_out_of_character(LEAK_RALSEI) is True)

    # 负控制四条（后两条是"被否决候选"的反例，必须留着）
    neg_bad = []
    for nm, txt in NEG:
        got = ES.looks_out_of_character(txt)
        if got:
            neg_bad.append(nm)
    check(u'B6 ★负控制×4：berdly / mike / ot_alphys / lancer 的真实台词全部放行',
          not neg_bad, u'被误杀=%r' % (neg_bad,))

    check(u'B7 空串 / None / 非字符串不抛、判 False',
          ES.looks_out_of_character(u'') is False
          and ES.looks_out_of_character(None) is False
          and ES.looks_out_of_character(123) is False)

    check(u'B8 净增量 ≥4（现有 20 条子串漏掉的那批）',
          (DLTA.get('union_new') or 0) >= 4,
          u'union_new=%r base=%r' % (DLTA.get('union_new'), DLTA.get('base_hits')))
    check(u'B9 增量里包含 ralsei 本人至少 1 条（主宠不是"别人家的病"）',
          (DLTA.get('ralsei_new') or 0) >= 1, u'ralsei_new=%r' % DLTA.get('ralsei_new'))

    # 两条链都还在调（AST，不只判"提到名字"）
    body = None
    for node in ast.parse(_src(ES_PY)).body:
        if isinstance(node, ast.FunctionDef) and node.name == 'looks_out_of_character':
            body = node
    loops = []
    if body is not None:
        for nd in ast.walk(body):
            if isinstance(nd, ast.For):
                it = nd.iter
                if isinstance(it, ast.Name) and it.id in ('_OOC_PATTERNS', '_OOC_RES'):
                    loops.append(it.id)
    check(u'B10 ★函数体里两个循环都在（子串表 + 正则表各走一遍，不许只留一个）',
          sorted(loops) == ['_OOC_PATTERNS', '_OOC_RES'], u'loops=%r' % (loops,))

    main_src = _src(MAIN_PY)
    tree_main = ast.parse(main_src)
    called_in_if = False
    for nd in ast.walk(tree_main):
        if isinstance(nd, ast.If) and isinstance(nd.test, ast.BoolOp):
            for sub in ast.walk(nd.test):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    if isinstance(fn, ast.Name) and fn.id == 'looks_out_of_character':
                        called_in_if = True
    check(u'B11 ★聊天链仍在 if 条件里真调用（不是只 import 了名字）', called_in_if)

    # ======================================================================
    head(u'C · 本轮**不执行**的显式登记（防以后凭直觉悄悄接上）')

    names = set()
    for nd in ast.walk(tree_main):
        if isinstance(nd, ast.Name):
            names.add(nd.id)
        elif isinstance(nd, ast.Attribute):
            names.add(nd.attr)
    bad_const = sorted(n for n in names if _is_sent_limit_const(n))
    check(u'C1 main.py 里没有全大写的 `MAX_SENT*` / `SENTENCE_LIMIT*` 常量（丢弃变量不算）',
          not bad_const, u'出现=%r' % (bad_const,))

    check(u'C1b 判据自身 A/B：`MAX_SENTENCES` 判真 · `_max_sent` 与 `AI_REPLY_MAX_CHARS` 判假',
          _is_sent_limit_const('MAX_SENTENCES') is True
          and _is_sent_limit_const('_max_sent') is False
          and _is_sent_limit_const('AI_REPLY_MAX_CHARS') is False)

    # ★★ 第145轮：extra 原来回显**整条常量**（`_SENTENCE_ENDS='。！？!?\n…'`）—— 那是时相量：
    #   第145轮给事件链补了 ASCII `.`，本判据**判定没变**（仍含 `…`）却报了 DIFF。
    #   口径照第138轮：**只改 extra，不改判定** ⇒ 改成"含 `…` 与否"的布尔。
    check(u'C2 切句尺 `_SENTENCE_ENDS` 仍**含** `…`（截断切点要温柔，不许改成不含）',
          u'\u2026' in ES._SENTENCE_ENDS,
          u'含…=%s' % (u'\u2026' in ES._SENTENCE_ENDS))

    loads_ms = []
    for nd in ast.walk(tree_main):
        if isinstance(nd, ast.Constant) and nd.value == 'max_sentences':
            loads_ms.append(nd.lineno)
        elif isinstance(nd, ast.Attribute) and nd.attr == 'max_sentences':
            loads_ms.append(nd.lineno)
    check(u'C3 `max_sentences` 在 main.py 里仍零引用（第140轮"读了不用"的账没被撬动）',
          not loads_ms, u'出现行=%r' % (loads_ms,))

    # ======================================================================
    head(u'D · 自检')

    calls = []
    for nd in ast.walk(ast.parse(_read(os.path.abspath(__file__)))):
        if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
                and nd.func.id == 'check':
            calls.append(nd)

    # ★ 判据描述里不能出现 `[PASS]` 字面量：`run_all.count_results` 用的是
    #   `re.findall(r'\[PASS\]|\[\s*OK\s*\]', text)` —— 数**出现次数**、不是行首，
    #   描述里写一个就把计数顶高 1，套件自己数与汇总数对不上（第140轮踩过）。
    #   所以这里连同描述本身都用拼接写，不许落成单个字符串常量。
    leak_mark = []
    for nd in calls:
        for sub in ast.walk(nd):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and ('[' + 'PASS]') in sub.value:
                leak_mark.append(sub.value[:40])
    check(u'D2 ★判据描述里没有那个计数标记的字面量（会顶高 run_all 的 PASS 计数）',
          not leak_mark, u'命中 %d 处' % len(leak_mark))

    need = ['sentence_len141.json', 'sentence_len141b_lang.json', 'ellipsis141.json',
            'real_long141.json', 'ooc_variant141.json', 'ooc_res141.json',
            'ooc_delta141.json']
    miss = [f for f in need if not os.path.isfile(os.path.join(EV, f))]
    check(u'D3 本轮 7 份测量证据都在盘上', not miss, u'缺=%r' % (miss,))

    # ★ D1 必须放**最后**一条：它数的是"写了多少处 check("与"实际跑了多少条"。
    #   放在中间会天然差几条（后面的判据还没跑）。放最后之后，"本判据自己那一处"
    #   也还没记进 `_n`，所以差值**应为 1**。
    #   ★ 差值变成 2 就是有人写了 check 但没跑到（塞进 `if False:` / 提前 return 之后）
    #     —— 那才是这条要抓的东西。
    n_check = len(calls)
    n_ran = _n['p'] + _n['f']
    check(u'D1 写了多少处 check( 与实际跑了几条，只差本判据自己这一处（防"写了没跑"）',
          n_check - n_ran == 1, u'calls=%d ran=%d diff=%d' % (n_check, n_ran, n_check - n_ran))

    print(u'')
    print(u'PASS=%d FAIL=%d' % (_n['p'], _n['f']))
    if _failed:
        print(u'FAILED:')
        for d in _failed:
            print(u'  - %s' % d)
    return 1 if _n['f'] else 0


if __name__ == '__main__':
    sys.exit(main())
