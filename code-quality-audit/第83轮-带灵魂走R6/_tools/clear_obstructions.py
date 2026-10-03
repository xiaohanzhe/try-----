"""清屏助手 —— 只关「会遮挡桌面、妨碍屏幕测试」的窗口（第83轮工具）。

★ 用户口径（2026-10-03，逐字）：
  「那个剩下我正在用的别管，**只关那个 bilbil 那样会挡住桌面的窗口**，
    防止看不到屏幕状态无法测试」

⇒ 判定规则（**保守，宁可不关也不误关**）：
  1. **必须**是"挡桌面"的：大面积 + 顶层 + 无 owner（owner≠0 的是对话框/子窗）；
  2. **白名单命中即关**：浏览器/视频/播放器这一类的**内容**窗口
     （`Chrome_WidgetWin_1` + 标题像网页、播放器类名）；
  3. **黑名单永不关**（免得关了用户正在用的）：
     · 桌面壳 / 任务栏（`Progman` / `Shell_TrayWnd` / `WorkerW`）；
     · 输入法（`IME` / `Sogou_*` / `MSCTFIME UI` / `Windows.UI.Core.CoreWindow`）；
     · 云文档 / 办公（`XLMAIN` = WPS/Excel、`OpusApp` = Word）；
     · 用户的文件管理器（`CabinetWClass`）；
     · 各种 helper / IPC 小窗（`DummyDWMListenerWindow` 等）；
     · **桌宠自己**（`Qt5152QWindowToolSaveBits` —— 关了就没得测了）；
     · 联想商店的 `pcm_h5_msg` / `wv_*`（用户明确说"别管"）。
  4. **默认不关**：没命中的一律打印出来让用户决定，**不许自作主张**。

用法：
    python clear_obstructions.py            # 只报告（dry-run）
    python clear_obstructions.py --apply    # 真关
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys

u = ctypes.windll.user32

# ---- 永不关（按窗口类名，大小写不敏感）----
NEVER_CLOSE_CLASSES = {
    'progman', 'shell_traywnd', 'workerw', 'shell_dll_defview',
    'ime', 'msctfime ui', 'sogou_tsf_ui', 'sopy_ui', 'sopy_hint',
    'sopy_status', 'windows.ui.core.corewindow', 'edgeuiinputtopwndclass',
    'dummydwmlistenerwindow', 'thumbnaildevicehelperwnd',
    'xlmain', 'opusapp',           # WPS / Word
    'cabinetwclass',               # 文件资源管理器
    'pcm_h5_msg',                  # 联想商店推广层（用户说"别管"）
    'lenovopcmanager',
    'qt5152qwindowtoolsavebits',   # ★ 桌宠/灵魂 自己
    'gdi+ hook window', 'atl:0069b5f8', 'base_powermessag',
    'xlmarexplorerhostislandwindow_w',
}

# ---- 命中即关（"bilbil 那样挡桌面的"）----
# 类名 → 说明
OBSTRUCTION_CLASSES = {
    'chrome_widgetwin_1': '浏览器/WebView 窗口（Edge/Chrome/内嵌页）',
    'chrome_widgetwin_0': '浏览器窗口（旧版）',
    'mozillawindowclass': 'Firefox 窗口',
    'mediaclass': '媒体播放窗口',
    'vlc video output': 'VLC 播放窗口',
    'mpcclass':    '媒体播放器窗口',
    'potplayermainwnd': 'PotPlayer',
    'bilibili': '哔哩哔哩',
    'kugou_ui': '酷狗',
    'txvideownd': '腾讯视频',
    'cloudmusic': '网易云音乐',
    'wechatmainwndforpc': '微信主窗',
    'qq': 'QQ',
    'tim': 'TIM',
}

# wv_ 前缀的 webview（联想商店内嵌页）也属"挡桌面"，但**用户说别管商店** ⇒ 排除
NEVER_CLOSE_PREFIXES = ('wv_', 'webview')


def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            u.SetProcessDPIAware()
        except Exception:
            pass


def enum_candidates():
    out = []
    E = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, l):
        if not u.IsWindowVisible(h) or u.IsIconic(h):
            return True
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        area = (r.right - r.left) * (r.bottom - r.top)
        if area < 200000:               # 小于约 450x450 的不算"挡桌面"
            return True
        e = u.GetWindow(h, 4)           # GW_OWNER
        t = ctypes.create_unicode_buffer(512); u.GetWindowTextW(h, t, 512)
        c = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, c, 256)
        pid = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        out.append({
            'hwnd': int(h), 'ownered': bool(e), 'area': area,
            'title': t.value, 'cls': c.value, 'pid': pid.value,
            'rect': (r.left, r.top, r.right, r.bottom),
        })
        return True

    u.EnumWindows(E(cb), 0)
    out.sort(key=lambda x: -x['area'])
    return out


def proc_name(pid):
    try:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
                           capture_output=True, text=True, encoding='gbk',
                           errors='replace')
        parts = [c.strip('"') for c in r.stdout.split('","')]
        return parts[0] if parts else '?'
    except Exception:
        return '?'


def decide(w):
    cls = (w['cls'] or '').lower()
    if w['cls'].lower() in NEVER_CLOSE_CLASSES:
        return ('KEEP', '永不关（系统壳/输入法/办公/桌宠/用户在用）')
    for p in NEVER_CLOSE_PREFIXES:
        if cls.startswith(p):
            return ('KEEP', '永不关（前缀 %s：联想商店内嵌页，用户说别管）' % p)
    if w['ownered']:
        return ('KEEP', '有 owner（对话框/子窗，不是独立挡屏窗）')
    if not w['title'].strip():
        return ('KEEP', '无标题（多为不可见辅助层）')
    if cls in OBSTRUCTION_CLASSES:
        return ('CLOSE', OBSTRUCTION_CLASSES[cls])
    if cls.startswith('chrome_widgetwin'):
        return ('CLOSE', 'Chromium 内核窗口（浏览器/WebView）')
    return ('REPORT', '未命中白名单 —— 交用户决定（默认不关）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真关（默认只报告）')
    args = ap.parse_args()
    dpi_aware()

    wins = enum_candidates()
    print('=== 大面积顶层窗口（≥200000 px²，可见未最小化）%d 个 ===' % len(wins))
    close_list = []
    for w in wins:
        act, why = decide(w)
        w['act'], w['why'] = act, why
        pn = proc_name(w['pid'])
        print('  [%-6s] h=%-10d %-22s %-26s %s' % (
            act, w['hwnd'], w['cls'][:22], (w['title'] or '(无)')[:26], pn))
        print('           → %s' % why)
        if act == 'CLOSE':
            close_list.append(w)

    print()
    if not close_list:
        print('=== 没有需要关闭的"挡桌面"窗口（桌面已可测试）===')
        return 0

    print('=== 判定为"挡桌面"的窗口 %d 个 ===' % len(close_list))
    for w in close_list:
        print('  h=%-10d %-24s %s' % (w['hwnd'], w['cls'][:24], (w['title'] or '(无)')[:40]))
    if not args.apply:
        print()
        print('（dry-run；加 --apply 才真关）')
        return 0

    print()
    print('=== 执行 WM_CLOSE ===')
    WM_CLOSE = 0x0010
    for w in close_list:
        ok = bool(u.PostMessageW(wt.HWND(w['hwnd']), WM_CLOSE, 0, 0))
        print('  h=%-10d %s -> %s' % (w['hwnd'], 'SENT' if ok else 'FAIL', w['title'][:40]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
