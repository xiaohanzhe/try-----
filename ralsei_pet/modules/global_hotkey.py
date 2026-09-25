# -*- coding: utf-8 -*-
"""全局热键 —— 让「S 键」在**桌面任何时刻**都能开菜单（不必先点中宠物）。

为什么需要这个模块
------------------
本项目此前**没有任何键盘入口**（全仓库只有 `dialogue_ui` 为输入框吞了几个键）。
而用户口径是「游戏里的背包这类的通过 S 键实现的菜单也要应用」——
桌宠最常见的用法是"用户正在别的窗口里干活，随手按一下"，所以**必须**是全局热键，
只在"宠物窗口有焦点时"响应等于没做。

实现路线（不引入新依赖）
------------------------
`ctypes` 调 `user32.RegisterHotKey` + `QtCore.QAbstractNativeEventFilter` 收 `WM_HOTKEY`。
两条都是现成的（ctypes 是标准库，native event filter 是 PyQt5 自带），
因此**不需要** pywin32 —— 虽然仓库里已有 pywin32（`desktop_interaction` 在用），
但热键这条路径用纯 ctypes 更短、更少假设。

降级纪律（重要）
----------------
注册失败**必须**如实返回 False 并记日志，**不许**假装成功：
一个"按了没反应"的 S 键比"明确告诉你没装上"更难排查。
调用方拿到 False 后应回落到窗口级 `keyPressEvent`（至少窗口有焦点时能用）。

线程：`RegisterHotKey` 绑在**创建它的线程**的消息队列上。Qt 里就是主线程，
本模块只准在主线程用（`install()` 里显式检查）。
"""
import ctypes
import ctypes.wintypes as wintypes
import logging

_log = logging.getLogger(__name__)

# ---- Win32 常量 -----------------------------------------------------------
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000          # Win7+：长按不重复触发（否则会疯狂开合菜单）

WM_HOTKEY = 0x0312

#: ★★ 为什么**不能**把裸字母 `S` 注册成全局热键
#: `RegisterHotKey` 不带修饰键时是**系统级抢占**：注册了裸 `S`，用户在任何程序里
#: （写文档、敲代码、聊天）都打不出那个字母 —— 这是伤人而不自知的改动。
#: ⇒ 本产品的两档方案：
#:   1. **裸 `S`**：只在宠物窗口有焦点时生效（`keyPressEvent`），忠于"游戏里按 S"的手感；
#:   2. **`Ctrl+Alt+S`**：全局热键，任何程序前台都能开菜单（不劫持任何常用输入）。
#: `Ctrl+Alt+S` 选它的理由：它同时被"另存为"家族（Ctrl+Shift+S）与输入法切换让开了，
#: 实测在本机 `RegisterHotKey` 成功（见回归套件的"真实注册"用例）。
HOTKEY_DEFAULT_MENU = 'ctrl+alt+s'

#: 与场景可交互物交互（对应原作 `scr_interact()`）的全局热键。
#: 为什么桌宠需要一个"交互键"：场景里的物件是**画上去的像素**（不是独立控件），
#: 玩家点不到；而宠物又跑在屏幕坐标里、没有"站在谁面前"这个信息。
#: ⇒ 用"与当前场景的可交互物交互"来近似原作的"走到它面前按交互"。
HOTKEY_DEFAULT_INTERACT = 'ctrl+alt+e'

#: 修饰键名 → MOD_* 位。**只认这 4 个**（不认识的整条热键拒绝，不猜）。
_MOD_NAMES = {
    'ctrl': MOD_CONTROL, 'control': MOD_CONTROL,
    'alt': MOD_ALT,
    'shift': MOD_SHIFT,
    'win': MOD_WIN, 'super': MOD_WIN, 'meta': MOD_WIN,
}

#: 热键 id 的取值区间：`RegisterHotKey` 要求 0x0000–0xBFFF（且进程内唯一）。
HOTKEY_ID_MIN = 0x1000
HOTKEY_ID_MAX = 0xBFFF

#: Qt 的修饰键 → Win32 修饰键。只映射用得到的几个（**不猜**没列的）。
_QT_MOD_MAP = None


def _user32():
    return ctypes.windll.user32


