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
        'desc': '第八轮：特殊动画只由 AI 触发（来源闸门）+ 播完不打断不移动 + 待机 3 分钟 + 鞠躬锚点',
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
                '+ Qt 跨线程投递（真事件队列：分片按序到达主线程槽、丢弃过期世代、reset 顺序严格）',
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
                '默认关闭 + ★屏幕→房间归一化映射防"目标比房间大被钳死" + 画布无 QTimer）',
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
    #   为什么单独立锁：objects 是**程序化生成的数据**（503 场景 / 2043 条），
    #   IDENTICAL 判据只比判据输出文本，数据本身悄悄变了不会被发现。
    #   本锁**直接把数据当事实断言**，并且独立重算期望值（不信生成器自报）。
    {
        'id': 'objects_round44',
        'script': os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                               'verify_objects44.py'),
        'offscreen': False,
        'desc': '第四十四轮续：场景 objects 补全不许静默漂移 —— '
                'A 结构不变量（每条 object pos=2×int / sprite 指向 objs/ 下'
                '真实文件 / ★无过期的 why_objects_is_empty 假话注释）+ '
                'B 真值锚点两种载体各一（ch1:2 krismro 独立文件 = doorA(155,230)'
                '+markerB(155,185)；ch1:3 krishallway 分片 = doorB/markerA/'
                'doorC/markerD，内容与原作普查逐条相等）+ C 覆盖与守恒'
                '（532 个场景 / ★2043 条 == 普查×objmap×objs 三源独立重算）'
                '+ D 负控制（编造 sprite 名必须判缺 / 普查缺席房间 objects==[] '
                '且键存在）',
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
]

# ---------------------------------------------------------------- 归一化
_TS = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?')
_ADDR = re.compile(r'0x[0-9a-fA-F]{6,}')
_DUR = re.compile(r'(?:耗时[:：]?\s*)?\d+(?:\.\d+)?\s*(?:秒|s\b|ms\b)')
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
_ENV_NOISE = re.compile(r'^\[日志\]\s*文件日志初始化失败')


def normalize(text):
    """把"每次运行都不一样"的东西抹平，只留下语义内容。"""
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    # 绝对路径统一成 <ROOT>/...
    for variant in {ROOT, ROOT.replace('\\', '/'), ROOT.replace('/', '\\')}:
        t = t.replace(variant, '<ROOT>')
    t = _TMPDIR.sub('<TMP>', t)
    t = _JIEBA_COST.sub('Loading model cost <COST> seconds.', t)
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
    """old_norm 为 None 时表示"基线只存了哈希、没存归一化文本"，此时打印全文。"""
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

    print('=' * 72)
    print('回归基线（G2）  ROOT = %s' % ROOT)
    print('解释器 = %s' % PYTHON)
    print('=' * 72)

    results = [run_suite(s, verbose=args.verbose) for s in picked]

    print()
    print('%-16s %-6s %-6s %-6s %-8s %s' % ('suite', 'exit', 'PASS', 'FAIL', '比对', '说明'))
    print('-' * 72)
    verdicts, problems = {}, []
    for s, r in zip(picked, results):
        if r['status'] == 'SKIP':
            print('%-16s %-6s %-6s %-6s %-8s %s' % (r['id'], '-', '-', '-', 'SKIP', r.get('reason', '')))
            continue
        old = (baseline or {}).get('suites', {}).get(r['id'])
        if args.update or old is None:
            cmp_txt = 'BASELINE'
        elif old['sha256'] == r['sha256'] and old['exit'] == r['exit'] and old['pass'] == r['pass']:
            cmp_txt = 'IDENTICAL'
        else:
            cmp_txt = 'DIFF'
        verdicts[r['id']] = cmp_txt
        print('%-16s %-6s %-6s %-6s %-8s %s' % (
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
        print()
        print('基线已更新（合并模式）：%s' % BASELINE)
        if args.only:
            print('  注意：本次只重建了 %d 个被 --only 选中的套件，其余套件的基线保持不动。' % len(picked))
        # 留一份原始文本供下次 DIFF 时做行级对比
        for r in results:
            if r['status'] == 'SKIP':
                continue
            with open(os.path.join(OUT_DIR, r['id'] + '.baseline.txt'), 'w',
                      encoding='utf-8', newline='\n') as fh:
                fh.write(r['norm'])

    tot_pass = sum(r.get('pass') or 0 for r in results)
    tot_fail = sum(r.get('fail') or 0 for r in results)
    print()
    print('合计：PASS=%d FAIL=%d  套件=%d' % (tot_pass, tot_fail, len(results)))
    if problems:
        print()
        print('【问题】')
        for p in problems:
            print('  - ' + p)
        return 1
    if not args.update and baseline is None:
        print()
        print('提示：本次基线为空，已按现状比对为 BASELINE。请用 --update 固化基线。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
