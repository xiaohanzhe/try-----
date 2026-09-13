# 第五轮代码审查 · 04_ai_growth（AI 决策 / 自主代理 / 养成 / 自定义 / 娱乐）

> 审查范围：`pet_ai.py`、`ai_driver.py`、`autonomous_agent.py`、`social_growth_system.py`、`customization_system.py`、`entertainment_system.py`
> 审查方式：逐行精读 + 跨文件交叉验证（仅只读，未改动任何源码/数据）
> 结论概览：**未发现可达的 P0（崩溃/数据丢失/任意命令执行）**；发现 **P1×3、P2×5、P3×8**。

---

## 一、发现汇总表

| # | 文件:行 | 类别 | 严重度 | 状态 | 一句话 |
|---|---------|------|--------|------|--------|
| 1 | social_growth_system.py:546 `first_touch` | 名实不符/错误解锁 | **P1** | 已证实 | `level>=1` 恒成立→首次加分即解锁，与"初次触摸"无关 |
| 2 | social_growth_system.py:543-593 | 名实不符/逻辑真空 | **P1** | 已证实 | 成就条件整体脱离描述（连续天数/送礼/聊天均用等级近似，且"事件调用unlock"路径不存在） |
| 3 | entertainment_system.py:515 | 名实不符/错误解锁 | **P1** | 已证实 | `game_master` 仅凭 `games_played>=4` 解锁，可重复玩同一游戏刷出 |
| 4 | social_growth_system.py:182,190 | 数据缺陷 | P2 | 已证实 | `guardian` 与 `caretaker` 显示名同为"守护者" |
| 5 | social_growth_system.py:544-545(注释) | 与声称不符 | P2 | 已证实 | 注释称"事件调用 `unlock`"，但全工程无 `unlock` 方法 |
| 6 | autonomous_agent.py:546,626-628 | 安全潜伏/死代码 | P2 | 已证实(已防御) | DELETE 分支带 `confirm=False`，当前不可达，一旦重启用即静默删文件 |
| 7 | customization_system.py:138-265 | 重复编码/混淆 | P2 | 已证实 | DEPRECATED 方法与活方法并存，同功能两份实现 |
| 8 | pet_ai.py:415-500 | 看着在用但未生效 | P2 | 已证实 | `check_action_triggers` 非基础动作被 `trigger_action` 白名单拦截，emotion_action_match 等逻辑基本失效 |
| 9 | ai_driver.py:101 | 死代码 | P3 | 已证实 | `ANIMATION_FALLBACK{"stretch":...}` 永不命中（stretch 不在 `ANIMATION_ACTIONS`） |
| 10 | pet_ai.py:119,138,177 | 死分支 | P3 | 已证实 | `trigger_cower/trigger_kneel_cry/trigger_wave_start` 恒返回 False 却仍注册在 `action_triggers` |
| 11 | social_growth_system.py:389-391 | 死状态 | P3 | 已证实 | `consecutive_days/last_interaction_day/daily_interaction_count` 永不被更新 |
| 12 | social_growth_system.py:682-689 | 功能未实现 | P3 | 已证实 | `check_other_pets` 返回硬编码模拟数据（注释自承） |
| 13 | entertainment_system.py:509 | 潜伏缺陷(疑点) | P3 | 疑点 | `perfect_score` 需 `score>=100`，多数游戏分数模型未保证可达 |
| 14 | customization_system.py:184-248 | 重复编码 | P3 | 已证实 | `reset_customization` 硬编码整份默认配置，与 `__init__` 重复 |
| 15 | social_growth_system.py:437-439 | 轻微数据缺陷 | P3 | 已证实 | 旧档含未知成就 id 时，orphan id 残留于 `self.achievements` |

