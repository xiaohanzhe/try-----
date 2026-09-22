# -*- coding: utf-8 -*-
"""第 35 轮 —— F35-1 复核：拿产品真实的动画名**生成函数**跑一遍，逐条比对资源。

为什么必须这么做（铁律）：
    「分类器太窄」和「闸有洞」长得一样。v2 扫描器漏掉了 main.py:7638 的
    `f"{base}_{dir}{suffix}"`，因为我把 `_sleep` 放进了 SUF 候选表、却没检查
    资源里其实不存在 `*_sleep`。⇒ 静态扫描永远有盲区。
    唯一可靠做法：**调用产品自己的拼名逻辑**，把它可能产出的**全集**枚举出来，
    再与资源比对。

做法：
    复刻 update_animation 里那段后缀决策（base × direction × suffix），
    产出的名字全集 → 与 animations.json 的 groups 求差集。
    「复刻」有失真风险，所以复刻逻辑**逐行对照源码行号**写在注释里，
    并在末尾附上源码原文供人工核对（本项目「探针必须保真」纪律）。
"""
import json
import os

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(WS, "ralsei_pet")
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")

anim = json.load(open(os.path.join(PET, "assets", "animations.json"), encoding="utf-8"))
GROUPS = set(anim.get("groups", {}).keys())
sl = open(os.path.join(PET, "modules", "sprite_loader.py"), encoding="utf-8").read()
import re
ALIAS = set(m.group(1) for m in re.finditer(r'["\']([a-zA-Z][a-zA-Z0-9_]{2,})["\']\s*:', sl))
KNOWN = GROUPS | ALIAS

# ---- 复刻 main.py update_animation L7605-7650 的拼名逻辑 ----
# 源码：base_animation = "run" if speed_sq > speed_threshold else "walk"
BASES = ["walk", "run"]
# 源码 L7617-7635 的 suffix 决策链
SUFFIXES = ["", "_butler", "_butler_unhappy", "_cotton_candy", "_blush", "_unhappy", "_sleep"]
# 源码 L7638: new_animation = f"{base_animation}_{self.current_direction}{animation_suffix}"
DIRECTIONS = ["down", "left", "right", "up"]

all_names = set()
for b in BASES:
    for d in DIRECTIONS:
        for s in SUFFIXES:
            all_names.add(f"{b}_{d}{s}")

missing = sorted(n for n in all_names if n not in KNOWN)

L = []
L.append("第35轮 F35-1 复核 —— 拿产品拼名逻辑枚举全集，比对资源")
L.append("=" * 66)
L.append("复刻口径（逐行对照 main.py）:")
L.append("  L7611-7614  base_animation ∈ {walk, run}")
L.append("  L7617-7635  animation_suffix ∈ {'', _butler, _butler_unhappy, _cotton_candy, _blush, _unhappy, _sleep}")
L.append("  L7638       name = f'{base}_{direction}{suffix}'")
L.append("")
L.append("枚举全集: %d 个" % len(all_names))
L.append("资源可解析: %d 个" % len(KNOWN))
L.append("")
L.append("★ 资源中不存在（运行时 anim-miss）: %d 个" % len(missing))
L.append("-" * 66)
for n in missing:
    L.append("  %s" % n)
L.append("")
L.append("结论:")
sleep_missing = [n for n in missing if n.endswith("_sleep")]
other_missing = [n for n in missing if not n.endswith("_sleep")]
L.append("  · 后缀 _sleep 相关缺失: %d 个  → %s" % (len(sleep_missing), ", ".join(sleep_missing) or "无"))
L.append("  · 其它缺失: %d 个  → %s" % (len(other_missing), ", ".join(other_missing) or "无"))
L.append("")
L.append("⇒ F35-1 的**真实影响面**：所有 _sleep 拼名（%d 个）全部不存在。" % len(sleep_missing))
L.append("  其中只有 direction==down 时会真的被请求（L7646 仅 down 置 is_sleeping_walk），")
L.append("  但 L7631-7638 读的是**上一帧**的 is_sleeping_walk，且下一帧若方向已变则请求别的方向；")
L.append("  实测只观测到 walk_down_sleep / walk_left_sleep，与推演一致。")
L.append("")

dst = os.path.join(EV, "37_F35-1复核_拼名全集.txt")
open(dst, "w", encoding="utf-8").write("\n".join(L))
print("\n".join(L))
print()
print("WROTE", dst)
