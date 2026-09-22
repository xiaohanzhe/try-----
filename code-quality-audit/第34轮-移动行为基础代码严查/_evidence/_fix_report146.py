# -*- coding: utf-8 -*-
"""用文件拼接替换报告里被 Bash 命令替换污染的 14.6 段。"""
import io

REP = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\第三十四轮移动行为基础代码严查报告_2026-09-22.md'
FIX = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence\_fix_146.md'

s = io.open(REP, 'r', encoding='utf-8').read()
fix = io.open(FIX, 'r', encoding='utf-8').read().rstrip() + '\n'

marker = '### 14.6 提交与推送'
i = s.find(marker)
if i < 0:
    print('[FAIL] 未找到标记')
    raise SystemExit(1)

before = s[:i].rstrip() + '\n\n'
after = fix
out = before + after

# 自证：替换后不得再有污染痕迹
bad = ['commit ****', '==  ==', '走 （', '首 3 字节  =']
found = [b for b in bad if b in out]
print('污染痕迹剩余:', found if found else '（无）')
print('新段含关键内容:', all(k in out for k in
      ['8f95f5e', 'origin/main', 'ls-remote', 'extraheader', '231,172,172']))

io.open(REP, 'w', encoding='utf-8', newline='').write(out)
print('报告已修正: %d -> %d chars' % (len(s), len(out)))
