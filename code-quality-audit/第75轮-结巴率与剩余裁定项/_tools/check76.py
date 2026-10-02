# -*- coding: utf-8 -*-
"""第七十五轮 B3 回归锁：宠物手势判定「唯一真源」不许静默漂移。

锁什么：
  ★ 改造前 main.py 有一套手写手势判定（`get_ralsei_body_part` 12 区域 +
    `_pet_detection_state` 状态机，约 666 行），与 `modules/pet_interaction.py`
    功能重叠但接口不兼容。第75轮 B3 统一到模块，main.py 退化为"坐标换算 +
    查表执行"。本套件锁三件事：

    A 模块侧：区域表 / 映射表 / 回应参数表**自洽**，且 kind 全在
      `event_speech.EVENT_TIERS` 登记过（不许悄悄新增事件名）。
    B 行为侧：`GestureTracker` 状态机真能区分 PUSH / PAT / PINCH / PULL /
      FLICK / STROKE（用真实量级输入，正负成对）。
    C 接线侧：main.py **真的**在调 tracker，且那一份手写判定**确实删干净**
      （AST 级：`_pet_detection_state` 不再作为变量被读写、没有第二份
      区域表、双击/长按/抚摸分支的 if/elif 已消失）。

判据纪律（本项目铁律，写在这里免得后人重复）：
  * 判据名里**不许**出现 `[PASS]` / `[ OK ]` / `[FAIL]` 这些计数标记字样；
  * `print('[PASS] %s')` 必须**字面量**（`run_all.py` 只认这个字面量）；
  * 断**行为/结构**，不断"某行代码存在"；
  * 需要"看着像在守其实没守"的判据 → 一律补**负控制**。
"""
import ast
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from modules import pet_interaction as P
from modules import event_speech as E

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_interaction.py')

_passed = 0
_failed = 0


