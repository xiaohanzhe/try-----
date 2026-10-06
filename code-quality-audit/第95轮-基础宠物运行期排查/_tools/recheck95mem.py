# -*- coding: utf-8 -*-
"""recheck95mem.py —— 记忆文件复检（第92轮收尾）

背景
----
第92轮把 `MEMORY.md`（速查本）压缩过一轮，把若干"原文"下沉到
`参考-契约与历轮（详版）.md`。记忆铁律要求压缩后必须做：
  ① 指针章节真的存在；
  ② 逐令牌回验（删掉的可检索令牌必须能在详版里找回来）；
  ③ 改动守恒（净减或不增，不借机塞新内容）。

本脚本把这三条变成**可复跑的判据**，另加一条**负控制**证明判据有鉴别力
（否则"全绿"可能只是判据恒真 —— 这是本项目反复栽过的地方）。

判据宽式声明（★ 判据过窄 = 会误报，见速查本 §4）
  - 指针匹配**不要求 `§` 字面量**：接受 `### 92.4` 这种小标题形式，
    也接受 `§87.10a` ↔ 详版 `### 87.10` + `（a）` 的**括号/后缀两种记法**。
  - **缩写令牌**（含 `…` `...` `<x>` `*` 等标记）按**标识符骨架**回验：
    把非标识符字符切掉，要求**每个**长度 ≥3 的片段都在详版里找到。
    ★ 这条只对**带缩写标记**的令牌开放 —— 普通标识符/路径仍须字面命中，
    否则像 `E:\Download\_tmp\` 这种分解后每段都常见的路径会被"假绿"放过。
  - **不吃行号**：所有输出都只打计数/名字，不打行号 —— 行号会随无关编辑漂移，
    让 sha256 每轮变，制造假 DIFF（第92轮实测过）。

★ 本脚本自己的 A/B（判据不是恒真）：
  修 MEMORY.md 的悬空指针**之前**跑，B1 必须报红（实测 `['87.10b','87.10c']`）；
  修完之后跑，B1 必须转绿。
  D 段的负控制令牌**运行时随机生成**（不写死字面量）—— 写死过一次，结果被
  "把令牌抄进详版做说明"这个动作污染、D1 立刻报红；生成式则永久免疫。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第92轮-宠物移动结算\\_tools\\recheck95mem.py
退出码 0 = 全绿；1 = 有 FAIL（会列出）。
"""
import io
import os
import random
import re
import subprocess
import sys
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(_HERE, '..', '..', '..')            # 仓库根
MEM_DIR = os.path.join(ROOT, '.workbuddy', 'memory')
CUR = os.path.join(MEM_DIR, 'MEMORY.md')
DET = os.path.join(MEM_DIR, '参考-契约与历轮（详版）.md')

# ★ 变异测试接缝（供 A/B 用）：只认**显式**给出的替代路径，
#   免得某个遗留环境变量悄悄把被测物换掉（第92轮 check92 同款纪律）。
if os.environ.get('RECHECK92MEM_CUR'):
    CUR = os.environ['RECHECK92MEM_CUR']

_FAILS = []
_N = [0]


def check(name, ok, detail=''):
    _N[0] += 1
    tag = 'OK  ' if ok else 'FAIL'
    print('[%s] %s%s' % (tag, name, ('  | ' + detail) if detail else ''))
    if not ok:
        _FAILS.append(name)


def read(p):
    # ★★★ 第95轮修正（真 bug）：A1 的 aj 体积判据必须**字节忠实**读。
    #   `io.open(..., encoding='utf-8')` 是**文本模式** ⇒ 通用换行会把 CRLF
    #   静默翻成 LF ⇒ `js_len` 少算「行数」个字符。
    #   ★ 第95轮**字节忠实复测**（以本轮为准）：该文件 `i/lf w/crlf`，
    #     磁盘态 CRLF **10,045** ↔ git 里的 LF blob **9,971**（差 74 = 行数）。
    #     注入器读的是**磁盘态** ⇒ 10,045 > 10,000 ⇒ 被砍尾
    #     （注入文本止于下标 9992）；而按 LF 口径看只有 9,971，"看着很安全"。
    #     （上一窗口笔记里的 10,040 与本轮实测差 5，属快照差异，已按实测校正。）
    #   ⇒ 真判据口径 = **原始字符数（含 CRLF）**，与注入器一致。
    return io.open(p, encoding='utf-8', newline='').read()


def norm(s):
    """供「跨版本比对」用（C2/E1）：两侧都归一到 LF，免得
       `git show`（LF）与工作区（CRLF）的行尾差被当成体积/内容变化。"""
    return s.replace('\r\n', '\n')


