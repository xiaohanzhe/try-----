
---

## 第 34 轮续：task #13 存储/配置层（生命周期线）细查与修复（2026-09-22 深夜 → 09-23 凌晨）

### 成果：4 条真缺陷 + 1 条同步修的隐私回归，全部已修 + 锁住
| # | 缺陷 | 严重性 | 触发频率 | 状态 |
|---|---|---|---|---|
| Q1b | `.corrupt.*` 配置备份**从未被收敛**（只剪 `.backup.`） | 中 | 每次配置损坏 | ✅ 修 |
| Q3b | `data_store` 留档固定名 `.old` → **静默覆盖**上一份 | 中 | 每次"目标更新"搬运 | ✅ 修 |
| Q4b | `memory_store` 留档固定名 `memory.old.json` → **覆盖** | **中高** | **每次启动都可能** | ✅ 修 |
| Q5 | 残留 `.migprobe` → `_movable` **恒 False** → 文件永久滞留 | 低（不丢数据） | 极端情况 | ✅ 修 |
| R1 | 修 Q4b 后隐私 `reset_all` **漏删时间戳留档**（旧记忆残留） | 高（若漏修） | 隐私清理时 | ✅ 同步修 |

### 修法要点
- **Q1b**：抽 `_prune_by_prefix(prefix, keep)`，`_prune_old_backups` 对
  `('.backup.', '.corrupt.')` **两类分别**收敛（各自独立计数）。
- **Q3b/Q4b**：新增 `_archive_name(path)` / `_rollback_path(target_dir)` ——
  **首选仍是约定名**（`.old` / `memory.old.json`，模块 docstring 对用户写明的契约），
  **被占用时**退到 `<约定名>.<ts>`。轮转语义 = 约定名永远是最新一次落选者。
  连带修 `_copy_verified`：`==` 精确比对 → `startswith`（否则漏判带后缀的那批）。
- **Q5**：`_movable` 动 `os.rename` **之前**先清残留 `.migprobe`；清不掉才判不可搬。
- **R1**：`reset_all` 枚举 `startswith(ROLLBACK_FILENAME + '.')` 一并清。

### ★★ 三条方法论（比缺陷本身值钱）
1. **"当年只修了一半"是常见形态**：Q1b 与该函数注释里**自己记着**的
   "程序目录积压 106 个 `config.json.backup.*`，纯垃圾"**是同一类问题** ——
   修的时候只覆盖了自己想到的那个前缀。
   ⇒ **修"堆积/收敛"类问题时，必须枚举所有会落同类文件的前缀**，别只修眼前这一个。
2. **"修 A 引入 B"必须回头查**：Q4b 改留档命名策略 → 立刻要查**所有读/删留档的地方**
   （`_copy_verified` 的精确比对、`memory_system.reset_all` 的精确删除）。
   ⇒ **改命名策略 = 全仓库找引用点**，漏一个就是一个新 bug（R1 就是这么冒出来的）。
3. **体检脚本的"还原判定"也会说谎**：`_mutcheck_store.py` v1 报
   "还原逐字节一致：False" 而终检 `rc=0 pass=17`。v2 改用**体检前的快照副本**
   做参照系（不再拿内存字符串比对），问题归零。
   ⇒ 复述铁律：**核验失败时，先怀疑核验，再怀疑被测物。**

### 回归锁与体检
- 第 29 套件 `round34_store_config`（**17 项**，`offscreen: False`，全部调产品真函数）；
  沙箱一律本地 NTFS `tempfile.mkdtemp()`（E 盘 exFAT 不当探针沙箱）。
- **鉴别力体检 4/4 全抓破坏**：逐条回退 Q1b/Q5/Q3b/Q4b → 报红 **2 / 1 / 2 / 2** 项 `rc=1`；
  还原后逐字节一致、17/17 PASS。（`18_鉴别力体检_store.txt`）

### G2 / 真机
- 全量 G2：**PASS=1427 FAIL=0，29 套件全 IDENTICAL，rc=0**（新套件首次建基线 `BASELINE`）。
- 真机：`src/main.py` 启动 **40s** 存活、**零 Traceback / 零 ERROR / 零 Logging error**；
  日志正确落 `E:\RalseiMemory\logs\ralsei_pet.log`（vault 优先有效）。

### 复核成立、未改
`data_store` import 期零磁盘操作 + `lazy_log` 断环；`_is_writable_dir` 快路径**不落文件**
（避开沙箱同路径删除配额 —— 第 13 轮 11 个假 DIFF 的真凶）；`_save_config` 原子写 +
`set`/`update`/`reset_config` 三处快照回滚；vault↔staging 迁移五条安全约定。

### 报告 / 记忆
- 报告新增 **§十三**（13.1 速览 / 13.2 Q1b / 13.3 Q3b+Q4b / 13.4 Q5 / 13.5 R1 /
  13.6 复核成立 / 13.7 回归锁与鉴别力 / 13.8 G2+真机），头部 G2 数字同步更正。
- 详版追加 **§23.11**。

### 下一步（按计划推进，不停下请示）
- **task #14**：交互 / 拖拽 / 点击基础代码深度严查（`desktop_interaction.py` 2974 行最大，
  `pet_interaction.py` 364 行、`command_manager.py` 200 行）。
