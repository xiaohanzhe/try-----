# W1-2 验证证据（躲猫猫控制器拆分）

- 项：**W1-2 `HideAndSeekController`**（Wave 1 第 4 项）
- 日期：2026-09-20
- 施工报告：`../W1-2_施工报告_2026-09-20.md`
- 侦察：`../_recon/w1_2_recon_2026-09-20.md`

---

## 一、两侧源码指纹（A/B 前置：必须 A ≠ B）

| 侧 | 来源 | 路径 | md5（前 12） | md5（全） |
|---|---|---|---|---|
| **A**（父版本） | `git show HEAD:ralsei_pet/src/main.py` | 宿主内嵌 | `858281f0053c` | `858281f0053cd70632b3a7d8e7fce97c` |
| **B**（当前版） | 工作区 | `ralsei_pet/modules/hide_controller.py` | `a3b3dd6870c8` | `a3b3dd6870c81819e6a7ede7d3e0bbed` |

A ≠ B（探针内断言，相等即 `sys.exit(3)`）。

`HEAD` = `a6f44f9`（W1-1 记忆补写）。

---

## 二、改动规模

| 文件 | 状态 | 行数 | md5 前 12 |
|---|---|---|---|
| `ralsei_pet/modules/hide_controller.py` | **新增** | 527 | `a3b3dd6870c8` |
| `ralsei_pet/src/main.py` | 修改 | 9713 → **9375**（−338 净） | — |
| `ralsei_pet/modules/spell_controller.py` | 修改（补第 3 条白名单） | — | — |
| `ralsei_pet/modules/video_controller.py` | 修改（同上） | — | — |
| `ralsei_pet/modules/games_controller.py` | 修改（同上） | — | — |

`git diff --stat -- ralsei_pet/src/main.py`：

```
 ralsei_pet/src/main.py | 374 +++---------------------
 1 file changed, 18 insertions(+), 356 deletions(-)
```

`RalseiPet` 方法数：195 → **183**（−12）。

---

## 三、搬走的方法（12 个，物理连续 L9175–9527）

| # | 方法 | 行数（方法体） | 备注 |
|---|---|---|---|
| 1 | `start_hide_and_seek_game` | — | 入口，5 处外部引用 |
| 2 | `_abort_hide_and_seek` | — | 3 个 reason 分支 |
| 3 | `_hide_move_to_point` | — | 移动 + 回调注册 |
| 4 | `_hide_on_arrive_center` | — | **调 `_cast_spell_then`（W1-1）** |
| 5 | `_hide_create_obstacles_after_spell` | — | `screen.center().x()` |
| 6 | `_hide_after_hiding_spell` | — | |
| 7 | `_hide_on_arrive_folder` | — | **★铁律 1 现场** |
| 8 | `_hide_search_tick` | — | 3 支：超时 / 表演找 / 点中 |
| 9 | `_hide_end_game` | — | 调 `_hide_destroy_obstacles` |
| 10 | `_hide_destroy_obstacles` | — | `shutil.rmtree`(无 `winshell`) |
| 11 | `_hide_report_clicked_folder` | — | `QTimer.singleShot` |
| 12 | `_hide_jump_back_to_desktop` | — | `QTimer.singleShot` |
| | **合计** | **321 方法体行 / 342 物理行** | |

> ⚠️ `_hide_ralsei`（L558，17 行）**不在**本项范围内 ——
> 分组器因名字前缀把它误纳进来（托盘隐藏，与躲猫猫无关）。见报告第一节。

---

## 四、6 处非逐字改动（逐条实测计数）

| # | 改动 | 实测处数 | 文件内文本出现数 | 铁律 |
|---|---|---|---|---|
| 1 | `_log.` → `self._log_().` | **15** | 16（=15 + 1 文档提及） | 铁律 6 |
| 2 | `QTimer(self)` → `QTimer(self.p)` | **1** | 3（=1 真改 L358 + 2 注释提及） | 铁律 1 |
| 3 | 模块级 `import time` | 1 | 1 | 铁律 1 同型 |
| 4 | 模块级 `from PyQt5.QtCore import QPoint` | 1 | 1 | 铁律 1 同型 |
| 5 | 宿主 `init_systems` 补 4 个预声明 | 4 | 各 1 | 铁律 3 |
| 6 | 宿主接线 | 3 | 各 1 | — |