def js_len(s):
    """JS `String.prototype.length` = UTF-16 码元数（星平面算 2）。"""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def old_text():
    """基线里的速查本（压缩前）。取不到就返回 None（该项标 SKIP）。

    ★ 基线 ref 可用 `RECHECK92MEM_BASE` 指定（默认 `HEAD`）。
      为什么需要：做 A/B 时 `RECHECK92MEM_CUR` 指向"修复前"副本，若基线仍取 `HEAD`
      （= 已修复的提交），C2/E1 会变成"拿修复前跟修复后比" ⇒ 报出**与 A/B 无关的假红**。
      把 BASE 钉到修复前那个提交，两次都拿同一份内容做基线，A/B 才只暴露 B3。
    """
    ref = os.environ.get('RECHECK92MEM_BASE', 'HEAD')
    try:
        b = subprocess.run(
            ['git', '-c', 'core.quotepath=false', 'show',
             ref + ':.workbuddy/memory/MEMORY.md'],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if b.returncode != 0:
            return None
        return b.stdout.decode('utf-8')
    except Exception:
        return None


# ---------------------------------------------------------------- 令牌抽取
_TOKEN_RE = re.compile(
    r'`[^`\n]{2,60}`'                       # 反引号内
    r'|§[0-9]+(?:\.[0-9]+)?[a-c]?'          # § 指针
    r'|\b[0-9][0-9,]{1,12}(?:\.[0-9]+)?%?\b'  # 数字 / 千分位 / 百分比
)


def tokens(s):
    out = set()
    for t in _TOKEN_RE.findall(s):
        t = t.strip('`')
        if len(t) >= 3:
            out.add(t)
    return out


# ---------------------------------------------------------------- 宽式解析
def _heads(det):
    return [l for l in det.split('\n') if l.lstrip().startswith('#')]


def resolve_ptr(core, heads, det):
    """指针解析。返回 `<How>|<数字节>`：
      'none'                         ⇒ 悬空
      'heading|87.10'                ⇒ 详版有独立小标题
      'label|87.10'                  ⇒ 只在 §87.10 段里以 `（c）` 这种**标签**存在
    ★ 两种都算"能落地"，但只有前者允许速查本写成 `§87.10c`（见 B3）。
    ★★ 数字节必须是**多级**（`23.13.1` 这种三层指针真存在：
       详版 `#### §23.13.1`）。**只允许一级小数点 ⇒ 会把 §23.13.1 误报悬空**
       —— 第一版就是这么假红的（判据过窄，见速查本 §4）。
    """
    c = re.sub(r'[()\s]', '', core)
    m = re.match(r'^(\d+(?:\.\d+)*)([a-c])?$', c)
    if not m:
        return 'none'
    p, suf = m.group(1), m.group(2)
    pat = re.compile(r'^#{1,6}\s*§?\s*' + re.escape(p) + r'(?!\d)')
    heading_on_p = any(pat.match(h) for h in heads)
    if not suf:
        return ('heading|' + p) if heading_on_p else 'none'
    pat_suf = re.compile(r'^#{1,6}\s*§?\s*' + re.escape(p + suf) + r'(?!\d)')
    if any(pat_suf.match(h) for h in heads):
        return 'heading|' + p + suf
    if heading_on_p and (('(%s)' % suf) in det or ('（%s）' % suf) in det):
        return 'label|' + p
    return 'none'


_ABBR = ('…', '...', '<', '>', '*')


def in_det(t, det, heads):
    """令牌能否在详版里回验（宽式，但**收紧到必要范围**）。"""
    if t in det:
        return True
    if t.startswith('§') and resolve_ptr(t.lstrip('§').strip(), heads, det) != 'none':
        return True
    # 仅对**带缩写标记**的令牌退到"标识符骨架"回验
    if any(a in t for a in _ABBR):
        runs = [r for r in re.split(r'[^0-9A-Za-z_.]+', t) if len(r) >= 3]
        if runs and all(r in det for r in runs):
            return True
    return False


# ---------------------------------------------------------------- 人工令牌表
# 摘要里点名的"必须能找回来"的令牌（与自动差分互为双保险）。
HAND = [
    '14,658,588', 'DELTARUNE_183049', 'UndertaleModCli', '__OUTDIR__',
    'undertale.apk', 'data.win',
    'floor_visible_contains', '_fall_reason', 'climb_1_', 'climb_0_',
    'HERMETIC_IDS', 'save_baseline', "'[PASS] %s'", 'learn_new_skill',
    '_on_ai_reply', 'reset_special_states', 'pet_interaction',
    'ralsei:v4', 'NUM_PARALLEL', 'keep_alive', '8.3%', '1,251',
    'RalseiMemory', 'RalseiPetMutex', '_virtual_screen_rect',
    'availableGeometry', 'WindowStaysOnTopHint', 'data_store',
    '_CTL_ALLOWED', 'round5_smoke', 'surrogateescape', 'pathfind_round45',
    'Errno 22', '_placement.json', 'POSSESSION_KINDS', 'KIND_CONSENT',
    'npc_speak', 'AI_REPLY_MAX_CHARS', 'ralsei_persona.md',
    '_clean_ai_reply', 'fit_scale', 'world_gate', 'by_source', 'home_of',
    'outertale_pending', 'gml65ut', 'occluded', 'PrintWindow',
    'PW_RENDERFULLCONTENT', 'BitBlt', 'walk_down', 'deltarune_ralsei',
    '9ebb41f', 'check92', 'mutate92', 'recheck92', 'check87', 'check85',
    'check86', 'check79',
    # 第92轮新增（本轮产物，必须双写）
    '_subpixel_x', '_subpixel_y', '_speed_pos', '3.9', '102.3', '91.9%',
    # 第93轮产物
    'pick_corner_screen_work_area', 'availableGeometry', 'check93',
    'climb_1_', 'handle_jump', '2410,1378', '650,450',
    # 第94轮产物
    'is_sleeping_walk', 'walk_down_sleep', 'check94', 'mutate94', 'recheck94',
    'pet_ai', 'drag_position', 'dedb799', '4577',
    # 第95轮产物
    'newline=', 'recheck95mem', 'walk_right_sleep',
    # 第95轮·第二批产物（走路朝向角度分档 · check94 行号 · 收尾）
    'recon95_move', 'atan2(1113,1283)', '-45/45/135', '40.9',
    'check95_AB', 'g2_95_final', 'move_log.txt', 'geometry.jsonl',
]

# 负控制：**运行时生成**（见 D 段）。★ 不写死字面量 —— 写死了就会被
# "把它抄进说明文档"这一动作污染（本轮实测：抄进详版 §92.7 后 D1 立刻报红）。


def main():
    mem = read(CUR)
    det = read(DET)

    print('=' * 78)
    print('A. 体积 / 编码（速查本）')
    print('=' * 78)
    print('路径 = %s' % CUR)
    n_chars = len(mem)
    n_js = js_len(mem)
    n_bytes = len(mem.encode('utf-8'))
    limit = 10000
    check('A1 注入上限按 **原始字符数（含 CRLF）** 判定 —— 与注入器同口径',
          0 < n_js <= limit, 'js_len=%d  chars=%d  bytes=%d  余量=%+d'
          % (n_js, n_chars, n_bytes, limit - n_js))
    check('A2 无 BOM', not mem.startswith('\ufeff'))
    check('A3 无 U+FFFD（编码损坏标记）', '\ufffd' not in mem)
    check('A4 无截断尾巴（结尾是完整行）', mem.endswith('\n'))

    print()
    print('=' * 78)
    print('B. 指针章节真的存在（宽式：§ 可选 / 小标题也算）')
    print('=' * 78)
    heads = _heads(det)
    raw = re.findall(r'§[0-9]+(?:\.[0-9]+)*(?:\([a-c]\)|[a-c])?', mem)
    ptrs = sorted(set(raw))
    dangling = []
    for p in ptrs:
        if resolve_ptr(p.lstrip('§'), heads, det) == 'none':
            dangling.append(p)
    check('B1 速查本中每个 § 指针都能在详版里落地',
          not dangling, '指针总数=%d 悬空=%s' % (len(ptrs), dangling or '无'))
    check('B2 指针总量达到预期规模（没被压成空指针）',
          len(ptrs) >= 60, '指针总数=%d' % len(ptrs))
    # B3 ★ 记法一致性：详版用「小标题 §87.10 + 段内标签（c）」时，
    #    速查本不许写成 `§87.10c`（会被误读成存在独立小标题 87.10c）。
    bad_form = []
    for p in ptrs:
        m = re.match(r'^§(\d+(?:\.\d+)*)([a-c])$', p)   # 裸后缀（无括号）
        if not m:
            continue
        how = resolve_ptr(m.group(1) + m.group(2), heads, det)
        if how.startswith('label|'):
            bad_form.append(p)
    check('B3 指针记法与详版一致（标签式必须带括号：`§87.10(c)`）',
          not bad_form, '非规范写法=%s' % (bad_form or '无'))

    print()
    print('=' * 78)
    print('C. 逐令牌回验（人工表 + 自动差分）')
    print('=' * 78)
    both = in_mem_only = det_only = nowhere = 0
    det_only_list = []
    bad = []
    for t in HAND:
        a = t in mem
        b = in_det(t, det, heads)
        if a and b:
            both += 1
        elif a:
            in_mem_only += 1
        elif b:
            det_only += 1
            det_only_list.append(t)
        else:
            nowhere += 1
            bad.append(t)
    check('C1 人工令牌表：全部可在「速查本 ∪ 详版」中回验',
          not bad, '共%d项  双命中=%d  仅速查本=%d  仅详版(已下沉)=%d  两处皆无=%d'
          % (len(HAND), both, in_mem_only, det_only, nowhere))
    if bad:
        print('     两处皆无 = %s' % bad)
    if det_only_list:
        print('     仅在详版（= 确实下沉了，不是丢了）= %s' % det_only_list)

    old = old_text()
    if old is None:
        print('[SKIP] C2 自动差分：取不到 HEAD 版本速查本')
    else:
        removed = sorted(tokens(norm(old)) - tokens(norm(mem)))
        lost = [t for t in removed if not in_det(t, det, heads)]
        check('C2 自动差分：HEAD → 现在，被移除的令牌无一丢失（都在详版）',
              not lost, '移除令牌=%d  丢=%d%s'
              % (len(removed), len(lost), ('  ' + str(lost)) if lost else ''))
        print('     （移除令牌样例：%s）' % ', '.join(removed[:12]))

    print()
    print('=' * 78)
    print('D. 负控制（证明判据不是恒真）')
    print('=' * 78)
    # ★★ 负控制令牌**运行时生成**，不写死字面量。
    #    原因（本轮实测踩到）：负控制写了字面量 ⇒ 后来把它写进详版做说明
    #    ⇒ D1 立刻"误命中"报红 —— **文档自污染了控制组**。
    #    生成式令牌不可能出现在文档里 ⇒ 判据永久免疫这类污染。
    neg_s = 'zz' + uuid.uuid4().hex[:14] + '92'
    neg_p = '§9%04d.9' % random.randint(0, 9999)
    neg_hit = [t for t in (neg_s, neg_p)
               if (t in mem) or in_det(t, det, heads)]
    check('D1 生成式编造令牌在两侧都找不到 ⇒ 判据有鉴别力',
          not neg_hit, '负控制=%s  误命中=%s' % ((neg_s, neg_p), neg_hit or '无'))
    check('D2 正控制：已确证存在的令牌必须命中',
          ('_subpixel_x' in mem or '_subpixel_x' in det)
          and ('check92' in mem or 'check92' in det))
    # D3 直接对**判据函数**下断言（不经过报告层）：编造输入必须返 False。
    check('D3 判据函数本身可判否（`in_det` 对编造输入返 False）',
          in_det(neg_s, det, heads) is False
          and in_det(neg_p, det, heads) is False
          and resolve_ptr('9999.9', heads, det) == 'none',
          'in_det 直接调用返回 False ×2 · resolve_ptr=none')

    print()
    print('=' * 78)
    print('E. 改动守恒（净减或持平，不借机塞新内容）')
    print('=' * 78)
    if old is None:
        print('[SKIP] E1 取不到 HEAD 版本，无法比对')
    else:
        o_n, m_n = norm(old), norm(mem)
        d_js = js_len(m_n) - js_len(o_n)
        check('E1 速查本体积相对于 HEAD **净减或持平**（两侧归一到 LF 后比）',
              d_js <= 0, 'HEAD js_len(LF)=%d → 现在=%d  Δ=%+d'
              % (js_len(o_n), js_len(m_n), d_js))
        added = sorted(t for t in (tokens(norm(mem)) - tokens(norm(old)))
                       if t not in det)
        check('E2 新增令牌必须都是"本轮产物"或能在详版自证',
              all(('92' in t) or in_det(t, det, heads) for t in added),
              '新增令牌=%d' % len(added))
        if added:
            print('     新增令牌 = %s' % added)

    print()
    print('=' * 78)
    print('合计 %d 条判据，FAIL = %d' % (_N[0], len(_FAILS)))
    if _FAILS:
        print('FAIL 明细：')
        for f in _FAILS:
            print('  - %s' % f)
    print('=' * 78)
    return 1 if _FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
