# -*- coding: utf-8 -*-
"""第二十五轮 · 收尾四项的行为级验证（G2 看不见的部分）。

G2 是「产品行为回归」，它**结构上看不见**本轮三类改动：
  1. video_controller 的 hasattr -> getattr(is not None)：只在"定时器已建"时才走 stop()，
     而 G2 的套件不跑真机视频播放循环。
  2. games_controller 新增的 __setattr__：G2 的 games 套件走的是**原地改字典**
     （game_state.update / [k] += 1），**根本不触发 __setattr__** → 新旧都绿。
  3. main.py 的 8 处 hasattr 改写：同样在 G2 的静态/单元断言之外。

所以本文件是**独立维度**（对应速查本「A/B 只能证两版行为等价、不能证落点正确；
凡涉及 self 指谁的改动必须有非 A/B 的独立维度」）。
用真控制器实例 + 真宿主，逐条断言行为。
"""
import io
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet"))
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "src"))

PASS = 0
FAIL = 0
FAILS = []


def chk(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILS.append("%s %s" % (name, extra))


# ---------------------------------------------------------------- 静态哨兵
def code_only(path):
    """规范化的「只有代码」文本：**注释已移除、docstring 已移除、字符串字面量保留**。

    ⚠️ 前三版都栽在同一个地方，记下来防止第四次（速查本「源级断言别用
    `"字面量" in 源码`」的同族坑）：
      第 1 版 正则逐行剥引号 → 跨行三引号 docstring 漏剥（假绿）；
               且 `re.sub(r"'[^']*'")` 把 `'p'` 也抹了 → 8 项假红。
      第 2 版 tokenize 剥**所有** STRING → 断言要找的 `'p'` / `'video_watching_timer'`
               本身也没了 → 13 项假红。
      第 3 版 tokenize 只剥 docstring/COMMENT，但 tokenize 会在**每个 token 之间**
               插空格（`f ( x )`、`'p' `）→ 含字面量的 needle 仍匹配不上 → 16 项假红。
    结论：**不要自己写清洗器**。`ast.unparse` 就是这个需求的标准答案 ——
    它输出规范化的 Python 源码，注释天然消失，docstring 作为字符串表达式
    （`Expr(Constant(str))`）被显式剔除，而函数实参里的字面量**原样保留**。
    """
    import ast
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    # 剔除所有「裸字符串表达式」= docstring / 游离字符串（对模块/类/函数体一致处理）
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            blk = getattr(node, field, None)
            if isinstance(blk, list):
                setattr(node, field, [
                    s for s in blk
                    if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                            and isinstance(s.value.value, str))
                ])
    return ast.unparse(tree)


VID = os.path.join(ROOT, "ralsei_pet", "modules", "video_controller.py")
GAM = os.path.join(ROOT, "ralsei_pet", "modules", "games_controller.py")
MAIN = os.path.join(ROOT, "ralsei_pet", "src", "main.py")

vid_code = code_only(VID)
chk("V1 stop_watching_video 用 getattr 非 None 判据",
    "getattr(self, 'video_watching_timer', None) is not None" in vid_code)
# V2 必须在**方法范围内**断言：L516 的 `_start_video_watching_loop` 里也有
# `hasattr(self, 'video_watching_timer')`，那是"未建则建"的正统写法、**必须保留**
# （第一版写成全文件 not-in → 假红）。
_slice = vid_code[vid_code.index("def stop_watching_video"):
                  vid_code.index("def suggest_watching_video")]
chk("V2 stop_watching_video 内不再用 hasattr 判定时器",
    "hasattr(self, 'video_watching_timer')" not in _slice, repr(_slice[:0]))
chk("V3 与 _start_video_watching_loop 的 `is not None` 契约一致",
    vid_code.count("video_watching_timer") >= 3 and "is not None" in vid_code)
chk("V4 video_controller 里 hasattr 只剩 1 处（'未建则建' 分支，语义正确须保留）",
    vid_code.count("hasattr(") == 1, "count=%d" % vid_code.count("hasattr("))

gam_code = code_only(GAM)
chk("G1 games_controller 已实现 __setattr__",
    "def __setattr__(self, name, value):" in gam_code)
chk("G2 __setattr__ 必跳过 'p'", "if name != 'p':" in gam_code)
chk("G3 __setattr__ 兜底走 object.__setattr__",
    "object.__setattr__(self, name, value)" in gam_code)
chk("G4 判据是宿主已拥有（实例字典 or MRO）",
    "name in pet.__dict__" in gam_code and "type(pet).__mro__" in gam_code)
chk("G5 五个控制器 now 全有 __setattr__（同构）",
    all("def __setattr__" in code_only(os.path.join(ROOT, "ralsei_pet", "modules", f))
        for f in ("games_controller.py", "video_controller.py", "spell_controller.py",
                  "hide_controller.py", "file_sheet_controller.py")))