> **安全专项结论（P0 排查）**
> - **自主代理执行权限**：`_execute_action` 调用的 `open_file/open_folder/examine/close/minimize/resize/delete` 均为 win32/枚举目标上的受控操作，**不经过 shell**，不存在把文件名/LLM 输出当命令执行的通路。**已防御**。
> - **提示注入→命令执行**：`ai_driver._execute` 对 `action` 严格走白名单（动画/WANDER/PASSIVE/sleep/wake/say），未知动作一律忽略；`say` 仅作为对话文本展示，不执行。**已防御**。
> - **越权文件操作**：`delete_file(confirm=False)` 存在但 `_pick_action` 永远不返回 `DELETE`（窗体类只返回 `OBSERVE`，文件/文件夹只返回 `OPEN/EXAMINE/OBSERVE`）。`DRAG/CLOSE_WINDOW/MINIMIZE_WINDOW/RESIZE_WINDOW` 同样不可达。**已防御，但属潜伏风险（见#6）**。
> - **白名单绕过**：自主代理不解析外部提供的任意路径，目标仅来自桌面枚举与窗口枚举，无 `..`/通配符/短文件名注入面。**已防御**。

---

## 二、逐条详情

### P1-1 【已证实】`first_touch` 成就必定解锁 —— social_growth_system.py:546
- **类别**：名实不符 / 成就错误解锁（用户可见功能错误）
- **关键片段**
  ```python
  'first_touch': lambda s: s['level'] >= 1,   # level 初始即 1，恒成立
  ```
- **出错机理**：`level` 初始化为 1，`_check_achievements` 在每次 `add_experience` 时调用。由于 `level>=1` 永远为真，"初次触摸"会在这只宠物第一次获得经验时（例如任何一次聊天/问候奖励）**无条件解锁**，与用户是否真的触摸过 Ralsei 毫无关系。
- **触发路径**：首次 `add_experience`（如 `interaction_types.greet` 给 5 经验）→ `_check_level_up`→`_check_achievements`→`first_touch` 条件满足→`_unlock_achievement('first_touch')`。
- **修复建议**：要么移除该 level 兜底、改为由真实触摸事件统计计数解锁；要么将描述改为"初次陪伴"，消除名实不符。其余 `first_interaction`(需 exp≥10)、`first_gift`(需 level≥2) 同为近似，建议统一口径。

### P1-2 【已证实】成就解锁条件整体与描述脱钩，且声明的解锁入口缺失 —— social_growth_system.py:543-593 + 注释 544-545
- **类别**：名实不符 / 与声称功能不符（P2 的底层根因，此处按"用户可见错误解锁"定 P1）
- **关键片段**
  ```python
  # 注释：首次触发即解锁（由对应事件调用 unlock，这里做兜底检查）
  'daily_visitor':   lambda s: s['level'] >= 3,    # 描述"连续5天互动"
  'weekly_visitor':  lambda s: s['level'] >= 5,    # 描述"连续7天互动"
  'monthly_visitor': lambda s: s['level'] >= 10,   # 描述"连续30天互动"
  'first_gift':      lambda s: s['level'] >= 2,    # 描述"第一次送礼物"
  ```
- **出错机理**：① 交叉验证确认全工程**不存在 `def unlock` / `.unlock(`**（仅在注释中声称）。所谓"事件调用 unlock"从未实现，`_check_achievements` 是**唯一**解锁路径，且全部用 `level/experience/evolution_stage` 近似。② "连续 N 天"类成就用等级近似，只要练到对应等级即解锁，未真实统计连续天数（`consecutive_days` 等字段从不更新，见 P3-11）。③ 体验上表现为"没做过的事也解锁了"，属用户可见的功能错误。
- **触发路径**：等级随经验自然增长 → `_check_achievements` 命中近似条件 → 解锁与描述不符的成就。
- **修复建议**：建立真实统计（连续天数计数、送礼/触摸/聊天计数器），或显式将成就改为"等级里程碑"并同步更新描述，避免误导。同时删除"由事件调用 unlock"的错误注释。

### P1-3 【已证实】`game_master` 可刷出，与"完成所有游戏"不符 —— entertainment_system.py:515
- **类别**：名实不符 / 成就错误解锁
- **关键片段**
  ```python
  if self.activity_stats['games_played'] >= len(self.games) and not ...['game_master']['unlocked']:
      # len(self.games)==4，且 games_played 每次 end_game +1，不区分游戏
  ```
