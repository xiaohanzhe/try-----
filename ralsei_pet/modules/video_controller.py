# -*- coding: utf-8 -*-
"""
视频控制器 —— H4/H5「上帝类拆分」Wave 1 第 2 项（W1-4）。

搬出来的是什么
--------------
`RalseiPet` 里「陪看视频」这一条业务线的 8 个方法：

    check_video_apps            —— 主入口：识别视频窗口，50% 概率开始看
    identify_video_apps         —— 窗口标题/类名白名单匹配（含 40+ 平台关键词）
    start_watching_video        —— 坐到视频窗口正中、面向视频、起 5s tick
    _start_video_watching_loop  —— 建 QTimer(5000ms) 并接到 _update_video_watching
    _update_video_watching      —— 每 tick：深夜自动关 / 10% 概率做反应
    _react_to_video             —— 8 条内置反应台词 + 上报 AI note_event
    stop_watching_video         —— 结算观看时长、写历史、恢复移动
    suggest_watching_video      —— 主动提议 + 50% 概率开 B站热门页

为什么是这一块（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）
--------------------------------------------------------------
W1-3（游戏）之后、W1-1/W1-2（施法 / 躲猫猫）之前搬它，因为它是 Wave 1 里
**第二块「块内闭合」**的：全项目对这批方法的外部调用点只有 1 处
（`check_entertainment_needs`，它是宿主自己的方法，走 `self.xxx()` 命中转发壳），
不碰施法（W1-1）、躲猫猫（W1-2）、文件表（W1-6）的任何状态。

与本轮口径的一致性
------------------
* 施工口径：**只搬方法、不搬状态**。视频状态全部留在 `RalseiPet.__init__` /
  `init_movement`：`is_watching_video` / `video_start_time` / `video_duration` /
  `current_video_url` / `video_platform` / `video_title` / `video_watch_history` /
  `video_preferences` / `video_watching_timer`。**还有 `max_idle_duration`** ——
  它看着像视频参数（观看时长 10~30s 写在这里），其实是**通用空闲时长**，
  ~16 处非视频代码在写它（`randomize_movement_pattern` / `update_movement` /
  睡眠 3600s）。搬它 = 把游戏/睡眠一起拖进来，故**留在宿主**。
* **`enter_sleep_mode` 没搬**：它是通用作息状态机（`update_movement` L1635 也在调），
  只是恰好被 `_update_video_watching` 的深夜分支叫到。留在宿主。
* **`close_bilibili` 没搬**：它是「按关键词关窗口」的**通用原语**，B站只是当前
  唯一调用者；它跟窗口枚举/关闭那套更近 → 明确留给 W1-6（文件与窗口表）。
  于是本模块的深夜分支里 `self.close_bilibili()` 仍然合法（宿主方法）。
* **`check_entertainment_needs` 没搬**：它是娱乐总调度，视频只是它的一个分支，
  留在宿主 —— 这正是本模块唯一的外部调用点。

为什么不 import 任何项目内模块
----------------------------
同 `event_speech.py` / `games_controller.py` / `lazy_log.py` 的纪律：本模块位于
「初始化环」下游（`main.py` import 期就要 `from modules.video_controller import
VideoController`），回头 import `logger_utils` / `dialogue_ui` 会把环重新接上。

本模块只 import 标准库：
  · `random` —— `check_video_apps` / `start_watching_video` / `_update_video_watching`
    / `stop_watching_video` / `suggest_watching_video` 方法体里都有 `import random`
    （**方法体内的局部 import 逐字保留**，模块级这份是给 `_react_to_video` 用的 ——
    它写的是 `random.choice(reactions)`，依赖模块级 import 兜底）；
  · `time` —— `time.time()` / `time.strftime()` 全是**裸用**，靠模块级 import 兜底；
  · `PyQt5.QtCore.QTimer` / `QRect` —— 见下面 ⚠️；
  · `logging` —— 见下面 `_log_()` 的说明。

⚠️ 不要删模块级的 `import random` / `import time` / Qt 那两个名字
--------------------------------------------------------------------
被搬的方法体里这些名字是**裸用**（没有局部 import），全靠模块级那份。
删掉 → `NameError`。这是本轮最容易埋的雷（W1-3 的 GamesController 同样靠模块级
`import random/time` 兜住）。

**真踩过一次**（第一版落盘后 e2e 才炸出来，G2 完全看不见）：
`start_watching_video` 用 `QRect(...)`、`_start_video_watching_loop` 用
`QTimer(self)`，两者在 main.py 里能解析，是因为 **main.py 模块级**有
`from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal`。
控制器若不 import，就 `NameError`。所以这里必须**同款导入**：
`from PyQt5.QtCore import QTimer, QRect`。

为什么现在能定位到它：`verify_w1_4_e2e.py` 真起了宿主逐条跑。静态等价断言**永远**
测不出这类问题（那段源码一个字都没改，只是**换了模块的作用域**）。

⚠️⚠️ `QTimer(self)` 必须改成 `QTimer(self.p)`（本模块唯一的**语义**改动）
------------------------------------------------------------------------
这是「只搬方法不搬状态」在本项目遇到的**第一个真语义坑**，务必看懂再动：

main.py 里 `self.video_watching_timer = QTimer(self)` 的 `self` 是 **RalseiPet**
（一个 `QMainWindow`）→ Qt 接受它做 parent，表挂在窗口身上。
搬进控制器后同一个 `self` 变成 **VideoController**（一个 `object`）→
`TypeError: QTimer(parent: Optional[QObject] = None): argument 1 has unexpected
type 'VideoController'` —— 真机一点就炸。**逐字等价断言 100% 看不出来**：
源码一字未改，改的是「这个名字指向谁」。

修法：`QTimer(self)` → `QTimer(self.p)`。语义**完全保持**（parent 仍是那个
QMainWindow），只是显式写出。注意 `self.p` 在控制器里是实例字典成员，
走常规查找、不触发 `__getattr__`，无递归风险。

**为什么其余 `self.xxx` 不用改**：`self.dialogue_ui` / `self.video_watching_timer`
这类只是**读/写属性**，经 `__getattr__` 回落给宿主后拿到的就是宿主那一份；
而 `QTimer(self)` 是把这个 `self` **当对象传出去**，回落救不了 —— 两者的区别是
「取出宿主的值」vs「把控制器自己交出去」。**这条要进项目的施工口径备忘。**

`_log` 去哪儿了
--------------
被搬的 `_react_to_video`（原 L4767）和 `suggest_watching_video`（原 L4875）各有一行

    _log.debug("main 防御性异常（已忽略）: %s", e)

施工时这 2 处被**机械改写**为 `_log_().debug(...)`（只动 `_log.` → `_log_().`），
并由下面 `_log_()` 把**宿主 main.py 的同一个 logger 对象**取过来。

为什么不自己 `logging.getLogger('modules.video_controller')`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
那会让这条『防御性异常』日志**换一个 logger 名** → 文件落点 / 级别 / 格式都可能变，
「行为等价」就不成立。取宿主 logger 则**逐字节同一条日志**。

为什么不像 GamesController 那样直接回落 `_log`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
因为回落白名单是「宿主实例字典」+「宿主类型 MRO」，而 `_log` 是 main.py 的
**模块级全局**，两条都不满足。放宽回落面去够一个 logger 不划算 ——
显式的 `_log_()` 更好审计。顺带一个**雷区**：类体里不能写
`_log = self.p...`（类体没有 self）、也不能用 `@property`（property 对象会
**挡住**模块级 `_log`，但方法体里写的是 `_log.debug`，取到 property 对象反而
报 AttributeError）。正确写法就是**普通方法** `def _log_(self)`，
与方法体里的 `_log_()` 正好成对。
"""
import logging
import random
import time

