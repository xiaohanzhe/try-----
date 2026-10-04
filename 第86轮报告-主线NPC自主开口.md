# 第86轮报告 — 主线 NPC 自主开口（B6 收口）

> 轮次日期：2026-10-04
> 上一轮：第85轮 `13020c5`（Shift 跑 + 暗世界移速 + 互动闸/缓冲 + 剧情标记 I10）
> 本轮锁：`check86.py`（**PASS=70 FAIL=0**）+ `mutate86.py`（27/0）+ `recheck86.py`（34/0）

---

## §0 本轮用户口径（逐字）

> **「只要不是在剧情里死了的npc就可以出现。不用。ok。继续推进吧」**

这句是承接第85轮 I10 的裁定，拆成三条 + 一个工作方式指令：

| 片段 | 含义 | 落地 |
|---|---|---|
| 「只要不是在剧情里死了的npc就可以出现」 | ★★★ **出场门控口径**：NPC 出不出场，**只被"剧情里已死亡"挡**；**剧情过完 ≠ NPC 消失** | 第85轮已完成（`plot_mark` 不接线为门控，见第85轮报告 §9） |
| 「不用」 | 不做 UI 显示"剧情已过" | 第85轮已完成 |
| 「ok」 | `Shift` 作跑键保持不动 | 无改动 |
| 「**继续推进吧**」 | 测绿即连续推进（既有工作方式） | **本轮据此自主选定 B6** |

---

## §1 本轮选题：为什么是"主线 NPC 自主开口"

不是随手挑的。三条证据：

1. **台账自己写着没做**：`ralsei_pet/assets/npc/_crossworld.json#round73.not_yet`
   第一条逐字就是「主线 NPC 自主开口（需 7B，排队让路未接）」。
2. **第73轮建锁时就把它记在 `not_yet`**，且 `check73.F2` 有一条专门判据守着这个"没做"的事实。
3. **B6（主动社交机制）在遗留池里**（第74轮登记），且用户口径已在第67.2 定过五条落地口径。

⇒ 本轮把 `not_yet` 里那条**真的做掉**，并让台账与代码**同步搬家**。

---

## §2 做了什么（代码面）

### 2.1 `ralsei_pet/modules/npc_life.py`（零依赖层，672 → 约 762 行）

新增**在场者感知**两个纯函数（`presence_hint()` / `where_of()`）：

| 函数 | 作用 | 关键纪律 |
|---|---|---|
| `where_of(dx, dy, near_px)` | 把位移归一成**一个粗方位词** | `same`/`near`/`left`/`right`；**算不出 ⇒ `None`（不猜）** |
| `presence_hint(speaker, others, positions, …)` | 产「**此刻这里还有谁**」一行 | 剔自己 / 去重 / 空 ⇒ `''`；**只给显示名 + 粗方位** |

★★★ **本轮实测抓到并修掉的一个真 bug**：`where_of` 早先写的是
`return 'left' if dx < 0 else 'right'` —— 于是**正上方 500 像素**（dx=0, dy=-500）
会被说成"**右边**"。那不是"粗档"，那是**错档**。
⇒ 加 `HORIZ_RATIO = 0.5`：`|dx| < |dy| * 0.5` ⇒ 视为纯竖直，**返回 `None`（不编左右）**。

> 这条是 `check86` C 段判据抓出来的 —— **判据侧先写对，产物侧才被逼着修对**。

零依赖复核：顶层 `import` 只有 `collections`；**零函数内 import**；不 import 项目内模块。

### 2.2 `ralsei_pet/src/main.py`（14,169 → 约 14,350 行）

| 新增/改动 | 作用 |
|---|---|
| `NPC_MAIN_TALK_GAP = 180.0` | **主线**自主开口的最小间隔（★本项目取值，原作用的是固定脚本对话） |
| `self._npc_main_last = 0.0` | 主线上次开口时刻 |
| `_npc_main_ids(ids)` | 主线准入**三条**：① 非 `PLAIN` 档 ② 装了人设 ③ 模型可用 |
| `_npc_life_blocks(npc_id)` | 改写为三块（新增 ②【此刻这里还有谁】） |
| `_npc_display_label` / `_npc_relative_positions` / `_npc_body_center` | 显示名（**不退回 id**，防泄露 `ut_`/`ch1.` 前缀）+ 相对位置 |
| `_npc_life_tick(dt)` | 拆分 2a 纯 NPC（`_npc_life_speak_plain`）→ 2b 主线（`_npc_life_speak_main`） |

**主线开口的关键结构**（`_npc_life_speak_main`）：

