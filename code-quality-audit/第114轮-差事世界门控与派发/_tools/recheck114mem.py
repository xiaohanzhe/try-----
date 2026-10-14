# -*- coding: utf-8 -*-
"""第114轮 · 记忆三件复检（skills: core-file-recheck + agent-memory-compaction）。

改过「重要核心文件」（速查本 `MEMORY.md` + 详版 `参考-契约与历轮（详版）.md`）⇒ 逐项复检。

判据
----
P1 结构：速查本所有 `## N.` 标题都在、无粘连；详版新增 `## §114` **恰一处**、排在 §113 之后、四个小节都在。
P2 体积：速查本 **JS 长度（UTF-16 码元） ≤ 10000**（`check95 A2` 硬闸）且有正向余量。
P3 编码：两文件 **无 BOM / 无 U+FFFD / 全 LF**（本仓记忆文件一律 LF）。
P4 ★★★ **逐令牌回验**（本套件的核心）：`tokenize(HEAD 版速查本) − tokenize(现盘速查本)`
    —— 每个被删掉的令牌都必须有归宿，否则 = 静默丢信息。三种归宿：
      ① **三级命中**：raw（整串逐字）→ norm（去空白/标点归一）→ sub（连续中文 ≥4 字子短语）；
      ② **别名锚点**：措辞改了，但语义在详版 —— 必须绑定一个**确实存在于详版**的锚点串
         （★ 锚点由 P4c 逐个回验 ⇒ 不是白名单放行：详版一旦丢了锚点，本套件立刻报红）；
      ③ **合理消失**：显式列出并写明理由（内部交叉引用 / 已解决的遗留 / 纯括注）。
    ★ 负控制：塞一个详版**没有**的令牌再删 ⇒ 必须被报出。
    ★ 正控制：塞一个详版**有**的令牌再删 ⇒ **不**得误报。
P5 恒真判据复查：本文件里**没有** `check(名字, True)` 这种恒真写法（★ 用 **AST**，
   不扫文本 —— 本文件的 docstring 里就写着这个词，裸正则扫到自己 ⇒ 本项目已第五次踩）。
P6 ★ 判据自身体检：提取器/命中器对**合成样本**真的有鉴别力（防"提取器坏了 ⇒ 全绿"）。

跑法：`C:\\Python311\\python.exe recheck114mem.py`
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

MEMDIR = os.path.join(ROOT, '.workbuddy', 'memory')
QUICK = os.path.join(MEMDIR, 'MEMORY.md')
DETAIL = os.path.join(MEMDIR, '参考-契约与历轮（详版）.md')

_N = {'p': 0, 'f': 0}
_OUT = []


def check(name, cond, detail=''):
    ok = bool(cond)
    _N['p' if ok else 'f'] += 1
    line = u'[%s] %s' % ('PASS' if ok else 'FAIL', name)
    if detail:
        line += u'  <- %s' % detail
    _OUT.append(line)
    print(line)
    return ok


def sec(t):
    _OUT.append(u'')
    _OUT.append(t)
    print(t)


def rdc(p):
    """★ 字节忠实：`newline=''`（契约：open() 默认会把 \\r\\n 归一化掉）。"""
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def js_len(s):
    """JS 字符串长度 = **UTF-16 码元数**（`check95 A2` 的真口径）。"""
    return len(s.encode('utf-16-le')) // 2


def head_version(path_rel):
    try:
        out = subprocess.run(
            ['git', 'show', 'HEAD:%s' % path_rel],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if out.returncode != 0:
            return None
        return out.stdout.decode('utf-8', 'surrogateescape')
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 令牌提取器（四类：反引号片段 / 连续中文≥4 / ASCII 标识符≥5 / 数字≥4）
# ---------------------------------------------------------------------------
_RE_BT = re.compile(u'`([^`\n]{2,60})`')
_RE_CJK = re.compile(u'[\u4e00-\u9fff]{4,}')
_RE_ASCII = re.compile(u'[A-Za-z_][A-Za-z0-9_]{4,}')
_RE_NUM = re.compile(u'[0-9][0-9,]{3,}')

_RE_NOISE = re.compile(
    u'[\\s\u3000`~!@#$%^&*()+\\-=\\[\\]{}\\\\|;:\'",.<>/?'
    u'\u3001\u3002\uff0c\uff1b\uff1a\uff08\uff09\u300a\u300b\u3010\u3011'
    u'\u2018\u2019\u201c\u201d\u2014\u2013\u00b7\uff01\uff1f\uff5c\uff0f]+')


def tokens(s):
    t = set()
    for m in _RE_BT.finditer(s):
        t.add(m.group(1).strip())
    for m in _RE_CJK.finditer(s):
        t.add(m.group(0))
    for m in _RE_ASCII.finditer(s):
        t.add(m.group(0))
    for m in _RE_NUM.finditer(s):
        t.add(m.group(0))
    return t


def hits(tok, det):
    """★ 三级命中：raw（整串逐字）→ norm（归一后整串）→ sub（连续中文 ≥4 字子短语）。"""
    if tok in det:
        return u'raw'
    n = _RE_NOISE.sub(u'', tok)
    if len(n) >= 4 and n in _RE_NOISE.sub(u'', det):
        return u'norm'
    for m in _RE_CJK.finditer(tok):
        if m.group(0) in det:
            return u'sub'
    return u''


# ★★ 措辞被压缩、但语义仍在详版 ⇒ 绑定**锚点串**（P4c 会逐个回验锚点真的在详版）
_REWORDED = {
    u'不自算不存盘': u'也不自己存盘',
    u'与原版逐像素等价': u'逐像素',
    u'倍率真源只一处': u'两份真源',
    u'偏移按半屏算': u'相对半块屏',
    u'幂等唯一正解': u'基准快照',
    u'灵魂减半': u'灵魂尺寸减半',
    u'画面砍半': u'画面比例砍半',
    u'真机抓帧活': u'真机抓帧抓出的画布活 bug',
    u'缩放方向': u'camera.scale = out_w',
    u'覆盖前面': u'后写覆盖前写',
    u'逐个下发': u'统一下发',
    u'非桌面黑边': u'非桌面场景铺黑',
    u'两消费面': u'消费面',
    u'家三连彩蛋': u'三连确认',
}

# ★★ 合理消失（逐条理由）
_GONE = {
    u'现口径见续四': u'速查本内部交叉引用（指向 §112续四），不是知识令牌',
    u'剩派发入口': u'§113 遗留项：派发入口本轮已落地 ⇒ 该遗留说明理应消失',
    u'自动满足': u'「隐字母（自动满足）」的括注；真令牌 隐字母 仍留在速查本 §19',
}


# ---------------------------------------------------------------------------
sec(u'=== P0. 前置：文件在盘 ===')
check(u'P0a 速查本在盘', os.path.isfile(QUICK), QUICK)
check(u'P0b 详版在盘', os.path.isfile(DETAIL), DETAIL)
_q = rdc(QUICK)
_d = rdc(DETAIL)
_old = head_version('.workbuddy/memory/MEMORY.md')
check(u'P0c 取得到 HEAD 版速查本（逐令牌回验的基准）',
      bool(_old) and len(_old) > 5000,
      u'chars=%d' % (len(_old) if _old else -1))
check(u'P0d 现盘速查本确实**改过**（不是没保存）',
      bool(_old) and _old != _q,
      u'HEAD=%d 现盘=%d 字符' % (len(_old or u''), len(_q)))

# ---------------------------------------------------------------------------
sec(u'=== P1. 结构 ===')
_ids = [int(re.match(u'^(\\d+)\\.', h).group(1))
        for h in re.findall(u'(?m)^## (.+)$', _q)
        if re.match(u'^(\\d+)\\.', h)]
check(u'P1a 速查本 `## N.` 标题数 ≥ 12', len(_ids) >= 12, u'n=%d' % len(_ids))
check(u'P1b 速查本标题序号**无重复**（重复 = 合并时粘了）',
      len(_ids) == len(set(_ids)), u'ids=%s' % _ids)
check(u'P1c ★ 本轮新增 `## 20.` 恰一处',
      _q.count(u'\n## 20.') == 1, u'n=%d' % _q.count(u'\n## 20.'))
check(u'P1d ★★ 详版 `## §114` 恰一处',
      _d.count(u'## §114') == 1, u'n=%d' % _d.count(u'## §114'))
check(u'P1e ★ 速查本里没有"标题粘在正文里"（`## ` 一律行首）',
      not re.search(u'(?m)^[^\\n]{3,}## \\d+\\.', _q))
_i113 = _d.find(u'## §113')
_i114 = _d.find(u'## §114')
check(u'P1f ★ §114 排在 §113 **之后**（追加而非插队）',
      0 <= _i113 < _i114, u'i113=%d i114=%d' % (_i113, _i114))
# ★ 只在 §114 段内找小节（否则命中的是前面章节里的同名串 —— 第一版就栽在这）
_tail114 = _d[_i114:] if _i114 >= 0 else u''
for _k in (u'用户口径', u'世界门控', u'跨作品章名两套写法', u'独立落盘'):
    check(u'P1g ★★ §114 段内有小节「%s」' % _k, _k in _tail114)

# ---------------------------------------------------------------------------
sec(u'=== P2. 体积（`check95 A2` 硬闸：JS 长度 ≤ 10000）===')
_n = js_len(_q)
check(u'P2a ★★★ 速查本 JS 长度 ≤ 10000', _n <= 10000, u'js_len=%d' % _n)
check(u'P2b ★ 余量 ≥ 10（留一点下次可用）', 10000 - _n >= 10, u'余量=%d' % (10000 - _n))
# ★ 门槛按 **JS 码元** 设（第一版误按 UTF-8 字节设 90 万 ⇒ 假红：中文 1 字 = 3 字节但只 1 码元）
check(u'P2c ★ 详版仍在（没被压成 0）', js_len(_d) > 400000,
      u'js_len=%d' % js_len(_d))

# ---------------------------------------------------------------------------
sec(u'=== P3. 编码 ===')
for _nm, _s in ((u'速查本', _q), (u'详版', _d)):
    check(u'P3a %s 无 BOM' % _nm, not _s.startswith(u'\ufeff'))
    check(u'P3b %s 无 U+FFFD（乱码替换符）' % _nm, u'\ufffd' not in _s)
    check(u'P3c %s 全 LF（无 CRLF）' % _nm, _s.count(u'\r\n') == 0,
          u'CRLF=%d' % _s.count(u'\r\n'))

# ---------------------------------------------------------------------------
sec(u'=== P4. ★★★ 逐令牌回验（删掉的必须有归宿）===')
check(u'P4a ★★ 每个"别名锚点"都**真的在详版**（锚点腐烂 ⇒ 立刻报红，不是白名单放行）',
      all(a in _d for a in _REWORDED.values()),
      u'锚点 %d 个｜缺失=%s'
      % (len(_REWORDED),
         repr([a for a in _REWORDED.values() if a not in _d]) or u'无'))

if not _old:
    check(u'P4b 取到 HEAD 版速查本', False)
    _removed, _miss = [], [u'<无基准>']
else:
    _removed = sorted(t for t in (tokens(_old) - tokens(_q)) if len(t) >= 3)
    _tiers, _miss = {}, []
    for t in _removed:
        if t in _GONE:
            _tiers[t] = u'gone'
            continue
        h = hits(t, _d)
        if not h and t in _REWORDED:
            h = u'reworded'
        _tiers[t] = h or u'MISS'
        if not h:
            _miss.append(t)
    _cnt = {}
    for v in _tiers.values():
        _cnt[v] = _cnt.get(v, 0) + 1
    check(u'P4b ★★★ 被删令牌**全部**有归宿（命中 / 别名锚点 / 合理消失）',
          not _miss,
          u'删了 %d 个｜raw=%d norm=%d sub=%d 锚点=%d 合理消失=%d｜**缺 %d**%s'
          % (len(_removed), _cnt.get(u'raw', 0), _cnt.get(u'norm', 0),
             _cnt.get(u'sub', 0), _cnt.get(u'reworded', 0),
             _cnt.get(u'gone', 0), len(_miss),
             (u'｜缺=' + repr(_miss[:12])) if _miss else u''))
    check(u'P4c ★★ "合理消失"是**有限**的（≤3 条 ⇒ 没被当成垃圾桶）',
          _cnt.get(u'gone', 0) <= 3, u'gone=%d' % _cnt.get(u'gone', 0))
    check(u'P4d ★★ 绝大多数是**逐字**命中（raw+norm 占多数，不是全靠宽松匹配）',
          (_cnt.get(u'raw', 0) + _cnt.get(u'norm', 0)) >= int(len(_removed) * 0.5),
          u'raw+norm=%d / %d' % (_cnt.get(u'raw', 0) + _cnt.get(u'norm', 0),
                                 len(_removed)))
    # ★★ 负控制：**详版没有**的令牌若被删 ⇒ 必须被抓到（证明 P4b 非恒真）
    #   ⚠️ 探针只能加在"基准侧"（HEAD）—— 第一版两边都加 ⇒ 相减后归零 ⇒ 负控制恒绿（假绿）
    _probe = u'ZZ_114_详版绝对没有的令牌_ZZ'
    _rem2 = (tokens(_old + u'\n' + _probe) - tokens(_q))
    _miss2 = [t for t in _rem2 if len(t) >= 3 and t not in _GONE
              and not hits(t, _d) and t not in _REWORDED]
    # 判据：从探针里**派生出来的**令牌（而非探针整串）必须被判缺
    check(u'P4e ★负控制：详版里**没有**的令牌一旦被删 ⇒ 必被报出',
          any(u'详版绝对没有' in t for t in _miss2),
          u'构造探针=%s｜判缺样本=%s'
          % (_probe, repr([t for t in _miss2 if u'详版绝对没有' in t]) or u'无'))
    # ★ 正控制：**详版有**的令牌被删 ⇒ 不得误报
    _probe2 = u'world_gate'
    _rem3 = (tokens(_old + u'\n' + _probe2) - tokens(_q))
    _miss3 = [t for t in _rem3 if len(t) >= 3 and t not in _GONE
              and not hits(t, _d) and t not in _REWORDED]
    check(u'P4f ★正控制：详版里**有**的令牌被删 ⇒ 不误报',
          u'world_gate' not in _miss3,
          u'构造探针=%s｜被判缺=%s' % (_probe2, u'是' if u'world_gate' in _miss3 else u'否'))
    _OUT.append(u'    （删掉的令牌命中级别：raw=%d norm=%d sub=%d 锚点=%d 合理消失=%d）'
                % (_cnt.get(u'raw', 0), _cnt.get(u'norm', 0), _cnt.get(u'sub', 0),
                   _cnt.get(u'reworded', 0), _cnt.get(u'gone', 0)))
    _OUT.append(u'    （别名锚点表 —— 每个都已在详版回验在盘：）')
    for _k, _v in sorted(_REWORDED.items()):
        _OUT.append(u'      · %s  ←  详版锚点「%s」' % (_k, _v))
    _OUT.append(u'    （合理消失表 —— 逐条理由：）')
    for _k, _v in sorted(_GONE.items()):
        _OUT.append(u'      · %s —— %s' % (_k, _v))

# ---------------------------------------------------------------------------
sec(u'=== P5. 恒真判据复查（★ 走 AST，不扫文本）===')
_self_src = rdc(os.path.abspath(__file__))
_tree = None
try:
    _tree = ast.parse(_self_src)
except SyntaxError as _e:
    _tree = None
    check(u'P5a 前置：本文件可被 ast.parse', False, repr(_e))
check(u'P5a 前置：本文件可被 ast.parse（解析成功）', _tree is not None)
if _tree is not None:
    _true_calls, _nck, _names = [], 0, []
    for _nd in ast.walk(_tree):
        if isinstance(_nd, ast.Call) and isinstance(_nd.func, ast.Name) \
                and _nd.func.id == 'check':
            _nck += 1
            if len(_nd.args) >= 2 and isinstance(_nd.args[1], ast.Constant) \
                    and _nd.args[1].value is True:
                _true_calls.append(_nd.lineno)
            if _nd.args and isinstance(_nd.args[0], ast.Constant) \
                    and isinstance(_nd.args[0].value, str):
                _names.append(_nd.args[0].value)
    check(u'P5b ★★ 本文件里没有 `check(名字, True)` 这种恒真写法'
          u'（源码里"写着这几个字"不算 —— 只看 AST 真调用）',
          not _true_calls, u'恒真调用行号=%s' % (_true_calls or u'无'))
    check(u'P5c 判据数经 AST 数得 ≥ 12（防"写了没调"）', _nck >= 12, u'n=%d' % _nck)
    _dups = sorted(set(x for x in _names if _names.count(x) > 1))
    check(u'P5d 判据名无重复', not _dups, u'dup=%s' % (_dups or u'无'))

# ---------------------------------------------------------------------------
sec(u'=== P6. 判据自身体检：提取器/命中器真有鉴别力 ===')
_ts = tokens(u'这是样本 `world_gate` 与 assign_errand 以及 123456 都在')
check(u'P6a 反引号令牌提得到', u'world_gate' in _ts)
check(u'P6b ASCII 标识符提得到', u'assign_errand' in _ts)
check(u'P6c 中文长串提得到', u'这是样本' in _ts)
check(u'P6d 数字串提得到', u'123456' in _ts)
check(u'P6e ★ `hits()` 有鉴别力（同一串在"详版有/详版无"两份文本上结论必须相反）',
      bool(hits(u'world_gate', _d)) and not hits(u'ZZ_114_绝无此串_ZZ', _d),
      u'有=%s｜无=%s'
      % (hits(u'world_gate', _d) or u'空', hits(u'ZZ_114_绝无此串_ZZ', _d) or u'空'))

# ---------------------------------------------------------------------------
print(u'')
print(u'=' * 70)
print(u'recheck114mem  结论：%d PASS / %d FAIL' % (_N['p'], _N['f']))
_ep = os.path.join(HERE, '..', '_evidence', 'recheck114mem.txt')
try:
    with io.open(_ep, 'w', encoding='utf-8', newline='') as fh:
        fh.write(u'\n'.join(_OUT) + u'\n')
    print(u'报告 = %s' % os.path.abspath(_ep))
except Exception as e:
    print(u'（报告落盘失败：%r）' % (e,))
sys.exit(1 if _N['f'] else 0)
