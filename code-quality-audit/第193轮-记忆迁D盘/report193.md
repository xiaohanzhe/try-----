# 第193轮报告：记忆库从 E 盘迁到 D 盘

日期：2026-11-17 22:00–22:12
起因：§201.3 两件待决之一（用户「都行」⇒ 由我拍板先做迁移，理由：E 盘仍在持续损坏，晚一天多丢一天数据）

---

## 0. 一句话结论

记忆库已落到 `D:\RalseiMemory`（45 个正常件 + 39 个污染件归档），用户级环境变量
`RALSEI_MEMORY_DIR=D:\RalseiMemory` 已生效，产品函数 `find_device_dir()` 与
`MemorySystem` 实测都读 D 盘、读出 3 条 fragment（不是回落空壳）。
**E 盘一个文件都没删、没改**。两件待决的另一件（只存关键词）未动。

---

## 1. 执行中发现的新情况（比迁移本身重要）

**`E:\RalseiMemory\memory.json` 已经又一次被 `USBC` 污染。**

| | §201.2 记录（11-16） | 本轮实测（11-17 22:05） |
|---|---|---|
| 污染文件数 | 38 / 81 | **39 / 81** |
| `memory.json` | 已从桌面兜底复制回来，sha1 `6e6c25146e87` | **头 `55534243`（USBC），JSON 解析失败，sha1 `ba4b03d848cd`** |

也就是说：§201 那次「抢救成功」**已经被坏点再次毁掉**，而且长度仍是 10725 B
（长度不变、内容被整份替换）—— 与 §201 记的「整份被替换」指纹一致。

⇒ 结论：**E 盘不是"已经坏过一次"，而是"还在持续坏"**。迁移是止损，不是善后。

### 污染分布（本轮实测）

| 类别 | 污染数 | 说明 |
|---|---|---|
| `npc_memory\*.json` | **22 / 22 全部** | ralsei / kris / lancer / noelle / queen / asgore … 无一幸免 |
| `logs\ralsei_pet.log*` | 8 | 11-04~11-10 归档 + 当前日志，约 2.9 MB |
| `memory.old.json.*` 三份历史备份 | 3 | 357 KB / 62 KB / 44 KB |
| 状态文件 | 5 | `ghost_state.json` / `motion_progress.json` / `npc_errands.json` / `npc_life.json` / `memory.json` |

**不可恢复**：这批坏件的 JSON 关键词零命中，不是"坏了头几个字节"。

---

## 2. 可用记忆的裁决

四份候选逐份验过（`_evidence/fallback_candidates193.txt`）：

| 候选 | 结果 | saved_at |
|---|---|---|
| 桌面兜底 `C:\Users\23002\Desktop\memory\memory.json` | ✅ JSON OK / 10725 B / `6e6c25146e87` / frag=3 / assoc=11 | **1794019045** ← 最新 |
| `E:\RalseiMemory\memory.old.json` | ✅ JSON OK / 9996 B / `9827fe82ac58` | 1791197862 |
| `E:\RalseiMemory\memory.old.json.1791273965` | ✅ 同上（副本，sha1 相同） | 1791197862 |
| `E:\RalseiMemory\memory.json` | ❌ USBC 污染 | — |
| 项目内 `ralsei_pet\memory.json` | ✅ 但是 537 B 空壳（frag=0） | — |

⇒ 用桌面兜底那份作主记忆。

---

## 3. 迁移方案与执行

工具 `_tools/migrate193.py`，四条硬约束：

1. **不删源**：E 盘不删、不改名、不改写。
2. **坏件不搬家**：头 4 字节 `USBC` ⇒ 进 `D:\RalseiMemory\_corrupt_archive\<原相对路径>`，原样留档。
3. **逐文件 sha1 读回校验**：写完重新读一遍比对，不信 `copy` 的返回值。
4. **幂等**：目标已存在且内容一致 ⇒ 跳过（同一条命令跑两次结果相同）。

### 结果

| 项 | 数量 |
|---|---|
| 复制成功 | 43（42 正常件 + 主记忆 1 份） |
| 污染归档 | 39 |
| 失败 | **0** |
| 首轮写入 | 22,539,775 B |

### 幂等复跑（第二次）

```
复制成功 = 0
已一致跳过 = 82
污染归档 = 0
失败 = 0
本轮写入字节 = 0
=== 判定 = OK ===
```

⇒ 零重复写入、零覆盖，幂等成立。

### 最终状态（`_evidence/dst_snapshot193.txt`）

- 正常件 **45**（43 + 产品自己生成的 `memory.old.json.1794924574` 备份）
- 归档坏件 **39**
- 总字节 **22,550,741**
- 主记忆 `memory.json`：10,725 B / sha1 `6e6c25146e87` / USBC=False / frag=3 / assoc=11

---

## 4. 验证：13 项全绿（`_evidence/verify193_output.txt`）

观察量全部由**产品自己的函数**给出，不是脚本自造：

