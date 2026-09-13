# 第五轮代码审查报告：`ralsei_pet/src/main.py` 第 1–3200 行

**审查范围**：`PerformanceMonitor`、`monitor_performance`、`RalseiPet.__init__`、`_setup_tray`、`_hide_ralsei`、`_show_from_tray`、`_on_tray_activated`、`init_ui`、`load_resources`、`init_systems`、`init_animation`、`init_timers`、`init_placeholder_system`、`create_placeholders`、`update_placeholders`、`get_element_at_pos`、`init_movement`、`update_environment`、`update_mood`、`_sync_system_to_emotions`、`_agent_busy_flags`、`_notify_arrived_if_needed`、`randomize_movement_pattern`、`generate_new_move_target`、`update_movement`、`_handle_mouse_follow`、`check_nearby_desktop_elements`、`check_desktop_element_at_target`、`initiate_auto_mouse_drag`、`start_mouse_drag`、`update_mouse_drag`、`stop_mouse_drag`、`check_api_commands`、`check_nearby_windows`、`start_jump`、`start_falling`、`_is_falling_through_window`、`handle_jump`、`check_window_movement`、`update_floor`、`start_fall`、`trigger_splat`、`handle_gravity_fall`、`handle_fall`、`wake_up`、`start_dragging_play`、`handle_dragging_play`、`trigger_laugh/surprise/shy/unhappy/victory/teasplash`、`reset_special_states`、`climb_to_top_window` 等。

**审查方式**：逐行精读（分 6 段读取 1–3266 行），只读审查，未实例化窗口、未启动 GUI、未修改任何源码。

---

## 一、发现汇总表

| 编号 | main.py 行号 | 类别 | 严重度 | 状态 | 一句话摘要 |
|------|------------|------|--------|------|-----------|
| F1 | 2914–2915 | 移动/目标边界 | P2 | 【已证实】 | `random.randint(100, screen_geom.width/height-200)` 未保护，屏幕 <300px 时 `a>b` → ValueError |
| F2 | 1090–1170、2139–2168、2913–2949、2627 | 多屏/边界一致性 | P2 | 【已证实】 | 目标生成/跳跃/拖拽玩耍用 `availableGeometry()`（主屏）而实际移动用 `_virtual_screen_rect()`（多屏），副屏被强拉回主屏 |
| F3 | 2425–2488 | 重复编码/死代码 | P3 | 【已证实】 | `update_floor` 全项目无调用点，逻辑与 `check_window_movement` 重复且已漂移 |
| F4 | 2405–2407 | 多屏/边界一致性 | P2 | 【已证实】 | `check_window_movement` 窗口跟随 clamp 用 `availableGeometry()` 而非虚拟矩形 |
| F5 | 3057–3074、3023 | 状态机 | P3 | 【已证实】 | `reset_special_states` 未复位 `is_happy`（trigger_laugh 置 True）与 `is_splat`，标志泄漏 |
| F6 | 2963–3018 | 死代码 | P3 | 【已证实】 | `handle_dragging_play` 的 `else`（拖光标）分支永远不可达，且引用未定义属性 |
| F7 | 2205–2226 | 死代码 | P3 | 【疑点】 | `_is_falling_through_window` 在本范围内未发现调用点 |
| F8 | 2635–2684、2722 | 多屏/边界一致性 | P2 | 【已证实】 | 重力落点 `drop_pos` 可能位于副屏负坐标，最终 `move` 被 clamp 到主屏 |
| F9 | 1300–1306 | 状态机 | P3 | 【已证实】 | `elif is_recovering` 分支恒被 `elif is_falling`（1300）提前拦截，冗余死分支 |
| F10 | 852–858 | 异常处理/逻辑 | P3 | 【已证实】 | `humidity` 的 `else` 分支无界随机游走，长期运行可越出 [0,100] |
| F11 | 3212–3217 | 异常处理 | P3 | 【已证实】 | `react_to_desktop_element` 用 `element['type']` 直接索引，与上方 `.get` 风格不一致 |
| F12 | 2578–2602 | 状态机 | P3 | 【疑点】 | `trigger_splat` 置 `is_falling=True` 但未清 `is_gravity_falling`，依赖调用方已清 |
| F13 | 982–1020、1055–1087 | 重复编码 | P3 | 【已证实】 | “主导情绪→概率/距离/速度”的 if/elif 链在多处复制 3 次，漂移风险 |
| F14 | 1091、1169–1170 | 重复编码 | P3 | 【已证实】 | `sprite_size=int(50*2.0)=100` 魔法数字与 clamp 的 `50`/`self.width()` 取值不一致 |

