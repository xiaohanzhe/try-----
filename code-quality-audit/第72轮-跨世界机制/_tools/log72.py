# -*- coding: utf-8 -*-
"""追加第72轮日志段（append-only）。--write 才落盘。"""
import sys, os, io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
LOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-10-01.md')

SEG = u'''
## 第72轮 · 跨世界机制（穿行域 RoamScope）

轮次目录：`code-quality-audit/第72轮-跨世界机制/`；报告：`第72轮报告-跨世界机制.md`（仓库根）
提交：`37317f9`（12 文件 / +2086 −163）

### 一、用户指令（逐字）

> 「继续按你的计划进行，对了**做好不同世界的角色在不同世界的兼容性哦**」

★ 本轮**唯一验收点** = 兼容性。它落回更早的长需求里**最硬的一段**：Niko 自由穿行所有世界 /
其余 UT 及同人**只能非暗世界**。

### 二、三个技术判断（地基）

1. **世界模型补第三档 `foreign`**：`light/dark` 是 **Deltarune 语汇**（暗之泉二分）；
   UT 地下世界、OneShot 城市**都不是"暗世界"**。第66轮把跨作品角色写成 `dark` 是
   **当时只有两分的借用**。★ **实证不改变运行时行为**——拦人的是 `escape_via_bubble`
   （`is_dark_only = DARK_ONLY_IDS + escape_via_bubble`），**不是 `home_world`**
   ⇒ 补 foreign 是**语义修正，非行为改动**（不这么说会被误读成"改个字就宣称修好了"）。
2. **`RoamScope` 是"许可维度"，与 `home_world`（归属维度）分开**：用户那句是**许可句**。
   Niko 归属 OneShot（foreign）但许可 = 全部 ⇒ **必须新字段**，混用必打架。
   三档 `home / non_dark / all`，当前 `35 / 60 / 1`（`all` 只有 niko）。
3. **AU 家族 vs 同名**：Outertale、黄魂**都是 UT 的同人衍生** ⇒ `ut_/hy_/ot_` 同名 =
   **同一角色的不同版本**（`has_au=True`）；OneShot 独立作品 ⇒ **只算同名**。
   ★ 用户点名的 toriel 实为**三人**：`ut_toriel`/`ot_toriel` 属 AU 家族，
   `toriel`（Deltarune 本作）**只是同名**——没有为凑"四个人"把它算进 AU。

### 三、代码面（`ralsei_pet/modules/npc_system.py`，核心文件）

`WORLD_FOREIGN` + `class RoamScope`（**必须定义在 `class NpcDef` 之前**，否则 import 期 NameError）
+ `__slots__` 第 **14** 项 + 归一规则（**排在 `home_world` 赋值之后**，从 home_world 推缺省）
+ `to_dict`/`npc_from_dict` 双向 + **`world_gate` 暗世界分支插跨作品判断**。

★★ **顺序敏感（本轮第二次踩到"顺序"坑）**：跨作品分支**必须排在 `if not npc.chapters` 之前**。
因为 UT 侧 NPC 的 `chapters` 在本作 `scene_chapter()` 下**无意义**（指的是另一个作品的章），
排后面会先被"未登记章节"拦掉 ⇒ `non_dark` 档**形同虚设**。

★ **光世界一侧不改**：光世界本来就"谁都能去"，许可句约束的是暗世界。

### 四、数据面 / 契约面

* `_registry.json`：96 条**逐条显式** `roam_scope`（不靠缺省偷懒）；
  `home_world` = `dark 30 / light 5 / foreign 61`；`source` 里"一律显式 dark"旧句**已改写**。
* `_crossworld.json`（新建 12.4 KB / 7 段）：`roam`（★**唯一 wired**）/ `twin_groups`（**10 组**）/
  `identity_blind` / `familiarity_seed`（`same_au_twin 0.55 / same_production 0.30 / stranger 0.0`）/
  `scene_traits`（6 条）/ `visitor` / `wiring` 台账。
  ★★ **诚实纪律**：7 段里**只有 roam 是 wired**，其余 5 块**如实 spec_only** + `not_yet` 6 条。

### 五、★ 兼容性 = 三层交付（不是一句话）

| 层 | 状态 |
|---|---|
| ① 门控（谁能去哪） | ✅ **wired**（`world_gate` + `roam_scope`，真 import 真跑） |
| ② 共存基础（贴图/人设/注册） | ✅ 已有（第70/71轮：96 注册 / 529 贴图 / 76 人设） |
| ③ 交互层（相认/熟悉/场景反应/访客） | ⏳ **spec_only**，如实排队 73 轮 |

### 六、判据 / 体检 / 复检

* `check72` **37 项 FAIL=0**（A 数据 8 / B 代码 5 / C 行为 14 / D 同名组 5 / E 诚实 3 / F 自检 2）；
  C 段**真 import 真跑** `world_gate`；C14 **负控制"niko 降档后必须进不去"**。
* `tamper72` T1~T4 **四种破坏全命中** + **三文件（含 `npc_system.py`）sha256 逐字节恢复**。
* `recheck72` **26 项 PASS=26**，含两条结构性守门：**定义顺序**（RoamScope 在 NpcDef 之前）、
  **判断顺序**（跨作品分支在 chapters 判空之前）。
* 全量 G2：**PASS=3190 / FAIL=0 / 套件=60 全 IDENTICAL**（第71轮 3153 / 59）。

### 七、判据侧自纠 5 处（**产物零错**，又是"判据自己会说谎"）

1. **C10 零回归判据报红**：我**凭印象**写"lancer 进别章 ⇒ 拒"，实测 `lancer.chapters`
   **含 ch3** ⇒ **错的是期望不是产品**。改：改用**从数据推**的用例（取 `noelle` 没登记的 ch1）。
   ★ 同第64轮 W22：**判据名与事实脱节却照样 PASS**。
2. **B2 `AttributeError: 'Constant' object has no attribute 'elts'`**：`body[0]` 是 docstring
   不是 `__slots__`。改：遍历 `body` 找 `targets[0].id=='__slots__'` 的 `ast.Assign`。
3. **recheck72 4.2 误报（判据过宽）**：把 `check(..., False, 'import 失败')` 这种**主动报红**
   也算成恒真。改：只查 `value is True`。★ **判据过窄漏报，过宽误报**。
4. **build72 锚点差一个标点**（写 `，两作品`，原文 `；两作品`）⇒ 首跑「source 同步=否」。
5. **check72 `gate()` 死代码**（嵌套推导式构造 NpcDef，从未调用）⇒ 删。

### 八、回归 / 记忆

* 全量 G2 **PASS=3190 / FAIL=0 / 套件=60**；`--only check72 --update` 合并模式重建 1 套（37 PASS）。
* 本文件（追加）。速查本 **未动**（未超限，且"记忆不要随便修改"）。

### 九、遗留

1. ★★ **跨作品场景面仍缺**：`_index.json` 只有 desktop+ch1~ch5；大图枢纽**没有 `hub:ot`/`hub:os`**
   ⇒ 第71轮电梯上端只能停**世界级** `hub:ot`。
2. 同名相认 / 无身份标识 / 熟络初值 / 场景反应 / 访客台词：契约已定，**未接线**。
3. `niko` 只在**磁盘**有（`content/npc/niko.xnb`），不在源清单 ⇒ 74 轮"源清单双向齐"会咬人。
4. `ot_asriel_twinkly` 是**两个物件名**（`iocAsrielDown` + `iocTwinklyMain`），改名须一并迁移。
5. 用户「**留了两个任务在等待发送里**」—— **仍未发出**，不擅猜。
6. 待裁定：源文件 5146 行错位的「黄魂：」分区标题，其后 12 行归属。

### 十、下一轮入口

* **73 · 自由生活**：NPC 无需用户发起即可私下闲聊 / 移动 / **传播信息**。
  ★ 与 `MiniMemory`（"一角色一份**物理分开**的记忆"）**存在张力**：现有 `npc_system.WORLD_*`
  只有"**能否进这个世界**"的政策，**没有信息传播机制**。
* **74 · 次要 NPC 内置设定**（用户授权我写）：原料 = 出现但不在 76 份人设里的角色
  （★ 含"黄魂 Toriel"，已实证源文件黄魂分区 15 人**无 Toriel**）。
'''


def main():
    if '--write' in sys.argv:
        with io.open(LOG, 'a', encoding='utf-8', newline='\n') as f:
            f.write(SEG)
        print('appended ->', LOG, os.path.getsize(LOG), 'bytes')
    else:
        print('dry-run chars=%d' % len(SEG))


if __name__ == '__main__':
    main()