class HotkeyRegistrar(object):
    """进程级热键登记表 —— 负责"注册 / 注销 / 派发"，**不碰 Qt**。

    与 Qt 的桥接在 `HotkeyFilter`（需要 PyQt5）与 `install()` 里做。
    这么切是为了：纯逻辑（id 分配、去重、派发）能被离线回归测试直接测，
    而不用起一个真窗口。
    """

    def __init__(self):
        self._next_id = HOTKEY_ID_MIN
        self._by_id = {}
        self._by_key = {}
        self.registered = []          #: Win32 侧真的注册成功的 id
        self.failed = []              #: 注册失败记录 [(key, errcode)]

    # ---------------------------------------------------------------- 分配
    def _alloc_id(self):
        for _ in range(HOTKEY_ID_MAX - HOTKEY_ID_MIN + 1):
            i = self._next_id
            self._next_id += 1
            if self._next_id > HOTKEY_ID_MAX:
                self._next_id = HOTKEY_ID_MIN
            if i not in self._by_id:
                return i
        raise RuntimeError('热键 id 用尽')

    # ---------------------------------------------------------------- 注册
    def register(self, hwnd, key, callback, vk, mods=None):
        """注册一个热键。返回 `True/False`（**不抛**，失败原因进 `self.failed`）。

        key  —— 人类可读名（如 `'ctrl+alt+s'`），用于去重与日志。
        vk   —— Win32 虚拟键码（`'S'` 的 vk 是 0x53）。
        mods —— 修饰键位掩码；`None` ⇒ 只加 `MOD_NOREPEAT`（**不带任何修饰**）。
        """
        if key in self._by_key:
            return True               # 幂等：同一个键重复注册直接算成功
        hid = self._alloc_id()
        mask = MOD_NOREPEAT if mods is None else (int(mods) | MOD_NOREPEAT)
        ok = bool(_user32().RegisterHotKey(wintypes.HWND(hwnd), hid, mask, int(vk)))
        if not ok:
            err = ctypes.get_last_error() if hasattr(ctypes, 'get_last_error') else 0
            self.failed.append((key, err))
            _log.warning('RegisterHotKey 失败 key=%s vk=0x%02X err=%s（可能已被别的程序占用）',
                         key, vk, err)
            return False
        self._by_id[hid] = (key, callback)
        self._by_key[key] = hid
        self.registered.append(hid)
        _log.info('全局热键已注册：%s（id=0x%04X）', key, hid)
        return True

    def unregister_all(self):
        n = 0
        for hid in list(self.registered):
            try:
                _user32().UnregisterHotKey(None, hid)
                n += 1
            except Exception:
                _log.exception('注销热键 id=0x%04X 失败', hid)
        self.registered = []
        self._by_id = {}
        self._by_key = {}
        return n

    # ---------------------------------------------------------------- 派发
    def dispatch(self, hotkey_id):
        """`WM_HOTKEY` 到达时调它。返回 True 表示"确实派发出去了"。"""
        rec = self._by_id.get(int(hotkey_id))
        if rec is None:
            return False
        key, cb = rec
        try:
            cb()
        except Exception:
            # ★ 回调异常**不许**吃掉整个事件循环（同 companion 的设计律 2）。
            _log.exception('全局热键 %s 的回调抛异常', key)
        return True


#: 进程级默认登记表（`install()` 用；测试里请用 `reset_default()` 隔离）。
_DEFAULT = None


def default_registrar():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = HotkeyRegistrar()
    return _DEFAULT


def reset_default():
    """只给测试用：换一份新的登记表（G2 套件之间不许互相污染）。"""
    global _DEFAULT
    if _DEFAULT is not None:
        _DEFAULT.unregister_all()
    _DEFAULT = HotkeyRegistrar()
    return _DEFAULT


def vk_for_letter(letter):
    """字母/数字 → Win32 虚拟键码（`'A'`..`'Z'` → 0x41..0x5A）。非法输入返回 `None`。"""
    if not isinstance(letter, str) or len(letter) != 1:
        return None
    ch = letter.upper()
    if 'A' <= ch <= 'Z':
        return 0x41 + (ord(ch) - ord('A'))
    if '0' <= ch <= '9':
        return 0x30 + (ord(ch) - ord('0'))
    return None


