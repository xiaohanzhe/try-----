
---

## 十三、存储 / 配置层细查（task #13，生命周期线）

**范围**：`data_store.py`（302 行）、`memory_store.py`（342 行）、`config_manager.py`（578 行）、
`logger_utils.py`（212 行，第 34 轮已修 F5）、`lazy_log.py`（55 行）。
**方法**：全文通读 + **全部调用产品真函数**的受控探针（沙箱一律用本地 NTFS `tempfile.mkdtemp()`，
E 盘 exFAT 不当探针沙箱）。

### 13.1 结论速览

| # | 问题 | 严重性 | 触发频率 | 处置 |
|---|---|---|---|---|
| Q1b | `.corrupt.*` 配置备份**从未被收敛** | 中（磁盘垃圾永不自愈） | 每次配置损坏 | **已修** |
| Q3b | `data_store` 留档名固定 `.old` → **静默覆盖** | 中（丢历史留档） | 每次"目标更新"搬运 | **已修** |
| Q4b | `memory_store` 留档名固定 → **静默覆盖** | **中高**（丢记忆留档） | **每次启动都可能** | **已修** |
| Q5 | 残留 `.migprobe` → `_movable` 恒 False | 低（不丢数据，只滞留） | 极端情况 | **已修** |
| R1 | 修 Q4b 引入的时间戳留档**破坏隐私 reset** | 高（若漏修） | 隐私清理时 | **同步修** |

### 13.2 Q1b：`.corrupt.*` 备份一份都不清（真缺陷）

**源码**：`config_manager._prune_old_backups()` 原先 `prefix = f"{self.config_file}.backup."`
—— **只匹配 `.backup.`**。而 `_load_config` 在配置损坏时会写下 `<config>.corrupt.<ts>`（L192）。
⇒ **`.corrupt.*` 从不参与剪枝**。

**受控取证**（`16_存储配置层探针.txt` Q1 段）：造 15 个 `.backup.*` + 15 个 `.corrupt.*`，
调产品真函数后实测 **`.backup.*=10`（已收敛）/ `.corrupt.*=15`（一份没清）**。

**触发路径真实可达**：配置一旦被同步工具 / 手改写坏一次就留一个，**永不自愈**。
这与该函数注释里自己记的"程序目录里积压了 106 个 `config.json.backup.*`，纯垃圾"
**是同一类问题 —— 当年只修了一半**。

**修法**：抽 `_prune_by_prefix(prefix, keep)`，`_prune_old_backups` 对
`('.backup.', '.corrupt.')` **两类分别**收敛（各自独立计数，互不挤占配额）。

### 13.3 Q3b / Q4b：留档名固定 → 静默覆盖（真缺陷，两条同源）

**`data_store.migrate_from_staging`**（原 L244）与 **`memory_store.migrate_from_fallback`**（原 L278/L286）
都用**固定名**做留档：前者 `dst + '.old'`，后者 `memory.old.json`。
`shutil.copy2` 到已存在的路径会**直接覆盖** ⇒ 第二次有落选者时，**第一次的留档永久消失**，
而调用方毫无察觉（`result['moved']` 两条记录长得几乎一样）。

**受控取证**（同文件 Q3b / Q4b 段）：
- `data_store`：round2 后 `.old` 内容从 `STAGING-OLD` 变成 `STAGING-OLD-2` → 第一份没了；
- `memory_store`：round2 后留档从 `desktop1` 变成 `desktop2` → 同理。

★ **Q4b 的触发频率远高于 Q3b**：`migrate_from_fallback` 由 `memory_system` 在
**每次启动**时调用（`memory_system.py:79`）；只要反复出现"设备版更新、桌面版落选"，
每一轮都会把上一轮留档覆盖掉 —— **只有最后一次落选者能存活**。

**修法**（保持"用户可见的约定名"这一产品契约）：
- 新增 `_archive_name(path)` / `_rollback_path(target_dir)`：**首选仍是约定名**
  （`.old` / `memory.old.json`），**被占用时**退到带时间戳的 `<约定名>.<ts>`；