# ⚠️ 必须与 main.py 同款导入：被搬方法体里 `QTimer(self)`（_start_video_watching_loop）
# 和 `QRect(...)`（start_watching_video）都是**裸用**，在 main.py 靠它模块级这份导入解析。
# 漏了它 → NameError，且**静态逐字等价断言测不出来**（源码没改，只是换了模块作用域）。
# 那是真踩过的一次：第一版落盘后 e2e 才炸出来。
from PyQt5.QtCore import QTimer, QRect

_log = logging.getLogger(__name__)


class VideoController(object):
    """陪看视频。宿主（`RalseiPet`）持有，方法通过宿主 `__getattr__` 转发壳暴露。

    与 `GamesController` 同构：本类**需要 `__getattr__`**，因为『只搬方法不搬状态』
    意味着方法体里 `self.is_watching_video` / `self.dialogue_ui` / `self.QTimer` 这些
    宿主成员一个字都没改。两种做法：(a) 全改写成 `self.p.xxx`（改动 100+ 处）；
    (b) 回落给宿主（本实现，方法体逐字不变、等价性可硬证明）。选 (b)。

    与宿主 `RalseiPet.__getattr__` 的**方向正好相反**（宿主 → 控制器找方法，
    控制器 → 宿主找状态），两侧都是显式白名单，构成闭合双向转发 —— 详见
    `games_controller.py` 的类 docstring 与 `main.py` 的 `_CONTROLLER_ATTRS` 注释。
    真机踩过的 `RecursionError`（构造期崩）也记在那里，勿回退。
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：视频状态全在宿主身上，本类只借用，不复制、不缓存。
        # 普通赋值 → `p` 进实例字典 → `self.p` 走常规查找，不会递归回 __getattr__。
        self.p = ralsei_pet

    def __getattr__(self, name):
        # 只在常规查找失败时进入。两条**显式白名单**后才回落：
        #   · 宿主实例字典（is_watching_video / video_* / dialogue_ui / desktop_interaction…）
        #   · 宿主**类型** MRO 上的东西（randomize_movement_pattern / change_animation
        #     / _clamp_pos_to_desktop / QMainWindow 的 move/width/height …）
        # 两条都不满足 → 抛，切断『宿主也没有 → 宿主 __getattr__ → 又转回本类』的成环路径。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        if name in pet.__dict__:
            return pet.__dict__[name]
        if any(name in klass.__dict__ for klass in type(pet).__mro__):
            return getattr(pet, name)
        # 第 3 条白名单：**兄弟控制器**（W1-2 施工中 e2e 抓到的真 P0）。
        # 控制器 A 调 `self.<B 的方法>` 时，B 的方法是 **B 的类属性** ——
        # 既不在宿主实例字典、也不在宿主类型 MRO → 前两条都不命中 → AttributeError。
        # 实例：`_hide_end_game` 调 `self._cast_spell_then`（属 SpellFlowController）。
        # 修法：复刻宿主的 `_CONTROLLER_ATTRS` 扫描，**跳过自己**；
        # 只看对方**类**上的名字（不触发对方实例的 __getattr__）→ 不成环。
        for _attr in getattr(type(pet), '_CONTROLLER_ATTRS', ()):
            _ctrl = pet.__dict__.get(_attr)
            if _ctrl is None or _ctrl is self:
                continue
            if getattr(type(_ctrl), name, None) is not None:
                return getattr(_ctrl, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # ⚠️ 这是本模块**第二个真语义坑**（e2e 才炸出来，静态等价看不见）。
        #
        #『只搬方法不搬状态』的口径要求状态留在宿主。`__getattr__` 只解决**读**：
        # 控制器里 `self.is_watching_video` 读时回落给宿主。
        # 但**写**不会自动回落 —— Python 的普通赋值走 `__setattr__` → 默认
        # `object.__setattr__` → 直接把属性写进**控制器自己的 `__dict__`**。
        # 实测（真踩）：控制器 `self.is_watching_video = True` 之后
        #   host.is_watching_video == False   /   ctrl.is_watching_video == True
        # → 状态被劈成两份：`check_entertainment_needs`（在宿主上读）永远看到 False，
        #   于是「看完视频」这个分支永远不会触发；而 `_update_video_watching`
        #   （在控制器里读）看到 True。**两边读数不一致**，行为静默错乱。
        #
        # 修法：把**业务属性**的赋值显式转发给宿主，只把控制器自身的私有成员
        # （`p` 宿主引用）留在自己身上。
        #
        # 转发名单 = 宿主**已经拥有**的名字（实例字典或 MRO 上有）。这个判据的关键是
        # **能自动覆盖新状态名**：以后 `RalseiPet` 再加 `video_xxx` 字段，只要它在
        # `__init__` 里赋了值，写进来就会自动落到宿主 —— 不需要来改这份名单
        # （这是本项目最贵的坑：'函数写对了但产品用不上'）。
        # 反过来说：控制器**故意不允许**给自己新增业务属性 —— 想加状态就加到宿主上。
        if name != 'p':
            pet = self.__dict__.get('p')
            if pet is not None:
                if name in pet.__dict__ or any(
                        name in klass.__dict__ for klass in type(pet).__mro__):
                    setattr(pet, name, value)
                    return
        object.__setattr__(self, name, value)

    def _log_(self):
        # 取宿主 main.py 的模块级 `_log`（同一个 logger 对象）—— 见模块 docstring。
        # `_log` 不在宿主实例字典里，所以走宿主**模块**的全局变量。
        import sys
        mod = sys.modules.get(type(self.p).__module__)
        if mod is not None:
            lg = getattr(mod, '_log', None)
            if lg is not None:
                return lg
        return _log

    # ------------------------------------------------------------------
    # 视频业务（W1-4 搬运区，**以下方法体逐字来自 main.py**）
    # ------------------------------------------------------------------


    def check_video_apps(self):
        # 检查视频应用并做出反应
        import random
        
        # 识别视频应用窗口
        video_apps = self.identify_video_apps()
        
        if video_apps:
            # 随机选择一个视频应用窗口
            target_video = random.choice(video_apps)
            
            # 有一定概率观看视频
            if random.random() < 0.5:  # 50%的概率
                self.start_watching_video(target_video)
        else:
            # 没有视频应用，有一定概率主动打开视频
            if random.random() < 0.3:  # 30%的概率
                self.suggest_watching_video()

    def identify_video_apps(self):
        # 识别视频相关应用窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        video_apps = []
        
        # 视频应用关键词，包含更多视频平台和应用
        video_keywords = [
            "YouTube", "哔哩哔哩", "B站", "腾讯视频", "爱奇艺", "优酷", 
            "芒果TV", "Netflix", "抖音", "快手", "视频", "腾讯视频", 
            "搜狐视频", "乐视视频", "PP视频", "风行视频", "西瓜视频", 
            "好看视频", "全民小视频", "梨视频", "土豆视频", "AcFun", 
            "A站", "斗鱼", "虎牙", "哔哩哔哩直播", "花椒直播", 
            "映客直播", "YY直播", "熊猫直播", "龙珠直播", "企鹅电竞",
            "Twitch", "Disney+", "HBO Max", "Prime Video", "Hulu",
            "Vimeo", "TikTok", "Snapchat", "Instagram", "Facebook Watch"
        ]
        
        for window in windows:
            # 检查窗口标题是否包含视频关键词
            if any(keyword in window['title'] for keyword in video_keywords):
                video_apps.append(window)
            # 检查窗口类名，识别常见视频播放器
            elif 'class_name' in window and window['class_name']:
                player_class_names = [
                    "WMPlayerApp", "VLC media player", "mpv", "PotPlayer", 
                    "QQPlayer", "KMPlayer", "GOM Player", "MediaPlayerClassic",
                    "MPV", "SMPlayer", "MPlayer", "Totem", "XBMC", "Kodi"
                ]
                if any(class_name in window['class_name'] for class_name in player_class_names):
                    video_apps.append(window)
        
        return video_apps

    def start_watching_video(self, video_app):
        # 开始观看视频
        import random
        
        self.is_watching_video = True
        self.video_start_time = time.time()
        self.video_platform = video_app['title']
        
        # 随机选择视频类型
        video_types = self.video_preferences.copy()
        video_type = random.choice(video_types)
        
        # 生成视频标题
        self.video_title = f"{video_type}相关视频"
        
        # 添加到观看历史
        self.video_watch_history.append({
            "title": self.video_title,
            "platform": self.video_platform,
            "start_time": self.video_start_time,
            "duration": 0
        })
        
        # 限制历史记录数量
        if len(self.video_watch_history) > 20:
            self.video_watch_history.pop(0)
        
        # 显示观看视频的消息
        watch_messages = [
            f"哇！我正在观看{self.video_platform}上的{self.video_title}，看起来很有趣呢！",
            f"这个{video_type}视频太吸引人了！我要仔细看看。",
            f"{self.video_platform}上的视频真好看，我沉浸进去了！",
            f"这个{video_type}内容真不错，我要继续观看。"
        ]
        message = random.choice(watch_messages)
        self.dialogue_ui.add_dialogue("ralsei", message, "happy")
        self.dialogue_ui.show_dialogue()
        
        # 确保Ralsei在视频窗口上，正面对着视频
        video_rect = QRect(video_app['x'], video_app['y'], video_app['width'], video_app['height'])
        
        # 计算视频窗口中心位置，让Ralsei面向视频
        video_center_x = video_app['x'] + video_app['width'] // 2
        video_center_y = video_app['y'] + video_app['height'] // 2
        
        # 调整Ralsei位置到视频窗口内，确保正对着视频中心
        # 确保Ralsei在视频窗口内，而不是在窗口下方
        ralsei_x = video_center_x - self.width() // 2
        ralsei_y = video_center_y - self.height() // 2
        
        # 确保Ralsei在视频窗口范围内，距离边缘至少20像素
        ralsei_x = max(video_rect.left() + 20, min(video_rect.right() - self.width() - 20, ralsei_x))
        ralsei_y = max(video_rect.top() + 20, min(video_rect.bottom() - self.height() - 20, ralsei_y))
        
        # 确保Ralsei位置在屏幕范围内（多显示器虚拟桌面夹紧）
        ralsei_x, ralsei_y = self._clamp_pos_to_desktop(ralsei_x, ralsei_y)
        
        # 移动Ralsei到视频窗口内
        self.move(ralsei_x, ralsei_y)
        
        # 更新当前窗口信息，确保Ralsei在视频窗口上
        self.current_window = video_app
        self.last_window_rect = (video_app['x'], video_app['y'], video_app['width'], video_app['height'])
        self.window_level = video_app['z_order']
        
        # 暂停移动，专注观看视频
        self.is_moving = False
        self.idle_timer = 0
        self.max_idle_duration = random.uniform(10, 30)  # 观看时间10-30秒，减少观看时间，让Ralsei能继续移动
        
        # 确保Ralsei正对着视频 - 根据视频中心位置计算方向
        # 获取Ralsei中心位置
        ralsei_center_x = ralsei_x + self.width() // 2
        ralsei_center_y = ralsei_y + self.height() // 2
        
        # 计算方向向量
        dx = video_center_x - ralsei_center_x
        dy = video_center_y - ralsei_center_y
        
        # 根据方向向量确定面向
        if abs(dx) > abs(dy):
            # 水平方向为主
            if dx > 0:
                self.current_direction = "right"  # 向右面对视频
            else:
                self.current_direction = "left"   # 向左面对视频
        else:
            # 垂直方向为主
            if dy > 0:
                self.current_direction = "down"   # 向下面对视频
            else:
                self.current_direction = "up"     # 向上面对视频
        
        # 更新动画为观看动画，使用合适的动画
        self.change_animation(f"idle", force=True)  # 使用idle动画作为观看动画
        
        # 检查是否是B站窗口，如果是，移动并调整大小
        if "哔哩哔哩" in video_app['title'] or "bilibili" in video_app['title'] or "B站" in video_app['title']:
            self.desktop_interaction.move_and_resize_bilibili_window()
        
        # 开始真正观看视频
        self._start_video_watching_loop()

    def _start_video_watching_loop(self):
        # 视频观看循环，模拟真正观看视频的行为
        self.video_watching_timer = QTimer(self.p)
        self.video_watching_timer.timeout.connect(self._update_video_watching)
        self.video_watching_timer.start(5000)  # 每5秒更新一次观看状态

    def _update_video_watching(self):
        # 更新视频观看状态
        if not self.is_watching_video:
            self.video_watching_timer.stop()
            return
        
        # 检查当前时间，最多晚上12:00必须关闭
        # 修复：原条件 (hour>=23 and minute>=55) 只在 23:55-23:59 为真，
        # 跨过午夜后 hour==0 永不满足，"深夜自动关闭"失效。23 点后或凌晨 6 点前都视为深夜。
        current_hour = int(time.strftime("%H"))
        current_minute = int(time.strftime("%M"))
        if current_hour >= 23 or current_hour < 6:
            # 快到12点了，准备关闭
            self.dialogue_ui.add_dialogue("ralsei", "时间不早了，我该睡觉了，晚安！", "tired")
            self.dialogue_ui.show_dialogue()
            self.stop_watching_video()
            self.close_bilibili()
            self.enter_sleep_mode()
            return
        
        # 随机做出一些观看反应
        import random
        if random.random() < 0.1:  # 10%的概率做出反应
            self._react_to_video()

    def _react_to_video(self):
        """陪看视频时的反应。**只上报事件，不说话**。

        ★★ 第51轮：**删除内置台词表**（用户口径逐字：「把他内置的对话去掉！！！！
        ……记住，**聊天系统全权由7B接管**，别放内置对话了，太木讷了」）。

        原实现是第八轮遗留：随机抽 8 条罐头台词
        （"haha！这个好好笑！" "哇！这个太厉害了！" …）直接 `add_dialogue` 显示 ——
        正是本文件下一行那条 `#15 对话全 AI 接管` TODO 点名的缺陷：
        **同一段对话里既有 AI 生成的句子、又有固定罐头**，用户根本分不清哪句是
        模型说的，观感就是"木讷"。

        现在只做两件**非对话**的事：
          · 记一次情绪（陪看视频确实让 Ralsei 开心 —— 这是状态，不是台词）；
          · 把"我在陪看视频"上报给 AI，**由 AI 决定说不说、说什么、做不做动作**。
        AI 未启用 / 不回应 ⇒ **安静陪着看**（与第八轮「特殊动画只交给 AI 判断」、
        以及 main.py「AI 不可用就沉默，绝不回落内置台词」是同一条纪律）。
        """
        emotion = 'happy'
        try:
            self.emotion_system.add_emotion(emotion, 10)
        except Exception as e:
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        try:
            _driver = getattr(self, 'ai_driver', None)
            if _driver is not None and callable(getattr(_driver, 'note_event', None)):
                _driver.note_event("我正在陪主人一起看视频", emotion)
        except Exception as e:
            self._log_().debug("main 防御性异常（已忽略）: %s", e)

    def stop_watching_video(self):
        # 停止观看视频
        if self.is_watching_video:
            self.is_watching_video = False
            duration = time.time() - self.video_start_time
            
            # 更新观看历史
            if self.video_watch_history and self.video_watch_history[-1]['title'] == self.video_title:
                self.video_watch_history[-1]['duration'] = duration
            
            # 显示停止观看的消息
            stop_messages = [
                "这个视频看完了，我要继续活动活动！",
                "视频结束了，我该做些其他事情了。",
                "哇，那个视频真好看！不过我该继续移动了。",
                "视频很有趣，但我需要休息一下眼睛了。"
            ]
            import random
            message = random.choice(stop_messages)
            self.dialogue_ui.add_dialogue("ralsei", message, "content")
            self.dialogue_ui.show_dialogue()
            
            # 恢复正常移动
            self.randomize_movement_pattern()
            self.is_moving = True
            # 使用随机化的最大空闲时间，而不是未定义的base_max_idle_duration
            self.max_idle_duration = random.uniform(0.5, 3.0)
            
            # 停止视频观看循环
            # 判据与 _start_video_watching_loop 里的 `if timer is not None:` 保持同一套：
            # 该属性已在宿主 init_systems 区**显式预声明为 None**（见 main.py
            # 「观看循环定时器（W1-4）」注释），所以「非 None」才是"定时器已建"的真判据。
            # 不用 hasattr —— 它只测名字存在、且遇描述符/属性会触发副作用。
            if getattr(self, 'video_watching_timer', None) is not None:
                self.video_watching_timer.stop()

    def suggest_watching_video(self):
        # 建议观看视频，只使用B站
        import random
        
        # 随机选择视频类型
        video_types = self.video_preferences.copy()
        video_type = random.choice(video_types)
        
        # 固定使用B站
        platform = "哔哩哔哩"
        
        # 显示建议消息
        suggestion_messages = [
            f"我想看点{video_type}视频，要不要一起看？",
            f"最近听说{platform}上有很好看的{video_type}视频，我想去看看！",
            f"无聊了，要不要打开{platform}看些{video_type}内容？",
            f"我想放松一下，看个{video_type}视频怎么样？"
        ]
        message = random.choice(suggestion_messages)
        self.dialogue_ui.add_dialogue("ralsei", message, "excited")
        self.dialogue_ui.show_dialogue()
        
        # 有一定概率直接打开视频
        if random.random() < 0.5:
            # 直接打开B站热门视频页面，在新窗口打开
            self.desktop_interaction.open_browser(f"https://www.bilibili.com/v/popular/all", new_window=True)
            # 打开视频后，移动并调整B站窗口大小
            self.desktop_interaction.move_and_resize_bilibili_window()
            # 设置为正在观看视频状态
            # 修复：此前只设 is_watching_video/video_start_time，未设 video_title、未启动
            # 观看定时器、未设 max_idle_duration → check_entertainment_needs 用残留旧值
            # （可能仅 0.5~3 秒）几秒内就判定"看完了"关掉视频，观看历史也因 video_title=="" 丢失。
            self.is_watching_video = True
            self.video_start_time = time.time()
            self.video_title = "B站热门视频"
            self.video_platform = platform
            # 观看时长：30~90 秒后再自然结束
            self.max_idle_duration = random.uniform(30.0, 90.0)
            # 启动 5 秒 tick 的观看循环（深夜自动关闭 / 随机反应）
            try:
                if not hasattr(self, 'video_watching_timer') or self.video_watching_timer is None:
                    self._start_video_watching_loop()
                elif not self.video_watching_timer.isActive():
                    self.video_watching_timer.start(5000)
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
