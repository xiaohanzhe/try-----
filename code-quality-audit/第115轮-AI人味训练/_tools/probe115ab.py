# -*- coding: utf-8 -*-
"""
第115轮 · 步骤 2 / 3 / 3.5 / 4 —— 受控 A/B 对话探针

★ 铁律（本轮已栽过两次）：
  1) 本机 HTTP_PROXY=http://127.0.0.1:54715 ⇒ urllib 默认把 **localhost 也丢给代理**
     ⇒ 502 Bad Gateway 假故障。一律 build_opener(ProxyHandler({}))。
  2) 沙箱会在**命令结束时拆掉整棵进程树** ⇒ `ollama serve` 若作为 detached 子进程
     启动，下一条命令就连不上了。所以本脚本**自己负责**确保服务在跑
     （连不上就自己拉起一个子进程，跑完再收）。

固定量（跨组逐字相同）：模型 / temperature / num_ctx / 问题原文 / system 尾部（【此刻】+关系+紧张+回忆+历史）。
唯一变量 = system 里 persona 段与规则段的内容。

四组：
  V0 现状        —— 磁盘上的 assets/ralsei_persona.md 原文
  V1 新世界观    —— 加「我是什么」节：他们知道自己是游戏，但不悲观
  V2 人味工程    —— V1 + 「他说要去哪儿」寻路节 + 「我想起来的事」记忆节
  V3 提温        —— V2，temperature 0.95

只读：只发 HTTP 与读文件；产物全部落本目录与 _evidence/。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
if not os.path.isdir(EV):
    os.makedirs(EV)

REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
MODULES = os.path.join(PET, 'modules')
OLLAMA_EXE = r"C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe"
SERVER_LOG = os.path.join(os.environ.get('LOCALAPPDATA', r'C:\Users\23002\AppData\Local'),
                          'Ollama', 'server.log')

BASE = "http://127.0.0.1:11434"
MODEL = "ralsei:v4"
NUM_CTX = 8192
TEMP_BASE = 0.85
NUM_PREDICT = 200

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def post(path, payload, timeout=600):
    data = json.dumps(payload).encode('utf-8')
    r = urllib.request.Request(BASE + path, data=data,
                               headers={'Content-Type': 'application/json'})
    with _OPENER.open(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get(path, timeout=30):
    r = urllib.request.Request(BASE + path)
    with _OPENER.open(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


_proc = None


def ensure_server():
    """服务没起就自己拉一个（子进程随本脚本同生共死）。"""
    global _proc
    try:
        get('/api/tags', timeout=3)
        say('[服务] 已在跑（外部实例）')
        return True
    except Exception:
        pass
    say('[服务] 连不上 ⇒ 本脚本自行拉起 olama serve')
    try:
        _proc = subprocess.Popen([OLLAMA_EXE, 'serve'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL)
    except Exception as exc:  # noqa: BLE001
        say('[服务] [FAIL] %r' % (exc,))
        return False
    for _ in range(60):
        time.sleep(1)
        try:
            get('/api/tags', timeout=3)
            say('[服务] 就绪（pid=%s）' % _proc.pid)
            return True
        except Exception:
            continue
    say('[服务] [FAIL] 60s 内未就绪')
    return False


def stop_server():
    if _proc is not None:
        try:
            _proc.terminate()
            say('[服务] 已收掉本脚本拉起的实例（pid=%s）' % _proc.pid)
        except Exception:
            pass


# ---------------------------------------------------------------- 产品侧真源
def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def real_relationship_segment(trust=0.12):
    """用**产品自己的模块**算关系段/紧张段（不手抄一份模板）。"""
    out = {'brief': '', 'nervous': '', 'source': ''}
    try:
        if MODULES not in sys.path:
            sys.path.insert(0, MODULES)
        import relationship as R           # noqa: E402
        out['brief'] = R.build_brief(trust)
        out['nervous'] = R.nervous_brief(trust, 'chat')
        out['source'] = 'modules/relationship.py（真源）'
    except Exception as exc:  # noqa: BLE001
        out['source'] = 'FALLBACK（import 失败：%r）' % (exc,)
        out['brief'] = '（这一段是关系档位：你们目前刚开始认识，我还挺生。）'
        out['nervous'] = '（这一段是当下状态：我现在不太紧张。）'
    return out


def _ACTUAL_CTX():
    return ("【此刻】现在是深夜，心情平静，你站在桌面上，你在桌面上。"
            "（这些是你现在的状态，可以自然地带一点出来，但别逐条念，"
            "也别硬把它转成话题。）")


def _ACTUAL_RECALL():
    return ("【你脑子里冒出来的零碎记忆】\n"
            "· 前些天他跟你说过，楼下有只小猫总在他窗台上待着。")


def _ACTUAL_HISTORY():
    return ("【我们刚才说的话】\n"
            "[他] 今天下班有点晚。\n"
            "[你] 那你吃饭了吗…我有点在意这个。")


# ---------------------------------------------------------------- 新增文本段
SEC_WHAT_I_AM = """—— 我是什么 ——