> 本审查段（1–3200 行）**未发现 P0（崩溃/数据丢失/安全）与 P1（用户可见功能错误）级别的缺陷**。所有问题均为潜伏缺陷（P2）或可维护性（P3）。理由见下文各条“已防御/误报排除”。

---

## 二、逐条详情

### F1 — `start_dragging_play` 未保护的 `randint(a, b)`（P2，已证实）
- **行号**：`main.py:2914-2915`
- **关键代码**：
  ```python
  target_x = random.randint(100, screen_geom.width() - 200)
  target_y = random.randint(100, screen_geom.height() - 200)
  ```
- **机理**：`random.randint(a, b)` 要求 `a <= b`。当主屏宽度/高度 < 300 像素时，`100 > width-200` 触发 `ValueError: empty range`。该调用位于 `update_movement`（1406 行）的非 try 块内，异常会冒泡出定时器槽。
- **触发路径**：极低分辨率虚拟机/远程桌面（主屏 <300px）→ 空闲且距上次拖拽玩耍 >90s 且 `random()<0.002` → `start_dragging_play()` → ValueError。
- **影响**：PyQt 会打印 traceback 但定时器继续触发（非硬崩溃），属潜伏缺陷。普通显示器（≥800px）不会触发。
- **修复建议**：改为 `max(100, min(..., screen_geom.width()-200))` 并把下限做成与上限比较：`lo, hi = 100, max(101, screen_geom.width()-200)` 后再 `randint(lo, hi)`。
- **对照**：`generate_new_move_target` 内的 `randint` 均为常量区间（如 `(100,300)`、`(-40,40)`、`(-10,10)`），且最终有 `max(50, min(target_x, width-sprite_size))` 兜底，本段 `a>b` 不构成崩溃 —— **已防御**，不计入。

### F2 — 屏幕几何来源不一致：目标生成用主屏、移动用多屏（P2，已证实）
- **行号**：`main.py:1090-1170`（generate_new_movement）、`2139-2168`（start_jump）、`2627`（handle_gravity_fall）、`2913-2949`（handle_dragging_play）使用 `QApplication.desktop().availableGeometry()`；而 `1513-1519`（`update_movement`）、`1662`（`_handle_mouse_follow`）使用 `self._virtual_screen_rect()`。
- **机理/影响**：在左/上副屏（负坐标）场景下，`generate_new_move_target` 以“当前位置 + 偏移”算出新目标后，被 `availableGeometry()`（非负、仅主屏）clamp 成主屏坐标 → 宠物被瞬间“吸”回主屏；同理 `start_jump` 着陆点（2148/2158/2163）与 `handle_dragging_play`（2948-2949）的 clamp 也会把宠物钉在主屏。`update_movement` 实际移动时又按虚拟矩形 clamp，两套坐标系打架，副屏漫游/跳跃发生抽搐或越界跳变。
- **触发路径**：多显示器 + 宠物走到副屏 → 周期性 `generate_new_move_target` / 窗口边跳跃 / 拖拽玩耍。
- **修复建议**：全项目统一使用 `_virtual_screen_rect()`（或新增 `_clamp_to_virtual(x,y)` 辅助函数），消除 `availableGeometry()` 与虚拟矩形混用。
- **对照**：`update_movement` 自身的 clamp（1518-1519）已用虚拟矩形，主循环不穿透/不出屏 —— **已防御**。

