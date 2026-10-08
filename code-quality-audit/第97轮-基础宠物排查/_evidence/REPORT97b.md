# 第97轮b · 用户三条观察 —— 看录像取证与修复

> 用户指令（原话）：
> 「做基础排查，然后网络已经好了」
> 「那个坠落的触发逻辑不对吧，还有，那并没有窗口他也会判定我们移动了窗口然后摔倒，
>   对了，他站起来不需要揉眼睛，OK？」
> 「**你在视频里看不到我看到的这些吗，你得看一下啊**」

---

## 0. 一句话结论

**看了录像 + 把 5 个坠落触发点全部穷举到代码层** ⇒ 逮到 **2 处真缺陷**
（跳跃穿透误判桌面层 / 摔后恢复播"揉眼"），已修 + 已加锁。
用户第 ② 条**在自然路径下复现不出来**——录像里那段"空桌面摔"是**我注入的**，
这一点必须如实说清（见 §2）。

---

## 1. 我看了录像（逐帧，不是只看 CSV）

| 段 | 时长 | 帧数 | 采集 | 内容 |
|---|---|---|---|---|
| run1 自然 | 600 s | 1191 | 1.96 Hz | **零坠落**（anim 分布只有 sleep/idle/walk_*/look_up，无 fall/jump/climb） |
| run2 定向 | 180 s | 356 | 1.95 Hz | 3 段坠落（含注入） |

run2 的坠落相位链（逐帧，`rec97_frames.csv`）：

```
t= 6.1s  fall          (gfall=True)                      ← 注入 start_falling
t=15.2s  fall_mad  →  splat_mad  →  fall_back_rub  →  land  →  idle   ← 注入 start_fall('window_move')
t=30.4s  fall          (gfall=True)
t=45.2s  fall_mad  →  splat_mad  →  fall_back_rub  →  land  →  idle
t=60.1s  fall          (gfall=True)
t=75.2s  fall_mad  →  splat_mad  →  fall_back_rub  →  land  →  idle
```

抽帧看图（`_tools/probe97b` 系列 + `C:\Users\23002\AppData\Local\Temp\wb97_frames\`）：

- `fall_mad`（f026）：宠物**直立**、位置几乎不动（CSV `moving=False`）
- `splat_mad`（f029）：宠物**横躺摔扁** ✓
- `fall_back_rub`（f036）：趴着**揉** ← **用户说"站起来不需要揉眼睛"指的就是它**
- 全屏（`full_f026.png`）：**沙箱桌面没有任何窗口**（一片壁纸 + 任务栏 + 沙箱图标渲染异常）

> ⚠️ 全屏里宠物周围那排**蓝框 + 绿色字母**是**沙箱桌面图标渲染异常**，
> 不是窗口、也不是产品画的。它们约 30×40 px < `get_all_visible_windows`
> 的 100×100 门槛 ⇒ 不会被当楼板（已核对 `desktop_interaction.py:1312`）。

---

## 2. ★★ 必须澄清：run2 的"空桌面摔"是**我注入的**

`rec97.py` 里加了 `REC97_INJECT_FALL=1`：每 15 s 交替调

```python
pet.start_falling(180, is_thrown=True, reason='probe_inject')
pet.start_fall('window_move')
```

**目的**：补第96轮遗留的 F7 覆盖缺口（自然 600 s 一次坠落都没触发）。

⇒ 用户在录像里看到的"**没有窗口，宠物却摔倒 + 揉眼**"，
**是这条注入线造成的**，不是产品自发行为。

**证据**：run1（产品自发跑 600 s、同一个空桌面）**坠落 0 帧、无任何无端摔倒**。

**为什么注入能触发、自然不能**：`start_fall(reason='window_move')` 的**唯一调用点**
是 `_follow_floor_move()`（`main.py`），而它前置要求
`old_floor.get('type') == 'window'`。桌面层的 `type` 恒为 `'desktop'`
（`floor_manager.py:158-163`）⇒ 站在桌面上**永远走不到这条路**。

---

## 3. 但确实逮到 **2 处真缺陷**

### 3.1 【真 bug·对应用户①】跳跃的"穿透检查"把**桌面层**当障碍

**位置**：`ralsei_pet/src/main.py` 的 `handle_jump`（穿透循环）

```python
all_floors = self.floor_manager.get_all_floors()      # = floors + [desktop_floor]
for floor in all_floors:
    if self._floor_identity_key(floor) in (cur_fid, tgt_fid):
        continue                                      # 只排除"起点/终点"
    if floor['rect'].intersects(current_rect):
        self.start_falling()                          # ← 判"穿透"，强制坠落
        return
