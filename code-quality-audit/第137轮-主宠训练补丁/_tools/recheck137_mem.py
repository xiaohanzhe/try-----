# -*- coding: utf-8 -*-
"""第137轮记忆复检：速查本没超限、详版接得住、删掉的令牌能搜回来。

## 为什么单独一个脚本

`check137` 守的是**产品接线**，`check95 A2` 守的是**记忆注入上限**（`js_len <= 10000`）。
本轮两件事都动了（产品 + 记忆）⇒ 分开取证，别让一个绿把另一个盖住。

## 守什么

A 速查本硬闸：`js_len <= 10000` · 无 BOM · 全 CRLF · 非空（防空文件假绿）
B 本轮四条新内容在位 + ★ **旧断言已清除**：`58/59` 改 `59/59`、`ralsei 零读取` 那句已经过时
C 详版 §137.1~§137.8 八节齐全 · 纯 LF · 无 BOM
D ★★★ **逐令牌回验**：为腾体积从速查本移出的 9 个令牌，**逐个**回详版 `in` 一次
  配反控制：编一个不存在的令牌必须 MISS —— 否则"全 HIT"可能只是 `in` 恒真
E 守恒：速查本行数没被吃（仍 56 行）· 详版新增段不是空壳也不是一大坨
F 自检：无恒真判据 · 零外部盘

零 Qt、零网络、零外部盘（只读仓库内 `.workbuddy/memory/` 的两份文件）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MEM_DIR = os.path.join(ROOT, '.workbuddy', 'memory')
MEM = os.path.join(MEM_DIR, 'MEMORY.md')
DETAIL = os.path.join(MEM_DIR, u'参考-契约与历轮（详版）.md')
EV = os.path.join(ROUND, '_evidence')

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
    # ★ `newline=''`：字节忠实读，别让 Python 悄悄把 CRLF 归一成 LF（那样 A3 恒真）
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def jslen(s):
    # 注入上限按 **UTF-16 码元** 计，不按字节、也不按 `len(str)`（BMP 外字符算 2）
    return len(s.encode('utf-16-le')) // 2


mem = _read(MEM)
det = _read(DETAIL)

# =============================================== A 速查本硬闸
head(u'A 速查本硬闸（注入上限 / 编码）')
_mem_js = jslen(mem)
check(u'A1 js_len <= 10000', _mem_js <= 10000,
      u'%d / 10000  余 %d' % (_mem_js, 10000 - _mem_js))
with io.open(MEM, 'rb') as _f:
    _raw = _f.read()
check(u'A2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))

_mem_crlf = mem.count(u'\r\n')
_mem_lf = mem.count(u'\n')
check(u'A3 全 CRLF（速查本必须与既有 56 行同一种行尾）',
      _mem_lf > 0 and _mem_crlf == _mem_lf,
      u'CRLF=%d 总LF=%d 裸LF=%d' % (_mem_crlf, _mem_lf, _mem_lf - _mem_crlf))
check(u'A4 非空（防空文件把 A1 蒙过去）', _mem_js > 5000, u'js_len=%d' % _mem_js)

# =============================================== B 本轮新内容在位 + 旧断言已清
head(u'B 本轮新内容在位（并确认过时断言真的清掉了）')
check(u'B1 锁号速查里有 `check137`', u'check137' in mem)
check(u'B2 `ralsei` 那条已标记 §137 已接',
      u'ralsei' in mem and u'§137 已接' in mem)
check(u'B3 新教训「链上函数必须模块级」在位',
      u'桩上新增的链上函数必须模块级' in mem)
check(u'B4 新教训「打桩前先证明拿到产品那一个对象」在位',
      u'打桩前先证明拿到的是产品那一个对象' in mem)
# ★ 第134轮登记缺口时写的是「`patches` 58/59 进 prompt（`ralsei` 零读取）」；
#   本轮接上以后那句话**已经过时**。留着它下一轮就会有人再补一次接线。
check(u'B5 旧断言已清除：`58/59` 与 `零读取` 都不在速查本',
      u'58/59' not in mem and u'零读取' not in mem,
      u'58/59=%s 零读取=%s' % (u'58/59' in mem, u'零读取' in mem))

# =============================================== C 详版结构
head(u'C 详版 §137 结构')
_want = [u'## §137.%d' % i for i in range(1, 9)]
_miss = [w for w in _want if w not in det]
check(u'C1 §137.1~§137.8 八节齐全', not _miss,
      u'缺 %s' % _miss if _miss else u'8/8')
check(u'C2 详版纯 LF（新增段落没混进 CRLF）', det.count(u'\r\n') == 0,
      u'CRLF=%d' % det.count(u'\r\n'))
with io.open(DETAIL, 'rb') as _f:
    _d_raw = _f.read()
check(u'C3 详版无 BOM', not _d_raw.startswith(b'\xef\xbb\xbf'))

# =============================================== D 逐令牌回验 + 反控制
head(u'D 逐令牌回验（从速查本移出的，必须在详版搜得回来）')
TOKENS = [
    (u'ast.walk+break', u'§96b.1 AST 抓"第一个匹配"是陷阱'),
    (u'等价写法', u'token 回验允许等价写法'),
    (u'怎么取证的', u'第125轮"先确认自己怎么取证"'),
    (u'scr_dbox', u'原作 UI 固定像素的判据名'),
    (u'_apply_scale_to_scene', u'疑零调用（§107~§110）'),
    (u'§42', u'"后者在 §42 证据目录"'),
    (u'§47.11', u'各轮遗留池起点'),
    (u'§125.10', u'各轮遗留池终点'),
    (u'§72', u'"全表见详版 §72~§125"'),
]
_ok_tok, _miss_tok = 0, []
for _t, _why in TOKENS:
    if _t in det:
        _ok_tok += 1
    else:
        _miss_tok.append(u'%s（%s）' % (_t, _why))
check(u'D1 9 个移出令牌逐个在详版可检索', not _miss_tok,
      u'%d/%d 命中 %s' % (_ok_tok, len(TOKENS), _miss_tok if _miss_tok else u''))
# ★ 反控制：编一个不可能存在的令牌。它必须 MISS —— 否则上面那条"全 HIT"可能只是 `in` 恒真。
_FAKE = u'ZZ_第137轮_不存在的令牌_ZZ'
check(u'D2 反控制：编造的令牌必须搜不到', _FAKE not in det, u'%s' % _FAKE)
check(u'D3 分母非空（令牌表不许被清空）', len(TOKENS) >= 9, u'n=%d' % len(TOKENS))

# =============================================== E 守恒
head(u'E 守恒（改记忆不许顺手吃掉别的东西）')
check(u'E1 速查本行数仍 56（本轮只做行内替换）',
      _mem_lf == 56, u'%d 行' % _mem_lf)
_i = det.find(u'## §137.1')
_seg = det[_i:] if _i >= 0 else u''
_seg_b = len(_seg.encode('utf-8'))
check(u'E2 详版 §137 段既不是空壳也不是一大坨',
      3000 < _seg_b < 20000, u'%d 字节' % _seg_b)
# ★ 显式登记"换了哪一个"：锁号速查保持 8 个，进来 check137、出去 check129
check(u'E3 锁号仍 8 个、且 check129 已被挤出（check128 仍在）',
      u'check129' not in mem and u'check128' in mem,
      u'check129=%s check128=%s' % (u'check129' in mem, u'check128' in mem))

# =============================================== F 自检
head(u'F 自检')
with io.open(os.path.abspath(__file__), 'r', encoding='utf-8', newline='') as _f:
    _src = _f.read()
_tree = ast.parse(_src)
_bad = [n for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == 'check' and len(n.args) >= 2
        and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad, u'%d 处' % len(_bad))
check(u'F2 零外部盘（读的两个文件都在仓库内）',
      all(os.path.abspath(p).startswith(ROOT + os.sep) for p in (MEM, DETAIL)))

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'mem_js_len': _mem_js, 'mem_remain': 10000 - _mem_js,
       'mem_lines': _mem_lf, 'mem_crlf': _mem_crlf,
       'detail_bytes': len(det.encode('utf-8')), 'seg137_bytes': _seg_b,
       'tokens_hit': _ok_tok, 'tokens_total': len(TOKENS)}
with io.open(os.path.join(EV, 'recheck137_mem.json'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'recheck137_mem：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
