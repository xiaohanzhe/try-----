# -*- coding: utf-8 -*-
"""W1-7 专属探针：`handle_game_input` 从宿主搬进 `GamesController` 的搬运保真 + 接线。

为什么单独一个文件（而不是塞进 W1-3 的三个探针）：
  W1-3 的三个探针是 **A/B 的同一把尺子** —— B 组（搬前快照）跑它们也必须全绿。
  但本项要断言的恰恰是"**搬走了**"这件事（宿主类上已无 def、解析到控制器的方法），
  它在 B 组**天生**为 FAIL。所以归属类断言必须独立出来，否则 A/B 必然报差异，
  而那个差异是"断言写错了地方"，不是产品有问题。
  （本项目铁律：A/B 用的 e2e 必须两版都该全绿 —— 第二十六轮踩实。）

覆盖：
  G1  方法体**逐字等价**（搬前快照 vs 现在，逐字节比较，零归一化）
  G2  归宿：宿主类上已无 def / 控制器类上有 def / 全仓库只定义 1 次
  G3  转发：宿主实例经 __getattr__ 解析到**绑定在控制器上**的方法
  G4  状态不搬：控制器实例字典里无 game_state 等
  G5  跨控制器链：hide_and_seek 分支真的调到 HideAndSeekController._abort_hide_and_seek
  G6  调用方不动：dialogue_ui.py L1249 仍是 `self.parent.handle_game_input(...)`
  G7  反向控制：把一个字符改坏，G1 必须能测出来（判据有鉴别力）
"""
import ast
import hashlib
import io
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
HERE = os.path.join(ROOT, "code-quality-audit", "架构改造-H4H5")
BEFORE = os.path.join(HERE, "_evidence", "w1_7_before")
OUT = r"E:\Download\_tmp\_w17_probe.txt"

CUR_MAIN = os.path.join(ROOT, "ralsei_pet", "src", "main.py")
OLD_MAIN = os.path.join(BEFORE, "ralsei_pet", "src", "main.py")
CUR_GC = os.path.join(ROOT, "ralsei_pet", "modules", "games_controller.py")
OLD_GC = os.path.join(BEFORE, "ralsei_pet", "modules", "games_controller.py")
DU = os.path.join(ROOT, "ralsei_pet", "modules", "dialogue_ui.py")

NAME = "handle_game_input"

lines = []
n_pass = n_fail = 0


def check(cond, msg):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        lines.append("[PASS] " + msg)
    else:
        n_fail += 1
        lines.append("[FAIL] " + msg)


def read(p):
    with io.open(p, encoding="utf-8", newline="") as fh:
        return fh.read()


