# 第191轮 · NPC 本体（在场的人真的看得见）

> 用户口径（本轮四条，逐字）：
> ① `在场的人？咱不是全部都做吗，而且，素材在原作游戏里面都有啊，你用就好`
> ② `一视同仁，不再是主体为ralsei的项目了`（承接第190轮）
> ③ `参考原作，应为找不到走路帧那就意味着要么原作里有其他移动方式要么就是不动`
> ④ 非人站位（sign / dumpster / wrapper / …）`先留着并登记`

---

## 0. 我这一轮先犯的错（必须先记）

我报了一个**错的前提**：盘完 `ralsei_pet/assets/` 之后我说
「在场的 30 位没图、有图的 27 位不在场」，并据此给了三条路线（补 Deltarune 立绘 / 放开跨作品进场 / 先做渲染层+占位）。

用户直接否掉了：

> `在场的人？咱不是全部都做吗，而且，素材在原作游戏里面都有啊，你用就好`

**我查错了范围** —— 只查了 `ralsei_pet/assets/`，**没查 `项目文件夹/deltarune/`**。那里有：

| 目录 | 内容 |
|---|---|
| `ch3` | 3,774 张 |
| `ch4` | 7,466 张 |
| `npc/ch1..ch4` | 各章 NPC 散图 |
| `boss/{king,lancer,spamton,tenna,mike,rouxls,gerson,queen}` | BOSS 级立绘 |
| `lighter/{toriel,asgore,rudy,...}` | 光世界 NPC |

素材**一直都在**，"没图"是我没找。为此道歉。

**教训（可复用）**：判断"素材有没有"之前，先把**整个项目的素材根**列一遍，而不是只看某个子目录。
`assets/` 是这个项目的成品目录，不是素材来源目录。

---

## 1. 这一轮做了什么（四件）

| # | 产出 | 位置 |
|---|---|---|
| 1 | 素材落仓：18 人 / 146 张 PNG / 306K | `ralsei_pet/assets/sprites/dr/` |
| 2 | 帧清单（尺寸 + sha256，运行时零猜解） | `assets/sprites/dr/_npc_frames.json` |
| 3 | 渲染层：取帧 / 一人一窗 / 窗口池 | `ralsei_pet/modules/npc_body_render.py` |
| 4 | 宿主接线（5 处） + 回归锁 + 变异套件 | `src/main.py`、`check191.py`、`mutate191.py` |

**对话框一个字节没动**（第190轮已否决"把动画塞进对话框"）。

---

## 2. 三个设计决定（都不是随手定的）

### 2.1 为什么是「一个人一个小窗口」，不是「一张全屏透明画布」

遮挡契约（第164轮用户裁定 `BBA` 第三项 / 第178轮落地）是**按屏幕 Y 排序**：
脚底更靠下的人在前。

而一张全屏透明画布只有**一个** z 序 —— 要么全体压在所有窗口之上、要么全在之下，**两种都不对**。

桌宠自己就是「一个窗口 + 按脚底 Y 插进 z 序」
（`main._apply_pet_z_order` → `floor_manager.pick_insert_after_by_foot_y`），
所以 NPC 走**同一条路径**才叫一视同仁：

```
main._npc_body_zorder(hwnd, foot_y)
  └→ fm.get_insert_after_hwnd(current_floor, foot_y=foot_y)
  └→ FloorManager.set_window_behind(hwnd, insert)
```

### 2.2 脚底锚点必须与遮挡锚点是**同一处**

`Body.x/y` 在全项目里的既有语义是**身体中心**（`_npc_interact_candidates` 用
`b.x/b.y ± ACTOR_HALF_W/H` 当命中框），而遮挡排序用**脚底**。

两者错开半个身高 ⇒ 在"身高差 2px 的两个人"上会给出**相反答案**。
所以：窗口 `bottom == 脚底`，而中心→脚底的换算**只在渲染层做一次**
（`sync(anchor='center')`），宿主不重复减。

### 2.3 倍率用 `camera.scale`，**不是** `_cached_scale_factor`