- **出错机理**：`games_played` 在 `end_game` 中无条件 `+1`，不区分 `game_id`。`len(self.games)=4` 意味着**把同一个游戏玩 4 次**即可解锁"游戏大师（完成所有游戏）"，完全背离描述。
- **触发路径**：连续 4 次 `end_game('matching_game', ...)` → `games_played=4` → 解锁。
- **修复建议**：改为记录"已玩过的不同 game_id 集合"，集合大小 == `len(self.games)` 才解锁；或按描述改为"通关全部 4 款游戏各至少一次"。

---

### P2-4 【已证实】两个成就显示名冲突"守护者" —— social_growth_system.py:182 & 190
- **类别**：数据缺陷
- **关键片段**：`guardian` 的 `'name': "守护者"`（行182，描述"始终保护Ralsei的隐私"），`caretaker` 的 `'name': "守护者"`（行190，描述"连续30天照顾"）。
- **机理/触发**：成就面板会出现两条同名"守护者"，用户无法区分；UI 若以 `name` 做去重/索引还会错乱。
- **修复**：将 `caretaker` 改名（如"守护者"→"照料者/长期陪伴"），并校验 `achievements_list` 内 `name` 唯一。

### P2-5 【已证实】声称的 `unlock` 入口不存在 —— social_growth_system.py:544-545（注释）
- **类别**：与声称功能不符（审查要点 7）
- **机理**：全局 grep 确认无 `def unlock`、无 `.unlock(` 调用。`_check_achievements` 是唯一解锁路径，且为等级近似兜底。注释承诺的"事件调用 unlock"是真空实现。
- **修复**：补齐真实事件计数 + `unlock(achievement_id)` 方法，或删除误导性注释。

### P2-6 【已证实(已防御)】DELETE 死代码带 `confirm=False` 危险默认值 —— autonomous_agent.py:546,626-628
- **类别**：安全潜伏缺陷 / 死代码（审查要点 2）
- **关键片段**
  ```python
  elif t.action == InteractionType.DELETE:
      if t.target.path:
          d.delete_file(t.target.path, confirm=False, send_to_recycle=True)
  ```
- **机理**：`_pick_action`（行447-481）对 window→OBSERVE，folder→[OPEN,OBSERVE,EXAMINE]，file→[OPEN,EXAMINE,OBSERVE]，**永不返回 DELETE/DRAG/CLOSE/MINIMIZE/RESIZE**。因此该 `delete_file(confirm=False)` 当前**不可达**（已防御）。但它是"一旦有人把 DELETE 重新加回 `_pick_action` 选择集就会静默送回收站"的定时炸弹，且 `confirm=False` 关闭了二次确认。
- **触发前提（若失效）**：`_pick_action` 的选择列表重新包含 `DELETE`，则自主代理每轮可能自动删除用户桌面文件。
- **修复**：彻底删除 `_execute_action` 中 DELETE/DRAG/窗口破坏性分支（既不可达又危险），或显式要求 `confirm=True` 且由用户显式指令路径触发（仅 `main.handle_window_operation` 走用户命令）。

### P2-7 【已证实】DEPRECATED 与活方法并存，同功能两份实现 —— customization_system.py:138-265
- **类别**：重复编码 / 维护混淆（审查要点 8）
- **机理**：存在 `update_behavior_DEPRECATED` 与 `update_behavior`、`update_content_preferences_DEPRECATED` 与 `update_content_preferences`、`apply_appearance_changes_DEPRECATED` 与 `apply_appearance_changes`、`get_available_outfits_DEPRECATED` 与 `get_available_outfits` 等成对方法。两者实现/返回列表不一致（如 `get_available_outfits` 新版 18 项 vs 旧版 5 项）。调用方若误用旧版将拿到错误选项集。
- **修复**：删除所有 `*_DEPRECATED` 方法；若需向后兼容，保留一个并 `@deprecated` 标注，且内部委托给活方法，避免逻辑分叉。

