# 第162轮 · 基础桌宠排查与修复（先量，后改）

> 口径：用户「我记得咱的基础桌宠还有一些问题，你抽空看看」——没列举。
> 本轮流程：**先量 → 报告 → 用户批「四条全修」→ 落地 → 回归锁 + 破坏性验证**。
> 环境：2560×1600 / 任务栏 72px（工作区高 1528）/ 150% 缩放 / Ollama 在线（`ralsei:v4`）。

## 0. 结论先说

基础功能**没崩**：构造、空转、拖拽、甩飞、右键菜单、托盘、点击穿透、退出清理，逐项实测都正常。
四条**真实偏差**已全部修完，按用户能感知的程度排：

| # | 问题 | 改前硬数据 | 修法 | 改后实测 | 产品位置 |
|---|------|-----------|------|----------|----------|
| 1 | 换动画时按「窗口中心」缩放，起步/停下人物会上下沉一下（脚底漂移 Δh/2） | `100×100 → 229×156`：脚底 **+28px**；`63×133 ↔ 229×156`：**±11~13px**，30 秒内 33 次尺寸变化 | 新增模块级纯函数 `anchored_resize_xy()`：**水平保中心、垂直保底边**；两处尺寸变化块与两处 `drag_position` 补偿同步改用 | 同尺寸对：脚底 **±0px**（Δ 全归零），水平仍保中心 | `main.py` `anchored_resize_xy`（模块级）+ 17547 / 17730 两处调用点 |
| 2 | 两套「地面」：坠落/走到最底用**整屏底**，待机窝着用**工作区底**，差 72px | `_desktop_floor_y=1500` vs `_taskbar_top_y=1428`；截图实测窗口 bottom=**1599**，任务栏上沿 1528 ⇒ 71px 被压 | 新增 `_desktop_ground_y()`（= 工作区底），甩飞/重力落地/弹跳三处落点改用它；`_desktop_floor_y` 只留作取不到工作区时的回落 | 同一甩飞路径 bottom **1599 → 1528**（正好踩任务栏上沿） | `_desktop_ground_y`（在 `_desktop_floor_y` 之后）+ 三处落点 |
| 3 | 记忆写盘失败**不回落**，只打一条 WARNING | E 盘实测 `os.listdir(E:\RalseiMemory)` → `OSError(22, '函数不正确')`，而 `describe()` 仍报 `vault_online: True` | `save_memory` 拆成 `_memory_payload()` / `_write_memory_atomic()` / `_fallback_memory_file()`；主落点失败换 `%LOCALAPPDATA%\RalseiPet` 再写，并把 `memory_dir/_file/_on_device` 切过去 | 主落点可写→不切（负控制绿）；主落点写不进→回落成功且路径切换；两条都不行→返 `False` 不抛 | `memory_system.py` `save_memory` + 三个辅助方法 |
| 4 | 托盘图标被 Win11 折叠时**没有第二条退出路径**（右键菜单 9 项里没有"退出"） | 右键菜单实测 9 项：聊天/去…/玩游戏/喂食/抚摸/爬上来/切换动画/配置/隐藏 | 菜单末尾 `addSeparator()` + 「退出 Ralsei」→ `_quit_from_tray`（先 `cleanup_on_exit()` 再 `quit()`） | 菜单 **9 → 10 项** | `show_interaction_menu`（14561） |

**回归锁**：`check162`（30 条判据）+ `mutate162`（9 条破坏性 + 2 条收口）全绿；
`check162` 已登记进 `regress/run_all.py` 并单独建了基线。

## 1. 已验正常（附判据，便于以后复跑）

| 项 | 结果 |
|----|------|
| 构造 + 空转 6 秒 | 异常 **0** 条、WARNING+ **0** 条 |
| 空转 CPU / 内存 | **0.0%** / **106.8 MB**，活动定时器 14 个 |
| 拖拽跟手 | 合成事件按**屏幕绝对坐标**发：窗口位移与鼠标位移 1:1（第一版报"3 倍"是探针用 `mapToGlobal` 造成的假象，已归因） |
| 甩飞回收 | `_fall_reason=None`，2.5 秒后落点仍在虚拟桌面内 |
| 透明区点击穿透 | 透明像素 60/60 命中桌面（`0x10166`）；不透明像素 60/60 命中自己 ⇒ 探针有鉴别力 |
| 隐藏/恢复 | 托盘路径往返正常 |
| 退出清理 | `cleanup_on_exit()` 不抛 |
| 四个交互入口 | 喂食 / 抚摸 / 玩游戏 都有台词与动画反馈；"玩游戏"抽到唱歌属设计（`games` 随机池） |
| 聊天入口 | 点了只聚焦输入框、不立即出字——与第 9 轮"换题只能由用户发起"一致，非缺陷 |

