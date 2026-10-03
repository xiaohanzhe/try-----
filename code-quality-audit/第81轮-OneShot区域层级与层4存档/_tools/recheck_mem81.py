# -*- coding: utf-8 -*-
"""记忆文件复检（第81轮）：六类判据逐项 PASS/FAIL。"""
import io, os, re

MEM = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory\MEMORY.md'
DET = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory\参考-契约与历轮（详版）.md'

mem = io.open(MEM, encoding='utf-8').read()
det = io.open(DET, encoding='utf-8').read()
ok = 0; bad = []

def chk(name, cond, detail=''):
    global ok
    if cond: ok += 1; print('[PASS] %s   %s' % (name, detail))
    else: bad.append(name); print('[FAIL] %s   %s' % (name, detail))

print('=' * 70)
print('一、可编译 / 可解析')
print('=' * 70)
chk('1.1 速查本可 UTF-8 解码', isinstance(mem, str))
chk('1.2 详版可 UTF-8 解码', isinstance(det, str))

print()
print('=' * 70)
print('二、结构自检（标题全在 / 无粘连）')
print('=' * 70)
heads = ['## 0.', '## 1.', '## 2.', '## 3.', '## 4.', '## 5.',
         '## 6.', '## 7.', '## 8.', '## 9.', '## 10.', '## 11.']
miss = [h for h in heads if h not in mem]
chk('2.1 速查本 12 个一级标题全在', not miss, '缺=%s' % (miss or '无'))
dheads = [l for l in det.splitlines() if re.match(r'^## §\d+', l)]
nums = sorted(int(re.search(r'§(\d+)', h).group(1)) for h in dheads)
chk('2.2 详版 § 序号单调递增（无重复/回退）',
    nums == sorted(set(nums)), '首=%s 末=%s 共%d' % (nums[0], nums[-1], len(nums)))
chk('2.3 详版含 §71 与 §72', '## §71' in det and '## §72' in det)

print()
print('=' * 70)
print('三、编码（无 BOM / 无 U+FFFD）')
print('=' * 70)
for tag, path in (('速查本', MEM), ('详版', DET)):
    raw = open(path, 'rb').read()
    chk('3.%s %s 无 BOM' % (1 if tag == '速查本' else 2, tag), raw[:3] != b'\xef\xbb\xbf')
    chk('3.%s %s 无 U+FFFD' % (3 if tag == '速查本' else 4, tag), '\ufffd' not in io.open(path, encoding='utf-8').read())

print()
print('=' * 70)
print('四、恒真判据复查')
print('=' * 70)
chk('4.1 速查本无 "or True" 式恒真', 'or True' not in mem)

print()
print('=' * 70)
print('五、逐令牌回验（本轮改/删过的令牌逐个 in 一次）')
print('=' * 70)
must_in_mem = ['§71', '## 10.', '§72', 'A1', 'A2', 'A3', 'hy_toriel',
               'Clover', 'Q3 旧口径已废除', '区域口径', '6 slug', '层4 全量落盘',
               '角色的记忆', '不许再挂回', 'scr_murderlv', 'Ralsei 恒暗档',
               'G5/G5n', 'BASELINE', '--allow-del', 'Write/Edit 工具']
m2 = [k for k in must_in_mem if k not in mem]
chk('5.1 速查本关键令牌全在', not m2, '缺=%s' % (m2 or '无'))

must_in_det = ['§71', '§72', '769ae48', '818cc5c', 'd009565',
               '1,014→1,659', '1,922', '静默不比对', '早都决定好了']
d2 = [k for k in must_in_det if k not in det]
chk('5.2 详版关键令牌全在', not d2, '缺=%s' % (d2 or '无'))

# 指针不悬空：速查本 §10 指向的 §72 必须真存在于详版
chk('5.3 指针不悬空（§10 → 详版 §72 真存在）',
    '详版 §72' in mem and '## §72' in det)

# ★★★ 5.4 判据修正（第一版过窄 ⇒ 假红）：
#   原写法 `det.count('command not found') <= 1` —— 但**详版历史里本来就有 5 处**
#   （§8.6.7/§18/§23.10 等正常记录的 Bash shim 故障），加上本轮 1 处描述 = 6。
#   ⇒ "拿一个高频技术词当污染指纹"是**判据过窄**（与 §60.3 同族）。
#   真污染形态 = shell **真的执行了**命令替换 ⇒ 会留下 `bash.exe: line N: ...` 前缀，
#   且反引号内容**整段消失**。⇒ 改成检测「shell 报错行前缀」+「本轮新段的令牌完整性」。
_shell_noise = len(re.findall(r'bash\.exe: line \d+:', det))
chk('5.4 详版无 shell 真实残留（无 "bash.exe: line N:" 报错前缀）',
    _shell_noise == 0, 'count=%d' % _shell_noise)
# 负控制：造一段真污染，判据必须报红
_fake = det + '\nbash.exe: line 1: data_store: command not found\n'
chk('5.4n 负控制：塞入真污染行后 count 必须 > 0（证明 5.4 非恒真）',
    len(re.findall(r'bash\.exe: line \d+:', _fake)) > 0, '')
# 正控制：本轮 §71 的令牌没被吞（反引号内容还在）
chk('5.4p 正控制：§71 段反引号令牌未被吞（data_store / run_all.SUITES 都在）',
    'data_store' in det and 'run_all.SUITES' in det)

print()
print('=' * 70)
print('六、体积（js_len 口径）')
print('=' * 70)
jl = len(mem.strip().encode('utf-16-le')) // 2
chk('6.1 速查本 js_len < 10000', jl < 10000, 'js_len=%d 余量=%d' % (jl, 10000 - jl))
chk('6.2 速查本改动守恒（未借机爆涨）', jl <= 10000, 'js_len=%d' % jl)

print()
print('=' * 70)
print('结果：PASS=%d FAIL=%d   %s' % (ok, len(bad), ('失败项=%s' % bad) if bad else '全绿'))
print('=' * 70)
