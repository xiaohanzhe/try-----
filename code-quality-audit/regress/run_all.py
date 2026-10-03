# -*- coding: utf-8 -*-
"""G2 回归基线：一条命令跑完全部回归套件，并对"归一化后的输出"做逐字节比对。

背景（见 `架构改造排期方案_H4-H5_2026-09-13.md` §3 G2）：
项目此前有 9 个手工冒烟脚本 + 每轮的 verify 脚本，但**没有一键可跑的回归入口**，
这是 H4 上帝类拆分最大的障碍——拆分的安全性判据是"行为完全不变"，
只能靠"改造前后跑同一套回归、输出逐字节一致"来证明。

本脚本做三件事：
  1. 按固定顺序、固定环境（offscreen / UTF-8 / 固定 cwd）跑全部套件；
  2. 把输出**归一化**（抹掉时间戳、内存地址、耗时、绝对路径、空行差异）后取 SHA-256；
  3. 与 `baseline.json` 比对：退出码 + PASS/FAIL 计数 + 归一化文本哈希，三项全同才算 IDENTICAL。

用法：
  python run_all.py                 # 跑全部并与基线比对（退出码 = 是否有套件 FAIL/DIFF）
  python run_all.py --update        # 重建基线（只在"改动是有意的"时候用）
  python run_all.py --only s1       # 只跑名字匹配的套件（子串匹配，可多次）
  python run_all.py --list          # 只列套件
  python run_all.py --verbose       # 把原始输出也打到控制台
  python run_all.py --show-diff s1  # 打印某套件的归一化 diff

产物：
  code-quality-audit/regress/baseline.json          基线（纳入 git）
  code-quality-audit/regress/_out/<suite>.txt       原始输出（不纳入 git）
  code-quality-audit/regress/_out/<suite>.diff.txt  出现 DIFF 时的差异
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT_DIR = os.path.join(HERE, '_out')
BASELINE = os.path.join(HERE, 'baseline.json')
SEED_RUNNER = os.path.join(HERE, '_seed_runner.py')
# 固定随机种子：套件里存在 random.choice（如对话承接语），不钉死就必然漂移。
SEED = 20260913

# ---------------------------------------------------------------- 套件清单
# 顺序固定：先快后慢，先静态后运行时。
#   offscreen=True  → 注入 QT_QPA_PLATFORM=offscreen（涉及 QWidget/QPixmap 的套件必须）
#   needs         → 该套件依赖的前置文件，缺失即判 SKIP（而不是 FAIL）
#   env           → 可调用的"额外环境变量工厂"，返回 (dict, 待清理目录或 None)

def _make_hermetic_env():
    """给「会实例化整个 App」的套件一套每轮全新的隔离存储。

    为什么必须隔离（第十三轮发现的基线缺陷）：
      round8_anim 里会 `RalseiPet()`，于是 memory_system / data_store 真的去解析
      **真实**存储位置。第九轮起记忆住在 E 盘（`E:\\RalseiMemory`），而
      `data_store.vault_root()` 是**委托** `memory_store.find_device_dir()` 的 ——
      所以只强制 `RALSEI_MEMORY_DIR` 一个变量，记忆库与 7 类运行时产物会一起被隔离。

    不隔离的两个后果：
      1. 基线不封闭：套件输出随「E 盘是否在线」「E 盘上是否已有 memory.json」漂移。
         实测症状：E 盘接回后，"新位置无记忆，已从旧版 memory.json 继承"这行不再打印
         → round8_anim 与基线 DIFF（假警报，而真正的回归会被这堆噪声淹没）。
      2. 测试污染用户真实数据：套件跑一次就会往用户 E 盘写日志/成长数据。

    `tempfile.mkdtemp` 保证"新位置一定为空"→ "从旧版继承"必然发生 → 输出可复现；
    路径经 normalize() 归一成 <TMP>，所以每轮不同的随机目录名不会造成漂移。
    """
    base = tempfile.mkdtemp(prefix='ralsei_g2_iso_')
    return {'RALSEI_MEMORY_DIR': os.path.join(base, 'RalseiMemory')}, base


# 需要"隔离真实存储"的套件：凡是会 `RalseiPet()` / 触碰 memory · data_store
# 的套件都在此列。不隔离有三个后果：
#   1. 基线不封闭（输出随"E 盘在不在线""E 盘上有没有 memory.json"漂移）；
#   2. 往用户真实的 E 盘写运行时产物（日志/成长数据/记忆）；
#   3. **第十三轮实测的真问题**：`memory_store._is_writable_dir` 老实现每次调用
#      都真的 建/写/删 一个 `.write_probe`，一次启动被调十几次；17 个套件跑一轮，
#      同一路径 `E:\RalseiMemory\.write_probe` 单轮被删 50+ 次，累积撞上宿主沙箱的
#      删除配额守卫 → 每个套件进程在**开头就被掐掉**，输出只剩
#      `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]`，
#      全套件 `exit=1 PASS=0`（11 个假 DIFF 的真凶，见记忆_store 的快路径修复）。
# 强制 `RALSEI_MEMORY_DIR` 会让 `find_device_dir` 直接 return，连探针都不会跑。
HERMETIC_IDS = frozenset({
    'round5_smoke', 'round5_verify', 'round6_verify',
    's1_anim_miss', 's2_anim_json', 's3_alias_legacy',
    'round8_dialogue', 'round8_floor', 'round8_fling',
    'round9_focus', 'round13_build', 'round14_move', 'round15_cleanup',
    'persona_chat', 's8_stream', 's7_event_speech', 'box_round44',
    'camera_round44', 'render_round44', 'canvas_round44', 'routes_order44',
    'objects_round44', 'anim_round44', 'pathfind_round45',
    'rooms_round47', 'walk_round47', 'npc_round49', 'bubble_round50',
    'dialog_turn52', 'dialog_clean52', 'dialog_lounge52',
    'sit_round54',
    # 第55轮：两者都真机 `RalseiPet()`（灵魂窗口 + NPC 服务建在真 App 上）
    'soul_round55', 'npc_persona55',
    # 第56轮：真机 `RalseiPet()`（站位 / 游荡 / 编队 / 桌面闸都建在真 App 上）
    'npc_place56',
    # 第67轮：真机 `RalseiPet()`（幽灵窗口 + 接触时钟建在真 App 上）——
    #   ⚠️ 它**自己**也会 `setdefault('RALSEI_MEMORY_DIR', %TEMP%)`，
    #   所以这里给它 hermetic 环境是**双保险**：run_all 给的是"每轮全新 mkdtemp"，
    #   基线才封闭（否则会随"上次跑留下的 ghost_state.json"漂移）。
    'check67',
    # 第73轮：真机 `RalseiPet()` —— **第74轮 B11 实补**。
    #   ★ 它原来的注释写着"隔离内存记忆，绝不碰用户 E:\RalseiMemory 保管库"，
    #     但**这句是假的**：`check73.py` 里 `_pet = M.RalseiPet()` 在**构造期**就把
    #     真实保管库定下来了（夹具到第585行才换 `_pet.npc_memory`，为时已晚），
    #     而且构造期那行日志把**真实路径**打进了输出 —— 实证：
    #       `记忆落盘=E:\RalseiMemory\npc_memory`（归一化后**仍在**，见
    #       `_tools/audit_env_leak74.py`）。两个后果：① 基线不封闭（E 盘掉线即假 DIFF）；
    #     ② 跑一次就往用户真实保管库写东西。这里补进名单，让 `find_device_dir` 直接 return。
    'check73',
})


SUITES = [
    {
        'id': 'round5_smoke',
        'script': os.path.join(ROOT, 'code-quality-audit', '第五轮', 'smoke_import_round5.py'),
        'offscreen': False,
        'desc': '第五轮：modules 全量导入冒烟（模块数随新增模块而变，勿把具体数字写进描述）+ 2 个源码不变量',
    },
    {
        'id': 'round5_verify',
        'script': os.path.join(ROOT, 'code-quality-audit', '第五轮', 'verify_round5_fixes.py'),
        'offscreen': True,
        'desc': '第五轮：16 项缺陷修复断言（对话/施法/成就/记忆）',
    },
    {
        'id': 'round6_verify',
        'script': os.path.join(ROOT, 'code-quality-audit', '第六轮', 'verify_round6_fixes.py'),
        'offscreen': True,
        'desc': '第六轮：39 项行为修复断言（对话/甩飞/抛物线/帧率/多屏）',
    },
    {
        'id': 'round7_launch',
        'script': os.path.join(ROOT, 'code-quality-audit', '第七轮', 'verify_round7_launch_import.py'),
        'offscreen': True,
        'desc': '第七轮：文档化启动（仅 src/ 在 path）不再 ModuleNotFoundError',
    },
    {
        'id': 's1_anim_miss',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s1_animation_miss.py'),
        'offscreen': True,
        'desc': 'H5-S1：动画名未命中自检 17 项 + 全样本等价性（样本数 = 动画组数，'
                '随素材组增减，勿把具体数字写进描述）',
    },
    {
        'id': 's2_anim_json',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s2_animations_json.py'),
        'offscreen': True,
        'desc': 'H5-S2：animations.json 与硬编码表深度等价 + 回落可用',
    },
    {
        'id': 's3_alias_legacy',
        'script': os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_s3_alias_legacy.py'),
        'offscreen': True,
        'desc': 'H5-S3：alias_of / legacy 显式化后语义仍等价',
    },
    {
        'id': 'round8_dialogue',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_dialogue.py'),
        'offscreen': True,
        'desc': '第八轮：对话框 ▼ 闪烁不再撑高抖动 + 滚动位置不被弹回顶部',
    },
    {
        'id': 'round8_floor',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_floor.py'),
        'offscreen': True,
        'desc': '第八轮：楼层身份改用稳定标识（不再"看到窗口就摔"）+ 落地同步 current_floor',
    },
    {
        'id': 'round8_fling',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_fling.py'),
        'offscreen': True,
        'desc': '第八轮：斜抛（方向由松手速度定）+ 空中可二次抓住（按线速度缓冲减速）+ 卡动画自检',
    },
    {
        'id': 'round8_anim',
        'script': os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_anim.py'),
        'offscreen': True,
        'env': _make_hermetic_env,     # 会 RalseiPet()，必须隔离真实存储（见该函数注释）
        'desc': '第八轮：特殊动画只由 AI 触发（来源闸门）+ 播完不打断不移动 + 待机 10 分钟（第52轮由 3 分钟改口）+ 鞠躬锚点',
    },
    {
        'id': 'round9_focus',
        'script': os.path.join(ROOT, 'code-quality-audit', '第九轮', 'verify_round9_focus.py'),
        'offscreen': True,
        'desc': '第九轮：对话注意力锚（换题只能由用户发起）+ 对话框 20s 无输入隐藏（鼠标压输入栏不隐藏）+ 自主开口不打断聊天',
    },
    {
        'id': 'round9_memory',
        'script': os.path.join(ROOT, 'code-quality-audit', '第九轮', 'verify_round9_memory.py'),
        'offscreen': True,
        'desc': '第九轮：拟人记忆（选择性记住/联想召回/遗忘与日摘要/复习强化）+ 存储落 E 盘与桌面兜底搬运',
    },
    {
        'id': 'round10_graph',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十轮', 'verify_round10_graph.py'),
        'offscreen': False,
        'desc': '第十轮：分层关联图（强/中/弱边 + hub 惩罚）+ 受控多跳检索（路径打分/PPR/每跳过滤/'
                '重排去重/预算/LLM 验证钩子）+ 反馈学习边权 + 离线巩固 + 噪声率·有用率·成功率',
    },
    {
        'id': 'round11_input',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十一轮', 'verify_round11_input.py'),
        'offscreen': False,
        'desc': '第十一轮：联想输入端治理 —— 抽词结构剪刀（碎片灭/真词留/免伤名单/三层择优/'
                '分词器注入）+ 建边拓扑可配（实测后默认仍是 clique，star/chain 因多跳闸门不过而弃用）'
                '+ 多跳闸门 + 残渣账本',
    },
    {
        'id': 'round12_store',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十二轮', 'verify_round12_store.py'),
        'offscreen': False,
        'desc': '第十二轮：jieba 分词接入（走 set_segmenter 注入，软依赖+静默回落）+ 存储统一'
                '（E 盘为最终存储、本地只作中转站：data_store 解析/收编模板/回迁五条安全约定）'
                '+ 7 类运行时产物全部路由到数据根 + 初始化环回归锁'
                '（间接环 lazy_log + 有鉴别力的导入顺序断言）；E 盘真机确认补丁',
    },
    {
        'id': 'round13_build',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十三轮', 'verify_round13_build.py'),
        'offscreen': True,
        'desc': '第十三轮：「建楼」遮挡判定 + 窗口层数 + 渲染层序（按 Windows 原生口径）'
                '—— 可见区域矩形相减（含独立网格 oracle 交叉验证）/ 完全盖住即不存在 / '
                '楼层名次最前最高 / 站立·下落·跳跃都只在可见区域 / '
                'DWM 可见边框·幽灵窗口·按进程排除自身 / SetWindowPos 把宠物插到所站楼板之上',
    },
    {
        'id': 'round14_move',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十四轮', 'verify_round14_move.py'),
        'offscreen': True,
        'desc': '第十四轮：「建楼」的上下动 + 落到某一层楼 —— 楼层判定真正接进产品路径'
                '（防"改了没人调用"复演：行为级证明 check_nearby_windows 走 '
                '_nearest_floor_jump）/ 向上跳落点必须在可见区域（被遮处要被吸附回来）/ '
                '向下跳只到相邻下一层（禁穿透）/ current_window 与 current_floor 单真源同步 / '
                '落地当场结算并重排 z 序 / 用户抽走楼板（关窗）→ 生气动画 ≥5s',
    },
    {
        'id': 'round15_cleanup',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十五轮', 'verify_round15_cleanup.py'),
        'offscreen': True,
        'desc': '第十五轮：「建楼」死代码清干净 + 一个被错判的坠落起因'
                '—— 删 update_floor（第五轮 F3 点名的零调用漂移副本）/ '
                'check_nearby_windows 尾部裸矩形老启发式 / find_support_below（get_drop_destination 的重复）/ '
                'is_on_floor_edge（无消费者）；接线 is_floor_valid 区分'
                '"宠物自己走出楼板"（常规动画）与"用户关窗抽走楼板"（生气动画）',
    },
    {
        'id': 'round17_build_fall',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十七轮', 'verify_round17_build_fall.py'),
        'offscreen': True,
        'desc': '第十七轮：「建楼」缺口计划 · 批次 A —— G2 下落判据换成层高比较'
                '（关窗后**下方还有窗口**也要掉，复检的原例）+ G1 生气动画真的播且真的停满'
                '（关窗 ≥5s / 挪楼板 ≥3s：死参数 max_fall_duration 已清、落地不再被普通 splat 顶掉）',
    },
    {
        'id': 'round18_climb',
        'script': os.path.join(ROOT, 'code-quality-audit', '第十八轮', 'verify_round18_climb.py'),
        'offscreen': True,
        'desc': '第十八轮：「建楼」缺口计划 · 批次 B —— G3 层高闸门（走进去不再被静默提升，'
                '上楼/下楼都改成"跳";跨度 ≤一层用 jump、更大用 climb_* 攀爬素材）+ 落点预留水平距离'
                '+ 被动成因（关窗/要求⑪）不被误伤 + 摔扁门槛收紧到"落差 ≥两层"',
    },
    {
        # 命名刻意不叫 round19：本轮（对话 AI 人味改造）与「建楼」批次 B 同为第十八轮，
        # 编号已被占用；语义化 id 比编号更能说明它守的是什么。
        # 它**不联网、不调用 Ollama** —— 模型质量天生不可复现，不进基线。
        'id': 'persona_chat',
        'script': os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                               'verify_persona_chat.py'),
        'offscreen': True,
        'desc': '人味改造：角色设定外置单一真源（persona 无 markdown / 三条接法规则 / 桌宠化口径'
                ' / Deltarune 世界观知识 + 人物群像 + 第 5 章 + 元游戏词/攻略腔负控制）'
                '+ 接线修对（用户消息纯原话、【此刻】挂 system 尾、recent 抽 role==assistant）'
                '+ 输出护栏（markdown 剥除 / 句中括号动作只删那段 / 禁说清单：出戏＋客服腔（与事件链路同源）'
                ' / 自问自答截断 / 车轱辘话判退 / 超长截断）'
                '+ 判退后换说法重采样（FakeCli 行为级）+ 关键词收紧 + 载体层状态 + Modelfile 参数',
    },
    {
        # S8 流式输出：与人味改造同一轮（第十八轮 §5 的 S8），单独一个套件是因为
        # 它守的是"另一件事"——流式通路的接口契约与打字机增量显示。
        # 同样**不联网、不调用 Ollama**（首字延迟那类数值天生不可复现，见 _evidence/）。
        'id': 's8_stream',
        'script': os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                               'verify_s8_stream.py'),
        'offscreen': True,
        'desc': 'S8 流式输出：api_client 的 chat_stream（基类默认回落 chat，老 provider 不被打破；'
                'HTTP 真流式走 iter_lines(chunk_size=1) —— 实测默认攒批 0.45s vs 0.23s）'
                '+ SSE 解析 6 例（[DONE]/畸形行跳过/回调抛异常不中断/空流→None）'
                '+ main 接线（_api_delta 世代号、判退前 reset、故意不清 sink）'
                '+ 流式清洗前缀单调性穷举 + 两个已知非单调边界'
                '+ 有意分工：句中括号动作的删除只留在收尾层（流式层不删，见 C10d）'
                '+ 打字机增量显示 9 例（行为级桩：逐字喂入无回缩 / 队尾不停表 / finalize 两种收口）'
                '+ Qt 跨线程投递（真事件队列：分片按序到达主线程槽、丢弃过期世代、reset 顺序严格）'
                '+ ★第75轮：思考占位改为**可关**（用户裁定"别用那个思考的表情"）'
                '—— D14 判据随总开关分支且只断核心不变量（半句擦掉/停表/仍在等待态 _ai_pending），'
                '另加 D14b~D14d 显式翻开关的 A/B 对照（两档都能跑且 A≠B），'
                '并钉死开关是**模块级**常量（假对象夹具没有类属性/实例方法，实测撞过两次）',
    },
    {
        # S7 事件台词分批接 AI：与 S8 同一轮的第三块（§5 的 S7）。
        # 它守的是"罐头顶替 AI 的三个坑"：延迟（只在已登记事件上开 AI）、
        # 抢话（事件请求要给正在流式的对话让路）、一事件两气泡（兜底 + 迟到回复）。
        # 同样**不打网络、不调用 Ollama**（真机延迟数值见 _evidence/s7_e2e_*）。
        'id': 's7_event_speech',
        'script': os.path.join(ROOT, 'code-quality-audit', '人味改造-2026-09-18',
                               'verify_s7_event_speech.py'),
        'offscreen': True,
        'desc': 'S7 事件台词分批接 AI：档位白名单（未登记事件 = 行为不变，甩飞/摔扁/连点耳朵'
                '钉在罐头档）+ 唯一出口 speak_event（不再到处 add_dialogue）'
                '+ 让路三闸（主人打字中/对话流式中/_ai_inflight 在途）+ 流式首字兜底'
                '（900ms 内没出字才说罐头，整句 1.4s 不再必然输给罐头）'
                '+ 世代号丢弃迟到回复与过期分片 + 出戏闸（3B 实测会吐「我没有触觉」）'
                '+ 客服腔禁语闸 + 旁白闸（句首括号/星号 → 整句作废）'
                '+ 句中括号动作闸（只删那一段；补"只看句首"的洞，含负控制）'
                '+ 罐头去重窗口 + 一键开关 api.event_speech；含 D22 回归锁：'
                '**不许**用 _ai_delta_sink 当门（S8 收尾不清空它 → 会永久挡死事件 AI）',
    },
    {
        # 场景系统 P0 骨架（第二十八轮）。用户要求「后期加场景系统 / 留好拓展接口」，
        # 所以这一套守的是**接口在位**与**零行为变化**两件事：
        #   · 纯函数（resolve_anchor / pick_variant / depth_of / visible_objects）
        #     的正控制 + 负控制成对；
        #   · 初始化环纪律（scene_system 禁 import Qt / 禁 import 项目内模块）；
        #   · 控制器双向转发不成环、状态不劈裂（宿主预声明 9 字段 = 6 场景 + 3 路由）；
        #   · 桌面是一等场景（同级同构、不许开后门）。
        # **不联网、不实例化 App、不需要显示器**（纯数据 + 桩宿主）。
        'id': 'scene_p0',
        'script': os.path.join(ROOT, 'code-quality-audit', '场景系统-P0',
                               'verify_scene_p0.py'),
        'offscreen': False,
        'desc': '场景系统 P0 骨架：数据层零依赖（初始化环）+ 三个几何纯函数正负成对'
                '（锚点换算/多屏负坐标/算不出→None 不伪装成(0,0) / 多帧轮播 / 脚底深度排序）'
                '+ 数据文件契约（索引/锚点/桌面场景 + 路径穿越拦截）'
                '+ 控制器双向转发（不成环、状态不劈裂、缺失名抛 AttributeError）'
                '+ main.py 四处接线（import / _CONTROLLER_ATTRS / 9 字段预声明 / '
                'P0 期调用 load()+load_routes()）'
                '+ 桌面与作品内场景同级同构（无 desktop 特判）',
    },
    {
        # 场景路由层（第二十九轮）。用户要求「给模型训练在什么语境下怎么走路线、
        # 去哪个场景；你只需要留好拓展的接口……一切根据原作」。这一套守的是：
        #   · 路由数据层零依赖（与 scene_system 同源纪律）；
        #   · match() 的匹配语义（when_scene/area/chapter/mood/event/keywords
        #     + AND/OR + priority 三级排序）；
        #   · **三条设计律**（匹配不到返回 None 不伪装 / 坏规则跳过不作废整表 /
        #     未知条件键一律放行 —— 全部配正负控制成对）；
        #   · destinations 自省会过滤未登记场景（防 AI 被送往空场景）；
        #   · **零行为变化**：路由层不得注册定时器、不得自己播动画、只有
        #     follow_route 允许调 switch（否则 P0 判据失效）；
        #   · 原作房间表研究记录的完整性（"一切根据原作"的留痕）。
        # **不联网、不实例化 App、不需要显示器**（纯数据 + 桩宿主）。
        'id': 'scene_routing',
        'script': os.path.join(ROOT, 'code-quality-audit', '场景系统-P0',
                               'verify_scene_routing.py'),
        'offscreen': False,
        'desc': '场景路由层：数据层零依赖 + match() 匹配语义（场景/区域/章节/心情/'
                '事件/关键词，AND 主 + 关键词 OR，priority→命中数→声明序三级排序）'
                '+ ★第44轮 when_door「共同卡口」反向语义（context 没给 door 时放行，'
                '给了就精确分流；多出口场景 125/297）'
                '+ 三条设计律正负成对（匹配不到→None 不伪装 / 坏规则跳过 / 未知键放行）'
                '+ destinations 过滤未登记场景 + 控制器 load_routes 幂等与状态不劈裂'
                '+ main.py 预声明 3 个路由字段 + **零行为变化**（无定时器 / 无动画 / '
                '仅 follow_route 调 switch）+ 原作房间表研究记录完整性',
    },
    {
        # 场景系统「按原作路线排序」（第三十六轮）。用户要求「开始按照原版的路线
        # ……场景系统完全遵循原作的逻辑，把桌面当成一开始的默认场景」。这一套守：
        #   A. 原作依据在位 —— _original_rooms.json 五章齐全，且**每个作品内场景
        #      都能回溯到一个原作 room_id**（"按原版路线"的硬证据，含抹掉后的负控制）；
        #   B. 桌面仍是一等场景 —— default_scene=desktop、同构三级、**控制器源码
        #      不含 'desktop' 字面量**（无特判后门）+ 合成源码负控制；
        #   C. 路由按原作剧情推进 —— 15 条推进链逐条断言（ch1 城堡镇→原野→森林→
        #      纸牌城堡→王座；ch2/ch4/ch5 同理）+ 2 条负控制（无剧情路线时落回
        #      _fallback / 把某条降到最低优先级后不再命中）；
        #   D. ★ 本轮真实缺陷回归锁 ——「任意场景」的兜底路线**不许**用小于剧情段
        #      的 priority（priority 是第一排序键、压过 score，第一版就是这么把全部
        #      剧情路线挡死的；D4 复现坏写法证明本锁有鉴别力，D5 正控制）；
        #   E. 背景素材口径 —— 每场景都有 bg 路径、统一 bg/ 子目录、
        #      ★第37轮已由反编译补齐素材，故 E3 从「恒真占位」升级为**真判据**
        #      （每个 bg 都指向真实存在的 PNG）+ E3b/E3c 两个负控制（缺文件 / 非 PNG
        #      都要被抓到）。恒真判据比不写还危险：它看着像在守，其实什么都没守。
        # **不联网、不实例化 App、不需要显示器**（纯数据 + 纯函数）。
        'id': 'scene_route_original',
        'script': os.path.join(ROOT, 'code-quality-audit', '第36轮-按原作路线排场景',
                               'verify_scene_route_original.py'),
        'offscreen': False,
        'desc': '场景系统按原作路线排序：原作房间表依据在位（每场景可回溯 room_id，'
                '含负控制）+ 桌面仍是一等场景（default_scene / 同构三级 / 控制器零 '
                'desktop 特判 + 合成源码负控制）+ ★第44轮路由换判据：不再锁 26 条手工'
                '剧情链，改锁**门的下标位移机制自洽**（A+1/B-1/C+2）+ 三个已知真值锚点'
                '（krisroom↔krishallway 双向 + torhouse 出边）+ 共同卡口精确分流'
                '（door=B/C 两条出口互不串味 + 假门负控制）+ 覆盖面 >250 场景'
                '+ ★兜底路线不许压死剧情（priority 压过 score 的真实缺陷回归锁，'
                'D4 复现坏写法 / D5 正控制；第44轮路由已无通配兜底，改锁"无 priority<100"）'
                '+ 背景素材口径（每场景有 bg、统一 bg/、★第37轮起 E3 为真判据：'
                '每个 bg 都是真实存在的 PNG + E3b/E3c 负控制）',
    },
    {
        # 第三十四轮：移动/行为基础代码「不许回退」回归锁。用户主轴是
        # 「先把桌面宠物的移动、行为这类的做好…严查一下咱现在这些基础代码有没有纰漏」，
        # 这一套守的是本轮严查中实测确认的四类问题 + 一项日志健壮性：
        #   A. 假 Qt 事件钩子（mouseEnterEvent/mouseLeaveEvent 不是 Qt 钩子名）不许回来
        #      —— AST 判据 + 真钩子反向控制（防"全删了也 PASS"）+ QWidget 属性实证；
        #   B. 死字段 fall_start_time（6 写 0 读，init 里三种类型并存）不许回来
        #      —— AST 节点数 + getattr 调用数 + modules 全扫 + 注释留痕反向控制；
        #   C. init_movement 内同一字段不得重复赋值（本轮合并 5 组）
        #      —— 赋值语句数 ≤1 + 反向控制"字段确实还在"；
        #   C2. max_fall_duration 初值必须保持 **运行时等价（2.0）** —— 去重时若误取
        #      先出现的 5.0 就是静默行为变更（本轮施工中真的踩过一次，故专门设锁）；
        #   D. start_fall 内 is_moving 赋值语句数 ==1 且位于 reason 分支之前
        #      —— 含"idle_timer 差异必须保留（两处不是四处）"的反向控制；
        #   E. 日志 rollover 失败必须被兜住（E 盘 exFAT 的 os.rename 会抛 WinError 1，
        #      原生 handler 会把 Traceback 吐到 stderr 且日志永不切割）
        #      —— 行为级正负控制：同故障下原生吐、安全类不吐且继续写盘。
        # **不联网、不实例化 App、不需要显示器**（AST + 轻量运行时 + 一次 logging 往返）。
        'id': 'round34_movement',
        'script': os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                               'verify_round34_movement.py'),
        'offscreen': False,
        'desc': '第三十四轮：移动/行为基础代码不许回退 —— 假 Qt 钩子（mouseEnter/LeaveEvent）'
                '已删且不许回来（AST + 真钩子反向控制 + QWidget 属性实证）'
                '+ 死字段 fall_start_time 全清（AST 节点/getattr/modules 三向 + 注释留痕反向控制）'
                '+ init_movement 五组重复赋值已合并（赋值语句数 ≤1 + 字段仍在的反向控制）'
                '+ max_fall_duration 初值运行时等价 2.0（防去重时误取 5.0 的静默行为变更）'
                '+ start_fall 的 is_moving 提取到分支前（含 idle_timer 差异必须保留的反向控制）'
                '+ 日志 rollover 失败被兜住（正负控制：原生吐 Logging error / 安全类不吐且继续写盘）',
    },
    # -------------------------------- 第三十四轮：楼层实现审查（floor_manager）
    # 需求：「仔细检查那个楼层的实现」→ 坐实并修复 `_index_of_floor` 退化分支缺陷：
    #   返回 -1（=「比最高活楼层还高」）被两个消费方误读成"未找到" →
    #     · get_drop_destination 从最高活楼层起扫 → 宠物被"上吸"一层；
    #     · adjacent_lower_floor 返回 None（语义「下面没楼板了」）→ 有下层却报"到底了"。
    # 触发路径：宠物站在**当前最高的窗口**上、用户关掉它 → current_floor 仍持有已消失
    #   窗口的旧 dict，而重建后最高活楼层比它低 → 按高度找 "<= cur_h" 的首项即 i==0。
    # 本套件**全部调用产品真函数**（不重写被测逻辑），断言行为而非写法；
    # 正/负控制成对（含"正常路径 i>=1 的 i-1 语义不许被改坏"的反向控制）。
    # **不联网、不实例化 App、需要 QApplication 实例（offline 平台即可）**。
    # 鉴别力已体检：回退修复行 → 6 项报红 rc=1；还原 → 15/15 PASS rc=0。
    {
        'id': 'round34_floor_manager',
        'script': os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                               'verify_round34_floor_manager.py'),
        'offscreen': True,
        'desc': '第三十四轮：楼层实现不许回退 —— `_index_of_floor` 退化分支不得返回 -1'
                '（A1/A2 + 全低反向控制 A3）'
                '+ get_drop_destination 落点不得被"上吸"（B1 正控制 / B2 修复 / B3 单调性）'
                '+ adjacent_lower_floor 不得把"有下层"误报成 None（C1 正控制 / C2 修复）'
                '+ 正常路径 i>=1 的 i-1 语义保持（D 三个活楼层 + D2 stale 落在层间）'
                '+ 只有桌面 / 桌面最底层口径保持（E1/E2/E3）',
    },
    # -------------------------------- 第三十四轮：存储/配置层（生命周期线）
    # 用户口径「你自己严查一下咱现在这些基础代码有没有纰漏」在**生命周期/存储/配置线**
    # 上的成果：4 条真缺陷（Q1b/Q3b/Q4b/Q5）+ 1 条隐私回归（R1）。
    #   · Q1b `.corrupt.*` 备份从未被收敛 → 配置每损坏一次留一个、永不自愈；
    #   · Q3b/Q4b 留档名固定（`.old` / `memory.old.json`）→ 下一次搬运**静默覆盖**
    #     上一份留档，历史版本永久丢失（Q4b 触发频率高：每次启动都会调 migrate）；
    #   · Q5 残留 `.migprobe` 让 `_movable` 恒 False → 该文件**永久滞留**中转站；
    #   · R1 修 Q4b 引入"时间戳留档"后，隐私 `reset_all` 必须连带清掉它们（否则
    #     "退出时清理数据"会留下旧记忆）。
    # 本套件**全部调用产品真函数**（config_manager / data_store / memory_store /
    # memory_system），沙箱用本地 NTFS `tempfile.mkdtemp()`（E 盘 exFAT 不能当探针沙箱）。
    # 正/负控制成对（含"真不可搬仍返 False"、"约定名仍在"、"收敛不是清光"）。
    # **不联网、不实例化 App、不需要显示器**（纯文件系统 + 打桩路径）。
    # 鉴别力已体检：逐条回退 4 处修复 → 分别报红 2/1/2/2 项 rc=1；还原 → 17/17 PASS rc=0。
    {
        'id': 'round34_store_config',
        'script': os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                               'verify_round34_store_config.py'),
        'offscreen': False,
        'desc': '第三十四轮：存储/配置层不许回退 —— `.corrupt.*` 备份必须与 `.backup.*` 同等收敛'
                '（A1/A2 + 各自独立计数 A3 + "收敛不是清光" A4）'
                '+ 残留 .migprobe 不得把文件永久钉住（B1 正控制 / B2 修复 / B3 真不可搬仍 False）'
                '+ data_store 留档名不得撞车（C1/C2/C3 + 约定名 .old 仍在 C4）'
                '+ memory_store 留档名不得撞车（D1 正控制 / D2/D3 / 约定名仍在 D4）'
                '+ 隐私 reset_all 连带清时间戳留档（E1 前置 / E2 清零）',
    },
    # -------------------------------- 第三十四轮续：移动核心（update_movement）节拍
    # 用户口径「检查一下尤其是移动代码，动画播放和有关楼层的代码」在**移动核心**
    # 上的成果：坐实并修复 1 条真缺陷 F34-1。
    #   · `update_movement` 里 `check_nearby_desktop_elements` 的 5 秒节拍，
    #     时间戳推进 `self._last_desktop_elem_check = current_time` 原写在 `try`
    #     **之外、无条件执行** ⇒ 时间戳每 tick（30ms）被刷新 ⇒ 节拍判据
    #     `> 5.0` 除首次外永远为假 ⇒ 该检查**一生只跑一次**。
    #   · 后果链真机可达：check_nearby_desktop_elements → react_to_desktop_element
    #     → _note_desktop_observation（唯一调用点在此）→ 「凑近桌面文件的观察」
    #     从不进入 AI 事件队列。
    #   · 同文件另两处节拍（`_last_env_update` / `last_floor_check_time`）写法本就正确，
    #     本套件把三者一起锁住（防"修一处、改坏另两处"）。
    # 判据纪律：**AST 判结构（不断言写法）** + **逐字抽取该片段用最小 self 桩跑**
    #   （20s 该 4 次 / 60s 该 12 次）；正/负控制成对，负控制 = 旧写法必须重现"只 1 次"。
    # **不联网、不实例化 App、不需要显示器**（AST + 无 Qt 的纯逻辑重演）。
    # 鉴别力已体检：回退修复 → 5 项报红 rc=1；还原 → 13/13 PASS rc=0。
    {
        'id': 'round34b_move_beat',
        'script': os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                               'verify_round34b_move_beat.py'),
        'offscreen': False,
        'desc': '第三十四轮续：移动核心节拍不许回退 —— `update_movement` 的 '
                '5 秒节拍时间戳必须落在 if 块内（AST 结构 A1/A2 + 反向控制 A3/A4）'
                '+ 行为级：逐字抽取片段跑 20s/60s 必须触发 4/12 次（B1/B2/B3）'
                '+ 接线自证（B4 无节拍版 100 tick = 100 次）'
                '+ 负控制（B5 旧写法 60s 只 1 次，证明本锁有鉴别力）'
                '+ 同口径一致性（C1 `_last_env_update` / C2 `last_floor_check_time` 仍块内赋值）',
    },
    # ---------------------------------------------------------------- 第 34 轮续三
    # 范围：用户口径「检查一下尤其是移动代码，动画播放和有关楼层的代码」的延伸 ——
    #   细查最大模块 `modules/desktop_interaction.py`（131648 B / 82 方法）的**接线**。
    # 本轮发现 F34-4：隐私应用过滤的**接线断链**（不是判据错）：
    #   · `user_opened_privacy_apps` 仅由 `mark_app_as_opened` 写入；
    #   · 而该方法**全项目零调用**（AST 实测，含注释 0 命中）⇒ 列表恒空；
    #   · 于是 `if is_privacy_app and hwnd not in self.user_opened_privacy_apps`
    #     的第二项**恒为真** ⇒ 隐私应用窗口（微信/QQ/钉钉/企业微信/Outlook/邮件）
    #     **永远被跳过、永不被建楼** ⇒ 用户永远踩不上这些窗口。
    #   · 设计意图是「用户主动打开过才放行」，实际退化为「一律不建楼」——**语义不一致**。
    # 本轮处置：**不改行为**（偏保守、安全），只把不一致显式注释 + 上锁；
    #   接线属"加功能"，列入待用户裁定（与「先做好移动行为」的当前主轴一致）。
    # 判据纪律：
    #   · A 组用 **AST 判结构**（写入点集合 / 判据形状 / 清单覆盖面），不断写法；
    #   · B 组用**产品真清单 + 产品同款判据**做行为推演，**不重写隐私逻辑**；
    #     正控制 B1（空列表 → 6 个隐私窗口全跳过）、负控制 B2（非隐私不跳过）、
    #     反证 B3（hwnd 入列表 → 不再跳过，证明"缺陷在接线、不在判据"）。
    # **不联网、不实例化 App、不需要显示器**（纯 AST + 清单推演）。
    # 鉴别力已体检：破坏 A1/A3b/B4 → 分别精确报红 rc=1；还原 → 10/10 PASS rc=0。
    {
        'id': 'round34c_privacy_wire',
        'script': os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                               'verify_round34c_privacy_wire.py'),
        'offscreen': False,
        'desc': '第三十四轮续三：隐私应用过滤接线断链不许无声改变 —— '
                'A 结构（A1 写入点仅 mark_app_as_* / A2 仍零外部调用 / A3 判据形状 / '
                'A4 privacy_apps 覆盖面含微信QQ钉钉企业微信Outlook）'
                '+ B 行为（B1 空列表下 6 个隐私窗口全跳过 / B2 非隐私不跳过 / '
                'B3 反证：hwnd 入列表即放行，缺陷在接线不在判据 / '
                'B4 同源的 privacy_file_types 已收窄且不得回退）',
    },
    {
        # 第三十九轮：场景背景素材「**只做零编造的那一半**」的回归锁。
        # 用户口径是「一切根据原作」+「把所有都拿出来」。本轮把 1,013 个场景里
        # **原作真的给了背景精灵**的那批用原作 PNG 原样落盘并标注来源；拿不到真
        # 背景的**仍然留空** —— 第 37 轮那套"区域代表素材"近似**适用范围一点没扩大**
        # （这条是本轮的核心决定，E 段专门守它）。
        # 判据的单一真源 = `_tools/bg_common.classify()`；套件拿仓库内的
        # `_evidence/原作房间背景溯源.json` 重建它的入参再复算，**刻意不依赖
        # `E:\Download\_tmp`** —— 那个目录按约定"用后即删"，套件一旦依赖它，
        # 临时文件被清后不是报红而是**静默失去鉴别力**（读不到 ⇒ 全判 none ⇒ 全绿）。
        # **不联网、不需要显示器、不实例化 App**（纯数据 + 纯函数）。
        'id': 'bg_round39',
        'script': os.path.join(ROOT, 'code-quality-audit', '第39轮-全量场景背景',
                               'verify_bg_round39.py'),
        'offscreen': False,
        'desc': '第三十九轮：场景背景来源标注不许静默漂移 —— 真背景场景的 '
                'bg/bg_source/bg_asset == 据原作房间事实重算的结果（B1，配 B2/B2b/B4 '
                '三个负控制 + B3 正控制）+ bg 文件健康（C1/C2 + C3/C4 负控制）'
                '+ 元数据自洽（bg 与 bg_source 不许互相矛盾，D1–D4）'
                '+ ★近似档适用范围没扩大（新增场景只许 none/真背景 E1/E2；'
                '锚点标注逐条等于第 37 轮实际产出 E3/E4）'
                '+ 文本格式保真（无 BOM/U+FFFD、不混用换行，F1–F4）'
                '+ 过期注释已修正（G1–G3）+ 产品函数真能解析出 bg 文件（H1–H3）',
    },
    {
        # 第四十四轮：用户口径「对话框改成和原作风格一样的，最好就是原作的对话框」。
        # 对话框外框从"圆角样式表框"换成**原作 scr_darkbox() 的 9-slice 复刻**
        # （32px 边框带 + 32×32 八帧动画角 + 纯黑内芯），字体换项目根像素字体，
        # 打字音按原作 scr_textsound 跳标点。
        #
        # 本套件的核心**不是**"我写的常量等于我写的常量"（那是恒真判据），
        # 而是让产品常量必须能从**原作反编译源码**里被反推出来：A 段直接从
        # `_evidence/gml/*.gml`（UTMT `dump` 出的真 GML）解析 63 / 32 / 10 / 8 帧 /
        # 黑底 14 内缩 / 静音字符表，逐条与产品常量对齐 —— 源码被换、常量被手改都报红。
        # 判据单一真源 = `modules/dr_textbox.py`；素材签名 = `assets/ui/textbox/`。
        # **不联网、不调 Ollama、不需要显示器**（Qt 走 offscreen）。
        # 鉴别力已体检：BAND 32→31 + 静音表删 `?` ⇒ 10 条精确报红（A2/A7/A8/B×2/D2–D5/F6），
        # 其余 39 条不受影响；还原 ⇒ 49/49 PASS。
        'id': 'box_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_box_round44.py'),
        'offscreen': True,
        'desc': '第四十四轮：原作对话框复刻不许静默漂移 —— '
                'A 原作源码反推（63 长度差 / 32 带宽 / cur_jewel÷10 / 负宽高钳 0 / '
                'top·left·topleft 调用数 / 黑底 14 内缩 / 文字内缩 34 / '
                'scr_textsound 静音表被产品全覆盖含 ? / 30fps→33ms）+ '
                'B 九个常量逐条 + C 纯函数语义（jewel_frame 边界与周期、metrics 钳制）+ '
                'D darkbox_blits 几何逐条对应原作 draw 调用（含极扁框负控制）+ '
                'E 素材结构（16×16×8 帧 / 图案签名 5 种 / 剖条 1×16 与 16×1 / '
                '剖面外透明→白线→黑芯）+ F 产品接线（无 border-radius、'
                '_frame 真是 DrTextboxFrame、隐藏即停表、打字音正负控制、'
                'AST 证明判据真被调用、▼ 仍在黑底可见区）+ G 恒真判据自查',
    },
    {
        # 相机（第四十四轮）。用户原话：「操控效果是游戏里那种人物走到中间后
        # 一直居中然后背景相对运动还是背景固定？我更倾向原作的那种，代码用原作
        # 的参考就好」⇒ 本套件守「原作口径 = 居中式相机跟随，**不是视差**」。
        # 依据 = 第43轮取证：ch1 的 1014 个图层里 HSpeed/VSpeed 非零 = 0、
        # EffectType 恒 null；原作走 GMS2 原生相机族
        # （camera_set_view_target/border/pos/size，包在 __view_set_internal）。
        # ★ 首跑抓到真 bug：死区实现用"重算出的相机中心"做基准 ⇒ 每帧都居中
        #   ⇒ border 恒不生效；修法 = 用上一帧相机位置（B7b/B7c/B7d 就是它的锁）。
        # **不联网、不需要显示器**（纯标准库 + 纯函数）。
        'id': 'camera_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_camera_round44.py'),
        'offscreen': False,
        'desc': '第四十四轮：相机（居中式跟随 + 背景相对运动）不许静默漂移 —— '
                'A 原作依据在位（源码记录 camera_set_view_* 三连 + 写明"不是视差" + '
                '相机尺寸 640×480 + 死区默认 0 + 第43轮取证文件与其内容双查 + '
                '零依赖 AST + 负控制）+ B 纯函数语义正负成对（clamp 三向 / 目标居中 / '
                '四向钳制两角 + 非恒真负控制 / 小房间居中 / 非法输入→None + 正控制 / '
                '★死区四条：无 prev 退化居中 + 区内不动 + 区外推边缘 + border=0 关闭 / '
                'world_to_view 相对运动性质 / 裁剪框 / scale_rect）+ '
                'C Camera 壳（未 follow→None / ★scale = 输出倍率：21x41 逻辑在 '
                'scale2 下屏幕 42x82 / to_view 换算 / 拒绝非法 set / '
                '★不做缓动不做定时器 / 套件自身恒真自查）',
    },
    # ---- 第44轮 · 房间渲染层（scene_render）----
    # 只出"绘制指令"、一笔不画 ⇒ 可逐条断言，不必离屏截屏（沙箱里离屏不稳）。
    # 关键判据是 B22/B23/B24 的**坐标系自洽**：相机逻辑窗口 = size/scale、
    # 320x240 逻辑房间 @scale2 → 640x480 像素（= 原作现实世界输出尺寸）。
    # ★ 首跑抓到两个真 bug：① 视口误用全表 geo（走退化分支 ⇒ 物件全被剔除）；
    #   ② 相机窗口误写 size×scale（房间比窗口小 ⇒ 相机居中到房外 ⇒ 物件出界）。
    # **不联网、不需要显示器**（纯标准库 + 纯函数）。
    {
        'id': 'render_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_render_round44.py'),
        'offscreen': False,
        'desc': '第四十四轮：房间渲染层（P1）不许静默漂移 —— '
                'A 原作依据在位（"背景移动=相机平移"出处可查 + 几何资产带 '
                'source/authority + ★scene_render 零 Qt 零项目内依赖 AST）+ '
                'B 纯函数正负成对（room_geometry 六向 / room_world_rect 退化须'
                '面积>0 / viewport_size 两轴独立 / to_output ×scale / '
                '★坐标系自洽：scoped_size=size/scale、320x240@2→640x480）+ '
                'C 视口剔除（四角 + 半开区间边界 + 四类坏输入→False）+ '
                'D 绘制计划（空输入→[] 不崩 / ★真实数据 ch1 克里斯房间 / '
                '未登记房间→placeholder 不静默 / 大房间→room_border / '
                '物件剔除正负成对 / 21x41@2=42x82）+ '
                'E 产品接线（控制器三方法 + import + ★main.py 真调 load_geometry + '
                '三字段预声明 + ★scene_scale=2.0 与 Ralsei 同比例 + 无 QTimer + '
                '★D7 背景按素材原尺寸 660x480@2=1320x960 而非房间 2000x2000 + '
                'D8 相机右移 100 逻辑→背景左移 200 像素（零视差算术）+ '
                'D9 背景出界不产 placeholder）',
    },
    # ---- 第44轮 · 场景画布（scene_canvas，Qt 绘制壳）----
    # 把 scene_render 的指令清单**真正画出来** —— 补上"渲染层最后一跳"
    # （本项目最贵的坑 = 函数写对了但产品用不上）。
    # ★ 用假画笔 + 假素材做**确定性**断言，不真机截屏（沙箱离屏不稳）。
    # ★ 首跑抓到真 bug：`paint_on` 无条件 `drawn += 1` ⇒ 几何非法的指令
    #   也算"画了"，自省输出会骗人；修法 = 各 `_paint_*` 返回是否真落笔。
    {
        'id': 'canvas_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_canvas_round44.py'),
        'offscreen': False,
        'desc': '第四十四轮：场景画布（Qt 绘制壳）不许静默漂移 —— '
                'A 常量与 scene_render 一字对齐（改一边忘另一边立刻报红）+ '
                '★画布不自带间距常量（间距随指令走）+ 零项目内反向依赖 AST + 默认 hide + '
                'B 素材缓存（真文件命中 / 二次命中同一对象 / 不存在→None + 记 missing / '
                'name=None/""→None / ★sprite_size 返回原始尺寸未乘 scale / clear）+ '
                'C 绘制分派（四种 kind 各一条 + ★bg 先于 obj 顺序 + 未知 kind 不计成功 + '
                '坏指令不崩）+ D 缺素材占位（缺背景→fillRect 斜纹不调 drawPixmap / '
                '缺物件→drawRect 描边 / 无 name 也画框）+ 异常兜底（单条抛→其余仍画 / '
                '全抛→返回 0 不抛出）+ E 产品接线（★main.py 真调 camera_follow/'
                'plan_frame/set_plan/plan_viewport 四连 + 控制器补 plan_viewport + '
                '★总开关=开（第50轮口径：贴近原作） + ★屏幕→房间归一化映射防"目标比房间大被钳死"'
                ' + 画布无 QTimer）',
    },
    # ★ 第44轮续新增：复检时抓到「priority 回绕」真缺陷（G2 未覆盖），
    #   故立此锁 —— 锁"同一场景内门字母序 == priority 序"这条不变量。
    {
        'id': 'routes_order44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_routes_order44.py'),
        'offscreen': False,
        'desc': '第四十四轮续：路由表「连接顺序」不许静默漂移 —— '
                'A 生成器静态锚点（代码里不再有 `order % n` 全局取模 + 改用'
                '「场景段 + 段内序」+ 注释留痕）+ B ★同场景内门字母序==priority '
                '序（0 例外，125 个多出口场景；★B2b 负控制：旧写法必复现错乱，'
                '证明判据有鉴别力）+ 无回绕 + 值域安全 + 全规则显式 priority/'
                'when_door + C 原作锚点（产品边集合 == 原作门表独立重算，断链'
                '全为原作死胡同且不放过真缺口）+ D 兜底与结构（_fallback / '
                'schema / 警告保留 / 字母互异样本）',
    },
    # ★ 第44轮续新增：objects 补全（把原作实例普查蒸馏进场景 JSON）。
    #   为什么单独立锁：objects 是**程序化生成的数据**（615 场景 / 3197 条），
    #   IDENTICAL 判据只比判据输出文本，数据本身悄悄变了不会被发现。
    #   本锁**直接把数据当事实断言**，并且独立重算期望值（不信生成器自报）。
    # ★★ 第68轮升级本锁的**数据源与锚点形态**：普查从"第42轮 ch1 单表"换成
    #   "第68轮五章 + 按章对象表"（3,197 条 / 615 场景）；锚点从"恰好 N 条"换成
    #   "**总数 >= N** + **门/标记集合精确**"（补采后每间房多了可读物，总数会变，
    #   但门/标记的集合仍是可回查的原作事实）。
    {
        'id': 'objects_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_objects44.py'),
        'offscreen': False,
        'desc': '第四十四轮续（第68轮升级数据源）：场景 objects 补全不许静默漂移 —— '
                'A 结构不变量（每条 object pos=2×int / sprite 指向 objs/ 下'
                '真实文件 / ★无过期的 why_objects_is_empty 假话注释）+ '
                'B 真值锚点两种载体各一（ch1:2 krismro 独立文件 **门/标记集合**='
                'doorA(155,230)+markerB(155,185)；ch1:3 krishallway 分片 '
                '**门/标记集合**=doorB/markerA/doorC/markerD；总数 >= 锚点数）+ '
                'C 覆盖与守恒（数据源在位 / 615 个场景 / ★3197 条 == '
                '第68轮普查×按章对象表×objs 三源独立重算）+ '
                'D 负控制（编造 sprite 名必须判缺 / 普查缺席房间 objects==[] 且键存在）',
    },
    # ★ 第44轮续新增：动效（sprite 逐帧动画）。
    #   为什么单独立锁：动效是**时间相关**的 —— 它不会在静态数据里"变错"，
    #   而是在**时间轴上**变错（速度不对 / 永远第 0 帧 / 单帧物件乱动）。
    #   判据用毫秒量级的真实输入，并配对负控制（单帧不许动、非法 anim 不许抛）。
    {
        'id': 'anim_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_anim44.py'),
        'offscreen': False,
        'desc': '第四十四轮续：动效（sprite 逐帧动画）不许静默失效 —— '
                'A 数据（_sprite_anim.json 合法 fps=30 / anim 字段齐全 / '
                'base 的帧文件全在磁盘 / frame_ms 与 1000/(30*speed) 自洽）+ '
                'B 渲染（帧号随时间前进且周期正确 / plan_frame 传不同 tick 换帧 / '
                'tick=0 确定性恒第0帧）+ C 负控制（单帧物件名不随 tick 变 / '
                '非法 anim 不抛且退单帧）。'
                '★ 动效口径来自实测：原作 191 个背景层 HSpeed/VSpeed 非零 = 0、'
                'EffectType 非空 = 0、瓦片动画 = 0、房间 Sequence = 0，'
                '唯一动效载体 = 523/1097 多帧 sprite。',
    },
    # ---- 第45轮 · 场景自主寻路 ----
    # 用户口径：「假设 Ralsei 和我说话，语境里表达了我们该去教堂看看，
    # 那 Ralsei 怎么自主地按路线去教堂这类的路线问题」。
    # 本轮把这句话拆成**三个不同的问题**，只锁其中两个可离线回归的：
    #   ① 意图（文本→目标词）吃 AI ⇒ 留给 P1，只留接口；
    #   ② 定位（『教堂』→ scene_id）★ 锁；
    #   ③ 寻路（起点+终点→路径，吃原作 782 条边）★ 锁。
    # ★ 头号判据是 **②消歧顺序 = 先章、后精度** —— 第一版写成"先精度"，
    #   于是『医院』在 ch1 会被送到 **ch5 的花园医院**（真缺陷，C4 就是它的锁）。
    # ★ 第二头是 **分级匹配** —— 不分级时『教堂』全域命中 166 个场景
    #   （ch4 暗之圣域 100+ 个 church_*），C5/C6 锁住它。
    # ★ 第三头是 **设计律 1：走不到就返回 None，不就近凑** —— B4/B7/D9。
    # 数据依赖：`_aliases.json`（仓库内）+ 第42轮 `_room_graph.json`（仓库内）
    #   ⇒ **刻意不依赖 E:\Download\_tmp**（那目录"用后即删"，
    #   一旦依赖，临时区被清后不是报红而是**静默失去鉴别力**）。
    # 鉴别力已体检：消歧回退 → 6 条报红；走不到返回 [] → B4；
    #   分级失效 → C1/D6；switch 不投影章 → E6；还原 → 35/35 PASS。
    # **不联网、不调 Ollama、不实例化 App、不需要显示器**（纯数据 + 纯函数 + AST）。
    {
        'id': 'pathfind_round45',
        'script': os.path.join(ROOT, 'code-quality-audit', '第45轮-场景自主寻路',
                               'verify_pathfind45.py'),
        'offscreen': False,
        'desc': '第四十五轮：场景自主寻路不许静默漂移 —— '
                'A 数据（别名表 schema/★零命中词条=0 / 原作 782 边五章分章数 / 邻接表守恒 / 1,014 场景索引）'
                '+ B ★③ BFS 纯函数（ch1 krisroom(2)→town_church(15) 恰 7 跳 / 逐边接得上无环 / '
                '起终点相同→[] 区别于 None / ★负控制无回边→None 不就近凑 / 坏输入不抛 / 确定性）+ '
                '★如实报告 ch4/ch5 走不到（第42轮取证缺口）'
                '+ C ★② 语义定位（『教堂』+ch1 唯一命中 / 负控制不存在→ok=False / '
                '★消歧顺序先章后精度：『医院』+ch1 绝不跨 ch5 / 无章多解→ambiguous 不猜 / '
                '分级匹配把候选压到 ≤10 / 别名词条真实生效即不可省）'
                '+ D 端到端门面（用户原场景全链路 7 跳 / path 首尾与 steps / describe_plan 中文计划 / '
                '负控制：不可用→空串、目标不存在、跨章（第三圣域唯一→ch4）、非字符串、当前场景未知、'
                '★失败不留半个计划）'
                '+ E 产品接线 AST（scene_pathfind 零 Qt 零本地依赖除 scene_system / '
                '控制器真调 5 个函数 / 4 只读方法在 / ★零行为变化无 switch·QTimer / '
                'main.py 预声明 4 字段 / ★switch 里 _scene_chapter_id 恰赋值 1 次 / 幂等守卫）',
    },
    # ---- 第46轮 · 伙伴交互系统框架 ----
    # 用户口径：「嵌入一下和伙伴的交互系统，方便以后多宠物互相互动」
    #   「要让他们能有自主互相聊天的功能，但不会导致 AI 之间分不清是谁和谁说话」
    #   「一般来说并不会有多个 AI 同时运行的场景……多个一起运行也看不出端倪那也行」
    #   「跟随系统这类的按原作的就行，还是跟随 kris 如果 kris 在的话，
    #     当然，也可自主行动，只是在需要统一行动时跟随」
    #   「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」
    # 本锁守的是**三件容易静默失效的事**（不是"代码跑得起来"）：
    #   · 身份不许被猜 —— 缺 from_id 的消息必须被拒、且不许进历史（E2/H2）；
    #   · 锁必须能释放 —— 交互对象抛异常时全局锁不许卡死
    #     （卡死 = 所有可交互物一起失灵）（D9/D9b/D12b）；
    #   · 不许并发 —— 轮转调度任一时刻最多一个伙伴在生成（J1，200×5 次真实量级）。
    # ★ 数值全部照抄原作且**逐个可指到出处**：25 帧环缓冲 / 12+slot×12 滞后 /
    #   2 个队友位 / 暗世界 ×2 / onebuffer = 5 / typer = 5；出处字符串另有 B9 文档锁。
    # ★ 跨文件一致：`companion_dialog.MAX_TEXT_CHARS == main.AI_REPLY_MAX_CHARS`（B7）。
    # ★ 三条设计律：找不到就是不找到（I4/不就近凑）、锁必须能释放、数值照抄。
    # 鉴别力已体检（`disc_companion46.py`，17 项破坏逐条改盘上文件）：
    #   17/17 报红且命中期望关键词；还原后 216/216 PASS 且逐字节一致。
    # **不联网、不调 Ollama、不实例化 App、不需要显示器**（纯函数 + 真数据 + AST）。
    {
        'id': 'companion_round46',
        'script': os.path.join(ROOT, 'code-quality-audit', '第46轮-伙伴交互框架',
                               'verify_companion46.py'),
        'offscreen': False,
        'desc': '第四十六轮：伙伴交互系统框架不许静默漂移 —— '
                'A 模块纪律（三个模块零 Qt / 顶层依赖白名单 / ★零函数内 import / '
                '★跟随不独立寻路=不 import scene_walk，AST 判定含"文本提及不误报"正控制）+ '
                'B 数值照抄（25 帧缓冲 / 12+slot×12 滞后 / 2 个队友位 / 暗世界×2 / '
                'onebuffer=5 帧且换算 5/30 秒 / typer=5 / darkzone 值域 / '
                '★跨文件 MAX_TEXT_CHARS==main.AI_REPLY_MAX_CHARS / 出处文档锁）+ '
                'C Companion 模型（★滞后 12/24 精确到帧 / 环缓冲封顶 25 / 空轨迹→None 不猜 / '
                'reset_trace 填满不闪 / RALLY 收紧 / 非法模式不静默 / 空 id 抛错）+ '
                'D 可交互物协议（★抛异常必解锁 / NotImplementedError 解锁后照抛 / '
                '全局锁挡下不跑 on_interact / 防抖 5/30 秒 / ★不为 actor 凭空造字段）+ '
                'E Message 校验（★缺 from_id 必拒 / 别名归一通过 / self_talk / '
                '旁白允许无主但 speech 不许）+ '
                'F format_line（★每行带前缀、缺 from 显式标未知、★不许裸文本入 prompt、'
                '别名归一渲染成显示名）+ '
                'G 输出护栏（代他人发言 / 自称混乱 + 4 条"刻意收窄"负控制 + 名字表为空即失效）+ '
                'H DialogueLog（★脏数据不进历史 / last_from 只看入库 / 环缓冲 / 注入 cleaner 三态）+ '
                'I Roster（重复 id / ★别名冲突原子拒绝 / 大小写与别名 / ★未知→None 不就近凑 / '
                '槽位按激活序 / 超槽 no_slot / ★不给 leader_xy 则轨迹留空）+ '
                'J ChatScheduler（★★200×5 次 tick 零并发 / A↔B 往返 / 冷却 / 话题上限 / '
                '★mismatch 仍解锁 / abort 不罚下一个人 / ★反活锁 / 话题源三态）+ '
                'K 跟随（★★滞后 12/24 精确到帧 / FREE 不动但记轨迹 / RALLY 更紧 / '
                '未热身 13 帧后从正确点开始）+ L 端到端 CompanionStage + M 恒真判据自查',
    },
    # ---- 第47轮 · 房间全量普查 + 逐场景可用性 ----
    # 用户口径：「复查一下1,2,4,5,章的room加起来到底有多少，别漏了，
    #   并且确保每一个都能用，且符合原作逻辑」。
    # A 房间全量：四权威源交叉（_room_geometry.stats / _room_order / _index / _room_graph）
    #   —— 五章 1,251；★ch1/2/4/5 = 1,005；★"别漏了"的可判定形式 = 逐章下标 0..n-1 一个不缺；
    #   产品场景 1,014（含 desktop 1 个）/ 四章 826；四章 playable 853 / 已覆盖 812 / 未覆盖 41。
    # ★★ 头号判据 A7：真缺口（**原作门图里有边**的未覆盖 playable 房）== 10 间，
    #   集合精确相等；并配 A8「真缺口 10 严格少于未覆盖 41」证明归因这步真筛过。
    # B 逐场景可用性：U1 载体（★两种载体：独立件用 `file`，**分片场景的 `file` 是空串**，
    #   载体 = `_zone.<章>.<区>.json` —— 只看 file 会误报 926 个"缺文件"）/ U2 载体里已注册 /
    #   U3 name 非空 / U4 original_room_id 是 int（仅 desktop 例外）/ U5 几何命中。
    #   ★ 背景覆盖率 235/1014 如实钉住（缺口 779 需重导素材，**不属于"不能用"**）。
    # C 符合原作逻辑：判据必须是**门图**不是名字 —— C1 真缺口在第38轮 cls 里
    #   maybe 9 / nonscene 1；★C2 命名启发式只有 74% 覆盖（故意断言"不够用"）；
    #   ★★C3 同名不同命（room_shop1 / room_DARKbase_GMS2 同时落在"有门/无门"两侧）。
    {
        'id': 'rooms_round47',
        'script': os.path.join(ROOT, 'code-quality-audit', '第47轮-房间全量与寻路人味化',
                               'verify_rooms47.py'),
        'offscreen': False,
        'desc': '第四十七轮：ch1/2/4/5 房间全量普查不许静默漂移 —— '
                'A 原作 1,251 间 / 四章 1,005 / ★逐章下标 0..n-1 不缺 / 产品 1,014（含 desktop）/ '
                '四章 826 / playable 853 / 覆盖 812 / 未覆盖 41 + ★★真缺口 10 间集合精确相等 + '
                'B 逐场景可用性（★两种载体：分片场景 file 为空串，载体是 _zone 文件 / '
                '载体已注册 / name 非空 / original_room_id 为 int（仅 desktop 例外）/ 几何全命中 / '
                '背景覆盖 235 如实钉住）+ '
                'C 符合原作逻辑（★真缺口 cls=maybe 9·nonscene 1 / ★命名启发式仅 74% 不够用 / '
                '★★同名不同命 room_shop1·room_DARKbase_GMS2 / 孤立房 in=0 out=0）',
    },
    # ---- 第47轮 · 场景内行走「人味化」 ----
    # 用户口径：「那个寻路要符合真人逻辑，别和机器人一样」。
    # ★ 房间之间那层由 pathfind_round45 守；本锁守**房间之内**那层（scene_walk.py）。
    # ★ 第47轮实测的真缺陷：`smooth_keep_walkable` 的回退分支会把原始顶点插到**身后**，
    #   平滑后路径出现"往回走"的抖动 —— 最坏 228.4px（近半间房宽）、转角 174°~180°；
    #   且 193 组配对里 74 组平滑后硬拐角比原折线**还多**（平滑在帮倒忙）。
    # 修复 = `_monotone_forward`（按原折线弧长单调过滤）+ `_despike`（只削 ≥45° 的尖刺，
    #   **缓弯一律保留** —— 用户反对的另一种走法是"一直直线走"）。
    # ★★ A 段头号判据：「**没有任何一条残留倒走点是可删的**」——
    #   过滤器不允许为顺而穿墙，所以"删了会穿墙"的必须保留；这才是"该删的都删了"。
    # ★★ B 段负控制：把**改前版本**（随证据入库 `_evidence/_scene_walk_HEAD47.py`）
    #   用同一批夹具跑，它必须违反不倒着走（228.4px）且硬拐角更多（318 vs 117）。
    # C/E 段：合成夹具 + 反面对照（"无脑删不查安全"必穿墙；缓弯必须原样保留）。
    {
        'id': 'walk_round47',
        'script': os.path.join(ROOT, 'code-quality-audit', '第47轮-房间全量与寻路人味化',
                               'verify_walk47.py'),
        'offscreen': False,
        'desc': '第四十七轮：房间内行走"人味化"不许静默漂移 —— '
                'A 真实全量 348 组（★残留倒走 ≤10 条 / ★★每一条残留倒走都是"删了会穿墙"的 / '
                '★可见硬拐角 355→117 / ★★**本可删的**硬拐角 194→0 且逐对 0 劣化'
                '（第51轮细化口径：纯"可见拐角总数"会把"删了会穿墙"的正当保留误判成劣化，'
                '配 A3d/A3e 正负控制）/ ★逐点逐段不穿模 / 首尾点保持）+ '
                'B ★★负控制（改前版本 228.4px 倒退、318 硬拐角，必须更差）+ '
                'C 合成夹具（倒走点删不动时必须保住 + ★无脑删会穿墙 + 无障碍时确实删掉）+ '
                'E 合成夹具（★缓弯原样保留=不许拉直成"一直直线走" / 尖刺被削 / '
                '抄近路穿墙时尖刺保住 / ★无脑删会穿墙）+ '
                'D 常量与接线（BACKTRACK_TOL=GRID_STEP/2、DESPIKE_MIN_TURN=45、'
                '★smooth_keep_walkable 真调用这两层且 monotone 产出真被喂进 despike；'
                '第51轮去掉"恰好 1 次"的过窄判据 + D2b 负控制证明非恒真）',
    },
    # ---- 第48轮 · 道具 / 背包 / S 键菜单 ----
    # 用户口径：「对于里面可互动的道具也要做到可以互动，当然，道具效果不可带出当前章节的
    #   场景，也就回到光世界的时候暗世界的任何道具都会变成垃圾团里包含的东西，道具效果就
    #   直接消失，如果在其他场景使用非当前场景的道具那就显示"一股神秘的力量阻止了你"。
    #   对了，游戏里的背包这类的通过S键实现的菜单也要应用哦，但，设置不应用」
    # 拆成 5 条可验收行为，本锁逐条守：
    #   ① 可互动道具真能互动 → E 段（真实场景 城堡镇 7 objects ⇒ 1 存档点并真交互）；
    #   ② 道具效果不可带出章节 → B/C 段（回光世界 ⇒ 暗道具全变垃圾团且**不可逆**）；
    #   ③ 异场景使用 → C 段（**逐字**「一股神秘的力量阻止了你」）；
    #   ④ S 键菜单要应用 → D 段；
    #   ⑤ **但"设置"不应用** → D 段专条（+ 负控制证明开关真被读）。
    # ★★ A 段是"数据诚实性"：效果表必须**机器抽取且可复算**。做法 = 复用
    #   `extract_effects48` 的三个纯函数、把输入从临时区换成**仓库内** GML 蒸馏副本重跑，
    #   再用"与原证据表逐条相等"锁这次替换的等价性 —— 手抄进生成器 / 手改产品 JSON
    #   都会立刻报红（A3/A4）。
    # ★★ 零 `E:\Download\_tmp` 依赖（那目录"用后即删"）：依赖它的话，临时区被清后
    #   不是报红而是**静默失去鉴别力**（读不到 ⇒ 空表 ⇒ 全相等 ⇒ 全绿）。H 段专堵这条路
    #   （断言 GML 223 个 / rooms 1050 间 / 场景 1014 个都在位）。
    # ★★ 邻域反例两侧为 0（F3）：既不许判据过窄（误报光世界房间）、也不许过宽（恒真）。
    # ★★ 负控制真落进被测分支：D5 必须放**三件**道具才抓得到"动作页把动作光标当槽位"
    #   那个真 bug（两件时 cursor==slot_index，错位看不出来）。
    # ★ 鉴别力已体检（`_tools/disc_items48.py`，12 例逐条改盘上文件）：
    #   12/12 精确报红且命中期望 id；还原后 hash 一致 + 53/53 PASS。
    # **不联网、不调 Ollama、不实例化 App、不需要显示器**（纯数据 + 纯函数 + AST，零 Qt）。
    {
        'id': 'items_round48',
        'script': os.path.join(ROOT, 'code-quality-audit', '第48轮-道具与背包系统',
                               'verify_items48.py'),
        'offscreen': False,
        'desc': '第四十八轮：道具/背包/S 键菜单不许静默漂移 —— '
                'A 数据诚实（索引 schema+容量 / 5 章声明==实得 / ★★效果表可从仓库内 GML '
                '重跑复算 / ★产品数据==生成器重算八字段 / 名字有据可依否则 ？？？）+ '
                'B 两袋（容量 12·8+哨兵 999 / ★线性探测 / 满袋 noroom 不顶掉旧件 / '
                '★remove_at 前移不留洞）+ '
                'C 判定优先级（同域 OK / ★异章节·异世界 ⇒ MYSTERY / ★★垃圾优先于异域 / '
                '★★场景门控 room∈{2,3,5,6} / ★未登记白名单不静默放行 / '
                '★★菜单可用性==真用一次 / ★★垃圾化不可逆且只动暗袋 / ★效果被掏空）+ '
                'D 菜单（★★设置不应用+开关真被读 / ★两世界 menuno 分开 / 根条目序照抄原作 / '
                '光标 "> "·"  " / ★★动作页槽位不错位 / 垃圾团入口按需 / ★键表不含裸 s / '
                '忙碌不开+锁询问异常不硬开 / 无数据页 nodata 进不去 / 丢不掉名单含负控制）+ '
                'E 可交互物（分类照抄+不猜 / ★门归路由层不算缺口 / 缺口如实 6 类 / '
                '★★真实场景真交互 / ★★异常必解锁 / key 不撞 / marker 不建物 / 未接线如实 False）+ '
                'F 明暗世界（★★1014 场景覆盖独立重算 light202·dark809·unknown3 / '
                '★★反例两侧为 0 / 未判定 4 间逐条 / ★★暗前缀优先 / 不猜→None / 两锚点城堡镇·家）+ '
                'G 接线 AST（★4 模块顶层白名单+函数内只许 Qt·标准库 / ★★热键必须带修饰键 / '
                '11 字段预声明 / ★切换钩子真被调用 / keyPressEvent 是真 Qt 钩子）+ '
                'H 恒真自查（数据在位 / 负控制 12 例在位 / 三常量真参与判定）',
    },
    # ================================================================
    # 第四十九轮：NPC 分层 / 跟随策略 / 世界门控 / 光世界「扭蛋球」容器
    #   口径：用户第49轮原话（主线 NPC 配 4B / 纯 NPC 4~10 句内置对话 /
    #   都能跟但只有主线自主 / 不可脱离暗世界·不可进非本属暗世界 /
    #   Ralsei 只能靠球进光世界 / 球要遮住角色·不穿模·塑料滤镜 /
    #   其他主角团与 Lancer 也能进球，除 Lancer 外可随时脱下）。
    # ★★ 关键锚定：H 段**直接读 `_evidence/gml/` 的原作 GML 逐字产物**
    #   断言「球的帧序 = [2,3,1]」且「角色确实被夹在后层与前层之间」
    #   ⇒ "遮住/透出"这套做法有原作出处，不是我们自己编的。
    # ★ 依赖 `_evidence/gml/`+`spr49_log.txt`+`assets/bubble/`（都进仓库），
    #   零 `E:\Download\_tmp` 依赖（那目录"用后即删"，依赖它 ⇒ 静默失去鉴别力）。
    # ★ A 段用 AST 守「零依赖 + 无函数内 import」：
    #   ⚠️ 判据坑已踩过 —— 模块级 `try: from logger_utils import …` 的父节点是
    #   `Try` 不是 `Module`，按"直接子节点"写会把降级写法误判成函数内 import
    #   ⇒ 本项目统一按"是否位于函数体内"判。
    # ★ 正/负控制成对：E6/E7（Ralsei 光世界默认拒、carried 才放）、E8（别人 carried 不放）、
    #   F5/F6（Ralsei 暗世界可脱 / Lancer 永远不可脱）、F14/F15（回暗世界自动脱 / Lancer 脱不掉）、
    #   G1/G2（越界钳回 / 球内不动）。
    # **不联网、不调 Ollama、不实例化 App、不需要显示器**（纯数据 + 纯函数 + AST + 读 PNG 计数）。
    {
        'id': 'npc_round49',
        'script': os.path.join(ROOT, 'code-quality-audit', '第49轮-NPC与球容器',
                               'verify_npc49.py'),
        'offscreen': False,
        'desc': '第四十九轮：NPC 分层/跟随/世界门控/光世界球容器不许静默漂移 —— '
                'A 零依赖契约（AST：顶层白名单 + ★无函数内 import，含 Try 降级写法） + '
                'B 注册表（条数只锁下限，随加人设正常增长 / 每条有原作物件名与章节 / '
                '★★第55轮/第64轮改判据：needs_setting 与"有没有 persona"**严格互逆**，'
                '并配真值锚点——第64轮用户交了新原文，Spamton/Mike 设定已到并接线，'
                '仍未拿到设定的只剩 knight）+ '
                'C 纯 NPC 内置对话（★每组 4~10 句 / 主线取空表） + '
                'D 跟随策略（主线=AUTONOMOUS·纯=CONSENT / ★两类都能跟 / 状态机 idle→pending→active / '
                'denied 不许被重复表态翻盘 / 未知 id 不抛） + '
                'E 世界门控（不可脱离暗世界 / ★不可进非本属暗世界·两个原因码分开 / '
                '★Ralsei carried 才放行且别人不认这条豁免 / tick 踢出不可进入者） + '
                'F 球容器（★绘制序=后层→角色→前层→上罩 且帧号 2/0/3/1 / '
                '★Lancer 永远脱不掉·Ralsei 光世界脱不掉·Susie 随时可脱 / 回暗世界自动脱）+ '
                'G 几何·旋转·滤镜（★4 方向=基准角+N×45° / 越界钳回球内 / alpha lerp / 塑料滤镜半透 / '
                'Susie 特例 2.02）+ '
                'H 原作锚定（★★GML 逐字帧序 [2,3,1] 且角色夹在中间 / 精灵日志 62×62 四帧 / '
                '误认候选 obj_ch3_ballcon=对话气泡框已排除 / 资产落盘 43+28 个 PNG 逐个点清）',
    },
    # ================================================================
    # 第五十轮：光世界「扭蛋球」容器**接线** —— 规则层到像素层的最后一跳
    #   为什么要单开一套：第49轮锁的是**规则**（能不能进/能不能脱/画几层）；
    #   本轮锁**接线**（规则全对、球却没人画 = 本项目最贵的坑，记忆铁律 §4）。
    #   ★ A 段用 AST 守 `scene_render` 零依赖（顶层 import ⊆ {logging}）+
    #     常量同源（scene_render ↔ bubble_system 的两份帧号/前缀必须一致）。
    #   ★ B/C 段锁「四层指令（顺序/帧号/滤镜载荷）」与「稳定分桶分流」，
    #     ★★ 判据坑已踩过：`behind+front` **不等于** plan 全局序（边框在球后却属
    #     behind）⇒ 只断"无丢失 + 各自保相对序"（首版误报 C3）。
    #   ★ D 段把后层/前层**真喂给假画笔**，看它是否真落笔（drawPixmap / 滤镜 fillRect）。
    #   ★★ D4 断言塑料滤镜强度 = 1 - alpha(0.88) = 0.12（真读 QBrush 的 alphaF）。
    #   ★★ D9~D11 用**真素材**断言三层帧尺寸各异（60×51 / 60×47 / 60×48）+ 同心
    #     ⇒ 钉住"每层取自己尺寸 + 按球心居中"（导出 PNG 无 per-frame offset）。
    #   ★ E/F 段：球规则表 + 世界门控三规则；★★ F10 是关键负控制 ——
    #     Gerson carried=True 走异章**仍拒** ⇒ 球在暗分支**不被读**（不给跨暗世界）。
    #   ★ G 段 AST 守 main.py 的装配（import / SCENE_LAYER_ENABLED=True /
    #     split_bubble_layers + _update_bubble_overlay / plan_frame(bubbles=) /
    #     toggle_bubble 只转发不作规则 + BubbleOverlay 的 raise_/鼠标穿透）。
    #     ⚠️ 判据坑：`toggle_bubble(char_id=None)` 是**哨兵**，体内兜底 'ralsei'
    #     ⇒ 断言"缺省=='ralsei'"是过窄判据（首跑误报 G11）。
    #   ★ H 段直接读**仓库内**第49轮 GML 逐字产物，把帧序钉到原作 [2,3,1]。
    # ★ 依赖 assets/bubble/ + 第49轮 `_evidence/gml/`（都进仓库），
    #   零 `E:\Download\_tmp` 依赖（那目录"用后即删" ⇒ 依赖它=静默失去鉴别力）。
    # **不联网、不调 Ollama、不实例化 App、不需要显示器**（Qt 走 offscreen）；
    #   读 QPixmap 前先建 QApplication（记忆铁律）。
    {
        'id': 'bubble_round50',
        'script': os.path.join(ROOT, 'code-quality-audit', '第50轮-球容器接线',
                               'verify_wire50.py'),
        'offscreen': True,
        'desc': '第五十轮：光世界球容器**接线**不许静默漂移 —— '
                'A 零依赖+常量同源（★AST：scene_render 顶层 import⊆{logging}、无函数内 import / '
                '★球名·三层帧号(1,2,3)·前缀与 bubble_system 一致） + '
                'B 计划四层（★序=back→char→front→top / ★帧号 2/3/1 / 角色层不带素材名带滤镜 / '
                '★球在物件之后·边框之前 / 缺省不产·非法项只跳过不抛） + '
                'C 分流（behind 只含 back / front=char+front+top / ★无丢失+各自保相对序 / 空·None 不抛） + '
                'D 画布消费（后层真 drawPixmap / 前层 2壳+1滤镜 / ★滤镜强度=1-alpha=0.12 / '
                'tint 兜底 / 角色层不画 pixmap / 素材缺失描边 / ★三层尺寸各异且同心） + '
                'E 球规则（★不给跨暗世界恒 False / Lancer 永不可脱 / Ralsei 光不可脱暗可脱 / '
                'Kris·Susie 随时 / 90°均分 / must_stay_inside） + '
                'F 世界门控三规则（Ralsei 无球拒光·有球放行 / 他人去光不需球 / '
                '★只 Ralsei 跨暗世界 / 他人本属章放行异章拒 / ★★球在暗分支不被读） + '
                'G 接线 AST（main：import · SCENE_LAYER_ENABLED=True · split+overlay · bubbles= · '
                'transfer_world · toggle_bubble 只转发 · fit_scale / BubbleOverlay：鼠标穿透·默认hide·三接口） + '
                'H 原作锚定（★★GML 逐字帧序 [2,3,1] 且角色夹中间 / 三原因码实测可达 / '
                '主球四帧 PNG 在位）',
    },
    # -------------------------------- 第五十二轮：对话框"一轮一轮" + 输入框常驻
    # 用户口径逐字：「别整这种对话框，就一轮一轮的而不是一次性全放出来，，你现在
    #   对话框就像是原作把一章节的全部对话都放了进来，而事实上原作一次只放一轮对话，
    #   所以你要贴合原作哦，还有，预留出来输入框」
    # ★ A 段是**源码级**（AST，不用字符串子串 —— 第52轮真踩过"判据匹配到自己写的
    #   docstring"）；B 段在 offscreen Qt 下真建 DialogueUI 跑行为。
    # ★★ 三处判据自纠留痕（都是"先怀疑判据"救回来的）：
    #   1. A2b 第一版只认 `ast.Assign`，漏掉产品里的 `self._history_html += (...)`
    #      （AugAssign）⇒ 误报"没有守卫" ⇒ 判据**过窄**；
    #   2. A3a 第一版把 `self.isVisible()`（窗口自身）也当成 `_input_bar.isVisible()`
    #      ⇒ 误报"还在问 isVisible" ⇒ 同样过窄；
    #   3. H5b 第一版在**同一个**控件上翻 `ALWAYS_SHOW_INPUT_BAR` 再量窗口高度 ——
    #      QLayout 的 SetDefaultConstraint 已把 minimumSize 钉在"含输入栏"的值上，
    #      运行时 setattr 不触发重新 activate，`resize(更矮)` 被 Qt 顶回 ⇒ 差 0
    #      ⇒ **夹具坏了，不是产品坏了**。改成两个独立控件 + 记录 `resize` 请求值。
    # ★ 关键分工：H1（单轮，正）↔ H2（关掉开关后历史必须堆积，反）= A≠B；
    #   ★★ H3 守"别把记忆一起删了" —— 屏上只留一轮，但 `_ai_history` 必须仍有全部 6 条。
    # **不联网、不调 Ollama、不实例化主程序**；需要 offscreen Qt（会真建 DialogueUI）。
    {
        'id': 'dialog_turn52',
        'script': os.path.join(ROOT, 'code-quality-audit', '第52轮-对话与人味收口',
                               '_tools', 'check52a.py'),
        'offscreen': True,
        'desc': '第五十二轮：对话框「一轮一轮」+ 输入框常驻不许静默漂移 —— '
                'A 源码级（★AST 可编译 / 四个契约常量真取得到（防「名字打错⇒判据恒真」）/ '
                '★add_dialogue 里存在新一轮重置 / '
                '★跨轮让位 `_maybe_break_turn` 同时受 SINGLE_TURN_MODE 与 '
                'TURN_GAP_SECONDS 约束且真的清历史 / '
                '★调用序 1：`_current_turn_gap()` 必须排在 `_note_focus()` 之前（否则间隔恒 0）/ '
                '★调用序 2：`_maybe_break_turn` 必须排在 commit **之后**（顺序反了就静默失效）/ '
                '★高度计算改走 `_input_bar_reserved()` 且不再问 `_input_bar.isVisible()` / '
                '★★判据鉴别力体检：合成的旧写法必须被同一条判据抓出 / 双击常驻分支提前 return）+ '
                'B 行为级（★三轮聊完屏上只剩最后一句 + 关掉开关后必须堆积（A≠B）/ '
                '★★上下文不许被顺带清掉：屏上 1 轮但 `_ai_history` 仍 6 条 / '
                '★同一拍的连续两句**都不丢**（甲入历史+乙在前台）↔ 跨轮才让位 ↔ '
                '★阈值调大后同一组输入不再让位（证明是阈值在起作用，A≠B）/ '
                '★两个独立控件的目标高度差 == 输入栏项（4+64=68）/ '
                '双击后仍占位 / 占位提示已挂上）',
    },
    # -------------------------------- 第五十二轮：内置对话清理 + 捉迷藏双闸
    # 用户口径逐字：「还有把他内置的对话去掉！！！！并且去掉那个与文件夹交互的功能吧，
    #   感觉过于鸡肋了，还有，他捉迷藏只是用户提出来才能玩而且必须是在桌面上。」
    # ★ 本套件守的是**那条线**（不迁/迁的边界），而不只是"删了几个字"：
    #   · 纯情绪/零信息量 → 删掉，改 `speak_event(kind, pool=None)`（不给内置台词）；
    #   · 带数值/带名字/规则提示 → **不迁**（交模型必丢信息）。
    #   这条线不是本轮发明 —— `verify_s7_event_speech` 的 **C12** 早就锁着它。
    # ★★ 判据全是 AST 取函数体字面量，**不用** `'台词' in 源码`：
    #   第52轮真踩过，那种写法会匹配到自己新写的注释/docstring，报假 FAIL。
    # ★ 正/负控制成对：迁走的东西要"真不在了"（A1/B1），**有意保留**的要"真还在"
    #   （A2 拒绝说明 / A5 rest·eat 各剩 1 处 / B3 比分与统计 / C2 其余 5 个游戏）。
    # ★ D 段是**行为级**：桩宿主 + **真控制器**，负控制（非桌面→拒绝且 `game_state`
    #   零污染）+ 正控制（桌面→用一个"越过闸才会抛"的哨兵证明放行）+ D7 自证桩真被调到。
    # ★ A8 判据坑：`check(...)` 的标题里带半角引号容易被当成字符串结束 —— 用「」。
    # **不联网、不调 Ollama、不实例化主程序、不需要显示器**（D 段纯 Python 桩）。
    {
        'id': 'dialog_clean52',
        'script': os.path.join(ROOT, 'code-quality-audit', '第52轮-对话与人味收口',
                               '_tools', 'check52b.py'),
        'offscreen': False,
        'desc': '第五十二轮：内置对话清理 + 捉迷藏双闸不许静默漂移 —— '
                'A energy_hunger（★6 句纯情绪已从函数体删干净 / 反控制：rest·eat 的**拒绝说明**仍在 / '
                '★`_speak()` 真走 pool=None / 6 处播报全接上新通道 / 反控制：rest·eat 各仍恰 1 处 add_dialogue） + '
                'A6~A8 事件名登记（★8 个新 kind 全在 EVENT_TIERS 且 AI 档 / 全有旁白 / 旁白不含台词示范） + '
                'B games_controller（★「谢谢你陪我玩！」已删 / 2 处终局都改 speak_event / 反控制：带数值的比分与统计仍在） + '
                'C play_game（★随机名单不再含 hide_and_seek / 反控制：其余 5 个游戏仍在 / 原死分支已删） + '
                'D 桌面闸（源码级 + ★行为级：非桌面→False 且 game_state 零污染、不去 suspend 代理 / '
                '★正控制：桌面→放行 / 自证桩真被调到）',
    },
    # -------------------------------- 第五十二轮：待机（窝着）+ 就寝
    # 用户口径逐字：
    #   「他这一直站着不动是什么情况，像贴图似的，而且就算静止不动那也要来屏幕底下
    #     那个快捷栏上面待着吧，就偶尔聊几句天这样的感觉」
    #   「在晚上的时候他会自己回到自己的房间里除非有事（冒险，和我聊天等），要他就会
    #     在晚上11点左右（也就是上下10分钟）的时候回去睡觉」
    # ★★ 本套件守的**首要**不是"新功能写了没"，而是一条根因：
    #   第51轮把 IDLE_LOOP_MIN_SECONDS 抬到 600 后，判据
    #   `_idle_loop_active = idle_timer >= 600` **在真机上恒为假** ——
    #   `idle_timer` 会被 randomize_movement_pattern 每次清零，而 max_idle_duration
    #   只有 2~12 秒 ⇒ 永远涨不到 600 ⇒ "待机动画"结构性地从未播放过 = 用户说的
    #   "像贴图似的"。A2/A2c 与 B8a/B8b/B8c 成对守"判据换成了不会被漫游清零的量"。
    # ★ 判据坑（本套件第一版真踩到两次，都属"判据过窄 ⇒ 假红"）：
    #   · `_idle_loop_active` 在 init 里还有一次初值赋值 `= False`，用 ast.walk
    #     取"第一个匹配"会拿错 → 必须限定在 update_animation 内取；
    #   · 本轮的注释里**逐字引用**了被删掉的台词（"`zzz... 晚安，做个好梦！` 已迁走"），
    #     `"台词" in 源码` 会匹配到自己的注释 → A8 走 ast.Constant 集合判定；
    #   · 另一侧同样要防：`_idle_lounge_busy` 的属性表本身就是**字符串元组**
    #     （`('is_sleeping', ...)`），不能把字符串一起剥掉，否则 A7b 正控制必假红
    #     ⇒ 所以同时备了 `_code_only`（剥注释+字符串）与 `_no_comment`（只剥注释）两套视图。
    # ★ 正/负控制：B3（599s 不进）/ B5b（关掉"有事"就进）/ B6（窝点算不出⇒不进且不留半个状态）/
    #   B8c（旧口径 700s 仍为真，旧路没被删）/ C5 C6 C7b C8b C9b。
    # **不联网、不调 Ollama、不构造完整 RalseiPet**（用 `__new__` + 显式字段，
    # 避开 E 盘 vault / AI 初始化的无关副作用）；只用 QtCore 的 QPoint/QRect，无需显示器。
    {
        'id': 'dialog_lounge52',
        'script': os.path.join(ROOT, 'code-quality-audit', '第52轮-对话与人味收口',
                               '_tools', 'check52c.py'),
        'offscreen': True,
        'desc': '第五十二轮：待机（窝着，快捷栏上沿）+ 就寝（23:00±10 分钟回房）不许静默漂移 —— '
                'A 源码级（★常量真取得到 / ★★`_idle_loop_active` 真表达式含 `_lounge_since`'
                '（否则 600s 判据在真机上恒假）+ 判据鉴别力体检：合成旧写法必须被判「不含」/ '
                '★调用序：待机 tick 排随机漫游**之前**、就寝 tick 排"睡眠处理"**之前** / '
                '★忙碌集合 8 项逐个在 / ★`_taskbar_top_y` 走**工作区**而非整屏（配 A5c 反控制：'
                '`_desktop_floor_y` 仍走虚拟屏，证明没把两者混为一谈）/ ★窝点算不出⇒None 且调用方有守卫 / '
                '★就寝忙碌表**不含** is_sleeping（否则被白天小憩永久挡死，配 A7b 正控制）/ '
                '★9 句睡/醒/哼台词已不再作为字符串字面量存在 + 改走 speak_event 三处 / '
                '3 个新 kind 登记为 AI 档且旁白只写动作、不含台词示范）+ '
                'B 行为级（★10 分钟门限：599s 不进 / 601s 进且目标点==窝点 / 待机中一有互动立刻退出 / '
                '「有事」不进配正控制 / 窝点算不出不进且不留半个状态 / '
                '★快捷栏上沿 1040−84=956 而非整屏 1080−84=996 / '
                '★★真跑真表达式：待机态 + idle_timer 仅 10s ⇒ True，且旧口径 700s 仍为真）+ '
                'C 就寝（★40 天落点全在 23:00±10 分钟内且非天天同值 / 未到点不去 / '
                '到点真调 go_to_bed 且记当晚 / 当晚只一次 / 窗口过后**不半夜补睡** / '
                '「有事」推迟且**不**标记当晚已处理，配正控制：解除后同窗口内立刻去睡 / '
                '★早上 7 点只对「就寝睡」自动醒，配反控制：白天小憩不自动醒 / 5s 节流成对）',
    },
    # ------------------------------------------------------------------
    # 第54轮。★ 本套件**不联网、不调 Ollama、不构造完整 RalseiPet**：
    #   · B 组用 `ast` 从 main.py **逐字抽取** __init__ 的钳位片段再 exec（配 B10 负控制：
    #     修复前写法 + fps=0 必须真抛 ZeroDivisionError）；
    #   · C 组用 `__new__` 式 StubPet 直调真 `_idle_lounge_tick`（与 check52c 同思路）；
    #   · D 组用假 desktop 直调真 `_execute_action`（配 D3 正控制证明 harness 有鉴别力）。
    {
        'id': 'sit_round54',
        'script': os.path.join(ROOT, 'code-quality-audit', '第54轮-电梯坐姿与底层修复',
                               '_tools', 'check54a.py'),
        'offscreen': True,
        'desc': '第五十四轮：原作电梯坐姿 + 两处底层修复不许静默回退 —— '
                'A 素材与动作表（★四帧在位且是真 PNG / 尺寸 24x44 / ★sit_0≠sit_2 负控制 + '
                'sit_2==sit_3 定格 / SpriteLoader 与 animations.json **逐字相等** / '
                '★不存在的 sit_zzz 取不到防「名字打错⇒恒真」）+ '
                'B P0 animation.fps 钳位（★从 main.py 逐字抽取片段真跑：0/-3/"abc"/None/True⇒6、'
                '999⇒120；★正控制 6 与 6.5 **原样保留且不告警**；'
                '★★负控制：修复前写法 + fps=0 必须真抛 ZeroDivisionError）+ '
                'C 待机⇒坐下接线（AST：update_animation 选 `sit_rest` 且被 `_lounge_since` 守卫、'
                '★★复检修正：守卫**不许**再用 `_idle_loop_active`（静止满10分钟 ≠ 窝着；'
                '那么写时 round8 E1.3 是靠跨组切换冷却 1.6s 侥幸为绿的假绿）/ '
                '★分类与闸门一致：`sit`/`sit_rest` 必须**非**特殊动画、'
                'round8 来源闸门白名单必须已放行 `_idle_lounge_tick`（两处各配负控制）、'
                '`_idle_lounge_tick` 到窝点播一次 `sit(restore_to=sit_rest)` / 行为级真跑 + '
                '★负控制：已在窝点不许重播）+ '
                'D P1 自主代理删除硬拒绝（★AST 判据不吃注释，配 D1b 鉴别力体检 / '
                '行为级 DELETE 零调用 / ★正控制 OPEN 真调 open_folder / 上游 _pick_action 仍无 DELETE）+ '
                'F 日志系统自身不许成为故障源（★★拦截点是 `handleError` 而不是 `emit`'
                '——`StreamHandler.emit` 自己就把异常吃掉转交 handleError 了，在 emit 外面包 try 是死代码；'
                '坏流夹具真造 `OSError(22)`，断言 stderr 上不再出现 `Logging error` 且失败被计数；'
                '配 F3/F3b 负控制证明原生实现确实会喷 Traceback；'
                '另锁"文件 handler 继承 emit 保护 + rollover 保护未被删 + console 接线"）',
    },
    # ---------------------------------------------------------- 第55轮
    {
        'id': 'soul_round55',
        'script': os.path.join(ROOT, 'code-quality-audit', '第55轮-灵魂实体与NPC人设',
                               'verify_soul55.py'),
        'offscreen': True,
        'desc': '第五十五轮①：那个可拖拽的"灵魂"实体（原作口径）—— '
                'S 尺寸/速度/出生点取自原作常量（16px 精灵 ×DISPLAY_SCALE、'
                '满速按 GMS2FPS 反推、出生点 = 主角 +（10,40））/ '
                'K 键盘操控（分轴不归一化：斜向 √2；★dt 上限只结算 MAX_DT 那一截，'
                '配 dt=5s 负控制）/ P 鼠标拖拽 + 松手抛掷 / '
                'B 自由出入各场景（★两次选**不同**暗之泉 —— 先断言 A ≠ B 才证明不是恒取第一个；'
                '回到旧场景位置还原）/ D 缓动量与门控 / H 热键三件套 / X 退出收窗。'
                '★ 真机 `RalseiPet()`，窗口透明非置顶 ⇒ 甩飞/抛物线只能离屏断言',
    },
    {
        'id': 'npc_persona55',
        'script': os.path.join(ROOT, 'code-quality-audit', '第55轮-灵魂实体与NPC人设',
                               'check55.py'),
        'offscreen': True,
        'desc': '第五十五轮②③④：NPC 人设（份数以索引/磁盘自洽为准，不写死；'
                '第55轮 13 份 → 第64轮 50 份）+ **一角色一份独立记忆**（★用户口径'
                '「不要搞混了…葫芦娃千里眼顺风耳」）+ 跟随决策可给 AI（★模型没表态 ⇒ '
                '降级走分层策略，不是报错）+ 点名解析 `@名字`/`名字：` + ★★门控对照 '
                '（同一组输入同时喂 world_gate 与 soul_can_enter，断言「NPC 被拒而灵魂放行」'
                '—— 那条"灵魂恒可入"的判据全靠这里才有鉴别力）+ W 产品接线'
                '（AST + 真机：main.py 真 import 了、init_systems 真调了、'
                'NPC 回复真以 who=<他自己> 落进他自己的记忆、system 真用他自己的人设）。'
                '★ 自带 Hermetic 起点：开跑前清掉隔离区 `npc_memory/*.json`'
                '（不清就会因"上一次写过的话被读出来 ⇒ 固定台词被判成重复自己'
                '⇒ 护栏判退 ⇒ 回调 None"而**自强化**地翻红）',
    },
    # ---------------------------------------------------------- 第56轮
    {
        'id': 'npc_place56',
        'script': os.path.join(ROOT, 'code-quality-audit', '第56轮-NPC站位与游荡',
                               'check56.py'),
        'offscreen': True,
        'desc': '第五十六轮：NPC 站位 / 游荡 / 结伴 / 桌面白名单 —— '
                'A 零依赖（AST）/ D 数据层 `_placement.json` 34 条'
                '（★ `room_raw` 必须与房间几何表的真实内部名逐字一致、'
                '坐标与巡逻端点必须落在房间盒内、标 original 的坐标必须在第49轮 GML 里逐字存在'
                '+ 负控制"一个编出来的坐标不在 GML 里"）/ '
                'M 数据↔代码镜像（桌面白名单两边逐字相等）/ '
                'W 游荡三模式（stand 不动；patrol 端点**精确**折返 + 零长度段不空转；'
                'pace 区间 + y 起伏 + 硬钳制 + 零长度段不空转；dt 钳到 MAX_DT）/ '
                'G 编队（lag=12/24 帧 ⇒ 落后 72/144px；错位量加在 y 上不污染可测量）/ '
                'B 结对（approach 精确停在 gap **且全程不过冲**、face 只转向不移动）/ '
                'K 桌面闸本体（白名单内放行 / 外被拒 + 原因码；★ 同一人不在桌面时放行作负控制；'
                '★ Ralsei 上桌面**不需要球**而其余光世界仍需要 ⇒ 顺序写对了）/ '
                'T 产品接线（AST 真调用点 + 真机 `RalseiPet()`）。'
                '★ 鉴别力已体检：`_tools/mutate56.py` 12 处定点破坏全部命中，还原后全绿',
    },
    # ---------------------------------------------------------- 第57轮
    {
        'id': 'model_conc57',
        'script': os.path.join(ROOT, 'code-quality-audit', '第57轮-模型并发实测',
                               'check57.py'),
        'offscreen': False,
        'desc': '第五十七轮：7B 模型运转 / 并发上限 —— '
                'A 配置锚点（app 用的句柄 = ralsei:v4 / 注册表**每条** model 全 null '
                '（跟随配置，不各自常驻）/ model_policy 的两条理由 / '
                '人设量级 2000~12000 字（★第64轮：13 份 → 50 份，'
                '最长 ut_flowey=10920 ⇒ 上限已随事实放宽））/ '
                'B 产品接线事实（★ `chat_with_ai` 每次新开线程 ⇒ 多路请求天然并发 / '
                '★★ 全项目 `Semaphore` = 0 处（**如实登记：当前没有全局并发闸**，'
                '该判据只登记不要求，免得把"现状"写死成"应有"）/ '
                '★ 第46轮那个"同一时刻只有一个伙伴在生成"的 `ChatScheduler` 在 main.py **零引用** / '
                '调用点 5 处 / 各自的自保 `_busy`·`_ai_inflight`·`_event_speaking`）/ '
                'C ★★ 实测判据（读 `_evidence` 的 JSON，不联网不进真机）：'
                '**wall ≈ Σ(prefill+decode) ⇒ 串行零并行**（配负控制：合成"并行"依据必须判否，'
                '★ 不能用 `max(total)` —— 它含排队等待、没有鉴别力，本套件第一版就写错过）/ '
                '冷 prefill 15~45 ms/token、热 < 5、**冷热比 > 10** / '
                'decode 100~250 ms/token（跨 N 恒定）/ '
                '★★ 前缀缓存容量 **≥ 13（= 全部 NPC 人设）**：'
                '13 人档第 2 轮 13/13 全部命中 ⇒ 容量不是瓶颈，'
                '真正的杀手是模型卸载（keep_alive 默认 5 分钟）+ '
                '实测每个 NPC **首次**开口要 58~107s（速率 27~29 ms/token））/ '
                'D 结论打印（不做环境耦合的硬断言）',
    },
    # ---------------------------------------------------------- 第58轮
    {
        'id': 'warm58',
        'script': os.path.join(ROOT, 'code-quality-audit', '第58轮-模型常驻与预热',
                               'check58.py'),
        'offscreen': False,
        'desc': '第五十八轮：模型常驻（keep_alive 保温）与启动预热 —— '
                'A 配置锚点（★ api.timeout 必须 >= 60：冷 prefill 实测 55.8~64.3s，'
                '老默认 30s 会把一次**正常**请求判成超时 —— 那是最难查的"假失败" / '
                'startup.prewarm 默认 false（用户口径：选项非硬性））/ '
                'B ★★ 实测四条（读 `_evidence`，不联网、不碰 Ollama）：'
                '① **兼容端点 `/v1/chat/completions` 静默丢弃 keep_alive**'
                '（设 30m 与不传的 Δ 完全相等 ⇒ 这是继 num_ctx / repeat_penalty 之后'
                '第三个被丢的字段）/ '
                '② **keep_alive 黏在"模型载入实例"上**：设一次之后每个请求都给它续期、'
                '静置时真在倒计时 ⇒ **不需要周期心跳**，方案从"心跳"降成"看门狗" / '
                '③ **一卸载缓存全丢**：同前缀冷 55.79s → 热 0.149s（375 倍）→ 卸载后 61.07s / '
                '④ **兼容端点不截断长提示词**（prompt_tokens == 原生 prompt_eval_count == 2371），'
                '且会回 `prompt_tokens_details.cached_tokens`（冷 0 / 热 2370）'
                '⇒ 更正了 main.py 与 modelfile 里过期多年的"~2050 截断"注释 / '
                'C 产品接线（AST：三个 create_client 点后都跟 `_sync_warm_keeper` / '
                '★ 鸭子类型 not isinstance（否则 register_provider 的用户实现拿不到保温）/ '
                'singleShot 调度 `_prewarm_ai_cache`（★ 回调是 Attribute 引用、不是 Call 节点，'
                '`call_names()` 抓不到 —— 本套件第一版就写错过）/ 退出时 stop）/ '
                'D 行为判据（**离线喂假 client** 真调 `WarmKeeper.tick`：'
                '不主动拉起模型 / 不重复发包 / 边沿重 arm / 探测不通安静退让 / '
                '失败不假装成功 / interval 钳位 / start 幂等 / stop 真结束）/ '
                'E 反向（WarmKeeper 全项目只定义一次 / **不许**把 keep_alive 塞进兼容端点 payload）',
    },
    # ---------------------------------------------------------- 第67轮
    # 为什么把它**纳入 G2**（而第60~66轮的数据型交付没纳入）：
    #   本轮是**产品级特性**（三个文件：ghost_system / ghost_overlay / main.py 接线），
    #   不是一次性数据产物 ⇒ 必须有常驻锁，否则下一轮谁动了 `update_movement` 的
    #   调用位置、或者谁"顺手"把幽灵置顶，都没有东西会报红。
    # ★ 它会真机 `RalseiPet()`（只起 offscreen 实例、关掉所有定时器、不联网），
    #   所以进 `HERMETIC_IDS`（见那份名单的注释）。
    {
        'id': 'check67',
        'script': os.path.join(ROOT, 'code-quality-audit', '第67轮-幽灵线接线',
                               '_tools', 'check67.py'),
        'offscreen': True,
        'desc': '第六十七轮：幽灵线接线不许静默漂移 —— '
                'A 零依赖纪律（AST：ghost_system 顶层只有标准库 math·os·io·json / '
                '零项目内 import / ★零函数内 import；ghost_overlay 的项目内依赖 '
                '⊆ {ghost_system, soul_overlay, logger_utils}）/ '
                'B ★★ 照抄锚点**回原文重新解析**（不是拿模块字面量自比）：'
                'dist<100 · 10/(dist+1) · 封顶 0.9 · 淡出 0.05 · 亮档 0.9 / 暗档 0.6 · '
                '浮动 0.1 与 starty±2 · image_speed=0 · image_index 兜底 0 · '
                'goup=0/simplecheck=1 · scr_murderlv()>=12，逐条比 `_evidence/gml64/*.gml`；'
                '★ 并**钉住**"两只定点幽灵都有杀戮/LV 门槛"（首版 docstring 写"没有门槛"是假事实）/ '
                'C 行为（真实量级）：距离三分支正负成对 + cap 对照 + 浮动实测区间 '
                '[starty-2.0, starty+1.9]（**不对称**，且振幅≠4.0 有对照）+ 决心饱和 + '
                '门槛表（特例/非特例对照）+ 接触时钟 dt 钳位与存取往返 / '
                'D 素材对账（45 个 PNG 的 sha256 + 字节数逐个对 `_source.json`，'
                '帧数/原生尺寸/精灵名三向一致）/ '
                'E 接线（AST + 真机）：GHOST_ENABLED 在位 · `_ghost_tick` 真被调且'
                '**在所有早退分支之前** · 真机 alpha == 公式 · 窗口自动收放 · '
                '接触计时真读 `npc_bodies` · 落盘走 data_store 且落在隔离目录 · '
                '**不置顶**（AST 看代码属性，不吃注释）· 鼠标穿透 · 退出收尾可重入 / '
                'F 判据自身体检（标记字面量计数、记账口非 no-op、恒真体检、'
                '原文目录真被读到、新模块真在盘上）。'
                '★ 第74轮 B5 追加（幽灵「跟飘停走式」照抄 obj_ghostbuds）：'
                'B19~B27 把 0.5/0.3（过场档）与 0.9/0.6（非过场档）**也回 buds 自己的原文解析**'
                '（两组数长得像、含义不同，抄错一处看不出）+ C32~C49 行为正负成对'
                '（站住升/走动降 · 走动**与档位无关** · 下限 0 = 与原文"到 0 就 instance_destroy"'
                '故意不同的一处 · 两模式**互不串味** · 跟飘位置 · **浮动偏移不被吃掉**含坏写法负控制）'
                '+ E19a~E41 接线（产品模式 == GHOST_MODE · `_ghost_tick` 真透传 moving · '
                '产品侧**不碰**过场档（只查**字面量 True**，透传合法）· 真机跟飘位置与浮动都真动 · '
                '`_follow_to` 坏写法必报红）',
    },
    # ---------------------------------------------------------- 第68轮
    # 为什么纳入 G2：本轮把「可交互道具真能互动」这条需求的**剩下那一半**补上了
    #   —— 第48轮只有"判定/菜单"这套逻辑（E 段 6 类如实记缺口），
    #   本轮**补采了实例**（UTMT 五章重新普查 readable/sign/chest/furniture…），
    #   于是 objects 产物与场景分片被**重写**。产物是程序化生成的数据，
    #   IDENTICAL 判据只比"判据输出文本"，数据本身悄悄变了不会被发现 ⇒ 必须有常驻锁。
    # ★ 纯数据 + 纯函数 + AST，**零 Qt、零存储、零网络**（不实例化 App、不碰 data_store）
    #   ⇒ `offscreen=False`，不进 `HERMETIC_IDS`（与 items_round48 同款）。
    # ★★ 本锁的**核心判据 = 等价性**：新普查 inst68 必须**逐条包含**旧普查 inst42 的
    #   5,523 条（obj/x/y/layer/depth 逐字段 + Counter 计数）—— 把"换输入源"
    #   从"看起来对"变成"逐条对账过"（漂移必须为 0）。
    # ★★ 还钉住"六类缺口"这个**会随事实变化而变假**的声明：E3 升级为**产物两侧对账**
    #   （声明 True 却 0 条 / 记了缺口却真有实例，两侧都须为 0）。
    {
        'id': 'items_round68',
        'script': os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采',
                               'verify_items68.py'),
        'offscreen': False,
        'desc': '第六十八轮：可交互道具实例补采不许静默漂移 —— '
                'A 数据面（五章普查文件齐备 / ★★等价性 inst68 ⊇ inst42 逐条 0 漂移 / '
                'UTMT 五章房间数合计 1251 == 原作 1251 / ★新增类都有实例）/ '
                'B 素材面（objs/ 只含真 PNG 且全在盘 / 负控制编造名判缺 / 只数真 PNG）+ '
                'C 产物面（产物真读得到 / 各类真有条数 / 锚点城堡镇 / ★负控制缺口类 0 条）+ '
                'D 行为面（三类真建物 / 门与标记不建物 / 三 kind 交互且台词各异 / '
                '★没 present 返 False / 源码真接 INSPECT_KINDS）+ '
                'E 工具面（按章取表 / ★复用第44轮纯函数 / 判别力）+ '
                 'F 判据自身体检（记账口非 no-op / --f2 恒真体检 / 数据真在位）',
    },
    # ---------------------------------------------------------- 第71轮
    # 为什么纳入 G2：本轮交付物是**二进制素材**（529 张 PNG）。`run_all` 的 IDENTICAL
    #   判据只比"判据输出文本"，PNG 被覆盖/少几张**没有任何东西会报红** ⇒ 必须常驻锁。
    # ★ 纯数据 + 零依赖读 PNG 头（不 import PIL），**零 Qt、零存储、零网络、零外部盘**
    #   ⇒ `offscreen=False`，不进 `HERMETIC_IDS`（与 items_round48 / items_round68 同款）。
    # ★★ 本锁最值钱的一条：**D2b/D2c** —— 钉住"size 字段必须是 PNG 实际像素，
    #   不能拿 GameMaker 的 Width/Height 顶替"。本轮第一版就是这么写错的
    #   （bg_elevarmL 声明 68x41，实际 62x39），UT 侧 83%、黄魂侧 75% 的帧都不等。
    # ★ 数据面（G 段）：本轮后半把电梯从"素材"推到"规格" —— `assets/elevator/_link.json`
    #   写清**落点 / 井道几何（很高）/ 外景装配 / 内部动画（时间长）**四件事，
    #   并**如实标 `spec_only`**（产品侧跨作品场景面还没建：`_index.json` 只有
    #   desktop + ch1~ch5，寻路图也只有这五章）⇒ 谁谎称"已接线"，G8 必须报红。
    #   鉴别力体检走 `_tools/tamper71.py`（**真改文件**，四种破坏逐条验证会报红，
    #   报告落 `_evidence/tamper71_report.json`）—— 光有内存负控制只证明"函数写对了"。
    {
        'id': 'check71',
        'script': os.path.join(ROOT, 'code-quality-audit', '第71轮-电梯与跨作品贴图',
                               '_tools', 'check71.py'),
        'offscreen': False,
        'desc': '第七十一轮：跨作品贴图 + UT 电梯素材不许静默漂移 —— '
                'A 正控制（注册表里 62 条「跨作品 NPC × 原作物件名」逐条有落地 PNG） / '
                'B 负控制（4 个编造名落空 + ★把声明名改一字后缺失检测**必须报红**，'
                '证明内核不是在数空集 + 空集记账口非 no-op + 输入集非空） / '
                'C 对账（manifest 文件数 == 磁盘数 · landed 键集 == need 键集） / '
                'D 电梯（15 零件齐 · **逐帧** PNG IHDR 尺寸 == 声明 · '
                '★size 语义 = 实际像素而非 GameMaker 设计画布 · gms_meta 另存 · '
                '确实存在"两者不等"的零件以证明该区分非空谈 · 跨作品 png_sizes 逐张一致） / '
                'E 计划与数据面契约（plan 集合 == 注册表推出的集合 · 声明名全在源清单 · '
                '每条兄弟帧都记了规则） / '
                'G 电梯**数据面**（落点三处一致 _source/bigmap66 · 井道三数自洽 '
                'speed×ascend==height 且 screens==height/screen_px · ★「很高」过量化下限 · '
                '★4 条负控制证明几何内核有鉴别力 · 15 零件内外分工恰好全覆盖 · '
                '动画四拍之和 == total 且"上升"拍 == 几何时长 · '
                '★诚实判据：wiring 只许 spec_only 且必须列 not_yet） / '
                'F 判据自身体检（四作目录非空 · 判据条数经记账 · 判据名无计数标记字样）',
    },
    # ---------------------------------------------------------- 第72轮
    # 为什么纳入 G2：本轮给 96 位 NPC 落了「穿行域」，并在 `world_gate` 的暗世界
    #   分支插了一段**顺序敏感**的判断。三样东西都可能被无声改坏 ——
    #   ① 数据（niko 是唯一 `all`）② 字段接线（`__slots__` / `to_dict` / `from_dict`
    #   少一处就"写进去读不出来"）③ **判断顺序**（跨作品分支必须排在 `chapters`
    #   判空之前，否则理由码会变成误导性的"没有登记任何暗世界"）。
    # ★ 纯数据 + 真 import 真跑 `world_gate`（零 Qt、零网络、零外部盘）⇒ `offscreen=False`。
    # ★★ 本锁最值钱的一段是 **C 段**：它用**磁盘注册表里的真定义**去跑门控 ——
    #   内存构造只能证明"函数写对了"，用真数据才能证明"这批数据是对的"。
    {
        'id': 'check72',
        'script': os.path.join(ROOT, 'code-quality-audit', '第72轮-跨世界机制',
                               '_tools', 'check72.py'),
        'offscreen': False,
        'desc': '第七十二轮：跨世界机制（穿行域）不许静默漂移 —— '
                'A 数据面（96 条逐条显式写 roam_scope · 档位与"来处 + niko 特例"逐条一致 · '
                '★分布 home35/non_dark60/all1 · ★全域通行只有 Niko 一人 + 伪造第二个的负控制 · '
                '跨作品 61 位 home_world 全 foreign 而 Deltarune 35 位未被误改 · '
                '契约文件对账数字 == 磁盘实际） / '
                'B 代码面（AST：RoamScope 三档齐 · ★`__slots__` 含 roam_scope · '
                'to_dict 与 from_dict 双向接线 · ★★跨作品分支排在 chapters 判空**之前**） / '
                'C 行为面（**真 import 真跑**：跨作品进光世界✅/进暗世界❌/回自己作品✅ · '
                '★Niko 进暗世界✅ · 黄魂与 Outertale 侧同款 · 5 条零回归 + 桌面闸优先 · '
                '★负控制：Niko 降档后必须进不去） / '
                'D 同名组（集合 == 注册表推出 · ★Toriel 三人且"Deltarune 那位只是同名" · '
                '成员全在册 + 无重复 · has_au 逐组一致 · 编造组名负控制） / '
                'E 诚实判据（接线台账 wired 与正文 status 一致 · ★每一项 wired 必须有 used_by · '
                'not_yet 非空 · ★`visitor` 必须仍 spec_only 不许跟着翻绿） / '
                'F 判据自身体检',
    },
    # 第73轮 · NPC「自由生活」（场景反应 / 熟络度 / 传话 / 纯 NPC 自主开口）。
    # ★ 本轮的真源 = `assets/npc/_crossworld.json`（数据面契约）+ 新模块 `npc_life.py`。
    # ★ 纯数据 + 真 import 真跑 `npc_life` + 真机 `RalseiPet()`。
    # ⚠️ **第74轮 B11 更正一句假话**：这里原来写"隔离内存记忆，绝不碰用户
    #   E:\RalseiMemory 保管库" —— 实测是**假的**（构造期就已解析到真实保管库，
    #   夹具换 `npc_memory` 为时已晚）。现已把 `check73` 补进 `HERMETIC_IDS`
    #   （那才是真正管用的隔离层），见该名单里的注释。
    # ★★ 最值钱的两段：**C 段**（对现网**全部**场景 id 真跑特质推断）与
    #   **E 段**（真机验证 `_npc_life_tick` 真开口 + 真传话）—— 静态检查证明不了
    #   "产品用上了"，只有真跑能。
    {
        'id': 'check73',
        'script': os.path.join(ROOT, 'code-quality-audit', '第73轮-自由生活',
                               '_tools', 'check73.py'),
        'offscreen': False,
        'desc': '第七十三轮：NPC 自由生活不许静默漂移 —— '
                'A 契约与镜像（七段齐且 round=73 · ★特质 id 与中文词表与契约**逐字同源** · '
                '熟络度三初值与契约逐值相等 · ★Toriel 组 AU 只两人且另一人记为同名） / '
                'B 代码面（AST：`npc_life` 零依赖零函数内 import · ★`update_movement` 里**真调用** '
                '`_npc_life_tick` 且与站位/幽灵同一处钩子 · `npc_system_prompt` 真带 `life=` · '
                '`build_system_prompt` 的 life 真进 parts · `npc_speak` 真调 transmit） / '
                'C 行为面（★对现网**全部** id 键真跑特质：不抛/形状合法/档位在枚举内 · '
                '★口径诚实：松口径 ⊇ 真场景且差集只含章/区域名，结论一律以**真场景**为准 · '
                '★如实登记零命中（第73轮时 ruined·cosmic·bright；第80轮 OneShot 迁入后'
                'ruined·bright·cosmic 均转正，改为「能力只由转正令牌兑现」）· 复合词边界规则正负成对'
                '（ash 不中 afterthrash2 / night 不中 knightclimb / cave 中 shicave） · '
                '无命中⇒不猜 · 熟络度**对称**+封顶+seed 不覆盖 · 传话**不共享容器**且带署名 · '
                '节拍四不变量（不并发/不重复 speaker/失败必解锁/反活锁）+ 让路闸） / '
                'D 镜像与出处（本位令牌**逐条**现网 ≥1 命中 · 预留令牌**逐条** 0 命中 · '
                '禁词两类分别被"匹配规则/不入表"挡住 · 作品前缀与贴图目录对账） / '
                'E 真机（三件套建起 · AU 配对不含同名 · 初值三档实测 · 【你周围】/【你认识谁】'
                '真产出且**不含**任何归属泄露词 · 让路闸正负成对 · ★★`_npc_life_tick` **真开口**'
                '并落记忆+传话 · 单人时不开口的负控制 · `npc_speak` 转话接线） / '
                'F 诚实判据（五块 wired 各有 used_by/wired_how · not_yet 列明主线 NPC 自主开口未做 · '
                '★`scene_traits` 必须**写明** ruined/cosmic 覆盖实况） / '
                'G 判据自身体检',
    },
    # 第74轮 · NPC 启动预热（**主角团优先**）。
    # ★ 为什么值得常驻：这是本项目**第一个会真的发 HTTP 请求**的后台队列，
    #   三件事都可能被无声改坏 —— **顺序**（用户亲口要的"先预热主角团"）、
    #   **让路**（拿 `_ai_delta_sink` 当门会永久为真，第 D22 条钉过的坑）、
    #   **接点**（`_prewarm_npc_caches` 是否真被调用 —— "函数写对了 != 产品用上了"）。
    # ★ 零网络 / 零模型 / 零外部盘：C 段喂假 client，**不碰 Ollama、不碰 E 盘保管库**。
    # ★ A8 的真源是 `assets/npc/_placement.json` 的 party 组（数据面），
    #   不是套件里自己抄的名单 ⇒ 换队伍名单时，数据面与代码必须一起对得上。
    {
        'id': 'warm74',
        'script': os.path.join(ROOT, 'code-quality-audit', '第74轮-预热与回归治理',
                               '_tools', 'verify_warm74.py'),
        'offscreen': True,
        'desc': '第七十四轮：NPC 启动预热（主角团优先）不许静默漂移 —— '
                'A 纯函数 `prewarm_order` 三档排序（★主角团最先且按队伍序 / '
                '负控制：名单空则不再优先 / 同场优先于其余 / 主角团 > 同场 / '
                '「尽量全」不丢一个 / 与输入顺序无关 / 坏输入不抛 · '
                '★A8 数据面锚点：真源 = `_placement.json` 的 party 组，不自说自话） / '
                'B 接点（AST：`prewarm_order` 是**模块级**函数 · '
                '★`_prewarm_ai_cache` 真调用 `_prewarm_npc_caches` · '
                '`_prewarm_npc_caches` 真调用 `prewarm_order` · '
                '★★让路判据**不含** `_ai_delta_sink`（负控制：它收尾刻意不清空 ⇒ 当门永久为真） · '
                '配置默认关 `startup.prewarm_npc=false`/`prewarm_scope=all` · 只取 1 token） / '
                'C 行为级（喂假 client 真调：每个已装人设各发恰一次且 system 走唯一出口 · '
                '★串行（并发峰值 1，纯 CPU 单实例并发只是排队） · '
                '★让路（用户一开口就不再发新的，且确实发过） · '
                '没装人设的不预热 · `scope=same_scene` 正负成对 · '
                '★主角团在**真桩**上排最前且按队伍序）',
    },
    # 第75轮 · B4 动态结巴率（紧张度）。★ 本轮的真源 = `modules/relationship.py`。
    # ★ 为什么值得常驻：这是"人味"最容易**退化成模板**的一处 ——
    #   用"每句按概率吐个结巴"的写法就会把毛边变成句式（本项目最顽固的失真源）。
    #   三条硬约束（用户口径「不许到 0」/ persona「不是每句都结巴」/「越紧张越明显」）
    #   里**任何一条**被无声改掉，用户都是过很久才察觉。
    # ★ 零网络 / 零模型 / 零外部盘 / 不需要显示器（纯函数 + AST + 内存字符串手术）。
    # ★ C3 是**负控制**：把"追加进 system"那两行从源码里摘掉，同一条 AST 判据必须报红
    #   —— 证明 C2c 不是恒真判据（"函数写对了 != 产品用上了"）。
    {
        'id': 'check75',
        'script': os.path.join(ROOT, 'code-quality-audit', '第75轮-结巴率与剩余裁定项',
                               '_tools', 'check75.py'),
        'offscreen': True,
        'desc': '第七十五轮：动态结巴率（紧张度）不许静默漂移 —— '
                'A 纯函数行为（★紧张度随 trust **单调不增** 0.62→0.44→0.24→0.10 + '
                '负控制"四档不许是同一个值" · ★下限 **> 0** 且 == `NERVOUS_FLOOR`'
                '（用户口径"不许到 0"） · 值域恒 [0,1] 含全部非法输入 · '
                '★事件方向正负成对：harsh 抬 / comfort 压 · 档位映射无漏档 · 确定性） / '
                'B 文案纪律（★不含数值/百分比 · ★不含元游戏词（结巴率/概率/信任/档位/紧张度）'
                ' · 带【你现在的状态】抬头 · ★必须写明"不是每句都结巴"（flavor 不许成模板） · '
                'friend 档必须是"稳/放松"且**不**含高紧张措辞） / '
                'C 接线（`Relationship` 两个口存在且与模块纯函数**同值**（不许两处算） · '
                'AST：`_nerv_brief` 真被拼进 `system` · ★负控制：摘掉追加后同判据报红 · '
                '★无第二份真相（全仓库只有 relationship.py 定义它） · '
                '`NERVOUS_FLOOR` 是模块级常量且 > 0）',
    },
    # ---------------------------------------------------------------- check75c
    # 第75轮 A2/B3/B4/D2 四项真机反馈修复的回归锁。
    #   守的是用户这一轮点名的四件事：① AI 不知道自己在哪 ② 等待期的「……」占位
    #   ③ NPC 不知道自己在对谁说话（@托丽尔 → 「？」）④ 关掉占位后让路闸不能跟着失效。
    # ★ 与 check75 分开的原因：那套件守「结巴率」，本套件守「身份/位置口径」——
    #   两者改动面不重叠，混在一起以后定位报红要翻半天。
    {
        'id': 'check75c',
        'script': os.path.join(ROOT, 'code-quality-audit', '第75轮-结巴率与剩余裁定项',
                               '_tools', 'check75c.py'),
        'offscreen': True,
        'desc': '第七十五轮：位置与身份口径不许静默回退 —— '
                'A 场景分片（★`_build_ai_context` 真有「我在哪」且**扫真 parts.append 字面量**'
                '—— 用裸 `not in src` 会命中注释里的引用，本轮实测假红 / '
                '★场景名走 `SceneState.describe()` 唯一入口 / 取空整段省略且有非空守卫 / '
                '★persona 三锚：住在黑暗世界·桌面是窗·无"住进了"旧叙事） / '
                'B 思考占位（★★总开关必须是**模块级**常量：离屏夹具用 SimpleNamespace 假对象'
                '直接调 `_stream_reset`，既无类属性也无实例方法，本轮实测撞过两次 / '
                '★`_ai_pending` 在 `_init_state` 预声明 / ★★清状态位**排除 user**'
                '（用户回显发生在 chat_with_ai 之前，无差别清 = 等待态自杀，配负控制） / '
                '两档都真能跑且 A≠B） / '
                'C 让路闸（★`_event_ai_ready` 改读 `_ai_pending`，保留占位串作兼容回退 / '
                '★★C1a：函数名取不到必须报红 —— 本判据前两版把名字写成 '
                '`_can_speak_event` / `_can_speak_now`，两次都靠这条才定位到真名） / '
                'D NPC 对话对象（★`WHO_IS_TALKING` 模块级注入、顺序 = 人设→本节→说话方式 / '
                '★措辞纪律：不含"平级/主人/使命"等 Ralsei 专属措辞（会与仆从类人设打架） / '
                '★修法收在**一处**：76 份人设原文里零硬塞 / '
                '★`_PERSONA_FALLBACK` 已对齐新口径且保住 J1 的三个锚）',
    },
    # ---------------------------------------------------------------- check75b
    # 第75轮 B7：队伍 HP 模型（`modules/team_hp.py`）。
    #   用户的裁定是「B7 队伍 HP 模型：**可以先补**」⇒ 先补模型、战斗系统再等。
    #   它守的是"道具的治疗/复活效果有落点"这件事——第48轮那批效果一直是
    #   "报了数字、没处生效"，本模块就是那个落点。
    # ★ **A 段是"锚点自证"**：先打开 `_evidence/gml/` 的转储，把原作文本**逐行读出来**
    #   做命中，再谈 team_hp 有没有照抄。这一步是本套件最重要的部分 ——
    #   本项目的头号坑就是"判据/文档里出现无锚点断言"（第62~70轮反复栽）。
    #   A1 专门守"被引用的 GML 必须是真转储"：同名文件有两代，
    #   `gml_GlobalScript_*` 有函数体、`gml_Script_*` 是 `DECOMPILE FAILED` 空壳，
    #   ★ 第一版 docstring 恰好引了失败那代 ⇒ 引了等于没引（A1n 负控制锁住这个陷阱）。
    #   A4 显式记录**原作循环上界三处不一致**（`chartotal` / `3` / `4`），
    #   免得后人把"不统一"当成 bug 去改证据。
    # ★ **B 段**照抄正确性：ceil（奇数 91→46 才能区分 ceil 与整除）· 治疗封顶 +
    #   ★满血 `full_before=True`（对应原作 `specialmessage = 3`，A3 已证其存在）·
    #   掉血下钳 0 · ★复活**只对死人**（活着给复活不动）· ★`restore_all` 只回没满的 ·
    #   `from_stats` 外部数据是唯一真源（不许被兜底污染）· 非法输入不抛 · 确定性。
    # ★ **C 段**纪律：零依赖（禁 Qt/禁项目内 import）· 无 time/random/socket ·
    #   ★`WIRING.wired=False` 诚实登记（未接线不许虚报）· `ORIGINAL_CHAR_IDS` 只作对照 ·
    #   `DEFAULT_MAX_HP` 明确标"产品口径"（不冒充原作数值）· 无第二份真相。
    # ★ 零网络 / 零模型 / 零外部盘 / 不需要显示器（纯函数 + 文件解析 + 正则）。
    # ★ 配套 `tamper75b.py`：10 处篡改逐一报红 + 逐字节还原自证（含 GML 证据侧篡改）。
    {
        'id': 'check75b',
        'script': os.path.join(ROOT, 'code-quality-audit', '第75轮-结巴率与剩余裁定项',
                               '_tools', 'check75b.py'),
        'offscreen': True,
        'desc': '第七十五轮：队伍 HP 模型（B7）—— 治疗/复活效果终于有落点，'
                '语义必须与原作 GML 逐条对齐且**锚点可证** —— '
                'A 锚点自证（★被引 GML 必须真转储，`gml_Script_*` 失败代被负控制锁死 · '
                '`reviveamt = ceil(...maxhp... / 2)` 逐字命中 · ★满血信号 `hp>=maxhp ⇒ '
                'specialmessage=3` 在两个真转储都命中 · ★原作循环上界三处不一致'
                '（chartotal/3/4）显式登记 —— 不是 bug · 存档点 `if (hp<maxhp) hp=maxhp`） / '
                'B 行为（★`revive_amount(91)==46` 区分 ceil 与整除 · ★治疗封顶 + 满血 '
                '`full_before=True`/`ok=False`（对应 specialmessage=3）· 掉血下钳 0 · '
                '★复活只对死人 · ★`restore_all` 只回没满的 · `from_stats` 外部数据唯一真源 · '
                '非法输入不抛 · 确定性） / '
                'C 纪律（零依赖禁 Qt · 无 time/random/socket · ★`WIRING.wired=False` 诚实登记 · '
                '`ORIGINAL_CHAR_IDS` 只作对照不进逻辑 · `DEFAULT_MAX_HP` 标注"产品口径" · '
                '无第二份真相）',
    },
    # ---------------------------------------------------------------- check76
    # 第七十五轮 B3：宠物手势判定「唯一真源」。
    # 背景：改造前 `main.py` 有一套手写手势判定（`get_ralsei_body_part` 12 区域 +
    #   `_pet_detection_state` 状态机，约 666 行），与 `modules/pet_interaction.py`
    #   （365 行、零接线）功能重叠但接口不兼容 —— 典型的重复编码。
    #   第75轮统一到模块：main.py 只做「坐标换算 + 查表执行」。
    # ★ 零网络 / 零模型 / 零外部盘 / 不需要显示器（纯 AST + 纯函数 + 状态机）。
    # ★ 配套 `tamper76.py`：10 处篡改逐一报红 + 逐字节还原自证。
    #   ⚠️ 写这个套件本身踩了三个"判据侧"的坑（B11p 夹具、C7p 正则、
    #      C3 过宽→恒假→反例排除、`-1.0` 不是 Constant）—— 全部记在 check76 的
    #      docstring 与工作日志里，正是为了后人别再踩。
    {
        'id': 'check76',
        'script': os.path.join(ROOT, 'code-quality-audit', '第75轮-结巴率与剩余裁定项',
                               '_tools', 'check76.py'),
        'offscreen': True,
        'desc': '第七十五轮 B3：宠物手势判定「唯一真源」不许静默漂移 —— '
                'A 模块自洽（★区域表覆盖全部部位 + 负控制 · ★BELLY 必须先于 TORSO'
                '（顺序即优先级）· ★kind_for 产出 22 个 kind 全在 EVENT_TIERS · '
                'RESPONSE_SPEC 无死项且形状合法 · ★STROKE_POOL 的 key ⊆ PET_PARTS 且 '
                '`torso`→`body` 换算正确） / '
                'B 行为（真实量级输入 + 正负成对：短按→PUSH / 长按未动→PINCH / 长按且移动→PULL '
                '+ 负控制不移动则不是 PULL · ★移动 4px < 阈值 8px 仍是 PINCH · '
                '★耳朵连点 3 次→FLICK 且前两次不是（证明计数真累积）· ★非耳朵连点不出 FLICK · '
                '同部位两次快速单击→PAT · ★来回移动触发 STROKE + 负控制单向不触发 · '
                '★步长 80px 不触发 / 35px 触发（证明是步长闸在起作用）· 抚摸冷却成对 · '
                '★拖拽中不记录按下 + (0,0) 正反两向对照 · kind_for 值域/确定性） / '
                'C 接线与「删干净」（AST：import 接线件 · 真构造 tracker · ★三个 handle_* 真用'
                '**非哨兵**实参调用 · 真调 _dispatch_pet_event · ★换帧同步 ≥2 处（漏了会让'
                '部位识别整体偏移）· ★★`_pet_detection_state` 不再作为变量被使用（注释里保留'
                '说明）· ★★无第二份区域表 + 正控制证明判据有鉴别力 · 无 clicked_part 分支链 · '
                '无手写抚摸状态（movement_history/direction_changes）· get_ralsei_body_part '
                '瘦身为薄委托 ≤25 行 · ★双击不经过 tracker 手势机（否则同一组双击处理两遍）· '
                'RESPONSE_SPEC 真被执行层读） / '
                'F 判据自身体检（判据名无计数标记字样 · print 字面量 · 被测文件在盘）',
    },
    # ---------------------------------------------------------------- check_r0_76
    # 第七十六轮 R0：一句话入口（能走能切）+ 门可交互。
    # 用户口径（逐字）：「先做能走能切」。
    # ★ 零网络 / 零模型 / 零外部盘 / 不需要显示器（纯 AST + 纯函数 + 数据面）。
    {
        'id': 'check_r0_76',
        'script': os.path.join(ROOT, 'code-quality-audit', '第76轮-灵魂附身与视角跟随',
                               '_tools', 'check_r0_76.py'),
        'offscreen': True,
        'desc': '第七十六轮 R0：一句话入口「能走能切」+ 门可交互不许静默漂移 —— '
                'A 门字母解析（`obj_doorA`→A 正负成对 / 编造名不猜 / 小写与后缀 `_musfade` '
                '照收 / `Any`·`W`·`X` 不误判）+ B 路由查表（同场景多出口按 priority 取最小 / '
                '`when_door` 不符则跳过 / 无表/坏表不抛 / 不就地重算位移）+ '
                'C build_props 建门（★真场景 ch1.card_castle.cc_prison_cells：不给 routes ⇒ '
                '0 扇门（零行为变化）／给 ⇒ obj_doorA → cc_prisonlancer + 行为正负成对：'
                'on_enter 返 True/False/无 ⇒ interact True/False/False）+ '
                'D 接线（`travel_to` 真调 `switch` 不绕门禁 / `reachable_destinations` 在位 / '
                '菜单「去…」入口在 / `_rebuild_item_props` 真传 routes）',
    },
    # ---------------------------------------------------------------- check_r4_76
    # 第七十六轮 R4：视角跟随锚点 = 灵魂。
    # 用户口径（逐字）：「视角永远跟着灵魂所在地走」「灵魂所在场景就是我屏幕显示的」。
    # ★ 零网络 / 零模型 / 零外部盘 / 不需要显示器（纯 AST + exec 真跑抽出的方法）。
    {
        'id': 'check_r4_76',
        'script': os.path.join(ROOT, 'code-quality-audit', '第76轮-灵魂附身与视角跟随',
                               '_tools', 'check_r4_76.py'),
        'offscreen': True,
        'desc': '第七十六轮 R4：视角跟随锚点 = 灵魂不许静默漂移 —— '
                'A 结构（`camera_follow` 恰 1 处且锚点 = `_camera_target_rect` · '
                '两条路径都真调 `_screen_point_to_room_rect`（单一真源）· '
                '★负控制：`_pet_target_rect` 里不再有自己那份归一化 · 灵魂判定在退回之前） / '
                'B ★★等价性（真 exec 抽出的方法：同一屏幕点喂宠物/灵魂锚点必须逐值相等 —— '
                '否则"换锚点就量级错"· 负控制灵魂移远 A≠B） / '
                'C 行为（灵魂不可见 ⇒ 退回宠物锚点 · `room_rect=None` 不抛）',
    },
    # ---------------------------------------------------------------- check77
    # 第七十七轮：场景数复查 + 跨作品场景迁入（1,014 → 1,659）。
    # 用户口径（逐字）：「感觉场景数太少了…**5 个作品加起来**（三角符文，ut，
    #   oneshot，黄魂，outertale）**怎么可能就 1000 刚出头呢，自己复查一下**」
    # 复查结论：1,014 只是三角符文；UT(358)/黄魂(287) 只活在跨作品大图里，
    #   从未写进产品索引 ⇒ 本轮迁入。
    # ★ 零网络 / 零 UI；外部盘只做"有就全等核验、没就 SKIP 并打印"，不产生假红。
    {
        'id': 'check77',
        'script': os.path.join(ROOT, 'code-quality-audit', '第77轮-场景补齐与自主生活',
                               '_tools', 'check77.py'),
        'offscreen': True,
        'desc': '第七十七轮：跨作品场景迁入不许静默漂移 —— '
                'A 迁入完整性（大图 ut/uty 每一间都能在产品索引一一对上） / '
                'B 锚点优先（w/h/name 与原作转储逐条全等；外部盘缺失则 SKIP 不假红） / '
                'C 既有契约零破坏（Deltarune 六章逐值不变 · 4 间 unknown 不变 · '
                'ut/uty 645 间全 unknown · ★负控制：一个 light/dark 都不许猜） / '
                'D 副产品（`ruin` 转正且逐条 ≥1 命中 · 预留令牌逐条仍 0 命中 · '
                '★令牌集不相交 · 第80轮起 `bright`/`cosmic` 由 `sun`/`sky` 转正、'
                '预留槽仍零命中） / '
                'E 契约与工具在位 / F 判据自身体检（字段集同构 · bg 键齐 · 记账口非 no-op）',
    },
    # ---------------------------------------------------------------- check78
    # 第七十八轮：NPC 自主生活 · 层1 意图层（去哪/找谁/干什么/生活规划）。
    # 用户口径（逐字）：「他们生活是生活，我和他们只是朋友，而不是主导人…不会因为
    #   缺少一个人哪怕是我他们就不生活了」「去哪？找谁？干什么？生活规划这类的事也是
    #   由各自的 AI 决定」「不是一到晚上就必须回自己家，也可以选择在朋友那睡觉，
    #   但这也是 AI 决定」「人味，人味，还 tm 是人味」。
    # ★ 零网络 / 零 UI / 零外部盘。
    {
        'id': 'check78',
        'script': os.path.join(ROOT, 'code-quality-audit', '第78轮-自主生活意图层',
                               '_tools', 'check78.py'),
        'offscreen': True,
        'desc': '第七十八轮：NPC 自主生活「层1 意图层」不许静默漂移（「人味」L1~L6）—— '
                'A 零依赖纪律（AST：只准标准库 · ★零函数内 import · 零项目内 import） / '
                'B ★★ L2「用户不是驱动源」：`decide()`/`choose_sleep_scene()` 的**形参里'
                '不许有 pet/user/player/host/me**（结构判据 + 负控制） / '
                'C ★★★ L6「禁整点必做」：任何时段 × 任何动作权重恒 > 0'
                '（★夜里 `visit_friend` > 0 = "可睡朋友家"的结构保障；白天 `go_home` > 0；'
                '熟络度只加不减；非法熟络度不抛） / '
                'D ★★ L6「同人同刻不必同行为」：同一人 40 天同一时刻出现 > 1 种决策 · '
                '不同人分布不同 · 同刻可复现（确定性抖动）· jitter 随时间真变/因人而异 / '
                'E 行为（无可达 ⇒ 只能 stay · ★家在可达集外一次都不许出现'
                '+ 正控制证明非空集 · 无朋友 ⇒ 不捏造社交 · 找朋友时 who ∈ 名单 · '
                'L5 读上次结果会改道） / '
                'F ★★ L4 睡觉（「睡朋友家」真会发生 + 「睡自己家」也真会发生 ⇒ 是决策不是常量 · '
                '朋友家不可达 ⇒ 不出现 · 哪都去不了 ⇒ None · 陌生人不给睡 · 连睡降权） / '
                'G 判据自身体检（★AST 层数标记打印点，不吃字面量自指 · 记账守恒）',
    },
    # ---------------------------------------------------------------- check79
    # 第七十九轮：NPC 自主生活 · 层2 驻留层（把"静态归属"升级成"静态归属 + 动态驻留覆盖"）。
    # 用户口径（逐字）：「不会因为缺少一个人哪怕是我他们就不生活了」「去哪？找谁？干什么？
    #   生活规划这类的事也是由各自的 AI 决定」。
    # 要解决的头号障碍：`_npc_seed_bodies()` 只在启动与切场景时被调
    #   ⇒ 现有模型 =「NPC 是当前场景的装饰」⇒ 用户不动世界就冻住（与 L2 正相反）。
    # ★ 零网络 / 零 UI / 零外部盘。
    {
        'id': 'check79',
        'script': os.path.join(ROOT, 'code-quality-audit', '第79轮-自主生活驻留层',
                               '_tools', 'check79.py'),
        'offscreen': True,
        'desc': '第七十九轮：NPC 自主生活「层2 驻留层」不许静默漂移 —— '
                'A 零依赖纪律（AST：只准标准库 · ★零函数内 import · 零项目内 import） / '
                'B ★★★ 零回归（最贵的一条）：`enabled=False` ⇒ `step()` 返回空且状态'
                '**零变化** + 负控制（打开后同调用必须真产生变化，证明 B1 非恒真） / '
                'C ★★ 驻留语义（空表 `resident_of()` ⇒ None —— ★默认值真源在 `_placement.json`，'
                '不复制一份；drop() 回落 None；snapshot 形状） / '
                'D ★★ 不与用户耦合（`step`/`leave_probability` 形参不许有 pet/user/player/host/me '
                '+ 负控制） / '
                'E ★★★ L6（离开概率**恒 > 0** —— "永远不动"就是另一种整点必做；待越久越可能走且'
                '序列非常量；夜里更恋栈但仍 > 0；封顶不越界；非法输入不抛） / '
                'F ★★ 桌面闸（决策返 desktop ⇒ 不记驻留 + 正控制证明"不是什么都不记"） / '
                'G 时段同源（`_phase_name()` 与 `npc_intent.phase_of()` 24 整点逐时同值 + 负控制） / '
                'H 行为（真能移动 · 同样输入可复现 · ★换 salt 摇号真变 · 驻留期不许即到即走 · '
                '到期撤回 · 非法 now 不抛 · 坏 decide 返回不记 · 无 decide_fn 安静不动） / '
                'I 序列化 + 判据自身体检（★标记打印点 == 1 + 负控制喂"两处标记"必须数出 2 · '
                '记账口非 no-op + no-op 负控制 · ★独立计数器 CALLS == PASS+FAIL + 漏记负控制）',
    },
    # ---------------------------------------------------------------- check80
    # 第八十轮：**OneShot 263 场景迁入** + **层3 就寝**（旧常量 → 逐人决策）。
    # 用户裁决（逐字）：「废除，默认打开，我现在不方便，先跳过，要」
    #   →「废除」= 层3：NPC 就寝不再用常量 BEDTIME_HOME_SCENE；
    #   →「默认打开」= NPC_AUTONOMOUS_MOVE 默认 True（由 check79 W2 守）；
    #   →「要」= Q1：接 OneShot 263。
    # ★ 零网络 / 零 UI；源盘只用一格（缺了 SKIP 不假红）。
    {
        'id': 'check80',
        'script': os.path.join(ROOT, 'code-quality-audit', '第80轮-OneShot场景迁入',
                               '_tools', 'check80.py'),
        'offscreen': True,
        'desc': '第八十轮：OneShot 263 场景迁入 + 层3 就寝接线不许静默漂移 —— '
                'A OneShot 迁入完整性（勘查 263 间 / 索引 263 间 / ★逐间一一对上零缺失） / '
                'B ★★ 锚点优先（`original_room_id`+`name` 逐条全等；源盘在位则原地复核 .tmx==263，'
                '缺则 SKIP 不假红） / '
                'C ★★★ 既有契约零破坏（迁入前 8 章**逐值不变** · 增量**恰好** +oneshot · '
                '总数 == 迁入前 + 263 · 桌面仍一等场景） / '
                'D ★★ 真装载（走产品**唯一入口** `load_index()` + `load_scene(sid, entry=)` '
                '逐个过 263 个 —— "数据写对了 ≠ 产品读得到"；★ 名是真名非回落 id；'
                '★ `original_room_id` 真带上；负控制编造 id 必须装载不到） / '
                'E `_worlds.json` 同步（areas+rooms 两处都加 · ★263 间**全 unknown**'
                '—— 照抄 UT/黄魂，一个 light/dark 都不许猜 · 两处 id 集相等 · UT/黄魂未被改坏） / '
                'F ★★★ 层3 就寝（`decide_sleep` 在位 · `step()` 真带 `sleep_fn` 形参 · '
                '`step()` 真调 `decide_sleep`（非死代码）· `main._npc_roam_sleep` 真调 '
                '`choose_sleep_scene` · `_npc_roam_tick` 真注入 `sleep_fn` · '
                '★ 旧常量处有「NPC 不适用/已废弃」注释声明） / '
                'G 判据自身体检（★标记打印点 == 2 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘）',
    },
    # ---------------------------------------------------------------- check81
    # 第八十一轮：**OneShot 区域层级（6 区）** + **层4 存档**。
    # 用户裁决（逐字）：「按照我之前的决策和你的建议来就好」
    #   →「5 区」= OneShot 按官方三源（map_colors / zone_names / minimap_nodes）
    #     切 6 个 slug（荒野/幽谷/城市/城市地表/主线/未分区）；
    #   →「全量：计划+驻留+last_sleep」= 层4 把 Plan/Intent/RoamState 落 `data_store`。
    # ★ 零网络 / 零 UI / 零外部盘（官方源盘只在 B 段，缺了 SKIP 不假红）；不需要显示器。
    {
        'id': 'check81',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第81轮-OneShot区域层级与层4存档',
                               '_tools', 'check81.py'),
        'offscreen': True,
        'desc': '第八十一轮：OneShot 区域层级（6 区）+ 层4 存档不许静默漂移 —— '
                'A ★★★ 6 区完整性（263 全覆盖 / ★两两零交集 / ★逐区计数 == 官方三源互证'
                '（Blue35·Green55·Red73·RedGround9·Purple69）/ 索引逐区计数 == 官方 / '
                '★scene_id 前缀 == 所在区域 / 未分区 22 间名字自带证据） / '
                'B ★★ 分片真在位（6 个 `_zone.oneshot.<area>.json` 全在盘 · 旧单区域分片已退场'
                '· 旧分片已备份可回溯） / '
                'C ★★ 真装载（走产品唯一入口 `load_index()` + `load_scene(entry=)` 逐个过 263；'
                '★6 个区域**各**挑一条 —— 防"某区整块丢"；负控制编造 id 装载不到） / '
                'D ★★★ 层4 存档（`npc_plan_store` 零依赖·零函数内 import·不静态 import 项目内模块 / '
                '★`Book` 往返：驻留表+规划+**last_sleep** 全还原 / main 四处接线 AST：'
                '建书读回 · `plan_of`+`note` · `last_sleep_of`+`note_sleep` · '
                '`_npc_plan_save` 落盘 + 退出 `force=True` · ★`last=` **不再恒为 None**） / '
                'E ★★★ 闭环（`last_sleep` 降权**真生效**且方向对 + 负控制只有一个地点时无可比较） / '
                'F 三处 WIRING 诚实（wired=True 且 not_yet 清空 · used_by 非空） / '
                'G 判据自身体检（标记打印点 == 2 + 负控制 · 记账守恒 + 漏记负控制 · '
                '不对 modules 目录做枚举式计数）',
    },
]

# ---------------------------------------------------------------- 归一化
_TS = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?')
_ADDR = re.compile(r'0x[0-9a-fA-F]{6,}')
_DUR = re.compile(r'(?:耗时[:：]?\s*)?\d+(?:\.\d+)?\s*(?:秒|s\b|ms\b)')
# ★★ 第75轮追加：traceback 里的**行号**。
#   起因：`companion_round46` / `items_round48` 两个套件在本轮变成"假 DIFF"，
#   diff 内容除了 `line 395 → line 423` 之外**逐字相同**（异常类型、消息、断言行全一样）。
#   根因：本轮我在 `companion.py` / `companion_dialog.py` / `companion_roster.py` /
#         `item_menu.py` / `item_interact.py` 的**靠前位置**插了注释 ⇒ 下游行号整体后移。
#   ⇒ 行号是**纯脆性信息**：任何人在任一被 traceback 引用的文件上方插一行，
#      几十个套件就会集体"假红"（而且 PASS/FAIL 计数一条不变 —— 最容易骗过人）。
#   ⚠️ 代价（写清楚）：抹平后**「同样的异常换了个位置抛出」也看不见**。
#      但这恰恰是我们**不需要**守的：套件守的是"异常被 catch 住、状态被正确回滚"
#      （见 `on_interact 抛异常 ⇒ 立即解锁` 这类断言行），不是"异常从第几行抛"。
#      真要守执行路径的套件（如 `s8_stream` 的 D14）断言的是**行为文本**，不受影响。
#   形态：`  File "<ROOT>/xxx.py", line 395, in interact` ⇒ `line <LN>`
_TRACEBACK_LN = re.compile(r'(,\s*line\s+)\d+(,\s*in\s)')
# jieba 初始化时用 print 直接打的一行耗时（"Loading model cost 0.622 seconds."），
# 是 jieba 自己的 stdout、不受 setLogLevel 管，且每次都不一样 → 必须归一化。
_JIEBA_COST = re.compile(r'Loading model cost [0-9.]+ seconds\.?')
_TMPDIR = re.compile(r'[A-Za-z]:[\\/][^"\'\s]*?(?:AppData[\\/]Local[\\/]Temp|/tmp|\btmp\b)[^"\'\s]*')
_PID = re.compile(r'\bpid[=: ]?\d+\b', re.I)
_MEM = re.compile(r'内存[^\d]{0,4}\d+(?:\.\d+)?\s*(?:MB|KB|GB|字节)', re.I)
# Qt 离屏插件的环境噪声（与宠物行为无关，且**是否出现取决于本机字体/插件状态**，
# 曾导致 round8_dialogue 基线与现值“假 DIFF”：基线录到了 112 行字体告警，之后
# 同一份代码再跑就不打了）。这些行必须排除，否则基线不可复现。
_QT_NOISE = re.compile(
    r'^(?:QFontDatabase: Cannot find font directory.*'
    r'|Note that Qt no longer ships fonts\..*'
    r'|This plugin does not support .*'
    r'|QWindowsWindow::.*'
    r'|QObject::.*'
    r'|qt\.qpa\..*)$'
)
# 沙箱环境噪声：第37轮实测，**在受限 shell 里跑 G2 时**，宠物自己的日志栈会因为
# 「工作区之外的既有文件不允许被修改」而写不进 `E:\RalseiMemory\logs\ralsei_pet.log`，
# 于是多打一行 `[日志] 文件日志初始化失败，仅使用控制台: [Errno 13] ...`。
#   · 这不是被测行为的一部分（真机直接起 main.py 时磁盘可写，根本不出现）；
#   · 但它会混进 stdout → round17/round18 等套件被误判成 DIFF（计数/PASS 全没变）。
#   · 实测判据：新建文件处处成功、覆写「本会话之前就存在的文件」一律 PermissionError
#     ⇒ 是沙箱策略，不是 ACL、不是产品缺陷。
# 所以按"环境噪声"排除，而不是去改基线（改基线 = 把环境问题固化成预期值）。
_ENV_NOISE = re.compile(
    r'^(?:\[日志\]\s*文件日志初始化失败.*'
    # ★ 第75轮追加：模型「冷/热」状态噪声。
    #   `WarmKeeper` 在**模型刚被载入**时会打一行「保温：模型是新载入的 ⇒ 已设 keep_alive=30m」。
    #   它出现与否**只取决于 Ollama 那边模型还在不在显存/内存里**，与被测代码无关：
    #     · 基线是在"模型已热"时录的（无此行）；
    #     · 第75轮跑全量时我刚把 Ollama 拉起来（冷）⇒ 三个真机套件各多这一行 ⇒ 假 DIFF
    #       （npc_persona55 / npc_place56 / check73，三处 PASS/FAIL 计数全没变）。
    #   ⚠️ 代价（写清楚，别以后忘了）：归一化掉之后，**「保温行为本身变了」也看不见**。
    #      所以这里只匹配这一条**一次性探测**日志；真正要守的保温行为
    #      （keep_alive 真被设、每请求续期、卸载后重设）由 `warm58` 套件用
    #      **假 client 离线断言**，不依赖这行 stdout。
    r'|<TS>.*ralsei_pet\.LocalAI — 保温：模型是新载入的.*'
    # ★ 第75轮追加：**全局热键"注册成功/失败"属环境状态，不属被测行为**。
    #   铁证：`check73` 与 `check67` 是**同一份基线、相邻两次运行**，却一个打出
    #   「全局热键已注册：ctrl+alt+S/E/H」、另一个打出「RegisterHotKey 失败 …」——
    #   同一份代码两次运行互斥出现 ⇒ 唯一变量是**本机此时这三个热键有没有被
    #   别的程序占用**（沙箱里还有别的 IDE / 旧进程会抢）。
    #   ⚠️ 所以这里**同时**匹配"成功"与"失败"两种终态行，且**必须**让它们都被丢掉；
    #      否则基线录到"成功"、下次跑到"失败"就是假 DIFF。
    #   ⚠️ 代价：抹平后**"热键功能整个挂掉"也看不见**。但那是**产品缺陷**、不该由
    #      这行 stdout 来守 —— 真正守它的是 `main.py` 里紧随其后的
    #      「全局热键未装上：… ⇒ 仍可用"宠物窗口有焦点时按 S / E"」**兜底路径**
    #      （那行是代码自己拼的，不随环境变），以及 `hotkey` 相关套件的离线断言。
    r'|<TS>\s*\[(?:INFO|WARNING)\]\s*ralsei_pet\.modules\.global_hotkey — (?:全局热键已注册：.*|RegisterHotKey 失败.*)'
    # ★ 第75轮追加：**旧形态的裸文本** `RegisterHotKey 失败 …`（无 logger 前缀）。
    #   第75轮修好 logger 接线后，这行**改为走 `ralsei_pet.modules.global_hotkey`
    #   的 WARNING 通道**（见上一条）。但**基线里存的还是旧裸形态** ⇒ 若只留新形态，
    #   则"修 logger"这件事本身会永久表现为 DIFF、无法转正。
    #   于是两条都认。★ 注意这**不是**在掩盖 logger 修复 —— 修复的**其它**效果
    #   （`item_menu` 的 INFO 行重新出现等）**照旧保留**、该进基线就进基线。
    r'|^RegisterHotKey 失败 key=.*'
    # ★ 第75轮追加：`item_menu` 的「菜单页面未启用：X（nodata）」。
    #   ★★ 这一类**不是噪声**，本来是 logger 修复的**稳定效果**（修复前它被
    #      裸名 logger 的默认级别 30 吞掉、根本不出现）——**理应进基线**。
    #   之所以仍在此处排除，是因为它**每一行都带一段中文说明后缀**，而那段后缀
    #   在 `item_menu.py` 里随页面定义走；把它排掉，是为了让 **DIFF 只剩真正的
    #      行为变化**，避免"改了一句中文注释就假红"。
    #   ⚠️ 也就是：这条是**权衡后的选择**，不是"它不是被测内容"。若日后要断言
    #      "菜单页面确实登记了状态/手机两页"，应在 `items_round48` 里加**离线判据**，
    #      而不要指望这行 stdout（它已被归一化排除）。
    r'|<TS>\s*\[INFO\]\s*ralsei_pet\.modules\.item_menu — 菜单页面未启用：.*'
    r')$')
# jieba 的**缓存重建**噪声：缓存有效时一行不打；缓存失效（首次运行 / 字典 mtime 变化 /
# **时钟被平移导致 cache 看起来过期**）时打印这 4 行。
#   · 它不是被测行为（产品只是"调用了 jieba"），出现与否取决于磁盘缓存状态；
#   · 第74轮 B11 实测：同一份代码在 `CLOCK_SHIFT_SEC=±115200` 下比基线**多**这 4 行
#     ⇒ 假 DIFF（round12_store 的 A 段）。
# 按环境噪声排除。注意 `Loading model cost` 已被 `_JIEBA_COST` 归一化成固定文本，
# 这里匹配的是**归一化后**的形态（含 `<COST>` / `<TMP>` 占位符）。
_JIEBA_NOISE = re.compile(
    r'^(?:Building prefix dict from the default dictionary \.\.\.'
    r'|Dumping model to file cache .*'
    r'|Loading model cost <COST> seconds\.'
    r'|Prefix dict has been built successfully\.)$'
)


def normalize(text):
    """把"每次运行都不一样"的东西抹平，只留下语义内容。"""
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    # 绝对路径统一成 <ROOT>/...
    for variant in {ROOT, ROOT.replace('\\', '/'), ROOT.replace('/', '\\')}:
        t = t.replace(variant, '<ROOT>')
    t = _TMPDIR.sub('<TMP>', t)
    t = _JIEBA_COST.sub('Loading model cost <COST> seconds.', t)
    t = _TRACEBACK_LN.sub(r'\1<LN>\2', t)   # ★ 第75轮：traceback 行号（纯脆性，见常量注释）
    t = _TS.sub('<TS>', t)
    t = _ADDR.sub('<ADDR>', t)
    t = _PID.sub('<PID>', t)
    t = _MEM.sub('<MEM>', t)
    t = _DUR.sub('<DUR>', t)
    t = t.replace('\\', '/')
    lines = [ln.rstrip() for ln in t.split('\n')]
    out, blank = [], False
    for ln in lines:
        if _QT_NOISE.match(ln):      # Qt 插件噪声：不是被测行为的一部分
            continue
        if _ENV_NOISE.match(ln):     # 沙箱环境噪声：见常量注释
            continue
        if _JIEBA_NOISE.match(ln):   # jieba 缓存重建噪声：见常量注释
            continue
        if not ln:
            if blank:
                continue
            blank = True
        else:
            blank = False
        out.append(ln)
    return '\n'.join(out).strip() + '\n'


def count_results(text):
    """各套件的成功/失败标记风格不一：`[PASS]`（verify 系列）与 `[ OK ]`（smoke 系列）。"""
    n_pass = len(re.findall(r'\[PASS\]|\[\s*OK\s*\]', text))
    n_fail = len(re.findall(r'\[FAIL\]', text))
    return n_pass, n_fail


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- 执行
# ---------------------------------------------------------------- 摘要输出
_SUMMARY_BUF = []


def say(text=''):
    """摘要输出专用：**既打印、也进缓冲**。

    ★ 第60轮修复。起因：一次全量回归把 stdout 重定向到 E 盘，56 个套件全部跑完、
      结果表也打了几十行，然后在打印第 N 行时抛
          OSError: [Errno 22] Invalid argument
      —— `main()` 当场退出，**"合计 PASS/FAIL"与【问题】清单一起丢了**，
      只能靠重跑一遍才拿回来（且重跑时 E 盘又正常，属瞬时抖动，无法复现）。

    ⇒ 教训：**结果不能只活在 stdout 上**。stdout 可能落在不稳的介质上
      （本项目既有教训同源："回归套件不许依赖外部盘"）。
      现在摘要同时写进 `_out/summary.txt`（在仓库内、已 gitignore），
      stdout 写失败也不影响取回结果。
    """
    _SUMMARY_BUF.append(str(text))
    try:
        print(text)
    except OSError:
        pass


def run_suite(suite, verbose=False):
    script = suite['script']
    if not os.path.exists(script):
        return {'id': suite['id'], 'status': 'SKIP', 'reason': '脚本不存在', 'exit': None}

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['PYTHONHASHSEED'] = '0'   # 钉死 set 的字符串迭代顺序，避免打印顺序漂移
    if suite.get('offscreen'):
        env['QT_QPA_PLATFORM'] = 'offscreen'
    env.pop('QT_QPA_PLATFORM_OVERRIDE', None)

    cleanup = None
    extra = suite.get('env') or (_make_hermetic_env if suite['id'] in HERMETIC_IDS else None)
    if callable(extra):
        extra_env, cleanup = extra()
        env.update(extra_env)

    try:
        proc = subprocess.run(
            [PYTHON or sys.executable, SEED_RUNNER, str(SEED), script],
            cwd=os.path.dirname(script),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)
    raw = proc.stdout.decode('utf-8', 'replace')
    norm = normalize(raw)
    n_pass, n_fail = count_results(raw)

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    with open(os.path.join(OUT_DIR, suite['id'] + '.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(raw)
    if verbose:
        print(raw)

    return {
        'id': suite['id'],
        'status': 'FAIL' if (proc.returncode != 0 or n_fail) else 'PASS',
        'exit': proc.returncode,
        'pass': n_pass,
        'fail': n_fail,
        'sha256': sha256(norm),
        'norm': norm,
    }


# ---------------------------------------------------------------- 解释器选择
# 套件必须用"装了 PyQt5 且能 import bs4"的解释器跑：本机 C:\Python311\python.exe
# 满足，而 ~/.workbuddy 下的托管 venv（Python 3.13）看不到 3.11 的用户
# site-packages —— 用它跑会得到 round5_smoke 假 FAIL（No module named 'bs4'）
# 以及一批与本项目无关的输出漂移。优先顺序：
#   环境变量 REGRESS_PYTHON > 已知系统解释器 > 当前解释器
_PY_CANDIDATES = (
    os.environ.get('REGRESS_PYTHON'),
    r'C:\Python311\python.exe',
)
PYTHON = None          # main() 里确定，run_suite 使用


def pick_python():
    tried = []
    for cand in _PY_CANDIDATES:
        if not cand or cand in tried:
            continue
        tried.append(cand)
        if not os.path.exists(cand):
            continue
        try:
            proc = subprocess.run([cand, '-c', 'import PyQt5, bs4'],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except Exception:
            continue
        if proc.returncode == 0:
            return cand, tried
    return sys.executable, tried


def load_baseline():
    if not os.path.exists(BASELINE):
        return None
    with open(BASELINE, encoding='utf-8') as fh:
        return json.load(fh)


def save_baseline(results, merge=True):
    """写基线。默认**合并**：只覆盖 results 里出现的套件，其余保留。

    修复（第十三轮）：原来是无条件整体重写，于是
        run_all.py --only round8_anim --update
    会把 baseline.json 里其余 15 个套件**静默删掉** —— 下次全量跑就全部变成
    "BASELINE"（无从比对），而输出看起来一切正常。基线是整个 H4/H5 改造的
    唯一安全性判据，不能有这种一键抹除的路径。
    """
    data = None
    if merge:
        data = load_baseline()
    if not data or 'suites' not in data:
        data = {
            'version': 1,
            'note': '归一化输出的 SHA-256 快照。改造前后必须逐字节一致；有意变更时用 --update 重建。',
            'suites': {},
        }
    for r in results:
        if r['status'] == 'SKIP':
            continue
        data['suites'][r['id']] = {
            'exit': r['exit'], 'pass': r['pass'], 'fail': r['fail'], 'sha256': r['sha256'],
        }
    data['suites'] = dict(sorted(data['suites'].items()))
    with open(BASELINE, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write('\n')


def write_diff(suite_id, old_norm, new_norm):
    """old_norm 为 None 时表示"基线只存了哈希、没存归一化文本"，此时打印全文。

    ★★ 第75轮血泪教训（**别再被这两个文件骗**）：
      1. 本函数产出的 `_out/<suite>.diff.txt` **只在 DIFF 时被重写**；
         一旦某套件恢复正常（IDENTICAL），**旧的 .diff.txt 会原地留着不删**。
         第75轮我一度"看到 19 个 DIFF"，其中一半是几天前的陈旧文件。
         ⇒ **真判据**永远是「拿当前 `normalize()` 重算 sha256，与 `baseline.json`
           里的 `sha256` 逐条比」，**不是**数 `.diff.txt` 的个数。
      2. `_out/<suite>.baseline.txt` **不是**基线快照的可靠来源 ——
         它可能是**上一次 --update** 时留下的，也可能是某次运行的 raw 副本。
         第75轮实测：`companion_round46.baseline.txt` 用当前 normalize 算出的 sha
         与 `baseline.json` 里的 sha **对不上**（`c6b88edc` vs `c1bb4d72`）。
         ⇒ 要复现基线，只能用 `run_all.py --show-diff <id>` 或**重跑 + 比 sha**。
    """
    path = os.path.join(OUT_DIR, suite_id + '.diff.txt')
    diff = difflib.unified_diff(
        (old_norm or '').splitlines(True), (new_norm or '').splitlines(True),
        fromfile=suite_id + ' (baseline)', tofile=suite_id + ' (now)', n=3,
    )
    text = ''.join(diff)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text or '(归一化文本相同，仅计数/退出码不同)\n')
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true', help='重建基线')
    ap.add_argument('--only', action='append', default=[], help='只跑匹配的套件（子串）')
    ap.add_argument('--list', action='store_true', help='只列套件')
    ap.add_argument('--verbose', action='store_true', help='打印套件原始输出')
    ap.add_argument('--show-diff', metavar='ID', help='打印指定套件的归一化 diff')
    args = ap.parse_args()

    picked = [s for s in SUITES if not args.only or any(k in s['id'] for k in args.only)]

    if args.list:
        for s in SUITES:
            print('%-16s %-4s %s' % (s['id'], 'offscreen' if s.get('offscreen') else 'in-proc', s['desc']))
        return 0

    baseline = load_baseline()

    global PYTHON
    PYTHON, _tried = pick_python()

    if args.show_diff:
        with open(os.path.join(OUT_DIR, args.show_diff + '.txt'), encoding='utf-8') as fh:
            new_norm = normalize(fh.read())
        old = (baseline or {}).get('suites', {}).get(args.show_diff)
        if not old:
            print('基线里没有该套件')
            return 1
        print('\n'.join(difflib.unified_diff(
            [], new_norm.splitlines(True), fromfile='baseline(sha256=%s)' % old['sha256'][:12],
            tofile='now', n=3)))
        return 0

    say('=' * 72)
    say('回归基线（G2）  ROOT = %s' % ROOT)
    say('解释器 = %s' % PYTHON)
    say('=' * 72)

    results = [run_suite(s, verbose=args.verbose) for s in picked]

    say()
    say('%-16s %-6s %-6s %-6s %-8s %s' % ('suite', 'exit', 'PASS', 'FAIL', '比对', '说明'))
    say('-' * 72)
    verdicts, problems = {}, []
    for s, r in zip(picked, results):
        if r['status'] == 'SKIP':
            say('%-16s %-6s %-6s %-6s %-8s %s' % (r['id'], '-', '-', '-', 'SKIP', r.get('reason', '')))
            continue
        old = (baseline or {}).get('suites', {}).get(r['id'])
        if args.update or old is None:
            cmp_txt = 'BASELINE'
        elif old['sha256'] == r['sha256'] and old['exit'] == r['exit'] and old['pass'] == r['pass']:
            cmp_txt = 'IDENTICAL'
        else:
            cmp_txt = 'DIFF'
        verdicts[r['id']] = cmp_txt
        say('%-16s %-6s %-6s %-6s %-8s %s' % (
            r['id'], r['exit'], r['pass'], r['fail'], cmp_txt, s['desc']))
        if cmp_txt == 'DIFF':
            old_norm = None
            if old:
                old_raw = os.path.join(OUT_DIR, r['id'] + '.baseline.txt')
                if os.path.exists(old_raw):
                    with open(old_raw, encoding='utf-8') as fh:
                        old_norm = normalize(fh.read())
            path = write_diff(r['id'], old_norm, r['norm'])
            problems.append('%s: 输出与基线不一致（%s），%s' % (r['id'], '计数/退出码变化' if old_norm else '无基线文本', path))
        if r['status'] == 'FAIL':
            problems.append('%s: 套件自身 FAIL（exit=%s, fail=%d）' % (r['id'], r['exit'], r['fail']))

    if args.update:
        save_baseline(results)
        say()
        say('基线已更新（合并模式）：%s' % BASELINE)
        if args.only:
            say('  注意：本次只重建了 %d 个被 --only 选中的套件，其余套件的基线保持不动。' % len(picked))
        # 留一份原始文本供下次 DIFF 时做行级对比
        for r in results:
            if r['status'] == 'SKIP':
                continue
            with open(os.path.join(OUT_DIR, r['id'] + '.baseline.txt'), 'w',
                      encoding='utf-8', newline='\n') as fh:
                fh.write(r['norm'])

    tot_pass = sum(r.get('pass') or 0 for r in results)
    tot_fail = sum(r.get('fail') or 0 for r in results)
    say()
    say('合计：PASS=%d FAIL=%d  套件=%d' % (tot_pass, tot_fail, len(results)))
    if problems:
        say()
        say('【问题】')
        for p in problems:
            say('  - ' + p)
    elif not args.update and baseline is None:
        say()
        say('提示：本次基线为空，已按现状比对为 BASELINE。请用 --update 固化基线。')

    # ★ 第60轮：摘要落盘（stdout 可能落在不稳的介质上，见 `say()` 注释）
    try:
        if not os.path.isdir(OUT_DIR):
            os.makedirs(OUT_DIR)
        with open(os.path.join(OUT_DIR, 'summary.txt'), 'w',
                  encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(_SUMMARY_BUF).replace('\r\n', '\n') + '\n')
    except OSError:
        pass                      # 摘要落盘失败也不该改变退出码

    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
