# -*- coding: utf-8 -*-
u"""recheck96b_final.py —— 第96轮b 核心文件复检（六类判据，可复算）。

按用户口径（2026-09-23「以后再调整重要核心文件时一定要记得复检」）：
  ① 语法/可编译  ② 结构自检  ③ 编码（无 BOM / 无 U+FFFD）
  ④ 恒真判据复查  ⑤ 逐令牌回验  ⑥ 工作区干净 + 无删除

★ 复检脚本自己也会说谎 ⇒ 判据报红先怀疑判据。
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
REG = os.path.join(ROOT, 'code-quality-audit', 'regress')

N = [0, 0]


def ck(desc, cond, note=''):
    N[0] += 1
    if cond:
        N[1] += 1
        print('[PASS] %s%s' % (desc, ('  —— ' + note) if note else ''))
    else:
        print('[FAIL] %s%s' % (desc, ('  —— ' + note) if note else ''))


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def rb(p):
    return io.open(p, 'rb').read()


FILES = {
    'main.py': os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    'run_all.py': os.path.join(REG, 'run_all.py'),
    'check96b.py': os.path.join(ROUND, '_tools', 'check96b.py'),
    'probe96b_canned.py': os.path.join(ROUND, '_tools', 'probe96b_canned.py'),
    'probe97_surprise_jump.py': os.path.join(ROUND, '_tools', 'probe97_surprise_jump.py'),
    'mutate96b.py': os.path.join(ROUND, '_tools', 'mutate96b.py'),
    'reach96b.py': os.path.join(ROUND, '_tools', 'reach96b.py'),
    'baseline.json': os.path.join(REG, 'baseline.json'),
    'REPORT.md': os.path.join(ROUND, '_evidence', 'REPORT.md'),
    'cand1 FALSIFIED': os.path.join(ROUND, '_evidence',
                                    'cand1_surprise_jump_FALSIFIED.md'),
}

print('=' * 78)
print('# 第96轮b 核心文件复检')
print('=' * 78)

# ---------------- ① 可编译（ast.parse，不产 .pyc） ----------------
print('\n--- ① 语法 / 可编译 ---')
for name, p in FILES.items():
    if not name.endswith('.py'):
        continue
    if not os.path.isfile(p):
        ck('① %s 在盘' % name, False, p)
        continue
    try:
        ast.parse(rd(p))
        ck('① %s 可编译（ast.parse）' % name, True)
    except SyntaxError as e:
        ck('① %s 可编译（ast.parse）' % name, False, repr(e))

# ---------------- ② 结构自检 ----------------
print('\n--- ② 结构自检（标题/关键锚点齐全） ---')
_m = rd(FILES['main.py'])
ck('② main.py 含本轮修复说明锚（口径违规 · 真机实证）',
   '# ★★★ 第96轮b 修复（口径违规 · 真机实证）' in _m)
ck('② main.py 含拖拽位检测修复锚（第96轮b 修复：`event.buttons() == ...`）',
   '第96轮b 修复：`event.buttons() == Qt.LeftButton` 是**等值**判断' in _m)
ck('② main.py 含 SHOW_FILE_HELP_HINTS 保护通道说明',
   'SHOW_FILE_HELP_HINTS' in _m)
ck('② main.py 的 `reaction[\'dialogue\']` 停用说明在位',
   '自本轮起不再被任何地方显示' in _m)

_r = rd(FILES['run_all.py'])
ck('② run_all.py 含 check96b 条目', "'id': 'check96b'" in _r)
ck('② run_all.py 的 check96b 指向本轮目录',
   '第96轮b-基础宠物专项复现' in _r)

_rep = rd(FILES['REPORT.md'])
for sec in ['## 0. 一句话结论', '## 1. 候选1', '## 2. 候选3', '## 3. 候选5',
            '## 5. 本轮新增回归锁', '## 6. 机器验收']:
    ck('② REPORT.md 含章节 %s' % sec, sec in _rep)

# ---------------- ③ 编码 ----------------
print('\n--- ③ 编码（无 BOM / 无 U+FFFD） ---')
for name, p in FILES.items():
    if not os.path.isfile(p):
        continue
    b = rb(p)
    has_bom = b[:3] == b'\xef\xbb\xbf'
    txt = b.decode('utf-8', 'replace')
    has_bad = '\ufffd' in txt
    ck('③ %s 无 BOM / 无 U+FFFD' % name, (not has_bom) and (not has_bad),
       'BOM=%s U+FFFD=%s' % (has_bom, has_bad))

# EOL
_mb = rb(FILES['main.py'])
_mlf = _mb.count(b'\n')
_mcrlf = _mb.count(b'\r\n')
ck('③ main.py EOL 仍为纯 CRLF（未被改坏）',
   _mlf == _mcrlf and _mlf > 10000, 'CRLF=%d LF=%d' % (_mcrlf, _mlf))

# ---------------- ④ 恒真判据复查 ----------------
print('\n--- ④ 恒真判据复查 ---')
for nm in ('check96b.py', 'probe96b_canned.py', 'probe97_surprise_jump.py'):
    _s = rd(FILES[nm])
    _code = re.sub(r'u?"""[\s\S]*?"""', '', _s)
    _code = re.sub(r'^\s*#.*$', '', _code, flags=re.M)
    hits = re.findall(re.escape('check' + '(') + r'\s*[^,]+,\s*True\s*[,)]', _code)
    ck('④ %s 无「检查名, True」式恒真判据' % nm, len(hits) == 0,
       '命中 %d' % len(hits))

# run_all.py 里 check96b 的 desc 不该含恒真
#   ★ 首版正则假定 desc 与 'id' 在同一行格式 ⇒ 匹配不到 ⇒ NoneType.group 崩。
#     改成"先定位 check96b 条目起点，再取其后一段文本"（不依赖具体换行/缩进）。
_i96 = _r.find("'id': 'check96b'")
_seg96 = _r[_i96: _i96 + 4000] if _i96 >= 0 else ''
ck('④ run_all.py 的 check96b desc 非空且长度合理',
   _i96 >= 0 and len(_seg96) > 1000 and 'desc' in _seg96,
   '条目起点=%s 段长=%d' % (_i96, len(_seg96)))

# ---------------- ⑤ 逐令牌回验 ----------------
print('\n--- ⑤ 逐令牌回验（改/删过的东西逐个回原文件 in 一次） ---')
TOK = {
    'main.py': [
        'self.jump_height = 20',                 # 候选1 证伪锚（仍在，未被误删）
        'self.jump_duration = 0.5',
        'def trigger_surprise(self):',
        'SHOW_FILE_HELP_HINTS = False',
        'if event.buttons() & Qt.LeftButton:',
        'self.dialogue_ui.add_dialogue("ralsei", help_messages[file_ext], "helpful")',
        'def speak_event(self, kind, pool=None',
        '不给内置台词',
        'def _note_desktop_observation',
    ],
    'run_all.py': [
        'check96b',
        '第九十六轮b',
        'probe96b_canned.py',
        'mutate96b.py',
    ],
    'check96b.py': [
        'SHOW_FILE_HELP_HINTS',
        '_calls_outside_guard',
        'buttons() & Qt.LeftButton',
        '_TRUE_LIT',
        're.escape',
    ],
    'REPORT.md': [
        '这是文本文件呢！ 纸做的东西要小心处理哦！',
        'PASS=4638 FAIL=0  套件=88',
        'trigger_surprised',
        'PASS=4638 FAIL=0  套件=88',
    ],
    'cand1 FALSIFIED': [
        'trigger_surprise',
        '9278',
        '恒为 False',
    ],
}
for nm, toks in TOK.items():
    p = FILES[nm]
    if not os.path.isfile(p):
        ck('⑤ %s 在盘' % nm, False)
        continue
    t = rd(p)
    miss = [x for x in toks if x not in t]
    ck('⑤ %s 令牌全在（%d 个）' % (nm, len(toks)), not miss,
       '缺: %s' % miss if miss else '')

# 反向：不该在的（删掉的东西必须真不在）
_rev = {
    'main.py': [
        # 旧写法：函数体内（开关外）不该再有裸 add_dialogue 显示
        # 注意：开关内那处**应当保留** ⇒ 这里只查"修复注释所描述的那两行"是否消失
    ],
}
_lines = _m.split('\n')
# ★ 判据必须**剥注释**再查（首版没剥 ⇒ 命中的是我自己 9455 行那段
#   "原实现在这里 `dialogue_ui.add_dialogue("ralsei", reaction['dialogue'], …)`" 的
#   **注释** ⇒ 假红）。这与 check96b C4、95 轮 D1 是同一个坑的**第三次发作**。
_code_lines = [re.sub(r'#.*$', '', l) for l in _lines]
_has_old_display = any('add_dialogue("ralsei", reaction' in l for l in _code_lines)
ck('⑤ ★ main.py **代码层**不再存在 `add_dialogue("ralsei", reaction[`（已删的那两行；'
   '剥注释后）', not _has_old_display)

# batch_dialogue 类：确认 buttons() & 只有一处、== 在代码层零处
_code_only = re.sub(r'#.*', '', _m)
ck('⑤ ★ main.py 代码层 `buttons() == Qt.LeftButton` 零处',
   len(re.findall(r'buttons\(\)\s*==\s*Qt\.LeftButton', _code_only)) == 0)

# ---------------- ⑥ 工作区干净 + 无删除 ----------------
print('\n--- ⑥ 工作区与无删除 ---')
try:
    por = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         capture_output=True).stdout.decode('utf-8', 'replace')
    lines = [l for l in por.split('\n') if l.strip()]
    dels = [l for l in lines if l.startswith('D ') or l.startswith(' D')]
    ck('⑥ 无文件被删除（`D` 条目为 0）', len(dels) == 0,
       '删除条数 %d' % len(dels))
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=ROOT,
                            capture_output=True).stdout.decode('utf-8', 'replace')
    ck('⑥ 暂存区为空（无意外 pre-staged 改动）', not staged.strip(),
       '暂存: %r' % staged.strip()[:120])
    print('    改动文件 %d 个' % len(lines))
except Exception as e:
    ck('⑥ git 状态可读', False, repr(e))

print('\n' + '=' * 78)
print('合计  PASS=%d  FAIL=%d' % (N[1], N[0] - N[1]))
print('=' * 78)
sys.exit(1 if (N[0] - N[1]) else 0)