`_cached_scale_factor = camera.scale × pet_scale`，而 `pet_scale` 是用户专门调**桌宠一个**的旋钮。
拿它放大 NPC 会让「我把 Ralsei 调大」变成「整条街的人都变大了」。

默认 `pet_scale = 1.0` 时两者数值相同 ⇒ 这是个**只在用户动过旋钮之后才显形**的偏差，
机器抓不到，只能从代码上钉（`check191 D4`）。

---

## 3. 素材：配到 18 人，未配到 16 条

`pick191.py` 用**逐条手写**的映射表 + 存在性校验 + 复制 + 清单 + 对照图。
**没有一处在运行时猜文件名** —— 素材库有三种命名写法：

| 写法 | 例 |
|---|---|
| `walk` + 方向 + 世界 | `spr_susie_walk_down_dw_3` |
| ch3+ 的 dt/lt/rt/ut | `spr_lancer_dt_0` |
| 不分方向 | `spr_gerson_idle_0` |

猜解一定会有猜错的那天，而**猜错不报错、只画错人**。

### 3.1 对照图抓出 3 处误配（正解，不是判据问题）

`_evidence/sheet191.png`（18 格、脚底对齐、2× NEAREST）出来后**看图**才发现：

| id | 原选 | 实际是 | 改成 |
|---|---|---|---|
| `addison_tea` | `spr_npc_addison_stand` | **店招框** | `spr_npc_addison_blue`（且在 `npc/` 不是 `ch4/`） |
| `gerson` | `spr_gerson_battle_overworld` | **蘑菇状杂物** | `spr_gerson_idle` |
| `mike` | `spr_mike_med` | **黑白猫** | `spr_mike_l`（44×86 直立像） |

★ 这三处**自动挑族一定会犯**：按 token 匹配会把
`spr_dw_castle_queen_room_traffic_light` 当成 queen、把 `spr_pebble` 当成 puzzlemaster。
最终把关只有一条：**看图**。

### 3.2 配到（18）

`susie` `noelle` `berdly` `kris` `toriel` `asgore` `queen` `rudy` `lancer`
`king` `rouxls` `tenna` `mike` `gerson` `addison_tea` `rabbits` `hammerguy` `susiedark`

### 3.3 未配到（16，全部如实登记在 `manifest['no_art']`）

| 类别 | 名单 | 理由 |
|---|---|---|
| **不是人**（8） | `sign` `dumpster` `wrapper` `zapper` `mansion_room` `npc_room` `castle_cafe` `conbini` | 用户裁定「先留着并登记」⇒ 已进 `not_a_person` |
| 只有头像/家人素材 | `catti` | 没有本体立绘 |
| 只有 cutscene/battle | `spamton` | 无 overworld 站姿 |
| 素材库搜不到 | `doubter` `flowery` `police` `puzzlemaster1` `puzzlemaster2` | 原作可能是物件/机关 |
| **由老路径画** | `ralsei` | `sprite_label` 已经在画他；两边都画就是**叠两个他**（`E3` 钉这个） |

---

## 4. 用户口径③ 的落地：「找不到走路帧＝不动」

核查 `assets/npc/_placement.json`（**实测，不是印象**）：

- 共 84 条 placement 记录
- 其中**有具体场景**的 **34 条**：`stand` **27** / `patrol` **4** / `pace` **3**
- 另 50 条只有"家"没有具体站位，全部 `stand`

⇒ **27/34 = 79.4% 的人在原作里就不动**，只有 7 人会移动
（`ralsei` `asgore` `king` `flowery` `hammerguy` `rabbits` `wrapper`）。

所以「找不到走路帧」对绝大多数人**不是缺口**，与用户口径③ 一致。
代码侧对应：`moving=False` 时**钉在首帧**，只有 `moving=True` 才轮播（`C13b` 钉）。

> 订正：本轮方案里我一度写成"22 条 stand"，实测是 **27 条**（34 条有场景的站位里）。
> 数字以本节为准。

---

## 5. 一视同仁的两条落地（用户口径②）

### 5.1 桌面态：z 序走 `floor_manager` 同一条路径
见 §2.1。`D6` 从 AST 上钉「`get_insert_after_hwnd` + `set_window_behind` 都在」。