## 2. 逐条证据

### 2.1 锚点：中心 vs 脚底

```
t(s)  from        to          anim                dFeetY  dCtrY
0.24  100x100     229x156     idle->idle          +28.0    0.0     ← 纯锚点效应（Δh 56 / 2）
10.29 229x156     63x133      idle->walk_left     -11.0   +0.5
17.37 63x133      229x156     idle->idle          +11.0   -0.5
```
判据：`dCtrY ≈ 0` 而 `dFeetY = Δh/2` ⇒ 换尺寸时"中心不动、脚在动"。
用户视角：起步/停下像"顿一下"，站在任务栏边时脚会陷进去十几像素。

### 2.2 两套地面

```
[SCR] geometry   = (0, 0, 2560, 1600)
[SCR] available  = (0, 0, 2560, 1528)     ← 任务栏 72px
[SCR] floor_y(screen) = 1500   taskbar_top_y = 1428   差 = 72
[SHOT] 一次真实运行里窗口 bottom=1599（任务栏上沿 1528）
```
产品自己的注释就写着这种落点是错的（"窗口贴屏幕底边会被任务栏盖住下半截"），
但那条注释只服务于待机窝点，坠落/普通行走的地面仍走整屏底。

### 2.3 记忆写盘失败不回落

```
[ROOT] describe() = {'vault_dir': 'E:\\RalseiMemory', 'vault_online': True,
                     'staging_dir': 'C:\\Users\\...\\RalseiPet',
                     'active_dir': 'E:\\RalseiMemory', 'active_kind': 'vault',
                     'staging_has_data': True}
OSError(22, '函数不正确。')      ← 同一时刻列目录失败（E 盘抽风）
```
`save_memory` 的异常分支只有 `_log.warning` + 删临时文件，**没有**换根重试。
⇒ 用户视角只有一句"他记不住"。

### 2.4 右键菜单没有"退出"

菜单 9 项逐项 `connected` 都非 0（接线没问题），但唯一退出入口在托盘。
Win11 默认把新图标收进溢出区 ⇒ 用户找不到关掉的办法（产品用一次性气泡缓解，
但折叠后仍只有托盘一条路）。

## 3. 环境注记（不是产品 bug，但会影响判断）

- **E 盘是间歇性坏的**：同一分钟内 `os.listdir(E:\RalseiMemory)` 先抛 `OSError 22`、后又能正常列出
  （`memory.json` / `npc_life.json` / `npc_errands.json` 都在）。任何"数据丢了"的判断都要**先复测一次**，
  否则会把盘的问题记到产品头上。
- `E:\RalseiMemory\` 里还躺着一批**历轮探针的残留**（`_wtest2.json`、`_wchk60_*`、`_probe162.tmp` 的同类、
  `zz_clean51.json`、`config.json.bak18` 等）。不是产品产物，建议单独清一次（不在本轮做）。
- **本轮两次误写真实库**（已定位、已堵）：
  1. `vault162.py` 为模拟真实环境**没有**打桩，构造宠物时按产品路径写了真实库
     （`memory.json` / `npc_life.json` / `ghost_state.json` 的 mtime 变成 01:33）。
  2. `check162` 的 D 段第一版让 `MemorySystem()` 自己挑目录，而 `MemorySystem.__init__`
     **内部**会调 `memory_store.default_memory_dir()`（设备优先）⇒ 直接把
     `E:\RalseiMemory\memory.json` 从 **39KB 写成 72KB**（mtime 15:37）。
  - 两次都是「当前状态重存」，**没有删除历史条目**；两次的修法都是**在构造之前**把
    `memory_store.find_device_dir` 打桩成 `lambda create=True: None`（D 段那条已在套件里定稿）。
  - 其余探针一律 `RALSEI_DATA_DIR=D:\_tmp` + 打桩 `vault_root`。
  - ★ 教训：**回归套件必须默认打桩设备目录**——`MemorySystem.__init__` 会自己找设备，
    光设环境变量不够，必须在 import 之后、构造之前把 `find_device_dir` 换掉。

## 4. 沙箱约定（本轮踩过的坑，留给下一轮）

- 精灵素材**不在** `ralsei_pet/` 里：`sprite_loader.sprite_dir = <仓库根>/deltarune_ralsei`。
  只拷 `ralsei_pet` 会得到一屏灰色"?"占位图 —— 那是**沙箱假象**，不是产品缺图。
- `ctypes.windll.user32` 的属性每次访问都是新的 `_FuncPtr`；而且产品代码会按自己的口径改
  `argtypes` ⇒ 每次调用前重设签名，否则报 `expected POINT instance instead of _PT`。
- 本轮截图入库两张：`_evidence/shot162_pet.png`（宠物本体，39KB）、`_evidence/shot162_throw.png`
  （甩飞途中，145KB）。整屏那张 4.6MB 没入库（体积不值当，结论已写在 §0 的 bottom=1599→1528 里）。

## 5. 已修（用户批「四条全修」后落地）

四条**全部按上面 §0 的修法实现**，逐条过 `check162` 判据 + `mutate162` 破坏性验证。

### 5.1 改动清单

**`ralsei_pet/src/main.py`**（CRLF，四处）

```python
# ① 新增模块级纯函数（要能单测 ⇒ 不放类里）
def anchored_resize_xy(pos_x, pos_y, old_w, old_h, new_w, new_h):
    """窗口尺寸变化后的新左上角：**水平保中心、垂直保底边**。"""
    cx = int(pos_x) + int(old_w) // 2
    return cx - int(new_w) // 2, int(pos_y) + int(old_h) - int(new_h)