- 轮转语义 = **约定名永远是最新一次落选者**，更早的在 `<约定名>.<ts>` 里；
- 连带修正 `_copy_verified` 的判据：`basename == ROLLBACK_FILENAME` 精确比对会**漏掉带后缀的那批**，
  改为 `startswith`。

**为什么不用"直接改名加时间戳"**：约定名在模块 docstring 里是对用户写明的
（"落选的那份挪成 `memory.old.json` 留档"），改成纯时间戳会破坏这个可见契约。

### 13.4 Q5：残留 `.migprobe` 把文件**永久**钉在中转站（真缺陷）

**源码**：`data_store._movable(src)` 用 `os.rename(src, src + '.migprobe')` 试改名来判断占用。
其"改回来"那步失败时**自己注释里承认**会残留 `.migprobe`（"极罕见：回不去就把探针当正式文件留着"）。
而**残留之后**：每次再来改名，`os.rename` 都因**目标已存在**抛 `OSError` →
`_movable` **恒返 False** → `migrate_from_staging` 每轮把它列进 `skipped`
→ 该文件**永远搬不进最终存储**，`staging_has_data()` 也恒为 True
（"本地只作中转站"的口径就此落空）。

**受控取证**（同文件 Q5 段）：造残留 `.migprobe` 后 `_movable` 返回 `False`，源文件仍在。

**修法**：动 rename **之前**先清残留探针；清不掉才判为不可搬（保守，不误搬被占用的文件）。

### 13.5 R1：修 Q4b 引入的**隐私回归**（同步修，重要）

`memory_system.reset_all()` 是**隐私口径**（"清空**全部**记忆，**含留档副本**"，供
"退出时清理数据"使用）。它原先精确删 `memory.old.json` —— 而 13.3 的修法会产生
`memory.old.json.<ts>` ⇒ **改完 Q4b 后，reset 会漏删时间戳留档，磁盘上残留旧记忆**。

⇒ **同步修**：`reset_all` 枚举同前缀（`startswith(ROLLBACK_FILENAME + '.')`）一并清掉。
（★ 这是"修 A 引入 B"的典型 —— **改留档命名策略必须回头检查所有读/删留档的地方**。）

### 13.6 复核成立（未改）

- `data_store` **import 期零磁盘操作**（第五轮冒烟前提），且被 `logger_utils` 反向依赖时
  一律走 `lazy_log.LazyLogger` → 初始化环已断（第 12 轮锁 `round12_store` 覆盖）；
- `memory_store._is_writable_dir` 两级判定：快路径 `os.access` **不落文件**，
  避开宿主沙箱"同路径删除配额"（第 13 轮 11 个假 DIFF 的真凶），**修复有效**；
- `config_manager._save_config` **原子写**（`.tmp` + `os.replace`）+ 失败回滚内存，
  `set()` / `update()` / `reset_config()` 三处都做快照回滚，**一致**；
- `vault → staging` 的迁移五条安全约定（先探测可搬 → copy → **校验长度** → 删源 → 只删空目录）
  与 `memory_store` 同源，**逐条复核成立**。

### 13.7 回归锁与鉴别力

- 新增**第 29 套件** `round34_store_config`（17 项，全部调产品真函数）；
- **鉴别力体检 4/4 全部抓破坏**（`18_鉴别力体检_store.txt`）：
  逐条回退 Q1b/Q5/Q3b/Q4b → 分别报红 **2 / 1 / 2 / 2** 项、`rc=1`；还原后逐字节一致、17/17 PASS。

> ⚠️ 体检 v1 报的"还原逐字节一致：False"是**核验判据自己说谎**的又一例。
> v2 改用**体检前的快照副本**做参照系（不再拿内存字符串），归零。
> 通则复述：**核验失败时，先怀疑核验，再怀疑被测物。**

### 13.8 本线 G2 / 真机

- 全量 G2：**PASS=1427 FAIL=0，29 套件全 IDENTICAL，rc=0**（新增 `round34_store_config` 17 项，
  首次建立基线）；
- 真机：`src/main.py` 启动 **40s** 存活、峰值 RSS **192.3MB**、
  **零 Traceback / 零 ERROR / 零 `Logging error`**；
  日志正确落在 `E:\RalseiMemory\logs\ralsei_pet.log`（vault 优先路径有效）。