main_code = code_only(MAIN)
_TARGETS = ("last_movement_end_time", "previous_direction", "_last_env_update",
            "_cached_screen_geom", "fall_slide_speed_y", "_last_drag_pos",
            "_fall_phase", "_bounce_params")
for nm in _TARGETS:
    chk("M-getattr %s" % nm,
        "getattr(self, '%s', None)" % nm in main_code)
chk("M1 8 处读取守卫已全部改写",
    all("getattr(self, '%s', None)" % nm in main_code for nm in _TARGETS))
# 用 AST 分类：READ 型守卫应为 0（写回型 = False / 删除型 del|delattr 必须保留）
_mt = __import__("ast").parse(io.open(MAIN, encoding="utf-8").read())
_read_left = []
for _par in __import__("ast").walk(_mt):
    _b = getattr(_par, "body", None)
    if not isinstance(_b, list):
        continue
    for _st in _b:
        if isinstance(_st, __import__("ast").If):
            _t = _st.test
            _neg = isinstance(_t, __import__("ast").UnaryOp) and isinstance(_t.op, __import__("ast").Not)
            if _neg:
                _t = _t.operand
            _nm = None
            if isinstance(_t, __import__("ast").Call) and isinstance(_t.func, __import__("ast").Name) \
                    and _t.func.id == "hasattr" and len(_t.args) >= 2 \
                    and isinstance(_t.args[0], __import__("ast").Name) and _t.args[0].id == "self" \
                    and isinstance(_t.args[1], __import__("ast").Constant):
                _nm = _t.args[1].value
            if not _nm:
                continue
            import ast as _A
            _creates = any(isinstance(_s, _A.Assign) and any(
                isinstance(_x, _A.Attribute) and isinstance(_x.value, _A.Name)
                and _x.value.id == "self" and _x.attr == _nm for _x in _s.targets) for _s in _st.body)
            _dels = any((isinstance(_s, _A.Delete) and any(
                isinstance(_x, _A.Attribute) and isinstance(_x.value, _A.Name)
                and _x.value.id == "self" and _x.attr == _nm for _x in _s.targets))
                or (isinstance(_s, _A.Expr) and isinstance(_s.value, _A.Call)
                    and isinstance(_s.value.func, _A.Name) and _s.value.func.id == "delattr")
                for _s in _st.body)
            if not _creates and not _dels:
                _read_left.append((_st.lineno, _nm))
chk("M2 AST 分类：READ 型守卫已清零（仅剩建缓存型/删除型/写回型）",
    len(_read_left) == 0, "left=%r" % _read_left)

# ---------------------------------------------------------------- 行为级
import importlib
gc = importlib.import_module("modules.games_controller")


class FakeHost(object):
    """最小宿主：有 game_state（实例字典成员）+ 一个 MRO 上的方法。"""

    def __init__(self):
        self.game_state = {"is_playing": False}

    def host_method(self):
        return "host"


ctrl = gc.GamesController(FakeHost())

# 行为 1：写宿主「已拥有」的名字 → 必须落到宿主
ctrl.game_state = {"is_playing": True, "x": 1}
chk("B1 写宿主已拥有属性 → 落到宿主",
    ctrl.p.game_state.get("is_playing") is True, repr(ctrl.p.game_state))
chk("B2 该属性未落进控制器 __dict__",
    "game_state" not in ctrl.__dict__, repr(list(ctrl.__dict__)))

# 行为 2：写宿主没有的名字 → 留在控制器自己身上（故意不允许新增业务属性）
ctrl.brand_new_attr = 42
chk("B3 写宿主没有的名字 → 留在控制器",
    ctrl.__dict__.get("brand_new_attr") == 42 and not hasattr(ctrl.p, "brand_new_attr"))

# 行为 3：'p' 必须留在控制器（否则拿不到宿主）
chk("B4 'p' 未被转发出去（宿主无 p）", not hasattr(ctrl.p, "p"))
chk("B5 'p' 仍指向宿主", ctrl.p is ctrl.__dict__["p"])

# 行为 4：读回落仍正常
chk("B6 读回落（宿主实例字典）正常", ctrl.game_state["x"] == 1)
chk("B7 读回落（宿主 MRO）正常", ctrl.host_method() == "host")

# 行为 5：反控 —— 若 __setattr__ 被摘掉，行为 1 会失败
_patched = gc.GamesController.__setattr__


class NoGuard(gc.GamesController):
    __setattr__ = object.__setattr__  # 故意破坏


c2 = NoGuard(FakeHost())
c2.game_state = {"is_playing": True}
chk("B8 反控：去掉护栏后状态确实会劈裂（证明 B1 有鉴别力）",
    "game_state" in c2.__dict__ and not c2.p.__dict__.get("game_state", {}).get("is_playing"))

print("PASS=%d FAIL=%d" % (PASS, FAIL))
for f in FAILS:
    print("  FAIL: " + f)
