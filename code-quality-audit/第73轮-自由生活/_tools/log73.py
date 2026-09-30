# -*- coding: utf-8 -*-
"""追加第73轮日志段（append-only）。--write 才落盘。"""
import sys, os, io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
LOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-10-01.md')

SEG = u'''
## 第73轮 · NPC「自由生活」

轮次目录：`code-quality-audit/第73轮-自由生活/`；报告：`第73轮报告-自由生活.md`（仓库根）

### 一、用户指令（逐字）

> 「我希望他们是**生活在这**而不是我走到哪他们加载到哪……我希望他们是**能对场景有反应**的，
> 比如 sans 来到 oneshot 会吐槽，这地方真黑之类的话（当然，**不止黑，破败这类的词也需要有
> 能力识别**）……之后不同世界的人一开始也不认识，所以他们也是**循序渐进的熟悉起来**，
> 当然，**面对不同版本的自己熟悉的会更快**……还有，**怪物们之间没有身份标识说你是哪个世界观的，
> 所以那需要自己判断**」

⇒ 本轮把其中**能落地且能验证**的四件事接进了产品；其余如实 `not_yet`。

### 二、三个关键设计判断

1. **不复用现成的 `ChatScheduler`**（第46轮写的 `companion_roster.ChatScheduler` 一直零引用）：
   它的主键是 `Companion`（跟着主角走、带槽位滞后），这里主键是 `NpcDef`（世界居民）。
   硬塞会造出"**不是伙伴的伙伴**"。⇒ `npc_life.LifeLoop` **平行实现**同一组不变量
   （不并发 / 相邻两句不同人 / 失败必解锁 / 反活锁），判据判的是"**性质相同**"，不是"代码复用"。
2. **传话 ≠ 共享记忆**：`MiniMemory` 接口层**没有** `all()/everyone()` ⇒ 串味写不出来。
   但 `dst.remember(text, who=src)` 是**合法显式动作** —— B 记的是"**A 说过**"（带署名），
   不是"我知道了"（无署名）。⇒ 落地用户那句「**没有身份标识，需要自己判断**」：
   **信息带来源走，不带"他是哪个世界的"**。
3. **AU 家族 vs 同名**：Toriel 组 `[ot_toriel, toriel, ut_toriel]` 里 `toriel`（Deltarune）
   **只是同名** ⇒ `au_twin_pairs()` **只取 `au_family_members`**；取整个 `members`
   会白送 0.55 起手熟络度，**正是"面对不同版本的自己熟悉的会更快"被读歪的地方**。

### 三、新模块 `npc_life.py`（零依赖，顶层只 `import collections`，AST 验过零函数内 import）

1. `scene_traits()` / `trait_hits()` / `trait_hint()` —— 场景特质，**只从文本找关键词、
   返回命中词**（可解释），无命中返回 `()` —— **不猜**。
2. `Bonds` —— 熟络度：**对称**（`pair_key` 排序成对，结构上不可能 A-B ≠ B-A）、渐增、封顶、
   `seed` **不覆盖**已有记录。
3. `transmit()` —— 传话（见二·2）。
4. `LifeLoop` —— 自主开口节拍（四条不变量 + 可插拔**让路闸**）。
5. `pick_line()` —— 纯 NPC **零模型**台词挑选（不重复，走完一圈自动开新圈）。

### 四、接线（`main.py`，约 690 KB 核心文件）

import 区 `npc_life_mod`；类常量 `NPC_LIFE_ENABLED/MIN_GAP=45.0/MAX_TURNS=2`；
`init_npc_systems()` 8 个预声明字段 + `Bonds(seed_lookup=...)` + `LifeLoop(gate=...)`；
**三处接线**：`update_movement`（与 `npc_placement_tick`/`_ghost_tick` 同处调 `_npc_life_tick`）/
`npc_system_prompt`（传 `life=self._npc_life_blocks(npc_id)`）/
`npc_speak`（记完玩家那句后 `transmit` 给同场另一位 + `bonds.meet`）。
新增 9 方法：`_npc_production_of` / `_npc_seed_lookup` / `_npc_life_gate` / `_npc_life_ids` /
`_npc_plain_ids` / `_npc_say_line` / `_npc_scene_text` / `_npc_life_blocks` / `_npc_life_tick`。

★ **让路闸**：CPU-only 单实例 `NUM_PARALLEL=1`（57 轮实测"并发=排队"）⇒
"正在跟用户说话 / 模型忙 / 宠物在施法·躲猫猫·拖拽"一律**不自主开口**；
被让路的是**这一次机会**，不是这个人（**不推进轮转**）。

### 五、★★ 实证结论（本轮最值钱）

1. **现网 1,014 个真场景只命得中三个特质**：`dark` 141 / `crowded` 262 / `quiet` 372；
   另有 **483 个场景零特质**（返回空元组，**不猜**）。用户点名的
   **`ruined`（破败）/ `cosmic`（宇宙）/ `bright` 全部 0 命中** ——
   因 OneShot/Outertale 场景**没进 `_index.json`**（70/71 轮 `not_yet`）。
   ⇒ 令牌放 `TRAIT_TOKENS_RESERVED` **如实留白**，契约 `wired_how` **写明**，`check73` F3 守着。**不假装覆盖**。
2. **子串匹配造假命中（实测）**：`'ash' in 'forest_afterthrash2'`、`'night' in 'church_knightclimb'`
   ⇒ 改**英语复合词边界**规则（令牌须等于某分量或落在词首/词尾）。
   另两词是**语义**错位：`room`（Deltarune 命名前缀）、`light`（`lightworld*` = 光世界）
   ⇒ 靠"**不入表**"挡（边界规则挡不住），`BANNED_TOKENS` 分 `SUBSTRING`/`OMITTED` 两类。
3. **自主闲聊现网只有一个场景跑得起来**：`_placement.json` 34 条里同场 ≥2 位**纯 NPC** 的
   只有 `ch5.my_castle_town.my_castle_town`（`wrapper`+`doubter`），62 位未安置 ⇒ **密度不够**。
4. ★★ **顺手抓到一个沿用已久的错口径**：报告数字必须真跑 ⇒ 去 `_index.json` 真数，
   发现 **"现网 1,013 个场景"是错的**。真相：`check73` 取 id 的口径（"带 `file` **或**
   `name`"）把 **5 个章名 + 32 个区域名**也当场景收了 ⇒ 实跑 **1,051** 个键，
   其中**真场景 1,014**（= 1,013 原作房间 + desktop）。处理 = **判据名如实写两个数** +
   新增 **C1b** 钉住"差集只含名字、真场景一个不漏" + **结论改用真场景口径**
   （松口径会把 `forest` 这类区域名算成"安静"命中，虚高 10 次）+ **删掉 G2 描述里写死的 1,013**。
   ★ 这条**不是报红暴露的**，是"报告数字要真跑"逼出来的（同 66 轮"判据名写死 35 条实测 70"）。

### 六、判据 / 体检 / 复检

* `check73` **85 项 FAIL=0**（A 契约镜像 8 / B 代码 9 / C 行为 22 / D 镜像出处 7 / E 真机 14 /
  F 诚实 5 / G 自检 3）；C 段**对 1,014 个真场景（+37 个章/区域名，松口径 1,051）真跑**；
  E 段**真机**验 `_npc_life_tick` 真开口 + 真传话
  （停全部定时器 + **隔离内存记忆**，绝不碰用户 `E:\\RalseiMemory` 保管库）。
* `tamper73` **T1~T6 六处破坏全命中**，三文件（`npc_life.py`/`main.py`/`_crossworld.json`）
  **sha256 逐字节恢复**，恢复后 check73 rc=0，`ALL_DETECTED=True`。
* `recheck73` **45/45 PASS**，含第72轮两条守门复验（`RoamScope` 在 `NpcDef` 之前 /
  跨作品分支在 `chapters` 判空之前）。
* 全量 G2 **PASS=3277 / FAIL=0 / 套件 61**。

### 七、判据侧自纠 7 处（**产物零错，全是"判据自己会说谎"**）

1. `check73` B7 判据过窄：写"`if` 的 test 必须是**裸 `ast.Name`**"，实际是 `BoolOp`
   （`isinstance(life, str) and life.strip()`）⇒ **真接线被判 FAIL**。改：在 test 子树里找 `life`。
2. `check73` C9 首版**差点恒真**：`check('C9', _b2 := L.Bonds())` —— 对象恒为真 ⇒ 永远 PASS。
   改：真断言"`seed` 不覆盖已有记录"。★ 本项目最怕的形状（"看着在守，其实没守"）。
3. `recheck73` 锚点取到**定义处**而非**使用处**：`find('roam_all') < find('REASON_NO_CHAPTERS')`
   —— 后者是**常量定义**在文件顶部 ⇒ 恒为假。改：`'roam_all' < 'if not npc.chapters:'`。
4. `check73` E4/E5 目标 NPC 选错：`ralsei` 是**桌宠本体、不在 `npc_personas`** ⇒
   `npc_system_prompt` 恒返回 `''`。改用主线 NPC `toriel`。
5. `check73` E8 用纯 NPC 测 `npc_speak`：它对没设定的人**明确拒绝**（该做的事），
   被误读成"转话没接上"。改用两位主线 NPC 做夹具。
6. `check73` F1b 抓出**真数据缺口**：`roam` 是 72 轮接的线、当时**没写 `wired_how`**。
   处理 = **补字段**（扩大数据），**不是把判据放宽** —— 放宽带过的是真缺口。
7. ★ 体检**证据口径**自纠：`tamper73` T5 靠**第二套 check72** 报红，JSON 只记 `rc=0` 会**自我矛盾**
   ⇒ 落盘时补 `rc_alt` / `rc_alt_suite` 字段（**证据要自解释**）。

### 八、回归 / 记忆

* 全量 G2 **PASS=3278 / FAIL=0 / 套件=61**；`--only` 合并模式重建 6 套
  （`check73` **85** / `round5_smoke` 62 / `npc_persona55` 151 / `model_conc57` 27 / `check72` 39，
  另有 `check73` 因加 C1b 单独重建一次）。
* 5 条 DIFF **逐条看过**才更新基线：`round5_smoke`（模块数 61→62，`npc_life` 入册）/
  `npc_persona55`（W1 import 清单 +1）/ `model_conc57`（**只是行号位移**，判据"≥4 处"实测仍 5）/
  `check72`（37→39）/ `check73`（**84→85**，新增 C1b 口径诚实）。所有无关套件 **IDENTICAL**。
* 本文件（追加）。速查本 **未动**（未超限，且"记忆不要随便修改"）。

### 九、遗留

1. **主线 NPC 自主开口**（需 7B，须与用户请求排队让路）。
2. **相认台词**（`au_family_members` 已用于熟络度，"相遇怎么开口"未接）。
3. **跨作品场景特质**：`ruined`/`bright`/`cosmic` 令牌已预留，等 `hub:ot`/`hub:os` 进大图。
4. **NPC 密度**：62 位未安置。
5. **信息二次传播的衰减**（传话目前是"最近的 N 条"，没有"传着传着走样"）。
6. 用户「**留了两个任务在等待发送里**」—— **仍未发出**，不擅猜。
7. 待裁定：源文件 5146 行错位的「黄魂：」分区标题，其后 12 行归属。

### 十、下一轮入口

* **74 · 次要 NPC 内置设定**（用户授权我自己写）：原料 = `其余人物设定.txt` /
  `人物关系叙述.txt` 里出现、但不在 76 份人设里的角色（★ 含用户点名的"黄魂 Toriel"，
  已实证源文件黄魂分区 15 人**无 Toriel**）。
  ★ 与本轮的接口：给纯 NPC 补设定后，其**内置对话池**（`_dialogue.json`）也要跟着补。
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
