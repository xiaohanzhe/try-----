# -*- coding: utf-8 -*-
"""第66轮：**记忆文件**复检（速查本 `MEMORY.md` vs 详版 `参考-契约与历轮（详版）.md`）。

背景 / 为什么要有这个脚本
------------------------------------------------------------------
本轮改了速查本（§4 加自纠两例、§10 索引加 66、§11 N1~N4 转"已裁定"、头部段号 §0–§61 → §0–§62）。
按用户口径（记忆门槛五条）改速查本必须做「**逐令牌回验**」：**删掉/下沉的令牌要能在详版找得到**。

第一版回验是**手列令牌**的（把 16 个"下沉令牌"写死在脚本里），结果：
  * 6 个令牌报 `detail=False`（`相机+换房` / `道具背包` / `真机巡行` / `对话收口` / `底层彻查` / `常驻预热`）
    —— 但这 6 个**本来就还在速查本 §10 索引里**（是"轮次标签"，不是被删内容）⇒ **判据前提就错了**；
  * `nextroom=N;xx=..;yy=..` 报 `detail=False` —— 但详版 §61.2.2 **有**这个知识，只是写成多行代码块
    （`nextroom = 7;` / `xx = 160;  yy = 360;`）⇒ **判据过窄**（本项目头号坑）。
  ⇒ 这正是记忆本 §4 反复写的「**判据过窄 = 会误报**」。所以本脚本把第一版的**手列清单**换成
    **自动 diff**：`被删令牌 = toks(改前) - toks(改后)`，不再由我挑。

改前版本从哪来（★ 可复跑的关键）
------------------------------------------------------------------
不能拿 `git show HEAD:...` 现算 —— 本轮一 commit，HEAD 就变成"改后"，diff 变空、整条判据**静默失效**（恒真判据）。
⇒ 改用**快照入库**：`_evidence/mem_quick_before66.md` 存改前的速查本全文（**已在仓库内**，符合"蒸馏进仓"铁律）。
   本脚本 === 快照 vs 现盘 === 。

判据（10 组，含 2 条负控制 / no-op 控制）
------------------------------------------------------------------
M0  三份输入文件都在（速查本 / 详版 / 快照）
M1  速查本 js_len <= 10000（定义照抄详版 §40：`len(t.strip().encode('utf-16-le'))//2`），打印余量
M2  速查本头部段号 `§0–§NN` == 详版里真实的最大段号（防"指针比详版旧"）
M3  详版 §62 的 12 个小节 62.1 ~ 62.12 全在
M4  速查本 §10 索引含 `66` 及本轮三个数字（129→1 / 338→358 / 35→70）
M5  速查本 §11 的 N1~N4 四条裁定都在
M6  ★ 反向（本轮**真正被删**的令牌，每条要么宽式命中详版、要么进白名单）
    M6a 自动命中数 > 0（**no-op 控制**：命中 0 说明判据没在干活）
    M6b **负控制**：伪造令牌必须**不**命中、且不在白名单（证明判据有鉴别力）
    M6c 白名单每条都要**验证锚点真在详版**（白名单不是免检，是可审计的"宽容"）
M7  正向：本轮新增令牌必须在速查本（清单固定）
M8  编码：详版 / 速查本 无 BOM、无 U+FFFD
M9  快照是 LF-only（保证本脚本换行口径与仓库一致）
M10 改动守恒：本轮速查本净增 <= 200 JS 字符 + 余量 >= 100（★ 理由见下）

★ M10 为什么不是"净增 <= 0"
------------------------------------------------------------------
用户口径「**改动守恒（等量或净减）**」是针对**压缩动作**（不许借机塞新内容）。
但速查本每轮有**强制性轮次记账**：§10 索引加一行、§11 裁定状态更新、§4 记本轮判据教训
—— 本轮净增 **+80 JS 字符**（9774 → 9854）全部来自这三项，不是"塞内容"。
⇒ 判据取「净增 <= 200」（≈ 一条索引 + 一条教训的额度）而不是 "<= 0"：
   一旦某轮净增超过 200，说明**确实在往里塞东西**，那时必须先结构性去重再加。
余量 >= 100 是"别贴着容量墙"（本轮 146；历史最低曾到 6）。

跑法：`C:\\Python311\\python.exe code-quality-audit/第66轮-大图连通与mod并入/_tools/recheck66_mem.py`
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.join(HERE, '..')                       # code-quality-audit/第66轮-...
ROOT = os.path.join(ROUND, '..', '..')                 # 仓库根
EV = os.path.join(ROUND, '_evidence')
QUICK = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md')
BEFORE = os.path.join(EV, 'mem_quick_before66.md')

PASS = 0
FAIL = 0
FAILED = []


def check(name, ok, extra=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('[PASS] %s%s' % (name, ('  ' + extra) if extra else ''))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s%s' % (name, ('  ' + extra) if extra else ''))


def read_text(path):
    return io.open(path, encoding='utf-8').read()


def js_len(text):
    """详版 §40 的定义（对齐 JS 字符串长度）。"""
    return len(text.strip().encode('utf-16-le')) // 2


# ---------------------------------------------------------------- 令牌化
_RE_BACKTICK = re.compile(u'`([^`\n]+)`')
_RE_IDENT = re.compile(u'[A-Za-z_][A-Za-z0-9_.]{2,}')
_RE_NUM = re.compile(u'[0-9][0-9,.]{1,}')
_RE_CJK_SPLIT = re.compile(u'[^\u4e00-\u9fff]+')


def tokenize(text):
    """可检索令牌 = 反引号片段 + 标识符 + 多位数 + 连续中文短语(>=3 字)。"""
    toks = set()
    for m in _RE_BACKTICK.findall(text):
        toks.add(m.strip())
    for m in _RE_IDENT.findall(text):
        toks.add(m)
    for m in _RE_NUM.findall(text):
        toks.add(m)
    for run in _RE_CJK_SPLIT.split(text):
        if len(run) >= 3:
            toks.add(run)
    toks.discard('')
    return toks


def _squash(text):
    """去掉空白与常见分隔符 —— 用来吸收 `a = 1; b = 2` vs `a=1;b=2` 这类**纯书写形式**差异。"""
    return re.sub(u'[\\s;=,.\'"()\\[\\]:]', u'', text)


def relaxed_hit(tok, detail, detail_squashed=None):
    """宽式命中：返回命中的"方式"字符串，未命中返回 None。

    1) raw        原样在
    2) squashed   去空白/分隔符后在（吸收书写形式差异 —— 对应本项目"判据过窄"的教训）
    3) subphrase  中文短语的**任一 >=4 字连续子串**在（宽式；配 M6b 负控制证明不空转）
    """
    if tok in detail:
        return 'raw'
    if detail_squashed is not None:
        s = _squash(tok)
        if len(s) >= 3 and s in detail_squashed:
            return 'squashed'
    if _RE_CJK_SPLIT.sub('', tok) == tok and len(tok) >= 5:   # 纯中文且够长
        for i in range(0, len(tok) - 3):
            sub = tok[i:i + 4]
            if sub in detail:
                return 'subphrase:%s' % sub
    return None


# ---------------------------------------------------------------- 白名单（显式、可审计）
# 每条 = (为什么可以不在详版里原样出现, 锚点) —— 锚点必须真在详版里（M6c 校验）。
WHITELIST = {
    u'nextroom=N;xx=..;yy=..': (
        u'详版 §61.2.2 以多行代码块保留同一知识（`nextroom = 7;` / `xx = 160;  yy = 360;`）⇒ 仅书写形式不同',
        u'xx = 160'),
    u'挂接点待裁定': (
        u'状态注记；已被第66轮「大图连通」结论取代（3 hub 节点 + 合成边）',
        u'129 → 1 分量'),
    u'轮已出数据面': (
        u'同上：第65轮状态被第66轮连通取代',
        u'129 → 1 分量'),
    u'原文已收到': (
        u'状态注记；当前状态 = 人设原文待用户提供（66轮用户口径）',
        u'### 62.1 用户授权'),
    u'建议等': (
        u'N1~N4 的建议文本，已被 66 轮用户裁定取代',
        u'### 62.10 N1~N4 裁定'),
    u'按建议': (
        u'同上',
        u'### 62.10 N1~N4 裁定'),
}

# 本轮**新增**令牌（必须出现在速查本里）
FORWARD = [
    u'66 大图连通', u'129→1', u'338→358', u'N4', u'35→70',
    u'与 Kris 等人接触的时间', u'spr_*', u'DIFF 必看', u'定点距离式', u'蒸馏 105 个 GML',
]

# 负控制：伪造令牌（中文 + 代码型各一），必须既不命中详版、也不在白名单。
# ★ 第一版夹具选错，自己踩了坑：`这段字绝对不在详版里甲卜乙卜丙卜丁` 里含 `在详版里`
#   —— 这是**文档本身的高频措辞**，必然命中 ⇒ 负控制"报红"（判据侧误报，不是真问题）。
#   ⇒ 换用**生僻字**（不会与任何正常措辞撞车），并在 M6b0 先自证夹具是"真阴性"。
NEG_CJK = u'彘鬻鱻麤龘靐齉爩虪黐'
NEG_CODE = u'zzq_fabricated_token_66_never_exists'


def main():
    print(u'=' * 72)
    print(u'第66轮 记忆文件复检（速查本 vs 详版）')
    print(u'=' * 72)

    # ------------------------------------------------------------ M0
    missing = [p for p in (QUICK, DETAIL, BEFORE) if not os.path.isfile(p)]
    check(u'M0 三份输入都在（速查本/详版/快照）', not missing,
          u'' if not missing else u'缺: %s' % missing)
    if missing:
        print(u'\n输入不齐，终止。')
        return 1

    quick = read_text(QUICK)
    detail = read_text(DETAIL)
    before = read_text(BEFORE)
    det_sq = _squash(detail)

    # ------------------------------------------------------------ M1
    n = js_len(quick)
    check(u'M1 速查本 js_len <= 10000', n <= 10000,
          u'js_len = %d  上限 = 10000  余量 = %d' % (n, 10000 - n))

    # ------------------------------------------------------------ M2
    m_head = re.search(u'全文（§0[–—-]§(\\d+)）', quick)
    head_sec = int(m_head.group(1)) if m_head else -1
    # ★ 判据过窄修正：详版标题两种写法混用（`## §57 …` 与 `## 56. …`）⇒ 必须容忍 `§` 前缀。
    #   第一版写 `^##\s+(\d+)` ⇒ 只捞到 §56 ⇒ 误报"头部 §0–§62 但详版 max=56"。
    secs = [int(m.group(1)) for m in re.finditer(u'(?m)^#{2,3}\\s*§?(\\d+)\\b', detail)]
    real_max = max(secs) if secs else -1
    check(u'M2 头部段号 == 详版实际最大段号', head_sec == real_max and real_max > 0,
          u'头部 §0–§%d  详版 max = %d（容忍 `§` 前缀）' % (head_sec, real_max))

    # ------------------------------------------------------------ M3
    subs = re.findall(u'(?m)^###\\s+62\\.(\\d+)', detail)
    want = [str(i) for i in range(1, 13)]
    check(u'M3 详版 §62 小节 62.1~62.12 全在', sorted(set(subs), key=int) == want,
          u'实得 %s' % sorted(set(subs), key=int))

    # ------------------------------------------------------------ M4
    idx = quick.split(u'## 10.', 1)[-1].split(u'## 11.', 1)[0]
    m4_bits = [(t, t in idx) for t in (u'66', u'129→1', u'338→358', u'35→70')]
    check(u'M4 §10 索引含 66 与本轮三个数字', all(ok for _, ok in m4_bits),
          u' '.join(u'%s=%s' % (t, ok) for t, ok in m4_bits))

    # ------------------------------------------------------------ M5
    dec = quick.split(u'## 11.', 1)[-1]
    m5_bits = [
        (u'与 Kris 等人接触的时间', u'与 Kris 等人接触的时间' in dec),
        (u'定点距离式', u'定点距离式' in dec),
        (u'接线 = 我定', u'接线 = 我定' in dec),
        (u'跨作品 35 条已注册', u'跨作品 35 条' in dec and u'已注册' in dec),
    ]
    check(u'M5 §11 的 N1~N4 四条裁定都在', all(ok for _, ok in m5_bits),
          u' '.join(u'%s=%s' % (t, ok) for t, ok in m5_bits))

    # ------------------------------------------------------------ M6 反向（自动 diff，不手列）
    removed = sorted(tokenize(before) - tokenize(quick), key=lambda x: (-len(x), x))
    auto, wl_used, unhandled = [], [], []
    for t in removed:
        mode = relaxed_hit(t, detail, det_sq)
        if mode:
            auto.append((t, mode))
        elif t in WHITELIST:
            wl_used.append(t)
        else:
            unhandled.append(t)

    print(u'-- M6 反向：被删令牌 %d 个（自动 diff 得出）' % len(removed))
    for t, mode in auto:
        print(u'     [auto %-9s] %s' % (mode.split(':')[0], t) +
              (u'   ← 子串 %s' % mode.split(':', 1)[1] if mode.startswith('subphrase') else u''))
    for t in wl_used:
        print(u'     [whitelist] %s   —— %s' % (t, WHITELIST[t][0]))
    for t in unhandled:
        print(u'     [UNHANDLED] %s' % t)

    check(u'M6 被删令牌全部**自动命中或已白名单**（无未处置）', not unhandled,
          u'自动 %d / 白名单 %d / 未处置 %d' % (len(auto), len(wl_used), len(unhandled)))
    # M6a no-op 控制
    check(u'M6a no-op 控制：自动命中数 > 0（判据确实在干活）', len(auto) > 0,
          u'自动命中 = %d' % len(auto))
    # M6b 负控制（夹具先自证是"真阴性"，再用它证明判据有鉴别力）
    neg_grams = [NEG_CJK[i:i + 4] for i in range(len(NEG_CJK) - 3)]
    fixture_clean = all(g not in detail for g in neg_grams) and (NEG_CODE not in detail)
    check(u'M6b0 负控制夹具自证：4-gram 与伪造标识符都不在详版（夹具是真阴性）',
          fixture_clean,
          u'4-gram %d 个；脏子串 = %s' % (
              len(neg_grams), [g for g in neg_grams if g in detail] or u'无'))
    neg_hit_cjk = relaxed_hit(NEG_CJK, detail, det_sq)
    neg_hit_code = relaxed_hit(NEG_CODE, detail, det_sq)
    check(u'M6b 负控制：伪造令牌不命中且不在白名单（判据有鉴别力）',
          fixture_clean and (neg_hit_cjk is None) and (neg_hit_code is None)
          and (NEG_CJK not in WHITELIST) and (NEG_CODE not in WHITELIST),
          u'cjk=%s code=%s' % (neg_hit_cjk, neg_hit_code))
    # M6c 白名单锚点校验（白名单不是免检）
    bad_anchor = [t for t in wl_used if WHITELIST[t][1] not in detail]
    check(u'M6c 白名单每条锚点真在详版（白名单不免检）', not bad_anchor,
          u'缺锚点: %s' % bad_anchor if bad_anchor else u'%d 条锚点全部命中' % len(wl_used))

    # ------------------------------------------------------------ M7 正向
    fwd_bad = [t for t in FORWARD if t not in quick]
    check(u'M7 本轮新增令牌全部在速查本', not fwd_bad,
          u'缺: %s' % fwd_bad if fwd_bad else u'%d 条全部命中' % len(FORWARD))

    # ------------------------------------------------------------ M8 编码
    enc_bad = []
    for p, name in ((QUICK, u'速查本'), (DETAIL, u'详版')):
        raw = io.open(p, 'rb').read()
        if raw.startswith(b'\xef\xbb\xbf'):
            enc_bad.append(u'%s 有 BOM' % name)
        txt = raw.decode('utf-8')
        if u'\ufffd' in txt:
            enc_bad.append(u'%s 含 U+FFFD' % name)
    check(u'M8 无 BOM / 无 U+FFFD', not enc_bad, u'; '.join(enc_bad) if enc_bad else u'ok')

    # ------------------------------------------------------------ M9 快照换行
    raw_before = io.open(BEFORE, 'rb').read()
    check(u'M9 快照 LF-only（换行口径与仓库一致）', b'\r' not in raw_before,
          u'CR 个数 = %d' % raw_before.count(b'\r'))

    # ------------------------------------------------------------ M10 改动守恒
    nb = js_len(before)
    delta = n - nb
    print(u'【记录 / 非判据】速查本 js_len：%d → %d，净增 %+d' % (nb, n, delta))
    check(u'M10 改动守恒：净增 <= 200 且余量 >= 100',
          delta <= 200 and (10000 - n) >= 100,
          u'净增 %+d（额度 200）  余量 %d（下限 100）' % (delta, 10000 - n))

    # ------------------------------------------------------------ M11 结构自检
    # 用户复检口径 ②「结构自检（标题全在、无粘连）」
    quick_secs = [int(m.group(1)) for m in re.finditer(u'(?m)^##\\s+(\\d+)\\.', quick)]
    glued = [i + 1 for i, l in enumerate(quick.split(u'\n')) if l.count(u'## ') > 1]
    check(u'M11 速查本 §0~§11 标题全在且严格递增、无粘连',
          quick_secs == list(range(12)) and not glued,
          u'实得 %s；粘连行 %s' % (quick_secs, glued or u'无'))

    # ------------------------------------------------------------ 汇总
    print(u'-' * 72)
    print(u'合计：PASS=%d FAIL=%d' % (PASS, FAIL))
    if FAILED:
        print(u'FAIL 列表：')
        for f in FAILED:
            print(u'  - %s' % f)
    else:
        print(u'ALL PASS')
    return 1 if FAIL else 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
