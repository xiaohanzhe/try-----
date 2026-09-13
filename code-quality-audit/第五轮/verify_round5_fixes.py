# -*- coding: utf-8 -*-
"""第五轮修复的回归验证（只读，不改动项目文件）。

覆盖：
  V1 对话系统：直接问"内存/cpu"必须真正调用 desktop_interaction.get_system_resources()
  V2 对话系统：承接语（"还有呢"）仍走上下文兜底，不被修复误伤
  V3 施法流程：_tick_spell_flow 的 casting 分支不再抛 NameError，且能调用完成回调
  V4 娱乐系统：game_master 成就要求"每种游戏都玩过"（去重），而非累计次数
  V5 记忆系统：save_memory 落盘载荷键（记录现状，供报告引用）
"""
import io
import os
import re
import sys
import types

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, os.path.join(BASE, "modules"))

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  [PASS] " if ok else "  [FAIL] ") + name + ((" :: " + detail) if detail else ""))


# ---------------- V1/V2 对话系统 ----------------
print("=== V1/V2 对话系统：系统类意图是否触达真实桌面操作 ===")
import dialogue_system as ds_mod

calls = []


class FakeDesktopInteraction:
    def get_system_resources(self):
        calls.append("get_system_resources")
        return {"cpu_percent": 11.1, "memory_percent": 22.2, "disk_percent": 33.3}

    def get_battery_status(self):
        calls.append("get_battery_status")
        return {"percent": 88, "plugged": True}

    def get_network_status(self):
        calls.append("get_network_status")
        return {"is_connected": True}

    def optimize_system(self):
        calls.append("optimize_system")
        return True

    def clean_temp_files(self):
        calls.append("clean_temp_files")
        return True

    def backup_data(self):
        calls.append("backup_data")
        return True


ds = ds_mod.DialogueSystem(desktop_interaction=FakeDesktopInteraction())

# V1: 直接问内存 —— 必须真正查询
calls.clear()
r1 = ds.generate_response("内存使用率是多少呢")
check("V1a 问'内存使用率'触达 get_system_resources",
      "get_system_resources" in calls,
      "calls=%s reply=%r" % (calls, r1))
check("V1b 回复中带真实数值(11.1)",
      "11.1" in r1,
      "reply=%r" % r1)

# V1b: 优化 / 清理 / 备份
calls.clear()
r2 = ds.generate_response("帮我优化一下系统吧")
print("   [debug] 优化 -> calls=%s reply=%r" % (calls, r2))
check("V1c 说'优化'触达 optimize_system",
      "optimize_system" in calls, "calls=%s reply=%r" % (calls, r2))

calls.clear()
r3 = ds.generate_response("清理一下垃圾文件")
print("   [debug] 清理 -> calls=%s reply=%r" % (calls, r3))
check("V1d 说'清理'触达 clean_temp_files",
      "clean_temp_files" in calls, "calls=%s reply=%r" % (calls, r3))

calls.clear()
r4 = ds.generate_response("帮我备份数据")
check("V1e 说'备份'触达 backup_data",
      "backup_data" in calls, "calls=%s" % calls)

# V1f: 单独说"优化"（不含"系统"字样），确认不被 system_status 分支抢占
calls.clear()
r6 = ds.generate_response("优化一下吧")
print("   [debug] 纯'优化' -> calls=%s reply=%r" % (calls, r6))
check("V1f 纯'优化'触达 optimize_system",
      "optimize_system" in calls, "calls=%s reply=%r" % (calls, r6))


# V2: 承接语仍走上下文兜底（不应因修复而彻底失效）
ds2 = ds_mod.DialogueSystem(desktop_interaction=None)
ds2.generate_response("看看系统状态")           # 第一轮：建立 last_intent
r5 = ds2.generate_response("还有呢")           # 第二轮：承接
has_intent = ds2.context.get("last_intent")
check("V2a 承接语仍能读到上一轮意图",
      has_intent == "system_status", "last_intent=%s" % has_intent)
check("V2b 承接语得到上下文回复而非崩溃",
      isinstance(r5, str) and len(r5) > 0, "reply=%r" % r5)

# ---------------- V3 施法流程 ----------------
print()
print("=== V3 施法流程 casting 分支（含本次 P0 修复） ===")
MAIN = os.path.join(BASE, "src", "main.py")
src = io.open(MAIN, encoding="utf-8").read()
lines = src.splitlines()

import ast
tree = ast.parse(src)
node = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == "_tick_spell_flow":
        node = n
        break