```

**机制**：
- `get_all_floors()`（`floor_manager.py:675`）**总是**把桌面层算进去；
- `desktop_floor['rect']` 恒等于**整个虚拟屏幕**（`update_floors`，`SM_*VIRTUALSCREEN`）；
- 排除条件只有"起点/终点"，而桌面层的 key 是 `'desktop'`
  ⇒ **只有起点或终点本身是桌面时才被排除**；
- ⇒ **起点与终点都是窗口**时（站在窗口 A 上跳到更高的窗口 B —— 这正是
  `get_jump_destinations` 给出的**真实候选**），桌面层留在循环里，
  而宠物矩形恒在屏幕内 ⇒ `intersects` **恒为 True** ⇒ 起跳**第一帧**就被判
  "穿透"并 `start_falling()` **强迫摔下来**。

**用户视角** = "**跳一半自己掉下来**" ⇒ 对应用户①「坠落的触发逻辑不对」。

**取证**（`_tools/probe97b_pierce.py`，用**真实 FloorManager** 复算该循环）：

| 场景 | 起点→终点 | 命中 | 结果 |
|---|---|---|---|
| 无窗口，桌面→桌面 | desktop→desktop | 无 | ok ✅ |
| 窗口A→窗口A | window→window | **desktop** | **误判坠落** ★ |
| **窗口A→更高窗口B** | window→window | **desktop** | **误判坠落** ★ |
| 窗口→桌面 | window→desktop | 无 | ok ✅ |

```
↳ get_jump_destinations(A, 站位) = [('window(h=5)', (500,760)),
                                    ('window(h=10)', (500,260)),   ← B，真实候选
                                    ('desktop(h=0)', (500,10))]
```

### 3.2 【真 bug·对应用户③】摔后恢复播 `fall_back_rub`（揉眼 / 啜泣）

**位置**：`handle_fall` 的 `dazed`（晕乎）阶段。

```python
if "fall_back_rub" in self.sprite_loader.sprites:
    self.change_animation("fall_back_rub", force=True)