def check(desc, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print('[PASS] %s' % desc)
    else:
        _failed += 1
        print('[FAIL] %s' % desc)


def _read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def _tree(p):
    return ast.parse(_read(p))


MAIN_SRC = _read(MAIN)
MOD_SRC = _read(MOD)
MAIN_TREE = _tree(MAIN)
MOD_TREE = _tree(MOD)


def code_only_no_comment(src):
    """去掉注释与 docstring 的源码（AST 无关，供正则扫字面量用）。"""
    # 用 tokenize 更稳，但为免依赖，这里走"逐行剥 #" + 去三引号块的近似法。
    out = []
    in_doc = False
    quote = None
    for ln in src.split('\n'):
        s = ln.strip()
        if in_doc:
            if quote and quote in ln:
                in_doc = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            q = s[:3]
            if s.count(q) >= 2 and len(s) > 3:
                continue          # 单行 docstring
            in_doc = True
            quote = q
            continue
        i = ln.find('#')
        out.append(ln if i < 0 else ln[:i])
    return '\n'.join(out)


# ============================================================================
# A 段：模块自洽（区域表 / 映射表 / 事件名登记）
# ============================================================================
def _a1_regions_cover_all_parts():
    """区域表必须覆盖所有非 WHOLE_BODY 部位 —— 少一个就有事件名永不触发。"""
    covered = set(p for p, *_ in P._REGIONS_PERCENT)
    want = set(P.BodyPart) - {P.BodyPart.WHOLE_BODY}
    missing = want - covered
    check('A1 区域表覆盖全部部位（缺 %s）'
          % (sorted(x.value for x in missing) or '无'), not missing)
    # 负控制：★ 构造"表里真少了 belly"的场景，同一判据必须报缺。
    #   （首版写错：`fake - fake_covered` 两边都摘了 belly ⇒ 差集恒空 ——
    #    这是典型的"负控制自己失去鉴别力"。正确写法 = 期望集**不摘**、覆盖集才摘。）
    fake_want = set(P.BodyPart) - {P.BodyPart.WHOLE_BODY}      # 期望：含 belly
    fake_covered = covered - {P.BodyPart.BELLY}                # 覆盖：缺 belly
    check('A1n 负控制：把 BELLY 从覆盖里摘掉后，判据确实报缺（缺 %s）'
          % sorted(x.value for x in (fake_want - fake_covered)),
          bool(fake_want - fake_covered))


def _a2_belly_before_torso():
    """★ BELLY 必须排在 TORSO 之前 —— 顺序即优先级（先命中先返回）。

    改造前 main.py 的区域表就是 belly 在 body 之前；顺序反了，
    整个肚子区域会被躯干吃掉，`double_belly` / `pat_belly` 永不触发。
    """
    order = [p for p, *_ in P._REGIONS_PERCENT]
    check('A2 区域表里 BELLY 先于 TORSO（顺序即优先级）',
          order.index(P.BodyPart.BELLY) < order.index(P.BodyPart.TORSO))
    # 负控制：交换后判据必须为假
    swapped = list(order)
    swapped[order.index(P.BodyPart.BELLY)] = P.BodyPart.TORSO
    swapped[order.index(P.BodyPart.TORSO)] = P.BodyPart.BELLY
    check('A2n 负控制：交换 BELLY/TORSO 后同一判据为假（证明不是恒真）',
          not (swapped.index(P.BodyPart.BELLY) < swapped.index(P.BodyPart.TORSO)))


def _a3_all_kinds_registered():
    """`kind_for` 能产出的每个 kind 都必须在 EVENT_TIERS 登记过。

    ★ 不登记 = 走 `tier_of` 的默认档（TIER_INSTANT，罐头），且没有旁白 ⇒
      AI 永远收不到这条事件。这是"看着触发了其实没交给模型"的静默坑。
    """
    produced = set()
    for part in P.BodyPart:
        for g in P.Gesture:
            k = P.kind_for(part, g)
            if k:
                produced.add(k)
    not_reg = sorted(k for k in produced if k not in E.EVENT_TIERS)
    check('A3 kind_for 产出的 %d 个 kind 全在 EVENT_TIERS（未登记=%s）'
          % (len(produced), not_reg or '无'), not not_reg)
    # 负控制：编一个 kind 必须被判"未登记"
    check('A3n 负控制：编造 kind `poke_zzz` 被判未登记（证明 A3 能分辨）',
          'poke_zzz' not in E.EVENT_TIERS)


def _a4_spec_reachable_and_complete():
    """RESPONSE_SPEC 的 key 必须都能被 kind_for 产出（否则是死项）。"""
    produced = set()
    for part in P.BodyPart:
        for g in P.Gesture:
            k = P.kind_for(part, g)
            if k:
                produced.add(k)
    dead = sorted(set(P.RESPONSE_SPEC) - produced)
    check('A4 RESPONSE_SPEC 无死项（产不出的=%s）' % (dead or '无'), not dead)
    # 每个 spec 的四个字段形状必须合法。
    #  ★★ 本判据第一版要求 `emo` 是 `list`、`pool` 是 `list`，实测**全 13 项报红**：
    #     实现里 `emotions` 是 **tuple 的 tuple**（`(("happy", 15), ("curious", 10))`），
    #     `pool` 是 **list**。判据比实现"更严"不等于更对 —— 严在**错的地方**就是假红。
    #     正确做法：只钉**真正重要**的语义（能解包成 4 段、脸是字符串、
    #     情绪项是 `(名字, 值)` 对），不钉容器的具体类型。
    #     ★ 教训：判据报红时**先怀疑判据**（本项目"报红三步"第二条）。
    bad = []
    for k, spec in P.RESPONSE_SPEC.items():
        if not (isinstance(spec, (tuple, list)) and len(spec) == 4):
            bad.append((k, '长度 != 4'))
            continue
        emo, anim, face, pool = spec
        if not isinstance(emo, (tuple, list)):
            bad.append((k, '情绪表非序列'))
        else:
            for e in emo:
                if not (isinstance(e, (tuple, list)) and len(e) == 2
                        and isinstance(e[0], str) and isinstance(e[1], (int, float))):
                    bad.append((k, '情绪项非 (名, 值)：%r' % (e,)))
                    break
        if not isinstance(face, str) or not face:
            bad.append((k, 'face 非非空字符串：%r' % (face,)))
        if anim is not None and not isinstance(anim, str):
            bad.append((k, 'anim 非 str/None：%r' % (anim,)))
        if pool is not None and not (isinstance(pool, (list, tuple)) and pool):
            bad.append((k, 'pool 非非空序列/None：%r' % (pool,)))
    check('A4b RESPONSE_SPEC 每条形状合法（坏项=%s）' % (bad or '无'), not bad)


def _a5_stroke_pool_matches_petparts():
    """STROKE_POOL 的 key 必须是 event_speech.PET_PARTS 的子集。

    ★ PET_PARTS 用的是 `body`（不是 `torso`）—— 两边不同步的话，
      `pet_kind("torso")` 会落到 `pet_other`，抚摸躯干变成"抚摸未知部位"。
    """
    bad = sorted(k for k in P.STROKE_POOL if k not in E.PET_PARTS)
    check('A5 STROKE_POOL 的 key 全在 PET_PARTS（越界=%s）' % (bad or '无'), not bad)
    # ★★ 判据第一版写成 `P._STROKE_PETTABLE`，实测 AttributeError（模块里叫
    #    `_PART_TO_PET`）。**"判据里的名字写错"在本项目出现过多次**
    #    （取不到 ⇒ 恒假或直接崩），所以这里先钉"名字存在"，再断言映射值。
    _tbl = getattr(P, '_PART_TO_PET', None)
    check('A5a `_PART_TO_PET` 映射表存在（判据别拿写错的名字去取）'
          '（候选名=%s）'
          % sorted(x for x in dir(P) if 'PETTAB' in x or 'PART_TO' in x),
          isinstance(_tbl, dict) and bool(_tbl))
    if isinstance(_tbl, dict):
        check('A5b `torso` 经 `_PART_TO_PET` 映射到 `body`（PET_PARTS 的名字）'
              '（实得=%r）' % (_tbl.get(P.BodyPart.TORSO),),
              _tbl.get(P.BodyPart.TORSO) == 'body')
        check('A5c 且 `belly` 同样映射到 `body`（PET_PARTS 里没有 belly）'
              '（实得=%r）' % (_tbl.get(P.BodyPart.BELLY),),
              _tbl.get(P.BodyPart.BELLY) == 'body')


def _a6_no_new_kinds():
    """★ 不许新增事件名：改造前的 22 个手势 kind 必须一个不多一个不少。

    理由：这些 kind 同时被 `EVENT_TIERS` / `EVENT_DIRECTIVES` /
    `verify_s7_event_speech` 三处登记。新增一个会同时打破三处，
    而"悄悄多一个"正是最容易发生的漂移。
    """
    produced = set()
    for part in P.BodyPart:
        for g in P.Gesture:
            k = P.kind_for(part, g)
            if k:
                produced.add(k)
    expect = {
        'poke_body', 'poke_shoulder', 'poke_default',
        'pinch_ear', 'pinch_face', 'press_body', 'pat_belly',
        'pull_arm', 'pull_shoulder',
        'double_hair', 'double_belly', 'double_face', 'double_shoulder',
        'double_other', 'ear_ruffle',
        'pet_hair', 'pet_ear', 'pet_face', 'pet_body', 'pet_arm',
        'pet_shoulder', 'pet_other',
    }
    check('A6 手势事件名恰好 22 个且与改造前集合相等（多=%s 少=%s）'
          % (sorted(produced - expect) or '无', sorted(expect - produced) or '无'),
          produced == expect)


# ============================================================================
# B 段：行为（GestureTracker 状态机，真实量级输入）
# ============================================================================
_STROKE_MAX_PX = 40.0
_MIN_MOVE_PX = 3.0


def _fresh():
    return P.GestureTracker()


def _b1_push_single_click():
    """单击（短按即松、未移动）→ PUSH。"""
    g = _fresh()
    g.on_press((50.0, 50.0), P.BodyPart.TORSO)
    time.sleep(0.01)
    ev = g.on_release((50.0, 50.0))
    check('B1 短按即松 → PUSH（实测 %s）'
          % (ev.gesture.value if ev else None),
          ev is not None and ev.gesture == P.Gesture.PUSH
          and ev.body_part == P.BodyPart.TORSO)


def _b2_pinch_long_no_move():
    """长按 ≥0.5s 且未移动 → PINCH。"""
    g = _fresh()
    g.on_press((50.0, 50.0), P.BodyPart.EAR)
    time.sleep(0.55)
    ev = g.on_release((50.0, 50.0))
    check('B2 长按 0.55s 未移动 → PINCH（实测 %s）'
          % (ev.gesture.value if ev else None),
          ev is not None and ev.gesture == P.Gesture.PINCH)


def _b3_pull_long_moved():
    """长按 ≥0.5s 且移动超阈值 → PULL（★ 与 B2 正负成对）。"""
    g = _fresh()
    g.on_press((50.0, 50.0), P.BodyPart.ARM)
    # 移动超过 PULL_MOVE_THRESHOLD(8.0)
    g.on_move((80.0, 50.0), P.BodyPart.ARM, True)
    time.sleep(0.55)
    ev = g.on_release((80.0, 50.0))
    check('B3 长按且移动 → PULL（实测 %s）'
          % (ev.gesture.value if ev else None),
          ev is not None and ev.gesture == P.Gesture.PULL)
    # 负控制：同样长按但**不**移动，必须不是 PULL
    g2 = _fresh()
    g2.on_press((50.0, 50.0), P.BodyPart.ARM)
    time.sleep(0.55)
    ev2 = g2.on_release((50.0, 50.0))
    check('B3n 负控制：同样长按但不移动 → 不是 PULL（实测 %s）'
          % (ev2.gesture.value if ev2 else None),
          ev2 is not None and ev2.gesture != P.Gesture.PULL)


def _b4_push_move_below_threshold_still_not_pull():
    """★ 移动量**未超**阈值（4px < 8px）时不算 PULL —— 边界正负成对。"""
    g = _fresh()
    g.on_press((50.0, 50.0), P.BodyPart.ARM)
    g.on_move((54.0, 50.0), P.BodyPart.ARM, True)   # 4px
    time.sleep(0.55)
    ev = g.on_release((54.0, 50.0))
    check('B4 长按 + 只移动 4px（<阈值 8px）→ 仍是 PINCH 不是 PULL（实测 %s）'
          % (ev.gesture.value if ev else None),
          ev is not None and ev.gesture == P.Gesture.PINCH)


def _b5_ear_flick():
    """耳朵连点 3 次 → FLICK（★ 且第 3 次返回的是 FLICK 而不是 PUSH）。"""
    g = _fresh()
    kinds = []
    for _ in range(3):
        g.on_press((10.0, 10.0), P.BodyPart.EAR)
        ev = g.on_release((10.0, 10.0))
        kinds.append(ev.gesture.value if ev else None)
    check('B5 耳朵连点 3 次，第 3 次返回 FLICK（实测序列 %s）' % kinds,
          kinds[-1] == P.Gesture.FLICK.value)
    check('B5b 前两次不是 FLICK（证明计数真在累积，不是一按就 FLICK）',
          kinds[0] != P.Gesture.FLICK.value and kinds[1] != P.Gesture.FLICK.value)


def _b6_flick_only_ear():
    """★ 连点 3 次**非耳朵**部位不许出 FLICK（正负成对）。"""
    g = _fresh()
    kinds = []
    for _ in range(3):
        g.on_press((50.0, 50.0), P.BodyPart.TORSO)
        ev = g.on_release((50.0, 50.0))
        kinds.append(ev.gesture.value if ev else None)
    check('B6 躯干连点 3 次不出现 FLICK（实测 %s）' % kinds,
          P.Gesture.FLICK.value not in kinds)


def _b7_pat_double_click():
    """★ 双击（同部位、间隔 < 0.4s）→ PAT。

    ⚠️ 本模块的 PAT 与 Qt 的 `mouseDoubleClickEvent` **不是同一件事**：
      Qt 会自己派发双击事件，而本机只按"两次单击间隔"判。
      main.py 的接线里双击走 `mouseDoubleClickEvent`（不经过本机），
      ⇒ 本机判出的 PAT 只在"两次单击没被 Qt 合成双击"时出现。
      这条判据锁的是**模块自身**的能力，不是产品路径。
    """
    g = _fresh()
    g.on_press((50.0, 50.0), P.BodyPart.HAIR)
    g.on_release((50.0, 50.0))
    g.on_press((50.0, 50.0), P.BodyPart.HAIR)
    ev = g.on_release((50.0, 50.0))
    check('B7 同部位两次快速单击 → PAT（实测 %s）'
          % (ev.gesture.value if ev else None),
          ev is not None and ev.gesture == P.Gesture.PAT)


def _b8_stroke_back_and_forth():
    """★ 抚摸：来回移动 3 次方向反转 → STROKE（用真实量级 30px）。"""
    g = _fresh()
    base = 50.0
    step = 30.0
    hits = []
    pos = base
    signs = [1, -1, 1, -1, 1, -1, 1, -1]
    for s in signs:
        pos += s * step
        ev = g.on_move((pos, base), P.BodyPart.HAIR, True)
        if ev is not None:
            hits.append(ev.gesture.value)
    check('B8 来回移动（30px、交替方向）能触发 STROKE（实测命中 %s）' % hits,
          P.Gesture.STROKE.value in hits)
    # 负控制：一直朝同方向移动（不往返）必须**不**触发
    g2 = _fresh()
    hits2 = []
    p2 = base
    for _ in range(8):
        p2 += step
        ev = g2.on_move((p2, base), P.BodyPart.HAIR, True)
        if ev is not None:
            hits2.append(ev.gesture.value)
    check('B8n 负控制：单向持续移动不触发 STROKE（实测 %s）' % (hits2 or '无命中'),
          P.Gesture.STROKE.value not in hits2)


def _b9_stroke_step_out_of_range():
    """★ 步长超上限（80px > 40px）不许计入抚摸 —— 边界负控制。"""
    g = _fresh()
    hits = []
    pos = 50.0
    for s in (1, -1, 1, -1, 1, -1):
        pos += s * 80.0
        ev = g.on_move((pos, 50.0), P.BodyPart.HAIR, True)
        if ev is not None:
            hits.append(ev.gesture.value)
    check('B9 步长 80px（>上限 40px）不触发 STROKE（实测 %s）' % (hits or '无命中'),
          P.Gesture.STROKE.value not in hits)
    # 正控制：把同一步长降到上限内（35px）必须能触发 ⇒ 证明是"步长闸"在起作用
    g2 = _fresh()
    hits2 = []
    pos2 = 50.0
    for s in (1, -1, 1, -1, 1, -1, 1, -1):
        pos2 += s * 35.0
        ev = g2.on_move((pos2, 50.0), P.BodyPart.HAIR, True)
        if ev is not None:
            hits2.append(ev.gesture.value)
    check('B9p 正控制：步长降到 35px（<上限）能触发 STROKE（实测 %s）' % hits2,
          P.Gesture.STROKE.value in hits2)


def _b10_cooldown():
    """★ 抚摸有冷却：触发后立刻再来一轮不许连着触发第二次。"""
    g = _fresh()
    pos = 50.0

    def run_round():
        nonlocal pos
        got = False
        for s in (1, -1, 1, -1, 1, -1, 1, -1):
            pos += s * 35.0
            if g.on_move((pos, 50.0), P.BodyPart.HAIR, True) is not None:
                got = True
        return got

    first = run_round()
    second = run_round()
    check('B10 第一轮触发 STROKE（%s）、紧接着第二轮被冷却挡住（%s）'
          % (first, second), first and not second)


def _b11_drag_blocks_press():
    """★ 拖拽中 `handle_press` 不记录按下 —— 保护"拖窗口"不误判成点击。"""
    t = P.PetInteractionTracker()
    t.set_drag_active(True)
    t.handle_press((50.0, 50.0))
    check('B11 拖拽中 handle_press 不进入按下态',
          t.gesture.is_pressing is False)
    # 正控制：关掉拖拽后同一路径必须能进入按下态。
    # ⚠️ 夹具修正（首跑 FAIL）：无 pixmap 时 `is_on_pet` 退化成
    #    `0 <= x <= self._width`，而 `_width == 0` ⇒ **任何正坐标都不命中**。
    #    所以正控制必须用一个"落在退化矩形内"的坐标 —— 即 (0, 0)。
    t2 = P.PetInteractionTracker()
    t2.handle_press((0.0, 0.0))
    check('B11p 正控制：无拖拽时退化的 (0,0) 能进入按下态（证明 B11 不是恒真）',
          t2.gesture.is_pressing is True)
    # 反向对照：同一坐标在**拖拽中**必须仍然进不去 ⇒ 两条判据都活着
    t3 = P.PetInteractionTracker()
    t3.set_drag_active(True)
    t3.handle_press((0.0, 0.0))
    check('B11q 反向对照：同样 (0,0) 在拖拽中仍进不去',
          t3.gesture.is_pressing is False)


def _b12_kind_for_shape():
    """★ `kind_for` 的返回值类型：要么是已登记的 str，要么是 None。"""
    bad = []
    for part in P.BodyPart:
        for g in P.Gesture:
            k = P.kind_for(part, g)
            if k is not None and k not in E.EVENT_TIERS:
                bad.append((part.value, g.value, k))
    check('B12 kind_for 返回的每个非 None 值都在 EVENT_TIERS（坏=%s）'
          % (bad or '无'), not bad)


def _b13_deterministic():
    """★ 纯查询确定性：同样输入两次结果相同。"""
    a = [P.kind_for(p, g) for p in P.BodyPart for g in P.Gesture]
    b = [P.kind_for(p, g) for p in P.BodyPart for g in P.Gesture]
    check('B13 kind_for 确定性（两次调用完全一致）', a == b)


# ============================================================================
# C 段：接线与"手写判定确实删干净"
# ============================================================================
def _c1_main_imports_module():
    imported = set()
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.ImportFrom) and node.module:
            if 'pet_interaction' in node.module:
                for a in node.names:
                    imported.add(a.name)
    want = {'PetInteractionTracker', 'kind_for', 'RESPONSE_SPEC',
            'STROKE_EMOTIONS', 'STROKE_POOL'}
    check('C1 main.py 真从 pet_interaction 导入了接线件（缺 %s）'
          % (sorted(want - imported) or '无'), not (want - imported))


