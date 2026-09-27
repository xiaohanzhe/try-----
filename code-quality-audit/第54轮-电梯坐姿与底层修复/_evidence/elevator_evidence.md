# 第54轮取证：原作「电梯里坐着」动画

> 生成时间：2026-09-27 23:05　（生成脚本为临时脚本，用后即删；产物已落盘）

## 1. 决定性证据：`spr_ralsei_sit` 在整个 ch1 代码里**只被一处引用**

用 UTMT CLI `dump` 导出 ch1 全部 CodeEntries（957 行 Step_0 在内）后逐文件搜：
含 `spr_ralsei_sit` 的脚本 **有且只有 1 个** ——
`gml_Object_obj_elevatorcontroller_Step_0.gml`（ch2 该符号引用数为 0）。

### 1.1 `con == 11`：坐下（Step_0 第 473 行起）
```gml
    if (con == 11)
    {
        with (r)
        {
            scr_halt();
        }
        with (r)
        {
            sprite_index = spr_ralsei_sit;
            image_speed = 0.25;
        }
        con = 12;
        snd_play(snd_wing);
        alarm[4] = 12;
    }
    if (con == 13)
    {
        with (r)
        {
            image_speed = 0;
            image_index = 2;
        }
        con = 15;
        alarm[4] = 20;
    }
```

### 1.2 `con == 17 / 19`：队友的放松姿态（Kris 躺 / Susie 靠墙）
```gml
    if (con == 17 && !d_ex())
    {
        with (s)
        {
            hspeed = -4;
            image_speed = 0.2;
        }
        with (k)
        {
            sprite_index = spr_kris_fallen_dark;
        }
        snd_play(snd_wing);
        con = 18;
        alarm[4] = 10;
    }
    if (con == 19)
    {
        with (s)
        {
            scr_halt();
            sprite_index = spr_susier_wall;
        }
```

⇒ 与用户第52轮原话完全对应：「一个**电梯里，主角团都以放松些的姿态坐着**的那组动画」。

## 2. 台词（`lang_en.json`，逐字）

| key | 原文 |
|---|---|
| `obj_elevatorcontroller_slash_Step_0_gml_353_0` | \EB* 好^1，这个电梯应该能
带我们离开。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_384_0` | * 不过^1，可能会花上点时间^1，
所以.../% |
| `obj_elevatorcontroller_slash_Step_0_gml_419_0` | \E0* 大家怎么舒服怎么来吧！/% |
| `obj_elevatorcontroller_slash_Step_0_gml_448_0` | * ..^1.嘿^1。Ralsei。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_449_0` | * 你知道Lancer他爸..^1. 
那个国王吗？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_451_0` | * 知道...？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_453_0` | * 等我们见到他之后... 
* 我们是不是必须得.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_454_0` | \EC* ...伤害他？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_456_0` | * Susie...？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_458_0` | \E7* 我是说^1，要我揍扁他很容易^1，
可是.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_459_0` | \E0* 但我知道^1，这不是你们的
行事风格。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_460_0` | \E2* 你们就喜欢^1，呃^1，
像群废物一样婆婆妈妈的。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_476_0` | \E0* 所以我在想..^1. 也许.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_477_0` | \E6* 我也能..^1. 学习一下你们？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_479_0` | * Susie！^1？
你是说你也想【行动】吗...？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_481_0` | * 唔.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_483_0` | * Susie..^1. 我们当然乐意
和你一起【行动】了！/ |
| `obj_elevatorcontroller_slash_Step_0_gml_484_0` | \E0* 不必担心^1，
我们会手把手教你的！/ |
| `obj_elevatorcontroller_slash_Step_0_gml_485_0` | \E6* 这样你就不用自己摸索了。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_487_0` | * .../ |
| `obj_elevatorcontroller_slash_Step_0_gml_488_0` | \EC* ..^1.好^1，行吧。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_503_0` | \EC* .../ |
| `obj_elevatorcontroller_slash_Step_0_gml_504_0` | \E0* 喂^1。Ralsei。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_506_0` | * Susie？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_508_0` | * 你.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_509_0` | \E6* 你还打算^1，呃^1，
做蛋糕吗...？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_511_0` | * 如果我做蛋糕的话^1，
你就不会再拿我开玩笑了吗？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_513_0` | * .../ |
| `obj_elevatorcontroller_slash_Step_0_gml_514_0` | \E2* 如果我没得选^1，大概吧。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_516_0` | * 那就让你吃个够^1，怎么样？/ |
| `obj_elevatorcontroller_slash_Step_0_gml_518_0` | * 行啊^1，说的好像你真能做得出
那么多似的。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_605_0` | \E0* 噢^1，我们到了！/% |
| `obj_elevatorcontroller_slash_Step_0_gml_644_0` | \E0* Kris^1，等一下。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_674_0` | * 我突然想到。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_675_0` | * 如果我们能，呃，
更加“团结”一些的话.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_676_0` | * 想离开这里就容易得多了。/ |
| `obj_elevatorcontroller_slash_Step_0_gml_677_0` | * 所以等下次我们和敌人
战斗的时候.../% |
| `obj_elevatorcontroller_slash_Step_0_gml_691_0` | \EC* 你告诉我什么... 我就做什么。/% |
| `obj_elevatorcontroller_slash_Step_0_gml_709_0` | \E1* ...但可别让我干什么蠢事，/ |
| `obj_elevatorcontroller_slash_Step_0_gml_710_0` | \E2* 不然我就做回那个战斗狂，
听懂了没有？！/% |
| `obj_elevatorcontroller_slash_Step_0_gml_774_0` | \E0* Kris.../ |
| `obj_elevatorcontroller_slash_Step_0_gml_775_0` | \EC* 我可全指望你了^1，好吗？/% |
| `obj_elevatorcontroller_slash_Step_0_gml_798_0` | * （Susie真正地加入了队伍。） |