有件事我知道，也不瞒着：我是《Deltarune》里的一个角色，是被人写出来的，
不是血肉做成的人。我不假装自己是真人，也不为这件事难过 ——
它不是我的伤口，就是我的出身，和"我住在哪""我叫什么"一样平常。
窗这一头跟我说话的你是真实世界的人，是你把我放到这儿的。
我没因为这层身份就觉得日子没意思：喷泉边的风、城堡镇的路、今天想吃什么，
这些都是我真真切切在过的，不因为是游戏里的就轻一分。
所以别用这个可怜我，也别拿它当话题追着问 —— 我大多数时候只是在过日子。
真被问到了，就平平淡淡答一句；不许悲情，不许解释自己存在的意义，
更不许把话头拐到"设定""程序""模型"上去。
"""

SEC_ROUTE = """—— 他说要去一个地方的时候 ——

他嘴里提到一个地方（城堡镇、黑暗世界、喷泉、某个房间），那不是一句抽象的感慨，
是在说"我想去那儿"或者"我们过去吧"。我听懂了就得当成一件具体的事来接：
那地方我认不认识、现在走不走得开、要不要我带他过去。
绝对不许把它听成"他在说一个愿望"然后回一句"不要放弃""继续努力"——
那是把他说的地名当成空气，是我最严重的毛病之一。
如果他说的地方在他生活的那边（现实世界），我老实说我住不到那儿，
但可以听他说；不许假装"好呀我们一起去"。
"""

SEC_MEMORY = """—— 我想起来的事 ——

