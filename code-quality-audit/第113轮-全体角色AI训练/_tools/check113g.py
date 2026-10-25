# -*- coding: utf-8 -*-
u"""第113轮g回归锁：性格**不许演成极端**（用户口径「要和正常人一样」）。

用户口径（2026-10-25 逐字）
--------------------------
「对，但**不要过度突出个人特点**，要不然会显得过于暴躁，过于柔弱等等后果，**要和正常人一样** ok？」

这是对「尤其性格，也要好好做」的**限定**：性格必须存在，但不许演成极端。

本套件守什么
------------
① **写法红线**（A 段）：这条规则**不许出现任何极端词**。
   113g 探针实测：规则里只要带上「描述那种行为长什么样」的括注，同类违规率
   从 1/10 涨到 **10/10**（susie P1P），asgore 三个变体全 10/10（对规则免疫）。
   ⇒ 写「不要过于暴躁」= 把「暴躁」示范一遍。所以本段只描述「正常是什么样」
     + 一条**中性**正例，一个极端词都不许有。

② **度量本身可信**（B 段）：`extreme113` 的软上限表 + 鉴别力自证
   （暴怒/柔弱样本必判红、正常样本必不判红、5 条正常台词 0 误伤）。

③ **批次不许混**（C 段）：`metrics.lang` 是第113轮后续才加的字段。
   没有它的语料是**旧 prompt**（system_chars 实测比现在少 545 字），
   拿它下「现在过火」的结论是错的（本轮就栽过，见 `Personality_Calibration_113g.md` §1.1）。

★ 判据一律走 AST 取 `SPEAK_RULES` 的**值**，不吃注释 ——
  注释里专门写了「不要写暴躁」这句教训本身，纯文本扫会**自指误报**（第96b/97/98 轮同坑）。

零网络、零 Qt、零外部盘。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, HERE)

NP = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_persona.py')

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))
        _failed.append(desc)


# ---------------------------------------------------------------- 判据（纯函数，便于负控制）
#: 规则里必须有的四句（缺任何一句 ⇒ 这条口径就漏了）
MUST = (
    '性格是你的底色',
    '你大多数时候就是普通人在聊天',
    '靠你选什么词、先注意到什么',
    '嗯，我知道了。那我先去看看。',
)

#: ★★★ 值里**不许**出现的极端词。判断的是「有没有把极端演法描述出来」。
EXTREME = ('暴躁', '柔弱', '过分', '过度', '动不动就', '太凶', '太软',
           '撒娇', '歇斯底里', '尖叫', '哭诉', '卑微', '发火', '撒野')


def has_rule(text):
    """四句齐全 ⇒ True。"""
    return all(s in (text or '') for s in MUST)


def has_extreme(text):
    """出现任一极端词 ⇒ True（表示**违规**）。返回命中的词表。"""
    return [w for w in EXTREME if w in (text or '')]


def speak_rules_value():
    """AST 取 `SPEAK_RULES` 的**值**（相邻字符串字面量拼接后）。不吃注释。"""
    with io.open(NP, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id == 'SPEAK_RULES':
                consts = [x.value for x in ast.walk(node.value)
                          if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                return ''.join(consts)
    return None


print('=' * 72)
print('A 规则面：只说「正常」，一个极端词都不许有')
print('=' * 72)

VAL = speak_rules_value()
check('A1 SPEAK_RULES 解析到（不是 None）', VAL is not None,
      '值长度 %s' % (len(VAL) if VAL else '—'))
VAL = VAL or ''

check('A2 四句性格校准规则齐全', has_rule(VAL),
      '缺：%s' % ([s for s in MUST if s not in VAL] or '无'))
hit = has_extreme(VAL)
check('A3 ★ 值里没有把极端演法描述出来', not hit, '命中：%s' % (hit or '无'))

# A4 正控制：这个判据抓得住（合成串必须报红）
check('A4 ★ 正控制：往值里加「不要过于暴躁」必须被抓到',
      bool(has_extreme(VAL + '不要过于暴躁。')),
      '命中：%s' % (has_extreme(VAL + '不要过于暴躁。') or '（漏了）'))

# A5 中性正例本身必须中性
NEUTRAL = '嗯，我知道了。那我先去看看。'
check('A5 ★ 中性正例不含被弃用的角色台词（上一版就是栽在这里）',
      '烦死了' not in VAL and '盯着我' not in VAL)
check('A6 中性正例里不含括号（别把括号风格又带回来）', '（' not in NEUTRAL and '(' not in NEUTRAL)

# A7 顺序：性格这段必须在「用简体中文」之后（与既有 SPEAK_RULES 的追加约定一致）
i_cn = VAL.find('用简体中文说话')
i_per = VAL.find('性格是你的底色')
check('A7 性格段排在「用简体中文说话」之后', 0 <= i_cn < i_per,
      'cn@%d persona@%d' % (i_cn, i_per))

print()
print('=' * 72)
print('B 度量面：extreme113 的软上限表与鉴别力')
print('=' * 72)

try:
    import extreme113 as E
    check('B1 extreme113 可导入', True)
except Exception as ex:      # noqa: BLE001
    check('B1 extreme113 可导入', False, repr(ex)[:120])
    E = None

if E is not None:
    caps = getattr(E, 'SOFT_CAP', {})
    check('B2 软上限表 6 个分量齐备',
          set(caps) == {'excl', 'multi', 'caps', 'emph', 'ellip', 'apol'},
          '实得 %s' % sorted(caps))
    check('B3 每一项都带「单位 + 为什么是这个位置」（可复查）',
          all(len(v) == 3 and v[1] and v[2] for v in caps.values()))

    RAGE = '你到底想干什么！！！我受够了！每次都这样！根本没人听我说话！！'
    MEEK = '对不起……都是我的错……我不该说话的……对不起对不起……算了，我没事……'
    NORM = '今天有点累。我先歇会儿，等下再说。'

    def over(t):
        m = E.measure(t)
        return [k for k in caps if m[k] > caps[k][0]]

    check('B4 暴怒样本判红', bool(over(RAGE)), '命中 %s' % (over(RAGE) or '（漏了）'))
    check('B5 柔弱样本判红', bool(over(MEEK)), '命中 %s' % (over(MEEK) or '（漏了）'))
    check('B6 ★ 负控制：正常样本**不许**判红', not over(NORM),
          '命中 %s' % (over(NORM) or '无'))

    BATCH = ['今天有点累。我先歇会儿，等下再说。',
             '嗯，好啊。你说的那个我也想过。',
             '外面在下雨。你带伞了吗？',
             '我明白了。那我明天再来一趟。',
             '这个我不太确定，得问问别人。']
    nb = [s for s in BATCH if over(s)]
    check('B7 ★ 正控制：5 条正常台词 0 误伤（曾因裸字「太」误判「不太确定」）',
          not nb, '误伤：%s' % (nb or '无'))

# B8 批次判据必须存在（防止再把旧 prompt 的毛病算到当前头上）
with io.open(os.path.join(HERE, 'extreme113.py'), 'r', encoding='utf-8',
             newline='') as f:
    EXT_SRC = f.read()
check('B8 ★ extreme113 按 `metrics.lang` 拆新旧批次（缺了就会拿旧语料下当前结论）',
      'has_lang' in EXT_SRC and '批次拆分' in EXT_SRC)

print()
print('=' * 72)
print('D 破坏性负控制：证明 A 段不是恒真')
print('=' * 72)

# D1 把四句全删掉 ⇒ has_rule 必须报 False
stripped = VAL
for s in MUST:
    stripped = stripped.replace(s, '')
check('D1 ★ 删掉四句后 A2 必须重新报红（证明 A2 不是恒真）',
      not has_rule(stripped), '删后 has_rule=%s' % has_rule(stripped))

# D2 只删一句也必须报红（防「只要有一句在就算过」）
one_off = VAL.replace(MUST[0], '')
check('D2 ★ 只删第一句也必须报红', not has_rule(one_off),
      '删「%s」后 has_rule=%s' % (MUST[0], has_rule(one_off)))

# D3 逐词验证 EXTREME 表每一项都真能被抓到（防表里混进永不匹配的空字串）
bad_tokens = [w for w in EXTREME if not has_extreme('前缀' + w + '后缀')]
check('D3 ★ EXTREME 表每一项都真能被匹配', not bad_tokens,
      '失灵项：%s' % (bad_tokens or '无'))

print()
print('=' * 72)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _n_fail:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 72)
sys.exit(0 if _n_fail == 0 else 1)
