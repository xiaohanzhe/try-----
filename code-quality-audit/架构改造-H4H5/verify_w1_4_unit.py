# -*- coding: utf-8 -*-
"""W1-4 校验 · 单元级 —— 逐字等价 + 状态归属 + 回落白名单 + 反向控制。

⚠️ 本脚本第 3 版。前两版的 12 个 FAIL **全是探针自身的 bug**，一个都不是产品代码的
问题。记在这里防回退：

  ① **`\r` 未归一**：`main.py` 是 CRLF，`split("\n")` 后每行尾带 `\r`；而探针从
     `git show` 拿到的同样是 CRLF。但**切片区间**是拿两条不同的来源拼的
     （旧：旧文件行；新：新文件行），只要有一边 `\r` 被剥掉，逐字节比就全红。
     修法：两边**都**先把 `\r\n` 归一成 `\n` 再比 —— 比的是「代码内容」，
     不是「行尾风格」（行尾风格另有独立断言）。
  ② **`python -c` 里嵌三引号字面量**：外层双引号 shell 会把反斜杠转义吃掉 →
     Python 收到的字符串提前闭合 → 后续比较形态错位、误判。**含三引号的代码
     一律写进文件跑，别塞进 `-c`。**
  ③ **`video_watching_timer` 的归属是动态的**：它不是 `__init__` 里预赋值的字段，
     而是 `_start_video_watching_loop` 运行到才 `self.video_watching_timer = QTimer(self)`
     —— 写在**控制器**里，但 `self` 是宿主 → 属性落在**宿主的实例字典**上。
     所以"状态留在宿主"这句对它是**成立**的，只是"宿主源码里能搜到赋值"这个静态
     判据站不住。改成**行为级断言**（见 e2e 探针）才是对的。
  ④ **宿主 MRO 解析**：`move` / `width` / `height` 来自 `QMainWindow`（C++ 侧），
     静态 `__dict__` 扫描看不见 → 必须走真实 `type(host).__mro__` 或"已知基类白名单"。
"""
import ast
import hashlib
import io
import os
import subprocess
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
MAIN_PY = os.path.join(ROOT, "ralsei_pet", "src", "main.py")
CTRL_PY = os.path.join(ROOT, "ralsei_pet", "modules", "video_controller.py")

MOVE_METHODS = [
    "check_video_apps",
    "identify_video_apps",
    "start_watching_video",
    "_start_video_watching_loop",
    "_update_video_watching",
    "_react_to_video",
    "stop_watching_video",
    "suggest_watching_video",
]

# 施工时允许的**全部**改写（逆归一用）。除这两类之外，控制器方法体必须与父版本逐字节相同。
REWRITES = (
    ("_log_().", "_log."),              # logger 取宿主那一个（改 logger 名 = 改落盘行为）
    ("QTimer(self.p)", "QTimer(self)"),  # Qt parent 必须是 QMainWindow（宿主），不是控制器
)


def unrewrite(s):
    """把控制器方法体逆归一回父版本口径。"""
    for new, old in REWRITES:
        s = s.replace(new, old)
    return s

# 视频状态：必须在宿主上「可解析」（实例字典赋值 / 方法 / MRO）
#   video_watching_timer 是**运行期**在控制器方法里赋到宿主身上的 → 不在静态赋值集，
#   但必须在 e2e 探针里被验证（见 ③）。
HOST_STATE_STATIC = (
    "is_watching_video", "video_start_time", "video_duration", "current_video_url",
    "video_platform", "video_title", "video_watch_history", "video_preferences",
    "max_idle_duration", "close_bilibili", "enter_sleep_mode",
)
# Qt 宿主（QMainWindow）提供的名字 —— 静态看不到，运行时才在 MRO 上
QT_HOST_ATTRS = {"move", "width", "height", "pos", "screen", "isVisible", "show"}

FAILS = []
PASSES = []


def check(name, cond, detail=""):
    if cond:
        PASSES.append(name)
        print("  PASS  %s" % name)
    else:
        FAILS.append((name, detail))
        print("  FAIL  %s   %s" % (name, detail))


def norm(s):
    """把 CRLF 归一成 LF —— 比代码内容，不比行尾风格。"""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def read_text(p):
    return io.open(p, "rb").read().decode("utf-8")


def md5(b):
    return hashlib.md5(b).hexdigest()


def cls_methods(src, cls_name):
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return {n.name: (n.lineno, n.end_lineno) for n in cls.body if isinstance(n, ast.FunctionDef)}


def seg_of(src, span):
    lines = src.split("\n")
    a, b = span
    return "\n".join(lines[a - 1:b])


def self_attrs(seg):
    """AST 级收集 `self.<attr>`（不用字符串匹配）。"""
    tree = ast.parse("if True:\n" + seg)
    out = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self"):
            out.add(node.attr)
    return out