### F3 — `update_floor` 为死代码且与 `check_window_movement` 重复（P3，已证实）
- **行号**：`main.py:2425-2488`
- **机理**：`check_window_movement`（2390 行注释明确写“`update_floor()` 全项目无任何调用点”）。`update_floor` 实现与 `check_window_movement`（2356-2423）几乎逐行重复（窗口跟随平移、大幅移动摔倒、层级切换掉落），但二者已不完全一致（如 `update_floor` 额外处理“桌面被新窗口覆盖站上去”），属于重复编码且会持续漂移。
- **修复建议**：删除 `update_floor`，或将其重构为 `check_window_movement` 的内部函数，单一事实来源。

### F4 — `check_window_movement` 窗口跟随 clamp 用主屏几何（P2，已证实）
- **行号**：`main.py:2405-2407`
- **机理**：窗口被移动时，`n_x = pos.x() + x_diff; n_x = max(0, min(n_x, screen_geom.width()-self.width()))`，其中 `screen_geom = QApplication.desktop().availableGeometry()`（主屏）。若宠物/窗口位于副屏（尤其负坐标），平移后被 clamp 到 `[0, 主屏宽]`，宠物瞬移回主屏。与 F2 同源。
- **修复建议**：改用 `_virtual_screen_rect()` 的 `left()/right()/top()/bottom()` 做 clamp。

### F5 — `reset_special_states` 未复位 `is_happy` / `is_splat`（P3，已证实）
- **行号**：`main.py:3057-3074`（复位列表）、`3023`（`trigger_laugh` 置 `self.is_happy=True`）
- **机理**：`trigger_laugh` 将 `is_happy=True`，但 `reset_special_states` 只复位 `is_laughing/is_surprised/is_shy/is_unhappy/is_victorious/is_teasplashed/...`，遗漏 `is_happy`；`trigger_splat` 设置的 `is_splat` 也未被本函数复位（靠 `handle_fall` 在恢复完成时清）。导致“开心”等布尔标志可能长期滞留，且与“表演动画最小持续时长”逻辑耦合后存在状态泄漏。
- **修复建议**：在 `reset_special_states` 中补 `self.is_happy = False; self.is_splat = False`。并确认 `is_happy` 在别处是否真正被读取，若否可删除该字段（见下方“死变量”）。
- **补充**：`is_happy` 在当前 1–3200 行范围内**未被任何读取方使用**（动画时长走 `init_animation._perf_anim_min_duration`），属于“赋值后从未读取”的死状态变量，建议一并清理或接入实际消费逻辑。

### F6 — `handle_dragging_play` 拖光标分支为死代码且引用未定义属性（P3，已证实）
- **行号**：`main.py:2963-3018`
- **机理**：`start_dragging_play`（2891 行）固定 `drag_target = "desktop_element"`，`if drag_target == "desktop_element":` 恒真，故 `else`（2963 起，拖光标）**永远不可达**。该死分支却引用 `self.dragging_cursor_start_time` 与 `self.dragging_cursor_duration`，二者在类内从未赋值；一旦将来把 `drag_target` 改成 `"cursor"` 就会 `AttributeError`。
- **修复建议**：删除死分支，或补全 `dragging_cursor_*` 属性的初始化与真实实现（当前为有意禁用的“抢鼠标”行为，应在文档里彻底移除而非留半截代码）。

### F7 — `_is_falling_through_window` 疑似未被调用（P3，疑点）
- **行号**：`main.py:2205-2226`
- **机理**：定义了简易线段/矩形穿越检测，但本范围内所有穿透处理都在 `handle_jump`（2280-2289）内联完成（遍历 `floor_manager.get_all_floors()`），未见对 `_is_falling_through_window` 的调用。需超 3200 行二次确认；若确实无调用点为死代码。
- **修复建议**：确认后删除，或替换 `handle_jump` 内联逻辑以复用之。

