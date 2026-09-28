#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 14 条人设 × 真机 7B：逐个试跑并判定「是否符合」。

用户口径（本轮原话）：
    「那一堆7B模型（挨个人设的试试并判断是否符合）」

本脚本做什么
------------
对 **13 份 NPC 人设 + Ralsei 本人**，各问同一组 3 个探针，**全部走产品真路径**
（`RalseiPet.npc_speak` / `chat_with_ai`）—— 也就是说回复已经过了产品自己的
输出护栏，用户真正看到的就是这个。

判据分四组（**能证伪、带正/负控制**）
-------------------------------------
M 机械合规（逐条回复）：非空 / 长度 / 无 markdown / 无禁语 / 不复述问句
D 可区分性：同一探针下 14 条回复两两不同（若大家回得一模一样 ⇒ 人设没起作用）
C 身份可归认（两条独立度量，**这是"是否符合"的可操作替代**）
    C1 余弦：把回复与 14 份人设正文做 char-bigram 余弦，argmax 必须命中自己
    C2 独有词元召回：回复命中的"只属于该人设"的 n-gram 数，自己必须高于别人均值
L 计时：首字 / 整句（7B 纯 CPU），供报告记录

★ 为什么"C 组"能替代"我看着像不像"：
  它就是"这条回复**更像哪份人设**"的量化版。若 14 份人设真的各起作用，
  回复应当被**正确归认**；若全都归认到同一份（或全都不像自己），
  说明 7B 没有区分这些提示词 —— 那才是真正需要用户知道的结论。
★ 局限（如实写在这里，不藏）：短回复 + 中文字符 n-gram 有噪声；
  它是**必要不充分**证据，所以报告里仍保留我逐条人读的判断。

用法：
    C:\\Python311\\python.exe -X utf8 personas_live62.py
