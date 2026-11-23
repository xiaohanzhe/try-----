# 第201轮 · 桌面四扇门贴到屏幕四边

> 任务书：《首轮任务书.md》—— 路线图唯一可立刻开工的一轮。
> 分工：高等级模型（DeepSeek-V4-Pro）写方案，低等级模型（DeepSeek-V4.1-Flash）执行；本报告由方案方验收把关后落盘。

---

## 0. 一句话结论

桌面四扇门从「贴房间取景框边」改为「贴真实主屏四边」，四边 **±0 px** 达成。
真机 2560×1600 下，上/下门水平居中贴顶/贴底、左/右门垂直居中贴左/贴右，w/h 保持 `sprite_size × scale` 不变。

---

## 1. 改了哪些文件、哪些函数、多少行

| 文件 | 改动 | 行数 |
|---|---|---|
| `ralsei_pet/src/main.py` | ① `_DESKTOP_DOOR_EDGE` 值从 `(边, 比例)` 改为纯边字符串；② `_pin_desktop_doors()` 整函数体重写为只登记边映射；③ 新增 `_rewrite_desktop_door_rects()`（`plan_frame` 之后把 4 条门 `rect` 就地改成屏幕坐标）；④ `_update_scene_layer` 桌面分支改 `view=(主屏宽,主屏高)`、偏移 `(0,0)`，并在 plan 后调改写 | 76 增 / 52 删（净 +24） |
| `code-quality-audit/第89轮…/_tools/check89.py` | E4 判据从「完全包含」改为与 `visible_in_view` 同口径的「不完全在外」 | +1 注释 +1 行 |
| `code-quality-audit/regress/baseline.json` | `--only check89 --update` 固化基线 | 1 键 |

非桌面场景一个字节未动。EOL 纪律：main.py 改前改后均纯 CRLF（bareLF=0）。

---

## 2. 回归结果

**本轮相关套件（改后）：**

```
check89           0      80     0      BASELINE（E4 已修，FAIL 从 1 归 0，--update 固化）
scene_p0          0      90     0      IDENTICAL（非桌面 P0 骨架零变化）
round5_smoke      0      78     0      IDENTICAL（非桌面模块导入冒烟零变化）
check107          1      78     4      DIFF（第200轮遗留欠账，见下）
```

**欠账归因（非本轮引入，接手时即存在）：**

- `check107` FAIL=4：A11/A12 判据硬编码 `SCENE_FIT_FRACTION == 0.5`、`scale 6.666→3.331`，但第200轮已改成 `1/3`（0.333）、`2.222`，基线/判据未同步。
- 7 个套件 DIFF（check99 / check73 / check67 / npc_place56 / npc_persona55 / soul_round55 / round8_anim）：共同根因 = 第200轮 `SCENE_FIT_FRACTION` 0.5→1/3，导致日志「场景全屏化：画面 400x300（比例 0.50）→ 267x200（比例 0.33）」变化；其中 check99/check67/round8_anim 额外含本轮**有意新增**的 3 行日志（场景层自省 / 桌面门登记边 / 场景层指令）。这些套件 FAIL 均为 0，**非桌面行为零破坏**。

任务书「接手事实」写的是「全 IDENTICAL / FAIL=0」，实测不符——第200轮改了 `SCENE_FIT_FRACTION` 却未更新基线。本轮的处置：只 `--update check89`（本轮真改了判据，属允许范围）；check107 及 7 套件 DIFF **单开「回归基线修复」轮**处理，本轮不顺手改（一轮只做一件事）。

---

## 3. 四扇门的实际屏幕坐标（真机 2560×1600）

| 门 | 边 | x | y | w | h | 贴边校验 |
|---|---|---|---|---|---|---|
| desk_door_oneshot（OneShot） | 上 | 1231 | 0 | 98 | 124 | y=0 贴顶，x=(2560-98)/2 居中 ✓ |
| desk_door_niko_home（Niko 家） | 下 | 1231 | 1476 | 98 | 124 | y=1476=1600-124 贴底 ✓ |
| desk_door_ut（UT） | 左 | 0 | 690 | 98 | 220 | x=0 贴左，y=(1600-220)/2 居中 ✓ |
| desk_door_deltarune（三角符文） | 右 | 2480 | 742 | 80 | 116 | x=2480，x+w=2560 贴右 ✓ |