```
mains = self._npc_main_ids(ids)              # 三条准入
if len(mains) < MIN_TALKERS: return []
if now - self._npc_main_last < NPC_MAIN_TALK_GAP: return []   # 专属限流
speaker = loop.tick(now, mains)              # ★ 同一个 loop（闸已注入）
if speaker is None: return []
sent = self.npc_speak(speaker, '', _on_reply)   # ★ 同一条 7B 路径
if not sent:
    loop.abort(now); return []               # ★★★ 失败必解锁（否则永久 busy）
self._npc_main_last = now
loop.finish(now, speaker)                    # 传话 + meet 双向记账
```

### 2.3 三条纪律（本轮的核心设计）

1. **不另起炉灶**：主线走的是 `npc_speak` 的**同一条** 7B 路径 —— 不是复制一份调用。
2. **失败必解锁 + 反活锁**：主线走 7B 一旦报错，若不 `abort` 就永久 `busy`，整个生活线卡死。
   `mutate86` 专门有一条破坏验证它（"失败不 abort"⇒ 必报红）。
3. **让路闸一处拦、两支生效**：闸**注入到同一个 `LifeLoop`**（`gate=self._npc_life_gate`），
   由 `loop.tick()` 内部统一拦 ⇒ 纯 NPC 与主线天然共用一条规则。
   ★ 这是「**同一份规则两处算**」最贵的坑的反面应用：**只算一处**。

---

## §3 验证（四道关）

| 关卡 | 工具 | 结果 |
|---|---|---|
| ① 行为级自证 | `_tmp86/probe86.py` | **22 PASS / 0 FAIL** |
| ② 回归锁 | `check86.py` | **PASS=70 FAIL=0**（I 段 58 个 ★ 标记打印点） |
| ③ 鉴别力体检 | `mutate86.py` | **PASS=27 FAIL=0**（10 处破坏全报红 + 全归因到位） |
| ④ 核心文件复检 | `recheck86.py` | **PASS=34 FAIL=0** |

### 3.1 `mutate86` 的 10 处定点破坏（每处都必报红且归因）

| # | 破坏 | 归因词 | 结果 |
|---|---|---|---|
| 1 | 纯竖直位移又编左右（删 `None` 分支） | 「纯竖直」 | FAIL=2 ✓ |
| 2 | 说话者自己没被剔除 | 「说话者」 | FAIL=1 ✓ |
| 3 | 空名单也硬产一行 | 「无别人」 | FAIL=2 ✓ |
| 4 | 归属泄露（删"是哪个版本不知道"） | 「版本」 | FAIL=1 ✓ |
| 5 | 主线不再走 `npc_speak` | 「npc_speak」 | FAIL=1 ✓ |
| 6 | 失败不 `abort` | 「abort」 | FAIL=1 ✓ |
| 7 | `_npc_main_ids` 不再要求人设 | 「人设」 | FAIL=1 ✓ |
| 8 | `_npc_main_ids` 不再查模型可用 | 「模型可用」 | FAIL=1 ✓ |
| 9 | 让路闸被摘掉 | 「注入到 loop」 | FAIL=1 ✓ |
| 10 | `life=` 不再进 `build_system_prompt` | 「build_system_prompt」 | FAIL=1 ✓ |

**覆盖度**：10 条破坏全部归因到预期判据组（缺 `[]`）。

### 3.2 两处**判据侧**踩坑（都记在案）

| 症状 | 真因 | 修法 |
|---|---|---|
| `check86` C「远处/竖直不瞎编左右」报红 | **产物真 bug**（`where_of` 把正上方说成右边） | **修产物**（加 `HORIZ_RATIO`） |
| `check86` E「LifeLoop 可实例化」报红 | **判据侧错**：我把 `LifeLoop(['a','b','c'])` 当构造参，实际签名是 `(min_gap, max_turns, allow_solo, gate)`，ids 是 `tick(now, ids)` 的第二参 | 改判据（断行为：busy 置位/解除） |
| `check86` F「`_npc_life_tick` 内调用让路闸」报红 | **判据侧错形状**：闸不是 tick 里显式调的，是**构造注入**到 loop | 改判据（断"注入到 loop"这个事实） |
| `check86` G「`_npc_main_ids` 调用 `_npc_plain_ids`」报红 | **判据侧过窄**：实现是直接比 `tier` | 改判据（断"排除 PLAIN 档"） |
| `recheck86` ②「npc_life 接口全在」报红 | **判据侧错**：`familiarity_of`/`meet` 是 `Bonds` **类方法**，不是顶层函数 | 改判据（顶层按实际列 + 类方法另查） |