| 类别 | 判据 | 结果 |
|---|---|---|
| 配置 | 用户级变量落在 `HKCU\Environment` | PASS |
| 正控制 | `find_device_dir(create=False)` == `D:\RalseiMemory` | PASS |
| 内容 | `memory.json` 非 USBC / 可解析 / frag=3 / assoc=11 | PASS ×4 |
| 负控制 A | 变量指 X ⇒ 返回 X；指 Y ⇒ 返回 Y；X≠Y 且都≠D | PASS ×4 |
| 负控制 B | `RALSEI_MEMORY_DEVICE=off` ⇒ 返回 `None`（走桌面兜底分支） | PASS |
| 产品级 | `MemorySystem` 实加载 ⇒ `fragments` 长度 = 3 | PASS |

### ★ 中途有一格报红，是判据错、不是产品错

v1 的负控制 B 写成「清掉变量后不该再指向 D」，**实测报红**。
读源码后确认是产品**有意设计**：

```python
# memory_store.py:150
dir_exists = os.path.isdir(target)
if not label_hit and not dir_exists:
    continue
```

设备根下只要已经有 `RalseiMemory` 目录，就算「上次就是它」（卷标被改也认得出）。
我建出 `D:\RalseiMemory` 之后，它本身就成了证据 ⇒ 清变量仍返回 D。

⇒ 判据前提本身是假的。改成成对控制（X/Y 两个不同路径、再加 `DEVICE=off` 分支），
这才是真有鉴别力的写法。**没有改产品代码一行。**

★ 顺带得到一个好消息：`D:\RalseiMemory` 目录一旦存在，**即使环境变量丢了，
产品也会自动认回 D 盘**。迁移自带一层兜底。

---

## 5. 副作用（必须交代）

跑 `MemorySystem` 验证时，产品执行了 `migrate_from_fallback()`：

```
记忆已从桌面搬入设备目录: {'moved': True, 'removed_fallback_file': True, ...}
```

⇒ **`C:\Users\23002\Desktop\memory\memory.json` 被产品自己删掉了**（桌面目录现在只剩一个
0 字节的 `_wtest.txt`）。这是产品既有约定（copy → verify → 删源），不是我手动删的；
但我在方案里说的是「只读验证」，这一点没预告到，如实记下。

**数据没丢**：D 盘那份已 sha1 核验为 `6e6c25146e87`。

为补回「只有一份」的单点风险，已加冷备：

```
D:\_bak\ralsei_memory_193\memory.json      10725 B  sha1 6E6C25146E87（与源一致）
D:\_bak\ralsei_memory_193\memory.old.json   9996 B  sha1 9827FE82AC58（与源一致）
```

---

## 6. 回退方法

任一步都可退，且不依赖 E 盘：

1. **退出 D 盘**：删掉用户级变量
   `[Environment]::SetEnvironmentVariable('RALSEI_MEMORY_DIR',$null,'User')`
   ⇒ 产品会走设备探测。**注意**：因为 `D:\RalseiMemory` 目录仍在，它仍会认 D
   （见 §4 末尾）；要彻底退出还需把该目录改名。
2. **回到 E 盘**：把变量设为 `E:\RalseiMemory` 即可（E 盘原件未动）。
3. **主记忆回滚**：从 `D:\_bak\ralsei_memory_193\memory.json` 复制回
   `D:\RalseiMemory\memory.json`。

---

## 7. 遗留 / 未做

- **`npc_memory` 22 份全灭**：E 盘原件是污染件，归档在 `_corrupt_archive\npc_memory\`，
  **不可恢复**。这是本轮之前就发生的事，不是迁移造成的。
- **日志 11-04~11-10 全灭**（约 2.9 MB），同样不可恢复。
- **「只存关键词」未动**：§201.3 第二件待决，要改 `_note_memory` 的写入形态，
  属改码，需先跑 G2 全量回归。
- **E 盘原目录未清理**：按「只禁用不删」口径原样留着，等用户确认后再处置。
- **已运行中的进程读不到新变量**：桌宠 App 需重启才切到 D 盘。

---

## 8. 证据清单

| 文件 | 内容 |
|---|---|
| `_tools/probe_e193.py` | E 盘只读探测（逐层兜异常） |
| `_tools/migrate193.py` | 迁移（只增不删 / 幂等 / sha1 读回校验） |
| `_tools/verify193.py` | 产品级验证（成对正负控制） |
| `_tools/snapshot193.py` | D 盘最终快照 |
| `_evidence/e_probe193.txt` | 迁移前 E 盘 81 文件明细 |
| `_evidence/fallback_candidates193.txt` | 5 份候选比对 |
| `_evidence/migrate_rerun_idempotent193.txt` | 幂等复跑日志 |
| `_evidence/dst_snapshot193.txt` | D 盘最终状态（含主记忆单列断言） |
| `_evidence/verify193_output.txt` | 13 项验证输出 |