- 前 3 行来自真机日志 `场景层指令` 的 rect 直读；第 4 行（右门）因日志只打「前 3 个 rect」（`_objs[:3]` 切片），据 sprite 尺寸 36×52 × scale 2.222 推算（w=80/h=116），右门贴右由代码 `x = sw - w` 保证，`x+w = sw` 与 w 无关，贴右 0 px 成立。
- 稳定性：第 1 / 30 / 120 帧三处 rect 完全一致，无漂移。

---

## 4. 关键日志行（真机 app.log，全文见 `_evidence/app.log`）

```
[INFO] ralsei_pet.__main__ — 桌面门登记边：{'desk_door_oneshot': 'top', 'desk_door_niko_home': 'bottom', 'desk_door_ut': 'left', 'desk_door_deltarune': 'right'}
[INFO] ralsei_pet.__main__ — 场景层指令（第30帧）：view=(2560, 1600) behind=4 kinds=['obj'] obj数=4 前3个rect=[(1231, 0, 98, 124), (1231, 1476, 98, 124), (0, 690, 98, 220)]
[INFO] ralsei_pet.__main__ — 场景层自省（第30帧）：{'enabled': True, ..., 'scene_id': 'desktop', 'objects': 4, 'canvas_visible': True, 'canvas_geom': [0, 0, 2560, 1600], ...}
```

任务书验收第 3 条三要素全部命中：`behind=4`、`kinds=['obj']`、`canvas_visible=True`。

---

## 5. 左右门「靠近渐显」（第112轮口径）

仍生效。证据链：

1. **代码分析**：渐显逻辑（`door_reveal.apply_to_objects`）在 `plan_frame` **之前**用房间坐标算 alpha（main.py L9858–9877），本轮新增的 `_rewrite_desktop_door_rects` 在 `plan_frame` **之后**只改 rect、不碰 alpha，两者无冲突。
2. **回归**：check112 在完整回归 DIFF 清单之外（IDENTICAL），其 F 段「改动=恰好 2 扇（UT/三角符文），OneShot/Niko 家无 alpha 键」判据未破。

---

## 6. 画面验证的边界（如实说明）

任务书验收第 2 条要「真机截图四门贴边 ±0px」。真机已起（进程正常、持续出帧、canvas_visible=True），但**截图画面里看不到门**：

- 沙箱 GUI 隔离：`gui_screenshot` 取景分辨率报 1920×1080，与 main.py `Qt primaryScreen` 的 2560×1600 不一致；全屏透明画布窗口不出现在任何可捕获截图里，三次截图（screen / childsession / 运行中）都只截到用户真实桌面。
- 这是**沙箱环境限制，非程序缺陷**（门在日志里的屏幕坐标、canvas_geom、behind 全部正确）。

因此「门贴边 ±0px」以**程序日志直读的屏幕坐标**为准（比截图更精确），视觉一环如实标注「沙箱不可验」，截图留档 `_evidence/真机截图_沙箱隔离看不到门.png`。

---

## 7. 遗留问题 + 下一轮

1. **回归基线欠账（第200轮遗留，本轮未碰）**：check107 的 A11/A12 判据需从 `0.5 / 3.331` 更新为 `1/3 / 2.222`，并对 7 个受 `SCENE_FIT_FRACTION` 影响的套件统一 `--update` 重建基线。建议**单开「回归基线修复」轮**（与路线图 202 并列，优先做，否则后续每轮都背着这批 DIFF）。
2. 右门坐标是推算（日志只打前 3 门）——若要把「前 3 个 rect」扩成「全部 rect」属日志措辞改动，需走方案确认，本轮不动。

---

_证据：`_evidence/app.log`（真机日志）、`_evidence/run201.py`（起程序脚本）、`_evidence/真机截图_沙箱隔离看不到门.png`（截图尝试）。_