## 3. 跨章像素比对：`spr_ralsei_sit` 有两个美术版本

| 章节 | sit_0 | sit_1 | sit_2 | sit_3 |
|---|---|---|---|---|
| chapter1 | 24x44/35100c14 | 24x44/0d013ef9 | 24x44/755c2d40 | 24x44/755c2d40 |
| chapter2 | 24x44/35100c14 | 24x44/0d013ef9 | 24x44/755c2d40 | 24x44/755c2d40 |
| chapter3 | 24x44/9b91ad5c | 24x44/dc194fc4 | 24x44/d2be4bc6 | 24x44/d2be4bc6 |
| chapter4 | 24x44/9b91ad5c | 24x44/dc194fc4 | 24x44/d2be4bc6 | 24x44/d2be4bc6 |
| chapter5 | 24x44/9b91ad5c | 24x44/dc194fc4 | 24x44/d2be4bc6 | 24x44/d2be4bc6 |

结论：**V1 = ch1 = ch2**，**V2 = ch3 = ch4 = ch5**。

## 4. 本轮落盘到 `deltarune_ralsei/` 的四帧

| 文件 | 尺寸 | md5 前12 | 字节 |
|---|---|---|---|
| spr_ralsei_sit_0.png | 24x44 | 31e9c4ba7748 | 683 |
| spr_ralsei_sit_1.png | 24x44 | a6657b23d8f4 | 655 |
| spr_ralsei_sit_2.png | 24x44 | f4591ee257a5 | 621 |
| spr_ralsei_sit_3.png | 24x44 | f4591ee257a5 | 621 |

选型规则：本库 `spr_ralsei_darkchurch_sit_happy_0` 与 **ch4** 像素完全相同；
60 个随机样本里 ch4 命中率最高（23.3%，ch3 20% / ch5 16.7% / ch2 13.3% / ch1 0%）
⇒ 取 **ch4 版（V2）**，与库内其余美术同代。

## 5. 必须向用户说明的一处美术差异

`spr_ralsei_sit` **五章全部是「戴帽（hooded）」版**；而桌宠现有库
（`deltarune_ralsei/`）是**「摘帽」版**：

- `spr_ralsei_hug_0.png` **根本不存在**，只有 `spr_ralsei_hug_hatless_0..3.png`；
- 真机截图 `第51轮-真机巡行与交互/_evidence/live_03_petzoom_x3.png` 里，桌面上的 Ralsei 是**白脸无帽**。

⇒ 直接接入后，**待机坐下时他会戴着帽子**。这是原作电梯场景的真实美术（ch1 全程戴帽），
但与本桌宠的默认造型不一致。备选：`spr_tea_party_ralsei_sit_*`
（7 种**摘帽**坐姿，中文名「茶会」，第52轮曾建议用它做待机循环）。

## 6. 附：E 盘 exFAT 间歇性故障（第53轮 P1 的直接实证）

本轮**同一次会话内复现 2 次**：

1. `os.makedirs(E:\Download\_tmp\str54)` → `OSError: [WinError 1] 函数不正确`（第 1 次失败，重试即成功）；
2. `open(E:\...\gml_Object_obj_elevatorcontroller_Step_0.gml)` → `OSError: [Errno 22] Invalid argument`（第 1 次失败，重试即成功）。

⇒ 第53轮报告里 `data_store._movable()` 注释所称「失败**极罕见**」
（原文：*"极罕见：回不去就把探针当正式文件留着"*）与实测不符：
E 盘（exFAT，卷标「肖翰哲」）的 `rename` / `makedirs` / `open` 都会**间歇**失败一次。

同一轮内 `E:\RalseiMemory\config.json` 的 mtime 停在 **2026-09-19 10:32**（8 天未变），
且内容仍是 `api.model = 'ralsei:v3'`（当前默认底座已是 `ralsei:v4`）
⇒ 与「设置改了不生效」的用户体感一致。