### F8 — 重力落点 `drop_pos` 可能落在副屏负坐标，被强制 clamp 到主屏（P2，已证实）
- **行号**：`main.py:2635-2684`（落窗分支）、`2722`（`move`）
- **机理**：`get_drop_destination(ralsei_pos, current_floor)` 返回的 `drop_pos` 取自窗口 `rect`，在副屏可为负坐标。落窗分支仅把 `new_y = drop_pos.y()`，`new_x` 沿用到 2628 已被 `availableGeometry` clamp；`self.move(int(new_x), int(new_y))` 落在主屏范围，导致宠物“掉到副屏窗口上”却被画在主屏。与 F2/F4 同源的多屏坐标系不一致。
- **修复建议**：落点计算与最终 `move` 统一使用 `_virtual_screen_rect()`。

### F9 — `update_movement` 中 `elif is_recovering` 为冗余死分支（P3，已证实）
- **行号**：`main.py:1300-1306`
- **机理**：`start_fall`/`trigger_splat` 置 `is_falling=True`；`is_recovering` 直到 `handle_fall` 恢复完成（2809 行）才被置 True，而此时 `is_falling` 才被置 False。因此在整个恢复期 `is_falling` 始终为 True，第 1300 行 `elif self.is_falling:` 已先匹配并 `return`，第 1303 行 `elif is_recovering` **恒不可达**。
- **修复建议**：删除 1303-1306 的冗余分支（其 `handle_fall` 调用已在上方覆盖）。

### F10 — `humidity` 无界随机游走（P3，已证实）
- **行号**：`main.py:852-858`
- **机理**：`rainy`/`sunny` 分支有 `min(90)/max(30)` 边界，但 `else` 分支 `self.humidity += random.uniform(-1.0, 1.0)` 无 clamp。长期运行（数小时）后湿度可能越出 [0,100]，虽不影响物理积分，但与“客观因素”语义不符，且下游若按百分比使用会得到脏值。
- **修复建议**：统一加 `self.humidity = max(0.0, min(100.0, self.humidity + ...))`。

### F11 — `react_to_desktop_element` 对 `element` 用直接索引（P3，已证实）
- **行号**：`main.py:3212-3217`
- **机理**：前面已统一用 `element.get(...)` 防御，但 `if element['type'] == 'folder':` / `elif element['type'] == 'file':` 直接索引。若某桌面元素缺 `type` 键（异常/外部数据），此处 `KeyError` 中断反应流程。
- **修复建议**：改为 `element.get('type')` 并默认 `None`。

### F12 — `trigger_splat` 未显式清除 `is_gravity_falling`（P3，疑点）
- **行号**：`main.py:2578-2602`
- **机理**：`trigger_splat` 置 `is_falling=True`、`is_splat=True`，但没有 `self.is_gravity_falling=False`。当前唯一调用点（`handle_gravity_fall` 2638/2694 行）在调用前已清 `is_gravity_falling`，故实际不会冲突；但若日后从 `start_fall`/其它路径直接调用，会出现 `is_falling` 与 `is_gravity_falling` 同时为真，`update_movement`（1297 行）优先走重力分支，`is_falling` 状态滞留。
- **修复建议**：`trigger_splat` 开头显式 `self.is_gravity_falling = False`。

### F13 — “主导情绪→参数”的 if/elif 链多处复制（P3，已证实）
- **行号**：`main.py:982-1020`（`randomize_movement_pattern` 移动概率）、`1006-1020`（休息时长）、`1055-1087`（`generate_new_move_target` 移动时长/速度）
- **机理**：同一组 `dominant_emotion ∈ {excited, shy/peaceful, curious, sad/tired, else}` 的分支逻辑在至少 3 处复制，数值（如 `0.4`/`0.7` 速度系数、`random.uniform` 区间）已出现局部不一致（如 `randomize` 用 `0.4` 默认而 `generate` 用 `0.4`~`0.6` 区间），后续维护极易漂移。
- **修复建议**：抽取 `_emotion_profile(emotion)` 返回 `{move_prob, idle_range, move_range, speed_range}` 的单一字典/函数。

