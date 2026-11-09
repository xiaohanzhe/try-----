# 第178轮 · 「遮挡 = 按屏幕 Y 排序」落地（第164轮裁定 `BBA` 第三项）

> 一句话：宠物跟窗口谁压谁，从"看窗口自己的 z 序"改成"**看谁更靠下**"。
> 这条规则你在第164轮就裁定了（回 `BBA`），之后一直挂在"❌ 未实现"上 —— 本轮补上。

---

## 1. 改之前是什么样

`_apply_pet_z_order()` 每秒调一次：

```python
insert_after = self.floor_manager.get_insert_after_hwnd(self.current_floor)
FloorManager.set_window_behind(hwnd, insert_after)
```

`get_insert_after_hwnd(floor)` 的口径是**「插到宠物所站的那块楼板之上」**：

- 站在窗口 A 上 ⇒ 插到 A 之后；
- 站在桌面 ⇒ 插到 WorkerW 之后（桌面图标之上、所有应用窗口之下）。

问题：**谁挡谁完全由窗口自己的 z 序决定**，跟宠物站在屏幕什么高度毫无关系。
宠物站在屏幕最下方（离观众最近）时，仍会被一个位于屏幕中上部的小窗口挡住 ——
这正是 2.5D 空间模型里说不通的那一格。

## 2. 改之后是什么样（本轮口径）

| 概念 | 用什么代表 | 实现在哪 |
|---|---|---|
| 宠物离观众多远 | **脚底**屏幕 Y（窗口下沿，`pos().y() + height()`） | `_apply_pet_z_order` |
| 窗口离观众多远 | **下沿** Y（`top + height`，半开口径） | `_rect_bottom_y` |
| 谁挡谁 | 窗口下沿 **>** 脚底 ⇒ 窗口在前 ⇒ 挡住宠物 | `pick_insert_after_by_foot_y` |
| 谁都没有前挡 | `HWND_TOP`（非置顶带最前） | 同上 |

锚点取**下沿最小**的那个前挡者（离宠物最近的那块板）。原因写在函数注释里：
Win32 的 z 序是**一根线性链**，只能表达"插到某个窗口之后"，没法一次说清
"在 A 后面、但在 B 前面"；取最近的前挡者当锚点，正好落在 Y 排序要求的那一格。

**候选遮挡者取 `self.floors`，不是 `underlying_windows` 全量。**
被前面的窗口完全压住的窗口按建立楼层的口径是"**暂时不存在**"，
它既不显示、也不该当遮挡者 —— 否则会出现"被一个看不见的窗口挡住"。

## 3. ★★★ 顺手挖出来的一个真 bug：`HWND_TOP == 0` 是假值

`set_window_behind` 原来这么写：

```python
insert = hwnd_after or HWND_BOTTOM          # ← 错
```

`HWND_TOP == 0`、`HWND_BOTTOM == 1`。于是**传 `HWND_TOP`（"插到最前"）会被 `or` 吞掉、
变成 `HWND_BOTTOM`（"插到最底"）** —— 语义正好反过来，而且不报错、不抛异常，
只是宠物默默地出现在所有窗口后面。

这个坑以前没暴雷，是因为**从来没人传过 `HWND_TOP`**（老路径只会给有效句柄或 `None`）。
本轮 Y 排序第一次用到它，正好踩上。修法：

```python
insert = HWND_BOTTOM if hwnd_after is None else hwnd_after
```

`check178 D1` 用桩捕获 `SetWindowPos` 的第 2 个实参来钉这条（`D0` 先证明桩真被调用，
否则整段是空转）。

## 4. 向后兼容（硬要求）

**不给 `foot_y` 时行为一字不变**：

- `get_insert_after_hwnd(floor)` ⇒ 还是"插到所站楼板之上"；
- 第十三轮 `verify_round13_build` 的 F1/F2（句柄失效 / 桌面层 ⇒ 回落 `HWND_BOTTOM`）
  与第十六轮 A4（`_apply_pet_z_order` 走 `get_insert_after_hwnd` + `set_window_behind`）
  全部照旧通过；
- 窗口表为空（还没跑过 `update_floors`）⇒ **回退老逻辑**，绝不在启动第一拍把宠物顶到最前。

## 5. 判据 38 条（五段）

