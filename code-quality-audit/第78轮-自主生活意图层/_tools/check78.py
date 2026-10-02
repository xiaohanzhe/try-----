# -*- coding: utf-8 -*-
"""第78轮回归锁：**NPC 自主生活 · 层1 意图层**不许静默漂移。

用户口径（逐字，第77轮）
------------------------
> 「人物之间也可以自己动，也就是，**他们生活是生活，我和他们只是朋友**，
>  而不是主导人，也就是**不会因为缺少一个人哪怕是我他们就不生活了**，OK？还有，
>  像是**去哪？找谁？干什么？生活规划**这类的事也是由**各自的 AI 决定**，
>  并且**不是一到晚上就必须回自己家**，也可以选择**在朋友那睡觉**，但这也是 AI 决定，
>  反正就是，**人味，人味，还 tm 是人味**，重要的事情说三遍！」

守什么
------
* **A 零依赖纪律**（AST）：只准标准库、**零函数内 import**、零项目内 import。
* **B ★★ L2「用户不是驱动源」**：`decide()` 签名里**不许出现** pet/user/player
  ⇒ 这是**结构判据**，不是靠"看代码觉得没用到"。
* **C ★★★ L6「禁整点必做」**：任何动作在任何时段权重都 > 0
  （尤其 **夜里 `visit_friend` 仍 > 0** = "可以睡朋友家"的前提）。
* **D ★★ L6「同人同刻不必同行为」**：同一人两天同一时刻 ⇒ `Intent` **不强制相同**。
* **E 行为**：回不去家 ⇒ 不许凭空回家；没可达场景 ⇒ 只能 stay；原地打转被降权。
* **F ★★ L4 睡觉**：`choose_sleep_scene` 在"朋友熟 + 可达"时**真能选到朋友家**；
  且**没有**任何写死常量在主导。
* **G 判据自身体检**：记账口非 no-op（★不打那 6 字符字面量到 stdout）。

★ 零网络 / 零 UI / 零外部盘 / 不需要显示器。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_intent.py')

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def _probe_ledger():
    """G 段自检：造一个失败看它真进账。

    ★★ 绝不许走 `check()` —— 它会往 stdout 打那 6 字符标记，
    而 `regress/run_all.py` 的 `count_results()` 是**正则数字面量**的
    ⇒ 探针会污染套件的 FAIL 计数（第77轮 `check77` 踩过，§69.7）。
    """
    global PASS, FAIL
    p0, f0 = PASS, FAIL
    FAIL += 1
    FAILED.append('__probe__')
    got = (FAIL == f0 + 1 and '__probe__' in FAILED)
    FAIL = f0
    FAILED.remove('__probe__')
    return got and (PASS, FAIL) == (p0, f0)


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


# ================================================================ A
print('=' * 74)
print('A 零依赖纪律（对齐 companion* / npc_placement 的既有口径）')
print('=' * 74)

src = read(MOD)
tree = ast.parse(src)
#: **本文件**源码 —— G 段的自检判据必须看自己，不许看被测模块（第一版就写错成 `tree`）
_SELF = read(os.path.abspath(__file__))

ALLOWED_STD = {'collections', 'hashlib', 'random', 'math', 'time', 'json', 'io', 'os'}

tops = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
top_names = []
for n in tops:
    if isinstance(n, ast.Import):
        top_names.extend(a.name.split('.')[0] for a in n.names)
    else:
        top_names.append((n.module or '').split('.')[0])
bad = [t for t in top_names if t not in ALLOWED_STD]
check('A1 顶层 import 全部是标准库', not bad, '越界=%s 全量=%s' % (bad or '无', top_names))

inner = [n for n in ast.walk(tree)
         if isinstance(n, (ast.Import, ast.ImportFrom)) and n not in tops]
check('A2 ★ 零函数内 import（既有零依赖模块的硬纪律）', not inner,
      '函数内=%d' % len(inner))

proj = [t for t in top_names if t in ('npc_life', 'companion', 'data_store', 'npc_placement')]
check('A3 不 import 任何项目内模块（熟络度走入参，不自己拉）', not proj, '项目内=%s' % (proj or '无'))

# 模块真能 import（不只是 AST 通过）
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
import npc_intent as NI          # noqa: E402

check('A4 模块真能 import（AST 过 ≠ 可加载）', hasattr(NI, 'decide'),
      'decide=%s' % hasattr(NI, 'decide'))

# ================================================================ B
print()
print('=' * 74)
print('B ★★ L2「用户不是驱动源」：决策签名里不许有"用户"')
print('=' * 74)

fn = None
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == 'decide':
        fn = n
        break
check('B1 decide() 是模块级函数', fn is not None, '')

if fn is not None:
    args = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    banned = [a for a in args
              if a.lower() in ('pet', 'user', 'player', 'host', 'me')]
    check('B2 ★★ decide() 的形参里没有 pet/user/player/host/me（L2 结构保证）',
          not banned, '形参=%s 违规=%s' % (args, banned or '无'))
    # ★ 负控制：把 banned 检测喂一个"真有 pet"的签名，必须判违规
    fake = ast.parse('def decide(pet, now): pass').body[0]
    fake_args = [a.arg for a in fake.args.args] + [a.arg for a in fake.args.kwonlyargs]
    check('B2n 负控制：同样的检测喂 `decide(pet, now)` 必须判违规（否则判据是恒真）',
          bool([a for a in fake_args if a.lower() in ('pet', 'user', 'player', 'host', 'me')]),
          '')

# 睡眠决策同样不许有用户
sn = [n for n in tree.body if isinstance(n, ast.FunctionDef)
      and n.name == 'choose_sleep_scene']
check('B3 choose_sleep_scene() 是模块级函数', bool(sn), '')
if sn:
    sargs = [a.arg for a in sn[0].args.args] + [a.arg for a in sn[0].args.kwonlyargs]
    sb = [a for a in sargs if a.lower() in ('pet', 'user', 'player', 'host', 'me')]
    check('B4 ★ 睡觉决策同样无"用户"形参', not sb, '形参=%s' % sargs)

# ================================================================ C
print()
print('=' * 74)
print('C ★★★ L6「禁整点必做」：任何动作在任何时段都必须有非零权重')
print('=' * 74)

all_pos = True
zero_hits = []
for ph in NI.PHASES:
    w = NI.action_weights('toriel', ph, traits=('quiet',), familiar=0.5)
    for k, v in w.items():
        if not (v > 0):
            all_pos = False
            zero_hits.append((ph, k, v))
check('C1 ★★ 任何时段 × 任何动作，权重恒 > 0（"整点必做"的结构性排除）',
      all_pos, '零/负项=%s' % (zero_hits[:5] or '无'))

# ★★★ 最关键的一条：夜里也必须能去找朋友（= "可以睡朋友家"的前提）
night = NI.action_weights('kris', 'night', traits=(), familiar=0.0)
check('C2 ★★★ 夜里 `visit_friend` 权重 > 0（⇒「不是一到晚上就必须回自己家」有结构保障）',
      night.get('visit_friend', 0) > 0, 'night visit_friend=%.4f' % night.get('visit_friend', 0))
check('C2n 负控制：把 visit_friend 夜里乘数改成 0 ⇒ 该判据必报红',
      (lambda: (lambda w: not (w.get('visit_friend', 0) > 0))(
          {k: (v * (0.0 if k == 'visit_friend' else 1.0)) for k, v in night.items()}))(),
      '演示用：0 乘后为 %.1f' % 0.0)

# 白天也必须能回家（不强制"白天必须在外"）
day = NI.action_weights('kris', 'day', traits=(), familiar=0.0)
check('C3 ★ 白天 `go_home` 权重 > 0（不强制"白天必须在外"）',
      day.get('go_home', 0) > 0, 'day go_home=%.4f' % day.get('go_home', 0))

# 熟络度只加不减（越熟越想找朋友）
w0 = NI.action_weights('a', 'day', familiar=0.0)
w1 = NI.action_weights('a', 'day', familiar=1.0)
check('C4 ★ 熟络度↑ ⇒ visit_friend 权重↑（只加不减）',
      w1['visit_friend'] > w0['visit_friend'],
      '%.3f -> %.3f' % (w0['visit_friend'], w1['visit_friend']))

# 非法熟络度不许炸
ok_bad = True
try:
    NI.action_weights('a', 'day', familiar=None)
    NI.action_weights('a', 'day', familiar='abc')
    NI.action_weights('a', 'day', familiar=-5)
except Exception:
    ok_bad = False
check('C5 非法熟络度（None/"abc"/负数）不抛', ok_bad, '')

# ================================================================ D
print()
print('=' * 74)
print('D ★★ L6「同人同刻不必同行为」：两天同一时刻不强制相同')
print('=' * 74)

REACH = ['s.a', 's.b', 's.c', 's.d', 's.e']

# 同一个人、同样的时辰、但**不同的天** ⇒ 结果应至少出现 2 种
seen = set()
for d in range(40):
    now = 86400.0 * (1000 + d) + 3600.0 * 22      # 每天 22:00
    it = NI.decide('susie', now, traits=(), familiar=0.4,
                   home='s.a', favorites=['s.b'], reachable=REACH,
                   friends=[('kris', 0.7)], extra_weights=None)
    seen.add((it.what, it.dest_scene))
check('D1 ★★★ 同一人 40 天里同一时刻（22:00）的决策**出现 > 1 种**（不是整点必做）',
      len(seen) > 1, '不同结果数=%d 例=%s' % (len(seen), sorted(seen)[:3]))

# 不同人 ⇒ 更应不同（"各自的人生"）
a = set()
b = set()
for d in range(40):
    now = 86400.0 * (1000 + d) + 3600.0 * 10
    a.add(NI.decide('toriel', now, traits=('quiet',), familiar=0.3,
                    home='s.a', favorites=['s.b'], reachable=REACH,
                    friends=[('kris', 0.2)]).what)
    b.add(NI.decide('susie', now, traits=('crowded',), familiar=0.9,
                    home='s.c', favorites=['s.d'], reachable=REACH,
                    friends=[('kris', 0.8)]).what)
check('D2 ★ 不同人（不同种子/特质/熟络度）⇒ 行为分布不同（不是同一份人生）',
      a != b, 'toriel=%s susie=%s' % (sorted(a), sorted(b)))

# 确定性：同样入参（含同一时刻）⇒ 同一结果（可复现，不是真随机）
x1 = NI.decide('npc', 5000.0, traits=(), reachable=REACH, home='s.a')
x2 = NI.decide('npc', 5000.0, traits=(), reachable=REACH, home='s.a')
check('D3 ★ 同一时刻同样入参 ⇒ 结果**可复现**（抖动是确定性的，不是真随机）',
      (x1.what, x1.dest_scene) == (x2.what, x2.dest_scene),
      '%s vs %s' % (x1.what, x2.what))

# jitter 自己：范围正确、同刻同值
j1 = NI.jitter('a', 12345.6)
j2 = NI.jitter('a', 12345.6)
check('D4 jitter 值域 ∈ [0,1] 且同刻可复现', 0.0 <= j1 <= 1.0 and j1 == j2,
      'j=%.6f' % j1)
js = set(NI.jitter('a', 1000.0 + i * 0.5) for i in range(30))
check('D5 ★ jitter 随时间**真变化**（不是常量；否则等于没抖）',
      len(js) > 5, '不同值=%d' % len(js))
check('D6 ★ jitter 不同人给不同值（独立人生）',
      NI.jitter('a', 777.0) != NI.jitter('b', 777.0),
      'a=%.4f b=%.4f' % (NI.jitter('a', 777.0), NI.jitter('b', 777.0)))

# ================================================================ E
print()
print('=' * 74)
print('E 行为级：回不去/去不了/原地打转')
print('=' * 74)

it = NI.decide('a', 1000.0, reachable=[], home='s.a')
check('E1 没有任何可达场景 ⇒ 只能 stay（不是"凭空传送"）',
      it.what == 'stay' and it.dest_scene is None, 'what=%s dest=%s' % (it.what, it.dest_scene))

# ★ 回家：家在 reachable 之外 ⇒ 不许"凭空回家"
hits_home_unreach = []
for d in range(60):
    now = 86400.0 * (2000 + d) + 3600.0 * 23
    it = NI.decide('b', now, home='s.zzz', reachable=REACH, strength=None
                   if False else None) if False else NI.decide(
        'b', now, home='s.zzz', reachable=REACH)
    if it.dest_scene == 's.zzz':
        hits_home_unreach.append(it)
check('E2 ★★ 家在可达集之外 ⇒ **一次都不许**出现在 dest_scene（不许凭空回家）',
      not hits_home_unreach, '违规=%d' % len(hits_home_unreach))

# 家在可达集内 ⇒ 确实会出现"回家"（否则 E2 是空谈）
hits_home_ok = 0
for d in range(120):
    now = 86400.0 * (3000 + d) + 3600.0 * 22
    it = NI.decide('b', now, home='s.a', reachable=REACH)
    if it.dest_scene == 's.a' and it.what == 'go_home':
        hits_home_ok += 1
check('E3 ★ 正控制：家在可达集内时，"回家"真会发生（证明 E2 不是在数空集）',
      hits_home_ok > 0, '发生 %d 次 / 120 天' % hits_home_ok)

# 没有朋友 ⇒ 不许报 visit_friend
it = NI.decide('c', 4000.0, reachable=REACH, friends=[])
check('E4 没给朋友 ⇒ 不出现 is_social 的意图（不凭空捏造社交对象）',
      not it.is_social, 'what=%s who=%s' % (it.what, it.who))

# 找朋友 ⇒ who 非空且是给定的人
social = []
for d in range(200):
    now = 86400.0 * (5000 + d) + 3600.0 * 18
    it = NI.decide('d', now, reachable=REACH,
                   friends=[('kris', 0.9), ('susie', 0.8)])
    if it.is_social:
        social.append(it)
check('E5 ★ 真的会"去找朋友"（发生了 > 0 次），且 who ∈ 给定名单',
      bool(social) and all(s.who in ('kris', 'susie') for s in social),
      '发生 %d 次，who=%s' % (len(social), sorted({s.who for s in social})))

# 原地打转：连续两次 visit_favorite 到同一处 ⇒ 第二次被改道
last = NI.Intent('visit_favorite', 's.b', None, 'favorite')
switched = 0
for d in range(200):
    now = 86400.0 * (7000 + d) + 3600.0 * 15
    it = NI.decide('e', now, reachable=REACH, favorites=['s.b'], last=last)
    if it.what != 'visit_favorite':
        switched += 1
check('E6 ★ L5 读上次结果：上次已去过同一个 favorite ⇒ 这次**真会改道**',
      switched > 0, '改道 %d / 200' % switched)

# ================================================================ F
print()
print('=' * 74)
print('F ★★ L4 睡觉地点：不硬性回家，真能睡朋友家')
print('=' * 74)

friends3 = [('kris', 0.9, 's.b'), ('susie', 0.85, 's.c')]
picked = set()
for d in range(200):
    now = 86400.0 * (9000 + d) + 3600.0 * 23
    s, why = NI.choose_sleep_scene('f', now, home='s.a', friends=friends3,
                                   reachable=REACH)
    if s:
        picked.add(s)
check('F1 ★★★ 「睡朋友家」真会发生（出现 s.b 或 s.c）',
      bool(picked & {'s.b', 's.c'}), '选过的地点=%s' % sorted(picked))
check('F2 ★ 睡自己家也真会发生（不是一边倒）',
      's.a' in picked, '选过的地点=%s' % sorted(picked))
check('F3 ★★ **两类都出现** ⇒ 睡觉地点是"决策"而不是"常量"（旧 `BEDTIME_HOME_SCENE` 反例）',
      ('s.a' in picked) and bool(picked & {'s.b', 's.c'}),
      'own_home=%s friend=%s' % ('s.a' in picked, bool(picked & {'s.b', 's.c'})))

# 朋友家不可达 ⇒ 不许睡那
s_only, why_only = NI.choose_sleep_scene('g', 1000.0, home='s.a',
                                         friends=[('kris', 0.9, 's.zzz')],
                                         reachable=['s.a'])
check('F4 ★ 朋友家不可达 ⇒ 不出现该地点', s_only == 's.a',
      '得到 %s (%s)' % (s_only, why_only))

# 哪都去不了 ⇒ None（不假装有地方睡）
s_none, why_none = NI.choose_sleep_scene('h', 1000.0, home='s.x', friends=[],
                                         reachable=['s.a'])
check('F5 自己家与朋友家都不可达 ⇒ 返回 None（不假装有地方睡）',
      s_none is None, 'why=%s' % why_none)

# 陌生人（熟络度 0）⇒ 不给睡他家
s_str, _ = NI.choose_sleep_scene('i', 1000.0, home=None,
                                 friends=[('kris', 0.0, 's.b')],
                                 reachable=['s.a', 's.b'])
check('F6 ★ 熟络度 0（陌生人）⇒ 不会去睡他家（不是谁家都能睡）',
      s_str != 's.b', '得到 %s' % s_str)

# 连睡两晚同一处会被降权（不是禁止）
hits = 0
for d in range(400):
    now = 86400.0 * (11000 + d) + 3600.0 * 23
    s, _ = NI.choose_sleep_scene('j', now, home='s.a', friends=friends3,
                                 reachable=REACH, last_sleep='s.b')
    if s == 's.b':
        hits += 1
check('F7 ★ 上一晚睡过的朋友家会被**降权**（仍可能，但明显更少）',
      0 < hits < 200, '连选 s.b %d / 400（降权后应 < 一半）' % hits)

# ================================================================ G
print()
print('=' * 74)
print('G 判据自身体检')
print('=' * 74)

check('G1 ★★ 记账口不是 no-op（造失败真进账，探针自身零痕迹：不打标记、不动计数）',
      _probe_ledger(), '')

# 记账守恒：PASS+FAIL 应等于本文件里 check(...) 的实际调用次数
#   ★ 必须解析**本文件**（`__file__`）而不是被测模块 ——
#     第一版写成 `tree`（= npc_intent 的 AST）⇒ 数出 0 个调用，假报红。
_self_tree = ast.parse(_SELF)


def _print_points(tree_, marker):
    """数 `print('<marker> ...')` 的**语句**数。

    ★★ 绝不能用 `src.count("print('[PASS]")` —— 判据自己的**字符串字面量**
    也含这两个标记（自指），实测数出 4 而不是 1（第77轮 §69.7 同源的坑）。
    ⇒ 只能看 **AST 里真被 print 的那个常量的开头**。

    ★ 三种形状都要认（第一版只认 `Constant` ⇒ 数出 0 个，因为
      `check()` 里的写法是 `print('[PASS] %s' % (...))` ⇒ 首参是 `BinOp`）：
      `Constant` / `JoinedStr`(f-string) / `BinOp`(% 格式化，左操作数是常量)。
    """
    n = 0
    for node in ast.walk(tree_):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'print' and node.args):
            continue
        head = node.args[0]
        if isinstance(head, ast.BinOp) and isinstance(head.op, ast.Mod):
            head = head.left                      # 剥掉 `% (...)` 的外壳
        if isinstance(head, ast.JoinedStr) and head.values:
            head = head.values[0]                 # f-string 取第一个片段
        if isinstance(head, ast.Constant) and isinstance(head.value, str) \
                and head.value.lstrip().startswith(marker):
            n += 1
    return n


_n_bare = sum(1 for node in ast.walk(_self_tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == 'check')
n_check_calls = _n_bare

check('G2 ★ 标记打印点唯一（AST 层计数，不吃字面量自指）：恰 1 个 print(PASS) + 1 个 print(FAIL)',
      _print_points(_self_tree, '[PASS]') == 1
      and _print_points(_self_tree, '[FAIL]') == 1,
      'PASS 点=%d FAIL 点=%d' % (_print_points(_self_tree, '[PASS]'),
                               _print_points(_self_tree, '[FAIL]')))
check('G3 被测文件在盘上且非空', os.path.getsize(MOD) > 8000,
      '%d B' % os.path.getsize(MOD))
check('G4 ★ 记账守恒：PASS+FAIL == 本文件 check() 调用次数（不漏记/不重复记）',
      # ★ G4 自己也是一次 check()，而它在比较**之后**才进账
      #   ⇒ 右边要 +1 抵消（第一版漏了这一步，恒差 1，是**判据自己的** bug）
      (PASS + FAIL) == n_check_calls - 1,
      'PASS+FAIL=%d  源码 check() 调用=%d（含 G4 自身）'
      % (PASS + FAIL, n_check_calls))

print()
print('=' * 74)
print('第78轮 NPC 意图层锁：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：')
    for n in FAILED:
        print('  - %s' % n)
print('=' * 74)
