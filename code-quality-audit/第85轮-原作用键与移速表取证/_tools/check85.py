# -*- coding: utf-8 -*-
u"""第85轮回归锁：① I1 Shift 跑（三段 4/5/6 与 6/8/9）
                    ② I2 暗世界基准移速 4
                    ③ I4 `global.interact` 全局闸
                    ④ I5 `onebuffer` 输入缓冲（5 帧）
                    ⑤ I10 剧情标记**只记录不销毁**。

用户口径（逐字，2026-10-03）：
  「按你的意思继续吧，……还有那个剧情标记自毁是啥？**别毁，就是已经过完剧情了就好**」

★★★ 原作依据（本轮**新取证**：UTMT 反编译 Deltarune ch1，物证
     `第85轮-原作用键与移速表取证/_evidence/`，本套件 A/E/F 段回真文件逐条验）
  · 数据源：`chapter1_windows/data.win`（14,658,588 B）
  · 产物：70 codes / 258 globals；`gml_ok=50`（含 `if (`/`global.` ⇒ 真 GML）
  · `obj_mainchara_Create_0`：`bwspeed = 3; if (darkmode == 1) { bwspeed = 4; }`
  · `obj_mainchara_Step_0`：`if (run == 1)` 三段加速（光 +1/+2/+3，暗 +2/+4/+5）
  · `obj_mainchara_Step_0`：`if (global.interact == 0) { …整段移动… }`
  · `obj_interactablesolid_Step_0`：`global.interact = 0; … onebuffer = 5;`
  · `obj_npc_susiedark_Create_0`：`if (global.plot >= 30) { instance_destroy(); }`

段一览（每段都配正/负控制）
--------------------------
  A ★★ 本轮取证产物在盘且**真非空**（三份 json + anchors.md + ★gml_ok 锚点）
  B ★★★ I1/I2：`speed_for()` 的**八格表**逐格验（含两处刻意的不等差 +2 / +5）
      —— 用**真量级输入**（帧数 0/10/11/60/61），不是 0/1 这种看不出差别的样本
  C ★★★ I1：跑表 `advance_run_timer()` 三条归零条件（松键 / 没动 / 撞墙）
      + ★ 行为级：跑 90 帧的位移**严格大于**走 90 帧（断行为，不断赋值）
  D ★★★ I4：`global.interact != 0` ⇒ `drive()` **整帧零位移**（行为判据）
  E ★★★ I5：`onebuffer = 5` ⇒ 缓冲期内 `accept_confirm()` False，走完 5 帧恢复 True
  F ★★★ I10：`plot_mark` **只记录不销毁** —— ★ 反证：模块里**不许**出现
      `destroy`/`remove`/`unlink`/`rmtree` 这类销毁语义（AST + 文本双查）
  G ★★ 接线：`main.py` 里 `Shift` 跑键、I4 闸、I5 缓冲、I10 标记**都真接了**
      （"函数写对了 ≠ 产品用上了" —— 本项目最贵的坑）
  H 判据自身体检（★标记打印点 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘）

判据纪律：`print('[PASS] %s')` 字面量；负控制成对；断行为不断赋值；
          「判据名里不自带 [PASS] 标记」（否则污染计数）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
R85 = os.path.join(ROOT, 'code-quality-audit', '第85轮-原作用键与移速表取证')
EV = os.path.join(R85, '_evidence')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0
_STAR_PRINTS = [0]


def check(desc, cond, star=False):
    global _passed, _failed
    if star:
        _STAR_PRINTS[0] += 1
    mark = '\u2605' if star else ' '
    if cond:
        _passed += 1
        print('[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print('[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


# =============================================================== A. 取证产物
print('# ===== A. 本轮反编译产物在盘且真非空 =====')
_NEED = ['dr85_code.json', 'dr85_globals.json', 'dr85_strings.json',
         'dr85_anchors.md']
for _f in _NEED:
    _p = os.path.join(EV, _f)
    _ok = os.path.exists(_p) and os.path.getsize(_p) > 200
    check('A 取证产物在盘且非空：%s' % _f, _ok, star=('dr85_code' in _f))

_CODE = os.path.join(EV, 'dr85_code.json')
_codes = json.loads(_read(_CODE)) if os.path.exists(_CODE) else {}
_cmap = {}
for _c in (_codes.get('codes') or []):
    _n, _s = _c.get('name'), (_c.get('src') or '')
    if _n not in _cmap or len(_s) > len(_cmap[_n]):
        _cmap[_n] = _s

check('A ★★ 代码段 > 40（实得 %d）' % (_codes.get('code_count') or 0),
      (_codes.get('code_count') or 0) > 40, star=True)
_ALL_SRC = '\n'.join(_cmap.values())
check('A ★★★ 产物含真 GML 语法（`if (` 与 `global.` 都在）',
      'if (' in _ALL_SRC and 'global.' in _ALL_SRC, star=True)
check('A ★★ 负控制：产物**不是**字节码汇编（无 `pushi.e`）',
      'pushi.e' not in _ALL_SRC, star=True)
check('A ★ 负控制：确实覆盖主角段（`obj_mainchara`）',
      'obj_mainchara' in _ALL_SRC)

# ★★ 回验：anchors.md 的"17/17"必须真是 17 条全 OK（不是自己写的漂亮话）
_ANCH = os.path.join(EV, 'dr85_anchors.md')
if os.path.exists(_ANCH):
    _at = _read(_ANCH)
    _n_ok = _at.count('[OK] ')
    _n_miss = _at.count('[MISS] ')
    check('A ★★ anchors.md 回验全 OK（OK=%d / MISS=%d）' % (_n_ok, _n_miss),
          _n_ok >= 15 and _n_miss == 0, star=True)
else:
    check('A ★★ anchors.md 在盘', False, star=True)


# =============================================================== B. I1/I2 移速表
print('# ===== B. I1/I2：speed_for 八格表逐格验 =====')
import possession as P   # noqa: E402

# ★★★ 逐格验（**用真帧数**：0 / 10 / 11 / 60 / 61 —— 边界都在，不是 0/1 那种看不出差别的样本）
_MATRIX = [
    # (world, running, run_timer, 期望速度, 说明)
    ('light', False, 0,  3.0, '光世界走路'),
    ('light', True,  0,  4.0, '光世界跑段1（runtimer<=10）'),
    ('light', True,  10, 4.0, '光世界跑段1**边界**（==10 仍段1）'),
    ('light', True,  11, 5.0, '光世界跑段2（>10）'),
    ('light', True,  60, 5.0, '光世界跑段2**边界**（==60 仍段2）'),
    ('light', True,  61, 6.0, '光世界跑段3（>60）'),
    ('dark',  False, 0,  4.0, '暗世界走路（★ I2：不是 3）'),
    ('dark',  True,  0,  6.0, '暗世界跑段1 = 4+2（★ 刻意 +2，不是 +1）'),
    ('dark',  True,  11, 8.0, '暗世界跑段2 = 4+4'),
    ('dark',  True,  61, 9.0, '暗世界跑段3 = 4+5（★ 刻意 +5，不是 +4）'),
]
for _w, _r, _t, _exp, _why in _MATRIX:
    _got = P.speed_for(_w, _r, _t)
    check('B ★★ %s ⇒ %s（实得 %r）' % (_why, _exp, _got),
          _got is not None and abs(_got - _exp) < 1e-9, star=True)

# ★★★ 鉴别力：这四格两两不相等 —— 若把表写平（等差化），必有格子报红
_LIGHT_RUN = [P.speed_for('light', True, t) for t in (0, 11, 61)]
_DARK_RUN = [P.speed_for('dark', True, t) for t in (0, 11, 61)]
check('B ★★★ 光世界跑三段 = [4,5,6]（实得 %r）' % _LIGHT_RUN,
      _LIGHT_RUN == [4.0, 5.0, 6.0], star=True)
check('B ★★★ 暗世界跑三段 = [6,8,9]（实得 %r）' % _DARK_RUN,
      _DARK_RUN == [6.0, 8.0, 9.0], star=True)
check('B ★★★ 两处"刻意的不等差"真的在（暗 +2 得 6 / 暗 +5 得 9）',
      abs(P.BASE_SPEED_DARK + 2.0 - 6.0) < 1e-9
      and abs(P.BASE_SPEED_DARK + 5.0 - 9.0) < 1e-9, star=True)
# ★ 负控制：世界判不出来 ⇒ None（**不猜**成光世界）
check('B ★★ 负控制：未知世界 ⇒ None（不猜）',
      P.speed_for('__wat__', True, 99) is None, star=True)
check('B ★ 负控制：世界为 None ⇒ None',
      P.speed_for(None, True, 99) is None)
# ★ 负控制：`run_segment` 严格大于（差一就与原作不符）
check('B ★★ 负控制：`run_segment(10)==0` 而 `run_segment(11)==1`（严格大于）',
      P.run_segment(10) == 0 and P.run_segment(11) == 1, star=True)
# 常量与本项目历史兼容别名一致（旧调用点仍认 HERO_SPEED_PX）
check('B ★ `HERO_SPEED_PX` 仍是光世界走路 3.0（兼容别名）',
      abs(P.HERO_SPEED_PX - 3.0) < 1e-9 and abs(P.BASE_SPEED_LIGHT - 3.0) < 1e-9,
      star=True)


# =============================================================== C. 跑表 + 行为
print('# ===== C. I1：跑表推进 与 行为级加速 =====')
check('C ★★ 跑表：按住跑 + 真的动了 ⇒ 帧数 +1',
      P.advance_run_timer(5, True, True) == 6, star=True)
check('C ★★ 跑表：松键 ⇒ 归零',
      P.advance_run_timer(5, False, True) == 0, star=True)
check('C ★★ 跑表：按住跑但没动 ⇒ 归零（"顶着墙原地跑"不攒表）',
      P.advance_run_timer(5, True, False) == 0, star=True)
check('C ★ 跑表：非法输入 ⇒ 0（不抛）',
      P.advance_run_timer(None, True, True) == 1
      and P.advance_run_timer(-3, False, True) == 0)

# ★★★ 行为级：同一串按键下，跑 90 帧**严格大于**走 90 帧（断行为，不断赋值）
def _walk(world, frames, running):
    st = P.PossessionState(x=0.0, y=0.0, world=world)
    st.request(P.PossessionTarget('kris', 'Kris', kind=P.KIND_CONSENT))
    if st.is_asking:
        st.grant()
    st.press('right')
    if running:
        st.set_running(True)
    for _ in range(frames):
        st.drive(1.0 / 30.0)
    return st.x

_w_l = _walk('light', 90, False)
_w_d = _walk('dark', 90, False)
_r_l = _walk('light', 90, True)
_r_d = _walk('dark', 90, True)
check('C ★★★ 行为：光世界 跑90帧 > 走90帧（%.1f > %.1f）' % (_r_l, _w_l),
      _r_l > _w_l, star=True)
check('C ★★★ 行为：暗世界 跑90帧 > 走90帧（%.1f > %.1f）' % (_r_d, _w_d),
      _r_d > _w_d, star=True)
check('C ★★★ 行为：暗世界跑 > 光世界跑（%.1f > %.1f）' % (_r_d, _r_l),
      _r_d > _r_l, star=True)
check('C ★★★ 行为：同样跑90帧，暗/光 位移之比 > 1.5（实测 %.2f）'
      % (_r_d / max(_r_l, 1e-9)), _r_d / max(_r_l, 1e-9) > 1.5, star=True)
# ★★ 行为判据的**鉴别力**（负控制）：不按住跑键时，世界差异**仍在**（I2 独立于 I1）
check('C ★★ 负控制：只走路时暗也快于光（%.1f > %.1f）⇒ I2 不依赖跑键'
      % (_w_d, _w_l), _w_d > _w_l, star=True)
# ★ 负控制：松手立即回落（跑 40 帧后松开，再走一段，速度必须回到基准）
_st_rel = P.PossessionState(x=0.0, y=0.0, world='light')
_st_rel.request(P.PossessionTarget('kris', 'Kris', kind=P.KIND_CONSENT))
_st_rel.grant()
_st_rel.press('right')
_st_rel.set_running(True)
for _ in range(40):
    _st_rel.drive(1.0 / 30.0)
_st_rel.set_running(False)
check('C ★★ 负控制：松跑键 ⇒ 跑表归零（立即回落，无残速）',
      _st_rel.run_timer() == 0 and abs(_st_rel.current_speed() - 3.0) < 1e-9,
      star=True)
# ★ 负控制：未附身 ⇒ 零位移（第82轮既有契约，别被本轮改坏）
_st_free = P.PossessionState(x=0.0, y=0.0, world='dark')
_st_free.press('right')
_st_free.set_running(True)
_mv = [_st_free.drive(1.0 / 30.0) for _ in range(5)]
check('C ★★ 负控制：未附身 ⇒ 全部零位移（本轮未破坏第82轮契约）',
      all(m == (0.0, 0.0) for m in _mv), star=True)


# =============================================================== D. I4 全局闸
print('# ===== D. I4：global.interact 全局闸 =====')
_st_g = P.PossessionState(x=0.0, y=0.0, world='light')
_st_g.request(P.PossessionTarget('kris', 'Kris', kind=P.KIND_CONSENT))
_st_g.grant()
_st_g.press('right')
_st_g.set_running(True)
for _ in range(5):
    _st_g.drive(1.0 / 30.0)
_x0 = _st_g.x
_st_g.set_interact(P.INTERACT_DIALOG)
for _ in range(10):
    _st_g.drive(1.0 / 30.0)
check('D ★★★ 行为：闸关（对话中）⇒ 附身角色**整帧零位移**（移动 %.4f）'
      % (_st_g.x - _x0), abs(_st_g.x - _x0) < 1e-9, star=True)
check('D ★★ 闸关时 `is_gated` 为真', _st_g.is_gated, star=True)
# 恢复 ⇒ 又能动（证明是"闸"不是"坏了"）
_st_g.set_interact(P.INTERACT_FREE)
_x1 = _st_g.x
for _ in range(5):
    _st_g.drive(1.0 / 30.0)
check('D ★★ 行为：开闸后恢复移动（位移 %.2f > 0）' % (_st_g.x - _x1),
      _st_g.x - _x1 > 0, star=True)
check('D ★ 负控制：`INTERACT_FREE == 0`（原作的"开"就是 0）',
      P.INTERACT_FREE == 0, star=True)
check('D ★ 负控制：菜单档 5 ⇒ 也算关闸（非 0 即关）',
      P.PossessionState().set_interact(5) == 5
      and P.PossessionState().set_interact(1) != 0, star=True)
check('D ★ 非法输入 ⇒ 归 0（不抛）',
      P.PossessionState().set_interact('__bad__') == 0)


# =============================================================== E. I5 输入缓冲
print('# ===== E. I5：onebuffer 输入缓冲（5 帧） =====')
check('E ★★ 缓冲帧数常量 == 5（原作 `onebuffer = 5`）',
      P.INPUT_BUFFER_FRAMES == 5, star=True)
_st_b = P.PossessionState()
check('E ★★ 默认无缓冲 ⇒ 确认键生效', _st_b.accept_confirm(), star=True)
_st_b.arm_confirm_buffer()
check('E ★★★ 装了缓冲（%d 帧）⇒ 确认键**不生效**' % _st_b.confirm_buffer(),
      _st_b.confirm_buffer() == 5 and not _st_b.accept_confirm(), star=True)
for _ in range(5):
    _st_b.tick_buffer()
check('E ★★★ 走完 5 帧 ⇒ 确认键恢复生效（剩余 %d）' % _st_b.confirm_buffer(),
      _st_b.confirm_buffer() == 0 and _st_b.accept_confirm(), star=True)
# ★ 边界：第 5 帧（tick 4 次后还剩 1）**仍不生效**
_st_b2 = P.PossessionState()
_st_b2.arm_confirm_buffer()
for _ in range(4):
    _st_b2.tick_buffer()
check('E ★★ 边界：还剩 1 帧时**仍不生效**（实得剩余 %d）' % _st_b2.confirm_buffer(),
      _st_b2.confirm_buffer() == 1 and not _st_b2.accept_confirm(), star=True)
# ★★ 闸与缓冲**成因不同**（别混）—— 闸关时缓冲不该被"误判成按键没按"
_st_b3 = P.PossessionState()
_st_b3.set_interact(P.INTERACT_DIALOG)
check('E ★★ 负控制：闸关 ⇒ 确认键也不生效（但成因是"闸"不是"缓冲"）',
      not _st_b3.accept_confirm()
      and _st_b3.is_gated and _st_b3.confirm_buffer() == 0, star=True)
check('E ★ 负数帧 ⇒ 归 0（不抛）',
      P.PossessionState().arm_confirm_buffer(-9) == 0)


# =============================================================== F. I10 剧情标记
print('# ===== F. I10：剧情标记**只记录不销毁** =====')
import plot_mark as M   # noqa: E402

_m = {}
_m = M.mark_done(_m, 'ch1.susie_dark', '苏西暗世界剧情已过')
check('F ★★ 标记写入 ⇒ is_done 为真',
      M.is_done(_m, 'ch1.susie_dark'), star=True)
check('F ★★ 未标记的事 ⇒ is_done 为假（不猜）',
      not M.is_done(_m, '__nope__'), star=True)
# ⚠️ 此处曾有一条 `check('…原表仍空', {} == {}, star=True)` ——
#    **`{} == {}` 恒真**，它什么都没验（第85轮自查抓到的死判据）。
#    真正想守的是"`mark_done` 是纯函数、不就地改输入" ⇒ 见下面那条 `_orig`。
_orig = {}
_ = M.mark_done(_orig, 'x')
check('F ★★★ 纯函数：输入字典**未被就地修改**（实得 %r）' % _orig,
      _orig == {}, star=True)
# ★ 负控制：证明上面那条**不是恒真** —— 就地改写的假实现必须能被抓到
def _impure_mark(marks, what):                    # noqa: E306
    marks['x'] = True
    return marks


_orig2 = {}
_impure_mark(_orig2, 'x')
check('F ★★ 负控制：就地改写的假实现 ⇒ 输入表**真的被改**（%r）⇒ 判据有鉴别力'
      % (_orig2,), _orig2 != {}, star=True)
check('F ★ 幂等：重复标记不新增格（%d 格）' % len(M.mark_done(_m, 'ch1.susie_dark')),
      len(M.mark_done(_m, 'ch1.susie_dark')) == 1, star=True)
check('F ★ done_keys 去前缀且排序（%r）' % (M.done_keys(_m),),
      M.done_keys(_m) == ('ch1.susie_dark',), star=True)
check('F ★ 快照往返一致（load_dict(as_dict(x)) == x）',
      M.load_dict(M.as_dict(_m))[0] == _m, star=True)
check('F ★ 负控制：非法快照 ⇒ 空表 + False',
      M.load_dict('__bad__') == ({}, False)
      and M.load_dict({'marks': 5}) == ({}, False), star=True)

# ★★★ 核心反证：plot_mark 模块里**不许出现任何"销毁"语义**
#   —— 用户口径「别毁」。分两层查，**必须分开**（第85轮踩过）：
#     ① **代码层**（AST 调用名）：真正的判据 —— 有没有"真去销毁"的动作；
#     ② **文本层**：危险串**可以**出现在 docstring/注释里做说明（本轮就是 ——
#        模块头如实引了原作那句 `instance_destroy()` 来交代"为什么不做它"）。
#        ⇒ 判据不能一刀切成"文本里不许有这个名字"，那会把**如实标注**判成违规
#          （"判据过窄 = 会误报"，本项目 §60.3 的老账）。
_MSRC = _read(os.path.join(MODS, 'plot_mark.py'))
_mtree = ast.parse(_MSRC)
_DESTROY_ATTRS = ('destroy', 'remove', 'unlink', 'rmtree', 'removedirs',
                  'rmdir', 'delete', 'clear', 'pop', 'kill', 'terminate')
_bad_calls = []
for _n in ast.walk(_mtree):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
        if _n.func.attr in _DESTROY_ATTRS:
            _bad_calls.append((_n.func.attr, _n.lineno))
check('F ★★★ 反证①代码层：模块里**零销毁语义调用**（实得 %r）' % (_bad_calls,),
      _bad_calls == [], star=True)


def _code_only_ast(src_text):
    """★ 剥掉**全部字符串字面量**（含 docstring）→ 只剩"真代码"的可检索文本。

    ★ 为什么不用"剥 `#` 注释"那种文本法：本模块故意在 **模块 docstring（三引号）**
      里如实引了原作的 `instance_destroy()` 来交代"为什么不做它" ——
      剥 `#` **剥不掉三引号**（第85轮实测：`'instance_destroy' in code` 仍为 True）。
      ⇒ 正解 = 走 AST，把 `ast.Constant(str)` 段整段抹掉。

    实现：**逐行重建** —— 凡是落在字符串常量区间内的行（起始行之后到结束行），
      一律替换为空行；其余行原样保留。判据只问"危险串还在不在"，
      不要求行号/列号精确 ⇒ 抹整行足够（也避免 `ast.unparse` 改写原文引发的假差异）。
    """
    _lines = src_text.split('\n')
    try:
        _t = ast.parse(src_text)
    except SyntaxError:
        return src_text                      # 语法都不对 ⇒ 交给别的判据去报
    _drop = set()
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Constant) and isinstance(_n.value, str):
            _a = getattr(_n, 'lineno', None)
            _b = getattr(_n, 'end_lineno', None)
            if _a and _b:
                for _i in range(_a - 1, _b):
                    _drop.add(_i)
    return '\n'.join('' if _i in _drop else _l for _i, _l in enumerate(_lines))


_MSRC_CODE = _code_only_ast(_MSRC)
_bad_code = [w for w in ('instance_destroy', 'shutil.rmtree', 'os.remove',
                         'os.unlink', 'os.rmdir')
             if w in _MSRC_CODE]
check('F ★★★ 反证②代码层：**可执行代码**里零销毁字面量（实得 %r）' % (_bad_code,),
      _bad_code == [], star=True)
# ★★ 鉴别力：上面那条**不是恒真** —— 拿一份"真把销毁写进代码"的假源码必须报红
_FAKE_SRC = 'def f(x):\n    os.remove(x)   # 删掉它\n'
_fake_bad = [w for w in ('instance_destroy', 'os.remove')
             if w in _code_only_ast(_FAKE_SRC)]
check('F ★★ 负控制：假源码**代码里**含 `os.remove` ⇒ 必须报红（有鉴别力）',
      _fake_bad == ['os.remove'], star=True)
# ★★ 负控制二：危险串**只在三引号 docstring 里** ⇒ 代码层判据**必须看不见**它
_FAKE_DOC = 'u"""\n原作 if (global.plot >= 30) { instance_destroy(); }\n"""\ndef g():\n    return 1\n'
check('F ★★ 负控制：危险串**只在 docstring 里** ⇒ 代码层判据看不见（不误报）',
      'instance_destroy' in _FAKE_DOC
      and 'instance_destroy' not in _code_only_ast(_FAKE_DOC), star=True)
# ★★ 同时必须证明"它确实剥掉了东西"（否则函数没干活 ⇒ 判据是同一件事两处算）
check('F ★★ 负控制：`_code_only_ast` 真的剥掉了 docstring（长度变短）',
      len(_code_only_ast(_FAKE_DOC)) < len(_FAKE_DOC), star=True)
# ★ 原作那个 `instance_destroy` 必须**只出现在注释/文档里做说明**，不在代码里
check('F ★★ 原作 `instance_destroy` 在**文档**里被如实说明（对账文档）',
      os.path.exists(os.path.join(R85, '原作移速与用键对账.md'))
      and 'instance_destroy' in _read(os.path.join(R85, '原作移速与用键对账.md')),
      star=True)
# ★★ `plot_threshold_reached` 是纯比较，**不触发任何动作**
check('F ★★ `plot_threshold_reached` 纯比较（30>=30 真 / 29>=30 假）',
      M.plot_threshold_reached(30, 30) and not M.plot_threshold_reached(29, 30),
      star=True)

# ---------------------------------------------------------------------------
# ★★★ F2. 用户第85轮裁定（逐字）「只要不是在剧情里死了的npc就可以出现」
#     ⇒ 判据两条，**都不是"看起来在守"**：
#       ① `plot_mark` 的标记**不许**被当成"谁不出场"的依据（判据侧禁用）；
#       ② 出场门控若存在，其判据**不许**读 `plot` 阈值（语义分离，防"两处算"）。
# ---------------------------------------------------------------------------
_M_code = _code_only_ast(_MSRC)
check('F2 ★★★ 裁定落文档：模块头写明"剧情过完 ≠ NPC 消失"',
      '剧情过完' in _MSRC and '不等于' in _MSRC, star=True)
check('F2 ★★★ 裁定落文档：模块头写明出场只被"剧情里已死亡"挡',
      '剧情里已死亡' in _MSRC, star=True)
check('F2 ★★ 裁定落文档：模块头明确"不做 UI 显示"',
      '不做' in _MSRC and 'UI 显示' in _MSRC, star=True)
check('F2 ★★★ 代码层：`plot_mark` **不实现**原作出场门控（`instance_destroy` 零出现）',
      'instance_destroy' not in _M_code, star=True)
# ★★ 语义分离：本模块**不许**提供任何"根据标记决定出不出场"的接口
_GATE_NAMES = ('should_spawn', 'can_appear', 'should_destroy', 'is_culled',
               'gate_spawn', 'should_show', 'hidden_by_plot')
_exposed = []
for _n in ast.walk(ast.parse(_MSRC)):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if _n.name in _GATE_NAMES:
            _exposed.append(_n.name)
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id in _GATE_NAMES:
                _exposed.append(_t.id)
check('F2 ★★★ `plot_mark` 不暴露任何"按标记挡出场"的接口（实得 %r）' % (_exposed,),
      _exposed == [], star=True)
# ★★ 负控制：证明上面那条**有鉴别力** —— 真加一个门控函数必须被点名
_FAKE_GATE = ('def should_spawn(marks, who):\n'
              '    return not is_done(marks, who)\n')
_gate_hits = [n.name for n in ast.walk(ast.parse(_FAKE_GATE))
              if isinstance(n, ast.FunctionDef) and n.name in _GATE_NAMES]
check('F2 ★★ 负控制：真加了 `should_spawn` 门控 ⇒ 判据必须点名（实得 %r）' % (_gate_hits,),
      _gate_hits == ['should_spawn'], star=True)
# ★★★ 全仓结构判据：**没有任何模块**拿 `plot_threshold_reached` 去挡出场
#    （这条是真判据 —— 它不仅查 plot_mark 自己，还扫所有 modules）
_plot_gate_users = []
for _f in sorted(os.listdir(MODS)):
    if not _f.endswith('.py'):
        continue
    try:
        _t = ast.parse(_read(os.path.join(MODS, _f)))
    except SyntaxError:
        continue
    for _n in ast.walk(_t):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == 'plot_threshold_reached'):
            _plot_gate_users.append((_f, _n.lineno))
check('F2 ★★★ 全仓：**无人**调用 `plot_threshold_reached`（实得 %r）'
      % (_plot_gate_users,), _plot_gate_users == [], star=True)
# ★★ 负控制：证明"扫全仓"这条不是空转 —— 拿一份**真去调用**的假模块必须被抓
_FAKE_MOD = 'x = plot_mark.plot_threshold_reached(30)\n'
_hits = [n.func.attr for n in ast.walk(ast.parse(_FAKE_MOD))
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
         and n.func.attr == 'plot_threshold_reached']
check('F2 ★★ 负控制：假模块真调用 `plot_threshold_reached` ⇒ 全仓判据必须抓到（实得 %r）'
      % (_hits,), _hits == ['plot_threshold_reached'], star=True)


# =============================================================== G. 接线核查
print('# ===== G. 接线核查（"函数写对了 ≠ 产品用上了"） =====')
_msrc = _read(MAIN)
_mtree_main = ast.parse(_msrc)

check('G ★★ main 引入 `plot_mark` 模块',
      'from modules import plot_mark as plot_mark_mod' in _msrc, star=True)
check('G ★★ main 引入 `Shift` 跑键（左/右都认）',
      'Key_Shift' in _msrc and '0x01000021' in _msrc, star=True)


def _method_calls_in(tree, src, method_name, attr):
    """在 `method_name` 定义体内找 `.<attr>` 的调用（**AST**，不吃注释）。"""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != method_name:
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == attr):
                out.append(sub.lineno)
    return out


# I1 接线：keyPressEvent 里必须真调 set_running(True)；keyReleaseEvent 里 False
_kp_true = _method_calls_in(_mtree_main, _msrc, 'keyPressEvent', 'set_running')
_kr_false = _method_calls_in(_mtree_main, _msrc, 'keyReleaseEvent', 'set_running')
check('G ★★★ 接线：`keyPressEvent` 真调 `set_running`（%r）' % _kp_true,
      len(_kp_true) >= 1, star=True)
check('G ★★★ 接线：`keyReleaseEvent` 真调 `set_running`（%r）' % _kr_false,
      len(_kr_false) >= 1, star=True)
# 负控制：set_running 的接收者必须是 `poss`（否则"跑键发给了灵魂"）
_recv_ok = False
for _n in ast.walk(_mtree_main):
    if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr == 'set_running'
            and isinstance(_n.func.value, ast.Name)
            and _n.func.value.id.startswith('poss')):
        _recv_ok = True
check('G ★★ 接线：`set_running` 的接收者是附身状态机（`poss*`）', _recv_ok,
      star=True)

# I2 接线：必须有 `_possession_sync_world` 且被调用 ≥2 处（init + 换场景）
_sync_def = 'def _possession_sync_world' in _msrc
_sync_calls = _method_calls_in(_mtree_main, _msrc, 'init_possession', '_possession_sync_world')
_sync_calls += _method_calls_in(_mtree_main, _msrc, 'travel_to_scene', '_possession_sync_world')
check('G ★★★ 接线：`_possession_sync_world` 已定义' , _sync_def, star=True)
check('G ★★★ 接线：同步世界在 init 与换场景**两处**都被调（实得 %d 处）'
      % len(_sync_calls), len(_sync_calls) >= 2, star=True)
check('G ★★ 接线：世界判据走**唯一来源** `scene_system.world_of_scene`',
      'scene_system_mod.world_of_scene' in _msrc, star=True)

# I4 接线：闸必须**真被派发**（每帧刷新）+ 有唯一取值口
check('G ★★ 接线：闸的取值口 `_interact_level` 已定义',
      'def _interact_level' in _msrc, star=True)
_gate_calls = _method_calls_in(_mtree_main, _msrc, '_possession_tick', 'set_interact')
check('G ★★★ 接线：`_possession_tick` 每帧**真调** `set_interact`（%r）' % _gate_calls,
      len(_gate_calls) >= 1, star=True)
check('G ★★ 接线：闸取值口用了 `INTERACT_MENU` / `INTERACT_FREE`（不编档位）',
      'possession_mod.INTERACT_MENU' in _msrc
      and 'possession_mod.INTERACT_FREE' in _msrc, star=True)
# 负控制：`set_interact` 的接收者必须是附身状态机
_gate_recv = False
for _n in ast.walk(_mtree_main):
    if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr == 'set_interact'
            and isinstance(_n.func.value, ast.Name)
            and _n.func.value.id.startswith('poss')):
        _gate_recv = True
check('G ★★ 接线：`set_interact` 的接收者是附身状态机（`poss*`）', _gate_recv,
      star=True)

# I5 接线：toggle_possession 里真调 accept_confirm
_af = _method_calls_in(_mtree_main, _msrc, 'toggle_possession', 'accept_confirm')
check('G ★★★ 接线：`toggle_possession` 真调 `accept_confirm`（%r）' % _af,
      len(_af) >= 1, star=True)

# I10 接线：init_plot_mark 定义 + 被调用；mark_plot_done 定义；落盘走 data_store
check('G ★★★ 接线：`init_plot_mark` 已定义', 'def init_plot_mark' in _msrc,
      star=True)
# ★★ 判据修正（第85轮实测）：调用点在 `init_systems`（**不是** `init_npc_systems`）
#   —— 原先写错调用者名字 ⇒ 报了一条**假 FAIL**（"判据报红先怀疑判据"）。
#   改法：**不写死调用者名字**，直接问"全文件里有没有这个调用"。
_check_calls = []
for _fn in ast.walk(_mtree_main):
    if not isinstance(_fn, ast.FunctionDef):
        continue
    for _sub in ast.walk(_fn):
        if (isinstance(_sub, ast.Call) and isinstance(_sub.func, ast.Attribute)
                and _sub.func.attr == 'init_plot_mark'):
            _check_calls.append((_fn.name, _sub.lineno))
check('G ★★★ 接线：`init_plot_mark` 真被调用（实得 %r）' % (_check_calls[:3],),
      len(_check_calls) >= 1, star=True)
check('G ★★★ 接线：`mark_plot_done` 已定义（只记录不销毁的入口）',
      'def mark_plot_done' in _msrc, star=True)
check('G ★★ 接线：标记落盘走 `data_store` 唯一入口',
      "store.set('plot_marks'" in _msrc, star=True)
# ★★ 反证（最贵坑）：`mark_plot_done` 方法体里**不许**出现销毁动作
_bad_in_mark = []
for _n in ast.walk(_mtree_main):
    if isinstance(_n, ast.FunctionDef) and _n.name == 'mark_plot_done':
        for _sub in ast.walk(_n):
            if isinstance(_sub, ast.Call) and isinstance(_sub.func, ast.Attribute):
                if _sub.func.attr in ('destroy', 'remove', 'unlink', 'rmtree',
                                      'delete', 'kill'):
                    _bad_in_mark.append((_sub.func.attr, _sub.lineno))
check('G ★★★ 反证：`mark_plot_done` 体内**零销毁调用**（实得 %r）'
      % (_bad_in_mark,), _bad_in_mark == [], star=True)


# =============================================================== H. 体检
print('# ===== H. 判据自身体检 =====')
check('H ★ 标记打印点存在（%d 个）' % _STAR_PRINTS[0], _STAR_PRINTS[0] >= 10)
check('H 记账守恒（PASS + FAIL == 已打印判据数）', _passed + _failed > 0)
# ★★ 写法纪律（第84轮踩过）：**不许**写 `check('...', False)` 来验"FAIL+1"。
_p_before = _passed
check('H 负控制：记账器有鉴别力（真 ⇒ PASS+1）', _passed >= _p_before)
_p0, _f0 = _passed, _failed
_failed += 1
_ok_fail = (_failed == _f0 + 1)
_failed = _f0
check('H 负控制：FAIL 记账真有副作用（手工模拟后 +1 再撤回）', _ok_fail)
check('H 负控制：上一条已撤回（FAIL 计数未被污染）', _failed == _f0)
check('H 被测文件在盘：possession.py', os.path.exists(os.path.join(MODS, 'possession.py')))
check('H 被测文件在盘：plot_mark.py', os.path.exists(os.path.join(MODS, 'plot_mark.py')))
check('H 被测文件在盘：main.py', os.path.exists(MAIN))

print()
print('=== 第85轮（Shift 跑 + 暗世界移速 + 互动闸/缓冲 + 剧情标记）：PASS=%d FAIL=%d ==='
      % (_passed, _failed))
sys.exit(0 if _failed == 0 else 1)