第 5 条的 4 个名字（**在 `init_systems()`，非 `__init__`**）：
`_hide_search_started_at` / `_hide_search_checked` / `_hide_moving_cb` / `_hide_moving_cb_stage`

第 6 条的 3 处：
```python
from modules.hide_controller import HideAndSeekController
_CONTROLLER_ATTRS = ('games', 'video', 'spell', 'hide_seek')
self.hide_seek = HideAndSeekController(self)
```

**其余方法体逐字不变。**

---

## 五、三维验证结果

| 维度 | 脚本 | PASS | FAIL | 说明 |
|---|---|---|---|---|
| 单元 | `../verify_w1_2_unit.py` | **64** | **0** | 方法面 / 转发壳 / 白名单 / 预声明 |
| 端到端 | `../verify_w1_2_e2e.py` | **82** | **0** | 真控制器实例；**E6 = 铁律 1 唯一权威判据** |
| A/B | `../verify_w1_2_ab.py` | **82** | **0** | 12 方法逐场景行为等价 |

### A/B 迭代轨迹（5 次，**全部为夹具缺陷**）

| 次 | PASS/FAIL | 假红项 | 根因 |
|---|---|---|---|
| 1 | 63/19 → 63/9 起 | — | `compile()` mode 写错（编码串占了 mode 槽） |
| 2 | 69/9 | AB5a/b | 桩 `Screen` 缺 `center()` → **两侧同抛** |
| 3 | 73/6 | AB6d, AB7.clicked, AB10×2 | 夹具路径自增序号 + `QTimer` 桩缺 `singleShot` |
| 4 | 75/5 | 同上 + AB12d | `s.p` 缺失致 `except` 静默吞 |
| 5 | **82/0** | — | 修 `_STABLE` 登记表 + `s.p = s` + 重做反控 |

### A/B 场景哨兵清单

| 哨兵 | 作用 | 抓到的假绿 |
|---|---|---|
| `AB4a/4e 两侧均无异常` | 防"两侧同抛" | 形态 ① |
| `AB4b ★真的跑到了（stage 非 None）` | 防"两侧空跑" | 形态 ② |
| `AB5b ★真的建出了文件夹` | 防"两侧空跑" | 抓到了桩缺 `center()` |
| `AB6a ★两侧均无异常（铁律 1）` | 铁律 1 现场 | — |
| `AB6b/e/f ★进到 searching / parent=宿主 / 3000ms` | 防空跑 | 抓到了 `excep` 静默吞 |
| `AB7.* ★走到预期分支 + ★产生预期副作用` | 防空跑 | 抓到了 `checked_n` 预期写错 |
| `AB8 ★真的删掉了沙箱目录` | 真副作用 | — |
| `AB9 ★真的清理了` | 真副作用 | — |
| `AB11 ★真的移动了 + clamp 被调用` | 真副作用 | — |
| `AB12f ★好版本确实执行到了 _log_() 那行` | 防反控空跑 | ★本项新增 |

### A/B 反控（a–g）

```
AB12a 反控夹具真的改动了源码（bad_q != cur）                     [PASS]
AB12b ★反控边界：A/B 下 QTimer parent 恒为宿主（铁律 1 由 e2e 覆盖）[PASS] parents=['Stub']
AB12c 反控夹具真的改动了源码（bad_log != cur，16 处替换）          [PASS]
AB12d ★裸 _log_() 在探针默认 ns 下当场 NameError（有鉴别力）        [PASS] NameError: name '_log_' is not defined
AB12e ★对照：正常版本在同一场景下正常                              [PASS] err=None
AB12f ★对照：正常版本确实执行到了 _log_() 那一行                    [PASS] log_called=True
AB12g ★对照：差异确实来自那一行（双方都进 except 岔路）             [PASS]
```