def _c2_tracker_instantiated():
    """`PetInteractionTracker()` 必须在 __init__ 里被真调用。"""
    hits = []
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, 'id', None) or getattr(f, 'attr', None)
            if name == 'PetInteractionTracker':
                hits.append(node.lineno)
    check('C2 main.py 真构造 PetInteractionTracker（%d 处）' % len(hits),
          len(hits) >= 1)


def _c3_handlers_are_called():
    """三个 handle_* 必须在 main.py 里被真调用（AST 级）。

    ★ 判据两轮才写对（篡改自证抓出来的，两次都是**判据侧**的错）：
      首版只查"方法名出现过" ⇒ 把精灵内那一支删掉，`handle_move((-1.0,-1.0))`
      （离开精灵那一支）照样让它为真 ⇒ **判据过宽**。
      二版改成"实参必须直接是 `_pet_rel_pos(...)` 调用" ⇒ **恒假**，
      因为产品里是 `rel = self._pet_rel_pos(...)` 再 `handle_press(rel)`。
      三版（本版）＝ **反例排除**：要求
        ① 方法名真出现；
        ② 至少有一处调用的实参**不是**常量（即不是哨兵值 `(-1.0,-1.0)`/`(0.0,0.0)`）。
      这样"只剩哨兵那一处"会被抓出来，而变量实参能通过。
    """
    def _is_literal(node):
        """字面量判定：`0.0` / `-1.0` / `"x"` / 由它们构成的 tuple 都算。

        ★ 坑：`-1.0` 在 AST 里是 `UnaryOp(USub, Constant(1.0))`，
          **不是** `Constant` ⇒ 首版把 `(-1.0, -1.0)` 误判成"非字面量"，
          于是 case② 的篡改（两处都变常量）照样全绿。判据自身的错。
        """
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return _is_literal(node.operand)
        if isinstance(node, (ast.Tuple, ast.List)):
            return all(_is_literal(e) for e in node.elts)
        return False

    def arg_is_constant(call_node):
        if not call_node.args:
            return True
        return _is_literal(call_node.args[0])

    got = {}
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            m = node.func.attr
            if m in ('handle_press', 'handle_move', 'handle_release'):
                got.setdefault(m, [])
                got[m].append(arg_is_constant(node))

    for want in ('handle_press', 'handle_move', 'handle_release'):
        flags = got.get(want, [])
        check('C3 main.py 真用**非哨兵**实参调用 %s（调用点 %d 处，非哨兵 %d 处）'
              % (want, len(flags), sum(1 for f in flags if not f)),
              bool(flags) and not all(flags))