def parse_hotkey(spec):
    """`'ctrl+alt+s'` → `(规范名, 修饰键掩码, vk)`；**认不出返回 `(None, 0, None)`**。

    规范名的写法固定为「修饰键按 ctrl/alt/shift/win 顺序 + 主键小写」，
    例如 `'alt+ctrl+S'` 与 `'ctrl+alt+s'` 都会规范成 `'ctrl+alt+s'` ——
    否则同一个热键用不同写法注册两次，去重会失效（`_by_key` 按名字查）。

    **不猜**：未识别的修饰键名、多主键、空主键一律整条拒绝（返回 None 三元组），
    由调用方如实报"这条没装上"。
    """
    if not isinstance(spec, str) or not spec.strip():
        return None, 0, None
    parts = [p.strip().lower() for p in spec.split('+') if p.strip()]
    if not parts:
        return None, 0, None
    mods = 0
    main = None
    for p in parts:
        if p in _MOD_NAMES:
            mods |= _MOD_NAMES[p]
        elif main is None and vk_for_letter(p) is not None:
            main = p
        else:
            return None, 0, None          # 多主键 / 未知记号 ⇒ 整条拒绝
    if main is None:
        return None, 0, None
    order = ['ctrl', 'alt', 'shift', 'win']
    names = [n for n in order if mods & _MOD_NAMES[n]]
    canonical = '+'.join(names + [main.upper()])
    return canonical, mods, vk_for_letter(main)


# ===========================================================================
#  Qt 桥接（只有这一段需要 PyQt5；纯逻辑部分刻意不依赖它）
# ===========================================================================

def install(widget, keys, registrar=None):
    """在 `widget` 上装全局热键。

    keys : `{热键写法: 回调}`，例如 `{'ctrl+alt+s': toggle_menu}`。
        写法 = 修饰键 + 单字母/数字（`'ctrl+alt+s'` / `'s'` / `'alt+1'`）。
        ⚠️ 写不带修饰键的裸字母（如 `'s'`）是**合法但危险**的：
        它会系统级抢占该字母（见 `HOTKEY_DEFAULT_MENU` 的说明）。代码允许，
        但产品口径上我们**不**这么做。

    返回 `(成功注册的键列表, 失败记录列表)`。

    ⚠️ 失败**不抛**：调用方据此决定要不要回落到窗口级键盘事件。
    """
    try:
        from PyQt5 import QtCore
    except Exception:
        _log.warning('PyQt5 不可用 ⇒ 全局热键装不上（如实返回失败）')
        return [], list(keys.keys())

    app = QtCore.QCoreApplication.instance()
    if app is None:
        _log.warning('没有 QApplication 实例 ⇒ 全局热键装不上')
        return [], list(keys.keys())
    if QtCore.QThread.currentThread() is not app.thread():
        _log.warning('不在主线程调 install() ⇒ 热键会绑错消息队列，拒绝执行')
        return [], list(keys.keys())

    reg = registrar or default_registrar()
    hwnd = int(widget.winId())
    done, bad = [], []
    for spec, cb in keys.items():
        name, mods, vk = parse_hotkey(spec)
        if name is None:
            _log.warning('热键写法不合法 %r ⇒ 跳过（不猜）', spec)
            bad.append(spec)
            continue
        if reg.register(hwnd, name, cb, vk, mods):
            done.append(name)
        else:
            bad.append(name)

    if done:
        flt = HotkeyFilter(reg)
        app.installNativeEventFilter(flt)
        widget._ralsei_hotkey_filter = flt      # 保引用：局部变量会被 GC 掉
        widget._ralsei_hotkey_registrar = reg
    return done, bad


def HotkeyFilter(registrar):                       # noqa: N802 —— 工厂式命名，与 Qt 类并列
    """惰性构造 `QAbstractNativeEventFilter` 子类（PyQt5 不在时不会走到这里）。"""
    from PyQt5 import QtCore

    class _F(QtCore.QAbstractNativeEventFilter):
        def __init__(self, reg):
            super().__init__()
            self.reg = reg
            self.seen = 0

        def nativeEventFilter(self, event_type, message):   # noqa: N802
            try:
                if event_type in (b'windows_generic_MSG', 'windows_generic_MSG'):
                    import ctypes as _ct
                    msg = _ct.cast(int(message), _ct.POINTER(wintypes.MSG)).contents
                    if msg.message == WM_HOTKEY:
                        self.seen += 1
                        self.reg.dispatch(msg.wParam)
            except Exception:
                _log.exception('nativeEventFilter 处理异常（已吞掉，避免拖垮事件循环）')
            # 返回 (False, 0) = "我不消费这条消息，继续正常派发"
            return False, 0

    return _F(registrar)