| 段 | 条 | 内容 |
|---|---|---|
| A 排列语义 | 13 | 空表 / 全在前 / 取下沿最小 / 齐平算"后面" / 挪 20px 翻面 / **打乱顺序无关** / 两种 rect 形态一致 / 两种 hwnd 键名等价 / 无效句柄跳过 / **1px 边界** / 并列取 z 更前 / `foot_y=None` ⇒ `None` |
| B 接线 | 8 | 签名含 `foot_y=None` · 真调用纯函数 · 候选是 `self.floors` · 空表回退闸 · `_apply_pet_z_order` 真传 `foot_y` · 脚底由 `pos().y()+height()` 得来 · **167 置顶闸还在** · 不再 `or HWND_BOTTOM` |
| C 真对象 | 4 | 打桩后跑真 `FloorManager`：按 Y 取锚点 / 被压住的窗口不参与 / 空表回退 / 不传 `foot_y` 走老口径 |
| D 语义陷阱 | 6 | 桩自检 · `HWND_TOP` 真传成 0 · `None` 仍回落 BOTTOM · 有效句柄原样 · 失效句柄回落 · 目标无效返回 `False` 且不调用 |
| E 自检 | 7 | 两个文件无 BOM/AST · **查恒真** · 单一 harness · 条数下限 · 零外部盘零网络 · 不构造真机 |

## 6. ★★ 本轮夹具/判据自己的三处错（都是实测后改的）

1. **合成窗口表的 `z_order` 与下沿同向** —— "按 Y"与"按 z 序"给出**同一答案**，
   `A3`/`A5` 于是成了**恒真判据**（怎么实现都能过）。改成**故意反向排列**，
   `M2`（排序键换成 z 序优先）才被抓出来。
2. **`M3` 直接删掉 `if` 行** —— 下面的 `continue` 没了块头 ⇒ `IndentationError`
   ⇒ 判据整个崩掉、`[FAIL]` 一条不打（rc=1 但红项为空，**看着"抓到了"其实什么都没证明**）。
   改成 `if False:` 保持语法有效。
3. **`C1` 的 floors 夹具漏了一条** —— 只放了 0x11、没放 0x22，于是"取 0x22"变成
   "取 TOP"的假红。补上后转绿。

`B7` 也踩了一次：闸是 `if getattr(self, '_scene_topmost_on', False): return False`，
名字是**字符串字面量**（`getattr` 的实参），不是 `ast.Attribute` —— 第一版只查 Attribute
⇒ 恒假 ⇒ 假红。改成两种形态都收。

## 7. 变异 11/11

| 变异 | 红 |
|---|---|
| M1 删掉 `foot_y` 分支（撤回接线） | B2 B3 B4 C1 C2 |
| M2 排序键改成 z 序优先 | A3 A4 A5 A6 |
| M3 不做下沿过滤 | A2 A4 A5 A6 A11 C1 C2 |
| M4 `<=` → `<`（齐平算前挡） | A2 A4 A11 |
| M5 取下沿最大 | A3 A4 A5 A6 A12 |
| M6 无前挡者返回 BOTTOM | A1 A2 A11 C2 |
| M7 恢复 `or HWND_BOTTOM` | **B8 D1** |
| M8 `_apply_pet_z_order` 不传 `foot_y` | B5 |
| M9 候选用 `underlying_windows` | B3 C2 |
| M10 删掉空表回退闸 | B4 C3 |
| M11 下沿用 `QRect.bottom()` | A3 A4 **A11** |

每条跑完 `shutil.copy2` 还原 + **sha1 相同 + 全文逐字相同**双核；备份落 `D:\_tmp\mut178\`。

## 8. 全量回归

- 注册进 `regress/run_all.py` 的 `SUITES`（`offscreen: True`），`--only check178 --update` 建基线（合并模式）。
- 全量：**`PASS=7897 FAIL=0`，套件 = 176，176/176 IDENTICAL**（rc=0）。
- **零老锁被撞**：第十三轮 F1/F2、第十六轮 A4、`check89`（场景层置顶那条）全绿。

## 9. 遗留

1. **锚点法是近似**：Win32 只能表达"插到某窗口之后"，所以当同时存在多个前挡者、
   且它们彼此的 z 序与 Y 序不一致时，只保证"最近的那个前挡者"关系正确。
   真要严格逐对排序，得自己接管全部窗口的绘制（不现实）。已在函数注释里写明。
2. **真机手感未验**（沿用第166轮口径：真机验收已弃）。可观测的量都能离屏断言，
   但"用户看着舒服不舒服"只能你自己看。
3. `spr_doorAny*` 素材仍未导出（第173/174轮遗留，与本轮无关；且门的画面本来就在背景图里）。

## 证据清单（`_evidence/`）

| 文件 | 内容 |
|---|---|
| `check178_out.txt` | 38 条判据完整输出（PASS=38 FAIL=0） |
| `mutate178_out.txt` | 11 条变异完整输出（11/11 + 还原后复跑全绿） |
| `g2_178_summary.txt` | 全量 G2 摘要（PASS=7897 FAIL=0 套件=176） |