```

**该素材的原始语义是「坐在地上啜泣」**——仓库根 `要求:80` 逐字：

> 坐在地上啜泣的 2 帧动作示例（`spr_ralsei_fall_back_rub_0.png`）：
> 使用条件为触发轻微悲伤事件、角色处于"坐在地上"状态、非战斗

拿它当"摔后恢复" ⇒ 把呻吟演成**啜泣揉眼**。用户口径：**"他站起来不需要揉眼睛"**。

> 附：`emotion_system.py:910` 的 `'disappointed' → 'fall_back_rub'`（语义**正确**，
> 就是悲伤）全项目零调用（`get_animation_for_emotion` 是死代码）⇒ **不动它**。

---

## 4. 修复（`ralsei_pet/src/main.py`，2 处）

| # | 位置 | 改动 |
|---|---|---|
| 1 | `handle_jump` 穿透循环 | 加 `if floor.get('type') == 'desktop': continue`（桌面层永远不参与穿透判定——它只可能是**落点**，不是障碍） |
| 2 | `handle_fall` 的 `dazed` 阶段 | `fall_back_rub` → **`fall_back`**（`animations.json:545-547`，注释即"地上状态动画"，5 帧）；两者都缺时**不切动画**（保持 landed 躺姿），绝不回落揉眼素材 |

---

## 5. 回归锁 `check97.py`（14 条，自报 PASS=14 FAIL=0；G2 口径 **14** 一致）

| 段 | 判据 | 类型 |
|---|---|---|
| A1 | 两个目标函数都能抽到真源码 | 前置锚点 |
| A2 | `handle_jump`（剥注释）含桌面层排除 | 源码级 |
| A3 | 起点终点都是窗口 ⇒ 不命中桌面层（**复算口径取自产品源码**） | **行为级** |
| A3b | 真实 `get_jump_destinations` 把窗口 B 当候选 ⇒ 场景可达 | 可达性 |
| A4 | 负控制（恢复式变异）：不排除 ⇒ **必命中** desktop | 负控制 |
| B1 | `handle_fall`（剥注释）不含 `fall_back_rub` | 源码级 |
| B1b | 确实切 `fall_back`（不是把动画删了） | 源码级 |
| B2 | 真跑 `trigger_splat`+`handle_fall` ⇒ 晕乎阶段切 `fall_back` | **行为级** |
| B3 | 负控制：连 `fall_back` 素材都没有 ⇒ 不崩、也不回落揉眼 | 负控制 |
| C1 | 恒真防护：本套件没有 `check(..., True)` | 判据自身体检 |
| C2 | 成功标记的**打印点**只出现 1 次（AST 数真实调用，非 `str.count`） | 判据自身体检 |
| C3 | 被测文件在盘 | 判据自身体检 |
| C4 | **剥注释链自证**（原文含 `fall_back_rub`、剥后必须不含） | 判据自身体检 |
| C5 | ★★★ 成功标记**字面量**只能是打印模板（防 **G2 计数自匹配**） | 判据自身体检 |

> ★ **判据数以 G2 口径为准**，不是脚本自报：G2 的 `count_results` 用
> `len(re.findall(r'\[PASS\]|\[\s*OK\s*\]', stdout))` —— **纯文本出现次数**。
> 首版 C2 的 desc 里回显了该字面量 ⇒ **一行被数 2 次** ⇒ G2 记成 **14**（真 13），
> 而 `FAIL=0` 照样成立（只让统计列说谎）。
> 现 desc 已去字面量 + 新增 **C5** 守卫，并固化 `_tools/verify_check97_count.py`
> 用 **G2 的同一正则**做正/负控制核验（正控制 14==14；负控制塞回字面量 ⇒
> G2 计数 15 且 C5 报红）。

### ★★ 本轮判据自身又栽了 4 次（"判据也是被测物"第 19~22 例）

| # | 缺陷 | 症状 | 修法 |
|---|---|---|---|
| 19 | **A3 恒真** | 首版 `skip_desktop=True` 是**我硬编码**的 ⇒ 只测了我自己的函数、测不到产品 | 改为**由产品源码推导**：`_need in _hj_code` |
| 20 | **C2 自匹配** | `_self_src.count("print('[PASS] %s'")` 把自己 docstring / 断言里的同名子串也数进去 ⇒ count=3 假红 | 改 **AST 数真实 print 调用** |
| 21 | **剥注释链静默失效** | "切文本 + `textwrap.dedent` + `ast.parse`" 在**方法体首条语句是多行 docstring**时（内容行缩进不足 ⇒ 公共前缀被拉低）抛 `unexpected indent` ⇒ `except` **静默返回原文** ⇒ B1 把**注释里**的 `fall_back_rub` 当代码引用 ⇒ 假红。**前后栽了两次**（先没 dedent、后加了 dedent 仍不够） | 改 **`ast.unparse(函数节点)`** 一步到位；并加 **C4** 用真实源码自证这条链有效 |
| 22 | **G2 计数自匹配** | C2 的 desc 写成 `C2 真实 print('[PASS] %s') 调用只出现 1 次` ⇒ 运行时**一行里含 2 个**该字面量，而 G2 是 `re.findall` **纯文本计数** ⇒ 套件判据数被顶成 **14**（真 13）。`FAIL=0` 照样成立 ⇒ **只让统计列说谎**。★ **同一个坑第三次发作**（95D1 → 96bC4 → 97C2-G2） | ① desc 去掉字面量；② 新增 **C5** 静态守卫（含该字面量的 **AST Constant** 只允许"恰好等于打印模板"那一个）；③ C5 自身用**拆写** `'[PA' + 'SS]'` 规避自指；④ 固化 `verify_check97_count.py` 用 **G2 的正则**复算 stdout 做正/负控制 |

---

## 6. 待用户确认（② 的现场）

第 ② 条「**那并没有窗口他也会判定我们移动了窗口然后摔倒**」：

- **自然路径下不可达**：`_follow_floor_move`（`start_fall('window_move')` 唯一调用点）
  前置要求 `old_floor['type'] == 'window'`；桌面层是 `'desktop'` ⇒ 站在空桌面上
  **永远走不到**。run1 实测 600 s 零坠落，与此一致。
- 请用户补充：**当时屏幕上到底有没有窗口**、**是不是拖动过它**、
  以及"摔倒"是**生气动画**（`fall_mad`/`splat_mad`）还是**普通坠落**（`fall`）。
- 若是在**录像**里看到的 ⇒ 那就是 §2 说的**注入线**，不是产品自发。

---

## 7. 产物清单

| 文件 | 说明 |
|---|---|
| `_tools/probe97b_pierce.py` | ★ 真 bug 复现（真实 FloorManager 复算穿透循环） |
| `_tools/check97.py` | ★ 回归锁（14 条） |
| `_tools/verify_check97_count.py` | ★ 用 **G2 的正则**复算 stdout 计数（正/负控制自证） |
| `_tools/rec97.py` / `analyze97.py` | 真机录制 + 逐帧分析（上半场） |
| `_evidence/check97_before_fix.txt` / `check97_final.txt` | 套件输出快照（改前 FAIL=4 / 改后全绿） |
| `_evidence/REPORT97b.md` | 本报告 |
| `_evidence/rec97_raw.avi` 等 | run1/run2 录像与逐帧数据（**不入库**，见 §8） |

---

## 8. G2 回归与入库守卫

| 阶段 | 结果 |
|---|---|
| 改前基线 | `PASS=4638 FAIL=0 套件=88`（全 IDENTICAL） |
| 改 `main.py` 后（未注册新套件） | **仍 `PASS=4638 FAIL=0 套件=88`、全 IDENTICAL** ⇒ 两处改动**零副作用** |
| 注册 `check97` 后 `--update` | `check97  0  14  0  BASELINE` |
| **全量最终** | **`PASS=4652 FAIL=0 套件=89`**（4638 + 14 = 4652 ✅ 逐项对上） |

★★ **入库守卫（本轮新增工序，逮到一个真漏网）**：`.gitignore` 里
`code-quality-audit/*/_evidence/*.avi` **只匹配一层**，而本轮把 run1 的自然录制放在
`_evidence/run1_natural/` 子目录 ⇒ **136 MB 的 avi 漏网**，`git status` 会直接把它带进
提交。⇒ 改为 `**` 递归匹配，并连带忽略 `**/frames/`（逐帧抓屏 PNG ~11 MB，含整个桌面，
与 §90 的 `shots/` 同理）。已用 `git check-ignore -v` **逐条验证**：
4 个大项 IGNORED / 报告 · CSV · 脚本 NOT-IGNORED。