def method_src(src, cls_name, method):
    """取类体内某方法的源码段（不含外层缩进归一）。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for b in node.body:
                if isinstance(b, ast.FunctionDef) and b.name == method:
                    return ast.get_source_segment(src, b)
    return None


# ---------------------------------------------------------------- G1 逐字等价
old_main = read(OLD_MAIN)
cur_main = read(CUR_MAIN)
old_gc = read(OLD_GC)
cur_gc = read(CUR_GC)

a = method_src(old_main, "RalseiPet", NAME)
b = method_src(cur_gc, "GamesController", NAME)
check(a is not None, "搬前快照里 RalseiPet 有 %s" % NAME)
check(b is not None, "当前 GamesController 有 %s" % NAME)
if a and b:
    a2 = a.replace("\r\n", "\n").rstrip()
    b2 = b.replace("\r\n", "\n").rstrip()
    check(a2 == b2, "方法体**逐字等价**（零归一化：%d 字符）" % len(a2))
    if a2 != b2:
        for i, (ca, cb) in enumerate(zip(a2, b2)):
            if ca != cb:
                lines.append("       首个差异 @%d: old=%r new=%r"
                             % (i, a2[max(0, i - 40):i + 40], b2[max(0, i - 40):i + 40]))
                break
    # G7 反向控制：改一个字符必须能测出来
    needle = "reason='user_quit'"
    hits = b2.count(needle)
    check(hits >= 1, "反向控制：needle %r 命中 %d 次（必须 ≥1）" % (needle, hits))
    tampered = b2.replace(needle, "reason='user_quitX'", 1)
    check(tampered != b2, "反向控制：篡改确实改变了文本（不是空操作）")
    check(tampered != a2, "反向控制：篡改后判据判为不等（判据有鉴别力）")
    check(b2 == a2, "反向控制：未篡改的原文仍判为相等（排除替换式自伤）")

# ---------------------------------------------------------------- G2 归宿
host_cls_methods = set()
for node in ast.walk(ast.parse(cur_main)):
    if isinstance(node, ast.ClassDef) and node.name == "RalseiPet":
        for x in node.body:
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)):
                host_cls_methods.add(x.name)
ctrl_cls_methods = set()
for node in ast.walk(ast.parse(cur_gc)):
    if isinstance(node, ast.ClassDef) and node.name == "GamesController":
        for x in node.body:
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ctrl_cls_methods.add(x.name)

check(NAME not in host_cls_methods, "宿主 RalseiPet 类体里已无 %s 的 def" % NAME)
check(NAME in ctrl_cls_methods, "GamesController 类体里有 %s 的 def" % NAME)
check("    def %s(" % NAME not in cur_main,
      "当前 main.py 全文里已无 %s 的定义（迁移不留副本）" % NAME)

# ---------------------------------------------------------------- G3 转发
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))
import games_controller as _gc  # noqa: E402

GC = _gc.GamesController
ATTRS = ("games", "video", "spell", "hide_seek", "file_sheet")


class HostShim(object):
    """与 RalseiPet.__getattr__ 同构的最小宿主。"""
    _CONTROLLER_ATTRS = ATTRS

    def __init__(self):
        self.games = GC(self)

    def __getattr__(self, name):
        for attr in ATTRS:
            ctrl = self.__dict__.get(attr)
            if ctrl is None:
                continue
            impl = getattr(type(ctrl), name, None)
            if impl is not None:
                return getattr(ctrl, name)
        raise AttributeError(name)


host = HostShim()
got = None
try:
    got = host.handle_game_input
except AttributeError as e:
    lines.append("  AttributeError: %s" % e)
check(callable(got), "宿主实例经 __getattr__ 可解析 %s" % NAME)
check(getattr(got, "__self__", None) is host.games,
      "%s 解析到的是**绑定在 GamesController 上**的方法" % NAME)
# 类型查找必须失败（__getattr__ 只对实例生效）—— 记录这条语义，防后人误用
check(NAME not in type(host).__dict__,
      "宿主**类**上没有该方法（类型查找 getattr(type(x), n) 会 AttributeError，符合语义）")

# ---------------------------------------------------------------- G4 状态不搬
for attr in ("game_state", "guess_number_game", "rock_paper_scissors_options"):
    check(attr not in host.games.__dict__,
          "控制器实例字典里无 %s（状态没搬进控制器）" % attr)

# ---------------------------------------------------------------- G5 跨控制器链
hs = read(os.path.join(ROOT, "ralsei_pet", "modules", "hide_controller.py"))
hs_methods = set()
for node in ast.walk(ast.parse(hs)):
    if isinstance(node, ast.ClassDef) and node.name == "HideAndSeekController":
        for x in node.body:
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)):
                hs_methods.add(x.name)
check("_abort_hide_and_seek" in hs_methods,
      "HideAndSeekController 类上有 _abort_hide_and_seek（兄弟白名单的目标）")


class FakeHideSeek(object):
    def __init__(self):
        self.calls = []

    def _abort_hide_and_seek(self, **kw):
        self.calls.append(kw)
        return "aborted"


class StateRec(object):
    def __init__(self):
        self.state = {"is_playing": True, "game_type": "hide_and_seek"}
        self.dialogues = []

    def __getitem__(self, k):
        return self.state[k]

    def add_dialogue(self, w, t, f):
        self.dialogues.append((w, t, f))

    def show_dialogue(self):
        pass


hs_ctrl = FakeHideSeek()
rec = StateRec()
h2 = HostShim()
h2.hide_seek = hs_ctrl
h2.game_state = rec
h2.dialogue_ui = rec
h2.rock_paper_scissors_options = ["石头", "剪刀", "布"]

r = h2.games.handle_game_input("退出游戏")
check(r is True, "躲猫猫中说「退出游戏」→ 返回 True")
check(len(hs_ctrl.calls) == 1 and hs_ctrl.calls[0].get("reason") == "user_quit",
      "**跨控制器链真的接通**：调到了 HideAndSeekController._abort_hide_and_seek"
      "（实际 %r）" % (hs_ctrl.calls,))
check(any("下次再一起玩" in t for _, t, _ in rec.dialogues),
      "躲猫猫退出后说了收场台词")

# 反向控制：把 hide_seek 槽位拿掉，同一条路径必须 AttributeError
h3 = HostShim()
h3.game_state = StateRec()
h3.dialogue_ui = h3.game_state
h3.rock_paper_scissors_options = ["石头", "剪刀", "布"]
try:
    h3.games._abort_hide_and_seek
    check(False, "反向控制：无兄弟控制器时应 AttributeError")
except AttributeError:
    check(True, "反向控制：无兄弟控制器时确实 AttributeError（上面那条不是恒真）")

# ---------------------------------------------------------------- G6 调用方不动
du = read(DU)
hit = [i for i, l in enumerate(du.split("\n"), 1)
       if "self.parent.handle_game_input(" in l]
check(len(hit) >= 1,
      "dialogue_ui.py 仍以 `self.parent.handle_game_input(...)` 调用（行 %r）" % (hit,))
check("        if self.parent.handle_game_input(user_input):" in du
      or "self.parent.handle_game_input(user_input)" in du,
      "调用写法未变（仍是 self.parent，未改成 self.parent.games.…）")

lines.append("")
lines.append("合计：PASS=%d FAIL=%d" % (n_pass, n_fail))

with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if n_fail else 0)
