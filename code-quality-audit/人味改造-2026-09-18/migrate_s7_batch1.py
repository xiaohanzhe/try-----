# -*- coding: utf-8 -*-
"""S7 batch 1 迁移手术：把「鼠标体感交互 + 菜单抚摸/喂食」20 处事件台词
从 `dialogue_ui.add_dialogue(...) + show_dialogue()` 改成走统一出口 `self.speak_event(...)`。

为什么用脚本而不是手工改
------------------------
第十五轮的教训：这种"逐处替换、每处只差几行"的改动，手工 `old_string` 匹配一次打错
就白干，而且**没有任何东西证明"该改的都改了"**。这里按行匹配 + 每次断言**恰好命中一次**
+ 收尾 `py_compile` + 打印手术日志（进 `_evidence/`）。

安全默认：**只改列在 MIGRATIONS 里的这 20 处**。物理状态机（坠落/摔扁/惊醒）、
游戏与文件操作等程序性反馈**一律不动** —— 它们要么要求 0 延迟，要么是控制流。
"""
import io
import os
import py_compile
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
OUT = os.path.join(HERE, '_evidence', 's7_batch1_surgery_log.txt')

I20, I24, I28, I16, I8 = ' ' * 20, ' ' * 24, ' ' * 28, ' ' * 16, ' ' * 8
A = 'self.dialogue_ui.add_dialogue("ralsei", '
S = 'self.dialogue_ui.show_dialogue()'

# (旧行列表（要求连续、逐行完全一致）, 新行, 说明)
MIGRATIONS = [
    ([I20 + A + '"别戳我啦...我都扁了...", "sad")', I20 + S],
     I20 + 'self.speak_event("splat_poked", ["别戳我啦...我都扁了..."], "sad", instant=True)',
     '摔扁形态被戳（短促 + 状态机 → 有意保持罐头）'),

    ([I28 + A + '"哎呀！别不楞我的耳朵啦！", "surprised")', I28 + S],
     I28 + 'self.speak_event("ear_ruffle", ["哎呀！别不楞我的耳朵啦！"], "surprised", instant=True)',
     '连点 3 下耳朵的机关（极短拟声 → 罐头）'),

    ([I20 + A + 'random.choice(body_responses), "curious")', I20 + S],
     I20 + 'self.speak_event("poke_body", body_responses, "curious")',
     '轻点躯干'),

    ([I20 + A + '"嗯？有什么事吗？", "curious")', I20 + S],
     I20 + 'self.speak_event("poke_shoulder", ["嗯？有什么事吗？"], "curious")',
     '轻推肩膀'),

    ([I20 + A + 'random.choice(short_responses), "happy")', I20 + S],
     I20 + 'self.speak_event("poke_default", short_responses, "happy")',
     '点击其它部位'),

    ([I28 + A + 'random.choice(response_list), "happy")', I28 + S],
     I28 + 'self.speak_event(pet_kind(pet_part), response_list, "happy")',
     '抚摸（按部位分事件名）'),

    ([I20 + A + '"哇啊——！", "surprised")', I20 + S],
     I20 + 'self.speak_event("fling", ["哇啊——！"], "surprised", instant=True)',
     '被甩飞（要求 0 延迟 → 罐头）'),

    ([I24 + A + '"哎呀！别捏我的耳朵！好痒呀！", "surprised")', I24 + S],
     I24 + 'self.speak_event("pinch_ear", ["哎呀！别捏我的耳朵！好痒呀！"], "surprised")',
     '长按耳朵'),

    ([I24 + A + '"嘿嘿~ 别拉我的手臂啦！", "happy")', I24 + S],
     I24 + 'self.speak_event("pull_arm", ["嘿嘿~ 别拉我的手臂啦！"], "happy")',
     '长按手臂'),

    ([I24 + A + '"嗯~ 好舒服！", "happy")', I24 + S],
     I24 + 'self.speak_event("press_body", ["嗯~ 好舒服！"], "happy")',
     '长按躯干'),

    ([I24 + A + '"嘿嘿~ 我的肚子很软哦！", "happy")', I24 + S],
     I24 + 'self.speak_event("pat_belly", ["嘿嘿~ 我的肚子很软哦！"], "happy")',
     '长按肚子'),

    ([I24 + A + '"哎呀~ 别捏我的脸！", "shy")', I24 + S],
     I24 + 'self.speak_event("pinch_face", ["哎呀~ 别捏我的脸！"], "shy")',
     '长按脸'),

    ([I24 + A + '"谢谢你拉我的肩膀！", "happy")', I24 + S],
     I24 + 'self.speak_event("pull_shoulder", ["谢谢你拉我的肩膀！"], "happy")',
     '长按肩膀'),

    ([I16 + A + '"嘿嘿~ 摸头杀好舒服！", "happy")', I16 + S],
     I16 + 'self.speak_event("double_hair", ["嘿嘿~ 摸头杀好舒服！"], "happy")',
     '双击摸头'),

    ([I16 + A + '"哈哈！别用力拍我的肚子啦！", "laughing")', I16 + S],
     I16 + 'self.speak_event("double_belly", ["哈哈！别用力拍我的肚子啦！"], "laughing")',
     '双击肚子'),

    ([I16 + A + '"哎呀！别捏我的脸！", "surprised")', I16 + S],
     I16 + 'self.speak_event("double_face", ["哎呀！别捏我的脸！"], "surprised")',
     '双击脸'),

    ([I16 + A + '"谢谢你拍拍我的肩膀！", "happy")', I16 + S],
     I16 + 'self.speak_event("double_shoulder", ["谢谢你拍拍我的肩膀！"], "happy")',
     '双击肩膀'),

    ([I16 + A + '"嘿嘿~ 你对我真好！", "happy")', I16 + S],
     I16 + 'self.speak_event("double_other", ["嘿嘿~ 你对我真好！"], "happy")',
     '双击其它部位'),

    ([I8 + A + '"谢谢你喂我！肚子饱饱的，好幸福~", "happy")', I8 + S],
     I8 + 'self.speak_event("feed", ["谢谢你喂我！肚子饱饱的，好幸福~"], "happy")',
     '菜单喂食'),

    ([I8 + A + '"嘿嘿~ 好舒服呀！", "happy")', I8 + S],
     I8 + 'self.speak_event("pet_menu", ["嘿嘿~ 好舒服呀！"], "happy")',
     '菜单抚摸'),
]


