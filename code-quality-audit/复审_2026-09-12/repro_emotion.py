# -*- coding: utf-8 -*-
"""独立复现：energy_hunger 喂食卡死 / emotion_system happy 自激锁死 / 负 elapsed"""
import sys, os, time, tempfile, json
ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, os.path.join(ROOT, 'modules'))
os.chdir(tempfile.mkdtemp())

class FakeDialogue:
    def add_dialogue(self, *a, **k): pass
    def show_dialogue(self, *a, **k): pass
class FakeParent:
    def __init__(self):
        self.dialogue_ui = FakeDialogue()
        self.is_moving = False
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.current_animation = 'idle'
    def change_animation(self, *a, **k): return True

print("=========== 复现 1：hunger>80 时 eat() 是否卡死 ===========")
from energy_hunger import EnergyHungerSystem
eh = EnergyHungerSystem(FakeParent())
eh.hunger = 85.0
eh._prev_hunger_tier = eh._hunger_tier()   # 模拟"上一 tick 就已经是 high 档"
print("初始 hunger=%.1f tier=%s is_eating=%s" % (eh.hunger, eh._prev_hunger_tier, eh.is_eating))
ok = eh.eat()
print("调用 eat() -> is_eating =", eh.is_eating)
for i in range(30):                        # 30 个 tick，每个 tick 视为 1 分钟
    eh.last_update_time = time.time() - 60
    eh.update_stats()
print("30 tick 后: hunger=%.1f is_eating=%s" % (eh.hunger, eh.is_eating))
print("结论:", "卡死（is_eating 永真、hunger 钉在 100）" if eh.is_eating else "正常结束")

print()
print("=========== 复现 2：happy 是否自激锁死 ===========")
from emotion_system import EmotionSystem
es = EmotionSystem(FakeParent())
es.update(10)   # 先跑一 tick 建立基线
base_happy = es.emotions['happy']
print("基线 happy=%.2f" % base_happy)
es.add_emotion('happy', 30)
print("add_emotion('happy', 30) 后 happy=%.2f" % es.emotions['happy'])
for i in range(12):
    es.update(10)
    if (i+1) % 3 == 0:
        print("  第 %2d 个 tick(每 tick 10s) 后 happy=%.2f dominant=%s" % (i+1, es.emotions['happy'], es.get_current_emotion()))
print("结论:", "自激锁死 → 永久极度开心" if es.emotions['happy'] >= 99 else "有界")

print()
print("=========== 复现 3：系统时间回拨 ===========")
eh2 = EnergyHungerSystem(FakeParent())
eh2.energy = 20.0; eh2.hunger = 20.0
eh2.last_update_time = time.time() + 3600   # 模拟时钟往前 1 小时
eh2.update_stats()
print("回拨 1 小时后 energy=%.1f hunger=%.1f" % (eh2.energy, eh2.hunger))
es2 = EmotionSystem(FakeParent())
es2.emotions['sad'] = 50.0
es2.last_emotion_change = time.time() + 3600
es2.update(3600)
print("情绪 sad=%.1f" % es2.emotions['sad'])