frag_lines = lines[node.lineno - 1: node.end_lineno]
dedented = [(ln[4:] if ln.startswith("    ") else ln) for ln in frag_lines]
# 第 0 行是签名 "def _tick_spell_flow(self):"，丢弃；其余行作为 _fn 的函数体
body = dedented[1:]
ns = {"__name__": "_probe", "time": __import__("time"), "os": os}
mod_src = "def _fn(self):\n" + "\n".join("    " + ln for ln in body)
exec(compile(mod_src, "<probe>", "exec"), ns)
fn = ns["_fn"]
# 自检：确保拿到的是有真实语句的函数体，而不是空的壳
check("V3-pre 探针成功提取方法体", node.body and len(node.body) > 5,
      "语句数=%d" % len(node.body))

# 反汇编确认不再有 LOAD_GLOBAL current_time
import dis
bad = []


def scan(c):
    for ins in dis.get_instructions(c):
        if ins.opname == "LOAD_GLOBAL" and ins.argval == "current_time":
            bad.append(ins.offset)
    for const in c.co_consts:
        if hasattr(const, "co_names"):
            scan(const)


scan(fn.__code__)
check("V3a 反汇编中已无 LOAD_GLOBAL current_time",
      not bad, "offsets=%s" % bad)


# 构造最小 stub，跑完一次 casting tick
class Loader:
    sprites = {"spell": [object()] * 11}


class Stub:
    _spell_stage = "casting"
    _spell_target_direction = "right"
    _spell_target_kind = "file"
    _spell_target_path = r"C:\tmp\x.txt"
    _spell_touched_flag = False
    _spell_seen_frame = -1
    _spell_frames_seen = 0
    _spell_cast_start_time = None
    _spell_cast_start_frame = None
    _is_being_dragged = False
    is_jumping = False
    is_falling = False
    _hide_stage = None
    _spell_auto_suspended = False
    current_animation = "spell"
    current_frame = 0
    current_direction = "right"
    previous_direction = "right"

    def __init__(self):
        self.sprite_loader = Loader()
        self.cb_called = False

    def _spell_interrupted_reason(self):
        return None

    def _spell_finish_cb(self, path, kind):
        self.cb_called = True

    def change_animation(self, name, force=False):
        self.current_animation = name
        return True

    class _A:
        def resume(self):
            pass
    autonomous_agent = _A()


stub = Stub()
err = None
# 模拟真实主循环：每帧推进 current_frame（与 update_animation 一致），
# spell 共 11 帧，tick 到第 11 帧才应触发完成回调。
try:
    for f in range(14):
        stub.current_frame = f
        fn(stub)
        if stub.cb_called:
            break
except Exception as e:
    err = repr(e)
check("V3b casting tick 不再抛 NameError", err is None, "err=%s" % err)
check("V3c 施法结束回调被真正调用（文件才会被打开）",
      getattr(stub, "cb_called", False),
      "cb_called=%s frames_seen=%s" % (getattr(stub, "cb_called", False),
                                       getattr(stub, "_spell_frames_seen", None)))
check("V3d _spell_stage 已复位（不再永久卡在 casting）",
      stub._spell_stage is None, "stage=%r" % getattr(stub, "_spell_stage", "N/A"))

# ---------------- V4 娱乐成就 ----------------
print()
print("=== V4 游戏大师成就（去重逻辑） ===")
import entertainment_system as ent_mod
import inspect

src_ent = inspect.getsource(ent_mod.EntertainmentSystem._check_game_achievements)
check("V4a 判定使用 games_played_ids 去重集合",
      "games_played_ids" in src_ent,
      "")
check("V4b 不再使用累计次数 games_played 判定",
      "activity_stats['games_played'] >= len(self.games)" not in src_ent, "")
src_init = inspect.getsource(ent_mod.EntertainmentSystem.__init__)
check("V4c activity_stats 初始化含 games_played_ids",
      "'games_played_ids': []" in src_init, "")

# ---------------- V5 记忆载荷键 ----------------
print()
print("=== V5 memory save_memory 落盘键 ===")
import memory_system as mem_mod
src_save = inspect.getsource(mem_mod.MemorySystem.save_memory)
keys = re.findall(r"'(\w+)':\s*self\.", src_save)
print("  save_memory 实际落盘键:", keys)
ms = mem_mod.MemorySystem.__dict__.get('__init__')
print("  记录：memory_strength 是否在落盘键中 ->", "memory_strength" in keys)

print()
print("=" * 60)
fails = [r for r in results if not r[1]]
print("总计 %d 项，通过 %d，失败 %d" % (len(results), len(results) - len(fails), len(fails)))
for n, ok, d in fails:
    print("  FAILED:", n, d)
sys.exit(1 if fails else 0)