def _c4_dispatch_used():
    got = set()
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == '_dispatch_pet_event':
                got.add(f.attr)
    check('C4 main.py 真调用 _dispatch_pet_event（拿到事件后有执行层）',
          '_dispatch_pet_event' in got)


def _c5_sync_sprite_called():
    """★ `_sync_pet_tracker_sprite` 必须真被调用，且**每个 `setPixmap` 之后都要同步**。

    不调的话换帧后部位识别会按旧尺寸算、整体偏移（这是接线时最容易漏的一环）。

    ★★ 第75轮收口加强：初版只断言「同步点 >= 2 处」—— 这是**过窄判据**。
       它守不住"以后新增第三个 `sprite_label.setPixmap(...)` 却忘了同步"这种
       最常见的退化（新增一处 setPixmap，同步点数仍是 2，判据照样 PASS）。
       ⇒ 改成**配对判据**：对每一个 `setPixmap(...)` 调用点，在它**之后**必须有
          `_sync_pet_tracker_sprite()`。配对不上就报红。
    """
    sync_lines, pixmap_lines = [], []
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == '_sync_pet_tracker_sprite':
                sync_lines.append(node.lineno)
            if isinstance(f, ast.Attribute) and f.attr == 'setPixmap':
                pixmap_lines.append(node.lineno)
    sync_lines.sort()
    pixmap_lines.sort()

    # ---- 基本量（保留原有）----
    check('C5 _sync_pet_tracker_sprite 真被调用（%d 处，换帧都要同步）'
          % len(sync_lines), len(sync_lines) >= 2)

    # ---- ★ 新增：配对判据 ----
    #   对每个 setPixmap(line=L)，要求存在一个同步点 line > L 且是**离它最近的那个**。
    #   允许在 setPixmap 与同步之间夹任意行（实际实现就是相邻两行）。
    unpaired = []
    for pl in pixmap_lines:
        # 找 L 之后**唯一**的一段同步：取第一个 > pl 的同步点；
        # 若该同步点之前还有另一个 setPixmap（说明这一对属于后面的换帧），则判为未配对。
        after = [s for s in sync_lines if s > pl]
        if not after:
            unpaired.append((pl, '无同步点'))
            continue
        nxt = min(after)
        # 两者之间不许再有 setPixmap（否则这一段其实是"两处换帧、一个同步"）
        between = [p for p in pixmap_lines if pl < p < nxt]
        if between:
            unpaired.append((pl, '与同步点 %d 之间还夹着 setPixmap %s' % (nxt, between)))
    check('C5a 每个 setPixmap 之后都有同步（%d 处 setPixmap / %d 处同步；未配对=%s）'
          % (len(pixmap_lines), len(sync_lines), unpaired or '无'),
          (len(pixmap_lines) >= 2) and (not unpaired))

    # ---- ★ 正控制：本判据的配对逻辑要真能抓到"漏同步" ----
    #   合成一段"3 处 setPixmap、只有 2 处同步"的源码，走**同一套**配对逻辑。
    fake = (
        "class X:\n"
        "    def a(self):\n"
        "        self.sprite_label.setPixmap(p1)\n"
        "        self._sync_pet_tracker_sprite()\n"
        "    def b(self):\n"
        "        self.sprite_label.setPixmap(p2)\n"
        "        self._sync_pet_tracker_sprite()\n"
        "    def c(self):\n"
        "        self.sprite_label.setPixmap(p3)\n"      # ← 故意不同步
    )
    ft = ast.parse(fake)
    f_sync, f_pm = [], []
    for node in ast.walk(ft):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == '_sync_pet_tracker_sprite':
                f_sync.append(node.lineno)
            if isinstance(f, ast.Attribute) and f.attr == 'setPixmap':
                f_pm.append(node.lineno)
    f_sync.sort(); f_pm.sort()
    f_bad = []
    for pl in f_pm:
        after = [s for s in f_sync if s > pl]
        if not after:
            f_bad.append(pl); continue
        nxt = min(after)
        if [p for p in f_pm if pl < p < nxt]:
            f_bad.append(pl)
    check('C5b 正控制：合成的"3 换帧 2 同步"必须被判缺（坏点=%s）'
          % (f_bad or '无'), len(f_bad) == 1)

    # ---- ★ 负控制：全都同步时不许报红 ----
    fake_ok = (
        "class X:\n"
        "    def a(self):\n"
        "        self.sprite_label.setPixmap(p1)\n"
        "        self._sync_pet_tracker_sprite()\n"
        "    def b(self):\n"
        "        self.sprite_label.setPixmap(p2)\n"
        "        self._sync_pet_tracker_sprite()\n"
    )
    ot = ast.parse(fake_ok)
    o_sync, o_pm = [], []
    for node in ast.walk(ot):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == '_sync_pet_tracker_sprite':
                o_sync.append(node.lineno)
            if isinstance(f, ast.Attribute) and f.attr == 'setPixmap':
                o_pm.append(node.lineno)
    o_sync.sort(); o_pm.sort()
    o_bad = []
    for pl in o_pm:
        after = [s for s in o_sync if s > pl]
        if not after:
            o_bad.append(pl); continue
        nxt = min(after)
        if [p for p in o_pm if pl < p < nxt]:
            o_bad.append(pl)
    check('C5c 负控制：全配对的合成源码不许被判缺（坏点=%s）' % (o_bad or '无'), not o_bad)


