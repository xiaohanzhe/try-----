# 第94轮 · 证据：`check89` 的 DIFF = 真非确定性（不是回归、也不是行尾）

> 只读取证，落盘于 `第94轮-基础宠物真机全功能验收/_evidence/`。
> 结论：**check89 的输出天生不可复现**（同一份代码连跑两次都不同），
> 故它的 DIFF **不是**本轮的回归信号，也**不能靠 `--update` 修**（那会把一次随机摇号冻成预期值）。

## 1. 现象

全量 G2（`g2_94_after_fix.txt`）：

```
check89          0      63     0      DIFF
合计：PASS=4555 FAIL=1  套件=85      ← 那 1 个 FAIL 是 check81 G5（见 §4），与 check89 无关
```

`baseline.json` 里 check89 记的是 `exit=0 fail=0 pass=63`，与本次**计数完全一致**
⇒ 差异只在**归一化文本**，是 sha256 不匹配，不是"红了"。

## 2. 实验：连跑两次 `--only check89`，逐字节比

产物：`check89_run1.txt` / `check89_run2.txt`（原始 stdout 各一份）。

```
$ cmp check89_run1.txt check89_run2.txt
differ: byte 3172, line 29
```

差异**只有两类**：

① 时间戳 —— 会被 `run_all.normalize()` 的 `_TS` 抹平，**不影响 sha**；

② ★★★ **NPC 启动摇号的目的地每次都不同**：

| NPC | run1 | run2 |
|---|---|---|
| `addison_tea` | `ch4.kris_room.kris_s_room` | `ut.rooms.room_start` |
| `castle_cafe` | `ut.rooms.room_start` | `oneshot.barrens.Blue` |
| `conbini` | `ut.rooms.room_start` | `ch3.dark_world.dark_world` |
| `king` | `oneshot.barrens.Blue` | `ch3.dark_world.dark_world` |
| `susie` | `oneshot.barrens.Blue` | （另一处） |
| …（30 行里绝大多数都变了） | | |

② 这类行是 `ralsei_pet.main — NPC <id> 自己挪到了 <scene_id>`。

## 3. 根因（读源码，不是猜）

`ralsei_pet/modules/npc_roam.py`：

```python
def _unit(npc_id, now, salt=''):
    """`(npc_id, 连续时间, salt)` → 确定性 `u ∈ [0,1)`。"""
    ... sha256(('%.6f|%s|%s' % (float(now), npc_id or '', salt or '')))
```

判据是**连续时间 `now`**。G2 的固定种子（`run_all.SEED = 20260913`，经 `_seed_runner.py`）
**管不到它** —— 它不吃 `random` 全局态，吃的是墙钟。

⇒ 这不是缺陷：**"换个时刻就换个分布"正是 NPC 自主生活的设计目标**
（`check79` 专门断言过"换 salt 摇号真变"、`check80`/`check87` 用**注入的 `now` + salt**
做确定性断言）。**问题只出在 check89 把这个随机的启动快照打进了 stdout。**

## 4. 为什么本轮**不修**它（三条理由）

1. **不在用户口径范围内**。本轮原话：「现在所有其他的模块先不用管，主要就是基础模块（基础桌宠）修复」
   —— `npc_roam` 不属基础宠物。
2. **上一窗口已有裁定**：把它标为"已知随机项，保持如实 DIFF，不掩盖"（见 `eol_rootcause_94.md` §4.3）。
   ★ 本轮做的是**把"已知"升级成"实证"**：之前只是记录，现在有"连跑两次"的硬证据。
3. **两种"修法"都更糟**：
   - `--update`：等于**把某一次随机摇号冻成预期值** ⇒ 下次跑还 DIFF，而且掩盖了"它本来不可复现"这件事；
   - 直接改 `normalize()` 加一条噪声过滤：那会**同时改变所有会实例化 App 的套件**的归一化文本
     ⇒ 它们全部转 DIFF ⇒ 被迫跟着 `--update` ⇒ **一次动到几十个套件**。
     要动 `normalize()` 必须先做"哪些套件会打印这类行"的普查，那是独立一轮的工作量，
     且属于 G2 基建（重要核心文件，按用户口径改完必须逐项复检）。

⇒ 结论：**如实留一个 DIFF，并把它记为待裁定项**（"要不要给 G2 的 `normalize()` 加 NPC 摇号噪声过滤"）。

## 5. 判据侧留痕（别的套件守住了什么）

check89 自己的 A~J 共 63 条判据**一条都不依赖**这些行：

```
A 桌面 8 扇门数据面 / B 路由表 8 条 / C `_match_tier` 的 -1 档 / D 菜单不空
E 渲染计划（真机 plan objs=8 · rect = 贴图×scale）/ F 推门真切场景
G 旧行为不回归 / I 可见性（`as_window=True` / `lower()` / `_place_scene_layer` 只 move 不 resize）
J 不许自作主张开 B 站（代码层零 URL 字面量 + 负控制）
H 判据自身体检（记账守恒 · 记账器鉴别力）
```

⇒ 63/63 全 PASS。DIFF 纯属"启动快照"那一行列进了比对范围。
