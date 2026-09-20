# -*- coding: utf-8 -*-
"""W1-4 施工脚本（正式版）—— 生成 modules/video_controller.py 并改写 main.py。

设计要点
--------
* **方法体由脚本机械拼接**（不是人手抄），保证逐字；
* 模块 docstring / 类 docstring / `__init__` / `__getattr__` / `_log_` 由模板给出；
* 模板用 `<<<HEAD>>>` / `<<<TAIL>>>` 标记包在一个普通字符串里，**避开三引号嵌套问题**；
* 落盘前做等价性硬证明（逆归一逐字节比对）+ `ast.parse` 编译自检。
"""
import ast
import io
import os

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

Q3 = '"""'
NL = "\n"

TEMPLATE = (
    "# -*- coding: utf-8 -*-" + NL
    + Q3 + NL
    + "视频控制器 —— H4/H5「上帝类拆分」Wave 1 第 2 项（W1-4）。" + NL
    + NL
    + "搬出来的是什么" + NL
    + "--------------" + NL
    + "`RalseiPet` 里「陪看视频」这一条业务线的 8 个方法：" + NL
    + NL
    + "    check_video_apps            —— 主入口：识别视频窗口，50% 概率开始看" + NL
    + "    identify_video_apps         —— 窗口标题/类名白名单匹配（含 40+ 平台关键词）" + NL
    + "    start_watching_video        —— 坐到视频窗口正中、面向视频、起 5s tick" + NL
    + "    _start_video_watching_loop  —— 建 QTimer(5000ms) 并接到 _update_video_watching" + NL
    + "    _update_video_watching      —— 每 tick：深夜自动关 / 10% 概率做反应" + NL
    + "    _react_to_video             —— 8 条内置反应台词 + 上报 AI note_event" + NL
    + "    stop_watching_video         —— 结算观看时长、写历史、恢复移动" + NL
    + "    suggest_watching_video      —— 主动提议 + 50% 概率开 B站热门页" + NL
    + NL
    + "为什么是这一块（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）" + NL
    + "--------------------------------------------------------------" + NL
    + "W1-3（游戏）之后、W1-1/W1-2（施法 / 躲猫猫）之前搬它，因为它是 Wave 1 里" + NL
    + "**第二块「块内闭合」**的：全项目对这批方法的外部调用点只有 1 处" + NL
    + "（`check_entertainment_needs`，它是宿主自己的方法，走 `self.xxx()` 命中转发壳），" + NL
    + "不碰施法（W1-1）、躲猫猫（W1-2）、文件表（W1-6）的任何状态。" + NL
    + NL
    + "与本轮口径的一致性" + NL
    + "------------------" + NL
    + "* 施工口径：**只搬方法、不搬状态**。视频状态全部留在 `RalseiPet.__init__` /" + NL
    + "  `init_movement`：`is_watching_video` / `video_start_time` / `video_duration` /" + NL
    + "  `current_video_url` / `video_platform` / `video_title` / `video_watch_history` /" + NL
    + "  `video_preferences` / `video_watching_timer`。**还有 `max_idle_duration`** ——" + NL
    + "  它看着像视频参数（观看时长 10~30s 写在这里），其实是**通用空闲时长**，" + NL
    + "  ~16 处非视频代码在写它（`randomize_movement_pattern` / `update_movement` /" + NL
    + "  睡眠 3600s）。搬它 = 把游戏/睡眠一起拖进来，故**留在宿主**。" + NL
    + "* **`enter_sleep_mode` 没搬**：它是通用作息状态机（`update_movement` L1635 也在调），" + NL
    + "  只是恰好被 `_update_video_watching` 的深夜分支叫到。留在宿主。" + NL
    + "* **`close_bilibili` 没搬**：它是「按关键词关窗口」的**通用原语**，B站只是当前" + NL
    + "  唯一调用者；它跟窗口枚举/关闭那套更近 → 明确留给 W1-6（文件与窗口表）。" + NL
    + "  于是本模块的深夜分支里 `self.close_bilibili()` 仍然合法（宿主方法）。" + NL
    + "* **`check_entertainment_needs` 没搬**：它是娱乐总调度，视频只是它的一个分支，" + NL
    + "  留在宿主 —— 这正是本模块唯一的外部调用点。" + NL
    + NL
    + "为什么不 import 任何项目内模块" + NL
    + "----------------------------" + NL
    + "同 `event_speech.py` / `games_controller.py` / `lazy_log.py` 的纪律：本模块位于" + NL
    + "「初始化环」下游（`main.py` import 期就要 `from modules.video_controller import" + NL
    + "VideoController`），回头 import `logger_utils` / `dialogue_ui` 会把环重新接上。" + NL
    + NL
    + "本模块只 import 标准库：" + NL
    + "  · `random` —— `check_video_apps` / `start_watching_video` / `_update_video_watching`" + NL
    + "    / `stop_watching_video` / `suggest_watching_video` 方法体里都有 `import random`" + NL
    + "    （**方法体内的局部 import 逐字保留**，模块级这份是给 `_react_to_video` 用的 ——" + NL
    + "    它写的是 `random.choice(reactions)`，依赖模块级 import 兜底）；" + NL
    + "  · `time` —— `time.time()` / `time.strftime()` 全是**裸用**，靠模块级 import 兜底；" + NL
    + "  · `PyQt5.QtCore.QTimer` / `QRect` —— 见下面 ⚠️；" + NL
    + "  · `logging` —— 见下面 `_log_()` 的说明。" + NL
    + NL
    + "⚠️ 不要删模块级的 `import random` / `import time` / Qt 那两个名字" + NL
    + "--------------------------------------------------------------------" + NL
    + "被搬的方法体里这些名字是**裸用**（没有局部 import），全靠模块级那份。" + NL
    + "删掉 → `NameError`。这是本轮最容易埋的雷（W1-3 的 GamesController 同样靠模块级" + NL
    + "`import random/time` 兜住）。" + NL
    + NL
    + "**真踩过一次**（第一版落盘后 e2e 才炸出来，G2 完全看不见）：" + NL
    + "`start_watching_video` 用 `QRect(...)`、`_start_video_watching_loop` 用" + NL
    + "`QTimer(self)`，两者在 main.py 里能解析，是因为 **main.py 模块级**有" + NL
    + "`from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal`。" + NL
    + "控制器若不 import，就 `NameError`。所以这里必须**同款导入**：" + NL
    + "`from PyQt5.QtCore import QTimer, QRect`。" + NL
    + NL
    + "为什么现在能定位到它：`verify_w1_4_e2e.py` 真起了宿主逐条跑。静态等价断言**永远**" + NL
    + "测不出这类问题（那段源码一个字都没改，只是**换了模块的作用域**）。" + NL
    + NL
    + "⚠️⚠️ `QTimer(self)` 必须改成 `QTimer(self.p)`（本模块唯一的**语义**改动）" + NL
    + "------------------------------------------------------------------------" + NL
    + "这是「只搬方法不搬状态」在本项目遇到的**第一个真语义坑**，务必看懂再动：" + NL
    + NL
    + "main.py 里 `self.video_watching_timer = QTimer(self)` 的 `self` 是 **RalseiPet**" + NL
    + "（一个 `QMainWindow`）→ Qt 接受它做 parent，表挂在窗口身上。" + NL
    + "搬进控制器后同一个 `self` 变成 **VideoController**（一个 `object`）→" + NL
    + "`TypeError: QTimer(parent: Optional[QObject] = None): argument 1 has unexpected" + NL
    + "type 'VideoController'` —— 真机一点就炸。**逐字等价断言 100% 看不出来**：" + NL
    + "源码一字未改，改的是「这个名字指向谁」。" + NL
    + NL
    + "修法：`QTimer(self)` → `QTimer(self.p)`。语义**完全保持**（parent 仍是那个" + NL
    + "QMainWindow），只是显式写出。注意 `self.p` 在控制器里是实例字典成员，" + NL
    + "走常规查找、不触发 `__getattr__`，无递归风险。" + NL
    + NL
    + "**为什么其余 `self.xxx` 不用改**：`self.dialogue_ui` / `self.video_watching_timer`" + NL
    + "这类只是**读/写属性**，经 `__getattr__` 回落给宿主后拿到的就是宿主那一份；" + NL
    + "而 `QTimer(self)` 是把这个 `self` **当对象传出去**，回落救不了 —— 两者的区别是" + NL
    + "「取出宿主的值」vs「把控制器自己交出去」。**这条要进项目的施工口径备忘。**" + NL
    + NL
    + "`_log` 去哪儿了" + NL
    + "--------------" + NL
    + "被搬的 `_react_to_video`（原 L4767）和 `suggest_watching_video`（原 L4875）各有一行" + NL
    + NL
    + "    _log.debug(\"main 防御性异常（已忽略）: %s\", e)" + NL
    + NL
    + "施工时这 2 处被**机械改写**为 `_log_().debug(...)`（只动 `_log.` → `_log_().`），" + NL
    + "并由下面 `_log_()` 把**宿主 main.py 的同一个 logger 对象**取过来。" + NL
    + NL
    + "为什么不自己 `logging.getLogger('modules.video_controller')`" + NL
    + "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" + NL
    + "那会让这条『防御性异常』日志**换一个 logger 名** → 文件落点 / 级别 / 格式都可能变，" + NL
    + "「行为等价」就不成立。取宿主 logger 则**逐字节同一条日志**。" + NL
    + NL
    + "为什么不像 GamesController 那样直接回落 `_log`" + NL
    + "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" + NL
    + "因为回落白名单是「宿主实例字典」+「宿主类型 MRO」，而 `_log` 是 main.py 的" + NL
    + "**模块级全局**，两条都不满足。放宽回落面去够一个 logger 不划算 ——" + NL
    + "显式的 `_log_()` 更好审计。顺带一个**雷区**：类体里不能写" + NL
    + "`_log = self.p...`（类体没有 self）、也不能用 `@property`（property 对象会" + NL
    + "**挡住**模块级 `_log`，但方法体里写的是 `_log.debug`，取到 property 对象反而" + NL
    + "报 AttributeError）。正确写法就是**普通方法** `def _log_(self)`，" + NL
    + "与方法体里的 `_log_()` 正好成对。" + NL
    + Q3 + NL
    + "import logging" + NL
    + "import random" + NL
    + "import time" + NL
    + NL
    + "# ⚠️ 必须与 main.py 同款导入：被搬方法体里 `QTimer(self)`（_start_video_watching_loop）" + NL
    + "# 和 `QRect(...)`（start_watching_video）都是**裸用**，在 main.py 靠它模块级这份导入解析。" + NL
    + "# 漏了它 → NameError，且**静态逐字等价断言测不出来**（源码没改，只是换了模块作用域）。" + NL
    + "# 那是真踩过的一次：第一版落盘后 e2e 才炸出来。" + NL
    + "from PyQt5.QtCore import QTimer, QRect" + NL
    + NL
    + "_log = logging.getLogger(__name__)" + NL
    + NL
    + NL
    + "class VideoController(object):" + NL
    + "    " + Q3 + "陪看视频。宿主（`RalseiPet`）持有，方法通过宿主 `__getattr__` 转发壳暴露。" + NL
    + NL
    + "    与 `GamesController` 同构：本类**需要 `__getattr__`**，因为『只搬方法不搬状态』" + NL
    + "    意味着方法体里 `self.is_watching_video` / `self.dialogue_ui` / `self.QTimer` 这些" + NL
    + "    宿主成员一个字都没改。两种做法：(a) 全改写成 `self.p.xxx`（改动 100+ 处）；" + NL
    + "    (b) 回落给宿主（本实现，方法体逐字不变、等价性可硬证明）。选 (b)。" + NL
    + NL
    + "    与宿主 `RalseiPet.__getattr__` 的**方向正好相反**（宿主 → 控制器找方法，" + NL
    + "    控制器 → 宿主找状态），两侧都是显式白名单，构成闭合双向转发 —— 详见" + NL
    + "    `games_controller.py` 的类 docstring 与 `main.py` 的 `_CONTROLLER_ATTRS` 注释。" + NL
    + "    真机踩过的 `RecursionError`（构造期崩）也记在那里，勿回退。" + NL
    + "    " + Q3 + NL
    + NL
    + "    def __init__(self, ralsei_pet):" + NL
    + "        # 宿主引用：视频状态全在宿主身上，本类只借用，不复制、不缓存。" + NL
    + "        # 普通赋值 → `p` 进实例字典 → `self.p` 走常规查找，不会递归回 __getattr__。" + NL
    + "        self.p = ralsei_pet" + NL
    + NL
    + "    def __getattr__(self, name):" + NL
    + "        # 只在常规查找失败时进入。两条**显式白名单**后才回落：" + NL
    + "        #   · 宿主实例字典（is_watching_video / video_* / dialogue_ui / desktop_interaction…）" + NL
    + "        #   · 宿主**类型** MRO 上的东西（randomize_movement_pattern / change_animation" + NL
    + "        #     / _clamp_pos_to_desktop / QMainWindow 的 move/width/height …）" + NL
    + "        # 两条都不满足 → 抛，切断『宿主也没有 → 宿主 __getattr__ → 又转回本类』的成环路径。" + NL
    + "        pet = self.__dict__.get('p')" + NL
    + "        if pet is None:" + NL
    + "            raise AttributeError(name)" + NL
    + "        if name in pet.__dict__:" + NL
    + "            return pet.__dict__[name]" + NL
    + "        if any(name in klass.__dict__ for klass in type(pet).__mro__):" + NL
    + "            return getattr(pet, name)" + NL
    + "        raise AttributeError(name)" + NL
    + NL
    + "    def __setattr__(self, name, value):" + NL
    + "        # ⚠️ 这是本模块**第二个真语义坑**（e2e 才炸出来，静态等价看不见）。" + NL
    + "        #" + NL
    + "        #『只搬方法不搬状态』的口径要求状态留在宿主。`__getattr__` 只解决**读**：" + NL
    + "        # 控制器里 `self.is_watching_video` 读时回落给宿主。" + NL
    + "        # 但**写**不会自动回落 —— Python 的普通赋值走 `__setattr__` → 默认" + NL
    + "        # `object.__setattr__` → 直接把属性写进**控制器自己的 `__dict__`**。" + NL
    + "        # 实测（真踩）：控制器 `self.is_watching_video = True` 之后" + NL
    + "        #   host.is_watching_video == False   /   ctrl.is_watching_video == True" + NL
    + "        # → 状态被劈成两份：`check_entertainment_needs`（在宿主上读）永远看到 False，" + NL
    + "        #   于是「看完视频」这个分支永远不会触发；而 `_update_video_watching`" + NL
    + "        #   （在控制器里读）看到 True。**两边读数不一致**，行为静默错乱。" + NL
    + "        #" + NL
    + "        # 修法：把**业务属性**的赋值显式转发给宿主，只把控制器自身的私有成员" + NL
    + "        # （`p` 宿主引用）留在自己身上。" + NL
    + "        #" + NL
    + "        # 转发名单 = 宿主**已经拥有**的名字（实例字典或 MRO 上有）。这个判据的关键是" + NL
    + "        # **能自动覆盖新状态名**：以后 `RalseiPet` 再加 `video_xxx` 字段，只要它在" + NL
    + "        # `__init__` 里赋了值，写进来就会自动落到宿主 —— 不需要来改这份名单" + NL
    + "        # （这是本项目最贵的坑：'函数写对了但产品用不上'）。" + NL
    + "        # 反过来说：控制器**故意不允许**给自己新增业务属性 —— 想加状态就加到宿主上。" + NL
    + "        if name != 'p':" + NL
    + "            pet = self.__dict__.get('p')" + NL
    + "            if pet is not None:" + NL
    + "                if name in pet.__dict__ or any(" + NL
    + "                        name in klass.__dict__ for klass in type(pet).__mro__):" + NL
    + "                    setattr(pet, name, value)" + NL
    + "                    return" + NL
    + "        object.__setattr__(self, name, value)" + NL
    + NL
    + "    def _log_(self):" + NL
    + "        # 取宿主 main.py 的模块级 `_log`（同一个 logger 对象）—— 见模块 docstring。" + NL
    + "        # `_log` 不在宿主实例字典里，所以走宿主**模块**的全局变量。" + NL
    + "        import sys" + NL
    + "        mod = sys.modules.get(type(self.p).__module__)" + NL
    + "        if mod is not None:" + NL
    + "            lg = getattr(mod, '_log', None)" + NL
    + "            if lg is not None:" + NL
    + "                return lg" + NL
    + "        return _log" + NL
    + NL
    + "    # ------------------------------------------------------------------" + NL
    + "    # 视频业务（W1-4 搬运区，**以下方法体逐字来自 main.py**）" + NL
    + "    # ------------------------------------------------------------------" + NL
    + NL
    + NL
)


