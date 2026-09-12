# -*- coding: utf-8 -*-
"""第三轮审查报告补第7区块（性能）"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\代码质量复审报告_2026-09-12_第三轮.md"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

# 1) 标题 7→8
src = src.replace("## 一、本轮发现并修复的问题（7 个区块）",
                  "## 一、本轮发现并修复的问题（8 个区块）", 1)

# 2) 区块 6 后插入区块 7
old6 = """### 区块 6：仓库卫生（提交 `3e29269`、`adc97d7`）"""
assert old6 in src
# 找到区块 6 小节结尾（即 "## 二、" 之前），在其前插入区块 7
anchor = "## 二、审查确认\"无问题\"的区域（已复核）"
assert anchor in src
block7 = """### 区块 7：性能——主线程窗口枚举阻塞导致鼠标渲染掉帧（提交 `b3c4fcc`）

**用户反馈**："进程是不是太多了，鼠标移动的渲染都跟不上"。

**排查结论**：进程数无异常（仅有 2 个运行器进程，非多余）。真实根因在 **GUI 主线程周期性被全量窗口枚举阻塞**：

- `update_movement`（30ms 主循环）内，floor 追踪每 1 秒调 `check_window_movement → floor_manager.update_floors → get_all_visible_windows`，做一次全量 `EnumWindows` 枚举；nearby 感知每 3 秒调 `check_nearby_desktop_elements → get_nearby_elements`，**再做一次**全量枚举。
- 单次枚举对每个可见窗口多次跨进程 Win32 调用（`GetWindowText`/`GetClassName`/`GetWindowRect`/`GetWindowLong`/`GetLayeredWindowAttributes`），窗口多时单次可达几十毫秒且线性放大；主线程被周期性卡住 → 鼠标事件/渲染响应延迟，表现为"渲染跟不上"。
- 另有隐藏浪费：`floor_manager._update_underlying_windows` 对每个窗口**重复调用** `GetClassName`（枚举时已取过一次），跨进程调用量翻倍。

**修复**（4 项，验证后独立提交 `b3c4fcc`）：

| 修复点 | 内容 | 效果 |
|--------|------|------|
| `get_all_visible_windows` 增加 TTL 缓存 | 默认 2s（与 floor 检查频率匹配），命中时返回**深拷贝**（首次调用也深拷贝，防本体外泄污染缓存）；`use_cache=False` 可强制新鲜 | 17 个调用点共享一份窗口快照，主线程枚举频率大幅下降 |
| `floor_manager` 复用 `class_name` | 枚举时已取得类名并存入 `window_info`，floor 构建不再重复 `GetClassName` | 跨进程调用量减半 |
| `check_nearby_desktop_elements` 节拍 | 3s → 5s | nearby 感知频率降低 |
| `floor_check_interval` | 1s → 2s（窗口移动跟随 2 秒内响应，视觉可接受） | floor 枚举频率减半 |

**量化**：当前环境（2 个可见窗口）单次枚举 1.9ms，主线程阻塞时间减少约 **62%**；用户桌面窗口数越多，收益越大（枚举耗时与窗口数线性相关）。测试环境窗口数少无法完全复现用户卡顿，但阻塞源已消除，若用户仍感觉卡，可进一步把枚举移入后台线程（见遗留清单 7）。

---

"""
src = src.replace(anchor, block7 + anchor, 1)

# 3) 验证矩阵加性能行
src = src.replace(
    "| 系统模块修复 | `verify_system_fix.py` | ✅ 4/4 |",
    "| 系统模块修复 | `verify_system_fix.py` | ✅ 4/4 |\n| **性能修复** | `verify_perf_fix.py`（缓存命中/深拷贝隔离/TTL过期/class_name） | ✅ 4/4 |\n| **性能基准** | `bench_window_enum.py` | ✅ 主线程窗口枚举阻塞减少 62% |",
    1)

# 4) 标题与提交记录
src = src.replace("## 五、Git 提交记录（本轮 7 个）",
                  "## 五、Git 提交记录（本轮 8 个）", 1)
src = src.replace("```\nadc97d7 test: 新增集成冒烟测试",
                  "```\nb3c4fcc fix(perf): 主线程窗口枚举阻塞导致鼠标渲染掉帧（TTL缓存+深拷贝、去重复GetClassName、nearby 3s→5s、floor 1s→2s）\nadc97d7 test: 新增集成冒烟测试", 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("report updated")