### F14 — `sprite_size` 魔法数字与 clamp 魔法数不一致（P3，已证实）
- **行号**：`main.py:1091`（`sprite_size = int(50 * 2.0)`）、`1169-1170`（clamp 用 `50`）、多处用 `self.width()`
- **机理**：目标 clamp 用硬编码 `50`，而 `sprite_size` 又算成 `100`，与实际 `self.width()`（init_ui 设为 100）理论上一致但来源分散。窗口跟随/拖拽玩耍（2406、2948 等）又用 `self.width()` 做 clamp。三套取法，若将来改宠物尺寸，`sprite_size` 与 `self.width()` 易脱节。
- **修复建议**：统一用 `self.width()/self.height()` 或常量 `PET_SIZE`，移除 `50` 散点。

---

## 三、误报/已防御排除清单（明确不计入缺陷）
1. `generate_new_move_target` 内全部 `randint` 为常量区间 + 末尾 `max(50, min(target, width-sprite_size))` 兜底，窄屏不会 `a>b` 崩溃 —— **已防御**。
2. `update_movement` 每帧位移 = `min(distance, new_speed, speed)`，与 `elapsed_time` 无关（速度语义为“像素/帧”），大 `elapsed_time`（休眠唤醒）不会引起穿屏/穿透 —— **已防御**；`handle_jump` 用 `jump_progress=min(elapsed/dur,1.0)` 且 ≥1.0 时 snap 到目标，不穿透 —— **已防御**；`handle_gravity_fall` 的 `fall_distance/fall_velocity_x` 最终被 `availableGeometry` clamp 到屏内 —— **已防御**（仅多屏坐标错，见 F2/F4/F8，非穿透）。
3. `handle_jump` 首行 `if not getattr(self,'jump_duration',0) or self.jump_duration<=0: return` 防御除零 —— **已防御**。
4. 定时器均在 `__init__` 内单点创建并 parent 到 `self`（`QTimer(self)`），销毁随窗口级联停止，无“重复创建多份定时器”或“销毁后回调”隐患（本轮未见 `singleShot` 延迟 lambda 捕获 `self` 的写法）—— **已防御**。
5. `_hide_ralsei` 恢复用 `self.show()/raise_()/activateWindow()`，位置沿用隐藏前坐标；托盘不可用时退化为 `showMinimized`，无“恢复后落在屏外导致宠物消失”的路径 —— **已防御**（`_show_from_tray` 不重置坐标，故不会越界）。
6. `initiate_auto_mouse_drag` 为空实现，但注释明确“有意禁用（不抢用户鼠标）”且保留签名，非“冒充功能”；属设计决策，不计入缺陷（仅提示其 `auto_mouse_drag_timer` 每 60s 空转一次，轻微浪费）。

---

## 四、结论
本轮 1–3200 行**无 P0、无 P1**。最值得优先处理的三条：
- **F2（多屏坐标系不一致，含 F4/F8）**：副屏下宠物被强拉回主屏，是最可能影响真实多显示器用户体验的潜伏缺陷（P2）。
- **F1（`start_dragging_play` 未保护 `randint`）**：极小分辨率下抛 ValueError，应在 randint 前做上下界归一（P2）。
- **F3 + F6 + F7（死代码/重复逻辑）**：`update_floor`、`handle_dragging_play` 拖光标分支、`_is_falling_through_window` 三处冗余，应清理以消除漂移与未来误改风险（P3）。
状态机方面 `reset_special_states` 漏复位 `is_happy/is_splat`（F5）与 `trigger_splat` 未清 `is_gravity_falling`（F12）属轻微标志泄漏，建议一并补齐。
