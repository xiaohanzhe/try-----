# W1-6 验证证据（FileSheetController）

日期：2026-09-21 ｜ 基线：`70e01c0` ｜ 载体：`ralsei_pet/modules/file_sheet_controller.py`（469 行）

---

## 1. 探针运行结果（三跑复现）

| 探针 | 结果 | 用时 |
|---|---|---|
| `verify_w1_6_unit.py` | **PASS=59 FAIL=0**（exit 0） | <2s |
| `verify_w1_6_e2e.py` | **PASS=53 FAIL=0**（exit 0） | ~8s |
| `verify_w1_6_ab.py` | **PASS=57 FAIL=0**（exit 0） | ~12s |
| **合计** | **169 PASS / 0 FAIL** | — |

复跑一轮，三者结果稳定（59/53/57）。

---

## 2. 搬运保真度（逐字节）

```
306 行方法体 vs 「源块经 _log. -> self._log_(). 变换」
md5 = 07dfdc72e1b160fd6b62eb3a6d5da35a   （两侧相同）
```

## 3. 改写计数（口径：只数**代码**，排除 docstring）

| 量 | 值 | 说明 |
|---|---|---|
| `_log.` → `self._log_().` | **12** | 代码口径 |
| `QTimer(self)` | **0** | 本项无铁律 1 |
| 裸 `_log_()` 调用 | **0** | 铁律 6 |
| 裸 `os.`（方法体内） | **15** | 铁律 7；靠**模块级** `import os` 解析 |
| 全文件 `self._log_().` | **13** | = 12 实码 + **1 docstring 讲解**（探针 E8h 显式证明 docstring 噪声存在） |

模块级 import = `{'logging', 'os'}`；方法体内局部 import = `{'os', 're', 'win32com.client'}`（**保持局部**）。

## 4. 源码结构

| 项 | 改前 | 改后 |
|---|---|---|
| `main.py` 行数 | 9375 | **9019**（净 −356） |
| `RalseiPet` 方法数 | 175 | **170** |
| 新模块行数 | — | **469** |
| 新模块方法数 | — | **8**（4 业务 + 4 基础设施） |

行数对账：`57（死代码）+ 143 + 39 + 52 + 69 = 360` → 净 −356，差 4 = 新增接线/注释行。

## 5. 宿主接线三处

```
L339  from modules.file_sheet_controller import FileSheetController
L506  _CONTROLLER_ATTRS = ('games', 'video', 'spell', 'hide_seek', 'file_sheet')
L755  self.file_sheet = FileSheetController(self)
```

## 6. G1 零引用筛查（W1-6 组）

| 方法 | 引用点 | 判定 |
|---|---|---|
| `handle_file_operation` | 1（`dialogue_ui.py` L1724） | 活 |
| `fix_excel_format` | 1（控制器内 L280） | 活 |
| `fill_names_in_excel` | 1（控制器内 L243） | 活 |
| `_open_desktop_item_by_name` | 经 `handle_file_operation` 调用 | 活 |
| `create_person_name_table` | **0** | 死代码 → **已删** |
| `check_excel_table_needs` | 0 | 第六轮已删（扫描器清单残留） |

## 7. G2 全量回归

```
合计：PASS=1164 FAIL=0  套件=24   （全部 IDENTICAL）
round5_smoke 预期变化：待导入模块数 35 -> 36（+file_sheet_controller）→ --update --only 合并重固
```

## 8. 判据边界（防误判）

- **铁律 7 由 e2e 覆盖**（A/B 结构上看不见模块级 `os`）。
- **铁律 1 本项不存在**（无 `QTimer` 站点）。
- **铁律 2/3 无触发路径**（4 方法均不写宿主状态）；护栏保留为同构纪律，鉴别力由 unit V3/V4 人为赋值覆盖。
- A/B 的"没差别"**不能**用来否定上述铁律。
