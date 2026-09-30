# -*- coding: utf-8 -*-
u"""第67轮：**记忆文件**复检（速查本 `MEMORY.md` vs 详版 `参考-契约与历轮（详版）.md`）。

背景
------------------------------------------------------------------
本轮速查本改动：头部段号 §0–§62 → §0–§63；§3 补两条教训（**DPI 感知** / **产物侧看不见 ≠ 调用侧没发生**）；
§4 把"第66轮四例"并成"第66/67轮判据侧自纠"并补第67轮三例；§7 幽灵线 **"暂不接线" → "已接线（§63）"**；
§10 索引加 67；§11 N1~N3 **"待落地" → "已落地"**。
★ 首次测量 **超限**（9888 → 10295 > 10000）⇒ 按用户口径做**结构性去重**（不是削语义）：
  把 §7 里已在详版的细则收紧、把 3 条**详版没有**的语义**下沉进 §63.15**，净增 **−56**。

用户的记忆门槛（五条）逐条对应到本脚本
------------------------------------------------------------------
(a) **实证超限** ⇒ M1 打印改动前后 js_len 与余量
(b) **先补详版** ⇒ M2/M3（详版必须已有 §63 且小节齐全，速查本指针不许比详版新）
(c) **逐令牌回验** ⇒ M6（**自动 diff**，不手列）+ M6c（白名单**不免检**：锚点必须真在详版）
(d) **改动守恒** ⇒ M10（净增进额度内 + 余量 ≥ 100）
(e) **说清为什么必须改** ⇒ 报告 §9 + 本 docstring

改前版本从哪来（★ 可复跑的关键）
------------------------------------------------------------------
不能拿 `git show HEAD:` 现算 —— 一 commit，HEAD 就成"改后"、diff 变空、判据**静默失效**（恒真判据）。
⇒ **快照入库**：`_evidence/mem_quick_before67.md`（**已在仓库内**，符合"蒸馏进仓"铁律）。

跑法：`C:\\Python311\\python.exe code-quality-audit/第67轮-幽灵线接线/_tools/recheck67_mem.py`
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))          # code-quality-audit/第67轮-...
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))    # 仓库根
EV = os.path.join(ROUND, '_evidence')
QUICK = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md')
BEFORE = os.path.join(EV, 'mem_quick_before67.md')

PASS = 0
FAIL = 0
FAILED = []


def check(name, ok, extra=u''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(u'[PASS] %s%s' % (name, (u'  ' + extra) if extra else u''))
    else:
        FAIL += 1
        FAILED.append(name)
        print(u'[FAIL] %s%s' % (name, (u'  ' + extra) if extra else u''))


def read_text(path):
    return io.open(path, encoding='utf-8').read()


def js_len(text):
    u"""详版 §40 的定义（对齐 JS 字符串长度）。"""
    return len(text.strip().encode('utf-16-le')) // 2


# ---------------------------------------------------------------- 令牌化
_RE_BACKTICK = re.compile(u'`([^`\n]+)`')
_RE_IDENT = re.compile(u'[A-Za-z_][A-Za-z0-9_.]{2,}')
_RE_NUM = re.compile(u'[0-9][0-9,.]{1,}')
_RE_CJK_SPLIT = re.compile(u'[^\u4e00-\u9fff]+')


def tokenize(text):
    u"""可检索令牌 = 反引号片段 + 标识符 + 多位数 + 连续中文短语(>=3 字)。"""
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
    u"""去掉空白与常见分隔符 —— 吸收 `a = 1; b = 2` vs `a=1;b=2` 这类**纯书写形式**差异。"""
    return re.sub(u'[\\s;=,.\'"()\\[\\]:]', u'', text)


def relaxed_hit(tok, detail, detail_squashed=None):
    u"""宽式命中：raw / squashed / subphrase 三档，未命中返回 None。"""
    if tok in detail:
        return 'raw'
    if detail_squashed is not None:
        s = _squash(tok)
        if len(s) >= 3 and s in detail_squashed:
            return 'squashed'
    if _RE_CJK_SPLIT.sub('', tok) == tok and len(tok) >= 5:
        for i in range(0, len(tok) - 3):
            sub = tok[i:i + 4]
            if sub in detail:
                return 'subphrase:%s' % sub
    return None


# ---------------------------------------------------------------- 白名单（显式、可审计）
# 每条 = (为什么可以不在详版里原样出现, 锚点) —— 锚点必须真在详版里（M6c 校验）。
# ★ 第67轮只有 2 条：都是"**措辞被合并**"造成的碎片，语义并未丢（§62.9 / §63.15 有本体）。
#   `暂不接线` / `待落地` 这两个**状态口径变更**的旧说法已**显式下沉进 §63.15**（raw 命中），
#   所以它们**不需要**白名单 —— 白名单越短越好，长了就是变相宽恕。
WHITELIST = {
    u'轮四例自纠': (
        u'"第66轮四例自纠"已并入"第66/67轮判据侧自纠"；四条本体仍在详版 §62.9',
        u'四个自纠错'),
    u'例见详版': (
        u'是"另 2 例见详版 §62.9"的**指向短语**；指向本体仍在（§62.9 内文）',
        u'### 62.9'),
}

# 本轮**新增**令牌（必须出现在速查本里）
FORWARD = [
    u'§0–§63', u'已接线（§63', u'ghost_system', u'ghost_overlay',
    u'与 Kris 等人接触时长', u'Ralsei 特例恒暗档', u'方向相反',
    u'67 幽灵线接线', u'已落地（67轮', u'DPI 感知', u'产物侧看不见',
    u'tamper67', u'live67', u'soul_round55', u'§63.10',
]

# 负控制：伪造令牌（中文 + 代码型各一）。★ 换用**生僻字**（不撞任何正常措辞），
# 并在 M6b0 先自证夹具是"真阴性"（第66轮踩过：夹具串里含"在详版里"⇒ 必然命中 ⇒ 假报红）。
NEG_CJK = u'彘鬻鱻麤龘靐齉爩虪黐'
NEG_CODE = u'zzq_fabricated_token_67_never_exists'


def main():
    print(u'=' * 72)
    print(u'第67轮 记忆文件复检（速查本 vs 详版）')
    print(u'=' * 72)

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
    # ★ 容忍详版标题的 `§` 前缀（第66轮 M2 踩过："判据过窄 ⇒ 误报"）
    secs = [int(m.group(1)) for m in re.finditer(u'(?m)^#{2,3}\\s*§?(\\d+)\\b', detail)]
    real_max = max(secs) if secs else -1
    check(u'M2 头部段号 == 详版实际最大段号', head_sec == real_max and real_max > 0,
          u'头部 §0–§%d  详版 max = %d（容忍 `§` 前缀）' % (head_sec, real_max))

    # ------------------------------------------------------------ M3
    subs = re.findall(u'(?m)^###\\s+63\\.(\\d+)', detail)
    want = [str(i) for i in range(1, 16)]
    check(u'M3 详版 §63 小节 63.1~63.15 全在', sorted(set(subs), key=int) == want,
          u'实得 %s' % sorted(set(subs), key=int))

    # ------------------------------------------------------------ M4
    idx = quick.split(u'## 10.', 1)[-1].split(u'## 11.', 1)[0]
    m4_bits = [(t, t in idx) for t in (u'67', u'§63', u'幽灵线接线')]
    check(u'M4 §10 索引含 67 / §63 / 幽灵线接线', all(ok for _, ok in m4_bits),
          u' '.join(u'%s=%s' % (t, ok) for t, ok in m4_bits))

    # ------------------------------------------------------------ M5
    dec = quick.split(u'## 11.', 1)[-1]
    m5_bits = [
        (u'N1 接触时间', u'与 Kris 等人接触的时间' in dec),
        (u'N2 定点距离式', u'定点距离式' in dec),
        (u'N3 接线我定', u'接线 = 我定' in dec),
        (u'N4 已注册', u'跨作品 35 条' in dec and u'已注册' in dec),
        (u'①②③ 已落地', u'已落地（67轮' in dec),
    ]
    check(u'M5 §11 的 N1~N4 四条裁定 + 落地状态都在', all(ok for _, ok in m5_bits),
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
    check(u'M6a no-op 控制：自动命中数 > 0（判据确实在干活）', len(auto) > 0,
          u'自动命中 = %d' % len(auto))
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
        if u'\ufffd' in raw.decode('utf-8'):
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
    quick_secs = [int(m.group(1)) for m in re.finditer(u'(?m)^##\\s+(\\d+)\\.', quick)]
    glued = [i + 1 for i, l in enumerate(quick.split(u'\n')) if l.count(u'## ') > 1]
    check(u'M11 速查本 §0~§11 标题全在且严格递增、无粘连',
          quick_secs == list(range(12)) and not glued,
          u'实得 %s；粘连行 %s' % (quick_secs, glued or u'无'))

    # ------------------------------------------------- 第67轮专属：状态口径已翻转（含负控制）
    sec7 = quick.split(u'## 7.', 1)[-1].split(u'## 8.', 1)[0]
    check(u'M12 §7 幽灵线口径已翻转：含「已接线（§63」且**不再含**「暂不接线」',
          (u'已接线（§63' in sec7) and (u'暂不接线' not in sec7),
          u'新说法=%s 旧说法残留=%s' % (u'已接线（§63' in sec7, u'暂不接线' in sec7))
    sec3 = quick.split(u'## 3.', 1)[-1].split(u'## 4.', 1)[0]
    check(u'M13 §3 含本轮两条新教训（DPI 感知 / 产物侧看不见）',
          (u'DPI 感知' in sec3) and (u'产物侧看不见' in sec3),
          u'DPI=%s 产物侧=%s' % (u'DPI 感知' in sec3, u'产物侧看不见' in sec3))

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
    sys.exit(main())
