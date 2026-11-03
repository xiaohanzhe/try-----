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

    ★★ 第89轮补第二根因（真实症状：5 个套件持续"输出与基线不一致"，PASS/FAIL 全 0）：
      上面那句"从旧版继承必然发生"**只在仓库里真的存在可继承的 `ralsei_pet/memory.json`
      时成立**。而那个文件是**上游提交进来的**（`git ls-files` 有它、无 .gitignore 覆盖、
      最后一次改动在 `d6df565`）。于是同一份代码的这行日志**随一个 git 跟踪文件的有无而变**：
        · 文件在 → `load_memory()` 走"从旧版继承"分支；
        · 文件没了（被清理 / 在干净 clone 里还没生成）→ 两行都不打。
      ⇒ 基线仍不封闭，只是把变量从"E 盘在不在线"换成了"仓库里那份 legacy 文件在不在"。
      修法：**显式架空 legacy 文件指针**（`RALSEI_LEGACY_MEMORY` 指向隔离目录里一个
      不存在的路径），让"新位置无记忆 ⇒ 也无旧版可继承"成为**唯一确定**的终态，
      与仓库里有没有那个文件、E 盘在不在线都无关。
      ⚠️ 代价（写清楚）：归一化后**"legacy 继承功能整个坏掉"也看不见**了。
         真正守它的是 `s3_alias_legacy` 那条**离线**断言链（它自己构造 legacy 文件再断言
         读得到），不依赖这行 stdout。
    """
    base = tempfile.mkdtemp(prefix='ralsei_g2_iso_')
    return {
        'RALSEI_MEMORY_DIR': os.path.join(base, 'RalseiMemory'),
        # 指向隔离目录内一个**不存在**的文件：legacy 继承分支必不触发 ⇒ 输出确定。
        'RALSEI_LEGACY_MEMORY': os.path.join(base, 'no_such_legacy_memory.json'),
        # ★★ 第89轮补第三根因：`RALSEI_MEMORY_DIR` 只钉住了"设备目录"，但
        #   `migrate_from_fallback()` 读的是**桌面兜底目录** `<桌面>\memory` ——
        #   那是个**宿主真实目录**（`C:\Users\<u>\Desktop\memory`），本机曾经
        #   真跑过产品 ⇒ 里面残留过 `memory.json` ⇒ 隔离区首启会打印
        #     「记忆已从桌面搬入设备目录: {'moved': True, ...}」
        #   而干净机器上这行**根本不出现** ⇒ 该行是环境噪声、不是被测行为。
        #   （实测：本机 `Desktop\memory\` 里有上次跑留下的 `_wtest.txt`。）
        #   修法：连兜底目录一起指进隔离区 ⇒ "桌面无记忆"成为确定终态。
        'RALSEI_DESKTOP': base,
    }, base


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
    # ★ 第89轮补（基线不封闭的实证）：`round8_anim` 也会 `RalseiPet()`，
    #   于是 `memory_system` 真去解析存储位置 ⇒ 输出随"E 盘在不在线 / 有没有
    #   可继承的 memory.json"漂移。本注释上方第 56 行**早就写了它会 RalseiPet()**，
    #   但名单里一直漏了它 —— 症状是 `round8_anim` 长期以"假 DIFF"混在问题清单里
    #   （这行"新位置无记忆，已从旧版继承"在有/无可继承文件时打印与否不同）。
    'round8_anim',
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
    # ★★ 第93轮补（**由被测脚本自证**，不是我的推断）：`check89.py` 的 docstring
    #   第 48 行自己就写着「需要真机 `RalseiPet()`（相机要 `follow` 过才出计划）
    #   ⇒ 进 `HERMETIC_IDS`」—— 第89轮只把它注册进 SUITES，**漏了这条**。
    #   实证后果（第93轮全量 G2 抓到）：`check89` 的基线**永不收敛** ——
    #   它读的是**真实** `E:\RalseiMemory\npc_life.json`，而 NPC 自主移动会往里写，
    #   于是每次跑「驻留 N 人」与「谁自己挪到了哪个房间」都不同（`30→34` 人、
    #   换了一批 NPC）。这正是本名单要消灭的"基线不封闭"。
    #   ★ 注意 `check88` **不需要**：它零依赖、不起真机（无 `RalseiPet()`）。
    'check89',
    # ★★ 第99轮：`check99.py` **真机 `RalseiPet()` ×3**（"惊讶三部曲"与"睡眠两拍"
    #   都在**真 App** 上驱动）⇒ 与 `check89` 同款风险：构造期就把真实保管库定下来
    #   ⇒ ① 基线不封闭（`E:\RalseiMemory\npc_life.json` 随 NPC 自主移动漂移、
    #   E 盘掉线即假 DIFF）；② 每跑一次就往用户**真实**保管库写。
    #   ★ 对照：`check97` / `check98` **不需要** —— 实测两者 `RalseiPet()` 出现 **0** 次
    #     （全用桩对象），所以它们留在名单外是对的。
    'check99',
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
        'desc': '第六轮：41 项行为修复断言（对话/甩飞/抛物线/帧率/多屏）。★ 第136轮把 B7 的靶子从'
                '「只取第一句」换成「显示一次 + 未超上限不硬切」，并新增 B7b 独立守长度上限 ——'
                '改口径的原因（原目的已由 40 字上限保证、只取第一句会砍掉"追问"）写在 B7 上方注释里，'
                '取证 `第136轮-截断单一真源/_evidence/diag136c.txt`',
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
                '+ ★近似档适用范围没扩大（新增场景只许 none/真背景/烘图档 E1，'
                'E1b 负控制证明白名单不是"列什么就过什么"；'
                '锚点标注逐条等于第 37 轮实际产出 E3/E4；'
                '★第120轮 E5/E6：烘图档 `room.bake120.*` 必须有图·在盘·是 PNG，'
                '正/负控制成对）'
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
                '序（0 例外，213 个多出口场景；★B2b 负控制：旧写法必复现错乱，'
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
                '★第105轮改口径：A 数据（别名表 schema/★零命中词条=0 / 原作**分章数逐章'
                '等值**（五章 782 + 第105轮并入的 oneshot 420）/ 邻接表守恒 / 2,166 场景索引）'
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
    #   ★★ 第120轮：背景覆盖 235 → 836（+ OneShot 263 + ut 338），**逐章钉死**
    #     并禁止出现未登记的章（两段相减会让"ch1 掉1、ch5 补1"抵掉）。
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
                '背景覆盖**逐章**钉住（Deltarune 235 + OneShot 263 + ut 338 = 836，'
                '不许"这边掉1那边补1"）+ '
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
                'C 对账（第71轮 manifest + **后续轮次登记清单** == 磁盘 · **无孤儿**：磁盘上多出的文件须指向后续轮次清单，靠读 `_source100.json` 而非写死数字 · landed 键集 == need 键集） / '
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
                'E 契约与工具在位 / F 判据自身体检（字段集同构 · bg 键齐 · ★第120轮起 '
                '`bg` **两路都不许撒谎**：`bg_source="none"` 的必须留空（20 间）、'
                '`room.bake120.ut` 的必须有真图（338 间）、第三种来源一律报红 · '
                '记账口非 no-op）',
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
    # ---------------------------------------------------------------- check82
    # 第八十二轮 R5：**Z 键附身**（原作功能 + 特效）。
    # 用户口径（逐字）：「交互键用Z（对 kris 和 firsk，niko 用可以在征求他们同意的情况下
    #   附身（特效用原作的），也就是达到原作操控的功能）」。
    # ★★ 原作依据（第82轮 UTMT 反取证）：Z ⇄ `control_check_pressed(0)` → `event_user(0)`；
    #   主角移动 = `obj_time.*` × **3 px/帧**；灵魂移动 = **同一组** `obj_time.*` × `global.sp`
    #   ⇒ "附身" = **换方向键的消费方**，不是新物理。证据在
    #   `code-quality-audit/第82轮-灵魂附身R5/_evidence/`（19 段真 GML）。
    # ★ 零网络 / 零 UI / 零外部盘（E 段读仓库内证据文件，缺了才假红）；不需要显示器。
    {
        'id': 'check82',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第82轮-灵魂附身R5', '_tools', 'check82.py'),
        'offscreen': True,
        'desc': '第八十二轮：Z 键附身（原作功能 + 特效）—— '
                'A ★★ 零依赖纪律（`possession.py` 顶层 import ⊆ {logging, math} · '
                '零函数内 import · 不 import 项目内模块） / '
                'B ★★★ 附身类别表 = 单一真源（kris/ut_frisk 可直接 · os_niko 需同意 · '
                '其余一律不可 · ★与 `_registry.json` 对账 · build_targets 恰 3 个） / '
                'C ★★★ 行为真跑（直接附身 · 征求同意三态 · 拒绝不静默放行 · '
                '★方向键一帧 **3 px** · ★回头 **2 px** · 未附身不驱动 · 跨场景拒 · dt 钳制） / '
                'D ★★ 产品接线（Z 键分支 · 方向键**附身优先** · release 对称 · 失焦放开 · '
                '★启动顺序 init_npc_systems→init_possession · `_possession_tick` 在早退分支前） / '
                'E ★★★ 原作对照（读 `_evidence/*.gml` 真文件 · ★3 px / 2 px 原文钉住 · '
                '`control_check_pressed(0)` / `snd_squeak` / `control_clear(2)` 在场） / '
                'F 判据自身体检（★ 标记打印点 · 记账鉴别力探针 · 被测文件在盘）',
    },
    # ---------------------------------------------------------------- check83
    # 第八十三轮 R6：**G 键带灵魂走**。
    # 用户口径（逐字）：「R6 可请求角色带灵魂走」；本轮两条裁定：「**新增 G 键**」
    #   ＋「**完全照原作（直接置位）**」。
    # ★★ 原作依据（第46轮取证）：跟随 = **主角轨迹延迟采样** ——
    #   `obj_caterpillarchara` 的 `remx[]/remy[]/facing[]` **长度 25** 环缓冲 +
    #   `target = 12 + (slot * 12)` 落后帧数；`parent = obj_mainchara`。
    # ⚠️ **方向与原作相反**（原作主角带路、队友跟随；R6 是角色带路、灵魂跟随），
    #   且原作**没有"灵魂"这个可被带领的实体** ⇒ R6 整体是**本项目扩展**，
    #   `escort.py` 模块头必须显式标注（E5 守这条，E6 负控制挡冒充句式）。
    # ★ 零网络 / 零 UI / 零外部盘（E 段读仓库内 46 轮证据文件，缺了才假红）；不需要显示器。
    {
        'id': 'check83',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第83轮-带灵魂走R6', '_tools', 'check83.py'),
        'offscreen': True,
        'desc': '第八十三轮：G 键带灵魂走（原作毛毛虫延迟采样 / 本项目扩展方向）—— '
                'A ★★ 零依赖纪律（`escort.py` 顶层 import ⊆ {logging, math} · '
                '零函数内 import · 不 import 项目内模块） / '
                'B ★ 原作照抄值（TRACE_LEN **25** · FOLLOW_LAG **12** · FRAME_HZ 30，'
                '★滞后取的是同一张原作表的第一档） / '
                'C ★★★ 行为真跑（直接置位 ⇒ LEADING · 征求同意三态 · 拒绝不静默放行 · '
                '★灵魂跳到"12 帧前"那一点 · ★未带路 ⇒ step 返回 None · 历史不足 ⇒ None 不飞屏 · '
                'stop 幂等 · 二次 request 后者胜 · nan/非法 id 不猜） / '
                'D ★★ 采样下标自证（lag=12 ⇒ trace[-13] · lag=1 ⇒ trace[-2] · '
                'lag=0/999 ⇒ None · 环缓冲封顶） / '
                'E ★★ 原作对照（读 46 轮取证真文件 · parent/滞后公式/25 帧原文钉住 · '
                '★ escort.py 显式标注"方向相反 + 原作没有" · ★负控制挡冒充句式） / '
                'F ★★ 产品接线（顶层 import · G 键分支与 Z **两条独立分支** · '
                '`_escort_tick` 在 `update_movement` 早退分支前 · ★R5/R6 **成对互斥** · '
                '★同意表复用（不另建第二张表） · ★位置源诚实登记 `wired=False` · '
                '★逆映射 `_room_point_to_screen` 在位 + 负控制挡不存在的 API） / '
                'G ★ 既有按键零回归（Key_G 唯一 · S/E/Z 全在 · 全局热键无裸 G） / '
                'H 判据自身体检（★ 标记打印点 · 记账守恒 + 漏记负控制 · 被测文件在盘）',
    },

    # ---------------------------------------------------------------- check84
    # 第八十四轮：① **所有人附身都要经过同意**（推翻第76轮"kris/frisk 直接附"）
    #             ② 附身效果照原作（补 `control_clear(2)`）
    #             ③ **原作该有的互动技能**取证（Deltarune ch1 反编译）
    # ★★ 原作依据（**本轮新取证**）：UTMT 反编译 `chapter1_windows/data.win`
    #   （14,658,588 B）⇒ 97 objects / 274 codes / 131 scripts，`gml_ok=True`。
    #   交互入口 = `scr_interact()`：`myinteract = 1; event_user(0);`；
    #   被交互者 = `obj_interactablesolid`（三态 `myinteract` + `global.interact` 闸）；
    #   附身清键 = `obj_mainchara_Other_12` 的 `control_clear(2)`；
    #   跟随队伍（R6 原作出处）= `obj_caterpillarchara` 25 格轨迹 +
    #   `scr_makecaterpillar` 的 `target = 12 + (arg3 * 12)`。
    # ★ 零网络 / 零 UI / **零外部盘**（产物已蒸馏进仓库 `_evidence/`，含三份原始 json）；
    #   不需要显示器。
    {
        'id': 'check84',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第84轮-原作互动技能取证', '_tools', 'check84.py'),
        'offscreen': True,
        'desc': '第八十四轮：附身全体先征同意 + 原作互动技能取证 —— '
                'A ★★ 取证产物在盘且真非空（三份原始 json 已进仓库 + 五份 evidence · '
                '★`gml_ok` 锚点：含 `if (`/`global.` ⇒ 真 GML 非字节码 · 负控制无 `pushi.e`） / '
                'B ★★★ 第1条口径：`POSSESSION_KINDS` **无 KIND_DIRECT 成员**（全体先问）· '
                '表非空 · 与 `_registry.json` 对账 · 真表行为 ⇒ ASKING · '
                '★负控制（假表必须能报红 + 显式 DIRECT 直接 POSSESSED 证明非恒 ASKING） / '
                'C ★★★ 第2条口径：附身效果照原作（`snd_squeak` + 灵魂收起 + '
                '★`control_clear(2)` **AST 真调用**，不吃注释） / '
                'D ★★★ 第3条口径：互动机制照抄锚点（回证词原文逐字：`myinteract` 三态 · '
                '`event_user(0)` · 四段射线 · `event_user(9)` 门 · 三态回收 + 5 帧缓冲 · '
                '★毛毛虫 25 格 / `12 + arg3*12`） / '
                'E ★★ 原作速度表（光 3 / 暗 4 / 跑三段加速）从真 GML 抽出并与本项目常量对账 · '
                '★如实登记"暗世界 4 / 跑动尚未实现" / '
                'F ★★ 诚实登记本轮未做的 I1~I10 互动技能 / '
                'G 判据自身体检（★标记打印点 · ★记账负控制用"手工模拟+撤回"而非造假 FAIL）',
    },
    # ---------------------------------------------------------------- check85
    # 第八十五轮：① **I1 Shift 跑**（三段加速）② **I2 暗世界基准移速 4**
    #             ③ **I4 `global.interact` 全局闸** ④ **I5 `onebuffer` 输入缓冲 5 帧**
    #             ⑤ **I10 剧情标记"只记录不销毁"**（★用户口径「别毁」）
    # ★★★ 原作依据（**本轮新取证**）：UTMT 反编译 Deltarune ch1
    #   `chapter1_windows/data.win`（14,658,588 B）⇒ 70 codes / 258 globals；
    #   `obj_mainchara_Create_0`：`bwspeed = 3; if (darkmode == 1) { bwspeed = 4; }`；
    #   `obj_mainchara_Step_0`：`if (run == 1)` 三段（光 +1/+2/+3 暗 +2/+4/+5
    #     ⇒ 4/5/6 与 6/8/9，★两处刻意的不等差 +2/+5 **不许规范化**）；
    #   `obj_mainchara_Step_0`：`if (global.interact == 0) { …整段移动… }`；
    #   `obj_interactablesolid_Step_0`：`… onebuffer = 5;`（投给主角）；
    #   `obj_npc_susiedark_Create_0`：`if (global.plot >= 30) { instance_destroy(); }`
    #     ⇒ 那是**出场门控**（不是删存档）⇒ 本项目**只打标记、零销毁**。
    # ★ 零网络 / 零 UI / **零外部盘**（产物已蒸馏进仓库 `_evidence/`）；不需要显示器。
    {
        'id': 'check85',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第85轮-原作用键与移速表取证', '_tools', 'check85.py'),
        'offscreen': True,
        'desc': '第八十五轮：Shift 跑 + 暗世界移速 + 互动闸/缓冲 + 剧情标记 —— '
                'A ★★ 取证产物在盘且真非空（三份 json + anchors.md · '
                '★`gml_ok` 锚点：含 `if (`/`global.` ⇒ 真 GML · 负控制无 `pushi.e`） / '
                'B ★★★ I1/I2 八格速度表逐格验（用真量级帧数 0/10/11/60/61，'
                '★含两处刻意的不等差 +2/+5） / '
                'C ★★★ 跑表 `advance_run_timer` 三条归零条件 + 行为级（跑 90 帧 > 走 90 帧） / '
                'D ★★★ I4 闸非 0 ⇒ `drive()` 整帧零位移（行为判据） / '
                'E ★★★ I5 `onebuffer=5` ⇒ 缓冲期内 `accept_confirm()` False、5 帧后 True / '
                'F ★★★ I10 `plot_mark` 只记录不销毁（AST 调用名 + AST 剥字符串后的代码层双查，'
                '★含"危险串只在 docstring 里"的负控制 —— 判据不许误报如实标注） / '
                'G ★★ 接线：`main.py` 的 Shift 跑键 / I4 闸 / I5 缓冲 / I10 标记**都真接了** / '
                'H 判据自身体检（★标记打印点 · 记账守恒 + 漏记负控制 · 被测文件在盘）',
    },
    # ---------------------------------------------------------------- check86
    # 第八十六轮：**主线 NPC 自主开口**（B6 收口）——
    #   ① 主线（装了人设、可走 7B 的那批）**也能**自发开口，走**同一条**
    #      `npc_speak` 路径（不另起炉灶）；
    #   ② 开口前能拿到「**此刻这里还有谁**」（在场者感知）⇒ 模型自己决定说还是不说；
    #   ③ 被切走的一方接着反应（`meet` 双向记账）；
    #   ④ 失败**必解锁**（`abort`）＋ 连续失败上限（反活锁）——
    #      否则主线走 7B 一报错就永久 `busy`，整个生活循环卡死；
    #   ⑤ 让路闸**注入到同一个 loop** ⇒ 一处拦、两支生效
    #      （「同一份规则两处算」最贵的坑）。
    # ★ 用户口径：「只要不是在剧情里死了的npc就可以出现」（承接第85轮 I10）。
    # ★ 判据纪律（本轮实测）：**禁止词本身出现在声明里 ≠ 泄露** ——
    #   产物尾巴里「是哪个版本，你并不知道」含"版本"二字，那是**禁止词本身**
    #   ⇒ 判"零作品名前缀"，不扫汉字（老账 §60.3「判据过窄 = 会误报」）。
    # ★ 零网络 / 零 UI / **零外部盘**；不需要显示器。
    {
        'id': 'check86',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第86轮-主线NPC自主开口', '_tools', 'check86.py'),
        'offscreen': True,
        'desc': '第八十六轮：主线 NPC 自主开口（B6 收口）—— '
                'A ★★ `npc_life.presence_hint()/where_of()` 在盘 + **零依赖**'
                '（顶层 import ⊆ 白名单 · 零函数内 import · 不 import 项目内模块） / '
                'B ★★★ `where_of()` 纯函数行为（same/near/left/right/None，用真量级位移） / '
                'C ★★★ `presence_hint()` 行为：剔自己/去重/空⇒空串/缺位置不编方位 · '
                '★**零作品名泄露**（负控制：把 `ut_papyrus` 直传必须被抓 · 走显示名路径零前缀） / '
                'D ★★★ 主线开口走**同一条** `npc_speak`（反证：方法体内零自建网络/模型调用） / '
                'E ★★★ 失败必解锁（`abort`）+ 反活锁（`MAX_CONSECUTIVE_FAILURES`，'
                '行为级：busy 置位/解除） / '
                'F ★★★ 让路闸**注入到 loop**（一处拦两处生效 · 行为级：闸关恒 None / 闸开能开口） / '
                'G ★★★ 接线（AST）：`_npc_life_tick`→`_npc_life_speak_main`→`_npc_main_ids`；'
                '`_npc_life_blocks`→`presence_hint`→`_npc_display_label`；`life=` 真进 `build_system_prompt` / '
                'H ★★ 主线限流 `NPC_MAIN_TALK_GAP` 与纯 NPC 的 gap 分开 / '
                'I 判据自身体检（★标记打印点 · 记账守恒 + 漏记负控制 · 被测文件在盘）',
    },
    # ---------------------------------------------------------------- check87
    # 第八十七轮：**每人一个家**（跨作品 NPC 的静态归属地 + 家字段接线）。
    #   用户口径（逐字）：「迁入场景后再找对应的，然后npc就按原作的分布规律来就好，
    #   oneshot那个就放在他游戏最后那个光门后面…」+「先落「家」的数据面（推荐）」+
    #   「标 authored，按原作分布规律安家（推荐）」+「立刻参与（推荐）」。
    #   ① `_placement.json` 新增**独立 `home` 列**（与 `scene`＝当前站位**语义不同**）；
    #   ② 补 50 条家（UT 14 / 黄魂 15 / OneShot 21；original 16 / derived 11 / authored 23）；
    #   ③ ★★ 自主移动候选池**收窄** —— 跨作品 NPC `scene` 为 `None` ⇒ 不进
    #      `npc_roam.step(roster=)`（否则一群"不在这个世界"的人会去 Deltarune 房间里
    #      游荡，而且**完全不报错**）；
    #   ④ ★★★ **修一个从第79轮就存在的真 bug**：`npc_roam._call()` 以
    #      `fn(npc_id, 默认值)`（**两个位置参数**）调用取值器，而 `main.py` 注入的
    #      `_npc_roam_traits/_familiar/_friends` 只收一个参数、两个 lambda 同样单参
    #      ⇒ `TypeError` 被 `_call` 自己的 `except` **静默吞掉** ⇒ 取值恒 `None`
    #      ⇒ **`home_of` 从未生效**（"回家"一直退化成"随便走走"）。
    #   ⑤ 鉴别力体检：6 个变异各被**精确对应**的判据抓住（见 `mutate87.py`）。
    # ★ 判据纪律（本轮实测踩过两次）：**取值器必须给全 且 必须吃两个位置参数** ——
    #   否则 `decide` 抛 `TypeError` 被吞 ⇒ 全员不动 ⇒ 负控制退化恒假判据。
    # ★★ 「函数写对了 ≠ 产品用上了」：B5 专锁"`main.py` 真把 `_npc_roam_roster()`
    #   传给了 `step`"—— 实测把它退回 `book.ids()` 时，其余判据**全都照常 PASS**。
    # ★ 零网络 / 零 UI / **零外部盘**（证据已蒸馏进仓库）；不需要显示器。
    {
        'id': 'check87',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第87轮-每人一个家', '_tools', 'check87.py'),
        'offscreen': True,
        'desc': '第八十七轮：每人一个家（跨作品 NPC 静态归属地）—— '
                'A ★★ 家的数据面（50 条 · 三级来源 · 逐条证据 · 与仓库内家表**交叉核验** · '
                '未登记者回落 `scene` · 无家无站位返 None 的负控制 · 跨作品 `scene=None` 不冒充站位） / '
                'B ★★★ 自主移动隔离（候选池收窄 · 跨作品零决策 · '
                '★**接线断言**：`main.py` 真把 `_npc_roam_roster()` 传给 `step` · '
                '成对负控制：未过滤池下真被派出去 46 人且真落场景） / '
                'C ★★★ 就寝真消费 `home`（落回自己家 · 不可达不硬落的负控制） / '
                'D ★★★ **`_call` 两参约定防回归锁**（AST：5 个注入取值器都吃两个位置参数 + '
                '行为级 `_call` 拿到非 None + 单参 lambda 返 None 的负控制 + 三个方法形参 >=2） / '
                'E ★★ Outertale 11 人未被硬安家（`_index.json` 无 `outertale` 章 ⇒ 如实挂起） / '
                'F ★★ 数据面自洽（索引登记 · 原作几何可查 · `load_scene` 真加载带房间号 + 负控制） / '
                'G 判据自身体检（被测文件在盘 · 计数守恒）',
    },
    {
        'id': 'check88',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第88轮-NPC交互链', '_tools', 'check88.py'),
        'offscreen': True,
        'desc': '第八十八轮：NPC 交互链（原作「Z → 射线检测 → 触发交互」的等价物）—— '
                'A ★★★ 射线几何**逐值等于**原作 `obj_mainchara_Step_0` 四段式子'
                '（A/B 锚点法：把原作式子独立重算 + 明暗两世界 8 组） / '
                'B ★★ 四段形状差异真在（互不相同 · 上下段"横向窄纵向延伸" · 方形射线负控制） / '
                'C ★★★ 命中按**朝向**选（背对不命中 · 最近优先 · 平手确定性 · '
                '空候选不硬选 · 非法输入分因 · `_box_of` 形状约定 · 逆序矩形归一化） / '
                'D ★★ 转向 I3（`face_actor` 看向主角 + 与 `npc_placement._facing_between` '
                '**逐例等价**（含退化阈值 `(1e-12,0)`）+ 成对负控制） / '
                'E ★★★ 接线断言（8 方法全定义 · `interact_scene_prop` 真调射线 · '
                '★AST 断言 Z 键真分流（if 体交回/else 体交互）+ 正负控制 · '
                '说话复用 `npc_speak` · 展示走 `_npc_say_line` · 转向真写 `body.facing` · '
                '明暗世界与速度表同源） / '
                'F ★★ 旧行为不回归（桌面场景不射线 · 旧降级链保留 · 零依赖 + 函数内零 import） / '
                'G 判据自身体检（射线几何差异真在 · 记账守恒 · 记账器鉴别力）',
    },
    {
        'id': 'check89',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第89轮-桌面与作品场景连通', '_tools', 'check89.py'),
        'offscreen': True,
        'desc': '第八十九轮：**桌面 ↔ 作品场景连通**（用户硬门槛「先能让我看到场景可以切换」）'
                '+ 基础桌宠三处修复 + 「别让他打开 bilbil」—— '
                'A 桌面门数据面（**第109轮起 4 扇 · 字母 A~D**（OneShot/Niko家/UT/Deltarune）· '
                'pos 在房间内 · 贴图在盘尺寸一致） / '
                'B 路由表（4 条 when_scene=desktop · 目标逐条可解析） / '
                'C `_match_tier` 的 **-1 档**（完整 id 命中最强档 · 别名仍工作） / '
                'D 菜单不空（跨章入口**排在头部** · 桌面 ≥4 条） / '
                'E 渲染计划（真机 `plan objs=4` · rect = 贴图×scale · 全在视口内） / '
                'F 推门真切场景（`build_props` 建 4 个门道具 = **第111轮起 3 `DoorProp` '
                '+ 1 `NikoHomeDoorProp`**（彩蛋门）· **按门字母**推 A/D 门 ⇒ `travel_to` 真改 `scene_id`） / '
                'G 旧行为不回归 · '
                'I ★★★ 可见性（`as_window=True` / `lower()` 与 as_window 绑定 / '
                '`_place_scene_layer` 只 move 不 resize · **第107轮起改固定摆主屏原点、'
                '不再四向钳制**（用户口径"不是跟随移动的窗口"）—— 判据全走 AST） / '
                'J ★★★ 不许自作主张开 B站（**全项目代码层零 B站 URL 字面量** · '
                '`suggest_watching_video` 无代开三件套 + 负控制 · 陪看能力未误伤 · '
                '用户明确指令「打开浏览器」仍可用）/ '
                'H 判据自身体检（记账守恒 · 记账器鉴别力）',
    },
    # 第90轮 · `handle_jump` 的**竖直方向坐标系**（屏幕 Y 向下）。
    # ★ 用户口径：「跳跃的抛物线也不对」「跳上去窗口也只有跳没有上去」。
    # 旧写法用的是 Y-up 弹道公式 ⇒ 竖直加速度恒朝屏幕上方（反重力），永远画不出“先上后下”的抛物线。
    # ★★ 本套件的 C 段是“鉴别力自证”：把旧公式**独立重算**一遍，必须过不了 B 段判据。
    # 零网络 / 零 UI / 不需要显示器 / 零外部盘。
    {
        'id': 'check90',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第90轮-基础宠物审查', '_tools', 'check90.py'),
        'offscreen': True,
        'desc': '第九十轮：`handle_jump` 竖直方向坐标系（抛物线）不许静默回退 —— '
                'A ★★ 公式结构（AST 逐式全等：`vy0` 无 +50 魔数 · `y` 的竖直加速度为 **+0.5gt²**· '
                '两条结构层负控制） / '
                'B ★★★ 行为（真调 `RalseiPet.handle_jump`（轻量桩）：同高跳必须是**先上后下**的真弧 · '
                '上跳不许“先往下沉” · 落点精确 == 目标（无末帧硬吸附残量）· '
                '下跳不许越过目标线 · 抬升随跨度单调） / '
                'C ★★★ 鉴别力自证（旧公式**独立重算**必须过不了 B1/B4/B5 + 正控制 C4） / '
                'D ★★ 同文件口径一致（`handle_jump` 与 `handle_fall` 的重力必须同号 · '
                '全文件无第二份真相残留） / '
                'E 判据自身体检（被测文件在盘 · 标记打印点 · 独立计数器守恒 + 漏记负控制）',
    },
    # 第91轮 · **基础宠物状态机**三条缺陷（睡眠动画 / 就寝跨天 / 小憩走路动画名）。
    # ★ 三条全部来自第89轮真机日志 `launch_after_rollback.log` 的硬证据，不是推测：
    #   D1 睡眠播的是 `idle`（用户看到的"站桩"），且 `update_animation` 无 `is_sleeping`
    #      分支会把它覆盖回来；D2 就寝醒来判据缺日期闸（22:58 入睡 ⇒ 5 秒后自己醒）；
    #   D3 `walk_down_sleep` 未登记（真机未命中 15515 次、静默回退 walk_down）。
    # ★★ A5/A6 是"代码拼出的动画名"与"注册表"的**对账**：防止再次出现"名字对不上"。
    # ★★★ D 段是**行为级**：真调 `RalseiPet._bedtime_tick`（轻量桩）跨四种时刻；
    #      E3 是**恒真防护**（该函数吞异常返 False ⇒ 必须证明桩真能走到唤醒分支）。
    # 零网络 / 零 UI / 不需要显示器 / 零外部盘。
    {
        'id': 'check91',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第91轮-基础宠物状态机', '_tools', 'check91.py'),
        'offscreen': True,
        'desc': '第九十一轮：基础宠物状态机三条缺陷 —— '
                'A ★★ 注册表（`sleep` 两帧 · `walk_down_sleep` 存在 · '
                'animations.json 与内置兜底表**两处真源一致** · '
                '`update_animation` 拼出的名字必须在表里 + 负控制） / '
                'B ★★★ `enter_sleep_mode` 必须播 `sleep`（AST + 结构层负控制） / '
                'C ★★★ `update_animation` 必须钉住 `sleep`（AST + 静止分支 idle 覆盖佐证 + 负控制） / '
                'D ★★★ 就寝跨天闸（**行为级**：同日 22:58 不许醒 · 次日 07:00 必须醒 · '
                '次日 00:30/06:59 不许醒 · 小憩睡与缺日期两个负控制 + 旧判据鉴别力自证） / '
                'F ★★ 就寝窗口三态（**行为级**：注入时刻喂 `_bedtime_tick` —— 未到点不睡且不标记 · '
                '窗口内真去睡 · ★窗口已过**不补睡但仍标记当晚** · 窗口内「有事」不标记（负控制）· '
                '窗口末点那一秒仍算窗口内（鉴别力自证）。**第98轮补**：承接 `run_all.py` 的 '
                '`_SLEEP_WINDOW_NOISE` 归一化（check89 原先依赖墙钟 ⇒ 逐字节基线恒假红）所抹掉的语义） / '
                'E 判据自身体检（★ 恒真防护：坏桩必须与好桩可区分 · 记账守恒）',
    },
    # 第92轮 · **宠物"走不动/站桩"**（位移结算）。
    # ★ 真机取证：进程内自省探针（劫持实例 `pet.move`，数每次移动尝试的真实 delta）——
    #   178.3s / **5047 次 `move()` 里 4890 次（91.9%）位移为 0**、平均 **3.9px/s**，
    #   而 `duty(is_moving)=94.9%`（一直在"走"）。用户："**他在这里站桩呢？？？**"
    # ★ 三段成因：D1 取整丢位移且不结转 · D2 近距减速无下限（永远差最后几步）·
    #   D3 速度被 0.2~0.9 的系数压出配置区间（实测 0.91px/帧）。
    # ★★ 修后同尺复测：零位移占比 **0.1%**、平均 **102.3px/s**（共 26 倍）。
    # ★★★ 本套件带**变异测试** `mutate92.py`（11 个变异，含"只改注释必须全绿"的负控制），
    #      证明每条判据"破坏必报红"。
    # 零网络 / 零 UI / 不需要显示器 / 零外部盘。
    {
        'id': 'check92',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第92轮-宠物移动结算', '_tools', 'check92.py'),
        'offscreen': True,
        'desc': '第九十二轮：宠物"走不动/站桩"的位移结算 —— '
                'A ★★★ 位移必须结转小数余量（AST：`int(round(… + _subpixel_x))` 形态 · '
                '余量双边有界 · **结转值必须是取整残差**（不是常量）· 旧/新公式独立重算的'
                '**鉴别力自证**：实测参数下旧式 300 帧走 0px、新式走 109px） / '
                'B ★★ 近距减速必须有两道下限（`max(比例,1.0)` + 情绪因子之后再 `max(…,1.0)` · '
                '旧式在 20/40px 处取整后位移为 0 的负控制 · 拆掉第二道下限仍为 0 的负控制） / '
                'C ★★★ 速度取位必须落在配置区间内（AST：不许再出现 `min/max_speed × 系数` · '
                '**行为级**：真调 `generate_new_move_target`（轻量桩）8 情绪 × 30 次断言 '
                '`min_speed <= speed <= max_speed` + 情绪排序 + 旧系数必然违反的负控制） / '
                'D ★★ 余量归零时机（到达 / 换目标）· 全文件无第二份"取整不结转"的写法 · '
                '`self.speed` 仍不参与跳跃物理（证明提速不污染抛物线那条线） / '
                'E 判据自身体检（★ 恒真防护：正/负重算必须可区分 · 桩真走到产品函数 · 记账守恒）',
    },
    # ---------------------------------------------------------------- 第九十三轮
    # ★★★ 基础宠物功能收口（第90轮审查的未结项在当前代码上的现状复审 + 收口）。
    #     为什么单独立锁：第90轮的基线是 `c251a54`，此后代码**整体回退重来**、第92轮又
    #     改过 `update_movement` ⇒ "那些缺陷现在还在不在"不能靠记忆猜，必须逐条取证
    #     （现状表见 `第93轮-基础宠物功能收口/_tools/audit93.py`）。
    # ★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：DPI 那条走**静态**，
    #   真机动态实测放 `probe_dpi93.py` 当证据（不进 G2）。
    # ★ 判据全部**谓词化**（吃源码字符串），因此可以对同一谓词喂"变异源码"做负控制，
    #   并额外断言"夹具保真"（替换真的发生了）—— 避免"夹具不保真 = 报假问题"。
    {
        'id': 'check93',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第93轮-基础宠物功能收口', '_tools', 'check93.py'),
        'offscreen': True,
        'desc': '第九十三轮：基础宠物功能收口 —— '
                'A P1-4 `init_ui` 首帧落点：不得用无参 `availableGeometry()`（只认主屏），'
                '必须"虚拟桌面矩形 → 判右下角落在**哪块屏** → 取**那块屏的工作区**"'
                '（`pick_corner_screen_work_area`，零 Qt 纯函数）；'
                '★ 行为级直接喂**单屏机器复现不了**的布局（右副屏等高 / 阶梯式 / 左副屏负坐标），'
                '旧语义在这些布局下必然答错（负控制）+ 单屏逐像素恒等（2410,1378）'
                '+ 抹掉原点项的负控制 / '
                'B P1-6 `handle_jump` 落地帧**二次改写**：落地分支必须 clamp→move→return，'
                '函数内只允许 2 处 `move`（删 return / 抽 clamp 两个负控制） / '
                'C P0-2 跳跃竖直物理**行为级**（用 AST 抽出的真实表达式求值：Δy=-300 ⇒ vy0<0 '
                '真起跳 · 落点误差 0 · Δy=-100 ⇒ 先上后下的真弧线 · 旧 Y-up 公式的'
                '落点误差 50 与"先下沉"双负控制） / '
                'D P1-5 DPI 裁定（静态：包内不得出现显式 DPI 声明 —— 实测 Qt5 在 `QApplication`'
                '构造时已设 PER_MONITOR_AWARE；`_virtual_screen_rect()` 仍读 SM_*VIRTUALSCREEN'
                '且保留回退） / '
                'E 判据自身体检（恒真防护 · 记账守恒）',
    },

    # ---------------------------------------------------------------- 第九十四轮
    # ★★★ 基础宠物**真机全功能验收**（用户口径：「主要就是基础模块（基础宠物）修复」）。
    #   为什么单独立锁：第94轮不是静态审查，而是把 `RalseiPet()` + `show()` 的**真启动路径**
    #   跑起来（`_tools/probe94_full.py` / `probe94_sleep.py` / `probe94_drag2.py` /
    #   `probe94_hittest.py`），真机上抓到 3 个真 signal，逐条定根因并修掉
    #   => 「以后再动这几行就会退回去」这件事必须钉住。
    #   ★ 顺带**否定**一条假设（留痕）：窗口透明留白**不会**吞掉桌面点击 ——
    #     最坏情形 `idle` 138x94 下 4 个 alpha==0 采样点全部不命中宠物
    #     （`WS_EX_LAYERED` 走 alpha 逐像素命中）=> 无缺陷可守，故不设锁。
    #   ★ 另一条判为**设计取舍、非缺陷**：拖拽中尺寸变化后**抓取偏移会漂移**，
    #     但角色中心始终精确钉在鼠标上；"保中心"与"保抓取偏移"在尺寸变化时
    #     必然不能同时成立，取用户看得见的那条（角色不跳）。
    # ★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：只读源码 + 解剖执行纯逻辑；
    #   真机动态实测在 `_tools/probe94_*.py`（当证据，不进 G2）。
    # ★ 判据纪律：全部**谓词化**（吃源码字符串）=> 可对同一谓词喂"变异源码"做负控制，
    #   并额外断言"夹具保真"（替换真的发生了）—— 避免"夹具不保真 = 报假问题"。
    {
        'id': 'check94',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第94轮-基础宠物真机全功能验收', '_tools', 'check94.py'),
        'offscreen': True,
        'desc': '第九十四轮：基础宠物真机全功能验收 —— '
                'A `pet_ai` **睡眠守卫**：`_skip_if_critical()` 与 `trigger_action()` 的'
                '关键过程列表里原来漏了 `is_sleeping` => AI 每 3 秒照常挑动作、'
                '`change_animation("idle")` 把 `sleep` 顶掉（真机 t=+6.2s 调用栈实锤）'
                '= 用户口径「睡着了却站着不动」；'
                '★ 行为级（把**真源码**解剖进空类 + 桩 parent，断言睡眠时 `change_animation`'
                '**零调用**、清醒时恰好 1 次）+ 抠掉守卫的翻面负控制 / '
                'B 睡眠**自愈**：`update_animation` 的 `_use_force` 原来只把 `idle` 当'
                '「状态恢复」（`new_animation == "idle"`）=> `sleep` 拿 `force=False` 被跨组冷却'
                '挡住、被顶掉后**回不来**；改为 `new_animation in ("idle", "sleep")`。'
                '★ AST 抽**真实表达式**求值（`(False,sleep)=>True` · `(False,idle)=>True` · '
                '`(False,walk_down)=>False` 有鉴别力）+ 换掉 `"sleep"` 的翻面负控制 + '
                '`_use_force` 唯一赋值且真被 `force=` 消费 / '
                'C 拖拽**锚点同步**：渲染分支按**中心**回算 `setGeometry` => 拖拽期窗口尺寸'
                '一变（`idle` 容器 69x47 => 窗口 138x94）就把「左上角 = 鼠标 - drag_position」'
                '这条唯一不变量破坏掉，下一个 `mouseMoveEvent` 按旧值拽回 => 宠物**先窜后弹**'
                '（实测 44/18px）；修 = 尺寸变化时同步平移 `drag_position`。'
                '★ AST 计数（**两个同构渲染分支都要**：sync 2 处 + setGeometry 2 处）+ '
                '同步必须在 setGeometry **之前** + 对调两段 / 抠掉 `_is_being_dragged` 两条负控制 / '
    },

    # ---------------------------------------------------------------- 第九十五轮
    # ★★★ 基础宠物**运行期排查**（承第94轮"先把基础桌宠修好"这条线）。
    #   ① 把"体积口径"的真判据钉死：速查本 `MEMORY.md` 的注入上限按**原始字符数
    #      （含 CRLF）**判 —— `io.open(..., encoding='utf-8')` 是文本模式，会把
    #      CRLF 静默翻成 LF ⇒ `js_len` 少算「行数」个（实测：文本模式 9,966 / 字节忠实 CRLF **10,045**，差 74 = 行数），
    #      于是文件明明超限、被注入器砍尾（注入文本止于下标 9992），判据却报"余量 +34"。
    #   ② `is_sleeping_walk` 的 `_sleep` 后缀**只允许拼在 `down`**：
    #      素材与注册表都只有 `walk_down_sleep`，而"置真/置假"在 `update_animation`
    #      **下游**，晚于后缀选择 ⇒ 方向刚由 down 变开的那一拍读到陈旧 True，会拼出
    #      `walk_left/right/up_sleep` ⇒ 静默回退 + 一条 `[anim-miss]` 噪声
    #      （真机 recon 实证 20:50:06 / 20:51:47）。
    #   ③ ★★★ 走路朝向的角度分档有**缝隙**：`-30/30/60/120/-60/-120` 这套档位把
    #      `[30,60)`（屏幕坐标 +y 向下 ⇒ 正是"右下"）落进了 `else` ⇒ 判成 `left`
    #      = **朝右下走却播朝左的精灵**。真机 recon 实锤（`_recon/move_log.txt`）：
    #      目标 (1877,1196)、起点 x=594 一路 +x 走出 907px、
    #      `atan2(1113,1283)=40.9°` 落进 [30,60) ⇒ `dir='left'`，
    #      **连续 10.48s / 297 个采样**方向反着（另 6 例单帧边界采样）。
    #      修 = 改回本文件其余四处同款的对称档 `-45/45/135`
    #      （L7057 拖文件跟随 / L7383 / L9373 面向桌面图标 / L10832 拖拽），
    #      该档与 `abs(dx) > abs(dy)` 判定**逐度等价**（A/B 实测：修复前那条链
    #      在 360 个整数度里错 89 个，修复后 0 个）。
    #      ★ 判据纪律：`update_movement` 里有**两条** angle 分档（L7057 / L7247），
    #      只挑一条会"挑中正确的那条"⇒ 修复前也全绿 ⇒ 必须**逐条全检**。
    # ★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：只读源码 + 解剖执行纯逻辑。
    # ★★ 观察量纪律（本轮踩到的第三种"夹具不保真"）：`update_animation` 命中不到时会走
    #    回退链（`walk_right_sleep` → `walk_right` → `idle`）⇒ **最终请求名两个版本可能相同**，
    #    所以必须观察 `note_animation_miss` 的**未命中记账**，而不是最终动画名。
    {
        'id': 'check95',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第95轮-基础宠物运行期排查', '_tools', 'check95.py'),
        'offscreen': True,
        'desc': '第九十五轮：基础宠物运行期排查 —— '
                'A 体积口径（速查本注入上限按**原始字符数（含 CRLF）**判：'
                '`recheck95mem.read()` 走 `newline=\'\'`；文本模式会吞 CRLF ⇒ '
                '第92~94 轮的 9,966 是**假安全**，字节忠实 CRLF 真值 10,045 已超限被砍尾；git 里的 LF blob 只有 9,971） / '
                'B ★★★ 行为级（解剖真源码 `update_animation` + 桩 `sprite_loader`）：'
                '`is_sleeping_walk` 的 `_sleep` 后缀**只允许拼在 `down`** —— '
                '素材/注册表只有 `walk_down_sleep`，方向刚由 down 变开的那一拍读到陈旧 True '
                '⇒ 拼出 `walk_left/right/up_sleep` ⇒ 静默回退 + `[anim-miss]` 噪声'
                '（真机 recon 实证）；★ 观察量必须是「未命中记账」（最终动画名两版相同 '
                '⇒ 只看名字会漏判）+ 生成式负控制（抠掉守卫必须重新报出未命中） / '
                'C 注册表与素材一致（三个方向未登记、磁盘无素材，两条负控制） / '
                'E ★★★ 走路朝向的角度分档（**行为级**：解剖 `update_movement` 的**两条**'
                '分档链）—— 原档 `-30/60/120` 把 `[30,60)`（屏幕坐标 +y 向下 ⇒ 正是'
                '"右下"）落进 `else` ⇒ 判成 `left` = **朝右下走却播朝左的精灵**'
                '（真机 recon：目标 (1877,1196)、x 从 594 一路 +x 走出 907px、'
                '`atan2(1113,1283)=40.9°` ⇒ **连续 10.48s / 297 采样**方向反着）；'
                '修 = 改回同文件其余四处同款的 `-45/45/135`（与 `abs(dx)>abs(dy)` '
                '**逐度等价**，实测消掉 89/360 个错档）+ 360 度逐度比对 + '
                '负控制（换回旧档必须翻面） / '
                'D 判据自身体检（桩保真 · 恒真防护 · 标记点名可复核） / '
                'F ★★★ 桌面图标矩形（第95轮真缺陷：`LVM_GETITEMRECT` 的 `lParam` 是'
                '**传入传出**参数 ⇒ 必须先预置 `LVIR_BOUNDS` 再 SendMessage，'
                '否则 63 个图标只量出 10 个不同位置 ⇒ 宠物被吸进左上角小方块出不来）'
                '—— 常量值 · 预写存在 · 预写先于 Send · 循环内每次重投 · '
                '缓冲区释放成对 + 两条负控制；★ 破坏性验证：回退预写 ⇒ F2/F3 必报红',
    },
    {
        'id': 'check96b',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第96轮b-基础宠物专项复现', '_tools', 'check96b.py'),
        'offscreen': True,
        'desc': '第九十六轮b：基础宠物两处「用户视角可感知」的修复不许静默回退 —— '
                'B ★★★ `react_to_desktop_element` **不许绕过台词唯一入口**直写对话：'
                '原实现在函数里 `dialogue_ui.add_dialogue(...)` + `show_dialogue()`，'
                '而用户 2026-09-19 口径是「所有对话全权交给 AI」'
                '（`speak_event` docstring 逐字："不给内置台词：说不了就不说话，'
                '宁可安静也不甩一句写死的台词"）；真机实证（`probe96b_canned.py`）：'
                '修前 A 段 `add_dialogue` 增量 **2**、`speak_event` 增量 **0**（绕过实锤），'
                '实抓台词「这是文本文件呢！ 纸做的东西要小心处理哦！」；'
                '同次运行负控制 `speak_event(pool=None)` 增量 0（口径没坏）、'
                '正控制 `speak_event(pool=[...])` 增量 2（入口可用）⇒ 修后 A 段增量 **0**。'
                '★ 判据**收窄**（首版过宽 ⇒ 假红）：函数内还有一处 `add_dialogue` 受 '
                '`SHOW_FILE_HELP_HINTS`（默认 False，第51轮定）保护 ⇒ 判据只在**开关外**'
                '生效，并按**行号区间**扣除受保护区（同名调用内外各一次时不许聚合错） / '
                'C ★★★ 拖拽判定必须**位检测**：`event.buttons() == Qt.LeftButton` 是等值比较，'
                '而 Qt 的 `buttons()` 返回**按位或**组合值 ⇒ 拖拽中再按右键（多键鼠标/触控板/'
                '触屏）会掉进 `else`：清 `_is_being_dragged`、删 `_drag_speed`、误触发悬停与'
                '抚摸 ⇒ 用户视角 = **拖到一半突然松脱**；修 = `& Qt.LeftButton`'
                '（单按左键时 `&` 与 `==` 同值 ⇒ 不改变既有行为） / '
                'A 前置锚点（口径串仍在 · 开关确为 False） / '
                'D 判据自身体检（恒真防护用 `re.escape` 拼模式避开**自指**：首版判据描述里'
                '写了该字面量 ⇒ 正则扫到自己 ⇒ 恒红；且"禁某写法"类判据一律**先剥注释/'
                '字符串**再扫，否则注释里引用旧写法就误报 —— 与 95 轮 D1 同坑第二次发作） / '
                '★ 破坏性验证（`mutate96b.py`）：M1 换回 `==` ⇒ C1/C2/C4/D3b 必红 · '
                'M2 开关外加回直写对话 ⇒ B1/B2 必红 · M3 开关改 True ⇒ B0b 必红 · '
                'M4 短路 ⇒ 如实不报红（判据按设计不覆盖该形态，已登记）',
    },
    {
        'id': 'check97',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第97轮-基础宠物排查', '_tools', 'check97.py'),
        'offscreen': True,
        'desc': '第九十七轮：两处「用户视角可感知」的修复不许静默回退 —— '
                'A ★★★ `handle_jump` 的"穿透检查"**不许再把桌面层当障碍**：'
                '`get_all_floors()` 恒含 `desktop_floor`，而 `desktop_floor[\'rect\']` '
                '恒等于**整个虚拟屏幕**（`update_floors`，SM_*VIRTUALSCREEN）；'
                '排除条件原来只有"起点/终点"两个 fid ⇒ **起点与终点都是窗口**时'
                '（站在窗口 A 上跳到更高的窗口 B —— 这正是 `get_jump_destinations` '
                '给出的**真实候选**）桌面层留在循环里、宠物矩形恒在屏幕内 ⇒ '
                '`intersects` 恒为真 ⇒ 起跳**第一帧**就被判"穿透"并 `start_falling()` '
                '**强迫摔下来**（用户原话："那个坠落的触发逻辑不对吧"）；'
                '★ 判据（源码级 A2 + 行为级 A3：复算口径**由产品源码推导**而非硬编码 '
                '+ 可达性 A3b + 恢复式变异负控制 A4，用**真实 FloorManager** 复算） / '
                'B ★★★ `handle_fall` 的晕乎阶段**不许再播 `fall_back_rub`**：'
                '该素材原始语义是「**坐在地上啜泣**」（仓库根 `要求:80` 逐字：'
                '使用条件为"触发轻微悲伤事件、角色处于坐在地上状态、非战斗"）⇒ '
                '拿它当"摔后恢复"把呻吟演成**啜泣揉眼**；用户口径："他站起来不需要'
                '揉眼睛"；修 = 改播 `fall_back`（`animations.json:545-547`，'
                '"地上状态动画"）· 两者都缺时不切动画、绝不回落揉眼素材；'
                '★ 判据（源码级 B1/B1b 剥注释 + 行为级 B2 真跑 '
                '`trigger_splat`+`handle_fall` + 素材缺失负控制 B3） / '
                'C 判据自身体检（★ C1 恒真防护 · C2 AST 数**真实** print 调用 —— '
                '首版 `str.count` 把自身 docstring/断言里的同名子串也数进去 ⇒ 假红 · '
                'C3 被测文件在盘 · ★★ C4 **剥注释链自证**：首版"切文本 + dedent + '
                'ast.parse"在"方法体首条语句是多行 docstring"时抛 `unexpected indent` '
                '⇒ `except` **静默返回原文** ⇒ B1 把**注释里**的名字当代码引用 ⇒ 假红，'
                '**前后栽两次**；改用 `ast.unparse(函数节点)` 一步到位）',
    },
    {
        'id': 'check98',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第98轮-基础宠物排查', '_tools', 'check98.py'),
        'offscreen': True,
        'desc': '第九十八轮：三处「用户视角可感知」的修复不许静默回退 —— '
                'A ★★★ **滑步**（"站着平移"）：`update_animation` 的 `_use_force` 原式 '
                '`is_same_category or new_animation in (\'idle\', \'sleep\')` ⇒ '
                '`idle → walk_right` 属"跨组"且新动画非 idle ⇒ `force=False` ⇒ 被 '
                '`change_animation` 的**跨组冷却 ×2**（0.8×2 = 1.6s）拦下 ⇒ 宠物'
                '**保持站立姿势原地平移**最多 1.6s；修 = 增 `or new_animation'
                '.startswith((\'walk_\', \'run_\'))`（`walk_*`/`run_*` 是**状态**不是动作）；'
                '真机 A/B：修复前 reject 日志 14 条 `REJECT \'walk_*\' (cur=\'idle\') '
                'kw={\'force\': False}` + CSV 持续段 2 段（f116-f118 1.0s / f542-f545 '
                '1.37s），修复后 **0 条 / 0 段**；★ 判据（A2 源码级 + A3 用**产品自己的'
                '表达式**求值 walk→True/laugh→False + A4 真 `change_animation` 桩验证'
                '冷却内 force=False 被拒 / force=True 通过 + A5 证明 `force=True` '
                '**绕过优先级闸** + A6 恢复式变异负控制）—— ★★ 判据防坑：片段'
                '**必须同容器尺寸**才算滑步，`walk_`(38x80)→`idle`(138x94) 的容器'
                '重定心会让窗口左上角必然位移 `(-50,-7)`，**可见宠物并不动** / '
                'B ★★★ **内置对话收口**：`start_fall`/`trigger_splat`/`handle_fall` '
                '的台词不许再直写 `dialogue_ui.add_dialogue`（绕过台词唯一入口 '
                '`speak_event`→`_event_say`），9 处改走 '
                '`speak_event("fall", [...], face, instant=True)`；★ 判据（B1 源码级'
                '**剥注释** + B2 真跑 `start_fall` 桩验证"台词走 speak_event、直写调用数 0" '
                '+ B3 恢复式变异负控制）—— ★★ `start_fall` **原文**里有 2 处 '
                '`dialogue_ui`（**全在注释里**）⇒ 纯文本扫描**假红**（同型坑第四次发作） / '
                'C ★★★ **重力坠落不许被 `idle` 顶掉**：`update_animation` 的 if/elif 链'
                '原本覆盖 is_jumping / is_falling / is_recovering / is_using_item / '
                'is_spellcasting / is_sleeping / is_moving，**唯独漏 `is_gravity_falling`** '
                '⇒ 落到链尾 `else` 算出 `idle`，而 `idle` 在 force 集合里 ⇒ `force=True` '
                '**绕过优先级闸**（`fall`=4 > `idle`=1）⇒ `start_falling` 刚播上的 '
                '`fall`/`fall_mad` 在 ~167ms 内被顶成站姿；用户视角 = "**从窗口上掉下来时'
                '保持站姿往下滑**"（真机 `run_natural_postfix` f228-f234 '
                '`is_gravity_falling=True` 而 `anim=\'idle\'`，y 15→1506 跨 3.5s，'
                '抽帧拼图确认）；修 = 增 `elif self.is_gravity_falling:` 支'
                '**保持当前动画**；★ 判据（C1 链可达 + C2 链上存在该支 + C3 恢复式变异'
                '负控制）—— ★★ C3 锚点两次自我打脸：① 只按分支头替换会改到 '
                '`update_movement` 里那处同名分支（**假绿**），锚点必须带**分支体**；'
                '② 源码是 CRLF 读入，含 `\\n` 的锚点**匹配不到**） / '
                'D 判据自身体检（D1 恒真防护 · D2 AST 数真实 print 调用 · D3 被测文件在盘 · '
                'D4 剥注释链自证（**合成样本**，不依赖产品注释存续） · D5 成功标记字面量'
                '只能是打印模板，防 G2 计数自匹配）',
    },
    {
        'id': 'check99',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第99轮-睡觉惊醒与场景系统', '_tools', 'check99.py'),
        'offscreen': True,
        'desc': '第九十九轮：**睡觉后惊醒**不许静默回退（用户口径「先从睡觉后惊醒做」，'
                '登记项原话是「睡着点醒播**惊吓动画**」）—— '
                '起因是第96b轮登记的"接线前置"：`trigger_surprise()` 当时**零调用**，'
                '而 `is_surprised` 分支把 `jump_height`/`jump_duration` 写死成 20/0.5 且'
                '**永不还原**（先接线就会永久污染之后所有跳跃）＋一次性标志 `surprised_jump` '
                '**永不删除**（惊讶只会跳一次）。本轮落 5 件事：'
                '① 睡眠**第二拍**在 `wake_up()` 之后追加 `trigger_surprise()`（顺序不可倒 —— '
                '`is_sleeping` 分支在 `update_animation` 的 if/elif 链里排在 `is_surprised` '
                '**之前**，第91轮同一坑）；② `trigger_surprise()` **自己**把惊吓落到画面'
                '（只置标志不够：跨组冷却 1.6s 而惊讶只 2.0s，且第54轮契约写明'
                '"表演/情绪动画不由静止分支自动驱动"）；'
                '③ ★★★ **不硬拆第8轮"特殊动画播完为止"契约** —— 第一拍 '
                '`play_animation_once("look_up")` 把 `_play_once_active` 置 True，'
                '那条"特殊→特殊不许打断"的守卫会把 `surprised_down` 一并拦下'
                '（真机实测：两拍都做完了画面仍停在 `look_up`）⇒ 改为把一次性的'
                '**回归目标** `next_animation` 换成惊吓脸，等它播完自然落地'
                '（`look_up` 只有 4 帧）；④ 还原点 `_surprised_saved_jump`（存→还原）；'
                '⑤ `_restore_surprised_jump()` 在"惊讶清除处"与 `reset_special_states` '
                '两处都调用。'
                '★ 判据（A 源码级 AST：A1 显式切 + A1b 排队 + A2 先存后写 + A3 三件事 + '
                'A4/A5 两处调用 + A6/A6b **内层 If** 的语句序列与顺序 + A7a/b/c '
                '恢复式变异负控制（抠掉 / 对调）；'
                'B 行为级真机驱动（B0c **夹具基线必须可与写死值区分** + B1 立刻落画面 + '
                'B2 存还原点 + B3 还原+删标志 + B4 第二次仍会跳 + B5 负控制）；'
                'C 行为级睡着→点两下（C3a 醒了且受惊 + **C3b 惊吓脸真会播到**（驱动真实'
                '一次性动画完成分支）+ C4/C5 两条负控制）；D 判据自身体检）。'
                '★★★ **已知未实现项（A8/A9 两条绊线锁着，别读成"已实现"）**：'
                '`is_surprised` 的"跳一下"块**嵌在 `elif self.is_moving:` 的子树里** '
                '⇒ 站着/睡着的宠物被吓到**只会变脸、不会跳**；且该块**从不置 `is_jumping`** '
                '⇒ 即便可达也只是记账（`jump_count += 1`），`handle_jump` 的抛物线不会跑'
                '（`jump_height` 第96b轮已证是死变量）。'
                '★★ 本轮判据自身栽了两次（都是 `ast.walk` 的锅）：'
                '① `_restore_surprised_jump` 走 `ast.unparse` ⇒ 断言串不能带空格'
                '（实际是 `del self.surprised_jump`，不是 `delattr(self, \'...\')`）；'
                '② `ast.walk` 是 **BFS** ⇒ "第一个含该赋值的 If"是**最外层** '
                '`if self.is_sleeping:`（body 里只有 `return`）⇒ 假红 `after=return`；'
                '定位 `is_surprised` 的 If 时又先命中函数**顶层**的清除块而不是嵌在 '
                '`is_moving` 里的写参块 ⇒ 必须在 `_moving_if` **子树内**找、并用 '
                '`"surprised_down" in unparse(node)` 认准写参块。',
    },
    {
        'id': 'check101',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第101轮-OneShot背景落盘与场景接线', '_tools', 'check101.py'),
        'offscreen': True,
        'desc': '第一百零一轮：OneShot **263 间**背景「合成 → 落盘 → 两层接线 → 渲染出图」。'
                '第100轮只打通管线（只在 `_evidence/` 产了 3 张样例），本轮落进产品：'
                '① 263 张 `assets/scenes/bg/oneshot_map<N>.png`（从原作 `map<N>.tmx` 瓦片 + '
                '`*.tsx` 图集 + `oneshot_map_colors.json` 底色逐像素合成，'
                '**唯一真源** = 第100轮的 `os_bg100.py`，本轮只 import 它）；'
                '② `bg`/`bg_source`/`bg_asset` 写进**两层登记**（`_zone.oneshot.*.json` 与 '
                '`_index.json` 内联副本 —— 侦察实证两者逐字段全等，所以必须两处都改）。'
                '★ 判据四段：A 落盘面（263 在位 / 尺寸 == **独立来源** `_room_geometry.json` '
                '的房间几何 1:1 / 与第100轮样例逐像素相同）；'
                'B 数据面（三字段合法 / 两层一致 / **无重复键** —— 首跑 bad=526 的守点：'
                'OneShot 的 `bg_source` 后面还跟着 `objects` ⇒ 原行**带尾逗号**，'
                '照搬第39轮"只认无逗号"的正则会漏替换并留下**重复键**，'
                '而 Python json 对重复键取最后一个 ⇒ `bg_source` 恒 `none`）；'
                'C **渲染面**（263 个场景逐个真跑 `SR.plan_frame` ⇒ 必须产 `K_BG` 且**盖满视口**，'
                '外加"把 bg 置 None 必改出占位"的负控制 —— **数据接好了 ≠ 画得出来**）；'
                'D 纪律（文件名/溯源与 room_id 自洽 / `bg_source` 只此新档 `tmx.composite` / '
                '单色图画像 13+1 可复查）。'
                '★ 本轮判据栽过两处并已修：① 单色判据（"空房"与 `blank*.tsx` 的**全透明占位**'
                '都忠实，只有"有实心瓦片却画成单色"才是合成空转）；'
                '② 行尾判据（`git show HEAD:` 给的是 autocrlf 归一化后的 LF，与工作区 CRLF 比'
                '**必然报红** ⇒ 改判"diff 规模恰好 == 526×3 增 / 526×2 删"）。'
                '★ 已知保真缺口（不在本锁内）：`events_map<N>.json` 的**可见物件**未画'
                '（7,805 个 / 244 间房 —— 第102轮已把图集整张入库，接线在下一轮）；'
                '`mapColors` 只覆盖 241/263（余 22 张走黑底）。'
                '★★ 归因更正（第102轮实测证伪，**别再把下面这条当缺口**）：'
                '「房间整体偏暗 = 未接 `lightmaps` + `ambient`」**不成立** —— '
                '`lightmaps` 是**加色光罩**（用了只会更亮）、`ambient` 是 RPG Maker 的'
                '**色调命令**（调暗）且全 gamedata 只有 7 次调用 / 6 间房；263 张合成图里'
                '**221 张**是"有实心瓦片却均亮度 < 90" ⇒ 暗来自**原作瓦片/图集本身**'
                '（见 `check102` A 段与 `brightness102.json`）。',
    },
    {
        'id': 'verify_scene_fit99',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第99轮-睡觉惊醒与场景系统', '_tools',
                               'verify_scene_fit99.py'),
        'offscreen': True,
        'desc': '第九十九轮：**场景系统 = 把原作全屏化**（用户口径「那个场景系统就像是'
                '把原作全屏化似的，但不是真的全屏，只是说像」＋第44轮原始设计「场景图与'
                'ralsei 桌宠体积/原作体积**等比放大**，剩下的用**黑色填充**」）。'
                '★ 本轮修掉**两条真缺陷**（都是真机录屏 + 数据普查双证）：'
                '① 背景 PNG 是**屏幕像素分辨率**的截图（房间 320×240 ↔ 素材 640×480）'
                '而旧代码把"素材像素"当"世界逻辑单位"铺在房间原点 ⇒ 素材比房间小时'
                '相机跟到另一侧背景**整条出界**（`card_castle_1f` 真机：plan 只剩一条'
                '**窗口外**的 room_border ⇒ `canvas.grab()` 非透明采样 0 ⇒ 壁纸透出）、'
                '素材不小于房间时被**额外放大 2 倍**（`kris_s_room` 只看到左上 1/4，'
                '原作里整间房恰好一屏）⇒ 新增 `fit_bg_world()`（**等比 cover**，'
                '两轴同倍 ⇒ 仍然禁非等比拉伸）＋ `K_ROOM_FILL` 纯黑房间底色'
                '（**最先画**，桌面场景 `TRANSPARENT_BG` 不产）；'
                '② 我们照抄了原作对象表的 `spr=` 却漏了 `vis=` ⇒ 把 `obj_doorA`/'
                '`obj_markerB`/`obj_readable_room1` 这些**不可见触发器**画了出来'
                '（真机：一屋子品红/白描边框；普查 3206 个带 src 实例里 **2749（85.7%）**'
                '属此类）⇒ 新增 `assets/scenes/_obj_visible.json`（由第43轮 UTMT 转储'
                '生成，只落 hidden 901 条）＋ `is_drawable_object()`/`obj_is_hidden()`'
                '（两份刻意重复的实现，靠 G26 全量对账）—— **只影响绘制**，'
                '不动 `scene.objects`，交互/道具/门控一概不受影响。'
                '★ 判据：A 口径在位（用户原话 + 旧口径的**代码签名**用 AST 验消失）；'
                'B `fit_bg_world` 正负成对（含六组真实量级的"必然盖满"不变量）；'
                'C `plan_frame`（黑底最前 / bg 盖满 / 桌面不透黑 / 缺素材退化）；'
                'D 画布消费 `room_fill`；E ★ **235 个真背景场景全量普查**零例外；'
                'G ★ 隐形触发器过滤（数据面 / 正负成对 / 真链路 9→0 与 ch4 存盘点照画 /'
                '**46 名过滤面 golden** / 两份实现全量一致）；F 接线与纪律。',
    },
    {
        'id': 'check102',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第102轮-光照与ambient接入', '_tools', 'check102.py'),
        'offscreen': True,
        'desc': '第一百零二轮：① **更正**第101轮"未接光照 ⇒ 偏暗"的归因（实测证伪）；'
                '② OneShot 房间**可见物件**普查；③ 物件图集**整张**入库 148 张。'
                '★ 归因为什么被推翻：`content/lightmaps/`(20 张) 是**加色光罩**（配 '
                '`AdditiveShader`，用了只会变亮），灯由**事件脚本**动态挂载 —— '
                '全 `gamedata` 只有 **7 次 `add_light` / 2 次 `del_light`**、分布 **6 间房**'
                '（2/39/180/188/189/203）；`ambient` **不是房间字段**而是 RPG Maker 的'
                '**色调命令**（exe 里有 `ambient -100, -100, -100`）。'
                '真正的形态是：263 张合成图里 **221 张（D 档）「有实心瓦片却均亮度<90」**'
                '⇒ 暗来自**原作瓦片/图集本身**。'
                '★ 真缺口因此换成「**物件没画**」：`events_map<N>.json` 共 **11,371** 事件 / '
                '**244** 间房，其中 **7,805**（68.6%）带 `character_name` = 原作道具/NPC'
                '（**149** 种图集，仓库侧 263 间房的 `objects` **全为空**）；'
                '3,397 是隐形触发器、169 用 `tile_id`（三档互斥、和为 11,371）。'
                '★ 本轮只**入库不切帧**（刻意的范围限制）：`graphic` 只有 7 键、'
                '**没有 `character_index`** ⇒ 148 张里**只有 26 张**是 64×64 单块，'
                '其余 **122 张**是多块图集，"取哪一块"数据里**没有依据**；'
                '现在切帧 = 把错假设固化进产品 ⇒ 栅格 A/B 锚点与接线留到下一轮。'
                '★ 判据四段：'
                'A 光照归因面（调用点 6 间 / 7+2 · API 是脚本方法而非字段 · '
                '263 张亮度**独立复算**（184 张落 0~31 档、均 30.75）· 五档登记一致 · '
                '★ **与第101轮 `bg_manifest101.json` 跨轮对账**（单色空房 13 == B2+C11、'
                '全透明占位 1 == A1 == {63}）· 负控制：提亮 +120 必翻档）；'
                'B 物件普查面（244/189/11371/7805/3397/169/149/380 · 三处计数自洽 · '
                '★★ 坐标锚点用**独立来源** `_room_geometry.json` 复算 0 越界 · '
                '负控制：挪出格必报红）；'
                'C 入库面（148 张 · 名单精确 == 普查 − 缺的 1 张 `npc_BIG` · '
                '★★ 逐张 **sha256** 对账 · 尺寸/总字节 · 负控制：裁 1 行必报红）；'
                'D 纪律（工具在位 · ★★ **零外部依赖**：AST 查本文件无原作绝对路径 '
                '（特征串必须**拼**出来，否则检查器自己扫到自己 ⇒ 恒假判据）· '
                '★★ **无恒真判据**：AST 查本文件所有 `ok(...)` 首参不是字面量 `True`）。'
                '★ 本轮判据自己栽过两次并已修：① `counts.rooms_with_events` 记成 189'
                '（那是"有**可见物件**的房"，真有事件的是 244）⇒ 拆成两个字段；'
                '② `(w,h) > (64,64)` 是**元组字典序**不是"两维都 >64" ⇒ 改显式 `or`。',
    },
    {
        'id': 'check103',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第103轮-物件栅格锚点与接线', '_tools', 'check103.py'),
        'offscreen': True,
        'desc': '第一百零三轮：OneShot 物件「**栅格 + 锚点**」规则定死 + 切帧 + 接线。'
                '第102轮把 **148** 张图集**整张**入库、**刻意不切帧**（`graphic` 无 '
                '`character_index`，"取哪一块"没依据）；本轮把依据**定死**：'
                '① **栅格** `cell = (sheet_w//4, sheet_h//4)`、`col = pattern`、'
                '`row = DIR_ROW[direction]`（`{2:0,4:1,6:2,8:3}` = 下/左/右/上，原点左上）；'
                '② **锚点** `tile_bottom_center`，'
                '`pos = (tile_x*16 + 8 - cw//2, tile_y*16 + 16 - ch)`。'
                '★★ **两轴都由像素定死**（不再只是"RPG Maker 惯例"）：'
                '竖向靠"`DOORS2`(16x32) 落进 `map4` 的门洞（列 21 行 8/9 全黑）"；'
                '横向靠"宽物件（cw>=32）落在**恰好同宽**的黑洞上"（6 候选里「底+居中」'
                '**54:0** 唯一赢）；"黑" = 原作 `black.tsx` 瓦片 = **原作自己给物件留的洞**。'
                '③ **切帧** 380 个 distinct `(sheet,col,row)` → 去掉缺图集的 1 张 '
                '`npc_BIG` → 实切 **379** 格（**2** 个全透明）、0.275 MB。'
                '④ **接线** **7804** 个物件写进 6 个区域分片（**189** 个场景行；其中 '
                '**188** 行非空 —— 第 189 行是房间 96，它唯一那个物件就是缺图集的 '
                '`npc_BIG`）。'
                '★★ **两层登记的偏差是声明过的**：物件只写区域分片，`_index.json` 内联'
                '副本的 `objects` 保持**占位空表**（场景体由 `scene_system.load_scene` 从'
                '「独立文件 > 区域分片」取），并在索引 `meta.objects_source` 写明原因。'
                '★ 判据四段：'
                'A 栅格/锚点面（**从磁盘复算**，不读构建脚本的结论）：格 x4 == 图集尺寸 '
                '(148/148) · 379 格与"按 (col,row) 重裁"**逐像素相同** · '
                '**每个物件的 `pos` 都等于公式**（`cw/ch` 取格 PNG 真尺寸）· '
                '★ **证据等级不得被悄悄降级**（`grid_anchor103.json` 两轴都须 '
                '`proven_by_pixel`，且横向那条由 `anchor_cases103.json` **派生**、'
                '54:0 其余全 0）· 负控制（`tile_x+1` 必须恰好差一个瓦片、且只动 x）；'
                'B 落盘面：379 张在位/无杂项 · 逐张 sha256 · 尺寸 · 总字节 · '
                '全透明**恰好 2** · 负控制（裁 1 列必报红）· "盘上没有多余的格"；'
                'C 数据面：守恒（7804 + 1 == 7805）· **逐房**对第102轮普查独立对账 · '
                'depth/layer 自洽（424/258/7122）+ 场景内 `(depth,tile_y,tile_x)` 非降 · '
                '两层登记偏差**正是声明的那样**（正负成对）；'
                'D 渲染面 + 纪律：整间房 1:1 相机下 `K_OBJ` 条数 == 物件数 · '
                '**渲染 `rect` == 栅格/锚点公式** · 真画布 `paint_on` 零缺素材 · '
                '7804 个 `sprite` 逐个查盘 · **负控制：挪 16px 必须恰好改 16** · '
                '零外部依赖（`ni`+`ko` 拼串）· **无恒真判据**（AST 查 `ok()` 首参）。'
                '★ 本套件**零外部盘依赖**（原作在 C 盘，回归碰不得）⇒ 独立验收由 '
                '`verify103.py` 承担（直接读原作 `events_map*.json` 重算 + 重裁每格，'
                '**不进 G2**）；变异测试 `mutate103.py` 7 个变异全部被对应判据抓到。'
                '★ 已知保真缺口（不在本锁内）：`lightmaps`/特效未接（**接了会变亮**）；'
                '`mapColors` 只覆盖 241/263；轮询/动效帧（`anim`）未接。',
    },
    {
        'id': 'check104',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第104轮-物件材质保真', '_tools', 'check104.py'),
        'offscreen': True,
        'desc': '第一百零四轮：OneShot 物件的**材质**（原作 `opacity` / `blend_type`）'
                '不许漂移。第103轮只接了**几何**（栅格 + 锚点 + 切帧 + 接线），'
                '`opacity`（半透明）与 `blend_type`（加色）还躺在原作 '
                '`events_map<N>.json` 里没人消费；本轮把它们接上：'
                '① **数据面** `graphic.opacity`(0..255) ⇒ 物件 `alpha = opacity/255`'
                '（**只写 != 255 的**，**34** 条）；`graphic.blend_type == 1`（加色）'
                '⇒ `blend = 1`（**389** 条）；并集 **399** 条 / **65** 个场景 / 6 个分片。'
                '`blend_type == 2`（减色）本数据集里**一条都没有** ⇒ 不做、只登记。'
                '② **渲染面** `scene_render.plan_frame` 把 `blend` 透传进绘制指令'
                '（**只在非 0 时写键** ⇒ 没材质的 7,405 条指令**一字不变**）；'
                '`scene_canvas._paint_obj` 在 `blend == 1` 时走 '
                '`QPainter.CompositionMode_Plus` —— '
                '★ 为什么不自己写像素算术：Qt 的 Plus 在**不透明目标**上恰好等于 RMXP 的 '
                '`d = min(255, d + c·a_pixel·opacity)`，且复用 Qt 的合成快路径。'
                '★ 本轮**最有说服力的样本**：`room 101` 的 `blue_silver`'
                '（`src = "invisible silver"`）与 `room 210` 的 `blue_npc_prototype`'
                '（`src = "invisi-proto"`）**opacity 就是 0** —— 原作把传送点画成"隐形"的，'
                '本轮之前被我们一五一十地**画了出来**；'
                '`start_lightmaps` 16 条 `opacity=35/155 且 blend=1` = 原作静态光罩；'
                '`jars_light`(189) / `tv_light`(54) / `portal_rays`(19) 清一色 `blend=1` 发光体。'
                '★ 判据四段：'
                'A 数据面（从 6 个分片**自己数**）：计数（34/389/399/2）· 值域'
                '（`alpha` 必须是 `n/255`，容差 1e-3 + 容差负控制）· 键集合 ⊆ 白名单 · '
                '★★ **正负成对**（`opacity==255 且 blend_type==0` 的 7,405 条必须'
                '**既无 `alpha` 也无 `blend`**）· 与 `_evidence/material104.json` 逐条对账；'
                'B 渲染面（**真 QPainter，离屏逐像素**）：`plan_frame` 原样透传 · '
                '「无材质的指令里**没有** `blend` 键」 · ★★ **加色像素 == RMXP 公式**'
                '（纯红 a=128 叠灰 128：`blend=1` 得 (255,128,128)、`blend=0` 得 '
                '(192,64,64)，差 191 级 ⇒ 判据真在分辨两种合成）· 加色**乘上 opacity** · '
                '★★ **合成模式必须还原**（加色指令之后画的普通物件仍是 SourceOver）· '
                '`alpha == 0` 画了等于没画 · 分层（`CompositionMode_*` 只许出现在 '
                '`scene_canvas`，AST 查 `Attribute` 不吃注释）；'
                'C 全量接线：65 个带材质场景逐个真跑 `plan_frame`（条数 + 逐条透传 + '
                '零缺素材）；D 纪律：工具在位 · 零外部依赖（`ni`+`ko` 拼串）· '
                '**无恒真判据**（AST 查 `ok()` 首参）。'
                '★ 本套件**零外部盘依赖**（原作在 C 盘，回归碰不得）⇒ 独立验收由 '
                '`verify104.py` 承担（直接读原作 `events_map*.json` 从头复算 + '
                '**像素级** A/B：`alpha==0` 整条删掉必须逐像素不变、`blend=1` 改回 0 '
                '必须变亮方向正确；**不进 G2**）；变异测试 `mutate104.py` **8** 个变异'
                '（含 3 个**产品源码**变异：删透传 / 换合成模式 / 不还原合成模式）'
                '全部被对应判据抓到。'
                '★ 已知保真缺口（不在本锁内）：`blend_type=2`（减色，本数据集 0 条）；'
                '`character_hue` / `step_anime` / `move_route`（原作是 MonoGame/.NET，'
                '**无可读脚本** ⇒ 依据不足，只登记不做）；多页**条件页**：'
                '**7** 条事件的 page1+ 会改 `opacity`/`blend_type`（全部由 switch/variable '
                '门控）+ **222** 条可见物件的 **page0 自带条件** ⇒ 本轮固定取 `pages[0]`'
                '（= 原作**初始态**，开局开关全 OFF），接入存档/开关状态前它们才有依据翻页。',
    },
    {
        'id': 'check105',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第105轮-OneShot房间连接', '_tools', 'check105.py'),
        'offscreen': False,
        'desc': '第一百零五轮：OneShot 的**房间连接（传送门）**接进产品，补上'
                '「看得到、走不通」的真缺口。★ 核心口径：OneShot 的房间连接**不是** '
                'Deltarune 那种「门 + 下标位移」，而是原作事件指令 **code 201 = '
                'Transfer Player**。全 **263** 张图实测 **826** 条 code-201 ⇒ '
                '**749**（page0 且该页无条件 = 纯位置门）+ **77**（有条件 / 非 page0 '
                '= 剧情传送，**只登记不生成**）；749 门候选 = **19** 自环（只登记）+ '
                '**0** 未登记 + **730** 跨房 ⇒ 按 `(src_map, dst_map)` 去重成 '
                '**420** 条唯一边（**196** 个源场景）。'
                '★ `original_room_id` 是 map_id ↔ scene_id 的唯一桥（263 个 oneshot '
                '场景**全带**它，749 门候选**两端 100% 已登记**）；'
                '`when_door` = 代表性事件名归一化 slug（重名 `__2`/`__3`），'
                '满足既有硬闸「同场景内唯一 + 字母序 == priority 序」；'
                'priority 走独立段 `PRIO_BASE = 3000`（追加在声明序末尾 ⇒ '
                '「原作生成段无回绕」仍成立）。'
                '★★ **两个消费面同时喂**：① `_routes.json` 语境路由 452 → **872** 条；'
                '② `_room_graph.json` 逐门寻路补上 `chapters.oneshot`（原本只有 '
                'ch1~ch5 = 782 边 ⇒ `plan_route_to` 在 OneShot 里拿不到边 ⇒ '
                '`travel_to` 只能退化成「直达」），现 **1,411** 边'
                '（★第126轮给 outertale 补 209 条后：1,202 → 1,411）。'
                '★ 判据七段：A 证据面自洽（计数 / rid 一致 / 无自环去重）· '
                'B **产品 == 蒸馏证据（对称差恰好为空）** · C **独立重推** when_door / '
                'priority（`label_from_evidence` 与生成器 `slug` **代码分开写**）· '
                'D **既有 452 条逐字节指纹不变**（sha256 锚点 + desktop 仍 9 条）· '
                'E **只登记不生成**（19 自环 / 77 剧情传送）· '
                'F 行为级（真调 `scene_routing.load_routes/match/destinations`）· '
                'G 鉴别力总检（**AST** 查 `ok()` 首参非常量真，禁纯文本扫）。'
                '★ 本套件**零外部盘依赖**（原作在 E 盘，回归碰不得）⇒ 独立验收由 '
                '`verify105.py` 承担（现扫原作 826/749/77/19/420 + 三方对账 + '
                '连通分量 5/212 + 「Start」西门的真值锚点；**不进 G2**，'
                '原作不可达时**报 SKIP 并 exit 3**，不伪装成绿）；'
                '变异测试 `mutate105.py` **9/9** 全部被对应判据抓到。'
                '★ 已知保真缺口（不在本锁内）：77 条剧情传送（**只登记**，等开关/剧情'
                '状态面接入才有依据）；19 条同图自环（原作「出去又回来」，登记不动）。',
    },
    {
        'id': 'check106',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第106轮-非瞬移与全屏化', '_tools', 'check106.py'),
        'offscreen': False,
        'desc': '第一百零六轮：**非瞬移（逐跳走完）** + **场景全屏化（等比放大）**。'
                '★ A 非瞬移：第105轮录屏打出的真缺口 —— `travel_to()` 算出 '
                '`plan["steps"]`（桌面→OneShot S1 实测 **18 跳**）后**只调一次 '
                '`self.switch(sid)`**，`steps` 抄进返回值即无消费方 ⇒'
                '「路径算出来了，但没人走」（与第45轮 `follow_route` 零调用是'
                '**同一类坑的第二形态**）。用户口径「完整的走过去……'
                '如果我对里面任何一个人说马上回桌面，他们顶多是带着我一起**非常快地'
                '按原路线返回**，也不是瞬移」。⇒ 新增 `walk_steps()`（逐跳 `switch()`、'
                '链式校验 `from==当前`、失败停在 `aborted_at` 且 `visited` 保留、'
                '空 steps = 成功 0 跳）+ `walk_route_home()`（**复用** `plan_route_to` '
                '的原路线交给 `walk_steps` 走完 —— 另算新路 = 变相瞬移）；'
                '`travel_to` 的有路线分支改逐跳、直达降级分支**原样保留**。'
                '★★ B 全屏化：用户口径「类似游戏全屏」「占屏比例不美观就适当放大，'
                '**那意味着人物也要等比例放大**」⇒ 新增 `fit_camera_to_screen()`，'
                '**成对**写 `camera.size` 与 `camera.scale`（`scale = out_w/320`）'
                '⇒ `scoped_size()` 恒 **320×240**（可见范围不变、画布铺开）；'
                '背景/物件/**人物与灵魂 walk 同一条 `to_output`**（乘法发生点唯一）'
                '⇒ 人物自动等比放大，**不需要**特判。'
                '★★★ **第107轮口径更正**（用户「**场景是全屏，不是跟随移动的窗口，'
                '是像原作全屏后的效果似的**」＋「**按场景比例铺满、留黑边**」）：'
                '`fit_camera_to_screen` **删掉 `frac` 形参**、改调纯函数 '
                '`scene_camera.fit_fullscreen()`（最大 4:3 内接矩形 + 居中偏移）'
                '⇒ 画布铺满主屏物理尺寸、固定摆主屏原点（**废弃第89轮的"居中+四向钳制"**）；'
                '实测 2560×1600 屏 ⇒ **2133×1600 @ scale 6.666（左右各 214 黑边）**、'
                '800×600 离屏 ⇒ 800×600 @ 2.500（4:3 零黑边）。'
                '（第106轮原口径 `frac` 留边 / 680×510 @ 2.125 **已作废**。）'
                '★ C 清死代码：`main.py` 里 `scene.camera_follow_or_create()`'
                '（全仓无此方法，真走到会 `AttributeError` 被 `except` 吞）已删，'
                '阶梯降级保留。★ D 判据自身体检（AST 查无 `ok(..., True)` 恒真）。'
                '★ 本套件**零外部盘依赖**（回归碰不得 E 盘）。',
    },
    {
        'id': 'check107',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第107轮-全屏化与全局缩放', '_tools', 'check107.py'),
        'offscreen': True,
        'desc': '第一百零七轮：**场景真全屏化** + **全局缩放（宠物/场景/UI 同源）**'
                '不许静默漂移。★ A 全屏化数学：`scene_camera.fit_fullscreen()` '
                '纯函数（**零 Qt、零项目内 import、零函数内 import**）· '
                '`SCENE_ASPECT = 4/3` · 用 `<=` 判限制轴（写 `max` 会**溢出屏幕**= 裁画面）· '
                '返 **4 元组** `(w,h,ox,oy)` · 非法输入返 `None`（≥2 处）· '
                '真跑五例逐值（**2560×1600 ⇒ 2133×1600 左右各 214 黑边**｜'
                '**800×600 ⇒ 零黑边**｜竖屏 1600×2560 ⇒ 上下各 680）· 不变量'
                '（恒在屏内 + 恒 4:3 + 居中）。★ B 相机：`fit_camera_to_screen` '
                '**无 `frac` 形参**（第107轮口径「不再留边、要真全屏」⇒ 第106轮旧口径作废）· '
                '真调 `fit_fullscreen` · **成对** `set_size`+`set_scale` · '
                'AST 求值 `scoped == 320×240`（可见范围不变 = 不是镜头拉近）· '
                '`scale = out_w / scoped_w`（放大唯一来源）。★ C 画布铺满 + 固定摆位：'
                '`set_output_offset` / `set_opaque_bg` 在位 · `paintEvent` **真守卫**消费'
                '（AST 排除 `if False and ...` 短路 —— 变异 M8 逼出来）· '
                '`_place_scene_layer` 只 move 不 resize · **零四向钳制**'
                '（`max/min` == 0，废弃第89轮"居中+四向钳制"）· 以**主屏**为基准'
                '（`primaryScreen()` + `geometry()`）· 摆位后 `repaint()` · '
                '`_primary_screen_size()` 用主屏物理尺寸（非多屏合并）。'
                '★ D 桌面透明 / 房间不透明：`_scene_is_transparent()` · '
                '`bg == TRANSPARENT_BG` 显式声明 · **`except` 块必返 `False`**'
                '（AST 定点判 —— 变异 M11 逼出来："数 `return False` 总数"会被别处掩盖）· '
                '`desktop.json` 数据面同源。★ E 全局缩放：`PET_SCALE_*` 四常量'
                '（DEFAULT=1.0 = 与场景同比例 = 最贴原作）· `_cached_scale_factor` '
                '**真被赋值**（第44轮起从未赋值 ⇒ 恒走默认 2.0）· '
                'AST **数据流**判 `v = <含 scale 的量> × <相对倍率>`'
                '（允许 `getattr(cam,\'scale\',…)` 与局部变量中转 —— 变异 M13 逼出来）· '
                '`set_pet_scale(persist=)` 真钳位（AST 判真守卫）· `ui_scale()` '
                '**平方根**折中 + 钳 `[0.5,3.0]` · 设置面板 `pet_scale_spinbox` 实时预览'
                '（`persist=False`）+ `save_config` 落盘 · 旧档位名双向兼容'
                '（`literal_eval` 求值 `normal ⇒ 1.0`）· **接线调用顺序**'
                '（读回 → 全屏化 → 刷新倍率；按 AST 调用序判，不按字符 `.find()`'
                '—— 注释里提到 `fit_camera_to_screen` 会污染位置）。'
                '★ F 零依赖纪律（`scene_camera`/`scene_render` 顶层零 Qt/零项目内）。'
                '★ G 判据自身体检（无 `ok(...,True)` 恒真 · 记账守恒 · '
                '九处令牌逐个回原文件 `in`）。'
                '★★ 数值实证由 `verify107.py` 承担（**21 PASS/0 FAIL**，不进 G2）；'
                '录屏几何自证由 `rec107.py` 承担（**13 PASS/0 FAIL**：'
                '画布 == 主屏尺寸 · 位置 == 主屏原点 · **宠物移动后画布位置不变**'
                '= "不是跟随移动的窗口"的直接反证 · 桌面透明/房间不透明成对）；'
                '变异测试 `mutate107.py` **16/16** 全部被对应判据抓到'
                '（含 `_place_scene_layer` 改回四向钳制、`paintEvent` 短路、'
                '`except` 返 True、两段钳位同拆等）。'
                '★ 本套件**零外部盘依赖**（回归碰不得 E 盘）。',
    },
    {
        'id': 'check109',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第109轮-场景过渡动画', '_tools', 'check109.py'),
        'offscreen': True,
        'desc': '第一百零九轮：**进入场景的原作式过渡动画**（纯黑遮罩 alpha 线性渐变）'
                '不许静默漂移。★ 取证（UTMT 反编译 ch1，逐字）：'
                '`obj_fadeout` / `obj_fadein` / `obj_persistentfadein` 三者 '
                '`image_blend = c_black`（= 纯黑，落在 `spr_pixel_white` 上）· '
                '`fadespeed = ±0.08`（macOS 淡出 0.14，**平台不对称**，如实记录）· '
                '`alarm[2] = 8` 帧 @30fps ⇒ 淡出 267ms、'
                '`1/0.08 = 12.5` 帧 ⇒ 淡入 417ms · 无音效、无"按任意键跳过"。'
                '★ A 机制存在且**被消费**：`request_scene_transition` 有真调用点 · '
                '`_advance_scene_transition` 挂在 `update_movement`'
                '（30ms 帧钩子 = 原作 GMS2FPS）。★ B 时序常量 = 原作换算值'
                '（B3 负控制：淡出/淡入两者**必须不同**，不然换了常量也发现不了）。'
                '★ C 阶段序：**先置 α=1 再换房**（`set_transition_alpha(1.0)` '
                'AST 序**先于** `_do_scene_transition_swap`）。★ D 换房真调 `switch`。'
                '★ E 画布遮罩：`paint_on` **先于** `fillRect`（画完内容再叠黑）· '
                '色值 `QColor(0,0,0)` · 遮罩在**所有 translate/scale 之外**'
                '（否则遮罩会跟着相机平移 ⇒ 露边）。★ F 默认零回归：'
                '`_transition_alpha > 0.0` 真守卫 · 构造值 0.0（不动产品时行为一字不变）。'
                '★ G 容错：`except` 内必把 α 归 0（否则异常 ⇒ 全黑卡死 = 比报错更糟）。'
                '★ H 可关开关 `SCENE_TRANSITION_ENABLED` + 入口接线'
                '（`travel_to_scene` 真走过渡、且保留 `_travel_commit` 回落路径）。'
                '★ I 判据自身体检（所有被判函数/类都**解析到了**，'
                '否则后续 `in src` 判据全变恒假 · 正/负控制成对）。'
                '★★ 判据一律走 AST，禁纯文本扫（"提到某名字"类恒真判据已四次发作）。'
                '★ 本套件**零外部盘依赖**（回归碰不得 E 盘）。',
    },
    {
        'id': 'check111',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第111轮-Niko家彩蛋', '_tools', 'check111.py'),
        'offscreen': True,
        'desc': '第一百一十一轮：**Niko 的家 = 永远进不去的彩蛋**（#47）。'
                '★ 口径（用户逐字）：连问三次确认（①「你确定吗？」'
                '②「你这样的行为可能导致世界崩坏，你真的确定吗？」'
                '③「你真的不再考虑考虑了吗？」）· 选项「我再考虑考虑」/'
                '「我确定！！！」· 选「我确定！！！」⇒ **伴随三角符文的高级爆炸特效**'
                '（`spr_realisticexplosion`）⇒ 选项**变回**「我再考虑考虑」· '
                '**永远进不去**。★ 三条判据线：A 结构层（类/常量/分支/'
                '`on_egg` 传递链 + **素材在盘**）· B 行为层（真跑 `build_props`：'
                'desktop B ⇒ `NikoHomeDoorProp`；A/C/D ⇒ 普通 `DoorProp`；'
                '别的场景 B ⇒ 普通门；**不给 `on_egg` ⇒ 不建**（不造假门，'
                '且**绝不能**退化成"吃路由的普通门"））· C 负控制（运行时生成 '
                'uuid 拼场景 id，证明"彩蛋判据"不是恒真）。'
                '★★★ 台词判据一律走 **AST 取常量值**，禁 `in` 源码 —— '
                '三句台词在模块里各出现两次（常量 + docstring 复述口径），'
                '`in` 会变恒真（变异测试 M3 实证）。',
    },
    {
        'id': 'check112',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第112轮-桌面门渐显', '_tools', 'check112.py'),
        'offscreen': False,
        'desc': '第一百一十二轮：#47 续 —— **门渐显 + 门贴图重做 + Niko 家准入/问答**。'
                '★ 口径（用户逐字）：「门也不是都长那样啊，而且摆放的位置也不在屏幕'
                '四周啊」·「ut 就用**王座那个门**」·「给门添加一个功能，在检测到实体'
                '靠近后才从透明到实象，中间要有个从虚到实的过度动画，**只针对桌面上的 '
                'ut 和三角符文的门**，oneshot 和 niko 的家不变」·「niko 的家确保只是'
                '**除了用户（灵魂）不可以进去其他人都能进去**」·「先正常回答 niko 在'
                '原作里描述的那样，**如果继续追问**那就回答「内容以屏蔽」」。'
                '★ 三条判据线：A–H **门渐显**（`door_reveal` 零依赖纯函数：距离→alpha '
                '单调 · 只 `(desktop,C/D)` 命中、`A/B` 明确**不**命中 · 就地写 alpha 的'
                '幂等与"非目标门一字不动" · 两份字母表**不分叉**）· I–K **Niko 家准入与'
                '问答**（`niko_home`：`soul/user/灵魂` 拒、`None` 与陌生对象**放行**'
                '（默认站"能进"）· 第1次人设线、第2次起屏蔽 · 屏蔽语逐字）· G/L **数据'
                '与单一真源**（`desktop.json` 四门贴图/尺寸/`anim` · 三连台词由 `niko_home` '
                '派生且与 `item_interact` 完全相等）。'
                '★★ 零外部盘依赖；每个纯函数都有正/负成对断言（含"远端≠近端"防恒真）。',
    },
    {
        'id': 'check113',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113.py'),
        'offscreen': False,
        'desc': '第一百一十三轮：**全体角色 AI 训练**不许静默失效 —— '
                'A 数据面（96 张卡三档分型 77/18/1 / 缺口恰为 knight / 人设 sha256 与磁盘同源）·'
                'B 合规闸体检（6 条正常台词零误报 + 7 类坏样本逐个命中 + 空串/复读/语言占比）·'
                'C 产品契约（prompt 唯一出口：patch/relation/evolution 三块位置/读不到返空串/'
                '★ main.py 真接线 —— AST 断言，禁扫字符串）·'
                'D 产物（raw/transcript/corpus/报告四者对得上）· E/G 区分度与态度覆盖。',
    },
    {
        'id': 'check113e',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113e.py'),
        'offscreen': False,
        'desc': '第一百一十三轮e：**括号旁白**的两把尺不许再同时失效 —— '
                'A 产品护栏 `strip_action_parentheticals` 对 4 条真实模型输出'
                '（`（你皱起眉头…"…"）` 这类**第二人称描述自己**）必删旁白、留台词 · '
                'B 负控制 7 条正常台词逐字不变（含第一人称心里话 `（其实我很害怕）`，按既有裁定保留）· '
                'C 训练判据 `_PAREN_RE` 同 4 条必报、无括号台词不误报 · '
                '★ C9 显式断言**两把尺刻意不同**（`（你懂的）` 产品保留/训练违规），'
                '免得后来者顺手统一 · '
                '★ D1/D3 **破坏性负控制**：把新判据拆干净后 4 条必须全部重新漏掉、'
                '上限改回 `{1,30}` 后必须重新漏报 —— 证明通过不是恒真。'
                '★★ 本套件对应的真缺陷：48 轮里 45 轮都在写旁白，而两处判据同时放行，'
                '指标显示「违规 2/48」。',
    },
    {
        'id': 'check113g',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113g.py'),
        'offscreen': False,
        'desc': '第一百一十三轮g：**性格不许演成极端**（用户口径「不要过度突出个人特点……要和正常人一样」）—— '
                'A 规则面（**AST 取 `SPEAK_RULES` 的值**，不吃注释）：四句性格校准规则齐全 · '
                '★★ 值里**不许出现任何极端词**（暴躁/柔弱/过分/动不动就…）—— 113g 探针实测：'
                '规则里只要描述「那种行为长什么样」，同类违规率就从 1/10 涨到 10/10 · '
                '正控制：往值里加「不要过于暴躁」必须被抓到 · '
                'B 度量面：`extreme113` 软上限表 6 分量 + 每项带「单位/为什么」· '
                '暴怒/柔弱样本必判红、正常样本必不判红、5 条正常台词 0 误伤 · '
                '★ 必须按 `metrics.lang` 拆新旧 prompt 批次（否则会拿旧语料下当前结论，本轮栽过）· '
                'D 破坏性负控制：删掉四句、只删一句都必须重新报红。'
                '★★ 结论诚实标注：当前新 prompt 批次（23 角色）最高过火率仅 0.06，'
                '**过火尚未被数据证实** —— 本规则是预防性护栏，不是缺陷修复。',
    },
    {
        'id': 'check113h',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113h.py'),
        'offscreen': False,
        'desc': '第一百一十三轮h：**角色档位两轴**（machine=不要活人感 / caps=显示层全大写）'
                '不许静默失效 —— 用户口径「他不是有字体吗，你直接用就好了」'
                '「别只顾着三人啊，这三人当示例然后再推进到其他人身上即可」'
                '「oneshot 里很多没被制御的机器人不必要要求活人感」。'
                'A 档位机制：human 段是 `SPEAK_RULES` 的**真后缀** · human 档返回**同一个对象** · '
                '★ A10 **两轴正交**（ot_papyrus 是 human 却大写 / os_kelvin 是 machine 却不大写，'
                '拿 kind 推 caps 必红其一）· A9 破坏性负控制：拆掉后缀 ⇒ machine 档必须退回 human · '
                'B 渲染层：`if _caps_on(speaker)` 分支内做 ASCII 大写化 —— **AST 判，不扫字符串** · '
                '★ B3 只用 AST 判有没有真的**调用** `QFont.setCapitalization`（纯文本扫会被'
                '「解释为什么不用它」的注释打红，已连踩六次）+ B3b 判据自检 · '
                'C 覆盖句：`caps` 登记角色 prompt 必带 `CAPS_RULE`，**未登记的一字不加**（C2 负控制）· '
                '★ C4 反向守着「不许把人设里的原作台词依据删掉」。'
                '★★ 判据刻意**不**去人设里数「全部大写」出现几次 —— 那是原作依据，删了才是错。',
    },
    # ★ 第113轮j：给 NPC 装「空间认知」。
    #   为什么进 G2：这一层决定模型**知不知道自己在哪**，而它的输出会被
    #   `check73 E4/E4b` 原样打印出来 —— 也就是说它一坏，check73 会先红。
    #   但 check73 只抽**一个**真场景，覆盖不到 2166 个；本锁做全量普查。
    {
        'id': 'check113j',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113j.py'),
        'offscreen': False,
        'desc': '第一百一十三轮j：**空间认知**（NPC 知道自己在哪 / 归属地在哪）不许静默失效 —— '
                '用户口径「方便的话可以训练一下他们寻路的能力（包括地方偏好，'
                '特定事件时去的地方等等）」。'
                '★ 为什么不是"让模型做路径搜索"：`npc_roam.step()` 早就是确定性权重决策，'
                '模型不参与；缺口在 prompt 只有「这地方什么样」没有「你在哪儿」。'
                'A 输出质量（真名要留：`FINALE`；内部 id 要剥：`rm_dalvExit`→`dalvExit`；'
                '容器名不露：「全部房间」「未分区」）· B **2166 个场景全量普查**（零空标签 / '
                '零泄漏 / 零三段 / 括号成对 —— 6 个样本全绿说明不了问题，本轮就是这么抓到 '
                '26 条容器名漏判 + 4 条混合大小写 id 泄漏）· C 块行为（★"在家不许说想回去"'
                '是真错误防线：在家还说想回去，模型会答"那我该回家了"）· D AST 接线与**顺序**'
                '（位置块必须先于场景特质，反了模型会把地名当形容气氛的词）+ `at_home` 必须是'
                '比较式 · E 真实数据 84 条 `_placement.json` 的分布 · F 方法级端到端'
                '（抽产品 `_npc_life_blocks` 整段跑）。'
                '★ 第113轮m 追加 A5~A8 / B6 = **地名整形**：复合词 `Bed_room` ⇒ `Bedroom`'
                '（`room_word` 把它拆成 `bed room` 后，`bed` 在首位被当类型词截断，'
                '“房间”直接丢了）、英文 Title Case（活动块 `Town Square` 与位置块 '
                '`town square` 曾两种写法并存，模型挑一个照抄）、纯中文标签逐字不变、'
                '虚词（`the` / `to` / `in`）不做首字母大写（`Snowdin Secret to Everybody`'
                ' 是**对**的英文，一刀切会把 6 条正确输出判红）。'
                '★★ 判据自身栽过：第一版把章名括注里的 ` · `（`第一章 · 黑暗世界`）'
           },
    # ★ 第113轮k：**特定事件 → 去哪儿**。
    #   为什么进 G2：这一层坏掉**不会报错**，而是角色很自信地推荐一个
    #   不存在 / 别的世界 / 调试房的地方 —— 静默错比崩溃难发现得多。
    {
        'id': 'check113k',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113k.py'),
        'offscreen': False,
        'desc': '第一百一十三轮k/l：**特定事件 → 去哪儿**（NPC 听懂「咱吃饭去吧」'
                '并给出「那要不去 XXX 家餐厅」）。'
                '用户口径「吃饭/活动/休息/做任务等，他能识别出来要去哪，并给出建议」'
                '；l 轮再追加三条：「名字用英文」「有些 room 名称并不口语化，要变口语化」'
                '「可以跨区域」「人名也要改成英文」。'
                '★ 两件事必须分开：`detect_activity` 只认**意图词**、`place_matches` 只认'
                '**地点词** —— 混成一张表会因果倒置（"因为人在餐厅所以他在吃饭"）。'
                'A 抽取 + 策略层零依赖 · B 听懂四种 + 多活动取**语序最先** · '
                'C `place_matches` 正负成对（`town_school` 要命中 `school`；`sparks` 不许命中 '
                '`park`）· D 候选必须**说得出是哪一家**（`Hometown · Diner`；'
                '第一版输出「真有的地方：家乡」，用户要的那个「XXX 家餐厅」没了 —— 实测抓到的真错误）+ '
                '去重不变量（同一个名字只列一次，但**不许过度**）· E 负控制（无关话/'
                '**调试区**不产块；★ 判不出章**不再阻塞** —— 跨区域后改说"有的不在你这一带"）· '
                'F 翻译表**不越权**（`Research Station` 不是火车站；现在只供去重键、不进 prompt）· '
                'G 名字整形三条正负成对（房号/行首单字母或数字/截到类型词为止）· '
                'H 全量普查（零空标签、零内部标记、零容器名 `Rooms`、零章括注、零裸通用词）· '
                'I AST 接线（`heard` 必须从 `chat_with_ai` 一路传下来，且**有闸** —— '
                '没闸就是给所有 NPC 无条件加行、等于改人设）· J 方法级端到端 · '
                'K 英文地名/口语化/跨区域（`speakable_en` 四条规则、所有格正负成对、'
                '容器区 `rooms` ⇒ 作品缩写 `UT`/`UTY`、中文人名换英文、同章优先）。'
                '★ 判据用**不变量**（"同一个名字只列一次"），不冻结数据（"ch1 必须 3 条"）'
                '—— 否则以后加素材就假红。',
    },
    # ★ 第113轮l：**出戏的元词汇**（自称 AI / "提示词" / "设定"）。
    #   为什么进 G2：这一层坏掉**不会报错** —— 角色会非常自然地回答
    #   「我没有提示词」「我知道这只是个设定」，读起来毫无异常，但角色已经"出戏"了。
    #   ★ 本轮两件事方向相反，都得锁：① 把尺子修准（裸词也判红）；
    #     ② **把纠正句撤掉**（实测三个候选句都比不加更差，详见套件头注释）。
    {
        'id': 'check113l',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113l.py'),
        'offscreen': False,
        'desc': '第一百一十三轮l：**出戏的元词汇**（自称 AI / 提示词 / 设定）。'
                '★ 两件事方向相反：① `_AI_RE` 原来只认「我是 AI / 我是程序」这种**句式**，'
                '全量扫 raw30 的 1956 轮回复，旧判据判红 22 条，而另**48 条 / 25 人**'
                '说着「我不是 AI 哦」「我知道这只是个设定」一条都没判 ⇒ 裸词也判红'
                '（这不是"角色变差"，是同一批数据换尺子才看见）。'
                '② 原计划给判红的人写通用纠正句，**三轮实测全部指向"更差"**：'
                '顺序四臂各 9 样本（不加 1 条含禁词、三个候选 3~4 条）、'
                '反向交替对照各 12 样本（不是漂移，是那句话在**激活**这些词：3/12 → 8/12）。'
                '⇒ `PATCH_RULES` 里**故意不设** `AI_SELF`，改靠判退重采样，'
                '并把这个决策锁成判据（防以后凭直觉加回来）。'
                'A 决策+负控制 · B 文本卫生（否决句本身也不许含禁词根；旧句会命中，'
                '证明"整句正则"太窄）· C 两份副本与产品读取链路 · D 尺子正负成对'
                '（`hy_sousborg` 的厨房"程序"、`os_prophetbot` 的"我的程序"不许误判）· '
                'E 实测证据只断言**方向**（不打印随数据变的绝对数，否则重跑探针就假 DIFF）· '
                'F 本轮脚本自检（语法 / 无 BOM / 行尾不混 / **无恒真判据** —— 扫 `check()` '
                '的 `args[1]` 是不是常量 True，带正控制）。',
    },
    # ★ 第113轮n：**「你还记得这些地方」接上了** —— 1 跳邻居来自原作门连接图。
    #   为什么进 G2：这一块从 113j 起就写着"预留，当前调用方没传" ——
    #   `place_hint(near=)` 有形参、有文案、有判据，产品**一次都没传过**。
    #   形状齐了、没人接线、指标全绿，正是本项目最贵的那类坑。
    {
        'id': 'check113n',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113n.py'),
        'desc': '第一百一十三轮n：**「你还记得这些地方」**（NPC 知道附近有什么、'
                '走过去能到哪）不许再是"有形状没人接线" —— 用户口径「训练一下他们'
                '**寻路**的能力（包括地方偏好，特定事件时去的地方等等）」。'
                '★ 真源 = 原作门连接图（`_room_graph.json`，第42轮反汇编 + 第105轮补 '
                'OneShot + ★第126轮补 outertale，共 1,411 条边）；'
                '**不按落点坐标算近** —— 房间坐标是各自的'
                '局部系，跨房比距离在原理上不成立（第44轮已证伪）。'
                'A `scene_pathfind.neighbor_rooms()` 纯函数（只取 1 跳且**方向正确**、'
                '自环丢掉、升序去重保证确定性、坏输入返 `[]` 不抛）。'
                'B `_npc_place_near()` **AST 抽出产品代码真跑**：标签取原作房间 id '
                '整形后的英文，**不**取 `_scene_place_label()` —— 后者对 '
                '`name_derived=True` 的场景只吐区名，于是 5 个邻居全叫「家乡」，'
                '等于没说（本轮探针实测）；调试/演出区与容器区被剔；无图章节'
                '（ut / uty / desktop —— ★第126轮起 outertale **不在**这份名单里，'
                '它有图了，B8b 是它的正控制）返 `[]` 不崩；全量普查零空标签、'
                '零内部结构、零重复，覆盖率用**只增不减**的下界（不打印随素材变的绝对值）。'
                'C `place_hint` 的 near 文案要说得出「就在这一带，走过去能到」—— '
                '只说"我记得有这些地方"，模型不会拿它当路线依据。'
                'D AST 接线（禁纯文本扫，已五次发作）：`_npc_life_blocks` 里 '
                '`place_hint` **真的**带 `near=`，值最终来自 `self._npc_place_near(...)`'
                '（允许局部变量中转，判一步数据流 —— 同 107 轮变异 M13），'
                '且那条链真走到 `load_room_graph()`。'
                'E 破坏性负控制：把 `neighbor_rooms` 打回 `[]`、只拆 `place_hint` 的 '
                'near 分支（其余不动），对应判据必须**真的变红**。'
                'F 本轮脚本自检（语法 / 无 BOM / 行尾不混 / 无恒真判据 + 正控制）。'
                'G **端到端**：整段 prompt 里真有那块（`ch1.hometown.diner` ⇒ '
                '`【你还记得这些地方】Town Mid —— 就在这一带，走过去能到。`），'
                '无图章节（`ut`）整段不含该块，且把 `neighbor_rooms` 打回 `[]` 后必须消失。'
                '★★ 踩到的坑：给被抽取的 `_npc_life_blocks` 加新 `self.xxx` 依赖后，'
                '`check113j` 的桩没有它 ⇒ `AttributeError` 被同一个 `except` 吞掉 ⇒ '
                '**整个位置块静默消失**、F1~F4 一起红（报的是真事实，根因在桩）。',
    },
    # ------------------------------------------------------------ 第113轮p
    # 为什么进 G2：`_pick_friend()` 挑出了**具体某个人**，目的地却是
    # `_pick_reachable(reach, rng)` —— 随机一个能去的地方。
    # `Intent.who` 有值、`dest_scene` 有值、`why='visit_friend'`，
    # **"他说去看朋友，其实走到了别处"，任何报告都读不出来**（无异常、无空值）。
    # 这是"有形状没人接线"的变种：形状有了、也接线了，但**接错了对象**。
    # ★★★ 2026-10-28 事故：看护在 39/75 处把训练 terminate 了（exit 15）——
    #   当时 `llama-server` 的 RSS 已从 5.9 GB 涨到 11.7 GB，可用内存只剩 17 MB。
    #   而**同一时刻调一次 `keep_alive=0` 卸载，可用内存 1.21 GB → 13.56 GB**。
    #   ⇒ "第一步就是杀"是错的。这条判据锁住新的决策顺序。
    {
        'id': 'test_guard_mem113q',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools',
                               'test_guard_mem113q.py'),
        'desc': '第一百一十三轮q：**训练看护的内存闸不许"一见低内存就杀训练"** —— '
                '2026-10-28 06:29 的实证事故：`llama-server` 的 RSS 随训练从 5.9 GB 长到 '
                '**11.7 GB**，可用内存压到 **17 MB**，看护直接 terminate，训练停在 '
                '**39/75**（`os_shepherd` 第 5 轮）。而同一时刻 `keep_alive=0` 卸载 '
                '能立刻回收 **12.35 GB**（1.21 → 13.56 GB）⇒ 压力几乎全在推理进程里，'
                '"杀训练"只能是最后手段。判据（`thermal113.relieve_mem` 抽成可注入的函数，'
                '因为正面路径在真机上复现不出来）：A 卸载后回到下限×4 ⇒ 判 ok 且**只卸 1 次** '
                '· B 两次后仍低于下限 ⇒ still_low 且两次都真试过 · **B3 A 与 B 必须不同** · '
                'C 没到宽裕档但已越过下限 ⇒ 仍放行（刚好过线也比杀训练强）· '
                'D 卸载接口本身失败且内存没回来 ⇒ 仍判 still_low（不因"试过了"就放行）· '
                'E ★★ **负回归：同一场景下旧逻辑会杀、新逻辑放行**（差异真实存在）· '
                'F 真落了日志（不是静默改判）。★ 写判据时自己栽过一次：夹具把"卸载前的值"'
                '塞进内存序列，而 `relieve_mem` 是**先卸载再读** ⇒ 假红；'
                '**夹具不保真 = 报假问题**。',
    },
    # ------------------------------------------------------------ 第113轮r
    # 为什么进 G2：`voice_markers` 是**评测口径**（回复里出现任一 marker 就算
    # "有他的味道"）。登记了 `I` / `……` / `[……]` / `想` / `时候` 这种任何人在
    # 任何一句里都有的东西 ⇒ 命中率被灌成 36/36，而报告读起来是"演得真好"。
    # **改错不会报错，只会让数字悄悄变样** ⇒ 必须有判据盯着这段手术：
    #   · `[……]` 这种登记项**自身就含 `]`** ⇒ 用"第一个 `]`"取数组会切在字符串
    #     中间，产出一个看似合法、实则被截断的 JSON（实测天真写法在 4125 处截断，
    #     真结尾 4153，差 28 字节）；
    #   · 卡里 CRLF/LF 两种 EOL 都有，写回被统一 ⇒ 整份文件变红、掩盖真改动。
    # 判据内含 A/B 与三条负控制（预览不写盘 / 删不存在的项必须炸 / 重复键必须炸）。
    # ------------------------------------------------------------ 第113轮r（其二）
    # 为什么进 G2：`_seek.json` 决定「NPC 想去找谁」，**猜错就是把 A 的偏好挂到
    # B 头上** —— 产品不报错，只会让某人莫名其妙天天往另一个人那儿跑。
    # 本次修的是"名字后面带注释"（`Silver（总工程师）`）解析不出来：
    # 带注释整体查名册 ⇒ 精确匹配落空、前缀匹配也不成立 ⇒ 判 unknown 丢掉。
    # 实测 33 条未解析里**就这一条是真漏**（27 条名册外人、5 条 `ot_`/`ut_` 重名），
    # 修完 `os_rowbot → os_silver` 解出来，理由正是"导航坏了要去找她修"。
    # ------------------------------------------------------------ 第113轮s
    # 为什么进 G2：这是**两处静默失效**，都不报错、也不影响跑通，只是成果不进产品。
    # ① `eval113.load_all` 只认 `phase=='baseline'`，而 `train30` 写 `phase='t30'`；
    #    同一 raw30 文件里两条都在 ⇒ 评测一直在评**旧的 4 轮**记录：
    #    77 人只产出 **2 条** patch，48 轮实测的 **419 次 `ACTION_PAREN`**、
    #    146 次 `AI_SELF`、108 次 `NOT_CN` **一条都没变成运行时纠正**
    #    （`_index.json.patches` 长期只有 3 条）。数字看着正常，评的是别的东西。
    # ② `main` 里 `idx['patches'] = patches` 是**整体替换** ⇒ 会把别的轮
    #    **手写**的 `ralsei` 名字规则（为「凯斯恩」这类拼名而加）静默删掉。
    # 判据：A 按轮数挑 / A2 负回归证明与旧写法不同 / B~D 边界 /
    #       E~E5 并集规则 / F 旧键不许丢 / F2 负回归证明差异真实 / G 真数据集成核对。
    {
        'id': 'test_evalpick113s',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools',
                               'test_evalpick113s.py'),
        'desc': '第一百一十三轮s：**训练成果回到产品这一步曾经整条断掉** —— '
                '`eval113.load_all` 只认 `phase==baseline`（4 轮 `dialogue113` 的记录），'
                '而 48 轮的 `train30` 写的是 `phase=t30`，且**每个 raw30 文件里两条都在** ⇒ '
                '评测一直在评那 4 轮：77 人只算出 **2 条** patch，'
                '本轮实测的 419 次 `ACTION_PAREN`/146 次 `AI_SELF`/108 次 `NOT_CN` '
                '**一条都没回到产品**（`_index.json.patches` 长期只有 3 条）。'
                '接上 `raw30` 后同一份数据算出 **57 条** patch（54 个角色第一次有纠正）。'
                '同轮还修了回填方式：`idx["patches"] = patches` 是整体替换，'
                '会把别的轮手写的 `ralsei` 名字规则删掉 ⇒ 改成按句求并集。'
                '判据 A/A2 证明选法变了且与旧写法结果不同；E3 钉住"互不包含时取并集'
                '而不是二选一"；F/F2 正负对照证明旧键不会丢；G 用真 `_index.json` 核对。',
    },
    {
        'id': 'test_seekresolve113r',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools',
                               'test_seekresolve113r.py'),
        'desc': '第一百一十三轮r（其二）：**剥掉名字尾部的括号注释再查名册**，'
                '但反向一条都不许松。A 正向 `Silver（总工程师）` 从 os_rowbot 视角解到 '
                '`os_silver`；B 负控制 `Sans（ambiguous）` **必须仍判重名**'
                '（`ot_sans`/`ut_sans` 两个候选，拒绝猜）；C 负控制 `母亲`/`Kanako`/'
                '`后备机器人` 仍判 unknown（名册里确实没有）；D 消歧规则不得退化 ——'
                '`Toriel（她妈妈）` 从 kris 视角仍落 `toriel` 而非 `ot_toriel`/`ut_toriel`；'
                'E/E2/E3 是 `_strip_note` 的边界（核心短于 3 字不剥、纯字符串操作、'
                '多层括号逐层变短必然终止）；E4 剥完仍解不出时**括号里的原因要回传**'
                '（否则 `Sans（ambiguous）` 会退化成 `unknown`，把"两人重名"误报成'
                '"名册没这人"）。★ 名册索引用真卡现造，不用手写桩（桩比产品旧＝假红）。',
    },
    {
        'id': 'test_markers113r',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools',
                               'test_markers113r.py'),
        'desc': '第一百一十三轮r：**清掉会把「口癖命中率」灌水的登记项** —— '
                '`assets/npc/_training/cards/*.json` 的 `voice_markers` 里，'
                '`I`（英文代词）/ `……` / `[……]`（标点）/ `想`（中文恒真）/ '
                '`时候`（常见名词）不可能当口头禅用，却让 `hy_chujin_ketsukane` 31/36、'
                '`mike` 与 `kris` 36/36 变成"满分"⇒ 那不是演得好，是判据太松。'
                '★ 名单**逐条来自磁盘实测**，不是抄文档：文档那张表里 `hy_guardener` 的 '
                '`_ ; >`、`noelle` 的 `……` 实际都不存在，而 `ut_frisk`(×2)、`ut_gaster` '
                '文档漏了。清完 `marker_hit` 返回 `None`（记 N/A，不记 0）。'
                '手术用 `raw_decode` 而不是"第一个 `]`"：`[……]` 自身含 `]`，'
                '天真写法会在 4125 处截断而真结尾是 4153。判据：A 预览零改动、'
                'B/B2 只换数组且回读一致、C EOL 逐文件保留、D/D2 陷阱真实存在、'
                'E 删不存在的项必须抛断言、F 重复键必须抛错、G 二次修改必须拒绝、'
                'H 测试只在副本上跑（真卡零改动）。'
                '⚠️ 脚本自带闸门：`train30.py` 在跑就拒绝执行（中途改会让同一份报告混两套口径）。',
    },
    # ★ 第117轮（补第115轮 §16）：**可读物正文资产**是产品数据，被手改/回滚都不会报错
    #   （空串照样能显示），所以要像守产品代码一样守它。
    {
        'id': 'check_readable_asset115',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第115轮-跨作品物件普查', '_tools',
                               'check_readable_asset115.py'),
        'desc': '第117轮（补第115轮 §16）：**可读物正文资产** '
                '`ralsei_pet/assets/scenes/_readable_text.json` —— 文本键由「房间」决定'
                '（原作 `obj_readable_*_Alarm_0` 里的 `if (room == N)`；反射取证 '
                '`ValueVariable={room}`），**不是**按实例坐标。A 结构（`schema_version` · '
                '`markers_raw` 为真 = % & / ^1 没被偷偷替换 · `markers_note` 在位，标记'
                '**未解码**）· B 分母（v2 起 ut ≥300 / outertale ≥250 条；uty 的 0 条是'
                '**原作事实**，显式记 EMPTY，不当作通过）· C 引用完整性（每个 scene_id 真在'
                '产品 `_zone.*.json` 里、每个 key 真在 `readables115.json` 里）· D 正文非空白'
                '（不用空串顶）· ★E `cn_tight` 去空白后与 `cn` 逐字相等（只许少空格，'
                '不是改了几个字）· ★F 分母守恒（资产里每个 (场景,对象) 组合都真在 '
                '`inst_full.tsv` 有实例，不造挂载点）· ★G 未解如实登记（ut 19 无房间条件 / outertale 另 186 '
                '**没有**混进 by_scene）· H 三条破坏性负控制（正文改空白 / key 改名 / '
                'cn_tight 换字 ⇒ 对应判据必须变红）· I 自检（AST 数恒真判据 + 正负控制；'
                '第一版用正则扫文本，被自己的正控制字符串打红 ⇒ 改 AST）。'
                '★ 本套件**零外部盘依赖**（只读仓库内文件）。',
    },
    {
        'id': 'check_readable_wire117',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第115轮-跨作品物件普查', '_tools',
                               'check_readable_wire117.py'),
        'desc': '第117轮：**可读物真的说原文** —— 控制符解码 + 资产载入 + 接进可交互物。'
                '数据层继续保留原始标记（`markers_raw` 仍为真，见 '
                '`check_readable_asset115`），解码只在**显示层**做，规则全部来自反编译取证'
                '（`_evidence/raw/ut/gml/`：`obj_base_writer_Draw_0` 分派 · `SCR_NEWLINE` '
                '`&`=真换行 · `Alarm_0` `^N`=停顿 · `scr_replace_buttons_pc` `[C]`=按键字形）：'
                '`&`=换行 · 单个 `%`=换页（本产品单框 ⇒ 退化成换行）· `%%`=**消息结束**（截断）· '
                '`/`=等按键且**不移动书写点**（删且**不换行**）· `^N`=停顿 · `\\\\X`=颜色/字体/音效 · '
                '`[C]`=字形占位。A 纯函数 13 条，`%` vs `%%`、`&` vs `/` **正负成对**；'
                'B 资产账目守恒（采用+未采用候选+解空==原始条目；v2 起为 335+613+6=954）'
                ' + 解码后无 `% & / ^ \\\\` 残留；'
                'C 真跑 `build_props`：给表用原文 / 不给表回落兜底 / 场景不在表里不造假（三条成对）；'
                'D 与"朴素实现（一律删标记字符）"必须不同 + B4 谓词非恒真；'
                'E AST 接线（`main.py` 真传 `readables=` 且来自 `load_readable_text`；'
                '`build_props` 函数体真用该参数；`item_interact` 仍零依赖）；F 自检（AST 数恒真 + 无 BOM）。'
                '★ 零外部盘依赖（只读仓库内资产）。',
    },
    {
        'id': 'check_readable_guard119',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第115轮-跨作品物件普查', '_tools',
                               'check_readable_guard119.py'),
        'desc': '第119轮：**可读物的第二层 if**（同一房间同一对象有多个候选文本时选哪条）。'
                '结论全部来自 GML 原文（`_evidence/raw/{ut,outertale}/gml_readable/`）：'
                '原作不是 `if/else if` 链，而是**一串平行 if 逐条覆盖 `global.msg[0]`** '
                '⇒ 语义是「最后一条成立的赋值获胜」，默认值只能取**守卫最松（base）的最后一条**。'
                'A `pick_readable_entry` 纯函数（多条 base 取最后一条 / 无 base 取第一条 / '
                'v1 老资产取第一条 / **与老实现必须不同**）；B 资产 v2 结构（合法 `guard`、'
                '`(obj,order)` 有序）；C ★★ 与 GML 原文对账（v1 缺 ut 105 组 / outertale 78 组，'
                '本判据防回退；`MSC_*` 交给 msc 脚本、不算正文）；D 防回滚下界（条目 ≥900、'
                '场景 ≥160、base ≥500）；A7~A9 空文本回退（选中 base 解完为空 ⇒ 退到其余候选，全空才放弃）；'
                'F 三个写死取样；E 自检（AST 数恒真 + 无 BOM）。'
                '★ 零外部盘依赖（只读仓库内资产 + 第118轮蒸馏进仓库的 TSV）。',
    },
    {
        'id': 'check_bg120',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第120轮-ut场景背景与物件', '_tools',
                               'check_bg120.py'),
        'desc': '第120轮：**UT 场景的空壳补上画面**。ut 的 game.droid 是 **GMS2** 结构，'
                '房间内容不在 `room.Backgrounds` / `room.Tiles`（GMS1.4 旧槽位 —— 之前脚本'
                '一直读它们，所以 UT 永远 `objects` 0 条 / `bg` 全 null），而在 `room.Layers`：'
                '背景层 + 68919 块 legacy tile + 13965 个实例。`bake120.py` 按 depth 顺序'
                '（大 = 靠后）烘成一张房间图，`apply120.py` 按**房间名**接进 `bg`。'
                'A 接线三面对得上（场景名 ↔ 图名 ↔ `bg_source` 前缀）；B 图尺寸 == 原作房间 w×h；'
                'C 338 间用 UT 自己的图，**另 20 间如实留空** —— 那 20 个名字在 UT 的 '
                'game.droid 里 0 命中（outertale 的 dump = UT 全 338 间 + 自有 20 间，'
                '说明它们本就不是 UT 的房间，第77轮从跨作品大图迁入时混进 ut 章）；'
                '第一版曾拿外传同名图顶上，已由 `revert120_ot.py` 撤线（外传美术冒充原作=编造）；'
                'D 无孤儿图；E 防回滚（338 间 / ≥2 MB）；'
                'F 自检（**AST** 数恒真判据，不扫注释 —— 扫注释会被文案误报）。'
                '★ 零 Qt、零外部盘（只读仓库资产 + 本轮蒸馏进 `_evidence` 的 TSV）。',
    },
    {
        'id': 'check_objs121',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第121轮-ut可交互物', '_tools',
                               'check_objs121.py'),
        'desc': '第121轮：**ut 场景的 objects（可交互物）** —— 第120轮把画面烘成了背景，'
                '但 `objects` 仍是 `[]` ⇒ `item_interact.build_props()` 遍历不到东西 '
                '⇒ 走进 ut 房间**什么都点不了**（可读物/存档点/告示牌全哑）。'
                '本轮写进 422 条（136 个场景）：readable 350 / sign 34 / savepoint 33 / '
                'pickup 3 / fountain 1 / interactable 1。'
                '★ 三条口径：① 只写**现在真能用**的 6 类 —— `door`(1,299 个实例) 不写'
                '（建门要 `routes`，ut 侧还没有 ⇒ 写了就是推不开的门，留待路由那轮），'
                '`cutscene`(375) 不写（`build_props` 落 else 丢弃）；'
                '② `sprite` **一律 None**：ut 画面已在背景里，再画即重复；且 '
                '`_obj_visible.json` 的 `hidden` 是**全局扁平**名单，ut 的 `obj_savepoint` '
                '与 Deltarune 的**同名**（实测唯一冲突）⇒ 并进全局名单会跨作品污染。'
                '`scene_canvas._paint_obj` 的 `if name` 不成立 ⇒ 不落笔（已核行）；'
                '③ `pos = [x-ox, y-oy]`（左上角语义，与 `bake120` 画实例的式子**同一个**）。'
                'A 规模/形状（字段恰好 4 个 · sprite None · pos 两个 int）· '
                'B 来源与分类（src 都在 objmap 里 · 只许 6 类 · 分布 == 实测）· '
                '★★C **位置全量复算**：用仓库里的 `inst_full.tsv` + `objmap_ut.txt` + '
                '`SPR` 原点段重算 pos，358 个场景**逐条相等**（配 1 像素负控制 + 正控制）· '
                'D 防回滚 · E 自检（AST 数恒真 / 无 BOM）。'
                '★ 零 Qt、零外部盘（只读仓库资产 + 第115/120轮蒸馏进仓库的 TSV）。'
                '★★ 第122轮起：`objects` 里**多了门**（548 条 / 243 组），准入闸 = '
                '「`_routes.json` 里有目标」，B2b 双向锁住"点不动的门"与"幽灵规则"。',
    },
    {
        'id': 'check122',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第122轮-ut门与房间连接', '_tools',
                               'check122.py'),
        'desc': '第122轮：**ut 的门**不许静默失效 / 不许静默改目标。'
                '第121轮把可交互物补上了，但门被**故意**排除（建门要查路由，ut 段是空的）。'
                '本轮补上 243 条：① **110 条对象级** —— ut 的门对象叫 `obj_door_ruins13` / '
                '`obj_door_s_musfade` 这种，**不带字母**，目标写在 GML 的 '
                '`if (room == X) room_goto(Y);` 里（证据 = 可信层 131 条边的反编译函数名，'
                '同名多目标一律丢掉）；② **133 条字母级** —— `obj_doorA` 的 `room_goto_next()`'
                '（`dst == src+1` 133/133 自洽）。⇒ 覆盖 548/1,299 个门实例（42.2%）。'
                '★ 为此产品加了一路 `when_src`（对象级路由）：`route_for_door(routes, sid, '
                'letter, src=)` 先按对象精确匹配，字母那一路**跳过**对象级条目（否则'
                '"到下一间"会顶替"走 B 门"）；`scene_routing._match_one` 里语境没给 `src` '
                '时**判不匹配**（不是放行 —— 放行等于凭空指定一扇门）。'
                'A 规模/形状（243 条 · priority 独立段 4000+ 连续 · 两端已登记 · 无自环）· '
                '★★B **独立重算**：从 `conn115` + `conn_inferred115` + `inst_full.tsv` 重推'
                '每条 (场景,对象)→目标，逐条相等（配改目标负控制 + 原样正控制 + 非空分母闸）· '
                'C **与 objects 双射**（点不动的门 0 / 幽灵规则 0）· D 产品接线'
                '（AST 判 `src` 形参与 `src=` 传递 + ★行为判"字母/对象互不串台"）· '
                'E 防回滚 · F 自检（AST 数恒真 / 无 BOM）。'
                '★★ 明确不做：`obj_doorB/C/D` 与 musicfade 变体在证据里**没有**边 ⇒ 一条不写；'
                '`obj_mainchara` 的 420 条是"走到屏幕边缘换房"，属另一层机制。'
                '★ 零 Qt、零外部盘（只读仓库资产 + 第115轮蒸馏进仓库的 TSV）。',
    },
    {
        'id': 'check123',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第123轮-补齐ut门证据', '_tools',
                               'check123.py'),
        'desc': '第123轮：**ut 剩下的 751 个门实例**补齐（覆盖率 42.2% → 94.9%）。'
                '第122轮只认 `room_goto(<常量>)` 与函数名**字面**，'
                '而 ut 的门把目标写成 `room_goto(room_previous(room))` —— 目标是**函数调用**，'
                '永远变不成边（这就是 `conn_ut.csx` 里 `n_nonconst_target: 30` 的成因）。'
                '本轮反编译 133 条 door 事件代码 + 34 个 door 对象元数据（**含 ParentId**），'
                '实测出纪律：`obj_doorA` +1 / `obj_doorB` −1 / `obj_doorC` +2 / `obj_doorD` −2，'
                '`obj_doorAmusicfade`/`obj_doorBmusicfade` **自己没有 Alarm_2**、'
                '只有 `event_inherited()` ⇒ 必须沿父链继承（这条不查 `ParentId` 就会把 214 个'
                '实例误判成"无机制"）；`obj_papdoor` +1 是本轮新发现的对象。'
                '⇒ 新增 282 条位移路由（字母级 183 / 对象级 99），ut 段 243 → 525 条，'
                '门覆盖 548/1,299 → **1,233/1,299**。'
                'A 规模/形状（525 条分账 · priority 4000~4524 连续 · 两端已登记 · 无自环 · '
                '**同场景同字母唯一** · shift 只含 {−2,−1,1,2} 与 9 个已实证对象）· '
                '★★B **独立重算**：另一套实现（手工括号配对，不用生成器正则）从事件源码重推'
                '282 条逐条相等（配改目标负控制 + 正控制 + 非空分母闸 + '
                '★**继承链生效自证** + ★**条件房间被识别**）· '
                'C 与 objects 双向相等（1,233 组 / 1,655 条 / 274 场景）· '
                'D 产品行为（`obj_doorB`→room_area1 / 撤掉 `when_src` ⇒ 0 扇）· E 防回滚 · '
                'F 自检。'
                '★★ 明确不做：`obj_elevatordoor` 是电梯 UI（`event_user(0)`）不是门位移；'
                '`Alarm_2` 里 `if (...)` 条件点名的房间不套通用位移'
                '（`obj_doorA` 在 `castle_prebarrier` 走 `global.flag[7]` 分叉）。'
                '★ 零 Qt、零外部盘（只读仓库资产 + 第115轮蒸馏进仓库的 TSV + 本轮事实 JSON）。',
    },
    {
        'id': 'check124',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第124轮-桌面门落点与可达性', '_tools',
                               'check124.py'),
        'desc': '第124轮：**桌面 C 门（UT）落点写错** —— 写的是 `ut.rooms.room_start`，'
                '而那是原作**下标 0 的空壳/标题房**（无门、无物、出边 0）⇒ 从桌面进 UT '
                '只能站着不动，**整个 UT 一间接不到**（实测可达 1 间）。'
                '真正的"人类坠落的地方"是 `room_area1`（原作下标 **4**，出边 1）。'
                '★ 根因不是路由条数不够（ut 已有 525 条门路由），而是**入口选错了一间房**；'
                '更关键的是 122 套件里**没有一条判据问过"从桌面出发能走到几间"** —— '
                '所有锁都在看"表里有没有这条边"，没有一条看"人能不能走到"。'
                'A 落点（4 条逐条等于口径 · C≠room_start · **目标出边必须 > 0** · '
                '★**落点真能画出来**（`load_scene` 产品真路径 → `bg/ut_room_area1.png` 4,751 B）· '
                '带 `obj_readable_flowers1`）· '
                '★★B 可达性账（桌面并集 215 = A160+B6+C33+D22 · 每扇门 > 1 · '
                '★**负控制：C 换回 room_start ⇒ ut 只剩 1 间、总可达恰好少掉 UT 那 32 间**，'
                '直接复现缺陷 · 守恒账）· '
                'C 空壳房负向锚（4 间出边全 0 且不在任何 `to` 里 · '
                '★**原作下标 0~3 恰好就是这 4 间**、`room_area1`=4）· '
                'D 密度账（每作品"有出边场景数"只增不减 · 唯一边 1526 + 5 条合法重复 = 1531，'
                '且每个重复组内**门标识两两不同**）· '
                'E 自检。'
                '★★ 顺带纠正一条**一直绿的错判据**：`check89.B4c` 把 UT 落点期望下标写成 0 —— '
                '它和 `B4b` 共享同一个错误假设（B4b 写 `room_start`、B4c 期望 0），'
                '**两条判据互证 ≠ 独立验证**。已改为 4。'
                '★ 零 Qt、零网络、零外部盘（只读仓库资产、走产品 `load_index`/`load_scene`）。',
    },
    {
        'id': 'check125',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第125轮-D门与X门补齐', '_tools', 'check125.py'),
        'desc': '第125轮：Deltarune 五章的 **D 门（−2）** 与 **X 门（表驱动）** 补齐。'
                '★ 根因不是"没数据"：`_room_graph.json` 里 ch1~ch5 有 **782** 条边，'
                '产品只转出 **443** 条 —— 差在**门型**（第44轮只编 A+1/B−1/C+2，'
                '并以"证据不足"拒收 `obj_doorD`/`obj_doorX`）。'
                '★★ 第44轮拒收 D 的理由"实测 +2 只有 33%"是**测错了位移**：'
                '`obj_doorD` 的 Alarm 是 `room_goto(room_previous(room_previous(room)))` = **−2**。'
                '★ 用第44轮对 A/B/C 的**同一条判据**独立复核（目标房必须含 '
                '`obj_marker<同字母>`）：D **71/74 = 95.9%**、X **94/94 = 100%**、'
                'W **0/97**（marker 实为小写 `obj_markerw`：60.2%；`obj_markerX` 84.3% '
                '⇒ 两套都到不了 100%，**W 仍不收**）。'
                '⇒ 追加 **139 条**（D 56 / X 83，priority 5000~5138），'
                '五章「有出边场景数」105/127/23/22/20 → **116/137/35/32/31**（+54）；'
                '桌面可达 199 → **215**。'
                'A 段位与分母（139 条 · priority 连续 · 只落 ch1~ch5 · 章内下标单射）· '
                '★★★B 独立重推（**只从证据重算**这 139 条，不读生成器决策字段；'
                '集合相等 · 挖一条/塞一条各判一次 · 丢弃账 782 = 139+20+507+98+15+3）· '
                'C 逐条自洽（D 的 −2 / X 的查表值 / marker / `name_raw` / 声明序；'
                '★负控制：D 的 `room_delta` 写 +2 必红）· '
                '★★D 拒收纪律（产品 **0 条** W 门 vs 证据**确有 98 条** —— 成对，防空集恒真）· '
                '★E 3 条 `no_marker` 例外有账（真值是 `ch2 263→261` / `ch2 55→53` / '
                '`ch4 34→32`；**我最初按印象写错了**，被这条判据当场纠正 —— '
                '`ch4 90→88` 属"端点未登记"不是"无 marker"，见 E4）· '
                'F 密度只增不减 · G 自检。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内证据与资产）。',
    },
    {
        'id': 'check126',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第126轮-门型收口', '_tools', 'check126.py'),
        'desc': '第126轮：**outertale 的门**（244 个场景、0 条路由 ⇒ 整个作品"看得到、'
                '走不通"，`plan_route_to` 在那个作品里一条边都拿不到）。'
                '★ 根因不是"没数据"：第115轮已经从 `game.droid` 抽出 **301** 条 '
                '`room_goto`（`conn_ut.json`）+ **358** 间房的实例表（`inst_full.tsv`），'
                '只是没人把它变成产品能读的边。'
                '★ 推导三类（机制 + **在场**两条独立证据）：`ot_door_guard` = '
                '`if (room == N) room_goto(M)`（★ 独立验证：那扇门**真的摆在 N 这间房**的'
                '实例表里 —— 等价于 Deltarune 的 `obj_marker`）；`ot_door_shift` = '
                '`room_goto_next()` ⇒ 每个实例房 r → r+1（第123轮 ut 同型）；'
                '无条件 `room_goto(M)`（src 未知）**丢**。'
                '⇒ 写入 **209 条**（guard 93 / shift 116，priority 6000~6208），'
                '覆盖 **162** 个源场景、并集 **204/244**；'
                '★ **两层同时喂**：`_routes.json` 1531 → **1740** 条，'
                '`_room_graph.json` 补 `chapters.outertale`（1,202 → **1,411** 边，'
                '逐门寻路 `plan_route_to` 读的是这张图）。'
                'A 段位与分母（209 条 · priority 连续 · 只落 outertale · `when_door` 全 None）· '
                '★★★B 独立重推（**另写一份推导**，不 import 生成器；集合相等 · '
                '挖一条/塞一条各判一次 · 丢弃账 28/24/54/1 与生成器一致）· '
                'C 逐条自洽（guard 的**在场**互证 / shift 的 `dst == src+1` / 端点已登记；'
                '★负控制：把源房换成"没摆这扇门"的房间必红）· '
                '★★D 拒收纪律**四对**（28 条无条件 / 24 条守卫与实例打架 / 1 组按坐标分叉 / '
                '62 条端点未登记 —— 每一对都是"证据里真有、产品里 0 条"）· '
                '★★E 两层同一集合（图里的边 == 路由新段）+ 冻结章逐章等值（ch1~ch5 + oneshot）· '
                'F 密度 0 → 162（只增不减，且**如实**登记覆盖并集 204 < 244，不假装全通）· '
                'G 自检（★`check` 的 args[1] 与 `ok` 的 args[0] **两套 harness 都查**）。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内证据与资产）。',
    },
    {
        'id': 'check127',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第127轮-训练偏好解析', '_tools', 'check127.py'),
        'desc': '第127轮：NPC「他想去找谁」的**名字消歧**不许再漏（用户口径'
                '「训练这类的也要抓一下」）。'
                '★ 训练线接线逐环实测**没有断的**（96 角色覆盖齐：77 AI + 18 内置台词 + '
                '`knight` 沉默；`patches` 59 条进 system prompt；`_seek.json` 72 人进决策）——'
                '真缺口在**数据被白白丢掉的那一段**：`unresolved_names` 里 4 条 '
                '`Asgore（ambiguous）` 其实解得开。'
                '★ 根因（`gen_seek113p.pick_id`）：「登记名以该名字开头」第三档被写在 '
                '`if not cand:` 里 ⇒ 只有精确档**零命中**才启用；而 UT 那个 Asgore 的登记名是 '
                '**`Asgore Dreemurr`**，精确档只拿到 Deltarune/outertale 两条，'
                '同作品候选为空 ⇒ 被判 ambiguous 丢弃。'
                '⇒ 修法：同作品候选为空时再兜一次别名档、**且只收同作品那一条**；'
                '跨作品同名（`Sans` 在 ut_/ot_ 各一条、源无前缀）仍丢弃 —— '
                '猜错等于把 A 的偏好挂到 B 头上（第113轮p 原始教训）。'
                '★ 影响面先量化再动手：`raw30` 全部 **477** 个 (名字, 源) 对上跑新旧两版，'
                '差异 **8 条、全部是 `ut_*` → `ut_asgore`、零倒退、零自指**。'
                '结果：`_seek.json` 条目 189 → **193**，既有 189 条逐字段一字未改，'
                '`formula` 未动。'
                'A 现场（8 个 ut_* 源真跑 `pick_id`）· B 拒猜纪律（跨作品/名册外/非人条目；'
                '★B1 首跑报红，**红的是我的断言**：无前缀源提 `Asgore` 本来就该落 `asgore`，'
                '真正该守的是"不许被别名兜底带到 ot_/ut_"）· C 数据面（4 条真在、'
                '`why` 原句真的提到 Asgore、自指零、仍被拒的 `Sans`/`Undyne` 还在）· '
                '★★D 破坏性负控制（把别名兜底拆掉重算 ⇒ 4 条必须消失；`ot_toriel` 换一部'
                '作品也成立，排除硬编码 ut；别名档**只有一份实现**）· E 自检（AST 恒真 + 无 BOM）。'
                '★ 零 Qt、零网络、零外部盘。',
    },
    {
        'id': 'check128',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第128轮-结巴率收敛', '_tools', 'check128.py'),
        'desc': '第一百二十八轮：**"起头结巴"收敛**（用户口径「这个结巴要少一些，'
                '100 句里出现 2 句就够了」，收口后又补一句「继续，当然，**不能为 0%** 啊」）。'
                '★★★ 先纠正自己的假设：按"重复字"型结巴去量，真机 50 条里 **0 条**；'
                '可同一批回复里 **26/50 = 52%** 开口先垫「嗯……／诶？」—— '
                '用户听到的"结巴"是**句首那口气**，不是叠字。照原假设改文案，指标不会动。'
                '★ 根因是三处"每句配额/示范"式指令（都在我们自己的文案里）：'
                '人设「最多沾一两处」「开口有时会带个语气词」「一时没准备好 → 起音含混」＋ '
                '`nervous_brief` distrust 档「会重复一两个字、会突然停住」「一条回复里最多'
                '带出一处磕绊」。7B 把"最多一处"读成"我说话要磕一下"。'
                '★ 第一版修法两层：提示词删许可/示范（52% → **4%**）＋ '
                '`event_speech.strip_head_hesitation` 只削句首那一簇（用户可见 **0%**）；'
                '两处（收尾护栏 0d + 流式 `_sanitize_partial_reply`）**共用同一个函数**，'
                '且该步**前缀安全**，流式不会"先打出来再擦掉"。'
                '★★★ 但用户说"不能为 0%" ⇒ 第一版**过头了**（一句也不结巴不像人）。'
                '于是把护栏从"全削"改成**节流闸**：`HES_ALLOW_GAP = 50` + `_hes_gap`，'
                '**每条回复 +1**、只有"放行且真留下一条带停顿的卡壳"才归零 ⇒ '
                '上限 1/50 = **2%**，下限 = 模型自然产出（**不做假卡壳**）；'
                '闸门必须在 `_ask` **之前**定（流式层在请求过程中就已把字打到屏幕上）。'
                '★ 第 5 臂实测（100 条，中性人设 + brief 条件式许可）：句首迟疑 17（17.0%）、'
                '**带停顿 12（12.0%）**，节流模拟后可见 **2/100**。'
                '★ 归因靠对照：双许可 12.1% vs 单许可 12.0% ⇒ **`brief` 才是决定项**，'
                '人设那句只是雪上加霜；且人设有体积闸（塞进去 10,067 B ⇒ K3 报红），'
                '所以人设那句改**中性**、许可只留 brief。'
                '★ 7B 对"只有/偶尔"这类频率副词几乎没有分辨力（写"只有那一下"仍产 12%）'
                '⇒ **频率不能交给提示词**。'
                'A 四档文案不许有配额句/指令式示范、紧张度数值一个没动 · B 人设起头纪律**中性**、'
                '许可只落在运行时 `nervous_brief`（B4b 条件式 / B4c 有封顶 / B4d 无次数）、'
                '体积没被砍瘦 · C **从 200 条 + 100 条原始回复重算**（五臂，不读汇总表）：'
                '基线 52%、第一版 4%、改回许可 12%、子类带停顿 12/100、节流模拟 ≤2 且 ≥1 · '
                'D 负控制（改前原文喂同一批判据必须报红）· E 护栏行为（只削头＝结果是原文后缀、'
                '反例原样返回、前缀安全**削与放行两种模式都穷举**、放行不是"放行了个寂寞"、'
                '两处接线、发请求前设闸、收尾层结算额度、单一真源、默认关）· F 自检（AST 恒真 + 分母）。'
                '★ 零 Qt、零网络、零外部盘；证据 `_evidence/raw/*.jsonl` 四臂各 50 条 + 第 5 臂 100 条。',
    },
    {
        'id': 'check129',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第129轮-复读与出戏', '_tools', 'check129.py'),
        'desc': '第一百二十九轮：**复读（车轱辘话）与出戏** —— 三处毛病，全是判据自己的错。'
                '★★★ ① 车轱辘话判据对短句**误伤 8/12**：`ratio ≥ 0.82` 在 8~10 字的中文短句上'
                '太敏感（「我想和你一起走」vs「我想和你一起看」= 0.857），而这类短句正是 Ralsei '
                '最常见的台词 ⇒ 判重复 ⇒ 整句作废 ⇒ 白重采样（体感是卡顿或回落罐头）。'
                '修法：**12 字以下只认"去标点后逐字相同"**（零误伤），12 字以上才用相似度；'
                '顺带补上"逐字复用"这条（旧判据因入口 `len(t) < 6` 把它整条挡在门外 —— '
                '是 A5/A6 两条判据抓出来的）。实测：误伤 8/12 → **0/12**，"长句改两三字"仍 **6/6** 全拦。'
                '★★★ ② 出戏闸的裸词 `机器人` **回退了**：第115轮对注册表全量 96 位各真发一次请求'
                '才发现 OneShot/UTY 有 **4 位角色本身就是机器人**（os_kelvin / os_rowbot / '
                'os_prophetbot / hy_sousborg），裸词把他们一律判退且重采样救不回来；'
                '当时代码确实删过（`ai115_oocfix.json` 记 `patterns_n: 19`），**但没提交、'
                '`check115` 也没进 SUITES**，本轮扫描时词表又是 20 条 —— "工作区会被回滚而 git '
                '不报错"的又一实例，根因是**守卫没登记**。⇒ 恢复 + 本套件接管这条守卫。'
                '★ ③ 出戏闸漏「只是」系变形（`我只是一个程序` 旧表拦不住）+ 裸词 `首先` 误伤'
                '正常口语（「首先我得谢谢你」被整句作废）⇒ 补变形、删 `首先`（设计意图是'
                '"首先…其次…总结一下"整套，留后续分点词即可；代价"只首先不分点"会漏，已登记）。'
                'A 复读判据（**AST 抽产品函数真跑**，不复制）：阈值可读 · 活性闸 · 短句误伤归零 · '
                '长句照抄不漏 · 逐字复用能拦 · 只差标点也拦 · **破坏性负控制**（门槛打回 0 ⇒ '
                '短句组必须重新误伤 8/12）· 空 recent 返 False · A/B 先断言不同 · '
                'B 出戏闸（无裸词 `机器人` · 4 位机器人自我介绍全放行 · 真出戏仍全拦 · '
                '"只是"系变形必须拦 · `首先` 不在表里 · 分点仍拦 · 正常口语不误伤 · '
                '**摘掉「其次」的破坏性负控制 + 原样恢复自证**）· '
                'C 探针同步（`verify_persona_worldview` 的复刻判据与产品**逐条等价**，'
                '且门槛数字从产品源码抽取、不另写一个 12）· D 自检（AST 恒真 / 分母 / 零外部盘）。'
                '★ 零 Qt、零网络、零外部盘；证据 `_evidence/probe129.json` + `report129.md`。',
    },
    {
        'id': 'check115',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第115轮-AI人味训练', '_tools', 'check115.py'),
        'desc': '第一百一十五轮（第130轮补登记）：**「他们知道自己是游戏，但并不对此感到悲观」**'
                '—— 用户原话，指的是复数（Ralsei + 76 位 NPC）。'
                '★★★ 这套判据写了半年、跑了半年，却**从来没进过 `SUITES`** ⇒ 它守的东西'
                '在 2026-10-28 之后整体消失，没有任何人收到通知。第130轮取证：那轮的产品改动'
                '（人设四节 + `_PERSONA_FALLBACK` + 76 份 NPC 尾块）是在一个**独立 worktree** '
                '里做的（`_evidence/verify115_files_out.txt` 首行写着 '
                '`Worktrees\\try - 副本\\main-a7556e9c\\...`），从未合并回主工作区；'
                '`git log -S` 对四个锚句全部返回空。只有 `_tools/` 与 `_evidence/` 被复制了回来，'
                '于是判据报红 9 条而无人看见。⇒ 本轮把产品侧补齐，并**把本套件登记进来**。'
                'A 人设结构（11 节标题 · 世界观节同时写"知道是角色"与"不悲观" · '
                '记忆节的对照写法"判法只有一条 + 而不是…" · 治"那边引力"的**正文**锚'
                '〔锚点必须取正文独有句，取标题会被标题喂饱 —— `mutate115 M4` 抓的〕· '
                '寻路"我带你过去要落在具体地方" · 禁 markdown · LF/无 BOM）'
                '· A8~A11 正负控制（删节报缺 / 塞 `**` 必真 / 抹对照必假 / 干净原文 A6 为假）'
                '· B 兜底人设（AST 取 `_PERSONA_FALLBACK` 单常量 · 已同步"是被人写出来的" · '
                '★ 保住 J1 钉的 `不用叫他`/`仅此而已`/`平级`）'
                '· C 两条路径不许劈裂（兜底讲的那层，真源里也必须有）'
                '· C2 NPC 76 份共用尾块（`_personas.json.tail_text` 是真源 · 不点名任何作品 · '
                '76 份逐字节相同 · 尾块 LF 而正文 CRLF · `tail_sha256` 自洽 · 5 个记账字段重算全中）'
                '· C3 出戏闸（无裸词 `机器人` · 4 位机器人放行 · 真出戏仍拦 · 客服腔那道闸未被波及）'
                '· D 自检（记账 · 无恒真判据 —— 走 AST 查 `check()` 第二实参 · 负控制）。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内人设与资产）。',
    },
    {
        'id': 'check113p',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113p.py'),
        'desc': '第一百一十三轮p：**NPC 之间互相寻找** —— 用户口径「npc 之间寻找偏好'
                '也要有哦」。修两件事：① `_pick_friend` 的**假目的地**（挑中了人、'
                '却走向随机地点；根因是宿主 `[(i, f) for i, f, _s in ...]` 把"那人在哪"'
                '丢掉了）；② 「他想找谁」偏好层（`assets/npc/_seek.json`）。'
                '★ 偏好数据**只用角色自己说过的话**：`raw30` 训练记录里'
                '「问句没点名、回答里却主动提到他」的行为频次（+ 关系段明说'
                '「想见/陪着」抬、"躲着/闹翻"降）。**不请模型二次判读、不把 '
                '`relations` 列表当偏好、不收「喜欢/在乎」这类宽词**。'
                'A `npc_seek` 纯函数：切句不切逗号；两道守卫（同句指向；**问句回声不算** '
                '— 剧本有「如果有一天你和 X 彻底闹翻了」，回答里的「闹翻」是复述题目，'
                '第一版没这道闸就把 berdly→kris 扣到 0.70）；权重单调 + 钳位 + 坏输入不抛。'
                'B `extract`/`rows_of` 合成夹具真跑（指名 / 主动提及 / 正负 cue 分开数），'
                '`id_of` 返 None 时**保留原名**不猜。'
                'C 登记表：结构合法、双方 id 都落在 `_registry.json`、**不许自指**、'
                '权重在区间内、覆盖率用**只增不减**的下界。'
                'D AST 接线（禁纯文本扫）：`decide()` 真带 `seek=` 与 `friend_scenes=`，'
                '值分别来自 `self._npc_seek_weights(...)` / `self._npc_friend_scenes(...)`；'
                '`_npc_friend_scenes` 真读元组**第三元素**。'
                'E 行为：默认参数与**旧实现逐值相同**（400 个种子逐条对照 + 600 拍 '
                '`seek` 全 1.0 完全相同）；给 `friend_scenes` ⇒ 目的地就是那人所在地；'
                '不可达时如实标 `visit_friend_away`（不把回落伪装成成功）；'
                '给 `seek` ⇒ 被偏爱者被选中次数真的变多。'
                'F 破坏性负控制：拆 `scenes` 分支 ⇒ 目的地回到随机；把 `_seek_mul` '
                '打回恒 1.0 ⇒ 与默认结果完全相同，装回去后差异重现。'
                'G 脚本自检（语法 / 无 BOM / 行尾不混 / 无恒真判据 + 正控制）。'
                'H ★★★ 宿主熟络度 API 活体核对（本轮真正卡住「互相寻找」的那一环）：'
                '`main._npc_roam_friends` 原来调 `bonds.familiarity(...)`，而 '
                '`npc_life.Bonds` **没有这个方法** —— `AttributeError` 被 '
                '`except Exception` 吞成 `fam=0.0`，再被 `if fam <= 0: continue` '
                '滤掉 ⇒ **`friends` 对每个 NPC 恒为 `[]`** ⇒ `visit_friend` / '
                '睡朋友家 / `npc_seek` 权重全部无声失效（`check78` 的 E/F 段喂的是'
                '**合成** friends，正好绕过这条链，所以一直全绿）。判据：H1 '
                '`bonds.<方法>()` 的每个方法都必须是 `Bonds` 真有的（并**要求非空**，'
                '`all([])` 恒真）+ H1n 把 `bonds.get(` 变异回 `familiarity(` 必须判红 '
                '+ H2 `get` 的 0.0 / >0 两种取值都真能出现 + H3 '
                '`_npc_roam_friends` 交出的**三元组**第三项是 `scene` + H4 '
                'Deltarune 章站位覆盖 ≥30 人（防回滚丢数据；跨作品 0/61 是**已知'
                '数据缺口**，只记录不判红）。',
    },
    {
        'id': 'check131',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第131轮-真机7题复测', '_tools', 'check131.py'),
        'desc': '第一百三十一轮：**真机 7 题复测** —— 第130轮补回来的那四节到底有没有用。'
                '★★★ 第130轮把第115轮丢在 worktree 里的人设四节取回来了（「我是什么」/'
                '「他说话的时候，先把他的事接住」/「他说要去一个地方的时候」/「我想起来的事」），'
                '但报告 §7 第 3 条明写着**真机没复测**：恢复的是当年 A/B 有据的文案，'
                '本轮没重发过请求。本轮补这一刀：同一模型（`ralsei:v4`）、同一批 7 题原文、'
                '同一段尾部（【此刻】+ 关系段/紧张段走 `modules/relationship.py` 真源 + 回忆 + 历史），'
                '只变 system 里的人设正文 ⇒ **before = `git show edae364^:…ralsei_persona.md`**'
                '（7 节 / 3,606 字符，四节不在）vs **after = 磁盘现值**（11 节 / 4,494 字符）。'
                '★★ 两处刻意设计：① **题序交错**（按题循环、两臂交替，抵消"跑得越久越热"的'
                '单调漂移，不是一臂跑完再跑另一臂）；② **先热身 2 条丢弃**，不把冷启动差异'
                '算到人设头上。★★★ 试跑一次就暴露了一个**量错了东西**的坑：Q7 的 before 组'
                '是「整句躲开」（「你说的是坏消息吧…那件事具体是怎么样的？」），'
                '产品护栏当然不报红 —— 用 OOC 命中数去量"它认不认"，等于**用空集证明没问题**；'
                '于是补 `role_ack`（承认这层身份）与 `asks_where`（把问题问回去，只作观察量）。'
                'A 六个旗标正负控制成对，且**负控制必须真落进被测分支**（`confab` 的负控里'
                '"豆豆"与 ADMIT 同时在场，否则 False 可能只是"没提豆豆"的空跑）· '
                'B 证据形状（2 臂 × 7 题 × N 采样、每格分母满、无 error/空回复、两臂问句逐字相同、'
                '★ **两臂差的正好是那四节**：after−before 的节名集合 == 四节且无缺失）· '
                'C 探针自检（`flags()` 复用 `probe115ab.extra_flags` ⇒ side/pushback/admit '
                '**只有一份实现**；基线来自 `git show` 不是手抄；回复取自 HTTP 响应不是常量）· '
                'D 自检（AST 查恒真判据 · 分母 · 零外部盘 · 夹具规模）。'
                '★★ 本套件**不把方向性结论写成判据**：真机输出会变，写"after 一定赢"就是'
                '定时炸弹，结论留在报告里、附原始回复全文。'
                '★ 零 Qt、零网络、零外部盘（只读 `_evidence/` 里冻结的那 42 条记录）。',
    },
    {
        'id': 'check132',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第132轮-提示词泄漏护栏', '_tools', 'check132.py'),
        'desc': '第一百三十二轮：**元话语泄漏**（把提示词规则当台词念出来）—— 第131轮真机 42 条里'
                '抓到 3 条，形态三种：① 把规则改写成第一人称自述（「你说的是坏消息的时候**我不该用'
                '亮起来的开头**，先就着那件具体的事问一句」）；② 直接引用模板（「**先就着你说的那件事'
                '问一句：**"这么说，你是觉得……"再留个"我在"的意思」）；③ 括注里自评合规'
                '（「（**这里说的是你自己的事，而不是直接给出建议**）」）。三处都是把人设「语气示范」'
                '第 136/147/148 行的编号规则改成第一人称念出来'
                '（★ 第138轮：这几个行号随人设文件漂，留着只会误导，已不再作为定位依据）。★★★ **本轮最重要的是一条负结论**：'
                '**重合度判不了这件事** —— 先试过"回复与 system 的最长公共子串 / 6-gram 重叠"，42 条里'
                '`lcs_flat` 最高的是 **17 和 13**，而那两条**都是正常好答案**，真正的泄漏只有 **10**；'
                '原因很朴素：人设本身就在讲"城堡/喷泉/角色/Deltarune"，好回复用同一批词。'
                '⇒ 用重合度当判据会**误伤说正事、漏掉念规则**，所以闸门按**元语言的结构特征**判'
                '（每条规则都要求"两件事同时出现"或"带冒号/引号/括号"这种强格式，避免'
                '「我昨天不该说那些话的」「（这里有点暗）」这类正常台词被误伤）。'
                'A 真实数据（131 的 42 条）：**那 3 条必须命中、其余 39 条一条不中**（n=39 负样本）· '
                'B 构造样本：5 条规则**逐条**都有命中例（防"正则写错了没人知道"）＋ 12 条刻意踩着'
                '规则边角的正常台词必须全放行 · C 历史大池（128 的 300 条真实回复）**0 命中** · '
                'D 接线（AST）：import 了、与另外两道闸**在同一个 if 里**、命中即 `return None`'
                '（走既有重采样，不是直接沉默）· E 自检（AST 恒真判据 · 分母 · 零外部盘 · '
                '`event_speech` 不 import 项目内模块/Qt · 把规则表清空必须让那 3 条全部失效的正控制，'
                '做完原样恢复）。★ 零 Qt、零网络、零外部盘。',
    },
    {
        'id': 'check133',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第133轮-事件台词元话语核查', '_tools', 'check133.py'),
        'desc': '第一百三十三轮：**事件台词链也装上元话语闸**，并钉住一条否定结果。'
                '第132轮的 `looks_like_meta_leak` 只接在**对话**链（`_clean_ai_reply` 第 0c 道），'
                '而事件台词走另一条链：`chat_with_ai(..., lean=True)` ⇒ system **就是整份人设**'
                '（`main.py` 的 lean 分支：只发 persona 全文 + 那块常量训练纠正 —— '
                '★ 第138轮：原文这里写的是"14171 行「只发 persona，一个字节都不变」"，'
                '行号会漂、说法也已被第137轮改正，一并去掉）⇒ `guard_reaction('
                'first_sentence(reply, 24))`。两条链共用同一个人设，却只有一条装了闸，这道不对称'
                '本身就是漏洞（第128轮的教训同型：同一道闸不许只在一条链上生效）。'
                '★★★ 但本轮真机采的 **42 条**（14 个 TIER_AI 事件 × 3 采样）`meta_raw`/'
                '`meta_first`/`meta_final` **全部 0/42**，平均首句只有 **7.4 字**；把第131轮那 3 条'
                '**真泄漏**按产品口径截到 24 字再喂给闸，**3 条一条都命中不了**（"…我不该"/"…先就着"'
                '被截在半句上）⇒ 两条结论一起登记：① 24 字上限**本身就压掉**了这次观测到的形态；'
                '② 「照搬对话链做法、对截断后文本判」**救不了那 3 条**。所以本轮的装闸理由是'
                '**结构对称 + 显示窗口**（24 字内仍容得下「我不该用亮起来的开头」这种整句自述），'
                '**不是**"修了一个观测到的 bug"，报告里不许写成"实测有效"。'
                'A 真实语料（42 条）：0 命中 · 加闸后输出**逐字不变**（回归判据，不是效果判据）· '
                'B 截断效应（那 3 条 0/3 命中，且确认真的被截短过）· '
                'C 闸的行为：三种形态全判退（**正控制真落进被测分支**）· '
                '★★ C4 是**判据自纠**：第一版写"剥括号后就不命中 ⇒ 闸必须排在 strip 之前"，'
                '实测 `strip_action_parentheticals` 对「（这里说的是你自己的事…）」这种**合规说明'
                '根本不删** ⇒ 这一形态对顺序不敏感，改成"登记事实 + 两处同判"，产品注释里的'
                '「硬约束」也一并改正（别把假断言留在代码里）· '
                'D 不误伤：42 条真机输出全放行 + 12 条踩边角短反应全放行（第一版把「（这里有点暗…）」'
                '当负样本 ⇒ 报红，红的是样本：那条本来就被老闸 `looks_like_narration` 拦）· '
                'D3 破坏性负控制：清空规则表 ⇒ C1~C3 全部失效（第一版把断言方向写反了，'
                '「仍判退 3/3」才是恒真）· E 接线（AST）：两条链调的是**同一个函数**'
                '（第一版只看 `tree.body`，漏掉类方法 `_clean_ai_reply` ⇒ 改递归）· F 自检。'
                '★ 零 Qt、零网络、零外部盘（只读本轮冻结的 42 条记录 + 第131轮的 42 条）。',
    },
    {
        'id': 'check134',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第134轮-训练线收口', '_tools', 'check134.py'),
        'desc': '第一百三十四轮：**训练线收口** —— 把"登记了没人读"这条老坑钉在训练产物上。'
                '113 轮起陆续落了四类产物（人设 76 份 · `patch` 59 人 · `relation` 58 人 · '
                '`evolution` 44 人），它们都由 `npc_persona.build_system_prompt` 拼进 system，'
                '但**没有任何判据守着这条接线**：`check113 C2` 只用一条**合成** patch 验证'
                '"传进去就会进 prompt"，把 `main.py` 的 `patch=npc_persona_mod.training_patch(...)`'
                ' 整行删掉，`check113` 照样全绿。'
                'A 数据面（96 条目 / 78+18 / persona 三态 76+1+19 / 96 张卡 / patch 59 全 main / '
                '`_index.counts` 对账 / gaps=[knight] / `_seek` 72+24，四个数从磁盘数出来）· '
                'B 端到端**真跑** `build_system_prompt`：进链的 58 条 patch / 57 条 relation / '
                '44 条 evolution **逐字**进 prompt，且没有卡的角色**一个块标题都不许出现**（成对负控制，'
                '分母 18 / 19）· **B5 第一版是恒真判据**：`_other_leak` 用 `nid not in REL` 过滤，'
                '而 `REL` 是**全 96 个 id** 的字典 ⇒ 永不为空 ⇒ 这条"守"其实没守，改成 `REL_IN` 后'
                '才真的能红 · C 接线（AST）：三个关键字实参在、值分别来自那三个函数，'
                '**破坏性负控制**（删掉 `patch=` 那一行 ⇒ 同一判据必须报缺）· '
                'D 空人设短路（`persona=""` ⇒ 返回 `""`，连 patch 也不拼；正控制证明不是"永远返回空"）· '
                'E `Twinkly` 结案：目标卡登记名是「Asriel Dreemurr 与 Twinkly」**两个人合一**、'
                '且已有 5 条出边 ⇒ 接它等于把两人当一人，本轮不接的理由钉在数据上 · F 自检。'
                '★★ 本轮**新发现的真缺口**（按现状登记，未改产品）：`patches["ralsei"]`（160 字，'
                '"不要自己造人名"那条）在链上**零读取** —— 他有卡，但 `load_personas()` 收的是 '
                '`_personas.json` 那 76 份游戏 NPC，不含主宠；而 `chat_with_ai` 把 '
                '`speaker == "ralsei"` 直接判成老路径 ⇒ `npc_system_prompt()` 永不服务他。'
                'B0b/B1b/B1c/B1c2 四条把这个状态**显式钉住**（含"把 `ralsei` 这个字面量全替掉后 '
                'B1c 必须报红"的破坏性负控制），所以谁哪天接上了会红 —— 逼人回来复审，而不是悄悄多读一条。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内的 registry / 索引 / 人设文件）。',
    },
    {
        'id': 'check135',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第135轮-事件截断吊尾巴', '_tools', 'check135.py'),
        'desc': '第一百三十五轮：事件台词的截断不许**吊尾巴**（修第133轮登记的遗留 1）。'
                '病根：`event_speech.first_sentence()` 原来按标点**类型**优先级挑切点'
                '（`。`→`！`→`？`→`!`→`?`→`\\n`，看哪个类型先出现在文里，再用它的第一个下标），'
                '于是"第一句是问句、后面某句有句号"时，切点被推到**后面那句的句号**上，'
                '再硬截 24 字 ⇒ 截在半个句子上，原样显示成坏台词。真机证据（第131轮 3 条元话语泄漏里的 2 条）：'
                '`你说的是坏消息吗？\\n\\n你说的是坏消息的时候我不该…` 旧输出 24 字吊在"我不该"，'
                '新输出 `你说的是坏消息吗？`（9 字，完整）。'
                '★★ 修法**不是**"取最靠前的句末标点"——第一版就是这么写的，'
                '被 `s7_event_speech A11` 当场判红（它把「诶？！好舒服呀。后面还有好多话要说呢。」'
                '整句留下了）⇒ **"句号 = 一个想法结束了"这条语义不能丢**。最终三条分支：'
                '① 有句号 ⇒ 只在"句号及之前"的切点里挑第一个够长的，都不够长就用句号本身；'
                '② 没句号 ⇒ 只看第一个句末标点，够长就切、太短就整句保留（「哎呀！别捏我的耳朵！好痒呀！」'
                '三个短感叹连起来才是一句反应）；③ 没句号+太短+全文超上限 ⇒ 切（保持改造前行为）。'
                'A 真机回归：42 条事件回复**逐字不变**（对照第133轮冻结的 first 字段；它们是回归判据，'
                '不是效果判据）+ 开头加一句的正控制 · B 修复效果：3 条真泄漏输出干净'
                '（B2 先断言"旧实现下确实有 2 条吊尾巴"、B3 断言新旧结果不同、B5 断言能过 `guard_reaction`）· '
                'C 规则面 8 条（其中 5 条是 `s7_event_speech A9/A11` 的**既有契约**，改实现不许丢）'
                '+ want 写错一个字的正控制 · D `MIN_FIRST_CHARS` 语义保住（「嗯？发生了什么吗？」不许切成 2 字）· '
                'E 不变量：45 条语料里 0 条顶格吊尾巴（分母非空）· F 接线（AST：`main.py` 仍调 '
                '`first_sentence(reply, self.EVENT_SPEAK_MAX_CHARS)`）· G 自检。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内的两份真机记录 + 产品源码）。',
    },
    {
        'id': 'check136',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第136轮-截断单一真源', '_tools', 'check136.py'),
        'desc': '第一百三十六轮：**截断规则单一真源**（自主开口那段不再自己写一遍）。'
                '病根：`main.start_autonomous_speech._on_reply` 里有一段**自己写的** 8 行截断'
                '（`for sep in (\'\\n\',\'。\',\'！\',\'？\',\'!\',\'?\')` + `if len(text) > 40: text = text[:40]`），'
                '与事件链的 `first_sentence()` **从来就不是同一份**（sep 顺序不同、一个换行优先一个句号优先、'
                '一个有 MIN 规则一个没有）；旧注释写的"同源"是假断言，第135轮已改正、第136轮删掉那段。'
                '★★★ 怎么做：先量三条路（`_tools/diag136.py` / `diag136c.py`）—— 口径是 **84 条真实 AI 回复**（第131轮真机 42 + 第133轮事件 42；diag136 另加 14 条构造样本覆盖边角，不混着报）：旧内联**吊尾巴 10 条**、平均 16.2 字；'
                '换成 `first_sentence(t, 40)` 吊尾巴 0 条但 **9 条砍掉后半句**、平均 12.5 字；（旧 vs first 共 20 条不同：10 条修掉吊尾巴、9 条变短、1 条其余；fit 比 first 多 33 条不同，其中 32 条多留一整句、平均 +6.2 字。）'
                '`fit_sentences(t, 40)` 吊尾巴 **0 条**、平均 18.6 字。⇒ 结论不是"合并成同一个函数"，而是'
                '**两条链各自只有一份实现、语义各自明确**：事件反应只要一句（24 字）｜主动搭话能说几句但'
                '必须说完整（40 字）。`AUTO_SPEAK_MAX_CHARS` 也收进模块（截断长度必须单一真源）。'
                '★★ 附带的两个发现：① `…` 进 `_SENTENCE_ENDS` 的依据是**实测**（对事件链 42 条真机回复 0 变动、'
                '3 条泄漏输出逐字不变、7 条既有契约全过），并在自主链上修掉一条真吊尾巴；'
                '② 连续句末标点必须一起吃（`……` / `？！`），配套 `_eat_sentence_end`。'
                '★★★ 本套件自己翻过一次车：E 段第一版拿 `fit_sentences` 处理「嗯，好吧……」这条当 `……` 的守卫，'
                '**实际恒真**（全文 6 字 ≤ 40，走"整段就是 head"那条路）⇒ 负控制把它抓出来'
                '（停掉 `_eat_sentence_end` 后 E1/E2 照样绿）。回查 `_evidence/diag136b*.txt` 才明白：'
                '`fit_sentences` 在**默认上限 40/24 上与 eat 状态完全等价**（6 个上限 × 1250 条语料，'
                '只有 max≤12 才有差异）—— 因为它挑 `ok[-1]`，而连续标点的 run-final 下标最大；'
                '真正会变的是 `first_sentence`（句号分支挑"第一个够长的切点"，靠前那个够长就会切在 run 中间），'
                '真实语料上有 **3 条**差异、方向全是 eat=on 保住 `……`。⇒ E 段改为：'
                'E1/E2 用 `first_sentence` 断，E3 是合同（不许以单个 `…` 收尾，并注明它**不是** eat 的守卫），'
                'E4 负控制（停掉 eat 必须退化成 `真的很好呀…`），E5 恢复，E6/E7 用真实语料那 3 条做正收益。'
                '★★★ 还有一条**既有契约变更**，必须显式登记：`round6_verify B7` 原来守「只取第一句」'
                '（期望 18 字），本轮改成「显示一次 + 未超上限不硬切」（期望 27 字），并新增 `B7b` 独立守'
                '原目的（超长无句点文本仍要压到 40 字以内）。理由：原注释的目的"避免撑爆对话框"已由 40 字上限'
                '保证（对话链气泡上限 220），而"只取第一句"在 84 条真机上修掉吊尾巴后只剩 10~12 字，'
                '把"追问一句"这层人味砍掉。取证 `_evidence/diag136c.txt`。'
                'A 单一真源（AST：`sep` 不再出现、魔法数 40 不再出现、改调 `fit_sentences`、import 在）'
                '+ A5 把内联形状写回去的破坏性负控制 · B 行为面 8 条（长句群 ≥30 字 / 不吊尾巴 / 短文本整句 / '
                '只有标点返空 / 无标点硬截 / 上限恒定）· C 两个函数分工不同（`fit` 不短于 `first`、两个上限是两个数）· '
                'D 84 条真实语料（D0 分母 / D1 旧内联确实吊 ≥5 条 / D2 新的 0 条 / D3 平均长度不降 / D4 上限恒定）· '
                'E 连续句末标点（含负控制与真实语料正收益）· F 事件链 3 条泄漏仍是 9 字完整句 · G 自检。'
                '★ 零 Qt、零网络、零外部盘。',
    },
    {
        'id': 'check137',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第137轮-主宠训练补丁', '_tools', 'check137.py'),
        'offscreen': True,
        'desc': '第一百三十七轮：`patches["ralsei"]` **真的**进主宠 system（修第134轮登记的"零读取"缺口）。'
                '病根：训练卡为**全部 96 位**角色各产出一条 `patch`（实测出过的毛病对应的纠正句），'
                'NPC 那边 `npc_persona.build_system_prompt()` 早就拼进 system 了；'
                '只有主宠走 `chat_with_ai(speaker="ralsei")` 的老路径，'
                '`system = self._build_persona_prompt()` 只读 persona 文件 ⇒ 那条 160 字的 patch **零读取**。'
                '★★ 这条 patch 到底补了什么（判据 B 段专门断"人设里确实没有"）：'
                '① "一次最多两三句"与人设「一次只说 1~3 句」**语义重复**（冗余无害）；'
                '② 只认原作里真有的名字（Kris/Susie/Lancer/Toriel/Asgore/Asriel/Noelle/Berdly）；'
                '③ 不要自己造人名（「凯斯恩」这种把两个名字拼起来的说法）——② ③ 在人设里**一个字都没有**。'
                '★★★ 接法：新增**模块级** `_with_ralsei_patch(system)`，在 `chat_with_ai` 与 '
                '`_prewarm_ai_cache` **各调用一次**。三条理由写在函数 docstring 里：'
                '(a) 不并进 `_build_persona_prompt()` —— 那个方法的契约是"读到的就是 persona **全文**"'
                '（`persona_chat B8` 守着），而本块是训练产出的增量、来源不同；'
                '(b) 必须是模块级函数而不是方法 —— 第一版写成 `RalseiPet` 的方法，'
                '`s7_event_speech F1` 当场 `AttributeError` 崩掉（桩只手工绑了少数方法）；'
                '(c) 预热**必须**同源 —— 否则预热喂的前缀比真实请求短 160 字，'
                '那 160 字每轮都要重新 prefill，预热白做一半。'
                '★ A 数据面（patch 在 / ②③ 在位 / 带实测例「凯斯恩」 / '
                '**① 已去重**：第139轮做了 56 条 A/B，那句无可测效果 ⇒ 已从数据里删，'
                'A1 翻面成"不许复述句数规格"）· '
                'B 人设面（"造人名"/"凯斯恩"/名字白名单三样**都不在** persona —— '
                '否则这轮的"补缺口"就是自欺）· '
                'C 行为面（以 persona 原文开头 / patch 逐字在 / 排在正文之后 / 第一人称标题 / '
                '空串与 None 不抛 / **破坏性负控制**：`training_patch` 返回空 ⇒ 尾块整个消失 / 恢复自证）'
                '+ ★ C8：打桩必须打在产品那**一个**模块实例上 —— 第一版 `import npc_persona` '
                '（`modules` 是包，`main` 用的是 `from modules import npc_persona`）会**再造一个实例**，'
                '负控制因此假绿，是 C6 报红抓出来的 · '
                'D 接线 AST（两处各 1 次、都排在 `_build_persona_prompt()` 之后、'
                '`_build_persona_prompt` 自己不碰训练纠正）· '
                'E 契约不破（桩上真跑：`_build_persona_prompt()` 仍逐字等于 persona 文件）· F 自检。'
                '★ 只读仓库内三份文件；Qt 用 offscreen；零网络、零外部盘。',
    },
    {
        'id': 'check138',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第138轮-判据输出去时相', '_tools', 'check138.py'),
        'offscreen': False,
        'desc': '第一百三十八轮：**判据的输出里不许含"时相量"**（行号 / 文件体积 / 字面量出现次数）。'
                '病根不是产品，是**判据自己**：`run_all.py` 逐行比对输出，一条判据只要把'
                '随版本漂移的绝对数打进 extra，它就会在**判定完全没变**的情况下报 DIFF，'
                '逼人逐个归因 —— 第129/132/135 各咬过一次，第137轮**一轮之内咬了两次**'
                '（改代码一次、改注释一次），累计 8 次。'
                '★★ 修法只有一条：**不改判定，只改 extra** —— 语义是处数 / 顺序 / 越阈值，'
                '就只回显处数 / 布尔 / `n/m`。共 7 处：'
                '`check129 D4/D5`（夹具规模去占位符、体积改 `n/2 过阈`）· '
                '`check131 D5`（字符数改 `n/2 过阈`）· '
                '`check132 D3/D4`（`[(15187, [...])]` 改并列闸名单、`行号=[...]` 改处数）· '
                '`check134 B1c2`（`原文出现 19 次` 改布尔）· '
                '`check135 F1/G4`（`第 [12438] 行` 改处数、常量全文不回显）· '
                '`check137 D1~D3`（`[14234]` 改处数、`a vs b` 改布尔）· '
                '`verify_s2_animations_json A4`（`%d 字节` 改长度是否一致）。'
                '★★★ A 段是全仓闸：从 `run_all.py` 的 `SUITES` **AST 解析**出 136 个脚本，'
                '逐个扫 `check(...)`/`ok(...)` 的**输出位**，不许出现 `.lineno`、'
                '不许出现 `len(_read(...))`。两条关键工程教训写进代码：'
                '① 全仓 `check` 有 **24 种**签名、`ok` 有 **16 种** ⇒ 不能靠签名猜位置，'
                '输出位规则＝第 3 个位置实参（4 参形态再取第 4 个），两参形态登记为**盲区**；'
                '② `.lineno` **参与算布尔**不算印行号（`check107 E8b` 就是这种合规写法，'
                '第一版判据把它判红 = 误报）⇒ 只抓"直接当 % 元素"和"取 .lineno 的列表推导"。'
                '★ B 段把 7 处新形状逐个钉住（旧形状不许回潮），其中 `check134 B1c2` 第一版用'
                '纯文本扫、被**自己的注释**误伤 ⇒ 改 AST（"禁某短语出现"类判据禁纯文本扫的第 8 次）。'
                'C 段 5 条控制：正控制 2 条（旧写法必须被抓到）+ 反控制 3 条'
                '（`len(_call)` 处数不算体积、`bool(a.lineno==b.lineno)` 不算行号、'
                '`%r` 打"装着行号的变量"如实登记为**抓不到**）。'
                'D 分母闸：136 个脚本 / 6000+ 处调用 / SUITES 路径全部存在。'
                'E 鉴别力自证（阈值抬到 1GB ⇒ `n/2` 必须变 0）。F 自检（含"本文件自己也过 A 段"）。'
                '★ 零 Qt、零网络、零外部盘（只读仓库内脚本）。',
    },
    {
        'id': 'check139',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第139轮-patch与人设去重', '_tools', 'check139.py'),
        'offscreen': True,
        'desc': '第一百三十九轮：`patches["ralsei"]` **不再复述**人设已有的句数规格。'
                '第137轮登记的遗留①「一次最多两三句，短一点，像随口说出来的。」与 persona'
                '「一次只说 1~3 句」重复，当时判为"冗余但无害、本轮不清"。'
                '★★ 本轮先证明它**没用**再删：同一条"一次说几句"在本项目写了**三遍** —— '
                '人文本（`ralsei_persona.md` 的「我怎么说」）· 机器可读'
                '（`cards/ralsei.json` 的 `length_policy{200, 3}`）· 提示词（patch 里的 ①，'
                '由 `common113.PATCH_RULES[\'TOO_LONG\']` 生成）。第三份是**派生品**，'
                '既不是"训练里真复现过的毛病"，也说不清来源。'
                '★★ A/B 证据（`第139轮/_evidence/ab139.jsonl`，本机 `ralsei:v4`，'
                '同尾块 534 字、同 7 题、题序交错、热身 2 条丢弃，**唯一变量**是那段 21 字）：'
                '56 条真机回复，>3 句 **14/28 vs 13/28**、平均句数 3.93 vs 3.71、'
                '平均字数 74.0 vs 60.4 ⇒ 句数自助法 **p=0.64**、字数 **p=0.24**，'
                '两样都测不出差别；两臂 OOC/BANNED/MD 全 0。'
                '⇒ 重复第二遍没换来可测的东西，删。'
                '★ 顺带清掉 `check137` 里 4 处同类型 extra（`len(_out)` / `patch@%d` / '
                '`ralsei %d 字` / `len %d → %d`）—— 数据一改就 DIFF、判定却一个字没变，'
                '正是第138轮那条口径；并把 `check137 A1` **翻面**（原断"①②③ 都在位"，'
                '现断"① 不在位"，判据名与描述同步改）。'
                '★★ 套件内容：A 数据面（三份副本逐字一致 / ① 不在 / ②③ 与实测例「凯斯恩」一条没少）· '
                'B 真源面（人文本与 `length_policy` 都还在 —— 删的是第三份派生品，不是规格）· '
                'C 行为面（system 里确实没 ① 了、尾块没跟着消失、**破坏性负控制**'
                '：`training_patch` 返回空 ⇒ 只剩 persona）· '
                'D 改动最小（用**改动前的冻结快照** `patches_before139.json` 比对，'
                '不用 `git HEAD` —— 提交后 HEAD 就等于工作区，那种判据是恒真的；'
                'D2 变动键恰好 `{ralsei}`、D3 其余 58 条逐字未动、D5 三份副本"仍含 ①"的集合一致）· '
                'E 同型普查（**38/76**：人设已写句数规格、patch 仍复述 ① 的人数 —— '
                '本轮只修 ralsei，其余登记未修，数字一变就该回来看这一节）· '
                'F 证据完整性（56 条 / 两臂各 28 / 汇总与 raw 重算一致 / 两臂 system 差 == len(①)）· G 自检。'
                '★ 另附 `mutate139.py` 6 个破坏性负控制（塞回 ① / 抹掉实测例 / 只改一份副本 / '
                '动别人的 patch / 删证据行 / 只改汇总不改数据）—— 全都要报红，恢复后要重新全绿。'
                '★ 只读仓库内文件；Qt 用 offscreen（C 段要 `import main`）；零网络、零外部盘。',
    },
    {
        'id': 'check140',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第140轮-执行长度规格', '_tools', 'check140.py'),
        'offscreen': True,
        'desc': '第一百四十轮：`length_policy` 从**死数据**变成**真执行的规格**（只执行字数那一半）。'
                '★★ 第139轮把「一次说几句」数清了：人文本 / `length_policy` / 提示词 ①，'
                '删了第三份之后，`length_policy` 仍是**全仓零读取**（96 张卡写着、零处读），'
                '真正生效的是 `_clean_ai_reply` 里硬写的 220 —— 两套数字并存，以没人维护的那套为准。'
                '★★★ 先量再改，量出来的第一件事是**推翻自己上一轮的结论**：第139轮那个'
                '「>3 句 83.3%」是**切句口径的产物** —— 它把 `…` 当句号，而人设第 57 行写着'
                '「用省略号让声音软下来：别拿它当句号」。同一批 48 轮换切法：含 `…` 40/48=83.3%、'
                '不含 `…`（人设口径）31/48=**64.6%**、再剔引号内 24/48=**50.0%**。'
                '★★ 放大到**全体角色**（`第113轮/_evidence/raw30/` 77 份语料 / **5592 条**真机回复）：'
                '句数中位数 **4**（**44.1%** 的回复在 3 句以内）、≥3 句 73.7%、≥4 句 55.9%、'
                '≥6 句 24.7%、≥8 句 8.7%。'
                '⇒ 按 3 句硬砍要动 **55.9%**（注意不是 73.7% —— 那个是 ≥3 句的占比，'
                '砍只动 >3 句的，这两个数本轮我自己先读错过一次，靠证据落盘才抓回来）、'
                '按 6 句砍动 **15.1%**，而那批 6 句的回复平均才 150 字、**本来就在字数预算内** —— '
                '"句子多"和"话太多"不是同一件事。截断砍的是**结尾**，'
                '而人设要求的「先接住、再补一句我自己的感受」正好在结尾。'
                '★★ 所以本轮只执行 `max_chars`（200，卡片驱动、只许收紧 220），'
                '`max_sentences` **读进来但不参与截断**，并用 E 段钉成"显式不执行"'
                '（AST：`_max_sent` 有 Store 无 Load、零处当实参、全仓零"句数截断"函数定义），防以后凭直觉接上。'
                '★★ 改法踩到的坑写进代码：长度结算**不能**写成 `self._xxx()` —— '
                '回归桩只绑 `_clean_ai_reply` 一个方法，`AttributeError` 会被本方法自己的 '
                '`except` 静默吞掉 ⇒ 整条护栏返回原文不洗（首跑 13 条老判据一起红，'
                '`persona_chat` 13 FAIL）。改成模块级 `npc_persona.reply_length_limits()` 后全绿。'
                '★★ 套件内容：A 数据面（96 张卡里 77 张带规格、**分布唯一** {(200,3)}、真 int、'
                '另有卡不带规格 ⇒ "缺卡回落"不是假想分支）· B 读取层（真值 / 未登记 / 非法入参 / '
                '**坏卡三连**：`"200"` 字符串、`true`（`isinstance(True,int)` 陷阱）、`0` / 缓存真生效）· '
                'C 结算层（只许收紧：100 赢 200、500 不顶掉 200、非法 hard 回落 220）· '
                'D 行为面（210 字截到 ≤200、195 字成对不动、截点落在句末标点、'
                '**破坏性负控制**：读不到卡 ⇒ 210 字原样且 225 仍被 220 兜底、'
                '换 speaker 同限额、**D6b~D6d 三条哨兵**证明 markdown / 自问自答 / 引号剥除没被改哑）· '
                'E 不执行的显式登记 · F 常量面（220 / 24 / 40 一个没动、`speaker` 是带默认值第三参）· G 自检'
                '（G4 用**源码 AST 数** check() 处数做独立计数器 —— 自己数自己是恒真的）。'
                '★ 另附 `mutate140.py` 破坏性负控制与 `recheck140_core.py` 核心文件复检。'
                '★ 顺带清掉 `check133 E3` 一处时相量回显（`共 %d 个调用` ⇒ 三闸布尔），'
                '以及两个桩两处过期签名（`verify_s7_event_speech` 的 lambda 不吃 `speaker=`）。'
                '★ 零网络、零外部盘；临时卡片写系统 temp，不碰工作区。',
    },
    {
        'id': 'check141',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第141轮-单句长度测量', '_tools', 'check141.py'),
        'offscreen': True,
        'desc': '第一百四十一轮：「一句话太长」该不该上闸 —— 量完的答案是**不该**；'
                '副产品是补一条出戏正则。'
                '★★★ 正题：第140轮登记的候选指标（单句过长 / 最长句占比）本轮量完，**不执行**。'
                '三条理由，每条都有数据：'
                '① 那个"最长句 P90=83 字"是**英文样本顶起来的假象** —— 切句尺 `END` 不含 ASCII `.`'
                '（中文产品现状，对的），英文角色整段算一句。分层后 zh P90=71 / en P90=323；'
                '把 `.` 也当句末（**只用于归因**）再跑：en 层塌 180 字（323→143）、zh 层只动 −2。'
                '② 剩下那批长句大半是 **`…` 串**出来的：全语料 5672 个省略号记号，**97.4% '
                '后面话还在继续**（当逗号用）。人设第 57 行只写了「别拿它当句号」，没管"当逗号"'
                '—— 是个规格漏洞，但**本轮不动**：ralsei 本人 ≥3 个是 0%、max=2，密度榜首是 '
                '`ut_napstablook` 5.57/100字，那是 Napstablook 的口癖，拿主宠的尺子量别人会误伤。'
                '③ 真·长句（中文 / ≥80 字 / 省略号≤1，共 181 条）里混着**四类完全不同的东西**：'
                'queen 的无标点空格分词（人设第 18~20 行明写的风格，**是设计不是缺陷**）、'
                '元话语、引号里塞英文台词、正常叙述长句（`ot_toriel` 105 字，是人味）。'
                '⇒ 按 80 字砍动 5.4%、按 60 字砍动 **21.6%** —— 后者是重写行为，不是抓跑飞。'
                '★★★ 副产品（本轮唯一代码改动）：181 条里 `hy_ceroba_ketsukane` 那条'
                '「我是基于《Undertale Yellow》中的…这个角色进行设定和扮演的」喂进 '
                '`looks_out_of_character` 是 **False** —— 20 条子串一条都命中不了，'
                '`looks_like_meta_leak` 也不认（它管"念规则"，不管"自陈出处"）。'
                '全语料这一族 6 条、现有闸漏 **4 条**（1.7%→1.8%），其中**含 ralsei 本人 1 条**'
                '（「虽然我是根据特定的角色设定和性格来扮演的，但我确实是Ralsei」）。'
                '补的只有一条正则 `设定.{0,4}扮演` —— 用正则不用子串，因为这族特征是'
                '**"设定"与"扮演"两头都要出现**，单写任一头都会误伤。'
                '★ 被语料否决的候选（每条都有反例，别再加回来）：裸 `扮演`（78 条/18 角色，'
                '反例 `berdly`「我也在暗世界里扮演了一个聪明的勇士」是正常台词）· `角色扮演`'
                '（`mike` 在讲自己的皮套）· `(不是|并非).{0,6}真实存在`（反例 `ot_alphys` '
                '「不管是不是真实存在的」正常、`lancer`「我是从设定里诞生的角色」**正是人设允许的**'
                '「平平淡淡认一句」）。边界以人设为准：**认自己是角色放行，解释按设定演才拦**。'
                '★ 本套件守什么：A 数据面（英文污染/补点后成对变化/逗号链不存在/`…`当连接符/'
                '阈值扫描量级）· B 闸（恰 1 条正则 · 被否决候选没塞回 · 正控制×2 · **负控制×4**'
                '（含两条反例）· 两条链都在调）· C **不执行的显式登记**（没有全大写单句闸常量 · '
                '`_SENTENCE_ENDS` 仍含 `…`（切点温柔）与数句子不含 `…` 是两套尺子 · '
                '`max_sentences` 仍零引用）· D 自检。'
                '★ 另附 `mutate141.py` 破坏性负控制（6 处破坏，每处断言**指定**判据报红，'
                '并用 sha1 核对还原）与 `recheck141_core.py` 核心文件复检。'
                '★ 零网络、零 Qt（本套件不 `import main`，只用 AST 读源码）。',
    },
    {
        'id': 'check142',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第142轮-NPC补丁去重', '_tools', 'check142.py'),
        'offscreen': True,
        'desc': '第一百四十二轮：38 位 NPC 的 patch 开头那句不是"人设的重复"，是**38 份实测诊断**'
                ' —— 不许批量删；同时订正第139轮删 `ralsei` 那条的归因。'
                '★★★ 正题：第139轮登记了「38 位 NPC 的 patch 同型重复未修」，本轮去修之前先量了一步，'
                '结果**推翻了那个前提**。人设 76 份里写的是「一次开口通常 **1~2 句**，最长不超过 200 字」，'
                '而 patch 里那句（简称 ①）是「一次**最多两三句**，短一点，像随口说出来的」——'
                '**① 更宽**，所以删它不是去重，是把规格收紧，那是行为改变。'
                '★★ ① 真正的来源（`第113轮/_tools/common113.py`）：`evaluate()` 里 '
                '`if len(t) > MAX_CHARS: bad.append((\'TOO_LONG\', ...))` ——触发条件是**回复超 200 字**，'
                '与句数无关；再由 `build_patch` 按优先级取**前 3 条**，`TOO_LONG` 排**第 7 位**。'
                '⇒ patch 里出现 ① ＝ 这个角色**真的踩过超长**，而且前面几项没把 3 个槽位占满。'
                '★★★ 语料侧取证（77 份 raw30 / 5592 条真机回复）：带 ① 的 38 人 **100%** 有 >200 字的回复'
                '（共 247 条、最长 465 字）；不带的 39 人只有 **20.5%**（8 人）；'
                '「既没超长也没超句」却带 ① 的 **0 人**。⇒ 38/76 不是模板没清干净，是 38 份诊断。'
                '★ 连带订正：`ralsei` 实测最长 **211 字**、有 1 条 >200 ⇒ 它当初**确实踩过 TOO_LONG**，'
                '第139轮说它"只是重复"的归因不成立。删掉后 56 条 A/B 无差别**仍是实测结论**，'
                '现状保留不回滚；但**不能当先例**去删另外 38 条。'
                '★ 本套件守什么：A 数据面（人设规格只 1 种写法且是 1~2 句 · ① 只 1 种写法且逐字等于 '
                '`PATCH_RULES[\'TOO_LONG\']` · 三处副本集合一致）· B 因果（用 AST 读"触发是 `len>MAX_CHARS`"'
                '与"`TOO_LONG` 排第 7、只取前 3"，再用语料三连 100% / <25% / 0 人）· '
                'C 结论登记（**三处副本都仍是 38 条**、`ralsei` 三处都不含 ①、`ralsei` 实测最长 >200、'
                '`common113` 里有订正注释）· D 自检。'
                '★ 另附 `mutate142.py` 破坏性负控制（7 处破坏，每处断言**指定**判据报红 + sha1 核对还原）。'
                '★ 判据自身踩的坑：`C1`/`C2` 第一版只读 `_index.json` 那一份 ⇒ 删 `cards/asgore.json` '
                '里的 ① 时不报红（两份副本各守一半才叫守住）· `A2` 第一版只看 `list(specs)[0]`，'
                '多写法时取哪个取决于 set 迭代顺序 ⇒ 改成"所有写法都含 1~2 句"。'
                '★ 零网络、零 Qt：只读 `_index.json` / `cards/*.json` / `persona/*.txt` / `common113.py` '
                '源码，以及本轮已落盘的两份测量证据（语料侧不重跑）。',
    },
    {
        'id': 'check143',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第143轮-对话链截断切点', '_tools', 'check143.py'),
        'offscreen': True,
        'desc': '第一百四十三轮：对话链的**超长截断**补上 ASCII `.` —— 英文 NPC 不再被切成半个单词。'
                '★★★ 起因：第141/142 两轮连续登记了「`…` 当逗号」这个规格漏洞，速查本里还留着一句'
                '「数句子不含 `…`、切点含 `…`（两套标点）」。把它当**待证陈述**去核，结论是'
                '**那句话本身说混了**：`common113._sentences`（训练侧数句）**含** `…`；'
                '`event_speech._SENTENCE_ENDS`（事件链截断）**含** `…`；'
                '`main._clean_ai_reply` 第 3 步（对话链截断）**不含** `…`。'
                '⇒ 真正分叉的只有对话链那一处，而它的病**不是缺 `…`**。'
                '★★★ 真缺陷是**缺 ASCII `.`**。语料（77 人 / 5592 条真机回复）：超 `max_chars`(200) 的 336 条'
                '＝中文 170 + 英文 166；其中**硬截**（一个切点都没找到 ⇒ 走 `t[:200]`）中文 **0** 条、'
                '英文 **61 条（36.7%）**，61 条的尾字符**没有一条**是句末标点，全是半个单词'
                '（`…\'tty fragile in\'` / `\' such a tough \'` / `\'see beyond the\'`）——'
                '这正是第135轮治过的"吊尾巴"，只是**对话链这一支从来没治**。'
                '★ 四个变体对照（同一批 336 条）：`。！？!?\\n`（原）0/61 · + `…` 0/59 · **+ `.` 0/2** · '
                '+ `…` + `.` 0/1 ⇒ 采用「+ `.`」。**不加 `…`**：只解 2 条，却会抢走 8 条本该切在 `。` 上、'
                '5 条本该切在换行上的切点 —— 而 `…` 在语料里 **97.4% 是当逗号用的**，切在它后面等于切在半句话上。'
                '两条链上限不同（事件链 24 / 自主开口 40 vs 对话链 200），约束本来就不同，'
                '**这是刻意的分叉，不是漏改**（`check143 B4/B6` 两头都钉住）。'
                '★ 改动是**纯新增 31 行、零删除**（`git diff -U0` 实证）：主查找单独算一次'
                '`_dot = t.rfind(\'.\', 0, max_chars)`，配一条小数点守卫（`3.14` 的点后面跟数字就往回再找）。'
                '行为面 A/B 用 **AST 把产品源码那一段抠出来 `exec` 跑**（不复刻夹具）：英文硬截 61 → 2、'
                '中文 0 → 0、截断结果变化 107 条（中 15 / 英 92，15 条中文的新尾**全是句末标点**）。'
                '★ 负控制成对：删掉 `_dot` 整块 ⇒ 与改动前逐条一致（0 条不一致）；小数点守卫删掉 ⇒ '
                '`a…3.14…b` 当场切在 `3.` 后。'
                '★ 判据自身踩的三个坑（都写进注释）：① `B3` 第一版断"`.` 在 `for sep` 元组里"——'
                '本轮刻意不放元组（要过守卫），判断错了对象；第二版断"段里出现 `t.rfind(\'.\'," 又被 `M1` 抓出'
                '**还是太松**（守卫的 `while` 里也有一句），最后钉到**那一行赋值**。'
                '② `D1` 第一版只断"段里有「第143轮」" ⇒ 恒真族（证据路径里也有这四个字），改成钉完整首行。'
                '③ 负控制第一版用 `replace("\'.\', ", "")` 拆 `.` ⇒ 把 `t.rfind(\'.\',` 也拆了，'
                '报的是崩溃不是判据失效。'
                '★ `mutate143.py` 7 处破坏各自断言**指定**判据报红 + sha1 核对还原；'
                '`recheck143_core.py` 核心文件复检（`main.py` 是产品主链路，改动面 / 语法 / 编码 / 恒真 / '
                '逐令牌 / 白名单 / 写盘七项）。'
                '★ 零网络、零 Qt（不 `import main`，只用 AST 读源码 + 抠出那一段 `exec`）。'
                '★ 语料是仓库内的冻结证据（`第113轮/_evidence/raw30`），不依赖外部盘。',
    },
    {
        'id': 'check144',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第144轮-证据冻结', '_tools', 'check144.py'),
        'offscreen': True,
        'desc': '第一百四十四轮：**`phase138.json` 冻结** —— 会自己变的历史证据不能拿来对账。'
                '★★★ 病：`check138.py` 每跑一次都往 `第138轮/_evidence/phase138.json` 写两个数'
                '（`files_scanned` / `calls_scanned`），而这两个数**必然随套件数变化**。'
                '`git log` 实证：从第138轮起**连续 6 个提交（138~143）全被改**，'
                '137/6120 → 138/6158 → 139/6198 → 140/6228 → 141/6246 → 142/6274，'
                '**每次都是 +1 个文件、+N 正好等于那一轮新加的判据条数**（38/40/30/18/28）⇒ '
                '它不是"当时量到的东西"，是"套件清单长度的回声"。后果：每轮 commit 都捎带一个'
                '语义无关的改动，review 时纯噪声。'
                '★ 改法不是"备份"也不是"干脆不写"：`.gitignore` 里有 `*.backup*`，跨目录备份既有'
                '被误伤的风险、也治不了"每轮都改"；而"不写"会让想看扫描面的人没了出口。'
                '⇒ **证据冻结在仓库里（137/6120 + `_note` 说明来历），活计数留在工作区外**：'
                '`check138` 改写到 `code-quality-audit/regress/_out/phase138.live.json`，'
                '该目录`.gitignore` 已整目录忽略。停写的风险为零：全仓**读盘 0 处**'
                '（只有三个 `recheck1xx` 的白名单里提到路径）。'
                '★ 判据自身踩的两个坑（都写进注释）：① `B2` 第一版**读 `_out` 的运行产物**比对键集 ——'
                '那个文件在新克隆的机器上不存在 ⇒ 判据条数会在 16/17 之间跳，"判据条数随环境变"'
                '本身就是缺陷（`H4d` 现在专门钉住"有 live / 无 live 条数一致"），改成'
                '**静态读 `check138.py` 里 `_ev` 字典的键**；② 全仓 AST 扫描第一次直接崩在'
                '`UnicodeDecodeError`（第113轮 `_tools/disk/` 有 5 个非 UTF-8 脚本 + 1 个 SyntaxError）——'
                '**静默 `continue` 会让"没扫到"和"扫过且干净"长得一样**，所以逐个 `[SKIP]` 记名打印，'
                '再对它们做一次**字节级**兜底（一次都没提过 `phase138.json` ⇒ 绝不可能写它；'
                '这个方向只误报不漏报），并加 `B1b` 守扫描面不塌（下限 ≥100 个 `.py`）。'
                '★ 连带登记：`eval113.merge_patches` **保留旧键**、两边都有走 `merge_text` 求并集 ⇒'
                '「重跑训练会把 ① 塞回 `ralsei`」是**条件成立的**，所以 `check139 A1` 不能删（`C1~C4`）。'
                '★ `mutate144.py` 8 处破坏各自断言**指定**判据报红（含打自己的 `D1` / `B1b`，'
                '"守别人的人自己不守"）+ 字节级还原核对；`recheck144_core.py` 核心文件复检'
                '（改过 `check138.py`：**判据 ID 集与 HEAD 版逐字相同**、hunk 2 处、删的那 1 行不含 `check(`）。'
                '★ 零网络、零 Qt、零外部盘（备份落 `D:\\_tmp`，用完即删）。',
    },
    {
        'id': 'check145',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第145轮-事件链英文切点', '_tools', 'check145.py'),
        'offscreen': True,
        'desc': '第一百四十五轮：事件链（24 字）/ 主动开口（40 字）不认 ASCII `.` —— 英文切在半个单词上。'
                '★★★ 这是第143轮那条病的**另一半**：143 修的是**对话链**（上限 200），'
                '当时只查了那一条。`event_speech._SENTENCE_ENDS = u\'。！？!?\\n…\'` '
                '**没有 ASCII `.`** ⇒ 英文回复在这张表里一个切点都没有 ⇒ 只能走末尾那句 '
                '`t[:max_chars].rstrip(\'，,、。！？!?；;：: \')` 硬截 ⇒ '
                '`Well, well, well. What d`（紧跟 `o we have he`）。'
                '★ 24 个**字符**对英文大约只有 4 个单词，所以这条链比对话链更狠。'
                '★★ 实测（77 人 / 5592 条真机回复，`_evidence/lead145.json` + `ab145.json`，'
                'A/B = HEAD 版 vs 工作区版**各自真 import**，不复刻夹具）：'
                '事件 24 字**英文 203 → 135**（占英文 448 条的 15.2%）、中文 1031 → 959；'
                '开口 40 字**英文 184 → 100**、中文 239 → 200；全量 24 字 1234 → 1094、40 字 423 → 300。'
                '中文也降了 72 条 —— 模型在中文里也用 `...` 当省略号，切在它后面是**完整**停顿，'
                '比硬截在汉字中间好；132 条中文输出变化**逐条看过**，全是"切在句末 / 省略号后"。'
                '★ 改法两处且是**减少重复**：① `_SENTENCE_ENDS` 加 `.`，配套过滤 —— `.` 前面已有 '
                '≥ `MIN_FIRST_CHARS` 个字才算句末（挡缩写点 `Mr.` / 开头 `...`），后面紧跟数字一律不算'
                '（挡小数点 `3.14`）；② `first_sentence` 与 `fit_sentences` 原来**各自抄了一遍**'
                '"扫标点 + 吃连续 + 去重"，合成 `_sentence_ends()` 一处（加过滤必须两边一致，'
                '否则又是"同一份规则两处算"）。diff **+46/−13**，删掉的 13 行**全部**是那两段重复循环 + 常量行。'
                '★ 不加 `,` / `;`：它们在中英文里都是**句内**停顿，在 `.` 上切是"到句末了"，'
                '在 `,` 上切是"话没说完就换行"，那是另一种坏。'
                '★★★ 判据自身的坑（`mutate145 M6` 抓出来的）：`B8/B9` 第一版写的是 '
                '`\'isdigit\' in 函数源码` / `\'MIN_FIRST_CHARS\' in 函数源码` —— 而 `_sentence_ends` 的 '
                '**docstring 里本来就写着这两个名字**（解释规则）⇒ 守卫被改成 `if False:` 判据**照样绿**。'
                '改成 AST 结构判定（真有一次 `.isdigit()` 调用 / `MIN_FIRST_CHARS` 真进了比较式）。'
                '这就是"判据只判提到某名字＝恒真"的第 N 次。'
                '★ 另一条如实登记：缩写点有**两层**防线（过滤 + `first_sentence` 自己那条 '
                '`len(head) >= MIN_FIRST_CHARS`），所以 `M6` 只让 `B9` 红、`C2` 不红 —— `C2` 的鉴别力'
                '由 `C9`（把 MIN 调 0 ⇒ 立刻切出 `Mr.`）单独证，不靠 mutate。'
                '★ 两条负控制成对：去掉 `.` ⇒ C1 立刻退回 `Well, well, well. What d`；'
                '把 MIN 调 0 ⇒ `Mr.` 立刻被当句末。'
                '★ `mutate145.py` 8 处破坏各自断言**指定**判据报红（含打自己的 `E2`）+ 字节级还原；'
                '`recheck145_core.py` 45 条（改过 `event_speech.py`：4 处 hunk / +46−13 / 删的 13 行'
                '逐行归类 / `main.py` 一字未动 / EOL 无裸 LF / 逐令牌 16 条）。'
                '★ 零网络、零 Qt（只 import 那个纯逻辑模块，不 import `main`）、零外部盘。',
    },
    {
        'id': 'check146',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第146轮-判据输出不再回显计数', '_tools', 'check146.py'),
        'offscreen': False,
        'desc': '第一百四十六轮：`check138` 的输出里不再回显"规模量"（扫了多少文件 / 多少处调用）。'
                '★★★ 病：`D1`/`D2` 的 extra 原来写 `u\'%d 个\' % len(_targets)` / '
                '`u\'%d 处\' % _n_calls`。这两个数**每加一个套件必然变** ⇒ 判定一个字没改，'
                '`check138` 却报 DIFF ⇒ 每轮都得 `--only check138 --update` 一次。'
                '第144轮只冻了**落盘**那一半（`_evidence/phase138.json` 不再重写），'
                '**stdout** 这一半没动 —— 时相量回显的第 9 次复发。'
                '★ 改法：语义是"越阈值"，extra 就只回显**布尔**'
                '（`u\'过阈=%s（闸门 ≥100）\' % (len(_targets) >= 100)`），'
                '具体数值留在 `regress/_out/phase138.live.json`（已忽略、不入库）。'
                '判定表达式与 desc **与 HEAD 逐字相同**（`recheck146_core H16` 钉住），只动了 extra。'
                '★★★ 为什么是**行为级**证明（本套件 B 段）：临时往 `SUITES` 塞一条探针套件 ⇒ '
                'Δfiles=+1、Δcalls=+5 ⇒ `check138` 的 stdout **必须逐行不变**（实测 0 行不同）。'
                '负控制成对：**旧形状**渲染那两行，改前改后的数**必然不同**（2/2）—— '
                '否则"输出没变"就不是修好了，而是夹具没生效（`M4` 把探针改成 no-op 时 `B1/B2/B4` 当场红）。'
                '`run_all.py` 每轮按字节还原并校验 sha1，探针文件用完即删。'
                '★★ 静态那一层只是**前置筛**：`measure146.tainted()` 做文件内数据流（'
                '`_targets = [p for p in _suite_scripts()…]` → `for _p in _targets` → '
                '`_tree = ast.parse(_read(_p))` → `_n_calls += sum(…_tree…)`，四跳，跑到不动点）。'
                '第一版按**名字**匹配（`_targets`/`_n_calls`/`SUITES`）抓出 15 处，'
                '**13 处是误报** —— `check90/91/92/99` 的 `_n_calls` 是它们**自己的记账计数器**'
                '（判据 `CALLS == PASS + FAIL`），跟套件数无关。'
                '这正是"提到名字 ≠ 会变"的反面教材，已写成 `C4` 反控制钉住。'
                '★ 补的一刀：第一版只追"值里出现脏名字"的累加，漏了最常见的 '
                '`for p in _targets: _n += 1`（值是常数 1）—— `C5` 正控制只抓到 1/2 处才暴露。'
                '★ 豁免桶**登记不静默**：`check138 A4` 的 `_missing`（登记的脚本缺了几个）'
                '是**命中列表**（健康态恒 0，只有真登记了坏路径才变），判据是"推导式里带否定过滤"。'
                '另有一条半恒真判据被删掉：`A5` 原来写 `"\'regress\'" in 源码`，'
                '而 `check138` 抬头的 `RUN_ALL` 路径里就有 `regress` ⇒ 永远成立；'
                '改成行为级 `B7/B8`（跑完 check138 后冻结件字节没变 + 活计数真落到 `_out/`）。'
                '★ `mutate146.py` 5 处破坏各自断言**恰好**指定判据变红 + 字节级还原 + 收口全绿；'
                '`recheck146_core.py` 51 条（改过 `check138.py`：+12/−2 / 删的 2 行逐行归类 / '
                'EOL 与 HEAD 同构 / `check`+`ok` 两套 harness 恒真复查 / 逐令牌 5 条）。'
                '★ 复检自己第一版报了 9 条红，**逐条查完没有一条是产品坏了**：'
                '`H1/H2/H3/H18/H23` 还守着"只许改 1 个文件"的**过期前提**（登记 check146 本来就要改 '
                '`run_all.py`）；`H12` 抓到我自己写的 `check(..., True)` **两处**'
                '（本轮第 2 次自己写恒真，第 1 次是 `E5` 的 `or True`）；'
                '`H14` 判定"旧写法已消失"报红，因为**我把旧写法抄进注释当反例** —— '
                '又一次"禁某短语出现禁纯文本扫"，改成只看非注释行。'
                '★ 零网络、零 Qt（只 import `measure146` 那个纯逻辑模块，不 import `main`）、'
                '临时件只落 `D:\\_tmp`（用完即删）。',
    },
    {
        'id': 'check147',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第147轮-硬截退到词边界', '_tools', 'check147.py'),
        'offscreen': False,
        'desc': '第一百四十七轮：硬截兜底**切在半个单词**上时，退到最后一个空格。'
                '★ 病（第145轮遗留①）：ASCII `.` 进 `_SENTENCE_ENDS` 治掉了"英文有句号却被硬截"，'
                '但 24/40 字里**一个句末标点都没有**的（全大写自造拼写、`hehe that tickles` 连写）'
                '只能走兜底 `t[:max_chars].rstrip(...)` ⇒ 显示成 `hehe that tickles so mu`。'
                '★ 改法：抽出 `_hard_cut(t, max_chars)`（原来**三处**各抄一遍），'
                '切点落在词中间时退到最后一个空格；两道底线（留下 ≥ `MIN_FIRST_CHARS`、'
                '留下 ≥ 半个预算）都是**数据选**的：ratio 0/0.3/0.4/0.5 结果完全一致、'
                '0.6 起开始少收（135→133→128）⇒ 取 0.5。'
                '★★★ 本轮最贵的一课：`str.isalnum()` 对 CJK 也返回 True。'
                '第一版用它判"切在词中"⇒ **每一次中文硬截**都被判成切在词中 ⇒ 退到空格'
                '（往往在英文人名前）⇒ 中文输出被改了 **151 / 57 条**（`_evidence/ab147.json`）。'
                '改成 ASCII 白名单 `_WORDY` 后归 **0**。A/B 用 `git show HEAD:` 落临时件再 '
                '`spec_from_file_location` 独立加载，**先断言两份 sha1 不同**才算真对照。'
                '★★ 对账用**守恒式**而不是"两数相等"：`旧切词中 − 仍切词中 == 改动数`'
                '（142−2=140、109−0=109）—— 被底线拒掉的几条**不会改**，第一版写等号是错的。'
                '★★ 中文改动要拆 `legal / illegal` 两类：句尾正好切在英文人名里**就该改**，'
                '写"中文必须 0 改动"是错的判据（实测 42 / 14 条全是这一类，违规 0）。'
                '★ 契约变更已登记：`check145 C8` 原来断言"去掉 `.` ⇒ 退回 `What d`（半个单词）"，'
                '兜底自己变好了 ⇒ 改成 `Well, well, well. What`（多带一个悬空的词），'
                '降级依然真实、C1 的鉴别力还在（18 字 vs 22 字）。'
                '★ `mutate147.py` 6 处破坏各自断言**恰好**指定判据变红 + 字节级还原 + 收口全绿；'
                '其中 `M5` 必须**同时拆两道底线**才复现（底线① 在底线② 存在时是冗余的）。'
                '★ 覆盖不足被负控制抓出来两次：底线② 原本**没有样本**（删掉它整套照样全绿）⇒ 补 `HALF`；'
                '`NOSPACE` 名字说"空格在开头"其实**一个空格都没有**（`\'a\' + \'bcdef…\'`）⇒ '
                '拆成 `NOSPACE`（无空格）+ `SPACE0`（空格在第 0 位）；'
                '而 `SPACE0` 从公开 API **走不到**（两个入口开头都 `strip()`）⇒ `B7` 改成单元级探针，'
                '并写明"这不是端到端行为"。'
                '★ `recheck147_core.py` 核心文件复检（改过 `event_speech.py`）：'
                '改动面 +46/−3 且删的 3 行逐行归类 / EOL 还原成 LF（与同目录其他模块一致）/ '
                '`check`+`ok` 两套 harness 恒真复查 / 逐令牌回验。'
                '★ 零网络、零 Qt（只 import `modules.event_speech` 那个纯逻辑模块）、'
                '临时件只落 `D:\\_tmp`（用完即删）。',
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
# ★★★ 第95轮追加：**NPC 自主移动日志**（"NPC <id> 自己挪到了 <scene>"）——
#   ★★ 这不是"环境噪声"，是**真机自主生活的时间驱动产物**，必须从逐字节基线里剔除。
#
#   为什么它**物理上不可能收敛**（第95轮实测确证，不是推断）：
#     决策真源 = `npc_intent.decide()`，其随机种子是
#         `rng.seed(seed_for(npc_id, salt) ^ int(jitter(npc_id, now, salt, 0, 1 << 30)))`
#     其中 `now` = **真实绝对秒**（`time.time()`）。源码注释自己写着
#     「★ 抖动叠在随机源上：同样权重、不同时刻 ⇒ 结果可不同（L6）」——
#     这是**产品设计意图**（NPC 要"活着"，不能每次开机走同一条路线），**不是缺陷**。
#     ⇒ 同一份代码，任何两次运行的 "谁在哪一拍挪到了哪" 都不同。
#
#   实测（决定性实验，2026-10-07）：
#     · 现状跑 2 次：moves 计数 34 / 32、sha 不同；`--update` 后**立刻**再跑仍 DIFF；
#     · 再加 `RALSEI_DATA_DIR` 隔离（假设是 staging 未隔离）⇒ **仍不收敛**（32/33/34），
#       ⇒ 该假设被证伪，漂移源确实是时钟、不是存储。
#     ⇒ 结论：**凡 `RalseiPet()` 真机跑过 NPC 自主节拍的套件（如 `check89`），
#       其 stdout 天然含不可复现行**，逐字节基线对它**恒假红**。
#       前几轮把它加进 `HERMETIC_IDS` 是冲错根因（以为只是存储隔离），故注释写了
#       "已修"而实测未修 —— 本条才是真修法。
#
#   ⚠️ 代价（写清楚，别以后忘了）：抹平后**「NPC 自主移动整体坏掉」也看不见**了。
#      真正守它的是**离线断言套件**，它们不依赖这行 stdout：
#        · `npc_round49`  —— 容器/驻留语义
#        · `npc_place56`  —— 站位 / 游荡 / 编队
#        · `check87`      —— `home_of()` / 自主移动隔离 / 跨作品零决策
#        · `check89` 自己 —— A~F 段把"桌面门 / 路由 / 渲染计划 / 推门真切换"全断言掉
#      ⇒ 本行只承载"这一拍恰好谁动了"这一**无被测语义**的时间戳式信息，剔除它
#        不损失任何该守的行为。
#   形态：行首可能被 `[INFO]`/时间戳前缀（已被 `_TS` 归一），故按**裸行**匹配。
_NPC_ROAM_NOISE = re.compile(
    r'^(?:<TS>\s*)?(?:\[INFO\]\s*)?ralsei_pet\.main — NPC \S+ 自己挪到了 \S+$'
)

# ---------------------------------------------------------------------------
# ★ 第98轮：**本地 AI（Ollama + 代理）连接失败**的日志行 —— 环境噪声，整行剔除。
#
#   起因（实测）：`check89` 会真机跑一次 `RalseiPet()`，其中"就寝到点"那一步会让 NPC/宠物
#   开口 ⇒ 触发一次**真实的**本地 AI 流式请求。本机 Ollama 不在跑 / 代理状态不同 ⇒
#   同一份代码、同一个沙箱、**连续两次运行**打出来的错误文本都不一样：
#     基线：`… 本地 AI 流式请求失败（忽略）: HTTPConnectionPool(host='127.0.0.1',
#            port=64650): Max retries exceeded … ProxyError('Unable to connect to proxy',
#            ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接。', …))`
#     复跑：`… 本地 AI 流式 HTTP 502: upstream connect failed: 由于目标计算机积极拒绝，
#            无法连接。 (os error 10061)`
#   ⇒ 逐字节基线对它**恒假红**（`--update` 也稳不住：刚 update 完复跑又变）。
#
#   ⚠️ 代价（写清楚）：抹平后**"本地 AI 整体坏掉"在这条 stdout 上看不见了**。
#      真正守 AI 链路的是一批**不依赖网络**的套件（`s7_event_speech` 的"AI 不可用 ⇒
#      退回罐头/沉默"、`dialog_*` 系列、`check98` 的 `speak_event` 唯一入口断言）。
#      本行承载的只是"本机此刻连不上 Ollama"这一**与被测行为无关**的环境状态。
#
#   形态：`<TS> [INFO|WARNING|ERROR] ralsei_pet.LocalAI — 本地 AI 流式…`
#        （时间戳已被 `_TS` 归一成 `<TS>`；只匹配"流式请求失败/HTTP 4xx-5xx/超时"，
#          **不**匹配其它 LocalAI 日志 —— 免得把"AI 已就绪"这类有用信息也抹掉。）
#
#   ★★ 第99轮实测修正（原正则**匹配不到**它自己要抹的那一行）：
#     第98轮写的是 `流式(?:请求)?(?:失败|HTTP \d+|超时)`，而真机打出来的是
#     「本地 AI 流式 **HTTP 502**: …」—— `流式` 与 `HTTP` 之间**有一个空格**，
#     于是两组分支都落空 ⇒ 正则**恒不命中** ⇒ `check99`/`check89` 的基线里
#     仍然留着这几行 502，运行时刻一变（AI 是否被触发、重试几次）就 DIFF。
#     第99轮全量三跑实测：同一份代码，`check99` 的 502 警告行从 1 条变 2 条、
#     位置也在漂 ⇒「注释说已归一，其实没归一」的**判据自欺**（本项目第 N 次）。
#     ⇒ 修法：`流式(?:请求)?\s*(?:失败|HTTP \d+|超时)`，把那个空格吃掉。
#     ⚠️ 关键是**实测**正则命中真行（`_LOCAL_AI_NOISE.match(<真行>) is True`），
#        不是"看着像"—— 这个坑的正因就是没人拿真行试过。
# ---------------------------------------------------------------------------
_LOCAL_AI_NOISE = re.compile(
    r'^(?:<TS>\s*)?(?:\[(?:INFO|WARNING|ERROR)\]\s*)?ralsei_pet\.LocalAI\s+—\s+本地 AI '
    r'流式(?:请求)?\s*(?:失败|HTTP \d+|超时)'
)


# ---------------------------------------------------------------------------
# ★ 第98轮：**就寝决策**的日志行 —— 墙钟驱动，整行剔除。
#
#   起因（实测）：`check89` 会真机跑一次 `RalseiPet()`，而它的定时器每 5 秒调一次
#   `RalseiPet._bedtime_tick`。这个函数走哪条分支**完全由运行时的墙上时钟决定**：
#     基线（那次录制 ≈22:59，正落在就寝窗口内）：
#       `… [就寝] 到点（目标 22:59），回房间睡觉`（+ 随后 [就寝] 回房间…/由小憩升级为就寝睡）
#     复跑（此刻 23:12，窗口 22:59~23:09 已过）：
#       `… [就寝] 今晚（2026-10-08）窗口 22:59~23:09 已过，不再补睡`
#   ⇒ 同一份代码、同一个沙箱，**换个时刻跑**就输出不同行数/不同文本 ⇒ 逐字节基线对它
#      **恒假红**（`--update` 也稳不住：换一个时刻再跑又变。第98轮连续三次全量都栽在它，
#      前两次我误判成"代理/服务状态"，真凶是墙钟）。
#   形态：`ralsei_pet.main — [就寝] …`（时间戳已被 `_TS` 归一；以下就寝日志同族）。
#
#   ⚠️ 代价（写清楚）：抹平后**整个就寝日志族**（到点 / 窗口已过 / 回房间 / 升级 /
#      自动醒来）在这条 stdout 上都**看不见了**。真正守就寝语义的是**不依赖墙钟**
#      的判据：
#        · `check91` F 段（同轮补）：真调 `_bedtime_tick(now=<注入>)` 断言窗口三态 ——
#          未到点不睡且不标记 / 窗口内真去睡 / ★窗口已过**不补睡但仍标记当晚** /
#          窗口内「有事」返 False 却不标记（负控制）/ 窗口末点那一秒仍算窗口内（`>` 非 `>=`）；
#        · `check91` D 段：跨天闸（入睡当日不醒 / 次日 07:00 醒 / 00:30 与 06:59 不醒）；
#        · `check80` F 段：层3 就寝接线（`decide_sleep` / `sleep_fn` 真注入）。
#      ❗ 仍未覆盖：`go_to_bed()` 内部"回房间失败 ⇒ 就地就寝"的降级路径（第98轮登记为遗留）。
# ---------------------------------------------------------------------------
_SLEEP_WINDOW_NOISE = re.compile(
    r'^(?:<TS>\s*)?(?:\[(?:INFO|WARNING|ERROR)\]\s*)?ralsei_pet\.main\s+—\s+\[就寝\]'
)


# ---------------------------------------------------------------------------
# ★ 第113轮h：**外置盘/分区探测失败**的日志行 —— 环境状态，整行剔除。
#
#   起因（实测，2026-10-25）：跑全量 G2 时 10 个套件集体 DIFF，而 PASS/FAIL 计数
#   **一条没变**。逐条看 `.diff.txt` 都在同一位置多一行：
#     `<TS> [WARNING] ralsei_pet.desktop_interaction — 获取存储分区信息失败:
#      [WinError 1] 函数不正确。: 'E://'`
#   直接查盘确认根因不在代码：
#     `os.path.exists('E:/')` → **False**；`os.listdir('E:/')` → `OSError(22, '函数不正确。')`
#   ⇒ 用户的 E 盘**整体掉线**（exFAT 外置盘，仓库文件在 C 盘、不受影响），
#     产品每次枚举分区就多一条告警。换回一个"盘在"的时刻，这行又消失 ⇒
#     逐字节基线对它**必然假红**，而且假红形态最容易骗人（计数全对、只多一行）。
#
#   ⚠️ 代价（写清楚）：抹平后**"存储盘掉了"在这条 stdout 上看不见了**。
#      真正该守的是数据落点：`data_store` 的 vault 解析、`npc_memory` 落盘、
#      `check67`/`check73` 的隔离目录断言 —— 它们不依赖这行 stdout。
#      另：本行只承载"这台机器此刻有没有 E 盘"这一**与被测行为无关**的环境事实。
#
#   形态：`… ralsei_pet.desktop_interaction — 获取存储分区信息失败: <任意>`
#        （只匹配前缀到"失败"，**不**吃盘符/错误码 —— 盘符 `E:` `D:` 都可能变。）
# ---------------------------------------------------------------------------
_STORAGE_PROBE_NOISE = re.compile(
    r'^(?:<TS>\s*)?(?:\[(?:INFO|WARNING|ERROR)\]\s*)?'
    r'ralsei_pet\.desktop_interaction\s+—\s+获取存储分区信息失败'
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
        if _NPC_ROAM_NOISE.match(ln):  # ★ 第95轮：NPC 自主移动（真时钟驱动，见常量注释）
            continue
        if _LOCAL_AI_NOISE.match(ln) or _SLEEP_WINDOW_NOISE.match(ln):  # ★ 第98轮：本地 AI 连接失败 + 就寝决策（见常量注释）
            continue
        if _STORAGE_PROBE_NOISE.match(ln):  # ★ 第113轮h：外置盘掉线时的分区探测告警（见常量注释）
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


def normalize_noblank(text):
    u"""`normalize()` 之后再**剔掉空行** —— 只给"第二道比对"用（第99轮）。

    为什么不直接把 `normalize()` 改成剔空行：基线里存的是**旧规则**（折叠连续空行）的结果，
    全局改规则会让 **92 个套件的基线一次性全变**（为一条噪声重刷全套 baseline，风险远大于收益）。
    ⇒ 保留 `normalize()` 原样，另开一道**只在第一道不等时才跑**的比对：
       两道都相等 ⇒ 判 `IDENTICAL*`（标注"仅空行噪声"），**不刷基线**。
    """
    return '\n'.join(ln for ln in normalize(text).split('\n') if ln) + '\n'


def _verify_norm99():
    u"""★ 第99轮新增规则（第二道**空行不敏感**比对）的**正 / 负控制成对**自检（离屏、零 GUI）。

    判据自己也会说谎 ⇒ 改了比对层就必须证明：
      · 正控制：只有**空行位置/数量**不同 ⇒ 第二道判**相等**（这正是要消掉的噪声）；
      · 负控制 A：真删掉一行**断言** ⇒ 第二道仍**不等**（证明没把内容也抹掉）；
      · 负控制 B：真删掉一行断言 ⇒ `count_results()` 的 PASS 条数**必须变**（第三道独立防线）。
    跑法：`python code-quality-audit/regress/run_all.py --selftest-norm`
    """
    head = ('<TS> [INFO] ralsei_pet.main — 全局热键未装上\n'
            '<TS> [INFO] ralsei_pet.main — 道具系统就绪\n')
    body = ('[PASS] A1 第一条\n'
            '[PASS] A2 第二条\n')
    banner = ('====\n'
              '第99轮：PASS=2 FAIL=0\n'
              '====\n')
    a = head + '\n' + body + banner                  # 空行在 head 与 body 之间
    b = head + body + '\n' + banner                  # 空行改到 body 与 banner 之间（实测两种都出现过）
    c = head + body + banner                         # 干脆没有空行
    d = head + '[PASS] A1 第一条\n' + banner         # 真删掉一行**断言**（不是空行）

    def eq(x, y):
        return normalize_noblank(x) == normalize_noblank(y)

    def normalize_no_raise_on_leading_blank():
        u"""★ 第99轮补的**绊线**：`normalize()` 本体也曾被改坏而自检全绿。

        真 bug：把 `out, blank = [], False` 误改成 `out = []` ⇒ `blank` 未初始化。
        它**只在“首行即空行”时**触发 `UnboundLocalError`（其余情况会被 else 分支赋成
        False，侥幸躲过）—— 而单套件跑法首行恰好非空，所以 `--only check95/check99`
        全绿、**全量才崩**。这里直接把“首行是空行”喂进去当绊线。
        """
        try:
            out = normalize('\n\n[PASS] A1 第一条\n\n[PASS] A2 第二条\n')
        except Exception:
            return False
        return ('[PASS] A1 第一条' in out) and ('[PASS] A2 第二条' in out)

    cases = [
        ('正控制：仅空行位置不同 ⇒ 第二道判等', eq(a, b), True),
        ('正控制：仅少一个空行 ⇒ 第二道判等', eq(a, c), True),
        ('负控制 A：真删一行断言 ⇒ 第二道仍不等', eq(a, d), False),
        ('负控制 B：真删一行断言 ⇒ PASS 条数必须变',
         count_results(d)[0] != count_results(a)[0], True),
        # ★ 正/负控制成对：上面 4 条只测 normalize_noblank()，这条测 **normalize() 本体**。
        ('正控制：normalize() 遇“首行即空行”不抛异常（blank 未初始化类 bug 的绊线）',
         normalize_no_raise_on_leading_blank(), True),
    ]
    bad = 0
    for name, got, want in cases:
        ok = (got == want)
        bad += 0 if ok else 1
        print('[PASS] NORM99 %s：%s（期望 %r，得到 %r）'
              % ('OK' if ok else 'FAIL', name, want, got))
    print('---')
    print('normalize 空行规则自检：%d/%d' % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


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
    ap.add_argument('--selftest-norm', action='store_true',
                    help='★ 第99轮：只见证 normalize() 的空行规则（正/负控制成对，零 GUI）')
    args = ap.parse_args()

    if args.selftest_norm:
        return _verify_norm99()

    picked = [s for s in SUITES if not args.only or any(k in s['id'] for k in args.only)]

    if args.list:
        for s in SUITES:
            print('%-16s %-4s %s' % (s['id'], 'offscreen' if s.get('offscreen') else 'in-proc', s['desc']))
        return 0

    baseline = load_baseline()

    # ★★ 第82轮修：`--update` 时**先把键集补齐**再跑，否则"自指的基线条数判据"
    #    （`check81` G5：基线套件集合 == SUITES 集合）会**每一轮 --update 都假红一次** ——
    #    因为它读的是**磁盘上的旧基线**（本次 update 要到全部跑完才落盘）。
    #    时序真相：run_all 在开头 load 快照 → 各套件跑 → 结束后 save_baseline。
    #    ⇒ 新入列的套件在 `check81` 眼里"还没固化"，于是它诚实地报红 —— 报的是**真事实**，
    #      但这是**执行顺序**造成的假警报（下一轮跑就绿了），会污染"全 IDENTICAL"的验收。
    #    修法：update 前先把 picked 的 id 写进基线（值留哨兵，跑完全部再被真值覆盖）。
    #    ⚠️ 只补"缺失的 id"，不动既有条目的真值 ⇒ 不改变任何既有比对语义。
    if args.update:
        _pre = load_baseline() or {'version': 1, 'suites': {}}
        _pre.setdefault('suites', {})
        _added = []
        for _s in picked:
            if _s['id'] not in _pre['suites']:
                _pre['suites'][_s['id']] = {
                    'exit': 0, 'pass': 0, 'fail': 0,
                    'sha256': 'PENDING_UPDATE',   # 哨兵：跑完必被真值覆盖
                }
                _added.append(_s['id'])
        if _added:
            _pre['suites'] = dict(sorted(_pre['suites'].items()))
            with open(BASELINE, 'w', encoding='utf-8', newline='\n') as _fh:
                json.dump(_pre, _fh, ensure_ascii=False, indent=2, sort_keys=True)
                _fh.write('\n')
            say('[update] 预登记新套件进基线键集（避开自指判据的假红）：%s' % _added)
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
        old_raw_path = os.path.join(OUT_DIR, r['id'] + '.baseline.txt')
        if args.update or old is None:
            cmp_txt = 'BASELINE'
        elif old['sha256'] == r['sha256'] and old['exit'] == r['exit'] and old['pass'] == r['pass']:
            cmp_txt = 'IDENTICAL'
        else:
            cmp_txt = 'DIFF'
            # ★★★ 第99轮：第二道比对 —— **空行不敏感**（正负控制见 `_verify_norm99`）。
            #   真机套件的 stdout 由 log 线程与 `print` 交错写入 ⇒ **空行的位置/数量会抖**
            #   （实证 `check99` 连跑三次：**非空行恒 111**，空行在 2 / 3 之间跳）
            #   ⇒ 第一道（逐字节哈希）**恒假红**，而语义差为 **0**。
            #   条件刻意收得很紧：**exit / PASS / FAIL 三项必须全同**，且剔空行后逐行全等，
            #   才判 `IDENTICAL*` —— 它**不刷基线**，也**不算问题**，但会在摘要里显式报数。
            if (old and old['exit'] == r['exit'] and old['pass'] == r['pass']
                    and old['fail'] == r['fail'] and os.path.exists(old_raw_path)):
                try:
                    with open(old_raw_path, encoding='utf-8') as fh:
                        if normalize_noblank(fh.read()) == normalize_noblank(r['norm']):
                            cmp_txt = 'IDENTICAL*'
                except OSError:
                    pass
        verdicts[r['id']] = cmp_txt
        say('%-16s %-6s %-6s %-6s %-8s %s' % (
            r['id'], r['exit'], r['pass'], r['fail'], cmp_txt, s['desc']))
        if cmp_txt == 'DIFF':
            old_norm = None
            if old and os.path.exists(old_raw_path):
                with open(old_raw_path, encoding='utf-8') as fh:
                    old_norm = normalize(fh.read())
            path = write_diff(r['id'], old_norm, r['norm'])
            problems.append('%s: 输出与基线不一致（%s），%s' % (r['id'], '计数/退出码变化' if old_norm else '无基线文本', path))
        else:
            # ★ 第99轮顺手堵掉 write_diff docstring 里记的那个坑（第75轮血泪）：
            #   `_out/<id>.diff.txt` **只在 DIFF 时重写**，恢复绿了旧文件会原地留着
            #   ⇒ 曾把陈旧 diff 当成"今天的 19 个 DIFF"。判非 DIFF 时主动清掉。
            stale = os.path.join(OUT_DIR, r['id'] + '.diff.txt')
            try:
                if os.path.exists(stale):
                    os.remove(stale)
            except OSError:
                pass
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
    _nb = sorted(k for k, v in verdicts.items() if v == 'IDENTICAL*')
    if _nb:
        say('★ 其中 %d 个套件判 `IDENTICAL*` —— **仅空行噪声**（真机 log/print 交错；'
            '剔空行后逐行全等且 exit/PASS/FAIL 全同，**未刷基线**）：%s'
            % (len(_nb), ', '.join(_nb)))
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
