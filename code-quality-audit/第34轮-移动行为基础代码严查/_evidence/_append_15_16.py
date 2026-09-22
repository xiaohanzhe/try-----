# -*- coding: utf-8 -*-
"""把 §十五/§十六 追加到第34轮报告（用文件拼接，避开 Bash 反引号坑）。"""
import io
import os

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
REPORT = os.path.join(ROOT, '第三十四轮移动行为基础代码严查报告_2026-09-22.md')
APPEND = os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                      '_evidence', '_report_append_15_16.md')

before = io.open(REPORT, encoding='utf-8').read()
add = io.open(APPEND, encoding='utf-8').read()

# 幂等：若已追加过就跳过
if '## 十五、追加范围（用户第 34 轮续指令）' in before:
    print('已存在 §十五，跳过追加')
else:
    merged = before.rstrip('\n') + '\n' + add
    io.open(REPORT, 'w', encoding='utf-8', newline='\n').write(merged)
    print('已追加；新长度 = %d 字符（旧 %d，增 %d）'
          % (len(merged), len(before), len(merged) - len(before)))

after = io.open(REPORT, encoding='utf-8').read()
print('核验：含 §十五 =', '## 十五、追加范围（用户第 34 轮续指令）' in after)
print('核验：含 §十六 =', '## 十六、第 34 轮续 · 方法论追加' in after)
print('核验：含 F34-1 =', 'F34-1' in after)
print('核验：含 1440 =', 'PASS=1440' in after)
print('核验：反引号未被吞（0122 段的示例仍在）=',
      'self._last_desktop_elem_check = current_time' in after)
