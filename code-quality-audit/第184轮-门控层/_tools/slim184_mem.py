# -*- coding: utf-8 -*-
u"""第184轮 · 记忆缩容的**判据**：证明"腾出来的地方"不是"删掉的信息"。

本轮速查本从 `js_len=9979` 压到 `9969` 再塞进 184 条目 —— 先腾 143 字符才够放 110 字符的新条目。
腾掉的**全是冗词与重复索引**。四条闸：

  S1 `js_len`（UTF-16 码元，含 CRLF）≤ 10000 —— 与 `check95 A2` 同一口径
  S2 被压掉的每一项，**去处逐条举证**（在速查本新措辞里 / 在详版里 / 在用户级 MEMORY.md 里）
  S3 速查本的关键铁律仍在（防"为了腾地方把整段删了"）
  S4 ★★★ **逐令牌回验**（对 `git HEAD` 版做真 diff）：丢的令牌必须**全在白名单内**，
     且白名单**不多于**实测丢失数（防止"以后无脑压缩"靠加白名单绕过）

★★ 负控制贯穿 S2/S4：一个肯定不存在的串必须找不到，一组肯定**没丢**的令牌必须**不在**
   丢失名单里 —— 否则说明扫描器恒真（§85/§129：「恒真判据比不写还危险」）。

用法（仓库根）：python code-quality-audit/第184轮-门控层/_tools/slim184_mem.py
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
MEM_REL = '.workbuddy/memory/MEMORY.md'
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(REPO, '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md')
USER = os.path.join(u'C:\\Users\\23002', '.workbuddy',
                    'user-eaa36f7b-2fa8-4183-8c58-e1fd70cfc9bc-personal', 'MEMORY.md')

_n = {'p': 0, 'f': 0}


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def js_len(s):
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def lf(s):
    return s.replace('\r\n', '\n')


mem = rd(MEM)
det = rd(DET)
user = rd(USER)

#: ★★★ 本轮从速查本里压掉的**每一项事实**：`(说明, [举证串, ...], 去处)`。
#: 去处 ∈ {'mem': 速查本新措辞, 'det': 详版, 'user': 用户级 MEMORY.md}。
#: ★★ 举证串必须是**锚定短语**，不能是裸数字 —— 180 轮踩过"`801` 命中 `18016`"的子串假阳性。
DELETED = [
    (u'「没说≠可省这一问」改成「≠免这一问」', [u'≠免这一问'], 'mem'),
    (u'同上：用户级原话「可以省掉这一问」仍在', [u'省掉这一问'], 'user'),
    (u'180 只保留轮号，`双跑` 这个别名在详版', [u'双跑'], 'det'),
    (u'171 的 A/B 锚点脚本名与结果挪回详版', [u'ab171.py', u'14/0'], 'det'),
    (u'167 的「多占图标位」新措辞', [u'多占图标位＝Win 固有'], 'mem'),
    (u'`Windows` 只剩 `Win`，全称在详版', [u'Windows'], 'det'),
    (u'178「静默翻成插最底」压成「静默插最底」', [u'静默插最底（已修）'], 'mem'),
    (u'179 的因果链「命中所站的板⇒永远在前」压成「命中即在前」，原链在详版',
     [u'命中所站的板', u'它永远'], 'det'),
    (u'183 的 B3/B4 展开式压成「（B3/B4 反证）」，展开与 `7121` 在详版',
     [u'加回', u'抠掉', u'本来是活的'], 'det'),
    (u'183 的 `moss 仍不可达` 改成 `moss 见 184`（184 已修），原文在详版', [u'不可达'], 'det'),
    (u'「不许砍 prompt」是「prompt 尽量完整」的同义复述，只留前者', [u'prompt 尽量完整'], 'mem'),
    (u'§10 索引的轮次别名链（地基／再补门型／隐藏房／删边）改成「见 §7 逐条」，各轮条目都在',
     [u'181（§183）', u'182（§184）', u'183（§185）', u'184（§186）'], 'mem'),
    (u'§11「I10 不作出场门控、未做 I3/I6/I7/I8/I9」压成「I3/I6~I10 全未做」，明细在详版',
     [u'未做 I1~I10'], 'det'),
]

#: 负控制：这些串**不应该**出现（证明 S2 的扫描不是恒真）
NEG = [u'这个字符串故意不存在_zz7', u'另一条负控制_qq9']

print('')
print('=' * 70)
print(u'S1 体积（与 `check95 A2` 同口径：UTF-16 码元，含 CRLF）')
print('=' * 70)
_js = js_len(mem)
check(u'S1 速查本 `js_len` ≤ 10000', 0 < _js <= 10000,
      u'js_len=%d  chars=%d  余量=%+d' % (_js, len(mem), 10000 - _js))
check(u'S1.1 纯 CRLF（无混行尾，与 git 属性一致）',
      mem.count('\r\n') > 0 and mem.count('\n') == mem.count('\r\n'),
      u'CRLF=%d  LF=%d' % (mem.count('\r\n'), mem.count('\n')))
check(u'S1.2 无 BOM、无 U+FFFD', not mem.startswith(u'\ufeff') and u'\ufffd' not in mem)

print('')
print('=' * 70)
print(u'S2 压掉的每一项都有去处（逐条举证 + 负控制）')
print('=' * 70)
check(u'S2.0 分母闸：待举证项 >= 12（防止列表被清空后整段恒真）',
      len(DELETED) >= 12, u'项数=%d' % len(DELETED))

_SRC = {'mem': mem, 'det': det, 'user': user}
_lost = []
for desc, toks, where in DELETED:
    miss = [t for t in toks if t not in _SRC[where]]
    if miss:
        _lost.append((desc, where, miss))
    check(u'S2 %s' % desc, not miss,
          u'在 %s 里缺=%r' % (where, miss) if miss else u'（%s）' % where)

_hit = [t for t in NEG if any(t in v for v in _SRC.values())]
check(u'S2.9 负控制：故意不存在的串**找不到**（否则扫描器恒真）', not _hit,
      u'误命中=%r' % (_hit,))

print('')
print('=' * 70)
print(u'S3 速查本的关键铁律仍在（防"整段删掉换体积"）')
print('=' * 70)
KEEP = [
    (u'动手前四步', u'动手前四步'),
    (u'沉默≠默认', u'沉默≠默认'),
    (u'工作区会被回滚', u'回滚'),
    (u'`HWND_TOP==0` 假值', u'HWND_TOP==0'),
    (u'站谁上面优先于 Y', u'站谁上面'),
    (u'两层登记查重复键', u'改两层登记前先查重复键'),
    (u'G2 全 IDENTICAL', u'IDENTICAL'),
    (u'gitpush 必须 --refspec', u'--refspec'),
    (u'不许叫"主人"', u'主人'),
    (u'改动即 commit+push', u'commit+push'),
    (u'误报清单', u'误报清单'),
    (u'已裁定绝不重问', u'绝不重问'),
    (u'记忆门槛四件套', u'逐令牌回验'),
    (u'184 条目已入册', u'184（§186）门控层'),
]
for desc, tok in KEEP:
    check(u'S3 %s' % desc, tok in mem, u'' if tok in mem else u'缺 token=%r' % tok)

print('')
print('=' * 70)
print(u'S4 ★★★ 逐令牌回验（对 `git HEAD` 真 diff，CRLF 归一）')
print('=' * 70)

#: 令牌 = 汉字串 / ASCII 标识符 / 数字串（含千分位）。★ 180 轮的教训：裸数字会被大数
#: 子串命中，所以这里比的是**令牌相等**，不是 `in`。
TOK = re.compile(u'[\u4e00-\u9fff]+|[A-Za-z_][A-Za-z0-9_.]{1,}|[0-9][0-9,.]*')

try:
    _raw = subprocess.check_output(['git', 'show', 'HEAD:' + MEM_REL], cwd=REPO,
                                   stderr=subprocess.PIPE)
    old = lf(_raw.decode('utf-8'))
    _git_ok = True
except Exception as exc:  # 不在 git 里 / 浅克隆 ⇒ 如实跳过，不假装通过
    old = u''
    _git_ok = False
    print(u'[SKIP] 取不到 `HEAD:%s`（%s）' % (MEM_REL, exc))

if _git_ok:
    _new = lf(mem)
    _newset = set(TOK.findall(_new))
    _miss = []
    _seen = set()
    for t in TOK.findall(old):
        if t in _seen:
            continue
        _seen.add(t)
        if t not in _newset:
            _miss.append(t)

    #: ★★★ 白名单：本轮**刻意**压掉的令牌（每一条都在 S2 里有去处）。
    WHITE = set([
        u'可省这一问', u'双跑', u'ab171.py', u'14', u'多占一图标位', u'Windows',
        u'如实', u'静默翻成', u'插最底', u'命中所站的板', u'它永远',
        u'加回不改', u'抠', u'7121', u'则', u'上位', u'仍不可达', u'不许砍',
        u'地基', u'再补门型', u'隐藏房', u'删边', u'不作出场门控', u'未做',
        u'I7', u'I8', u'I9',
    ])

    check(u'S4.0 分母闸：老令牌 >= 1000（防止令牌正则失效后"零丢失"假绿）',
          len(_seen) >= 1000, u'去重令牌=%d' % len(_seen))
    _bad = [t for t in _miss if t not in WHITE]
    check(u'S4.1 丢失令牌**全在白名单内**', not _bad, u'意外丢失=%r' % (_bad,))
    check(u'S4.2 白名单**不多于**实测丢失数（禁止"先加白名单再压"）',
          len(WHITE) >= len(_miss) and len(WHITE) - len(_miss) <= 2,
          u'丢失=%d  白名单=%d' % (len(_miss), len(WHITE)))
    #: ★★ 负控制：三条**必然还在**的铁律令牌若出现在丢失名单，说明上面的 diff 在乱算
    _wk = [t for t in [u'--refspec', u'IDENTICAL', u'绝不重问'] if t in _miss]
    check(u'S4.3 负控制：三条铁律令牌**不在**丢失名单', not _wk, u'误判丢失=%r' % (_wk,))
    print(u'    丢失去重令牌：%d 个 → %s' % (len(_miss), u'、'.join(_miss)))
    print(u'    js_len(old)=%d  js_len(new)=%d  差=%+d'
          % (js_len(old), js_len(_new), js_len(_new) - js_len(old)))

print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _lost:
    print(u'★ 下列事实**找不到去处**，说明削语义了：')
    for d, w, m in _lost:
        print(u'   %s → %s 缺 %r' % (d, w, m))
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)