### P2-8 【已证实】`check_action_triggers` 逻辑基本失效 —— pet_ai.py:415-500
- **类别**：看着在用但未生效（审查要点 7）
- **机理**：`trigger_action`（行502-528）对白名单 `_BASIC_ANIM_WHITELIST`（仅 idle/walk*/run*）之外的动作一律 `return` 拦截。而 `check_action_triggers` 在 rest/idle/interact/play 状态下检查的动作（look_up/pose/tea/laugh/wave/hug/nuzzle/dance/sing/roll）**均不在白名单**，要么被 `action==current_animation` 跳过、要么被 `trigger_action` 拦截。结果是：除 move 状态能触发 walk、其余状态大多只能触发 `idle`。文件中精心编写的 `emotion_action_match`（行464-475）、复杂动作冷却分流（行489-497）对表演动画形同虚设。
- **触发/影响**：非崩溃，但"AI 表情/情绪匹配"的设计意图未落地，体验上宠物几乎不自发表演（表演完全依赖 ai_driver）。属"声明能力 > 实际能力"。
- **修复**：要么让 `check_action_triggers` 在非 move 状态下只检查 idle（与白名单一致、删掉无效分支），要么放开 `trigger_action` 对表演动画的拦截并补上冲突守卫——但二者必须一致，不能一个想触发一个拦截。

---

### P3-9 【已证实】`ANIMATION_FALLBACK` 永不生效 —— ai_driver.py:101
- **类别**：死代码
- **机理**：`_execute` 用 `action in ANIMATION_ACTIONS` 命中（行446），而 `ANIMATION_ACTIONS = set(ANIMATION_METADATA.keys())` 不含 `"stretch"`。模型即使输出 `stretch`，先在第388行小写化，第446行不在集合→落入未知动作→返回 False（按幻觉处理）。`ANIMATION_FALLBACK` 的 `stretch→pose` 映射永远用不上。
- **修复**：若确要支持 stretch，将其加入 `ANIMATION_METADATA` 或在命中前先做 `action = ANIMATION_FALLBACK.get(action, action)`；否则删除该无用字典。

### P3-10 【已证实】恒返回 False 的触发器仍注册 —— pet_ai.py:119,138,177
- **类别**：死分支
- **机理**：`trigger_cower`/`trigger_kneel_cry`/`trigger_wave_start` 直接 `return False`，却仍在 `action_triggers`（行54-59,72-73）中占键。`check_action_triggers` 每轮对它们做冷却判断 + `trigger_func()` 调用，纯属浪费；且与"动作存在但永不触发"的潜在误解叠加。
- **修复**：从 `action_triggers` 移除恒 False 项，或在注释中明确"仅供事件触发、轮询不触发"。

### P3-11 【已证实】连续天数统计字段从不更新 —— social_growth_system.py:389-391
- **类别**：死状态
- **机理**：`consecutive_days / last_interaction_day / daily_interaction_count` 在 `__init__` 初始化，但全类无任何地方写回（没有"跨天+1/断签清零"逻辑）。与之相关的 `daily_visitor/weekly_visitor/monthly_visitor` 成就只得用 `level` 近似（见 P1-2）。
- **修复**：在每日首次互动时更新 `last_interaction_day` 并维护 `consecutive_days`；或删除这些字段避免误导。

### P3-12 【已证实】`check_other_pets` 返回硬编码 mock —— social_growth_system.py:682-689
- **类别**：功能未实现（审查要点 7）
- **机理**：方法注释自承"暂时返回模拟数据"，返回固定两个宠物。任何调用方（社交成就 `social_butterfly/popular/community_leader` 依赖"认识其他宠物"）拿到的都是假数据，相关成就只能靠等级近似解锁。
- **修复**：接入真实多宠物发现，或明确标注为未实现并关闭相关 UI 入口，避免"看起来有功能实则假数据"。

