# 第195轮报告（第 1 批）：NPC 一人一库

日期：2026-11-17 23:38–00:05
起因：用户「ralsei 和其他人一样，是同级的那种，也就是现有 ralsei 的功能需要在所有人身上都能看到，
但，也要根据具体情况来看」；记忆库落点由用户裁定 `D:\RalseiMemory\npc_mem\<id>\`。

---

## 0. 一句话结论

NPC 现在有**自己的长期记忆**了：一人一个目录、一人一个 `memory.json`，与 Ralsei 同级但**物理分开**。
不会串味（Lancer 在教室盘算的事，Ralsei 想不起来）。性能上**懒加载 + LRU 上限 6**，
常驻内存只跟"在场几个人"同阶，与 96 个人无关。

判据 23 条全绿，**变异 4/4 全抓**；全量回归 **192/192 IDENTICAL、PASS=8456、FAIL=0**。

---

## 1. 两个必须做对的设计（做错就是白做）

### 1.1 为什么不能用"一个大库 + owner 字段"

`recall()` 对关键记忆的匹配面是：

```python
hay = t
if str(k.get('kind')) == 'inner':
    hay = t + ' ' + str((k.get('meta') or {}).get('where') or '')
for kw in _probe:
    if kw and kw in hay:
```

**不含 `who`**。所以混在一个库里，Lancer 在教室"盘算"过一次，问"教室"时 Ralsei 也会想起来 ——
`who` 字段只是存着好看，**拦不住**任何东西。

`npc_persona.MiniMemory` 早在自己的注释里写过同一个结论：
「不是"一个大文件按 id 分桶"：分桶写法只要有一处忘了带过滤就会串」。

⇒ 走物理分开：`<记忆根>/npc_mem/<id>/memory.json`。读谁的记忆，在文件系统层面就只碰得到谁的数据。

### 1.2 `_legacy_file` 是暗雷

`MemorySystem` 有个"升级不失忆"的机制：新位置没有记忆时，从仓库里的
`ralsei_pet/memory.json` 继承。

NPC 的空库第一次加载时，**会走同一条路** ⇒ 每个 NPC 一开口就自带 Ralsei 的旧记忆。

⇒ 指定 `memory_dir` 时**必须**把 `_legacy_file` 置 `None`（B3 钉住，B3b 是它的反向控制：
本体那条路必须**仍有** legacy，否则 B3 可能只是"属性不存在"而恒真）。

---

## 2. 实现

| 文件 | 改动 |
|---|---|
| `modules/people_memory.py` | **新增**（`PeopleMemoryBank`：懒加载 + LRU + 一人一目录） |
| `modules/memory_system.py` | `__init__(parent, memory_dir=None)`；指定目录时不做兜底搬运、不继承 legacy |
| `modules/dialogue_ui.py` | 新增 `_note_person_memory()`；`add_npc_line` 在 `if char_id:` 后调用 |
| `src/main.py` | 初始化 `self.people_memory`（失败不拖垮启动） |

### 2.1 性能怎么顾的（用户原话：「要么来个 5090 都跑不动这程序的算力」）

一个 `MemorySystem` 要加载 JSON、建倒排索引、建关联图，不是轻对象。96 个人一人一个常驻 = 必卡。所以：

1. **懒加载**：`of(npc_id)` 才建库，没人跟他说话就不存在；
2. **LRU 上限 6**：超了先把最久没用的 `save_memory()` 再释放。6 的依据是一屏不会同时有 6 个人说话；
3. **单库内部**的上限仍由 `MAX_KEYS` / `INNER_KEYS_MAX` / 片段裁剪负责，不重复设限；
4. `default_root()` 按 `RALSEI_MEMORY_DIR` 值**缓存**：设备探测只做一次（`MemorySystem(self)` 已经探过一次）。

### 2.2 NPC 的内在活动要从两个地方摘

Ralsei 那条路从 `message` 正文里摘 `（...）`。但 NPC 的括号**在 `_clean_ai_reply` 阶段就被护栏
删出正文、只留在 sink（`_acts`）里**了 —— 而 sink 恰恰是 NPC 的主路径。

⇒ `_note_person_memory` 两个地方都摘，并用 `seen` 去重（同一句里同一个动词只记一次）。

### 2.3 只记有 `char_id` 的

没有 `char_id` 就不知道是谁说的。宁可记不住，也不记错人（`if char_id:` 守卫，D4 钉住）。

`people_memory.safe_id` 还要求"清洗后**必须等于原值**"：`'../etc'` 洗一洗会变成 `etc`，
放行就等于把这段非法输入悄悄当成了另一个人 ⇒ 返回 `''`，调用方安静跳过。

---

## 3. 判据（23 条）与变异

| 段 | 条 | 内容 |
|---|---|---|
| A 路径与 id | 5 | 合法 id 原样 / 非法 id 一律空串（负控制）/ 分母闸 / 一人一目录 / root=None 不伪造路径 |
| B 隔离 | 5 | **B1 行为级不串味** / B2 自写自问必命中（B1 的负控制）/ B3 `_legacy_file is None` / B3b 本体仍须有 legacy（B3 的反向控制） |
| C 性能 | 5 | 超上限淘汰 / LRU 顺序 / **淘汰后数据还在** / C4 上限调大不淘汰（负控制）/ 懒加载 |
| D 接线 | 5 | `add_npc_line` 真调了 / 取的是 `people_memory.of` 而非本体 `memory_system` / 两处摘 inner / `if char_id:` 守卫 / main 里真**赋值** |
| E 兼容 | 4 | `memory_dir` 必须是**可选**参数（老调用方零影响）/ 分母闸 / 名字无重复 / 源码 sha1 |

**变异 4/4 全抓**（`_tools/mutate195.py`）：

| 变异 | 结果 |
|---|---|
| 去掉 legacy 防护 | B3 红（1 条）✔ |
| 去掉 LRU 淘汰 | C1/C2 红（2 条）✔ |
| 断掉 `add_npc_line` 接线 | D1 红（1 条）✔ |
| 只改注释（无害） | **红 0** ✔ |

★ 变异当场抓出**我自己一条假变异**：第一版把 `_legacy_file = None` 换成
`os.environ.get('RALSEI_LEGACY_MEMORY')` —— 那个变量没设时本来就返回 `None`，等于没改，
B3 当然不红。换成硬编码字符串才真正破坏到被测性质（**夹具不保真 = 报假问题**，又一次同款）。

---

## 4. 全量回归

```
套件=192   PASS=8456   FAIL=0   192/192 IDENTICAL   EXIT=0
```

第一遍有 6 个 DIFF，逐份机器核对后**意外差异 0**：

| 套件 | 差异 | 归因 |
|---|---|---|
| `round5_smoke` | `待导入模块数 77→78` + 新增 `people_memory` | **新增零依赖模块必撞的闸**（记忆里记过） |
| `check107` / `check191` | 行号位移 | `main.py` 加了 12 行 import |
| `check182` / `check185` / `check186` | `8125→8137`、`7539→7551`、`1800→1812` | 同上，**全部 +12，完全一致** |

---

## 5. 这一批**没做**的（下一批）

| 项 | 为什么没在本批 |
|---|---|
| **NPC 表情动画**（用户明确要求"不能关"） | 要先盘清可用素材与"模板复制"的具体做法；`play_expression_anim` 现在是 `if char_id: return False`，改它要动宿主 + 每个 NPC 的帧源 |
| **记错机制（B）** | 作用在 `recall_text` 的 inner 分支，本批刚把 NPC 的库建起来，下一批一起做（Ralsei 与 NPC 共用同一渲染入口，一处改全员生效） |
| 口癖补齐（70 份人设） | 纯文本批处理，独立 |
| NPC 情绪 / 关系 | 要先定"对谁"（对玩家？对彼此？），需设计 |

---

## 6. 证据

| 文件 | 内容 |
|---|---|
| `_evidence/npc_inventory.md` | 96 人逐人素材明细（人设/立绘/表情/作品/活动范围） |
| `_evidence/regress195_full.txt` | 第一遍全量（6 个 DIFF，含归因用） |
| `_evidence/regress195_full_v2.txt` | 终检：192/192 IDENTICAL、PASS=8456、FAIL=0 |
| `plan195.md` | 能力矩阵 + 分批计划（第 1 批已交付，其余待做） |
| `_tools/check195.py` / `mutate195.py` / `inventory195.py` | 判据 / 变异 / 盘点 |