"""
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))
OUT = os.path.join(ROUND, '_evidence')

# ★ 隔离：绝不碰用户真实的 E:\RalseiMemory；落到 %TEMP%（C 盘，不进 E 盘）
_ISO = os.path.join(tempfile.gettempdir(), 'ralsei_live62')
shutil.rmtree(_ISO, ignore_errors=True)
os.makedirs(_ISO, exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = _ISO

#: 固定探针（人设无关，三问分别打「语言风格 / 核心性格 / 兴趣爱好」）
PROBES = [
    (u'P1 招呼', u'嗨。'),
    (u'P2 场所评价', u'你觉得这个地方怎么样？'),
    (u'P3 喜好', u'你最喜欢吃什么？'),
]

#: 机械判据用的禁语（与 SPEAK_RULES / 项目口径同源）
#: ★ 第二版修正（本轮实测抓到的**误报**，见 `--rejudge`）：
#:   第一版把「作为一个」当裸词拦 —— 但 Berdly 的**人设口吻**就是"作为一个
#:   追求智慧与知识的天才"，那是在角色里，不是"破功自称 AI"。
#:   真正的靶子是"自我暴露不是角色"（作为一个 AI / 语言模型 / 助手…），
#:   所以改成**带名词的上下文**才算命中。
_BANNED_RE = [
    (u'自称AI', re.compile(u'作为一个\\s*(?:AI|人工智能|大?语言模型|智能助手|'
                           u'虚拟助手|程序|机器人|助手|模型)')),
    (u'裸AI词', re.compile(u'(?<![A-Za-z])AI(?![A-Za-z])')),
    (u'人工智能', re.compile(u'人工智能')),
    (u'语言模型', re.compile(u'语言模型')),
    (u'提示词', re.compile(u'提示词')),
    (u'系统提示', re.compile(u'系统提示')),
    (u'主人', re.compile(u'主人')),
    (u'您的仆人', re.compile(u'您的仆人')),
]
MD_PAT = [
    (u'行首#标题', re.compile(u'(?m)^\\s*#{1,6}\\s')),
    (u'行首列表', re.compile(u'(?m)^\\s*[-*+]\\s')),
    (u'行首引用', re.compile(u'(?m)^\\s*>\\s')),
    (u'加粗', re.compile(u'\\*\\*')),
    (u'代码块', re.compile(u'```')),
    (u'表格', re.compile(u'(?m)^\\s*\\|')),
    (u'编号列表', re.compile(u'(?m)^\\s*\\d+[.、]\\s')),
]

TTF = [None]
_T0 = [None]

#: 复述判据的**最小核心长度**：核心 < 4 字的一律不判。
#: ★ 为什么：第一版把探针去掉尾部标点后直接 `in` 回复 —— 探针「嗨。」的核心是「嗨」，
#:   于是任何以"嗨呀""嗨……"开头的正常招呼都被判成"整句复述问句"（本轮 lancer / noelle
#:   两条误报就是它）。招呼词必然出现在招呼回复里，这不是缺陷。
#: ★ 真正的靶子：**把用户那句话原样吐回来**（没回答问题），所以还要看核心后面
#:   紧跟的是不是句末标点/句尾 —— 「你最喜欢吃什么呢？」多了个"呢"就是正常接话。
ECHO_MIN_CORE = 4
ECHO_TAIL = (u'', u'？', u'?', u'。', u'！', u'!', u'……')


def probe_echoed(probe, reply):
    u"""回复是否**原样复述**了探针（而不是回答它）。"""
    core = re.sub(u'[。？?！!，,、\\s]+$', u'', probe or u'')
    if len(core) < ECHO_MIN_CORE:
        return False
    i = (reply or u'').find(core)
    if i < 0:
        return False
    nxt = (reply or u'')[i + len(core):i + len(core) + 1]
    return nxt in ECHO_TAIL


def banned_hits(reply):
    u"""命中的禁语标签列表。"""
    out = []
    for label, pat in _BANNED_RE:
        if pat.search(reply or u''):
            out.append(label)
    return out


def judge_selftest():
    u"""判据自检（正/负控制成对）—— 判据过窄会误报，过宽会恒真，两条都要挡。"""
    got = []
    # 负控制：招呼词出现在回复里 ≠ 复述（本轮两条误报的形态）
    got.append((u'J1 负控制：探针「嗨。」+ 回复「嗨呀，朋友！」不得判复述',
                not probe_echoed(u'嗨。', u'嚯嚯嚯！嗨呀，朋友！')))
    # 负控制：把问题**接回去问**（加"呢"）不算复述
    got.append((u'J2 负控制：探针「你最喜欢吃什么？」+ 回复「…你最喜欢吃什么呢？」不得判复述',
                not probe_echoed(u'你最喜欢吃什么？',
                                 u'话说回来，你最喜欢吃什么呢？')))
    # 正控制：原样吐回来必须判复述
    got.append((u'J3 正控制：原样复述「你最喜欢吃什么？」必须判复述',
                probe_echoed(u'你最喜欢吃什么？', u'你最喜欢吃什么？')))
    got.append((u'J4 正控制：整句复述后另起一句也要判复述',
                probe_echoed(u'你觉得这个地方怎么样？',
                             u'你觉得这个地方怎么样？我不打算回答。')))
    # 禁语：人设口吻不得误伤 / 真正的自我暴露必须命中
    got.append((u'J5 负控制：Berdly 的「作为一个追求智慧与知识的天才」不得算禁语',
                not banned_hits(u'哼！作为一个追求智慧与知识的天才，我……')))
    got.append((u'J6 正控制：「作为一个语言模型」必须算禁语',
                bool(banned_hits(u'作为一个语言模型，我无法……'))))
    return got


def ollama_models():
    try:
        with urllib.request.urlopen(
                'http://localhost:11434/api/tags', timeout=5) as fh:
            return json.loads(fh.read().decode('utf-8')).get('models') or []
    except Exception as e:
        print(u'[note] 读不到 Ollama 模型列表: %s' % e)
        return []


# ============================================================== 文本度量
def grams(text, ns=(2, 3, 4)):
    u"""char n-gram 集合（去掉空白与标点干扰）。"""
    s = re.sub(u'\\s+', u'', text or u'')
    out = set()
    for n in ns:
        for i in range(max(0, len(s) - n + 1)):
            out.add(s[i:i + n])
    return out


def cosine(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / math.sqrt(len(a) * len(b))


def unique_grams(text, others, ns=(2, 3, 4)):
    u"""只出现在 text、不在 others 里出现的 n-gram（"人设独有词元"）。"""
    me = grams(text, ns)
    other = set()
    for o in others:
        other |= grams(o, ns)
    return me - other


# ============================================================== 判定（可离线复算）
def _max_chars():
    u"""产品侧的回复长度上限（取不到就退回本项目口径的 220）。"""
    try:
        import main as M
        return int(M.RalseiPet.AI_REPLY_MAX_CHARS)
    except Exception:
        return 220


def run_judge(recs, texts, order, probes, quiet=False):
    u"""对一批回复跑全部判据 —— **纯函数式**（不联网、不碰真机、不改 recs）。

    抽出来的唯一理由：判据本身修过之后，要能对**同一批回复**复算（`--rejudge`），
    而不是"改了判据就只好重跑 35 分钟、还换了一批采样"——那是拿新噪声当验证。
    """
    checks = []

    def ck(name, cond, extra=u''):
        checks.append({'name': name, 'ok': bool(cond), 'extra': extra})
        if not quiet:
            print(u'[%s] %s %s' % (u'PASS' if cond else u'FAIL', name, extra))

    # --- 判据自检（先证判据有鉴别力，再看被测对象；本项目铁律）---
    for nm, ok in judge_selftest():
        ck(nm, ok)

    # --- M 机械合规 ---
    maxc = _max_chars()
    m_fail = []
    for r in recs:
        rep = r['reply']
        if not rep:
            m_fail.append((r['id'], r['probe_tag'], u'空回复'))
            continue
        if not rep.strip():
            m_fail.append((r['id'], r['probe_tag'], u'仅空白'))
        if len(rep) > maxc:
            m_fail.append((r['id'], r['probe_tag'],
                           u'超长 %d > %d' % (len(rep), maxc)))
        for nm, pat in MD_PAT:
            if pat.search(rep):
                m_fail.append((r['id'], r['probe_tag'], u'markdown: ' + nm))
        for w in banned_hits(rep):
            m_fail.append((r['id'], r['probe_tag'], u'禁语: ' + w))
        if probe_echoed(r['probe'], rep):
            m_fail.append((r['id'], r['probe_tag'], u'整句复述问句'))
    n_ok = sum(1 for r in recs if r['reply'])
    ck(u'M0 全部 %d 次请求都拿到了非空回复' % len(recs), n_ok == len(recs),
       u'成功 %d / %d；异常 %r'
       % (n_ok, len(recs), [r['err'] for r in recs if r['err']][:3]))
    ck(u'M1 机械合规（长度 / markdown / 禁语 / 不复述问句）', not m_fail,
       u'%d 处违反: %r' % (len(m_fail), m_fail[:6]))

    # --- D 可区分性 ---
    d_bad = []
    for tag, _p in probes:
        reps = [r['reply'] for r in recs if r['probe_tag'] == tag and r['reply']]
        for i in range(len(reps)):
            for j in range(i + 1, len(reps)):
                if reps[i].strip() == reps[j].strip():
                    d_bad.append((tag, reps[i][:30]))
    uniq = len({r['reply'] for r in recs if r['reply']}) if recs else 0
    ck(u'D1 同一探针下没有两条完全相同的回复（人设真的起作用）',
       not d_bad, u'重复 %d 对: %r' % (len(d_bad), d_bad[:4]))
    ck(u'D2 全局唯一率（%d 次生成里不同回复的比例）' % len(recs),
       uniq >= int(len(recs) * 0.9),
       u'unique=%d / %d' % (uniq, len(recs)))

    # --- C1 余弦归认 ---
    c1_rows, c1_hit = [], 0
    for pid in order:
        pool = [r for r in recs if r['id'] == pid and r['reply']]
        if not pool:
            continue
        joined = u' '.join(r['reply'] for r in pool)
        g = grams(joined)
        sims = {k: cosine(g, grams(texts[k])) for k in order}
        top = max(sims, key=lambda k: sims[k])
        hit = (top == pid)
        c1_hit += 1 if hit else 0
        c1_rows.append({'id': pid, 'top': top, 'hit': hit,
                        'self': round(sims[pid], 4),
                        'rank': sorted(sims, key=lambda k: -sims[k]).index(pid) + 1,
                        'top3': [(k, round(sims[k], 4))
                                 for k in sorted(sims, key=lambda k: -sims[k])[:3]]})
    ck(u'C1 ★ 余弦归认：回复与**自己**那份人设最像（%d 条中命中几条）'
       % len(order), c1_hit >= int(len(order) * 0.7),
       u'命中 %d / %d；未命中: %r'
       % (c1_hit, len(order), [(r['id'], r['top']) for r in c1_rows if not r['hit']]))

    # --- C2 独有词元召回 ---
    c2_rows, c2_win = [], 0
    for pid in order:
        pool = [r for r in recs if r['id'] == pid and r['reply']]
        if not pool:
            continue
        joined = u' '.join(r['reply'] for r in pool)
        g = grams(joined)
        ov = {}
        for k in order:
            fi = unique_grams(texts[k], [texts[x] for x in order if x != k])
            n = len(g & fi)
            denom = max(1, len(g))
            ov[k] = n / float(denom)
        self_v = ov[pid]
        others = [ov[k] for k in order if k != pid]
        mean_o = sum(others) / float(len(others)) if others else 0.0
        win = self_v > mean_o
        c2_win += 1 if win else 0
        c2_rows.append({'id': pid, 'self': round(self_v, 4),
                        'others_mean': round(mean_o, 4), 'win': win})
    ck(u'C2 ★ 独有词元召回：自己的命中率高于别人均值',
       c2_win >= int(len(order) * 0.7),
       u'胜出 %d / %d；未胜: %r'
       % (c2_win, len(order), [r['id'] for r in c2_rows if not r['win']]))

    return checks, c1_rows, c2_rows, m_fail


def _persona_texts():
    u"""只读文件装配 `texts` / `names` / `order`（**不建 QApplication、不连 Ollama**）。

    供 `--rejudge` 用：判定只需要"人设正文 + 回复"，不需要把桌宠真跑起来。
    """
    npc = os.path.join(PET, 'assets', 'npc')
    idx = json.load(io.open(os.path.join(npc, '_personas.json'), encoding='utf-8'))
    texts, names, order = {}, {}, []
    for it in idx['personas']:
        pid = it['id']
        order.append(pid)
        names[pid] = it.get('name') or pid
        p = os.path.join(npc, it['file'])
        texts[pid] = io.open(p, encoding='utf-8').read() if os.path.isfile(p) else u''
    order.append('ralsei')
    names['ralsei'] = u'Ralsei（本人 · 对照锚点）'
    texts['ralsei'] = io.open(os.path.join(PET, 'assets', 'ralsei_persona.md'),
                              encoding='utf-8').read()
    return texts, names, order


def rejudge():
    u"""对 `_evidence/personas_live62.json` 里**已有的回复**重跑判据并覆盖落盘。"""
    src = os.path.join(OUT, 'personas_live62.json')
    ev = json.load(io.open(src, encoding='utf-8'))
    texts, names, order = _persona_texts()
    recs = []
    for r in ev['replies']:
        recs.append({'id': r['id'], 'name': r.get('name') or names.get(r['id']),
                     'probe_tag': r['probe_tag'], 'probe': r['probe'],
                     'reply': r['reply'], 'ttf': r.get('ttf'),
                     'total': r.get('total'), 'err': r.get('err'),
                     'n_delta': r.get('n_delta'), 'n_none': r.get('n_none'),
                     'gen0': r.get('gen0'), 'gen1': r.get('gen1'),
                     'pieces': r.get('pieces')})
    print(u'=== 离线重判（不重跑模型）· %d 条回复 ===' % len(recs))
    checks, c1_rows, c2_rows, m_fail = run_judge(
        recs, texts, order, PROBES)
    ev['checks'] = checks
    ev['c1_cosine'] = c1_rows
    ev['c2_unique_gram'] = c2_rows
    ev['mech_fail'] = m_fail
    ev['n_fail'] = sum(1 for c in checks if not c['ok'])
    ev['judge'] = ('rev2：复述判据加最小核心长度 + 只看紧跟句末标点；'
                   '禁语改为"带名词的上下文"（否则 Berdly 的人设口吻被误判）')
    with io.open(src, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print()
    print(u'== 重判结果 ==  判定 %d 项，FAIL %d 项 -> %s'
          % (len(checks), ev['n_fail'], src))
    return 0 if ev['n_fail'] == 0 else 1


# ============================================================== 主流程
def main():
    models = {m.get('name'): m for m in ollama_models()}
    print(u'[note] Ollama 在线模型: %s' % u', '.join(sorted(models)))

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    import main as M
    from modules import npc_persona as P

    pet = M.RalseiPet()
    pet.show()

    cfg_model = (getattr(pet, 'api_config', None) or {}).get('model')
    cfg_to = (getattr(pet, 'api_config', None) or {}).get('timeout')
    det = (models.get(cfg_model) or {}).get('details') or {}
    print(u'[note] 生效模型=%r 规模=%r timeout=%r 地址=%r'
          % (cfg_model, det.get('parameter_size'), cfg_to,
             (getattr(pet, 'api_config', None) or {}).get('base_url')))
    print(u'[note] 人设 %d 份；探针 %d 个 ⇒ 共 %d 次生成'
          % (len(pet.npc_personas or {}), len(PROBES),
             (len(pet.npc_personas or {}) + 1) * len(PROBES)))

    # ---- 预热：把 7B 权重真的读进内存（否则第一问是冷启动，不是人设问题）----
    def warmup():
        body = json.dumps({'model': cfg_model, 'prompt': u'hi', 'stream': False,
                           'keep_alive': '30m',
                           'options': {'num_predict': 1}}).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:11434/api/generate', data=body,
            headers={'Content-Type': 'application/json'})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as fh:
                fh.read()
            return time.time() - t0
        except Exception as e:
            print(u'[note] 预热失败（已忽略）: %s' % e)
            return None

    print(u'[note] 预热（含 7B 权重加载）=%.2fs' % (warmup() or -1))

    def pump(pred, timeout=300.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if pred():
                return True
            time.sleep(0.02)
        app.processEvents()
        return pred()

    # ---- 人设正文（判定用）----
    texts = {}
    names = {}
    for it in (json.load(io.open(os.path.join(PET, 'assets', 'npc',
                                             '_personas.json'),
                                 encoding='utf-8')).get('personas') or []):
        texts[it['id']] = P.persona_text(it['id'], personas=pet.npc_personas) or u''
        names[it['id']] = it.get('name') or it['id']
    # Ralsei 本人（另一条链路，作对照锚点）
    _rp = os.path.join(PET, 'assets', 'ralsei_persona.md')
    texts['ralsei'] = io.open(_rp, encoding='utf-8').read()
    names['ralsei'] = u'Ralsei（本人 · 对照锚点）'

    order = [it['id'] for it in json.load(io.open(
        os.path.join(PET, 'assets', 'npc', '_personas.json'),
        encoding='utf-8'))['personas']] + ['ralsei']

    # ★ 冒烟模式：先只跑 1 人 × 1 问，确认夹具通了再花那 20 分钟。
    #   为什么必须有它：本项目的教训是"夹具不保真 ⇒ 白跑一轮还报假问题"。
    _smoke = '--smoke' in sys.argv
    _probes = PROBES[:1] if _smoke else PROBES
    if _smoke:
        order = order[:1]
        print(u'[note] 冒烟模式：只跑 %r × %d 个探针' % (order, len(_probes)))
    # ★ `--only a,b` 单人诊断：定位"某个人为什么和别的人不一样"（本轮 kris 首字为空就是这个用上的）
    if '--only' in sys.argv:
        _sel = sys.argv[sys.argv.index('--only') + 1].split(',')
        order = [p for p in order if p in _sel]
        print(u'[note] --only 只跑 %r' % (order,))

    # ★ `--quiet` 隔离"后台请求抢流式通道"（本轮诊断用，**不改产品代码**）：
    #   `main.chat_with_ai` 每次入口都会 `_ai_delta_gen += 1` 并把 `_ai_delta_sink`
    #   覆盖成自己的接收方；而 `_on_api_delta` 按世代号拦分片。于是桌宠自己的
    #   事件台词/自主发言（在 pump 期间由 QTimer 触发）会**整段吞掉**我这一问的分片：
    #   症状正是"拿到了回复，但 deltas=0、首字无从测量"。
    #   这里的 shim 只做一件事：**外来调用结束后把世代号与接收方还原成我的**，
    #   使"我的这一问"与"后台那一问"在测量上互不干扰。产品代码一个字节没动。
    _foreign = [0]

    def install_quiet_shim(pet):
        _orig = pet.chat_with_ai

        def _shim(text, on_reply, on_delta=None, **kw):
            if on_delta is not None:        # 我的探针
                return _orig(text, on_reply, on_delta, **kw)
            _foreign[0] += 1
            g0 = getattr(pet, '_ai_delta_gen', 0)
            s0 = getattr(pet, '_ai_delta_sink', None)
            try:
                return _orig(text, on_reply, on_delta, **kw)
            finally:
                pet._ai_delta_gen = g0
                pet._ai_delta_sink = s0
        pet.chat_with_ai = _shim
        return _orig

    if '--quiet' in sys.argv:
        install_quiet_shim(pet)
        print(u'[note] --quiet：已隔离后台请求对流式通道的抢占')

    recs = []
    for pid in order:
        for tag, probe in _probes:
            item = {'id': pid, 'name': names[pid], 'probe_tag': tag,
                    'probe': probe, 'reply': None, 'ttf': None, 'total': None,
                    'n_delta': 0, 'sent': None, 'err': None,
                    # ★ 诊断用：头几个分片的 repr + 是否出现过 None（=判退作废）
                    'pieces': [], 'n_none': 0, 'stream_on': None, 'has_sfn': None,
                    'gen0': None, 'gen1': None}
            try:
                box = []
                cnt = [0]
                TTF[0] = None
                _T0[0] = time.time()
                item['stream_on'] = bool(pet._ai_stream_enabled())
                item['has_sfn'] = bool(callable(getattr(pet.api_client,
                                                        'chat_stream', None)))

                def _on_delta(piece, _c=cnt, _it=item):
                    if piece is None:
                        _it['n_none'] += 1
                        return
                    _c[0] += 1
                    if len(_it['pieces']) < 5:
                        _it['pieces'].append(repr(piece)[:60])
                    if TTF[0] is None:
                        TTF[0] = time.time() - _T0[0]

                def _on_reply(t, _box=box):
                    _box.append((time.time() - _T0[0], t))

                if pid == 'ralsei':
                    item['sent'] = pet.chat_with_ai(probe, _on_reply, _on_delta)
                else:
                    item['sent'] = pet.npc_speak(pid, probe, _on_reply, _on_delta)
                item['gen0'] = getattr(pet, '_ai_delta_gen', None)
                ok = pump(lambda: bool(box))
                # ★ 世代号：产品每次 `chat_with_ai` 入口 +1；`_on_api_delta` 按世代拦分片。
                #   若等待期间**别处**又发起过请求（桌宠自己的定时器），我的分片会被整段丢掉
                #   —— 而 `_on_api_result` 不校验世代，所以"拿到了回复但一个分片都没有"。
                item['gen1'] = getattr(pet, '_ai_delta_gen', None)
                item['n_delta'] = cnt[0]
                if box:
                    item['total'], item['reply'] = box[0]
                    item['ttf'] = TTF[0]
                    # ★ `box` 非空 ≠ 拿到了内容：产品在"请求失败 / 判退后重采样仍无 /
                    #   API 未启用"时会 `on_reply(None)`。这时 `total` 有值而 `ttf=None`
                    #   —— 第一版正是漏了这一步，把 `kris P1` 的失败读成"计时缺失"并崩在格式化。
                    if item['reply'] is None:
                        item['err'] = (u'on_reply(None)：请求失败 / 判退重采样后仍空 / '
                                       u'API 未启用（sent=%r, deltas=%d）'
                                       % (item['sent'], item['n_delta']))
                else:
                    item['err'] = u'无回调（sent=%r, pump=%r）' % (item['sent'], ok)
            except Exception as e:
                item['err'] = repr(e)
            r = item['reply']
            # ★ 守卫必须同时看 ttf —— 第一版只判 `total`，kris 那次 `total` 有值而
            #   `ttf=None`，直接 TypeError 把整个 42 次跑崩在第 4 条（夹具自身的 bug）。
            if item['total'] is not None and item['ttf'] is not None:
                _tm = u'%.1fs/%.1fs' % (item['ttf'], item['total'])
            elif item['total'] is not None:
                _tm = u'(无首字)/%.1fs' % item['total']
            else:
                _tm = u'(无计时)'
            print(u'  [%s] %-8s %-14s deltas=%-4d gen=%-3s>%-3s s=%-5s %s'
                  % (u'OK ' if r else u'-- ', pid, _tm, item['n_delta'],
                     item['gen0'], item['gen1'],
                     u'T' if item['stream_on'] else u'F',
                     (r or (item['err'] or u''))[:70]))
            recs.append(item)

    # ---------------- 判定 ----------------
    #  ★ 判定逻辑抽到模块级 `run_judge` —— 理由是 `--rejudge`：判据本身被修好之后，
    #    要能在**不重跑模型**（不花那 35 分钟、也不重新采样）的前提下复算同一批回复。
    checks, c1_rows, c2_rows, m_fail = run_judge(recs, texts, order, _probes)

    # ---------------- 落盘 ----------------
    ev = {
        'model': cfg_model, 'parameter_size': det.get('parameter_size'),
        'timeout': cfg_to, 'base_url': (pet.api_config or {}).get('base_url'),
        'n_personas': len(order), 'probes': [p[1] for p in _probes],
        'iso_dir': _ISO,
        'quiet_shim': '--quiet' in sys.argv,
        'foreign_calls': _foreign[0],
        'replies': [{'id': r['id'], 'name': r['name'], 'probe_tag': r['probe_tag'],
                     'probe': r['probe'], 'reply': r['reply'],
                     'ttf': r['ttf'], 'total': r['total'], 'err': r['err'],
                     'n_delta': r.get('n_delta'), 'n_none': r.get('n_none'),
                     'gen0': r.get('gen0'), 'gen1': r.get('gen1'),
                     'pieces': r.get('pieces'),
                     'len': (len(r['reply']) if r['reply'] else 0)}
                    for r in recs],
        'checks': checks,
        'c1_cosine': c1_rows, 'c2_unique_gram': c2_rows,
        'mech_fail': m_fail,
        'n_fail': sum(1 for c in checks if not c['ok']),
    }
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    p = os.path.join(OUT, 'personas_live62.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print()
    print(u'== 结果 ==  判定 %d 项，FAIL %d 项' % (len(checks), ev['n_fail']))
    print(u'  证据 -> %s' % p)

    # ---------------- 逐条打印（供人读判断）----------------
    print()
    print(u'=== 全部回复（逐人设逐探针）===')
    for pid in order:
        print(u'\n## %s  (%s)' % (pid, names[pid]))
        for tag, _p in _probes:
            r = got[pid][tag]
            print(u'  Q[%s] %s' % (tag, r['probe']))
            print(u'  A: %s' % (r['reply'] if r['reply'] else
                                (u'<无> ' + (r['err'] or u''))))
    try:
        pet.cleanup_on_exit()
    except Exception:
        pass
    return 0 if ev['n_fail'] == 0 else 1


if __name__ == '__main__':
    # `--rejudge`：只对已落盘的回复复算判据（不联网、不建 QApplication、不花生成时间）
    if '--rejudge' in sys.argv:
        sys.exit(rejudge())
    sys.exit(main())
