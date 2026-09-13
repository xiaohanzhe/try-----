# -*- coding: utf-8 -*-
"""第六轮 · 定点删除 main.py 里的"系统自带主动台词"实现。

用户要求：把系统里自带的对话删了，全权由 AI 接管（10 分钟内最多 1 次自主触发说话）。

删除区间（1-based，含端点），自底向上切以免行号漂移：
  7584..7601   check_interesting_files          （自动跑去"感兴趣文件"并搭话）
  4743..4766   check_weather_response           （每 5 分钟播报天气台词）
  4099..4113   check_excel_table_needs          （办公类硬推销台词）
  3316..3733   check_browser_windows ... check_work_life_balance（17 个办公检查台词）

保留但不再被调度的：无（本脚本只删已确认仅被 check_initiate_dialogue 引用的实现）。
"""
import io
import os
import sys

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', '..', '..', 'ralsei_pet', 'src', 'main.py')
TARGET = os.path.abspath(TARGET)

RANGES = [
    (7584, 7601),
    (4743, 4766),
    (4099, 4113),
    (3316, 3733),
]


def main():
    with io.open(TARGET, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    total = len(lines)
    print('before lines =', total)

    # 安全校验：确认每个区间的首行是预期的 def / 空行锚点
    anchors = {
        7584: 'def check_interesting_files',
        4743: 'def check_weather_response',
        4099: 'def check_excel_table_needs',
        3317: 'def check_browser_windows',
    }
    for start, _end in RANGES:
        for probe, expect in anchors.items():
            if probe == start:
                got = lines[start - 1].strip()
                if expect not in got:
                    print('ABORT: line %d expected %r, got %r' % (start, expect, got))
                    return 1
    # 额外校验：3316 必须是空行（保留上一方法的收尾）
    if lines[3315].strip() != '':
        print('ABORT: line 3316 not blank:', repr(lines[3315]))
        return 1

    removed = 0
    for start, end in sorted(RANGES, reverse=True):
        assert 1 <= start <= end <= len(lines), (start, end)
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
