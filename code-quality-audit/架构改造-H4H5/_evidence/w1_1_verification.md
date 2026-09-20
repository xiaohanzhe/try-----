# W1-1 验证留痕（`SpellFlowController` 抽取）

**日期**：2026-09-20
**项**：H4/H5 Wave 1 第 3 项 — 从 `RalseiPet` 抽出 `SpellFlowController`
**结论**：✅ 三维校验 98 PASS / 0 FAIL；G2 24/24 `IDENTICAL`（1162 PASS / 0 FAIL）

---

## 1. 两侧源码 md5（A/B 前置：必须不同）

| 侧 | 文件 | md5 |
|---|---|---|
| **A（父版本）** | `HEAD:ralsei_pet/src/main.py` | `5d325a1b2f03507437c95e3c1152321d` |
| **B（当前）** | 工作区 `ralsei_pet/modules/spell_controller.py` | `7c9f83da3ba49e65e8b7350bd700b86f` |

> **A ≠ B 已断言通过**（相同则 `SystemExit(3)` —— 探针退化防护，W1-4 报告第五节有先例）。
>
> **注**：本项 A、B 是**两个不同文件**（父版 `main.py` vs 当前控制器）。
> 搬运类改造的旧/新实现本来就不在同一文件里；写成"同文件取 HEAD / HEAD~1"是错的。
>
> 上面 B 的 md5 是**探针口径**（`git show` 的文本按 UTF-8 编码后取 md5，
> 用于和 A 比"是否同一份东西"）。新模块**文件本体** 29,795 B / 506 行 / LF（无 CRLF），
> 与探针口径的 md5 不同属正常（文本编码往返 vs 原始字节）。

## 2. 方法搬运清单（4 方法 / 290 行）

| 方法 | 父版本行号 | 行数 | 改写处 |
|---|---|---|---|
| `_spell_interrupted_reason` | 9152 | 26 | — |
| `_tick_spell_flow` | 9179 | 183 | 8 × `_log.` → `self._log_().` |
| `_cast_spell_then` | 9363 | 44 | 2 × `_log.` → `self._log_().` |
| `_start_open_with_spell` | 9408 | 37 | 1 × `_log.` → `self._log_().` |

改写命中总数 **11**，已在生成期断言。

`main.py` 行数 9992 → 9713（−279）；方法数 191 → 187。
删除区间：L9152–9444。

## 3. 三维校验结果

### A 逐字等价 — `verify_w1_1_unit.py`

```
W1-1 单元级：共 26 项，通过 26，失败 0
exit=0
```

覆盖：X1–X4（加载 + A≠B md5 哨兵）、V1a/V1b（逐方法体逐字等价 + 改写计数 0/8/2/1 = 11）、
V1c/V1d、V2a–c（反向控制）、V3a（**只扫模块级**导入 —— `ast.walk` 会误抓方法内局部
`import shutil`，已改成只遍历 `t.body`）、V3b/V3c、V4（预声明扫描面 = 整个类体 − 搬运方法）、
V5a–d（接线）。

### B 行为等价 — `verify_w1_1_e2e.py`

```
W1-1 e2e：共 38 项，通过 38，失败 0
exit=0
```

关键组：

| 组 | 内容 | 现场值 |
|---|---|---|
| E1 | 构造不 `RecursionError` | — |
| E2/E2x | 转发壳两个方向 | — |
| E3a/E3b | **无状态劈裂** | 控制器 `__dict__` == `{'p'}`；12 个 `_spell_*` 全落宿主 |
| E4 | `_cast_spell_then` | — |
| E5 | `_start_open_with_spell` | — |
| E6 | 8 次 tick | — |
| E7 | 走动分支**强制构造 `QPoint`** | 逼出坑 3 |
| E8 | **中断路径** | ★ 抓到 P0：修复前 `stage=None` 且 `AttributeError` |
| E9a–f | `_spell_interrupted_reason` 全分支 | — |
| E10 | `Qt(self)` parent 传参哨兵（跨 3 个控制器） | `hits=[]` |
| E11 | 裸 `_log_()` 哨兵 + `self._log_()` 计数 | `count=13`（≥11） |

