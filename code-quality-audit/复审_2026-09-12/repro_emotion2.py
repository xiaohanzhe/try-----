# -*- coding: utf-8 -*-
import sys, os, time, tempfile
ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, os.path.join(ROOT, 'modules'))
os.chdir(tempfile.mkdtemp())
class FakeDialogue:
    def add_dialogue(self, *a, **k): pass
    def show_dialogue(self, *a, **k): pass
class FakeParent:
    def __init__(self):
        self.dialogue_ui = FakeDialogue(); self.is_moving=False; self._spell_stage=None
        self.game_state={'is_playing':False}; self.current_animation='idle'
    def change_animation(self, *a, **k): return True

from emotion_system import EmotionSystem
print("=========== 复现 2：happy 自激 ===========")
es = EmotionSystem(FakeParent())
es.last_emotion_change = time.time() - 10
es.update()
print("基线 happy=%.2f dominant=%s" % (es.emotions['happy'], es.get_current_emotion()))
es.add_emotion('happy', 30)
print("add_emotion('happy',30) -> happy=%.2f" % es.emotions['happy'])
for i in range(15):
    es.last_emotion_change = time.time() - 10   # 模拟每 10 秒一次 stats_timer
    es.update()
    if (i+1) % 3 == 0:
        print("  tick %2d (每tick 10s) happy=%.2f dominant=%s" % (i+1, es.emotions['happy'], es.get_current_emotion()))
print("结论:", "自激锁死→永久极度开心" if es.emotions['happy'] >= 99 else "有界")
print("     期望：happy 应在若干 tick 后回落到低位")

print()
print("=========== 复现 3：时钟回拨 ===========")
from energy_hunger import EnergyHungerSystem
eh = EnergyHungerSystem(FakeParent())
eh.energy=20.0; eh.hunger=20.0
eh.last_update_time = time.time() + 3600
eh.update_stats()
print("回拨 1h: energy=%.1f hunger=%.1f (应保持低位)" % (eh.energy, eh.hunger))
es2 = EmotionSystem(FakeParent())
es2.emotions['sad']=50.0
es2.last_emotion_change = time.time() + 3600
es2.update()
print("回拨 1h: sad=%.1f dominant=%s" % (es2.emotions['sad'], es2.get_current_emotion()))

print()
print("=========== 复现 4：复合情绪被下个 tick 覆盖 ===========")
es3 = EmotionSystem(FakeParent())
es3.add_emotion('shy', 45)
print("add shy+45 后立刻 shy=%.1f" % es3.complex_emotions['shy'])
es3.last_emotion_change = time.time() - 10
es3.update()
print("一个 tick 后 shy=%.1f" % es3.complex_emotions['shy'])

print()
print("=========== 复现 5：relieved 永不衰减 ===========")
es4 = EmotionSystem(FakeParent())
es4.add_emotion('relieved', 25)
for _ in range(10):
    es4.last_emotion_change = time.time() - 10
    es4.update()
print("10 tick 后 relieved=%.1f dominant=%s" % (es4.complex_emotions.get('relieved'), es4.get_current_emotion()))