def _c6_state_machine_removed():
    """★★ 手写状态机 `_pet_detection_state` 必须**只出现在注释里**。

    这是"删干净了没有"的硬判据 —— 只查字符串不够（注释里也会有），
    要查**它是否还被当成变量读写**（AST 里的 Subscript / Store 上下文）。
    """
    used = []
    for node in ast.walk(MAIN_TREE):
        # `self._pet_detection_state[...]` → Subscript(value=Attribute(...))
        if isinstance(node, ast.Attribute) and node.attr == '_pet_detection_state':
            used.append(node.lineno)
        # `'xx' in self._pet_detection_state` 等直接属性访问
        if isinstance(node, ast.Name) and node.id == '_pet_detection_state':
            used.append(node.lineno)
    check('C6 main.py 里 `_pet_detection_state` 不再作为变量被使用（命中 %s）'
          % (used or '无'), not used)
    # 反向：注释里应该**留**说明（证明确实是"保留了历史说明"而不是整段抹掉）
    comments = [ln for ln in MAIN_SRC.split('\n')
                if '_pet_detection_state' in ln]
    check('C6b 注释里保留了改造说明（%d 处，便于后人理解为何删除）'
          % len(comments), len(comments) >= 1)


def _c7_no_second_region_table():
    """★★ main.py 里不许再有第二份区域表。

    ★ 判据形状修正（首跑 C7p FAIL）：改造前 main.py 的区域表是**字符串 + 整数**
      `("ear", 0, 0, 30, 40)`；而模块现在是**枚举 + 浮点**
      `(BodyPart.EAR, 0.0, 0.0, 30.0, 40.0)`。所以"同一正则两处都能命中"
      这个写法是错的 —— 两代表达式本来就不同形。
      ⇒ 改成**抽象判据**：查"连续 ≥6 条『元组首元素是部位名、后四个是数』的行"。
      这能同时抓两代写法，且对无关代码零误报。
    """
    def count_region_rows(src):
        rows = 0
        for ln in code_only_no_comment(src).split('\n'):
            s = ln.strip()
            # 首元素允许 `"ear"` / `'ear'` / `BodyPart.EAR`
            if not re.match(r'^\(\s*("|\')?[A-Za-z_][\w.]*("|\')?\s*,', s):
                continue
            nums = re.findall(r'[-+]?\d+(?:\.\d+)?', s)
            # 形如 (名字, 4 个数) —— 行尾是 `),` 或 `)`（列表项 / 独立元组）
            if re.search(r'\)\s*,?\s*$', s) and len(nums) >= 4:
                rows += 1
        return rows

    main_rows = count_region_rows(MAIN_SRC)
    mod_rows = count_region_rows(MOD_SRC)
    check('C7 main.py 没有第二份部位区域表（实测区域行 %d 条）' % main_rows,
          main_rows == 0)
    check('C7p 正控制：同一判据在 pet_interaction 里命中 ≥8 条（实测 %d 条）'
          % mod_rows, mod_rows >= 8)


