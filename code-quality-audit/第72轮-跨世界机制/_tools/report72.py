# -*- coding: utf-8 -*-
"""第72轮报告生成器（自写 UTF-8，避免 PS 5.1 编码坑）。--write 才落盘。"""
import sys, os, io

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE = <repo>/code-quality-audit/第72轮-跨世界机制/_tools  ⇒ 仓库根要上 3 层
ROOT = os.path.join(HERE, '..', '..', '..')
REPORT = os.path.join(ROOT, '第72轮报告-跨世界机制.md')

TEXT = u'''# 第72轮报告 · 跨世界机制（穿行域 RoamScope）

* 轮次目录：`code-quality-audit/第72轮-跨世界机制/`
* 提交：`37317f9`（工作区 12 文件 / +2086 −163）
* 一句话：**给"不同世界的角色在不同世界的兼容性"补上可执行的许可模型**——
  NPC 不再只有一个"我属于哪个世界"的静态标签，而是多了一个"我能去哪"的动态许可（穿行域）。

---

## 一、用户指令（逐字）

> 「继续按你的计划进行，对了**做好不同世界的角色在不同世界的兼容性哦**」

这一句是本轮的**唯一验收点**。它同时落回更早的长需求（仍在生效）：

> 「……因为各个世界观里有重复的角色，**我要求他们能够共存**，而且，**niko 可自由穿行所有世界，
> 其余 ut 及其同人的任务只能在非暗世界穿梭**，并且，**我希望他们是生活在这而不是我走到哪他们加载到哪**……
> 之后不同世界的人一开始也不认识，所以他们也是循序渐进的熟悉起来，当然，**面对不同版本的自己
> 熟悉的会更快，比如 toriel**……还有，**怪物们之间没有身份标识说，你是哪个世界观的，所以那需要自己判断**」

⇒ 本轮做的是其中**最硬、最可执行**的一段：**门控（谁能去哪）**。其余（生活、熟悉、场景反应）登记为
`spec_only`，如实排队。

---

## 二、三个技术判断（本轮的地基）

### 2.1 世界模型补第三档 `foreign`

`light` / `dark` 是 **Deltarune 的语汇**（暗之泉那一侧的二分）。**UT 的地下世界、OneShot 的城市都不是
"暗世界"** —— 它们只是"本作之外的另一个世界"。

第66轮把 61 位跨作品角色的 `home_world` 一律写成 `dark`，那是**当时只有两分的借用**。
本轮补第三档：

```python
WORLD_FOREIGN = 'foreign'   # ★ 本作（Deltarune）之外的世界
```

并把 61 条跨作品 NPC 的 `home_world` 由 `dark` 改为 `foreign`。

★★ **实证这不改变运行时行为**：真正拦人的是 `escape_via_bubble` / `is_dark_only`
（= `DARK_ONLY_IDS + escape_via_bubble`），**不是 `home_world`**。所以补 `foreign` 是
**语义修正，不是行为改动** —— 这一点必须说清楚，否则会被误读成"改了个字就宣称修好了"。

修正后分布：`dark 30 / light 5 / foreign 61`。

### 2.2 穿行域 `RoamScope`：**许可维度**，与 `home_world`（归属维度）**分开**

用户那句话是**许可句**（"**能**自由穿行所有世界 / **只能**在非暗世界穿梭"），
而 `home_world` 回答的是**归属**（"我来自哪个世界"）。两者混用会立刻打架：
Niko 的归属是 OneShot（`foreign`），但他的**许可**是全部世界。

⇒ 必须是**新字段**：

| 档 | 含义 | 本项目当前适用 |
|---|---|---|
| `home`   | 静态归属，不跨世界 | Deltarune 本作 35 位 |
| `non_dark` | 可在**非暗世界**穿梭 | UT 及其同人（Outertale / 黄魂）60 位 |
| `all`    | 自由穿行所有世界 | **仅 `niko` 一人** |

同一套判断也解释了用户为什么单点 Niko：**他是唯一"可自由穿行"的**。

### 2.3 AU 家族 vs 同名：**同名 ≠ 同一人**

> 「**面对不同版本的自己熟悉的会更快，比如 toriel，有 ut 的，三角符文的，黄魂里的，outertale 里的，
> 他们四个会熟悉的很快**」

要落地这句，先得回答"**谁是谁的另一个版本**"：

* **Outertale** 与 **黄魂（Undertale Yellow）** **都是 UT 的同人衍生**
  ⇒ `ut_*` / `hy_*` / `ot_*` 之间同名为「**同一角色的不同版本**」（`has_au = True`）。
* **OneShot** 是**独立作品**，只能算**同名**（`has_au = False`）。

★ 用户点名的 toriel 恰好是**三人**（不是四人）：`ut_toriel` / `ot_toriel` 属 AU 家族，
而 `toriel`（Deltarune 本作）**只是同名**。这一条在 `twin_groups` 里**如实标出**，
没有为了凑"四个人"把 Deltarune 的 Toriel 也算进 AU 家族。

---

## 三、代码面（`ralsei_pet/modules/npc_system.py`，核心文件）

```python
WORLD_FOREIGN = 'foreign'      # ★ 新增

class RoamScope(object):       # ★ 新增（必须定义在 class NpcDef 之前）
    HOME     = 'home'
    NON_DARK = 'non_dark'
    ALL      = 'all'
    ALL_VALUES = ('home', 'non_dark', 'all')
```

四处接线：

1. `NpcDef.__slots__` 增第 **14** 项 `'roam_scope'`。
2. **归一规则**（必须放在 `home_world` 赋值**之后**）：

   ```python
   self.roam_scope = (roam_scope if roam_scope in RoamScope.ALL_VALUES
                      else (RoamScope.NON_DARK
                            if self.home_world == WORLD_FOREIGN
                            else RoamScope.HOME))
   ```
   ⇒ 缺省不是"一刀切"，而是**从 `home_world` 推**：跨作品默认 `non_dark`，本作默认 `home`。
3. `to_dict` / `npc_from_dict` 双向持久化。
4. **`world_gate` 暗世界分支插跨作品判断**（★ **顺序敏感**）：

   ```python
   ch = scene_chapter(scene_id)
   if npc.roam_scope != RoamScope.HOME:
       if ch is not None and ch in npc.chapters:
           return GateResult(True, REASON_OK, 'home_production:%s' % ch)
       if npc.roam_scope == RoamScope.ALL:
           return GateResult(True, REASON_OK, 'roam_all')
       return GateResult(False, REASON_FOREIGN_DARK,
                         '%s 只能在非暗世界穿梭' % npc.name_cn)
   if not npc.chapters:                       # ← 跨作品分支必须排在它之前
       return GateResult(False, REASON_NO_CHAPTERS, ...)
   ```

   ★★ 为什么顺序敏感：UT 侧 NPC 的 `chapters` 是空的（他们的章节号指的是**另一个作品**的章，
   在 Deltarune 的 `scene_chapter()` 下无意义）。**若跨作品分支排在 `chapters` 判空之后**，
   他们会先被"未登记章节"拦掉，**永远走不到跨作品放行**⇒ `non_dark` 档形同虚设。

★ **光世界一侧不用改**：光世界本来就"谁都能去"，用户的许可句约束的是暗世界。

---

## 四、数据面（`ralsei_pet/assets/npc/_registry.json`）

* 96 位 NPC **逐条显式**写 `roam_scope`（不靠缺省偷懒）：
  `home 35 / non_dark 60 / all 1`。
* `home_world` 由 `dark 30 / light 5 / foreign 61`（第66轮是 `dark 91 / light 5`）。
* `source` 里旧句「两作品 `home_world` 一律显式 `dark`（本项目世界模型只有两分）」**已改写**
  为含 `foreign` + `roam_scope` + 分区计数的说明。

---

## 五、契约面（`ralsei_pet/assets/npc/_crossworld.json`，新建 12.4 KB / 7 段）

| 段 | 内容 | status |
|---|---|---|
| `roam` | 门控实现 + 三档取值 + 分布 + `all_ids` + 为什么补 foreign | **wired** |
| `twin_groups` | **10 组**同名（含 `au_family` / `has_au`）| spec_only |
| `identity_blind` | 「**不注入**对方作品归属」的规则 | spec_only |
| `familiarity_seed` | 熟络初值 `same_au_twin 0.55 / same_production 0.30 / stranger 0.0` | spec_only |
| `scene_traits` | 6 条场景特质（`dark/ruined/bright/crowded/quiet/cosmic`）| spec_only |
| `visitor` | 访客落点策略 | spec_only |
| `wiring` | 台账 + `not_yet` 6 条 | — |

★★ **诚实纪律**：7 段里**只有 `roam` 是 `wired`**，其余 5 块**如实写 `spec_only`**。
理由（用户口径）：「**函数写对了 ≠ 产品用上了**」。数据有了、规则定下来了，
**但没有接进产品**的东西不许标 `wired`。

---

## 六、兼容性的三层交付（★ 本轮用户强调的点）

| 层 | 状态 | 说明 |
|---|---|---|
| ① **门控**（谁能去哪） | ✅ **wired** | `world_gate` + `roam_scope`，**真 import 真跑** |
| ② **共存基础**（贴图 / 人设 / 注册） | ✅ **已有** | 第70/71轮：96 位全注册、529 张贴图、76 份人设 |
| ③ **交互层**（相认 / 熟悉 / 场景反应 / 访客） | ⏳ **spec_only** | 契约已定、`not_yet` 已列，排队 73 轮 |

⇒ "兼容性"**不是**一句话，而是三层；本轮**做实了第①层**（唯一能"真跑"的一层），
第③层**没有假装做完**。

---

## 七、判据 / 体检 / 复检

* **`check72`：37 项 FAIL=0**
  * A 数据面 8：96 条逐条显式 + 档位与"来处 + niko 特例"逐条一致 + 分布 + **全域通行只有 Niko**
    （+ 伪造第二个的负控制）+ 跨作品 61 全 `foreign` 而 Deltarune 35 未被误改 + 契约数字对账。
  * B 代码面 5（AST）：`RoamScope` 三档齐 + `__slots__` 含 `roam_scope` + 双向接线
    + ★★**跨作品分支排在 `chapters` 判空之前**。
  * C 行为面 14：**真 import 真跑** —— 跨作品进光世界 ✅ / 进暗世界 ❌ / 回自己作品 ✅；
    Niko 进暗世界 ✅；黄魂 / Outertale 同款；5 条零回归 + 桌面闸优先；
    ★**负控制：Niko 降档后必须进不去**。
  * D 同名组 5：集合 == 注册表推出 + ★Toriel 三人且"Deltarune 那位只是同名"
    + 成员全在册无重复 + `has_au` 逐组一致 + 编造组名负控制。
  * E 诚实判据 3：台账只把 `roam` 记 `wired`，其余五项**必须** `spec_only`；
    `not_yet` 非空；台账与正文 status 不许打架。
  * F 判据自身体检 2。

* **`tamper72`（真改文件体检）**：T1~T4 **四种破坏全命中**，且
  **三文件（含 `npc_system.py`）sha256 逐字节恢复**。

* **`recheck72`（核心文件复检）：26 项 PASS=26**，含两条结构性守门：
  * ★「**定义顺序**」：`class RoamScope` 必须在 `class NpcDef` **之前**（否则 import 期 `NameError`）。
  * ★「**判断顺序**」：跨作品分支在 `chapters` 判空**之前**。

---

## 八、判据侧自纠（★ **产物零错**，全是"判据自己会说谎"）

1. **C10 零回归判据报红（`lancer` 进 ch3）**：我**凭印象**写"Lancer 进别章暗世界 ⇒ 拒"，
   实测 `lancer.chapters = ch1,ch2,ch3,ch4` **含 ch3** ⇒ **错的是期望，不是产品**。
   改：用**从数据推**的用例 —— 取 `noelle`（`ch2,ch4,ch5`）**没登记**的 `ch1` 来验"别章拒"。
   ★ 教训同第64轮 W22：**判据名与事实脱节却照样 PASS**。
2. **`check72` B2 `AttributeError: 'Constant' object has no attribute 'elts'`**：
   `CLS['NpcDef'].body[0]` 是 **docstring**（Constant），不是 `__slots__`。
   改：遍历 `body` 找 `targets[0].id == '__slots__'` 的那条 `ast.Assign`。
3. **`recheck72` 4.2 误报（判据过宽）**：判据写的是"第二参是**布尔字面量**"，
   把 `check('C0 …', False, 'import 失败')` 这种**主动报红**（合法用法）也算成恒真。
   改：只查 `a.value is True`，并注明"`False` 是主动报红，不算"。
   ★ 教训：**判据过窄会漏报，过宽会误报**。
4. **`build72.py` 锚点差一个标点**：写 `，两作品…`，原文是 `；两作品…` ⇒ 首跑
   「source 同步 = 否」。改对标点后通过。
5. **`check72.py` `gate()` 里一段死代码**（嵌套推导式构造 `NpcDef`，从未被调用）⇒ 删除。

---

## 九、回归

* 全量 G2：**PASS=3190 / FAIL=0 / 套件=60 全 IDENTICAL**（第71轮为 3153 / 59）。
* `--only check72 --update` **合并模式**重建 1 套（37 PASS）。
* 新增套件 `check72` 已进 `run_all.py` 的 `SUITES`（`offscreen=False`），打印字面量 `[PASS]`。

---

## 十、遗留（诚实清单）

1. ★★ **跨作品场景面仍缺**：`_index.json` 只有 `desktop` + `ch1~ch5`；
   寻路图 `_room_graph.json` 只这五章；大图枢纽只有 `hub:desktop`/`hub:ut`/`hub:uty`，
   **没有 `hub:ot` / `hub:os`** ⇒ 第71轮电梯上端只能停在**世界级** `hub:ot`。
2. **同名相认 / 无身份标识 / 熟络初值 / 场景反应 / 访客台词**：契约已定，**未接线**（见 §五 台账）。
3. **`niko` 只在磁盘有**（`content/npc/niko.xnb`），不在源清单里 ⇒ 轮次 74 若要"源清单双向齐"会咬人。
4. **`ot_asriel_twinkly` 是两个物件名**（`iocAsrielDown` + `iocTwinklyMain`），改名时须一并迁移。
5. 用户「**留了两个任务在等待发送里**」—— **仍未发出**，不擅猜。
6. 待用户裁定：源文件 5146 行错位的「黄魂：」分区标题，其后 12 行归属。

---

## 十一、下一轮入口

* **轮次 73 · 自由生活**：NPC 无需用户发起即可私下闲聊 / 移动 / **传播信息**。
  ★ 与 `MiniMemory`（"一角色一份**物理分开**的记忆"）存在**张力**：
  现在的 `npc_system.WORLD_*` 只有"**能否进这个世界**"的政策，**没有信息传播机制**。
* **轮次 74 · 次要 NPC 内置设定**（用户授权我自己写）：原料 = `其余人物设定.txt` /
  `人物关系叙述.txt` 里出现、但不在 76 份人设里的角色（★ 含用户点名的"黄魂 Toriel"，
  已实证源文件黄魂分区 15 人**无 Toriel**）。
'''


def main():
    if '--write' in sys.argv:
        with io.open(REPORT, 'w', encoding='utf-8', newline='\n') as f:
            f.write(TEXT)
        print('written:', REPORT, os.path.getsize(REPORT), 'bytes')
    else:
        print(TEXT[:600])
        print('...(dry-run，加 --write 落盘)  chars=%d' % len(TEXT))


if __name__ == '__main__':
    main()
