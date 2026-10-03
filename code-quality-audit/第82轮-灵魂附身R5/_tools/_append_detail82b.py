# -*- coding: utf-8 -*-
"""追加 §73.8（用户视角验证 + 透明窗口测法）到详版。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
P = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

ADD = u'''

### 73.8 ★★ 用户视角验证（配合 `screen-automation` 实测，2026-10-03 下午）

用户口径要"达到原作操控的功能" ⇒ 必须回答**用户在屏幕上真正看到什么**。

**做法**（`_tools/live_r5_user_view.py`）：真机起实例 → `toggle_possession()`（真产品入口）
→ 每阶段快照两路：**产品内省** `_soul_visible()` + **真实窗口状态** `IsWindowVisible`。

| 阶段 | 灵魂控件窗口 `IsWindowVisible` | 屏上可见窗口数 | 内省 |
|---|---|---|---|
| 附身前 | `True` · `[2491,1549,2539,1597]` | 3 | True |
| **按 Z 附身后** | **`False`** | **2** | False |
| 再按 Z 解除 | `True` | 3 | True |

⇒ **双向对账**（内省 × 真实窗口）方向完全一致：附身 ⇒ 灵魂**真的从屏幕上消失**；
解除 ⇒ **真的回来**。这就是用户能直接看到的"操控权转移"。验收 **9/9 PASS**。

#### ★★★ 本轮实测确认的环境事实（此前只是推断）

用 `screen-automation` 探测桌宠窗口：

```
cli task begin --handle <桌宠>  ⇒ visible_regions: [] , visible_area: 0 , visible_ratio: 0.0
cli task observe                ⇒ {"ok": false, "error": "目标窗口无法恢复到可视状态"}
cli screen capture --region …   ⇒ 截图里桌宠/灵魂区域**一片空白**（只拍到任务栏）
```

**结论**：桌宠与灵魂都是**透明无边框分层窗口**（类名 `Qt5152QWindowToolSaveBits`）⇒
**屏幕自动化的「可见性/截图」判定对它们完全失效**；但**窗口几何探测（`window list-visible`
及 `task begin` 的坐标）精确可用**。

⇒ **正确测法**：
1. **几何** → 用 `screen-automation`（`window list-visible` / `task begin` 的 region）；
2. **可见性** → 用 Win32 `IsWindowVisible` + 产品内省，**双向对账**；
3. **绝不**用"截图上有没有"或"`visible_area` 是不是 0"下结论 ——
   这正是记忆里那条「**产物侧看不见 ≠ 调用侧没发生**」的实证。

#### 附：本机 CLI 调用备忘（`screen-automation`）
- EXE：`C:\\Users\\23002\\AppData\\Local\\Programs\\Xiaozs\\ScreenAutomationHelper\\ScreenAutomationHelper.exe`
  （`resolve_cli.ps1` 可解析；★ `resolve_cli.sh` 是 **macOS** 版，在 Windows 上会误报 `platform: macos`）。
- **PowerShell 工具在本机静默无输出** ⇒ 走 **Git Bash** 调 CLI。
- ⚠️ **CLI 对管道极敏感**：`| head` / `| tail` 会让它 **SIGTERM**（截图退出时报
  `can't open file for write !` 但**文件其实已落盘**）⇒ **别接管道**，直接跑再 `ls` 验文件。
- `--region` 是 **`left,top,right,bottom`**（不是 `x,y,w,h`）。
- `screen.capture --target virtual-screen` = 全屏。
- 桌宠窗口类名 = `Qt5152QWindowToolSaveBits`，`dpi=144 / scale=1.5`。
'''

with io.open(P, encoding='utf-8') as fh:
    old = fh.read()
if u'73.8' in old:
    print('SKIP: 详版已有 §73.8')
else:
    with io.open(P, 'a', encoding='utf-8', newline='') as fh:
        fh.write(ADD)
    print('APPENDED')
with io.open(P, encoding='utf-8') as fh:
    s = fh.read()
print('len chars:', len(s))
print('73.8 ok:', u'73.8' in s, '| IsWindowVisible ok:', u'IsWindowVisible' in s)