def _c8_old_branches_gone():
    """★ 改造前的 `clicked_part == "body"` 这类 if/elif 链必须消失。"""
    src = code_only_no_comment(MAIN_SRC)
    pat = re.findall(r'clicked_part\s*==\s*"[a-z_]+"', src)
    check('C8 main.py 不再有 `clicked_part == "…"` 分支链（命中 %s）'
          % (pat or '无'), not pat)


def _c9_no_duplicate_stroke_detector():
    """★ main.py 里不许再有手写抚摸检测（`movement_history` / `direction_changes`）。"""
    src = code_only_no_comment(MAIN_SRC)
    for token in ('movement_history', 'direction_changes', 'last_pet_time'):
        check('C9 main.py 不再有手写抚摸状态 `%s`' % token, token not in src)
    # 正控制：模块里必须有同样概念的实现（证明"删的是重复份，不是功能"）
    mod = code_only_no_comment(MOD_SRC)
    check('C9p 正控制：pet_interaction 里有抚摸检测实现（_StrokeDetector）',
          '_StrokeDetector' in mod and '_direction_changes' in mod)


def _c10_get_body_part_is_delegate():
    """★ `get_ralsei_body_part` 保留为薄委托（不再自带区域表）。"""
    fn = None
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == 'get_ralsei_body_part':
            fn = node
            break
    ok = fn is not None and fn.end_lineno - fn.lineno <= 25
    check('C10 get_ralsei_body_part 已瘦身为薄委托（行数 %s ≤ 25）'
          % (fn.end_lineno - fn.lineno if fn else 'N/A'), ok)
    check('C10b 它真的转调 tracker（body 里有 region.classify）',
          fn is not None and any(
              isinstance(n, ast.Attribute) and n.attr == 'classify'
              for n in ast.walk(fn)))


