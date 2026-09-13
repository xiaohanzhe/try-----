# -*- coding: utf-8 -*-
"""第六轮 · 删除 dialogue_system 里"主动搭话"的模板台词库。

- should_initiate_conversation()  1291..1329  （按概率决定要不要主动搭话）
- initiate_conversation()         1498..1561  （早/中/下/晚四套模板台词）

删除后这两个方法全项目零引用（已用 Grep 确认）——主动开口统一走
RalseiPet.start_autonomous_speech()，由 AI 生成，10 分钟最多 1 次。
"""
import io
import os
import sys

TARGET = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', 'ralsei_pet', 'modules', 'dialogue_system.py'))

RANGES = [
    (1498, 1561),
    (1291, 1329),
]


def main():
    with io.open(TARGET, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print('before lines =', len(lines))

    checks = {
        1291: 'def should_initiate_conversation',
        1498: 'def initiate_conversation',
    }
    for start, expect in checks.items():
        got = lines[start - 1].strip()
        if expect not in got:
            print('ABORT: line %d expected %r, got %r' % (start, expect, got))
            return 1
    # 尾行锚点
    if 'return random.random() < base_prob' not in lines[1329 - 1]:
        print('ABORT: line 1329 unexpected:', repr(lines[1329 - 1]))
        return 1
    if 'return random.choice(topics)' not in lines[1560 - 1]:
        print('ABORT: line 1560 unexpected:', repr(lines[1560 - 1]))
        return 1

    removed = 0
    for start, end in sorted(RANGES, reverse=True):
        del lines[start - 1:end]
        removed += end - start + 1
    print('removed lines =', removed)
    print('after lines =', len(lines))

    with io.open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)
    print('written:', TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())