def main():
    cur_main = read_text(MAIN_PY)
    cur_ctrl = read_text(CTRL_PY)

    print("=" * 72)
    print("W1-4 校验 A · 父版本 vs 控制器：逐字等价")
    print("=" * 72)

    r = subprocess.run(["git", "show", "HEAD:ralsei_pet/src/main.py"],
                       cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        print("  !! git show 失败:", r.stderr.decode("utf-8", "replace")[:200])
        return 2
    old_main_bytes = r.stdout

    # ① A ≠ B 硬闸
    if md5(old_main_bytes) == md5(io.open(MAIN_PY, "rb").read()):
        print("  !! A == B：父版本与当前 md5 相同 → 探针退化，终止")
        return 2
    print("  父版本 md5 %s" % md5(old_main_bytes))
    print("  当前   md5 %s" % md5(io.open(MAIN_PY, "rb").read()))
    print("  (已确认 A ≠ B —— 教训：若改动先提交，HEAD 就不再是父版本)")

    old_main = norm(old_main_bytes.decode("utf-8"))
    nm, nc = norm(cur_main), norm(cur_ctrl)
    old_m = cls_methods(old_main, "RalseiPet")
    new_m = cls_methods(nm, "RalseiPet")
    ctrl_m = cls_methods(nc, "VideoController")

    print("-" * 72)
    for name in MOVE_METHODS:
        check("逐字等价 · %-26s" % name,
              unrewrite(seg_of(nc, ctrl_m[name])) == norm(seg_of(old_main, old_m[name])),
              "起止 旧%s vs 新%s" % (old_m[name], ctrl_m[name]))
    for name in MOVE_METHODS:
        check("已从 main.py 摘除 · %s" % name, name not in new_m)

    # _log 归一：只准动 2 处，且只在 2 个方法里
    print("-" * 72)
    per = {n: seg_of(nc, ctrl_m[n]).count("_log_().") for n in MOVE_METHODS}
    per = {k: v for k, v in per.items() if v}
    check("_log_(). 只在 _react_to_video / suggest_watching_video",
          set(per) == {"_react_to_video", "suggest_watching_video"}, "实际 %r" % (per,))
    check("_log_(). 总数 == 2", sum(per.values()) == 2, "实际 %d" % sum(per.values()))
    # 控制器里裸 `_log.` 调用（排除 docstring 文本）：用 AST 找真实 Call
    tree = ast.parse(nc)
    bare_log_calls = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "_log"):
            bare_log_calls.append((node.lineno, node.func.attr))
    check("控制器里无裸 _log.<m>() 调用", not bare_log_calls, "实际 %r" % (bare_log_calls,))
    check("控制器保留模块级 _log（兜底）", "_log = logging.getLogger(__name__)" in nc)
    # 逐条核 import
    top_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_imports |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            top_imports.add((node.module or "").split(".")[0])
    # 允许集：标准库 + PyQt5（与 main.py 同款 Qt 依赖，见 QTimer/QRect 说明）。
    # **项目内模块（modules.* / logger_utils / data_store …）一个都不许有** —— 那会接回初始化环。
    PROJECT_MODS = {"modules", "logger_utils", "data_store", "text_segmenter"}
    check("控制器顶层 import 无项目内模块", not (top_imports & PROJECT_MODS),
          "实际 %r" % (sorted(top_imports & PROJECT_MODS),))
    check("控制器顶层 import 在允许集内（stdlib + PyQt5）",
          top_imports <= {"logging", "random", "time", "PyQt5", "sys"},
          "实际 %r" % (sorted(top_imports),))
    check("控制器顶层含 import random（_react_to_video 裸用）", "random" in top_imports)
    check("控制器顶层含 import time（time.xxx 裸用）", "time" in top_imports)

    # Qt 依赖：被搬方法体裸用 QTimer / QRect（main.py 靠它模块级 import 解析）
    print("-" * 72)
    ctrl_body_all = "\n".join(seg_of(nc, ctrl_m[n]) for n in MOVE_METHODS)
    for qt_name in ("QTimer", "QRect"):
        used = qt_name in ctrl_body_all
        imported = qt_name in [a.name for node in ast.walk(tree)
                               if isinstance(node, ast.ImportFrom)
                               and (node.module or "").startswith("PyQt5")
                               for a in node.names]
        check("裸用 %s → 已导入（否则 NameError）" % qt_name,
              (not used) or imported,
              "used=%s imported=%s" % (used, imported))
    check("QTimer 的 parent 显式传宿主 self.p（不是 self）",
          "QTimer(self.p)" in ctrl_body_all and "QTimer(self)" not in ctrl_body_all,
          "控制器里仍有 QTimer(self)")
    check("QTimer(self.p) 恰好 1 处",
          ctrl_body_all.count("QTimer(self.p)") == 1,
          "实际 %d" % ctrl_body_all.count("QTimer(self.p)"))

    print("=" * 72)
    print("W1-4 校验 B · 回落面：方法体用到的 self.<attr> 必须可解析")
    print("=" * 72)

    host_inst, host_methods = set(), set(new_m)
    tree_h = ast.parse(nm)
    cls = next(n for n in tree_h.body if isinstance(n, ast.ClassDef) and n.name == "RalseiPet")
    for node in ast.walk(cls):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "self" and isinstance(node.ctx, ast.Store)):
            host_inst.add(node.attr)
    # 控制器方法里赋到 self 上的名字 → 最终落在宿主实例字典（见 ③ 的说明）
    for name in MOVE_METHODS:
        for node in ast.walk(ast.parse("if True:\n" + seg_of(nc, ctrl_m[name]))):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "self" and isinstance(node.ctx, ast.Store)):
                host_inst.add(node.attr)

    ctrl_own = set(ctrl_m) | {"p", "_log_", "QTimer", "QRect", "random", "time"}
    all_attrs = set()
    for name in MOVE_METHODS:
        all_attrs |= self_attrs(seg_of(nc, ctrl_m[name]))
    unresolved = sorted(a for a in all_attrs
                        if a not in ctrl_own and a not in host_methods
                        and a not in host_inst and a not in QT_HOST_ATTRS)
    check("self.<attr> 全部可解析（宿主/控制器/Qt 基类）", not unresolved,
          "未解析 %r" % (unresolved,))

    print("-" * 72)
    for key in HOST_STATE_STATIC:
        check("宿主持有 %-22s" % key, key in host_inst or key in host_methods)
    check("video_watching_timer 由控制器方法赋到宿主（运行期）",
          "video_watching_timer" in host_inst,
          "不在宿主赋值集 → 检查 _start_video_watching_loop 是否还写 self.video_watching_timer")

    # 未搬的方法一个都不能少
    print("-" * 72)
    for key in ("close_bilibili", "enter_sleep_mode", "check_entertainment_needs"):
        check("未搬方法仍在宿主 · %s" % key, key in host_methods)

    print("=" * 72)
    print("W1-4 校验 C · 反向控制（篡改后结论必须变）")
    print("=" * 72)
    NEEDLE = "self.is_watching_video = True"
    check("① needle 命中（先证不是空替换）", old_main.count(NEEDLE) >= 1,
          "命中 %d 次" % old_main.count(NEEDLE))
    tampered = old_main.replace(NEEDLE, "self.is_watching_video = False")
    check("② 篡改确实改了文本", tampered != old_main)
    got = unrewrite(seg_of(nc, ctrl_m["start_watching_video"]))
    check("③ 篡改后逐字等价转为 FAIL",
          got != seg_of(tampered, old_m["start_watching_video"]))

    # 反向控制 2：往控制器里塞一个多余的 _log_() → 计数断言必须转为 FAIL
    #   ⚠️ 别把期望值写成字面量 3：docstring 里也含 `_log_()` 文本（讲解用），
    #   所以基线计数是 4 不是 2 —— 只有**方法体内的**计数才是 2。
    #   这里断"性质"不断"数字"：注入后**方法体计数**必须 +1。
    def body_log_count(src):
        m = cls_methods(src, "VideoController")
        return sum(seg_of(src, m[n]).count("_log_().") for n in MOVE_METHODS if n in m)

    base_cnt = body_log_count(nc)
    # ⚠️ needle 里含换行 → 必须用**归一后**的文本（LF），否则 CRLF 文件里命中 0 次
    #    （这正是"反例控制 needle 必须先断言命中"那条教训的又一个实例）。
    NEEDLE_INJ = "        self.is_watching_video = True"
    n_hit = nc.count(NEEDLE_INJ)
    check("④ 注入前 needle 命中（不是空替换）", n_hit >= 1,
          "命中 %d 次" % n_hit)
    dirty = nc.replace(NEEDLE_INJ, "        _log_().debug('x')\n" + NEEDLE_INJ, 1)
    check("⑤ 注入确实改了文本", dirty != nc)
    check("⑥ 注入后方法体内 _log_() 计数 +1",
          body_log_count(dirty) == base_cnt + 1,
          "%d → %d" % (base_cnt, body_log_count(dirty)))
    check("⑦ 注入体不被计数断言放过（原断言会 FAIL）",
          not (body_log_count(dirty) == 2))

    print()
    print("=" * 72)
    print("结果：PASS %d / FAIL %d" % (len(PASSES), len(FAILS)))
    for n, d in FAILS:
        print("  FAIL %s  %s" % (n, d))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
