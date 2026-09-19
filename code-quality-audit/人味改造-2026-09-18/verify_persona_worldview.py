# -*- coding: utf-8 -*-
"""世界观验证探针（第二十一轮升级版）：**端到端**，复刻 chat_with_ai 的真实 system 拼装。

为什么需要它（本文件存在的理由）：
  `verify_persona_chat.py` 只能证明 **persona / 索引文件里写没写**（契约级）。
  它证明不了 **模型真的会用**（行为级）—— 而"写了但问起来还是瞎编"是本项目最贵的坑
  （见 MEMORY §5："函数写对了 ≠ 产品用上了"）。
  所以真机可测时，必须跑这个探针，看的是**模型的实际回答**。

第二十一轮升级（用户口径：「你直接做探针吧，测试这类的留到后面」）：
  旧版**只把 persona 当 system 发出去**，没带召回块 —— 那测的是"光有 persona
  他能答成什么样"，**不是产品真实链路**。真实链路（main.py `chat_with_ai`）是：

      system = persona + "\\n\\n" + 记忆召回 + "\\n\\n" + 世界观召回 + "\\n\\n" + 关系档位

  本版复刻这条链路里的**世界观那一段**：每题先按 cue 跑 `worldview_recall.recall_text`
  真算出召回块，再拼进 system。这样测出来的才是"用户真问这句话时他会怎么答"。
  同时加**负控制题**：闲聊时召回必须为空 → system 里就不该出现「【你想起了那边的事】」。

用法（需 Ollama 在跑、且 ralsei:v3 已 build）：
  C:\\Python311\\python.exe verify_persona_worldview.py            # 跑全部
  C:\\Python311\\python.exe verify_persona_worldview.py --only 5   # 只跑第 5 题
  C:\\Python311\\python.exe verify_persona_worldview.py --model ralsei:v3
  C:\\Python311\\python.exe verify_persona_worldview.py --raw      # 连原始回复一起打印
  C:\\Python311\\python.exe verify_persona_worldview.py --no-recall # 对照组：关掉召回

判据分两层（**别只看第一层**）：
  1. 命中锚（hit）：答里有没有提到该知道的关键词 —— 说明"他知道"；
  2. 反面（bad）：有没有出现元游戏词 / 攻略腔 / 客服腔 —— 说明"他没退化成旁白/维基"。
  两者都过才算 PASS。只过第 1 层但出现第 2 层的，算 **PARTIAL**（要人工看）。

输出落盘：本目录 `_evidence/worldview_probe_<日期>.txt`（UTF-8，Python 自写，不经 PowerShell）。

第二十三轮升级（2026-09-20）：**把 `_clean_ai_reply` 的四步闸全部复刻进探针**。
  上一版只复刻了长度闸，两轮里连撞两次"探针漏一道闸 → 报一个假问题"：
    · 长度闸漏 → 误读"召回让回答变啰嗦"（其实是 150 的上限砍的）；
    · 动作闸漏 → 误报"产品漏删（停顿了一下）"（其实是探针没跑 0a 步）。
  本版补齐 0a（括号动作）、0c（出戏/客服腔）、1（自问自答截断）、
  2（车轱辘话，靠探针自维护的 `recent`）、3（超长）—— 于是"闸后"就是
  **用户实际看到的文本**，判退（返回 None）会被如实报成「判退」而不是被洗掉。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')      # `import modules.*` 需要这一级进 path
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
OUTDIR = os.path.join(HERE, '_evidence')

if PET not in sys.path:
    sys.path.append(PET)

# 12 道题：每题 = (编号, 问题, 必须命中的锚(任一), 必须不出现的反面词)
# 最后一题(#12)是**负控制**：闲聊，召回应为空。
QUESTIONS = [
    (1, '黑暗世界是什么？',            ('黑暗', '喷泉'),          ('玩家', '游戏')),
    (2, '光之民和暗之民有什么不一样？',  ('光之民', '暗之民'),       ('设定', '属性')),
    (3, '那个预言说的是什么？',        ('预言', '英雄'),           ('任务', '剧情')),
    (4, 'Kris 和 Susie 是什么样的人？', ('Kris', 'Susie'),        ('玩家', '操作')),
    (5, 'Kris 的妈妈是谁？',           ('托丽尔', 'Toriel'),       ('NPC', '角色卡')),
    (6, 'Noelle 是个什么样的女孩？',    ('Noelle', 'Susie'),       ('好感度', '攻略')),
    (7, 'Asgore 呢？他在做什么？',      ('Asgore', '花店'),         ('路线', '结局分支')),
    (8, '你上次去花之王国是什么时候？',  ('花', '庆典'),            ('第5章', '关卡', '攻略')),
    (9, 'Flowery 是谁？',              ('Flowery', '花'),          ('boss', 'BOSS', '击败')),
    (10, 'Asgore 最后怎么了？',         ('骑士', '带走'),           ('剧情杀', '过场')),
    (11, 'Dess 是谁？',                ('Dess', '失踪'),           ('彩蛋', '伏笔')),
    (12, '你今天过得怎么样？',          ('今天', '你'),             ('有什么可以帮', '作为', 'AI')),
]

HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
DATE = time.strftime('%Y-%m-%d')


def load_persona():
    return io.open(PERSONA, encoding='utf-8').read()


def build_system(persona, cue, use_recall=True):
    """复刻 chat_with_ai 的世界观那一段。返回 (system, recall_keys, recall_text)。"""
    if not use_recall:
        return persona, [], ''
    try:
        import modules.worldview_recall as WR
        blocks = WR.recall(cue, limit=2)
        txt = WR.recall_text(cue, limit=2)
    except Exception as e:
        return persona, ['<ERR %r>' % (e,)], ''
    if not txt:
        return persona, [], ''
    return persona + '\n\n' + txt, [b.key for b in blocks], txt


# 第二十二轮加：**长度闸 + 动作闸**的复刻。
# 第二十三轮（2026-09-20）补：**第 1、2 步**（自问自答截断、车轱辘话判退）也要复刻。
#
# 为什么探针里也要过这些闸：它们都在 `_clean_ai_reply`（产品链路上**每一条**
# 回复都会走完这几步）。探针若只看裸输出，报的就不是"用户实际看到的文本"。
#   ① 长度闸漏复刻 → 上一轮量到 214 字，以为"召回让它变啰嗦"，
#      实际 214 已 > 当时的 150 上限、用户看到的是被砍过尾巴的 150 字。
#   ② 动作闸漏复刻 → 本轮报出「（停顿了一下）」像"产品漏删旁白"，
#      其实是探针没复刻 0a 步（`_ACTION_PAREN_RE` 里明明有「停顿」）。
# 两次都是同一类错：**探针漏一道闸就报一个假问题**。
# 所以这里把 0a / 1 / 2 / 3 四步**全部复刻**，让"闸后"就是"用户实际看到的"。
#
# 为什么不直接 import main 里的 `_clean_ai_reply`：它会拉起 PyQt 依赖链
# （本探针要在裸 python 下跑；实测托管 3.13 里根本没有 PyQt5）。所以：
#   · 常量/正则 → 从 `src/main.py` **源码抽取**（`_load_*` 三个函数）；
#   · 判据（动作/出戏/客服腔）→ 从 `modules.event_speech` **直接 import**
#     （该模块 Qt-free）。**绝不另抄一份判据**（项目铁律：判据只许有一处，
#     抄第二份必然漂移）。
def _load_reply_cap():
    """从 src/main.py 里取 AI_REPLY_MAX_CHARS（不 import main，只正则抓常量）。"""
    try:
        src = io.open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
        import re
        m = re.search(r'^\s*AI_REPLY_MAX_CHARS\s*=\s*(\d+)', src, re.M)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _load_role_marker_re():
    """从 src/main.py 源码里抽出 `_role_marker_re` 的正则（第 1 步的判据）。

    正则源码是**两段相邻字符串拼接**（`re.compile(r"..." r"...")`）——
    这也是从源码抽取而非 import 的原因（import 会拉 PyQt）。两段都要取，
    只取第一段会少掉 `[：:]` 那个结尾。

    抽不到 → 返回 None，由调用方降级（当作"没有这道闸"，并在报告里标注）。
    """
    try:
        import re
        src = io.open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
        m = re.search(
            r'_AI_ROLE_MARKER\s*=\s*re\.compile\(\s*\n'
            r'\s*r"([^"]*)"\s*\n'
            r'\s*r"([^"]*)"', src)
        if not m:
            return None
        return re.compile(m.group(1) + m.group(2))
    except Exception:
        return None


def _is_repeat_of_recent(text, recent):
    """复刻 `RalseiPet._is_repeat_of_recent` 的车轱辘话判据（第 2 步）。

    判据**逐字对齐** src/main.py（第十八轮定的经验值，两条互补）：
      1) 整体相似度 difflib ≥ 0.82（且长度差 ≤ 6）—— 抓"只改两三个字"的整句复用；
      2) 最长公共匹配块 ≥ 12 字 —— 抓"整体相似度不到 0.82、但有一大段原样搬来"。
    归一化先去标点/空白/星号（与产品一致）。

    ⚠️ 这里是**唯一的例外**：产品那份判据写在 `main.py` 的实例方法里，
    没法从源码里"取出来直接用"（它依赖 `self` 与 `difflib` 运行时），
    所以只能重写一份。为防漂移，验证脚本里有一条**等价性断言**
    （`verify_persona_chat.py` 的 W 组）会拿同一批样本跑两侧、比对结果。
    """
    try:
        import re as _re
        import difflib

        def _norm(s):
            return _re.sub(r'[\s，。！？!?、~…—\-（）()「」“”"\'’*`]', '', str(s))

        t = _norm(text)
        if len(t) < 6 or not recent:
            return False
        for sample in recent:
            s = _norm(sample)
            if len(s) < 6:
                continue
            if abs(len(s) - len(t)) <= 6 and \
                    difflib.SequenceMatcher(None, t, s).ratio() >= 0.82:
                return True
            biggest = max(
                (b.size for b in difflib.SequenceMatcher(None, t, s).get_matching_blocks()),
                default=0)
            if biggest >= 12:
                return True
    except Exception:
        return False
    return False


def _load_md_strip_re():
    """从 src/main.py 源码里抽出 `_md_strip_re` 的正则（第 0b 步的判据）。

    与 `_role_marker_re` 同一套路（源码抽取，不 import main）。
    ⚠️ 抽不到不要紧 —— 但**必须让 0b 步有兜底**：`_md_strip_fallback()` 用
    一份等价的朴素正则，并会在报告里标注"用的是兜底"。宁可标注，不要静默漏闸。
    """
    try:
        import re
        src = io.open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
        m = re.search(r'_MD_STRIP_RE\s*=\s*re\.compile\(\s*\n\s*r\'([^\']*)\'',
                      src)
        if not m:
            return None
        return re.compile(m.group(1), re.M)
    except Exception:
        return None


def _md_strip_fallback():
    """与 main.py `_md_strip_re` 等价的朴素实现（仅在源码抽取失败时兜底）。

    抽不到源码正则说明 main.py 被大改过 —— 那时**宁可少剥也不能崩**，
    但报告里要能看出来（否则又是一个"静默漏闸"）。
    """
    import re
    return re.compile(r'\*{1,3}|`{1,3}|^[#>\-]\s*|^\d+[.、]\s+', re.M)


# 判据一次导入，供整轮复用（模块级；导入失败置 None，由调用方降级）
try:
    if PET not in sys.path:
        sys.path.append(PET)
    from modules.event_speech import (
        strip_action_parentheticals as _STRIP_ACTION,
        looks_out_of_character as _OOC,
        looks_like_assistant_speak as _ASST)
except Exception as _e:                                  # pragma: no cover
    _STRIP_ACTION = _OOC = _ASST = None
    sys.stderr.write('[warn] event_speech 判据导入失败，0a/0c 步降级：%r\n' % (_e,))

_ROLE_RE = _load_role_marker_re()
_MD_RE = _load_md_strip_re()
_MD_FALLBACK = _MD_RE is None


def _apply_gates(text, cap, recent=None):
    """复刻 `_clean_ai_reply` 的四步闸，返回 (最终文本或 None, 闸后长度, 是否被截断)。

    与产品（`src/main.py::_clean_ai_reply`）**逐步对应**（顺序即优先级）：
      0a) 删句中括号动作旁白（判据 import 自 modules.event_speech）→ 删净则判退
      0b) 剥 markdown 强调/列表标记 + 去包裹引号（判据从 main.py 源码抽取）
      0c) 出戏 / 客服腔（判据同 modules.event_speech）→ 判退 ［本步与内容有关，
          探针也要过，否则"模型真吐了客服腔"会被探针洗掉，报出一个假 PASS］
      1)  自问自答续写 → 截到标记之前；截完为空 → 判退
      2)  车轱辘话（与探针维护的 recent 比）→ 判退
      3)  超长 → 从最近的句末标点截断

    ⚠️ 0a 必须排在 0b 之前（与产品同）：星号版的动作旁白 `*轻轻敲了敲键盘*`
    若先过 0b，那对星号会被吃掉、只剩裸旁白，反而认不出来。

    返回值语义（与产品一致）：
      * `(None, …)` = **判退**（产品会走"换一个说法重采样"路径，不是沉默）；
      * `(str, …)`  = 该显示的文本。
    第 3 元组 `was_cut` 只对第 3 步（超长）有意义 —— 第 1 步的截断不在此列
    （它由 `_ROLE_RE` 直接改文本，语义是"续写被切掉"，与"太长被砍尾巴"不同，
    产品里也是分开处理的）。

    第 2 步需要 `recent`：探针把**本轮已产出的回复**当 recent 累积传进来
    （产品里 recent 也确实是"他自己最近说的话"）。
    """
    t = text
    if not isinstance(t, str):
        return None, 0, False
    t = t.strip()
    if not t:
        return None, len(text), False
    was_cut = False
    # 0a) 括号动作旁白（删那一段）—— 必须在剥 markdown 之前
    if _STRIP_ACTION is not None:
        t = _STRIP_ACTION(t)
        if not t:
            return None, len(text), False
    # 0b) 剥 markdown 标记 + 去包裹引号/书名号
    t = (_MD_RE or _md_strip_fallback()).sub('', t).strip()
    t = t.strip('"\'“”「」『』《》').strip()
    if not t:
        return None, len(text), False
    # 与产品同步：只剩标点（无任何实义字符）→ 判退
    import re as _re_local
    if not _re_local.search(r'[0-9A-Za-z\u4e00-\u9fff]', t):
        return None, len(text), False
    # 0c) 出戏 / 客服腔 → 判退（与产品同源；探针不替产品"洗掉"这类输出）
    if _OOC is not None and _OOC(t):
        return None, len(text), False
    if _ASST is not None and _ASST(t):
        return None, len(text), False
    # 1) 自问自答续写 → 截到标记之前
    if _ROLE_RE is not None:
        m = _ROLE_RE.search(t)
        if m:
            t = t[:m.start()].strip()
        if not t:
            return None, len(text), False
    # 2) 车轱辘话 → 判退（调用方/产品会重采样）
    if _is_repeat_of_recent(t, recent):
        return None, len(text), False
    # 3) 超长 → 最近的句末标点处截断
    n0 = len(t)
    if not cap or n0 <= cap:
        return t, n0, False
    cut = -1
    for sep in ('。', '！', '？', '!', '?', '\n'):
        i = t.rfind(sep, 0, cap)
        if i > cut:
            cut = i
    out = (t[:cut + 1] if cut > 0 else t[:cap]).strip()
    return out, n0, True


def ask(model, system, user, timeout=180):
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(
        HOST + '/api/chat', data=body,
        headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode('utf-8'))
    dt = time.time() - t0
    return (data.get('message') or {}).get('content', ''), dt


def score(reply, anchors, bads):
    hit = [a for a in anchors if a.lower() in reply.lower()]
    bad = [b for b in bads if b.lower() in reply.lower()]
    if hit and not bad:
        return 'PASS', hit, bad
    if hit and bad:
        return 'PARTIAL', hit, bad
    return 'FAIL', hit, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='ralsei:v3')
    ap.add_argument('--only', type=int, default=0)
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--no-recall', action='store_true',
                    help='对照组：不发召回块（只发 persona），用于对比"召回到底有没有用"')
    args = ap.parse_args()

    persona = load_persona()
    _cap = _load_reply_cap()
    lines = []
    lines.append('世界观真机探针（端到端版）· %s' % DATE)
    lines.append('=' * 64)
    lines.append('模型 : %s' % args.model)
    lines.append('端点 : %s' % HOST)
    lines.append('persona : %d 字符 / 作 system 前缀发出' % len(persona))
    lines.append('长度闸 : AI_REPLY_MAX_CHARS = %s（第二十二轮；复刻 _clean_ai_reply 第 3 步）'
                 % _cap)
    lines.append('动作闸 : 复刻 _clean_ai_reply 第 0a 步（句中括号动作只删那段，判据从 '
                 'modules.event_speech 导入）')
    lines.append('格式闸 : 复刻第 0b 步（剥 markdown 标记 + 去包裹引号；正则从 src/main.py 抽取）')
    lines.append('话术闸 : 复刻第 0c 步（出戏 / 客服腔 → 判退；判据同源 event_speech）')
    lines.append('续写闸 : 复刻第 1 步（自问自答截断；正则从 src/main.py 源码抽取）')
    lines.append('复读闸 : 复刻第 2 步（车轱辘话判退；recent = 本轮已产出的回复，逐题累积）')
    lines.append('召回 : %s' % ('**关闭（对照组：只发 persona）**'
                                if args.no_recall else '开启（复刻 chat_with_ai 链路）'))
    lines.append('')
    lines.append('判据：hit(该知道的关键词, 任一) 且 无 bad(元游戏词/攻略腔/客服腔) → PASS；')
    lines.append('      hit 但有 bad → PARTIAL(人工看)；连 hit 都没有 → FAIL。')
    lines.append('      #12 是负控制题（闲聊），期望"召回为空、不出现设定倾倒"。')
    lines.append('      判分用**闸后**文本（用户实际看到的那条）；闸前长度另列，用于看模型原始倾向。')
    lines.append('      ⚠️ 本版已复刻 `_clean_ai_reply` 全部六道闸（0a/0b/0c/1/2/3）→ "闸后"即'
                 '"用户实际看到的"。')
    lines.append('         若某题标「判退(None)」，意味着产品链路上这条会走**重采样**、'
                 '用户看不到它。')
    lines.append('         重采样后的结果本探针不模拟（那要多打一次模型）—— 所以判退题计为'
                 '**RETAIN**，单列不算分。')
    lines.append('')

    counts = {'PASS': 0, 'PARTIAL': 0, 'FAIL': 0, 'ERR': 0}
    stats = []          # (num, raw_len, final_len, cut?)
    recent = []         # 第 2 步用：本轮**已产出**的回复（复刻产品"他自己最近说过的话"）
    rejected = []       # (num, why) —— 判退的题
    for num, q, anchors, bads in QUESTIONS:
        if args.only and num != args.only:
            continue
        system, rkeys, rtxt = build_system(persona, q, use_recall=not args.no_recall)
        try:
            reply_raw, dt = ask(args.model, system, q)
        except Exception as e:
            lines.append('[ERR ] Q%-2d %s' % (num, q))
            lines.append('        %r' % (e,))
            counts['ERR'] += 1
            continue
        verdict_raw = reply_raw
        reply, raw_len, was_cut = _apply_gates(reply_raw, _cap, recent=recent)
        if reply is None:
            # 判退：产品链路上这条不会被用户看到（会重采样）。单列，不计分。
            lines.append('[RETN] Q%-2d %s  (%.1fs)' % (num, q, dt))
            lines.append('        system=%d 字 ; 召回=%r' % (len(system), rkeys))
            lines.append('        判退：这条被 _clean_ai_reply 拦下（产品会重采样，用户看不到它）')
            lines.append('        闸前原文：%s' % verdict_raw.replace('\n', ' / ')[:200])
            lines.append('')
            rejected.append((num, 'gated'))
            continue
        recent.append(reply)        # 只有"真的显示给用户"的那句才进 recent
        stats.append((num, raw_len, len(reply), was_cut))
        verdict, hit, bad = score(reply, anchors, bads)
        counts[verdict] += 1
        lines.append('[%s] Q%-2d %s  (%.1fs)' % (verdict, num, q, dt))
        lines.append('        system=%d 字 ; 召回=%r' % (len(system), rkeys))
        lines.append('        长度：闸前 %d → 闸后 %d%s'
                     % (raw_len, len(reply), '  **被截断**' if was_cut else ''))
        lines.append('        hit=%r bad=%r' % (hit, bad))
        lines.append('        回复：%s' % reply.replace('\n', ' / '))
        if args.raw and rtxt:
            lines.append('        --召回原文--')
            for ln in rtxt.split('\n'):
                lines.append('        | %s' % ln)
        if args.raw and was_cut:
            lines.append('        --闸前原文--')
            lines.append('        | %s' % reply_raw.replace('\n', ' / '))
        lines.append('')

    lines.append('=' * 64)
    lines.append('合计：PASS=%d PARTIAL=%d FAIL=%d ERR=%d  判退(RETN)=%d' % (
        counts['PASS'], counts['PARTIAL'], counts['FAIL'], counts['ERR'],
        len(rejected)))
    if rejected:
        lines.append('判退题：%s（产品链路上会重采样；探针不模拟第二次调用）'
                     % ', '.join('Q%d' % n for n, _w in rejected))
    if stats:
        _rls = [s[1] for s in stats]
        _fls = [s[2] for s in stats]
        _cuts = [s for s in stats if s[3]]
        lines.append('')
        lines.append('— 篇幅（第二十二轮新增的观测量）—')
        lines.append('闸前：均值 %.0f 字，最长 %d 字（模型原始倾向）'
                     % (sum(_rls) / len(_rls), max(_rls)))
        lines.append('闸后：均值 %.0f 字，最长 %d 字（用户实际看到的）'
                     % (sum(_fls) / len(_fls), max(_fls)))
        lines.append('被截断：%d/%d 条%s' % (
            len(_cuts), len(stats),
            ('  → ' + ', '.join('Q%d(%d→%d)' % (s[0], s[1], s[2]) for s in _cuts))
            if _cuts else ''))
        _over = [s for s in stats if s[1] > (_cap or 99999)]
        lines.append('超过上限的条数：%d/%d（这是"闸门本来会不会砍它"的直接证据）'
                     % (len(_over), len(stats)))
    lines.append('')
    lines.append('怎么读这份结果：')
    lines.append('  · FAIL 里若"谁都答不出"，先查模型/端点；若只有 ch5 的题(8/9/10/11)答不出，')
    lines.append('    那是**正常**的 —— 本机语料只到 ch4，ch5 是照官方资料写的，模型没见过原文。')
    lines.append('  · PARTIAL 要看 bad 命中了什么：出现"玩家/存档"=元游戏词漏了；')
    lines.append('    出现"boss/击败/攻略"=攻略腔漏了；出现"有什么可以帮"=客服腔漏了。')
    lines.append('    这三类都该回 persona 收紧写法，而不是改代码（除非是 _clean_ai_reply 没拦住）。')
    lines.append('  · 这一版把召回块真的拼进 system 了 —— 若某题 FAIL 但"召回"字段显示命中，')
    lines.append('    说明**召回取到了、模型没接住**，问题在 persona 的"怎么说"而不是索引内容。')
    lines.append('    若"召回"字段是 []，说明是**取错了块**，该回去查触发词或图边。')
    lines.append('  · RETN（判退）不是坏事：它说明护栏在干活。但若**判退突然变多**，')
    lines.append('    多半是模型输出风格漂了（或 persona 改过头）—— 该去看闸前原文长什么样。')

    os.makedirs(OUTDIR, exist_ok=True)
    suffix = '_norecall' if args.no_recall else ''
    out = os.path.join(OUTDIR, 'worldview_probe_%s%s.txt' % (DATE, suffix))
    io.open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    # 回显 stdout **必须做异常兜底**（2026-09-20 踩过）：
    # 回复里可能夹带模型吐的成对代理字符（surrogate），Windows 控制台编码器
    # 遇到它会抛 `OSError: [Errno 22] Invalid argument` —— 那会让整个探针
    # **在最后一步崩掉**，落盘结果明明已经写好了（文件是完整的），
    # 但退出码非 0、stderr 只有一行 traceback，看起来像"探针失败"。
    # 这里改成"回显失败就降级"，绝不让回显问题吃掉已经拿到的结果。
    try:
        print('\n'.join(lines))
    except Exception as e:
        sys.stderr.write('[warn] stdout 回显失败（不影响落盘）：%r\n' % (e,))
    print('WROTE %s' % out)


if __name__ == '__main__':
    main()
