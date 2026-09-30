# -*- coding: utf-8 -*-
"""第73轮报告生成器（自写 UTF-8）。--write 落盘到仓库根。"""
import sys, os, io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
REPORT = os.path.join(ROOT, '第73轮报告-自由生活.md')

TEXT = u'''# 第73轮报告 · NPC「自由生活」

* 轮次目录：`code-quality-audit/第73轮-自由生活/`
* 新模块：`ralsei_pet/modules/npc_life.py`（零依赖纯策略）
* 一句话：让 NPC **不只是被叫到才开口** —— 他们会对自己所在的地方有反应、
  会跟同场的人**慢慢熟起来**、会把自己参与过的话**转告**给别人；
  纯 NPC 还能**零模型成本**地自发说一句。

---

## 一、用户指令（逐字）

> 「我希望他们是**生活在这**而不是我走到哪他们加载到哪……我希望他们是**能对场景有反应**的，
> 比如 sans 来到 oneshot 会吐槽，这地方真黑之类的话（当然，**不止黑，破败这类的词也需要有
> 能力识别**）……之后不同世界的人一开始也不认识，所以他们也是**循序渐进的熟悉起来**，
> 当然，**面对不同版本的自己熟悉的会更快**……还有，**怪物们之间没有身份标识说你是哪个世界观的，
> 所以那需要自己判断**」

⇒ 本轮把其中**能落地且能验证**的四件事接进了产品。

---

## 二、交付边界（★ 先说清楚哪接了、哪没接）

| 能力 | 状态 |
|---|---|
| **场景反应**（这地方什么样 → 进 prompt） | ✅ **wired** |
| **熟络度**（渐增、对称、AU 加速 → 进 prompt） | ✅ **wired** |
| **传话**（说完一句告诉同场另一位，带署名） | ✅ **wired** |
| **纯 NPC 自主开口**（零模型，取内置台词池） | ✅ **wired** |
| **主线 NPC 自主开口** | ⏳ `not_yet` —— 要靠 7B，需把"无用户发起的生成"接进异步回调链并与用户请求排队 |
| **相认台词**（认出对方是另一个版本的我） | ⏳ `not_yet` |
| **跨作品场景特质**（`ruined` / `cosmic`） | ⏳ `not_yet` —— 见 §五 |

---

## 三、三个关键设计判断

### 3.1 为什么不复用现成的 `ChatScheduler`

第46轮写的 `companion_roster.ChatScheduler` 一直**零引用**（第57轮登记过）。
它的名册主键是 `Companion`（**跟着主角走的那几位**，带槽位 `12+slot*12` 滞后），
而这里的主键是 `NpcDef`（**世界里的居民**）。把 `NpcDef` 硬塞成 `Companion`
会造出一批"**不是伙伴的伙伴**"，反而把两个概念搅在一起。

⇒ `npc_life.LifeLoop` **平行实现**同一组不变量（不并发 / 相邻两句不同人 /
失败必解锁 / 反活锁），并在 `check73` C 段对这四条**逐条**判据 ——
判的是"**性质相同**"，不是"代码复用"。

### 3.2 传话 ≠ 共享记忆（与 `MiniMemory` 的"物理分开"不冲突）

`npc_persona.MiniMemory` 的设计是"**一角色一份、物理分开**"，接口层面
**没有** `all()` / `everyone()`，所以"忘了过滤导致串味"写不出来。用户最怕的
"葫芦娃千里眼顺风耳"正是这一点。

但"**A 把自己说的这句话告诉 B**"是一条**合法的、显式的**动作 —— 它就是
`dst.remember(text, who=src)`。B 记下的是"**A 说过这句话**"（带署名），
**不是**"我知道了这件事"（无署名）。两者在存储上仍是**两份物理分开的数据**。

⇒ 这正是「怪物之间**没有身份标识**，所以**那需要自己判断**」的落地方式：
**信息带着来源走，但不带"他是哪个世界的"**。`check73` C 段有一条判据专门钉
"src 与 dst 是两条独立列表"。

### 3.3 AU 家族 vs 同名：**同名的一对不许享受加速**

契约里 Toriel 组是 `[ot_toriel, toriel, ut_toriel]`，但 `toriel`（Deltarune）
与另外两位**只是同名**（`namesake_members` 已写明）。所以
`npc_system.au_twin_pairs()` 只取 `au_family_members` —— 拿整个 `members` 配对
会把"同名"错当成"另一个版本的我"，**白送 0.55 的起手熟络度**，
正是用户那句「面对不同版本的自己熟悉的会更快」被读歪的地方。

---

## 四、新模块 `npc_life.py`（零依赖，顶层只 `import collections`）

1. `scene_traits()` / `trait_hits()` / `trait_hint()` —— 场景特质。
   ★ **有出处**：只从场景 id / 内部名的**文本**里找关键词，返回**命中词**（可解释），
   无命中就返回 `()` —— **不猜**。
2. `Bonds` —— 熟络度。**对称**（`pair_key` 排序成对，结构上不可能 A-B ≠ B-A）、
   **渐增**、封顶 1.0、`seed` 不覆盖已有记录。
3. `transmit()` —— 传话（见 3.2）。
4. `LifeLoop` —— 自主开口的节拍（四条不变量 + 可插拔**让路闸**）。
5. `pick_line()` —— 纯 NPC 的**零模型**台词挑选（不重复，走完一圈自动开新圈）。

---

## 五、★★ 实证结论（本轮最值钱的部分）

### 5.1 场景特质：现网**只认三个**

对 `_index.json` 里**全部 1,014 个真场景**真跑（数字由 `_tools/probe73_traits.py` 产出，
不是从源码字面量或记忆里抄的）：

| 特质 | 命中场景 | 逐令牌（各自命中多少场景） |
|---|---|---|
| `crowded` | **262** | `town` 204 / `city` 52 / `shop` 19 |
| `quiet` | **372** | `church` 166 / `home` 157 / `forest` 33 / `house` 24 / `library` 14 / `grave` 5 |
| `dark` | **141** | `dark` 137 / `cave` 2 / `basement` 2 |
| **`ruined`（破败）** | ❌ **0** | — |
| **`cosmic`（宇宙）** | ❌ **0** | — |
| `bright` | ❌ **0** | — |

另有 **483 / 1,014 个场景一个特质都不命中** ⇒ 返回空元组（**不猜**）。

★ 用户点名的「**破败这类的词也需要有能力识别**」——**当前做不到**。
原因不是没做，是 OneShot / Outertale 的场景**还没进 `_index.json`**
（70/71 轮登记的 `not_yet`）。⇒ 令牌已放进 `TRAIT_TOKENS_RESERVED` **预留**，
**不假装覆盖**；契约里 `scene_traits.wired_how` 也**写明**了这件事（`check73` F3 守着）。

### 5.2 子串匹配会造假命中（实测踩到）

朴素 `token in text` 会得出：

* `'ash' in 'forest_afterthrash2'` → 假"破败"
* `'night' in 'church_knightclimb'` → 假"黑"

⇒ 改成**英语复合词边界**规则：令牌必须等于某个分量，或落在分量的**词首 / 词尾**。
`shicave` / `yellowcave` 仍能命中 `cave`；`afterthrash2` / `knightclimb` 不再命中。

另有两个词是**语义**错位（不是子串问题）：`room` 是 Deltarune 的**命名前缀**
（所有 `room_*` 都是房间）、`light` 是 `lightworld*`（**光世界**，一个世界名）。
这两个靠"**不入任何令牌表**"挡住，并写进 `BANNED_TOKENS` 分了两种禁法。

### 5.3 自由生活的自主闲聊，现网**只有一个场景真跑得起来**

`_placement.json` 34 条站位里，同场有 ≥ 2 位**纯 NPC** 的只有
`ch5.my_castle_town.my_castle_town`（`wrapper` + `doubter`）。
62 位 NPC 尚未安置 ⇒ "他们生活在这"的**密度还不够**。这条如实记进
`check73.LIVE_SCENE` 的注释与报告，不掩盖。

### 5.4 ★ 顺手抓到的一个**口径问题**（"1,013" 是个错数字）

写报告时按纪律"数字必须来自真跑产物"，于是去 `_index.json` 上真数了一遍 —— 结果发现
**"现网 1,013 个场景"这个沿用已久的口径是错的**：

* `check73` 的取 id 口径是"带 `file` **或** `name` 的节点键"⇒ 把 **5 个章名 + 32 个区域名**
  也当成场景 id 收了进来 ⇒ 实际跑的是 **1,051** 个键；
* 其中**真场景**是 **1,014**（= 1,013 原作房间 + 桌面 `desktop`）；
* 也就是说：**判据名写的"全部场景 id"、判据实跑的 1,051、记忆里的 1,013，三个数字互不相等**。

⇒ 按"**口径与措辞不许打架**"处理，**不是**把数字改一改就完事：

1. 判据名如实写：`全部 1051 个 id 键（真场景 1014 + 章/区域名 37）`；
2. 新增 **C1b** 钉住这个关系：`松口径 ⊇ 真场景`，且差集**全部**是章名/区域名
   （**一个真场景都不漏**）；
3. **结论一律改用真场景口径**（松口径会把 `forest` 这类**区域名**算成一次"安静"命中，
   虚高 10 次）；
4. G2 描述里**写死的"1,013"删掉**（同第72轮"判据名里不许写死数字"那条教训）。

★ 这条**不是报红暴露的**，是"报告数字要真跑"这条纪律逼出来的 —— 与第66轮那次
"判据名写死 35 条而实测 70 却照样 PASS"是同一族问题。

---

## 六、接线（main.py）

| 位置 | 改动 |
|---|---|
| import 区 | `from modules import npc_life as npc_life_mod` |
| 类常量 | `NPC_LIFE_ENABLED = True` / `NPC_LIFE_MIN_GAP = 45.0` / `NPC_LIFE_MAX_TURNS = 2` |
| `init_npc_systems()` | 8 个预声明字段 + 契约读取 + `Bonds(seed_lookup=...)` + `LifeLoop(gate=...)` |
| `update_movement` | **与 `npc_placement_tick` / `_ghost_tick` 同一处**调用 `_npc_life_tick` |
| `npc_system_prompt` | 传 `life=self._npc_life_blocks(npc_id)` |
| `npc_speak` | 记完玩家那句后，**转告**同场的另一位（带署名） |
| 新增方法 | `_npc_life_tick` / `_npc_life_blocks` / `_npc_life_gate` / `_npc_life_ids` / `_npc_plain_ids` / `_npc_say_line` / `_npc_scene_text` / `_npc_seed_lookup` / `_npc_production_of` |

★ **让路闸（`_npc_life_gate`）**：模型是 CPU-only、单实例、`NUM_PARALLEL=1`
（第57轮实测"并发 = 排队"）⇒ 只要"正在跟用户说话 / 模型忙 / 宠物在施法·躲猫猫·拖拽"
一律**不自主开口**；返回 `False` 时**不推进轮转**（被让路的是这一次机会，不是这个人）。

★ **`identity_blind` 的执行点** = `_npc_life_blocks()`：只注入**显示名 + 熟络程度**，
`not_injected` 列的四样（作品归属 / 版本 / npc id / 对方人设）**一处都没进 prompt**。
`check73` E4c 用具体标识符黑名单反查（`ut_`/`hy_`/`ot_`/`os_`/`Deltarune`/`Undertale`/
`Outertale`/`OneShot`/`黄魂`/`foreign`/`roam_scope`/`home_world` 一个都不许出现）。

---

## 七、判据 / 体检 / 复检

* **`check73`：85 项 FAIL=0**
  A 契约镜像 8 / B 代码面 9 / C 行为面 22 / D 镜像出处 7 / E 真机 14 / F 诚实 5 / G 自检 3。
  * **C 段真 import 真跑**：对 **1,014 个真场景**（另有 37 个章/区域名，松口径 1,051）真跑
    特质推断；熟络度对称/封顶；传话不共享容器；节拍四不变量正负成对。
  * **E 段真机**：实例化 `RalseiPet()`（停全部定时器 + **隔离内存记忆**，绝不碰用户
    `E:\\RalseiMemory` 保管库），真验证 `_npc_life_tick` **开了一次口**并落记忆 + 传话，
    还有"只有 1 人时不开口"的负控制。
* **`tamper73`（真改文件体检）**：T1~T6 **六处破坏全部命中**，
  且三文件（`npc_life.py` / `main.py` / `_crossworld.json`）**sha256 逐字节恢复**，
  恢复后 check73 rc=0。`ALL_DETECTED=True`。
* **`recheck73`（核心文件复检）：45 项 PASS=45**，含
  "`RoamScope` 在 `NpcDef` 之前"、"跨作品分支在 `chapters` 判空之前"两条第72轮守门复验。
* 回归：全量 G2 **PASS=3278 / FAIL=0 / 套件 61**，全 IDENTICAL。

---

## 八、判据侧自纠（★ 产物零错，全是"判据自己会说谎"）

1. **`check73` B7 判据过窄**：写的是"`if` 的 test 必须是**裸 `ast.Name`**"，
   而实际写法是 `if isinstance(life, str) and life.strip():` —— test 是 **`BoolOp`**，
   于是**真接线被判成 FAIL**。改：在 test 子树里找"有没有出现 `life` 这个名"。
2. **`check73` C9 首版差点写成恒真**：`check('C9 ...', _b2 := L.Bonds())` ——
   一个 `Bonds` 对象恒为真 ⇒ **判据永远 PASS**。改：真断言 `seed` 不覆盖已有记录。
   ★ 这正是本项目最怕的形状（"看着在守，其实没守"）。
3. **`recheck73` 锚点取到"定义处"而不是"使用处"**：判据写
   `find('roam_all') < find('REASON_NO_CHAPTERS')`，而 `REASON_NO_CHAPTERS`
   是**常量定义**、位置在文件顶部 ⇒ 恒为假。改：用 `'roam_all' < 'if not npc.chapters:'`。
   ★ 同第72轮那条教训：**判据本身也是被测物**。
4. **`check73` E4/E5 目标 NPC 选错**：一开始用 `ralsei`，但 `ralsei` 是桌宠本体、
   **不在 `npc_personas` 里** ⇒ `npc_system_prompt` 对它恒返回 `''`，判据必然报红。
   改：用一位真装了设定的主线 NPC（`toriel`）。
5. **`check73` E8 用纯 NPC 测 `npc_speak`**：`npc_speak` 对没设定的人**明确拒绝**
   （这是它该做的事），于是"拒绝"被误读成"转话没接上"。改用两位主线 NPC 做夹具。
6. **`check73` F1b 抓出一个真数据缺口**：`roam` 是第72轮接的线，当时**没写
   `wired_how`**。处理方式是**补字段**（扩大数据），**不是把判据放宽** ——
   放宽带过的是真缺口。
7. **`check73` C 段取 id 的口径与措辞不符**（详见 §5.4）：判据名写"全部**场景** id"，
   实际把 5 个章名 + 32 个区域名一起收了 ⇒ 实跑 1,051 而真场景 1,014。
   改法 = ① 判据名如实写两个数；② 新增 C1b 钉住"差集只含名字、真场景一个不漏"；
   ③ 结论改用真场景口径；④ 删掉 G2 描述里写死的 1,013。**不是**只改个数字。
8. **体检证据口径自纠**：`tamper73` 的 T5 靠**第二套 `check72`** 报红，
   证据 JSON 里只记 `rc=0` 会**自我矛盾**（看着像漏检）⇒ 落盘时补 `rc_alt` /
   `rc_alt_suite` 两个字段。**证据要自解释**。

---

## 九、回归明细

| 套件 | 结果 |
|---|---|
| `check73`（新） | 85 PASS |
| `round5_smoke` | 模块数 61 → **62**（`npc_life` 入册） |
| `npc_persona55` | W1 的 import 清单多了 `modules.npc_life` |
| `model_conc57` | B6 打印的 `chat_with_ai` 调用点**行号位移**（判据是"≥4 处"，实测仍 5 处） |
| `check72` | 判据 37 → **39**（新增 E1b / E4，E 段改写为"允许生长但不许撒谎"） |
| `check73` | 判据 **84 → 85**（新增 C1b 口径诚实；C1/C2 措辞改为如实写两个数） |
| 全量 G2 | **PASS=3278 / FAIL=0 / 套件 61**（全 IDENTICAL） |

★ 四条 DIFF **逐条看过**才更新基线（`model_conc57` 只是行号位移，不是判据变化）。

---

## 十、遗留

1. **主线 NPC 自主开口**（需 7B，排队让路未接）。
2. **相认台词**（`twin_groups` 的 `au_family_members` 已用于熟络度，但"相遇怎么开口"没接）。
3. **跨作品场景特质**：`ruined` / `bright` / `cosmic` 令牌已预留，等 `hub:ot` / `hub:os` 进大图。
4. **NPC 密度**：62 位未安置 ⇒ 自主闲聊现网只有 1 个场景跑得起来。
5. **信息二次传播的衰减**（传话目前是"最近的 N 条"，没有"传着传着走样"）。
6. 用户「**留了两个任务在等待发送里**」—— **仍未发出**，不擅猜。
7. 待用户裁定：源文件 5146 行错位的「黄魂：」分区标题，其后 12 行归属。

---

## 十一、下一轮入口

* **轮次 74 · 次要 NPC 内置设定**（用户授权我自己写）：原料 = `其余人物设定.txt` /
  `人物关系叙述.txt` 里出现、但不在 76 份人设里的角色
  （★ 含用户点名的"黄魂 Toriel"，已实证源文件黄魂分区 15 人**无 Toriel**）。
  ★ 与本轮的接口：给纯 NPC 补设定后，他们的**内置对话池**（`_dialogue.json`）也要跟着补。
'''


def main():
    if '--write' in sys.argv:
        with io.open(REPORT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(TEXT)
        print('written:', REPORT, os.path.getsize(REPORT), 'bytes')
    else:
        print('dry-run chars=%d' % len(TEXT))


if __name__ == '__main__':
    main()