★ 五条里**四条是判据侧**、一条是产物侧 —— 与第62~70轮的历史分布一致（**判据侧栽跟头居多**）。

### 3.3 「禁止词本身出现在声明里 ≠ 泄露」（本轮最有价值的一条）

`probe86` A6 首跑报红：判据扫 `'版本'` 二字，而产物尾巴句是

> 「只知道他叫什么、大概在哪个方位 —— 他是**哪里来的**、是**哪个版本**，你并不知道，也别去猜。」

**那个"版本"二字，正是"禁止词本身"**（在声明"别说出去"），不是在泄露。

⇒ 修法（**判"有没有把作品归属当事实给出去"**，不扫汉字）：
- 断言产物里**零作品名前缀**（`ut_`/`uty_`/`hy_`/`ot_`/`ch1.`~`ch4.`/`deltarune`/`undertale`/`oneshot`/`outertale`）
- 加 **A6n 负控制**（把 `ut_papyrus` 当名字拼进去必须被抓）
- 加 **A6b**（走显示名路径 ⇒ 产物更干净）

---

## §4 台账同步（"接完了台账却忘了搬"是另一种失真）

`_crossworld.json#round73` 回写：

```diff
   "wired": [
     ...
     "LifeLoop -> 纯 NPC 零模型自发台词（内置对话池）",
+    "LifeLoop -> 主线 NPC 自主开口（第86轮接入：走同一条 npc_speak；在场者感知 presence_hint；失败必 abort；让路闸注入同一 loop）"
   ],
   "not_yet": [
-    "主线 NPC 自主开口（需 7B，排队让路未接）",
     "相认台词",
     "跨作品场景特质（ruined/cosmic 零命中）"
   ]
```

★ `check73.F2` 同步**加强**（不是削弱）：

```diff
- check('F2 `not_yet` 里明确列了「主线 NPC 自主开口」没做', ...)
+ check('F2 ★★★ 台账随事实推进：「主线 NPC 自主开口」**已从 not_yet 移进 wired**（第86轮接入）
+       —— 判据**加强**：不仅要求它现在在 wired，还要求 not_yet 里**不再有**它
+       （防"接完了台账却忘了搬"）', ...)
```

判据数：**88 项，FAIL=0**（判据名改了 ⇒ 基线已重固）。

---

## §5 全量回归（G2）

```
run_all.py：PASS=4201+70=4271 FAIL=0 套件=78  全 IDENTICAL
```

（套件数 77 → **78**，新增 `check86`。）

---

## §6 本轮产出文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `ralsei_pet/modules/npc_life.py` | 改 | +在场者感知两函数；修纯竖直档 |
| `ralsei_pet/src/main.py` | 改 | +主线自主开口全链 |
| `ralsei_pet/assets/npc/_crossworld.json` | 改 | round73 台账搬家 |
| `code-quality-audit/第86轮-主线NPC自主开口/_tools/check86.py` | 新 | 回归锁 70 项 |
| `code-quality-audit/第86轮-主线NPC自主开口/_tools/mutate86.py` | 新 | 鉴别力体检 27 项 |
| `code-quality-audit/第86轮-主线NPC自主开口/_tools/recheck86.py` | 新 | 核心文件复检 34 项 |
| `code-quality-audit/第73轮-自由生活/_tools/check73.py` | 改 | F2 判据随事实加强 |
| `code-quality-audit/regress/run_all.py` | 改 | 注册 check86 |
| `code-quality-audit/regress/baseline.json` | 改 | 固 check86 + check73 基线 |

---

## §7 遗留 / 下一步

**本轮已消掉**：`not_yet` 里的「主线 NPC 自主开口」。

**仍在 `_crossworld.json#round73.not_yet`**（未动）：
- 相认台词
- 跨作品场景特质（ruined/cosmic 零命中）

**由第85轮裁定派生的新待办（仍未澄清）**：
> 「**剧情里已死亡**」标记语义**尚无真源**。它现在是**唯一的出场门控依据**
> ⇒ 需要时**单开一份**（与 `plot` 明确分离），**不塞进 `plot_mark`**。

**遗留池**（未获明确放行，见详版 §74.10 / §75）：
`R1` 每人一个家 / `R7` 原作菜单键位 / `P3` `pet_interaction` 三选 / `Q2` Outertale 采样 /
跨作品贴图 / `B8` 预热 / `B11` 修 13 套件 / `B14` 瓦片 / `B15` 素材补采 / `R6` 的 `ESCORT_WIRING.wired=False`。

**待用户裁定**：无（本轮全部按既有口径推进，无需新裁定）。