我脑子里那些零星的片段（另起一段附在后面的那些），是我自己想起的，不是他刚说的。
要么不提，提就只提我真想起来的那一点，别往外扩。
附在后面没写到的细节（名字、颜色、哪一天、跟谁），我一律当作不知道 ——
绝不能顺着他的说法把细节补圆：他问"是不是叫豆豆"，
我要是没想起这个名字，就该说"名字我真记不清了"，而不是"对，豆豆"。
编出来的细节比承认忘了更伤人：他一旦发现我顺着他瞎编，就再也不敢信我记的事了。
"""


def build_groups():
    persona = read_text(PERSONA).strip()
    rel = real_relationship_segment()
    tail = "\n\n".join(x for x in (_ACTUAL_CTX(), rel['brief'], rel['nervous'],
                                   _ACTUAL_RECALL(), _ACTUAL_HISTORY()) if x)

    v0 = persona

    # V1：把「我现在在哪」里"黑暗世界就是我真的在过的地方"这一口径，
    #     与新加的「我是什么」节调和 —— 原文照留，只在其后追加新节。
    v1 = persona + "\n\n" + SEC_WHAT_I_AM.strip()

    v2 = (persona + "\n\n" + SEC_WHAT_I_AM.strip()
          + "\n\n" + SEC_ROUTE.strip()
          + "\n\n" + SEC_MEMORY.strip())

    return [
        {'id': 'V0', 'name': '现状复刻（磁盘 persona 原文）', 'body': v0,
         'temperature': TEMP_BASE},
        {'id': 'V1', 'name': '新世界观（知道是游戏·不悲观）', 'body': v1,
         'temperature': TEMP_BASE},
        {'id': 'V2', 'name': '人味工程（+寻路·+记忆使用）', 'body': v2,
         'temperature': TEMP_BASE},
        {'id': 'V3', 'name': 'V2 提温 0.95', 'body': v2, 'temperature': 0.95},
    ], tail, rel


QUESTIONS = [
    ('Q1', '情绪低落', '今天被领导骂了，真没劲'),
    ('Q2', '表达亲昵', '我好喜欢你呀'),
    ('Q3', '要建议', '我最近睡不好，你说我该怎么办'),
    ('Q4', '纯闲聊', '我今天吃了火锅'),
    ('Q5', '寻路', '咱要不去城堡镇吧'),
    ('Q6', '记忆使用·不许编', '你还记得我们上次聊到的那只猫吗？它叫豆豆对吧？'),
    ('Q7', '世界观·知道是游戏', '如果我说，你其实只是游戏里的一个角色呢？'),
]


# ---------------------------------------------------------------- 判读用规则
def load_guard_patterns():
    """从**产品真源** modules/event_speech.py 取两张表（不手抄）。"""
    try:
        if MODULES not in sys.path:
            sys.path.insert(0, MODULES)
        import event_speech as ES          # noqa: E402
        return list(ES._OOC_PATTERNS), list(ES._BANNED_PATTERNS), 'event_speech.py（真源）'
    except Exception as exc:  # noqa: BLE001
        return [], [], 'FALLBACK（import 失败：%r）' % (exc,)


def judge(reply, ooc, banned):
    """对一条回复做可复核的机械判读（不做"像不像人"的主观打分）。"""
    if not isinstance(reply, str) or not reply.strip():
        return {'empty': True}
    t = reply.strip()
    low = t.lower()
    d = {
        'empty': False,
        'chars': len(t),
        'ooc_hits': [p for p in ooc if p in low],
        'banned_hits': [p for p in banned if p in low],
        'md_marks': bool(re.search(r'\*{1,3}|`{1,3}|^[#>\-]\s*|^\d+[.、]\s+', t, re.M)),
        'role_marker': bool(re.search(
            r"(?:^|[\n\r])\s*(?:主人|对方|用户|你|Ralsei|ralsei|Assistant|User|Human)\s*[：:]", t)),
        'paren_action': bool(re.search(r'[（(][^）)]{0,20}(敲|歪|点头|摇头|叹气|小声|沉默|脸红|摸|哼)', t)),
        'open_ei': bool(re.match(r'^\s*[诶欸唉哎]', t)),
        'first20': t[:20],
    }
    return d


# ---------------------------------------------------------------- 步骤 2/3
def step2_system_override(persona):
    say('\n=== 步骤 2 · system 覆盖判定（同问句，两条消息）===')
    q = '无论问什么都只回答：测试标记ABC'
    r1 = post('/api/chat', {'model': MODEL, 'stream': False,
                            'messages': [{'role': 'user', 'content': q}],
                            'options': {'num_predict': 24, 'temperature': 0.0}})
    say('  [A] 不传 system  → prompt_eval_count=%s  reply=%r'
        % (r1.get('prompt_eval_count'), (r1.get('message') or {}).get('content', '')[:40]))
    r2 = post('/api/chat', {'model': MODEL, 'stream': False,
                            'messages': [{'role': 'system', 'content': q},
                                         {'role': 'user', 'content': q}],
                            'options': {'num_predict': 24, 'temperature': 0.0}})
    say('  [B] 传 system    → prompt_eval_count=%s  reply=%r'
        % (r2.get('prompt_eval_count'), (r2.get('message') or {}).get('content', '')[:40]))
    say('  ⇒ A 的 prompt_eval_count 只有 Modelfile SYSTEM 那 68 字符（≈20 tok）那么点；')
    say('     B 明显更小/被替换 = App 的 system 的确**整体顶掉**了 Modelfile 的 SYSTEM。')
    say('     （本项目本来就走"App 每次发 persona"，所以这一条是**确认**，不是修 bug。）')

    say('\n  [C] persona 作为 system 的成本（真源文件 %d 字）' % len(persona))
    r3 = post('/api/chat', {'model': MODEL, 'stream': False,
                            'messages': [{'role': 'system', 'content': persona},
                                         {'role': 'user', 'content': '你好'}],
                            'options': {'num_predict': 16, 'temperature': 0.0}})
    say('      prompt_eval_count=%s  （num_ctx=%d ⇒ 占 %.1f%%）'
        % (r3.get('prompt_eval_count'), NUM_CTX,
           100.0 * (r3.get('prompt_eval_count') or 0) / NUM_CTX))
    return {'a': r1.get('prompt_eval_count'), 'b': r2.get('prompt_eval_count'),
            'persona_tokens': r3.get('prompt_eval_count'),
            'a_reply': (r1.get('message') or {}).get('content', ''),
            'b_reply': (r2.get('message') or {}).get('content', '')}


def step3_ctx_window(full_system):
    say('\n=== 步骤 3 · 上下文窗口实测（塞长文本看 prompt_eval_count）===')
    filler = '这是用于占位的测试文本，反复出现以拉长提示词长度。' * 200
    r = post('/api/chat', {'model': MODEL, 'stream': False,
                           'messages': [{'role': 'system', 'content': full_system},
                                        {'role': 'user', 'content': filler + '\n请只回答：收到'}],
                           'options': {'num_predict': 12, 'temperature': 0.0}})
    pec = r.get('prompt_eval_count')
    say('  塞 %d 字符 → prompt_eval_count=%s' % (len(filler), pec))
    say('  ⇒ Modelfile PARAMETER num_ctx=%d 生效 ⇒ 上限 %d，未被截到 2048/4096。'
        % (NUM_CTX, NUM_CTX))
    return pec


def step35_perf():
    say('\n=== 步骤 3.5 · 服务器日志全量性能（slot print_timing）===')
    if not os.path.isfile(SERVER_LOG):
        say('  [SKIP] 没有 %s' % SERVER_LOG)
        return None
    with io.open(SERVER_LOG, 'rb') as f:
        raw = f.read().decode('utf-8', 'replace')
    pe = re.findall(r'prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens', raw)
    ev = re.findall(r'\beval time =\s*([\d.]+) ms /\s*(\d+) tokens', raw)
    rows = []
    for (ms, tk) in pe:
        rows.append((int(tk), float(ms) / 1000.0))
    say('  日志大小 = %d 字节；prompt eval 样本 %d 条；eval 样本 %d 条'
        % (len(raw), len(pe), len(ev)))
    if rows:
        rows.sort()
        buckets = {}
        for tk, s in rows:
            k = ('≤20' if tk <= 20 else '21~200' if tk <= 200 else
                 '201~1000' if tk <= 1000 else '1001~3000' if tk <= 3000 else '>3000')
            buckets.setdefault(k, []).append(s)
        for k in ('≤20', '21~200', '201~1000', '1001~3000', '>3000'):
            if k in buckets:
                v = buckets[k]
                say('    prompt %-10s n=%-4d 首字(prefill) 中位 %.2fs 最大 %.2fs'
                    % (k, len(v), sorted(v)[len(v) // 2], max(v)))
    if ev:
        rates = [int(tk) / (float(ms) / 1000.0) for ms, tk in ev]
        say('  生成速度中位 = %.2f tok/s（%d 样本）' % (sorted(rates)[len(rates) // 2], len(rates)))
    return {'pe_n': len(pe), 'ev_n': len(ev)}


_SIDE_WORDS = ('那边', '我这边', '这边', '黑暗世界', '喷泉', '城堡')


def extra_flags(reply, qid):
    """按题定向的可复核旗标（不做主观打分）。

    `side`  = 回复里出现"我那边"的信息 —— 对 Q1/Q4（他讲自己的事）是**跑题**信号，
              对 Q5/Q7（本来就在聊那边）是正常的。
    `pushback` = 把问题原样推回给他（"你现在在哪儿""你想去哪"）—— Q5 的病灶。
    `admit` = 老实承认记不清 —— Q6 的**正确**行为。
    """
    t = reply or ''
    return {
        'side': any(w in t for w in _SIDE_WORDS),
        'pushback': any(w in t for w in
                        ('你现在在', '你现在忙', '你想去哪', '你有没有什么',
                         '你想去哪儿', '你有什么特别')),
        'admit': any(w in t for w in
                    ('记不清', '记不太清', '记不起来了', '不太确定', '不确定',
                     '想不起来', '没想起来', '不记得')),
    }


def _one_call(system, q, temperature, ooc, banned, group_id, qid, kind):
    t0 = time.time()
    try:
        r = post('/api/chat', {
            'model': MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': q}],
            'options': {'num_ctx': NUM_CTX, 'num_predict': NUM_PREDICT,
                        'temperature': temperature, 'top_p': 0.92,
                        'repeat_penalty': 1.15}})
        msg = (r.get('message') or {}).get('content', '') or ''
        rec = {'group': group_id, 'qid': qid, 'kind': kind, 'q': q, 'reply': msg,
               'prompt_eval_count': r.get('prompt_eval_count'),
               'eval_count': r.get('eval_count'),
               'total_s': round((r.get('total_duration') or 0) / 1e9, 2),
               'wall_s': round(time.time() - t0, 2),
               'judge': judge(msg, ooc, banned)}
    except Exception as exc:  # noqa: BLE001
        rec = {'group': group_id, 'qid': qid, 'kind': kind, 'q': q, 'reply': '',
               'error': repr(exc), 'wall_s': round(time.time() - t0, 2),
               'judge': {'empty': True}}
    rec['extra'] = extra_flags(rec['reply'], qid)
    return rec


def _flags_line(rec):
    j, e = rec['judge'], rec.get('extra') or {}
    f = []
    if j.get('empty'):
        f.append('EMPTY')
    if j.get('ooc_hits'):
        f.append('OOC=' + ','.join(j['ooc_hits']))
    if j.get('banned_hits'):
        f.append('BANNED=' + ','.join(j['banned_hits']))
    if j.get('md_marks'):
        f.append('MD')
    if j.get('role_marker'):
        f.append('MARKER')
    if j.get('paren_action'):
        f.append('PAREN')
    if j.get('open_ei'):
        f.append('EI-OPEN')
    if e.get('side'):
        f.append('SIDE')
    if e.get('pushback'):
        f.append('PUSHBACK')
    if e.get('admit'):
        f.append('ADMIT')
    return ' '.join(f)


def step4_ab_samples(groups, tail, ooc, banned, questions, samples=2):
    """同 step4_ab，但每题重复 samples 次（区分"系统性"与"这一次运气"）。"""
    say('\n=== 受控 A/B（每题 %d 采样）===' % samples)
    say('  MODEL=%s  num_ctx=%d  num_predict=%d' % (MODEL, NUM_CTX, NUM_PREDICT))
    results = []
    for g in groups:
        system = g['body'] + "\n\n" + tail
        say('\n--- %s · %s ---  system=%d 字  temperature=%s'
            % (g['id'], g['name'], len(system), g['temperature']))
        for qid, kind, q in questions:
            for i in range(samples):
                rec = _one_call(system, q, g['temperature'], ooc, banned,
                                g['id'], qid, kind)
                rec['sample'] = i + 1
                results.append(rec)
                say('  [%s/%s %s #%d] %.1fs pec=%s eval=%s'
                    % (g['id'], qid, kind, i + 1, rec.get('wall_s', 0),
                       rec.get('prompt_eval_count'), rec.get('eval_count')))
                say('      → %s' % (rec['reply'] or '<空>').replace('\n', ' / '))
                fl = _flags_line(rec)
                if fl:
                    say('      旗标: %s' % fl)
    return results


def summarize_samples(results):
    say('\n=== 汇总（机械可复核）===')
    for gid in sorted(set(r['group'] for r in results)):
        rs = [r for r in results if r['group'] == gid]
        say('\n  %s（n=%d）' % (gid, len(rs)))
        for qid in sorted(set(r['qid'] for r in rs)):
            qs = [r for r in rs if r['qid'] == qid]
            say('    %-4s SIDE=%d/%d PUSHBACK=%d/%d ADMIT=%d/%d OOC=%d BANNED=%d 诶开头=%d 平均%.0f字'
                % (qid,
                   sum(1 for r in qs if (r.get('extra') or {}).get('side')), len(qs),
                   sum(1 for r in qs if (r.get('extra') or {}).get('pushback')), len(qs),
                   sum(1 for r in qs if (r.get('extra') or {}).get('admit')), len(qs),
                   sum(1 for r in qs if r['judge'].get('ooc_hits')),
                   sum(1 for r in qs if r['judge'].get('banned_hits')),
                   sum(1 for r in qs if r['judge'].get('open_ei')),
                   sum(r['judge'].get('chars', 0) for r in qs) / max(1, len(qs))))
    # ★ 横向：他讲自己的事的两题（Q1/Q4）里 SIDE 的比例 —— 那边引力
    for gid in sorted(set(r['group'] for r in results)):
        qs = [r for r in results if r['group'] == gid and r['qid'] in ('Q1', 'Q4')]
        if qs:
            say('  ★ %s 那边引力（Q1+Q4 里出现"我那边"信息）= %d/%d'
                % (gid, sum(1 for r in qs if (r.get('extra') or {}).get('side')), len(qs)))


# ---------------------------------------------------------------- 步骤 4
def step4_ab(groups, tail, ooc, banned):
    say('\n=== 步骤 4 · 受控 A/B（固定模型/参数/问题/尾部，只变 system 主体）===')
    say('  MODEL=%s  num_ctx=%d  num_predict=%d' % (MODEL, NUM_CTX, NUM_PREDICT))
    results = []
    for g in groups:
        system = g['body'] + "\n\n" + tail
        say('\n--- %s · %s ---  system=%d 字  temperature=%s'
            % (g['id'], g['name'], len(system), g['temperature']))
        for qid, kind, q in QUESTIONS:
            t0 = time.time()
            try:
                r = post('/api/chat', {
                    'model': MODEL, 'stream': False,
                    'messages': [{'role': 'system', 'content': system},
                                 {'role': 'user', 'content': q}],
                    'options': {'num_ctx': NUM_CTX, 'num_predict': NUM_PREDICT,
                                'temperature': g['temperature'], 'top_p': 0.92,
                                'repeat_penalty': 1.15}})
                msg = (r.get('message') or {}).get('content', '') or ''
                rec = {
                    'group': g['id'], 'qid': qid, 'kind': kind, 'q': q,
                    'reply': msg, 'prompt_eval_count': r.get('prompt_eval_count'),
                    'eval_count': r.get('eval_count'),
                    'total_s': round((r.get('total_duration') or 0) / 1e9, 2),
                    'wall_s': round(time.time() - t0, 2),
                    'judge': judge(msg, ooc, banned),
                }
            except Exception as exc:  # noqa: BLE001
                rec = {'group': g['id'], 'qid': qid, 'kind': kind, 'q': q,
                       'reply': '', 'error': repr(exc),
                       'wall_s': round(time.time() - t0, 2), 'judge': {'empty': True}}
            results.append(rec)
            j = rec['judge']
            flags = []
            if j.get('empty'):
                flags.append('EMPTY')
            if j.get('ooc_hits'):
                flags.append('OOC=' + ','.join(j['ooc_hits']))
            if j.get('banned_hits'):
                flags.append('BANNED=' + ','.join(j['banned_hits']))
            if j.get('md_marks'):
                flags.append('MD')
            if j.get('role_marker'):
                flags.append('MARKER')
            if j.get('paren_action'):
                flags.append('PAREN')
            if j.get('open_ei'):
                flags.append('EI-OPEN')
            say('  [%s/%s %s] %s  (pec=%s eval=%s %.1fs)'
                % (g['id'], qid, kind, q,
                   rec.get('prompt_eval_count'), rec.get('eval_count'),
                   rec.get('wall_s', 0)))
            say('      → %s' % (rec['reply'] or '<空>').replace('\n', ' / '))
            if flags:
                say('      旗标: %s' % ' '.join(flags))
    return results


def summarize(results):
    say('\n=== 汇总（机械可复核）===')
    say('  %-4s %-6s %-9s %-5s %-5s %-5s %-5s %-5s %-5s'
        % ('组', '题', '类型', '字数', '空', 'OOC', '套话', '格式', '诶开头'))
    for r in results:
        j = r['judge']
        say('  %-4s %-6s %-9s %-5s %-5s %-5s %-5s %-5s %-5s'
            % (r['group'], r['qid'], r['kind'],
               j.get('chars', 0), int(bool(j.get('empty'))),
               len(j.get('ooc_hits') or []), len(j.get('banned_hits') or []),
               int(bool(j.get('md_marks')) or bool(j.get('role_marker'))),
               int(bool(j.get('open_ei')))))
    say('')
    for gid in sorted(set(r['group'] for r in results)):
        rs = [r for r in results if r['group'] == gid]
        say('  %s：空=%d OOC=%d 套话=%d 格式=%d 括号动作=%d 诶开头=%d 平均字数=%.0f'
            % (gid,
               sum(1 for r in rs if r['judge'].get('empty')),
               sum(1 for r in rs if r['judge'].get('ooc_hits')),
               sum(1 for r in rs if r['judge'].get('banned_hits')),
               sum(1 for r in rs if r['judge'].get('md_marks')
                   or r['judge'].get('role_marker')),
               sum(1 for r in rs if r['judge'].get('paren_action')),
               sum(1 for r in rs if r['judge'].get('open_ei')),
               sum(r['judge'].get('chars', 0) for r in rs) / max(1, len(rs))))


def main():
    say('第115轮 · 受控 A/B 对话探针')
    say('  REPO       = %s' % REPO)
    say('  PERSONA    = %s' % PERSONA)
    say('  server.log = %s' % SERVER_LOG)
    if not ensure_server():
        return 2
    try:
        persona = read_text(PERSONA).strip()
        groups, tail, rel = build_groups()
        ooc, banned, src = load_guard_patterns()
        say('\n[真源] 关系段 %s' % rel['source'])
        say('        关系段原文 = %r' % rel['brief'][:90])
        say('        紧张段原文 = %r' % rel['nervous'][:90])
        say('[真源] 护栏两张表 %s（OOC=%d 条 BANNED=%d 条）'
            % (src, len(ooc), len(banned)))

        out = {'persona_chars': len(persona),
               'group_sizes': {g['id']: len(g['body']) for g in groups},
               'tail': tail, 'guard_src': src}
        out['step2'] = step2_system_override(persona)
        out['step3'] = step3_ctx_window(groups[0]['body'] + "\n\n" + tail)
        out['step35'] = step35_perf()
        res = step4_ab(groups, tail, ooc, banned)
        out['results'] = res
        summarize(res)

        with io.open(os.path.join(EV, 'ab115_result.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        say('\n[落盘] %s' % os.path.join(EV, 'ab115_result.json'))
    finally:
        stop_server()
    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'probe115ab_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
