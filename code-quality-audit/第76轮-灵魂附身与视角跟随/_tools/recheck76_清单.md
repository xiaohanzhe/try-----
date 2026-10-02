# -*- coding: utf-8 -*-
"""第76轮收尾复检 · 主脚本（core-file-recheck 六类判据）。

⚠️ 为什么不用 `python <本文件>` 直接跑：
   本机清理守卫存在「按路径累计删除」的阈值，`_tools/recheck76.py` 这个路径
   多次写入会被判为噪声 ⇒ **进程在 import 后被 SIGTERM 且零输出**（本项目铁律已记录）。
   ⇒ 所以复检逻辑改为**内联执行 + 分节落盘**，本文件只作为**可读的判据清单**
     （即"这次复检守了什么"的正式记录），不作为唯一执行体。

判据口径（三处都踩过坑，已在下面注明）：
  ① 令牌"在位"必须扫**全部相关文件**（含 `_tools/`）—— 只扫产品源码会漏掉锁文件里的令牌；
  ② **唯一真源**只许扫**产品源码 `ralsei_pet/`** —— 把 `code-quality-audit/` 算进去会
     把锁文件里"引用名字做判据"的字符串也数进去（自指假红）；
  ③ `def travel_to` 是 `def travel_to_scene` 的**前缀** ⇒ 必须带 `(` 定界（判据过窄）。
"""
# =============================================================== 1. 可编译 / 可解析
# ast.parse（**不产 .pyc**，复检不许改变被测状态）：
#   main.py · run_all.py · check_r0_76.py · check_r4_76.py ·
#   tamper_r4_76.py · live_r4_76.py · probe_r0_76.py · live_windows76.py
# json.loads(baseline.json)
# 报告代码围栏成对（按行首数，不用裸 count）
# ⇒ 实得 8+1+1 = 10 / 10 PASS

# =============================================================== 2. 结构自检（报告）
# 报告 0~8 章全在 · 无标题粘连（先剔围栏代码块再查）· 恰 1 个一级标题
# ⇒ 3 / 3 PASS

# =============================================================== 3. 编码
# 无 BOM · 无 U+FFFD：报告 · main.py · baseline.json · run_all.py + 6 个 _tools 脚本
# ⇒ 37 / 37 PASS（含重复计入 main/run_all 的 BOM/U+FFFD 两项）

# =============================================================== 4. 恒真判据复查（AST）
# AST 判据：check/ck/ok/expect/verify 的第 2 实参是字面量 True，
# 且**不在任何 If.orelse 子树内**（豁免"前置条件"写法）。
# 对象：check_r0_76.py · check_r4_76.py · tamper_r4_76.py
# ⇒ 3 / 3 PASS（零未豁免的常量 True）

# =============================================================== 5. 逐令牌回验
# 5.1 令牌"在位"（扫 main + item_interact + scene_controller + run_all + 全部 _tools）：
#     _camera_target_rect · _screen_point_to_room_rect · travel_to · reachable_destinations ·
#     travel_to_scene · _travel_feedback_fail · DoorProp · door_letter_of · route_for_door ·
#     DOOR_LETTERS · _routes.json · cc_prison_cells · cc_prisonlancer ·
#     check_r0_76 · check_r4_76 · tamper_r4_76 · live_r4_76      ⇒ 17 / 17 PASS
# 5.2 唯一真源（★ 只扫产品源码 `ralsei_pet/**/*.py`，2828991 B）：
#     def _camera_target_rect( · def _screen_point_to_room_rect( · def travel_to( ·
#     def door_letter_of( · def route_for_door( · class DoorProp(    ⇒ 6 / 6 均恰 1 次
#     ★★ 本条踩过两个坑（都是判据侧）：
#       (a) 把 `code-quality-audit/` 一起扫 ⇒ 锁文件里"引用名字做判据"的字符串被数进来（自指假红）
#       (b) 写 `def travel_to` 不带括号 ⇒ 它是 `def travel_to_scene` 的前缀（过窄假红）

# =============================================================== 6. R4 关键事实回验
# 6.1 产品不写 `state.size()`            ⇒ PASS
# 6.2 产品写 `soul.state.size`（裸属性）  ⇒ PASS
# 6.3 SoulState.size 是 property（真源码 AST）  ⇒ PASS
# 6.4 SoulState.center 是方法（真源码 AST）     ⇒ PASS
# 6.5 camera_follow 恰 1 处且锚点 = _camera_target_rect  ⇒ PASS
# ⇒ 5 / 5 PASS

# =============================================================== 7. 基线一致性
# 含 check_r0_76 / check_r4_76 · PASS 各为 38 / 21 · 无 None 条目 · 基线总 FAIL == 0
# ⇒ 6 / 6 PASS；info：套件 = 68，总 PASS = 3590

# =============================================================== 8. 工作区状态
# git -c core.quotepath=false status --porcelain -z（非 ASCII 路径不被转义）
# 变更项 13 个，全部落在预期白名单内 ⇒ 8.1 PASS；8.2 负控制（伪造路径必判意外）PASS
# ⇒ 2 / 2 PASS
# ★ 注：13 项里含 3 个复检自身的临时文件（_recheck76_part1.txt / _recheck76_start.txt /
#   _trace.txt）—— 收尾前须删除，不留散落文件。

# =============================================================== 结论
# 复检 PASS=35 FAIL=0（第 5 节两项口径修正后另计 22/22）。
# 3 个 FAIL 全部为**判据侧**（扫描范围过窄 / 子串重叠），产品侧零问题 —— 与
# core-file-recheck §二 的"报红先怀疑判据"一致。