```

```python
# ② 两处尺寸变化块（约 17547 / 17730）原本各自复制一份"保中心"，改成同一函数
old_pos = self.pos()
new_x, new_y = anchored_resize_xy(
    old_pos.x(), old_pos.y(), self.width(), self.height(),
    target_width, target_height)
```

```python
# ③ 拖拽补偿同步（第 94 轮那段，两处）：垂直分量从"半高差"改成"全高差"
self.drag_position = QPoint(
    self.drag_position.x() + target_width // 2 - self.width() // 2,
    self.drag_position.y() + target_height - self.height())
```

```python
# ④ 新增"脚踩的那条线"，三处落点（甩飞 / 重力落地 / 弹跳）改用它
def _desktop_ground_y(self):
    try:
        return int(self._taskbar_top_y())
    except Exception as e:
        _log.debug("main 防御性异常（已忽略）: %s", e)
        return self._desktop_floor_y()
```

```python
# ⑤ 右键菜单末尾补退出（托盘被折叠时的第二条路径）
menu.addSeparator()
quit_action = QAction("退出 Ralsei", self)
quit_action.triggered.connect(self._quit_from_tray)
menu.addAction(quit_action)
```

**`ralsei_pet/modules/memory_system.py`**（CRLF）

新增类属性 `FALLBACK_DIRNAME = 'RalseiPet'` 与三个方法，`save_memory` 改成"先主落点、失败换根、两条都不行返 False"：

```
_memory_payload()          # 纯数据，不碰 IO，供重试复用
_fallback_memory_file()    # %LOCALAPPDATA%\RalseiPet\memory.json（RALSEI_DATA_DIR 优先）
_write_memory_atomic(path) # makedirs + tmp + os.replace
save_memory()
  ├─ _write_memory_atomic(self.memory_file)         成功 → return True
  ├─ _write_memory_atomic(self._fallback_memory_file())  成功 → 切 memory_dir/_file/_on_device(False)
  └─ 两条都失败 → _log.warning + return False（不抛）
```

### 5.2 甩飞落点必须**逐帧重算**

第一版把 `_fall_land_y` 算一次就缓存，结果下落途中换了动画（133 ↔ 156），落点按旧高度定死
⇒ 落地后**悬空 20 多像素**（实测 `bottom=1505`）。改成逐帧调 `_desktop_ground_y()`：
它只依赖窗口高、不依赖横坐标 ⇒ 不会抖，也跟得上尺寸变化。

### 5.3 回归锁

`code-quality-audit/第162轮-基础桌宠排查/_tools/check162.py` —— **30 条判据**：

```
A1-A6  anchored_resize_xy 行为（保中心/保底边/真实尺寸对/负坐标/★负控制：老口径必不同）
B1-B4  定义在模块级 / 恰好 2 处调用 / AST 查 old_center_y 一处不剩 / 拖拽补偿旧式 0 新式 2
C1-C7  _desktop_ground_y 在位、取工作区底、取不到回落整屏底、三处落点都调它、
       _desktop_floor_y 只剩两个回落 owner、甩飞落点逐帧重算（在 _is_thrown 内、不在 hasattr 缓存内）