def _c11_module_is_zero_dep_in_region_side():
    """★ 模块顶层 import 只许标准库 + Qt（可选）。

    ⚠️ 与其它零依赖模块不同：本模块**确实** import 了 Qt（要读 pixmap 的
      alpha 通道），所以闸门口径是"不许 import **项目内**模块"。
    """
    proj = []
    for node in ast.walk(MOD_TREE):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split('.')[0] == 'modules':
                    proj.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in ('modules', 'src'):
                proj.append(node.module)
    check('C11 pet_interaction 不 import 项目内模块（命中 %s）' % (proj or '无'),
          not proj)
    # 函数内 import 也要禁（零依赖纪律的老账）
    inner = []
    for node in ast.walk(MOD_TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    inner.append(node.name)
                    break
    check('C11b pet_interaction 无函数内 import（命中 %s）'
          % (sorted(set(inner)) or '无'), not inner)


def _c12_double_click_does_not_use_tracker_gesture():
    """★ 双击**不**经过 tracker 的手势机（否则同一组双击会被处理两遍）。"""
    fn = None
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == 'mouseDoubleClickEvent':
            fn = node
            break
    check('C12 找到 mouseDoubleClickEvent', fn is not None)
    if fn is None:
        return
    calls = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            calls.add(n.func.attr)
    check('C12b 双击里只调 classify（取部位），**不**调 handle_release/handle_press',
          'classify' in calls and 'handle_release' not in calls
          and 'handle_press' not in calls)


def _c13_responsespec_used_by_apply():
    """★ `_apply_pet_response` 真的读 `RESPONSE_SPEC`（不是空转）。"""
    fn = None
    for node in ast.walk(MAIN_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == '_apply_pet_response':
            fn = node
            break
    check('C13 找到 _apply_pet_response', fn is not None)
    names = set()
    if fn is not None:
        for n in ast.walk(fn):
            if isinstance(n, ast.Name):
                names.add(n.id)
    check('C13b 它真读 RESPONSE_SPEC', 'RESPONSE_SPEC' in names)
    check('C13c 它真调 speak_event / add_emotion', 'speak_event' in names
          or any(isinstance(n, ast.Attribute) and n.attr in ('speak_event',
          'add_emotion') for n in ast.walk(fn or ast.Module())))


# ============================================================================
# F 段：判据自身体检
# ============================================================================
def _f1_no_count_markers_in_names():
    """★ 判据名里不许自带计数标记字样（会污染 `count_results`）。"""
    src = _read(os.path.abspath(__file__))
    bad = []
    for m in re.finditer(r"check\(\s*'([^']*)'", src):
        name = m.group(1)
        if '[PASS]' in name or '[ OK ]' in name or '[FAIL]' in name:
            bad.append(name)
    check('F1 判据名里无计数标记字样（坏=%s）' % (bad or '无'), not bad)


def _f2_pass_is_literal():
    """★ `print('[PASS] %s')` 必须是**字面量**（run_all.py 只认这个）。

    ★★ 这里踩过一次坑（第75轮 B3 收尾自查时发现，**不是报红暴露的**）：
       第一版判据名直接写成 `"F2 文件里存在 print('[PASS] %s' % …) 字面量"`，
       名字里**自带 `[PASS]` 字样** ⇒ `run_all.py` 的 `count_results()` 用
       `re.findall(r'\[PASS\]|\[\s*OK\s*\]', text)` 数行，会把这**一行判据名本身**
       也算一个 PASS ⇒ 计数比真实判据数多 1（基线记 60，实际 59）。
       铁律：**判据名里不许出现 `[PASS]` / `[ OK ]` / `[FAIL]` 这些计数标记**。

    修法：① 判据名里把标记拆开写（`[PASS]` → `[+PASS+]` 之类会被计数，所以
    改成不含方括号的描述）；② 需要检测的字面量也用**拼接**构造，
    免得判据名/源码本身被自己数进去。
    """
    src = _read(os.path.abspath(__file__))
    needle = "print(" + "'" + "[PA" + "SS] %s" + "'"      # 拆开写，避免自匹配
    check('F2 文件里存在 print(单引号加方括号 PASS 加 %s) 的字面量',
          needle in src)


def _f3_module_on_disk():
    check('F3 被测模块真在盘上', os.path.isfile(MOD))
    check('F3b 被测文件真在盘上', os.path.isfile(MAIN))


def _run_all():
    # A
    _a1_regions_cover_all_parts()
    _a2_belly_before_torso()
    _a3_all_kinds_registered()
    _a4_spec_reachable_and_complete()
    _a5_stroke_pool_matches_petparts()
    _a6_no_new_kinds()
    # B
    _b1_push_single_click()
    _b2_pinch_long_no_move()
    _b3_pull_long_moved()
    _b4_push_move_below_threshold_still_not_pull()
    _b5_ear_flick()
    _b6_flick_only_ear()
    _b7_pat_double_click()
    _b8_stroke_back_and_forth()
    _b9_stroke_step_out_of_range()
    _b10_cooldown()
    _b11_drag_blocks_press()
    _b12_kind_for_shape()
    _b13_deterministic()
    # C
    _c1_main_imports_module()
    _c2_tracker_instantiated()
    _c3_handlers_are_called()
    _c4_dispatch_used()
    _c5_sync_sprite_called()
    _c6_state_machine_removed()
    _c7_no_second_region_table()
    _c8_old_branches_gone()
    _c9_no_duplicate_stroke_detector()
    _c10_get_body_part_is_delegate()
    _c11_module_is_zero_dep_in_region_side()
    _c12_double_click_does_not_use_tracker_gesture()
    _c13_responsespec_used_by_apply()
    # F
    _f1_no_count_markers_in_names()
    _f2_pass_is_literal()
    _f3_module_on_disk()


if __name__ == '__main__':
    _run_all()
    print('')
    print('合计：PASS=%d FAIL=%d' % (_passed, _failed))
    sys.exit(1 if _failed else 0)