### 5.2 全屏房间（置顶带）：按脚底 Y **升序依次提升**

置顶带内的前后关系由 `SetWindowPos(HWND_TOPMOST)` 的**调用顺序**决定（后设的在上），
**没法用"插到某人之后"表达**。

⇒ 若把 NPC 一股脑排在桌宠之后，站在 Ralsei 前面的人也会被他盖住 ——
与桌面模式给出**两个相反的答案**，那正是"同一份规则两处算"。

新增 `_scene_topmost_targets_ordered()`：画布永远第一（最底）、灵魂/幽灵永远最后（最上），
**中间的"人"（桌宠 + NPC）按脚底 Y 混排**。老函数 `_scene_topmost_targets()` **一个字没动**，
留作 `D9b` 的负控制靶子。

另配 `_resync_topmost_group()`：`_set_scene_topmost` 是幂等的（只在翻转时真动），
所以"置顶态里新出现一个 NPC"不会触发它 ⇒ 那个小人会被画布盖住（`D12` 钉）。

---

## 6. 判据与变异

### 6.1 `check191` —— 69 条，分六段

| 段 | 条数 | 内容 |
|---|---|---|
| A 清单↔磁盘对账 | 14 | 尺寸走 **PNG IHDR 直读**（不经 Qt）、sha256 独立重算、目录**双向**对账防孤儿 |
| B 取帧 | 13 | 含 **146 帧全量真取一遍**（"一定画得出来"的硬证据） |
| C 窗口/锚点/z 序 | 21 | 中心→脚底、z 序锚点 == 窗口下沿、节流、上限、hide_all/destroy_all |
| D 接线（AST） | 13 | 不 import main；顺序、倍率优先、同一路径、混排、负控制 |
| E 一视同仁 | 5 | 渲染层不反向依赖、ralsei 不进两套、宿主不按 id 白名单 |
| F 自检 | 3 | 条数、只读、标记字面量 |

**两条负控制成对**：
- `C2`/`C6` —— 无立绘的人**不建窗口**；有立绘的人 z 序回调拿到的必须是**脚底**（拿中心也能"通过"，判据写松就看不出）
- `D9`/`D9b` —— 新函数**混排**；老函数里**不许**出现 NPC 逻辑

### 6.2 `mutate191` —— 31 条变异，**31/31 全抓**

每条断言 `0 < 红数 < 69`；整文件还原并核 sha1；双跑一致。

```
M01~M09  A 数据面（删方向 / 改 sha / 改 w / 删图 / 塞孤儿 / 摘 ralsei / 摘 sign / 改 kind / 塞 5 帧）
M10~M22  B/C 渲染层（左右互转 / 缓存键 / 半高 / 按中心摆 / 加 topmost / 恒播 / 去上限 /
                    反排序 / 无立绘返 down / 去 float 保护 / hide_all / 不复用 / 反向依赖）
M23~M30  D 接线（顺序 / 倍率优先 / 去早退 / 不插 z 序 / 用回老函数 / 去排序 / ralsei 特判 / 老函数读 NPC）
M31      destroy_all 不清池
```

### 6.3 ★★ 变异抓出**我自己的三条错判据**

这是本轮最有价值的部分 —— 67 条全绿只说明"现在的代码满足它们"，**不说明它们守得住**。

| 判据 | 错在哪 | 怎么暴露 | 修法 |
|---|---|---|---|
| `hide_all` 无覆盖 | `C10` 走的是 `sync([])` 分支，`hide_all()` 是**另一条路径**（宿主关开关/无人可画时走它） | `M20` **红 0** | 补 `C17`/`C18` |
| `E5` **恒真** | 用 `funcs()` 找 `BodyWindow`，而它是 **ClassDef** 不是 FunctionDef ⇒ `_bw_src` 是空串 ⇒ `not in ''` 永远真 | `M14` 只红 `C14`、`E5` 没红 | 收 ClassDef；★ 再发现类 **docstring 里**本来就写着「★ 为什么不加 `WindowStaysOnTopHint`」⇒ 字符串扫盘照样恒真 ⇒ **改走 AST 属性节点** |
| `E1` 判据过窄 | 只取 `node.module`，`from modules import main` 会被看成"导入了 modules"，**名字 main 整个漏掉** | 写 M22 时发现 | 连 `from X import Y` 的 **Y** 一起收 |

