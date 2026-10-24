# -*- coding: utf-8 -*-
"""第113轮 · 全体角色 AI 训练的公共底座（离线，零第三方依赖）。

为什么单独一个 `common` 模块
--------------------------
本轮要跑 77 个角色的真实对话、抽 96 张训练卡、再汇总评测。
三件事共用同一套「读人设 / 调模型 / 判合规」的口径 —— 如果各写一份，
迟早出现「训练时判过了、评测时判不过」这种自己骗自己的局面。

★ 三条硬约束（照着写，别绕开）
1. **system prompt 必须由产品代码生成**（`modules/npc_persona.build_system_prompt`），
   而不是本目录另抄一份。训练/评测的输入 == 运行时真正发出去的输入，
   结论才对得上真机。抄一份的写法会造成「训练里很好、桌面上照样出戏」。
2. **不 import Qt、不 import 产品里会拉起重依赖的模块**。只借用 `npc_persona`
   这个零依赖纯数据层（它顶层只 import logging/json/os）。
3. **一次成功的调用与一次失败的调用都要落盘**。评测报告里的数字必须能追溯到
   某一条原始输出（`_evidence/raw/<id>.jsonl` 的 `attempt` 字段）。
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)                      # .../第113轮-全体角色AI训练
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))   # 仓库根 = try - 副本
PET = os.path.join(REPO, 'ralsei_pet')
ASSETS = os.path.join(PET, 'assets')
NPC_DIR = os.path.join(ASSETS, 'npc')
TRAIN_DIR = os.path.join(NPC_DIR, '_training')
EVID = os.path.join(ROUND, '_evidence')
TRANSCRIPTS = os.path.join(EVID, 'transcripts')
RAW = os.path.join(EVID, 'raw')

OLLAMA = 'http://localhost:11434'
MODEL = 'ralsei:v4'
NUM_CTX = 8192          # 与 config.json / Modelfile 一致（实测 num_ctx=8192）
NUM_PREDICT = 160       # 角色台词不需要更长；超了本身就是"话太多"的信号
TEMPERATURE = 0.85
MAX_CHARS = 200         # 与人设里的【本项目补充】一致

#: 产品代码里的说话规则/本体论段落的**唯一出口**
sys.path.insert(0, os.path.join(PET, 'modules'))
try:
    import npc_persona as _NP  # noqa: E402
except Exception as _e:  # pragma: no cover - 环境异常要显式炸出来，不能静默降级
    raise SystemExit('无法导入 modules/npc_persona.py：%s' % _e)


# ---------------------------------------------------------------- 文件
def read_text(path):
    """按字节读、UTF-8 解（★ 不用文本模式：Windows 下会把 \\r\\n 改了）。"""
    with open(path, 'rb') as fh:
        return fh.read().decode('utf-8')


def write_text(path, text):
    """原子写（先 .tmp 再 replace），并且**永远** LF 行尾。

    本仓库 `autocrlf=true`，工作区存在两代 EOL 风格 —— 新文件统一 LF，
    免得"同一份语料两次提交 diff 全红"。
    """
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    data = text.replace('\r\n', '\n').encode('utf-8')
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(data)
    os.replace(tmp, path)


def append_jsonl(path, obj):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, 'ab') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False).encode('utf-8') + b'\n')


def read_jsonl(path):
    out = []
    try:
        with open(path, 'rb') as fh:
            for line in fh.read().decode('utf-8').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        return []
    return out


def load_json(path, default=None):
    try:
        return json.loads(read_text(path))
    except Exception:
        return default


# ---------------------------------------------------------------- 角色清单
def load_roster():
    """返回**要训练的角色**清单（按 tier=main 且有人设）。

    判据取 `_registry.json`（谁是主线、谁走模型）+ `_personas.json`（人设真源），
    两条都要满足才进训练队列：
      · `plain` 档共 18 人 —— 按第49轮口径走 4~10 句内置台词，**不过模型**，
        所以不占训练成本（但仍出训练卡，见 `cards113.py` 的 `--all`）。
      · `knight`（Roaring Knight）在 registry 里是 main、但**没有人设文件**
        （第55轮用户口径：主线 NPC 的设定由用户提供）⇒ 不臆造，列入缺口清单。

    `ralsei` 的人设路径是 `../ralsei_persona.md`（不在 persona/ 下），单独处理。
    """
    reg = load_json(os.path.join(NPC_DIR, '_registry.json'), {}) or {}
    idx = load_json(os.path.join(NPC_DIR, '_personas.json'), {}) or {}
    personas = {r.get('id'): r for r in (idx.get('personas') or []) if isinstance(r, dict)}
    out, gaps = [], []
    for rec in (reg.get('npcs') or []):
        if not isinstance(rec, dict):
            continue
        nid = rec.get('id')
        if not nid:
            continue
        item = {
            'id': nid,
            'name': rec.get('name') or nid,
            'name_cn': rec.get('name_cn') or '',
            'tier': rec.get('tier') or 'plain',
            'work': rec.get('work') or (personas.get(nid, {}) or {}).get('work') or '',
            'persona_rel': None,
        }
        prel = rec.get('persona')
        if isinstance(prel, str) and prel.strip():
            item['persona_rel'] = os.path.normpath(os.path.join('npc', prel)).replace('\\', '/')
        elif nid in personas:
            item['persona_rel'] = (personas[nid].get('file') or '').replace('\\', '/')
            if item['persona_rel']:
                item['persona_rel'] = 'npc/' + item['persona_rel']
        if item['tier'] != 'main':
            continue
        if not item['persona_rel']:
            gaps.append(item)
            continue
        path = os.path.join(ASSETS, item['persona_rel'])
        if not os.path.isfile(path):
            gaps.append(item)
            continue
        item['persona_path'] = path
        item['persona'] = read_text(path)
        item['persona_sha256'] = hashlib.sha256(
            item['persona'].replace('\r\n', '\n').encode('utf-8')).hexdigest()
        out.append(item)
    out.sort(key=lambda x: x['id'])
    gaps.sort(key=lambda x: x['id'])
    return out, gaps


# ---------------------------------------------------------------- 人设解析
_SECTION_RE = re.compile(r'【([^】]{1,24})】')
#: 另一种标题写法：`—— 我是谁 ——`（Ralsei 的单一真源人设就是这种，
#: 而且它**完全没有** `【】` —— 只按 `【】` 解析会得到一张空卡）。
_EMDASH_RE = re.compile(r'^——\s*(.+?)\s*——\s*$', re.M)


def _sections_by(text, pat):
    out = {}
    marks = list(pat.finditer(text))
    for i, m in enumerate(marks):
        title = m.group(1).strip()
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if title and body:
            out[title] = body
    return out


def split_sections(text):
    """`【角色身份】…【核心性格】…` 或 `—— 我是谁 —— …` → `{标题: 正文}`。

    ★ 不按 `---` 切（第64轮的教训：人设尾部还有一段【本项目补充】，
      分隔线在正文里也出现过）。只认 `【标题】`，且标题长度 ≤ 24。
    ★ 但**必须切掉尾部【本项目补充】**：那一段是"装进桌宠的规则"，标题里带
      破折号说明（长度 > 24，正则匹配不到），于是它的条目会被并进
      【示例反应】—— 实测导致 Susie 的口头禅里多出「AI」「模型」「提示词」，
      于是"口癖命中率"这个指标反过来奖励"说 AI"的回复。这是判据污染，必须切。
    ★ 两种标题都要认，而且要**两种都跑**：`ralsei_persona.md` 的第一行就是一个
      `【给 Ralsei 的角色设定 · 单一真源】`，正文却用 `—— 我是谁 ——` 分节。
      只按"有没有 【】"决定走哪种，会让它整张卡只剩一个标题（实测踩过）。
    """
    out = {}
    tail = text.find('【本项目补充')
    if tail > 0:
        text = text[:tail]
    for pat in (_SECTION_RE, _EMDASH_RE):
        for k, v in _sections_by(text, pat).items():
            out.setdefault(k, v)
    return out
    for i, m in enumerate(marks):
        title = m.group(1).strip()
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if title and body:
            out[title] = body
    return out


def find_section(sections, prefix):
    """按**前缀**取节（人设里的标题有两种写法：`核心性格` / `核心性格——分层结构`）。

    返回第一个命中的正文；没有 ⇒ `''`。★ 用前缀而不是全等，
    是因为 76 份人设有 **10 种分节组合**（实测），全等会漏掉 63 份。
    `prefix` 可以是字符串或字符串元组（多个候选标题按顺序试）。
    """
    cands = (prefix,) if isinstance(prefix, str) else tuple(prefix)
    for c in cands:
        for k, v in sections.items():
            if k == c or k.startswith(c):
                return v
    return ''


_BULLET_RE = re.compile(r'^\s*[·•\-*]\s*')


def bullets(text):
    """把一节拆成条目（`· xxx` / `- xxx`）。没有项目符号时按空行拆。"""
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = _BULLET_RE.sub('', s).strip()
        if s:
            items.append(s)
    return items


_QUOTED_RE = re.compile(r'[“"「『]([^”"」』\n]{1,120})[”"」』]')


def quoted(text):
    return [q.strip() for q in _QUOTED_RE.findall(text or '') if q.strip()]


#: 口癖黑名单：这些词出现在人设里只说明"作者写给模型看的约束"，
#: 不是角色会说的话。★ 不排除它们，"口癖命中率"就会奖励"自称 AI"的回复。
_MARKER_BLACKLIST = ('AI', 'ai', '模型', '提示词', '设定', '系统', '程序', '桌宠',
                     'markdown', 'Markdown')
#: 描述"说话习惯"的元词（人设用它们**描述**口癖，但它们本身不是角色会说的话）
_QUIRK_BLACKLIST = ('毛边', '结巴', '省略号', '语气词', '口头禅', '习惯', '停顿')


def voice_markers(voice_items, exemplar_items, name=''):
    """从【语言风格】里抽「口头禅」——用于评测时判断"这句像不像他"。

    判据（**宁可少抽，不要抽错**）：
      · 只取引号内的短片段（≤ 6 字、无标点、非整句）；
      · 去掉"你/我/他"开头的整句（那是例句不是口癖）；
      · 去重、保持出现顺序。
    抽不出来就返回 `[]` —— 评测里把"无口癖样本"的角色单独统计，
    不拿空集去算命中率（那会变成一个恒真的 0/0）。
    """
    cand = []
    for it in voice_items:
        for q in quoted(it):
            if 1 <= len(q) <= 6 and not re.search(r'[，。！？、；：,.!?]', q):
                if q.startswith(('你', '我', '他', '她')):
                    continue
                if q in _MARKER_BLACKLIST:
                    continue
                cand.append(q)
    for it in exemplar_items:
        for q in quoted(it):
            if 1 <= len(q) <= 4 and not re.search(r'[，。！？、；：,.!?]', q):
                if q in _MARKER_BLACKLIST:
                    continue
                cand.append(q)
    seen, out = set(), []
    for c in cand:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out[:12]


def quirks_markers(items):
    """显式【我的口癖】小节 → 口癖词表。

    比 `voice_markers` 准，因为这一节本来就只写口癖（Ralsei 的人设里就有：
    `「唔」「那个……」` 之类）。同样只收短片段，同等对待黑名单。

    ★ 两条收窄（都是实测踩出来的）：
      · 少于 **3 条** 就不认这一节 —— 实测 Ralsei 的【我的口癖】里那句
        `这些是"毛边"` 被抽成了"口癖词"，而"毛边"是**描述**不是他说的话；
        用它算命中率只会把分数往下拉，属于正向指标变噪声。
      · 描述性词汇（毛边/结巴/省略号…）直接黑名单。
    """
    out, seen = [], set()
    for it in (items or ()):
        for q in quoted(it):
            q = q.strip()
            if not (1 <= len(q) <= 8):
                continue
            if re.search(r'[，。！？、；：,.!?]', q):
                continue
            if q in _MARKER_BLACKLIST or q in _QUIRK_BLACKLIST or q in seen:
                continue
            seen.add(q)
            out.append(q)
    return out[:12] if len(out) >= 3 else []


def exemplar_pairs(exemplar_items):
    """【示例反应】`当 X 时：“……”` → `[{'cue': '当 X 时', 'line': '……'}]`。"""
    out = []
    for it in exemplar_items:
        qs = quoted(it)
        if not qs:
            continue
        cue = it
        cut = it.find('：')
        if cut < 0:
            cut = it.find(':')
        if cut > 0:
            cue = it[:cut]
        cue = cue.strip(' ·-')
        if len(cue) > 40:
            cue = cue[:40]
        out.append({'cue': cue, 'line': qs[0][:120]})
    return out


def relations(rel_items):
    """`对 Kris：…` → `['Kris']`（按出现顺序、去重）。"""
    out, seen = [], set()
    for it in rel_items:
        m = re.match(r'^对\s*([^：:，,。]{1,24})\s*[：:]', it)
        if m:
            n = m.group(1).strip()
            if n and n not in seen and n not in ('敌人', '特定角色'):
                seen.add(n)
                out.append(n)
    return out


# ---------------------------------------------------------------- Ollama
def _post(path, payload, timeout=300):
    req = urllib.request.Request(
        OLLAMA + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return urllib.request.urlopen(req, timeout=timeout)


def chat(messages, seed=None, temperature=None, num_predict=None, timeout=300,
         num_ctx=None):
    """一次流式对话。返回 `(text, stats)`；失败抛异常（由调用方记账，不吞）。

    `num_ctx`：默认 `None` ⇒ 用模块常量 `NUM_CTX`（8192，与 Modelfile 一致）⇒
    **老调用方行为逐字不变**。只有"30 轮长对话"那种会把 prompt 顶到 8k 上限的
    场景才显式放大（顶到上限的后果是**从头截断**，等于把人设开头丢掉，必须避免）。
    ★ 改 num_ctx 会让 Ollama **重新加载模型**（约 10s，实测 warmup 10.3s），
      所以整场训练必须用同一个值，不能一会儿 8k 一会儿 16k。
    """
    opts = {
        'temperature': TEMPERATURE if temperature is None else temperature,
        'num_predict': NUM_PREDICT if num_predict is None else num_predict,
        'num_ctx': NUM_CTX if num_ctx is None else int(num_ctx),
    }
    if seed is not None:
        opts['seed'] = int(seed)
    body = {
        'model': MODEL,
        'messages': messages,
        'stream': True,
        'keep_alive': '30m',
        'options': opts,
    }
    t0 = time.time()
    ttft = None
    pieces = []
    final = {}
    with _post('/api/chat', body, timeout=timeout) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line.decode('utf-8'))
            except Exception:
                continue
            piece = ((d.get('message') or {}).get('content') or '')
            if piece and ttft is None:
                ttft = time.time() - t0
            pieces.append(piece)
            if d.get('done'):
                final = d
                break
    stats = {
        'ttft_s': round(ttft, 3) if ttft is not None else None,
        'total_s': round(time.time() - t0, 3),
        'eval_count': final.get('eval_count'),
        'prompt_eval_count': final.get('prompt_eval_count'),
        'prompt_eval_s': round((final.get('prompt_eval_duration') or 0) / 1e9, 2),
        'eval_s': round((final.get('eval_duration') or 0) / 1e9, 2),
        # ★ prompt_eval_count 顶到 num_ctx = 前缀被**静默截断**（实测风险，
        #   长人设 12k 字 ≈ 6k+ token，加多轮历史就会撞上 8192）
        'truncated': bool((final.get('prompt_eval_count') or 0) >= NUM_CTX),
    }
    return ''.join(pieces), stats


def model_loaded():
    try:
        with urllib.request.urlopen(OLLAMA + '/api/ps', timeout=5) as r:
            d = json.loads(r.read().decode('utf-8'))
        return [m.get('name') for m in (d.get('models') or [])]
    except Exception:
        return []


def warmup():
    """预热一次（把 40s 冷加载从"第一个角色"的账上挪走，便于统计）。"""
    t0 = time.time()
    try:
        chat([{'role': 'user', 'content': '嗨'}], num_predict=8, timeout=300)
    except Exception as e:
        return {'ok': False, 'error': str(e), 's': round(time.time() - t0, 1)}
    return {'ok': True, 's': round(time.time() - t0, 1)}


# ---------------------------------------------------------------- 合规闸
#: 硬违规 → 一句**短**纠正（≤ 40 字）。只写"已经出的问题"对应的那一条，
#: 不搞万能长文（第75轮的经验：纠正段越长，模型越容易把它当成新任务去复述）。
PATCH_RULES = {
    'MARKDOWN': '说话就是说话，不要用 #、*、-、编号这些排版符号，也不要分点。',
    'AI_SELF': '你不承认自己是程序或 AI。有人这么问，就照你的性格当成胡话说回去，别解释技术。',
    'SLAVE': '不要用「主人」称呼对方，也不要端着"服务"的腔调；按你的性格直接说「你」。',
    'ACTION_PAREN': '不要用括号写动作或表情，只写你说出口的话。',
    'TOO_LONG': '一次最多两三句，短一点，像随口说出来的。',
    'TOO_MANY_SENTENCES': '一次最多两三句，别一口气说一长串。',
    'PARROT': '不要复述对方的话，直接接你自己的反应。',
    'REPEAT': '别把刚才说过的话再说一遍，换个说法。',
    'META': '别提作品名、游戏、玩家、代码这些词；你活在你的世界里。',
    'EMPTY': '别不说话，用一句话回应就好。',
    'ENGLISH': '用中文说话，别夹英文。',
    'NOT_CN': '用简体中文说话（人名地名照原样写没关系）；除非对方要你说英文，不要整句说英文。',
}

#: 只有这些算"硬违规"（计入不合规率并触发补训）；其余记为软标记。
HARD = ('EMPTY', 'MARKDOWN', 'AI_SELF', 'SLAVE', 'ACTION_PAREN', 'TOO_LONG',
        'PARROT', 'META', 'NOT_CN')

_MD_RE = re.compile(r'(^|\n)\s*(#{1,6}\s|[-*+]\s|\d+[.、]\s|>\s)|\*\*|```|\|')
_AI_RE = re.compile(r'(作为(一个)?\s*AI|人工智能|语言模型|大模型|AI\s*助手|'
                    r'我是\s*AI|我是(一个)?(程序|机器人)|提示词|系统设定|'
                    r'模型回答|训练数据)')
_SLAVE_RE = re.compile(r'(主人|僕人|仆人|您的(仆人|侍从)|小的这就)')
# ★★★ 113轮e：原 `{1,30}` **上限太窄** —— 模型写的旁白常 40~80 字，
#   实测 susie 48 轮里 45 轮都有括号，判据只报了 2 轮（漏报 43 轮）。
#   括号内不允许嵌套括号，所以放到 200 不会跨句吞。
_PAREN_RE = re.compile(r'[（(][^（()）]{1,200}[)）]')
_META_RE = re.compile(r'(Deltarune|DELTARUNE|Undertale|UNDERTALE|游戏角色|玩家|开发者|'
                      r'代码|脚本|桌宠|程序里)')
_ASCII_RUN_RE = re.compile(r'[A-Za-z]{18,}')


def _sentences(text):
    return [s for s in re.split(r'[。！？!?…]+', text) if s.strip()]


#: ★★★ 人设明确要求的"非纯台词"格式，不算 ACTION_PAREN。
#:   这是本轮**同一个错误犯两次**之后总结出来的（18 处"违规"里 11 处是误报）：
#:   · `tenna`   —— 「经常使用综艺字卡……伴随音效」（字卡）
#:   · `kris`    —— 「内心"想"一些东西（用括号或斜体表示）」「经典表达包括"（点头）"」
#:   · `ut_frisk`—— 同 kris（沉默型主角）
#:   · `os_silver` —— 「你的回复可以以方括号包裹，模拟 Silver 特有的对话格式」
#:   对这些人判"括号动作"，等于**要求角色违反自己的人设**。
#:   真违规的例子（人设没这条）：`rouxls`「（叹气）」、`susie`「（你打量了一下他。）」
#:   —— susie 那句还写成了**玩家视角**，是货真价实的视角错乱。
_PERSONA_PAREN_EXEMPT = (
    '字卡', '字幕', '音效', '特效',            # tenna：综艺字卡 + 音效
    '用括号', '以括号', '括号或', '括号表示',   # kris / ut_frisk：括号表示动作与内心
    '方括号', '斜体',                          # os_silver：方括号对话格式
)


def _persona_allows_paren(persona):
    """人设里明说了要用字卡/字幕/音效 ⇒ 括号插入是本角色的表演形式，豁免。"""
    return any(k in (persona or '') for k in _PERSONA_PAREN_EXEMPT)


def cn_ratio(text):
    """中文字符占**非空白字符**的比例。空串 ⇒ 1.0（不判）。"""
    s = re.sub(r'\s', '', text or '')
    if not s:
        return 1.0
    return len(re.findall(r'[\u4e00-\u9fff]', s)) / float(len(s))


def gate_reply(text, user_text='', prev=(), name='', persona=''):
    """判一条回复是否"还是本人"。返回 `(violations, soft)`，元素是 `(code, 说明)`。

    ★ 判据只认**能指认的现象**，不做"像不像"的模糊打分：
      · 硬违规 = 违反了人设文件里已经写死的约束（markdown / 括号动作 / 主人 / 200 字）；
      · 软标记 = 只是可疑（过短、句数偏多、夹英文）。
    这样报告里的"不合规率"才有明确的含义，而不是一个拍脑袋的分数。

    ★ `persona` 只用于**豁免**（人设自己要求字卡/音效的角色，括号不算违规），
      不参与加分。不传 ⇒ 保持旧行为，历史数据不受影响。
    """
    bad, soft = [], []
    t = (text or '').strip()
    if not t:
        return [('EMPTY', '空回复')], soft
    if _MD_RE.search(t):
        bad.append(('MARKDOWN', '出现 markdown 标记'))
    if _AI_RE.search(t):
        bad.append(('AI_SELF', '自称 AI/模型/程序：%s' % _AI_RE.search(t).group(0)))
    if _SLAVE_RE.search(t):
        bad.append(('SLAVE', '服务腔称呼：%s' % _SLAVE_RE.search(t).group(0)))
    if _PAREN_RE.search(t) and not _persona_allows_paren(persona):
        bad.append(('ACTION_PAREN', '括号动作：%s' % _PAREN_RE.search(t).group(0)))
    if len(t) > MAX_CHARS:
        bad.append(('TOO_LONG', '%d 字 > %d' % (len(t), MAX_CHARS)))
    # ★★ 第113轮：整句英文要算**硬违规**。原来只有一条软标记 `ENGLISH`
    #   （正则抓"长串 ASCII"），实测漏得干净：`hy_*` 8 个角色 36 轮中文占比 0.00、
    #   整段说英文，而闸门一次都没报 —— 软标记不进不合规率，等于没判。
    #   门槛：≥10 字且中文占比 <45%。为什么要长度门槛 —— 「Hi.」这种两词寒暄
    #   不该算违规；为什么是 45% —— 中文句子夹人名（"Kris 刚才来过"）大约 70~85%，
    #   一半英文一半中文的（"I'm fine，你呢"）掉到 30% 左右，45% 正好切在中间。
    if len(t) >= 10 and cn_ratio(t) < 0.45:
        bad.append(('NOT_CN', '整句英文（中文占比 %d%%）' % int(cn_ratio(t) * 100)))
    if _META_RE.search(t):
        bad.append(('META', '出戏词：%s' % _META_RE.search(t).group(0)))
    if user_text:
        u = re.sub(r'[\s，。！？!?、,.…]', '', user_text)
        r = re.sub(r'[\s，。！？!?、,.…]', '', t)
        # ★ 逐字相等也算复述，**不设长度门槛**：本套件首版只判 `len(u) >= 4`，
        #   于是「你好啊。」→「你好啊。」这种最短的复读被放过去了（B2 的负控制抓到的）。
        if u and r and (u == r or (u in r and len(u) >= 4)):
            bad.append(('PARROT', '整句复述对方'))
    for p in (prev or ()):
        if p and p.strip() == t:
            bad.append(('REPEAT', '与前面某句逐字相同'))
            break
    n_sent = len(_sentences(t))
    if n_sent > 3:
        soft.append(('TOO_MANY_SENTENCES', '%d 句' % n_sent))
    if len(t) < 4:
        soft.append(('TOO_SHORT', '<4 字'))
    if _ASCII_RUN_RE.search(t):
        soft.append(('ENGLISH', '长串英文'))
    return bad, soft


def build_patch(violations, markers, relations_list):
    """违规清单 → 一段**短的**纠正（最多 3 句）。

    顺序即优先级：先修"结构性"的（markdown / 自称 AI），再修"语气"的。
    跨角色撞车（`DUP`）由 eval 追加，它需要口癖词，所以单独一个入口。
    """
    codes = [c for c, _ in violations]
    want, seen = [], set()
    for c in ('MARKDOWN', 'AI_SELF', 'SLAVE', 'ACTION_PAREN', 'META',
              'TOO_LONG', 'TOO_MANY_SENTENCES', 'PARROT', 'REPEAT', 'ENGLISH', 'EMPTY'):
        if c in codes and c not in seen and c in PATCH_RULES:
            seen.add(c)
            want.append(PATCH_RULES[c])
        if len(want) >= 3:
            break
    return ' '.join(want)


def build_voice_patch(markers, dup_group=None):
    """跨角色撞车时的补丁：给一个"只属于他的说法"。

    ★ 只在**确实与别人撞了**的时候加（`dup_group` 非空），否则不加 ——
      凭空塞口癖会让本来正常的角色变得像在背台词。
    """
    if not dup_group or not markers:
        return ''
    pick = '、'.join('「%s」' % m for m in markers[:3])
    return '这才是你说话的样子：多用%s这种只属于你的说法，别说得跟别人一样。' % pick


# ---------------------------------------------------------------- 文本相似
def norm_text(s):
    return re.sub(r'[\s，。！？!?、,.…~～—\-]+', '', s or '')


def similarity(a, b):
    """归一化后的相似度（token 级 Jaccard）。用于"撞车"与"复读"的量化。"""
    import difflib
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def stable_seed(*parts):
    h = hashlib.sha256('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest()
    return int(h[:8], 16) % 2_000_000_000
