# -*- coding: utf-8 -*-
"""第46轮 · 「伙伴交互系统框架」回归锁（L1 companion / L2 companion_dialog / L3 companion_roster）

配套模块：
  · `ralsei_pet/modules/companion.py`         （L1 实体层，零依赖）
  · `ralsei_pet/modules/companion_dialog.py`  （L2 对话层，发言人标识协议）
  · `ralsei_pet/modules/companion_roster.py`  （L3 调度层，名册/轮转/跟随）

用户口径（第 46 轮原文）：
  「嵌入一下和伙伴的交互系统，方便以后多宠物互相互动」
  「那个交互系统你仔细研究一下吧，就是到时候能做到和真人间对话一样就好」
  「一般来说并不会有多个 AI 同时运行的场景，当然，如果可以的话，多个一起运行
    也看不出端倪那也行」
  「要让他们能有自主互相聊天的功能，但不会导致 AI 之间分不清是谁和谁说话」
  「跟随系统这类的按原作的就行，还是跟随 kris 如果 kris 在的话，当然，也可自主
    行动，只是在需要统一行动时跟随」
  「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」

★ 纪律（与 G2 其它套件同源）：
  1. 每条断言 **必须** `print('[PASS] ...')` 字面量（`run_all.py` 按它计数）；
  2. **正/负控制成对**（报了 A 也要证明"反过来不报"）；
  3. **行为判据必须用真实量级输入**（200 帧跟随、1200 次 tick，不是 2 次小玩具）；
  4. **不实例化 App、不需要显示器、不联网**（纯函数 + 真数据）。

★ 本套件守的不是"代码跑得起来"，而是三件容易静默失效的事：
  · **身份不许被猜** —— 消息缺 `from_id` 必须被拒，且不许进历史；
  · **锁必须能释放** —— 交互对象抛异常时全局锁不许卡死（卡死 = 交互系统全瘫）；
  · **不许并发** —— 轮转调度任一时刻最多一个伙伴在生成。
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
MAIN_PY = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')

if MODS not in sys.path:
    sys.path.insert(0, MODS)

PASS = 0
FAIL = 0


def check(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % name)
    else:
        FAIL += 1
        print('[FAIL] %s %s' % (name, extra))


def section(title):
    print()
    print('== %s ==' % title)


def io_read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


# ===========================================================================
#  AST 小工具
# ===========================================================================

def _imports_of(src, top_level=True):
    """收集 import 的顶层包名。`top_level=True` 只收模块级，False 只收函数/类内。"""
    out = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out

    class V(ast.NodeVisitor):
        def __init__(self):
            self.depth = 0

        def _hit(self, names):
            if (self.depth == 0) == top_level:
                out.update(names)

        def visit_Import(self, node):
            self._hit([a.name.split('.')[0] for a in node.names])

        def visit_ImportFrom(self, node):
            if node.module:
                self._hit([node.module.split('.')[0]])
            else:
                self._hit(['.' * max(1, node.level)])

        def visit_FunctionDef(self, node):
            self.depth += 1
            self.generic_visit(node)
            self.depth -= 1

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            self.depth += 1
            self.generic_visit(node)
            self.depth -= 1

    V().visit(tree)
    return out


_QT_MODULES = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6'}
#: 三个模块的**顶层**依赖白名单。★ 一律不许有函数内 import（见 A4）——
#: 依赖全部写在文件顶部，AST 才能"一次看全"，不用管调用路径。
_DEP_ALLOWED = {
    'companion': {'collections', 'logging', 'math'},
    'companion_dialog': {'collections', 'dataclasses', 'logging', 're', 'companion'},
    'companion_roster': {'logging', 'companion', 'companion_dialog'},
}
#: 允许出现在这三个模块里的项目内模块名（用于 A5 的 AST 判定）。
_PROJECT_MODS = {'companion', 'companion_dialog', 'companion_roster',
                 'scene_system', 'scene_routing', 'scene_camera', 'scene_render',
                 'scene_pathfind', 'scene_walk', 'scene_controller'}


def func_rally_lag(c):
    """把伙伴临时切到 RALLY 取 effective_lag，然后还原原模式。"""
    keep = c.mode
    c.set_mode('rally')
    v = c.effective_lag
    c.set_mode(keep)
    return v


def main():
    print('=== 第46轮 伙伴交互系统框架 回归锁 ===')
    print('模块目录: %s' % MODS)

    files = {}
    missing = []
    for name in ('companion', 'companion_dialog', 'companion_roster'):
        p = os.path.join(MODS, name + '.py')
        if not os.path.isfile(p):
            missing.append(p)
            continue
        files[name] = io_read(p)
    check('A0 三个骨架模块都存在', not missing, '缺失=%r' % missing)
    if missing:
        print()
        print('RESULT: PASS=%d FAIL=%d' % (PASS, FAIL))
        return 1

    src_all = '\n'.join(files.values())

    # =======================================================================
    section('A 模块纪律（零 Qt / 依赖白名单）')
    # =======================================================================
    for name, src in files.items():
        check('A1.%s 源码不含 PyQt / PySide 字样' % name,
              not any(q in src for q in sorted(_QT_MODULES)))
    # 负控制：先证明解析器真能抓到 Qt，否则 A1 是恒真判据
    _fake = 'import PyQt5.QtCore\nfrom PySide6 import QtWidgets\n'
    check('A1b 负控制：解析器能抓到 Qt 导入（A1 有鉴别力）',
          bool(_imports_of(_fake) & _QT_MODULES),
          'got=%s' % sorted(_imports_of(_fake)))
    check('A1c 负控制：假样本里确实有 import（A1b 的前提）',
          'import ' in _fake)

    for name, src in files.items():
        got = _imports_of(src, top_level=True)
        over = got - _DEP_ALLOWED[name]
        check('A2.%s 顶层 import 不越界（只准 %s）' % (name, sorted(_DEP_ALLOWED[name])),
              not over, 'imports=%s 越界=%s' % (sorted(got), sorted(over)))

    local = _imports_of(files['companion_dialog'], top_level=False)
    check('A3 companion_dialog 顶层依赖含 companion（L2 允许依赖 L1）',
          'companion' in _imports_of(files['companion_dialog'], top_level=True))
    # ★★ 首版 A4 写成"companion / companion_roster 的函数内没有 import" ——
    #    结果它报红：`companion_roster.select_mode` 里其实有 `from companion import ...`。
    #    **判据没错，是我的代码错了**（局部 import 藏在函数里，静态审计看不全）。
    #    于是改成一条更强的、对三个模块一律成立的不变量：**零函数内 import**。
    for name in sorted(files):
        check('A4.%s 没有函数 / 类内 import（依赖必须全在文件顶部）' % name,
              not _imports_of(files[name], top_level=False),
              'local=%s' % sorted(_imports_of(files[name], top_level=False)))

    # ★ 设计决策锁：跟随**不独立寻路**（走主角走过的路）。
    #   ⚠️ 必须用 **AST 判 import**，不能拿源码文本 `in` ——
    #   companion_roster 的**文档字符串**里就写着「`scene_walk` 仍有用」，
    #   文本判据会把这个正当提及当成违规（判据过窄 = 误报，与过宽同样要防）。
    _roster_imports = _imports_of(files['companion_roster'], top_level=True) \
        | _imports_of(files['companion_roster'], top_level=False)
    check('A5 ★ 跟随不独立寻路：companion_roster 不 import scene_walk',
          'scene_walk' not in _roster_imports,
          'imports=%s' % sorted(_roster_imports))
    check('A5b 负控制：同一个 AST 判据能抓到真的 import scene_walk',
          'scene_walk' in _imports_of('import scene_walk  # noqa'))
    check('A5c 正控制：文本里提到 scene_walk 但没 import 时判据不误报',
          _imports_of('# 第 45 轮的 scene_walk 仍有用\n') == set())
    check('A5d 三个模块的项目内依赖只在白名单内',
          (_roster_imports | _imports_of(files['companion_dialog']) 
           | _imports_of(files['companion'])) & _PROJECT_MODS
          <= {'companion', 'companion_dialog'})

    try:
        import companion as CM
        import companion_dialog as CD
        import companion_roster as CR
        imp_ok, imp_err = True, ''
    except Exception as e:                                  # pragma: no cover
        CM = CD = CR = None
        imp_ok, imp_err = False, repr(e)
    check('A6 三个模块能被真的 import（无初始化环 / 无语法错）', imp_ok, imp_err)
    if not imp_ok:
        print()
        print('RESULT: PASS=%d FAIL=%d' % (PASS, FAIL))
        return 1

    # =======================================================================
    section('B 数值照抄（每个数字都要能指到原作出处）')
    # =======================================================================
    check('B1 trace 缓冲长度 == 25（原作 obj_caterpillarchara 的 remx[25]）',
          CM.TRACE_LEN == 25, 'got=%r' % CM.TRACE_LEN)
    check('B2 跟随滞后公式 == 12 + slot*12（原作 scr_makecaterpillar）',
          (CM.FOLLOW_LAG_BASE, CM.FOLLOW_LAG_STEP) == (12, 12),
          'got=%r' % ((CM.FOLLOW_LAG_BASE, CM.FOLLOW_LAG_STEP),))
    check('B3 队友位 == 2（原作 scr_setparty(arg0, arg1) 正好两个参数）',
          CM.MAX_COMPANIONS == 2, 'got=%r' % CM.MAX_COMPANIONS)
    check('B4 暗世界缩放 == ×2（原作 image_xscale = 2）',
          CM.DARK_SCALE == 2, 'got=%r' % CM.DARK_SCALE)
    check('B4b darkzone 取值域 0=光明 / 1=暗世界（原作 obj_dialoguer_Create_0）',
          (CM.DARKZONE_LIGHT, CM.DARKZONE_DARK) == (0, 1))
    check('B5 交互防抖 == 5 帧（原作 with (obj_mainchara) onebuffer = 5）',
          CM.INTERACT_COOLDOWN_FRAMES == 5, 'got=%r' % CM.INTERACT_COOLDOWN_FRAMES)
    check('B5b 防抖换算成秒 == 5/30（本项目 update 的 dt 单位是秒）',
          abs(CM.INTERACT_COOLDOWN_SEC - 5 / 30.0) < 1e-9,
          'got=%r' % CM.INTERACT_COOLDOWN_SEC)
    check('B5c 打字机默认速度 == 5（原作 scr_writetext 的 global.typer = 5）',
          CD.DEFAULT_TYPER == 5, 'got=%r' % CD.DEFAULT_TYPER)

    main_src = io_read(MAIN_PY) if os.path.isfile(MAIN_PY) else ''
    m = re.search(r'^\s*AI_REPLY_MAX_CHARS\s*=\s*(\d+)', main_src, re.M)
    check('B6 main.py 里能解析出 AI_REPLY_MAX_CHARS（B7 的前提）', bool(m))
    if m:
        check('B7 ★ 跨文件一致：companion_dialog.MAX_TEXT_CHARS == main.AI_REPLY_MAX_CHARS',
              int(m.group(1)) == CD.MAX_TEXT_CHARS,
              'main=%s dialog=%s' % (m.group(1), CD.MAX_TEXT_CHARS))
    check('B8 main.py 仍有 _clean_ai_reply（L2 与它的职责分工是真的）',
          'def _clean_ai_reply' in main_src)

    for token, why in (('scr_makecaterpillar', '跟随滞后'),
                       ('scr_interact', '交互入口'),
                       ('onebuffer', '防抖'),
                       ('scr_setparty', '队友位'),
                       ('obj_caterpillarchara', '毛毛虫'),
                       ('darkzone', '明暗世界')):
        check('B9 文档锁：源码里留有 %s 的出处（%s）' % (token, why),
              token in src_all)

    # =======================================================================
    section('C Companion 模型（行为，正/负成对）')
    # =======================================================================
    a = CM.Companion('Ralsei', display_name='Ralsei', aliases=['ral', 'RAL'], slot=0)
    b = CM.Companion('Susie', display_name='Susie', aliases=['sus'], slot=1,
                     darkmode=CM.DARKZONE_DARK)
    check('C1 slot0 滞后 == 12', a.follow_lag == 12, 'got=%d' % a.follow_lag)
    check('C2 slot1 滞后 == 24', b.follow_lag == 24, 'got=%d' % b.follow_lag)
    check('C2b slot2 滞后 == 36（公式外推）',
          CM.Companion('x', slot=2).follow_lag == 36)
    check('C3 别名归一 + 去重（ral / RAL 只留一个）',
          a.aliases == ('ral',) and a.names() == ('ralsei', 'ral'),
          'aliases=%r names=%r' % (a.aliases, a.names()))
    check('C4 缩放：光明 1 / 暗世界 2',
          CM.Companion('x').scale == 1 and b.scale == 2)

    for i in range(100):
        a.push_trace(float(i), 0.0)
    check('C5 压 100 帧后环缓冲仍是 25', len(a.trace) == 25, 'got=%d' % len(a.trace))
    # ★★ 真实量级 + 精确值：0..99，lag=12 ⇒ 12 帧前那一点是 99-12 = 87
    check('C6 ★★ sample_at(12) 精确 == 87（滞后 12 帧，不是 11 帧）',
          a.sample_at(12) is not None and a.sample_at(12).x == 87.0,
          'got=%r' % (a.sample_at(12),))
    check('C6b sample_at(24) 精确 == 75', a.sample_at(24).x == 75.0,
          'got=%r' % (a.sample_at(24),))
    check('C7 越界 lag（0 / 25 / 负数）→ None（不猜）',
          a.sample_at(0) is None and a.sample_at(25) is None
          and a.sample_at(-3) is None)

    fresh = CM.Companion('fresh')
    check('C8 ★★ 空轨迹 sample_at → None（防"未热身就返回 (0,0)"）',
          len(fresh.trace) == 0 and fresh.sample_at(1) is None)
    fresh.reset_trace(500.0, 600.0)
    check('C8b reset_trace 填满 25 帧 ⇒ 立刻可用、初始位置 = 主角位置',
          len(fresh.trace) == 25 and fresh.sample_at(12).x == 500.0
          and fresh.x == 500.0)

    check('C9 set_mode 非法值 → False 且保持原值（不静默吃掉）',
          a.set_mode('teleport') is False and a.mode == CM.FollowMode.FREE)
    check('C9b set_mode 合法值 → True', a.set_mode(CM.FollowMode.FOLLOW) is True)
    check('C9c 默认模式是 FREE（用户口径「也可自主行动」）',
          CM.Companion('z').mode == CM.FollowMode.FREE)
    check('C10 RALLY 收紧滞后（12 → 3），FOLLOW 不收紧',
          func_rally_lag(a) == 3 and a.follow_lag == 12,
          'rally=%d' % func_rally_lag(a))
    check('C11 speaker_id 为空 → ValueError（身份必须显式）',
          raises(lambda: CM.Companion('   '), ValueError))
    check('C11b 负控制：正常 id 不抛', not raises(lambda: CM.Companion('ok'), ValueError))
    check('C12 normalize_id：大小写 / 全角空格 / 内部空白折叠',
          CM.normalize_id('  Ral\u3000sei  ') == 'ral sei')
    check('C13 is_blank_id 认可 None 与空串与短横线（对应原作 arg0 = false）',
          CM.is_blank_id(None) and CM.is_blank_id('') and CM.is_blank_id('-')
          and not CM.is_blank_id('ralsei'))

    # =======================================================================
    section('D 可交互物协议（正/负成对，重点是"锁必须能释放"）')
    # =======================================================================
    bus = CM.InteractBus()
    seen = []

    def presenter(text, actor):
        seen.append(text)
        return object()

    sign = CM.ReadableInteractable('sign_1', '欢迎来到城堡镇', present=presenter, bus=bus)
    check('D1 interact → True 且 myinteract==3（原作 User Event 0 里设 3）',
          sign.interact() is True and sign.myinteract == 3,
          'myinteract=%d' % sign.myinteract)
    check('D2 上锁后 bus.locked == True', bus.locked is True)
    check('D3 同一物重复 interact → False（自己还 busy）', sign.interact() is False)
    other = CM.ReadableInteractable('sign_2', 'x', present=presenter, bus=bus)
    blocked0 = bus.blocked_count
    check('D4 另一物在锁上时 interact → False 且 blocked_count +1',
          other.interact() is False and bus.blocked_count == blocked0 + 1)
    check('D5 ★ 被锁挡下的那次不该让 on_interact 跑（presenter 只被调 1 次）',
          len(seen) == 1, 'seen=%r' % seen)

    sign.dialog = None
    check('D6 dialog 消失后 update → True（刚解锁）', sign.update(0.0333) is True)
    check('D6b ★ 解锁后 bus.locked == False（锁必须能释放）', bus.locked is False)
    check('D6c 防抖 == INTERACT_COOLDOWN_SEC（5/30 秒）',
          abs(sign.cooldown - 5 / 30.0) < 1e-9, 'cooldown=%r' % sign.cooldown)
    check('D7 防抖期内 interact → False', sign.interact() is False)
    for _ in range(6):
        sign.update(0.0333)
    check('D8 防抖走完（6×1/30 ≈ 0.2s > 5/30）后 interact → True',
          sign.interact() is True)
    sign.dialog = None
    sign.update(0.0333)

    # ★★ 设计律 2：on_interact 抛异常 ⇒ 必须解锁（否则整个交互系统瘫痪）
    bus2 = CM.InteractBus()

    class Boom(CM.Interactable):
        def on_interact(self, actor=None):
            raise RuntimeError('故意炸')

    boom = Boom('boom', bus=bus2)
    check('D9 ★★ on_interact 抛异常 → interact 返回 False', boom.interact() is False)
    check('D9b ★★ 抛异常后锁被释放（bus.locked == False）', bus2.locked is False,
          'locked=%r holder=%r' % (bus2.locked, bus2.holder))
    check('D9c 抛异常后 myinteract 回到 0（不留半开状态）', boom.myinteract == 0)
    check('D10 负控制：抛异常不往外冒（interact 自己吞掉）',
          not raises(lambda: boom.interact(), Exception))

    bus3 = CM.InteractBus()
    quiet = CM.ReadableInteractable('quiet', 'x', present=None, bus=bus3)
    check('D11 on_interact 返回 False → 不锁（bus 立刻空）',
          quiet.interact() is False and bus3.locked is False)
    check('D12 ★ 基类 on_interact 未实现 → NotImplementedError（不静默通过）',
          raises(lambda: CM.Interactable('raw', bus=bus3).interact(), NotImplementedError))
    check('D12b ★ 但锁仍然被释放（NotImplementedError 也不许卡死）',
          bus3.locked is False)

    class Actor(object):
        pass

    bus4 = CM.InteractBus()
    pit = CM.ReadableInteractable('pit', 'x', present=presenter, bus=bus4)
    ac = Actor()
    pit.interact(actor=ac)
    pit.dialog = None
    pit.update(0.0333)
    check('D13 ★ actor 本来没有 interact_cooldown → 不许凭空造出来',
          not hasattr(ac, 'interact_cooldown'))

    class Actor2(object):
        interact_cooldown = 0.0

    bus5 = CM.InteractBus()
    pit2 = CM.ReadableInteractable('pit2', 'x', present=presenter, bus=bus5)
    ac2 = Actor2()
    pit2.interact(actor=ac2)
    pit2.dialog = None
    pit2.update(0.0333)
    check('D13b actor 本来就有该字段 → 被写成 5/30（照抄 onebuffer = 5）',
          abs(ac2.interact_cooldown - 5 / 30.0) < 1e-9,
          'got=%r' % ac2.interact_cooldown)
    check('D14 默认总线可被重置（测试隔离用）',
          CM.reset_default_bus() is not CM.reset_default_bus())

    # =======================================================================
    section('E Message 校验（★ §4.2 铁律 1：缺 from_id 一律拒）')
    # =======================================================================
    ids = {'kris', 'ralsei', 'susie'}
    amap = {'kris': 'kris', 'ralsei': 'ralsei', 'ral': 'ralsei',
            'susie': 'susie', 'sus': 'susie'}
    check('E1 正常消息通过',
          CD.Message(text='我们去哪儿？', from_id='kris').validate(ids, amap)
          == (True, ''))
    check('E2 ★★ 缺 from_id 的 speech → missing_from',
          CD.Message(text='我们去哪儿？', from_id=None).validate(ids, amap)
          == (False, 'missing_from'))
    check('E3 未知 from → unknown_from',
          CD.Message(text='x', from_id='sans').validate(ids, amap)[1]
          .startswith('unknown_from'))
    check('E4 别名 from（ral）→ 通过（正控制，证明归一真的生效）',
          CD.Message(text='x', from_id='ral').validate(ids, amap) == (True, ''))
    check('E5 未知 to → unknown_to',
          CD.Message(text='x', from_id='kris', to_id='sans').validate(ids, amap)[1]
          .startswith('unknown_to'))
    check('E6 自己跟自己说 → self_talk',
          CD.Message(text='x', from_id='ralsei', to_id='ral').validate(ids, amap)[1]
          == 'self_talk')
    check('E7 空文本 / 纯空白 → empty_text',
          CD.Message(text='   ', from_id='kris').validate(ids, amap)[1] == 'empty_text'
          and CD.Message(text='', from_id='kris').validate(ids, amap)[1] == 'empty_text')
    check('E8 超长 → too_long',
          CD.Message(text='あ' * (CD.MAX_TEXT_CHARS + 1), from_id='kris')
          .validate(ids, amap)[1].startswith('too_long'))
    check('E8b 恰好等于上限 → 通过（边界正控制）',
          CD.Message(text='あ' * CD.MAX_TEXT_CHARS, from_id='kris')
          .validate(ids, amap) == (True, ''))
    check('E9 非法 kind → bad_kind',
          CD.Message(text='x', from_id='kris', kind='song').validate(ids, amap)[1]
          .startswith('bad_kind'))
    check('E10 typer 非数字 → bad_typer',
          CD.Message(text='x', from_id='kris', typer='快').validate(ids, amap)[1]
          .startswith('bad_typer'))
    check('E10b typer=0 → 生效值是默认 5（原作 if (typer != 0)）',
          CD.Message(text='x', from_id='kris', typer=0).effective_typer == 5)
    check('E10c typer=9 → 生效值 9', CD.Message(text='x', from_id='kris', typer=9)
          .effective_typer == 9)
    check('E11 旁白（narrate）允许无 from（正控制）',
          CD.Message(text='风从北边吹来。', from_id=None, kind=CD.KIND_NARRATE)
          .validate(ids, amap) == (True, ''))
    check('E11b ★ 负控制：speech 无 from 必须拒（E11 不是"什么都能过"）',
          CD.Message(text='风从北边吹来。', from_id=None, kind=CD.KIND_SPEECH)
          .validate(ids, amap)[1] == 'missing_from')
    check('E11c 旁白也不许编造说话人',
          CD.Message(text='x', from_id='sans', kind=CD.KIND_NARRATE)
          .validate(ids, amap)[1].startswith('unknown_from'))
    check('E12 known_ids=None → 只校验形状（不校验身份存在性）',
          CD.Message(text='x', from_id='whoever').validate(None, None) == (True, ''))

    # =======================================================================
    section('F format_line（★ §4.2 铁律 2：每一行都带名字前缀）')
    # =======================================================================
    disp = {'ralsei': 'Ralsei', 'susie': 'Susie', 'kris': 'Kris'}
    l1 = CD.format_line(CD.Message(text='我们去哪儿？', from_id='kris'), disp, ids, amap)
    check('F1 基本格式 [名字] 文本', l1 == '[Kris] 我们去哪儿？', 'got=%r' % l1)
    l2 = CD.format_line(CD.Message(text='随便', from_id='sus', to_id='ral'), disp, ids, amap)
    check('F2 ★ 定向 → [a→b]（"谁跟谁说话"的可见答案）',
          l2 == '[Susie→Ralsei] 随便', 'got=%r' % l2)
    l3 = CD.format_line(CD.Message(text='谁来着', from_id=None), disp, ids, amap)
    check('F3 ★★ 缺 from → [未知说话人]，且原文不裸奔',
          l3 == '[未知说话人] 谁来着' and l3.startswith('['), 'got=%r' % l3)
    l4 = CD.format_line(CD.Message(text='x', from_id='sans'), disp, ids, amap)
    check('F4 未知 from + known_ids → [未知说话人:原始值]',
          l4 == '[未知说话人:sans] x', 'got=%r' % l4)
    l6 = CD.format_line(CD.Message(text='我想去城北', from_id='Ral'), disp, ids, amap)
    check('F5 ★★ 别名归一后渲染成显示名（首版没接 alias_map，会打成"未知说话人"）',
          l6 == '[Ralsei] 我想去城北', 'got=%r' % l6)
    check('F5b 负控制：不传 alias_map 时别名会退化成未知（证明 F5 真的依赖它）',
          CD.format_line(CD.Message(text='x', from_id='Ral'), disp, ids, None)
          .startswith('[未知说话人'))
    check('F6 ★★ 负控制：全部消息都没 from ⇒ 每一行仍以 [ 开头（不许裸文本入 prompt）',
          all(x.startswith('[') for x in
              CD.format_context([CD.Message(text='a'), CD.Message(text='b')],
                                disp, ids, amap).splitlines()))
    check('F7 format_context 空列表 → 空串（不是 None）',
          CD.format_context([], disp, ids, amap) == '')

    # =======================================================================
    section('G 输出护栏（★ §4.2 铁律 3 自称 / 铁律 4 代他人发言）')
    # =======================================================================
    check('G1 检出"别人开的头"（Susie：…）',
          CD.detect_foreign_speaker_lines('好吧。\nSusie：我才不去。', 'ralsei', amap)
          == [('susie', 'Susie：我才不去。')])
    check('G2 检出我们自己的上下文格式被抄（[susie] …）',
          len(CD.detect_foreign_speaker_lines('[susie] 随便', 'ralsei', amap)) == 1)
    check('G3 负控制：自己开的头不算',
          CD.detect_foreign_speaker_lines('[ralsei] 我说完了', 'ralsei', amap) == [])
    check('G4 负控制：句中提到名字不算（"Susie 你怎么了"）',
          CD.detect_foreign_speaker_lines('Susie 你怎么了？', 'ralsei', amap) == [])
    check('G5 ★ 负控制（刻意收窄）：转述不算（"Susie说她不喜欢这里"）',
          CD.detect_foreign_speaker_lines('Susie说她不喜欢这里。', 'ralsei', amap) == [])
    check('G6 检出"自称混乱"（我是Susie）',
          len(CD.detect_wrong_self_claim('我是Susie。', 'ralsei', amap)) == 1)
    check('G7 负控制：自称自己不算',
          CD.detect_wrong_self_claim('我是Ralsei。', 'ralsei', amap) == [])
    check('G8 负控制："我是说，Susie…"不算（自称词后必须紧跟名字）',
          CD.detect_wrong_self_claim('我是说，Susie 大概会来。', 'ralsei', amap) == [])
    check('G9 check_reply：干净的通过',
          CD.check_reply('我想去城北看看。', 'ralsei', amap) == (True, ''))
    check('G9b check_reply：代他人发言被拒',
          CD.check_reply('Susie：滚。', 'ralsei', amap)[1].startswith('foreign_speaker'))
    check('G9c check_reply：自称混乱被拒',
          CD.check_reply('我是Susie。', 'ralsei', amap)[1].startswith('wrong_self_claim'))
    check('G9d check_reply：超长被拒',
          CD.check_reply('あ' * 999, 'ralsei', amap)[1].startswith('too_long'))
    check('G9e check_reply：空文本被拒',
          CD.check_reply('   ', 'ralsei', amap) == (False, 'empty_text'))
    check('G10 ★★ 负控制：name_index 为空 ⇒ 两条检测都失效（判据不是恒真）',
          CD.detect_foreign_speaker_lines('Susie：滚', 'ralsei', {}) == []
          and CD.detect_wrong_self_claim('我是Susie。', 'ralsei', {}) == [])

    hdr = CD.build_speaker_header(a, others=[b, a])
    check('G11 提示里写明本名 + id', ('Ralsei' in hdr) and ('ralsei' in hdr))
    check('G12 提示里写明在场伙伴 + 禁止替其说话',
          ('Susie' in hdr) and ('不要替他们说话' in hdr))
    check('G13 提示里不出现"主人"（既有禁用词口径）', '主人' not in hdr)
    check('G14 没有别人在场时不提"在场还有"',
          '在场还有' not in CD.build_speaker_header(a, others=[a]))
    check('G15 负控制：extra_rules 真被拼进去（不是恒定的死字符串）',
          '【自定义规则】' in CD.build_speaker_header(
              a, others=[], extra_rules=['【自定义规则】']))

    # =======================================================================
    section('H DialogueLog（★ 铁律 1 的载体：无效消息不进历史）')
    # =======================================================================
    log = CD.DialogueLog(known_ids=ids, alias_map=amap, display=disp)
    ok1, _ = log.append(CD.Message(text='我们去哪儿？', from_id='kris'))
    check('H1 合法消息入库', ok1 and len(log) == 1)
    ok2, r2 = log.append(CD.Message(text='谁来着', from_id=None))
    check('H2 ★★ 非法消息**不入历史**',
          (ok2 is False) and (len(log) == 1) and r2 == 'missing_from',
          'len=%d reason=%s' % (len(log), r2))
    check('H2b 被拒的消息进 rejected（如实留痕，不静默丢）',
          len(log.rejected()) == 1 and log.rejected()[0][1] == 'missing_from')
    check('H3 ★ last_from_id 只看**入库**消息（被拒的不算）',
          log.last_from_id() == 'kris', 'got=%r' % log.last_from_id())
    log.append(CD.Message(text='随便。', from_id='sus'))
    check('H3b 新消息进来后 last_from_id 跟着变（正控制）',
          log.last_from_id() == 'susie')
    log.append(CD.Message(text='坏消息', from_id='sans'))
    check('H3c 再次被拒后 last_from_id 不动、长度不变（负控制）',
          log.last_from_id() == 'susie' and len(log) == 2)

    ctx = log.context_lines()
    check('H4 ★★ context_lines 每行都带前缀（走 alias_map，别名不被误判）',
          ctx == ['[Kris] 我们去哪儿？', '[Susie] 随便。'], 'got=%r' % ctx)
    check('H5 空历史 → last_from_id 是 None（不是空串）',
          CD.DialogueLog(known_ids=ids, alias_map=amap).last_from_id() is None)

    tiny = CD.DialogueLog(known_ids=ids, alias_map=amap, maxlen=3)
    for i in range(5):
        tiny.append(CD.Message(text='第%d条' % i, from_id='kris'))
    check('H6 环缓冲上限生效（maxlen=3，进 5 条 ⇒ 3 条）', len(tiny) == 3,
          'got=%d' % len(tiny))
    check('H6b 保留的是最新的 3 条', tiny.recent(1)[0].text == '第4条',
          'got=%r' % tiny.recent(1)[0].text)

    log_c = CD.DialogueLog(known_ids=ids, alias_map=amap, cleaner=lambda t, rec: None)
    check('H7 ★ 注入的 cleaner 返回 None ⇒ 消息被拒（cleaner_dropped）',
          log_c.append(CD.Message(text='x', from_id='kris'), clean=True)
          == (False, 'cleaner_dropped'))
    check('H7b 负控制：不传 cleaner 时同一条消息能进',
          log_c.append(CD.Message(text='x', from_id='kris')) == (True, ''))

    def boom_cleaner(t, rec):
        raise RuntimeError('cleaner 炸了')

    log_d = CD.DialogueLog(known_ids=ids, alias_map=amap, cleaner=boom_cleaner)
    check('H8 ★ cleaner 抛异常 ⇒ 被拒且不崩',
          log_d.append(CD.Message(text='x', from_id='kris'), clean=True)
          == (False, 'cleaner_dropped'))

    # =======================================================================
    section('I Roster（名册：登记 / 解析 / 上场）')
    # =======================================================================
    rs = CR.Roster()
    # ★ 用**新建**的实例，不复用上面的 `a`/`b`：
    #   C9b 已经把 `a.mode` 改成 FOLLOW 了，复用会让 I6e「默认 FREE」假报红
    #   （测试隔离问题，不是产品问题 —— 但假报红会掩盖真问题，必须修）。
    ca = CM.Companion('Ralsei', display_name='Ralsei', aliases=['ral', 'RAL'], slot=0)
    cb = CM.Companion('Susie', display_name='Susie', aliases=['sus'], slot=1)
    check('I1 add 正常 → True', rs.add(ca)[0] is True and rs.add(cb)[0] is True)
    check('I1b add 重复 id → 拒',
          rs.add(CM.Companion('Ralsei'))[1] == 'duplicate_id:ralsei')
    check('I1c ★★ 原子性：被拒后名册长度不变（不留半只）', len(rs) == 2)
    check('I1d add 别名冲突 → 拒（不许后者覆盖前者）',
          rs.add(CM.Companion('Lancer', aliases=['ral']))[1] == 'alias_conflict:ral')
    check('I1e 冲突被拒后原主仍在（正控制）',
          rs.resolve('ral').speaker_id == 'ralsei')
    check('I2 add 非 Companion → 拒', rs.add('susie')[0] is False)

    check('I3 resolve 大小写不敏感（RAL）', rs.resolve('RAL').speaker_id == 'ralsei')
    check('I3b resolve 别名（sus）', rs.resolve('sus').speaker_id == 'susie')
    check('I3c resolve 显示名（Susie）', rs.resolve('Susie').speaker_id == 'susie')
    check('I4 ★ resolve 未知 → None（不猜、不就近凑）', rs.resolve('sans') is None)
    check('I4b resolve 空 / None → None', rs.resolve('') is None and rs.resolve(None) is None)
    check('I5 ids() == {ralsei, susie}', rs.ids() == {'ralsei', 'susie'})
    check('I5b alias_index() 含别名映射', rs.alias_index().get('ral') == 'ralsei')
    check('I5c display_map() 给显示名', rs.display_map().get('ralsei') == 'Ralsei')

    act, un = rs.activate(['susie', 'ralsei'], leader_xy=(100.0, 200.0))
    check('I6 ★ 槽位按**成功激活顺序**分配（susie 先 ⇒ slot0）',
          [c.speaker_id for c in act] == ['susie', 'ralsei']
          and act[0].slot == 0 and act[1].slot == 1,
          'slots=%r' % [(c.speaker_id, c.slot) for c in act])
    check('I6b 对应的滞后是 12 / 24', [c.follow_lag for c in act] == [12, 24])
    check('I6c active() 按槽位序',
          [c.speaker_id for c in rs.active()] == ['susie', 'ralsei'])
    check('I6d activate(leader_xy) ⇒ 轨迹填满 25 帧（不闪）',
          all(len(c.trace) == 25 for c in act)
          and all(c.x == 100.0 and c.y == 200.0 for c in act))
    check('I6e 默认模式仍是 FREE（跟不跟由 select_mode 决定）',
          all(c.mode == CM.FollowMode.FREE for c in act))

    rs2 = CR.Roster()
    rs2.add(CM.Companion('Ralsei', display_name='Ralsei', aliases=['ral'], slot=0))
    rs2.add(CM.Companion('Susie', display_name='Susie', aliases=['sus'], slot=1))
    act2, un2 = rs2.activate(['ralsei', None, '', 'nobody', 'susie'])
    check('I7 空位（None / 空串）被跳过，未解析的如实报出',
          [c.speaker_id for c in act2] == ['ralsei', 'susie']
          and un2 == [('nobody', 'not_found')], 'unresolved=%r' % un2)
    check('I7b ★ 未解析的名字**不被静默忽略**（unresolved 非空）', len(un2) == 1)

    act3, _ = rs2.activate('ralsei')
    check('I8 ★ activate 传 str 不按字符拆（只激活 1 个）',
          len(act3) == 1 and act3[0].speaker_id == 'ralsei')
    _act4, un4 = rs2.activate(['ralsei', 'susie', 'ralsei'])
    check('I8b 同一请求里重复名字 → duplicate_in_request',
          any(w == 'duplicate_in_request' for _, w in un4), 'unresolved=%r' % un4)

    tiny_rs = CR.Roster(slot_count=1)
    tiny_rs.add(CM.Companion('Ralsei', slot=0))
    tiny_rs.add(CM.Companion('Susie', slot=1))
    act5, un5 = tiny_rs.activate(['ralsei', 'susie'])
    check('I8c 超过槽位数 → no_slot（不挤掉已上场的）',
          [c.speaker_id for c in act5] == ['ralsei']
          and un5 == [('susie', 'no_slot')], 'unresolved=%r' % un5)

    rs3 = CR.Roster()
    rs3.add(CM.Companion('a', slot=0))
    rs3.add(CM.Companion('b', slot=1))
    rs3.activate(['a', 'b'])
    check('I9 ★★ activate 不给 leader_xy ⇒ 轨迹留空（不填 (0,0) 造成可见漂移）',
          all(len(c.trace) == 0 for c in rs3.active()))
    check('I9b 正控制：同一对伙伴给 leader_xy 时轨迹就满了（见 I6d）',
          all(len(c.trace) == 25 for c in rs.active()))
    check('I10 deactivate_all 清场并返回人数',
          rs2.deactivate_all() == 2 and rs2.active() == [])

    # =======================================================================
    section('J ChatScheduler（★「看不出端倪」= 不并发 + A↔B 往返 + 反活锁）')
    # =======================================================================
    def fresh_sched(**kw):
        r = CR.Roster()
        r.add(CM.Companion('ralsei', aliases=['ral'], slot=0))
        r.add(CM.Companion('susie', aliases=['sus'], slot=1))
        r.activate(['ralsei', 'susie'], leader_xy=(0.0, 0.0))
        kw.setdefault('min_gap', 0.0)
        kw.setdefault('max_turns', 100000)
        return r, CR.ChatScheduler(r, **kw)

    _rr, sc = fresh_sched()
    seq, concurrent = [], 0
    for i in range(200):                       # ★ 真实量级
        now = i * 0.05
        c = sc.tick(now)
        if c is None:
            continue
        seq.append(c.speaker_id)
        for _ in range(5):                     # 生成期间连问 5 次
            if sc.tick(now + 0.001) is not None:
                concurrent += 1
        sc.finish(now, c.speaker_id)
    check('J1 ★★ 生成期间 200×5 次 tick 全 None（绝不并发）', concurrent == 0,
          'concurrent=%d' % concurrent)
    check('J1b 负控制：这个循环真的产生了 200 次发言（J1 不是恒真）',
          len(seq) == 200, 'len(seq)=%d' % len(seq))
    check('J2 ★★ A↔B 往返：相邻两次发言绝不是同一个人',
          all(x != y for x, y in zip(seq, seq[1:])), 'seq[:8]=%r' % seq[:8])
    check('J2b 两个人都说过话（不是一个人刷屏）', set(seq) == {'ralsei', 'susie'},
          'set=%r' % set(seq))
    check('J2c 轮转严格交替', seq[:6] == ['ralsei', 'susie'] * 3,
          'seq[:6]=%r' % seq[:6])

    _rr2, sc2 = fresh_sched(min_gap=8.0)
    c1 = sc2.tick(0.0)
    sc2.finish(0.0, c1.speaker_id)
    check('J3 冷却期内 tick → None', sc2.tick(7.9) is None)
    check('J3b 冷却过后 tick → 非 None（正控制）', sc2.tick(8.1) is not None)

    _rr3, sc3 = fresh_sched(max_turns=3)
    for i in range(40):
        if sc3.tick(float(i)) is None:
            break
        sc3.finish(float(i), sc3.pending_id)
    check('J4 话题上限到顶后停（不硬凑）',
          sc3.turns == 3 and sc3.tick(999.0) is None, 'turns=%d' % sc3.turns)

    solo = CR.Roster()
    solo.add(CM.Companion('ralsei', slot=0))
    solo.activate(['ralsei'], leader_xy=(0.0, 0.0))
    check('J5 ★ 只有 1 个在场 → 恒 None（"互相聊天"至少要 2 个）',
          CR.ChatScheduler(solo, min_gap=0.0).tick(0.0) is None)
    check('J5b allow_solo=True 时放行（正控制）',
          CR.ChatScheduler(solo, min_gap=0.0, allow_solo=True).tick(0.0) is not None)

    _rr4, sc4 = fresh_sched()
    c4 = sc4.tick(0.0)
    wrong = 'susie' if c4.speaker_id == 'ralsei' else 'ralsei'
    ok4, why4 = sc4.finish(0.0, wrong)
    check('J6 ★★ 实际说话人与调度预期不一致 → speaker_mismatch',
          (ok4 is False) and why4.startswith('speaker_mismatch'), 'why=%r' % why4)
    check('J6b ★★ 但**仍然解锁**（设计律 2：卡死比错一次更严重）',
          sc4.busy is False)
    check('J6c mismatch 计数 +1', sc4.mismatch_count == 1)
    _rr6d, sc6d = fresh_sched()
    c6d = sc6d.tick(0.0)
    sc6d.finish(0.0, c6d.speaker_id)
    check('J6d 负控制：传对的人时无 mismatch', sc6d.mismatch_count == 0)

    _rr5, sc5 = fresh_sched()
    first = sc5.tick(0.0)
    sc5.abort(0.0)
    check('J7 ★ abort 解锁', sc5.busy is False)
    again = sc5.tick(1.0)
    check('J7b ★ abort **不推进轮转**：下次还是同一个人（不罚下一个人）',
          again is not None and again.speaker_id == first.speaker_id)

    _rr6, sc6 = fresh_sched()
    before_ok = []
    for i in range(3):
        c = sc6.tick(float(i))
        before_ok.append(c is not None)
        sc6.abort(float(i))
    check('J8 ★★ 连续失败 3 次之前还能说话（J8b 的前提）', all(before_ok))
    check('J8b ★★ 连续失败 3 次后 tick 恒 None（反活锁，不许无限重试）',
          sc6.fail_count >= CR.MAX_CONSECUTIVE_FAILURES and sc6.tick(99.0) is None,
          'fail_count=%d' % sc6.fail_count)
    _rr7, sc7 = fresh_sched()
    c7 = sc7.tick(0.0)
    sc7.finish(0.0, c7.speaker_id)
    check('J8c 成功一次后 fail_count 归零（能重新开口）',
          sc7.fail_count == 0 and sc7.tick(1.0) is not None)

    _rr8, sc8 = fresh_sched(topic_source=lambda: None)
    check('J9 topic_source 没话题 → 不开口', sc8.tick(0.0) is None)
    sc8.topic_source = lambda: '城堡镇'
    check('J9b 有话题 → 开口（正控制）', sc8.tick(1.0) is not None)

    def boom_topic():
        raise RuntimeError('话题源炸了')

    _rr9, sc9 = fresh_sched(topic_source=boom_topic)
    check('J9c 话题源抛异常 → 不开口且不崩', sc9.tick(0.0) is None)

    check('J10 not_busy 时 finish → (False, not_busy)',
          sc9.finish(0.0) == (False, 'not_busy'))
    check('J10b 未 busy 时 abort → False', sc9.abort(0.0) is False)
    check('J11 reset 清空轮转状态',
          sc2.reset(keep_topic=False).turns == 0 and sc2.last_from is None)

    # =======================================================================
    section('K 跟随（★ 毛毛虫：走主角走过的路，滞后 12/24 帧）')
    # =======================================================================
    def two(mode0=CM.FollowMode.FOLLOW, mode1=CM.FollowMode.FOLLOW,
            leader_xy=(0.0, 0.0)):
        r = CR.Roster()
        r.add(CM.Companion('ralsei', slot=0))
        r.add(CM.Companion('susie', slot=1))
        r.activate(['ralsei', 'susie'], leader_xy=leader_xy)
        for c, m in zip(r.active(), (mode0, mode1)):
            c.set_mode(m)
        return r

    r_f = two()
    for i in range(60):                        # ★ 真实量级：60 帧
        CR.step_follow(r_f, 100.0 + i, 0.0)
    c0, c1 = r_f.active()
    check('K1 ★★ 滞后 12 帧精确（60 帧后 = 159-12 = 147）', c0.x == 147.0,
          'got=%r' % c0.x)
    check('K2 ★★ 滞后 24 帧精确（= 135）', c1.x == 135.0, 'got=%r' % c1.x)
    check('K2b 两人位置不同（不是"叠在一起"）', c0.x != c1.x)
    check('K3 历史长度封顶 25', len(c0.trace) == 25)

    r_free = two(CM.FollowMode.FREE, CM.FollowMode.FREE)
    moved = [CR.step_follow(r_free, 100.0 + i, 0.0) for i in range(60)]
    check('K4 ★ 负控制：FREE 模式不跟（moved 恒 0）', sum(moved) == 0)
    check('K4b ★ 但历史仍在记录（FREE 时位置不变、轨迹在长）',
          len(r_free.active()[0].trace) == 25 and r_free.active()[0].x == 0.0)

    r_rally = two(CM.FollowMode.RALLY, CM.FollowMode.RALLY)
    for i in range(60):
        CR.step_follow(r_rally, 100.0 + i, 0.0)
    check('K5 RALLY 跟得更紧（12//4 = 3 ⇒ 156）',
          r_rally.active()[0].x == 156.0, 'got=%r' % r_rally.active()[0].x)
    check('K5b RALLY 的 slot1 也更紧（24//4 = 6 ⇒ 153）',
          r_rally.active()[1].x == 153.0, 'got=%r' % r_rally.active()[1].x)

    r_cold = two(leader_xy=None)
    early = [CR.step_follow(r_cold, 100.0 + i, 0.0) for i in range(12)]
    check('K6 ★★ 未热身：前 12 帧一步都不动（不是"从 (0,0) 挪过去"）',
          sum(early) == 0, 'moved=%r' % early)
    r_cold2 = two(leader_xy=None)
    mv = [CR.step_follow(r_cold2, 100.0 + i, 0.0) for i in range(25)]
    check('K6b 第 13 帧 slot0 开始动（滞后 12 需要 13 帧历史）', mv[12] == 1,
          'mv[12]=%d' % mv[12])
    check('K6c 第 25 帧 slot1 也开始动（滞后 24 需要 25 帧历史）',
          mv[23] == 1 and mv[24] == 2, 'mv[23]=%d mv[24]=%d' % (mv[23], mv[24]))

    p = CM.Companion('p', slot=0)
    check('K7 主角不在场 → FREE', CR.select_mode(p, False, True, dist=999) == 'free')
    check('K7b need_rally → RALLY',
          CR.select_mode(p, True, False, dist=0, need_rally=True) == 'rally')
    check('K7c 主角在动且远 → FOLLOW',
          CR.select_mode(p, True, True, dist=999) == 'follow')
    check('K7d 主角在动且近 → FREE（自主行动是常态）',
          CR.select_mode(p, True, True, dist=10) == 'free')
    check('K7e 主角静止 → FREE', CR.select_mode(p, True, False, dist=999) == 'free')
    check('K7f 距离未知且主角在动 → FOLLOW（不知道多远时跟上更安全）',
          CR.select_mode(p, True, True, dist=None) == 'follow')
    check('K7g 阈值可调（far_threshold=5 时 dist=10 变 FOLLOW）',
          CR.select_mode(p, True, True, dist=10, far_threshold=5) == 'follow')

    r_am = two()
    modes = CR.apply_modes(r_am, (1000.0, 0.0), leader_moving=True)
    check('K8 apply_modes 对全队生效',
          set(modes) == {'ralsei', 'susie'} and set(modes.values()) == {'follow'},
          'modes=%r' % modes)
    modes2 = CR.apply_modes(r_am, None, leader_moving=True)
    check('K8b 主角不在场 ⇒ 全队 FREE', set(modes2.values()) == {'free'},
          'modes=%r' % modes2)
    modes3 = CR.apply_modes(r_am, (1000.0, 0.0), leader_moving=True, need_rally=True)
    check('K8c need_rally 覆盖 FOLLOW', set(modes3.values()) == {'rally'})

    # =======================================================================
    section('L 端到端（CompanionStage：三层串起来）')
    # =======================================================================
    st = CR.CompanionStage(min_gap=0.0)
    st.add(CM.Companion('ralsei', display_name='Ralsei', aliases=['ral'], slot=0))
    st.add(CM.Companion('susie', display_name='Susie', aliases=['sus'], slot=1))
    st.roster.activate(['ralsei', 'susie'], leader_xy=(10.0, 10.0))
    check('L1 用别名说话能入库（证明 refresh_log_index 生效）',
          st.say('ral', '我们该出发了。') == (True, ''),
          'rejected=%r' % st.log.rejected())
    check('L1b 定向消息能入库', st.say('sus', '随便。', to_id='ralsei') == (True, ''))
    check('L1c ★ 无主消息被拒', st.say(None, '……')[0] is False)
    check('L1d 端到端上下文带名字 + 别名被归一',
          st.context() == ['[Ralsei] 我们该出发了。', '[Susie→Ralsei] 随便。'],
          'got=%r' % st.context())

    nxt = st.tick(0.0)
    check('L2 tick 给出下一个说话人',
          nxt is not None and nxt.speaker_id in ('ralsei', 'susie'))
    check('L2b ★ tick 之后 busy（不许再并发问）',
          st.scheduler.busy is True and st.tick(0.0) is None)
    ok_l2, _ = st.done(0.0, nxt.speaker_id)
    check('L2c done 正常收束', ok_l2 is True and st.scheduler.busy is False)

    moved_n = st.step((1000.0, 10.0), leader_moving=True)
    check('L3 step 全链路：决策 + 移动都跑了',
          moved_n == 2
          and all(c.mode == CM.FollowMode.FOLLOW for c in st.roster.active()),
          'moved=%d modes=%r' % (moved_n, [c.mode for c in st.roster.active()]))
    check('L3b 主角不在场时 step 不移动且不崩',
          st.step(None, leader_moving=True) == 0)

    # =======================================================================
    section('M 恒真判据自查（本套件自己也要能被查）')
    # =======================================================================
    own = io_read(os.path.abspath(__file__))
    tree = ast.parse(own)
    const_true = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'check':
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value is True:
                const_true.append(node.lineno)
    check('M1 ★★ 本套件没有 check(..., True) 这种恒真判据', not const_true,
          'lineno=%r' % const_true)
    check('M2 本套件不 import Qt', not (_imports_of(own) & _QT_MODULES),
          'imports=%s' % sorted(_imports_of(own)))
    check('M3 负控制确实是成对设计的（"负控制"字样 ≥ 14 处）',
          own.count('负控制') >= 14, 'count=%d' % own.count('负控制'))

    print()
    print('RESULT: PASS=%d FAIL=%d' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