### P3-13 【疑点】`perfect_score` 可能永远不可达 —— entertainment_system.py:509
- **类别**：潜伏缺陷（疑点，需看游戏实现）
- **机理**：`if score >= 100` 解锁"满分达人"。但各 `games` 的计分模型在 `entertainment_system` 之外实现，本报告范围内未见 score 是否能达到 100。若某游戏满分上限 <100，则该成就不可达成（违反"可达成"审查点）。
- **触发**：端到端实测各游戏最高得分。当前标记为疑点，非已证实缺陷。
- **修复**：将阈值改为"各游戏自身满分"或 `score == max_score`，而非硬编码 100。

### P3-14 【已证实】`reset_customization` 硬编码整份默认配置 —— customization_system.py:184-248
- **类别**：重复编码（审查要点 8）
- **机理**：把 `__init__` 里那份默认 dict 又抄了一遍（约 60 行）。两处默认必须同步维护，当前已存在不一致风险（例如若将来 `__init__` 增加一个 appearance 字段，reset 会遗漏）。
- **修复**：抽出一个 `_default_config()` 工厂函数，供 `__init__` 与 `reset_customization` 共用。

### P3-15 【已证实】旧档未知成就 id 残留 —— social_growth_system.py:437-439
- **类别**：轻微数据缺陷
- **机理**：加载时 `if achievement_id in self.achievements_list` 才标记 unlocked，但 `self.achievements` 列表仍保留该未知 id。`get_achievements()` 不返回它，可它 persist 在文件里循环往返，可能随时间累积垃圾 id。
- **修复**：加载时过滤掉不在 `achievements_list` 的 id。

---

## 三、边界 / 异常处理 复核（要点 4、5、6）

- **空列表 `random.choice`**：已审查并确认——`move_to_random_location` 用 `max(51, max_x)` 防 `randint(a>b)`；`_pick_destination` 用 `max(101, ...)`；`interact_with_something` 的 `random.choice(folders/files)` 均有 `if folders:/if files:` 守卫；`interact_with_something` 的 `random.choices` 权重和恒为 1。**已防御**。
- **除零**：`adjust_probabilities_based_on_state` 对 `total<=0` 回退均分（行366-372）；`apply_appearance_changes` 对 `animation_speed<=0` 回退 1.0（行387-388）；`get_progress_to_next_level` 对 `level_range>0` 有守卫（行742）。**已防御**。
- **裸 except / 静默 pass**：少量存在但均伴随 `_log.debug/warning`（如 pet_ai:682,722；ai_driver 各处），未发现"裸 except + 完全吞掉且掩盖关键错误"的危险模式。`react_to_event` 的 `user_dragged_forcefully` 分支用 `except Exception: pass`（行722）吞掉情绪写入异常，影响极小。
- **冷却卡死**：自主代理 WALKING 已有 18s 超时兜底（行274-277，`_task_started_at` 已正确更新，见行503 修复注释）；ai_driver `_busy` 有 90s 强制复位（行282-284）。**已防御**。

---

## 四、最严重三条（含文件:行）

1. **social_growth_system.py:546** — `first_touch` 用 `level>=1`（恒成立）作解锁条件，首次获得经验即错误解锁"初次触摸"，与用户行为无关（P1，名实不符/错误解锁）。
2. **social_growth_system.py:543-593（根因 544-545）** — 成就整体用等级近似解锁，且注释承诺的"事件调用 `unlock`"方法全工程不存在，连续天数统计字段从不更新（P1，与声称功能不符 + 名实不符）。
3. **entertainment_system.py:515** — `game_master` 仅凭 `games_played>=4` 解锁，可重复玩同一游戏刷出，与"完成所有游戏"描述严重不符（P1，错误解锁）。

> 配套安全结论：自主代理的 `delete_file(confirm=False)`（autonomous_agent.py:628）与窗口破坏性操作当前**不可达**（`_pick_action` 仅返回 OPEN/EXAMINE/OBSERVE），`ai_driver` 对 LLM 输出严格白名单，无可达的任意命令执行 / 越权文件操作路径——**P0 为 0**。
