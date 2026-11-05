# -*- coding: utf-8 -*-
"""运动能力档案 —— 「练出来的能力」，每人一份，初始值与成长率都不同。

回答用户这条需求（第165轮）：
    「给AI加装一个学习模块，让他能够像是练习一样练出来，当然，针对不同NPC的
      特点，运动能力肯定也不同，所以初始和进步速度都不同哦」

★ 为什么能力存「倍率」而不是「绝对值」（这条是零回归的全部秘密）
--------------------------------------------------------------------
产品里本来就有一套**全局常量**在定义"人能做到多少"：
`JUMP_SPEED_MAX`（跳力上限）/ `RUNUP_SPEED_MAX`（冲刺上限）/ `RUNUP_ACCEL`（助跑加速度）。
如果档案改存绝对值，那这几十个套件里凡是断言常量的地方全都要重钉；
而且"没有档案的人物"就没有行为可依。

⇒ 档案只存**倍率**：`1.0` = 就是全局常量本身。
   · 没档案 / 档案坏 / 还没读到 ⇒ 一律 `1.0` ⇒ **乘法恒等**，现有行为逐值不变；
   · 浮点下 `x * 1.0 == x` 精确成立，不是"约等于"。
   · 于是"加一个学习模块"对旧存档、旧测试、旧行为是**零改动**。

★★ 初始值不同 vs 进步速度不同（用户点名的两件事，两个不同字段）
---------------------------------------------------------------
· 初始值   ⇒ `jump` / `run` / `accel` 三个倍率。天生壮的起点就高。
· 进步速度 ⇒ `growth` 一个倍率。**同一套练法**下，growth 大的涨得多。
  两者正交：可以有"起点很高但练不动"（growth 0.6）和"起点低但一练就成"（growth 1.8）。

★ 成长曲线（刻意简单，可解释、可断言）
--------------------------------------
    level = exp // LEVEL_STEP          （0 ~ MAX_LEVEL）
    mult  = 1 + GAIN_PER_LEVEL * growth * level
    exp   = min(MAX_EXP, exp + amount) （**封顶**、**不退步**）

· **不退步**：`apply_exp` 只做加法与钳制，全模块**没有任何减分路径**
  —— 用户没要求遗忘，加了就是自造需求（本项目历史上"凭空加功能"踩过）。
· **封顶**：`MAX_EXP` 到顶就停，不会练成超人（否则跑速迟早突破屏幕）。
· 典型量级：growth 1.0 练满 +30%；growth 1.6 练满 +48%；growth 0.6 练满 +18%。
  满级需要 `LEVEL_STEP * MAX_LEVEL = 1200` 经验 ≈ **100 次成功起跳**（每次 12）。

零依赖纪律（与 scene_walk / possession / npc_roam 同源）
------------------------------------------------------
本模块**只准标准库**：禁 import Qt、禁 import 任何项目内模块。
理由同那几处 —— `main.py` import 期就要建控制器，回头 import 项目内模块
会把「初始化环」接上（本仓已踩 4 次）。本模块连标准库都不需要。
"""

#: 三个能力倍率的键（顺序固定，便于按位解包）
EFF_KEYS = ('jump', 'run', 'accel')

#: 没有任何档案时的默认倍率 —— 全 1.0 = 就是现有全局常量本身
DEFAULT_PROFILE = {
    'jump': 1.0,
    'run': 1.0,
    'accel': 1.0,
    'growth': 1.0,
}

#: 合法区间（倍率）。越界一律钳回来，不抛异常 —— 档案是人手写的，写错不许炸产品。
LIMITS = {
    'jump': (0.4, 2.0),
    'run': (0.4, 2.0),
    'accel': (0.4, 2.0),
    'growth': (0.3, 2.5),
}

#: 依据等级（三档，用户 2026-11-06 选「每人落值 + 标依据等级」）
EVIDENCE_LEVELS = ('明证', '推断', '无据')

#: 每级所需经验
LEVEL_STEP = 240.0

#: 等级上限
MAX_LEVEL = 5

#: 每级涨幅（乘 growth）
GAIN_PER_LEVEL = 0.06

#: 经验上限 = 满级所需
MAX_EXP = LEVEL_STEP * MAX_LEVEL

#: 记账权重（练什么给多少）
EXP_JUMP_OK = 12.0      # 一次成功的起跳/落地
EXP_JUMP_FAIL = 3.0     # 被闸门拒了 / 半路掉下来（失败也是练）
EXP_MOVE_OK = 4.0       # 一次跨场景移动走完（NPC）
EXP_ERRAND = 8.0        # 办完一件差事（NPC，跑腿本身就是运动）