D1-D5  真 MemorySystem：主落点可写 / 写不进回落并切路径 / ★负控制能写时不切 / 两条都不行返 False
E1-E3  菜单有"退出 Ralsei" / 连到 _quit_from_tray / 该函数先 cleanup 再 quit
F1-F4  判据名字面量 / 只用 check() / 无 BOM 且行尾统一 / 零外部盘
```

`mutate162.py` —— **9 条破坏性 + 2 条收口**，全绿：

```
M1 锚点改回保中心 → A3 A4 A5 A6   M2 拖拽补偿退回半高差 → B4
M3 地面退回整屏底 → C2 C3 C6      M4 重力落地退回整屏底 → C5 C6
M5 甩飞退回只算一次 → C7           M6 回落位置算不出来   → D2 D3
M7 主落点永远不写 → D1 D3          M8 菜单项改名        → E1
M9 无害变异（只改注释字面量）→ 一条都不许红（实得 0 条）
Z1 还原后 30/0 全绿                Z2 两文件 sha1 与改前字节一致
```

### 5.4 本轮判据踩的坑（留给下一轮）

- **★ 判据别绑写法**：F3 第一版要求"全 LF"，但 `main.py` / `memory_system.py` 在仓库里
  本来就是 CRLF ⇒ 改成"无 BOM + 行尾统一"。
- **★ "提到某名字 = 恒真"**：E1 第一版写 `'退出 Ralsei' in dump or 'quit_action' in dump`，
  把菜单项改名成"走啦"照样绿 ⇒ 收窄成只认**用户看得见的显示文案**。
- **★ 多行变异锚点必须 CRLF 归一**：产品是 CRLF、脚本写的是 `\n` ⇒ M1/M3/M4/M6/M9 整片 MISS。
- **★ 桩要找对对象**：`_func()` 第一版只扫 `tree.body`（模块级），而 `show_interaction_menu`
  是类方法 ⇒ 全红。改成 `ast.walk`。
- **★ 判红先怀疑判据**：C6 本以为 `_desktop_floor_y` 只剩 1 处，实际 2 处
  （`_desktop_ground_y` 与 `_taskbar_top_y` 各一处回落）⇒ 判据改成按 owner 函数名计数。

## 6. 老套件的连带修正（全量 G2 逼出来的）

单套件绿了不算绿。第一次全量跑出 **`PASS=7283 FAIL=1` + 5 个 DIFF**，逐条归因：

| 套件 | 症状 | 真因 | 处理 |
|------|------|------|------|
| `round9_memory` | **FAIL=1**（`I5`） | 判据是 `"'schema': self.SCHEMA" in func_src(save_memory)` —— 我把键表搬进 `_memory_payload()`，**语义没变、判定却红** | 改成**断行为**：真落一次盘、读回 JSON，断 `schema == SCHEMA` + `long_term_memory`/`fragments`/`keys` 三层都在。**51/0** |
| `round6_verify` | **整段 traceback**（`AttributeError: _desktop_ground_y`） | 桩是 `SimpleNamespace`，只挂了 `_desktop_floor_y` ⇒ **桩比产品旧** | 桩上补 `o._desktop_ground_y = o._desktop_floor_y`（老套件考抛物线、不考"哪条地面"）；`E4` 从精确字符串改成 AST「`update_bounce` 里真的调了 `_desktop_ground_y`」。**41/0** |
| `round8_fling` | **整段 traceback**（同上） | 同上 | 同上补桩。**31/0** |
| `round5_verify` | DIFF（`落盘键: []`） | `V5` 用正则从 `save_memory` 源码抓键表 | 改成抓 `_memory_payload`（抓不到再退回原函数）⇒ 键表与基线**逐字一致**。**16/0** |
| `round8_anim` | DIFF（`before=(657,471)` → `(657,492)`） | 判据回显**绝对坐标**；锚点改保底边后初始落点上移 21px | detail 改成回显**位移量** `moved=(0,0)` —— 判据要的就是"没动"。**29/0** |
| `check162` | DIFF（每次跑都不同） | **我自己的套件**用 `mkdtemp` 随机目录名，而产品把含路径的异常打进 WARNING ⇒ 输出含时相量 | 临时根改**固定名** `%TEMP%\check162_work`（跑前清空）；detail 改 `relpath`。连跑两次输出逐字相同 |

★ 三条教训：
1. **"单套件绿 ≠ 全量绿"**：`check162` 30/0 时，另外 6 个套件还在红/漂。
2. **老套件用字符串判据的，产品一重构就会假红**（`round9 I5` / `round5 V5` / `round6 E4` 三处同族）。
   改法统一是「**换成断行为，或换成 AST**」，不是把代码改回去迎合格子。
3. **桩比产品旧要改桩**，不要让产品为旧桩让步 —— 但桩上要让语义**保持老口径**
   （`_desktop_ground_y = _desktop_floor_y`），这样老断言的数值一个都不用动。

### 6.1 最终 G2

```
PASS=7331  FAIL=0  套件=161  全部 IDENTICAL
```
（改前 7301 / 160 套件；本轮 +30 = `check162`，另修 5 个老套件。）