def main():
    raw = io.open(MAIN_PY, "rb").read()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "main.py 换行不统一（非纯 CRLF）"
    src = raw.decode("utf-8")
    # split('\n') → 每行末尾带 '\r'（除最后一行）。搬运时逐字带 '\r'，
    # 控制器文件写回时也统一 CRLF，保证两边可逐字节比对。
    lines = src.split(NL)
    tree = ast.parse(src)

    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RalseiPet")

    found = {}
    for node in klass.body:
        if isinstance(node, ast.FunctionDef) and node.name in MOVE_METHODS:
            found[node.name] = (node.lineno, node.end_lineno)
    assert len(found) == len(MOVE_METHODS), "缺方法: %r" % ([n for n in MOVE_METHODS if n not in found],)

    spans = sorted((found[n][0], found[n][1], n) for n in MOVE_METHODS)
    for i in range(1, len(spans)):
        assert spans[i][0] > spans[i - 1][1], "区间重叠"

    # --- 方法体逐字取出（含行尾 \r），并把 _log. 机械改写为 _log_(). ---
    # 两处**唯一允许的改写**（都有硬证明，见下方逆归一断言）：
    #   ① `_log.` → `_log_().`        —— logger 必须取宿主那一个（换 logger 名会改落盘行为）
    #   ② `QTimer(self)` → `QTimer(self.p)` —— Qt parent 必须是 QMainWindow（宿主），
    #      不是 VideoController（plain object）。**这是语义改动，不是等价变换** ——
    #      所以必须在 e2e 里真跑一遍 `start_watching_video` 才算证毕。
    REWRITES = (
        ("_log.", "_log_().", 2),                    # 期望命中 2 处
        ("QTimer(self)", "QTimer(self.p)", 1),       # 期望命中 1 处
    )
    bodies = {}
    for a, b, name in spans:
        seg = NL.join(lines[a - 1:b])
        assert seg.startswith("    def %s(" % name), "切片起点不对: %r" % seg[:60]
        bodies[name] = seg
    hit_report = []
    for old, new, expect in REWRITES:
        got = sum(bodies[n].count(old) for n in bodies)
        assert got == expect, "改写 %r 期望命中 %d 处，实际 %d 处" % (old, expect, got)
        for n in bodies:
            bodies[n] = bodies[n].replace(old, new)
        hit_report.append((old, new, got))

    # --- 逆归一断言：把改写整体逆回去，必须与原文逐字节相同 ---
    for a, b, name in spans:
        orig = NL.join(lines[a - 1:b])
        back = bodies[name]
        for old, new, _ in REWRITES:
            back = back.replace(new, old)
        assert back == orig, "%s 逆归一回不去（改写不止这两类？）" % name

    # --- 组装控制器文件 ---
    body_text = (NL + NL).join(bodies[name] for _, _, name in spans)
    ctrl_src = TEMPLATE + body_text + NL
    # 控制器文件统一 CRLF
    ctrl_out = ctrl_src.replace("\r\n", NL).replace(NL, "\r\n").encode("utf-8")
    ast.parse(ctrl_out.decode("utf-8"))   # 编译自检

    # --- 改写 main.py ---
    # 删除区间：每个方法连同其**后面那一行类内空行**一起删（避免留双空行）。
    # 用倒序删，避免下标漂移。
    new_lines = list(lines)
    for a, b, name in sorted(spans, reverse=True):
        assert new_lines[b].strip() == "", "预期 %d 行是类内空行，实际 %r" % (b + 1, new_lines[b])
        del new_lines[a - 1:b + 1]
    new_src = NL.join(new_lines)

    # 三处定点插桩
    anchor_imp = "from modules.games_controller import GamesController"
    assert new_src.count(anchor_imp) == 1, "import 锚点命中 %d 次" % new_src.count(anchor_imp)
    new_src = new_src.replace(
        anchor_imp,
        anchor_imp + NL + "from modules.video_controller import VideoController",
    )

    anchor_mount = "        self.games = GamesController(self)"
    assert new_src.count(anchor_mount) == 1, "挂载锚点命中 %d 次" % new_src.count(anchor_mount)
    new_src = new_src.replace(
        anchor_mount,
        anchor_mount + NL
        + "        # 视频控制器（W1-4）：持有「陪看视频」这条业务线的 8 个方法。" + NL
        + "        # 时机同 games —— 在 init_systems 内、晚于 dialogue_ui / desktop_interaction。" + NL
        + "        self.video = VideoController(self)",
    )

    anchor_attrs = "    _CONTROLLER_ATTRS = ('games',)"
    assert new_src.count(anchor_attrs) == 1, "转发名单锚点命中 %d 次" % new_src.count(anchor_attrs)
    new_src = new_src.replace(
        anchor_attrs,
        "    #   · 'games'  → GamesController（W1-3）" + NL
        + "    #   · 'video'  → VideoController（W1-4）" + NL
        + "    _CONTROLLER_ATTRS = ('games', 'video')",
    )

    # (4) 把 `video_watching_timer` 预声明到宿主状态里。
    #     为什么必须加这一行（**第三个真语义坑**）：控制器新引入的
    #     `__setattr__` 只在"宿主**已经拥有**这个名字"时才把赋值转给宿主。
    #     `video_watching_timer` 是**控制器首次创建**的属性 —— 宿主 `__init__` 里
    #     从没赋过它，于是第一次 `self.video_watching_timer = QTimer(self.p)` 会
    #     落在**控制器**的实例字典上（状态再次被劈开），而 `_update_video_watching`
    #     在控制器里能读到、宿主侧却看不到。
    #     修法：在宿主的视频状态块里预声明为 None → 之后所有赋值都正确落到宿主。
    #     （这与"状态留在宿主"的口径一致：timer 本来就是这个宿主窗口的子对象。）
    anchor_video_state = '        self.video_watch_history = []  # 视频观看历史'
    assert new_src.count(anchor_video_state) == 1, "视频状态锚点命中 %d 次" % new_src.count(anchor_video_state)
    new_src = new_src.replace(
        anchor_video_state,
        anchor_video_state + NL
        + "        # 观看循环定时器（W1-4）：由 VideoController._start_video_watching_loop 创建。" + NL
        + "        # 在这里**预声明为 None** 是必须的 —— 控制器的 __setattr__ 只把赋值转发给" + NL
        + "        # 宿主「已经拥有」的名字；不预声明的话这个属性会落在控制器上，状态被劈成两份。" + NL
        + "        self.video_watching_timer = None",
    )

    ast.parse(new_src)   # 编译自检

    # --- 落盘 ---
    io.open(CTRL_PY, "wb").write(ctrl_out)
    io.open(MAIN_PY, "wb").write(new_src.encode("utf-8"))

    print("=== W1-4 落盘完成 ===")
    for old, new, n in hit_report:
        print("  改写 %-18s → %-22s 命中 %d 处" % (old, new, n))
    print("  main.py              %d 行 -> %d 行  (删 %d)" % (
        len(lines), len(new_src.split(NL)), len(lines) - len(new_src.split(NL))))
    print("  video_controller.py  %d 行" % len(ctrl_out.decode("utf-8").split(NL)))
    print("  搬运方法 %d 个 / 方法体 %d 行" % (len(spans), sum(b - a + 1 for a, b, _ in spans)))
    for a, b, name in spans:
        print("    %-28s 原 %5d-%5d  (%d 行)" % (name, a, b, b - a + 1))


if __name__ == "__main__":
    main()