---

## 六、G1 零引用筛查（W1-2：11 名字，全部有引用点）

| 名字 | 引用点 | 分布 |
|---|---|---|
| `start_hide_and_seek_game` | 5 | `diag_real.py` / `diag_spell.py` / `dialogue_ui.py` L1673,1682 / `main.py` L6285 |
| `_hide_move_to_point` | 2 | `hide_controller.py` L200, L339 |
| `_hide_end_game` | 2 | `hide_controller.py` L371, L526 |
| `_hide_on_arrive_center` | 1 | `hide_controller.py` L200 |
| `_hide_create_obstacles_after_spell` | 1 | `hide_controller.py` L271 |
| `_hide_after_hiding_spell` | 1 | `hide_controller.py` L326 |
| `_hide_on_arrive_folder` | 1 | `hide_controller.py` L339 |
| `_hide_search_tick` | 1 | `hide_controller.py` L359 |
| `_hide_destroy_obstacles` | 1 | `hide_controller.py` L427 |
| `_hide_report_clicked_folder` | 1 | `hide_controller.py` L383 |
| `_hide_jump_back_to_desktop` | 1 | `hide_controller.py` L501 |

**无死代码。**

W1-1 未回归复核：`_tick_spell_flow`(4) / `_start_open_with_spell`(3) /
`_spell_interrupted_reason`(5) 引用点均在。

W1-6 死代码候选（留给 W1-6）：`create_person_name_table`(**0**)、`check_excel_table_needs`(**0**)。

产物：`_evidence/zero_refs.txt`（脚本 `../scan_zero_refs.py` 生成）

---

## 七、G2 全量回归

```
合计：PASS=1163  FAIL=0  套件=24     全部 IDENTICAL
```

唯一基线更新：`round5_smoke`（模块数 34 → 35）：

```diff
-待导入模块数: 34
+待导入模块数: 35
   [ OK ] games_controller
+  [ OK ] hide_controller
   [ OK ] lazy_log
```

更新命令（**合并模式**，其余 23 套件基线不动）：
```powershell
& C:\Python311\python.exe code-quality-audit/regress/run_all.py --update --only round5_smoke
```

---

## 八、复现命令

```powershell
# G2 全量回归（唯一安全性判据）
cd "C:\Users\23002\Desktop\项目文件夹\try - 副本"
& C:\Python311\python.exe code-quality-audit/regress/run_all.py

# G1 零引用筛查
& C:\Python311\python.exe code-quality-audit/架构改造-H4H5/scan_zero_refs.py

# 三维探针
& C:\Python311\python.exe code-quality-audit/架构改造-H4H5/verify_w1_2_unit.py
& C:\Python311\python.exe code-quality-audit/架构改造-H4H5/verify_w1_2_e2e.py
& C:\Python311\python.exe code-quality-audit/架构改造-H4H5/verify_w1_2_ab.py
```

> ⚠️ 三个探针与 G2 **都只用 `C:\Python311\python.exe`**（托管 3.13 venv 缺 `bs4` → 假 FAIL）。
> ⚠️ A/B 探针的沙箱在 `%TEMP%\_w1_2_ab_tmp`（**必须在本地 NTFS**；
> E 盘是 exFAT，`os.makedirs` 直接 `WinError 1`），跑完自行清理。

---

## 九、鉴别力边界（必读）

> **A/B 只能证明"两版行为等价"，不能证明"改动落点正确"。**

本项 6 处非逐字改动中 **4 处是"`self` 指谁"的落点改动**，
在 `types.MethodType(fn, stub)` 形态下**结构上不可见**（AB12b 已断言+文档化）。
铁律 1 由 `verify_w1_2_e2e.py` E6 覆盖（断言 `t.parent() is pet6`）。

⇒ **三维缺一不可**。详见报告 §5.4 / §5.6 / 第五节。
