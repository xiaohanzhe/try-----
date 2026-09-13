# 第五轮代码审查 · 桌面交互 / Win32 / GDI 句柄专项

- **审查对象**：`ralsei_pet/modules/desktop_interaction.py`(实际 2802 行)、`floor_manager.py`(352 行)、`pet_interaction.py`(365 行)、`sprite_loader.py`(实际 600 行)
- **审查方式**：逐行精读 + 2 个只读运行探针（均在非审查机 Python 环境执行，临时文件落 `%TEMP%` 且用完清理）
- **约束**：只读审查，未改动/新建/删除任何源码或用户数据
- **结论速览**：**P0 = 0，P1 = 1，P2 = 3，P3 = 8**（另有"已防御"项 6 条，见末节）

---

## 发现汇总表

| 编号 | 文件:行 | 类别 | 严重度 | 状态 | 简述 |
|------|---------|------|--------|------|------|
| F1 | desktop_interaction.py:997-998, 1063-1066 | 多显示器/坐标过滤 | **P1** | 已证实 | 用虚拟屏"尺寸"做整窗在屏判断，`rect[2]<0`/`rect[3]<0` 误杀主屏左/上侧副屏窗口 |
| F2 | desktop_interaction.py:2419-2452 | 主线程阻塞/UI 冻结 | **P2** | 已证实 | `resize_window_smoothly` 未像 `move_window_smoothly` 那样每步 `processEvents`，缩放动画冻结 UI |
| F3 | desktop_interaction.py:634-708, 676-689 | DPI/坐标换算 | **P2** | 疑点(机制已证实,需运行时量化) | 图标真实坐标用 `GetWindowRect` 屏幕原点+客户区坐标，DPI 虚拟化/列表视图工作区原点偏移导致对不齐 |
| F4 | desktop_interaction.py:1042, 1224 | 隐私过滤正确性 | **P2** | 已证实 | 子串匹配 `mail`/`QQ` 等，误伤无关窗口或漏放真实隐私窗 |
| F5 | desktop_interaction.py:1060-1065, 1154-1214 | 句柄生命周期 | **P3** | 已证实 | `user_opened_privacy_apps` 存裸 HWND 无失效清理，HWND 复用导致误判 |
| F6 | floor_manager.py:245-252 | 边界/降级 | **P3** | 已证实 | `_index_of_floor` 回退 `i-1` 在 i==0 时返回 -1，落点从顶层重判 |
| F7 | desktop_interaction.py:2458-2473, 2609-2757 | 枚举回调健壮性 | **P3** | 已证实 | `find_window_by_keyword`/`identify_*_windows` 回调无单窗口异常保护，中途销毁窗口→整轮返回空 |
| F8 | desktop_interaction.py:1516, 1566-1572, 1644-1649 | 主线程阻塞 | **P3** | 已证实 | 与"移除主线程 sleep"修复相悖的残留 `time.sleep` |
| F9 | desktop_interaction.py:2589-2601 | COM 资源重复释放 | **P3** | 已证实 | `create_new_excel` 成功路径已 Close/Quit，finally 又 `_safe_release_com` 二次释放 |
| F10 | pet_interaction.py:121-128, 130-139 | 边界一致性 | **P3** | 已证实 | `is_on_pet` 无 mask 分支用 `<=` 上界、含 `==0` 歧义；`classify` 越界坐标仍返回 WHOLE_BODY |
| F11 | pet_interaction.py:240-244 | 手势状态 | **P3** | 已证实 | 长按返回后未重置 `last_click_time`/`consecutive_clicks`，后续单击可能误判连击 |
| F12 | desktop_interaction.py:2499-2500 | 多显示器 | **P3** | 已证实 | `move_and_resize_bilibili_window` 用主屏 `SM_CXSCREEN/CYSCREEN` 定位 |
| F13 | desktop_interaction.py:1365-1367 | SHFileOperation 入参 | **P3** | 疑点(需运行时) | `pFrom=file_path` 是否需 `\\?\` 长路径前缀/双 `\0` 终止，超长中文路径下可能失败 |

---

## 逐条详情

### F1 · 多显示器负坐标窗口被错误过滤【P1，已证实】
- **文件:行**：`desktop_interaction.py:997-998, 1063-1066`
- **片段**：
  ```python
  screen_width  = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN (仅尺寸)
  screen_height = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
  ...
  if (rect[0] > screen_width or rect[1] > screen_height or
      rect[2] < 0 or rect[3] < 0):
      return True   # 整窗丢弃
  ```
- **机理**：虚拟屏矩形原点应为 `SM_XVIRTUALSCREEN(76)`/`SM_YVIRTUALSCREEN(77)`。当一台副屏位于主屏**左侧或上方**时，其窗口坐标含负值（如 x∈[-1920,-1800]），`rect[2] < 0` 成立 → 整窗被排除。对比 `floor_manager.py:49-53` 正确使用了 76/77 原点，佐证此处缺原点偏移是缺陷。
- **触发路径**：副屏在主屏左/上的多显示器布局下，任何落在该副屏的可见窗口都不会进入 `get_all_visible_windows` → 宠物无法在其边框"建楼"、nearby 感知缺失。
- **修复建议**：用 `vx=GetSystemMetrics(76); vy=GetSystemMetrics(77)` 构造虚拟屏矩形，判断改为"窗口矩形与虚拟屏矩形是否相交"而非单边比较；或借鉴 floor_manager 用 `QRect(vx,vy,vw,vh).intersects(QRect(...))`。

### F2 · resize_window_smoothly 主线程冻结【P2，已证实】
- **文件:行**：`desktop_interaction.py:2419-2452`（对照 `2399-2412`）
- **片段**：`move_window_smoothly` 循环内已 `QApplication.processEvents()`，而 `resize_window_smoothly` 循环仅 `time.sleep(step_duration)`，无 `processEvents`。
- **机理**：1.5s 缩放动画期间 Qt 事件循环不派发，界面（宠物动画、拖拽、点击）完全卡死；与同文件"修复主线程阻塞"的注释意图自相矛盾。
- **触发路径**：自治代理或用户触发窗口缩放（如 `move_and_resize_bilibili_window` 内部调用）。
- **修复建议**：在 `resize_window_smoothly` 每步 `MoveWindow` 后同样 `try: QApplication.processEvents() except Exception: pass`。

### F3 · 桌面图标真实坐标的 DPI/列表视图原点偏差【P2，疑点】
- **文件:行**：`desktop_interaction.py:634-708, 676-689`
- **片段**：
  ```python
  lv_rect = win32gui.GetWindowRect(list_view_hwnd)
  ...
  x = local_rect.left + lv_rect[0]; y = local_rect.top + lv_rect[1]
  ```
- **机理**：`LVM_GETITEMRECT` 返回列表视图**客户区**坐标，加 `GetWindowRect` 屏幕原点得到屏幕坐标。两处隐患：(a) 本进程若非 DPI_AWARE，`GetWindowRect` 由 Windows 按 DPI 虚拟化缩放，叠加后坐标偏离真实 DPI 因子；(b) 桌面 `SysListView32` 的工作区原点相对虚拟屏未必是 (0,0)，严格做法应 `MapWindowPoints` 或相对桌面工作区。结论：机制层面确实存在，高 DPI / 副屏下图标位置与宠物互动坐标错位。严重性取决于运行环境 DPI 设置 → 标注疑点。
- **触发路径**：高分屏(DPI≠100%)或副屏布局下，宠物"跳到图标上/躲猫猫"对不准。
- **修复建议**：进程声明 `PROCESS_PER_MONITOR_DPI_AWARE`；改用 `user32.MapWindowPoints(list_view_hwnd, 0, byref(pt), 1)` 将客户区点映射为屏幕点。

### F4 · 隐私应用子串匹配过宽【P2，已证实】
- **文件:行**：`desktop_interaction.py:1042`（`is_privacy_app` 同 `1224`）
- **片段**：`is_privacy_app = any(kw in title_lower or kw in class_lower for kw in privacy_keywords)`，关键词含 `"mail"`/`"QQ"`/`"微信"` 等。
- **机理**：`"mail"` 子串命中任意标题含 mail 的网页/应用；`"QQ"` 命中含 "QQ" 的无关窗口；同时真实隐私窗若标题不含这些子串会被放行。属"声称的隐私保护"与实际不符。
- **触发路径**：标题含 "mail" 的普通浏览器标签被当作隐私窗过滤（宠物不互动），或某些 IM 窗口未被识别。
- **修复建议**：改为对进程可执行名/精确类名匹配，或要求整词边界。

### F5 · user_opened_privacy_apps 裸 HWND 无失效清理【P3，已证实】
- **文件:行**：`desktop_interaction.py:1060-1065, 1154-1214`
- **机理**：HWND 以 int 存入 `user_opened_privacy_apps`，仅 `mark_app_as_closed`（按标题重新搜索）时移除。窗口关闭后 Windows 复用 HWND；陈旧 HWND 可能与新窗口句柄相等，导致隐私过滤误判（漏放或误放行），且列表随会话累积增长。
- **修复建议**：存储 `(hwnd, exe_path, title)` 三元组；定时用 `win32gui.IsWindow(hwnd)` 清理失效项。

### F6 · _index_of_floor 回退返回 -1【P3，已证实】
- **文件:行**：`floor_manager.py:245-252`
- **片段**：回退 `for i, floor ...: if floor['platform_height'] <= cur_h: return i-1`；当 `i==0`（当前楼层等价于最顶层且对象已失效）时返回 `-1`。
- **机理**：`get_drop_destination` 用 `range(current_index+1, len)` → 从 `0`（最顶层）开始重判落点，与"从当前楼层往下找"的修复意图相悖，最差情况是落点被错误上提到顶层窗口。
- **修复建议**：回退值 `clamp(0, len-1)`；或直接 `return 0`。

### F7 · 其它 EnumWindows 回调缺单窗口异常保护【P3，已证实】
- **文件:行**：`desktop_interaction.py:2458-2473, 2609-2757`
- **机理**：`get_all_visible_windows` 回调已逐窗口 try/return True（注释 1048-1053），但 `find_window_by_keyword`、`identify_ppt_windows`、`identify_excel_windows`、`identify_word_windows` 的回调未保护；枚举中途窗口被销毁抛异常时，仅外层 try 捕获 → 整轮返回空列表（过度降级）。
- **修复建议**：在回调内对 `GetWindowRect` 等调用包 try/except 并 continue。

### F8 · 残留主线程 sleep【P3，已证实】
- **文件:行**：`desktop_interaction.py:1516`（`create_folder`）、`1566-1572`（`copy_file`）、`1644-1649`（`cut_file`）
- **机理**：与全文件"移除主线程阻塞"修复相悖：`create_folder` 仍有 `time.sleep(0.5)`；复制/剪切按文件大小 sleep 0.4~1.5s。均在主线程同步执行，期间 UI 卡顿。
- **修复建议**：移至工作线程或改为非阻塞延时。

### F9 · create_new_excel 成功路径二次释放 COM【P3，已证实】
- **文件:行**：`desktop_interaction.py:2589-2601`
- **片段**：`workbook.Close(); excel.Quit()` 后 `finally` 仍 `_safe_release_com(app=excel, doc=workbook)`。
- **机理**：对已释放的 COM 对象再次 `Close`/`Quit` 抛 COMError，被 `_safe_release_com` 内部吞掉（仅 debug 日志）。无害但冗余且产生噪声日志。
- **修复建议**：成功路径 `break` 出 finally 释放，或在 finally 中 `excel=None; workbook=None` 后再调用 `_safe_release_com`（其接受 None 安全跳过）。

### F10 · is_on_pet / classify 边界不一致【P3，已证实】
- **文件:行**：`pet_interaction.py:121-139`
- **机理**：有 mask 时用 `ix < self._width`（开区间），无 mask 用 `0 <= x <= self._width`（含 `==`，且 `_width==0` 时仅 `x==0` 成立）；`classify` 对越界坐标不裁剪直接返回 `WHOLE_BODY`。属可维护性/边界隐患。
- **修复建议**：统一边界语义；`classify` 对越界返回 None 或裁剪。

### F11 · on_release 长按后未重置点击计数【P3，已证实】
- **文件:行**：`pet_interaction.py:240-244`
- **机理**：长按返回 PINCH/PULL 时未更新 `last_click_time`/`consecutive_clicks`，其后续快速单击可能因此被并入"连续点击"判定，触发误判的 ear flick / 双击。
- **修复建议**：长按分支同样重置点击状态。

### F12 · B 站窗口定位仅用主屏【P3，已证实】
- **文件:行**：`desktop_interaction.py:2499-2500`
- **机理**：`GetSystemMetrics(0/1)` 返回主屏尺寸，多显示器下目标位置按主屏计算，副屏 B 站窗口可能定位到主屏右侧边缘外。
- **修复建议**：用虚拟屏或窗口当前所在屏的 geometry。

### F13 · SHFileOperation 长路径/中文路径【P3，疑点】
- **文件:行**：`desktop_interaction.py:1365-1367`
- **机理**：`pFrom=file_path` 未加 `\\?\` 前缀，超长路径（>MAX_PATH）或含特殊字符时 `FO_DELETE` 可能失败（返回非零，当前代码会保留文件——安全，但功能不达预期）。pywin32 对单路径已自动补 `\0\0`（已探针确认），故双 `\0` 无需担心。
- **修复建议**：对 `file_path` 套 `os.path.abspath` 并必要时加 `\\?\` 前缀后再传入。

---

## 已防御项（确认无问题，避免误报）

1. **64 位 HWND 截断**：`desktop_interaction.py:50-65` 已显式声明 `restype/argtypes` 用 `c_void_p`/`c_ulong`；只读探针确认 `win32gui` 返回任意宽度 int 且 `c_void_p` 不截断大句柄。**已防御**。
2. **图标探测 GDI/内核句柄泄漏**：`OpenProcess→VirtualAllocEx→ReadProcessMemory→VirtualFreeEx→CloseHandle` 全部在 `try/finally` 中成对释放（`desktop_interaction.py:659-708`）。**已防御**（无 `GetDC/CreateCompatibleDC/CreateCompatibleBitmap` 调用，Grep 全模块 0 命中）。
3. **回收站不再静默永久删除**：`delete_file` 的 `SHFileOperation` 失败（含不存在/占用/无权限）返回非零码，当前代码 `int(_errcode)!=0 → return False` 保留文件，且 except 分支**不再降级为 `os.remove`**。只读探针确认 `SHFileOperation` 对不存在源返回 `(2,False)`（非零、非异常），修复**运行时确认生效**。**已防御**。
4. **无 winshell 回退永久删除**：本代码根本未使用 `winshell`，回收站走 `SHFileOperation(FOF_ALLOWUNDO)`，无 `shutil.rmtree` 回退路径。**已防御**。
5. **EnumWindows 回调 GC**：所有回调均为嵌套闭包，枚举期间被 pywin32 强引用，不会被 GC 中断。**已防御**。
6. **`.lnk`/符号链接**：`open_file`/`double_click_file` 用 `os.startfile`，对 `.lnk` 会打开其指向目标（系统行为），不解析后误删；破坏性操作均经 `os.path.exists`/权限前置校验。**已防御**。

---

## 附带提醒
- `modules/desktop_interaction.py.bak` 存在（与现文件高度重叠的旧版本）。**不在本轮审查范围**，但建议确认其不会因 `__pycache__` 或 IDE 误加载被当作源码使用，并避免误提交。
- 本轮**未发现任何主动 P0 数据丢失路径**：删除走回收站且失败即保留；复制/剪切/重命名/拖拽均对同名目标加时间戳/序号后缀，**无静默覆盖**。