### C A/B 对照 — `verify_w1_1_ab.py`

```
W1-1 A/B：共 34 项，通过 34，失败 0
父版本 rev = HEAD (md5 5d325a1b2f03)
当前   md5 = 7c9f83da3ba4
exit=0
```

场景：AB4（`_cast_spell_then` left/right）、AB5（`_start_open_with_spell` file/folder）、
AB6（`_spell_interrupted_reason` 8 分支 + 5 个"确实产出原因"哨兵）、
AB7（`_tick_spell_flow` casting×3 / interrupt(drag) / walking×3，含"两侧均无异常"哨兵）。

AB7 `interrupt(drag)` 逐字结果（修复后）：

```
old={'stage': None, 'dir': None, ..., 'err': None}
new={'stage': None, 'dir': None, ..., 'err': None}
```

**两侧都真的跑到了**（`stage` 由 `casting` → `None`）—— 这才叫一致。

### D 全量回归 — `regress/run_all.py`

```
合计：PASS=1162 FAIL=0  套件=24
exit=0
IDENTICAL = 24 / DIFF rows = 0
```

`round5_smoke` PASS=34（原 33，新增 `[ OK ] spell_controller`），
按 H4/H5 规范以 `--update --only round5_smoke` **合并模式**重固；
其余 23 套件哈希逐字节未变。

## 4. G1 零引用筛查（`_evidence/zero_refs.txt`）

| 方法 | 引用点 | 位置 |
|---|---|---|
| `_tick_spell_flow` | 4 | `main.py` L8350；`diag_logic.py` L83/105/108 |
| `_start_open_with_spell` | 3 | `main.py` L8773/8794；`diag_logic.py` L103 |
| `_spell_interrupted_reason` | 5 | `spell_controller.py` L247；`diag_logic.py` L68/106；`diag_spell.py` L59；`diag_real.py` L87 |

**W1-1 块零死代码。**

## 5. 本轮顺带修的存量缺陷

| 文件 | 位置 | 缺陷 | 修法 |
|---|---|---|---|
| `ralsei_pet/modules/video_controller.py` | L426, L505 | 裸 `_log_()` → `NameError`（W1-4 坑 5 的存量，藏在 `except Exception:` 分支里从未被覆盖） | → `self._log_()` |
| `code-quality-audit/第五轮/verify_round5_fixes.py` | L112–155 | 定位器只扫 `main.py` → `AttributeError: 'NoneType' ... .lineno` | `_SEARCH` 扩到 4 个文件；找不到即 `SystemExit` |
| `code-quality-audit/第五轮/smoke_import_round5.py` | L34–44 | 同上 → `IndexError` | 换 `_extract_func_body(fname)` 走 `_CANDIDATES`，失败 `sys.exit(2)` |

> 两条锁的定位器改完后，`round5_verify` 的基线哈希**一个字节都没动** ——
> 证明修复点在定位器、不在产品、也不在基线。

## 6. 现场重跑命令（可复现）

```powershell
Set-Location "C:\Users\23002\Desktop\项目文件夹\try - 副本"
& C:\Python311\python.exe code-quality-audit\架构改造-H4H5\verify_w1_1_unit.py
& C:\Python311\python.exe code-quality-audit\架构改造-H4H5\verify_w1_1_e2e.py
& C:\Python311\python.exe code-quality-audit\架构改造-H4H5\verify_w1_1_ab.py
& C:\Python311\python.exe code-quality-audit\regress\run_all.py
& C:\Python311\python.exe code-quality-audit\架构改造-H4H5\scan_zero_refs.py
```

> ⚠️ 一律用 `C:\Python311\python.exe`（PyQt5/pywin32/bs4/psutil/jieba）。
> ⚠️ **别用 PS 管道捕获原生 stdout**（GBK 有损 → 中文真损坏）；让 Python 自己写 UTF-8。