def main():
    with io.open(MAIN, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    eol = '\r\n' if text.count('\r\n') > 200 else '\n'
    cr = '\r' if eol == '\r\n' else ''
    lines = text.split('\n')
    norm = [ln[:-1] if ln.endswith('\r') else ln for ln in lines]

    log = []
    log.append('S7 batch 1 迁移手术日志')
    log.append('目标：%s' % os.path.relpath(MAIN, ROOT).replace('\\', '/'))
    log.append('行尾：%r   手术前总行数：%d' % (eol, len(norm)))
    log.append('')
    errors = []
    hits = []
    for old_lines, new_line, tag in MIGRATIONS:
        found = []
        n = len(old_lines)
        for i in range(len(norm) - n + 1):
            if norm[i:i + n] == old_lines:
                found.append(i)
        if len(found) != 1:
            errors.append('%-16s 命中 %d 处（要求恰好 1 处）' % (tag, len(found)))
            continue
        hits.append((found[0], n, new_line, tag))

    if errors:
        log.append('=== 中止（未写盘） ===')
        log.extend('  ' + e for e in errors)
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(log) + '\n')
        sys.stdout.write('ABORT: %d 处不满足"恰好命中一次"\n' % len(errors))
        return 1

    # 从后往前替换，避免行号位移
    hits.sort(key=lambda h: -h[0])
    for idx, n, new_line, tag in hits:
        lines[idx:idx + n] = [new_line + cr]
        log.append('  L%-6d -%d +1   %s' % (idx + 1, n, tag))
    text2 = '\n'.join(lines)
    with io.open(MAIN, 'w', encoding='utf-8', newline='') as f:
        f.write(text2)

    log.append('')
    log.append('手术数：%d' % len(hits))
    log.append('手术后总行数：%d（-%d）' % (len(lines), len(norm) - len(lines)))
    # 编译校验
    try:
        py_compile.compile(MAIN, doraise=True, cfile=os.path.join(HERE, '_evidence', '_s7pyc.pyc'))
        log.append('py_compile: OK')
        rc = 0
    except Exception as e:
        log.append('py_compile: FAIL %s' % e)
        rc = 2
    # 结构性断言：这 20 处不许再有裸 add_dialogue
    rest = text2.count('add_dialogue(')
    log.append('剩余 add_dialogue( 出现次数：%d（手术前 %d）' % (rest, text.count('add_dialogue(')))
    log.append('speak_event( 出现次数：%d' % text2.count('speak_event('))
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(log) + '\n')
    sys.stdout.write('OK migrated=%d rc=%d\n' % (len(hits), rc))
    return rc


if __name__ == '__main__':
    sys.exit(main())