另有三处写在判据注释里：

- **`A9b` 判据过宽**：第一版断言"`stand` 类方向数不许 >2"，实测 `lancer` 就是四方向各 1 帧（站着也能转身看你）⇒ 误报。改成"不许**多方向 + 多帧**"（真走路的特征）。
- **`D4` 是纯文本扫出来的假象**：`_npc_body_scale` 的 **docstring 第一句**就是「★ 为什么不是 `_cached_scale_factor`」⇒ 按字符串位置比出来的是"注释谁写在前面"，与代码顺序无关。改走 AST 字面量行号。
- **`A0b` 只在 `except` 里发** ⇒ 正常时少一条，**条数随环境变**。改恒发。

---

## 7. 六条老基线的 DIFF —— 逐条看完才刷

| 套件 | 变的东西 | 判定 |
|---|---|---|
| `round5_smoke` | 模块数 76 → **77**，多了 `npc_body_render` | 设计预期 |
| `check73` D4 | 贴图目录列表多了 **`dr`** | 新素材目录 |
| `check182` C1/C2 | 行号 7849 → 8042（插入 ~193 行） | 相对顺序不变 |
| `check185` C6/C7 | 行号 7346 → 7539 | 同上 |
| `check186` C4/C5 | 1793→1800 / 7226→7419 | 同上 |
| `check190` D2 | 18237 → 18488 | 同上 |

**没有一条是真回归**。刷基线用 `--only <id> --update`（合并模式），默认环境（不加 `QT_QPA_PLATFORM`）。

★ 顺带确认：`--only check190` 是**子串匹配**，把 `check190b` 也一起跑了；
但它刷新后算出的 sha 与基线一致 ⇒ **没有实际影响**（`baseline.json` 只动了 6 条）。

---

## 8. 全量回归

```
合计：PASS=8366  FAIL=0  套件=189      （上一轮 8297 / 188）
判定分布：IDENTICAL 189 / DIFF 0
```

`check191` 已登记进 `regress/run_all.py` 的 `SUITES`
（`offscreen: True`，**不进** `HERMETIC_IDS`：建 `QApplication` 但不构造 `RalseiPet()`、不碰 `data_store`）。

---

## 9. 本轮没做 / 留给下一轮

| 项 | 状态 |
|---|---|
| **翻页队列**（一框一条 + 旁白单独一页） | 未开工，需单独一轮 |
| 「对话期微动作」三版示意 | **未采用**。用户选了"全部都做"（上本体），这份示意留档在 `_evidence/demo_microaction.html`，不是本轮实现 |
| 8 个"不是人"的站位 | 按用户裁定**只登记**不画 |
| `catti` / `spamton` / `doubter` / `flowery` / `police` / `puzzlemaster1,2` | 素材库确实没有对应站姿，如实留空 |
| `心里盘算着` 这类"心里 + 内在动词" | `_INNER_ACT_RE` 仍未覆盖（第190轮遗留） |

---

## 10. 落盘清单

```
ralsei_pet/assets/sprites/dr/                 18 目录 + _npc_frames.json（146 PNG / 306K）
ralsei_pet/modules/npc_body_render.py          新增 ~476 行
ralsei_pet/src/main.py                         +约 193 行（5 处接线）
code-quality-audit/第191轮-NPC本体/_tools/pick191.py     素材挑选器（--write / --sheet）
code-quality-audit/第191轮-NPC本体/_tools/check191.py    69 条判据
code-quality-audit/第191轮-NPC本体/_tools/mutate191.py   31 条变异
code-quality-audit/第191轮-NPC本体/_evidence/sheet191.png  18 格人工核对图
code-quality-audit/regress/run_all.py         SUITES 登记 check191
code-quality-audit/regress/baseline.json      6 条老基线重刷 + check191 新增
```