def _num(v, default):
    """把任意输入变成有限浮点。坏值（None/字符串/NaN/inf）一律回落默认。

    ★ 不抛异常是**刻意的**：档案在 json 里，手写必然出错，
      而这份档案会在启动路径上被读 —— 抛一次就整个宠物起不来。
      「静默降级 + 留痕」在本项目是明确的取舍（见 scene_walk 设计律 2）。
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float(default)
    if f != f or f in (float('inf'), float('-inf')):   # NaN / inf
        return float(default)
    return f


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def default_profile():
    """一份默认档案（全 1.0）。**返回新 dict**，别让调用方改到模块常量上。"""
    return dict(DEFAULT_PROFILE)


def from_dict(d):
    """把 json 里的一条记录变成规范档案。**永不抛异常**。

    缺字段 ⇒ 用默认值；越界 ⇒ 钳回区间；非数字 ⇒ 默认值。
    `evidence` / `why` 原样保留（它们是给人看的，不参与计算）。
    """
    out = default_profile()
    if isinstance(d, dict):
        for k in ('jump', 'run', 'accel', 'growth'):
            lo, hi = LIMITS[k]
            out[k] = _clamp(_num(d.get(k), DEFAULT_PROFILE[k]), lo, hi)
        ev = d.get('evidence')
        out['evidence'] = ev if ev in EVIDENCE_LEVELS else ''
        why = d.get('why')
        out['why'] = why if isinstance(why, str) else ''
    else:
        out['evidence'] = ''
        out['why'] = ''
    return out


def to_dict(profile):
    """规范档案 → 可落 json 的纯数据（只保留已知键，别把内部字段漏出去）。"""
    p = from_dict(profile)
    return {
        'jump': p['jump'], 'run': p['run'], 'accel': p['accel'],
        'growth': p['growth'], 'evidence': p['evidence'], 'why': p['why'],
    }


def level_of(exp):
    """累计经验 → 等级（0 ~ MAX_LEVEL）。坏值按 0 处理。"""
    e = max(0.0, _num(exp, 0.0))
    lv = int(e // LEVEL_STEP)
    return MAX_LEVEL if lv > MAX_LEVEL else lv


def progress_of(exp):
    """当前等级内的进度 0.0 ~ 1.0（满级恒 1.0）。给"快升级了"这类判断用。"""
    e = max(0.0, _num(exp, 0.0))
    if e >= MAX_EXP:
        return 1.0
    return (e % LEVEL_STEP) / LEVEL_STEP


def apply_exp(exp, amount):
    """练一次：加经验，**封顶**、**不退步**（负数不给减）。

    返回新经验值。这是全模块**唯一**改经验的地方 —— 只加不减，
    「不练也不退步」因此是结构性成立的，不靠调用方自觉。
    """
    e = max(0.0, _num(exp, 0.0))
    a = _num(amount, 0.0)
    if a <= 0:
        return e
    e += a
    return MAX_EXP if e > MAX_EXP else e


def effective(profile, exp=0.0):
    """算出**实际生效**的三项倍率（基础 × 成长）。

    返回 `{'jump':x, 'run':y, 'accel':z}`。
    ★ 没练过（exp=0）⇒ 原样返回基础倍率 ⇒ 与"没有这个模块"完全等价。
    """
    p = from_dict(profile)
    lv = level_of(exp)
    mult = 1.0 + GAIN_PER_LEVEL * p['growth'] * lv
    out = {}
    for k in EFF_KEYS:
        lo, hi = LIMITS[k]
        out[k] = _clamp(p[k] * mult, lo, hi * 1.5)
    return out


def effective_tuple(profile, exp=0.0):
    """同 `effective`，但按 `EFF_KEYS` 顺序返回元组（给解包用）。"""
    e = effective(profile, exp)
    return tuple(e[k] for k in EFF_KEYS)


def validate_entry(entry, npc_id=''):
    """校验一条档案。返回**问题列表**（空 = 合格）。

    ★ 这是「防编数据」的硬闸：`why` 必填、`evidence` 必须落在三档里。
      用户 2026-11-06 选的是「每人落值 + 标依据等级」——
      所以"有值"不够，还得能说清这个值是哪来的。
    """
    bad = []
    if not isinstance(entry, dict):
        return ['%s: 不是对象' % npc_id]
    for k in ('jump', 'run', 'accel', 'growth'):
        if k not in entry:
            bad.append('%s: 缺 %s' % (npc_id, k))
            continue
        # ★ 这里**不能**用 `_num(v, None)`：`_num` 的回落分支是 `float(default)`，
        #   `float(None)` 会抛 TypeError —— 校验函数自己先崩，就变成了"坏档案能把
        #   启动路径炸掉"，正好是它要防的事。所以单独 try。
        try:
            v = float(entry.get(k))
        except (TypeError, ValueError):
            bad.append('%s: %s 不是数字' % (npc_id, k))
            continue
        if v != v or v in (float('inf'), float('-inf')):
            bad.append('%s: %s 不是有限数' % (npc_id, k))
            continue
        lo, hi = LIMITS[k]
        if not (lo <= v <= hi):
            bad.append('%s: %s=%s 越界 [%s, %s]' % (npc_id, k, v, lo, hi))
    ev = entry.get('evidence')
    if ev not in EVIDENCE_LEVELS:
        bad.append('%s: evidence=%r 不在三档 %s' % (npc_id, ev, list(EVIDENCE_LEVELS)))
    why = entry.get('why')
    if not isinstance(why, str) or not why.strip():
        bad.append('%s: 缺 why（每人都要给一句依据）' % npc_id)
    return bad
